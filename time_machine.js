#!/usr/bin/env node

/**
 * ================================================================================
 * HOOPSIPEDIA TIME MACHINE
 * ================================================================================
 *
 * Predicts hypothetical matchups between any two historical team-seasons.
 * The signature feature of Hoopsipedia — "What if 1972 UCLA played 2015 Kentucky?"
 *
 * Uses our proprietary efficiency engine (adjOE/adjDE per 100 possessions) and
 * HTSS v2 rankings to produce realistic game simulations with predicted scores,
 * win probabilities, matchup breakdowns, and narrative verdicts.
 *
 * Usage:
 *   node time_machine.js "1972 UCLA" "2015 Kentucky"
 *   node time_machine.js "duke 1992" "uconn 2024"
 *   node time_machine.js                              # runs "Greatest Games Never Played" showcase
 *
 * Data sources:
 *   - efficiency_ratings.json  — adjEM, adjOE, adjDE for every team-season
 *   - htss_v2_results.json     — HTSS scores and component breakdowns
 *   - seasons.json             — AP rankings, records, conference, coach
 *   - data.json                — team metadata (H key: names, nicknames, records)
 *   - espn_to_sr.json          — ESPN ID to Sports Reference slug mapping
 */

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// Data Loading
// ---------------------------------------------------------------------------

const BASE = path.dirname(__filename);

/**
 * Load all required data files. We load them synchronously at startup since
 * the CLI needs everything in memory to run any matchup.
 */
function loadData() {
  const efficiency = JSON.parse(fs.readFileSync(path.join(BASE, 'efficiency_ratings.json'), 'utf8'));
  const htss = JSON.parse(fs.readFileSync(path.join(BASE, 'htss_v2_results.json'), 'utf8'));
  const seasons = JSON.parse(fs.readFileSync(path.join(BASE, 'seasons.json'), 'utf8'));
  const data = JSON.parse(fs.readFileSync(path.join(BASE, 'data.json'), 'utf8'));
  const espnToSr = JSON.parse(fs.readFileSync(path.join(BASE, 'espn_to_sr.json'), 'utf8'));
  // Load game data for close-game analysis (fallback for teams outside HTSS top 100)
  const games = {};
  for (const file of ['games_1.json', 'games_2.json', 'games_3.json']) {
    const fp = path.join(BASE, file);
    if (fs.existsSync(fp)) {
      const gd = JSON.parse(fs.readFileSync(fp, 'utf8'));
      for (const [id, entry] of Object.entries(gd)) {
        const arr = entry.games && Array.isArray(entry.games) ? entry.games : (Array.isArray(entry) ? entry : []);
        if (!games[id]) games[id] = [];
        games[id].push(...arr);
      }
    }
  }
  return { efficiency, htss, seasons, data, espnToSr, games };
}

// ---------------------------------------------------------------------------
// Team Name Resolution — Fuzzy Matching
// ---------------------------------------------------------------------------

/**
 * Common abbreviations and nicknames mapped to canonical team names.
 * These let users type "UNC" instead of "North Carolina" etc.
 */
const ABBREVIATIONS = {
  'unc':            'North Carolina',
  'uk':             'Kentucky',
  'uconn':          'UConn',
  'conn':           'UConn',
  'connecticut':    'UConn',
  'nova':           'Villanova',
  'zags':           'Gonzaga',
  'msu':            'Michigan State',
  'osu':            'Ohio State',
  'lsu':            'LSU',
  'usc':            'USC',
  'unlv':           'UNLV',
  'smu':            'SMU',
  'tcu':            'TCU',
  'vcu':            'VCU',
  'fsu':            'Florida State',
  'pitt':           'Pittsburgh',
  'cuse':           'Syracuse',
  'uk':             'Kentucky',
  'cal':            'California',
  'bama':           'Alabama',
  'cincy':          'Cincinnati',
  'ole miss':       'Mississippi',
  'a&m':            'Texas A&M',
  'ku':             'Kansas',
  'iu':             'Indiana',
  'wvu':            'West Virginia',
  'st johns':       "St. John's",
  "st. john's":     "St. John's",
  'georgetown':     'Georgetown',
  'gtown':          'Georgetown',
  'michigan st':    'Michigan State',
  'michigan state': 'Michigan State',
  'nc state':       'North Carolina State',
  'ncsu':           'North Carolina State',
};

/**
 * Parse user input like "1972 UCLA" or "UCLA 1972" or "ucla 1971-72"
 * into { year: "1971-72", teamQuery: "ucla" }
 *
 * We support multiple input formats:
 *   - "1972 UCLA"      → academic year 1971-72 (spring year)
 *   - "UCLA 1972"      → same
 *   - "ucla 1971-72"   → direct season key
 *   - "duke 1992"      → 1991-92
 */
function parseInput(input) {
  input = input.trim();

  // Try to extract a season in "YYYY-YY" format first
  const seasonMatch = input.match(/(\d{4})-(\d{2,4})/);
  if (seasonMatch) {
    const startYear = parseInt(seasonMatch[1]);
    const endYearStr = seasonMatch[2];
    const endYear = endYearStr.length === 2
      ? parseInt(endYearStr) + Math.floor(startYear / 100) * 100
      : parseInt(endYearStr);
    const seasonKey = `${startYear}-${String(endYear).slice(-2)}`;
    const teamQuery = input.replace(seasonMatch[0], '').trim();
    return { seasonKey, springYear: endYear, teamQuery };
  }

  // Otherwise, look for a 4-digit year
  const yearMatch = input.match(/\b(\d{4})\b/);
  if (!yearMatch) {
    throw new Error(`Could not find a year in "${input}". Use format like "1972 UCLA" or "UCLA 1972".`);
  }

  const year = parseInt(yearMatch[1]);
  const teamQuery = input.replace(yearMatch[0], '').trim();

  // The year could be the spring year (how most people think of seasons)
  // or the fall year. We treat it as the spring year (tournament year).
  // So "1972 UCLA" means the 1971-72 season.
  const springYear = year;
  const fallYear = year - 1;
  const seasonKey = `${fallYear}-${String(springYear).slice(-2)}`;

  return { seasonKey, springYear, teamQuery };
}

