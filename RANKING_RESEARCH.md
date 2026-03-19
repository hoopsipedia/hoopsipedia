# Hoopsipedia Proprietary Ranking Systems: Research and Proposed Formulas

## Part 1: Landscape of Existing Rating Systems

### Systems Studied

**KenPom (Adjusted Efficiency)** is the gold standard for in-season predictive ratings. The core metric is AdjEM = Adjusted Offensive Efficiency minus Adjusted Defensive Efficiency, representing how many points a team would outscore an average D-I opponent per 100 possessions on a neutral court. Effects are additive: if Team A's offense is +10% and Team B's defense is -10%, the expected outcome is +20%. KenPom weights recent games more heavily and adjusts for the national average efficiency on the date each game was played. The Pythagorean winning percentage uses an exponent of 10.25 to produce game probabilities.

**NCAA NET** replaced the RPI in 2018. It has two components: the Team Value Index (TVI), which rewards beating quality opponents especially on the road, and an adjusted net efficiency rating. It does NOT factor in scoring margin directly, winning percentage, or game date. The exact formula is proprietary (developed with Google Cloud). The quadrant system classifies wins/losses by opponent NET rank and game location.

**RPI (1981-2018)** was 25% team win%, 50% opponents' win%, 25% opponents' opponents' win%. It was replaced because it had no statistical justification, ignored margin of victory, punished teams for beating weak opponents, and was a poor predictor of both future outcomes and committee decisions.

**Sagarin** uses three sub-systems: The Predictor (score-based), The Golden Mean (proprietary), and Recent (recency-weighted). These are combined into an overall rating. Home advantage is +4 points for college basketball.

**Sports Reference SRS** solves a system of linear equations: each team's rating equals their average point margin adjusted for opponents' strength. It is denominated in points above/below average (zero = average). Available back to ~1980 for college basketball.

**FiveThirtyEight Elo** adapted chess Elo for sports. Key parameters: K-factor around 20 (relatively high, meaning recent results matter a lot), season-to-season carryover of ~64% with reversion toward conference mean (not league mean), and home-court advantage built in. A Harvard Sports Analysis improvement added a within-season K-decay factor so early-season games move ratings more.

**Bart Torvik T-Rank** is similar to KenPom but adds explicit recency bias: games older than 40 days begin losing weight, and games older than 80 days carry only 60% weight. Key metric: Barthag (projected win% vs. average team on neutral court). Data available back to 2008.

**AP Poll** uses 60 voters, 25 points for first-place down to 1 for 25th. Research shows it is anchored too heavily on prior weeks and preseason expectations, but paradoxically, the preseason AP poll is one of the strongest single predictors of tournament success (wisdom of crowds). Kentucky has appeared in over 75% of all AP polls since 1949.

### What Research Says is Most Predictive of Tournament Success

Ranked by predictive power for tournament outcomes:

1. **Adjusted efficiency margin** (KenPom/Torvik style) -- consistently the strongest predictor
2. **Seed differential** -- strong baseline (~68% accuracy) but breaks down in later rounds
3. **Strength of schedule** -- critical context for win-loss records
4. **Margin of victory** -- captures dominance beyond W/L
5. **Preseason AP poll** -- surprisingly strong as a wisdom-of-crowds signal
6. **Box-score composites** (rebounds, assists, turnovers, shooting %) -- meaningful marginal lift
7. **Vegas lines** -- incorporate broad market knowledge

The accuracy ceiling for any model is roughly 75%, per Georgia Tech professor Joel Sokol. About a quarter of tournament games are effectively random.

---

## Part 2: The Blue Blood Index (BBI)

### Design Philosophy

The BBI answers: "Which programs are the greatest of all time?" It should be:
- **Cumulative** (rewarding sustained excellence across decades)
- **Dynamic** (updating as the current season progresses)
- **Era-aware** (a 1960 championship should count, but not as much as a 2020 one due to field size and competition depth)
- **Multi-dimensional** (championships alone are insufficient -- consistency, talent production, and prestige all matter)

