#!/usr/bin/env node
/**
 * ============================================================================
 * HISTORICAL TEAM-SEASON SCORE (HTSS) ALGORITHM
 * ============================================================================
 *
 * Hoopsipedia Proprietary Algorithm — v1.0
 *
 * Purpose: Score every college basketball team-season in history on a single
 * scale that enables meaningful cross-era comparisons.
 *
 * Methodology: Z-score normalization within defined eras (aligned to major
 * rule changes), combined across 5 weighted components, then transformed
 * to a human-readable 0-100 scale centered at 50.
 *
 * Scale interpretation:
 *   50  = Average D-I team-season
 *   60  = Strong team (roughly top 30-40 nationally)
 *   70+ = Elite team (top 10 nationally, deep tournament run)
 *   80+ = All-time great season (Final Four caliber, dominant margins)
 *   85+ = Historically transcendent (undefeated or near-undefeated champion)
 *   90+ = Reserved for the very best seasons ever
 *
 * Author: Hoopsipedia (Josh Davis)
 * Created: 2026-04-07
 * ============================================================================
 */

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// 1. LOAD DATA
// ---------------------------------------------------------------------------

const BASE = __dirname;
const seasonsData = JSON.parse(fs.readFileSync(path.join(BASE, 'seasons.json'), 'utf-8'));
const mainData = JSON.parse(fs.readFileSync(path.join(BASE, 'data.json'), 'utf-8'));
const draftData = JSON.parse(fs.readFileSync(path.join(BASE, 'draft_history.json'), 'utf-8'));

const teamInfo = mainData.H;   // espnId -> [name, nickname, conf, color, ...stats]
const coaches = mainData.COACHES; // espnId -> array of coach objects

// ---------------------------------------------------------------------------
// 1b. DETECT AND EXCLUDE DUPLICATE/CLONE TEAMS
// ---------------------------------------------------------------------------
// The scraping process created duplicates where partial name matches (e.g.,
// "North Carolina" matching both UNC and NC Central) caused multiple ESPN IDs
// to receive identical season data. We detect these by fingerprinting the
// first 10 seasons and keeping only the canonical team (highest all-time wins).