/**
 * Resolve a team query string to an ESPN team ID.
 * Uses fuzzy matching against team full names, nicknames, and SR slugs.
 *
 * Strategy:
 * 1. Check abbreviation map
 * 2. Exact match on full name or nickname
 * 3. Partial match (contains)
 * 4. Match against SR slugs
 */
function resolveTeam(teamQuery, data, espnToSr) {
  const query = teamQuery.toLowerCase().trim();

  // Check abbreviation map first
  const abbr = ABBREVIATIONS[query];
  const searchTerms = abbr ? [abbr.toLowerCase(), query] : [query];

  const H = data.H;
  const entries = Object.entries(H);

  for (const term of searchTerms) {
    // Exact match on full name (minus mascot suffix)
    for (const [id, arr] of entries) {
      const fullName = arr[0].toLowerCase();       // "Duke Blue Devils"
      const nickname = arr[1].toLowerCase();        // "Blue Devils"
      const schoolName = fullName.replace(` ${nickname}`, ''); // "Duke"

      if (schoolName === term || fullName === term) {
        return { espnId: id, fullName: arr[0], nickname: arr[1], conference: arr[2], color: arr[3] };
      }
    }

    // Partial / contains match — prefer shorter names (more specific)
    const partialMatches = [];
    for (const [id, arr] of entries) {
      const fullName = arr[0].toLowerCase();
      const nickname = arr[1].toLowerCase();
      const schoolName = fullName.replace(` ${nickname}`, '');

      if (schoolName.includes(term) || term.includes(schoolName)) {
        partialMatches.push({ id, arr, score: Math.abs(schoolName.length - term.length) });
      }
    }

    if (partialMatches.length > 0) {
      // Sort by closest length match (most specific)
      partialMatches.sort((a, b) => a.score - b.score);
      const best = partialMatches[0];
      return { espnId: best.id, fullName: best.arr[0], nickname: best.arr[1], conference: best.arr[2], color: best.arr[3] };
    }

    // Match against Sports Reference slugs
    for (const [espnId, slug] of Object.entries(espnToSr)) {
      if (slug === term || slug.replace(/-/g, ' ') === term) {
        if (H[espnId]) {
          const arr = H[espnId];
          return { espnId, fullName: arr[0], nickname: arr[1], conference: arr[2], color: arr[3] };
        }
      }
    }
  }

  throw new Error(`Could not find team matching "${teamQuery}". Try using the full school name (e.g., "Duke", "North Carolina", "UConn").`);
}

// ---------------------------------------------------------------------------
// Era Pace Estimation
// ---------------------------------------------------------------------------

/**
 * Historical average possessions per game by era.
 * College basketball pace has varied significantly — the 1950s were fast,
 * the 2010s were slow, and the shot clock changes shaped everything.
 */
function getEraPace(springYear) {
  if (springYear < 1965) return 78;
  if (springYear <= 1985) return 73;
  if (springYear <= 1993) return 70;
  if (springYear <= 2007) return 67;
  if (springYear <= 2015) return 65;
  return 67; // 2016+ saw slight pace increase
}

// ---------------------------------------------------------------------------
// Core Prediction Engine
// ---------------------------------------------------------------------------

/**
 * Gather all available data for a specific team-season from our various sources.
 * Returns a unified profile object with efficiency, HTSS, season, and metadata.
 */