### Proposed Categories and Weights

The formula uses 8 weighted pillars. Total raw points are computed, then normalized to a 0-100 scale (where the top program = 100).

| Pillar | Weight | Rationale |
|--------|--------|-----------|
| Championship Capital | 30% | The ultimate measure of program success |
| Tournament Depth | 20% | Sustained NCAA Tournament excellence beyond titles |
| Win Consistency | 15% | Decade-over-decade winning culture |
| Poll Prestige | 12% | National perception and sustained relevance |
| Talent Production | 10% | NBA draft picks as a proxy for recruiting/development |
| Conference Dominance | 5% | Regular season titles in context of conference strength |
| Coaching Prestige | 5% | Hall of Fame coaches, longevity, program builders |
| Current Momentum | 3% | Recent 5-year performance (keeps the index dynamic) |

### Pillar Formulas

**1. Championship Capital (30%)**

```
CC = SUM over all seasons of:
  (Championship_Won * 10 * era_multiplier)
  + (Runner_Up * 4 * era_multiplier)
  + (Final_Four * 2 * era_multiplier)
```

Era multipliers account for tournament field size and competition depth:
- Pre-1951 (8-team field): 0.60
- 1951-1974 (16-25 teams): 0.75
- 1975-1984 (32-48 teams): 0.85
- 1985-2000 (64 teams): 0.95
- 2001-2010 (65 teams): 1.00
- 2011-present (68 teams): 1.00

Rationale: A championship in a 68-team field with a modern talent pool is harder to win than in a 16-team field. But pre-expansion titles still carry significant weight -- 60-75% -- because those programs were genuinely dominant.

**2. Tournament Depth (20%)**

```
TD = SUM over all seasons of:
  (Elite_Eight * 1.0)
  + (Sweet_Sixteen * 0.5)
  + (Tournament_Appearance * 0.2)
  + (Tournament_Win * 0.15)
```

This rewards programs that consistently advance deep. A program with 20 Elite Eights scores much higher than one with 5, even if the latter has more titles.

**3. Win Consistency (15%)**

```
WC = (All_Time_Win_Pct * 40)
   + (Decades_With_Winning_Record * 5)
   + (20_Win_Seasons * 1.5)
   + (Seasons_Played * 0.1)
```

The "Decades with Winning Record" metric (out of a possible ~12 decades of organized play) specifically rewards sustained multi-generational excellence. The 20-win season count, used by several existing blue blood analyses, is a clean consistency signal.

**4. Poll Prestige (12%)**

```
PP = (Total_Weeks_Ranked_AP * 0.10)
   + (Weeks_Ranked_No1_AP * 1.0)
   + (Preseason_Top_10_Appearances * 0.5)
   + (Final_Poll_Top_5_Appearances * 0.75)
```

AP poll data goes back to 1949. Weeks at No. 1 are weighted 10x a normal ranked week because holding the top spot signals peak dominance. Preseason Top 10 appearances capture recruiting prestige and national expectations.

**5. Talent Production (10%)**

```
TP = (Lottery_Picks * 3.0)
   + (First_Round_Picks_11_to_30 * 1.5)
   + (Second_Round_Picks * 0.5)
   + (All_Americans * 1.0)
   + (Naismith_POY_Winners * 5.0)
```

NBA draft picks serve as an objective, external validation of talent level. Lottery picks are weighted 6x second-rounders because they represent truly elite talent. All-Americans and Player of the Year awards capture college-specific individual excellence.

**6. Conference Dominance (5%)**

```
CD = (Conference_Regular_Season_Titles * 1.0)
   + (Conference_Tournament_Titles * 0.5)
```

Conference titles are weighted lower because conference strength varies enormously (Big East in the 1980s vs. the WAC). Regular season titles are worth more than tournament titles because they reflect sustained play over months rather than a 3-game run.

**7. Coaching Prestige (5%)**

