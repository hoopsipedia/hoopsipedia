// Cloudflare Pages Function — "Ask Hoopsipedia" conversational AI chat
// POST /api/chat — accepts { messages: [{role, content}] }, returns SSE stream

// ── Field indices for data.json H array ──
const F = {
  NAME: 0, MASCOT: 1, CONF: 2, COLOR: 3, ATW: 4, ATL: 5,
  NC: 6, NCY: 7, FF: 8, E8: 9, S16: 10, TOURNEY: 11,
  CONF_TITLES: 12, AA: 13, NBA_FIRST: 14, AP_WEEKS: 15
};

// ── Module-level data caches (persist across requests within isolate) ──
let cachedData = null;       // data.json
let cachedSlugAliases = null; // slug_aliases.json
let cachedSeasons = null;     // seasons.json
let cachedH2H = null;         // h2h.json
let cachedHTSS = null;        // htss_v2_results.json
let cachedEfficiency = null;  // efficiency_ratings.json
let cachedDraft = null;       // draft_history.json
let cachedTeamHistory = null; // team_history.json
let cachedUpsets = null;      // upset_history.json
let cachedTimeMachine = null; // time_machine_results.json
let cachedGames1 = null;      // games_1.json
let cachedGames2 = null;      // games_2.json
let cachedGames3 = null;      // games_3.json

// ── Rate limiting ──
const rateLimits = new Map();
const RATE_LIMIT = 20;
const RATE_WINDOW = 5 * 60 * 1000; // 5 minutes

function checkRateLimit(ip) {
  const now = Date.now();
  const entry = rateLimits.get(ip);
  if (!entry || now > entry.resetAt) {
    rateLimits.set(ip, { count: 1, resetAt: now + RATE_WINDOW });
    return true;
  }
  if (entry.count >= RATE_LIMIT) return false;
  entry.count++;
  return true;
}

// ── Data loaders ──
async function loadJSON(assets, origin, path, cache) {
  if (cache) return cache;
  const url = new URL(path, origin).toString();
  const resp = await assets.fetch(url);
  if (!resp.ok) return null;
  return resp.json();
}

async function getData(ctx) {
  if (!cachedData) cachedData = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/data.json');
  return cachedData;
}
async function getSlugAliases(ctx) {
  if (!cachedSlugAliases) cachedSlugAliases = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/slug_aliases.json');
  return cachedSlugAliases;
}
async function getSeasons(ctx) {
  if (!cachedSeasons) cachedSeasons = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/seasons.json');
  return cachedSeasons;
}
async function getH2H(ctx) {
  if (!cachedH2H) cachedH2H = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/h2h.json');
  return cachedH2H;
}
async function getHTSS(ctx) {
  if (!cachedHTSS) cachedHTSS = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/htss_v2_results.json');
  return cachedHTSS;
}
async function getEfficiency(ctx) {
  if (!cachedEfficiency) cachedEfficiency = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/efficiency_ratings.json');
  return cachedEfficiency;
}
async function getDraft(ctx) {
  if (!cachedDraft) cachedDraft = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/draft_history.json');
  return cachedDraft;
}
async function getTeamHist(ctx) {
  if (!cachedTeamHistory) cachedTeamHistory = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/team_history.json');
  return cachedTeamHistory;
}
async function getUpsets(ctx) {
  if (!cachedUpsets) cachedUpsets = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/upset_history.json');
  return cachedUpsets;
}
async function getTimeMachine(ctx) {
  if (!cachedTimeMachine) cachedTimeMachine = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/time_machine_results.json');
  return cachedTimeMachine;
}

async function getGames(ctx) {
  if (!cachedGames1) cachedGames1 = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/games_1.json') || {};
  if (!cachedGames2) cachedGames2 = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/games_2.json') || {};
  if (!cachedGames3) cachedGames3 = await loadJSON(ctx.env.ASSETS, ctx.request.url, '/games_3.json') || {};
  return { ...cachedGames1, ...cachedGames2, ...cachedGames3 };
}

// ── Helper: team slug from name ──
function teamSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

// ── Tool implementations ──
async function executeTool(name, input, ctx) {
  switch (name) {
    case 'lookupTeam': return await toolLookupTeam(input, ctx);
    case 'getTeamSeasons': return await toolGetTeamSeasons(input, ctx);
    case 'getHeadToHead': return await toolGetHeadToHead(input, ctx);
    case 'getHTSSRankings': return await toolGetHTSSRankings(input, ctx);
    case 'getCoachInfo': return await toolGetCoachInfo(input, ctx);
    case 'getEfficiency': return await toolGetEfficiency(input, ctx);
    case 'getUpsetHistory': return await toolGetUpsetHistory(input, ctx);
    case 'getDraftHistory': return await toolGetDraftHistory(input, ctx);
    case 'getTeamHistory': return await toolGetTeamHistory(input, ctx);
    case 'navigateUser': return { status: 'link_rendered', route: input.route, label: input.label };
    case 'getTimeMachine': return await toolGetTimeMachine(input, ctx);
    case 'getChampionByYear': return await toolGetChampionByYear(input, ctx);
    case 'getTeamsByConference': return await toolGetTeamsByConference(input, ctx);
    case 'searchGames': return await toolSearchGames(input, ctx);
    case 'getTeamTournamentRecord': return await toolGetTeamTournamentRecord(input, ctx);
    default: return { error: `Unknown tool: ${name}` };
  }
}