function detectCloneTeams() {
  const cloneIds = new Set();

  // Method 1: Fingerprint-based detection.
  // Teams with identical season records (first 10 seasons) are duplicates
  // from the scraping process. Keep the one with the most all-time wins.
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

  // Method 2: Conference mismatch detection.
  // If a team's recent seasons show them in a major conference (ACC, SEC, etc.)
  // but their canonical conference in data.json is a mid-major, they inherited
  // another team's season data during scraping.
  const MAJOR_CONFS = new Set([
    'ACC', 'SEC', 'Big Ten', 'Big 12', 'Big East', 'Pac-12', 'AAC', 'WCC',
    'Big 12', 'MWC', 'American'
  ]);

  for (const id of Object.keys(seasonsData)) {
    if (cloneIds.has(id)) continue; // already flagged
    const info = teamInfo[id];
    if (!info) continue;
    const dataConf = info[2]; // canonical conference from data.json
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

// ---------------------------------------------------------------------------
// 2. ERA DEFINITIONS
// ---------------------------------------------------------------------------
// Eras are defined at major rule inflection points that cause discrete shifts
// in statistical distributions. This is NOT arbitrary — each boundary
// corresponds to a documented rule change that altered how the game is played.
//
// Pre-Shot Clock: No shot clock, no 3-point line. Fundamentally different game.
// Early Modern: 45-second shot clock introduced; 3-point line added 1986-87.
// Mid Modern: 35-second shot clock (1993-94). The "classic" modern era.
// Late Modern: 3-point line extended to 20'9" (2008). Analytics revolution begins.
// Current: 30-second shot clock (2015-16). International 3-point distance (2019-20).

const ERAS = [
  { name: 'Pre-Shot Clock',  start: 0,    end: 1985 },
  { name: 'Early Modern',    start: 1986, end: 1993 },
  { name: 'Mid Modern',      start: 1994, end: 2007 },
  { name: 'Late Modern',     start: 2008, end: 2015 },
  { name: 'Current',         start: 2016, end: 9999 },
];

/**
 * Get the era object for a given season start year.
 * The "year" field in seasons.json is like "2024-25", meaning the season
 * that started in fall 2024. We use the first year to determine era.
 * However, era boundaries reference the calendar year the season ENDS in
 * (e.g., 1985-86 season introduced the shot clock, so seasons ending in
 * 1986+ are "Early Modern"). We parse the END year for classification.
 */
function getSeasonEndYear(yearStr) {
  // "2024-25" -> 2025, "1975-76" -> 1976, "1971-72" -> 1972
  const parts = yearStr.split('-');
  if (parts.length === 2) {
    const startYear = parseInt(parts[0]);
    const endSuffix = parseInt(parts[1]);
    // Handle century boundary: "1999-00" -> 2000
    if (endSuffix < 50 && startYear >= 1950) return startYear + 1;
    if (endSuffix > 50) return parseInt(parts[0].substring(0, 2) + parts[1]);
    return startYear + 1;
  }
  return parseInt(yearStr);
}

function getEra(yearStr) {
  const endYear = getSeasonEndYear(yearStr);
  for (const era of ERAS) {
    if (endYear >= era.start && endYear <= era.end) return era;
  }
  return ERAS[0]; // fallback to earliest era
}

// ---------------------------------------------------------------------------
// 3. TOURNAMENT FIELD SIZE BY YEAR
// ---------------------------------------------------------------------------
// Used for the era-adjustment on tournament performance. A championship in a
// smaller field is less difficult (fewer rounds), so we normalize by the
// log2 of field size (which equals the number of rounds to win).

function getTournamentFieldSize(yearStr) {
  const endYear = getSeasonEndYear(yearStr);
  if (endYear <= 1950) return 8;
  if (endYear <= 1952) return 16;
  if (endYear <= 1974) return 25;  // varied between 22-25
  if (endYear <= 1978) return 32;
  if (endYear <= 1984) return 48;  // varied 40-53
  if (endYear <= 2000) return 64;
  if (endYear <= 2010) return 65;
  return 68; // First Four era (2011+)
}

// Modern reference field size — all tournament scores are normalized relative to this.
const MODERN_FIELD_SIZE = 68;

// ---------------------------------------------------------------------------
// 4. NIL/TRANSFER PORTAL DIFFICULTY MULTIPLIER
// ---------------------------------------------------------------------------
// Starting 2021, the NIL era and expanded transfer portal made sustained
// dominance harder because roster turnover increased dramatically. A team
// that dominates in this environment deserves a small bonus (not huge —
// the game itself didn't change, just the roster dynamics).
//
// This is applied as a multiplier on the final raw score: 1.0 for pre-2021,
// 1.03 for 2021+. The 3% bonus is deliberately small — enough to be a
// tiebreaker, not enough to vault a mediocre modern team above a great
// historical one.

function getNILMultiplier(yearStr) {
  const endYear = getSeasonEndYear(yearStr);
  return endYear >= 2021 ? 1.03 : 1.0;
}

// ---------------------------------------------------------------------------
// 5. PARSE TOURNAMENT RESULT
// ---------------------------------------------------------------------------
// Map the ncaaTourney string to a structured tournament finish.
// Returns: { round: string, isChampion: bool, isRunnerUp: bool, ... }

function parseTournamentResult(ncaaTourney) {
  if (!ncaaTourney) return { round: 'none', points: -2.0 };

  const s = ncaaTourney.replace(/\*/g, ''); // strip asterisks

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
    return { round: 'first_round', points: 0.0 };
  if (s.includes('Playing'))
    return { round: 'in_progress', points: 0.0 };
  if (s.includes('Regional Third Place'))
    return { round: 'final_four', points: 5.0 }; // Pre-1982 3rd place game = Final Four

  // Catch-all: team was in the tournament but result is unclear
  return { round: 'unknown_tourney', points: 0.0 };
}

// ---------------------------------------------------------------------------
// 6. BUILD ALL TEAM-SEASON RECORDS
// ---------------------------------------------------------------------------
// Flatten every team-season into a unified record with all available fields.

function buildAllSeasons() {
  const allSeasons = [];

  for (const espnId of Object.keys(seasonsData)) {
    // Skip clone/duplicate teams (see Section 1b)
    if (CLONE_IDS.has(espnId)) continue;

    const teamSeasons = seasonsData[espnId].seasons;
    if (!teamSeasons || !Array.isArray(teamSeasons)) continue;

    const info = teamInfo[espnId];
    const teamName = info ? info[0] : `Unknown (${espnId})`;

    for (const season of teamSeasons) {
      const endYear = getSeasonEndYear(season.year);
      const era = getEra(season.year);
      const tourney = parseTournamentResult(season.ncaaTourney);

      // Scoring margin — compute from ppg and oppPpg if available
      const scoringMargin = (season.ppg != null && season.oppPpg != null)
        ? season.ppg - season.oppPpg
        : null;

      allSeasons.push({
        espnId,
        teamName,
        year: season.year,
        endYear,
        era: era.name,

        // Raw stats
        wins: season.wins || 0,
        losses: season.losses || 0,
        winPct: season.winPct || 0,
        srs: season.srs != null ? season.srs : null,
        sos: season.sos != null ? season.sos : null,
        ppg: season.ppg != null ? season.ppg : null,
        oppPpg: season.oppPpg != null ? season.oppPpg : null,
        scoringMargin,

        // Conference
        conf: season.conf || null,
        confWinPct: season.confWinPct != null ? season.confWinPct : null,
        confWins: season.confWins || 0,
        confLosses: season.confLosses || 0,

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

        // Coach
        coach: season.coach || null,

        // NIL multiplier
        nilMultiplier: getNILMultiplier(season.year),
      });
    }
  }

  return allSeasons;
}

// ---------------------------------------------------------------------------
// 7. Z-SCORE CALCULATION UTILITIES
// ---------------------------------------------------------------------------

/**
 * Compute mean and standard deviation for an array of numbers.
 * Ignores null/undefined values.
 */
function meanAndStd(values) {
  const valid = values.filter(v => v != null && !isNaN(v));
  if (valid.length === 0) return { mean: 0, std: 1 }; // safe fallback

  const mean = valid.reduce((a, b) => a + b, 0) / valid.length;
  const variance = valid.reduce((a, b) => a + (b - mean) ** 2, 0) / valid.length;
  const std = Math.sqrt(variance);

  // Prevent division by zero — if all values are identical, std=0.
  // Use 1.0 as fallback so z-scores become 0 (which is correct: no variance).
  return { mean, std: std > 0 ? std : 1.0 };
}

/**
 * Compute z-score for a value given precomputed mean and std.
 * Returns null if value is null/undefined.
 */
function zScore(value, stats) {
  if (value == null || isNaN(value)) return null;
  return (value - stats.mean) / stats.std;
}

// ---------------------------------------------------------------------------
// 8. COMPUTE ERA STATISTICS
// ---------------------------------------------------------------------------
// For each era, compute the mean and std of every metric we need for z-scoring.

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
      winPct: meanAndStd(seasons.map(s => s.winPct)),
      srs: meanAndStd(seasons.map(s => s.srs)),
      sos: meanAndStd(seasons.map(s => s.sos)),
      scoringMargin: meanAndStd(seasons.map(s => s.scoringMargin)),
      confWinPct: meanAndStd(seasons.map(s => s.confWinPct)),

      // For AP ranks, we INVERT them: #1 should be highest z-score.
      // We store stats on the raw rank values, then invert during z-scoring.
      apHigh: meanAndStd(seasons.filter(s => s.apHigh != null).map(s => s.apHigh)),
      apFinal: meanAndStd(seasons.filter(s => s.apFinal != null).map(s => s.apFinal)),

      // Tournament points — for normalization of the conference + tourney components
      tourneyPoints: meanAndStd(seasons.map(s => s.tourneyPoints)),
    };
  }

  return eraStats;
}

