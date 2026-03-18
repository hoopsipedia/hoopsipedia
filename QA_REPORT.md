# QA Report: 2026 NCAA Tournament Team Pages
**Date:** 2026-03-18
**Scope:** All 68 tournament teams checked against data.json, games.json, h2h.json, seasons.json
**Site:** index.html (single-page app)

---

## Executive Summary

- **Teams checked:** 68 (including 4 play-in teams)
- **PASS:** 57 teams
- **FAIL:** 11 teams (3 critical, 5 moderate, 3 minor)

### Critical Issues (team page will not load at all)
| Team | Seed | Region | ESPN ID | Issue |
|------|------|--------|---------|-------|
| McNeese Cowboys | 12 | South | 2377 | **Missing from data.json** (has games.json + seasons.json data) |
| Troy Trojans | 13 | South | 2653 | **Missing from data.json** (has games.json + seasons.json data) |
| Tennessee State Tigers | 15 | East | 2634 | **Missing from data.json** (has games.json + seasons.json data) |

### Moderate Issues (page loads but data is incomplete)
| Team | Seed | Region | ESPN ID | Issue |
|------|------|--------|---------|-------|
| Pennsylvania Quakers | 14 | South | 219 | Record 0-0, no game data in games.json |
| American University Eagles | 16 | Midwest | 44 | Record 0-0, no game data in games.json |
| Winthrop Eagles | 15 | Midwest | 2737 | Record 0-0, no game data, no espn_to_sr mapping |
| IU Indianapolis Jaguars | 16 | West | 85 | Record 0-0, no game data in games.json |
| Sam Houston Bearkats | 13 | West | 2534 | Record 0-0, no game data in games.json |

### Minor Issues (functional but data quality concern)
| Team | Seed | Region | ESPN ID | Issue |
|------|------|--------|---------|-------|
| Drake Bulldogs | 12 | Midwest | 263 | Duplicate entry (ESPN 263 + 2181) causes duplicate slug |
| Tulsa Golden Hurricane | N/A | N/A | 2631/202 | Same duplicate slug issue (not a tournament team) |

---

## Detailed Findings

### 1. Teams Missing from data.json (CRITICAL)

These 3 teams exist in games.json, seasons.json, and espn_to_sr.json but are **not in data.json H object**. Their team profile pages will fail to load because `allTeamsData` is built from `H`.

**McNeese Cowboys (ESPN 2377)**
- games.json: 1,493 games, slug `mcneese-state`
- seasons.json: 1 entry
- espn_to_sr.json: mapped to `mcneese-state`
- data.json H: **MISSING**
- Current season (CS): **MISSING**

**Troy Trojans (ESPN 2653)**
- games.json: 1,002 games, slug `troy`
- seasons.json: 1 entry
- espn_to_sr.json: mapped to `troy`
- data.json H: **MISSING**
- Current season (CS): **MISSING**

**Tennessee State Tigers (ESPN 2634)**
- games.json: 1,339 games, slug `tennessee-state`
- seasons.json: 1 entry
- espn_to_sr.json: mapped to `tennessee-state`
- data.json H: **MISSING**
- Current season (CS): **MISSING**

**Root cause:** These teams were scraped (game data exists) but never added to the `H` object in data.json. The compile_schedules.py or data pipeline skipped adding their profile data.

### 2. Teams with 0-0 Records (MODERATE)

These 5 teams exist in data.json but have ATW=0 and ATL=0 (indices 4,5). Their profile pages load but show an empty all-time record. They also have **no game data** in games.json.

| Team | ESPN ID | Conference | Notes |
|------|---------|------------|-------|
| Pennsylvania Quakers | 219 | Ivy League | Ivy League team, likely never scraped |
| American University Eagles | 44 | Patriot League | Play-in team |
| Winthrop Eagles | 2737 | Big South | Also missing from espn_to_sr.json |
| IU Indianapolis Jaguars | 85 | Horizon League | Recently rebranded from IUPUI |
| Sam Houston Bearkats | 2534 | Conference USA | Recently FBS transition |

### 3. Slug Resolution Check

The site uses `teamSlug(name)` which converts team names to URL-friendly slugs via:
```
name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
```

**All 65 teams present in data.json generate valid, resolvable slugs** via `findTeamBySlug()`.

**Duplicate slug issue:** Two pairs of teams share identical slugs:
- `drake-bulldogs` -> ESPN 263 (real, 1485-1165 record) and ESPN 2181 (ghost entry, 0-0 record)
- `tulsa-golden-hurricane` -> ESPN 2631 (real, 1360-1040) and ESPN 202 (ghost entry, 0-0)