function buildTeamProfile(espnId, seasonKey, springYear, teamInfo, db) {
  const profile = {
    espnId,
    seasonKey,
    springYear,
    fullName: teamInfo.fullName,
    nickname: teamInfo.nickname,
    conference: teamInfo.conference,
    color: teamInfo.color,
    // These will be populated below
    adjOE: null,
    adjDE: null,
    adjEM: null,
    record: null,
    coach: null,
    htss: null,
    htssRank: null,
    htssComponents: null,
    apRank: null,
    seed: null,
    tourneyResult: null,
    eraPace: getEraPace(springYear),
  };

  // --- Efficiency data ---
  const seasonData = db.efficiency.seasons[seasonKey];
  if (seasonData && seasonData[espnId]) {
    const eff = seasonData[espnId];
    profile.adjOE = eff.adjOE;
    profile.adjDE = eff.adjDE;
    profile.adjEM = eff.adjEM;
    profile.record = eff.record;
    profile.sos = eff.sos;
    profile.effRank = eff.rank;
  }

  // --- HTSS data ---
  // First check allTimeTop100 for full component breakdowns
  const top100Entry = db.htss.allTimeTop100.find(
    e => e.season === seasonKey && e.team === teamInfo.fullName
  );
  if (top100Entry) {
    profile.htss = top100Entry.htss;
    profile.htssRank = top100Entry.rank;
    profile.htssComponents = top100Entry.components;
    profile.coach = profile.coach || top100Entry.coach;
    profile.tourneyResult = top100Entry.tourneyResult;
  }

  // Also check byTeam for HTSS score (covers teams outside top 100)
  if (!profile.htss && db.htss.byTeam[espnId]) {
    const teamEntry = db.htss.byTeam[espnId].find(e => e.season === seasonKey);
    if (teamEntry) {
      profile.htss = teamEntry.htss;
      profile.htssRank = teamEntry.rank;
    }
  }

  // --- Compute close-game stats directly from game data (fallback when not in top 100) ---
  if (!profile.htssComponents?.closeGame && db.games[espnId]) {
    const games = db.games[espnId];
    let closeWins = 0, closeLosses = 0, clutchWins = 0, clutchLosses = 0;
    for (const g of games) {
      if (!g.date || g.pts == null || g.opp_pts == null) continue;
      const [yr, mo] = g.date.split('-').map(Number);
      const gameSeason = mo >= 10 ? yr : yr - 1;
      const gameSeasonKey = `${gameSeason}-${String(gameSeason + 1).slice(2).padStart(2, '0')}`;
      if (gameSeasonKey !== seasonKey) continue;
      const margin = Math.abs(g.pts - g.opp_pts);
      const won = g.w === true || g.pts > g.opp_pts;
      if (margin <= 5) { won ? closeWins++ : closeLosses++; }
      if (margin <= 3) { won ? clutchWins++ : clutchLosses++; }
    }
    const closeTotal = closeWins + closeLosses;
    if (closeTotal >= 1) {
      const priorWeight = 2;
      const smoothedClose = (closeWins + priorWeight * 0.5) / (closeTotal + priorWeight);
      const clutchTotal = clutchWins + clutchLosses;
      const smoothedClutch = clutchTotal > 0
        ? (clutchWins + priorWeight * 0.5) / (clutchTotal + priorWeight)
        : smoothedClose;
      const rawScore = smoothedClose * 0.6 + smoothedClutch * 0.4;
      // Approximate z-score (era mean ~0.5, std ~0.15)
      const zScore = (rawScore - 0.5) / 0.15;
      if (!profile.htssComponents) profile.htssComponents = {};
      profile.htssComponents.closeGame = Math.round(zScore * 1000) / 1000;
    }
  }

  // --- Season data (AP rankings, coach, tourney info) ---
  if (db.seasons[espnId]) {
    const teamSeasons = db.seasons[espnId].seasons;
    if (teamSeasons) {
      const seasonEntry = teamSeasons.find(s => s.year === seasonKey);
      if (seasonEntry) {
        profile.record = profile.record || seasonEntry.record;
        profile.coach = profile.coach || seasonEntry.coach;
        profile.apRank = seasonEntry.apFinal || seasonEntry.apHigh || seasonEntry.apPre || null;
        profile.seed = seasonEntry.seed || null;
        profile.tourneyResult = profile.tourneyResult || seasonEntry.ncaaTourney || null;
        profile.ppg = seasonEntry.ppg;
        profile.oppPpg = seasonEntry.oppPpg;
      }
    }
  }

  return profile;
}

/**
 * The core prediction algorithm.
 *
 * Takes two team profiles and simulates a hypothetical neutral-site game.
 *
 * The math:
 * 1. Average both teams' era paces → simulated possessions
 * 2. Combine each team's offense vs opponent's defense (log5-style)
 * 3. Scale to actual points via pace
 * 4. Win probability via logistic model (calibrated to real CBB variance)
 * 5. Generate realistic final score with slight randomness
 */
function predictGame(profileA, profileB) {
  // Validate we have efficiency data for both teams
  if (!profileA.adjOE || !profileB.adjOE) {
    const missing = !profileA.adjOE ? profileA.fullName : profileB.fullName;
    throw new Error(`Missing efficiency data for ${missing} (${profileA.seasonKey || profileB.seasonKey}). Cannot simulate.`);
  }

  // Step 1: Neutral pace — average of both teams' era pace
  const simPossessions = (profileA.eraPace + profileB.eraPace) / 2;

  // Step 2: Predict scoring efficiency
  // This is the "log5" approach: if Team A's offense is X points above average
  // and Team B's defense is Y points below average, the combined effect is X+Y-baseline.
  const BASELINE = 100; // Average D-I team scores ~100 pts per 100 possessions

  const teamAOff = profileA.adjOE + profileB.adjDE - BASELINE;
  const teamBOff = profileB.adjOE + profileA.adjDE - BASELINE;

  // Step 3: Convert efficiency to actual points using simulated pace
  const teamARawPts = teamAOff * (simPossessions / 100);
  const teamBRawPts = teamBOff * (simPossessions / 100);

  // Step 4: Win probability via logistic model
  // The ~11-point standard deviation of CBB outcomes means we divide by ~4.5
  // to calibrate: a 10-point favorite wins ~90% of the time.
  const pointDiff = teamARawPts - teamBRawPts;
  const winProbA = 1 / (1 + Math.exp(-pointDiff / 4.5));
  const winProbB = 1 - winProbA;

  // Step 5: Generate a realistic final score
  // Add slight randomness (±2 pts) but keep the margin intact
  const jitterA = (Math.random() - 0.5) * 4; // ±2
  const jitterB = (Math.random() - 0.5) * 4; // ±2

  let scoreA = Math.round(teamARawPts + jitterA);
  let scoreB = Math.round(teamBRawPts + jitterB);

  // Ensure scores are reasonable — floor at 40, cap at 120
  scoreA = Math.max(40, Math.min(120, scoreA));
  scoreB = Math.max(40, Math.min(120, scoreB));

  // Determine winner — if margin is < 3, it's basically a coin flip
  // but we still pick based on win probability
  let winner, loser, winnerScore, loserScore;
  const margin = Math.abs(scoreA - scoreB);

  if (margin < 3) {
    // Coin-flip game: use win probability to decide
    const coinFlip = Math.random();
    if (coinFlip < winProbA) {
      winner = 'A';
    } else {
      winner = 'B';
    }
    // Make sure the winner's score is higher
    if (winner === 'A' && scoreA <= scoreB) {
      scoreA = scoreB + Math.ceil(Math.random() * 3);
    } else if (winner === 'B' && scoreB <= scoreA) {
      scoreB = scoreA + Math.ceil(Math.random() * 3);
    }
  } else {
    winner = scoreA > scoreB ? 'A' : 'B';
  }

  return {
    simPossessions: Math.round(simPossessions),
    teamAOff: round2(teamAOff),
    teamBOff: round2(teamBOff),
    teamARawPts: round2(teamARawPts),
    teamBRawPts: round2(teamBRawPts),
    scoreA,
    scoreB,
    pointDiff: round2(pointDiff),
    winProbA: round2(winProbA * 100),
    winProbB: round2(winProbB * 100),
    winner, // 'A' or 'B'
    margin: Math.abs(scoreA - scoreB),
  };
}