// ---------------------------------------------------------------------------
// 9. HTSS COMPONENT CALCULATIONS
// ---------------------------------------------------------------------------

/**
 * COMPONENT 1: DOMINANCE SCORE (35% weight)
 *
 * Measures raw team strength through margin-based and record-based metrics.
 * SRS (Simple Rating System) gets the highest sub-weight because research
 * consistently shows adjusted margin is the single strongest predictor of
 * team quality. Win percentage captures the bottom line. Scoring margin
 * provides a SRS-independent check on dominance.
 *
 * When SRS is unavailable (pre-~1980), we fall back to win% + scoring margin
 * only. This is a known limitation: pre-1980 scores have higher uncertainty,
 * which is accurately reflected in a narrower range of possible scores.
 *
 * Sub-weights (when SRS available):
 *   SRS: 0.40 — Most comprehensive single metric (margin + SOS in one number)
 *   Win%: 0.25 — The bottom line; undefeated seasons should score very high
 *   Scoring Margin: 0.20 — Independent dominance signal, less SOS-adjusted than SRS
 *   (Close-game resilience: 0.15 — OMITTED because we lack game-level data;
 *    its weight is redistributed to the other three sub-components)
 *
 * Adjusted sub-weights (no close-game data available):
 *   SRS: 0.45, Win%: 0.30, Scoring Margin: 0.25
 *
 * Fallback sub-weights (no SRS):
 *   Win%: 0.55, Scoring Margin: 0.45
 */
function computeDominance(season, stats) {
  const zWinPct = zScore(season.winPct, stats.winPct);
  const zMargin = zScore(season.scoringMargin, stats.scoringMargin);
  const zSRS = zScore(season.srs, stats.srs);

  let base;
  if (zSRS != null && zMargin != null) {
    // Full model: SRS + Win% + Margin
    base = zSRS * 0.45 + zWinPct * 0.30 + zMargin * 0.25;
  } else if (zMargin != null) {
    // No SRS: rely on win% and margin
    base = zWinPct * 0.55 + zMargin * 0.45;
  } else if (zWinPct != null) {
    // Only win% available (very old seasons)
    base = zWinPct;
  } else {
    return 0; // No data at all — score at average
  }

  // Undefeated bonus: Going undefeated in a full season (20+ games) is
  // historically rare and represents a level of dominance that raw z-scores
  // undervalue because win% is capped at 1.000. This bonus is proportional
  // to the number of wins (a 32-0 team is more impressive than a 20-0 team).
  if (season.winPct >= 1.0 && season.wins >= 20) {
    base += 0.3 + (season.wins - 20) * 0.015;
  }
  // One-loss bonus for seasons with 28+ wins and exactly 1 loss
  else if (season.losses === 1 && season.wins >= 28) {
    base += 0.15;
  }

  return base;
}

/**
 * COMPONENT 2: STRENGTH OF SCHEDULE (20% weight)
 *
 * Captures whether a team beat good opponents or feasted on weak ones.
 * SOS from Sports Reference is a margin-based measure already baked into SRS,
 * but we want it as an independent component because schedule difficulty
 * matters beyond what margin captures.
 *
 * Ideally we'd include "ranked wins" and "bad losses" as sub-components,
 * but we lack game-level opponent data. We use SOS as the primary signal,
 * with a penalty for teams whose SOS is extremely low relative to their era.
 *
 * When SOS is unavailable, we fall back to conference win% as a proxy
 * (playing in a tougher conference generally means tougher SOS).
 *
 * Sub-weights:
 *   SOS: 0.75 — Direct measure of schedule difficulty
 *   Conference membership proxy: 0.25 — Tougher conferences = tougher schedules
 */
