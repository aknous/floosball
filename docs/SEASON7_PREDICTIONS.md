# Season 7 — Preseason Simulation (50 runs)

_Generated 2026-09-21 by `tools_preseason.py`, from a prod pull with season 7 scheduled and 0 of 448 games played. Raw per-run results in `season7_runs.json`._

⚠️ **This is the first forecast run against the NFL-calibrated play calling and passing model** (merged to main the same day, `45c2738`). Season 6's forecast predates it, so a season-over-season comparison of the numbers below is comparing two engines as well as two rosters.

## Method

- Prod database simulated against a **copy**, never prod itself.
- Snapshot taken in the only window where the question is answerable: after the offseason finished and before the first kickoff, so every run starts from the **identical schedule and rosters** and the spread is the sim's own variance rather than a difference in setup.
- 50 runs at `--parallel 5`, each killed the moment its Floos Bowl row goes final. About 20 minutes wall clock, roughly 2 minutes a run.

### How much of this is signal

- Mean within-team spread is **2.32 wins**. ⚠️ That supports **two different claims and they are an order of magnitude apart, so keep them separate**. The *forecast* is precise: the standard error on a mean win total is `2.32/sqrt(50)` = **±0.33**, so two teams whose projections differ by more than about **1 win** are genuinely ranked. The *season* is not: only one gets played, and realized wins carry the full 2.32 SD, so two teams within about **4.6 wins** (2 SD) of each other will routinely finish in either order. Rank the table by the first number, bet on it with the second.
- Standard error on a title share is about **±5 points** at 50 runs (it was ±10 at 25). Read a single title as *"it happened once"*, not as a 2% chance.
- ⚠️ The standard error on a single team's SD is about **±0.23 wins**, which is why only the extremes of the dispersion column below are worth reading.

### Sanity checks

- League mean comes out at exactly **14.00**, which the schedule fixes (every game has one winner) rather than the sim producing.
- Every team played exactly 28 games in all 50 runs; 50 of 50 runs produced a Floos Bowl, none failed.
- 47 runs sum to 448 wins and 3 sum to 447. Those three had one tied game each. Arithmetic, not a fault.

## Floos Bowl, every run

| # | result | | # | result |
|---:|---|---|---:|---|
| 1 | Bees def. Dry Heat 30-13 | | 26 | Raccoons def. Rocks 41-40 |
| 2 | Pinecones def. Normals 36-21 | | 27 | Residents def. Raccoons 25-17 |
| 3 | Rhyme def. Residents 19-17 | | 28 | Classics def. Residents 38-31 |
| 4 | Rocks def. Raccoons 40-39 | | 29 | Classics def. Residents 30-28 |
| 5 | Raccoons def. Normals 16-9 | | 30 | Classics def. Normals 30-24 |
| 6 | Raccoons def. Residents 44-25 | | 31 | Normals def. Classics 23-20 |
| 7 | Rocks def. Rhyme 27-14 | | 32 | Raccoons def. Residents 38-10 |
| 8 | Rocks def. Tuesdays 34-9 | | 33 | Classics def. Rocks 30-25 |
| 9 | Normals def. Bees 27-23 | | 34 | Pinecones def. Rocks 28-23 |
| 10 | Normals def. Raccoons 20-14 | | 35 | Rocks def. Tuesdays 21-16 |
| 11 | Rocks def. Exoticos 30-7 | | 36 | Waffles def. Classics 35-13 |
| 12 | Residents def. Raccoons 33-20 | | 37 | Raccoons def. Rocks 52-41 |
| 13 | Rhyme def. Oysters 19-16 | | 38 | Exoticos def. Oysters 9-7 |
| 14 | Residents def. Rhyme 35-23 | | 39 | Caddies def. Raccoons 24-19 |
| 15 | Oysters def. Rhyme 27-15 | | 40 | Classics def. Normals 51-41 |
| 16 | Raccoons def. Normals 23-12 | | 41 | Sand Dollars def. Classics 42-39 |
| 17 | Rocks def. Classics 59-32 | | 42 | Rocks def. Classics 42-30 |
| 18 | Strangers def. Tuesdays 37-17 | | 43 | Raccoons def. Rocks 35-30 |
| 19 | Residents def. Exoticos 40-16 | | 44 | Raccoons def. Residents 18-14 |
| 20 | Waffles def. Classics 27-15 | | 45 | Normals def. Classics 47-7 |
| 21 | Raccoons def. Residents 38-19 | | 46 | Classics def. Sand Dollars 41-34 |
| 22 | Tuesdays def. Sand Dollars 34-6 | | 47 | Rocks def. Extras 61-0 |
| 23 | Sand Dollars def. Rhyme 25-13 | | 48 | Dry Heat def. Raccoons 24-17 |
| 24 | Residents def. Exoticos 22-14 | | 49 | Residents def. Pinecones 20-17 |
| 25 | Classics def. Strangers 27-25 | | 50 | Dry Heat def. Exoticos 41-21 |

