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
  // The inline script hides the block immediately for JS-enabled browsers so
  // the SPA's later removal of it causes no layout shift; crawlers and no-JS
  // users still get the visible content.
  return `<div id="ssr-content"><section style="${SSR_SECTION_STYLE}">${inner}</section></div>` +
    `<script>(function(){var s=document.getElementById('ssr-content');if(s)s.style.display='none';})();</script>`;
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
      const record = (s.record || `${s.wins}-${s.losses}`) + (s.synthesized ? ' *' : '');
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
      `</tr></thead><tbody>${rows}</tbody></table>` +
      (seasons.some(s => s.synthesized) ? `<p>* Season vacated by the NCAA — absent from the official season table; record computed from the game log and not counted in official totals or rankings.</p>` : '')
    );
  }

  const rivals = conferenceTeams(teams, team.conf, team.espnId);
  if (rivals.length) {
    const rivalLinks = rivals.map(r => `<a href="${teamHref(origin, r.slug)}">${escapeHtml(r.name)}</a>`).join(' · ');
    parts.push(`<h2>More ${escapeHtml(team.conf)} programs</h2><p>${rivalLinks}</p>`);
  }

  parts.push(`<p><a href="${origin}/teams">All Division I programs</a> · <a href="${origin}/rankings">Historical rankings</a> · <a href="${origin}/champions">Championship journeys</a> · <a href="${origin}/">Hoopsipedia home</a></p>`);

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

// Templated season story built from the game log and the program's other
// seasons — every sentence is a computed fact, so it is safe to generate for
// all 26,000 season pages. Gives thin seasons real, page-specific content and
// links each season to its neighbours (prev/next) for crawl connectivity.
function fmtDate(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || '');
  if (!m) return d || '';
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(m[2], 10) - 1]} ${parseInt(m[3], 10)}, ${m[1]}`;
}

function ordinal(n) {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function renderSeasonStory(team, seasonRow, games, seasons, teams, origin, slugIdx) {
  const slug = teamSlug(team.name);
  const nick = team.name.split(' ').slice(1).join(' ') || team.name; // "Wildcats"
  const oppNameOf = (g) => {
    let oppT = teams[String(g.opp)];
    if (!oppT && g.opp_slug && slugIdx && slugIdx[g.opp_slug]) oppT = teams[slugIdx[g.opp_slug]];
    const name = oppT ? oppT[F.NAME] : (g.opp_slug || 'an unlisted opponent').replace(/-/g, ' ');
    return oppT ? `<a href="${teamHref(origin, teamSlug(oppT[F.NAME]))}">${escapeHtml(name)}</a>` : escapeHtml(name);
  };
  const paras = [];

  if (games.length >= 3) {
    const counted = games.filter(g => !g.vacated);
    const split = { H: [0, 0], A: [0, 0], N: [0, 0] };
    let pf = 0, pa = 0, ot = 0;
    let streak = 0, bestStreak = 0, streakEnd = null, curStart = null, bestStart = null;
    let bestWin = null, worstLoss = null, closest = null;
    for (const g of counted) {
      const k = split[g.loc] ? g.loc : 'N';
      split[k][g.w ? 0 : 1]++;
      pf += g.pts; pa += g.opp_pts;
      if (g.ot) ot++;
      const margin = g.pts - g.opp_pts;
      if (g.w) {
        if (streak === 0) curStart = g.date;
        streak++;
        if (streak > bestStreak) { bestStreak = streak; streakEnd = g.date; bestStart = curStart; }
        if (!bestWin || margin > bestWin.pts - bestWin.opp_pts) bestWin = g;
      } else {
        streak = 0;
        if (!worstLoss || margin < worstLoss.pts - worstLoss.opp_pts) worstLoss = g;
      }
      if (Math.abs(margin) <= 3 && (!closest || Math.abs(margin) < Math.abs(closest.pts - closest.opp_pts))) closest = g;
    }
    const n = counted.length;
    const bits = [];
    bits.push(`Hoopsipedia's log holds ${n} game${n === 1 ? '' : 's'} from this season: ${split.H[0]}–${split.H[1]} at home, ${split.A[0]}–${split.A[1]} on the road${(split.N[0] + split.N[1]) ? `, and ${split.N[0]}–${split.N[1]} on neutral courts` : ''}.`);
    if (n > 0) {
      const diff = (pf - pa) / n;
      bits.push(` The ${escapeHtml(nick)} scored ${(pf / n).toFixed(1)} points per game and allowed ${(pa / n).toFixed(1)} (${diff >= 0 ? '+' : ''}${diff.toFixed(1)} per game).`);
    }
    if (bestStreak >= 3) bits.push(` Their longest winning streak ran ${bestStreak} games, from ${fmtDate(bestStart)} to ${fmtDate(streakEnd)}.`);
    if (bestWin) bits.push(` The most lopsided win was ${bestWin.pts}–${bestWin.opp_pts} ${bestWin.loc === 'A' ? 'at' : 'over'} ${oppNameOf(bestWin)} on ${fmtDate(bestWin.date)}`);
    if (worstLoss) bits.push(`${bestWin ? ';' : ''} the heaviest defeat was ${worstLoss.opp_pts}–${worstLoss.pts} ${worstLoss.loc === 'A' ? 'at' : 'to'} ${oppNameOf(worstLoss)} on ${fmtDate(worstLoss.date)}.`);
    else if (bestWin) bits.push('.');
    if (closest) bits.push(` The tightest finish was a ${Math.abs(closest.pts - closest.opp_pts)}-point ${closest.w ? 'win' : 'loss'} against ${oppNameOf(closest)} (${closest.pts}–${closest.opp_pts}${closest.ot ? ', overtime' : ''}).`);
    if (ot) bits.push(` ${ot} game${ot === 1 ? ' went' : 's went'} to overtime.`);
    paras.push(`<p>${bits.join('')}</p>`);
  }

  // Program context + prev/next season links
  if (Array.isArray(seasons) && seasons.length > 1) {
    const sorted = [...seasons].filter(r => r && r.year).sort((a, b) => String(a.year).localeCompare(String(b.year)));
    const idx = sorted.findIndex(r => r.year === seasonRow.year);
    const pct = (r) => (r.wins + r.losses) > 0 ? r.wins / (r.wins + r.losses) : null;
    const thisPct = pct(seasonRow);
    const bits = [];
    if (thisPct != null) {
      const rated = sorted.filter(r => pct(r) != null && (r.wins + r.losses) >= 10);
      const better = rated.filter(r => pct(r) > thisPct).length;
      if (rated.length >= 5 && (seasonRow.wins + seasonRow.losses) >= 10) {
        const poss = /s$/i.test(team.name) ? `${escapeHtml(team.name)}'` : `${escapeHtml(team.name)}'s`;
        bits.push(`Among ${poss} ${rated.length} recorded seasons, ${escapeHtml(seasonRow.year)}'s .${Math.round(thisPct * 1000).toString().padStart(3, '0')} winning percentage ranks ${ordinal(better + 1)}.`);
      }
    }
    const prev = idx > 0 ? sorted[idx - 1] : null;
    const next = idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null;
    const link = (r) => `<a href="${seasonHref(origin, slug, r.year)}">${escapeHtml(r.year)} ${escapeHtml(nick)} (${r.wins}–${r.losses})</a>`;
    if (prev) bits.push(` Previous season: ${link(prev)}.`);
    if (next) bits.push(` Next season: ${link(next)}.`);
    if (bits.length) paras.push(`<p>${bits.join('')}</p>`);
  }
  return paras.join('\n');
}