function computeSOS(season, stats) {
  const zSOS = zScore(season.sos, stats.sos);

  if (zSOS != null) {
    // SOS available — use it directly
    // Add a mild bonus for very high SOS (> 1 std above mean) as a "quality wins" proxy
    const qualityBonus = zSOS > 1.0 ? (zSOS - 1.0) * 0.15 : 0;
    return zSOS * 0.85 + qualityBonus;
  }

  // Fallback: use conference win% inverted as a rough SOS proxy
  // Logic: if you had a high conf win% in a major conference, your SOS was likely good.
  // This is imperfect but better than nothing for pre-1980 seasons.
  const zConfWP = zScore(season.confWinPct, stats.confWinPct);
  if (zConfWP != null) {
    return zConfWP * 0.3; // heavily discounted — it's a weak proxy
  }

  return 0;
}

/**
 * COMPONENT 3: TOURNAMENT PERFORMANCE (20% weight)
 *
 * Uses discrete achievement points rather than z-scores because tournament
 * outcomes are categorical, not continuous. Point values from RANKING_RESEARCH.md:
 *
 *   Championship:    15.0 — Winning it all is the ultimate achievement
 *   Runner-up:        8.0 — Reached the final, lost once
 *   Final Four:       5.0 — Top 4 in the nation
 *   Elite Eight:      3.0 — Regional champion
 *   Sweet Sixteen:    1.5 — Won at least one tournament game beyond opening weekend
 *   Round of 32:      0.5 — Won first-round game
 *   First Round exit:  0.0 — Made the tournament but didn't advance
 *   Did not make:    -2.0 — Mild penalty (not harsh — pre-expansion, many good teams missed)
 *
 * Era adjustment: We scale by log2(modern_field_size) / log2(team_era_field_size).
 * This means winning a championship in a 16-team field (4 rounds) is scaled
 * relative to winning in a 68-team field (~6 rounds). The adjustment rewards
 * modern champions for surviving more rounds while still giving substantial
 * credit to historical champions.
 *
 * The result is then normalized to a 0-1 scale using the maximum possible
 * tournament score (a championship with full era adjustment) as the denominator.
 */
function computeTournament(season) {
  // For seasons with "in_progress" tournament or current season with no
  // tournament data yet, treat as neutral (0). We detect "current season"
  // as the most recent year in the dataset where the tournament hasn't
  // happened yet for most teams.
  if (season.tourneyRound === 'in_progress') return 0;

  // If season is in current year and has no tournament data, don't penalize.
  // The -2 penalty is for teams that genuinely missed the tournament in
  // completed seasons, not teams whose season is still underway.
  if (season.tourneyRound === 'none' && season.endYear >= 2026) return 0;

  const rawPoints = season.tourneyPoints;

  // Era adjustment for field size
  // log2(68) ≈ 6.09, log2(8) = 3, log2(16) = 4, log2(25) ≈ 4.64, etc.
  const eraFieldLog = Math.log2(Math.max(season.fieldSize, 2));
  const modernFieldLog = Math.log2(MODERN_FIELD_SIZE); // ≈ 6.09

  // For positive achievements, scale UP for modern teams (more rounds to win).
  // For negative (did not make), scale DOWN for older eras (smaller fields = less stigma).
  let adjustedPoints;
  if (rawPoints > 0) {
    adjustedPoints = rawPoints * (modernFieldLog / eraFieldLog);
  } else if (rawPoints < 0) {
    // Did not make tournament: penalty is reduced for eras with smaller fields
    // because many good teams simply didn't get in.
    adjustedPoints = rawPoints * (eraFieldLog / modernFieldLog);
  } else {
    adjustedPoints = 0;
  }

  // Normalize to roughly 0-1 scale.
  // Max possible = championship (15) in modern era = 15 * (6.09/6.09) = 15
  // We divide by 15 so a modern champion gets 1.0.
  const maxPoints = 15.0;
  return adjustedPoints / maxPoints;
}

/**
 * COMPONENT 4: CONFERENCE PERFORMANCE (10% weight)
 *
 * Conference play is the most consistent signal of a team's quality because
 * it spans 15-20 games against known opponents over months. Unlike tournament
 * play (single elimination), conference performance is resistant to
 * single-game variance.
 *
 * We z-score conference win% within era. We cannot reliably detect conference
 * regular-season or tournament titles from the season-level data (would need
 * a separate dataset), so we use conference win% as the primary signal, with
 * a bonus for perfect or near-perfect conference records.
 *
 * Sub-weights:
 *   Conference win%: primary signal (z-scored within era)
 *   Undefeated conference bonus: +0.5 for 1.000 conf win%
 *   Near-perfect bonus: +0.2 for ≥ 0.900 conf win%
 */
function computeConference(season, stats) {
  const zConfWP = zScore(season.confWinPct, stats.confWinPct);

  if (zConfWP == null) return 0;

  let bonus = 0;
  if (season.confWinPct >= 1.0 && season.confWins > 0) {
    // Perfect conference record — extremely rare and impressive
    bonus = 0.5;
  } else if (season.confWinPct >= 0.900 && season.confWins > 0) {
    bonus = 0.2;
  }

  return zConfWP + bonus;
}

/**
 * COMPONENT 5: PEAK PERCEPTION (15% weight)
 *
 * The AP Poll provides a "consensus view" signal that captures how the nation
 * perceived the team during the season. Despite known biases (preseason
 * anchoring, recency), the AP poll is remarkably correlated with actual quality
 * and is the longest-running national ranking system (since 1949).
 *
 * We INVERT ranks so that #1 = highest value. Unranked teams get a default
 * value of 30 (below the 25-team poll cutoff), which ensures they get negative
 * z-scores as expected.
 *
 * Sub-weights:
 *   Peak AP rank: 0.40 — The team's ceiling during the season
 *   Final AP rank: 0.35 — Where they ended up (most reflective of full-season quality)
 *   Being #1 at any point: 0.25 — Holding the top spot signals peak dominance
 *
 * For pre-AP era (before 1949), this component is zeroed out and its weight
 * is effectively redistributed via the normalization process.
 */
