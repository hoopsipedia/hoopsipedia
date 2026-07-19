// Cloudflare Pages Function — dynamic Open Graph meta tags for social sharing
// Intercepts requests with ?team= or ?compare= query params and injects OG tags

const F = {
  NAME: 0, MASCOT: 1, CONF: 2, COLOR: 3, ATW: 4, ATL: 5,
  NC: 6, NCY: 7, FF: 8
};

function teamSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

// Cache data.json in module-level variable (persists across requests within same isolate)
let cachedTeamData = null;
let slugIndex = null;
let cachedCoaches = null;  // COACHES: per-team coach tenure records
let cachedCoachLb = null;  // COACH_LB_TOP100: all-time wins leaderboard
let coachIndex = null;     // coach slug -> leaderboard entry

async function getTeamData(assetFetcher, originUrl) {
  if (cachedTeamData && slugIndex) {
    return { teams: cachedTeamData, index: slugIndex, coaches: cachedCoaches, coachLb: cachedCoachLb, coachIdx: coachIndex };
  }

  const dataUrl = new URL('/data.json', originUrl).toString();
  const resp = await assetFetcher.fetch(dataUrl);
  if (!resp.ok) return null;

  const data = await resp.json();
  cachedTeamData = data.H;
  cachedCoaches = data.COACHES || {};
  cachedCoachLb = data.COACH_LB_TOP100 || data.COACH_LB || [];

  // Build slug-to-espnId index for fast lookups
  slugIndex = {};
  for (const [espnId, fields] of Object.entries(cachedTeamData)) {
    const slug = teamSlug(fields[F.NAME]);
    slugIndex[slug] = espnId;
  }

  // Coach slug index (same slug function the SPA's coachSlug uses)
  coachIndex = {};
  for (const c of cachedCoachLb) coachIndex[teamSlug(c.name)] = c;

  return { teams: cachedTeamData, index: slugIndex, coaches: cachedCoaches, coachLb: cachedCoachLb, coachIdx: coachIndex };
}

function lookupTeam(slug, teams, index) {
  const espnId = index[slug];
  if (!espnId) return null;
  const t = teams[espnId];
  return {
    espnId,
    name: t[F.NAME],
    mascot: t[F.MASCOT],
    conf: t[F.CONF],
    color: t[F.COLOR],
    allTimeW: t[F.ATW],
    allTimeL: t[F.ATL],
    natlChamps: t[F.NC],
    champYears: Array.isArray(t[F.NCY]) ? t[F.NCY] : [],
    finalFours: t[F.FF],
  };
}

// HTMLRewriter handler that removes existing OG/Twitter meta tags
class MetaTagRemover {
  constructor(tagsToRemove) {
    this.tagsToRemove = tagsToRemove;
  }

  element(el) {
    const property = el.getAttribute('property') || '';
    const name = el.getAttribute('name') || '';
    if (this.tagsToRemove.has(property) || this.tagsToRemove.has(name)) {
      el.remove();
    }
  }
}

// HTMLRewriter handler that injects new meta tags (and optional extra raw
// head HTML: canonical link, JSON-LD scripts) before </head>
class HeadInjector {
  constructor(metaTags, titleText, extraHeadHtml = '') {
    this.metaTags = metaTags;
    this.titleText = titleText;
    this.extraHeadHtml = extraHeadHtml;
    this.titleReplaced = false;
  }

  element(el) {
    // Inject all OG/Twitter meta tags at the end of <head>
    const tagHtml = this.metaTags
      .map(({ key, value }) => {
        const attr = key.startsWith('og:') ? 'property' : 'name';
        return `<meta ${attr}="${key}" content="${escapeAttr(value)}">`;
      })
      .join('\n    ');
    el.append(tagHtml, { html: true });
    if (this.extraHeadHtml) {
      el.append('\n    ' + this.extraHeadHtml, { html: true });
    }
  }
}

// HTMLRewriter handler that removes a pre-existing canonical link (if any)
// so the per-page canonical we inject is the only one.
class CanonicalRemover {
  element(el) {
    if ((el.getAttribute('rel') || '').toLowerCase() === 'canonical') {
      el.remove();
    }
  }
}

// HTMLRewriter handler that prepends crawler-visible HTML right after <body>
class BodyPrepender {
  constructor(html) {
    this.html = html;
  }

  element(el) {
    el.prepend(this.html, { html: true });
  }
}

class TitleRewriter {
  constructor(newTitle) {
    this.newTitle = newTitle;
  }

  element(el) {
    el.setInnerContent(this.newTitle);
  }
}