```
CP = (HOF_Coaches_Seasons * 0.3)
   + (HOF_Coaches_Count * 3.0)
   + (NABC_COY_Awards * 2.0)
```

Programs that attracted and retained Hall of Fame coaches demonstrate institutional commitment to basketball. This is measured by both the number of HOF coaches and the total seasons under HOF coaching.

**8. Current Momentum (3%)**

```
CM = (Last_5_Years_Avg_KenPom_Rank_Inverse * 2.0)
   + (Last_5_Years_Tournament_Wins * 0.5)
```

Where KenPom Rank Inverse = (360 - Avg_KenPom_Rank) / 360, yielding a 0-1 scale. This pillar is intentionally small -- it prevents the index from being purely historical while keeping it from overreacting to recent hot/cold streaks. It is the "dynamic" component that updates during the season.

### Final BBI Calculation

```
Raw_BBI = (CC_normalized * 0.30) + (TD_normalized * 0.20) + (WC_normalized * 0.15)
        + (PP_normalized * 0.12) + (TP_normalized * 0.10) + (CD_normalized * 0.05)
        + (CP_normalized * 0.05) + (CM_normalized * 0.03)

BBI = (Raw_BBI / Max_Raw_BBI_Among_All_Programs) * 100
```

Each pillar is independently normalized (0 to 1 scale) before weighting, so no single pillar dominates due to unit differences. The final score is rescaled so the top program = 100.

### Why These Weights

- **30% Championships** is deliberately high because titles are the defining feature of a blue blood. CBS Sports and every qualitative blue blood list anchors on championships first. But 30% (not 50%+) leaves room for programs like Illinois or Michigan State that lack title volume but demonstrate sustained excellence in every other dimension.
- **20% Tournament Depth** rewards the Kansas/North Carolina model of relentless March presence. A program that reaches 15 Elite Eights but only wins 3 titles is more "blue blood" than one with 4 titles but only 5 Elite Eights.
- **15% Win Consistency** captures the Kentucky model: winning records in 12 of 12 decades, 2300+ all-time wins. This prevents a one-dynasty program from ranking too highly.
- **3% Current Momentum** is small by design. The index is "all-time" -- it should not swing wildly based on a single bad or good season.

---

## Part 3: Historical Team-Season Score (HTSS)

### Design Philosophy

The HTSS answers: "How good was this specific team in this specific season?" It powers cross-era matchup simulations. Requirements:

- Every team-season from ~1950 to present gets a score
- Scores are comparable across eras (1976 Indiana vs. 2015 Kentucky)
- The score should correlate with actual dominance, not just win count
- Tournament performance is factored in but doesn't dominate (some great teams lose early)

### The Z-Score Era-Normalization Approach

The core insight from research: raw stats are meaningless across eras because of rule changes (shot clock: 45 to 35 to 30 seconds; 3-point line introduction in 1987; tournament expansion from 8 to 68 teams), pace differences, and talent pool changes. The solution is to compute era-relative z-scores for every metric, then combine them.

**Define eras based on major rule inflection points:**

| Era | Years | Key Characteristics |
|-----|-------|-------------------|
| Pre-Shot Clock | Before 1986 | No shot clock, no 3-point line (pre-1987) |
| Early Modern | 1986-1993 | 45-second clock, 3-point line introduced |
| Mid Modern | 1994-2007 | 35-second clock era |
| Late Modern | 2008-2015 | Extended 3-point line (2008), analytics emergence |
| Current | 2016-present | 30-second clock, international 3-point distance (2020) |

Within each era, compute the mean and standard deviation for every metric across all D-I teams. A team's z-score for a metric tells you how many standard deviations above or below their era's average they were.

### HTSS Component Formula

The HTSS has 5 components:

**Component 1: Dominance Score (35% weight)**

