# Season 8 — Preseason Simulation (50 runs)

_Generated 2026-09-28 by `tools_preseason.py`, from a prod copy with season 8 scheduled and 0 of 448 games played. Raw per-run results in `season8_runs.json`._

⚠️ **This supersedes the 2026-09-27 forecast** (25 runs, raw results kept as `season8_runs_v1.json`). It is the first forecast with the **team-form rework**: `FORM_MAX` 0.14 → 0.05, the mental gain `0.5 + trait` → `2 × trait`, and `FORM_NOISE` 0.050 → 0.018 (see the form entry in `CLAUDE.md`). The rework targets game-level swing (underdogs winning by 21+ fell from 9.2% to 6.2% of games on this same snapshot), and it also makes seasons less random. That second effect is visible throughout this forecast.

## Method

- Prod database simulated against a **copy**, never prod itself. The copy was checked against a SQLite backup taken on the prod machine (prod carries a `-wal` file); rosters, attributes, teams, schedule and app settings were identical, and only four newer fan rule votes differed.
- Snapshot taken after the offseason finished and before the first kickoff, so every run starts from the **identical schedule and rosters** and the spread is the sim's own variance.
- 50 runs (two batches of 25) at `--parallel 5`, each killed when its Floos Bowl row goes final.
- ⚠️ The open season-8 Game Format vote (Frames leading) closes at 16:00 UTC. Every run reached week 1 before that, so the vote stayed open and expired at week 8 with no change: **all 50 runs are standard format**. If fans carry the Frames vote, the real season will not match this forecast.

### How much of this is signal

- Mean within-team spread is **1.99 wins**. The standard error on a mean win total is `1.99/sqrt(50)` = **±0.28**, so two teams whose projections differ by more than about **0.6 wins** are genuinely ranked. The season itself carries the full 1.99 SD, so two teams within about **4 wins** of each other will routinely finish in either order.
- At 50 runs a title share has a standard error of about **±7 points** at its widest.

### Sanity checks

- League mean comes out at exactly **14.00**, which the schedule fixes rather than the sim producing.
- Every team played exactly 28 games in all 50 runs; 50 of 50 runs produced a Floos Bowl. Runs sum to 448 wins, or 447 where a game ended tied.

## Floos Bowl, every run

| # | result | | # | result |
|---:|---|---|---:|---|
| 1 | Classics def. Residents 23-14 | | 26 | Residents def. Raccoons 28-22 |
| 2 | Raccoons def. Residents 24-16 | | 27 | Residents def. Raccoons 37-17 |
| 3 | Raccoons def. Oysters 28-7 | | 28 | Trains def. Strangers 17-15 |
| 4 | Rocks def. Raccoons 41-39 | | 29 | Residents def. Raccoons 30-28 |
| 5 | Raccoons def. Normals 27-16 | | 30 | Classics def. Residents 34-17 |
| 6 | Classics def. Residents 20-17 | | 31 | Residents def. Classics 34-16 |
| 7 | Residents def. Raccoons 24-22 | | 32 | Residents def. Exoticos 30-13 |
| 8 | Oysters def. Raccoons 17-16 | | 33 | Oysters def. Trains 18-15 |
| 9 | Raccoons def. Residents 31-11 | | 34 | Classics def. Residents 30-21 |
| 10 | Raccoons def. Sodas 37-7 | | 35 | Raccoons def. Sodas 35-18 |
| 11 | Classics def. Residents 21-20 | | 36 | Classics def. Oysters 20-19 |
| 12 | Sodas def. Raccoons 25-23 | | 37 | Pinecones def. Residents 31-27 |
| 13 | Classics def. Residents 39-21 | | 38 | Classics def. Residents 26-21 |
| 14 | Raccoons def. Oysters 24-3 | | 39 | Classics def. Sand Dollars 43-27 |
| 15 | Classics def. Sodas 31-20 | | 40 | Residents def. Pinecones 37-24 |
| 16 | Raccoons def. Oysters 38-13 | | 41 | Classics def. Broads 31-17 |
| 17 | Raccoons def. Broads 28-17 | | 42 | Oysters def. Classics 50-10 |
| 18 | Residents def. Classics 23-13 | | 43 | Grillmeisters def. Residents 26-17 |
| 19 | Residents def. Classics 30-24 | | 44 | Raccoons def. Residents 23-21 |
| 20 | Raccoons def. Residents 23-16 | | 45 | Raccoons def. Residents 38-33 |
| 21 | Sodas def. Classics 41-30 | | 46 | Residents def. Raccoons 30-22 |
| 22 | Classics def. Rocks 45-21 | | 47 | Classics def. Oysters 24-9 |
| 23 | Residents def. Raccoons 28-25 | | 48 | Raccoons def. Broads 27-16 |
| 24 | Residents def. Pinecones 36-33 | | 49 | Grillmeisters def. Residents 27-22 |
| 25 | Raccoons def. Oysters 26-23 | | 50 | Raccoons def. Residents 48-19 |