`findTeamBySlug()` uses `.find()` which returns the first match. The result depends on the iteration order of `Object.entries(H)`. If the ghost entry (0-0 record) is returned first, the team page will show incorrect data.

### 4. Game Data Availability

**65 of 68 tournament teams in data.json have game data in games.json.**

Teams without game data (also have 0-0 records):
- Pennsylvania Quakers (219)
- American University Eagles (44)
- Winthrop Eagles (2737)
- IU Indianapolis Jaguars (85)
- Sam Houston Bearkats (2534)

### 5. Specific Team Deep Dives

#### SMU (ESPN 2567) -- previously reported Full Matchup issues
- **Status: PASS**
- data.json: Present, record 1447-1300
- games.json: 2,081 games
- h2h.json: 132 opponent entries
- seasons.json: 1 entry
- Slug: `smu-mustangs` (resolves correctly)
- **Full Matchup should work** -- h2h data is populated

#### Prairie View A&M (ESPN 2504) -- previously reported missing
- **Status: PASS**
- data.json: Present, record 407-920
- games.json: 1,327 games
- Slug: `prairie-view-a-m-panthers` (resolves correctly)
- **Fixed since last report**

#### Howard (ESPN 47) -- UMBC matchup issues
- **Status: PASS (with caveat)**
- data.json: Present, record 655-924
- games.json: 1,436 games
- h2h.json: 129 opponent entries
- UMBC (ESPN 2378): Present in data.json (502-686) and games.json
- **Howard vs UMBC h2h: NO DATA in h2h.json** -- these teams have no historical matchup record, which is expected if they have never played each other. The comparison page would show 0-0 head-to-head.

#### McNeese (ESPN 2377) -- smaller school
- **Status: CRITICAL FAIL** -- missing from data.json H
- Has game data (1,493 games) and SR mapping but no profile entry

#### Troy (ESPN 2653) -- smaller school
- **Status: CRITICAL FAIL** -- missing from data.json H
- Has game data (1,002 games) and SR mapping but no profile entry

#### Hofstra (ESPN 2275) -- smaller school
- **Status: PASS**
- data.json: Present, record 831-799
- games.json: Present with game data

#### Wright State (ESPN 2750) -- smaller school
- **Status: PASS**
- data.json: Present, record 658-526
- games.json: Present with game data

#### Akron (ESPN 2006) -- smaller school
- **Status: PASS**
- data.json: Present, record 794-580
- games.json: Present with game data

#### Idaho (ESPN 70) -- smaller school
- **Status: PASS**
- data.json: Present, record 881-1156
- games.json: Present with game data

#### Tennessee State (ESPN 2634)
- **Status: CRITICAL FAIL** -- missing from data.json H

### 6. slug_mapping.json Issues (Scraper-side, not site-display)

The `slug_mapping.json` file (used by the scraper to map ESPN IDs to Sports Reference slugs) has 118 incorrect mappings. This does NOT affect the live site display (which uses `teamSlug(name)` from data.json), but it means the scraper may be pulling wrong data for these teams. Notable tournament team mismatches:

| ESPN ID | Team | slug_mapping says | Should be |
|---------|------|-------------------|-----------|
| 70 | Idaho Vandals | `iowa` | `idaho` |
| 219 | Pennsylvania Quakers | `arizona-state` | `pennsylvania` |
| 44 | American University | `nebraska` | `american` |
| 85 | IU Indianapolis | `wisconsin` | `iu-indianapolis` |

These wrong mappings explain why these teams have 0-0 records -- the scraper pulled data for the wrong school.

### 7. Teams in games.json but NOT in data.json

14 teams have scraped game data but no data.json profile entry. Tournament-relevant ones:

| ESPN ID | Team | Games |
|---------|------|-------|
| 2377 | McNeese | 1,493 |
| 2634 | Tennessee State | 1,339 |
| 2653 | Troy | 1,002 |

---

## Recommendations (Priority Order)

1. **Add McNeese, Troy, and Tennessee State to data.json H** -- these are active tournament teams whose pages will not load
2. **Fix slug_mapping.json** for Idaho (70), Penn (219), American (44), IU Indianapolis (85), Sam Houston (2534), Winthrop (2737) -- wrong SR slugs mean the scraper pulled incorrect data
3. **Scrape game/record data** for Penn, American, Winthrop, IU Indianapolis, Sam Houston -- currently showing 0-0 records
4. **Remove duplicate entries** for Drake (ESPN 2181) and Tulsa (ESPN 202) -- ghost entries with 0-0 records that could cause slug collisions
5. **Add Winthrop to espn_to_sr.json** -- currently the only tournament team with no SR mapping at all
6. **Add current season (CS) data** for McNeese, Troy, Tennessee State once they are in data.json

