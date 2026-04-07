#!/usr/bin/env node
/**
 * Hoopsipedia Proprietary Efficiency Engine
 * ==========================================
 * KenPom/NET-style analytics applied retroactively to 75+ years of college basketball.
 * Computes Adjusted Efficiency Margin (adjEM), Adjusted Offensive/Defensive Efficiency,
 * quality tier records, and schedule strength for every team-season.
 *
 * Usage: node efficiency_engine.js
 * Output: efficiency_ratings.json
 */

const fs = require('fs');
const path = require('path');

const DATA_DIR = __dirname;
const HCA = 3.5; // Home court advantage in points
const CONVERGENCE_THRESHOLD = 0.01; // 0.01 on a ~40pt scale = sufficient precision
const MAX_ITERATIONS = 100;
const DAMPING = 0.5; // Blend 50% new, 50% old to ensure convergence
const BAYESIAN_MIN_GAMES = 10;

// ─── Era-specific possession estimation divisors ───
// These convert total_pts to estimated per-team possessions
// Formula: poss_per_team = total_pts / divisor
// Calibrated so that era-average scoring produces era-average pace
function getPossessionDivisor(year) {
  // year = starting year of season (e.g., 2024 for 2024-25)
  if (year < 1960) return 2.30; // ~80 poss/team, high-scoring pre-shot-clock era
  if (year < 1972) return 2.25; // ~75 poss/team
  if (year < 1986) return 2.20; // ~72 poss/team, post-Wooden
  if (year < 1994) return 2.15; // ~70 poss/team, 45-sec clock
  if (year < 2008) return 2.10; // ~67 poss/team, 35-sec clock
  if (year < 2016) return 2.08; // ~66 poss/team
  return 2.12;                  // ~68 poss/team, 30-sec clock (slightly faster)
}

// ─── Season key from date ───
function dateToSeasonKey(dateStr) {
  const [y, m] = dateStr.split('-').map(Number);
  // Games before June belong to the season that started the previous fall
  const startYear = m < 6 ? y - 1 : y;
  const endYear = startYear + 1;
  return `${startYear}-${String(endYear).slice(2)}`;
}

function seasonKeyToStartYear(key) {
  return parseInt(key.split('-')[0], 10);
}

// ─── Load all game data ───
function loadAllTeams() {
  console.log('Loading game data...');
  console.time('Data loading');

  const espnToSr = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'espn_to_sr.json'), 'utf8'));

  // Build reverse map: slug → ESPN ID
  const slugToEspn = {};
  for (const [espnId, slug] of Object.entries(espnToSr)) {
    slugToEspn[slug] = espnId;
  }

  const teams = {}; // espnId -> { slug, games[] }
  let totalGames = 0;

  for (const file of ['games_1.json', 'games_2.json', 'games_3.json']) {
    const data = JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), 'utf8'));
    for (const espnId of Object.keys(data)) {
      const entry = data[espnId];
      let games, slug;
      if (entry.games && Array.isArray(entry.games)) {
        games = entry.games;
        slug = entry.slug || espnToSr[espnId] || 'unknown';
      } else if (Array.isArray(entry)) {
        games = entry;
        slug = espnToSr[espnId] || 'unknown';
      } else {
        console.warn(`Skipping team ${espnId}: unexpected structure`);
        continue;
      }
      teams[espnId] = { slug, games };
      totalGames += games.length;
    }
  }

  console.timeEnd('Data loading');
  console.log(`Loaded ${Object.keys(teams).length} teams, ${totalGames.toLocaleString()} games`);
  return { teams, slugToEspn, espnToSr, totalGames };
}