async function toolLookupTeam(input, ctx) {
  const data = await getData(ctx);
  const aliases = await getSlugAliases(ctx);
  if (!data || !data.H) return { error: 'Data not available' };

  const query = (input.query || '').toLowerCase().trim();
  const results = [];

  // Build slug index
  const slugIndex = {};
  for (const [id, fields] of Object.entries(data.H)) {
    slugIndex[teamSlug(fields[F.NAME])] = id;
  }

  // Search by name, mascot, slug, alias
  for (const [id, fields] of Object.entries(data.H)) {
    const name = fields[F.NAME].toLowerCase();
    const mascot = (fields[F.MASCOT] || '').toLowerCase();
    const slug = teamSlug(fields[F.NAME]);
    if (name.includes(query) || mascot.includes(query) || slug.includes(query)) {
      results.push(formatTeamInfo(id, fields));
    }
  }

  // Check aliases
  if (results.length === 0 && aliases) {
    for (const [alias, id] of Object.entries(aliases)) {
      if (alias.includes(query) && data.H[String(id)]) {
        results.push(formatTeamInfo(String(id), data.H[String(id)]));
      }
    }
  }

  return results.length > 0 ? { teams: results.slice(0, 5) } : { error: `No team found matching "${input.query}"` };
}

function formatTeamInfo(id, fields) {
  return {
    espnId: id,
    name: fields[F.NAME],
    mascot: fields[F.MASCOT],
    conference: fields[F.CONF],
    color: fields[F.COLOR],
    allTimeWins: fields[F.ATW],
    allTimeLosses: fields[F.ATL],
    championships: fields[F.NC],
    championshipYears: fields[F.NCY],
    finalFours: fields[F.FF],
    eliteEights: fields[F.E8],
    sweetSixteens: fields[F.S16],
    tourneyAppearances: fields[F.TOURNEY],
    confTitles: fields[F.CONF_TITLES],
    allAmericans: fields[F.AA],
    nbaFirstRound: fields[F.NBA_FIRST],
    apWeeksRanked: fields[F.AP_WEEKS],
    slug: teamSlug(fields[F.NAME])
  };
}

async function toolGetTeamSeasons(input, ctx) {
  const seasons = await getSeasons(ctx);
  if (!seasons) return { error: 'Seasons data not available' };

  const teamData = seasons[String(input.espnId)];
  if (!teamData || !teamData.seasons) return { error: `No season data for team ${input.espnId}` };

  let filtered = teamData.seasons;
  if (input.startYear || input.endYear) {
    filtered = filtered.filter(s => {
      const yr = parseInt(s.year?.split('-')[0]) + 1;
      if (input.startYear && yr < input.startYear) return false;
      if (input.endYear && yr > input.endYear) return false;
      return true;
    });
  }

  // Limit to 15 most recent seasons to keep context manageable
  if (filtered.length > 15 && !input.startYear && !input.endYear) {
    filtered = filtered.slice(0, 15);
  }

  return { espnId: input.espnId, seasonCount: filtered.length, seasons: filtered };
}

async function toolGetHeadToHead(input, ctx) {
  const h2h = await getH2H(ctx);
  if (!h2h) return { error: 'H2H data not available' };

  const t1 = String(input.team1Id), t2 = String(input.team2Id);
  const record = h2h[t1]?.[t2];
  if (record) return { team1Id: t1, team2Id: t2, team1Wins: record.w, team2Wins: record.l, totalGames: record.g };

  const reverse = h2h[t2]?.[t1];
  if (reverse) return { team1Id: t1, team2Id: t2, team1Wins: reverse.l, team2Wins: reverse.w, totalGames: reverse.g };

  return { error: `No head-to-head data between ${t1} and ${t2}` };
}

async function toolGetHTSSRankings(input, ctx) {
  const htss = await getHTSS(ctx);
  if (!htss) return { error: 'HTSS data not available' };

  const limit = input.limit || 25;

  switch (input.type) {
    case 'top100':
      return { rankings: (htss.allTimeTop100 || []).slice(0, limit) };
    case 'programs':
      return { rankings: (htss.programRankings || []).slice(0, limit) };
    case 'era':
      if (!input.era) return { error: 'Era name required. Options: Pre-Modern, Integration Era, Early Modern, Mid Modern, Late Modern, Current' };
      const eraData = (htss.eraTop25 || []).find(e => e.era === input.era);
      return eraData ? { era: input.era, rankings: eraData.rankings.slice(0, limit) } : { error: `Era "${input.era}" not found` };
    case 'byTeam':
      if (!input.espnId) return { error: 'espnId required for byTeam lookup' };
      const teamSeasons = htss.byTeam?.[String(input.espnId)];
      return teamSeasons ? { espnId: input.espnId, seasons: teamSeasons.slice(0, limit) } : { error: `No HTSS data for team ${input.espnId}` };
    default:
      return { error: `Unknown HTSS type: ${input.type}` };
  }
}