// ---------------------------------------------------------------------------
// Matchup Analysis — Key Factors
// ---------------------------------------------------------------------------

/**
 * Analyze the matchup across multiple dimensions and identify key edges.
 * This produces the "MATCHUP BREAKDOWN" section of the output.
 */
function analyzeMatchup(profileA, profileB, prediction) {
  const factors = [];

  // --- Offense ---
  const offDiff = round2(profileA.adjOE - profileB.adjOE);
  const offEdge = offDiff > 1 ? profileA.fullName : offDiff < -1 ? profileB.fullName : 'Even';
  factors.push({
    name: 'Offense',
    teamA: `${round1(profileA.adjOE)} adjOE`,
    teamB: `${round1(profileB.adjOE)} adjOE`,
    edge: offEdge,
    diff: offDiff > 0 ? `+${round1(Math.abs(offDiff))}` : round1(Math.abs(offDiff)) !== 0 ? `-${round1(Math.abs(offDiff))}` : 'Even',
    edgeSide: offDiff > 1 ? 'A' : offDiff < -1 ? 'B' : null,
  });

  // --- Defense (lower adjDE = better) ---
  const defDiff = round2(profileA.adjDE - profileB.adjDE);
  // Negative defDiff means A has better defense
  const defEdge = defDiff < -1 ? profileA.fullName : defDiff > 1 ? profileB.fullName : 'Even';
  factors.push({
    name: 'Defense',
    teamA: `${round1(profileA.adjDE)} adjDE`,
    teamB: `${round1(profileB.adjDE)} adjDE`,
    edge: defEdge,
    diff: defDiff < 0 ? `${round1(Math.abs(defDiff))}` : `-${round1(Math.abs(defDiff))}`,
    edgeSide: defDiff < -1 ? 'A' : defDiff > 1 ? 'B' : null,
  });

  // --- Pace ---
  const paceNote = profileA.eraPace !== profileB.eraPace
    ? `Compromise between eras (${profileA.eraPace} vs ${profileB.eraPace})`
    : 'Same era pace';
  // The team from the faster era might be disadvantaged at slower pace
  const paceFavors = profileA.eraPace > profileB.eraPace ? profileB.fullName
    : profileA.eraPace < profileB.eraPace ? profileA.fullName : 'Neutral';
  factors.push({
    name: 'Pace',
    teamA: `${profileA.eraPace} era avg`,
    teamB: `${profileB.eraPace} era avg`,
    edge: paceFavors,
    diff: `${prediction.simPossessions} simulated`,
    edgeSide: profileA.eraPace > profileB.eraPace ? 'B' : profileA.eraPace < profileB.eraPace ? 'A' : null,
    note: paceNote,
  });

  // --- Coaching ---
  const coachA = profileA.coach || 'Unknown';
  const coachB = profileB.coach || 'Unknown';
  const coachPrestigeA = profileA.htssComponents ? profileA.htssComponents.coaching : null;
  const coachPrestigeB = profileB.htssComponents ? profileB.htssComponents.coaching : null;
  let coachEdge = 'N/A';
  let coachEdgeSide = null;
  if (coachPrestigeA != null && coachPrestigeB != null) {
    coachEdge = coachPrestigeA > coachPrestigeB ? profileA.fullName
      : coachPrestigeB > coachPrestigeA ? profileB.fullName : 'Even';
    coachEdgeSide = coachPrestigeA > coachPrestigeB ? 'A' : coachPrestigeB > coachPrestigeA ? 'B' : null;
  }
  factors.push({
    name: 'Coaching',
    teamA: coachA,
    teamB: coachB,
    edge: coachEdge,
    edgeSide: coachEdgeSide,
  });

  // --- Talent (draft production from HTSS components) ---
  const draftA = profileA.htssComponents ? profileA.htssComponents.draft : null;
  const draftB = profileB.htssComponents ? profileB.htssComponents.draft : null;
  let talentEdge = 'N/A';
  let talentEdgeSide = null;
  if (draftA != null && draftB != null) {
    talentEdge = draftA > draftB ? profileA.fullName
      : draftB > draftA ? profileB.fullName : 'Even';
    talentEdgeSide = draftA > draftB ? 'A' : draftB > draftA ? 'B' : null;
  }
  factors.push({
    name: 'Talent',
    teamA: draftA != null ? `Draft score: ${round1(draftA)}` : 'N/A',
    teamB: draftB != null ? `Draft score: ${round1(draftB)}` : 'N/A',
    edge: talentEdge,
    edgeSide: talentEdgeSide,
  });

  // --- Close-Game Resilience (clutch factor from HTSS) ---
  const clutchA = profileA.htssComponents ? profileA.htssComponents.closeGame : null;
  const clutchB = profileB.htssComponents ? profileB.htssComponents.closeGame : null;
  let clutchEdge = 'N/A';
  let clutchEdgeSide = null;
  if (clutchA != null && clutchB != null) {
    clutchEdge = clutchA > clutchB ? profileA.fullName
      : clutchB > clutchA ? profileB.fullName : 'Even';
    clutchEdgeSide = clutchA > clutchB ? 'A' : clutchB > clutchA ? 'B' : null;
  }
  factors.push({
    name: 'Clutch',
    teamA: clutchA != null ? `${round1(clutchA)}` : 'N/A',
    teamB: clutchB != null ? `${round1(clutchB)}` : 'N/A',
    edge: clutchEdge,
    edgeSide: clutchEdgeSide,
  });

  // --- HTSS Overall ---
  if (profileA.htss && profileB.htss) {
    const htssEdge = profileA.htss > profileB.htss ? profileA.fullName : profileB.fullName;
    factors.push({
      name: 'HTSS',
      teamA: `${round1(profileA.htss)} (#${profileA.htssRank || '?'})`,
      teamB: `${round1(profileB.htss)} (#${profileB.htssRank || '?'})`,
      edge: htssEdge,
      edgeSide: profileA.htss > profileB.htss ? 'A' : 'B',
    });
  }

  return factors;
}

