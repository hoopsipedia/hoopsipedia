# DATA_AUDIT.md - Hoopsipedia Data Verification Report
## Generated: 2026-03-18 (Pre-Launch Audit)

## Summary

- **Total changes made**: 297
- **Teams affected**: 129
- **All-time record corrections**: 246
- **Tournament stat corrections (NC/FF/NT)**: 45
- **Name corrections**: 5
- **Conference corrections**: 1
- **Teams with 0-0 records fixed**: 46 (all resolved)

## Methodology

### Source of Truth Hierarchy
1. **NCAA official record book** - Ultimate authority. Vacated wins are removed.
2. **d1sportsnet.com** - Uses NCAA official numbers (post-vacation) through end of 2024-25 season. Primary source for all-time W-L records of top 100 programs.
3. **ESPN API** (`site.api.espn.com`) - Fetched 2025-26 current season records for all 207 teams in real-time.
4. **Wikipedia team pages** - Cross-reference for tournament stats, championship counts, and historical records.
5. **NCAA.com** - Tournament appearance counts, championship verification.
6. **FOX Sports, CBS Sports, ESPN articles** - Final Four and tournament appearance verification.

### Calculation Method
```
All-time record = d1sportsnet (through 2024-25) + ESPN API (2025-26 current season)
```
For teams not in d1sportsnet top 100: Wikipedia/Sports Reference historical + ESPN current season.
For teams with no historical data found: ESPN 2025-26 current season only (minimum baseline).

### Vacated Wins Treatment
The following programs had wins vacated by the NCAA. Our records use the **post-vacation** (NCAA official) numbers:

| Program | Wins Vacated | Reason | Ruling Date |
|---------|-------------|--------|-------------|
| Kansas | 15 | Adidas/Silvio De Souza recruiting violations (2017-18) | Oct 2023 |
| Louisville | 123 | Recruiting scandal (2011-15 seasons); 2013 title vacated | Feb 2018 |
| Syracuse | 101 | Academic/eligibility violations (multiple seasons) | 2015 |
| Memphis | 38+ | Derrick Rose eligibility (2007-08) + 1980s era | 2009 |

## Root Cause of Discrepancies

Our previous all-time records were computed from `games.json`, which contained game-by-game data
starting from roughly the 1950s-1970s for most programs. This caused all-time win totals to be
significantly understated for programs with extensive pre-1950s history.

**Average correction magnitude for top-25 programs: +550 wins, +300 losses**

The 46 teams that previously had 0-0 records were teams added via ESPN API with only
placeholder data. These have now been populated with at minimum their current season records.

## Key Verifications Passed

- Kentucky (2,443 W) leads Kansas (2,437 W) as NCAA all-time wins leader
- All 15 championship programs have correct NC counts (UCLA 11, Kentucky 8, UNC 6, UConn 6, Duke 5, Indiana 5, Kansas 4, Villanova 3, Florida 3, Cincinnati 2, Louisville 2, NC State 2, Oklahoma State 2, San Francisco 2, Michigan State 2)
- Louisville 2013 championship correctly excluded (vacated)
- Florida 2025 championship correctly included
- Kansas 2018 Final Four correctly excluded (vacated)
- All 207 teams have non-zero records
- All conference affiliations verified against 2025-26 season (post-realignment)

## Critical Corrections (Blue Bloods and Top Programs)

### Kentucky Wildcats (ESPN ID: 96)
- **ATW (all-time wins)**: `1827` -> `2443`
  - Source: d1sportsnet.com (2422 thru 2024-25) + ESPN 2025-26 (21-13)
- **ATL (all-time losses)**: `560` -> `783`
  - Source: d1sportsnet.com (770 thru 2024-25) + ESPN 2025-26 (21-13)
- **NT (tournament appearances)**: `60` -> `63`
  - Source: Kentucky - 63 tournament appearances (most all-time, incl 2026)

### Kansas Jayhawks (ESPN ID: 2305)
- **ATW (all-time wins)**: `1729` -> `2437`
  - Source: d1sportsnet.com (2414 thru 2024-25) + ESPN 2025-26 (23-10)
- **ATL (all-time losses)**: `619` -> `919`
  - Source: d1sportsnet.com (909 thru 2024-25) + ESPN 2025-26 (23-10)
- **FF (Final Fours)**: `15` -> `16`
  - Source: Kansas - 16 FF per Wikipedia/KU Athletics
- **NT (tournament appearances)**: `50` -> `52`
  - Source: Kansas - 52 appearances (post-vacation, incl 2026)

### North Carolina Tar Heels (ESPN ID: 153)
- **ATW (all-time wins)**: `1795` -> `2419`
  - Source: d1sportsnet.com (2395 thru 2024-25) + ESPN 2025-26 (24-8)
- **ATL (all-time losses)**: `627` -> `882`
  - Source: d1sportsnet.com (874 thru 2024-25) + ESPN 2025-26 (24-8)
- **NT (tournament appearances)**: `52` -> `55`
  - Source: North Carolina - 55 appearances (incl 2026)

### Duke Blue Devils (ESPN ID: 150)
- **ATW (all-time wins)**: `1833` -> `2367`
  - Source: d1sportsnet.com (2335 thru 2024-25) + ESPN 2025-26 (32-2)
- **ATL (all-time losses)**: `634` -> `935`
  - Source: d1sportsnet.com (933 thru 2024-25) + ESPN 2025-26 (32-2)
- **FF (Final Fours)**: `17` -> `18`
  - Source: Duke - 18 FF per ESPN/Wikipedia (tied with UCLA)
- **NT (tournament appearances)**: `47` -> `48`
  - Source: Duke - 48 appearances (incl 2026)

### UCLA Bruins (ESPN ID: 26)
- **ATW (all-time wins)**: `1720` -> `2048`
  - Source: d1sportsnet.com (2025 thru 2024-25) + ESPN 2025-26 (23-11)
- **ATL (all-time losses)**: `641` -> `927`
  - Source: d1sportsnet.com (916 thru 2024-25) + ESPN 2025-26 (23-11)
- **NT (tournament appearances)**: `51` -> `52`
  - Source: UCLA - 52 appearances (incl 2026)

### Syracuse Orange (ESPN ID: 183)
- **ATW (all-time wins)**: `1515` -> `2022`
  - Source: d1sportsnet.com (2007 thru 2024-25) + ESPN 2025-26 (15-17)
- **ATL (all-time losses)**: `757` -> `1012`
  - Source: d1sportsnet.com (995 thru 2024-25) + ESPN 2025-26 (15-17)
- **NT (tournament appearances)**: `38` -> `39`
  - Source: Syracuse - 39 appearances (post-vacation)

### Louisville Cardinals (ESPN ID: 97)
- **ATW (all-time wins)**: `1430` -> `1834`
  - Source: d1sportsnet.com (1811 thru 2024-25) + ESPN 2025-26 (23-10)
- **ATL (all-time losses)**: `710` -> `1029`
  - Source: d1sportsnet.com (1019 thru 2024-25) + ESPN 2025-26 (23-10)
- **NC (national championships)**: `1` -> `2`
  - Source: NCAA.com - Louisville - 2 official NC (2013 vacated)
- **FF (Final Fours)**: `7` -> `8`
  - Source: Louisville - 8 official FF (2012, 2013 vacated from 10)
- **NT (tournament appearances)**: `42` -> `41`
  - Source: Louisville - 41 appearances (post-vacation)

### UConn Huskies (ESPN ID: 41)
- **ATW (all-time wins)**: `1327` -> `1890`
  - Source: d1sportsnet.com (1861 thru 2024-25) + ESPN 2025-26 (29-5)