function renderSeasonSsr(team, seasonRow, games, teams, origin, slugIdx, recaps, seasons) {
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
  if (seasonRow.synthesized) bits.push(` This season is absent from the official season table (results later vacated by the NCAA); the record shown is computed from the logged games.`);
  parts.push(`<p>${bits.join('')}</p>`);
  parts.push(renderSeasonStory(team, seasonRow, games, seasons, teams, origin, slugIdx));

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

  parts.push(`<p><a href="${origin}/teams/${encodeParam(slug)}">${escapeHtml(team.name)} program history</a> · <a href="${origin}/teams">All Division I programs</a> · <a href="${origin}/">Hoopsipedia home</a></p>`);

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

  parts.push(`<p><a href="${origin}/coaches">All-time coaches leaderboard</a> · <a href="${origin}/teams">All Division I programs</a> · <a href="${origin}/">Hoopsipedia home</a></p>`);

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
    `<p>Explore: <a href="${origin}/teams">All teams</a> · <a href="${origin}/rankings">Rankings</a> · <a href="${origin}/bracket">Tournament bracket</a> · <a href="${origin}/coaches">Coaches</a> · <a href="${origin}/champions">Championship journeys</a> · <a href="${origin}/upsets">Greatest upsets</a> · <a href="${origin}/classics">Instant classics</a></p>`,
    `<h2>Winningest programs of all time</h2><p>${winningest}</p>`,
    `<h2>Recent national champions</h2><p>${champList}</p>`,
  ];
  return ssrWrap(parts.join('\n'));
}

// ── Section pages (forever URLs) ─────────────────────────────────────────
// /rankings, /time-machine, /players, /rivalries, /coaches, /teams, /bracket,
// /upsets, /classics, /champions — plus /rivalries/{slug} and
// /time-machine/{slugA}/{seasonA}/{slugB}/{seasonB}. Each gets a canonical
// path, page-specific meta, and a crawler-visible SSR block built from the
// same JSON the SPA renders. The legacy ?view= form 301s to the path.

const LOGO_IMAGE = 'https://www.hoopsipedia.com/branding/hoopsipedia-logo.png';