**9 different teams won at least one title in 50 runs.**

## Title odds

| team | titles | odds | reached the bowl |
|---|---:|---:|---:|
| Raccoons | 15 | 30% | 24 |
| Classics | 13 | 26% | 18 |
| Residents | 12 | 24% | 28 |
| Oysters | 3 | 6% | 9 |
| Sodas | 2 | 4% | 5 |
| Grillmeisters | 2 | 4% | 2 |
| Pinecones | 1 | 2% | 3 |
| Rocks | 1 | 2% | 2 |
| Trains | 1 | 2% | 2 |
| Broads | 0 | 0% | 3 |
| Normals | 0 | 0% | 1 |
| Strangers | 0 | 0% | 1 |
| Exoticos | 0 | 0% | 1 |
| Sand Dollars | 0 | 0% | 1 |


## Average wins

| team | avg | SD | min | max | titles | SD vs coin flip |
|---|---:|---:|---:|---:|---:|---:|
| Classics | 21.7 | 1.96 | 17 | 26 | 13 | 0.89 |
| Residents | 20.6 | 2.18 | 14 | 25 | 12 | 0.94 |
| Raccoons | 20.2 | 1.99 | 15 | 24 | 15 | 0.84 |
| Broads | 19.0 | 2.06 | 15 | 23 | 0 | 0.83 |
| Oysters | 18.3 | 2.25 | 13 | 22 | 3 | 0.89 |
| Exoticos | 18.0 | 2.30 | 13 | 24 | 0 | 0.91 |
| Pinecones | 17.2 | 1.72 | 13 | 21 | 1 | 0.67 |
| Grillmeisters | 15.7 | 1.87 | 12 | 19 | 2 | 0.71 |
| Rocks | 15.3 | 1.36 | 12 | 19 | 1 | 0.52 |
| Jetskis | 15.2 | 1.83 | 11 | 19 | 0 | 0.69 |
| Normals | 15.1 | 2.00 | 9 | 19 | 0 | 0.76 |
| Trains | 14.4 | 2.01 | 9 | 20 | 1 | 0.76 |
| Dry Heat | 14.3 | 1.29 | 12 | 16 | 0 | 0.49 |
| Melons | 14.1 | 1.78 | 10 | 19 | 0 | 0.67 |
| Buffalo | 13.8 | 1.46 | 9 | 17 | 0 | 0.55 |
| Midnights | 13.8 | 1.83 | 9 | 18 | 0 | 0.69 |
| Curd | 13.5 | 2.31 | 8 | 18 | 0 | 0.87 |
| Sand Dollars | 13.5 | 2.51 | 8 | 20 | 0 | 0.95 |
| Sodas | 13.2 | 2.25 | 7 | 18 | 2 | 0.85 |
| Strangers | 13.2 | 1.84 | 9 | 18 | 0 | 0.70 |
| Tuesdays | 12.9 | 2.10 | 7 | 16 | 0 | 0.80 |
| Waffles | 12.3 | 2.12 | 8 | 16 | 0 | 0.81 |
| Bees | 12.3 | 2.11 | 6 | 16 | 0 | 0.80 |
| Rhyme | 12.3 | 2.12 | 6 | 16 | 0 | 0.81 |
| Cranes | 11.7 | 1.91 | 7 | 16 | 0 | 0.73 |
| Extras | 10.8 | 2.20 | 6 | 15 | 0 | 0.85 |
| Pops | 10.7 | 2.25 | 5 | 16 | 0 | 0.88 |
| Caddies | 9.9 | 2.38 | 5 | 15 | 0 | 0.94 |
| Slippers | 9.8 | 2.59 | 4 | 16 | 0 | 1.03 |
| Beans | 9.6 | 1.90 | 6 | 14 | 0 | 0.76 |
| Phones | 7.8 | 1.53 | 5 | 12 | 0 | 0.64 |
| Monuments | 7.7 | 1.64 | 4 | 11 | 0 | 0.69 |


