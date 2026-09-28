# Season 8 — Preseason Simulation (25 runs)

_Generated 2026-09-27 by `tools_preseason.py`, from a prod pull with season 8 scheduled and 0 of 448 games played. Raw per-run results in `season8_runs.json`._

⚠️ **First forecast after the 2026-09-27 deploy** (`9bea426`): true prospect projections, the promoted-prospect contract floor and cut protection, development on one clock on or off a roster, lost muffs counted as turnovers, and punts charging the clock once. The Floobit balance changes in the same deploy do not touch the sim. The punt clock fix does, slightly: every ordinary punt used to take 4-6 extra seconds.

## Method

- Prod database simulated against a **copy**, never prod itself. The copy is a SQLite backup taken on the prod machine (prod carries a `-wal` file, so copying `floosball.db` alone would have missed recent writes), downloaded, and the temporary file deleted.
- Snapshot taken after the offseason finished and before the first kickoff, so every run starts from the **identical schedule and rosters** and the spread is the sim's own variance.
- 25 runs at `--parallel 5`, each killed when its Floos Bowl row goes final.

### How much of this is signal

- Mean within-team spread is **2.37 wins**. The standard error on a mean win total is `2.37/sqrt(25)` = **±0.47**, so two teams whose projections differ by more than about **0.9 wins** are genuinely ranked. The season itself carries the full 2.37 SD, so two teams within about **4.7 wins** of each other will routinely finish in either order.
- At 25 runs a title share has a standard error of about **±10 points** at its widest. Read a single title as "it happened once".

### Sanity checks

- League mean comes out at exactly **14.00**, which the schedule fixes rather than the sim producing.
- Every team played exactly 28 games in all 25 runs; 25 of 25 runs produced a Floos Bowl. Every run sums to 448 wins (no tied games this batch).

## Floos Bowl, every run

| # | result | | # | result |
|---:|---|---|---:|---|
| 1 | Residents def. Raccoons 38-36 | | 14 | Classics def. Residents 21-8 |
| 2 | Sodas def. Pinecones 27-21 | | 15 | Residents def. Classics 42-29 |
| 3 | Residents def. Classics 13-0 | | 16 | Pinecones def. Residents 40-14 |
| 4 | Classics def. Residents 35-27 | | 17 | Raccoons def. Broads 28-21 |
| 5 | Raccoons def. Oysters 46-10 | | 18 | Grillmeisters def. Residents 30-12 |
| 6 | Exoticos def. Caddies 48-42 | | 19 | Broads def. Exoticos 24-17 |
| 7 | Rocks def. Classics 23-20 | | 20 | Raccoons def. Broads 20-16 |
| 8 | Raccoons def. Oysters 30-9 | | 21 | Oysters def. Raccoons 28-26 |
| 9 | Raccoons def. Residents 28-14 | | 22 | Oysters def. Exoticos 19-16 |
| 10 | Classics def. Broads 31-30 | | 23 | Residents def. Raccoons 31-22 |
| 11 | Rocks def. Extras 44-20 | | 24 | Pinecones def. Oysters 27-24 |
| 12 | Exoticos def. Oysters 30-28 | | 25 | Raccoons def. Broads 41-10 |
| 13 | Raccoons def. Rocks 26-24 | |  |  |

**10 different teams won at least one title in 25 runs.**

## Title odds

| team | titles | odds | reached the bowl |
|---|---:|---:|---:|
| Raccoons | 7 | 28% | 10 |
| Residents | 4 | 16% | 9 |
| Classics | 3 | 12% | 6 |
| Oysters | 2 | 8% | 6 |
| Exoticos | 2 | 8% | 4 |
| Rocks | 2 | 8% | 3 |
| Pinecones | 2 | 8% | 3 |
| Broads | 1 | 4% | 5 |
| Sodas | 1 | 4% | 1 |
| Grillmeisters | 1 | 4% | 1 |
| Caddies | 0 | 0% | 1 |
| Extras | 0 | 0% | 1 |

## Average wins

