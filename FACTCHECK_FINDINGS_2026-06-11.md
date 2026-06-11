# Narrative Fact-Check Findings — 2026-06-11 (blocks 1-3: top 30 programs)

Agent-verified against data.json/seasons.json + web sources. **For Josh review — no narrative text has been changed.**
Verdict counts: 32 findings, 11/30 teams clean.

## UCLA Bruins — `blurb` [WRONG]
> Before Wooden arrived in 1948, UCLA had never won a conference title

**Problem:** Provably false. UCLA had two conference championship seasons in the 18 years before Wooden, and won the Southern California Intercollegiate Athletic Conference in 1927. Wikipedia's UCLA basketball history states the program 'had not won a conference title of any sort since winning the Southern California Intercollegiate Athletic Conference in 1927' — i.e., it HAD won conference titles pre-Wooden.
**Suggested fix:** Change to something like 'Before Wooden arrived in 1948, UCLA had won just two conference titles in the previous 18 years' or 'had not won a conference title since 1927'.
**Sources:** https://en.wikipedia.org/wiki/UCLA_Bruins_men's_basketball · https://en.wikipedia.org/wiki/John_Wooden

## UCLA Bruins — `blurb` [WRONG]
> once lost 39 straight games to rival USC

**Problem:** No source supports 39. The documented streak is USC winning 42 consecutive games over UCLA from 1932 to 1943 (broken by a 42-37 UCLA win), which stood as the NCAA record for consecutive wins by one team over another until 1980. The '39' figure appears fabricated or garbled.
**Suggested fix:** Change to 'once lost 42 straight games to rival USC (1932-1943)'.
**Sources:** https://lasportshub.com/2012/01/13/a-history-of-the-ucla-usc-basketball-rivalry/ · https://en.wikipedia.org/wiki/UCLA%E2%80%93USC_rivalry

## Kentucky Wildcats — `funFact` [WRONG]
> Kentucky has led the nation in home attendance since 1976 and won the national attendance title a record 25 times

