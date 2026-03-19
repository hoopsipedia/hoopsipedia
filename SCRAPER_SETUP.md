# College Basketball Historical Data Scraper

This directory contains tools to compile comprehensive historical college basketball season-by-season data from Sports Reference for all ~362 D1 teams.

## Files

### Main Scripts
- **`compile_history.py`** - Main scraper script that fetches and parses data from Sports Reference
- **`generate_slug_mapping.py`** - Utility to generate/update the ESPN-to-slug mapping from data.json
- **`slug_mapping.json`** - Mapping file of ESPN IDs to Sports Reference URL slugs
- **`seasons.json`** - Output file containing all compiled historical season data (generated)

## Setup

### 1. Install Dependencies
```bash
pip install requests beautifulsoup4 --break-system-packages
```

### 2. Verify/Update Slug Mapping
The `slug_mapping.json` file contains mappings from ESPN team IDs to Sports Reference URL slugs. The initial mapping is pre-generated, but you can regenerate it from data.json:

```bash
python3 generate_slug_mapping.py
```

This will:
- Read team names from `data.json`
- Generate Sports Reference slug format from team names
- Save updated mapping to `slug_mapping.json`
- Report any potential conflicts

### 3. Run the Compiler
```bash
python3 compile_history.py
```

The script will:
1. Load the slug mapping
2. Load any existing seasons.json to resume if interrupted
3. For each team:
   - Fetch the Sports Reference page (with rate limiting)
   - Parse the season table
   - Extract: year, overall W-L, conference W-L, coach, postseason result, AP rank
4. Save progress incrementally every 10 teams
5. Generate final `seasons.json`

### Rate Limiting
- Respects Sports Reference's 20 requests/minute limit
- Enforces minimum 3-second delay between requests
- Can safely be interrupted and resumed

### Resume Interrupted Runs
If the script is interrupted (network error, rate limiting, etc.), simply run it again:
```bash
python3 compile_history.py
```

It will:
- Load existing `seasons.json`
- Skip teams already processed
- Continue from where it left off
- Show progress as [current/total]

## Output Format

The generated `seasons.json` follows this structure:

```json
{
  "96": {
    "seasons": [
      {
        "year": "2024-25",
        "record": "21-13",
        "confRecord": "10-8",
        "coach": "Mark Pope",
        "postseason": "Elite Eight",
        "apRank": 8
      },
      {
        "year": "2023-24",
        "record": "34-3",
        "confRecord": "15-3",
        "coach": "John Calipari",
        "postseason": "Elite Eight",
        "apRank": 2
      }
    ]
  },
  "97": {
    "seasons": [
      ...
    ]
  }
}
```

## Data Fields

Each season object contains:
- **year**: Season year (e.g., "2024-25")
- **record**: Overall win-loss record (e.g., "21-13")
- **confRecord**: Conference record (e.g., "10-8") - may be null if unavailable
- **coach**: Head coach name - may be null if unavailable
- **postseason**: Postseason result (e.g., "NCAA Round of 32", "NIT First Round") - null if none
- **apRank**: AP Top 25 ranking at end of season - null if unranked

## Slug Mapping Format

The `slug_mapping.json` maps ESPN IDs to Sports Reference URL slugs:

```json
{
  "96": "kentucky",
  "97": "louisville",
  "98": "south-carolina",
  "99": "tennessee"
}
```

Sports Reference URLs follow the pattern:
```
https://www.sports-reference.com/cbb/schools/{slug}/men/
```

### Common Slug Patterns
- Single word: `kentucky`, `michigan`, `duke`
- Multi-word: `north-carolina`, `michigan-state`, `texas-christian`
- Special characters removed: `saint-louis` (not `st-louis`)

## Handling Failures

If certain teams fail to scrape:
1. The script logs failures and continues
2. Check if the team exists at the expected URL
3. Manually verify the slug mapping for that team
4. Update `slug_mapping.json` with the correct slug
5. Re-run the script to retry failed teams

## Manual Slug Corrections

If you know a specific team has the wrong slug, you can edit `slug_mapping.json`:

```json
{
  "96": "kentucky",
  "123": "your-correct-slug-here"
}
```

Then run the compiler again - it will reprocess that team.

## Monitoring Progress

The script prints:
- `[1/361] ESPN ID 96` - Progress counter
- `Fetching: https://...` - Current URL
- `Found X seasons` - Successful parse
- `Error fetching...` - Network/timeout error
- `No seasons table found` - Team has no Sports Reference page
- `Error parsing...` - HTML parsing issue

### Progress File
Progress is automatically saved to `seasons.json` every 10 teams, allowing safe resumption.

## Troubleshooting

### "No seasons table found"
- Team may not have a Sports Reference page
- Verify the slug is correct at sports-reference.com
- Check if team name changed or school merged

### "Error fetching: Connection timeout"
- Sports Reference may be rate limiting
- Script automatically backs off with longer sleep intervals
- Try running again later

### Missing data fields
- Different teams have different data available on Sports Reference
- Some older seasons may lack coach or AP ranking data
- Script gracefully handles missing fields (sets to null)

### Slug mapping conflicts
- If two teams generate the same slug, `generate_slug_mapping.py` will report this
- Manual intervention required - update `slug_mapping.json` with corrections

## Integration with Hoopsipedia

Once generated, `seasons.json` can be loaded by the Hoopsipedia web app:

```javascript
const seasonsData = require('./seasons.json');
const teamSeasons = seasonsData['96'];  // Kentucky
console.log(teamSeasons.seasons[0]);    // Most recent season
```

The format is optimized for web consumption with minimal overhead.
