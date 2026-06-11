#!/usr/bin/env node
/**
 * ============================================================================
 * UNIFIED HISTORICAL RANKINGS — PROTOTYPE v0.1
 * ============================================================================
 *
 * Hoopsipedia research prototype — NOT wired to the site.
 *
 * One composite ranking that aggregates every signal the repo already
 * computes. Two artifacts written to unified_rankings.json:
 *
 *   programAllTime — every (non-clone) program, ranked by a composite of:
 *     1. Hardware           — era-weighted championships + Final Fours,
 *                             Elite Eights, Sweet 16s, tourney bids (data.json H)
 *     2. HTSS Program Score — top-10-season average HTSS v2 (htss_v2_results.json)
 *     3. Efficiency Profile — average within-season adjEM percentile across
 *                             all the program's rated seasons (efficiency_ratings.json)
 *     4. Win Percentage     — longevity-adjusted (Bayesian-shrunk) all-time win pct
 *     5. Poll Prestige      — AP weeks ranked (data.json H, log-scaled)
 *
 *   seasonAllTime — top 250 individual team-seasons, compositing:
 *     1. HTSS v2 season score (converted back to its underlying z-scale)
 *     2. Efficiency adjEM z-score WITHIN ERA
 *     3. Tournament result (same point ladder as htss_v2.js)
 *     4. SRS z-score within era (seasons.json)
 *
 * Missing components are handled by proportional weight redistribution —
 * the same approach htss_v2.js uses — so pre-1949 programs aren't punished
 * for the efficiency engine not existing yet.
 *
 * Deterministic: no randomness, no timestamps inside ranking entries.
 *
 * Usage: node unified_rankings.js
 *
 * Author: Hoopsipedia (research prototype for Josh's review)
 * ============================================================================
 */

const fs = require('fs');
const path = require('path');

const BASE = __dirname;

// ─────────────────────────────────────────────────────────────────────────────
// WEIGHTS — the single tunable surface. Each block sums to 1.0.
// ─────────────────────────────────────────────────────────────────────────────

const WEIGHTS = {
  program: {
    hardware:    0.30, // banners are the point of the sport
    htssProgram: 0.30, // our own deepest per-season signal, aggregated
    efficiency:  0.15, // sustained statistical quality, 1949-50 onward
    winPct:      0.15, // longevity-adjusted all-time win pct
    pollPrestige: 0.10, // AP weeks ranked — public perception across decades
  },
  season: {
    htss:       0.40, // already a 9-component composite; the anchor
    effZ:       0.25, // pure statistical dominance vs era peers
    tournament: 0.20, // what the season is remembered for
    srs:        0.15, // independent (SR-derived) rating as a cross-check
  },
  // Era weights applied to each championship year (hardware component).
  // Earlier titles came from smaller fields / pre-integration talent pools.
  champEra: [
    { end: 1949, w: 0.70 }, // 8-team field, pre-integration
    { end: 1974, w: 0.85 }, // 16-25 team field
    { end: 1984, w: 0.95 }, // 32-53 team field
    { end: 9999, w: 1.00 }, // 64+ team era
  ],
  // Hardware point ladder (applied to counts from data.json H)
  hardwarePts: { champ: 10, finalFour: 4, eliteEight: 2, sweet16: 1, bid: 0.4 },
  // Bayesian shrinkage prior games for win pct (pulls short-lived programs to .500)
  winPctPriorGames: 200,
  // HTSS scale transform constants (mirror htss_v2.js output scale: 50 + 15z)
  scaleBase: 50,
  scaleSpread: 15,
};

// ─────────────────────────────────────────────────────────────────────────────
// LOADERS — same guard pattern as htss_v2.js
// ─────────────────────────────────────────────────────────────────────────────

function loadJSONOrDie(filePath) {
  if (!fs.existsSync(filePath)) {
    console.error(`ERROR: required data file missing: ${filePath}`);
    console.error('Re-run the scraper/compiler that produces it, then retry.');
    process.exit(1);
  }
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (e) {
    console.error(`ERROR: failed to parse ${filePath}: ${e.message}`);
    console.error('The file may be truncated or corrupt. Restore it from backup or re-generate it.');
    process.exit(1);
  }
}