// ─── Step 1: Group games by season ───
function groupBySeason(teams, slugToEspn) {
  console.log('\nStep 1: Grouping games by season...');
  console.time('Season grouping');

  // seasonData[seasonKey][espnId] = { games: [...processedGames], slug }
  const seasonData = {};
  let unmappedCount = 0;
  let totalProcessed = 0;

  for (const [espnId, team] of Object.entries(teams)) {
    for (const game of team.games) {
      const seasonKey = dateToSeasonKey(game.date);
      if (!seasonData[seasonKey]) seasonData[seasonKey] = {};
      if (!seasonData[seasonKey][espnId]) {
        seasonData[seasonKey][espnId] = { games: [], slug: team.slug };
      }

      // Resolve opponent ESPN ID
      let oppId = game.opp || null;
      if (!oppId && game.opp_slug) {
        oppId = slugToEspn[game.opp_slug] || null;
      }
      const mappable = oppId !== null && teams[oppId] !== undefined;
      if (!mappable) unmappedCount++;

      seasonData[seasonKey][espnId].games.push({
        date: game.date,
        loc: game.loc || 'N',
        pts: game.pts,
        oppPts: game.opp_pts,
        w: game.w,
        oppId: mappable ? oppId : null,
        oppSlug: game.opp_slug,
      });
      totalProcessed++;
    }
  }

  const seasonKeys = Object.keys(seasonData).sort();
  console.timeEnd('Season grouping');
  console.log(`  ${seasonKeys.length} seasons (${seasonKeys[0]} to ${seasonKeys[seasonKeys.length - 1]})`);
  console.log(`  ${unmappedCount.toLocaleString()} unmappable opponent games (${(100 * unmappedCount / totalProcessed).toFixed(1)}%)`);
  return seasonData;
}

// ─── Steps 2-3: Compute raw efficiency metrics for each game ───
function computeRawEfficiency(seasonData) {
  console.log('\nSteps 2-3: Computing raw efficiency metrics...');
  console.time('Raw efficiency');

  for (const [seasonKey, teams] of Object.entries(seasonData)) {
    const startYear = seasonKeyToStartYear(seasonKey);
    const divisor = getPossessionDivisor(startYear);

    for (const [espnId, team] of Object.entries(teams)) {
      // Filter out invalid games (0-0 scores from COVID cancellations, forfeits, etc.)
      team.games = team.games.filter(g => g.pts + g.oppPts > 0);

      for (const game of team.games) {
        const rawMargin = game.pts - game.oppPts;

        // HCA adjustment
        let adjMargin;
        if (game.loc === 'H') adjMargin = rawMargin - HCA;
        else if (game.loc === 'A') adjMargin = rawMargin + HCA;
        else adjMargin = rawMargin;

        // Pace estimation (per-team possessions)
        const totalPts = game.pts + game.oppPts;
        const poss = totalPts / divisor;
        const pace100 = 100 / poss;

        game.per100Margin = adjMargin * pace100;
        game.offEff = game.pts * pace100;
        game.defEff = game.oppPts * pace100;
        game.poss = poss;
      }
    }
  }

  console.timeEnd('Raw efficiency');
}