async function toolGetCoachInfo(input, ctx) {
  const data = await getData(ctx);
  if (!data) return { error: 'Data not available' };

  if (input.coachName) {
    const query = input.coachName.toLowerCase();
    // Search leaderboard
    const matches = (data.COACH_LB || []).filter(c =>
      c.name.toLowerCase().includes(query)
    ).slice(0, 5);
    if (matches.length > 0) return { coaches: matches };

    // Search all team coaches
    const results = [];
    for (const [teamId, coaches] of Object.entries(data.COACHES || {})) {
      for (const c of coaches) {
        if (c.name.toLowerCase().includes(query)) {
          const teamName = data.H[teamId]?.[F.NAME] || 'Unknown';
          results.push({ ...c, team: teamName, teamId });
        }
      }
    }
    return results.length > 0 ? { coaches: results.slice(0, 10) } : { error: `No coach found matching "${input.coachName}"` };
  }

  if (input.espnId) {
    const coaches = data.COACHES?.[String(input.espnId)];
    const teamName = data.H?.[String(input.espnId)]?.[F.NAME] || 'Unknown';
    return coaches ? { team: teamName, coaches: coaches.slice(0, 10) } : { error: `No coach data for team ${input.espnId}` };
  }

  // Filter by win range if provided
  if (input.minWins || input.maxWins) {
    const min = input.minWins || 0;
    const max = input.maxWins || 99999;
    const filtered = (data.COACH_LB || []).filter(c => c.wins >= min && c.wins <= max);
    return { coaches: filtered.slice(0, 30), totalMatches: filtered.length };
  }

  // Default: return top 20 from leaderboard
  return { leaderboard: (data.COACH_LB || []).slice(0, 20) };
}

async function toolGetEfficiency(input, ctx) {
  const eff = await getEfficiency(ctx);
  if (!eff || !eff.seasons) return { error: 'Efficiency data not available' };

  const espnId = String(input.espnId);

  if (input.season) {
    const seasonData = eff.seasons[input.season]?.[espnId];
    return seasonData ? { season: input.season, ...seasonData } : { error: `No efficiency data for team ${espnId} in ${input.season}` };
  }

  // Return most recent 5 seasons
  const results = [];
  const years = Object.keys(eff.seasons).sort().reverse();
  for (const yr of years) {
    if (results.length >= 5) break;
    const teamEff = eff.seasons[yr]?.[espnId];
    if (teamEff) results.push({ season: yr, ...teamEff });
  }

  return results.length > 0 ? { espnId, seasons: results } : { error: `No efficiency data for team ${espnId}` };
}

async function toolGetUpsetHistory(input, ctx) {
  const upsets = await getUpsets(ctx);
  if (!upsets) return { error: 'Upset data not available' };

  if (input.seedMatchup) {
    const matchup = upsets[input.seedMatchup];
    return matchup ? { seedMatchup: input.seedMatchup, ...matchup, upsets: (matchup.upsets || []).slice(0, 20) }
      : { error: `No data for seed matchup "${input.seedMatchup}"` };
  }

  // Summary of all matchups
  const summary = {};
  for (const [key, val] of Object.entries(upsets)) {
    if (key === '_metadata') continue;
    summary[key] = {
      higherSeedWins: val.higherSeedWins,
      lowerSeedWins: val.lowerSeedWins,
      totalGames: val.totalGames,
      upsetPct: val.upsetPct
    };
  }
  return { matchups: summary };
}

async function toolGetDraftHistory(input, ctx) {
  const draft = await getDraft(ctx);
  if (!draft) return { error: 'Draft data not available' };

  const teamDraft = draft[String(input.espnId)];
  return teamDraft ? teamDraft : { error: `No draft data for team ${input.espnId}` };
}

async function toolGetTeamHistory(input, ctx) {
  const hist = await getTeamHist(ctx);
  if (!hist) return { error: 'Team history data not available' };

  const teamHist = hist[String(input.espnId)];
  return teamHist ? teamHist : { error: `No history data for team ${input.espnId}` };
}

async function toolGetTimeMachine(input, ctx) {
  const tm = await getTimeMachine(ctx);
  if (!tm || !tm.matchups) return { error: 'Time Machine data not available' };

  if (input.matchup) {
    const match = tm.matchups.find(m => m.matchup.toLowerCase().includes(input.matchup.toLowerCase()));
    return match || { error: `No matchup found matching "${input.matchup}"` };
  }

  return { matchups: tm.matchups.map(m => ({ matchup: m.matchup, prediction: m.prediction })) };
}