console.log('Unified Historical Rankings — prototype');
console.log('='.repeat(80));
console.time('Data loading');

const htss       = loadJSONOrDie(path.join(BASE, 'htss_v2_results.json'));
const efficiency = loadJSONOrDie(path.join(BASE, 'efficiency_ratings.json'));
const seasonsData = loadJSONOrDie(path.join(BASE, 'seasons.json'));
const mainData   = loadJSONOrDie(path.join(BASE, 'data.json'));
const netData    = loadJSONOrDie(path.join(BASE, 'net_rankings.json')); // current-era cross-check only

console.timeEnd('Data loading');

// data.json H schema (mirrors const F in index.html):
// 0 NAME, 1 MASCOT, 2 CONF, 3 COLOR, 4 ATW, 5 ATL, 6 NC, 7 NCY (champ years),
// 8 FF, 9 E8, 10 S16, 11 NT (bids), 12 CT, 13 AA, 14 NBA, 15 APW (AP weeks)
const H = mainData.H;
const F = { NAME: 0, CONF: 2, ATW: 4, ATL: 5, NC: 6, NCY: 7, FF: 8, E8: 9, S16: 10, NT: 11, APW: 15 };

const byTeam = htss.byTeam;        // espnId -> [{season, htss, rank}] sorted desc by htss
const effSeasons = efficiency.seasons; // "YYYY-YY" -> espnId -> {adjEM, rank, ...}

// ─────────────────────────────────────────────────────────────────────────────
// CLONE EXCLUSION — identical to htss_v2.js (fingerprint + conference mismatch)
// ─────────────────────────────────────────────────────────────────────────────

function detectCloneTeams() {
  const cloneIds = new Set();

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
        .map(id => ({ id, wins: H[id]?.[F.ATW] || 0 }))
        .sort((a, b) => b.wins - a.wins);
      for (let i = 1; i < sorted.length; i++) cloneIds.add(sorted[i].id);
    }
  }

  const MAJOR_CONFS = new Set([
    'ACC', 'SEC', 'Big Ten', 'Big 12', 'Big East', 'Pac-12', 'AAC', 'WCC', 'MWC', 'American'
  ]);
  for (const id of Object.keys(seasonsData)) {
    if (cloneIds.has(id)) continue;
    const info = H[id];
    if (!info) continue;
    const dataConf = info[F.CONF];
    const seasons = seasonsData[id]?.seasons;
    if (!seasons || seasons.length < 3) continue;
    const recentConfs = seasons.slice(0, 3).map(x => x.conf).filter(Boolean);
    if (recentConfs.length === 0 || !dataConf) continue;
    const allRecentMajor = recentConfs.every(c => MAJOR_CONFS.has(c));
    if (allRecentMajor && !MAJOR_CONFS.has(dataConf)) cloneIds.add(id);
  }
  return cloneIds;
}

const CLONE_IDS = detectCloneTeams();
console.log(`Clone teams excluded: ${CLONE_IDS.size}`);

// ─────────────────────────────────────────────────────────────────────────────
// SHARED HELPERS
// ─────────────────────────────────────────────────────────────────────────────

const ERAS = [
  { name: 'Pre-Modern',       start: 0,    end: 1964 },
  { name: 'Integration Era',  start: 1965, end: 1985 },
  { name: 'Early Modern',     start: 1986, end: 1993 },
  { name: 'Mid Modern',       start: 1994, end: 2007 },
  { name: 'Late Modern',      start: 2008, end: 2015 },
  { name: 'Current',          start: 2016, end: 9999 },
];

function getSeasonEndYear(yearStr) {
  const parts = String(yearStr).split('-');
  if (parts.length === 2) {
    const startYear = parseInt(parts[0], 10);
    const endSuffix = parseInt(parts[1], 10);
    const century = Math.floor(startYear / 100) * 100;
    let endYear = century + endSuffix;
    if (endYear < startYear) endYear += 100; // 1999-00 -> 2000
    return endYear;
  }
  return parseInt(parts[0], 10);
}

function getEra(endYear) {
  for (const era of ERAS) {
    if (endYear >= era.start && endYear <= era.end) return era.name;
  }
  return 'Current';
}

