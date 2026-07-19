export const meta = {
  name: 'team-boxscore-missing-pages',
  description: 'Per-page Sonnet extraction of ONLY the not-yet-extracted PDF pages for one program',
  phases: [{ title: 'Extract', detail: 'one Sonnet reader per missing PDF page', model: 'sonnet' }],
}

const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    page_label: { type: 'string' },
    games_extracted: { type: 'integer' },
    games_skipped: { type: 'integer' },
    output_path: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['page_label', 'games_extracted', 'games_skipped', 'output_path', 'notes'],
}

// args: { school, teamName, pdfDir, outDir, units: [{season, missing: [pageNums]}] }
// outDir MUST be durable (archives/<school>/extracted_pages) — tmp scratchpads get wiped.
const cfg = typeof args === 'string' ? JSON.parse(args) : args
const units = []
for (const s of cfg.units) {
  for (const p of s.missing) units.push({ season: s.season, page: p })
}

phase('Extract')
log(`${cfg.teamName}: ${units.length} missing-page readers across ${cfg.units.length} seasons`)

const results = await pipeline(
  units,
  (u) => {
    const threeEra = u.season >= '1986-87'
    return agent(`Read EXACTLY ONE page of a scanned ${cfg.teamName} basketball box-score compilation PDF: ${cfg.pdfDir}/${u.season}_boxscores.pdf — use the Read tool with pages: "${u.page}" (only this page; do not read any other pages).

This is the ${u.season} ${cfg.teamName} season. A page typically holds ONE game's box score (typed or handwritten official scoresheet; sometimes a title/cover/summary/season-stats page instead — if no game box score is on the page, write an empty games list and say so in notes; if the page holds MORE than one game, transcribe each). For each game transcribe: date (YYYY-MM-DD), opponent, final scores, and BOTH teams' player lines (keys: name, min, fg "made-attempted", ft "made-attempted"${threeEra ? ', tp "made-attempted" (3-pointers)' : ''}, reb, ast, pf, to, stl, blk, pts — omit columns the sheet lacks; never invent values).${threeEra ? '' : ' This season predates the 3-point line; there is no tp column.'} If the sheet has no per-player points column but shows made field goals and made free throws, you may compute pts = 2*fg_made + ft_made (valid in the pre-3-point era) — note it when you do.

CHECKSUM each team (player pts sum == that team's final score). You may re-read the page AT MOST once total. Any game that fails checksum or is too blurry/illegible to transcribe confidently goes in skipped with a reason — be ruthless about skipping rather than guessing.

Write JSON with the Write tool to ${cfg.outDir}/${u.season}_p${u.page}.json:
{"page": ${u.page}, "games": [{"date","opponent","teams":[{"name":"${cfg.teamName}","score":N,"players":[...]},{"name":"<opp>","score":N,"players":[...]}],"checksum_ok":true}], "skipped": [{"reason":"..."}]}

Return via StructuredOutput only: page_label "${u.season} p${u.page}", games_extracted, games_skipped, output_path, notes.`, { schema: RESULT_SCHEMA, label: `${u.season}:p${u.page}`, phase: 'Extract', model: 'sonnet' })
  }
)

const ok = results.filter(Boolean)
const total = ok.reduce((s, r) => s + (r.games_extracted || 0), 0)
const skipped = ok.reduce((s, r) => s + (r.games_skipped || 0), 0)
log(`${cfg.teamName} done: ${total} games, ${skipped} skipped across ${ok.length}/${units.length} pages`)
return { school: cfg.school, pages: ok.length, of: units.length, games: total, skipped }
