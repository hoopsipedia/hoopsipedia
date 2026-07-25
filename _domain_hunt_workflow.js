export const meta = {
  name: 'boxscore-domain-hunt',
  description: 'Sonnet hunters find historical athletics domains for 365 programs; Python CDX-probes 4 StatCrew URL patterns afterward (free)',
  phases: [{ title: 'Hunt', detail: '16 Sonnet hunters, ~23 programs each, domains only', model: 'sonnet' }],
}

const DOMAIN_SCHEMA = {
  type: 'object',
  properties: {
    programs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          program: { type: 'string' },
          current_domain: { type: 'string', description: 'current official athletics site host, no scheme (e.g. gohighlanders.com)' },
          historical_domains: {
            type: 'array',
            description: 'all distinct athletics-site hosts used ~1996-2012, no scheme; INCLUDE fansonly.com subdomains (e.g. uncbears.fansonly.com), old cstv/collegesports hosts, prior rebrands, and static.* CDN mirrors of any of these',
            items: { type: 'string' },
          },
          stats_path_hint: { type: 'string', description: 'if seen in Wayback, the URL path prefix where per-game box HTML lived, e.g. /sports/m-baskbl/stats/ or /bko/bkc/ or /custompages/.../ — else empty' },
        },
        required: ['program', 'current_domain', 'historical_domains'],
      },
    },
    programs_checked: { type: 'integer' },
  },
  required: ['programs', 'programs_checked'],
}

const batches = typeof args === 'string' ? JSON.parse(args) : args
phase('Hunt')
log(`16 domain hunters covering ${batches.flat().length} programs`)

const results = await pipeline(
  batches,
  (programs, _x, i) => agent(`You are a college-athletics web historian. For each program below, find EVERY distinct official-athletics-website hostname it used from roughly 1996 to 2012. I do NOT need box scores — only the DOMAINS. A free downstream job will probe the Wayback Machine for box-score archives on the domains you return, so completeness of the domain list is what matters.

WHAT TO RETURN PER PROGRAM:
- current_domain: today's official athletics host (no https://, no path). e.g. "gohighlanders.com"
- historical_domains: every OTHER athletics host the program used ~1996-2012. This is the valuable part. Sources of these:
  * FansOnly / CSTV era subdomains: "{nick}.fansonly.com" and "{nick}.collegesports.com" (e.g. uncbears.fansonly.com, goviks.fansonly.com). Very common 1999-2005.
  * Old standalone domains later abandoned or redirected (e.g. a school that moved from "catamounts.com" to "catamountsports.com").
  * "static.{currentdomain}" CDN mirror hosts (sidearm/Wayback often archived box HTML there).
  * cstv.com / grfx.cstv.com "/schools/{code}/" hosts — give the {code} host form if you can find it.
- stats_path_hint: if while checking Wayback you notice the URL path where per-game box scores lived (e.g. /sports/m-baskbl/stats/, /bko/bkc/, /custompages/stats/mbasketball/, /mbasketball/{year}boxes/), report it; else "".

HOW TO FIND THEM (fast, ~2-4 web ops per program):
- Web-search: "{school} basketball" + "fansonly.com", and "{school} athletics" site history / old website.
- Wayback CDX to confirm a host was archived and see paths:
    curl -s "http://web.archive.org/cdx/search/cdx?url={candidate-host}/*&collapse=urlkey&limit=20&fl=original&filter=statuscode:200"
  A non-empty result means the host is real and archived — good enough to include it.
- The current domain is easy (search "{school} athletics site:.com").

RULES: Prefer INCLUSION — if a host plausibly belonged to this program and CDX shows it was archived, include it. Do NOT include third-party hosts (espn, sports-reference, ncaa, cbssports content pages). Move fast; this is breadth work, not deep verification. Return one entry per program (all ${programs.length}).

Programs: ${programs.join(' | ')}

Return via StructuredOutput: programs (one per input program), programs_checked.`, { schema: DOMAIN_SCHEMA, label: `domainhunt:${i}`, phase: 'Hunt', model: 'sonnet' })
)

const ok = results.filter(Boolean)
const progs = ok.flatMap(r => r.programs || [])
const allHosts = new Set()
for (const p of progs) {
  if (p.current_domain) allHosts.add(p.current_domain)
  for (const h of (p.historical_domains || [])) allHosts.add(h)
}
log(`${progs.length} programs mapped, ${allHosts.size} distinct hosts collected`)
return { hunters: ok.length, programs: progs, hostCount: allHosts.size }