// Same point ladder as htss_v2.js parseTournamentResult
function parseTournamentResult(ncaaTourney) {
  if (!ncaaTourney) return { round: 'none', points: -2.0 };
  const s = ncaaTourney.replace(/\*/g, '');
  if (s.includes('Won NCAA Tournament National Final'))  return { round: 'champion', points: 15.0 };
  if (s.includes('Lost NCAA Tournament National Final')) return { round: 'runner_up', points: 8.0 };
  if (s.includes('National Semifinal') || s.includes('Regional Final (Final Four)'))
    return { round: 'final_four', points: 5.0 };
  if (s.includes('Regional Final'))    return { round: 'elite_eight', points: 3.0 };
  if (s.includes('Regional Semifinal') || s.includes('Third Round'))
    return { round: 'sweet_sixteen', points: 1.5 };
  if (s.includes('Second Round'))      return { round: 'round_of_32', points: 0.5 };
  if (s.includes('First Round') || s.includes('First Four') || s.includes('Opening Round'))
    return { round: 'first_round', points: -0.5 };
  if (s.includes('Playing'))           return { round: 'in_progress', points: 0.0 };
  if (s.includes('Regional Third Place')) return { round: 'final_four', points: 5.0 };
  return { round: 'unknown_tourney', points: 0.0 };
}

function meanStd(values) {
  if (values.length === 0) return { mean: 0, std: 1 };
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length;
  return { mean, std: Math.sqrt(variance) || 1 };
}

// z-score an array of {raw} objects in place -> .z
function zScoreField(items, rawKey, zKey) {
  const vals = items.filter(x => x[rawKey] != null).map(x => x[rawKey]);
  const { mean, std } = meanStd(vals);
  for (const x of items) {
    x[zKey] = x[rawKey] != null ? (x[rawKey] - mean) / std : null;
  }
}

// Weighted composite with proportional redistribution of missing weights
// components: [{ value: number|null, weight: number }]
function compositeWithRedistribution(components) {
  const available = components.filter(c => c.value != null);
  const totalW = available.reduce((s, c) => s + c.weight, 0);
  if (totalW === 0) return null;
  let raw = 0;
  for (const c of available) raw += c.value * (c.weight / totalW);
  return raw;
}

const round2 = x => Math.round(x * 100) / 100;
const round3 = x => Math.round(x * 1000) / 1000;

// ─────────────────────────────────────────────────────────────────────────────
// PRECOMPUTE: efficiency percentiles per season, era stats for adjEM and SRS
// ─────────────────────────────────────────────────────────────────────────────

// effPercentile[seasonKey][espnId] = percentile of adjEM within that season (0..1)
// effByEra[eraName] = list of adjEM values (for season z-scores)
const effPercentile = {};
const effByEra = {};
for (const [seasonKey, teams] of Object.entries(effSeasons)) {
  const era = getEra(getSeasonEndYear(seasonKey));
  if (!effByEra[era]) effByEra[era] = [];
  const ids = Object.keys(teams);
  const sorted = ids.slice().sort((a, b) => teams[a].adjEM - teams[b].adjEM);
  const n = sorted.length;
  effPercentile[seasonKey] = {};
  sorted.forEach((id, i) => {
    effPercentile[seasonKey][id] = n > 1 ? i / (n - 1) : 0.5;
    effByEra[era].push(teams[id].adjEM);
  });
}
const effEraStats = {};
for (const [era, vals] of Object.entries(effByEra)) effEraStats[era] = meanStd(vals);

// SRS era stats from seasons.json
const srsByEra = {};
for (const id of Object.keys(seasonsData)) {
  if (CLONE_IDS.has(id)) continue;
  for (const s of seasonsData[id].seasons || []) {
    if (s.srs == null) continue;
    const era = getEra(getSeasonEndYear(s.year));
    if (!srsByEra[era]) srsByEra[era] = [];
    srsByEra[era].push(s.srs);
  }
}
const srsEraStats = {};
for (const [era, vals] of Object.entries(srsByEra)) srsEraStats[era] = meanStd(vals);

// Quick lookup: seasons.json row by espnId + year
const seasonRow = {};
for (const id of Object.keys(seasonsData)) {
  seasonRow[id] = {};
  for (const s of seasonsData[id].seasons || []) seasonRow[id][s.year] = s;
}