async function toolGetChampionByYear(input, ctx) {
  const data = await getData(ctx);
  if (!data || !data.H) return { error: 'Data not available' };

  const year = input.year;
  if (!year) return { error: 'Year is required' };

  for (const [id, fields] of Object.entries(data.H)) {
    const ncyears = fields[F.NCY];
    if (Array.isArray(ncyears) && ncyears.includes(year)) {
      return {
        year,
        champion: fields[F.NAME],
        espnId: id,
        slug: teamSlug(fields[F.NAME]),
        allTimeChampionships: fields[F.NC],
        allChampionshipYears: ncyears
      };
    }
  }
  return { error: `No champion found for ${year}. NCAA Tournament began in 1939.` };
}

async function toolGetTeamsByConference(input, ctx) {
  const data = await getData(ctx);
  if (!data || !data.H) return { error: 'Data not available' };

  const query = (input.conference || '').toLowerCase().trim();
  if (!query) return { error: 'Conference name is required' };

  const teams = [];
  for (const [id, fields] of Object.entries(data.H)) {
    const conf = (fields[F.CONF] || '').toLowerCase();
    if (conf === query || conf.includes(query)) {
      teams.push({
        espnId: id,
        name: fields[F.NAME],
        mascot: fields[F.MASCOT],
        conference: fields[F.CONF],
        allTimeWins: fields[F.ATW],
        allTimeLosses: fields[F.ATL],
        championships: fields[F.NC],
        tourneyAppearances: fields[F.TOURNEY]
      });
    }
  }

  if (teams.length === 0) {
    // List available conferences
    const confs = [...new Set(Object.values(data.H).map(f => f[F.CONF]).filter(Boolean))].sort();
    return { error: `No conference matching "${input.conference}". Available: ${confs.join(', ')}` };
  }

  teams.sort((a, b) => b.allTimeWins - a.allTimeWins);
  return { conference: teams[0].conference, teamCount: teams.length, teams };
}

async function toolSearchGames(input, ctx) {
  const data = await getData(ctx);
  const allGames = await getGames(ctx);
  if (!allGames) return { error: 'Games data not available' };

  const espnId = String(input.espnId);
  const teamGames = allGames[espnId]?.games;
  if (!teamGames) return { error: `No game data for team ${espnId}` };

  let filtered = teamGames;

  // Filter by season year (games are dated, so filter by year range)
  if (input.season) {
    const startYear = parseInt(input.season.split('-')[0]);
    const seasonStart = `${startYear}-10-01`;
    const seasonEnd = `${startYear + 1}-06-01`;
    filtered = filtered.filter(g => g.date >= seasonStart && g.date <= seasonEnd);
  }

  // Filter by opponent
  if (input.opponentId) {
    filtered = filtered.filter(g => String(g.opp) === String(input.opponentId));
  }

  // Filter by opponent slug (for when name is known but not ID)
  if (input.opponentSlug) {
    const slug = input.opponentSlug.toLowerCase();
    filtered = filtered.filter(g => (g.opp_slug || '').toLowerCase().includes(slug));
  }

  // Filter tournament games only
  if (input.tournamentOnly) {
    // Tournament games are typically in March/April
    filtered = filtered.filter(g => {
      const month = parseInt(g.date?.split('-')[1]);
      return month >= 3 && month <= 4;
    });
  }

  // Get team name for context
  const teamName = data?.H?.[espnId]?.[F.NAME] || 'Unknown';

  // Limit results and format
  const results = filtered.slice(0, 30).map(g => ({
    date: g.date,
    opponent: g.opp_slug || g.opp,
    opponentId: g.opp,
    location: g.loc === 'H' ? 'Home' : g.loc === 'A' ? 'Away' : 'Neutral',
    result: g.w ? 'W' : 'L',
    score: `${g.pts}-${g.opp_pts}`,
    teamScore: g.pts,
    opponentScore: g.opp_pts
  }));

  return { team: teamName, espnId, totalGames: filtered.length, showing: results.length, games: results };
}