// ─── Step 4: Iterative opponent adjustment ───
function iterateRatings(seasonData) {
  console.log('\nStep 4: Iterative opponent adjustment...');
  console.time('Iteration');

  let totalIterations = 0;
  const seasonKeys = Object.keys(seasonData).sort();

  for (const seasonKey of seasonKeys) {
    const teams = seasonData[seasonKey];
    const teamIds = Object.keys(teams);

    // Initialize ratings: average per100Margin, offEff, defEff
    const ratings = {};
    for (const id of teamIds) {
      const games = teams[id].games;
      if (games.length === 0) continue;
      let sumMargin = 0, sumOff = 0, sumDef = 0;
      for (const g of games) {
        sumMargin += g.per100Margin;
        sumOff += g.offEff;
        sumDef += g.defEff;
      }
      ratings[id] = {
        adjEM: sumMargin / games.length,
        adjOE: sumOff / games.length,
        adjDE: sumDef / games.length,
      };
    }

    // Compute league averages for centering and Bayesian regression
    let leagueSum = 0, leagueOESum = 0, leagueDESum = 0, leagueCount = 0;
    for (const id of Object.keys(ratings)) {
      leagueSum += ratings[id].adjEM;
      leagueOESum += ratings[id].adjOE;
      leagueDESum += ratings[id].adjDE;
      leagueCount++;
    }
    const leagueAvg = leagueCount > 0 ? leagueSum / leagueCount : 0;
    const leagueAvgOE = leagueCount > 0 ? leagueOESum / leagueCount : 100;
    const leagueAvgDE = leagueCount > 0 ? leagueDESum / leagueCount : 100;

    // Convert OE/DE to relative-to-average for iteration, then restore at end
    // adjOE_rel = adjOE - leagueAvgOE (positive = better than average offense)
    // adjDE_rel = adjDE - leagueAvgDE (negative = better than average defense)
    for (const id of Object.keys(ratings)) {
      ratings[id].adjOE_rel = ratings[id].adjOE - leagueAvgOE;
      ratings[id].adjDE_rel = ratings[id].adjDE - leagueAvgDE;
    }

    // Iterate
    let iterations = 0;
    let maxDelta;
    do {
      maxDelta = 0;
      const newRatings = {};

      for (const id of Object.keys(ratings)) {
        const games = teams[id].games;
        let sumEM = 0, sumOE = 0, sumDE = 0;
        let countMappable = 0;

        for (const g of games) {
          if (g.oppId && ratings[g.oppId] !== undefined) {
            // Opponent-adjusted margin: raw margin + opponent overall strength
            sumEM += g.per100Margin + ratings[g.oppId].adjEM;
            // Opponent-adjusted offense: raw OE relative to avg + opponent DEF weakness
            // If opponent has bad defense (positive adjDE_rel), credit our offense less
            sumOE += (g.offEff - leagueAvgOE) - ratings[g.oppId].adjDE_rel;
            // Opponent-adjusted defense: raw DE relative to avg - opponent OFF strength
            // If opponent has good offense (positive adjOE_rel), credit our defense more
            sumDE += (g.defEff - leagueAvgDE) - ratings[g.oppId].adjOE_rel;
            countMappable++;
          }
        }

        if (countMappable === 0) {
          newRatings[id] = { ...ratings[id] };
          continue;
        }

        let newEM = sumEM / countMappable;
        let newOE_rel = sumOE / countMappable;
        let newDE_rel = sumDE / countMappable;

        // Bayesian regression for teams with few games
        if (games.length < BAYESIAN_MIN_GAMES) {
          const weight = games.length / BAYESIAN_MIN_GAMES;
          newEM = weight * newEM + (1 - weight) * leagueAvg;
          newOE_rel = weight * newOE_rel; // regress toward 0 (average)
          newDE_rel = weight * newDE_rel;
        }

        // Apply damping to prevent oscillation
        newEM = DAMPING * newEM + (1 - DAMPING) * ratings[id].adjEM;
        newOE_rel = DAMPING * newOE_rel + (1 - DAMPING) * ratings[id].adjOE_rel;
        newDE_rel = DAMPING * newDE_rel + (1 - DAMPING) * ratings[id].adjDE_rel;

        const delta = Math.abs(newEM - ratings[id].adjEM);
        if (delta > maxDelta) maxDelta = delta;

        newRatings[id] = { adjEM: newEM, adjOE_rel: newOE_rel, adjDE_rel: newDE_rel };
      }

      // Copy new ratings and re-center to prevent drift
      let sumNewEM = 0, sumNewOE = 0, sumNewDE = 0;
      const newIds = Object.keys(newRatings);
      for (const id of newIds) {
        sumNewEM += newRatings[id].adjEM;
        sumNewOE += newRatings[id].adjOE_rel;
        sumNewDE += newRatings[id].adjDE_rel;
      }
      const avgNewEM = sumNewEM / newIds.length;
      const avgNewOE = sumNewOE / newIds.length;
      const avgNewDE = sumNewDE / newIds.length;
      for (const id of newIds) {
        ratings[id] = {
          adjEM: newRatings[id].adjEM - avgNewEM,
          adjOE_rel: newRatings[id].adjOE_rel - avgNewOE,
          adjDE_rel: newRatings[id].adjDE_rel - avgNewDE,
        };
      }
      iterations++;
    } while (maxDelta > CONVERGENCE_THRESHOLD && iterations < MAX_ITERATIONS);

    // Center ratings: force league average adjEM to 0
    let avgEM = 0;
    const ratingIds = Object.keys(ratings);
    for (const id of ratingIds) avgEM += ratings[id].adjEM;
    avgEM /= ratingIds.length;

    // Center OE/DE relative values
    let avgOE_rel = 0, avgDE_rel = 0;
    for (const id of ratingIds) { avgOE_rel += ratings[id].adjOE_rel; avgDE_rel += ratings[id].adjDE_rel; }
    avgOE_rel /= ratingIds.length;
    avgDE_rel /= ratingIds.length;

    for (const id of ratingIds) {
      ratings[id].adjEM -= avgEM;
      ratings[id].adjOE_rel -= avgOE_rel;
      ratings[id].adjDE_rel -= avgDE_rel;
      // Convert back to absolute scale: adjOE = leagueAvgOE + relative
      ratings[id].adjOE = leagueAvgOE + ratings[id].adjOE_rel;
      ratings[id].adjDE = leagueAvgDE + ratings[id].adjDE_rel;
      // Fine-tune: ensure adjEM = adjOE - adjDE exactly
      const currentDiff = ratings[id].adjOE - ratings[id].adjDE;
      const adjustment = (ratings[id].adjEM - currentDiff) / 2;
      ratings[id].adjOE += adjustment;
      ratings[id].adjDE -= adjustment;
    }

    // Store final ratings back
    for (const id of Object.keys(ratings)) {
      teams[id].rating = { adjEM: ratings[id].adjEM, adjOE: ratings[id].adjOE, adjDE: ratings[id].adjDE };
    }
    teams._iterations = iterations;
    totalIterations += iterations;

    // Progress for select seasons
    if (seasonKey.endsWith('-25') || seasonKey.endsWith('-00') || seasonKey.endsWith('-50') || seasonKey === seasonKeys[0] || seasonKey === seasonKeys[seasonKeys.length - 1]) {
      console.log(`  ${seasonKey}: ${iterations} iterations, final delta ${maxDelta.toFixed(6)}, ${Object.keys(ratings).length} teams`);
    }
  }

  console.timeEnd('Iteration');
  console.log(`  Total iterations across all seasons: ${totalIterations}`);
  return totalIterations;
}