```
Dominance_z = (
    z_SRS * 0.40          // SRS (margin + SOS) -- available back to ~1980
  + z_WinPct * 0.25       // Win percentage
  + z_ScoringMargin * 0.20 // Average scoring margin
  + z_CloseGameRecord * 0.15 // Record in games decided by 5 or fewer points
)
```

All z-scores are computed within the team's era. SRS gets the highest sub-weight because research shows adjusted margin (which SRS captures) is the single strongest predictor. Close-game record serves as a "luck adjustment" -- a team that goes 12-1 in close games likely overperformed their true strength, while a team that goes 3-8 likely underperformed.

For seasons before SRS data is available (~pre-1980), fall back to:
```
Dominance_z = z_WinPct * 0.50 + z_ScoringMargin * 0.50
```

**Component 2: Strength of Schedule (20% weight)**

```
SOS_z = (
    z_OpponentWinPct * 0.40
  + z_RankedWins * 0.35      // Wins over teams ranked in that season's final poll
  + z_BadLosses * -0.25      // Losses to teams below .500 (penalty)
)
```

This captures whether a team beat good opponents or feasted on weak ones. The bad-loss penalty is critical: truly great teams almost never lose to bad opponents. A team with 30 wins but 3 losses to sub-.500 teams is less impressive than one with 28 wins and zero bad losses.

**Component 3: Tournament Performance (20% weight)**

```
TournPerf = (
    Championship * 15.0
  + Runner_Up * 8.0
  + Final_Four * 5.0
  + Elite_Eight * 3.0
  + Sweet_Sixteen * 1.5
  + First_Weekend_Exit * 0.0
  + Did_Not_Make * -2.0
)
```

This is NOT z-scored because tournament outcomes are discrete achievements. Instead, the raw score is normalized against the era's maximum possible tournament score (a championship). The -2.0 for not making the tournament is a mild penalty -- some great regular-season teams missed the tournament in early eras when the field was tiny, so the penalty is kept small.

Apply an era-adjustment for field size:
```
TournPerf_adjusted = TournPerf * (log2(current_field_size) / log2(team_era_field_size))
```

This means a championship in a 16-team field (log2 = 4) is scaled up by 68/16 ratio when compared to a modern championship (log2 = ~6), normalizing the number of rounds required. A team that went 4-0 to win in 1960 gets credit, but a team that went 6-0 in 2020 gets proportionally more.

**Component 4: Conference Performance (10% weight)**

```
ConfPerf_z = (
    z_ConferenceWinPct * 0.50
  + RegularSeasonTitle * 3.0
  + ConferenceTournamentTitle * 1.5
) normalized within era
```

Conference performance is a steady-state signal less prone to single-elimination variance. Regular season titles get double the tournament title weight because they represent 15-20 games of sustained excellence.

**Component 5: Peak Perception (15% weight)**

```
PeakPerc = (
    z_HighestAPRank * 0.40       // Peak AP ranking achieved (inverted: #1 = max)
  + z_FinalAPRank * 0.35         // End-of-season AP rank
  + z_WeeksAtNo1 * 0.25          // Weeks at #1 during that season
)
```

The AP poll, despite its biases, provides a useful "consensus view" signal. The preseason poll is deliberately excluded from the season score (it reflects expectations, not performance). Peak rank captures the team's ceiling; final rank captures where they ended up. This component is z-scored within era because the poll expanded from Top 20 to Top 25 in 1990.

### Final HTSS Calculation

```
HTSS_raw = (Dominance_z * 0.35) + (SOS_z * 0.20) + (TournPerf_adj * 0.20)
         + (ConfPerf_z * 0.10) + (PeakPerc * 0.15)

HTSS = 50 + (HTSS_raw * 10)
```

The final transformation centers the score at 50 (an average D-I team-season) with a standard deviation of 10. This means:
- **50** = Average D-I team-season
- **60** = Strong team (roughly top 30-40 nationally)
- **70** = Elite team (top 10 nationally, deep tournament run)
- **80** = All-time great season (Final Four caliber, dominant margins)
- **85+** = Historically transcendent (undefeated or near-undefeated champions)
- **90+** = Reserved for the very best seasons ever (1976 Indiana, 2015 Kentucky regular season, 1972 UCLA)