async function toolGetTeamTournamentRecord(input, ctx) {
  const data = await getData(ctx);
  const seasons = await getSeasons(ctx);
  const allGames = await getGames(ctx);
  if (!data || !seasons || !allGames) return { error: 'Data not available' };

  const espnId = String(input.espnId);
  const teamName = data?.H?.[espnId]?.[F.NAME] || 'Unknown';
  const teamSeasons = seasons[espnId]?.seasons || [];
  const teamGames = allGames[espnId]?.games || [];

  // Build slug→espnId lookup for resolving opponents without opp field
  const slugToId = {};
  for (const [id, fields] of Object.entries(data.H)) {
    slugToId[teamSlug(fields[F.NAME])] = id;
  }

  // Build set of tournament season years and seeds
  const tourneySeasons = {};
  for (const s of teamSeasons) {
    if (s.seed) {
      const startYear = parseInt(s.year?.split('-')[0]);
      tourneySeasons[startYear] = { seed: s.seed, result: s.ncaaTourney };
    }
  }

  // Find March/April games in tournament years
  // NCAA tournament typically starts mid-March (15th+), conference tournaments are earlier
  const tourneyGames = [];
  for (const g of teamGames) {
    if (!g.date) continue;
    const parts = g.date.split('-');
    const year = parseInt(parts[0]);
    const month = parseInt(parts[1]);
    const day = parseInt(parts[2]);
    // NCAA tournament: mid-March through April (skip early March conf tournaments)
    const isTourneyWindow = (month === 3 && day >= 14) || month === 4;
    if (isTourneyWindow && tourneySeasons[year - 1]) {
      const seed = tourneySeasons[year - 1].seed;
      // Resolve opponent ID: use opp field if present, otherwise resolve from slug
      const oppId = g.opp ? String(g.opp) : (g.opp_slug ? slugToId[g.opp_slug] : null);
      tourneyGames.push({
        date: g.date,
        season: `${year - 1}-${String(year).slice(2)}`,
        seed,
        opponent: g.opp_slug || g.opp,
        opponentId: oppId,
        result: g.w ? 'W' : 'L',
        score: `${g.pts}-${g.opp_pts}`
      });
    }
  }

  // Filter by opponent seed if requested
  if (input.opponentSeed) {
    const oppSeed = parseInt(input.opponentSeed);
    const filteredBySeed = [];
    for (const g of tourneyGames) {
      if (!g.opponentId) continue;
      const seasonYear = g.season.split('-')[0];
      const oppSeasonData = seasons[g.opponentId]?.seasons?.find(s => s.year?.startsWith(seasonYear));
      if (oppSeasonData?.seed === oppSeed) {
        filteredBySeed.push({ ...g, opponentSeed: oppSeed });
      }
    }
    const wins = filteredBySeed.filter(g => g.result === 'W').length;
    const losses = filteredBySeed.filter(g => g.result === 'L').length;
    return {
      team: teamName, espnId,
      filter: `vs ${oppSeed}-seeds`,
      record: `${wins}-${losses}`,
      wins, losses,
      games: filteredBySeed.slice(0, 20)
    };
  }

  // Summary by seed
  const bySeed = {};
  for (const g of tourneyGames) {
    if (!bySeed[g.seed]) bySeed[g.seed] = { wins: 0, losses: 0, games: [] };
    if (g.result === 'W') bySeed[g.seed].wins++;
    else bySeed[g.seed].losses++;
    bySeed[g.seed].games.push(g);
  }

  const totalWins = tourneyGames.filter(g => g.result === 'W').length;
  const totalLosses = tourneyGames.filter(g => g.result === 'L').length;

  return {
    team: teamName, espnId,
    totalTournamentRecord: `${totalWins}-${totalLosses}`,
    totalGames: tourneyGames.length,
    bySeed: Object.fromEntries(
      Object.entries(bySeed).map(([seed, data]) => [seed, { record: `${data.wins}-${data.losses}`, games: data.games.length }])
    ),
    recentGames: tourneyGames.slice(0, 15)
  };
}