// ---------------------------------------------------------------------------
// Narrative Generation
// ---------------------------------------------------------------------------

/**
 * Generate a compelling one-to-two sentence narrative explaining why the
 * predicted result makes sense. This is the "VERDICT" section.
 *
 * We build the narrative dynamically based on the actual matchup factors
 * rather than using canned templates. The narrative references specific
 * advantages and tells a story about how the game would unfold.
 */
function generateNarrative(profileA, profileB, prediction, factors) {
  const winner = prediction.winner === 'A' ? profileA : profileB;
  const loser = prediction.winner === 'A' ? profileB : profileA;
  const margin = prediction.margin;
  const winnerShort = getShortName(winner.fullName);
  const loserShort = getShortName(loser.fullName);
  const winnerYear = winner.springYear;
  const loserYear = loser.springYear;

  // Identify the winner's key advantages
  const winnerSide = prediction.winner;
  const winnerEdges = factors
    .filter(f => f.edgeSide === winnerSide && f.name !== 'HTSS')
    .map(f => f.name.toLowerCase());
  const loserSide = winnerSide === 'A' ? 'B' : 'A';
  const loserEdges = factors
    .filter(f => f.edgeSide === loserSide && f.name !== 'HTSS')
    .map(f => f.name.toLowerCase());

  // Build advantage descriptions
  const winnerAdvStr = describeAdvantages(winner, winnerEdges);
  const loserAdvStr = describeAdvantages(loser, loserEdges);

  // Categorize the game
  if (margin >= 10) {
    // Blowout
    return `${winnerYear} ${winnerShort}'s ${winnerAdvStr} would overwhelm ${loserYear} ${loserShort} in a convincing victory. ${loserEdges.length > 0 ? `${loserYear} ${loserShort}'s ${loserAdvStr} ${loserEdges.length === 1 ? 'isn\'t' : 'aren\'t'} enough to overcome the gap in overall quality.` : `The talent and efficiency gap is simply too wide to overcome.`}`;
  } else if (margin >= 5) {
    // Comfortable win
    return `${winnerYear} ${winnerShort}'s ${winnerAdvStr} ${winnerEdges.length === 1 ? 'gives' : 'give'} them the edge in a competitive but ultimately decisive game. ${loserEdges.length > 0 ? `${loserYear} ${loserShort}'s ${loserAdvStr} ${loserEdges.length === 1 ? 'keeps' : 'keep'} it interesting, but ${winnerShort} pulls away down the stretch.` : `${loserYear} ${loserShort} battles hard but can\'t match ${winnerShort}\'s firepower.`}`;
  } else {
    // Nail-biter
    return `This one goes down to the wire — ${winnerYear} ${winnerShort} barely edges ${loserYear} ${loserShort} in an instant classic. ${loserEdges.length > 0 ? `${loserYear} ${loserShort}'s ${loserAdvStr} nearly ${loserEdges.length === 1 ? 'steals' : 'steal'} the game, but ${winnerShort}'s ${winnerAdvStr} ${winnerEdges.length === 1 ? 'proves' : 'prove'} decisive in the final minutes.` : `Both teams trade blows, but ${winnerShort} makes one more play when it matters most.`}`;
  }
}

/**
 * Turn a list of advantage categories into a readable string.
 * e.g., ["offense", "coaching"] → "dominant offense and elite coaching"
 */