const SECTION_META = {
  'teams': {
    title: 'All Division I College Basketball Programs — Hoopsipedia',
    description: 'Browse every Division I men\'s basketball program by conference. All-time records, season-by-season results, coaches, and NCAA Tournament history for 365+ teams.',
  },
  'rankings': {
    title: 'College Basketball Rankings — All-Time Programs & the Greatest Seasons Ever (HTSS) — Hoopsipedia',
    description: 'The winningest programs, the most championships, and Hoopsipedia\'s HTSS — a cross-era score for every team-season since 1949. Who was better: 1972 UCLA or 2015 Kentucky? Settle it here.',
  },
  'time-machine': {
    title: 'Time Machine — Greatest College Basketball Games Never Played — Hoopsipedia',
    description: 'Cross-era matchups simulated from adjusted efficiency and HTSS: 1972 UCLA vs 2015 Kentucky, 1992 Duke vs 2018 Villanova, and any two team-seasons you pick. Predicted scores and win probability.',
  },
  'players': {
    title: 'Player Archive — Box-Score Leaders Across 20,000+ Archived Games — Hoopsipedia',
    description: 'Points per game, rebounds, assists and more from every archived college basketball box score, 1908 to today — with honest coverage denominators for every program.',
  },
  'rivalries': {
    title: 'College Basketball Rivalries — All-Time Series Records — Hoopsipedia',
    description: 'Duke–UNC, Kentucky–Louisville, Kansas–Missouri and the other great rivalries: all-time series records, decade-by-decade timelines, biggest wins, and recent meetings.',
  },
  'coaches': {
    title: 'All-Time Winningest College Basketball Coaches — Top 100 — Hoopsipedia',
    description: 'The 100 winningest head coaches in Division I history, verified against the NCAA record book: wins, losses, titles, Final Fours, and career tenures.',
  },
  'bracket': {
    title: 'NCAA Tournament Bracket — Live Scores & Historical Context — Hoopsipedia',
    description: 'The NCAA Tournament bracket with live scores, seed-matchup history, upset alerts, and every team\'s tournament résumé.',
  },
  'upsets': {
    title: 'Greatest NCAA Tournament Upsets of All Time — Hoopsipedia',
    description: 'Every Cinderella story, every bracket buster. Explore the most shocking upsets in March Madness history with scores, highlights, and the stories behind the madness.',
  },
  'classics': {
    title: '⚡ Instant Classics — 2026 NCAA Tournament | Hoopsipedia',
    description: 'Buzzer beaters, overtime thrillers, and games you\'ll never forget from the 2026 NCAA Tournament.',
  },
  'champions': {
    title: '🏆 Championship Journeys — Every Path to Cutting Down the Nets | Hoopsipedia',
    description: 'Relive every championship run in NCAA Tournament history. Game-by-game breakdowns, box scores, highlights, and the stories behind each title.',
  },
};

// Per-isolate cache for the JSON the section pages read.
const jsonCache = new Map();
async function getJsonCached(assetFetcher, originUrl, path) {
  if (jsonCache.has(path)) return jsonCache.get(path);
  try {
    const resp = await assetFetcher.fetch(new URL(path, originUrl).toString());
    if (!resp.ok) return null;
    const data = await resp.json();
    jsonCache.set(path, data);
    return data;
  } catch (e) {
    return null;
  }
}

function teamLinkByName(origin, name) {
  return `<a href="${teamHref(origin, teamSlug(name))}">${escapeHtml(name)}</a>`;
}