// ─── Step 5: Rankings, tiers, SOS ───
function computeTiersAndRankings(seasonData) {
  console.log('\nStep 5: Rankings, tiers, and schedule strength...');
  console.time('Tiers & Rankings');

  for (const [seasonKey, teams] of Object.entries(seasonData)) {
    const teamIds = Object.keys(teams).filter(id => id !== '_iterations' && teams[id].rating);

    // Rank by adjEM
    const ranked = teamIds
      .map(id => ({ id, adjEM: teams[id].rating.adjEM }))
      .sort((a, b) => b.adjEM - a.adjEM);

    const rankMap = {};
    ranked.forEach((t, i) => { rankMap[t.id] = i + 1; });

    // Assign tiers and compute SOS
    for (const id of teamIds) {
      const team = teams[id];
      team.rank = rankMap[id];

      // Compute SOS = average opponent adjEM
      let sosSum = 0, sosCount = 0;
      const tiers = { t1w: 0, t1l: 0, t2w: 0, t2l: 0, t3w: 0, t3l: 0, t4w: 0, t4l: 0 };

      for (const g of team.games) {
        if (g.oppId && teams[g.oppId] && teams[g.oppId].rating) {
          sosSum += teams[g.oppId].rating.adjEM;
          sosCount++;

          const oppRank = rankMap[g.oppId];
          const loc = g.loc;
          let tier;

          if (loc === 'H') {
            // Home: tougher thresholds
            if (oppRank <= 50) tier = 1;
            else if (oppRank <= 100) tier = 2;
            else if (oppRank <= 200) tier = 3;
            else tier = 4;
          } else {
            // Away or Neutral
            if (oppRank <= 30) tier = 1;
            else if (oppRank <= 75) tier = 2;
            else if (oppRank <= 160) tier = 3;
            else tier = 4;
          }

          const suffix = g.w ? 'w' : 'l';
          tiers[`t${tier}${suffix}`]++;
        }
      }

      team.sos = sosCount > 0 ? sosSum / sosCount : 0;
      team.tiers = tiers;

      // Record
      let wins = 0, losses = 0;
      for (const g of team.games) {
        if (g.w) wins++;
        else losses++;
      }
      team.record = `${wins}-${losses}`;
    }

    // Compute SOS rank
    const sosSorted = teamIds
      .filter(id => teams[id].sos !== undefined)
      .sort((a, b) => teams[b].sos - teams[a].sos);
    sosSorted.forEach((id, i) => { teams[id].sosRank = i + 1; });
  }

  console.timeEnd('Tiers & Rankings');
}