function escapeAttr(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Serialize a JSON-LD object into a <script> tag. '<' is escaped to < so
// the payload can never break out of the script element.
function jsonLdScript(obj) {
  const json = JSON.stringify(obj).replace(/</g, '\\u003c');
  return `<script type="application/ld+json">${json}</script>`;
}

// Encode a query param value but keep '/' literal so canonical URLs match
// the form used in sitemap.xml (?championship=1985/villanova-wildcats).
function encodeParam(value) {
  return encodeURIComponent(value).replace(/%2F/gi, '/');
}

// Build a schema.org BreadcrumbList from [{name, url}, ...]
function breadcrumbLd(items) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

// ---------- Server-rendered content (SSR) ----------
// Visible-by-default HTML prepended inside <body> so crawlers (and no-JS
// users) see real content instead of the empty SPA shell. index.html
// removes #ssr-content the moment the SPA renders, so JS users never see
// it. This replaces the old <noscript> summary, which Google largely
// ignores once it renders JS.

// Per-isolate cache of seasons/{espnId}.json slices (~15KB each). The
// full seasons.json is 5.4MB — too heavy to parse per request.
const seasonsCache = new Map();

async function getTeamSeasons(assetFetcher, originUrl, espnId) {
  if (seasonsCache.has(espnId)) return seasonsCache.get(espnId);
  try {
    const resp = await assetFetcher.fetch(new URL(`/seasons/${espnId}.json`, originUrl).toString());
    if (!resp.ok) return null;
    const data = await resp.json();
    const seasons = Array.isArray(data.seasons) ? data.seasons : null;
    if (seasons) seasonsCache.set(espnId, seasons);
    return seasons;
  } catch (e) {
    return null;
  }
}

const SSR_SECTION_STYLE = 'max-width:960px;margin:24px auto;padding:0 16px 24px;line-height:1.6';
const SSR_TABLE_STYLE = 'border-collapse:collapse;width:100%;font-size:14px';
const SSR_CELL_STYLE = 'border:1px solid #ccc;padding:4px 8px;text-align:left';

function ssrWrap(inner) {
  return `<div id="ssr-content"><section style="${SSR_SECTION_STYLE}">${inner}</section></div>`;
}

function teamHref(origin, slug) {
  return `${origin}/?team=${encodeParam(slug)}`;
}

function winPctText(w, l) {
  const games = w + l;
  if (!games) return '';
  return (w / games).toFixed(3).replace(/^0/, '');
}

// All teams in a conference as [{name, slug}], sorted by name.
function conferenceTeams(teams, conf, excludeEspnId) {
  const out = [];
  for (const [espnId, t] of Object.entries(teams)) {
    if (t[F.CONF] === conf && espnId !== excludeEspnId) {
      out.push({ name: t[F.NAME], slug: teamSlug(t[F.NAME]) });
    }
  }
  out.sort((a, b) => a.name.localeCompare(b.name));
  return out;
}

function renderTeamSsr(team, seasons, teams, origin, history) {
  const slug = teamSlug(team.name);
  const parts = [];

  parts.push(`<h1>${escapeHtml(team.name)} basketball — program history</h1>`);

  // Program story prose from team_history.json (curated, fact-checked).
  const hist = history && history[team.espnId];
  if (hist) {
    const prose = [];
    if (hist.blurb) prose.push(`<p>${escapeHtml(hist.blurb)}</p>`);
    if (hist.mascotOrigin) prose.push(`<h2>The name</h2><p>${escapeHtml(hist.mascotOrigin)}</p>`);
    if (hist.iconicMoment) prose.push(`<h2>Signature moment</h2><p>${escapeHtml(hist.iconicMoment)}</p>`);
    if (hist.funFact) prose.push(`<p>${escapeHtml(hist.funFact)}</p>`);
    if (prose.length) parts.push(prose.join('\n'));
  }

  const nSeasons = seasons ? seasons.length : 0;
  const firstYear = nSeasons ? seasons[seasons.length - 1].year : null;
  const pct = winPctText(team.allTimeW, team.allTimeL);
  const summaryBits = [
    `The ${escapeHtml(team.name)} compete in the ${escapeHtml(team.conf)} and hold an all-time record of ${team.allTimeW}–${team.allTimeL}${pct ? ` (${pct} winning percentage)` : ''}`,
  ];
  if (nSeasons && firstYear) {
    summaryBits.push(` across ${nSeasons} recorded seasons dating back to ${escapeHtml(firstYear)}`);
  }
  summaryBits.push('.');
  if (team.natlChamps > 0) {
    summaryBits.push(` The program has won ${team.natlChamps} NCAA national championship${team.natlChamps > 1 ? 's' : ''} (${team.champYears.join(', ')}) and reached ${team.finalFours} Final Four${team.finalFours === 1 ? '' : 's'}.`);
  } else if (team.finalFours > 0) {
    summaryBits.push(` The program has reached ${team.finalFours} Final Four${team.finalFours === 1 ? '' : 's'}.`);
  }
  parts.push(`<p>${summaryBits.join('')}</p>`);

  if (team.champYears.length) {
    const champLinks = team.champYears
      .map(y => `<a href="${origin}/?championship=${encodeParam(`${y}/${slug}`)}">${y}</a>`)
      .join(', ');
    parts.push(`<h2>National championships</h2><p>${champLinks}</p>`);
  }

  if (nSeasons) {
    const rows = seasons.map(s => {
      const record = s.record || `${s.wins}-${s.losses}`;
      const confCell = s.confRecord
        ? `${escapeHtml(s.confRecord)} (${escapeHtml(s.conf || '')})`
        : escapeHtml(s.conf || '');
      const apCell = s.apHigh ? `AP #${s.apHigh}` : '';
      const yearCell = `<a href="${seasonHref(origin, slug, s.year)}">${escapeHtml(s.year)}</a>`;
      return `<tr><td style="${SSR_CELL_STYLE}">${yearCell}</td><td style="${SSR_CELL_STYLE}">${escapeHtml(record)}</td><td style="${SSR_CELL_STYLE}">${confCell}</td><td style="${SSR_CELL_STYLE}">${escapeHtml(s.coach || '')}</td><td style="${SSR_CELL_STYLE}">${apCell}</td></tr>`;
    }).join('');
    parts.push(
      `<h2>Season-by-season results</h2>` +
      `<table style="${SSR_TABLE_STYLE}"><thead><tr>` +
      `<th style="${SSR_CELL_STYLE}">Season</th><th style="${SSR_CELL_STYLE}">Record</th><th style="${SSR_CELL_STYLE}">Conference</th><th style="${SSR_CELL_STYLE}">Coach</th><th style="${SSR_CELL_STYLE}">AP peak</th>` +
      `</tr></thead><tbody>${rows}</tbody></table>`
    );
  }

  const rivals = conferenceTeams(teams, team.conf, team.espnId);
  if (rivals.length) {
    const rivalLinks = rivals.map(r => `<a href="${teamHref(origin, r.slug)}">${escapeHtml(r.name)}</a>`).join(' · ');
    parts.push(`<h2>More ${escapeHtml(team.conf)} programs</h2><p>${rivalLinks}</p>`);
  }

  parts.push(`<p><a href="${origin}/?view=teams">All Division I programs</a> · <a href="${origin}/?view=rankings">Historical rankings</a> · <a href="${origin}/?view=champions">Championship journeys</a> · <a href="${origin}/">Hoopsipedia home</a></p>`);

  return ssrWrap(parts.join('\n'));
}

// Per-isolate cache of team_history.json (program prose: blurb, mascot
// origin, iconic moment, fun fact) — one 350KB fetch, cached for the isolate.
let teamHistoryCache = null;
async function getTeamHistory(assetFetcher, originUrl) {
  if (teamHistoryCache) return teamHistoryCache;
  try {
    const resp = await assetFetcher.fetch(new URL('/team_history.json', originUrl).toString());
    if (!resp.ok) return null;
    teamHistoryCache = await resp.json();
    return teamHistoryCache;
  } catch (e) {
    return null;
  }
}

// Per-isolate cache of recaps/{espnId}.json (date -> recap prose generated
// from the box-score store by scripts/generate_game_recaps.py).
const recapsCache = new Map();
async function getTeamRecaps(assetFetcher, originUrl, espnId) {
  if (recapsCache.has(espnId)) return recapsCache.get(espnId);
  try {
    const resp = await assetFetcher.fetch(new URL(`/recaps/${espnId}.json`, originUrl).toString());
    const recaps = resp.ok ? await resp.json() : {};
    if (recapsCache.size > 60) recapsCache.clear();
    recapsCache.set(espnId, recaps);
    return recaps;
  } catch (e) {
    return {};
  }
}

// Per-isolate cache of games/{espnId}.json slices for season pages.
const gamesCache = new Map();

// Reverse SR-slug -> espnId index (opp records sometimes lack the id).
let srSlugIndex = null;
async function getSrSlugIndex(assetFetcher, originUrl) {
  if (srSlugIndex) return srSlugIndex;
  try {
    const resp = await assetFetcher.fetch(new URL('/espn_to_sr.json', originUrl).toString());
    if (!resp.ok) return {};
    const m = await resp.json();
    srSlugIndex = {};
    for (const [eid, slug] of Object.entries(m)) srSlugIndex[slug] = eid;
    return srSlugIndex;
  } catch (e) {
    return {};
  }
}

async function getTeamGames(assetFetcher, originUrl, espnId) {
  if (gamesCache.has(espnId)) return gamesCache.get(espnId);
  try {
    const resp = await assetFetcher.fetch(new URL(`/games/${espnId}.json`, originUrl).toString());
    if (!resp.ok) return null;
    const data = await resp.json();
    const games = Array.isArray(data.games) ? data.games : (Array.isArray(data) ? data : null);
    if (games) {
      if (gamesCache.size > 40) gamesCache.clear(); // slices are ~50-300KB; cap memory
      gamesCache.set(espnId, games);
    }
    return games;
  } catch (e) {
    return null;
  }
}

// Season "1988-89" -> games dated 1988-08-01 .. 1989-07-31.
function gamesForSeason(games, seasonStr) {
  const startYear = parseInt(seasonStr.substring(0, 4), 10);
  if (!startYear) return [];
  const lo = `${startYear}-08-01`;
  const hi = `${startYear + 1}-07-31`;
  return games
    .filter(g => g.date && g.date >= lo && g.date <= hi)
    .sort((a, b) => (a.date < b.date ? -1 : 1));
}

function seasonHref(origin, slug, seasonStr) {
  return `${origin}/teams/${encodeParam(slug)}/${encodeParam(seasonStr)}`;
}

function renderSeasonSsr(team, seasonRow, games, teams, origin, slugIdx, recaps) {
  const slug = teamSlug(team.name);
  const parts = [];
  const seasonStr = seasonRow.year;

  parts.push(`<h1>${escapeHtml(seasonStr)} ${escapeHtml(team.name)} — schedule and results</h1>`);

  const record = seasonRow.record || `${seasonRow.wins}-${seasonRow.losses}`;
  const bits = [
    `The ${escapeHtml(seasonStr)} ${escapeHtml(team.name)} went ${escapeHtml(record)}`,
  ];
  if (seasonRow.confRecord) bits.push(` (${escapeHtml(seasonRow.confRecord)} in the ${escapeHtml(seasonRow.conf || team.conf)})`);
  if (seasonRow.coach) bits.push(` under head coach ${escapeHtml(seasonRow.coach)}`);
  bits.push('.');
  if (seasonRow.apHigh) bits.push(` The team peaked at #${seasonRow.apHigh} in the AP poll.`);
  if (seasonRow.srs != null) bits.push(` Simple Rating System: ${seasonRow.srs}.`);
  parts.push(`<p>${bits.join('')}</p>`);

  if (games.length) {
    const rows = games.map(g => {
      let oppT = teams[String(g.opp)];
      if (!oppT && g.opp_slug && slugIdx && slugIdx[g.opp_slug]) oppT = teams[slugIdx[g.opp_slug]];
      const oppName = oppT ? oppT[F.NAME] : (g.opp_slug || 'Unknown').replace(/-/g, ' ');
      const oppCell = oppT
        ? `<a href="${origin}/teams/${encodeParam(teamSlug(oppT[F.NAME]))}">${escapeHtml(oppName)}</a>`
        : escapeHtml(oppName);
      const loc = g.loc === 'H' ? 'vs' : g.loc === 'A' ? 'at' : 'neutral';
      const res = `${g.w ? 'W' : 'L'} ${g.pts}–${g.opp_pts}${g.ot ? ` (${g.ot}OT)` : ''}${g.vacated ? ' *' : ''}`;
      return `<tr><td style="${SSR_CELL_STYLE}">${escapeHtml(g.date)}</td><td style="${SSR_CELL_STYLE}">${loc} ${oppCell}</td><td style="${SSR_CELL_STYLE}">${res}</td><td style="${SSR_CELL_STYLE}">${escapeHtml(g.arena || '')}</td></tr>`;
    }).join('');
    parts.push(
      `<h2>Game-by-game results (${games.length} games)</h2>` +
      `<table style="${SSR_TABLE_STYLE}"><thead><tr>` +
      `<th style="${SSR_CELL_STYLE}">Date</th><th style="${SSR_CELL_STYLE}">Opponent</th><th style="${SSR_CELL_STYLE}">Result</th><th style="${SSR_CELL_STYLE}">Arena</th>` +
      `</tr></thead><tbody>${rows}</tbody></table>`
    );
    if (games.some(g => g.vacated)) {
      parts.push(`<p>* Result later vacated by the NCAA and not counted in official records.</p>`);
    }

    // Game recaps composed from archived box scores (generate_game_recaps.py).
    if (recaps) {
      const recapParas = games
        .filter(g => recaps[g.date])
        .map(g => `<p><strong>${escapeHtml(g.date)}:</strong> ${escapeHtml(recaps[g.date])}</p>`);
      if (recapParas.length) {
        parts.push(`<h2>Game recaps</h2>` + recapParas.join('\n'));
      }
    }
  }

  parts.push(`<p><a href="${origin}/teams/${encodeParam(slug)}">${escapeHtml(team.name)} program history</a> · <a href="${origin}/?view=teams">All Division I programs</a> · <a href="${origin}/">Hoopsipedia home</a></p>`);

  return ssrWrap(parts.join('\n'));
}

function renderTeamsDirectorySsr(teams, origin) {
  const byConf = new Map();
  for (const t of Object.values(teams)) {
    const conf = t[F.CONF] || 'Independent';
    if (!byConf.has(conf)) byConf.set(conf, []);
    byConf.get(conf).push({ name: t[F.NAME], slug: teamSlug(t[F.NAME]) });
  }
  const confs = [...byConf.keys()].sort((a, b) => a.localeCompare(b));
  const parts = [`<h1>All Division I college basketball programs</h1>`,
    `<p>Every program on Hoopsipedia, organized by conference. Each page covers the team's full history: all-time record, season-by-season results, coaches, NCAA Tournament runs, and national championships.</p>`];
  for (const conf of confs) {
    const list = byConf.get(conf).sort((a, b) => a.name.localeCompare(b.name))
      .map(t => `<a href="${teamHref(origin, t.slug)}">${escapeHtml(t.name)}</a>`).join(' · ');
    parts.push(`<h2>${escapeHtml(conf)}</h2><p>${list}</p>`);
  }
  return ssrWrap(parts.join('\n'));
}

// Coach accolades from season rows (row.coach + row.ncaaTourney) of the
// coach's own schools only — same counting rules as the SPA's
// computeCoachAccolades, but over seasons/{tid}.json slices instead of the
// 5.4MB seasons.json monolith. Title years are kept for linking.
async function computeCoachAccoladesSsr(assetFetcher, originUrl, coach, teams) {
  let titles = 0, finalFours = 0, trips = 0;
  const titleSeasons = []; // {year, teamName, teamSlug}
  const tids = [...new Set(coach.schools.map(([tid]) => String(tid)))];
  const slices = await Promise.all(tids.map(tid => getTeamSeasons(assetFetcher, originUrl, tid)));
  tids.forEach((tid, i) => {
    const rows = slices[i];
    if (!rows) return;
    for (const r of rows) {
      if (r.coach !== coach.name || !r.ncaaTourney) continue;
      trips++;
      const t = String(r.ncaaTourney);
      if (/National (Semifinal|Final)|\(Final Four\)/i.test(t)) finalFours++;
      if (/^Won NCAA Tournament National Final/i.test(t)) {
        titles++;
        const teamName = teams[tid] ? teams[tid][F.NAME] : '';
        titleSeasons.push({ year: r.year, teamName, teamSlug: teamName ? teamSlug(teamName) : null });
      }
    }
  });
  titleSeasons.sort((a, b) => (a.year < b.year ? -1 : 1));
  return { titles, finalFours, trips, titleSeasons };
}

function coachHref(origin, slug) {
  return `${origin}/coaches/${encodeParam(slug)}`;
}

function renderCoachSsr(coach, rank, accolades, teams, coaches, coachLb, origin) {
  const parts = [];
  const currentYear = 2026; // site data runs through the 2025-26 season
  const isActive = coach.yearsEnd >= currentYear;
  const nSeasons = coach.yearsEnd - coach.yearsStart + 1;
  const pct = winPctText(coach.wins, coach.losses);

  parts.push(`<h1>${escapeHtml(coach.name)} — college basketball coaching record</h1>`);

  const schoolNames = coach.schools
    .map(([tid]) => teams[String(tid)] ? teams[String(tid)][F.NAME] : null)
    .filter(Boolean);
  const bits = [
    `${escapeHtml(coach.name)} ${isActive ? 'has compiled' : 'compiled'} a career record of ${coach.wins}–${coach.losses}${pct ? ` (${pct} winning percentage)` : ''} across ${nSeasons} seasons as a Division I head coach (${coach.yearsStart}–${isActive ? 'present' : coach.yearsEnd}), ranking #${rank} on the all-time D1 wins list`,
  ];
  if (schoolNames.length) {
    bits.push(` with stops at ${schoolNames.map(escapeHtml).join(', ')}`);
  }
  bits.push('.');
  if (accolades.titles > 0) {
    bits.push(` He has won ${accolades.titles} NCAA national championship${accolades.titles > 1 ? 's' : ''} and reached ${accolades.finalFours} Final Four${accolades.finalFours === 1 ? '' : 's'} in ${accolades.trips} NCAA Tournament appearance${accolades.trips === 1 ? '' : 's'}.`);
  } else if (accolades.finalFours > 0) {
    bits.push(` He has reached ${accolades.finalFours} Final Four${accolades.finalFours === 1 ? '' : 's'} in ${accolades.trips} NCAA Tournament appearance${accolades.trips === 1 ? '' : 's'}.`);
  } else if (accolades.trips > 0) {
    bits.push(` He has made ${accolades.trips} NCAA Tournament appearance${accolades.trips === 1 ? '' : 's'}.`);
  }
  parts.push(`<p>${bits.join('')}</p>`);

  if (accolades.titleSeasons.length) {
    const links = accolades.titleSeasons.map(t => {
      const label = `${t.year}${t.teamName ? ` (${t.teamName})` : ''}`;
      return t.teamSlug
        ? `<a href="${seasonHref(origin, t.teamSlug, t.year)}">${escapeHtml(label)}</a>`
        : escapeHtml(label);
    }).join(', ');
    parts.push(`<h2>National championships</h2><p>${links}</p>`);
  }

  const tenureRows = coach.schools.map(([tid, start, end]) => {
    const tidStr = String(tid);
    const teamArr = teams[tidStr];
    const teamName = teamArr ? teamArr[F.NAME] : 'Unknown';
    const slug = teamArr ? teamSlug(teamName) : null;
    const rec = (coaches[tidStr] || []).find(x => x.name === coach.name);
    const schoolCell = slug
      ? `<a href="${origin}/teams/${encodeParam(slug)}">${escapeHtml(teamName)}</a>`
      : escapeHtml(teamName);
    const yearsCell = `${start}–${end >= currentYear ? 'Present' : end}`;
    const recCell = rec && rec.w > 0 ? `${rec.w}–${rec.l}` : '';
    const pctCell = rec && rec.pct != null ? `${rec.pct}%` : '';
    const bestCell = rec && rec.bestYr
      ? (slug
        ? `<a href="${seasonHref(origin, slug, rec.bestYr)}">${escapeHtml(rec.bestYr)} (${escapeHtml(rec.bestRec || '')})</a>`
        : `${escapeHtml(rec.bestYr)} (${escapeHtml(rec.bestRec || '')})`)
      : '';
    return `<tr><td style="${SSR_CELL_STYLE}">${schoolCell}</td><td style="${SSR_CELL_STYLE}">${yearsCell}</td><td style="${SSR_CELL_STYLE}">${recCell}</td><td style="${SSR_CELL_STYLE}">${pctCell}</td><td style="${SSR_CELL_STYLE}">${bestCell}</td></tr>`;
  }).join('');
  parts.push(
    `<h2>Coaching stops</h2>` +
    `<table style="${SSR_TABLE_STYLE}"><thead><tr>` +
    `<th style="${SSR_CELL_STYLE}">School</th><th style="${SSR_CELL_STYLE}">Years</th><th style="${SSR_CELL_STYLE}">Record</th><th style="${SSR_CELL_STYLE}">Win %</th><th style="${SSR_CELL_STYLE}">Best season</th>` +
    `</tr></thead><tbody>${tenureRows}</tbody></table>`
  );

  const others = coachLb
    .filter(c => c.name !== coach.name)
    .map(c => `<a href="${coachHref(origin, teamSlug(c.name))}">${escapeHtml(c.name)}</a>`)
    .join(' · ');
  if (others) {
    parts.push(`<h2>More all-time winningest coaches</h2><p>${others}</p>`);
  }

  parts.push(`<p><a href="${origin}/?view=coaches">All-time coaches leaderboard</a> · <a href="${origin}/?view=teams">All Division I programs</a> · <a href="${origin}/">Hoopsipedia home</a></p>`);

  return ssrWrap(parts.join('\n'));
}

function renderHomepageSsr(teams, origin) {
  const entries = Object.values(teams);
  const winningest = [...entries]
    .sort((a, b) => b[F.ATW] - a[F.ATW])
    .slice(0, 25)
    .map(t => `<a href="${teamHref(origin, teamSlug(t[F.NAME]))}">${escapeHtml(t[F.NAME])}</a> (${t[F.ATW]}–${t[F.ATL]})`)
    .join(' · ');

  const champs = [];
  for (const t of entries) {
    const years = Array.isArray(t[F.NCY]) ? t[F.NCY] : [];
    for (const y of years) champs.push({ year: y, name: t[F.NAME], slug: teamSlug(t[F.NAME]) });
  }
  champs.sort((a, b) => b.year - a.year);
  const champList = champs.slice(0, 30)
    .map(c => `<a href="${origin}/?championship=${encodeParam(`${c.year}/${c.slug}`)}">${c.year} ${escapeHtml(c.name)}</a>`)
    .join(' · ');

  const parts = [
    `<h1>Hoopsipedia — the college basketball history encyclopedia</h1>`,
    `<p>Hoopsipedia is a free historical database covering ${entries.length}+ Division I men's college basketball programs across 77 seasons (1949–2026): all-time records, season-by-season results, head coaches, NCAA Tournament history, championship runs, historical rankings, and retroactive efficiency ratings.</p>`,
    `<p>Explore: <a href="${origin}/?view=teams">All teams</a> · <a href="${origin}/?view=rankings">Rankings</a> · <a href="${origin}/?view=bracket">Tournament bracket</a> · <a href="${origin}/?view=coaches">Coaches</a> · <a href="${origin}/?view=champions">Championship journeys</a> · <a href="${origin}/?view=upsets">Greatest upsets</a> · <a href="${origin}/?view=classics">Instant classics</a></p>`,
    `<h2>Winningest programs of all time</h2><p>${winningest}</p>`,
    `<h2>Recent national champions</h2><p>${champList}</p>`,
  ];
  return ssrWrap(parts.join('\n'));
}

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  let teamParam = url.searchParams.get('team');
  const compareParam = url.searchParams.get('compare');
  const gameParam = url.searchParams.get('game');
  const champParam = url.searchParams.get('championship');
  const viewParam = url.searchParams.get('view');

  // Forever URLs: /teams/{slug} and /teams/{slug}/{season}. The path form is
  // canonical; ?team= keeps working and canonicalizes to the path.
  let seasonParam = null;
  let isPathRoute = false;
  const pathMatch = url.pathname.match(/^\/teams\/([a-z0-9-]+)(?:\/(\d{4}(?:-\d{2})?))?\/?$/);
  if (pathMatch) {
    teamParam = pathMatch[1];
    seasonParam = pathMatch[2] || null;
    isPathRoute = true;
  }

  // Forever URLs: /coaches/{slug} — top-100 all-time coaches.
  let coachParam = null;
  const coachPathMatch = url.pathname.match(/^\/coaches\/([a-z0-9-]+)\/?$/);
  if (coachPathMatch) coachParam = coachPathMatch[1];

  // Bare homepage gets SSR content too; everything else with no relevant
  // query params passes through to static files.
  const isHomepage = url.pathname === '/' && url.search === '';
  if (!isHomepage && !teamParam && !compareParam && !gameParam && !champParam && !viewParam && !coachParam) {
    return context.next();
  }

  // Fetch origin HTML (the index.html) via ASSETS binding to avoid recursive function calls
  const assetFetcher = context.env.ASSETS;
  const originUrl = new URL('/', url).toString();
  const [originResp, teamDataResult] = await Promise.all([
    assetFetcher.fetch(originUrl),
    getTeamData(assetFetcher, originUrl),
  ]);

  if (!originResp.ok || !teamDataResult) {
    return context.next();
  }

  const { teams, index, coaches, coachLb, coachIdx } = teamDataResult;
  let metaTags = [];
  let pageTitle = '';
  let canonicalUrl = url.toString();
  // Pin the canonical host: the site answers on both apex and www with no
  // redirect, and split canonicals dilute SEO signal. www matches branding
  // URLs and sitemap.xml — keep all three in lockstep.
  const origin = 'https://www.hoopsipedia.com';
  const jsonLdBlocks = []; // schema.org objects to inject as <script type="application/ld+json">
  let ssrHtml = '';        // crawler-visible content, prepended inside <body> as #ssr-content

  // Path routes must hard-404 on unknown teams/seasons — the SPA fallback
  // would otherwise serve soft-404s for every mistyped forever URL.
  const notFound = () => new Response(
    `<!doctype html><meta charset="utf-8"><title>Not found — Hoopsipedia</title>` +
    `<div style="font-family:sans-serif;max-width:600px;margin:80px auto;text-align:center">` +
    `<h1>Page not found</h1><p>No such team, coach, or season.</p>` +
    `<p><a href="/?view=teams">Browse all teams</a> · <a href="/">Hoopsipedia home</a></p></div>`,
    { status: 404, headers: { 'content-type': 'text/html; charset=utf-8' } });

  if (coachParam) {
    // /coaches/{slug} — coach career page
    const coach = coachIdx ? coachIdx[coachParam] : null;
    if (!coach) return notFound();

    const slug = teamSlug(coach.name);
    canonicalUrl = coachHref(origin, slug);
    const rank = coachLb.indexOf(coach) + 1;
    const accolades = await computeCoachAccoladesSsr(assetFetcher, originUrl, coach, teams);

    // OG image: logo of the school where the coach spent the most seasons.
    let primaryTid = null, primarySpan = -1;
    for (const [tid, start, end] of coach.schools) {
      if (end - start > primarySpan) { primarySpan = end - start; primaryTid = String(tid); }
    }
    const imageUrl = primaryTid
      ? `https://a.espncdn.com/i/teamlogos/ncaa/500/${primaryTid}.png`
      : `https://www.hoopsipedia.com/branding/hoopsipedia-logo.png`;

    pageTitle = `${coach.name} — Coaches — Hoopsipedia`;
    const accBits = [];
    if (accolades.titles > 0) accBits.push(`${accolades.titles} national title${accolades.titles > 1 ? 's' : ''}`);
    if (accolades.finalFours > 0) accBits.push(`${accolades.finalFours} Final Four${accolades.finalFours === 1 ? '' : 's'}`);
    const description = `${coach.name} coaching record: ${coach.wins}-${coach.losses} (${coach.pct}%), #${rank} all-time in D1 wins${accBits.length ? `, ${accBits.join(', ')}` : ''}. Full career history, season-by-season tenures, and comparisons on Hoopsipedia.`;

    metaTags = [
      { key: 'description', value: description },
      { key: 'og:type', value: 'profile' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];

    jsonLdBlocks.push({
      '@context': 'https://schema.org',
      '@type': 'Person',
      name: coach.name,
      jobTitle: 'College Basketball Head Coach',
      url: canonicalUrl,
      ...(primaryTid && teams[primaryTid]
        ? { affiliation: { '@type': 'SportsTeam', name: teams[primaryTid][F.NAME], sport: 'Basketball' } }
        : {}),
    });
    jsonLdBlocks.push(breadcrumbLd([
      { name: 'Hoopsipedia', url: `${origin}/` },
      { name: 'Coaches', url: `${origin}/?view=coaches` },
      { name: coach.name, url: canonicalUrl },
    ]));

    ssrHtml = renderCoachSsr(coach, rank, accolades, teams, coaches, coachLb, origin);
  } else if (teamParam && seasonParam) {
    // /teams/{slug}/{season} — self-contained season page
    const team = lookupTeam(teamParam, teams, index);
    if (!team) return notFound();
    const seasons = await getTeamSeasons(assetFetcher, originUrl, team.espnId);
    const seasonRow = seasons ? seasons.find(s => s.year === seasonParam) : null;
    if (!seasonRow) return notFound();

    const slug = teamSlug(team.name);
    canonicalUrl = seasonHref(origin, slug, seasonParam);
    const record = seasonRow.record || `${seasonRow.wins}-${seasonRow.losses}`;
    pageTitle = `${seasonParam} ${team.name} — schedule & results — Hoopsipedia`;
    const description = `${seasonParam} ${team.name} basketball: ${record}${seasonRow.coach ? ` under ${seasonRow.coach}` : ''}${seasonRow.apHigh ? `, peaked at AP #${seasonRow.apHigh}` : ''}. Full game-by-game schedule, scores, and box scores on Hoopsipedia.`;
    const imageUrl = `https://a.espncdn.com/i/teamlogos/ncaa/500/${team.espnId}.png`;

    metaTags = [
      { key: 'description', value: description },
      { key: 'og:type', value: 'website' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];
    jsonLdBlocks.push(breadcrumbLd([
      { name: 'Hoopsipedia', url: `${origin}/` },
      { name: 'Teams', url: `${origin}/?view=teams` },
      { name: team.name, url: `${origin}/teams/${encodeParam(slug)}` },
      { name: seasonParam, url: canonicalUrl },
    ]));

    const [allGames, slugIdx, recaps] = await Promise.all([
      getTeamGames(assetFetcher, originUrl, team.espnId),
      getSrSlugIndex(assetFetcher, originUrl),
      getTeamRecaps(assetFetcher, originUrl, team.espnId),
    ]);
    const seasonGames = allGames ? gamesForSeason(allGames, seasonParam) : [];
    // Thin-page guard: a season page with almost no recorded games has no
    // content value — keep it reachable but out of the index.
    if (seasonGames.length < 3) {
      metaTags.push({ key: 'robots', value: 'noindex, follow' });
    }
    ssrHtml = renderSeasonSsr(team, seasonRow, seasonGames, teams, origin, slugIdx, recaps);
  } else if (teamParam) {
    const team = lookupTeam(teamParam, teams, index);
    if (!team) return isPathRoute ? notFound() : context.next();

    // Path URL is the forever/canonical form; ?team= canonicalizes to it.
    canonicalUrl = `${origin}/teams/${encodeParam(teamSlug(team.name))}`;

    const champYearsText = team.champYears.length ? ` (${team.champYears.join(', ')})` : '';
    const ncText = team.natlChamps > 0
      ? `${team.natlChamps} National Championship${team.natlChamps > 1 ? 's' : ''}${champYearsText}`
      : 'No National Championships';
    const ffText = `${team.finalFours} Final Four${team.finalFours === 1 ? '' : 's'}`;

    pageTitle = `${team.name} — Hoopsipedia`;
    const description = `${team.name} basketball: ${team.allTimeW}-${team.allTimeL} all-time record, ${ncText}, ${ffText}. Member of the ${team.conf}. Full program history, stats, and head-to-head comparisons on Hoopsipedia.`;
    const imageUrl = `https://a.espncdn.com/i/teamlogos/ncaa/500/${team.espnId}.png`;

    metaTags = [
      { key: 'description', value: description },
      { key: 'og:type', value: 'website' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];

    jsonLdBlocks.push({
      '@context': 'https://schema.org',
      '@type': 'SportsTeam',
      name: team.name,
      alternateName: team.mascot,
      sport: 'Basketball',
      memberOf: { '@type': 'SportsOrganization', name: team.conf },
      url: canonicalUrl,
      logo: imageUrl,
    });
    jsonLdBlocks.push(breadcrumbLd([
      { name: 'Hoopsipedia', url: `${origin}/` },
      { name: 'Teams', url: `${origin}/?view=teams` },
      { name: team.name, url: canonicalUrl },
    ]));

    // Visible SSR block: full program history (season table, championships,
    // conference links). index.html removes #ssr-content on SPA hydration.
    const [seasons, history] = await Promise.all([
      getTeamSeasons(assetFetcher, originUrl, team.espnId),
      getTeamHistory(assetFetcher, originUrl),
    ]);
    ssrHtml = renderTeamSsr(team, seasons, teams, origin, history);
  } else if (compareParam) {
    const parts = compareParam.split('/');
    if (parts.length !== 2) return context.next();

    const team1 = lookupTeam(parts[0], teams, index);
    const team2 = lookupTeam(parts[1], teams, index);
    if (!team1 || !team2) return context.next();

    canonicalUrl = `${origin}/?compare=${encodeParam(compareParam)}`;
    pageTitle = `${team1.name} vs ${team2.name} — Hoopsipedia`;
    const description = 'Head-to-head comparison on Hoopsipedia';
    const imageUrl = `https://a.espncdn.com/i/teamlogos/ncaa/500/${team1.espnId}.png`;

    metaTags = [
      { key: 'og:type', value: 'website' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];
  } else if (champParam) {
    // ?championship=1985/villanova-wildcats
    const slashIdx = champParam.indexOf('/');
    if (slashIdx < 0) return context.next();

    const year = champParam.substring(0, slashIdx);
    const teamSlugStr = champParam.substring(slashIdx + 1);
    const team = lookupTeam(teamSlugStr, teams, index);

    const teamName = team ? team.name : teamSlugStr.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    canonicalUrl = `${origin}/?championship=${encodeParam(champParam)}`;
    pageTitle = `${teamName} — ${year} National Champions | Hoopsipedia`;
    const description = `Relive ${teamName}'s ${year} championship run. Full tournament path, box scores, highlights, and the story of how they cut down the nets.`;
    const imageUrl = team
      ? `https://a.espncdn.com/i/teamlogos/ncaa/500/${team.espnId}.png`
      : `https://www.hoopsipedia.com/branding/hoopsipedia-logo.png`;

    jsonLdBlocks.push({
      '@context': 'https://schema.org',
      '@type': 'SportsEvent',
      name: `${year} NCAA Men's Basketball National Championship`,
      description: `${teamName} won the ${year} NCAA Men's Basketball National Championship.`,
      startDate: year,
      url: canonicalUrl,
      competitor: {
        '@type': 'SportsTeam',
        name: teamName,
        sport: 'Basketball',
        ...(team ? { logo: imageUrl } : {}),
      },
    });
    jsonLdBlocks.push(breadcrumbLd([
      { name: 'Hoopsipedia', url: `${origin}/` },
      { name: 'Championship Journeys', url: `${origin}/?view=champions` },
      { name: `${year} — ${teamName}`, url: canonicalUrl },
    ]));

    metaTags = [
      { key: 'description', value: description },
      { key: 'og:type', value: 'article' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];
  } else if (viewParam) {
    // ?view=teams, ?view=upsets, ?view=classics, ?view=champions
    const viewMeta = {
      'teams': {
        title: 'All Division I College Basketball Programs — Hoopsipedia',
        description: 'Browse every Division I men\'s basketball program by conference. All-time records, season-by-season results, coaches, and NCAA Tournament history for 365+ teams.',
        image: 'https://www.hoopsipedia.com/branding/hoopsipedia-logo.png',
      },
      'upsets': {
        title: 'Greatest NCAA Tournament Upsets of All Time — Hoopsipedia',
        description: 'Every Cinderella story, every bracket buster. Explore the most shocking upsets in March Madness history with scores, highlights, and the stories behind the madness.',
        image: 'https://www.hoopsipedia.com/branding/hoopsipedia-logo.png',
      },
      'classics': {
        title: '⚡ Instant Classics — 2026 NCAA Tournament | Hoopsipedia',
        description: 'Buzzer beaters, overtime thrillers, and games you\'ll never forget from the 2026 NCAA Tournament.',
        image: 'https://www.hoopsipedia.com/branding/hoopsipedia-logo.png',
      },
      'champions': {
        title: '🏆 Championship Journeys — Every Path to Cutting Down the Nets | Hoopsipedia',
        description: 'Relive every championship run in NCAA Tournament history. Game-by-game breakdowns, box scores, highlights, and the stories behind each title.',
        image: 'https://www.hoopsipedia.com/branding/hoopsipedia-logo.png',
      },
    };
    const vm = viewMeta[viewParam];
    if (!vm) return context.next();

    if (viewParam === 'teams') {
      ssrHtml = renderTeamsDirectorySsr(teams, origin);
    }

    canonicalUrl = `${origin}/?view=${encodeParam(viewParam)}`;
    pageTitle = vm.title;
    const description = vm.description;
    const imageUrl = vm.image;

    jsonLdBlocks.push(breadcrumbLd([
      { name: 'Hoopsipedia', url: `${origin}/` },
      { name: pageTitle.replace(/ [—|].*$/, ''), url: canonicalUrl },
    ]));

    metaTags = [
      { key: 'description', value: description },
      { key: 'og:type', value: 'website' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];
  } else if (gameParam) {
    // ?game=2026/vcu-rams-vs-north-carolina-tar-heels
    const slashIdx = gameParam.indexOf('/');
    if (slashIdx < 0) return context.next();

    const year = gameParam.substring(0, slashIdx);
    const matchupSlug = gameParam.substring(slashIdx + 1);
    const vsIdx = matchupSlug.indexOf('-vs-');
    if (vsIdx < 0) return context.next();

    const winnerSlug = matchupSlug.substring(0, vsIdx);
    const loserSlug = matchupSlug.substring(vsIdx + 4);

    const winner = lookupTeam(winnerSlug, teams, index);
    const loser = lookupTeam(loserSlug, teams, index);

    // Build title and description even if team lookup fails
    const winnerName = winner ? winner.name : winnerSlug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const loserName = loser ? loser.name : loserSlug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

    // Known Instant Classics (non-upset memorable games)
    const instantClassics = {
      '2026/kentucky-wildcats-vs-santa-clara-broncos': {
        title: `⚡ Instant Classic: Kentucky Survives Santa Clara in OT — ${year} NCAA Tournament | Hoopsipedia`,
        desc: `Otega Oweh banks in a 32-foot buzzer beater to force overtime. Kentucky wins 89-84 in an instant classic first-round thriller.`
      }
    };

    const classicKey = `${year}/${matchupSlug}`;
    const classic = instantClassics[classicKey];

    canonicalUrl = `${origin}/?game=${encodeParam(gameParam)}`;
    pageTitle = classic
      ? classic.title
      : `${winnerName} Upsets ${loserName} — ${year} NCAA Tournament | Hoopsipedia`;
    const description = classic
      ? classic.desc
      : `Relive the Moment: ${winnerName} defeats ${loserName} in the ${year} NCAA Tournament. Box score, highlights, and why this upset mattered.`;
    const imageUrl = winner
      ? `https://a.espncdn.com/i/teamlogos/ncaa/500/${winner.espnId}.png`
      : `https://www.hoopsipedia.com/branding/hoopsipedia-logo.png`;

    jsonLdBlocks.push({
      '@context': 'https://schema.org',
      '@type': 'SportsEvent',
      name: `${winnerName} vs ${loserName} — ${year} NCAA Tournament`,
      description,
      startDate: year,
      url: canonicalUrl,
      competitor: [
        { '@type': 'SportsTeam', name: winnerName, sport: 'Basketball' },
        { '@type': 'SportsTeam', name: loserName, sport: 'Basketball' },
      ],
    });
    jsonLdBlocks.push(breadcrumbLd([
      { name: 'Hoopsipedia', url: `${origin}/` },
      { name: 'Greatest Upsets', url: `${origin}/?view=upsets` },
      { name: `${winnerName} vs ${loserName} (${year})`, url: canonicalUrl },
    ]));

    metaTags = [
      { key: 'description', value: description },
      { key: 'og:type', value: 'article' },
      { key: 'og:title', value: pageTitle },
      { key: 'og:description', value: description },
      { key: 'og:image', value: imageUrl },
      { key: 'og:url', value: canonicalUrl },
      { key: 'og:site_name', value: 'Hoopsipedia' },
      { key: 'twitter:card', value: 'summary_large_image' },
      { key: 'twitter:title', value: pageTitle },
      { key: 'twitter:description', value: description },
      { key: 'twitter:image', value: imageUrl },
    ];
  } else if (isHomepage) {
    // Keep index.html's own title/description; just add canonical, WebSite
    // schema, and the crawler-visible SSR content block.
    canonicalUrl = `${origin}/`;
    jsonLdBlocks.push({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: 'Hoopsipedia',
      url: `${origin}/`,
      description: 'The college basketball history encyclopedia: 365+ Division I programs, 77 seasons of records, NCAA Tournament history, and historical rankings.',
    });
    ssrHtml = renderHomepageSsr(teams, origin);
  }

  // Set of tags to remove from existing HTML
  const tagsToRemove = new Set(metaTags.map(t => t.key));

  // Extra head HTML: canonical link + JSON-LD structured data
  const extraHeadParts = [
    `<link rel="canonical" href="${escapeAttr(canonicalUrl)}">`,
    ...jsonLdBlocks.map(jsonLdScript),
  ];
  const extraHeadHtml = extraHeadParts.join('\n    ');

  // Use HTMLRewriter to stream-replace meta tags
  let rewriter = new HTMLRewriter()
    .on('meta', new MetaTagRemover(tagsToRemove))
    .on('link', new CanonicalRemover())
    .on('head', new HeadInjector(metaTags, pageTitle, extraHeadHtml));

  // Homepage keeps index.html's own <title>; an empty pageTitle must not
  // blank it out.
  if (pageTitle) {
    rewriter = rewriter.on('title', new TitleRewriter(pageTitle));
  }

  if (ssrHtml) {
    rewriter = rewriter.on('body', new BodyPrepender(ssrHtml));
  }

  const rewritten = rewriter.transform(originResp);

  // Return with appropriate headers
  const response = new Response(rewritten.body, rewritten);
  response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');
  return response;
}