**16 different teams won at least one title in 50 runs.**

## Title odds

| team | titles | odds | reached the bowl |
|---|---:|---:|---:|
| Raccoons | 9 | 18% | 15 |
| Rocks | 8 | 16% | 13 |
| Classics | 7 | 14% | 14 |
| Residents | 6 | 12% | 13 |
| Normals | 4 | 8% | 9 |
| Pinecones | 2 | 4% | 3 |
| Rhyme | 2 | 4% | 6 |
| Waffles | 2 | 4% | 2 |
| Sand Dollars | 2 | 4% | 4 |
| Dry Heat | 2 | 4% | 3 |
| Bees | 1 | 2% | 2 |
| Oysters | 1 | 2% | 3 |
| Strangers | 1 | 2% | 2 |
| Tuesdays | 1 | 2% | 4 |
| Exoticos | 1 | 2% | 5 |
| Caddies | 1 | 2% | 1 |

## Average wins

| team | avg | SD | min | max | titles | SD vs coin flip |
|---|---:|---:|---:|---:|---:|---:|
| Residents | 20.5 | 2.00 | 16 | 26 | 6 | 0.85 |
| Raccoons | 19.4 | 1.85 | 15 | 23 | 9 | 0.76 |
| Exoticos | 19.1 | 2.84 | 13 | 24 | 1 | 1.15 |
| Classics | 18.4 | 2.07 | 13 | 23 | 7 | 0.82 |
| Sand Dollars | 17.2 | 2.12 | 13 | 22 | 2 | 0.82 |
| Rhyme | 16.9 | 2.07 | 11 | 20 | 2 | 0.80 |
| Tuesdays | 16.8 | 2.72 | 10 | 22 | 1 | 1.05 |
| Pinecones | 16.7 | 2.51 | 12 | 22 | 2 | 0.97 |
| Rocks | 16.6 | 2.49 | 11 | 22 | 8 | 0.96 |
| Normals | 16.1 | 2.16 | 10 | 20 | 4 | 0.82 |
| Strangers | 15.7 | 1.47 | 13 | 19 | 1 | 0.56 |
| Extras | 15.7 | 1.80 | 13 | 20 | 0 | 0.69 |
| Dry Heat | 15.7 | 2.23 | 10 | 20 | 2 | 0.85 |
| Bees | 15.3 | 2.18 | 11 | 19 | 1 | 0.83 |
| Oysters | 14.5 | 2.32 | 9 | 20 | 1 | 0.88 |
| Curd | 13.9 | 2.91 | 6 | 20 | 0 | 1.10 |
| Waffles | 13.8 | 2.15 | 8 | 18 | 2 | 0.81 |
| Broads | 13.6 | 1.91 | 10 | 17 | 0 | 0.72 |
| Midnights | 13.6 | 1.87 | 9 | 18 | 0 | 0.71 |
| Monuments | 12.9 | 2.48 | 6 | 20 | 0 | 0.94 |
| Pops | 12.8 | 2.35 | 7 | 18 | 0 | 0.89 |
| Caddies | 12.3 | 2.14 | 8 | 16 | 1 | 0.82 |
| Melons | 12.2 | 2.69 | 6 | 16 | 0 | 1.02 |
| Cranes | 12.1 | 2.08 | 8 | 17 | 0 | 0.79 |
| Trains | 11.7 | 3.15 | 4 | 17 | 0 | 1.21 |
| Beans | 10.6 | 2.41 | 5 | 16 | 0 | 0.94 |
| Jetskis | 10.5 | 2.53 | 5 | 16 | 0 | 0.99 |
| Buffalo | 10.4 | 2.82 | 6 | 20 | 0 | 1.10 |
| Sodas | 9.9 | 2.38 | 4 | 14 | 0 | 0.94 |
| Grillmeisters | 9.3 | 2.38 | 4 | 15 | 0 | 0.96 |
| Slippers | 7.3 | 2.51 | 3 | 15 | 0 | 1.08 |
| Phones | 6.7 | 2.79 | 2 | 12 | 0 | 1.23 |

## Is the spread wild? No, it is narrower than chance