## Is the spread wild? No, and it narrowed sharply

Observed variance against the coin-flip benchmark (`SD = sqrt(28·p·(1-p))`, which peaks at 2.65 wins), league-wide:

| season | runs | mean within-team SD | observed variance vs coin flip |
|---|---:|---:|---:|
| 6 | 25 | 2.28 | 0.84 |
| 7 | 50 | 2.32 | 0.84 |
| 8 (v1, old form) | 25 | 2.37 | 0.87 |
| 8 (form rework) | 50 | 1.99 | **0.62** |

Three independent readings sat at 0.84-0.87; the form rework takes it to **0.62**. That is the mechanism working as measured: the old layer let a lucky stretch compound into a ±14% hot run, which re-rolled a team's season from one run to the next. Per-team extremes (standard error about ±0.2 at 50 runs): Dry Heat 0.49, Rocks 0.52 and Buffalo 0.55 are the steady ones; Slippers 1.03, Sand Dollars 0.95 and Caddies 0.94 the loose ones.

## Titles concentrate

The same change narrows the title race. The top three (Raccoons, Classics, Residents) win **80%** of titles here against **56%** in the v1 forecast, and 9 teams won a title in 50 runs against 10 in 25. Part of the gap is v1's 25-run noise, but the direction matches a controlled comparison on this snapshot (preseason top-five title share 80% → 88%). If more bracket chaos is wanted, `FORM_PLAYOFF_SCALE` (how much of a team's late form carries into the playoffs) is the dial for it.

## Year over year: the span widened

| season | team average wins, worst to best |
|---|---|
| 6 | 2.9 to 25.6 |
| 7 | 6.7 to 20.5 |
| 8 (v1) | 9.1 to 20.4 |
| 8 (form rework) | **7.7 to 21.7** |

The v1 forecast read the narrow span as structural, most likely the trade market. The form rework widens it again (team-average SD 2.94 → 3.48) without changing the order (corr 0.97 with v1), because rosters now decide more of the outcome. The trade-market explanation for seasons 7-8 is unaffected; it just no longer has form randomness compressing the table on top of it.

## At the end of season 8

Fill in against this forecast (the section on season 7 in `SEASON7_PREDICTIONS.md` is the template):

- the champion, and its forecast title odds and average wins;
- actual regular-season wins per team beside the forecast average, the mean absolute miss, the correlation, and how many teams landed inside their forecast min-max;
- the biggest over- and under-performers, and whether an in-season trade (weeks 15-22) explains any of them, since the forecast cannot see those.
- whether the real season's spread looks like this forecast (0.62 vs coin flip) or like the v1 forecast (0.87). That is the first live test of the form rework.

## Reproducing this

```bash
.venv/bin/python tools_preseason.py --db <season-start copy> --season 8 --runs 25 --parallel 5 --json out.json
```