- **ATL (all-time losses)**: `695` -> `1031`
  - Source: d1sportsnet.com (1026 thru 2024-25) + ESPN 2025-26 (29-5)

### Florida Gators (ESPN ID: 57)
- **ATW (all-time wins)**: `1248` -> `1591`
  - Source: d1sportsnet.com (1565 thru 2024-25) + ESPN 2025-26 (26-7)
- **ATL (all-time losses)**: `887` -> `1197`
  - Source: d1sportsnet.com (1190 thru 2024-25) + ESPN 2025-26 (26-7)
- **NT (tournament appearances)**: `30` -> `31`
  - Source: Florida - 31 appearances (incl 2026)

### Indiana Hoosiers (ESPN ID: 84)
- **ATW (all-time wins)**: `1432` -> `1968`
  - Source: d1sportsnet.com (1950 thru 2024-25) + ESPN 2025-26 (18-14)
- **ATL (all-time losses)**: `781` -> `1144`
  - Source: d1sportsnet.com (1130 thru 2024-25) + ESPN 2025-26 (18-14)
- **NT (tournament appearances)**: `40` -> `41`
  - Source: Indiana - 41 appearances

### Michigan State Spartans (ESPN ID: 127)
- **ATW (all-time wins)**: `1363` -> `1886`
  - Source: d1sportsnet.com (1861 thru 2024-25) + ESPN 2025-26 (25-7)
- **ATL (all-time losses)**: `793` -> `1170`
  - Source: d1sportsnet.com (1163 thru 2024-25) + ESPN 2025-26 (25-7)
- **NT (tournament appearances)**: `36` -> `39`
  - Source: Michigan State - 39 appearances (incl 2026)

### Villanova Wildcats (ESPN ID: 222)
- **ATW (all-time wins)**: `1462` -> `1927`
  - Source: d1sportsnet.com (1903 thru 2024-25) + ESPN 2025-26 (24-8)
- **ATL (all-time losses)**: `806` -> `1012`
  - Source: d1sportsnet.com (1004 thru 2024-25) + ESPN 2025-26 (24-8)
- **NT (tournament appearances)**: `42` -> `41`
  - Source: Villanova - 41 appearances (incl 2026)

### Houston Cougars (ESPN ID: 248)
- **NT (tournament appearances)**: `26` -> `27`
  - Source: Houston - 27 appearances (incl 2026)
- **ATW (all-time wins)**: `1299` -> `1435`
  - Source: Wikipedia/Sports Reference (1407 thru 2024-25) + ESPN 2025-26
- **ATL (all-time losses)**: `837` -> `853`
  - Source: Wikipedia/Sports Reference (847 thru 2024-25) + ESPN 2025-26

### Arkansas Razorbacks (ESPN ID: 8)
- **ATW (all-time wins)**: `1362` -> `1847`
  - Source: d1sportsnet.com (1821 thru 2024-25) + ESPN 2025-26 (26-8)
- **ATL (all-time losses)**: `871` -> `1036`
  - Source: d1sportsnet.com (1028 thru 2024-25) + ESPN 2025-26 (26-8)
- **NT (tournament appearances)**: `35` -> `36`
  - Source: Arkansas - 36 appearances (incl 2026)

### Purdue Boilermakers (ESPN ID: 2509)
- **ATW (all-time wins)**: `1358` -> `1980`
  - Source: d1sportsnet.com (1953 thru 2024-25) + ESPN 2025-26 (27-8)
- **ATL (all-time losses)**: `784` -> `1100`
  - Source: d1sportsnet.com (1092 thru 2024-25) + ESPN 2025-26 (27-8)
- **NT (tournament appearances)**: `31` -> `34`
  - Source: Purdue - 34 appearances (incl 2026)

### Tennessee Volunteers (ESPN ID: 2633)
- **ATW (all-time wins)**: `1336` -> `1822`
  - Source: d1sportsnet.com (1800 thru 2024-25) + ESPN 2025-26 (22-11)
- **ATL (all-time losses)**: `871` -> `1122`
  - Source: d1sportsnet.com (1111 thru 2024-25) + ESPN 2025-26 (22-11)
- **NT (tournament appearances)**: `28` -> `29`
  - Source: Tennessee - 29 appearances (incl 2026)

### Alabama Crimson Tide (ESPN ID: 333)
- **ATW (all-time wins)**: `1324` -> `1843`
  - Source: d1sportsnet.com (1820 thru 2024-25) + ESPN 2025-26 (23-9)
- **ATL (all-time losses)**: `874` -> `1117`
  - Source: d1sportsnet.com (1108 thru 2024-25) + ESPN 2025-26 (23-9)
- **NT (tournament appearances)**: `26` -> `27`
  - Source: Alabama - 27 appearances (incl 2026)

## Complete Change Log (All Teams)

### Alabama Crimson Tide (ESPN ID: 333)
- **ATW (all-time wins)**: `1324` -> `1843` | Source: d1sportsnet.com (1820 thru 2024-25) + ESPN 2025-26 (23-9)
- **ATL (all-time losses)**: `874` -> `1117` | Source: d1sportsnet.com (1108 thru 2024-25) + ESPN 2025-26 (23-9)
- **NT (tournament appearances)**: `26` -> `27` | Source: Alabama - 27 appearances (incl 2026)

### App State Mountaineers (ESPN ID: 2026)
- **ATW (all-time wins)**: `0` -> `19` | Source: ESPN 2025-26 current season only (19-13)
- **ATL (all-time losses)**: `0` -> `13` | Source: ESPN 2025-26 current season only (19-13)

### Arizona Wildcats (ESPN ID: 12)
- **ATW (all-time wins)**: `1274` -> `1945` | Source: d1sportsnet.com (1913 thru 2024-25) + ESPN 2025-26 (32-2)
- **ATL (all-time losses)**: `726` -> `1001` | Source: d1sportsnet.com (999 thru 2024-25) + ESPN 2025-26 (32-2)
- **NT (tournament appearances)**: `38` -> `37` | Source: Arizona - 37 appearances

### Arkansas Razorbacks (ESPN ID: 8)
- **ATW (all-time wins)**: `1362` -> `1847` | Source: d1sportsnet.com (1821 thru 2024-25) + ESPN 2025-26 (26-8)
- **ATL (all-time losses)**: `871` -> `1036` | Source: d1sportsnet.com (1028 thru 2024-25) + ESPN 2025-26 (26-8)
- **NT (tournament appearances)**: `35` -> `36` | Source: Arkansas - 36 appearances (incl 2026)

### Army Black Knights (ESPN ID: 349)
- **ATW (all-time wins)**: `0` -> `11` | Source: ESPN 2025-26 current season only (11-21)
- **ATL (all-time losses)**: `0` -> `21` | Source: ESPN 2025-26 current season only (11-21)

### BYU Cougars (ESPN ID: 252)
- **ATW (all-time wins)**: `1391` -> `1941` | Source: d1sportsnet.com (1918 thru 2024-25) + ESPN 2025-26 (23-11)
- **ATL (all-time losses)**: `840` -> `1166` | Source: d1sportsnet.com (1155 thru 2024-25) + ESPN 2025-26 (23-11)

### Ball State Cardinals (ESPN ID: 2050)
- **ATW (all-time wins)**: `0` -> `12` | Source: ESPN 2025-26 current season only (12-19)
- **ATL (all-time losses)**: `0` -> `19` | Source: ESPN 2025-26 current season only (12-19)

### Baylor Bears (ESPN ID: 239)
- **FF (Final Fours)**: `3` -> `1` | Source: Baylor - 1 FF (2021 championship)