The wide min/max columns above read as alarming (Trains 4 to 17, Buffalo 6 to 20) and are worth nothing without a benchmark. The benchmark: if every game were an independent coin flip at that team's own win rate, wins would be `Binomial(28, p)` with `SD = sqrt(28·p·(1-p))`, which **peaks at 2.65 wins**. Two SD is ±5, so a team with true talent of 14 wins lands between 9 and 19 as a matter of routine, before the sim contributes anything at all. A 28-game season is simply short.

Measured against that benchmark, league-wide:

| season | runs | mean within-team SD | observed variance vs coin flip |
|---|---:|---:|---:|
| 6 | 25 | 2.28 | **0.84** (SD 0.92x) |
| 7 | 50 | 2.32 | **0.84** (SD 0.92x) |

**0.84 in both seasons, computed independently on different rosters, different run counts and different engines.** The spread is not merely explainable by chance, it sits *below* the coin-flip benchmark, and that is structural rather than lucky:

> Variance of a season is `Σ p_i(1-p_i)` over its games, which is largest when every game is a coin flip. A good team that beats the bottom of the league 85% of the time and splits with the top contributes **less** variance per game than one that is 50/50 every week. Varying opponent strength mathematically compresses the spread below the single-`p` binomial. 0.84 is what that compression looks like.

So there is **no over-dispersion to explain**. Notably, neither the momentum form layer (documented as deliberately pushing *within-season* variance past the chance line) nor the new in-season trade market shows up as extra spread in season totals. Hot and cold runs create arcs inside a season that wash out by week 28, which is the intended behavior.

Real per-team differences do survive:

- **Strangers, 0.56 of expected** (1.47 SD against 2.63). Five standard errors low, so genuinely metronomic: 13 to 19 wins, with 33 of 50 runs landing on 15, 16 or 17.
- **Phones 1.23 and Trains 1.21** are the loose ones, but at about 2.3 standard errors they are suggestive rather than established.

### ⚠️ Trap: one outlier run is not a second mode

Buffalo, Curd and Monuments each posted a 20-win season against averages of 10.4, 13.9 and 12.9, and each looked bimodal at a glance. They are not. Each has **exactly one** such run with a gap beneath it (Buffalo goes 16, nothing, then 20; Monuments 17, nothing, then 20). Across 50 runs x 32 teams there are 1,600 team-seasons in this batch, so a handful of four-sigma outliers is expected. Read the distribution before calling a long tail a second hump.

## Year over year: the league got far more competitive

| season | team average wins, worst to best |
|---|---|
| 6 | 2.9 to 25.6 |
| 7 | **6.7 to 20.5** |

The talent span compressed hard while the dispersion ratio held at 0.84. Season 6's forecast had a team projected to win under 3 games and another over 25; season 7 has nobody outside 6.7 to 20.5, and **16 different champions in 50 runs** with the favorite converting under one time in five.

⚠️ **Candidate causes, none established at n=2 seasons.** The offseason between them was the first to run the **trade market** and the restored **rookie draft**, either of which redistributes surplus talent from teams that cannot use it toward teams that can. Roster churn alone could also do it. **The test for next season:** if the 6.7-to-20.5 style span holds into season 8 it is structural and the trading market is the likely cause; if it springs back toward season 6's range it was roster churn. Re-run this and compare the span, not the dispersion ratio, which has been stable at 0.84 twice.

## Actual results (added 2026-09-27)

**Champion: the Midnights**, who won 0 of the 50 forecast runs and never reached a single forecast Floos Bowl. The forecast had them at **13.6 wins (9 to 18)**; they went **17-11**, then won four straight playoff games, beating the forecast's projected best team, the Residents, in the Bowl. The Residents were the forecast's fourth-likeliest champion (12%); the Raccoons, its favorite at 18%, went out in round 1.

### Playoffs

| round | result |
|---|---|
| Round 1 | Normals def. Sand Dollars 24-3 |
| Round 1 | Pinecones def. Rhyme 21-20 |
| Round 1 | Exoticos def. Raccoons 17-6 |
| Round 1 | Residents def. Dry Heat 38-10 |
| Round 1 | Strangers def. Waffles 26-9 |
| Round 1 | Classics def. Extras 31-20 |
| Round 1 | Rocks def. Caddies 37-17 |
| Round 1 | Midnights def. Curd 50-0 |
| Round 2 | Midnights def. Pinecones 52-23 |
| Round 2 | Strangers def. Normals 34-24 |
| Round 2 | Residents def. Rocks 31-13 |
| Round 2 | Classics def. Exoticos 30-16 |
| League Championship | Residents def. Strangers 38-20 |
| League Championship | Midnights def. Classics 37-25 |
| Floos Bowl | Midnights def. Residents 28-24 |