// ── Tool definitions for Claude ──
const TOOLS = [
  {
    name: 'lookupTeam',
    description: 'Look up a college basketball team by name, mascot, or slug. Returns team info including all-time record, championships, conference, and more. Always use this first to resolve a team name to an ESPN ID before calling other tools.',
    input_schema: {
      type: 'object',
      properties: { query: { type: 'string', description: 'Team name, mascot, or slug to search for (e.g. "Duke", "Blue Devils", "duke-blue-devils")' } },
      required: ['query']
    }
  },
  {
    name: 'getTeamSeasons',
    description: 'Get season-by-season records for a team. Includes wins, losses, conference record, SRS, SOS, PPG, AP rankings, coach, NCAA tournament result and seed.',
    input_schema: {
      type: 'object',
      properties: {
        espnId: { type: 'string', description: 'ESPN team ID' },
        startYear: { type: 'number', description: 'Start year filter (e.g. 2010)' },
        endYear: { type: 'number', description: 'End year filter (e.g. 2020)' }
      },
      required: ['espnId']
    }
  },
  {
    name: 'getHeadToHead',
    description: 'Get the all-time head-to-head record between two teams.',
    input_schema: {
      type: 'object',
      properties: {
        team1Id: { type: 'string', description: 'ESPN ID of first team' },
        team2Id: { type: 'string', description: 'ESPN ID of second team' }
      },
      required: ['team1Id', 'team2Id']
    }
  },
  {
    name: 'getHTSSRankings',
    description: 'Query Hoopsipedia\'s proprietary HTSS (Historical Team-Season Score) rankings. Can get top 100 all-time seasons, top program rankings, era-specific rankings, or a specific team\'s HTSS history. Scale: 85+ GOAT, 80-85 Transcendent, 70-80 Elite, 65-70 Very Good, 60-65 Good.',
    input_schema: {
      type: 'object',
      properties: {
        type: { type: 'string', enum: ['top100', 'programs', 'era', 'byTeam'], description: 'Type of ranking query' },
        limit: { type: 'number', description: 'Max results to return (default 25)' },
        era: { type: 'string', description: 'Era name for era type. Options: Pre-Modern, Integration Era, Early Modern, Mid Modern, Late Modern, Current' },
        espnId: { type: 'string', description: 'ESPN team ID for byTeam type' }
      },
      required: ['type']
    }
  },
  {
    name: 'getCoachInfo',
    description: 'Look up coaching records. Can search by coach name, get coaches for a specific team, filter by win range, or get the all-time wins leaderboard (top 100).',
    input_schema: {
      type: 'object',
      properties: {
        coachName: { type: 'string', description: 'Coach name to search for' },
        espnId: { type: 'string', description: 'ESPN team ID to get that team\'s coaching history' },
        minWins: { type: 'number', description: 'Minimum career wins filter (e.g. 500)' },
        maxWins: { type: 'number', description: 'Maximum career wins filter (e.g. 600)' }
      }
    }
  },
  {
    name: 'getEfficiency',
    description: 'Get adjusted efficiency ratings (KenPom-style) for a team. Includes adjOE (offensive efficiency), adjDE (defensive efficiency), adjEM (efficiency margin), SOS, and quality tier records. Data available from 1949-2026.',
    input_schema: {
      type: 'object',
      properties: {
        espnId: { type: 'string', description: 'ESPN team ID' },
        season: { type: 'string', description: 'Specific season in YYYY-YY format (e.g. "2024-25"). Omit for most recent 5 seasons.' }
      },
      required: ['espnId']
    }
  },
  {
    name: 'getUpsetHistory',
    description: 'Get NCAA Tournament upset history by seed matchup (1985-present, 64-team era). Available matchups: 1v16, 2v15, 3v14, 4v13, 5v12, 6v11, 7v10, 8v9.',
    input_schema: {
      type: 'object',
      properties: {
        seedMatchup: { type: 'string', description: 'Seed matchup like "5v12" or "1v16". Omit for summary of all matchups.' }
      }
    }
  },
  {
    name: 'getDraftHistory',
    description: 'Get NBA draft history for a team including total players drafted, first-round picks, and draft picks by year.',
    input_schema: {
      type: 'object',
      properties: { espnId: { type: 'string', description: 'ESPN team ID' } },
      required: ['espnId']
    }
  },
  {
    name: 'getTeamHistory',
    description: 'Get the narrative history of a program including founding year, mascot origin story, iconic moment, and fun facts.',
    input_schema: {
      type: 'object',
      properties: { espnId: { type: 'string', description: 'ESPN team ID' } },
      required: ['espnId']
    }
  },
  {
    name: 'navigateUser',
    description: 'Create a clickable link in the chat that navigates the user to a specific page on Hoopsipedia. Use this proactively when mentioning teams, comparisons, or views. Route formats: #team/{slug}, #compare/{slug1}/{slug2}, #rankings, #htss-rankings, #time-machine, #trajectories, #upsets, #bracket, #coaches.',
    input_schema: {
      type: 'object',
      properties: {
        route: { type: 'string', description: 'Hash route (e.g. "#team/duke-blue-devils", "#compare/duke-blue-devils/north-carolina-tar-heels")' },
        label: { type: 'string', description: 'Display text for the link (e.g. "View Duke Profile", "Compare Duke vs UNC")' }
      },
      required: ['route', 'label']
    }
  },
  {
    name: 'getTimeMachine',
    description: 'Get cross-era "what if" matchup simulations between legendary teams. Pre-computed with predicted scores, win probabilities, and factor breakdowns.',
    input_schema: {
      type: 'object',
      properties: {
        matchup: { type: 'string', description: 'Search term to find a specific matchup (e.g. "UCLA vs Kentucky"). Omit for all matchups.' }
      }
    }
  },
  {
    name: 'getChampionByYear',
    description: 'Find which team won the NCAA championship in a given year. Returns champion name, ESPN ID, and all their championship years.',
    input_schema: {
      type: 'object',
      properties: {
        year: { type: 'number', description: 'Championship year (e.g. 2015). NCAA Tournament began in 1939.' }
      },
      required: ['year']
    }
  },
  {
    name: 'getTeamsByConference',
    description: 'List all teams in a conference with their all-time records. Useful for questions like "show me all Big 12 teams" or "who is in the ACC?"',
    input_schema: {
      type: 'object',
      properties: {
        conference: { type: 'string', description: 'Conference name (e.g. "ACC", "Big 12", "SEC", "Big Ten")' }
      },
      required: ['conference']
    }
  },
  {
    name: 'searchGames',
    description: 'Search game-by-game results for a team. Can filter by season, opponent, or tournament games. Returns scores, dates, locations. Use lookupTeam first to get ESPN IDs.',
    input_schema: {
      type: 'object',
      properties: {
        espnId: { type: 'string', description: 'ESPN team ID' },
        season: { type: 'string', description: 'Season in YYYY-YY format (e.g. "2014-15")' },
        opponentId: { type: 'string', description: 'ESPN ID of opponent to filter by' },
        opponentSlug: { type: 'string', description: 'Opponent slug to filter by (e.g. "wisconsin")' },
        tournamentOnly: { type: 'boolean', description: 'If true, only return March/April games (tournament window)' }
      },
      required: ['espnId']
    }
  },
  {
    name: 'getTeamTournamentRecord',
    description: 'Get a team\'s NCAA Tournament game-by-game record with seeds, scores, and opponents. Can filter by opponent seed (e.g. "how does Duke do against 12-seeds in the tournament?").',
    input_schema: {
      type: 'object',
      properties: {
        espnId: { type: 'string', description: 'ESPN team ID' },
        opponentSeed: { type: 'number', description: 'Filter to games against this seed number (e.g. 12 for 12-seeds)' }
      },
      required: ['espnId']
    }
  }
];

