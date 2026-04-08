#!/usr/bin/env node
/**
 * ============================================================================
 * HISTORICAL TEAM-SEASON SCORE (HTSS) ALGORITHM — v2.0
 * ============================================================================
 *
 * Hoopsipedia Proprietary Algorithm — v2.0
 *
 * Major upgrade from v1: Replaces Sports Reference SRS dependency with our
 * proprietary efficiency engine (adjEM, adjOE, adjDE, tier records, SOS).
 * Adds 4 new components: Quality Record Profile, Close-Game Resilience,
 * Coaching Prestige, and NBA Draft Production.
 *
 * 9 Components (including Era Difficulty bonus):
 *   1. Adjusted Efficiency (30%) — adjEM from our engine
 *   2. Strength of Schedule (12%) — sos from our engine
 *   3. Tournament Performance (18%) — discrete achievement points
 *   4. Quality Record Profile (10%) — tier records from our engine
 *   5. Peak Perception (10%) — AP poll rankings
 *   6. Close-Game Resilience (5%) — win% in close/OT games
 *   7. Coaching Prestige (5%) — coach career accomplishments
 *   8. NBA Draft Production (5%) — future draft picks on roster
 *   9. Era Difficulty Multiplier (5%) — NIL/portal era boost
 *
 * Scale interpretation:
 *   50  = Average D-I team-season
 *   60-65 = Good (top ~40 nationally)
 *   65-70 = Very good (conference contender)
 *   70-75 = Elite (top 10 nationally, deep tournament run)
 *   75-80 = All-time great (Final Four caliber, dominant margins)
 *   80-85 = Transcendent (undefeated or near-undefeated champion)
 *   85+   = GOAT tier
 *
 * Author: Hoopsipedia (Josh Davis)
 * Created: 2026-04-07
 * ============================================================================
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const BASE = __dirname;

// ─────────────────────────────────────────────────────────────────────────────
// 1. LOAD DATA — ensure efficiency_ratings.json exists, then load everything
// ─────────────────────────────────────────────────────────────────────────────

const efficiencyPath = path.join(BASE, 'efficiency_ratings.json');
if (!fs.existsSync(efficiencyPath)) {
  console.log('efficiency_ratings.json not found. Running efficiency engine...');
  execSync('node ' + path.join(BASE, 'efficiency_engine.js'), { stdio: 'inherit' });
}

console.log('HTSS Algorithm v2.0 — Hoopsipedia');
console.log('='.repeat(80));
console.log('Loading data...');
console.time('Data loading');

const efficiencyData = JSON.parse(fs.readFileSync(efficiencyPath, 'utf-8'));
const seasonsData     = JSON.parse(fs.readFileSync(path.join(BASE, 'seasons.json'), 'utf-8'));
const mainData        = JSON.parse(fs.readFileSync(path.join(BASE, 'data.json'), 'utf-8'));
const draftData       = JSON.parse(fs.readFileSync(path.join(BASE, 'draft_history.json'), 'utf-8'));

// Game data — loaded lazily for close-game analysis
const gamesData = {};
for (const file of ['games_1.json', 'games_2.json', 'games_3.json']) {
  const fp = path.join(BASE, file);
  if (fs.existsSync(fp)) {
    const data = JSON.parse(fs.readFileSync(fp, 'utf-8'));
    for (const [espnId, entry] of Object.entries(data)) {
      if (!gamesData[espnId]) gamesData[espnId] = [];
      const games = entry.games && Array.isArray(entry.games) ? entry.games : (Array.isArray(entry) ? entry : []);
      gamesData[espnId].push(...games);
    }
  }
}

const teamInfo  = mainData.H;        // espnId -> [name, nickname, conf, color, ...stats]
const coaches   = mainData.COACHES;   // espnId -> array of coach stints
const coachLB   = mainData.COACH_LB;  // array of top 100 coaches (ordered by career wins)

// Efficiency engine output: seasons keyed by "YYYY-YY" -> { espnId -> { adjEM, adjOE, adjDE, sos, tiers, ... } }
const effSeasons = efficiencyData.seasons;

console.timeEnd('Data loading');
console.log(`  Efficiency seasons: ${Object.keys(effSeasons).length}`);
console.log(`  Teams in seasons.json: ${Object.keys(seasonsData).length}`);
console.log(`  Teams with game data: ${Object.keys(gamesData).length}`);
console.log(`  Teams with draft data: ${Object.keys(draftData).length}`);

// ─────────────────────────────────────────────────────────────────────────────
// 1b. DETECT AND EXCLUDE DUPLICATE/CLONE TEAMS
// ─────────────────────────────────────────────────────────────────────────────
// Identical to v1: fingerprint-based + conference-mismatch detection.

function detectCloneTeams() {
  const cloneIds = new Set();

  // Method 1: Fingerprint identical season records
  const fingerprints = {};
  for (const id of Object.keys(seasonsData)) {
    const seasons = seasonsData[id]?.seasons;
    if (!seasons || seasons.length < 3) continue;
    const fp = seasons.slice(0, Math.min(10, seasons.length))
      .map(x => x.year + ':' + x.wins + '-' + x.losses).join('|');
    if (!fingerprints[fp]) fingerprints[fp] = [];
    fingerprints[fp].push(id);
  }

  for (const [, ids] of Object.entries(fingerprints)) {
    if (ids.length > 1) {
      const sorted = ids
        .map(id => ({ id, wins: teamInfo[id]?.[4] || 0 }))
        .sort((a, b) => b.wins - a.wins);
      for (let i = 1; i < sorted.length; i++) {
        cloneIds.add(sorted[i].id);
      }
    }
  }

  // Method 2: Conference mismatch — mid-major team with major conf seasons data
  const MAJOR_CONFS = new Set([
    'ACC', 'SEC', 'Big Ten', 'Big 12', 'Big East', 'Pac-12', 'AAC', 'WCC', 'MWC', 'American'
  ]);

  for (const id of Object.keys(seasonsData)) {
    if (cloneIds.has(id)) continue;
    const info = teamInfo[id];
    if (!info) continue;
    const dataConf = info[2];
    const seasons = seasonsData[id]?.seasons;
    if (!seasons || seasons.length < 3) continue;

    const recentConfs = seasons.slice(0, 3).map(x => x.conf).filter(Boolean);
    if (recentConfs.length === 0 || !dataConf) continue;

    const allRecentMajor = recentConfs.every(c => MAJOR_CONFS.has(c));
    const dataMajor = MAJOR_CONFS.has(dataConf);

    if (allRecentMajor && !dataMajor) {
      cloneIds.add(id);
    }
  }

  return cloneIds;
}

const CLONE_IDS = detectCloneTeams();
console.log(`  Clone teams excluded: ${CLONE_IDS.size}`);

// ─────────────────────────────────────────────────────────────────────────────
// 2. ERA DEFINITIONS — v2 uses 6 eras (split Pre-Shot Clock into 2)
// ─────────────────────────────────────────────────────────────────────────────
// Each boundary corresponds to a documented rule change that altered the
// statistical distribution of the game.
//
// Pre-Modern:      Before 1965 — No shot clock until 1985 in college,
//                  but the game was fundamentally different pre-integration.
// Integration Era: 1965-1985 — Game opens up, talent pool expands.
// Early Modern:    1986-1993 — 45-sec shot clock + 3-point line (1986-87).
// Mid Modern:      1994-2007 — 35-sec shot clock (1993-94).
// Late Modern:     2008-2015 — 3-point line extended (2008). Analytics begin.
// Current:         2016-present — 30-sec shot clock (2015-16).

const ERAS = [
  { name: 'Pre-Modern',       start: 0,    end: 1964 },
  { name: 'Integration Era',  start: 1965, end: 1985 },
  { name: 'Early Modern',     start: 1986, end: 1993 },
  { name: 'Mid Modern',       start: 1994, end: 2007 },
  { name: 'Late Modern',      start: 2008, end: 2015 },
  { name: 'Current',          start: 2016, end: 9999 },
];

/**
 * Parse season year string to the calendar year the season ENDS in.
 * "2024-25" -> 2025, "1975-76" -> 1976, "1999-00" -> 2000
 */