// ─────────────────────────────────────────────────────────────────────────────
// ARTIFACT 1: programAllTime
// ─────────────────────────────────────────────────────────────────────────────

function champEraWeight(year) {
  for (const band of WEIGHTS.champEra) {
    if (year <= band.end) return band.w;
  }
  return 1.0;
}

function buildPrograms() {
  const items = [];

  for (const espnId of Object.keys(H)) {
    if (CLONE_IDS.has(espnId)) continue;
    const info = H[espnId];
    const name = info[F.NAME];

    // 1. Hardware — era-weighted champs + flat FF/E8/S16/bid points.
    //    (Only championship YEARS are in the data; FF/E8/S16 are bare counts,
    //    so era weighting can only be applied to titles.)
    const champYears = Array.isArray(info[F.NCY]) ? info[F.NCY] : [];
    const weightedChamps = champYears.reduce((s, y) => s + champEraWeight(y), 0);
    const P = WEIGHTS.hardwarePts;
    const hardwareRaw =
      P.champ * weightedChamps +
      P.finalFour * (info[F.FF] || 0) +
      P.eliteEight * (info[F.E8] || 0) +
      P.sweet16 * (info[F.S16] || 0) +
      P.bid * (info[F.NT] || 0);
    // log1p tames the extreme right tail (UCLA/Kentucky) before z-scoring
    const hardwareLog = Math.log1p(hardwareRaw);

    // 2. HTSS program score — top-10-season average (mirrors htss_v2.js
    //    computeProgramRankings top10Avg). null if team not scored by HTSS.
    const hSeasons = byTeam[espnId];
    let htssProgram = null;
    if (hSeasons && hSeasons.length > 0) {
      const top10 = hSeasons.slice(0, 10); // byTeam is already sorted desc by htss
      htssProgram = top10.reduce((s, x) => s + x.htss, 0) / top10.length;
    }

    // 3. Efficiency profile — mean within-season adjEM percentile across all
    //    rated seasons (1949-50 onward). null if never rated.
    let effSum = 0, effN = 0;
    for (const [seasonKey, pct] of Object.entries(effPercentile)) {
      if (pct[espnId] != null) { effSum += pct[espnId]; effN++; }
    }
    const effProfile = effN > 0 ? effSum / effN : null;

    // 4. Longevity-adjusted win pct — Bayesian shrink toward .500
    const w = info[F.ATW] || 0, l = info[F.ATL] || 0;
    const k = WEIGHTS.winPctPriorGames;
    const winPctAdj = (w + l) > 0 ? (w + 0.5 * k) / (w + l + k) : null;

    // 5. Poll prestige — AP weeks ranked, log-scaled (0 weeks is real data, not missing)
    const apWeeks = info[F.APW] || 0;
    const pollLog = Math.log1p(apWeeks);

    items.push({
      espnId, name, conf: info[F.CONF],
      record: `${w}-${l}`,
      championships: info[F.NC] || 0,
      champYears,
      finalFours: info[F.FF] || 0,
      hardwareRaw: round2(hardwareRaw),
      _hardwareLog: hardwareLog,
      _htssProgram: htssProgram,
      _effProfile: effProfile,
      _winPctAdj: winPctAdj,
      _pollLog: pollLog,
      apWeeks,
      htssSeasons: hSeasons ? hSeasons.length : 0,
    });
  }

  // z-score each component across the program population
  zScoreField(items, '_hardwareLog', '_zHardware');
  zScoreField(items, '_htssProgram', '_zHtss');
  zScoreField(items, '_effProfile', '_zEff');
  zScoreField(items, '_winPctAdj', '_zWinPct');
  zScoreField(items, '_pollLog', '_zPoll');

  const W = WEIGHTS.program;
  for (const it of items) {
    const raw = compositeWithRedistribution([
      { value: it._zHardware, weight: W.hardware },
      { value: it._zHtss,     weight: W.htssProgram },
      { value: it._zEff,      weight: W.efficiency },
      { value: it._zWinPct,   weight: W.winPct },
      { value: it._zPoll,     weight: W.pollPrestige },
    ]);
    it._raw = raw;
    it.score = raw != null ? round2(WEIGHTS.scaleBase + WEIGHTS.scaleSpread * raw) : null;
    it.components = {
      hardware:    it._zHardware != null ? round3(it._zHardware) : null,
      htssProgram: it._zHtss != null ? round3(it._zHtss) : null,
      efficiency:  it._zEff != null ? round3(it._zEff) : null,
      winPct:      it._zWinPct != null ? round3(it._zWinPct) : null,
      pollPrestige: it._zPoll != null ? round3(it._zPoll) : null,
    };
  }

  const ranked = items
    .filter(it => it.score != null)
    .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));

  return ranked.map((it, i) => ({
    rank: i + 1,
    espnId: it.espnId,
    team: it.name,
    conf: it.conf,
    score: it.score,
    allTimeRecord: it.record,
    championships: it.championships,
    finalFours: it.finalFours,
    apWeeks: it.apWeeks,
    components: it.components,
  }));
}