function computePeakPerception(season, stats) {
  // If no AP data at all for this season, return null to signal "skip this component"
  if (season.apHigh == null && season.apFinal == null) return null;

  // Invert ranks: #1 becomes 26, #25 becomes 2, unranked (30) becomes 1
  // This ensures higher values = better teams in the z-score calculation
  const invertRank = (rank) => rank != null ? (31 - rank) : 1; // unranked ≈ 31st → 0

  const invertedHigh = season.apHigh != null ? invertRank(season.apHigh) : null;
  const invertedFinal = season.apFinal != null ? invertRank(season.apFinal) : null;

  // For z-scoring inverted ranks, we need era stats on inverted values.
  // Since we stored raw rank stats, we'll compute z-scores manually here.
  // Higher inverted rank = better, so z-score with inverted stats.

  let score = 0;
  let totalWeight = 0;

  if (invertedHigh != null) {
    // Z-score the inverted high rank
    // stats.apHigh is on raw ranks; inverted mean = 31 - rawMean, same std
    const invertedMean = 31 - stats.apHigh.mean;
    const zHigh = (invertedHigh - invertedMean) / stats.apHigh.std;
    score += zHigh * 0.40;
    totalWeight += 0.40;
  }

  if (invertedFinal != null) {
    const invertedMean = 31 - stats.apFinal.mean;
    const zFinal = (invertedFinal - invertedMean) / stats.apFinal.std;
    score += zFinal * 0.35;
    totalWeight += 0.35;
  }

  // Bonus for being AP #1 at any point.
  // Reaching #1 is rare and signals peak dominance — weighted as a strong positive.
  if (season.apHigh === 1) {
    score += 0.25 * 2.0; // 2.0 z-score equivalent bonus for reaching #1
    totalWeight += 0.25;
  } else if (season.apHigh != null && season.apHigh <= 3) {
    score += 0.25 * 1.0; // meaningful bonus for top-3
    totalWeight += 0.25;
  } else if (season.apHigh != null && season.apHigh <= 5) {
    score += 0.25 * 0.5; // smaller bonus for top-5
    totalWeight += 0.25;
  }

  // Normalize by total weight used (in case some sub-components are missing)
  if (totalWeight > 0) {
    return score / totalWeight * (totalWeight / 1.0); // scale by coverage
  }

  return 0;
}

// ---------------------------------------------------------------------------
// 10. MAIN HTSS CALCULATION
// ---------------------------------------------------------------------------

function computeHTSS(allSeasons, eraStats) {
  // Weights for each component — from RANKING_RESEARCH.md
  const W_DOMINANCE = 0.35;
  const W_SOS = 0.20;
  const W_TOURNAMENT = 0.20;
  const W_CONFERENCE = 0.10;
  const W_PERCEPTION = 0.15;

  for (const season of allSeasons) {
    const stats = eraStats[season.era];
    if (!stats) {
      season.htss = 50; // default average
      continue;
    }

    // Compute each component
    const dominance = computeDominance(season, stats);
    const sos = computeSOS(season, stats);
    const tournament = computeTournament(season);
    const conference = computeConference(season, stats);
    const perception = computePeakPerception(season, stats);

    // Store component scores for debugging/transparency
    season.components = {
      dominance: Math.round(dominance * 1000) / 1000,
      sos: Math.round(sos * 1000) / 1000,
      tournament: Math.round(tournament * 1000) / 1000,
      conference: Math.round(conference * 1000) / 1000,
      perception: perception != null ? Math.round(perception * 1000) / 1000 : null,
    };

    // When perception data is unavailable (pre-AP era or unranked teams),
    // redistribute its weight proportionally to the other components.
    // This prevents old teams from being penalized for lacking AP poll data.
    let raw;
    if (perception != null) {
      raw = dominance * W_DOMINANCE
          + sos * W_SOS
          + tournament * W_TOURNAMENT
          + conference * W_CONFERENCE
          + perception * W_PERCEPTION;
    } else {
      // Redistribute perception weight (0.15) proportionally
      const nonPerceptionTotal = W_DOMINANCE + W_SOS + W_TOURNAMENT + W_CONFERENCE;
      raw = dominance * (W_DOMINANCE / nonPerceptionTotal)
          + sos * (W_SOS / nonPerceptionTotal)
          + tournament * (W_TOURNAMENT / nonPerceptionTotal)
          + conference * (W_CONFERENCE / nonPerceptionTotal);
    }

    // Apply NIL/transfer portal era multiplier
    raw *= season.nilMultiplier;

    // Transform to human-readable scale.
    //
    // The raw composite is a weighted sum of z-scores, typically ranging from
    // about -2.5 (terrible) to +3.0 (transcendent). We want:
    //   50 = average (raw ≈ 0)
    //   70 = elite (raw ≈ 1.3)
    //   80 = all-time great (raw ≈ 2.0)
    //   85+ = transcendent (raw ≈ 2.5+)
    //
    // Base multiplier of 15 maps raw z-scores to the desired scale.
    // An additional nonlinear boost for extreme seasons (raw > 1.5) separates
    // the truly legendary from the merely great. The boost is:
    //   extra = (raw - 1.5)^1.3 * 3.0  (only applied above 1.5)
    //
    // This is calibrated so:
    //   raw=1.5 → HTSS=72.5 (no boost)
    //   raw=2.0 → HTSS=~82  (boost adds ~2 points)
    //   raw=2.5 → HTSS=~90  (boost adds ~5 points)
    //   raw=3.0 → HTSS=~98  (boost adds ~8 points)
    const BASE_MULT = 15;
    const BOOST_THRESHOLD = 1.5;
    const BOOST_EXPONENT = 1.3;
    const BOOST_SCALE = 3.0;

    let scaled = raw * BASE_MULT;
    if (raw > BOOST_THRESHOLD) {
      scaled += Math.pow(raw - BOOST_THRESHOLD, BOOST_EXPONENT) * BOOST_SCALE;
    }

    season.htssRaw = Math.round(raw * 10000) / 10000;
    season.htss = Math.round((50 + scaled) * 100) / 100;
  }
}