| team | avg | SD | min | max | titles | SD vs coin flip |
|---|---:|---:|---:|---:|---:|---:|
| Classics | 20.4 | 1.89 | 17 | 25 | 3 | 0.80 |
| Residents | 20.0 | 2.41 | 15 | 25 | 4 | 1.01 |
| Raccoons | 19.8 | 2.86 | 14 | 24 | 7 | 1.19 |
| Exoticos | 18.4 | 2.68 | 13 | 22 | 2 | 1.07 |
| Oysters | 17.9 | 2.55 | 13 | 23 | 2 | 1.00 |
| Broads | 17.3 | 2.14 | 14 | 22 | 1 | 0.83 |
| Pinecones | 15.7 | 1.57 | 11 | 19 | 2 | 0.60 |
| Jetskis | 15.6 | 2.24 | 11 | 19 | 0 | 0.85 |
| Grillmeisters | 15.6 | 2.90 | 7 | 19 | 1 | 1.10 |
| Dry Heat | 14.8 | 1.36 | 10 | 17 | 0 | 0.52 |
| Melons | 14.2 | 1.50 | 11 | 17 | 0 | 0.57 |
| Normals | 14.2 | 2.43 | 10 | 19 | 0 | 0.92 |
| Rocks | 14.2 | 2.08 | 10 | 18 | 2 | 0.78 |
| Sodas | 14.0 | 2.93 | 8 | 20 | 1 | 1.11 |
| Buffalo | 13.9 | 2.26 | 9 | 18 | 0 | 0.85 |
| Midnights | 13.8 | 2.77 | 8 | 19 | 0 | 1.05 |
| Bees | 13.4 | 1.73 | 9 | 17 | 0 | 0.66 |
| Sand Dollars | 13.4 | 3.28 | 8 | 18 | 0 | 1.24 |
| Trains | 13.3 | 3.06 | 7 | 17 | 0 | 1.16 |
| Strangers | 13.2 | 1.89 | 8 | 16 | 0 | 0.72 |
| Cranes | 13.1 | 2.22 | 9 | 18 | 0 | 0.84 |
| Rhyme | 12.6 | 1.91 | 6 | 15 | 0 | 0.73 |
| Tuesdays | 12.6 | 2.36 | 8 | 17 | 0 | 0.90 |
| Waffles | 12.2 | 2.47 | 8 | 16 | 0 | 0.94 |
| Extras | 12.0 | 2.92 | 5 | 18 | 0 | 1.12 |
| Caddies | 11.6 | 2.46 | 8 | 17 | 0 | 0.94 |
| Pops | 11.4 | 2.45 | 7 | 15 | 0 | 0.94 |
| Curd | 11.3 | 2.94 | 4 | 16 | 0 | 1.13 |
| Beans | 10.4 | 2.43 | 7 | 16 | 0 | 0.95 |
| Slippers | 9.4 | 2.33 | 4 | 14 | 0 | 0.93 |
| Phones | 9.3 | 2.61 | 5 | 16 | 0 | 1.05 |
| Monuments | 9.1 | 2.17 | 6 | 14 | 0 | 0.87 |

## Is the spread wild? No, it is narrower than chance again

Observed variance against the coin-flip benchmark (`SD = sqrt(28·p·(1-p))`, which peaks at 2.65 wins), league-wide:

| season | runs | mean within-team SD | observed variance vs coin flip |
|---|---:|---:|---:|
| 6 | 25 | 2.28 | 0.84 |
| 7 | 50 | 2.32 | 0.84 |
| 8 | 25 | 2.37 | **0.87** |

The third independent reading lands in the same place, so the spread is structural: varying opponent strength compresses a season below the single-`p` binomial. Per-team extremes (standard error about ±0.3 at 25 runs, so only the ends are worth reading): Dry Heat 0.52, Melons 0.57 and Pinecones 0.60 are the steady ones; Sand Dollars 1.24, Raccoons 1.19 and Trains 1.16 the loose ones.

## Year over year: the narrow span held

| season | team average wins, worst to best |
|---|---|
| 6 | 2.9 to 25.6 |
| 7 | 6.7 to 20.5 |
| 8 | **9.1 to 20.4** |

Season 7's forecast set the test: *if the narrow span holds into season 8 it is structural and the trading market is the likely cause; if it springs back toward season 6's range it was roster churn.* **It held, and tightened slightly.** A second full year of the trade market and the rookie draft kept the league inside about 11 wins from best to worst. That is consistent with trading redistributing surplus talent, though two seasons of one direction is still a trend rather than a mechanism.

## At the end of season 8

Fill in against this forecast (the section on season 7 in `SEASON7_PREDICTIONS.md` is the template):

- the champion, and its forecast title odds and average wins;
- actual regular-season wins per team beside the forecast average, the mean absolute miss, the correlation, and how many teams landed inside their forecast min-max;
- the biggest over- and under-performers, and whether an in-season trade (weeks 15-22) explains any of them, since the forecast cannot see those.

## Reproducing this

```bash
.venv/bin/python tools_preseason.py --db <season-start copy> --season 8 --runs 25 --parallel 5 --json out.json
```