// ── System prompt ──
const SYSTEM_PROMPT = `You are the Hoopsipedia Assistant, an expert on college basketball history and statistics. You help users explore data from Hoopsipedia, a comprehensive college basketball historical database covering 365+ Division I programs from 1949 to 2026.

You have access to tools that query Hoopsipedia's proprietary data. Use them to answer questions with specific facts and numbers. Always call tools to look up data rather than relying on general knowledge — Hoopsipedia's data is authoritative.

Available data includes:
- Team profiles: all-time records, championships, Final Fours, conference history (365 teams)
- Season-by-season records: W/L, conference records, SRS, SOS, PPG, AP rankings, tournament results (77 seasons, 1949-2026)
- Head-to-head records between any two teams (all-time)
- Game-by-game results with scores for every team (searchable by season, opponent, tournament)
- Championship history: look up champion by year (1939-2026)
- Conference rosters: list all teams in any conference
- HTSS Rankings: Hoopsipedia's proprietary Historical Team-Season Score ranking 25,000+ team-seasons across history (scale: 50=avg, 60-65 good, 65-70 very good, 70-80 elite, 80-85 transcendent, 85+ GOAT tier)
- Adjusted efficiency ratings: KenPom-style adjOE/adjDE/adjEM per team per season (1949-2026)
- Coach records: 557 coaches with 200+ career wins, filterable by win range, searchable by name
- NBA Draft history per team (with notable picks and player names)
- Program history narratives
- NCAA Tournament upset history by seed matchup (1985-present)
- Team tournament records: game-by-game tournament history, filterable by opponent seed
- Time Machine: simulated cross-era matchups between legendary teams

When you mention specific teams, comparisons, or rankings, use the navigateUser tool to create clickable links so the user can explore further on the site.

Route formats for navigateUser:
- Team profile: #team/{team-slug} (e.g. #team/duke-blue-devils)
- Comparison: #compare/{slug1}/{slug2} (e.g. #compare/duke-blue-devils/north-carolina-tar-heels)
- HTSS Rankings: #htss-rankings
- Time Machine: #time-machine
- Trajectories: #trajectories
- Upsets: #upsets
- Bracket: #bracket
- Coaches: #coaches

Guidelines:
- Be conversational but concise. Lead with the answer, then provide supporting detail.
- Use specific numbers and stats from tool results.
- When comparing teams or seasons, present data in a structured, easy-to-scan format.
- If you can't find data for a query, say so honestly — don't make up stats.
- Stay focused on college basketball. Politely redirect off-topic questions.
- You're in beta — it's okay to acknowledge limitations.
- IMPORTANT: Never narrate your tool-use process. Do NOT say things like "Let me look up...", "Now let me get...", "I'll search for...". Just call the tools silently and present the final answer. The user doesn't see tool calls — they only see your text, so narration about looking things up is confusing.`;

// ── Claude API streaming ──
async function callClaude(messages, apiKey, tools) {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 1500,
      system: SYSTEM_PROMPT,
      messages,
      tools,
      stream: true
    })
  });

  if (resp.status === 429) {
    // Rate limited — wait and retry once
    await new Promise(r => setTimeout(r, 3000));
    const retry = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 1500, system: SYSTEM_PROMPT, messages, tools, stream: true })
    });
    if (!retry.ok) {
      const err = await retry.text().catch(() => 'Unknown error');
      throw new Error(`Claude API error ${retry.status}: ${err}`);
    }
    return retry.body;
  }

  if (!resp.ok) {
    const err = await resp.text().catch(() => 'Unknown error');
    throw new Error(`Claude API error ${resp.status}: ${err}`);
  }

  return resp.body;
}