function describeAdvantages(profile, edges) {
  const descriptions = {
    offense: 'elite offense',
    defense: 'suffocating defense',
    pace: 'pace advantage',
    coaching: `${profile.coach || 'coaching'} pedigree`,
    talent: 'NBA-caliber talent',
    clutch: 'close-game toughness',
  };

  if (edges.length === 0) return 'overall balance';

  const parts = edges.map(e => descriptions[e] || e);
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return parts.slice(0, -1).join(', ') + ', and ' + parts[parts.length - 1];
}

/**
 * Extract the school name from the full name (e.g., "Duke Blue Devils" → "Duke")
 */
function getShortName(fullName) {
  // Handle special cases
  const specials = {
    'UConn Huskies': 'UConn',
    'UNLV Rebels': 'UNLV',
    'LSU Tigers': 'LSU',
    'USC Trojans': 'USC',
    'SMU Mustangs': 'SMU',
    'TCU Horned Frogs': 'TCU',
    'VCU Rams': 'VCU',
    'UCF Knights': 'UCF',
    'UCLA Bruins': 'UCLA',
    'BYU Cougars': 'BYU',
  };
  if (specials[fullName]) return specials[fullName];

  // General case: everything before the last word (mascot)
  // But handle multi-word mascots: "Blue Devils", "Tar Heels", etc.
  const parts = fullName.split(' ');
  // Try removing common mascot patterns from the end
  const mascots = [
    'Wildcats', 'Tigers', 'Bulldogs', 'Eagles', 'Bears', 'Cougars',
    'Panthers', 'Hawks', 'Wolverines', 'Spartans', 'Hoosiers', 'Boilermakers',
    'Hawkeyes', 'Jayhawks', 'Mountaineers', 'Cavaliers', 'Volunteers',
    'Crimson Tide', 'Blue Devils', 'Tar Heels', 'Demon Deacons',
    'Fighting Irish', 'Nittany Lions', 'Golden Gophers', 'Scarlet Knights',
    'Cardinal', 'Bruins', 'Huskies', 'Ducks', 'Beavers', 'Trojans',
    'Rebels', 'Razorbacks', 'Aggies', 'Longhorns', 'Seminoles',
    'Hurricanes', 'Commodores', 'Colonels', 'Hilltoppers',
    'Horned Frogs', 'Mustangs', 'Rams', 'Knights', 'Gaels',
    'Friars', 'Musketeers', 'Bearcats', 'Red Storm', 'Peacocks',
    'Orange', 'Orangemen', 'Terrapins', 'Terps', 'Badgers',
    'Buckeyes', 'Sooners', 'Cowboys', 'Miners', 'Zags',
  ];

  for (const mascot of mascots) {
    if (fullName.endsWith(` ${mascot}`)) {
      return fullName.replace(` ${mascot}`, '');
    }
  }

  // Fallback: return first word
  return parts[0];
}

// ---------------------------------------------------------------------------
// Console Output Formatting
// ---------------------------------------------------------------------------

/**
 * Format and print the full matchup result to the console.
 * Uses box-drawing characters and careful alignment for a premium feel.
 */