---

## Full Pass/Fail Matrix

| Status | Region | Seed | Team | ESPN ID | Record | Has Games | Slug |
|--------|--------|------|------|---------|--------|-----------|------|
| PASS | South | 1 | Florida Gators | 57 | 1542-1168 | Yes | florida-gators |
| PASS | South | 16 | Lehigh Mountain Hawks | 2329 | 713-1098 | Yes | lehigh-mountain-hawks |
| PASS | South | 16 | Prairie View A&M Panthers | 2504 | 407-920 | Yes | prairie-view-a-m-panthers |
| PASS | South | 8 | Clemson Tigers | 228 | 1452-1373 | Yes | clemson-tigers |
| PASS | South | 9 | Iowa Hawkeyes | 2294 | 1735-1232 | Yes | iowa-hawkeyes |
| PASS | South | 5 | Vanderbilt Commodores | 238 | 1722-1278 | Yes | vanderbilt-commodores |
| FAIL | South | 12 | McNeese Cowboys | 2377 | N/A | Yes* | N/A |
| PASS | South | 4 | Nebraska Cornhuskers | 158 | 1582-1436 | Yes | nebraska-cornhuskers |
| FAIL | South | 13 | Troy Trojans | 2653 | N/A | Yes* | N/A |
| PASS | South | 6 | North Carolina Tar Heels | 153 | 2419-882 | Yes | north-carolina-tar-heels |
| PASS | South | 11 | VCU Rams | 2670 | 1082-565 | Yes | vcu-rams |
| PASS | South | 3 | Illinois Fighting Illini | 356 | 1937-1068 | Yes | illinois-fighting-illini |
| FAIL | South | 14 | Pennsylvania Quakers | 219 | 0-0 | No | pennsylvania-quakers |
| PASS | South | 7 | Saint Mary's Gaels | 2608 | 1516-1292 | Yes | saint-mary-s-gaels |
| PASS | South | 10 | Texas A&M Aggies | 245 | 1918-1158 | Yes | texas-a-m-aggies |
| PASS | South | 2 | Houston Cougars | 248 | 1415-846 | Yes | houston-cougars |
| PASS | South | 15 | Idaho Vandals | 70 | 881-1156 | Yes | idaho-vandals |
| PASS | East | 1 | Michigan Wolverines | 130 | 1536-1017 | Yes | michigan-wolverines |
| PASS | East | 16 | Howard Bison | 47 | 655-924 | Yes | howard-bison |
| PASS | East | 8 | Georgia Bulldogs | 61 | 1493-1404 | Yes | georgia-bulldogs |
| PASS | East | 9 | Saint Louis Billikens | 139 | 1572-1302 | Yes | saint-louis-billikens |
| PASS | East | 5 | Texas Tech Red Raiders | 2641 | 1528-1178 | Yes | texas-tech-red-raiders |
| PASS | East | 12 | Akron Zips | 2006 | 794-580 | Yes | akron-zips |
| PASS | East | 4 | Alabama Crimson Tide | 333 | 1817-1114 | Yes | alabama-crimson-tide |
| PASS | East | 13 | Hofstra Pride | 2275 | 831-799 | Yes | hofstra-pride |
| PASS | East | 6 | Tennessee Volunteers | 2633 | 1822-1121 | Yes | tennessee-volunteers |
| PASS | East | 11 | SMU Mustangs | 2567 | 1447-1300 | Yes | smu-mustangs |
| PASS | East | 11 | Miami (OH) RedHawks | 193 | 1130-954 | Yes | miami-oh-redhawks |
| PASS | East | 3 | Virginia Cavaliers | 258 | 1786-1237 | Yes | virginia-cavaliers |
| PASS | East | 14 | Wright State Raiders | 2750 | 658-526 | Yes | wright-state-raiders |
| PASS | East | 7 | Kentucky Wildcats | 96 | 2443-784 | Yes | kentucky-wildcats |
| PASS | East | 10 | Santa Clara Broncos | 2541 | 1135-945 | Yes | santa-clara-broncos |
| PASS | East | 2 | Iowa State Cyclones | 66 | 1450-1368 | Yes | iowa-state-cyclones |
| FAIL | East | 15 | Tennessee State Tigers | 2634 | N/A | Yes* | N/A |
| PASS | Midwest | 1 | Auburn Tigers | 2 | 1509-1258 | Yes | auburn-tigers |
| FAIL | Midwest | 16 | American University Eagles | 44 | 0-0 | No | american-university-eagles |
| PASS | Midwest | 8 | Mississippi State Bulldogs | 344 | 1534-1288 | Yes | mississippi-state-bulldogs |
| PASS | Midwest | 9 | Creighton Bluejays | 156 | 1720-1099 | Yes | creighton-bluejays |
| PASS | Midwest | 5 | Marquette Golden Eagles | 269 | 1749-1087 | Yes | marquette-golden-eagles |
| WARN | Midwest | 12 | Drake Bulldogs | 263 | 1485-1165 | Yes | drake-bulldogs (dup) |
| PASS | Midwest | 4 | Wisconsin Badgers | 275 | 1723-1200 | Yes | wisconsin-badgers |
| PASS | Midwest | 13 | Grand Canyon Lopes | 2253 | 276-143 | Yes | grand-canyon-lopes |
| PASS | Midwest | 6 | BYU Cougars | 252 | 1940-1145 | Yes | byu-cougars |
| PASS | Midwest | 11 | Boise State Broncos | 68 | 923-691 | Yes | boise-state-broncos |
| PASS | Midwest | 3 | Texas Longhorns | 251 | 1918-1158 | Yes | texas-longhorns |
| PASS | Midwest | 14 | Loyola Chicago Ramblers | 2350 | 1462-1254 | Yes | loyola-chicago-ramblers |
| PASS | Midwest | 7 | UCLA Bruins | 26 | 2051-931 | Yes | ucla-bruins |
| PASS | Midwest | 10 | North Texas Mean Green | 249 | 842-1030 | Yes | north-texas-mean-green |
| PASS | Midwest | 2 | Duke Blue Devils | 150 | 2367-935 | Yes | duke-blue-devils |
| FAIL | Midwest | 15 | Winthrop Eagles | 2737 | 0-0 | No | winthrop-eagles |
| PASS | West | 1 | Gonzaga Bulldogs | 2250 | 1507-735 | Yes | gonzaga-bulldogs |
| FAIL | West | 16 | IU Indianapolis Jaguars | 85 | 0-0 | No | iu-indianapolis-jaguars |
| PASS | West | 8 | Colorado Buffaloes | 38 | 1429-1287 | Yes | colorado-buffaloes |
| PASS | West | 9 | Missouri Tigers | 142 | 1680-1225 | Yes | missouri-tigers |
| PASS | West | 5 | Purdue Boilermakers | 2509 | 1931-1060 | Yes | purdue-boilermakers |
| PASS | West | 12 | High Point Panthers | 2272 | 427-405 | Yes | high-point-panthers |
| PASS | West | 4 | Arizona Wildcats | 12 | 1863-955 | Yes | arizona-wildcats |
| FAIL | West | 13 | Sam Houston Bearkats | 2534 | 0-0 | No | sam-houston-bearkats |
| PASS | West | 6 | Oregon Ducks | 2483 | 1779-1426 | Yes | oregon-ducks |
| PASS | West | 11 | New Mexico Lobos | 167 | 1655-1201 | Yes | new-mexico-lobos |
| PASS | West | 3 | St. John's Red Storm | 2599 | 2001-1110 | Yes | st-john-s-red-storm |
| PASS | West | 14 | Dayton Flyers | 2168 | 1781-1176 | Yes | dayton-flyers |
| PASS | West | 7 | Kansas Jayhawks | 2305 | 2437-919 | Yes | kansas-jayhawks |
| PASS | West | 10 | Notre Dame Fighting Irish | 87 | 1989-1144 | Yes | notre-dame-fighting-irish |
| PASS | West | 2 | UConn Huskies | 41 | 1810-985 | Yes | uconn-huskies |
| PASS | West | 15 | Murray State Racers | 93 | 1175-748 | Yes | murray-state-racers |

*Yes = game data exists in games.json but team has no data.json entry so it cannot be loaded by the site

---

## Notes

- Midwest and West region teams were estimated based on available data (actual bracket is fetched live from ESPN API at runtime). The teams listed may differ from the final bracket; verify against the live bracket.
- The `slug_mapping.json` file maps ESPN IDs to Sports Reference slugs for the scraper. It is NOT used by the site for page routing. The site generates slugs from team names in data.json via `teamSlug()`.
- The `findTeamBySlug()` function uses `Array.find()` which returns the first match. For duplicate slugs (Drake, Tulsa), the returned team depends on JS object key iteration order.