// ─── Validation against SRS ───
function validateAgainstSRS(seasonData, espnToSr) {
  console.log('\nValidation: Comparing against SRS from seasons.json...');
  const seasonsFile = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'seasons.json'), 'utf8'));

  // Build lookup: srsData[espnId][seasonKey] = srs
  const srsData = {};
  for (const [espnId, teamData] of Object.entries(seasonsFile)) {
    if (!teamData.seasons) continue;
    for (const s of teamData.seasons) {
      if (s.srs !== undefined && s.year) {
        if (!srsData[espnId]) srsData[espnId] = {};
        srsData[espnId][s.year] = s.srs;
      }
    }
  }

  // Collect pairs for correlation
  const pairs = []; // { seasonKey, espnId, adjEM, srs, slug }
  for (const [seasonKey, teams] of Object.entries(seasonData)) {
    for (const id of Object.keys(teams)) {
      if (id === '_iterations') continue;
      if (!teams[id].rating) continue;
      if (srsData[id] && srsData[id][seasonKey] !== undefined) {
        pairs.push({
          seasonKey,
          espnId: id,
          adjEM: teams[id].rating.adjEM,
          srs: srsData[id][seasonKey],
          slug: teams[id].slug,
          rank: teams[id].rank,
        });
      }
    }
  }

  console.log(`  Found ${pairs.length.toLocaleString()} overlapping team-seasons for validation`);

  // Spearman rank correlation — compute per season, then average
  const seasonPairs = {};
  for (const p of pairs) {
    if (!seasonPairs[p.seasonKey]) seasonPairs[p.seasonKey] = [];
    seasonPairs[p.seasonKey].push(p);
  }

  let totalCorr = 0, corrCount = 0;
  for (const [sk, sp] of Object.entries(seasonPairs)) {
    if (sp.length < 10) continue; // Need enough data points

    // Rank by adjEM
    const byEM = [...sp].sort((a, b) => b.adjEM - a.adjEM);
    const byRankEM = {};
    byEM.forEach((p, i) => { byRankEM[p.espnId] = i + 1; });

    // Rank by SRS
    const bySRS = [...sp].sort((a, b) => b.srs - a.srs);
    const byRankSRS = {};
    bySRS.forEach((p, i) => { byRankSRS[p.espnId] = i + 1; });

    // Spearman: 1 - 6*sum(d^2) / (n*(n^2-1))
    const n = sp.length;
    let sumD2 = 0;
    for (const p of sp) {
      const d = byRankEM[p.espnId] - byRankSRS[p.espnId];
      sumD2 += d * d;
    }
    const corr = 1 - (6 * sumD2) / (n * (n * n - 1));
    totalCorr += corr;
    corrCount++;
  }

  const avgCorrelation = corrCount > 0 ? totalCorr / corrCount : 0;
  console.log(`  Average Spearman rank correlation: ${avgCorrelation.toFixed(4)} (across ${corrCount} seasons)`);

  // Sample comparisons: well-known team-seasons
  const sampleSlugs = [
    { slug: 'duke', seasons: ['2000-01', '2014-15', '2009-10'] },
    { slug: 'north-carolina', seasons: ['2004-05', '2008-09', '2016-17'] },
    { slug: 'kentucky', seasons: ['2011-12', '2014-15'] },
    { slug: 'kansas', seasons: ['2007-08', '2019-20'] },
    { slug: 'gonzaga', seasons: ['2016-17', '2020-21'] },
    { slug: 'connecticut', seasons: ['2003-04', '2013-14', '2023-24'] },
    { slug: 'villanova', seasons: ['2015-16', '2017-18'] },
    { slug: 'michigan-state', seasons: ['1999-00'] },
    { slug: 'florida', seasons: ['2005-06', '2006-07'] },
    { slug: 'indiana', seasons: ['1975-76'] },
  ];

  const sampleComparisons = [];
  for (const p of pairs) {
    for (const s of sampleSlugs) {
      if (p.slug === s.slug && s.seasons.includes(p.seasonKey)) {
        sampleComparisons.push({
          team: p.slug,
          season: p.seasonKey,
          adjEM: Math.round(p.adjEM * 100) / 100,
          srs: p.srs,
          emRank: p.rank,
        });
      }
    }
  }
  sampleComparisons.sort((a, b) => b.adjEM - a.adjEM);

  return { avgCorrelation, sampleComparisons, pairCount: pairs.length };
}