function printMatchup(profileA, profileB, prediction, factors, narrative) {
  const divider = '='.repeat(80);
  const shortA = getShortName(profileA.fullName);
  const shortB = getShortName(profileB.fullName);

  // When both teams are the same school (e.g., 1982 UNC vs 2017 UNC),
  // prefix short names with year so the output isn't ambiguous.
  const sameSchool = shortA === shortB;
  const labelA = sameSchool ? `'${String(profileA.springYear).slice(-2)} ${shortA}` : shortA;
  const labelB = sameSchool ? `'${String(profileB.springYear).slice(-2)} ${shortB}` : shortB;

  console.log('');
  console.log(divider);
  console.log(`  TIME MACHINE: ${profileA.springYear} ${shortA} vs ${profileB.springYear} ${shortB}`);
  console.log(divider);
  console.log('');

  // Team headers — side by side
  const leftHeader = `${profileA.seasonKey} ${profileA.fullName} (${profileA.record || '?'})`;
  const rightHeader = `${profileB.seasonKey} ${profileB.fullName} (${profileB.record || '?'})`;
  console.log(`  ${padRight(leftHeader, 40)}  vs  ${rightHeader}`);

  const leftCoach = `Coach: ${profileA.coach || 'Unknown'}`;
  const rightCoach = `Coach: ${profileB.coach || 'Unknown'}`;
  console.log(`  ${padRight(leftCoach, 44)}${rightCoach}`);

  // HTSS line
  const leftHtss = profileA.htss
    ? `HTSS: ${round1(profileA.htss)} (#${profileA.htssRank || '?'} All-Time)`
    : 'HTSS: N/A';
  const rightHtss = profileB.htss
    ? `HTSS: ${round1(profileB.htss)} (#${profileB.htssRank || '?'} All-Time)`
    : 'HTSS: N/A';
  console.log(`  ${padRight(leftHtss, 44)}${rightHtss}`);

  // AP rank line
  const leftAP = profileA.apRank ? `AP: #${profileA.apRank}` : 'AP: NR';
  const rightAP = profileB.apRank ? `AP: #${profileB.apRank}` : 'AP: NR';
  console.log(`  ${padRight(leftAP, 44)}${rightAP}`);

  // Efficiency rank
  const leftEff = profileA.effRank ? `Eff. Rank: #${profileA.effRank}` : '';
  const rightEff = profileB.effRank ? `Eff. Rank: #${profileB.effRank}` : '';
  if (leftEff || rightEff) {
    console.log(`  ${padRight(leftEff, 44)}${rightEff}`);
  }

  console.log('');

  // Predicted score — use year-prefixed labels for same-school matchups
  const winnerLabel = prediction.winner === 'A' ? labelA : labelB;
  const loserLabel = prediction.winner === 'A' ? labelB : labelA;
  const winnerScore = prediction.winner === 'A' ? prediction.scoreA : prediction.scoreB;
  const loserScore = prediction.winner === 'A' ? prediction.scoreB : prediction.scoreA;
  const winProbW = prediction.winner === 'A' ? prediction.winProbA : prediction.winProbB;
  const winProbL = prediction.winner === 'A' ? prediction.winProbB : prediction.winProbA;

  console.log(`  PREDICTED SCORE: ${winnerLabel} ${winnerScore}, ${loserLabel} ${loserScore}`);
  console.log(`  Win Probability: ${winnerLabel} ${Math.round(winProbW)}% | ${loserLabel} ${Math.round(winProbL)}%`);

  console.log('');
  console.log(`  MATCHUP BREAKDOWN:`);

  // Print each factor with proper column alignment
  // Dynamically size columns based on longest label + stat combination
  const COL_W = Math.max(28, labelA.length + 18, labelB.length + 18);
  for (const f of factors) {
    // Build edge string, with year prefix for same-school matchups
    let edgeStr = '';
    if (f.edge && f.edge !== 'N/A' && f.edge !== 'Even' && f.edge !== 'Neutral') {
      const edgeShort = getShortName(f.edge);
      if (sameSchool) {
        // Figure out which side has the edge to add year prefix
        const edgeYear = f.edgeSide === 'A' ? profileA.springYear : profileB.springYear;
        edgeStr = `  Edge: '${String(edgeYear).slice(-2)} ${edgeShort}`;
      } else {
        edgeStr = `  Edge: ${edgeShort}`;
      }
    } else if (f.edge === 'Even' || f.edge === 'Neutral') {
      edgeStr = '  Even';
    }

    if (f.name === 'Pace') {
      console.log(`    ${padRight(f.name + ':', 12)}${f.diff} (${f.note})`);
    } else {
      const leftVal = padRight(labelA + ' ' + f.teamA, COL_W);
      const rightVal = padRight(labelB + ' ' + f.teamB, COL_W);
      console.log(`    ${padRight(f.name + ':', 12)}${leftVal}vs  ${rightVal}${edgeStr}`);
    }
  }

  // Word-wrap the verdict to ~76 chars for readability
  console.log('');
  const verdictLines = wordWrap(`VERDICT: ${narrative}`, 74);
  for (const line of verdictLines) {
    console.log(`  ${line}`);
  }
  console.log(divider);
  console.log('');
}

// ---------------------------------------------------------------------------
// Main Orchestration
// ---------------------------------------------------------------------------

/**
 * Run a single matchup between two team-season strings.
 * Returns the full result object (for JSON export) and prints to console.
 */
function runMatchup(inputA, inputB, db, { silent = false } = {}) {
  // Parse inputs
  const parsedA = parseInput(inputA);
  const parsedB = parseInput(inputB);

  // Resolve teams
  const teamA = resolveTeam(parsedA.teamQuery, db.data, db.espnToSr);
  const teamB = resolveTeam(parsedB.teamQuery, db.data, db.espnToSr);

  // Build profiles
  const profileA = buildTeamProfile(teamA.espnId, parsedA.seasonKey, parsedA.springYear, teamA, db);
  const profileB = buildTeamProfile(teamB.espnId, parsedB.seasonKey, parsedB.springYear, teamB, db);

  // Validate we have data
  if (!profileA.adjOE) {
    throw new Error(
      `No efficiency data found for ${profileA.fullName} in ${parsedA.seasonKey}. ` +
      `Our data covers 1949-50 through 2025-26. Check the team name and year.`
    );
  }
  if (!profileB.adjOE) {
    throw new Error(
      `No efficiency data found for ${profileB.fullName} in ${parsedB.seasonKey}. ` +
      `Our data covers 1949-50 through 2025-26. Check the team name and year.`
    );
  }

  // Predict the game
  const prediction = predictGame(profileA, profileB);

  // Analyze matchup factors
  const factors = analyzeMatchup(profileA, profileB, prediction);

  // Generate narrative
  const narrative = generateNarrative(profileA, profileB, prediction, factors);

  // Print to console
  if (!silent) {
    printMatchup(profileA, profileB, prediction, factors, narrative);
  }

  // Return structured result for JSON export
  return {
    matchup: `${parsedA.springYear} ${getShortName(profileA.fullName)} vs ${parsedB.springYear} ${getShortName(profileB.fullName)}`,
    teamA: {
      name: profileA.fullName,
      season: profileA.seasonKey,
      record: profileA.record,
      coach: profileA.coach,
      adjOE: profileA.adjOE,
      adjDE: profileA.adjDE,
      adjEM: profileA.adjEM,
      htss: profileA.htss,
      htssRank: profileA.htssRank,
      apRank: profileA.apRank,
    },
    teamB: {
      name: profileB.fullName,
      season: profileB.seasonKey,
      record: profileB.record,
      coach: profileB.coach,
      adjOE: profileB.adjOE,
      adjDE: profileB.adjDE,
      adjEM: profileB.adjEM,
      htss: profileB.htss,
      htssRank: profileB.htssRank,
      apRank: profileB.apRank,
    },
    prediction: {
      winner: prediction.winner === 'A' ? profileA.fullName : profileB.fullName,
      winnerScore: prediction.winner === 'A' ? prediction.scoreA : prediction.scoreB,
      loserScore: prediction.winner === 'A' ? prediction.scoreB : prediction.scoreA,
      scoreA: prediction.scoreA,
      scoreB: prediction.scoreB,
      winProbA: prediction.winProbA,
      winProbB: prediction.winProbB,
      margin: prediction.margin,
      simPossessions: prediction.simPossessions,
    },
    factors: factors.map(f => ({
      name: f.name,
      edge: f.edge,
      teamA: f.teamA,
      teamB: f.teamB,
    })),
    narrative,
  };
}