// ---------------------------------------------------------------------------
// 11. POST-PROCESSING: CLAMP AND VALIDATE
// ---------------------------------------------------------------------------

function postProcess(allSeasons) {
  for (const s of allSeasons) {
    // Clamp to reasonable range (0-100)
    s.htss = Math.max(0, Math.min(100, s.htss));

    // Sanity: seasons with very few games (< 10) get capped at 65
    // because small samples are unreliable
    const totalGames = s.wins + s.losses;
    if (totalGames < 10 && s.htss > 65) {
      s.htss = 65;
      s.htssNote = 'Capped: fewer than 10 games played';
    }

    // Seasons with 0 wins get floored at 20
    if (s.wins === 0 && s.losses > 0) {
      s.htss = Math.min(s.htss, 20);
    }
  }
}

// ---------------------------------------------------------------------------
// 12. AGGREGATE PROGRAM RANKINGS
// ---------------------------------------------------------------------------

/**
 * Compute program-level scores by aggregating their best seasons.
 *
 * Method: Take a team's top N seasons by HTSS, with diminishing returns
 * for each additional season. This rewards programs with many great seasons
 * (Kansas, Kentucky) over one-hit wonders.
 *
 * Formula: Sum of (season_htss * decay_factor) for top 30 seasons,
 *   where decay_factor = 0.92^(rank-1).
 *   Season 1: full credit (1.00), Season 2: 0.92, Season 3: 0.85, etc.
 *
 * The decay rate of 0.92 means the 10th-best season contributes ~47% of
 * the best season, and the 20th contributes ~22%. This balances depth vs. peaks.
 */
function computeProgramRankings(allSeasons) {
  const teamSeasons = {};

  for (const s of allSeasons) {
    if (!teamSeasons[s.espnId]) {
      teamSeasons[s.espnId] = {
        espnId: s.espnId,
        teamName: s.teamName,
        seasons: [],
      };
    }
    teamSeasons[s.espnId].seasons.push(s);
  }

  const programs = [];
  const DECAY = 0.92;
  const TOP_N = 30; // Consider top 30 seasons per program

  for (const team of Object.values(teamSeasons)) {
    // Sort seasons by HTSS descending
    const sorted = team.seasons
      .filter(s => (s.wins + s.losses) >= 10) // exclude tiny-sample seasons
      .sort((a, b) => b.htss - a.htss);

    const topSeasons = sorted.slice(0, TOP_N);

    let programScore = 0;
    for (let i = 0; i < topSeasons.length; i++) {
      programScore += topSeasons[i].htss * Math.pow(DECAY, i);
    }

    // Normalize: divide by the theoretical max (30 seasons of 100 points each)
    const theoreticalMax = Array.from({ length: TOP_N }, (_, i) =>
      100 * Math.pow(DECAY, i)
    ).reduce((a, b) => a + b, 0);

    const normalizedScore = (programScore / theoreticalMax) * 100;

    programs.push({
      espnId: team.espnId,
      teamName: team.teamName,
      programScore: Math.round(normalizedScore * 100) / 100,
      rawProgramScore: Math.round(programScore * 100) / 100,
      totalSeasons: team.seasons.length,
      qualifyingSeasons: sorted.length,
      bestSeason: topSeasons[0] ? {
        year: topSeasons[0].year,
        record: `${topSeasons[0].wins}-${topSeasons[0].losses}`,
        htss: topSeasons[0].htss,
        coach: topSeasons[0].coach,
      } : null,
      top5Seasons: topSeasons.slice(0, 5).map(s => ({
        year: s.year,
        record: `${s.wins}-${s.losses}`,
        htss: s.htss,
      })),
    });
  }

  programs.sort((a, b) => b.programScore - a.programScore);
  return programs;
}

// ---------------------------------------------------------------------------
// 13. OUTPUT HELPERS
// ---------------------------------------------------------------------------

function formatSeason(s, rank) {
  const record = `${s.wins}-${s.losses}`;
  const tourney = s.tourneyRound !== 'none'
    ? s.tourneyRound.replace(/_/g, ' ')
    : 'no tourney';
  const coach = s.coach || 'Unknown';
  const padRank = String(rank).padStart(3);
  const padHTSS = s.htss.toFixed(2).padStart(6);
  const padRecord = record.padStart(5);
  const inProgress = s.endYear >= 2026 ? ' *' : '';
  return `${padRank}. ${padHTSS}  ${s.year}  ${s.teamName.padEnd(30)} ${padRecord}  ${tourney.padEnd(16)} (${coach})${inProgress}`;
}