### Matchup Prediction from HTSS

For the Time Machine feature, the HTSS difference between two team-seasons can generate a win probability:

```
Expected_Margin = (HTSS_A - HTSS_B) * 1.0
Win_Prob_A = 1 / (1 + 10^(-(HTSS_A - HTSS_B) / 10))
```

This is the logistic/Elo formula. A 10-point HTSS gap corresponds to roughly a 10-point expected margin and a ~76% win probability. A 5-point gap yields ~64% win probability. This aligns with research showing the standard deviation of college basketball game outcomes is approximately 10 points.

---

## Part 4: Key Design Decisions and Rationale

### Why Not Just Average Existing Rankings?

Averaging KenPom + Sagarin + NET creates a system that is:
1. **Redundant** -- they all measure similar things (efficiency, SOS) with high correlation
2. **Uninterpretable** -- a combined score has no clear unit or meaning
3. **Limited historically** -- KenPom goes back to 2002, Torvik to 2008, NET to 2018

The proposed systems use the *principles* from these systems (efficiency margins, SOS adjustment, z-score normalization) but apply them to historical data in a purpose-built framework.

### How Recency Should Work in the BBI

The BBI uses a two-pronged recency approach:
1. **Era multipliers on championships** (structural): Older titles count less due to smaller fields, but still count substantially (60-75%). This is not "recency bias" -- it is difficulty adjustment.
2. **Current Momentum pillar** (dynamic): Only 3% of the total score, so a 5-year cold streak cannot destroy a century of excellence. Kentucky could go 0-30 for 5 straight years and still rank top 5 on the BBI.

This mirrors how blue-blood status actually works culturally: once earned, it takes decades to lose.

### Normalizing Across Eras for HTSS

The z-score approach is the most defensible method found in the research. It avoids the trap of raw stat comparison (a team averaging 90 PPG in 1970 vs. 70 PPG in 2020 means nothing without context). By expressing every metric as "standard deviations above/below their era's mean," you inherently control for rule changes, pace, and talent pool size.

The era boundaries are set at major rule changes rather than arbitrary decades because rule changes cause discrete shifts in statistical distributions (e.g., the shot clock reduction from 35 to 30 seconds increased median possessions from 68.1 to 70.8 per game and median PPG from 67.9 to 71.5).

### Data Availability Constraints

A practical note: some metrics are unavailable for early eras.

| Metric | Available From |
|--------|---------------|
| Win-Loss records | ~1900 |
| AP Poll | 1949 |
| NCAA Tournament results | 1939 |
| Scoring margin | ~1950s |
| SRS | ~1980 |
| Per-possession efficiency | ~2002 (KenPom) |
| Full box scores | Varies by team/era |

The formulas above degrade gracefully: for pre-1980 seasons, SRS is replaced by raw margin z-scores. For pre-1949 seasons, the AP poll component is zeroed out and its weight redistributed to Dominance and SOS. This is a feature, not a bug -- earlier seasons have higher uncertainty, which is accurately reflected in a narrower range of possible scores.

---

## Part 5: Validation Strategy

Before finalizing weights, the system should be validated against known ground truths:

1. **BBI face validity**: Does the top 10 match the consensus blue bloods? (Kentucky, UCLA, North Carolina, Duke, Kansas should be top 5 in some order.) If Indiana is 15th, something is wrong.

2. **HTSS tournament prediction**: For seasons with tournament data, does a higher HTSS correlate with deeper tournament runs? Run a logistic regression of HTSS vs. tournament round reached for all team-seasons since 1985. Target: top-quartile HTSS teams should reach the Sweet 16 at 2x+ the base rate.

3. **HTSS cross-era sanity checks**: Do known great seasons score 85+? (1976 Indiana 32-0, 1972 UCLA 30-0, 2015 Kentucky 38-1 regular season.) Do known mediocre seasons from blue bloods score 50-60?