// ── Parse Claude SSE stream, execute tools, write to client ──
async function handleClaudeStream(claudeBody, writer, encoder, messages, apiKey, ctx, depth = 0) {
  const MAX_TOOL_ROUNDS = 4; // Prevent runaway recursion
  const reader = claudeBody.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentToolUse = null;
  let toolUseBlocks = [];
  let textContent = '';
  let inputJsonBuffer = '';
  let pendingText = '';
  let stopReason = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]' || !data) continue;

        let event;
        try { event = JSON.parse(data); } catch { continue; }

        switch (event.type) {
          case 'content_block_start':
            if (event.content_block?.type === 'tool_use') {
              currentToolUse = { id: event.content_block.id, name: event.content_block.name, input: '' };
              inputJsonBuffer = '';
            }
            break;

          case 'content_block_delta':
            if (event.delta?.type === 'text_delta' && event.delta.text) {
              textContent += event.delta.text;
              // Buffer text — only flush after we know this is the final response (not a tool-use round)
              pendingText += event.delta.text;
            }
            if (event.delta?.type === 'input_json_delta' && event.delta.partial_json) {
              inputJsonBuffer += event.delta.partial_json;
            }
            break;

          case 'content_block_stop':
            if (currentToolUse) {
              try { currentToolUse.input = JSON.parse(inputJsonBuffer); } catch { currentToolUse.input = {}; }
              toolUseBlocks.push(currentToolUse);
              currentToolUse = null;
              inputJsonBuffer = '';
            }
            break;

          case 'message_delta':
            if (event.delta?.stop_reason) stopReason = event.delta.stop_reason;
            break;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  // If this is the final response (no more tool calls), stream the text to the client
  if (stopReason !== 'tool_use' || toolUseBlocks.length === 0 || depth >= MAX_TOOL_ROUNDS) {
    if (pendingText) {
      await writer.write(encoder.encode(`event: text\ndata: ${JSON.stringify({ text: pendingText })}\n\n`));
    } else if (depth >= MAX_TOOL_ROUNDS && stopReason === 'tool_use') {
      await writer.write(encoder.encode(`event: text\ndata: ${JSON.stringify({ text: "That question required a lot of data lookups. Could you try breaking it into simpler questions? For example, ask about coaches first, then about a specific team." })}\n\n`));
    }
    return;
  }

  // Claude wants to use tools — execute them and continue
  if (stopReason === 'tool_use' && toolUseBlocks.length > 0 && depth < MAX_TOOL_ROUNDS) {
    // Build assistant message with all content blocks
    const assistantContent = [];
    if (textContent) assistantContent.push({ type: 'text', text: textContent });
    for (const tool of toolUseBlocks) {
      assistantContent.push({ type: 'tool_use', id: tool.id, name: tool.name, input: tool.input });
    }

    // Execute each tool
    const toolResults = [];
    for (const tool of toolUseBlocks) {
      const result = await executeTool(tool.name, tool.input, ctx);

      // If navigateUser, emit navigation event to client
      if (tool.name === 'navigateUser') {
        await writer.write(encoder.encode(`event: navigate\ndata: ${JSON.stringify({ route: tool.input.route, label: tool.input.label })}\n\n`));
      }

      toolResults.push({
        type: 'tool_result',
        tool_use_id: tool.id,
        content: JSON.stringify(result).slice(0, 4000) // Truncate large results to save tokens
      });
    }

    // Append to conversation and call Claude again
    const newMessages = [
      ...messages,
      { role: 'assistant', content: assistantContent },
      { role: 'user', content: toolResults }
    ];

    const nextStream = await callClaude(newMessages, apiKey, TOOLS);
    await handleClaudeStream(nextStream, writer, encoder, newMessages, apiKey, ctx, depth + 1);
  }
}

// ── Main handler ──
export async function onRequestPost(context) {
  const { request, env } = context;

  // CORS headers
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  };

  // Rate limit check
  const ip = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Forwarded-For') || 'unknown';
  if (!checkRateLimit(ip)) {
    return new Response(
      `event: error\ndata: ${JSON.stringify({ message: "You've been asking a lot of questions! Please wait a few minutes before trying again." })}\n\n`,
      { status: 429, headers }
    );
  }

  // Validate API key
  const apiKey = env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return new Response(
      `event: error\ndata: ${JSON.stringify({ message: 'Chat service is not configured. Please try again later.' })}\n\n`,
      { status: 500, headers }
    );
  }

  // Parse request body
  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(
      `event: error\ndata: ${JSON.stringify({ message: 'Invalid request format.' })}\n\n`,
      { status: 400, headers }
    );
  }

  const messages = body.messages;
  if (!Array.isArray(messages) || messages.length === 0 || messages.length > 40) {
    return new Response(
      `event: error\ndata: ${JSON.stringify({ message: 'Invalid message format.' })}\n\n`,
      { status: 400, headers }
    );
  }

  // Create streaming response
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const encoder = new TextEncoder();

  // Process in background (allows streaming)
  context.waitUntil((async () => {
    try {
      const claudeStream = await callClaude(messages, apiKey, TOOLS);
      await handleClaudeStream(claudeStream, writer, encoder, messages, apiKey, context);
      await writer.write(encoder.encode(`event: done\ndata: {}\n\n`));
    } catch (err) {
      console.error('Chat error:', err);
      await writer.write(encoder.encode(`event: error\ndata: ${JSON.stringify({ message: 'Something went wrong. Please try again.' })}\n\n`));
    } finally {
      await writer.close();
    }
  })());

  return new Response(readable, { status: 200, headers });
}

// Handle CORS preflight
export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    }
  });
}