function formatProgram(p, rank) {
  const padRank = String(rank).padStart(3);
  const padScore = p.programScore.toFixed(2).padStart(6);
  const best = p.bestSeason
    ? `Best: ${p.bestSeason.year} (${p.bestSeason.record}, ${p.bestSeason.htss.toFixed(1)})`
    : 'N/A';
  return `${padRank}. ${padScore}  ${p.teamName.padEnd(30)} ${p.qualifyingSeasons} qualifying seasons  ${best}`;
}

// ---------------------------------------------------------------------------
// 14. SANITY CHECKS
// ---------------------------------------------------------------------------

function runSanityChecks(allSeasons) {
  console.log('\n' + '='.repeat(80));
  console.log('SANITY CHECKS');
  console.log('='.repeat(80));

  const checks = [
    { desc: '1975-76 Indiana (32-0, National Champion)',   espnId: '84',  year: '1975-76' },
    { desc: '1971-72 UCLA (30-0, National Champion)',      espnId: '26',  year: '1971-72' },
    { desc: '2023-24 UConn (37-3, National Champion)',     espnId: '41',  year: '2023-24' },
    { desc: '2022-23 UConn (31-8, National Champion)',     espnId: '41',  year: '2022-23' },
    { desc: '2014-15 Kentucky (38-1, Final Four)',         espnId: '96',  year: '2014-15' },
    { desc: '2011-12 Kentucky (38-2, National Champion)',  espnId: '96',  year: '2011-12' },
    { desc: '1995-96 Kentucky (34-2, National Champion)',  espnId: '96',  year: '1995-96' },
    { desc: '2007-08 Kansas (37-3, National Champion)',    espnId: '2305', year: '2007-08' },
    { desc: '2008-09 North Carolina (34-4, National Champion)', espnId: '153', year: '2008-09' },
    { desc: '1991-92 Duke (34-2, National Champion)',      espnId: '150', year: '1991-92' },
  ];

  for (const check of checks) {
    const found = allSeasons.find(s => s.espnId === check.espnId && s.year === check.year);
    if (found) {
      const status = found.htss >= 80 ? 'PASS (80+)' :
                     found.htss >= 75 ? 'OK (75+)' :
                     found.htss >= 70 ? 'WARN (70+)' : 'FAIL (<70)';
      console.log(`  ${status}  ${check.desc} → HTSS: ${found.htss.toFixed(2)}`);
      console.log(`         Components: Dom=${found.components.dominance}, SOS=${found.components.sos}, Tourn=${found.components.tournament}, Conf=${found.components.conference}, Perc=${found.components.perception}`);
    } else {
      console.log(`  MISS   ${check.desc} → Season not found`);
    }
  }
}

// ---------------------------------------------------------------------------
// 15. FIND ESPN IDS FOR SANITY CHECK TEAMS
// ---------------------------------------------------------------------------

