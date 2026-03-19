# Quick Start Guide - College Basketball Scraper

## What Was Created

Four main tools to compile 362 D1 teams' historical basketball season data from Sports Reference:

1. **`compile_history.py`** - Main scraper (requires running)
2. **`generate_slug_mapping.py`** - Utility to generate/verify slug mapping
3. **`test_scraper.py`** - Test suite to validate setup
4. **`slug_mapping.json`** - Pre-generated ESPN ID → Sports Reference slug mapping
5. **`SCRAPER_SETUP.md`** - Detailed documentation

## Quickest Start (3 steps)

### Step 1: Test Your Setup
```bash
cd "/Sessions/affectionate-ecstatic-cori/mnt/Claude Personal/hoopsipedia-pages"
python3 test_scraper.py
```

This validates:
- Slug mapping integrity
- Can reach Sports Reference
- Output structure is ready

### Step 2: Run the Scraper
```bash
python3 compile_history.py
```

The scraper will:
- Fetch data for all 362 teams
- Save progress every 10 teams (safe to interrupt)
- Print detailed progress
- Generate `seasons.json`

**Estimated time:** 25-35 minutes (rate limited to 20 requests/min)

### Step 3: Verify Output
```bash
# Quick validation
python3 -c "import json; data = json.load(open('seasons.json')); print(f'✓ Generated {len(data)} teams')"

# Or use the test suite
python3 test_scraper.py structure
```

## If Something Goes Wrong

### Scraper was interrupted?
Just run `python3 compile_history.py` again - it continues from where it left off.

### Need to test a specific team?
```bash
python3 test_scraper.py fetch 96    # Test Kentucky (ESPN ID 96)
python3 test_scraper.py fetch 97    # Test Louisville (ESPN ID 97)
```

### Slug mapping seems wrong for a team?
1. Edit `slug_mapping.json` with correct slug
2. Run compiler again - it will reprocess that team
3. Or regenerate entire mapping: `python3 generate_slug_mapping.py`

## File Locations

All files in: `/sessions/affectionate-ecstatic-cori/mnt/Claude Personal/hoopsipedia-pages/`

- **Input:** `data.json`, `slug_mapping.json`
- **Output:** `seasons.json` (generated)
- **Scripts:** `compile_history.py`, `generate_slug_mapping.py`, `test_scraper.py`
- **Docs:** `SCRAPER_SETUP.md` (detailed), `QUICK_START.md` (this file)

## Output Format Example

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
  }
}
```

## Key Features

✓ **Rate limiting** - Respects Sports Reference limits (20 req/min)
✓ **Resumable** - Crashes? Just run again, picks up where it left off
✓ **Progress tracking** - Saves every 10 teams
✓ **Comprehensive** - Goes back to earliest available season
✓ **Flexible** - Easy to update slug mappings if needed
✓ **Testable** - Built-in validation and test suite

## For More Details

See `SCRAPER_SETUP.md` for:
- Detailed field descriptions
- Troubleshooting guide
- Manual slug corrections
- Integration instructions

---

**TL;DR:** Run `test_scraper.py` to verify setup, then `compile_history.py` to generate `seasons.json`