/**
 * "Greatest Games Never Played" — the 10 showcase matchups that demonstrate
 * the Time Machine's power. Run when no CLI arguments are provided.
 */
function runShowcase(db) {
  const showcaseMatchups = [
    ['1972 UCLA',           '2015 Kentucky'],
    ['1976 Indiana',        '2024 UConn'],
    ['1992 Duke',           '1996 Kentucky'],
    ['2018 Villanova',      '2008 Kansas'],
    ['1968 UCLA',           '2021 Gonzaga'],
    ['1973 UCLA',           '1976 Indiana'],
    ['2019 Virginia',       '1985 Villanova'],
    ['1982 North Carolina', '2017 North Carolina'],
    ['1991 UNLV',           '2024 UConn'],
    ['2026 Michigan',       '1989 Michigan'],
  ];

  console.log('');
  console.log('='.repeat(80));
  console.log('  HOOPSIPEDIA TIME MACHINE — Greatest Games Never Played');
  console.log('  10 hypothetical matchups across 75+ years of college basketball');
  console.log('='.repeat(80));

  const results = [];

  for (let i = 0; i < showcaseMatchups.length; i++) {
    const [a, b] = showcaseMatchups[i];
    console.log(`\n  Game ${i + 1} of ${showcaseMatchups.length}`);
    try {
      const result = runMatchup(a, b, db);
      results.push(result);
    } catch (err) {
      console.error(`  ERROR: ${err.message}`);
      results.push({ matchup: `${a} vs ${b}`, error: err.message });
    }
  }

  // Write results to JSON
  const outputPath = path.join(BASE, 'time_machine_results.json');
  const output = {
    generated: new Date().toISOString(),
    description: 'Hoopsipedia Time Machine — Greatest Games Never Played',
    algorithm: 'Efficiency-based neutral-site simulation with era-adjusted pace and logistic win probability',
    matchups: results,
  };

  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`\n  Results written to ${outputPath}`);
  console.log('');

  return results;
}

// ---------------------------------------------------------------------------
// Utility Functions
// ---------------------------------------------------------------------------

function round1(n) { return n != null ? Math.round(n * 10) / 10 : null; }
function round2(n) { return n != null ? Math.round(n * 100) / 100 : null; }

function padRight(str, len) {
  str = String(str);
  while (str.length < len) str += ' ';
  return str;
}

/**
 * Word-wrap a string to a given max line width, breaking on spaces.
 */
function wordWrap(text, maxWidth) {
  const words = text.split(' ');
  const lines = [];
  let current = '';
  for (const word of words) {
    if (current.length + word.length + 1 > maxWidth && current.length > 0) {
      lines.push(current);
      current = word;
    } else {
      current = current ? current + ' ' + word : word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

// ---------------------------------------------------------------------------
// CLI Entry Point
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);

  // Handle --help before loading data (faster response)
  if (args.length === 1 && args[0] === '--help') {
    printHelp();
    return;
  }

  const db = loadData();

  if (args.length === 0) {
    // No arguments: run the showcase
    runShowcase(db);
  } else if (args.length === 2) {
    // Two arguments: single matchup
    try {
      runMatchup(args[0], args[1], db);
    } catch (err) {
      console.error(`\n  ERROR: ${err.message}\n`);
      process.exit(1);
    }
  } else {
    console.error('\n  Usage: node time_machine.js "YEAR TEAM" "YEAR TEAM"');
    console.error('         node time_machine.js                            (runs showcase)');
    console.error('         node time_machine.js --help                     (show help)\n');
    console.error('  Examples:');
    console.error('    node time_machine.js "1972 UCLA" "2015 Kentucky"');
    console.error('    node time_machine.js "duke 1992" "uconn 2024"\n');
    process.exit(1);
  }
}

function printHelp() {
  console.log(`
  HOOPSIPEDIA TIME MACHINE
  ========================
  Predict hypothetical matchups between any two historical team-seasons.

  USAGE:
    node time_machine.js "YEAR TEAM" "YEAR TEAM"    Run a single matchup
    node time_machine.js                             Run "Greatest Games Never Played" showcase
    node time_machine.js --help                      Show this help

  INPUT FORMATS:
    "1972 UCLA"         Year + team name (year = tournament/spring year)
    "UCLA 1972"         Team name + year
    "ucla 1971-72"      Full season key format
    "duke 1992"         Case-insensitive

  TEAM NAME SHORTCUTS:
    UNC, UK, UConn, Nova, Zags, MSU, OSU, LSU, Bama, Cincy, KU, IU, etc.

  EXAMPLES:
    node time_machine.js "1972 UCLA" "2015 Kentucky"
    node time_machine.js "duke 1992" "uconn 2024"
    node time_machine.js "indiana 1976" "gonzaga 2021"
    node time_machine.js "unc 1982" "unc 2017"

  DATA COVERAGE:
    1949-50 through 2025-26 (77 seasons, 367 teams)
  `);
}

main();
