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
  let canonicalUrl = url.toString();
  // Pin the canonical host: the site answers on both apex and www with no
  // redirect, and split canonicals dilute SEO signal. www matches branding
  // URLs and sitemap.xml — keep all three in lockstep.
  const origin = 'https://www.hoopsipedia.com';
  const jsonLdBlocks = []; // schema.org objects to inject as <script type="application/ld+json">
  let noscriptHtml = '';   // crawler-visible summary, prepended inside <body> within <noscript>

  if (teamParam) {
    const team = lookupTeam(teamParam, teams, index);
    if (!team) return context.next();

    canonicalUrl = `${origin}/?team=${encodeParam(teamParam)}`;

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

    // Crawler-visible summary. Served inside <noscript> so the client SPA
    // (which renders the same data into #app) never double-renders it.
    // Google indexes <noscript> content; trade-off documented in repo notes —
    // upgrade to a visible SSR block once index.html can flag app init.
    noscriptHtml = [
      '<noscript data-ssr="true">',
      '<section style="max-width:720px;margin:24px auto;padding:16px;font-family:Georgia,serif;line-height:1.5">',
      `<h1>${escapeHtml(team.name)}</h1>`,
      `<p><strong>Conference:</strong> ${escapeHtml(team.conf)}</p>`,
      `<p><strong>All-time record:</strong> ${team.allTimeW}–${team.allTimeL}</p>`,
      `<p><strong>National championships:</strong> ${team.natlChamps > 0 ? `${team.natlChamps}${escapeHtml(champYearsText)}` : 'None'}</p>`,
      `<p><strong>Final Fours:</strong> ${team.finalFours}</p>`,
      `<p>Explore ${escapeHtml(team.name)} history, season-by-season results, and head-to-head comparisons on <a href="${origin}/">Hoopsipedia</a>, the college basketball historical database. This page is fully interactive with JavaScript enabled.</p>`,
      '</section>',
      '</noscript>',
    ].join('');
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
    .on('title', new TitleRewriter(pageTitle))
    .on('head', new HeadInjector(metaTags, pageTitle, extraHeadHtml));

  if (noscriptHtml) {
    rewriter = rewriter.on('body', new BodyPrepender(noscriptHtml));
  }

  const rewritten = rewriter.transform(originResp);

  // Return with appropriate headers
  const response = new Response(rewritten.body, rewritten);
  response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');
  return response;
}