function renderRankingsSsr(teams, htss, origin) {
  const entries = Object.values(teams);
  const rows = (list, cells) => `<table style="${SSR_TABLE_STYLE}">${list.map(cells).join('')}</table>`;
  const cell = (v) => `<td style="${SSR_CELL_STYLE}">${v}</td>`;

  const winningest = [...entries].sort((a, b) => b[F.ATW] - a[F.ATW]).slice(0, 25);
  const champs = [...entries].filter(t => t[F.NC] > 0).sort((a, b) => b[F.NC] - a[F.NC] || b[F.FF] - a[F.FF]).slice(0, 20);

  const parts = [
    `<h1>College basketball rankings — all-time programs and the greatest seasons ever</h1>`,
    `<p>Two kinds of ranking live here. The record book: all-time wins, national championships, Final Fours. And Hoopsipedia's own <strong>HTSS (Historical Team-Season Score)</strong>, which scores every Division I team-season since 1949 on one scale — adjusted efficiency, schedule strength, tournament result, quality wins, poll perception, coaching, and NBA draft talent, era-normalized — so a 1972 team and a 2015 team can be compared honestly. Scale: 50 is average, 70–75 elite, 80–85 transcendent, 85+ GOAT tier.</p>`,
    `<p>Related: <a href="${origin}/time-machine">Time Machine cross-era matchups</a> · <a href="${origin}/players">Player archive</a> · <a href="${origin}/coaches">Winningest coaches</a> · <a href="${origin}/champions">Championship journeys</a></p>`,
    `<h2>Winningest programs of all time</h2>`,
    rows(winningest, (t, i) => `<tr>${cell(i + 1)}${cell(teamLinkByName(origin, t[F.NAME]))}${cell(`${t[F.ATW]}–${t[F.ATL]}`)}${cell(((t[F.ATW] / (t[F.ATW] + t[F.ATL])) * 100).toFixed(1) + '%')}</tr>`),
    `<h2>Most national championships</h2>`,
    rows(champs, (t, i) => `<tr>${cell(i + 1)}${cell(teamLinkByName(origin, t[F.NAME]))}${cell(`${t[F.NC]} title${t[F.NC] === 1 ? '' : 's'}`)}${cell((Array.isArray(t[F.NCY]) ? t[F.NCY] : []).join(', '))}</tr>`),
  ];

  if (htss && Array.isArray(htss.allTimeTop100)) {
    const top = htss.allTimeTop100.slice(0, 25);
    parts.push(`<h2>HTSS: the 25 greatest team-seasons since 1949</h2>`);
    parts.push(rows(top, s => `<tr>${cell(s.rank)}${cell(`<a href="${seasonHref(origin, teamSlug(s.team), s.season)}">${escapeHtml(s.season)} ${escapeHtml(s.team)}</a>`)}${cell(escapeHtml(s.record || ''))}${cell(escapeHtml(s.coach || ''))}${cell(escapeHtml(s.tourneyResult || ''))}${cell(`HTSS ${s.htss}`)}</tr>`));
  }
  if (htss && Array.isArray(htss.programRankings)) {
    const top = htss.programRankings.slice(0, 25);
    parts.push(`<h2>HTSS program rankings — sustained greatness</h2>`);
    parts.push(`<p>A program's score is the average HTSS of its ten best seasons: a measure of peak sustained quality rather than longevity.</p>`);
    parts.push(rows(top, p => `<tr>${cell(p.rank)}${cell(teamLinkByName(origin, p.team))}${cell(`Score ${p.score}`)}${cell(`Best season: <a href="${seasonHref(origin, teamSlug(p.team), p.bestSeason)}">${escapeHtml(p.bestSeason)}</a>`)}</tr>`));
  }
  return ssrWrap(parts.join('\n'));
}

// "1971-72" -> 1972: seasons are named by the year the tournament was played.
function seasonEndYear(season) {
  return String(parseInt(String(season).slice(0, 4), 10) + 1);
}

function tmMatchupHref(origin, m) {
  return `${origin}/time-machine/${teamSlug(m.teamA.name)}/${m.teamA.season}/${teamSlug(m.teamB.name)}/${m.teamB.season}`;
}

function renderTimeMachineSsr(tm, origin) {
  const parts = [
    `<h1>Time Machine — the greatest college basketball games never played</h1>`,
    `<p>What happens when 1972 UCLA plays 2015 Kentucky? The Time Machine simulates cross-era matchups from each team's adjusted offensive and defensive efficiency (computed retroactively from every game in the database), its HTSS score, tempo, and era context, and produces a predicted score and win probability. Pick any two team-seasons since 1949 on the interactive version of this page.</p>`,
    `<p>See also: <a href="${origin}/rankings">HTSS rankings — the greatest seasons ever</a> · <a href="${origin}/rivalries">Rivalries</a></p>`,
  ];
  const matchups = (tm && Array.isArray(tm.matchups)) ? tm.matchups : [];
  for (const m of matchups) {
    const a = m.teamA, b = m.teamB, p = m.prediction || {};
    const seasonA = seasonEndYear(a.season), seasonB = seasonEndYear(b.season);
    parts.push(`<h2><a href="${tmMatchupHref(origin, m)}">${escapeHtml(seasonA)} ${escapeHtml(a.name)} vs ${escapeHtml(seasonB)} ${escapeHtml(b.name)}</a></h2>`);
    parts.push(`<p><strong>Prediction: ${escapeHtml(p.winner || '')} ${p.winnerScore ?? ''}–${p.loserScore ?? ''}</strong> (${p.winProbA ?? ''}% ${escapeHtml(a.name)} · ${p.winProbB ?? ''}% ${escapeHtml(b.name)}). `
      + `<a href="${seasonHref(origin, teamSlug(a.name), a.season)}">${escapeHtml(a.season)} ${escapeHtml(a.name)}</a> went ${escapeHtml(a.record || '')} under ${escapeHtml(a.coach || '')} (HTSS ${a.htss}, adjEM ${a.adjEM}); `
      + `<a href="${seasonHref(origin, teamSlug(b.name), b.season)}">${escapeHtml(b.season)} ${escapeHtml(b.name)}</a> went ${escapeHtml(b.record || '')} under ${escapeHtml(b.coach || '')} (HTSS ${b.htss}, adjEM ${b.adjEM}).</p>`);
    if (m.narrative && m.narrative !== '__loading__') parts.push(`<p>${escapeHtml(m.narrative)}</p>`);
  }
  return ssrWrap(parts.join('\n'));
}

