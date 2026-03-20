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

async function getTeamData(assetFetcher, originUrl) {
  if (cachedTeamData && slugIndex) return { teams: cachedTeamData, index: slugIndex };

  const dataUrl = new URL('/data.json', originUrl).toString();
  const resp = await assetFetcher.fetch(dataUrl);
  if (!resp.ok) return null;

  const data = await resp.json();
  cachedTeamData = data.H;

  // Build slug-to-espnId index for fast lookups
  slugIndex = {};
  for (const [espnId, fields] of Object.entries(cachedTeamData)) {
    const slug = teamSlug(fields[F.NAME]);
    slugIndex[slug] = espnId;
  }

  return { teams: cachedTeamData, index: slugIndex };
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
    champYears: t[F.NCY],
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

// HTMLRewriter handler that injects new meta tags before </head>
class HeadInjector {
  constructor(metaTags, titleText) {
    this.metaTags = metaTags;
    this.titleText = titleText;
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

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const teamParam = url.searchParams.get('team');
  const compareParam = url.searchParams.get('compare');
  const gameParam = url.searchParams.get('game');
  const champParam = url.searchParams.get('championship');
  const viewParam = url.searchParams.get('view');

  // No relevant query params — passthrough to static files
  if (!teamParam && !compareParam && !gameParam && !champParam && !viewParam) {
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

  const { teams, index } = teamDataResult;
  let metaTags = [];
  let pageTitle = '';
  const canonicalUrl = url.toString();

  if (teamParam) {
    const team = lookupTeam(teamParam, teams, index);
    if (!team) return context.next();

    const ncText = team.natlChamps > 0
      ? `${team.natlChamps} National Championship${team.natlChamps > 1 ? 's' : ''}`
      : 'No National Championships';

    pageTitle = `${team.name} — Hoopsipedia`;
    const description = `${team.allTimeW}-${team.allTimeL} all-time | ${ncText} | ${team.conf}`;
    const imageUrl = `https://a.espncdn.com/i/teamlogos/ncaa/500/${team.espnId}.png`;

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
  } else if (compareParam) {
    const parts = compareParam.split('/');
    if (parts.length !== 2) return context.next();

    const team1 = lookupTeam(parts[0], teams, index);
    const team2 = lookupTeam(parts[1], teams, index);
    if (!team1 || !team2) return context.next();

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
    pageTitle = `${teamName} — ${year} National Champions | Hoopsipedia`;
    const description = `Relive ${teamName}'s ${year} championship run. Full tournament path, box scores, highlights, and the story of how they cut down the nets.`;
    const imageUrl = team
      ? `https://a.espncdn.com/i/teamlogos/ncaa/500/${team.espnId}.png`
      : `https://www.hoopsipedia.com/branding/hoopsipedia-logo.png`;

    metaTags = [
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
    // ?view=upsets, ?view=classics, ?view=champions
    const viewMeta = {
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

    pageTitle = vm.title;
    const description = vm.description;
    const imageUrl = vm.image;

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

    pageTitle = classic
      ? classic.title
      : `${winnerName} Upsets ${loserName} — ${year} NCAA Tournament | Hoopsipedia`;
    const description = classic
      ? classic.desc
      : `Relive the Moment: ${winnerName} defeats ${loserName} in the ${year} NCAA Tournament. Box score, highlights, and why this upset mattered.`;
    const imageUrl = winner
      ? `https://a.espncdn.com/i/teamlogos/ncaa/500/${winner.espnId}.png`
      : `https://www.hoopsipedia.com/branding/hoopsipedia-logo.png`;

    metaTags = [
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
  }

  // Set of tags to remove from existing HTML
  const tagsToRemove = new Set(metaTags.map(t => t.key));

  // Use HTMLRewriter to stream-replace meta tags
  const rewritten = new HTMLRewriter()
    .on('meta', new MetaTagRemover(tagsToRemove))
    .on('title', new TitleRewriter(pageTitle))
    .on('head', new HeadInjector(metaTags, pageTitle))
    .transform(originResp);

  // Return with appropriate headers
  const response = new Response(rewritten.body, rewritten);
  response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');
  return response;
}