4. **Weight sensitivity analysis**: Vary each weight by +/- 5% and check if rankings change dramatically. A robust system should be relatively insensitive to small weight changes.

---

## Summary of Proposed Weights

### Blue Blood Index

| Pillar | Weight |
|--------|--------|
| Championship Capital | 30% |
| Tournament Depth | 20% |
| Win Consistency | 15% |
| Poll Prestige | 12% |
| Talent Production | 10% |
| Conference Dominance | 5% |
| Coaching Prestige | 5% |
| Current Momentum | 3% |

### Historical Team-Season Score

| Component | Weight |
|-----------|--------|
| Dominance (margin + record + SOS-adjusted) | 35% |
| Strength of Schedule | 20% |
| Tournament Performance | 20% |
| Peak Perception (AP poll) | 15% |
| Conference Performance | 10% |

---

Sources:
- [KenPom Ratings Explanation](https://kenpom.com/blog/ratings-explanation/)
- [KenPom Ratings Methodology Update](https://kenpom.com/blog/ratings-methodology-update/)
- [NCAA NET Rankings Explained](https://www.ncaa.com/news/basketball-men/article/2022-12-05/college-basketballs-net-rankings-explained)
- [How NET Rankings Work - NCAA.org](https://www.ncaa.org/news/2025/3/3/media-center-how-do-net-rankings-work-in-ncaa-tournament-selection.aspx)
- [RPI Wikipedia](https://en.wikipedia.org/wiki/Rating_percentage_index)
- [SRS Calculation Details - Sports Reference](https://www.sports-reference.com/blog/2015/03/srs-calculation-details/)
- [FiveThirtyEight March Madness Methodology](https://fivethirtyeight.com/methodology/how-our-march-madness-predictions-work-2/)
- [FiveThirtyEight NBA Elo Methodology](https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings/)
- [Harvard Sports Analysis - Elo K-Decay Improvement](https://harvardsportsanalysis.org/2019/01/a-simple-improvement-to-fivethirtyeights-nba-elo-model/)
- [College Basketball Elo Implementation on GitHub](https://github.com/grdavis/college-basketball-elo)
- [Bart Torvik T-Rank Explained - OddsShark](https://www.oddsshark.com/ncaab/what-are-torvik-ratings)
- [Sagarin Ratings Guide](https://www.pointspreads.com/guides/sagarin-betting-system-guide/)
- [CBS Sports Greatest Programs Formula](https://www.cbssports.com/college-basketball/news/the-greatest-college-basketball-programs-ever-ranking-the-top-teams-of-all-time/)
- [247Sports Blue Blood Tiers](https://247sports.com/longformarticle/college-basketball-blue-blood-tiers-re-evaluating-where-unc-duke-uconn-ucla-stand-on-all-time-scale-229731057/)
- [AP Poll Methodology - ESPN](https://www.espn.com/mens-college-basketball/story/_/id/47516040/what-ap-college-basketball-poll-how-does-work)
- [College Poll Tracker Bias Analysis](https://collegepolltracker.com/whats-new-bias/)
- [NCAA Bracket Prediction Using ML - arXiv](https://arxiv.org/html/2603.10916v1)
- [Nate Silver's COOPER System](https://www.natesilver.net/p/introducing-cooper-silver-bulletins)
- [The Power Rank - Predictive Analytics Guide](https://thepowerrank.com/cbb-analytics/)
- [Z-Scores in Sports Data Analysis](https://mattwaite.github.io/sports/zscores.html)
- [Variance in College Basketball - The Only Colors](https://www.theonlycolors.com/2020/4/27/21226073/the-variance-of-college-basketball-how-big-is-it-and-where-does-it-come-from)
- [Bryant University NCAA Tournament Z-Score Study](https://digitalcommons.bryant.edu/cgi/viewcontent.cgi?article=1004&context=honors_mathematics)