function renderTimeMachineMatchupSsr(teamA, seasonA, rowA, teamB, seasonB, rowB, origin) {
  const yr = seasonEndYear;
  const desc = (t, s, r) => `<a href="${seasonHref(origin, teamSlug(t.name), s)}">${escapeHtml(s)} ${escapeHtml(t.name)}</a>`
    + (r ? ` finished ${r.wins}-${r.losses}${r.coach ? ` under ${escapeHtml(r.coach)}` : ''}${r.ncaaTourney ? ` (${escapeHtml(String(r.ncaaTourney))})` : ''}` : '');
  const parts = [
    `<h1>Time Machine: ${escapeHtml(yr(seasonA))} ${escapeHtml(teamA.name)} vs ${escapeHtml(yr(seasonB))} ${escapeHtml(teamB.name)}</h1>`,
    `<p>${desc(teamA, seasonA, rowA)}. ${desc(teamB, seasonB, rowB)}. The Time Machine simulates this cross-era matchup from each team's retroactive adjusted efficiency, HTSS score, and tempo, and produces a predicted score with win probability — rendered on this page.</p>`,
    `<p>More: <a href="${origin}/time-machine">All featured Time Machine matchups</a> · <a href="${teamHref(origin, teamSlug(teamA.name))}">${escapeHtml(teamA.name)} history</a> · <a href="${teamHref(origin, teamSlug(teamB.name))}">${escapeHtml(teamB.name)} history</a> · <a href="${origin}/rankings">HTSS rankings</a></p>`,
  ];
  return ssrWrap(parts.join('\n'));
}

function renderPlayersSsr(players, teams, origin) {
  const meta = (players && players._metadata) || {};
  const cell = (v) => `<td style="${SSR_CELL_STYLE}">${v}</td>`;
  const teamLink = (key) => {
    const t = players.teams && players.teams[key];
    const eid = t && t.espnId != null ? String(t.espnId) : null;
    if (eid && teams[eid]) return teamLinkByName(origin, teams[eid][F.NAME]);
    return escapeHtml(key.replace(/-/g, ' '));
  };
  const parts = [
    `<h1>Player archive — box-score leaders across ${(meta.archivedGames || 0).toLocaleString()} archived games</h1>`,
    `<p>Every stat here comes from an archived box score in Hoopsipedia's database — ${(meta.players || 0).toLocaleString()} players across ${meta.d1Programs || 0} Division I programs, from 1908 to the current season. It is an archive, not a career-stats service: coverage is uneven by program, so leaderboards are sorted <strong>per game</strong> (minimum ${meta.minGamesForRateLeaderboard || 8} archived games) and every team view states how many of its games are archived.</p>`,
    `<p>Related: <a href="${origin}/rankings">Team rankings</a> · <a href="${origin}/teams">All programs</a></p>`,
  ];
  const ppg = (players && players.pointsPerGame) || [];
  if (ppg.length) {
    parts.push(`<h2>Highest points per game in the archive</h2>`);
    parts.push(`<table style="${SSR_TABLE_STYLE}">${ppg.slice(0, 30).map((p, i) => `<tr>${cell(i + 1)}${cell(escapeHtml(p.name))}${cell(teamLink(p.team))}${cell(`${p.ppg} ppg`)}${cell(`${p.games} archived games, ${Array.isArray(p.years) ? p.years.join('–') : ''}`)}</tr>`).join('')}</table>`);
  }
  const most = (players && players.mostArchivedPoints) || [];
  if (most.length) {
    parts.push(`<h2>Most archived points</h2><p>Totals reflect how deeply a program's games have been archived, not career scoring — a player from a well-archived program will rank above a greater scorer whose games are not yet in the database.</p>`);
    parts.push(`<table style="${SSR_TABLE_STYLE}">${most.slice(0, 15).map((p, i) => `<tr>${cell(i + 1)}${cell(escapeHtml(p.name))}${cell(teamLink(p.team))}${cell(`${p.pts.toLocaleString()} pts in ${p.games} archived games`)}</tr>`).join('')}</table>`);
  }
  return ssrWrap(parts.join('\n'));
}

function rivalrySeries(r, h2h, teams) {
  const t1 = teams[r.team1Id], t2 = teams[r.team2Id];
  if (!t1 || !t2) return '';
  const rec = h2h && h2h[r.team1Id] && h2h[r.team1Id][r.team2Id];
  if (!rec) return '';
  const n1 = t1[F.NAME], n2 = t2[F.NAME];
  if (rec.w > rec.l) return `${n1} leads the all-time series ${rec.w}–${rec.l}`;
  if (rec.l > rec.w) return `${n2} leads the all-time series ${rec.l}–${rec.w}`;
  return `The all-time series is tied ${rec.w}–${rec.l}`;
}