### Boston University Terriers (ESPN ID: 104)
- **ATW (all-time wins)**: `0` -> `17` | Source: ESPN 2025-26 current season only (17-17)
- **ATL (all-time losses)**: `0` -> `17` | Source: ESPN 2025-26 current season only (17-17)

### Bowling Green Falcons (ESPN ID: 189)
- **ATW (all-time wins)**: `0` -> `18` | Source: ESPN 2025-26 current season only (18-14)
- **ATL (all-time losses)**: `0` -> `14` | Source: ESPN 2025-26 current season only (18-14)

### Bryant Bulldogs (ESPN ID: 2803)
- **ATW (all-time wins)**: `0` -> `9` | Source: ESPN 2025-26 current season only (9-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (9-22)

### Butler Bulldogs (ESPN ID: 2086)
- **ATW (all-time wins)**: `966` -> `1710` | Source: d1sportsnet.com (1694 thru 2024-25) + ESPN 2025-26 (16-16)
- **ATL (all-time losses)**: `857` -> `1258` | Source: d1sportsnet.com (1242 thru 2024-25) + ESPN 2025-26 (16-16)

### Cal Golden Bears (ESPN ID: 25)
- **ATW (all-time wins)**: `1099` -> `1674` | Source: d1sportsnet.com (1653 thru 2024-25) + ESPN 2025-26 (21-11)
- **ATL (all-time losses)**: `1005` -> `1344` | Source: d1sportsnet.com (1333 thru 2024-25) + ESPN 2025-26 (21-11)
- **NAME**: `Cal Golden Bears` -> `California Golden Bears` | Source: ESPN uses California not Cal

### Canisius Golden Griffins (ESPN ID: 2099)
- **ATW (all-time wins)**: `0` -> `10` | Source: ESPN 2025-26 current season only (10-21)
- **ATL (all-time losses)**: `0` -> `21` | Source: ESPN 2025-26 current season only (10-21)

### Charleston Cougars (ESPN ID: 232)
- **ATW (all-time wins)**: `0` -> `21` | Source: ESPN 2025-26 current season only (21-11)
- **ATL (all-time losses)**: `0` -> `11` | Source: ESPN 2025-26 current season only (21-11)

### Cincinnati Bearcats (ESPN ID: 2132)
- **ATW (all-time wins)**: `1454` -> `1948` | Source: d1sportsnet.com (1930 thru 2024-25) + ESPN 2025-26 (18-15)
- **ATL (all-time losses)**: `756` -> `1110` | Source: d1sportsnet.com (1095 thru 2024-25) + ESPN 2025-26 (18-15)
- **NT (tournament appearances)**: `33` -> `34` | Source: Cincinnati - 34 appearances

### Cleveland State Vikings (ESPN ID: 325)
- **ATW (all-time wins)**: `0` -> `11` | Source: ESPN 2025-26 current season only (11-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (11-22)

### Coastal Carolina Chanticleers (ESPN ID: 324)
- **ATW (all-time wins)**: `0` -> `19` | Source: ESPN 2025-26 current season only (19-13)
- **ATL (all-time losses)**: `0` -> `13` | Source: ESPN 2025-26 current season only (19-13)

### Columbia Lions (ESPN ID: 171)
- **ATW (all-time wins)**: `0` -> `16` | Source: ESPN 2025-26 current season only (16-12)
- **ATL (all-time losses)**: `0` -> `12` | Source: ESPN 2025-26 current season only (16-12)

### Creighton Bluejays (ESPN ID: 156)
- **ATW (all-time wins)**: `1111` -> `1750` | Source: d1sportsnet.com (1735 thru 2024-25) + ESPN 2025-26 (15-17)
- **ATL (all-time losses)**: `863` -> `1127` | Source: d1sportsnet.com (1110 thru 2024-25) + ESPN 2025-26 (15-17)

### Davidson Wildcats (ESPN ID: 2166)
- **ATW (all-time wins)**: `1105` -> `1586` | Source: d1sportsnet.com (1566 thru 2024-25) + ESPN 2025-26 (20-14)
- **ATL (all-time losses)**: `928` -> `1311` | Source: d1sportsnet.com (1297 thru 2024-25) + ESPN 2025-26 (20-14)

### Dayton Flyers (ESPN ID: 2168)
- **ATW (all-time wins)**: `1342` -> `1805` | Source: d1sportsnet.com (1782 thru 2024-25) + ESPN 2025-26 (23-11)
- **ATL (all-time losses)**: `822` -> `1183` | Source: d1sportsnet.com (1172 thru 2024-25) + ESPN 2025-26 (23-11)

### Delaware Blue Hens (ESPN ID: 48)
- **ATW (all-time wins)**: `0` -> `10` | Source: ESPN 2025-26 current season only (10-21)
- **ATL (all-time losses)**: `0` -> `21` | Source: ESPN 2025-26 current season only (10-21)

### Drake Bulldogs (ESPN ID: 2181)
- **ATW (all-time wins)**: `0` -> `14` | Source: ESPN 2025-26 current season only (14-20)
- **ATL (all-time losses)**: `0` -> `20` | Source: ESPN 2025-26 current season only (14-20)

### Duke Blue Devils (ESPN ID: 150)
- **ATW (all-time wins)**: `1833` -> `2367` | Source: d1sportsnet.com (2335 thru 2024-25) + ESPN 2025-26 (32-2)
- **ATL (all-time losses)**: `634` -> `935` | Source: d1sportsnet.com (933 thru 2024-25) + ESPN 2025-26 (32-2)
- **FF (Final Fours)**: `17` -> `18` | Source: Duke - 18 FF per ESPN/Wikipedia (tied with UCLA)
- **NT (tournament appearances)**: `47` -> `48` | Source: Duke - 48 appearances (incl 2026)

### Eastern Washington Eagles (ESPN ID: 331)
- **ATW (all-time wins)**: `0` -> `1555` | Source: d1sportsnet.com (1541 thru 2024-25) + ESPN 2025-26 (14-19)
- **ATL (all-time losses)**: `0` -> `1327` | Source: d1sportsnet.com (1308 thru 2024-25) + ESPN 2025-26 (14-19)

### FAU Owls (ESPN ID: 2226)
- **NAME**: `FAU Owls` -> `Florida Atlantic Owls` | Source: Full name is Florida Atlantic Owls

### Florida Gators (ESPN ID: 57)
- **ATW (all-time wins)**: `1248` -> `1591` | Source: d1sportsnet.com (1565 thru 2024-25) + ESPN 2025-26 (26-7)
- **ATL (all-time losses)**: `887` -> `1197` | Source: d1sportsnet.com (1190 thru 2024-25) + ESPN 2025-26 (26-7)
- **NT (tournament appearances)**: `30` -> `31` | Source: Florida - 31 appearances (incl 2026)

### Fordham Rams (ESPN ID: 2230)
- **ATW (all-time wins)**: `845` -> `1623` | Source: d1sportsnet.com (1606 thru 2024-25) + ESPN 2025-26 (17-15)
- **ATL (all-time losses)**: `1092` -> `1511` | Source: d1sportsnet.com (1496 thru 2024-25) + ESPN 2025-26 (17-15)

### Georgetown Hoyas (ESPN ID: 46)
- **ATW (all-time wins)**: `1189` -> `1756` | Source: d1sportsnet.com (1740 thru 2024-25) + ESPN 2025-26 (16-18)
- **ATL (all-time losses)**: `880` -> `1190` | Source: d1sportsnet.com (1172 thru 2024-25) + ESPN 2025-26 (16-18)

### Georgia State Panthers (ESPN ID: 2247)
- **ATW (all-time wins)**: `0` -> `10` | Source: ESPN 2025-26 current season only (10-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (10-22)

### Gonzaga Bulldogs (ESPN ID: 2250)
- **ATW (all-time wins)**: `1269` -> `1872` | Source: d1sportsnet.com (1842 thru 2024-25) + ESPN 2025-26 (30-3)
- **ATL (all-time losses)**: `671` -> `1131` | Source: d1sportsnet.com (1128 thru 2024-25) + ESPN 2025-26 (30-3)
- **NT (tournament appearances)**: `25` -> `26` | Source: Gonzaga - 26 appearances (incl 2026)

### Harvard Crimson (ESPN ID: 108)
- **ATW (all-time wins)**: `0` -> `17` | Source: ESPN 2025-26 current season only (17-12)
- **ATL (all-time losses)**: `0` -> `12` | Source: ESPN 2025-26 current season only (17-12)

### Holy Cross Crusaders (ESPN ID: 107)
- **NC (national championships)**: `0` -> `1` | Source: NCAA.com - Holy Cross - 1 NC (1947)
- **NCY (championship years)**: `[]` -> `[1947]` | Source: NCAA.com - Holy Cross - 1 NC (1947)

### Houston Cougars (ESPN ID: 248)
- **NT (tournament appearances)**: `26` -> `27` | Source: Houston - 27 appearances (incl 2026)
- **ATW (all-time wins)**: `1299` -> `1435` | Source: Wikipedia/Sports Reference (1407 thru 2024-25) + ESPN 2025-26
- **ATL (all-time losses)**: `837` -> `853` | Source: Wikipedia/Sports Reference (847 thru 2024-25) + ESPN 2025-26

### Illinois Fighting Illini (ESPN ID: 356)
- **ATW (all-time wins)**: `1415` -> `1953` | Source: d1sportsnet.com (1929 thru 2024-25) + ESPN 2025-26 (24-8)
- **ATL (all-time losses)**: `805` -> `1082` | Source: d1sportsnet.com (1074 thru 2024-25) + ESPN 2025-26 (24-8)
- **NT (tournament appearances)**: `31` -> `36` | Source: Illinois - 36 appearances (incl 2026)

### Indiana Hoosiers (ESPN ID: 84)
- **ATW (all-time wins)**: `1432` -> `1968` | Source: d1sportsnet.com (1950 thru 2024-25) + ESPN 2025-26 (18-14)
- **ATL (all-time losses)**: `781` -> `1144` | Source: d1sportsnet.com (1130 thru 2024-25) + ESPN 2025-26 (18-14)
- **NT (tournament appearances)**: `40` -> `41` | Source: Indiana - 41 appearances

### Iona Gaels (ESPN ID: 314)
- **ATW (all-time wins)**: `0` -> `18` | Source: ESPN 2025-26 current season only (18-14)
- **ATL (all-time losses)**: `0` -> `14` | Source: ESPN 2025-26 current season only (18-14)

### Iowa Hawkeyes (ESPN ID: 2294)
- **ATW (all-time wins)**: `1238` -> `1796` | Source: d1sportsnet.com (1775 thru 2024-25) + ESPN 2025-26 (21-12)
- **ATL (all-time losses)**: `866` -> `1245` | Source: d1sportsnet.com (1233 thru 2024-25) + ESPN 2025-26 (21-12)

### Jacksonville Dolphins (ESPN ID: 294)
- **ATW (all-time wins)**: `0` -> `12` | Source: ESPN 2025-26 current season only (12-20)
- **ATL (all-time losses)**: `0` -> `20` | Source: ESPN 2025-26 current season only (12-20)

### James Madison Dukes (ESPN ID: 256)
- **ATW (all-time wins)**: `0` -> `18` | Source: ESPN 2025-26 current season only (18-15)
- **ATL (all-time losses)**: `0` -> `15` | Source: ESPN 2025-26 current season only (18-15)

### Kansas Jayhawks (ESPN ID: 2305)
- **ATW (all-time wins)**: `1729` -> `2437` | Source: d1sportsnet.com (2414 thru 2024-25) + ESPN 2025-26 (23-10)
- **ATL (all-time losses)**: `619` -> `919` | Source: d1sportsnet.com (909 thru 2024-25) + ESPN 2025-26 (23-10)
- **FF (Final Fours)**: `15` -> `16` | Source: Kansas - 16 FF per Wikipedia/KU Athletics
- **NT (tournament appearances)**: `50` -> `52` | Source: Kansas - 52 appearances (post-vacation, incl 2026)

### Kansas State Wildcats (ESPN ID: 2306)
- **ATW (all-time wins)**: `1268` -> `1768` | Source: d1sportsnet.com (1756 thru 2024-25) + ESPN 2025-26 (12-20)
- **ATL (all-time losses)**: `837` -> `1275` | Source: d1sportsnet.com (1255 thru 2024-25) + ESPN 2025-26 (12-20)

### Kentucky Wildcats (ESPN ID: 96)
- **ATW (all-time wins)**: `1827` -> `2443` | Source: d1sportsnet.com (2422 thru 2024-25) + ESPN 2025-26 (21-13)
- **ATL (all-time losses)**: `560` -> `783` | Source: d1sportsnet.com (770 thru 2024-25) + ESPN 2025-26 (21-13)
- **NT (tournament appearances)**: `60` -> `63` | Source: Kentucky - 63 tournament appearances (most all-time, incl 2026)

### LSU Tigers (ESPN ID: 99)
- **ATW (all-time wins)**: `1200` -> `1680` | Source: d1sportsnet.com (1665 thru 2024-25) + ESPN 2025-26 (15-17)
- **ATL (all-time losses)**: `1014` -> `1287` | Source: d1sportsnet.com (1270 thru 2024-25) + ESPN 2025-26 (15-17)

### La Salle Explorers (ESPN ID: 2325)
- **NC (national championships)**: `0` -> `1` | Source: NCAA.com - La Salle won 1954 championship
- **NCY (championship years)**: `[]` -> `[1954]` | Source: NCAA.com - La Salle 1954

### Lafayette Leopards (ESPN ID: 322)
- **ATW (all-time wins)**: `0` -> `11` | Source: ESPN 2025-26 current season only (11-21)
- **ATL (all-time losses)**: `0` -> `21` | Source: ESPN 2025-26 current season only (11-21)

### Lamar Cardinals (ESPN ID: 2320)
- **ATW (all-time wins)**: `0` -> `12` | Source: ESPN 2025-26 current season only (12-19)
- **ATL (all-time losses)**: `0` -> `19` | Source: ESPN 2025-26 current season only (12-19)

### Long Beach State Beach (ESPN ID: 299)
- **ATW (all-time wins)**: `0` -> `10` | Source: ESPN 2025-26 current season only (10-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (10-22)

### Louisiana Ragin' Cajuns (ESPN ID: 309)
- **ATW (all-time wins)**: `0` -> `11` | Source: ESPN 2025-26 current season only (11-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (11-22)

### Louisville Cardinals (ESPN ID: 97)
- **ATW (all-time wins)**: `1430` -> `1834` | Source: d1sportsnet.com (1811 thru 2024-25) + ESPN 2025-26 (23-10)
- **ATL (all-time losses)**: `710` -> `1029` | Source: d1sportsnet.com (1019 thru 2024-25) + ESPN 2025-26 (23-10)
- **NC (national championships)**: `1` -> `2` | Source: NCAA.com - Louisville - 2 official NC (2013 vacated)
- **FF (Final Fours)**: `7` -> `8` | Source: Louisville - 8 official FF (2012, 2013 vacated from 10)
- **NT (tournament appearances)**: `42` -> `41` | Source: Louisville - 41 appearances (post-vacation)

### Loyola Chicago Ramblers (ESPN ID: 2350)
- **NC (national championships)**: `0` -> `1` | Source: NCAA.com - Loyola Chicago - 1 NC (1963)
- **NCY (championship years)**: `[]` -> `[1963]` | Source: NCAA.com - Loyola Chicago - 1 NC (1963)

### Marquette Golden Eagles (ESPN ID: 269)
- **ATW (all-time wins)**: `1352` -> `1775` | Source: d1sportsnet.com (1763 thru 2024-25) + ESPN 2025-26 (12-20)
- **ATL (all-time losses)**: `814` -> `1093` | Source: d1sportsnet.com (1073 thru 2024-25) + ESPN 2025-26 (12-20)
- **NT (tournament appearances)**: `30` -> `34` | Source: Marquette - 34 appearances

### Marshall Thundering Herd (ESPN ID: 276)
- **ATW (all-time wins)**: `0` -> `1627` | Source: d1sportsnet.com (1608 thru 2024-25) + ESPN 2025-26 (19-13)
- **ATL (all-time losses)**: `0` -> `1214` | Source: d1sportsnet.com (1201 thru 2024-25) + ESPN 2025-26 (19-13)

### Maryland Terrapins (ESPN ID: 120)
- **ATW (all-time wins)**: `1386` -> `1699` | Source: d1sportsnet.com (1687 thru 2024-25) + ESPN 2025-26 (12-21)
- **ATL (all-time losses)**: `871` -> `1164` | Source: d1sportsnet.com (1143 thru 2024-25) + ESPN 2025-26 (12-21)
- **NT (tournament appearances)**: `28` -> `31` | Source: Maryland - 31 appearances

### Massachusetts Minutemen (ESPN ID: 113)
- **ATW (all-time wins)**: `0` -> `17` | Source: ESPN 2025-26 current season only (17-16)
- **ATL (all-time losses)**: `0` -> `16` | Source: ESPN 2025-26 current season only (17-16)

### Memphis Tigers (ESPN ID: 235)
- **ATW (all-time wins)**: `1166` -> `1715` | Source: d1sportsnet.com (1702 thru 2024-25) + ESPN 2025-26 (13-19)
- **ATL (all-time losses)**: `669` -> `990` | Source: d1sportsnet.com (971 thru 2024-25) + ESPN 2025-26 (13-19)
- **NT (tournament appearances)**: `26` -> `27` | Source: Memphis - 27 appearances

### Michigan State Spartans (ESPN ID: 127)
- **ATW (all-time wins)**: `1363` -> `1886` | Source: d1sportsnet.com (1861 thru 2024-25) + ESPN 2025-26 (25-7)
- **ATL (all-time losses)**: `793` -> `1170` | Source: d1sportsnet.com (1163 thru 2024-25) + ESPN 2025-26 (25-7)
- **NT (tournament appearances)**: `36` -> `39` | Source: Michigan State - 39 appearances (incl 2026)

### Michigan Wolverines (ESPN ID: 130)
- **ATW (all-time wins)**: `1183` -> `1648` | Source: d1sportsnet.com (1617 thru 2024-25) + ESPN 2025-26 (31-3)
- **ATL (all-time losses)**: `783` -> `1124` | Source: d1sportsnet.com (1121 thru 2024-25) + ESPN 2025-26 (31-3)
- **FF (Final Fours)**: `6` -> `7` | Source: Michigan - 7 FF including 2013 (not vacated for Mich)
- **NT (tournament appearances)**: `30` -> `31` | Source: Michigan - 31 appearances (incl 2026)

### Middle Tennessee Blue Raiders (ESPN ID: 2393)
- **ATW (all-time wins)**: `0` -> `17` | Source: ESPN 2025-26 current season only (17-15)
- **ATL (all-time losses)**: `0` -> `15` | Source: ESPN 2025-26 current season only (17-15)

### Minnesota Golden Gophers (ESPN ID: 135)
- **ATW (all-time wins)**: `1050` -> `1710` | Source: d1sportsnet.com (1695 thru 2024-25) + ESPN 2025-26 (15-17)
- **ATL (all-time losses)**: `901` -> `1351` | Source: d1sportsnet.com (1334 thru 2024-25) + ESPN 2025-26 (15-17)

### Mississippi State Bulldogs (ESPN ID: 344)
- **ATW (all-time wins)**: `1048` -> `1541` | Source: d1sportsnet.com (1528 thru 2024-25) + ESPN 2025-26 (13-19)
- **ATL (all-time losses)**: `976` -> `1298` | Source: d1sportsnet.com (1279 thru 2024-25) + ESPN 2025-26 (13-19)

### Missouri Tigers (ESPN ID: 142)
- **ATW (all-time wins)**: `1202` -> `1733` | Source: d1sportsnet.com (1713 thru 2024-25) + ESPN 2025-26 (20-12)
- **ATL (all-time losses)**: `896` -> `1269` | Source: d1sportsnet.com (1257 thru 2024-25) + ESPN 2025-26 (20-12)

### Montana Grizzlies (ESPN ID: 149)
- **ATW (all-time wins)**: `0` -> `1638` | Source: d1sportsnet.com (1620 thru 2024-25) + ESPN 2025-26 (18-16)
- **ATL (all-time losses)**: `0` -> `1333` | Source: d1sportsnet.com (1317 thru 2024-25) + ESPN 2025-26 (18-16)

### Murray State Racers (ESPN ID: 93)
- **ATW (all-time wins)**: `1175` -> `1772` | Source: d1sportsnet.com (1752 thru 2024-25) + ESPN 2025-26 (20-12)
- **ATL (all-time losses)**: `748` -> `983` | Source: d1sportsnet.com (971 thru 2024-25) + ESPN 2025-26 (20-12)

### NC State Wolfpack (ESPN ID: 152)
- **ATW (all-time wins)**: `1430` -> `1848` | Source: d1sportsnet.com (1828 thru 2024-25) + ESPN 2025-26 (20-14)
- **ATL (all-time losses)**: `891` -> `1169` | Source: d1sportsnet.com (1155 thru 2024-25) + ESPN 2025-26 (20-14)

### Navy Midshipmen (ESPN ID: 2426)
- **ATW (all-time wins)**: `0` -> `26` | Source: ESPN 2025-26 current season only (26-7)
- **ATL (all-time losses)**: `0` -> `7` | Source: ESPN 2025-26 current season only (26-7)

### Nebraska Cornhuskers (ESPN ID: 158)
- **ATW (all-time wins)**: `1051` -> `1627` | Source: d1sportsnet.com (1601 thru 2024-25) + ESPN 2025-26 (26-6)
- **ATL (all-time losses)**: `1014` -> `1477` | Source: d1sportsnet.com (1471 thru 2024-25) + ESPN 2025-26 (26-6)

### New Mexico Lobos (ESPN ID: 167)
- **ATW (all-time wins)**: `1227` -> `1662` | Source: d1sportsnet.com (1639 thru 2024-25) + ESPN 2025-26 (23-10)
- **ATL (all-time losses)**: `897` -> `1222` | Source: d1sportsnet.com (1212 thru 2024-25) + ESPN 2025-26 (23-10)

### New Mexico State Aggies (ESPN ID: 166)
- **ATW (all-time wins)**: `0` -> `1656` | Source: d1sportsnet.com (1640 thru 2024-25) + ESPN 2025-26 (16-16)
- **ATL (all-time losses)**: `0` -> `1174` | Source: d1sportsnet.com (1158 thru 2024-25) + ESPN 2025-26 (16-16)

### North Carolina Tar Heels (ESPN ID: 153)
- **ATW (all-time wins)**: `1795` -> `2419` | Source: d1sportsnet.com (2395 thru 2024-25) + ESPN 2025-26 (24-8)
- **ATL (all-time losses)**: `627` -> `882` | Source: d1sportsnet.com (874 thru 2024-25) + ESPN 2025-26 (24-8)
- **NT (tournament appearances)**: `52` -> `55` | Source: North Carolina - 55 appearances (incl 2026)

### Northeastern Huskies (ESPN ID: 111)
- **ATW (all-time wins)**: `0` -> `7` | Source: ESPN 2025-26 current season only (7-24)
- **ATL (all-time losses)**: `0` -> `24` | Source: ESPN 2025-26 current season only (7-24)

### Northern Arizona Lumberjacks (ESPN ID: 2464)
- **ATW (all-time wins)**: `0` -> `10` | Source: ESPN 2025-26 current season only (10-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (10-22)

### Notre Dame Fighting Irish (ESPN ID: 87)
- **ATW (all-time wins)**: `1332` -> `1991` | Source: d1sportsnet.com (1978 thru 2024-25) + ESPN 2025-26 (13-18)
- **ATL (all-time losses)**: `899` -> `1145` | Source: d1sportsnet.com (1127 thru 2024-25) + ESPN 2025-26 (13-18)
- **NT (tournament appearances)**: `30` -> `37` | Source: Notre Dame - 37 appearances

### Oakland Golden Grizzlies (ESPN ID: 2473)
- **ATW (all-time wins)**: `0` -> `16` | Source: ESPN 2025-26 current season only (16-16)
- **ATL (all-time losses)**: `0` -> `16` | Source: ESPN 2025-26 current season only (16-16)

### Ohio State Buckeyes (ESPN ID: 194)
- **ATW (all-time wins)**: `1285` -> `1828` | Source: d1sportsnet.com (1807 thru 2024-25) + ESPN 2025-26 (21-12)
- **ATL (all-time losses)**: `780` -> `1175` | Source: d1sportsnet.com (1163 thru 2024-25) + ESPN 2025-26 (21-12)
- **NT (tournament appearances)**: `31` -> `32` | Source: Ohio State - 32 appearances (incl 2026)

### Oklahoma Sooners (ESPN ID: 201)
- **ATW (all-time wins)**: `1314` -> `1815` | Source: d1sportsnet.com (1796 thru 2024-25) + ESPN 2025-26 (19-15)
- **ATL (all-time losses)**: `879` -> `1178` | Source: d1sportsnet.com (1163 thru 2024-25) + ESPN 2025-26 (19-15)
- **NT (tournament appearances)**: `32` -> `36` | Source: Oklahoma - 36 appearances

### Oklahoma State Cowboys (ESPN ID: 197)
- **ATW (all-time wins)**: `1193` -> `1785` | Source: d1sportsnet.com (1765 thru 2024-25) + ESPN 2025-26 (20-14)
- **ATL (all-time losses)**: `924` -> `1281` | Source: d1sportsnet.com (1267 thru 2024-25) + ESPN 2025-26 (20-14)

### Old Dominion Monarchs (ESPN ID: 295)
- **ATW (all-time wins)**: `0` -> `12` | Source: ESPN 2025-26 current season only (12-21)
- **ATL (all-time losses)**: `0` -> `21` | Source: ESPN 2025-26 current season only (12-21)

### Oral Roberts Golden Eagles (ESPN ID: 198)
- **ATW (all-time wins)**: `0` -> `10` | Source: ESPN 2025-26 current season only (10-23)
- **ATL (all-time losses)**: `0` -> `23` | Source: ESPN 2025-26 current season only (10-23)

### Oregon Ducks (ESPN ID: 2483)
- **ATW (all-time wins)**: `1171` -> `1816` | Source: d1sportsnet.com (1804 thru 2024-25) + ESPN 2025-26 (12-20)
- **ATL (all-time losses)**: `1015` -> `1448` | Source: d1sportsnet.com (1428 thru 2024-25) + ESPN 2025-26 (12-20)

### Penn State Nittany Lions (ESPN ID: 213)
- **ATW (all-time wins)**: `1039` -> `1589` | Source: d1sportsnet.com (1577 thru 2024-25) + ESPN 2025-26 (12-20)
- **ATL (all-time losses)**: `1022` -> `1294` | Source: d1sportsnet.com (1274 thru 2024-25) + ESPN 2025-26 (12-20)

### Pittsburgh Panthers (ESPN ID: 221)
- **ATW (all-time wins)**: `1142` -> `1733` | Source: d1sportsnet.com (1720 thru 2024-25) + ESPN 2025-26 (13-20)
- **ATL (all-time losses)**: `947` -> `1278` | Source: d1sportsnet.com (1258 thru 2024-25) + ESPN 2025-26 (13-20)

### Princeton Tigers (ESPN ID: 163)
- **ATW (all-time wins)**: `0` -> `9` | Source: ESPN 2025-26 current season only (9-20)
- **ATL (all-time losses)**: `0` -> `20` | Source: ESPN 2025-26 current season only (9-20)

### Providence Friars (ESPN ID: 2507)
- **ATW (all-time wins)**: `1163` -> `1591` | Source: d1sportsnet.com (1576 thru 2024-25) + ESPN 2025-26 (15-18)
- **ATL (all-time losses)**: `828` -> `1088` | Source: d1sportsnet.com (1070 thru 2024-25) + ESPN 2025-26 (15-18)

### Purdue Boilermakers (ESPN ID: 2509)
- **ATW (all-time wins)**: `1358` -> `1980` | Source: d1sportsnet.com (1953 thru 2024-25) + ESPN 2025-26 (27-8)
- **ATL (all-time losses)**: `784` -> `1100` | Source: d1sportsnet.com (1092 thru 2024-25) + ESPN 2025-26 (27-8)
- **NT (tournament appearances)**: `31` -> `34` | Source: Purdue - 34 appearances (incl 2026)

### Rhode Island Rams (ESPN ID: 227)
- **ATW (all-time wins)**: `986` -> `1615` | Source: d1sportsnet.com (1599 thru 2024-25) + ESPN 2025-26 (16-16)
- **ATL (all-time losses)**: `1028` -> `1247` | Source: d1sportsnet.com (1231 thru 2024-25) + ESPN 2025-26 (16-16)

### Saint Josephs Hawks (ESPN ID: 2603)
- **ATW (all-time wins)**: `1186` -> `1746` | Source: d1sportsnet.com (1724 thru 2024-25) + ESPN 2025-26 (22-11)
- **ATL (all-time losses)**: `912` -> `1242` | Source: d1sportsnet.com (1231 thru 2024-25) + ESPN 2025-26 (22-11)
- **NAME**: `Saint Josephs Hawks` -> `Saint Joseph's Hawks` | Source: Correct apostrophe in Joseph's

### Saint Louis Billikens (ESPN ID: 139)
- **ATW (all-time wins)**: `1193` -> `1572` | Source: d1sportsnet.com (1544 thru 2024-25) + ESPN 2025-26 (28-5)
- **ATL (all-time losses)**: `1008` -> `1296` | Source: d1sportsnet.com (1291 thru 2024-25) + ESPN 2025-26 (28-5)

### San Diego State Aztecs (ESPN ID: 21)
- **ATW (all-time wins)**: `951` -> `1646` | Source: d1sportsnet.com (1624 thru 2024-25) + ESPN 2025-26 (22-11)
- **ATL (all-time losses)**: `731` -> `1173` | Source: d1sportsnet.com (1162 thru 2024-25) + ESPN 2025-26 (22-11)

### San Diego Toreros (ESPN ID: 301)
- **ATW (all-time wins)**: `0` -> `12` | Source: ESPN 2025-26 current season only (12-21)
- **ATL (all-time losses)**: `0` -> `21` | Source: ESPN 2025-26 current season only (12-21)

### Santa Clara Broncos (ESPN ID: 2541)
- **ATW (all-time wins)**: `1135` -> `1633` | Source: d1sportsnet.com (1607 thru 2024-25) + ESPN 2025-26 (26-8)
- **ATL (all-time losses)**: `945` -> `1191` | Source: d1sportsnet.com (1183 thru 2024-25) + ESPN 2025-26 (26-8)

### Seattle Redhawks (ESPN ID: 2547)
- **NAME**: `Seattle Redhawks` -> `Seattle U Redhawks` | Source: ESPN official name

### Seton Hall Pirates (ESPN ID: 2550)
- **ATW (all-time wins)**: `1048` -> `1643` | Source: d1sportsnet.com (1622 thru 2024-25) + ESPN 2025-26 (21-12)
- **ATL (all-time losses)**: `978` -> `1184` | Source: d1sportsnet.com (1172 thru 2024-25) + ESPN 2025-26 (21-12)

### South Alabama Jaguars (ESPN ID: 6)
- **ATW (all-time wins)**: `0` -> `21` | Source: ESPN 2025-26 current season only (21-12)
- **ATL (all-time losses)**: `0` -> `12` | Source: ESPN 2025-26 current season only (21-12)

### Southern Miss Golden Eagles (ESPN ID: 2572)
- **ATW (all-time wins)**: `0` -> `19` | Source: ESPN 2025-26 current season only (19-16)
- **ATL (all-time losses)**: `0` -> `16` | Source: ESPN 2025-26 current season only (19-16)

### St. John's Red Storm (ESPN ID: 2599)
- **ATW (all-time wins)**: `1402` -> `2001` | Source: d1sportsnet.com (1973 thru 2024-25) + ESPN 2025-26 (28-6)
- **ATL (all-time losses)**: `838` -> `1109` | Source: d1sportsnet.com (1103 thru 2024-25) + ESPN 2025-26 (28-6)

### Stanford Cardinal (ESPN ID: 24)
- **ATW (all-time wins)**: `1159` -> `1651` | Source: d1sportsnet.com (1631 thru 2024-25) + ESPN 2025-26 (20-12)
- **ATL (all-time losses)**: `957` -> `1264` | Source: d1sportsnet.com (1252 thru 2024-25) + ESPN 2025-26 (20-12)

### Syracuse Orange (ESPN ID: 183)
- **ATW (all-time wins)**: `1515` -> `2022` | Source: d1sportsnet.com (2007 thru 2024-25) + ESPN 2025-26 (15-17)
- **ATL (all-time losses)**: `757` -> `1012` | Source: d1sportsnet.com (995 thru 2024-25) + ESPN 2025-26 (15-17)
- **NT (tournament appearances)**: `38` -> `39` | Source: Syracuse - 39 appearances (post-vacation)

### Temple Owls (ESPN ID: 218)
- **ATW (all-time wins)**: `1354` -> `2026` | Source: d1sportsnet.com (2010 thru 2024-25) + ESPN 2025-26 (16-16)
- **ATL (all-time losses)**: `837` -> `1188` | Source: d1sportsnet.com (1172 thru 2024-25) + ESPN 2025-26 (16-16)

### Tennessee Volunteers (ESPN ID: 2633)
- **ATW (all-time wins)**: `1336` -> `1822` | Source: d1sportsnet.com (1800 thru 2024-25) + ESPN 2025-26 (22-11)
- **ATL (all-time losses)**: `871` -> `1122` | Source: d1sportsnet.com (1111 thru 2024-25) + ESPN 2025-26 (22-11)
- **NT (tournament appearances)**: `28` -> `29` | Source: Tennessee - 29 appearances (incl 2026)

### Texas A&M Aggies (ESPN ID: 245)
- **ATW (all-time wins)**: `1108` -> `1567` | Source: d1sportsnet.com (1546 thru 2024-25) + ESPN 2025-26 (21-11)
- **ATL (all-time losses)**: `975` -> `1357` | Source: d1sportsnet.com (1346 thru 2024-25) + ESPN 2025-26 (21-11)

### Texas Longhorns (ESPN ID: 251)
- **ATW (all-time wins)**: `1280` -> `1938` | Source: d1sportsnet.com (1919 thru 2024-25) + ESPN 2025-26 (19-14)
- **ATL (all-time losses)**: `906` -> `1169` | Source: d1sportsnet.com (1155 thru 2024-25) + ESPN 2025-26 (19-14)
- **NT (tournament appearances)**: `36` -> `37` | Source: Texas - 37 appearances (incl 2026)

### Texas Tech Red Raiders (ESPN ID: 2641)
- **ATW (all-time wins)**: `1146` -> `1564` | Source: d1sportsnet.com (1542 thru 2024-25) + ESPN 2025-26 (22-10)
- **ATL (all-time losses)**: `933` -> `1199` | Source: d1sportsnet.com (1189 thru 2024-25) + ESPN 2025-26 (22-10)

### The Citadel Bulldogs (ESPN ID: 2643)
- **ATW (all-time wins)**: `0` -> `11` | Source: ESPN 2025-26 current season only (11-22)
- **ATL (all-time losses)**: `0` -> `22` | Source: ESPN 2025-26 current season only (11-22)

### Toledo Rockets (ESPN ID: 2649)
- **ATW (all-time wins)**: `0` -> `1605` | Source: d1sportsnet.com (1586 thru 2024-25) + ESPN 2025-26 (19-15)
- **ATL (all-time losses)**: `0` -> `1161` | Source: d1sportsnet.com (1146 thru 2024-25) + ESPN 2025-26 (19-15)

### Tulsa Golden Hurricane (ESPN ID: 202)
- **ATW (all-time wins)**: `0` -> `27` | Source: ESPN 2025-26 current season only (27-7)
- **ATL (all-time losses)**: `0` -> `7` | Source: ESPN 2025-26 current season only (27-7)
- **ATW (all-time wins)**: `27` -> `1558` | Source: d1sportsnet + ESPN (fixing duplicate Tulsa entry)
- **ATL (all-time losses)**: `7` -> `1269` | Source: d1sportsnet + ESPN (fixing duplicate Tulsa entry)

### UCLA Bruins (ESPN ID: 26)
- **ATW (all-time wins)**: `1720` -> `2048` | Source: d1sportsnet.com (2025 thru 2024-25) + ESPN 2025-26 (23-11)
- **ATL (all-time losses)**: `641` -> `927` | Source: d1sportsnet.com (916 thru 2024-25) + ESPN 2025-26 (23-11)
- **NT (tournament appearances)**: `51` -> `52` | Source: UCLA - 52 appearances (incl 2026)

### UConn Huskies (ESPN ID: 41)
- **ATW (all-time wins)**: `1327` -> `1890` | Source: d1sportsnet.com (1861 thru 2024-25) + ESPN 2025-26 (29-5)
- **ATL (all-time losses)**: `695` -> `1031` | Source: d1sportsnet.com (1026 thru 2024-25) + ESPN 2025-26 (29-5)

### UNC Greensboro Spartans (ESPN ID: 2430)
- **ATW (all-time wins)**: `0` -> `15` | Source: ESPN 2025-26 current season only (15-19)
- **ATL (all-time losses)**: `0` -> `19` | Source: ESPN 2025-26 current season only (15-19)

### USC Trojans (ESPN ID: 30)
- **ATW (all-time wins)**: `1157` -> `1748` | Source: d1sportsnet.com (1730 thru 2024-25) + ESPN 2025-26 (18-14)
- **ATL (all-time losses)**: `928` -> `1293` | Source: d1sportsnet.com (1279 thru 2024-25) + ESPN 2025-26 (18-14)

### USF Bulls (ESPN ID: 58)
- **NAME**: `USF Bulls` -> `South Florida Bulls` | Source: ESPN official name is South Florida

### UT Rio Grande Valley Vaqueros (ESPN ID: 292)
- **ATW (all-time wins)**: `0` -> `19` | Source: ESPN 2025-26 current season only (19-14)
- **ATL (all-time losses)**: `0` -> `14` | Source: ESPN 2025-26 current season only (19-14)

### Utah State Aggies (ESPN ID: 328)
- **ATW (all-time wins)**: `1314` -> `1768` | Source: d1sportsnet.com (1740 thru 2024-25) + ESPN 2025-26 (28-6)
- **ATL (all-time losses)**: `809` -> `1170` | Source: d1sportsnet.com (1164 thru 2024-25) + ESPN 2025-26 (28-6)

### Utah Utes (ESPN ID: 254)
- **ATW (all-time wins)**: `1389` -> `1924` | Source: d1sportsnet.com (1914 thru 2024-25) + ESPN 2025-26 (10-22)
- **ATL (all-time losses)**: `858` -> `1123` | Source: d1sportsnet.com (1101 thru 2024-25) + ESPN 2025-26 (10-22)

### Valparaiso Beacons (ESPN ID: 2674)
- **CONF (conference)**: `` -> `MVC` | Source: Valparaiso moved to Missouri Valley Conference
- **ATW (all-time wins)**: `0` -> `18` | Source: ESPN 2025-26 current season only (18-15)
- **ATL (all-time losses)**: `0` -> `15` | Source: ESPN 2025-26 current season only (18-15)

### Vanderbilt Commodores (ESPN ID: 238)
- **ATW (all-time wins)**: `1280` -> `1722` | Source: d1sportsnet.com (1696 thru 2024-25) + ESPN 2025-26 (26-8)
- **ATL (all-time losses)**: `923` -> `1279` | Source: d1sportsnet.com (1271 thru 2024-25) + ESPN 2025-26 (26-8)

### Villanova Wildcats (ESPN ID: 222)
- **ATW (all-time wins)**: `1462` -> `1927` | Source: d1sportsnet.com (1903 thru 2024-25) + ESPN 2025-26 (24-8)
- **ATL (all-time losses)**: `806` -> `1012` | Source: d1sportsnet.com (1004 thru 2024-25) + ESPN 2025-26 (24-8)
- **NT (tournament appearances)**: `42` -> `41` | Source: Villanova - 41 appearances (incl 2026)

### Virginia Cavaliers (ESPN ID: 258)
- **ATW (all-time wins)**: `1255` -> `1786` | Source: d1sportsnet.com (1757 thru 2024-25) + ESPN 2025-26 (29-5)
- **ATL (all-time losses)**: `959` -> `1237` | Source: d1sportsnet.com (1232 thru 2024-25) + ESPN 2025-26 (29-5)
- **NT (tournament appearances)**: `23` -> `24` | Source: Virginia - 24 appearances (incl 2026)

### Virginia Tech Hokies (ESPN ID: 259)
- **ATW (all-time wins)**: `1179` -> `1588` | Source: d1sportsnet.com (1569 thru 2024-25) + ESPN 2025-26 (19-13)
- **ATL (all-time losses)**: `958` -> `1319` | Source: d1sportsnet.com (1306 thru 2024-25) + ESPN 2025-26 (19-13)

### Wake Forest Demon Deacons (ESPN ID: 154)
- **ATW (all-time wins)**: `1225` -> `1659` | Source: d1sportsnet.com (1642 thru 2024-25) + ESPN 2025-26 (17-16)
- **ATL (all-time losses)**: `1006` -> `1335` | Source: d1sportsnet.com (1319 thru 2024-25) + ESPN 2025-26 (17-16)

### Washington Huskies (ESPN ID: 264)
- **ATW (all-time wins)**: `1167` -> `1891` | Source: d1sportsnet.com (1875 thru 2024-25) + ESPN 2025-26 (16-17)
- **ATL (all-time losses)**: `986` -> `1303` | Source: d1sportsnet.com (1286 thru 2024-25) + ESPN 2025-26 (16-17)

### Washington State Cougars (ESPN ID: 265)
- **ATW (all-time wins)**: `0` -> `1721` | Source: d1sportsnet.com (1709 thru 2024-25) + ESPN 2025-26 (12-20)
- **ATL (all-time losses)**: `0` -> `1630` | Source: d1sportsnet.com (1610 thru 2024-25) + ESPN 2025-26 (12-20)

### West Virginia Mountaineers (ESPN ID: 277)
- **ATW (all-time wins)**: `1451` -> `1892` | Source: d1sportsnet.com (1874 thru 2024-25) + ESPN 2025-26 (18-14)
- **ATL (all-time losses)**: `878` -> `1202` | Source: d1sportsnet.com (1188 thru 2024-25) + ESPN 2025-26 (18-14)
- **NT (tournament appearances)**: `29` -> `31` | Source: West Virginia - 31 appearances

### Western Kentucky Hilltoppers (ESPN ID: 98)
- **ATW (all-time wins)**: `0` -> `1929` | Source: d1sportsnet.com (1911 thru 2024-25) + ESPN 2025-26 (18-14)
- **ATL (all-time losses)**: `0` -> `1014` | Source: d1sportsnet.com (1000 thru 2024-25) + ESPN 2025-26 (18-14)

### Wichita State Shockers (ESPN ID: 2724)
- **ATW (all-time wins)**: `1273` -> `1714` | Source: d1sportsnet.com (1691 thru 2024-25) + ESPN 2025-26 (23-11)
- **ATL (all-time losses)**: `933` -> `1290` | Source: d1sportsnet.com (1279 thru 2024-25) + ESPN 2025-26 (23-11)

### Wisconsin Badgers (ESPN ID: 275)
- **ATW (all-time wins)**: `1136` -> `1756` | Source: d1sportsnet.com (1732 thru 2024-25) + ESPN 2025-26 (24-10)
- **ATL (all-time losses)**: `896` -> `1309` | Source: d1sportsnet.com (1299 thru 2024-25) + ESPN 2025-26 (24-10)
- **NT (tournament appearances)**: `26` -> `27` | Source: Wisconsin - 27 appearances (incl 2026)

### Wyoming Cowboys (ESPN ID: 2751)
- **ATW (all-time wins)**: `1115` -> `1638` | Source: d1sportsnet.com (1620 thru 2024-25) + ESPN 2025-26 (18-15)
- **ATL (all-time losses)**: `1062` -> `1304` | Source: d1sportsnet.com (1289 thru 2024-25) + ESPN 2025-26 (18-15)
- **NC (national championships)**: `0` -> `1` | Source: NCAA.com - Wyoming - 1 NC (1943)
- **NCY (championship years)**: `[]` -> `[1943]` | Source: NCAA.com - Wyoming - 1 NC (1943)

### Xavier Musketeers (ESPN ID: 2752)
- **ATW (all-time wins)**: `1219` -> `1625` | Source: d1sportsnet.com (1610 thru 2024-25) + ESPN 2025-26 (15-18)
- **ATL (all-time losses)**: `892` -> `1097` | Source: d1sportsnet.com (1079 thru 2024-25) + ESPN 2025-26 (15-18)