function getSeasonEndYear(yearStr) {
  const parts = yearStr.split('-');
  if (parts.length === 2) {
    const startYear = parseInt(parts[0]);
    const endSuffix = parseInt(parts[1]);
    if (endSuffix < 50 && startYear >= 1950) return startYear + 1;
    if (endSuffix > 50) return parseInt(parts[0].substring(0, 2) + parts[1]);
    return startYear + 1;
  }
  return parseInt(yearStr);
}

/** Get the start year from a season string. "2024-25" -> 2024 */
function getSeasonStartYear(yearStr) {
  return parseInt(yearStr.split('-')[0]);
}

function getEra(yearStr) {
  const endYear = getSeasonEndYear(yearStr);
  for (const era of ERAS) {
    if (endYear >= era.start && endYear <= era.end) return era;
  }
  return ERAS[0];
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. TOURNAMENT FIELD SIZE BY YEAR
// ─────────────────────────────────────────────────────────────────────────────
// Normalizes tournament achievement by the number of rounds required to win.

function getTournamentFieldSize(yearStr) {
  const endYear = getSeasonEndYear(yearStr);
  if (endYear <= 1950) return 8;
  if (endYear <= 1952) return 16;
  if (endYear <= 1974) return 25;   // varied 22-25
  if (endYear <= 1978) return 32;
  if (endYear <= 1984) return 48;   // varied 40-53
  if (endYear <= 2000) return 64;
  if (endYear <= 2010) return 65;
  return 68; // First Four era (2011+)
}

const MODERN_FIELD_SIZE = 68;

// ─────────────────────────────────────────────────────────────────────────────
// 4. TOURNAMENT RESULT PARSER
// ─────────────────────────────────────────────────────────────────────────────
// Maps the ncaaTourney string from seasons.json to discrete achievement points.
//
// Point values:
//   Championship:       15.0  — Winning it all
//   Runner-up:           8.0  — Reached the final
//   Final Four:          5.0  — Top 4
//   Elite Eight:         3.0  — Regional champion
//   Sweet Sixteen:       1.5  — Won weekend 1 + weekend 2 opener
//   Round of 32:         0.5  — Won first-round game
//   First round loss:   -0.5  — Made tournament, lost immediately
//   Did not make:       -2.0  — Missed the tournament entirely

function parseTournamentResult(ncaaTourney) {
  if (!ncaaTourney) return { round: 'none', points: -2.0 };

  const s = ncaaTourney.replace(/\*/g, '');

  if (s.includes('Won NCAA Tournament National Final'))
    return { round: 'champion', points: 15.0 };
  if (s.includes('Lost NCAA Tournament National Final'))
    return { round: 'runner_up', points: 8.0 };
  if (s.includes('National Semifinal') || s.includes('Regional Final (Final Four)'))
    return { round: 'final_four', points: 5.0 };
  if (s.includes('Regional Final'))
    return { round: 'elite_eight', points: 3.0 };
  if (s.includes('Regional Semifinal') || s.includes('Third Round'))
    return { round: 'sweet_sixteen', points: 1.5 };
  if (s.includes('Second Round'))
    return { round: 'round_of_32', points: 0.5 };
  if (s.includes('First Round') || s.includes('First Four') || s.includes('Opening Round'))
    return { round: 'first_round', points: -0.5 };
  if (s.includes('Playing'))
    return { round: 'in_progress', points: 0.0 };
  if (s.includes('Regional Third Place'))
    return { round: 'final_four', points: 5.0 };  // Pre-1982 3rd place game = Final Four

  return { round: 'unknown_tourney', points: 0.0 };
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. COACH LOOKUP UTILITIES
// ─────────────────────────────────────────────────────────────────────────────
// Build a lookup of coach name -> COACH_LB entry for prestige scoring.
// Also build a set of "Hall of Fame proxy" coaches (top 50 in career wins).

const coachLBMap = {};       // lowercase coach name -> COACH_LB entry
const hofCoachNames = new Set(); // top 50 coaches by career wins (HOF proxy)

if (coachLB && Array.isArray(coachLB)) {
  for (let i = 0; i < coachLB.length; i++) {
    const c = coachLB[i];
    coachLBMap[c.name.toLowerCase()] = c;
    if (i < 50) hofCoachNames.add(c.name.toLowerCase());
  }
}

/**
 * Find the coach for a given team-season.
 * Checks seasons.json coach field first, then falls back to COACHES array.
 * Returns { name, careerWins, careerPct, isHOF } or null.
 */
function getCoachInfo(espnId, yearStr, seasonCoachName) {
  // The season-level coach name from seasons.json
  let coachName = seasonCoachName;

  // If no coach name from seasons.json, look up from COACHES array
  if (!coachName && coaches[espnId]) {
    const endYear = getSeasonEndYear(yearStr);
    const startYear = getSeasonStartYear(yearStr);
    for (const stint of coaches[espnId]) {
      // stint.start and stint.end are calendar years of coaching tenure
      if (startYear >= stint.start - 1 && endYear <= stint.end + 1) {
        coachName = stint.name;
        break;
      }
    }
  }

  if (!coachName) return null;

  // Look up in coach leaderboard for career stats
  const lbEntry = coachLBMap[coachName.toLowerCase()];

  return {
    name: coachName,
    careerWins: lbEntry ? lbEntry.wins : null,
    careerPct: lbEntry ? lbEntry.pct : null,
    isHOF: hofCoachNames.has(coachName.toLowerCase()),
    // Approximate career wins at time of season:
    // If the coach's career ended in yearsEnd, we can interpolate.
    // careerWinsAtSeason = careerWins * (seasonYear - yearsStart) / (yearsEnd - yearsStart)
    careerWinsAtSeason: lbEntry ? estimateWinsAtSeason(lbEntry, yearStr) : null,
  };
}

/**
 * Estimate a coach's career win total at the time of a given season.
 * Uses linear interpolation across their career span.
 * This is approximate — coaches don't win at a constant rate — but it's
 * a reasonable proxy for distinguishing "young Coach K" from "prime Coach K".
 */
function estimateWinsAtSeason(lbEntry, yearStr) {
  const seasonEnd = getSeasonEndYear(yearStr);
  const careerSpan = lbEntry.yearsEnd - lbEntry.yearsStart;
  if (careerSpan <= 0) return lbEntry.wins;

  const yearsIn = Math.max(0, Math.min(seasonEnd - lbEntry.yearsStart, careerSpan));
  return Math.round(lbEntry.wins * (yearsIn / careerSpan));
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. CLOSE-GAME ANALYSIS
// ─────────────────────────────────────────────────────────────────────────────
// Pre-compute close-game records for every team-season from raw game data.
// A "close game" is decided by 5 or fewer points. "Clutch" is 3 or fewer.

console.log('\nPre-computing close-game records...');
console.time('Close-game analysis');

/**
 * Map a game date to a season key: "2024-11-15" -> "2024-25"
 */
function dateToSeasonKey(dateStr) {
  const [y, m] = dateStr.split('-').map(Number);
  const startYear = m < 6 ? y - 1 : y;
  const endYear = startYear + 1;
  return `${startYear}-${String(endYear).slice(2).padStart(2, '0')}`;
}

// closeGameRecords[espnId][seasonKey] = { closeWins, closeLosses, clutchWins, clutchLosses, otWins, otLosses }
const closeGameRecords = {};

for (const [espnId, games] of Object.entries(gamesData)) {
  if (!closeGameRecords[espnId]) closeGameRecords[espnId] = {};

  for (const g of games) {
    if (!g.date || g.pts == null || g.opp_pts == null) continue;

    const seasonKey = dateToSeasonKey(g.date);
    if (!closeGameRecords[espnId][seasonKey]) {
      closeGameRecords[espnId][seasonKey] = {
        closeWins: 0, closeLosses: 0,     // decided by <= 5 pts
        clutchWins: 0, clutchLosses: 0,    // decided by <= 3 pts
        otWins: 0, otLosses: 0,            // overtime games
      };
    }

    const rec = closeGameRecords[espnId][seasonKey];
    const margin = Math.abs(g.pts - g.opp_pts);
    const won = g.w === true || g.pts > g.opp_pts;

    // Detect overtime: if the game's margin is small relative to the score
    // and it's in the game data. We check if there's an OT indicator,
    // or infer from the score pattern (scores that end above typical regulation total).
    // Since we don't have an explicit OT flag, we use a heuristic:
    // games where both teams scored above era-average AND margin is tiny
    // are likely OT. But this is unreliable, so we'll only count games
    // where margin is 0 in regulation (i.e., tied at end of regulation).
    // Actually — in our data, the final score already includes OT.
    // We can't distinguish OT from regulation with this data alone.
    // So we'll proxy OT as: margin <= 3 AND total points are unusually high.
    // Better approach: just skip OT detection and weight close/clutch only.

    if (margin <= 5) {
      if (won) rec.closeWins++;
      else rec.closeLosses++;
    }
    if (margin <= 3) {
      if (won) rec.clutchWins++;
      else rec.clutchLosses++;
    }
    // OT proxy: margin exactly 1-3 with combined score > 150 suggests OT
    // (typical D-I game is ~130-140 combined; OT adds ~10-15).
    // This is rough but better than nothing.
    if (margin <= 3 && (g.pts + g.opp_pts) > 150) {
      if (won) rec.otWins++;
      else rec.otLosses++;
    }
  }
}

console.timeEnd('Close-game analysis');

// ─────────────────────────────────────────────────────────────────────────────
// 7. NBA DRAFT PRODUCTION PRE-COMPUTATION
// ─────────────────────────────────────────────────────────────────────────────
// For each team-season, count draft picks produced within 3 years.
// draft_history.json has notablePicks[] with year, name, pick, round.
// A pick from draft year Y is associated with seasons Y-3 through Y-1
// (the player was on the roster 1-3 years before being drafted).

console.log('Pre-computing draft production...');

// draftProduction[espnId][seasonKey] = { lotteryPicks, firstRoundPicks, secondRoundPicks, totalScore }
const draftProduction = {};

for (const [espnId, draftEntry] of Object.entries(draftData)) {
  if (!draftEntry.notablePicks || !Array.isArray(draftEntry.notablePicks)) continue;
  if (!draftProduction[espnId]) draftProduction[espnId] = {};

  for (const pick of draftEntry.notablePicks) {
    if (!pick.year || !pick.round) continue;

    // This pick was drafted in pick.year. The player was likely on the roster
    // during seasons ending in pick.year (their final season) through
    // pick.year - 2 (if they stayed 3 years). We credit all those seasons.
    for (let offset = 0; offset < 3; offset++) {
      const seasonEndYear = pick.year - offset;
      // Convert to season key: endYear 2015 -> "2014-15"
      const startYear = seasonEndYear - 1;
      const endSuffix = String(seasonEndYear).slice(2).padStart(2, '0');
      const seasonKey = `${startYear}-${endSuffix}`;

      if (!draftProduction[espnId][seasonKey]) {
        draftProduction[espnId][seasonKey] = { lottery: 0, firstRound: 0, secondRound: 0, score: 0 };
      }

      const dp = draftProduction[espnId][seasonKey];

      // Scoring: lottery (top 14) = 3x, first round = 2x, second round = 1x
      if (pick.round === 1 && pick.pick <= 14) {
        dp.lottery++;
        dp.score += 3;
      } else if (pick.round === 1) {
        dp.firstRound++;
        dp.score += 2;
      } else {
        dp.secondRound++;
        dp.score += 1;
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. BUILD ALL TEAM-SEASON RECORDS
// ─────────────────────────────────────────────────────────────────────────────
// Flatten every team-season into a unified record with all available fields,
// now enriched with efficiency engine data + new components.

function buildAllSeasons() {
  const allSeasons = [];

  for (const espnId of Object.keys(seasonsData)) {
    if (CLONE_IDS.has(espnId)) continue;

    const teamSeasons = seasonsData[espnId].seasons;
    if (!teamSeasons || !Array.isArray(teamSeasons)) continue;

    const info = teamInfo[espnId];
    const teamName = info ? info[0] : `Unknown (${espnId})`;

    for (const season of teamSeasons) {
      const endYear = getSeasonEndYear(season.year);
      const era = getEra(season.year);
      const tourney = parseTournamentResult(season.ncaaTourney);

      // ── Efficiency engine data ──
      // Look up this team-season in efficiency_ratings.json
      const effSeason = effSeasons[season.year]?.[espnId];
      const adjEM = effSeason?.adjEM ?? null;
      const adjOE = effSeason?.adjOE ?? null;
      const adjDE = effSeason?.adjDE ?? null;
      const effSOS = effSeason?.sos ?? null;

      // Tier records from efficiency engine
      const tiers = effSeason?.tiers ?? null;

      // ── Quality Record Profile score ──
      // Score = (T1_wins * 4 + T2_wins * 2 + T3_wins * 0.5) - (T1_losses * 0 + T2_losses * 1 + T3_losses * 2 + T4_losses * 4)
      // Rewards elite wins, punishes bad losses (selection committee logic)
      let qualityRecordScore = null;
      if (tiers) {
        qualityRecordScore = (
          (tiers.t1w || 0) * 4 +
          (tiers.t2w || 0) * 2 +
          (tiers.t3w || 0) * 0.5
        ) - (
          (tiers.t1l || 0) * 0 +     // Losses to Tier 1 = no penalty (expected)
          (tiers.t2l || 0) * 1 +      // Losses to Tier 2 = mild penalty
          (tiers.t3l || 0) * 2 +      // Losses to Tier 3 = moderate penalty
          (tiers.t4l || 0) * 4         // Losses to Tier 4 = severe penalty (bad loss)
        );
      }

      // ── Close-game resilience ──
      const cgr = closeGameRecords[espnId]?.[season.year];
      let closeGameScore = null;
      if (cgr) {
        const closeTotal = cgr.closeWins + cgr.closeLosses;
        const clutchTotal = cgr.clutchWins + cgr.clutchLosses;
        if (closeTotal >= 1) {
          // Weighted combination of close-game win% and clutch-game win%
          // Close (<=5): 60% weight, Clutch (<=3): 40% weight
          const closeWinPct = cgr.closeWins / closeTotal;
          const clutchWinPct = clutchTotal > 0 ? cgr.clutchWins / clutchTotal : closeWinPct;
          // Bayesian smoothing: blend with 50% prior, weighted by sample size
          // This prevents 1-0 = 1.000 or 0-1 = 0.000 from being extreme outliers
          const priorWeight = 2; // equivalent to 2 imaginary games at 50%
          const smoothedClose = (cgr.closeWins + priorWeight * 0.5) / (closeTotal + priorWeight);
          const smoothedClutch = clutchTotal > 0
            ? (cgr.clutchWins + priorWeight * 0.5) / (clutchTotal + priorWeight)
            : smoothedClose;
          closeGameScore = smoothedClose * 0.6 + smoothedClutch * 0.4;
        }
      }

      // ── Coaching prestige ──
      const coachInfo = getCoachInfo(espnId, season.year, season.coach);
      let coachPrestigeScore = null;
      if (coachInfo) {
        // Score based on:
        // - Career wins at time of season (0-50 scale, normalized later)
        // - Career win% (0-1 scale)
        // - HOF bonus (top 50 all-time in wins)
        let score = 0;
        if (coachInfo.careerWinsAtSeason != null) {
          // Normalize career wins: 500+ wins is elite
          score += Math.min(coachInfo.careerWinsAtSeason / 500, 1.5) * 2.0;
        }
        if (coachInfo.careerPct != null) {
          // Win% contribution: 75%+ is elite
          score += (coachInfo.careerPct / 100) * 1.5;
        }
        if (coachInfo.isHOF) {
          score += 1.0; // HOF proxy bonus
        }
        coachPrestigeScore = score;
      }

      // ── NBA Draft Production ──
      const dp = draftProduction[espnId]?.[season.year];
      const draftScore = dp ? dp.score : 0;

      allSeasons.push({
        espnId,
        teamName,
        year: season.year,
        endYear,
        era: era.name,

        // Basic record
        wins: season.wins || 0,
        losses: season.losses || 0,
        winPct: season.winPct || 0,
        record: `${season.wins || 0}-${season.losses || 0}`,

        // Conference
        conf: season.conf || null,
        confWinPct: season.confWinPct != null ? season.confWinPct : null,
        confWins: season.confWins || 0,
        confLosses: season.confLosses || 0,

        // Efficiency engine data (NEW in v2)
        adjEM,
        adjOE,
        adjDE,
        effSOS,

        // Quality record (NEW in v2)
        tiers,
        qualityRecordScore,

        // AP Poll
        apPre: season.apPre != null ? season.apPre : null,
        apHigh: season.apHigh != null ? season.apHigh : null,
        apFinal: season.apFinal != null ? season.apFinal : null,

        // Tournament
        ncaaTourney: season.ncaaTourney || null,
        seed: season.seed != null ? season.seed : null,
        tourneyRound: tourney.round,
        tourneyPoints: tourney.points,
        fieldSize: getTournamentFieldSize(season.year),

        // Close-game resilience (NEW in v2)
        closeGameScore,

        // Coach
        coach: coachInfo?.name || season.coach || null,
        coachPrestigeScore,

        // Draft production (NEW in v2)
        draftScore,

        // Old SRS/SOS from Sports Reference (kept for v1 comparison)
        srs: season.srs != null ? season.srs : null,
        srSOS: season.sos != null ? season.sos : null,
      });
    }
  }

  return allSeasons;
}

// ─────────────────────────────────────────────────────────────────────────────
// 9. Z-SCORE CALCULATION UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Compute mean and standard deviation for an array of numbers.
 * Ignores null/undefined/NaN values.
 */
function meanAndStd(values) {
  const valid = values.filter(v => v != null && !isNaN(v));
  if (valid.length === 0) return { mean: 0, std: 1 };

  const mean = valid.reduce((a, b) => a + b, 0) / valid.length;
  const variance = valid.reduce((a, b) => a + (b - mean) ** 2, 0) / valid.length;
  const std = Math.sqrt(variance);

  return { mean, std: std > 0 ? std : 1.0 };
}

function zScore(value, stats) {
  if (value == null || isNaN(value)) return null;
  return (value - stats.mean) / stats.std;
}

/**
 * Capped z-score: prevents any single component from producing absurd
 * values (e.g., draft score of 6 in an era where mean=0.02, std=0.28
 * would give z=21, which would dominate the composite).
 *
 * Cap at ±3.5 standard deviations — still allows differentiation among
 * truly elite teams, but prevents statistical artifacts from skewing rankings.
 */
const Z_CAP = 3.5;
function zScoreCapped(value, stats) {
  const z = zScore(value, stats);
  if (z == null) return null;
  return Math.max(-Z_CAP, Math.min(Z_CAP, z));
}

// ─────────────────────────────────────────────────────────────────────────────
// 10. COMPUTE ERA STATISTICS
// ─────────────────────────────────────────────────────────────────────────────
// For each era, compute mean/std of every metric we need for z-scoring.

function computeEraStats(allSeasons) {
  const eraGroups = {};
  for (const s of allSeasons) {
    if (!eraGroups[s.era]) eraGroups[s.era] = [];
    eraGroups[s.era].push(s);
  }

  const eraStats = {};

  for (const [eraName, seasons] of Object.entries(eraGroups)) {
    eraStats[eraName] = {
      count: seasons.length,

      // Component 1: Adjusted Efficiency
      adjEM: meanAndStd(seasons.map(s => s.adjEM)),

      // Component 2: Strength of Schedule
      effSOS: meanAndStd(seasons.map(s => s.effSOS)),

      // Component 4: Quality Record Profile
      qualityRecordScore: meanAndStd(seasons.map(s => s.qualityRecordScore)),

      // Component 5: AP ranks (inverted during scoring)
      apHigh: meanAndStd(seasons.filter(s => s.apHigh != null).map(s => s.apHigh)),
      apFinal: meanAndStd(seasons.filter(s => s.apFinal != null).map(s => s.apFinal)),

      // Component 6: Close-game resilience
      closeGameScore: meanAndStd(seasons.map(s => s.closeGameScore)),

      // Component 7: Coaching prestige
      coachPrestigeScore: meanAndStd(seasons.map(s => s.coachPrestigeScore)),

      // Component 8: Draft production
      draftScore: meanAndStd(seasons.map(s => s.draftScore)),

      // Fallback stats (for when efficiency data is unavailable)
      winPct: meanAndStd(seasons.map(s => s.winPct)),
      srs: meanAndStd(seasons.map(s => s.srs)),
      srSOS: meanAndStd(seasons.map(s => s.srSOS)),
      confWinPct: meanAndStd(seasons.map(s => s.confWinPct)),
    };
  }

  return eraStats;
}

// ─────────────────────────────────────────────────────────────────────────────
// 11. HTSS v2 COMPONENT CALCULATIONS
// ─────────────────────────────────────────────────────────────────────────────
// Each function returns a z-score-scale value (mean ~0, std ~1 within era).

/**
 * COMPONENT 1: ADJUSTED EFFICIENCY (30% weight)
 *
 * The single most important predictor of team quality. Our proprietary adjEM
 * from efficiency_engine.js captures pace-adjusted, opponent-adjusted margin
 * of victory. This replaces the old SRS + Win% + Margin "Dominance" component.
 *
 * When adjEM is unavailable (team not in efficiency engine), we fall back to
 * SRS from Sports Reference, then to win% + scoring margin.
 *
 * Bonuses:
 *   - Undefeated with 20+ wins: +0.3 base + 0.015 per win beyond 20
 *   - One loss with 28+ wins: +0.15
 *   These prevent the z-score ceiling from undervaluing perfect records.
 */
function computeAdjustedEfficiency(season, stats) {
  let base;

  const zEM = zScoreCapped(season.adjEM, stats.adjEM);
  if (zEM != null) {
    // Primary: use our efficiency engine's adjEM
    base = zEM;
  } else {
    // Fallback: SRS from Sports Reference
    const zSRS = zScoreCapped(season.srs, stats.srs);
    const zWinPct = zScoreCapped(season.winPct, stats.winPct);
    if (zSRS != null && zWinPct != null) {
      base = zSRS * 0.65 + zWinPct * 0.35;
    } else if (zWinPct != null) {
      base = zWinPct;
    } else {
      return 0;
    }
  }

  // Undefeated bonus: Going 32-0 is harder than raw z-score captures
  if (season.winPct >= 1.0 && season.wins >= 20) {
    base += 0.3 + (season.wins - 20) * 0.015;
  }
  // One-loss bonus for dominant seasons
  else if (season.losses === 1 && season.wins >= 28) {
    base += 0.15;
  }

  return base;
}

/**
 * COMPONENT 2: STRENGTH OF SCHEDULE (12% weight)
 *
 * Uses the SOS metric from our efficiency engine (average opponent adjEM).
 * This is more meaningful than Sports Reference SOS because it's based on
 * our own efficiency ratings rather than simple margin-based SRS.
 *
 * Falls back to SR SOS, then conference win% proxy.
 */
function computeSOS(season, stats) {
  // Primary: our efficiency engine's SOS
  const zSOS = zScoreCapped(season.effSOS, stats.effSOS);
  if (zSOS != null) {
    // Mild bonus for very high SOS (playing all killers)
    const qualityBonus = zSOS > 1.0 ? (zSOS - 1.0) * 0.1 : 0;
    return Math.min(zSOS + qualityBonus, Z_CAP);
  }

  // Fallback: Sports Reference SOS
  const zSrSOS = zScoreCapped(season.srSOS, stats.srSOS);
  if (zSrSOS != null) {
    return zSrSOS * 0.8; // slight discount — it's the old metric
  }

  // Last resort: conference win% as rough proxy
  const zConfWP = zScoreCapped(season.confWinPct, stats.confWinPct);
  if (zConfWP != null) {
    return zConfWP * 0.3;
  }

  return 0;
}

/**
 * COMPONENT 3: TOURNAMENT PERFORMANCE (18% weight)
 *
 * Discrete achievement points, era-adjusted by tournament field size.
 * Identical logic to v1 but with updated weight (18% vs 20%).
 *
 * Era adjustment: scale by log2(modern_field) / log2(era_field).
 * A championship in a 16-team field (4 rounds) is scaled relative to
 * winning in a 68-team field (~6 rounds).
 */
function computeTournament(season) {
  if (season.tourneyRound === 'in_progress') return 0;

  // Don't penalize current season teams that haven't played tournament yet
  if (season.tourneyRound === 'none' && season.endYear >= 2026) return 0;

  const rawPoints = season.tourneyPoints;

  const eraFieldLog = Math.log2(Math.max(season.fieldSize, 2));
  const modernFieldLog = Math.log2(MODERN_FIELD_SIZE);

  let adjustedPoints;
  if (rawPoints > 0) {
    // Positive achievements scaled up for modern era (more rounds to win)
    adjustedPoints = rawPoints * (modernFieldLog / eraFieldLog);
  } else if (rawPoints < 0) {
    // Penalties reduced for smaller fields (fewer teams could make it)
    adjustedPoints = rawPoints * (eraFieldLog / modernFieldLog);
  } else {
    adjustedPoints = 0;
  }

  // Normalize: modern champion = 1.0
  return adjustedPoints / 15.0;
}

/**
 * COMPONENT 4: QUALITY RECORD PROFILE (10% weight) — NEW IN v2
 *
 * Uses tier records from our efficiency engine to evaluate WHO a team
 * beat and WHO they lost to. This is how the NCAA selection committee
 * actually evaluates teams:
 *   - Beating Tier 1 teams (top 25%) is very valuable
 *   - Losing to Tier 4 teams (bottom 25%) is very damaging
 *
 * Score formula:
 *   (T1_wins * 4 + T2_wins * 2 + T3_wins * 0.5)
 *   - (T2_losses * 1 + T3_losses * 2 + T4_losses * 4)
 *
 * Note: T1 losses carry no penalty (losing to a top team is expected).
 * Z-scored within era.
 */
function computeQualityRecord(season, stats) {
  const z = zScoreCapped(season.qualityRecordScore, stats.qualityRecordScore);
  return z != null ? z : 0;
}

/**
 * COMPONENT 5: PEAK PERCEPTION (10% weight)
 *
 * AP poll rankings capture the consensus national perception of team quality.
 * Despite known biases, the AP poll has been remarkably well-correlated with
 * actual team strength since its inception in 1949.
 *
 * Sub-weights:
 *   Peak AP rank (inverted): 0.40
 *   Final AP rank (inverted): 0.35
 *   Being #1 at any point: 0.25 bonus
 *
 * Returns null for pre-AP seasons — weight is redistributed to other components.
 */
function computePeakPerception(season, stats) {
  if (season.apHigh == null && season.apFinal == null) return null;

  // Invert ranks: #1 -> 30, #25 -> 6, unranked (~30) -> 1
  const invertRank = (rank) => rank != null ? (31 - rank) : 1;

  let score = 0;
  let totalWeight = 0;

  if (season.apHigh != null) {
    const invertedHigh = invertRank(season.apHigh);
    const invertedMean = 31 - stats.apHigh.mean;
    const zHigh = Math.max(-Z_CAP, Math.min(Z_CAP, (invertedHigh - invertedMean) / stats.apHigh.std));
    score += zHigh * 0.40;
    totalWeight += 0.40;
  }

  if (season.apFinal != null) {
    const invertedFinal = invertRank(season.apFinal);
    const invertedMean = 31 - stats.apFinal.mean;
    const zFinal = Math.max(-Z_CAP, Math.min(Z_CAP, (invertedFinal - invertedMean) / stats.apFinal.std));
    score += zFinal * 0.35;
    totalWeight += 0.35;
  }

  // Bonus tier for AP #1
  if (season.apHigh === 1) {
    score += 0.25 * 2.0;
    totalWeight += 0.25;
  } else if (season.apHigh != null && season.apHigh <= 3) {
    score += 0.25 * 1.0;
    totalWeight += 0.25;
  } else if (season.apHigh != null && season.apHigh <= 5) {
    score += 0.25 * 0.5;
    totalWeight += 0.25;
  }

  if (totalWeight > 0) {
    return score / totalWeight * totalWeight;
  }

  return 0;
}

/**
 * COMPONENT 6: CLOSE-GAME RESILIENCE (5% weight) — NEW IN v2
 *
 * Teams that win close games are battle-tested. This matters for cross-era
 * comparison because dominant teams that also win tight games are truly elite.
 *
 * Score = weighted win% in close (<=5pt) and clutch (<=3pt) games.
 * Z-scored within era.
 *
 * Returns null if insufficient close-game data (< 2 close games).
 */
function computeCloseGameResilience(season, stats) {
  const z = zScoreCapped(season.closeGameScore, stats.closeGameScore);
  return z;  // null if no close-game data
}

/**
 * COMPONENT 7: COACHING PRESTIGE (5% weight) — NEW IN v2
 *
 * A team coached by a Hall of Fame coach in their prime deserves a small
 * boost vs. an unknown first-year coach. This captures the "coaching edge"
 * that contributes to sustained excellence.
 *
 * Score based on: career wins at time of season, career win%, HOF status.
 * Z-scored within era.
 */
function computeCoachingPrestige(season, stats) {
  const z = zScoreCapped(season.coachPrestigeScore, stats.coachPrestigeScore);
  return z;  // null if no coaching data
}

/**
 * COMPONENT 8: NBA DRAFT PRODUCTION (5% weight) — NEW IN v2
 *
 * Validates talent level: a team with 3 future NBA players was genuinely
 * loaded. Lottery picks = 3x, first round = 2x, second round = 1x.
 *
 * Z-scored within era. Teams with no draft picks in the window get 0
 * (which z-scores to a mildly negative value, as expected).
 */
function computeDraftProduction(season, stats) {
  const z = zScoreCapped(season.draftScore, stats.draftScore);
  return z != null ? z : 0;
}

// ─────────────────────────────────────────────────────────────────────────────
// 12. ERA DIFFICULTY MULTIPLIER (5% of final score)
// ─────────────────────────────────────────────────────────────────────────────
// The NIL/portal era (2021+) makes sustained dominance harder because roster
// turnover increased dramatically. Pre-integration era (before 1966) had a
// smaller talent pool. Both get context adjustments.
//
// This is applied as a direct additive component (not a multiplier) to maintain
// the z-score-based framework. A 5% weight on a +0.6 z-score equivalent gives
// a ~0.5 point boost on the final HTSS scale.

function computeEraDifficulty(season) {
  const endYear = season.endYear;

  if (endYear >= 2021) {
    // NIL/transfer portal era: roster turnover makes dominance harder.
    // 3% equivalent boost (mapped to z-score space as +0.6)
    return 0.6;
  }

  if (endYear < 1966) {
    // Pre-integration: smaller talent pool, fewer teams.
    // Slight negative context (-0.2 z-score equivalent)
    return -0.2;
  }

  // All other eras: neutral
  return 0.0;
}

// ─────────────────────────────────────────────────────────────────────────────
// 13. MAIN HTSS v2 CALCULATION
// ─────────────────────────────────────────────────────────────────────────────

function computeHTSS(allSeasons, eraStats) {
  // ── Component weights — MUST sum to 1.00 ──
  const W_EFFICIENCY   = 0.30;  // Adjusted Efficiency (from our engine)
  const W_SOS          = 0.12;  // Strength of Schedule (from our engine)
  const W_TOURNAMENT   = 0.18;  // Tournament Performance
  const W_QUALITY_REC  = 0.10;  // Quality Record Profile (from our engine)
  const W_PERCEPTION   = 0.10;  // Peak Perception (AP poll)
  const W_CLOSE_GAME   = 0.05;  // Close-Game Resilience
  const W_COACHING     = 0.05;  // Coaching Prestige
  const W_DRAFT        = 0.05;  // NBA Draft Production
  const W_ERA_DIFF     = 0.05;  // Era Difficulty Multiplier
  // Total: 0.30 + 0.12 + 0.18 + 0.10 + 0.10 + 0.05 + 0.05 + 0.05 + 0.05 = 1.00

  for (const season of allSeasons) {
    const stats = eraStats[season.era];
    if (!stats) {
      season.htss = 50;
      continue;
    }

    // ── Compute all 9 components ──
    const efficiency  = computeAdjustedEfficiency(season, stats);
    const sos         = computeSOS(season, stats);
    const tournament  = computeTournament(season);
    const qualityRec  = computeQualityRecord(season, stats);
    const perception  = computePeakPerception(season, stats);  // null if no AP data
    const closeGame   = computeCloseGameResilience(season, stats);  // null if insufficient data
    const coaching    = computeCoachingPrestige(season, stats);  // null if no coach data
    const draft       = computeDraftProduction(season, stats);
    const eraDiff     = computeEraDifficulty(season);

    // ── Store component scores for transparency ──
    season.components = {
      efficiency:  round3(efficiency),
      sos:         round3(sos),
      tournament:  round3(tournament),
      qualityRec:  round3(qualityRec),
      perception:  perception != null ? round3(perception) : null,
      closeGame:   closeGame != null ? round3(closeGame) : null,
      coaching:    coaching != null ? round3(coaching) : null,
      draft:       round3(draft),
      eraDiff:     round3(eraDiff),
    };

    // ── Weight redistribution for missing components ──
    // When a component returns null (data unavailable), redistribute its
    // weight proportionally to the components that DO have data.
    // This prevents pre-AP-era teams from being penalized for missing polls,
    // and teams without game data from being penalized for missing close-game stats.

    const componentEntries = [
      { value: efficiency, weight: W_EFFICIENCY,  available: true },
      { value: sos,        weight: W_SOS,         available: true },
      { value: tournament, weight: W_TOURNAMENT,  available: true },
      { value: qualityRec, weight: W_QUALITY_REC, available: true },
      { value: perception, weight: W_PERCEPTION,  available: perception != null },
      { value: closeGame,  weight: W_CLOSE_GAME,  available: closeGame != null },
      { value: coaching,   weight: W_COACHING,     available: coaching != null },
      { value: draft,      weight: W_DRAFT,        available: true },
      { value: eraDiff,    weight: W_ERA_DIFF,     available: true },
    ];

    // Sum of available weights (for redistribution)
    const totalAvailableWeight = componentEntries
      .filter(c => c.available)
      .reduce((sum, c) => sum + c.weight, 0);

    // Compute weighted composite with redistribution
    let raw = 0;
    for (const c of componentEntries) {
      if (c.available) {
        // Scale this component's weight up proportionally to account for missing components
        const adjustedWeight = c.weight / totalAvailableWeight;
        raw += c.value * adjustedWeight;
      }
    }

    // ── Transform to human-readable HTSS scale ──
    //
    // The raw composite is a weighted sum of z-scores, typically ranging from
    // about -2.5 (terrible) to +3.0 (transcendent).
    //
    // We want:
    //   50 = average (raw ≈ 0)
    //   60-65 = good (raw ≈ 0.7-1.0)
    //   65-70 = very good (raw ≈ 1.0-1.3)
    //   70-75 = elite (raw ≈ 1.3-1.7)
    //   75-80 = all-time great (raw ≈ 1.7-2.0)
    //   80-85 = transcendent (raw ≈ 2.0-2.3)
    //   85+   = GOAT tier (raw ≈ 2.3+)
    //
    // Base multiplier: 15 maps z-scores to the desired point spread.
    // Nonlinear boost above threshold (exponent 1.2) separates the truly
    // legendary from the merely great.
    const BASE_MULT = 15;
    const BOOST_THRESHOLD = 1.5;
    const BOOST_EXPONENT = 1.2;
    const BOOST_SCALE = 3.5;

    let scaled = raw * BASE_MULT;
    if (raw > BOOST_THRESHOLD) {
      scaled += Math.pow(raw - BOOST_THRESHOLD, BOOST_EXPONENT) * BOOST_SCALE;
    }

    season.htssRaw = Math.round(raw * 10000) / 10000;
    season.htss = Math.round((50 + scaled) * 100) / 100;
  }
}

function round3(v) {
  return v != null ? Math.round(v * 1000) / 1000 : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// 14. POST-PROCESSING: CLAMP AND VALIDATE
// ─────────────────────────────────────────────────────────────────────────────

function postProcess(allSeasons) {
  for (const s of allSeasons) {
    // Clamp to 0-100
    s.htss = Math.max(0, Math.min(100, s.htss));

    // Small-sample cap: < 10 games played = max HTSS of 65
    const totalGames = s.wins + s.losses;
    if (totalGames < 10 && s.htss > 65) {
      s.htss = 65;
      s.htssNote = 'Capped: fewer than 10 games played';
    }

    // Winless seasons floored at 20
    if (s.wins === 0 && s.losses > 0) {
      s.htss = Math.min(s.htss, 20);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 15. PROGRAM RANKINGS
// ─────────────────────────────────────────────────────────────────────────────
// Aggregate program scores from their top N seasons with decay.
// Method: top 10 seasons averaged for the "program score" metric,
// plus a depth-weighted sum of top 30 for the "raw program score".

function computeProgramRankings(allSeasons) {
  const teamSeasons = {};

  for (const s of allSeasons) {
    if (!teamSeasons[s.espnId]) {
      teamSeasons[s.espnId] = { espnId: s.espnId, teamName: s.teamName, seasons: [] };
    }
    teamSeasons[s.espnId].seasons.push(s);
  }

  const programs = [];
  const DECAY = 0.92;
  const TOP_N = 30;

  for (const team of Object.values(teamSeasons)) {
    const sorted = team.seasons
      .filter(s => (s.wins + s.losses) >= 10)
      .sort((a, b) => b.htss - a.htss);

    const top10 = sorted.slice(0, 10);
    const top10Avg = top10.length > 0
      ? top10.reduce((sum, s) => sum + s.htss, 0) / top10.length
      : 0;

    const topSeasons = sorted.slice(0, TOP_N);
    let rawProgramScore = 0;
    for (let i = 0; i < topSeasons.length; i++) {
      rawProgramScore += topSeasons[i].htss * Math.pow(DECAY, i);
    }

    const theoreticalMax = Array.from({ length: TOP_N }, (_, i) =>
      100 * Math.pow(DECAY, i)
    ).reduce((a, b) => a + b, 0);

    programs.push({
      espnId: team.espnId,
      teamName: team.teamName,
      score: Math.round(top10Avg * 100) / 100,
      rawProgramScore: Math.round(rawProgramScore * 100) / 100,
      normalizedScore: Math.round((rawProgramScore / theoreticalMax) * 100 * 100) / 100,
      totalSeasons: team.seasons.length,
      qualifyingSeasons: sorted.length,
      bestSeason: topSeasons[0] ? topSeasons[0].year : null,
      bestHTSS: topSeasons[0] ? topSeasons[0].htss : null,
      top5: topSeasons.slice(0, 5).map(s => ({
        year: s.year,
        record: s.record,
        htss: s.htss,
        coach: s.coach,
      })),
    });
  }

  programs.sort((a, b) => b.score - a.score);
  return programs;
}

// ─────────────────────────────────────────────────────────────────────────────
// 16. v1 COMPARISON LOADER
// ─────────────────────────────────────────────────────────────────────────────
// Load v1 results for side-by-side comparison in console output.

function loadV1Results() {
  const v1Path = path.join(BASE, 'htss_results.json');
  if (!fs.existsSync(v1Path)) return null;
  try {
    return JSON.parse(fs.readFileSync(v1Path, 'utf-8'));
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 17. CONSOLE OUTPUT HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function formatSeason(s, rank) {
  const tourney = s.tourneyRound !== 'none'
    ? s.tourneyRound.replace(/_/g, ' ')
    : 'no tourney';
  const coach = s.coach || 'Unknown';
  const padRank = String(rank).padStart(3);
  const padHTSS = s.htss.toFixed(2).padStart(6);
  const padRecord = s.record.padStart(5);
  const inProgress = s.endYear >= 2026 ? ' *' : '';
  return `${padRank}. ${padHTSS}  ${s.year}  ${s.teamName.padEnd(30)} ${padRecord}  ${tourney.padEnd(16)} (${coach})${inProgress}`;
}

function formatProgram(p, rank) {
  const padRank = String(rank).padStart(3);
  const padScore = p.score.toFixed(2).padStart(6);
  const best = p.bestSeason
    ? `Best: ${p.bestSeason} (${p.bestHTSS?.toFixed(1)})`
    : 'N/A';
  return `${padRank}. ${padScore}  ${p.teamName.padEnd(30)} ${p.qualifyingSeasons} seasons  ${best}`;
}

function printComponentBreakdown(s) {
  const c = s.components;
  console.log(`  ${s.year} ${s.teamName} (${s.record}, HTSS: ${s.htss.toFixed(2)})`);
  console.log(`    Efficiency:  ${fmtComp(c.efficiency)}  (adjEM: ${s.adjEM ?? 'N/A'})`);
  console.log(`    SOS:         ${fmtComp(c.sos)}  (effSOS: ${s.effSOS ?? 'N/A'})`);
  console.log(`    Tournament:  ${fmtComp(c.tournament)}  (${s.tourneyRound})`);
  console.log(`    Quality Rec: ${fmtComp(c.qualityRec)}  (tiers: ${s.tiers ? `T1:${s.tiers.t1w}-${s.tiers.t1l} T2:${s.tiers.t2w}-${s.tiers.t2l}` : 'N/A'})`);
  console.log(`    Perception:  ${fmtComp(c.perception)}  (AP high: ${s.apHigh ?? 'N/A'}, final: ${s.apFinal ?? 'N/A'})`);
  console.log(`    Close Game:  ${fmtComp(c.closeGame)}  (score: ${s.closeGameScore?.toFixed(3) ?? 'N/A'})`);
  console.log(`    Coaching:    ${fmtComp(c.coaching)}  (${s.coach || 'Unknown'})`);
  console.log(`    Draft:       ${fmtComp(c.draft)}  (score: ${s.draftScore})`);
  console.log(`    Era Diff:    ${fmtComp(c.eraDiff)}`);
}

function fmtComp(v) {
  if (v == null) return '  N/A ';
  const sign = v >= 0 ? '+' : '';
  return (sign + v.toFixed(3)).padStart(7);
}

// ─────────────────────────────────────────────────────────────────────────────
// 18. SANITY CHECKS
// ─────────────────────────────────────────────────────────────────────────────

function runSanityChecks(allSeasons) {
  console.log('\n' + '='.repeat(80));
  console.log('SANITY CHECKS — Famous Seasons');
  console.log('='.repeat(80));

  const checks = [
    { desc: '1971-72 UCLA (30-0, Champion)',         espnId: '26',   year: '1971-72' },
    { desc: '1975-76 Indiana (32-0, Champion)',       espnId: '84',   year: '1975-76' },
    { desc: '2014-15 Kentucky (38-1, Final Four)',    espnId: '96',   year: '2014-15' },
    { desc: '2023-24 UConn (37-3, Champion)',         espnId: '41',   year: '2023-24' },
    { desc: '1995-96 Kentucky (34-2, Champion)',      espnId: '96',   year: '1995-96' },
    { desc: '2007-08 Kansas (37-3, Champion)',        espnId: '2305', year: '2007-08' },
  ];

  for (const check of checks) {
    const found = allSeasons.find(s => s.espnId === check.espnId && s.year === check.year);
    if (found) {
      const status = found.htss >= 80 ? 'PASS (80+)' :
                     found.htss >= 75 ? 'OK (75+)' :
                     found.htss >= 70 ? 'WARN (70+)' : 'FAIL (<70)';
      console.log(`  ${status}  ${check.desc} → HTSS: ${found.htss.toFixed(2)}`);
      printComponentBreakdown(found);
    } else {
      console.log(`  MISS   ${check.desc} → Season not found`);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 19. MAIN EXECUTION
// ─────────────────────────────────────────────────────────────────────────────

function main() {
  console.log('\nBuilding all team-season records...');
  const allSeasons = buildAllSeasons();
  console.log(`Built ${allSeasons.length} team-seasons across ${Object.keys(seasonsData).length - CLONE_IDS.size} teams`);

  // Era distribution
  const eraCounts = {};
  for (const s of allSeasons) {
    eraCounts[s.era] = (eraCounts[s.era] || 0) + 1;
  }
  console.log('\nEra distribution:');
  for (const [era, count] of Object.entries(eraCounts)) {
    console.log(`  ${era}: ${count} team-seasons`);
  }

  // Compute era stats
  console.log('\nComputing era statistics...');
  const eraStats = computeEraStats(allSeasons);

  for (const [era, stats] of Object.entries(eraStats)) {
    console.log(`\n  ${era} (n=${stats.count}):`);
    console.log(`    adjEM:    μ=${stats.adjEM.mean.toFixed(2)}, σ=${stats.adjEM.std.toFixed(2)}`);
    console.log(`    effSOS:   μ=${stats.effSOS.mean.toFixed(2)}, σ=${stats.effSOS.std.toFixed(2)}`);
    console.log(`    qualRec:  μ=${stats.qualityRecordScore.mean.toFixed(2)}, σ=${stats.qualityRecordScore.std.toFixed(2)}`);
    console.log(`    closePct: μ=${stats.closeGameScore.mean.toFixed(3)}, σ=${stats.closeGameScore.std.toFixed(3)}`);
    console.log(`    coaching: μ=${stats.coachPrestigeScore.mean.toFixed(2)}, σ=${stats.coachPrestigeScore.std.toFixed(2)}`);
    console.log(`    draft:    μ=${stats.draftScore.mean.toFixed(2)}, σ=${stats.draftScore.std.toFixed(2)}`);
  }

  // Compute HTSS scores
  console.log('\nComputing HTSS v2 scores...');
  computeHTSS(allSeasons, eraStats);
  postProcess(allSeasons);

  // Sort by HTSS
  const rankedSeasons = [...allSeasons]
    .filter(s => (s.wins + s.losses) >= 10)
    .sort((a, b) => b.htss - a.htss);

  // ─── CONSOLE OUTPUT ───────────────────────────────────────────────────────

  // 1. Top 50 team-seasons of all time
  console.log('\n' + '='.repeat(80));
  console.log('TOP 50 TEAM-SEASONS OF ALL TIME (HTSS v2)');
  console.log('='.repeat(80));
  for (let i = 0; i < Math.min(50, rankedSeasons.length); i++) {
    console.log(formatSeason(rankedSeasons[i], i + 1));
  }

  // 2. Top 25 programs of all time
  const programs = computeProgramRankings(allSeasons);
  console.log('\n' + '='.repeat(80));
  console.log('TOP 25 PROGRAMS OF ALL TIME (avg of top 10 seasons)');
  console.log('='.repeat(80));
  for (let i = 0; i < Math.min(25, programs.length); i++) {
    console.log(formatProgram(programs[i], i + 1));
  }

  // 3. Top 25 current era (2016+)
  const currentEra = rankedSeasons.filter(s => s.endYear >= 2016);
  console.log('\n' + '='.repeat(80));
  console.log('TOP 25 CURRENT ERA (2016+)');
  console.log('='.repeat(80));
  for (let i = 0; i < Math.min(25, currentEra.length); i++) {
    console.log(formatSeason(currentEra[i], i + 1));
  }

  // 4. Component breakdown for famous seasons
  console.log('\n' + '='.repeat(80));
  console.log('COMPONENT BREAKDOWN — FAMOUS SEASONS');
  console.log('='.repeat(80));
  runSanityChecks(allSeasons);

  // 5. v1 vs v2 comparison for top 20
  const v1Data = loadV1Results();
  if (v1Data && v1Data.top100TeamSeasons) {
    console.log('\n' + '='.repeat(80));
    console.log('v1 vs v2 COMPARISON — TOP 20');
    console.log('='.repeat(80));
    console.log(`${'v2#'.padStart(4)} ${'HTSS'.padStart(6)}  ${'Season'.padEnd(8)} ${'Team'.padEnd(30)} ${'v1#'.padStart(4)} ${'v1 HTSS'.padStart(7)}  Δ`);
    console.log('-'.repeat(80));

    for (let i = 0; i < Math.min(20, rankedSeasons.length); i++) {
      const v2 = rankedSeasons[i];
      // Find this team-season in v1
      const v1Match = v1Data.top100TeamSeasons.find(
        s => s.espnId === v2.espnId && s.year === v2.year
      );
      const v1Rank = v1Match ? v1Data.top100TeamSeasons.indexOf(v1Match) + 1 : '—';
      const v1Score = v1Match ? v1Match.htss.toFixed(2) : '—';
      const delta = v1Match ? (v2.htss - v1Match.htss).toFixed(2) : '—';
      const arrow = v1Match
        ? (v2.htss > v1Match.htss ? '↑' : v2.htss < v1Match.htss ? '↓' : '=')
        : '';

      console.log(
        `${String(i + 1).padStart(4)} ${v2.htss.toFixed(2).padStart(6)}  ${v2.year.padEnd(8)} ${v2.teamName.padEnd(30)} ${String(v1Rank).padStart(4)} ${String(v1Score).padStart(7)}  ${arrow} ${delta}`
      );
    }
  }

  // ─── BUILD OUTPUT JSON ──────────────────────────────────────────────────

  console.log('\nBuilding output JSON...');

  // Per-era top 25
  const eraTop25 = {};
  for (const era of ERAS) {
    const eraSeasons = rankedSeasons.filter(s => s.era === era.name);
    eraTop25[era.name] = eraSeasons.slice(0, 25).map((s, i) => ({
      rank: i + 1,
      team: s.teamName,
      season: s.year,
      htss: s.htss,
      record: s.record,
      coach: s.coach,
    }));
  }

  // byTeam index
  const byTeam = {};
  for (const s of rankedSeasons) {
    if (!byTeam[s.espnId]) byTeam[s.espnId] = [];
    byTeam[s.espnId].push({
      season: s.year,
      htss: s.htss,
      rank: rankedSeasons.indexOf(s) + 1,
    });
  }

  const output = {
    metadata: {
      version: '2.0',
      generated: new Date().toISOString(),
      algorithm: 'HTSS v2 — Historical Team-Season Score',
      description: 'Hoopsipedia proprietary team-season ranking powered by our efficiency engine. Scale: 50=avg, 60-65=good, 65-70=very good, 70-75=elite, 75-80=all-time great, 80-85=transcendent, 85+=GOAT tier.',
      totalTeamSeasons: allSeasons.length,
      totalTeams: Object.keys(seasonsData).length - CLONE_IDS.size,
      excludedClones: CLONE_IDS.size,
      components: [
        { name: 'Adjusted Efficiency', weight: 0.30, source: 'efficiency_engine.js (adjEM)' },
        { name: 'Strength of Schedule', weight: 0.12, source: 'efficiency_engine.js (sos)' },
        { name: 'Tournament Performance', weight: 0.18, source: 'seasons.json (ncaaTourney)' },
        { name: 'Quality Record Profile', weight: 0.10, source: 'efficiency_engine.js (tier records)' },
        { name: 'Peak Perception', weight: 0.10, source: 'seasons.json (AP poll)' },
        { name: 'Close-Game Resilience', weight: 0.05, source: 'games_*.json' },
        { name: 'Coaching Prestige', weight: 0.05, source: 'data.json (COACHES, COACH_LB)' },
        { name: 'NBA Draft Production', weight: 0.05, source: 'draft_history.json' },
        { name: 'Era Difficulty Multiplier', weight: 0.05, source: 'derived from season year' },
      ],
      eras: ERAS,
      eraNormalization: 'Z-score normalization within each era. All metrics expressed as std devs above/below era mean.',
    },

    allTimeTop100: rankedSeasons.slice(0, 100).map((s, i) => ({
      rank: i + 1,
      team: s.teamName,
      season: s.year,
      htss: s.htss,
      adjEM: s.adjEM,
      record: s.record,
      coach: s.coach,
      era: s.era,
      conference: s.conf,
      tourneyResult: s.tourneyRound,
      seed: s.seed,
      components: s.components,
    })),

    programRankings: programs.slice(0, 50).map((p, i) => ({
      rank: i + 1,
      team: p.teamName,
      score: p.score,
      bestSeason: p.bestSeason,
      qualifyingSeasons: p.qualifyingSeasons,
      top5: p.top5,
    })),

    byTeam,

    eraTop25,
  };

  // Write output
  const outputPath = path.join(BASE, 'htss_v2_results.json');
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`\nResults written to ${outputPath}`);
  console.log(`  - All-time top 100 team-seasons`);
  console.log(`  - ${programs.length} program rankings`);
  console.log(`  - ${Object.keys(byTeam).length} teams indexed`);
  console.log(`  - ${ERAS.length} era top-25 lists`);
  console.log(`  - ${allSeasons.length} total team-seasons scored`);

  console.log('\n' + '='.repeat(80));
  console.log('HTSS v2 Algorithm complete.');
  console.log('='.repeat(80));
}

main();
