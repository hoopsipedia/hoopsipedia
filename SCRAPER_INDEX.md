# College Basketball Scraper - Complete File Index

## Quick Links

**Start here:** `QUICK_START.md` (3-step setup)
**Full details:** `SCRAPER_SETUP.md` (comprehensive guide)
**Overview:** `README_SCRAPER.md` (complete overview)

## Files Overview

### 📊 Data Files

| File | Size | Purpose |
|------|------|---------|
| `data.json` | 87 KB | Source team data (ESPN IDs + names) |
| `slug_mapping.json` | 12 KB | ESPN ID → Sports Reference slug mapping |
| `seasons.json` | Generated | Output file with all season data |

### 🔧 Main Scripts

| Script | Lines | Purpose | Run |
|--------|-------|---------|-----|
| `compile_history.py` | 299 | Main scraper - fetches & parses all team data | `python3 compile_history.py` |
| `test_scraper.py` | 261 | Test suite - validates setup & output | `python3 test_scraper.py` |
| `validate_setup.py` | 150 | Setup validator - checks all components | `python3 validate_setup.py` |

### 🛠️ Utility Scripts

| Script | Lines | Purpose | Run |
|--------|-------|---------|-----|
| `generate_slug_mapping.py` | 131 | Generate slugs from team names | `python3 generate_slug_mapping.py` |
| `check_references.py` | 233 | Debug individual teams | `python3 check_references.py` |

### 📚 Documentation

| File | Lines | Purpose |
|------|-------|---------|
| `QUICK_START.md` | 119 | 3-step quick start guide |
| `SCRAPER_SETUP.md` | 198 | Detailed technical setup & reference |
| `README_SCRAPER.md` | 263 | Complete overview & integration |
| `SCRAPER_INDEX.md` | This file | File directory & index |

## Command Reference

### Validate Everything is Ready
```bash
python3 validate_setup.py
```

### Run Tests
```bash
# All tests
python3 test_scraper.py

# Specific test
python3 test_scraper.py mapping      # Test slug mapping
python3 test_scraper.py fetch 96     # Test Kentucky
python3 test_scraper.py structure    # Test output format
```

### Run the Main Scraper
```bash
python3 compile_history.py
```

### Debug Tools
```bash
# Check all team URLs
python3 check_references.py all

# Check specific team
python3 check_references.py team 96

# Get slug suggestion
python3 check_references.py suggest "Team Name"
```

### Generate/Update Slug Mapping
```bash
python3 generate_slug_mapping.py
```

## File Locations

All files are in:
```
/sessions/affectionate-ecstatic-cori/mnt/Claude Personal/hoopsipedia-pages/
```

## Data Flow

```
data.json (team info)
    ↓
slug_mapping.json (ESPN ID → slug)
    ↓
compile_history.py (fetches & parses)
    ↓
seasons.json (output)
    ↓
Hoopsipedia web app
```

## Getting Started (3 Steps)

### Step 1: Validate Setup
```bash
python3 validate_setup.py
```
Expected: ✓ All checks pass

### Step 2: Test Components
```bash
python3 test_scraper.py
```
Expected: 3 tests pass (mapping, fetch, structure)

### Step 3: Run Scraper
```bash
python3 compile_history.py
```
Expected: All 362 teams compiled in 25-35 minutes

## Script Capabilities

### compile_history.py
- ✅ Fetches from Sports Reference
- ✅ Parses season tables
- ✅ Extracts 6 data fields
- ✅ Respects rate limits (3 sec/request)
- ✅ Saves progress every 10 teams
- ✅ Resumable if interrupted
- ✅ Graceful error handling

### test_scraper.py
- ✅ Validates slug mapping format
- ✅ Tests Sports Reference connectivity
- ✅ Validates output JSON structure
- ✅ Per-component testing
- ✅ Sample data verification

### validate_setup.py
- ✅ Checks all required files
- ✅ Validates Python syntax
- ✅ Tests JSON format
- ✅ Verifies dependencies
- ✅ Full status report

### check_references.py
- ✅ Tests individual team URLs
- ✅ Batch tests all teams
- ✅ Reports HTTP status codes
- ✅ Suggests slugs from team names
- ✅ Identifies 404 errors

### generate_slug_mapping.py
- ✅ Reads team names from data.json
- ✅ Generates slug format
- ✅ Detects conflicts
- ✅ Saves updated mapping
- ✅ Reports statistics

## Output Structure

Generated `seasons.json`:
```json
{
  "espn_id": {
    "seasons": [
      {
        "year": "2024-25",
        "record": "21-13",
        "confRecord": "10-8",
        "coach": "Mark Pope",
        "postseason": "Elite Eight",
        "apRank": 8
      }
    ]
  }
}
```

## Key Features

| Feature | Status |
|---------|--------|
| Rate limiting (20 req/min) | ✅ Implemented |
| Resumable (save every 10) | ✅ Implemented |
| Progress tracking | ✅ Implemented |
| Error handling | ✅ Implemented |
| Data validation | ✅ Implemented |
| Test suite | ✅ Included |
| Documentation | ✅ Complete |

## Troubleshooting

| Issue | Script | Command |
|-------|--------|---------|
| Setup incomplete | validate_setup.py | `python3 validate_setup.py` |
| Mapping issues | check_references.py | `python3 check_references.py team 96` |
| Test failures | test_scraper.py | `python3 test_scraper.py` |
| Parsing errors | compile_history.py | Check console output |
| Rate limiting | compile_history.py | Run again (auto-retry) |

## Performance Specs

| Metric | Value |
|--------|-------|
| Teams to process | 362 D1 schools |
| Estimated time | 25-35 minutes |
| Rate limit | 20 requests/minute |
| Request interval | 3+ seconds |
| Output file size | ~2-4 MB |
| Data fields per season | 6 fields |
| Historical depth | All available seasons |

## Integration

For Hoopsipedia web app:
```javascript
const seasonData = require('./seasons.json');
```

See `README_SCRAPER.md` for integration details.

## Support

- **Quick questions?** → `QUICK_START.md`
- **Technical details?** → `SCRAPER_SETUP.md`
- **Full overview?** → `README_SCRAPER.md`
- **Setup issues?** → Run `validate_setup.py`
- **Team-specific issues?** → Run `check_references.py team <ID>`

## Version Info

- Created: 2026-03-15
- Python: 3.10+
- Dependencies: requests 2.32+, beautifulsoup4 4.14+
- Rate limit: 20 requests/minute
- Status: ✅ Ready to run

---

**Next step:** Run `python3 validate_setup.py` to verify everything is ready, then `python3 test_scraper.py` for quick tests, then `python3 compile_history.py` to generate the data.