**Problem:** Two problems in one sentence. (1) 'led the nation... since 1976' implies every season, but Syracuse led the nation 16 times in that span, including 11 straight years 1985-1995. (2) The count of 25 is wrong/stale: NCAA attendance records (per NCAA.com's 2023 attendance review) credit Kentucky with leading the nation 29 times since 1976. Note this also contradicts the Syracuse entry in the same file, which claims Syracuse 'has led the nation in attendance 25 times' — both entries claim ~25 and both are wrong.
**Suggested fix:** Change to 'Kentucky has won the national attendance title 29 times since Rupp Arena opened in 1976, more than any other program'. Verify the current count against the latest NCAA attendance report before publishing.
**Sources:** https://www.ncaa.com/news/basketball-men/article/2023-05-26/10-lessons-learned-years-mens-college-basketball-attendance-numbers · http://fs.ncaa.org/Docs/stats/m_basketball_RB/Reports/attendanceYBYtop25.pdf · https://www.ncaa.com/news/basketball-men/article/2014-06-13/big-ten-sets-attendance-mark-conference-again-leads-nation

## Kentucky Wildcats — `blurb` [STALE]
> has a .892 all-time home winning percentage

**Problem:** Stale figure. UK Athletics currently lists Kentucky's all-time Rupp Arena record as 486-61, a .888 winning percentage. The .892 figure was true at some point but home losses in recent seasons have pulled it down, and any hardcoded percentage will keep drifting.
**Suggested fix:** Update to .888 (486-61) or soften to 'has won nearly 89% of its games' / 'one of the highest home winning percentages in the sport'.
**Sources:** http://www.bigbluehistory.net/bb/Statistics/arenarupparena.html · https://en.wikipedia.org/wiki/Rupp_Arena

## Duke Blue Devils — `blurb` [MISLEADING]
> The 'Blue Devils' nickname was adopted in 1924

**Problem:** Internally inconsistent with this same entry's mascotOrigin field, which says 'chosen by student newspaper editors in 1923'. Sources (Duke/goduke.com, Wikipedia): Trinity Chronicle editors William Lander and Mike Bradshaw began using 'Blue Devils' during the 1922-23 academic year, and it caught on from 1923. '1924' is at best the tail end of the 1923-24 school year and conflicts with the entry's own mascot field.
**Suggested fix:** Change blurb to 'adopted in 1923' (or '1922-23') to match the mascotOrigin field and standard sources.
**Sources:** https://goduke.com/sports/2006/2/21/story_of_blue_devil.aspx · https://en.wikipedia.org/wiki/Duke_Blue_Devils

## Duke Blue Devils — `blurb` [MISLEADING]
> Under Mike Krzyzewski, Duke won five national championships and became synonymous with college basketball excellence, producing six first-overall NBA draft picks.

**Problem:** Misleading attribution. Duke has six No. 1 overall picks (Art Heyman 1963, Elton Brand 1999, Kyrie Irving 2011, Zion Williamson 2019, Paolo Banchero 2022, Cooper Flagg 2025), but only four came under Krzyzewski — Heyman predates him and Flagg played for Jon Scheyer. The sentence structure credits all six to the Krzyzewski era. The funFact field's school-level version of this claim ('six players selected first overall... the most of any school') is correct.
**Suggested fix:** Detach the picks claim from Krzyzewski, e.g. '...synonymous with college basketball excellence. The program has produced six first-overall NBA draft picks, the most of any school.'
**Sources:** https://en.wikipedia.org/wiki/List_of_first_overall_NBA_draft_picks · https://www.espn.com/mens-college-basketball/story/_/id/40430005/which-colleges-produced-most-no1-nba-draft-picks · https://www.ncaa.com/news/basketball-men/article/2025-06-25/every-nba-draft-no-1-overall-pick-and-where-they-went-college

## Duke Blue Devils — `funFact` [STALE]
> Duke holds the best NCAA tournament winning percentage (.755) in history

**Problem:** Stale number. Duke does still hold the best NCAA tournament winning percentage, but .755 dates from around 2021 (114-38). ESPN's 2025 March Madness history lists Duke at 126-42 (about .750), and the 2025 Final Four run moved it again. The 'best in history' part remains true; the hardcoded .755 does not.
**Suggested fix:** Update the percentage to the current figure or drop the decimal, e.g. 'Duke holds the best NCAA tournament winning percentage in history (roughly .750)'.
**Sources:** https://www.espn.com/mens-college-basketball/story/_/id/44239878/duke-march-madness-history-men-ncaa-tournament-stats · https://en.wikipedia.org/wiki/Duke_Blue_Devils_men's_basketball

## Kansas Jayhawks — `funFact` [WRONG]
> Kansas's coaching lineage is unmatched: Naismith coached Allen, who coached Dean Smith and Adolph Rupp — between them, they won over 3,000 games and multiple national titles

**Problem:** The arithmetic fails. Career wins: Naismith ~55, Phog Allen 746, Adolph Rupp 876, Dean Smith 879 — a combined total of roughly 2,556, well short of 'over 3,000'. The lineage itself and 'multiple national titles' are accurate (Allen 1952, Rupp 4, Smith 2).
**Suggested fix:** Change to 'they combined for more than 2,500 wins' or 'nearly 2,600 wins'.
**Sources:** https://en.wikipedia.org/wiki/Phog_Allen · https://en.wikipedia.org/wiki/Adolph_Rupp · https://en.wikipedia.org/wiki/Dean_Smith

## Indiana Hoosiers — `mascotOrigin` [WRONG]
> The term 'Hoosier' has been associated with Indiana residents since the 1840s, though its exact origin remains debated among historians

**Problem:** Off by a decade. The Indiana Historical Bureau and IU archives document the word in widespread use by the early 1830s: earliest known written use in a letter dated February 11, 1831, and popularized by John Finley's poem 'The Hoosier's Nest' published January 1, 1833. The 'origin remains debated' part is accurate.
**Suggested fix:** Change '1840s' to '1830s'.
**Sources:** https://www.in.gov/history/about-indiana-history-and-trivia/emblems-and-symbols/what-is-a-hoosier/ · https://blog.history.in.gov/the-word-hoosier-an-origin-story/

## Villanova Wildcats — `mascotOrigin` [WRONG]
> The 'Wildcats' nickname has been used since the early days of the program, though the exact reason for its selection is lost to history

**Problem:** The origin is not lost to history — it is well documented by Villanova itself. In 1926 a university-wide contest was held to pick a mascot, and 'Wildcats' was the suggestion of Edward Hunsinger, a former Notre Dame All-American who had just joined Villanova's football staff as an assistant coach. Also, the basketball program began in 1920, so the nickname (1926) does not date to 'the early days of the program' in the strictest sense.
**Suggested fix:** Replace with the documented story: adopted via a 1926 campus-wide contest, suggested by assistant football coach Edward Hunsinger, formerly of Notre Dame's 'Four Horsemen'-era teams.
**Sources:** https://villanova.com/sports/2018/6/18/trads-nova-mascot-html · https://exhibits.library.villanova.edu/wildcats-past-and-present/wildcat

## Syracuse Orange — `blurb` [WRONG]
> ranks fifth all-time in total wins among NCAA programs

**Problem:** Contradicts the site's own data and external records. In this repo's data.json (H, wins index 4), Syracuse's 2,022 wins rank 8th — behind Kentucky, Kansas, North Carolina, Duke, UCLA, St. John's, and Temple. Wikipedia's most-victories list has Syracuse 6th even when counting the 101 wins the NCAA vacated in 2015. Syracuse was ~5th years ago, before the vacated wins and recent decline, so this reads as stale copy carried forward.
**Suggested fix:** Change to 'ranks among the top 10 all-time in total wins' or compute the rank dynamically from data.json instead of hardcoding it.
**Sources:** /Users/joshdavis/Projects/hoopsipedia/data.json · https://en.wikipedia.org/wiki/List_of_teams_with_the_most_victories_in_NCAA_Division_I_men's_college_basketball · https://en.wikipedia.org/wiki/Syracuse_Orange_men's_basketball

## Syracuse Orange — `blurb` [WRONG]
> Syracuse has led the nation in attendance 25 times

**Problem:** Overstated. NCAA attendance records (per NCAA.com's 2023 review) credit Syracuse with leading the nation 16 times since 1976 (including 11 straight from 1985-1995), versus Kentucky's 29. This claim also directly contradicts the Kentucky entry in the same file, which calls 25 attendance titles 'a record' for Kentucky — the two entries cannot both be right, and per NCAA data neither is.
**Suggested fix:** Change to 'Syracuse has led the nation in attendance 16 times, including 11 straight seasons from 1985 to 1995'. Verify against the latest NCAA attendance report.
**Sources:** https://www.ncaa.com/news/basketball-men/article/2023-05-26/10-lessons-learned-years-mens-college-basketball-attendance-numbers · http://fs.ncaa.org/Docs/stats/m_basketball_RB/Reports/attendanceYBYtop25.pdf

**Clean (no findings):** North Carolina, UConn, Louisville

## Houston Cougars — `blurb` [WRONG]
> Houston won its first NCAA Championship in 2025, finally breaking through after heartbreaking losses in the 1980s.

**Problem:** Houston did NOT win the 2025 title. Florida beat Houston 65-63 in the April 7, 2025 national championship game. Internally inconsistent with data.json H (Houston NC=0, NCY=[]) and seasons.json 2024-25 ('Lost NCAA Tournament National Final'). Florida's data.json NCY correctly includes 2025.
**Suggested fix:** Replace with something like: 'Houston is still chasing its first NCAA Championship, having reached seven Final Fours and lost national title games in 1983, 1984, and 2025 — the latter a 65-63 heartbreaker to Florida.'
**Sources:** https://www.espn.com/mens-college-basketball/game/_/gameId/401746082/florida-houston · https://en.wikipedia.org/wiki/2025_NCAA_Division_I_men's_basketball_championship_game · /Users/joshdavis/Projects/hoopsipedia/data.json (H['248'] NC=0) · /Users/joshdavis/Projects/hoopsipedia/seasons.json (248, 2024-25)

## Michigan Wolverines — `blurb` [STALE]
> Michigan's basketball program began in 1909 and won its sole NCAA Championship in 1989 when interim coach Steve Fisher guided the team to an overtime title win on Rumeal Robinson's clutch free throws.

**Problem:** Stale: Michigan won a second NCAA Championship in April 2026 under Dusty May, beating UConn 69-63. data.json H NCY=[1989, 2026] already reflects this, so 'sole NCAA Championship in 1989' contradicts the site's own data.
**Suggested fix:** Change 'won its sole NCAA Championship in 1989' to 'won its first NCAA Championship in 1989' and add a sentence noting the second title in 2026 under Dusty May (69-63 over UConn), the program's first championship in 37 years.
**Sources:** https://www.ncaa.com/news/basketball-men/article/2026-04-06/2026-michigan-beats-uconn-wins-2026-mens-basketball-national-championship · https://www.cbsnews.com/news/ncaa-mens-basketball-championship-michigan-uconn-2026-march-madness/ · /Users/joshdavis/Projects/hoopsipedia/data.json (H['130'] NCY=[1989,2026])

## Michigan State Spartans — `blurb` [WRONG]
> Under Tom Izzo, who arrived in 1995, Michigan State has reached ten Final Fours and won a second national title in 2000.

**Problem:** Conflates program total with Izzo's record. The program has 10 Final Fours per data.json (FF=8 index... H index 8 = 10), but only 8 came under Izzo (1999, 2000, 2001, 2005, 2009, 2010, 2015, 2019 per seasons.json); 1957 and 1979 were under Forddy Anderson and Jud Heathcote. External sources confirm Izzo has 8 Final Fours.
**Suggested fix:** Change to 'Under Tom Izzo, who arrived in 1995, Michigan State has reached eight Final Fours — ten in program history — and won a second national title in 2000.'
**Sources:** https://www.si.com/college/michiganstate/basketball/msu-spartans-tom-izzo-all-time-ncaa-tournament-record-best-finishes · https://www.hoophall.com/hall-of-famers/tom-izzo · /Users/joshdavis/Projects/hoopsipedia/seasons.json (127: Izzo-era national semifinal/final appearances = 8)

## Michigan State Spartans — `funFact` [WRONG]
> Tom Izzo has led Michigan State to ten Final Fours, tied for sixth most all-time, and ESPN named the Spartans the best team of the 2000s decade

**Problem:** Two errors: (1) Izzo has led MSU to eight Final Fours, not ten (the program's ten include 1957 and 1979, pre-Izzo), and eight is the fifth-most of any coach all-time, not 'tied for sixth.' (2) The ESPN claim is distorted — ESPN's seven-person panel named North Carolina the program of the decade (5 of 7 votes); it was one writer, Andy Katz, who individually picked Michigan State.
**Suggested fix:** Rewrite to: 'Tom Izzo has led Michigan State to eight Final Fours, the fifth most by any coach all-time, and ESPN's Andy Katz picked the Spartans as his college basketball team of the 2000s decade.'
**Sources:** https://www.si.com/college/michiganstate/basketball/msu-spartans-tom-izzo-all-time-ncaa-tournament-record-best-finishes · https://www.espn.com/mens-college-basketball/news/story?id=4783700 · /Users/joshdavis/Projects/hoopsipedia/seasons.json (127)

## Michigan State Spartans — `blurb` [MISLEADING]
> ESPN named MSU the best basketball team of the 2000s decade.

**Problem:** Misleading attribution. ESPN's panel of seven named North Carolina the program of the decade for the 2000s; Michigan State tied for third in the panel rankings. Only Andy Katz individually picked MSU as his team of the decade.
**Suggested fix:** Change to 'ESPN's Andy Katz picked MSU as his team of the 2000s decade' or drop the sentence.
**Sources:** https://www.espn.com/mens-college-basketball/news/story?id=4783700

## Cincinnati Bearcats — `blurb` [WRONG]
> Under Ed Jucker, Cincinnati won back-to-back NCAA Championships in 1961 and 1962, becoming the last team to win consecutive titles until Duke in 1991-92.

**Problem:** Provably false. UCLA won consecutive titles in 1964-65 and seven straight from 1967-1973. Duke in 1991-92 was the first repeat champion since UCLA (1973), not since Cincinnati (1962).
**Suggested fix:** Change to '...won back-to-back NCAA Championships in 1961 and 1962, and nearly a third straight in 1963, falling to Loyola Chicago in overtime in the final.' (Or simply delete the 'last team until Duke' clause.)
**Sources:** https://en.wikipedia.org/wiki/List_of_NCAA_Division_I_men's_basketball_champions

## Cincinnati Bearcats — `iconicMoment` [WRONG]
> Winning back-to-back NCAA Championships in 1961 and 1962 under coach Ed Jucker, the last team to repeat until Duke thirty years later

**Problem:** Same error as blurb: UCLA repeated in 1964-65 and won seven consecutive titles 1967-1973, all between Cincinnati's repeat and Duke's. Duke was the first repeat champion since UCLA, not since Cincinnati.
**Suggested fix:** Change to 'Winning back-to-back NCAA Championships in 1961 and 1962 under coach Ed Jucker, reaching a third straight title game in 1963'
**Sources:** https://en.wikipedia.org/wiki/List_of_NCAA_Division_I_men's_basketball_champions

## Cincinnati Bearcats — `mascotOrigin` [WRONG]
> Adopted in 1914 when cheerleader Norman 'Pat' Lyon combined 'bear' and 'cats' after a cartoon of a ferocious bear-cat hybrid appeared in the school newspaper

**Problem:** Origin story is told backwards and misstates the wordplay. During the Oct 31, 1914 game against Kentucky, cheerleader Norman 'Pat' Lyon led the chant 'They may be Wildcats, but we have a Baehr-cat on our side' — a pun on fullback Leonard K. 'Teddy' Baehr's name, not a combination of 'bear' and 'cats.' The cartoon (by John 'Paddy' Reece, depicting a 'Cincinnati Bear Cat' chasing a Kentucky Wildcat) was published in the student newspaper on Nov 3, AFTER the game, memorializing the cheer — it did not inspire it.
**Suggested fix:** Rewrite: 'Born Oct 31, 1914, when cheerleader Norman "Pat" Lyon punned on fullback Teddy Baehr's name — "They may be Wildcats, but we have a Baehr-cat on our side" — during a win over Kentucky; a student-newspaper cartoon of a "Cincinnati Bear Cat" days later cemented the name.' Note: the blurb repeats the same reversed cartoon-first version ('The Bearcats name was adopted in 1914 when a cheerleader combined bear and cats after a cartoon of a ferocious bear-cat hybrid') and should be fixed too.
**Sources:** https://magazine.uc.edu/issues/0315/teddy_baehr.html · https://gobearcats.com/what-is-a-bearcat · https://en.wikipedia.org/wiki/Cincinnati_Bearcats

## Gonzaga Bulldogs — `funFact` [WRONG]
> When Gonzaga opened McCarthey Athletic Center in 2004, the Bulldogs won 100 consecutive home games there, the longest such streak in the NCAA at the time

**Problem:** Provably false. Gonzaga opened McCarthey with a 38-game home winning streak (50 straight home wins counting the final 12 at the old Charlotte Y. Martin Centre), snapped by Santa Clara on Feb 12, 2007. The building's longest-ever streak is 75 games (2018-2023, snapped by Loyola Marymount). It was never 100.
**Suggested fix:** Replace with: 'Gonzaga opened McCarthey Athletic Center in 2004 with a 38-game home winning streak — and later won 75 straight there from 2018 to 2023, going more than five years without a home loss.'
**Sources:** https://en.wikipedia.org/wiki/McCarthey_Athletic_Center · https://www.cbssports.com/college-basketball/news/gonzagas-76-game-home-winning-streak-snapped-in-shocking-upset-by-loyola-marymount/

## Gonzaga Bulldogs — `blurb` [MISLEADING]
> Under Mark Few, who took over in 1999, Gonzaga has become one of the most consistent programs in the nation, including a 31-0 regular season in 2021.

**Problem:** The 31-0 figure was not a regular season — it was Gonzaga's overall record entering the 2021 national championship game (including WCC tournament and five NCAA tournament wins); they finished 31-1 after losing to Baylor (seasons.json 2020-21 record: 31-1). The 2020-21 regular season was 24-0 (26-0 with the WCC tournament).
**Suggested fix:** Change to '...including a 31-0 start in 2020-21 before falling to Baylor in the national championship game.'
**Sources:** https://en.wikipedia.org/wiki/2020%E2%80%9321_Gonzaga_Bulldogs_men's_basketball_team · /Users/joshdavis/Projects/hoopsipedia/seasons.json (2250, 2020-21: 31-1, Lost NCAA Tournament National Final)

## Kansas State Wildcats — `blurb` [WRONG]
> Kansas State has a proud basketball history, reaching the Final Four four times and finishing as national runner-up twice (1951, 1958).

**Problem:** K-State was national runner-up only once, in 1951 (lost the final to Kentucky 68-58). In 1958 they lost the national SEMIFINAL to Seattle and finished fourth after losing the consolation game to Temple. seasons.json confirms: 1957-58 = 'Lost NCAA Tournament National Semifinal'; only 1950-51 = 'Lost NCAA Tournament National Final'. The four Final Fours (1948, 1951, 1958, 1964) part is correct.
**Suggested fix:** Change to '...reaching the Final Four four times (1948, 1951, 1958, 1964) and finishing as national runner-up in 1951.'
**Sources:** https://en.wikipedia.org/wiki/1958_NCAA_University_Division_basketball_tournament · https://en.wikipedia.org/wiki/1951_NCAA_basketball_tournament · /Users/joshdavis/Projects/hoopsipedia/seasons.json (2306: 1950-51 National Final, 1957-58 National Semifinal)

## Florida Gators — `mascotOrigin` [MISLEADING]
> Chosen in 1911 as a tribute to the alligators native to Florida's Everglades region

**Problem:** The Everglades detail is unsupported by any documented account. The accepted origin: in 1907-08 Gainesville merchant Phillip Miller and his son Austin had alligator-emblem pennants made (Austin chose it because the alligator was native to the state of Florida and no other school used it); the 'Alligators' nickname first appeared in print attached to the team in 1911. No source ties the choice to the Everglades — Gainesville is in north-central Florida. The blurb repeats the same claim ('an homage to the alligators native to the Everglades region').
**Suggested fix:** Change to 'Popularized by 1908 alligator-emblem pennants sold by Gainesville merchant Phillip Miller and his son Austin, who picked the alligator because it was native to Florida and unclaimed by any other school; the nickname stuck to the team by 1911.' Apply the same fix to the blurb sentence.
**Sources:** https://floridagators.com/sports/2015/12/10/_overview_p_name · https://en.wikipedia.org/wiki/Florida_Gators

## Florida Gators — `iconicMoment` [MISLEADING]
> Winning back-to-back NCAA Championships in 2006 and 2007 with the same starting five — the first team to accomplish this since Duke in 1991-92

**Problem:** Distorted comparison: Florida was the first team EVER to repeat with the same starting five (Noah, Horford, Brewer, Humphrey, Green) — Duke repeated in 1991-92 but with a different starting lineup. As written, it implies Duke had previously repeated with the same starting five. (Florida was the first repeat champion of any kind since Duke — the blurb states the same-lineup feat correctly.)
**Suggested fix:** Change to 'Winning back-to-back NCAA Championships in 2006 and 2007 — the first repeat champion since Duke in 1991-92, and the first team ever to do it with the same starting five.'
**Sources:** https://en.wikipedia.org/wiki/2007_NCAA_Division_I_men's_basketball_championship_game · https://en.wikipedia.org/wiki/2007%E2%80%9308_Florida_Gators_men's_basketball_team

**Clean (no findings):** Arizona Wildcats, Ohio State Buckeyes, Arkansas Razorbacks

## Illinois Fighting Illini — `funFact` [WRONG]
> Despite being ranked No. 1 and undefeated, the 1943 'Whiz Kids' team opted not to play in the NCAA Tournament when three of its five starters were called to duty in World War II

**Problem:** The 1942-43 Whiz Kids were NOT undefeated — they finished 17-1 (12-0 Big Ten). 'Ranked No. 1' is also shaky: the AP basketball poll did not exist until 1949; the No. 1 status is the retroactive Premo-Porretta Power Poll. The WWII/three-starters-drafted part (Mathisen, Menke, Smiley) is accurate.
**Suggested fix:** Change to: 'Despite a 17-1 record and recognition as the nation's best team, the 1943 Whiz Kids opted not to play in the NCAA Tournament when three of their five starters were called to duty in World War II.'
**Sources:** https://en.wikipedia.org/wiki/1942%E2%80%9343_Illinois_Fighting_Illini_men's_basketball_team · https://www.news-gazette.com/sports/illini-legends-lists-lore-the-whiz-kids-and-the-1942-43-illinois-mens-basketball-season/article_4ed3c496-b400-11ef-a8a1-8f50370e6dd5.html

## Baylor Bears — `mascotOrigin` [STALE]
> the current live bears Joy and Lady are North American black bears that live on campus

**Problem:** Stale: both bears are deceased. Joy (Judge Joy Reynolds) died first; Lady (Judge Sue Sloan) died at age 23. Baylor's current live mascots since 2023 are cubs Judge Indy and Judge Belle, who debuted at Homecoming 2024. The 1914 first-live-bear date in the same field conflicts slightly with Baylor's own habitat history, which dates the live-bear tradition to 1917 — worth double-checking if edited.
**Suggested fix:** Change to: 'the current live bears, Judge Indy and Judge Belle, are North American black bears that live in the on-campus Bear Habitat'
**Sources:** https://bearhabitat.web.baylor.edu/about/our-bears · https://wacotrib.com/news/local/education/baylor-welcomes-black-bear-cubs-as-new-mascots/article_43f93430-f8ee-11ed-b3c0-8f7e2599ee10.html

## Baylor Bears — `blurb` [WRONG]
> demolcing previously undefeated Gonzaga 86-70 in the title game

**Problem:** Typo, not a factual error: 'demolcing' is not a word (the facts — 2021 title, Gonzaga undefeated entering the game, 86-70 score — all check out and match data.json NC/NCY).
**Suggested fix:** Replace 'demolcing' with 'demolishing'.
**Sources:** https://en.wikipedia.org/wiki/2021_NCAA_Division_I_men's_basketball_championship_game

## UNLV Rebels — `mascotOrigin` [STALE]
> The 'Rebels' nickname and Hey Reb mascot reflect the frontier spirit of Las Vegas and the American West

**Problem:** Stale and misleading. Hey Reb! was permanently retired in January 2021 (statue removed June 2020); UNLV currently has no mascot, only the Rebels nickname. The nickname's actual origin is the southern campus's 'rebellion' against University of Nevada, Reno — early imagery was Confederate-themed before the 1983 mountain-man redesign — so 'frontier spirit' misstates the origin.
**Suggested fix:** Change to: 'The Rebels nickname dates to the school's origins as a southern branch that rebelled against the University of Nevada, Reno; the Hey Reb! mountain-man mascot, created in 1983, was retired in 2021.'
**Sources:** https://www.unlv.edu/campuslife/mascot-nickname · https://www.cbssports.com/college-basketball/news/unlvs-hey-reb-mascot-is-being-retired-by-the-school/ · https://en.wikipedia.org/wiki/Hey_Reb!

## UNLV Rebels — `funFact` [MISLEADING]
> The 1991 UNLV team went 34-0 during the regular season and was heavily favored to repeat as champions, but was upset by Duke in the Final Four semifinal in one of the biggest upsets in tournament history

**Problem:** Misleading: the 1990-91 regular season was 27-0. The 34-0 mark includes the Big West tournament and four NCAA Tournament wins entering the Final Four semifinal. (The blurb in the same entry phrases it correctly: 'went 34-0 before a stunning upset loss'.) Duke won 79-77.
**Suggested fix:** Change to: 'The 1991 UNLV team entered the Final Four 34-0 (27-0 in the regular season) and was heavily favored to repeat as champions, but was upset 79-77 by Duke in the national semifinal.'
**Sources:** https://en.wikipedia.org/wiki/1990%E2%80%9391_UNLV_Runnin%27_Rebels_basketball_team · https://en.wikipedia.org/wiki/1991_Duke_vs._UNLV_men's_basketball_game

## NC State Wolfpack — `funFact` [STALE]
> the Jimmy V Foundation he inspired has raised over $150 million for cancer research

**Problem:** Stale: technically true but badly outdated. The V Foundation reports $310 million raised and over $458 million awarded in cancer research grants. The '$150 million' figure dates from roughly the mid-2010s.
**Suggested fix:** Change to: 'the V Foundation he co-founded has awarded over $450 million in cancer research grants'
**Sources:** https://www.v.org/facts/millions/ · https://www.v.org/research-overview/

## Wisconsin Badgers — `funFact` [MISLEADING]
> Wisconsin tried to replace Bucky Badger with a cow named 'Henrietta Holstein' in the 1970s, but the university ultimately kept Bucky

**Problem:** Misleading framing: 'Wisconsin tried to replace' overstates it. In 1973 a single state official — Wisconsin assistant attorney general Howard Koop — suggested replacing Bucky with Henrietta Holstein. It was never a university initiative or formal attempt. Core anecdote and the 'Buckingham U. Badger' name are accurate.
**Suggested fix:** Change to: 'In 1973 a Wisconsin assistant attorney general suggested replacing Bucky Badger with a cow named Henrietta Holstein, arguing kids love cows — Bucky (full name Buckingham U. Badger) survived the challenge.'
**Sources:** https://uwbadgers.com/sports/2019/2/14/bucky-badger-a-historical-look-back · https://news.wisc.edu/creator-of-bucky-dies-but-legacy-of-mascot-lives-on/

**Clean (no findings):** Georgetown Hoyas (46), Maryland Terrapins (120), Memphis Tigers (235), Texas Longhorns (251), Purdue Boilermakers (2509)