// ─────────────────────────────────────────────────────────────────────────────
// ARTIFACT 2: seasonAllTime (top 250 team-seasons)
// ─────────────────────────────────────────────────────────────────────────────

function buildSeasons() {
  const items = [];

  for (const [espnId, hSeasons] of Object.entries(byTeam)) {
    if (CLONE_IDS.has(espnId)) continue;
    const name = H[espnId] ? H[espnId][F.NAME] : `Unknown (${espnId})`;

    for (const hs of hSeasons) {
      const year = hs.season;
      const endYear = getSeasonEndYear(year);
      const era = getEra(endYear);
      const row = seasonRow[espnId] ? seasonRow[espnId][year] : null;

      // 1. HTSS — invert the 50 + 15z display transform back to z-scale
      const htssZ = (hs.htss - WEIGHTS.scaleBase) / WEIGHTS.scaleSpread;

      // 2. Efficiency adjEM z-score within era
      let effZ = null, adjEM = null;
      const effRow = effSeasons[year] ? effSeasons[year][espnId] : null;
      if (effRow && effRow.adjEM != null && effEraStats[era]) {
        adjEM = effRow.adjEM;
        effZ = (adjEM - effEraStats[era].mean) / effEraStats[era].std;
      }

      // 3. Tournament result — same ladder as HTSS, scaled so champion ≈ +3.0z
      let tourneyZ = null, tourneyRound = null;
      if (row) {
        const t = parseTournamentResult(row.ncaaTourney);
        tourneyRound = t.round;
        tourneyZ = (t.points / 15.0) * 3.0;
      }

      // 4. SRS z-score within era
      let srsZ = null;
      if (row && row.srs != null && srsEraStats[era]) {
        srsZ = (row.srs - srsEraStats[era].mean) / srsEraStats[era].std;
      }

      const W = WEIGHTS.season;
      const raw = compositeWithRedistribution([
        { value: htssZ,    weight: W.htss },
        { value: effZ,     weight: W.effZ },
        { value: tourneyZ, weight: W.tournament },
        { value: srsZ,     weight: W.srs },
      ]);
      if (raw == null) continue;

      items.push({
        espnId,
        team: name,
        season: year,
        era,
        score: round2(WEIGHTS.scaleBase + WEIGHTS.scaleSpread * raw),
        htss: hs.htss,
        adjEM,
        record: row ? row.record : null,
        coach: row ? row.coach : null,
        conf: row ? row.conf : null,
        seed: row && row.seed != null ? row.seed : null,
        tourneyResult: tourneyRound,
        components: {
          htss:       round3(htssZ),
          effZ:       effZ != null ? round3(effZ) : null,
          tournament: tourneyZ != null ? round3(tourneyZ) : null,
          srs:        srsZ != null ? round3(srsZ) : null,
        },
      });
    }
  }

  items.sort((a, b) =>
    b.score - a.score ||
    a.team.localeCompare(b.team) ||
    a.season.localeCompare(b.season));

  return items.slice(0, 250).map((s, i) => ({ rank: i + 1, ...s }));
}

// ─────────────────────────────────────────────────────────────────────────────
// BUILD + SANITY CHECKS
// ─────────────────────────────────────────────────────────────────────────────

console.log('Building programAllTime...');
const programAllTime = buildPrograms();
console.log(`  ${programAllTime.length} programs ranked`);

console.log('Building seasonAllTime...');
const seasonAllTime = buildSeasons();
console.log(`  top ${seasonAllTime.length} team-seasons kept`);