function findTeamId(namePart) {
  for (const id of Object.keys(teamInfo)) {
    if (teamInfo[id][0].toLowerCase().includes(namePart.toLowerCase())) {
      return id;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// 16. MAIN EXECUTION
// ---------------------------------------------------------------------------

function main() {
  console.log('HTSS Algorithm v1.0 — Hoopsipedia');
  console.log('='.repeat(80));
  console.log('Loading data...');

  const allSeasons = buildAllSeasons();
  console.log(`Loaded ${allSeasons.length} team-seasons across ${Object.keys(seasonsData).length - CLONE_IDS.size} teams (${CLONE_IDS.size} duplicate teams excluded)`);

  // Log era distribution
  const eraCounts = {};
  for (const s of allSeasons) {
    eraCounts[s.era] = (eraCounts[s.era] || 0) + 1;
  }
  console.log('\nEra distribution:');
  for (const [era, count] of Object.entries(eraCounts)) {
    console.log(`  ${era}: ${count} team-seasons`);
  }

  console.log('\nComputing era statistics...');
  const eraStats = computeEraStats(allSeasons);

  // Log era stats for transparency
  for (const [era, stats] of Object.entries(eraStats)) {
    console.log(`\n  ${era} (n=${stats.count}):`);
    console.log(`    Win%:     μ=${stats.winPct.mean.toFixed(3)}, σ=${stats.winPct.std.toFixed(3)}`);
    console.log(`    SRS:      μ=${stats.srs.mean.toFixed(2)}, σ=${stats.srs.std.toFixed(2)}`);
    console.log(`    Margin:   μ=${stats.scoringMargin.mean.toFixed(2)}, σ=${stats.scoringMargin.std.toFixed(2)}`);
    console.log(`    SOS:      μ=${stats.sos.mean.toFixed(2)}, σ=${stats.sos.std.toFixed(2)}`);
    console.log(`    Conf W%:  μ=${stats.confWinPct.mean.toFixed(3)}, σ=${stats.confWinPct.std.toFixed(3)}`);
  }

  console.log('\nComputing HTSS scores...');
  computeHTSS(allSeasons, eraStats);
  postProcess(allSeasons);

  // Sort all seasons by HTSS
  const rankedSeasons = [...allSeasons]
    .filter(s => (s.wins + s.losses) >= 10) // exclude tiny seasons
    .sort((a, b) => b.htss - a.htss);

  // ---------------------------------------------------------------------------
  // CONSOLE OUTPUT: Top 50 Team-Seasons
  // ---------------------------------------------------------------------------
  console.log('\n' + '='.repeat(80));
  console.log('TOP 50 TEAM-SEASONS OF ALL TIME');
  console.log('='.repeat(80));
  for (let i = 0; i < Math.min(50, rankedSeasons.length); i++) {
    console.log(formatSeason(rankedSeasons[i], i + 1));
  }

  // ---------------------------------------------------------------------------
  // CONSOLE OUTPUT: Top 25 Programs
  // ---------------------------------------------------------------------------
  const programs = computeProgramRankings(allSeasons);
  console.log('\n' + '='.repeat(80));
  console.log('TOP 25 PROGRAMS OF ALL TIME');
  console.log('='.repeat(80));
  for (let i = 0; i < Math.min(25, programs.length); i++) {
    console.log(formatProgram(programs[i], i + 1));
  }

  // ---------------------------------------------------------------------------
  // SANITY CHECKS
  // ---------------------------------------------------------------------------
  // Verify ESPN IDs for sanity check teams
  const kansasId = findTeamId('Kansas Jayhawks');
  const uncId = findTeamId('North Carolina Tar Heels');
  const dukeId = findTeamId('Duke Blue Devils');
  console.log(`\nTeam ID lookups: Kansas=${kansasId}, UNC=${uncId}, Duke=${dukeId}`);

  // Update sanity check IDs based on lookups
  runSanityChecks(allSeasons);

  // ---------------------------------------------------------------------------
  // BUILD OUTPUT JSON
  // ---------------------------------------------------------------------------
  console.log('\nBuilding output JSON...');

  // Per-team best season
  const bestPerTeam = {};
  for (const s of rankedSeasons) {
    if (!bestPerTeam[s.espnId] || s.htss > bestPerTeam[s.espnId].htss) {
      bestPerTeam[s.espnId] = {
        espnId: s.espnId,
        teamName: s.teamName,
        year: s.year,
        record: `${s.wins}-${s.losses}`,
        htss: s.htss,
        coach: s.coach,
        tourneyRound: s.tourneyRound,
        components: s.components,
      };
    }
  }

  const output = {
    metadata: {
      version: '1.0',
      generatedAt: new Date().toISOString(),
      algorithm: 'HTSS — Historical Team-Season Score',
      description: 'Hoopsipedia proprietary team-season ranking. Scale: 50=average, 70+=elite, 80+=all-time great, 90+=transcendent.',
      totalTeamSeasons: allSeasons.length,
      totalTeams: Object.keys(seasonsData).length - CLONE_IDS.size,
      excludedClones: CLONE_IDS.size,
      components: {
        dominance: { weight: 0.35, description: 'SRS, win%, scoring margin (z-scored within era)' },
        strengthOfSchedule: { weight: 0.20, description: 'SOS rating (z-scored within era)' },
        tournamentPerformance: { weight: 0.20, description: 'Championship=15, Runner-up=8, FF=5, E8=3, S16=1.5, R32=0.5, DNM=-2' },
        conferencePerformance: { weight: 0.10, description: 'Conference win% (z-scored) + title bonuses' },
        peakPerception: { weight: 0.15, description: 'AP peak rank, final rank, #1 bonus (z-scored within era)' },
      },
      eras: ERAS,
      eraNormalization: 'Z-score normalization within each era. All metrics are expressed as standard deviations above/below era mean.',
      nilMultiplier: 'Seasons 2021+ receive a 3% bonus for competing in the NIL/transfer portal era.',
    },

    // Top 100 team-seasons of all time
    top100TeamSeasons: rankedSeasons.slice(0, 100).map((s, i) => ({
      rank: i + 1,
      espnId: s.espnId,
      teamName: s.teamName,
      year: s.year,
      record: `${s.wins}-${s.losses}`,
      winPct: s.winPct,
      htss: s.htss,
      htssRaw: s.htssRaw,
      era: s.era,
      coach: s.coach,
      conference: s.conf,
      tourneyResult: s.tourneyRound,
      seed: s.seed,
      srs: s.srs,
      sos: s.sos,
      scoringMargin: s.scoringMargin,
      components: s.components,
      inProgress: s.endYear >= 2026,
    })),

    // Top 25 programs of all time
    top25Programs: programs.slice(0, 25),

    // Per-team best season
    bestSeasonPerTeam: Object.values(bestPerTeam).sort((a, b) => b.htss - a.htss),

    // All team-seasons (for full dataset access)
    allTeamSeasons: allSeasons.map(s => ({
      espnId: s.espnId,
      teamName: s.teamName,
      year: s.year,
      htss: s.htss,
      record: `${s.wins}-${s.losses}`,
      era: s.era,
      tourneyRound: s.tourneyRound,
      components: s.components,
    })),
  };

  // Write output
  const outputPath = path.join(BASE, 'htss_results.json');
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log(`\nResults written to ${outputPath}`);
  console.log(`  - Top 100 team-seasons`);
  console.log(`  - Top 25 programs`);
  console.log(`  - ${Object.keys(bestPerTeam).length} per-team best seasons`);
  console.log(`  - ${allSeasons.length} total team-seasons scored`);

  console.log('\n' + '='.repeat(80));
  console.log('HTSS Algorithm complete.');
  console.log('='.repeat(80));
}

main();