function renderRivalriesSsr(rivalries, h2h, teams, origin) {
  const parts = [
    `<h1>College basketball rivalries — all-time series records</h1>`,
    `<p>The games that matter most, with the full record behind them: every meeting in the database, decade-by-decade series timelines, biggest wins, and recent results. Click any rivalry for the complete history, or <a href="${origin}/#comparison">compare any two programs</a>.</p>`,
  ];
  for (const r of rivalries) {
    const t1 = teams[r.team1Id], t2 = teams[r.team2Id];
    if (!t1 || !t2) continue;
    const series = rivalrySeries(r, h2h, teams);
    parts.push(`<h2><a href="${origin}/rivalries/${encodeURIComponent(r.slug)}">${escapeHtml(r.name)}: ${escapeHtml(t1[F.NAME])} vs ${escapeHtml(t2[F.NAME])}</a></h2>`);
    parts.push(`<p>${series ? `<strong>${escapeHtml(series)}.</strong> ` : ''}${escapeHtml(r.description || '')} <a href="${teamHref(origin, teamSlug(t1[F.NAME]))}">${escapeHtml(t1[F.NAME])}</a> · <a href="${teamHref(origin, teamSlug(t2[F.NAME]))}">${escapeHtml(t2[F.NAME])}</a></p>`);
  }
  return ssrWrap(parts.join('\n'));
}

function renderRivalrySsr(r, h2h, teams, origin) {
  const t1 = teams[r.team1Id], t2 = teams[r.team2Id];
  const series = rivalrySeries(r, h2h, teams);
  const s1 = teamSlug(t1[F.NAME]), s2 = teamSlug(t2[F.NAME]);
  const parts = [
    `<h1>${escapeHtml(r.name)}: ${escapeHtml(t1[F.NAME])} vs ${escapeHtml(t2[F.NAME])}</h1>`,
    `<p>${series ? `<strong>${escapeHtml(series)}.</strong> ` : ''}${escapeHtml(r.description || '')}</p>`,
    `<p>${escapeHtml(t1[F.NAME])}: ${t1[F.ATW]}–${t1[F.ATL]} all-time, ${t1[F.NC]} national title${t1[F.NC] === 1 ? '' : 's'}, ${t1[F.FF]} Final Fours. ${escapeHtml(t2[F.NAME])}: ${t2[F.ATW]}–${t2[F.ATL]} all-time, ${t2[F.NC]} national title${t2[F.NC] === 1 ? '' : 's'}, ${t2[F.FF]} Final Fours.</p>`,
    `<p><a href="${origin}/?compare=${encodeParam(`${s1}/${s2}`)}">Full head-to-head comparison</a> · <a href="${teamHref(origin, s1)}">${escapeHtml(t1[F.NAME])} history</a> · <a href="${teamHref(origin, s2)}">${escapeHtml(t2[F.NAME])} history</a> · <a href="${origin}/rivalries">All rivalries</a></p>`,
  ];
  return ssrWrap(parts.join('\n'));
}

function renderCoachesSsr(coachLb, teams, origin) {
  const cell = (v) => `<td style="${SSR_CELL_STYLE}">${v}</td>`;
  const school = (c) => {
    let best = null, span = -1;
    for (const [tid, start, end] of (c.schools || [])) {
      if (end - start > span) { span = end - start; best = String(tid); }
    }
    return best && teams[best] ? teamLinkByName(origin, teams[best][F.NAME]) : '';
  };
  const parts = [
    `<h1>The 100 winningest coaches in Division I history</h1>`,
    `<p>Ranked by career Division I wins, verified against the NCAA record book. Each coach page carries the full season-by-season tenure history, titles and Final Fours, and head-to-head comparisons with any other coach.</p>`,
    `<table style="${SSR_TABLE_STYLE}">${coachLb.slice(0, 100).map((c, i) => `<tr>${cell(i + 1)}${cell(`<a href="${coachHref(origin, teamSlug(c.name))}">${escapeHtml(c.name)}</a>`)}${cell(`${c.wins}–${c.losses}`)}${cell(`${c.pct}%`)}${cell(school(c))}</tr>`).join('')}</table>`,
  ];
  return ssrWrap(parts.join('\n'));
}

function renderChampionsSsr(teams, origin) {
  const champs = [];
  for (const t of Object.values(teams)) {
    for (const y of (Array.isArray(t[F.NCY]) ? t[F.NCY] : [])) champs.push({ year: y, name: t[F.NAME] });
  }
  champs.sort((a, b) => b.year - a.year);
  const parts = [
    `<h1>Championship journeys — every NCAA champion, 1939 to today</h1>`,
    `<p>Every national champion's path through the bracket, game by game, with box scores, highlights and the Most Outstanding Player. Click a season to relive the run.</p>`,
    `<p>${champs.map(c => `<a href="${origin}/?championship=${encodeParam(`${c.year}/${teamSlug(c.name)}`)}">${c.year} ${escapeHtml(c.name)}</a>`).join(' · ')}</p>`,
  ];
  return ssrWrap(parts.join('\n'));
}