// NET cross-check (informational only — current era)
const netCount = Object.keys(netData).length;
console.log(`  (net_rankings.json loaded for reference: ${netCount} entries, not weighted in composite)`);

let sanityFailures = 0;

// Check 1: blue bloods in top 10
const BLUE_BLOODS = ['UCLA Bruins', 'Kentucky Wildcats', 'North Carolina Tar Heels', 'Duke Blue Devils', 'Kansas Jayhawks'];
const top10Names = programAllTime.slice(0, 10).map(p => p.team);
console.log('\nSanity checks:');
for (const bb of BLUE_BLOODS) {
  const rank = programAllTime.findIndex(p => p.team === bb) + 1;
  const ok = rank > 0 && rank <= 10;
  if (!ok) {
    sanityFailures++;
    console.log(`  !!! SANITY FAIL: ${bb} ranked #${rank || 'UNRANKED'} (expected top 10) !!!`);
  } else {
    console.log(`  OK: ${bb} is #${rank}`);
  }
}

// Check 2: canonical great seasons appear high in seasonAllTime
const CANON = [
  { team: 'UCLA Bruins', season: '1972-73', within: 25 },
  { team: 'Kentucky Wildcats', season: '1995-96', within: 25 },
  { team: 'Villanova Wildcats', season: '2017-18', within: 50 },
];
for (const c of CANON) {
  const idx = seasonAllTime.findIndex(s => s.team === c.team && s.season === c.season);
  const ok = idx >= 0 && idx < c.within;
  if (!ok) {
    sanityFailures++;
    console.log(`  !!! SANITY FAIL: ${c.season} ${c.team} at rank ${idx >= 0 ? idx + 1 : '>250'} (expected top ${c.within}) !!!`);
  } else {
    console.log(`  OK: ${c.season} ${c.team} is #${idx + 1}`);
  }
}

if (sanityFailures > 0) {
  console.log(`\n${'!'.repeat(80)}`);
  console.log(`!!! ${sanityFailures} SANITY CHECK(S) FAILED — output still written for Josh's review !!!`);
  console.log('!'.repeat(80));
} else {
  console.log('\nAll sanity checks passed.');
}

// ─────────────────────────────────────────────────────────────────────────────
// OUTPUT — atomic write (tmp + rename), deterministic content
// ─────────────────────────────────────────────────────────────────────────────

const output = {
  metadata: {
    version: '0.1-prototype',
    algorithm: 'Unified Historical Rankings — aggregates HTSS v2, efficiency engine, hardware, win pct, AP poll prestige',
    note: 'Research prototype. Not wired to the site. See RANKING_METHODOLOGY.md.',
    weights: WEIGHTS,
    inputs: [
      'htss_v2_results.json (byTeam season scores)',
      'efficiency_ratings.json (adjEM 1949-50 onward)',
      'seasons.json (records, SRS, AP, tournament results)',
      'data.json H (championships, Final Fours, all-time records, AP weeks)',
    ],
    programCount: programAllTime.length,
    seasonCount: seasonAllTime.length,
    excludedClones: CLONE_IDS.size,
    sanityFailures,
  },
  programAllTime,
  seasonAllTime,
};

const outPath = path.join(BASE, 'unified_rankings.json');
const tmpPath = outPath + '.tmp';
fs.writeFileSync(tmpPath, JSON.stringify(output, null, 2));
fs.renameSync(tmpPath, outPath);
console.log(`\nWrote ${outPath}`);

// Console summary
console.log('\nTOP 15 PROGRAMS (all-time):');
for (const p of programAllTime.slice(0, 15)) {
  console.log(`  ${String(p.rank).padStart(2)}. ${p.team.padEnd(30)} ${String(p.score).padStart(6)}  (${p.championships} titles, ${p.finalFours} FFs)`);
}
console.log('\nTOP 15 TEAM-SEASONS (all-time):');
for (const s of seasonAllTime.slice(0, 15)) {
  console.log(`  ${String(s.rank).padStart(2)}. ${(s.season + ' ' + s.team).padEnd(38)} ${String(s.score).padStart(6)}  ${s.record || '?'}  ${s.tourneyResult || '?'}`);
}
console.log('\nDone.');
