// Cloudflare Pages Function — Time Machine verdict writer.
// POST /api/tm-verdict  { matchup } -> { verdict }
// Writes a fresh 2-3 sentence basketball verdict for a simulated
// cross-era matchup. Haiku-priced, rate-limited, with a graceful
// client-side template fallback if anything fails.

const rateLimits = new Map();
const RATE_LIMIT = 30;
const RATE_WINDOW = 5 * 60 * 1000;

function checkRateLimit(ip) {
  const now = Date.now();
  if (rateLimits.size > 1000) {
    for (const [k, v] of rateLimits) if (now > v.resetAt) rateLimits.delete(k);
  }
  const e = rateLimits.get(ip);
  if (!e || now > e.resetAt) {
    rateLimits.set(ip, { count: 1, resetAt: now + RATE_WINDOW });
    return true;
  }
  if (e.count >= RATE_LIMIT) return false;
  e.count++;
  return true;
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const ip = request.headers.get('cf-connecting-ip') || 'local';
  if (!checkRateLimit(ip)) {
    return new Response(JSON.stringify({ error: 'rate_limited' }), { status: 429 });
  }

  let m;
  try {
    const body = await request.json();
    m = body && body.matchup;
  } catch (e) { /* fall through */ }
  if (!m || !m.teamA || !m.teamB || !m.prediction) {
    return new Response(JSON.stringify({ error: 'bad_request' }), { status: 400 });
  }

  const p = m.prediction;
  const factLines = (m.factors || [])
    .map(f => `- ${f.name}: ${m.teamA.name} ${f.teamA} vs ${m.teamB.name} ${f.teamB} (edge: ${f.edge})`)
    .join('\n');

  const prompt = `You are a sharp college basketball writer settling a cross-era barroom debate. A neutral-court simulation produced this result:

${m.matchup}
Final: ${p.winner} wins ${p.winnerScore}-${p.loserScore} (win probability ${Math.max(p.winProbA, p.winProbB)}%, ${p.simPossessions} possessions)

Team A: ${m.teamA.season} ${m.teamA.name} — ${m.teamA.record}, coached by ${m.teamA.coach || 'unknown'}${m.teamA.htss ? `, HTSS ${m.teamA.htss}` : ''}
Team B: ${m.teamB.season} ${m.teamB.name} — ${m.teamB.record}, coached by ${m.teamB.coach || 'unknown'}${m.teamB.htss ? `, HTSS ${m.teamB.htss}` : ''}

Matchup factors:
${factLines || '(none provided)'}

Write the VERDICT: 2-3 sentences explaining how this game plays out and why the winner wins. Requirements:
- Ground every claim in the data above (never invent stats, players, or events)
- Reference the era contrast when the seasons are far apart (style of play, pace)
- Vary your structure — do NOT open with the score or the phrase "This one"
- Concrete and vivid, but no purple prose, no exclamation points, no clichés like "instant classic" or "goes down to the wire"
Respond with ONLY the verdict text.`;

  try {
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 220,
        temperature: 0.9,
        messages: [{ role: 'user', content: prompt }],
      }),
    });
    if (!resp.ok) {
      return new Response(JSON.stringify({ error: 'upstream', status: resp.status }), { status: 502 });
    }
    const data = await resp.json();
    const verdict = (data.content && data.content[0] && data.content[0].text || '').trim();
    return new Response(JSON.stringify({ verdict }), {
      headers: { 'content-type': 'application/json' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'exception' }), { status: 500 });
  }
}
