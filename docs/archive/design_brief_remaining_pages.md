> ARCHIVED 2026-06: superseded — see README.md and docs/. Kept for history.

# Design Brief: Hoopsipedia — 4 Remaining Pages

**Vintage Collegiate Design System (Cream + Navy)**

**Design system reference:** See the live Homepage, Rankings, and Bracket pages at hoopsipedia.com for the established patterns. The full token set is in `/tmp/hoopsipedia-handover/design_handoff_hoopsipedia_redesign/styles.css`.

**Tokens already in use:**
- Palette: `--cream` / `--navy` / `--rust` / `--gold-brand` / `--moss` / `--ink-*`
- Type: Stint Ultra Condensed (display/headers), Roboto Slab (data/names), DM Sans (body), JetBrains Mono (labels/badges), Lobster (wordmark)
- Patterns: 3px navy bottom-border on section headers, mono uppercase labels, serif tabular numerals for stats, pill badges (navy/rust/gold/moss)

---

## 1. Coaches Page

**Current state:** Leaderboard table + coach compare widget at top. Functional but unstyled beyond basic tokens on the table headers.

**Components to design:**
- **Coach compare widget** — two search inputs + "Compare →" button (same pattern as homepage compare, but for coaches)
- **Leaderboard table** — 100 rows. Columns: rank, name, record (W-L), win%, schools list, years active, best season. Currently plain rows — needs the newspaper box-score feel
- **Active coach badge** — small "ACTIVE" pill next to currently coaching names
- **Coach rank badge** — "#6 All-Time" clickable pill on team profile coach sections (already exists, needs token pass)
- **Responsive:** Table collapses — which columns hide at 768px?

**Design questions:**
- Should the leaderboard have alternating row shading or stay clean with just bottom rules?
- Any special treatment for the top 10 (like the HTSS tier badges: GOAT / Elite / etc.)?
- Should the compare widget be a card above the table or integrated into a split layout?

---

## 2. Upsets Page

**Current state:** Most complex remaining page (~35 unique components). Has a stats dashboard, seed-pairing grid, era filter pills, sort toggles, individual upset moment cards with team logos, and a "fun fact" callout.

**Components to design:**
- **Stats dashboard** — 4 stat cards in a row (343 upsets, most upset-prone pairing, rarest upset, overall rate). Big display numerals + mono labels
- **"Did You Know?" callout** — gold accent icon, full-width banner with fun fact text + inline links
- **View toggle** — "By Seed Pairing" vs "By Team" (pill-style switcher)
- **Era filter pills** — "All Eras", "64-Team Era (1985-2010)", "68-Team Era (2011+)", "3-Point Era (1987+)", "NIL Era (2021+)"
- **Seed pairing grid** — 8 cards (1v16, 2v15, ... 8v9). Each shows: matchup label, W-L record, upset progress bar, upset count + rate. Cards are clickable — active state needs highlight
- **Upset detail section** — section header ("1 vs 16 Upsets (2)") + sort buttons ("Newest" / "Magnitude")
- **Upset moment card** — year (big display numeral), two team rows (logo + seed badge + name), score, "SHOCK" magnitude bar (coming soon), play button icon. Winner row is emphasized, loser row is muted
- **Team leaderboard tables** (in "By Team" view) — two side-by-side tables for "Most Upsets Pulled" and "Most Times Upset"
- **Responsive:** Seed grid goes 2-col, stat cards go 2x2 at mobile

**Design questions:**
- The upset moment cards have a left border accent (like a timeline) — keep this or rethink?
- The "SHOCK" magnitude bar is a future feature — placeholder treatment?
- Should the seed pairing cards use color coding to indicate upset frequency (green = rare, red = common)?

---

## 3. Championship Runs Page

**Current state:** Rich single-page experience for each champion. Has a team-colored hero banner, narrative story card, and a vertical tournament path timeline with expandable box scores.

**Components to design:**
- **Hero banner** — full-width, team-primary-color gradient background. Shows: team logo (large), "2024 NATIONAL CHAMPIONS" eyebrow, team name (huge display), seed/region/venue info, "Share This Run" button. Currently uses team color dynamically
- **"The Story" card** — narrative paragraph, serif italic text. How does this integrate with the cream paper aesthetic?
- **Tournament Path timeline** — vertical timeline with round labels (ROUND OF 64, ROUND OF 32, SWEET 16, ELITE EIGHT, FINAL FOUR, CHAMPIONSHIP). Each game shows: opponent logo, name, seed, score (W +margin). Championship game has special gold accent treatment
- **Expandable box scores** — click a game to expand and see per-player stats table (coming soon placeholder)
- **"← Back" navigation** — top-left back link
- **Stats card** — season summary stats (if added later)
- **Responsive:** Hero stacks vertically, timeline goes full-width

**Design questions:**
- The hero uses each team's primary color dynamically — how does this coexist with the cream+navy system? (Currently it's the one section that breaks the design system intentionally)
- Should the championship game in the timeline get a gold/trophy treatment distinct from other rounds?
- The "Share This Run" button — ghost style or filled?

---

## 4. Classics (Tournament History on Team Profile)

**Current state:** Grid of tournament appearances shown on each team's profile page. Small entry cards with year, seed, and round-result badge (color-coded: gold=champion, silver=runner-up, bronze=Final Four, blue=Elite 8, light=early rounds).

**Components to design:**
- **Tournament resume header** — "Tournament Resume" section with summary stats (appearances, championships, Final Fours, record)
- **Summary stat row** — display numerals for key counts
- **Tournament grid** — dense grid of year entries, each showing year + seed + round badge. Badges are color-coded by finish depth
- **Round badges** — Champion (gold gradient), Runner-Up (silver), Final Four (bronze), Elite 8 (navy-soft), Sweet 16 (blue), Early rounds (cream-deep). These need to map to design tokens
- **Championship year links** — clickable years that navigate to the Championship Run page

**Design questions:**
- Keep the dense grid layout or switch to a table/list for better readability?
- Badge color system: map to existing tokens (`--gold` for champion, `--navy` for deep runs, `--cream-deep` for early exits) or introduce new tournament-specific accents?

---

## General Notes

- All pages share the same Masthead nav and Footer (already designed and implemented)
- ESPN CDN team logos are used everywhere: `https://a.espncdn.com/i/teamlogos/ncaa/500/{id}.png`
- Mobile breakpoint is 768px
- Deliverable: Figma frames or annotated comps with specific token references. No need to spec the Masthead/Footer — just the page content area.