function renderSectionIntroSsr(section, origin) {
  const intro = {
    bracket: `<h1>NCAA Tournament bracket</h1><p>The full bracket with live scores during the tournament, seed-matchup history on every game ("16-seeds are 2–152 all-time vs 1-seeds"), upset alerts, and each team's tournament résumé. Off-season, it shows the most recent tournament.</p>`,
    upsets: `<h1>The greatest NCAA Tournament upsets of all time</h1><p>More than 340 verified upsets by seed matchup and era, each with the score, the box score where one exists, highlight video, and why it mattered.</p>`,
    classics: `<h1>Instant classics</h1><p>Buzzer beaters, overtime thrillers, and the games from the most recent NCAA Tournament nobody will forget.</p>`,
  }[section] || '';
  return ssrWrap(`${intro}<p><a href="${origin}/rankings">Rankings</a> · <a href="${origin}/champions">Championship journeys</a> · <a href="${origin}/teams">All programs</a></p>`);
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

  // Section forever URLs (see SECTION_META), rivalry pages, Time Machine matchups.
  let sectionParam = null, rivalrySlug = null, tmRoute = null;
  const sectionMatch = url.pathname.match(/^\/(teams|rankings|time-machine|players|rivalries|coaches|bracket|upsets|classics|champions)\/?$/);
  if (sectionMatch) sectionParam = sectionMatch[1];
  const rivalryMatch = url.pathname.match(/^\/rivalries\/([a-z0-9-]+)\/?$/);
  if (rivalryMatch) { sectionParam = 'rivalry'; rivalrySlug = rivalryMatch[1]; }
  const tmMatch = url.pathname.match(/^\/time-machine\/([a-z0-9-]+)\/(\d{4}-\d{2})\/([a-z0-9-]+)\/(\d{4}-\d{2})\/?$/);
  if (tmMatch) { sectionParam = 'time-machine-matchup'; tmRoute = tmMatch; }

  // Legacy ?view=X for a section that now has a path: 301 to the path so
  // search engines consolidate on one URL.
  if (viewParam && SECTION_META[viewParam] && url.pathname === '/') {
    return Response.redirect(`https://www.hoopsipedia.com/${viewParam}`, 301);
  }

  // Bare homepage gets SSR content too; everything else with no relevant
  // query params passes through to static files.
  const isHomepage = url.pathname === '/' && url.search === '';
  if (!isHomepage && !teamParam && !compareParam && !gameParam && !champParam && !viewParam && !coachParam && !sectionParam) {
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
    `<p><a href="/teams">Browse all teams</a> · <a href="/">Hoopsipedia home</a></p></div>`,
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
      { name: 'Coaches', url: `${origin}/coaches` },
      { name: coach.name, url: canonicalUrl },
    ]));

    ssrHtml = renderCoachSsr(coach, rank, accolades, teams, coaches, coachLb, origin);
  } else if (teamParam && seasonParam) {
    // /teams/{slug}/{season} — self-contained season page
    const team = lookupTeam(teamParam, teams, index);
    if (!team) return notFound();
    const seasons = await getTeamSeasons(assetFetcher, originUrl, team.espnId);
    let seasonRow = seasons ? seasons.find(s => s.year === seasonParam) : null;
    // Seasons the record book omits (NCAA-vacated years such as Michigan
    // 1991-92) have no summary row but do have logged games. Synthesize the
    // row from the game log so the page exists — vacated-games policy is to
    // show the history with an asterisk, not to hide it. Only a season with
    // a real log qualifies; anything else stays a hard 404.
    let synthesizedRow = false;
    if (!seasonRow && /^\d{4}-\d{2}$/.test(seasonParam)) {
      const logged = await getTeamGames(assetFetcher, originUrl, team.espnId);
      const inSeason = logged ? gamesForSeason(logged, seasonParam) : [];
      if (inSeason.length >= 8) {
        const wins = inSeason.filter(g => g.w).length;
        seasonRow = { year: seasonParam, wins, losses: inSeason.length - wins, record: `${wins}-${inSeason.length - wins}`, conf: team.conf };
        seasonRow.synthesized = true;
        synthesizedRow = true;
      }
    }
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
      { name: 'Teams', url: `${origin}/teams` },
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
    if (seasonGames.length < 8) {
      metaTags.push({ key: 'robots', value: 'noindex, follow' });
    }
    ssrHtml = renderSeasonSsr(team, seasonRow, seasonGames, teams, origin, slugIdx, recaps, seasons);
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
      { name: 'Teams', url: `${origin}/teams` },
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
      { name: 'Championship Journeys', url: `${origin}/champions` },
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
  } else if (sectionParam) {
    let description = '';
    let imageUrl = LOGO_IMAGE;
    const crumbs = [{ name: 'Hoopsipedia', url: `${origin}/` }];

    if (sectionParam === 'rivalry') {
      const rivalries = await getJsonCached(assetFetcher, originUrl, '/rivalries.json');
      const r = Array.isArray(rivalries) ? rivalries.find(x => x.slug === rivalrySlug) : null;
      if (!r || !teams[r.team1Id] || !teams[r.team2Id]) return notFound();
      const h2h = await getJsonCached(assetFetcher, originUrl, '/h2h.json');
      const t1 = teams[r.team1Id], t2 = teams[r.team2Id];
      canonicalUrl = `${origin}/rivalries/${encodeURIComponent(r.slug)}`;
      pageTitle = `${r.name}: ${t1[F.NAME]} vs ${t2[F.NAME]} — Rivalry History — Hoopsipedia`;
      const series = rivalrySeries(r, h2h, teams);
      description = `${series ? series + '. ' : ''}${r.description || ''}`.slice(0, 300);
      imageUrl = `https://a.espncdn.com/i/teamlogos/ncaa/500/${r.team1Id}.png`;
      ssrHtml = renderRivalrySsr(r, h2h, teams, origin);
      crumbs.push({ name: 'Rivalries', url: `${origin}/rivalries` }, { name: r.name, url: canonicalUrl });
    } else if (sectionParam === 'time-machine-matchup') {
      const [, slugA, seasonA, slugB, seasonB] = tmRoute;
      const teamA = lookupTeam(slugA, teams, index);
      const teamB = lookupTeam(slugB, teams, index);
      if (!teamA || !teamB) return notFound();
      const [rowsA, rowsB] = await Promise.all([
        getTeamSeasons(assetFetcher, originUrl, teamA.espnId),
        getTeamSeasons(assetFetcher, originUrl, teamB.espnId),
      ]);
      const rowA = (rowsA || []).find(r => String(r.year) === seasonA);
      const rowB = (rowsB || []).find(r => String(r.year) === seasonB);
      if (!rowA || !rowB) return notFound();
      canonicalUrl = `${origin}/time-machine/${slugA}/${seasonA}/${slugB}/${seasonB}`;
      pageTitle = `${seasonEndYear(seasonA)} ${teamA.name} vs ${seasonEndYear(seasonB)} ${teamB.name} — Time Machine — Hoopsipedia`;
      description = `Who wins if ${seasonEndYear(seasonA)} ${teamA.name} (${rowA.wins}-${rowA.losses}) plays ${seasonEndYear(seasonB)} ${teamB.name} (${rowB.wins}-${rowB.losses})? Cross-era simulation from adjusted efficiency and HTSS, with predicted score and win probability.`;
      imageUrl = `https://a.espncdn.com/i/teamlogos/ncaa/500/${teamA.espnId}.png`;
      ssrHtml = renderTimeMachineMatchupSsr(teamA, seasonA, rowA, teamB, seasonB, rowB, origin);
      crumbs.push({ name: 'Time Machine', url: `${origin}/time-machine` }, { name: pageTitle.replace(/ — .*$/, ''), url: canonicalUrl });
    } else {
      const meta = SECTION_META[sectionParam];
      if (!meta) return context.next();
      canonicalUrl = `${origin}/${sectionParam}`;
      pageTitle = meta.title;
      description = meta.description;
      if (sectionParam === 'teams') {
        ssrHtml = renderTeamsDirectorySsr(teams, origin);
      } else if (sectionParam === 'rankings') {
        const htss = await getJsonCached(assetFetcher, originUrl, '/htss_v2_results.json');
        ssrHtml = renderRankingsSsr(teams, htss, origin);
      } else if (sectionParam === 'time-machine') {
        const tm = await getJsonCached(assetFetcher, originUrl, '/time_machine_results.json');
        ssrHtml = renderTimeMachineSsr(tm, origin);
      } else if (sectionParam === 'players') {
        const players = await getJsonCached(assetFetcher, originUrl, '/players/index.json');
        ssrHtml = players ? renderPlayersSsr(players, teams, origin) : '';
      } else if (sectionParam === 'rivalries') {
        const [rivalries, h2h] = await Promise.all([
          getJsonCached(assetFetcher, originUrl, '/rivalries.json'),
          getJsonCached(assetFetcher, originUrl, '/h2h.json'),
        ]);
        ssrHtml = renderRivalriesSsr(Array.isArray(rivalries) ? rivalries : [], h2h, teams, origin);
      } else if (sectionParam === 'coaches') {
        ssrHtml = renderCoachesSsr(coachLb, teams, origin);
      } else if (sectionParam === 'champions') {
        ssrHtml = renderChampionsSsr(teams, origin);
      } else {
        ssrHtml = renderSectionIntroSsr(sectionParam, origin);
      }
      crumbs.push({ name: pageTitle.replace(/ [—|].*$/, ''), url: canonicalUrl });
    }

    jsonLdBlocks.push(breadcrumbLd(crumbs));
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
      { name: 'Greatest Upsets', url: `${origin}/upsets` },
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