### Regular season against the forecast

- **Ranking held up.** Correlation between forecast average and actual wins: **0.76**. Mean absolute miss: **2.7 wins**, close to the 2.3-win SD any single season carries.
- **25 of 32** teams landed within two forecast SDs of their average, and **28 of 32** inside the range the 50 runs actually produced. Outside it: Pinecones (24, range 12-22), Caddies (18, range 8-16), Cranes (7, range 8-17), Buffalo (4, range 6-20).
- **Biggest over-performers:** Pinecones +7.3, Curd +6.1, Caddies +5.7, Classics +4.6. **Biggest under-performers:** Buffalo -6.4, Grillmeisters -5.3, Cranes -5.1, Oysters -3.5.
- ⚠️ **The forecast cannot see in-season trades**, which open in week 15, after its snapshot. The Midnights (Trinity Pantsdown) and the Pinecones (Squall Baptiste) each made exactly one in-season acquisition, both in week 15. Curd and Caddies, two of the other big over-performers, made none, so trades are at most part of the story.

| team | forecast avg | forecast range | actual | miss | inside range |
|---|---:|---:|---:|---:|:---:|
| Pinecones | 16.7 | 12-22 | 24-4 | +7.3 | **no** |
| Classics | 18.4 | 13-23 | 23-5 | +4.6 | yes |
| Curd | 13.9 | 6-20 | 20-8 | +6.1 | yes |
| Normals | 16.1 | 10-20 | 19-9 | +2.9 | yes |
| Residents | 20.5 | 16-26 | 18-10 | -2.5 | yes |
| Raccoons | 19.4 | 15-23 | 18-10 | -1.4 | yes |
| Caddies | 12.3 | 8-16 | 18-10 | +5.7 | **no** |
| Extras | 15.7 | 13-20 | 17-11 | +1.3 | yes |
| Waffles | 13.8 | 8-18 | 17-11 | +3.2 | yes |
| Midnights | 13.6 | 9-18 | 17-11 | +3.4 | yes |
| Exoticos | 19.1 | 13-24 | 16-12 | -3.1 | yes |
| Rocks | 16.6 | 11-22 | 16-12 | -0.6 | yes |
| Strangers | 15.7 | 13-19 | 16-12 | +0.3 | yes |
| Dry Heat | 15.7 | 10-20 | 16-12 | +0.3 | yes |
| Sand Dollars | 17.2 | 13-22 | 15-13 | -2.2 | yes |
| Rhyme | 16.9 | 11-20 | 15-13 | -1.9 | yes |
| Tuesdays | 16.8 | 10-22 | 15-13 | -1.8 | yes |
| Monuments | 12.9 | 6-20 | 15-13 | +2.1 | yes |
| Trains | 11.7 | 4-17 | 15-13 | +3.3 | yes |
| Bees | 15.3 | 11-19 | 14-14 | -1.3 | yes |
| Pops | 12.8 | 7-18 | 14-14 | +1.2 | yes |
| Broads | 13.6 | 10-17 | 12-16 | -1.6 | yes |
| Jetskis | 10.5 | 5-16 | 12-16 | +1.5 | yes |
| Oysters | 14.5 | 9-20 | 11-17 | -3.5 | yes |
| Melons | 12.2 | 6-16 | 10-18 | -2.2 | yes |
| Beans | 10.6 | 5-16 | 9-19 | -1.6 | yes |
| Sodas | 9.9 | 4-14 | 9-19 | -0.9 | yes |
| Cranes | 12.1 | 8-17 | 7-21 | -5.1 | **no** |
| Slippers | 7.3 | 3-15 | 6-22 | -1.3 | yes |
| Phones | 6.7 | 2-12 | 6-22 | -0.7 | yes |
| Buffalo | 10.4 | 6-20 | 4-24 | -6.4 | **no** |
| Grillmeisters | 9.3 | 4-15 | 4-24 | -5.3 | yes |

## Reproducing this

```bash
.venv/bin/python tools_preseason.py --db <season-start copy> --season N --runs 50 --parallel 5 --json out.json
```

The dispersion check is the reusable part and is not in the tool. For each team take `SD(wins)` across runs against `sqrt(28·p·(1-p))` where `p = mean(wins)/28`, then sum variances league-wide for the ratio. Anything near 1.0 is pure chance; above 1.0 is genuine over-dispersion and worth chasing.