// ─── Build output ───
function buildOutput(seasonData, totalGames, totalIterations, validation, espnToSr) {
  console.log('\nBuilding output...');
  console.time('Output build');

  const seasonsFile = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'seasons.json'), 'utf8'));

  // Build team name lookup from seasons.json and espnToSr
  const teamNames = {};
  for (const [id, slug] of Object.entries(espnToSr)) {
    // Convert slug to readable name
    teamNames[id] = slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }

  const output = {
    metadata: {
      generated: new Date().toISOString(),
      totalTeams: Object.keys(espnToSr).length,
      totalGames,
      totalSeasons: Object.keys(seasonData).length,
      iterations: totalIterations,
    },
    seasons: {},
    allTimeTop100: [],
    validation: {
      srsCorrelation: Math.round(validation.avgCorrelation * 10000) / 10000,
      overlapCount: validation.pairCount,
      sampleComparisons: validation.sampleComparisons,
    },
  };

  const allTimeEntries = [];

  for (const [seasonKey, teams] of Object.entries(seasonData)) {
    const seasonOut = {};
    const teamIds = Object.keys(teams).filter(id => id !== '_iterations' && teams[id].rating);

    for (const id of teamIds) {
      const t = teams[id];
      const entry = {
        team: teamNames[id] || t.slug,
        adjEM: Math.round(t.rating.adjEM * 100) / 100,
        adjOE: Math.round(t.rating.adjOE * 100) / 100,
        adjDE: Math.round(t.rating.adjDE * 100) / 100,
        rank: t.rank,
        record: t.record,
        sos: Math.round(t.sos * 100) / 100,
        sosRank: t.sosRank,
        tiers: t.tiers,
        games: t.games.length,
      };
      seasonOut[id] = entry;

      allTimeEntries.push({
        ...entry,
        espnId: id,
        season: seasonKey,
      });
    }

    output.seasons[seasonKey] = seasonOut;
  }

  // Top 100 all time
  allTimeEntries.sort((a, b) => b.adjEM - a.adjEM);
  output.allTimeTop100 = allTimeEntries.slice(0, 100).map(e => ({
    season: e.season,
    espnId: e.espnId,
    team: e.team,
    adjEM: e.adjEM,
    adjOE: e.adjOE,
    adjDE: e.adjDE,
    record: e.record,
    rank: e.rank,
  }));

  console.timeEnd('Output build');

  // ─── Console output ───
  console.log('\n' + '='.repeat(80));
  console.log('TOP 50 TEAM-SEASONS OF ALL TIME (by adjEM)');
  console.log('='.repeat(80));
  console.log(`${'#'.padStart(3)} ${'Season'.padEnd(8)} ${'Team'.padEnd(28)} ${'adjEM'.padStart(7)} ${'adjOE'.padStart(7)} ${'adjDE'.padStart(7)} ${'Record'.padEnd(8)}`);
  console.log('-'.repeat(80));
  for (let i = 0; i < 50 && i < allTimeEntries.length; i++) {
    const e = allTimeEntries[i];
    console.log(
      `${String(i + 1).padStart(3)} ${e.season.padEnd(8)} ${e.team.padEnd(28)} ${e.adjEM.toFixed(2).padStart(7)} ${e.adjOE.toFixed(2).padStart(7)} ${e.adjDE.toFixed(2).padStart(7)} ${e.record.padEnd(8)}`
    );
  }

  console.log('\n' + '='.repeat(80));
  console.log('TOP 25 CURRENT ERA (2016+)');
  console.log('='.repeat(80));
  const modernEntries = allTimeEntries.filter(e => seasonKeyToStartYear(e.season) >= 2016);
  console.log(`${'#'.padStart(3)} ${'Season'.padEnd(8)} ${'Team'.padEnd(28)} ${'adjEM'.padStart(7)} ${'adjOE'.padStart(7)} ${'adjDE'.padStart(7)} ${'Record'.padEnd(8)}`);
  console.log('-'.repeat(80));
  for (let i = 0; i < 25 && i < modernEntries.length; i++) {
    const e = modernEntries[i];
    console.log(
      `${String(i + 1).padStart(3)} ${e.season.padEnd(8)} ${e.team.padEnd(28)} ${e.adjEM.toFixed(2).padStart(7)} ${e.adjOE.toFixed(2).padStart(7)} ${e.adjDE.toFixed(2).padStart(7)} ${e.record.padEnd(8)}`
    );
  }

  console.log('\n' + '='.repeat(80));
  console.log('SRS VALIDATION');
  console.log('='.repeat(80));
  console.log(`Spearman rank correlation: ${validation.avgCorrelation.toFixed(4)}`);
  console.log(`Overlapping team-seasons: ${validation.pairCount.toLocaleString()}`);
  console.log('\nSample comparisons (well-known team-seasons):');
  console.log(`${'Team'.padEnd(20)} ${'Season'.padEnd(8)} ${'adjEM'.padStart(7)} ${'SRS'.padStart(7)} ${'Rank'.padStart(5)}`);
  console.log('-'.repeat(50));
  for (const c of validation.sampleComparisons) {
    console.log(
      `${c.team.padEnd(20)} ${c.season.padEnd(8)} ${c.adjEM.toFixed(2).padStart(7)} ${c.srs.toFixed(2).padStart(7)} ${String(c.emRank).padStart(5)}`
    );
  }

  return output;
}

// ─── Main ───
function main() {
  console.log('Hoopsipedia Efficiency Engine v1.0');
  console.log('==================================\n');
  console.time('Total runtime');

  // Load data
  const { teams, slugToEspn, espnToSr, totalGames } = loadAllTeams();

  // Step 1: Group by season
  const seasonData = groupBySeason(teams, slugToEspn);

  // Steps 2-3: Raw efficiency
  computeRawEfficiency(seasonData);

  // Step 4: Iterative opponent adjustment
  const totalIterations = iterateRatings(seasonData);

  // Step 5: Tiers and rankings
  computeTiersAndRankings(seasonData);

  // Validation
  const validation = validateAgainstSRS(seasonData, espnToSr);

  // Build and write output
  const output = buildOutput(seasonData, totalGames, totalIterations, validation, espnToSr);

  const outputPath = path.join(DATA_DIR, 'efficiency_ratings.json');
  console.log(`\nWriting ${outputPath}...`);
  console.time('File write');
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.timeEnd('File write');

  const stats = fs.statSync(outputPath);
  console.log(`Output file size: ${(stats.size / 1024 / 1024).toFixed(1)} MB`);

  console.log('');
  console.timeEnd('Total runtime');
  console.log('\nDone!');
}

main();
