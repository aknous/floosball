# Season 6 — Preseason Simulation (25 runs)

_Generated 2026-09-14 by `tools_preseason.py`, from a prod pull with season 6 scheduled and 0 of 448 games played. Raw per-run results in `season6_runs.json`._

## Method

- Prod database pulled live and simulated against a **copy**, never prod itself.
- Snapshot taken in the only window where the question is answerable: after the offseason finished and before the first kickoff. Every run therefore starts from the **identical schedule and rosters**, so the spread is the sim's own variance and not a difference in setup.
- 25 independent runs at `--parallel 5`, each killed the moment its Floos Bowl row goes final. 532 seconds wall clock.

### How much of this is signal

- Mean within-team spread across runs is **2.28 wins**, so the standard error on a mean win total is about **±0.46**. Two clubs closer than roughly **4.5 wins** apart are not separable in a single season.
- Standard error on a title share is about **±10 points**. Read the win averages confidently; read a single title as *"it happened once"*, not as a 4% chance.

### Sanity checks

- League mean comes out at exactly **14.00**, which the schedule fixes (every game has one winner) rather than the sim producing.
- Every team played exactly 28 games in all 25 runs.
- Run 16 sums to 447 wins rather than 448 — that is one tied game, arithmetic, not a fault.

## Floos Bowl, every run

| # | result | | # | result |
|---:|---|---|---:|---|
| 1 | Pinecones def. Caddies 17-8 | | 14 | Sand Dollars def. Tuesdays 27-6 |
| 2 | Pinecones def. Dry Heat 23-9 | | 15 | Waffles def. Pinecones 23-17 |
| 3 | Pinecones def. Broads 23-13 | | 16 | Pinecones def. Oysters 23-22 |
| 4 | Pinecones def. Normals 35-3 | | 17 | Strangers def. Pinecones 13-6 |
| 5 | Strangers def. Pinecones 34-23 | | 18 | Residents def. Exoticos 17-16 |
| 6 | Pinecones def. Strangers 33-16 | | 19 | Dry Heat def. Phones 27-10 |
| 7 | Pops def. Exoticos 19-16 | | 20 | Residents def. Pinecones 26-13 |
| 8 | Caddies def. Exoticos 37-13 | | 21 | Residents def. Curd 31-17 |
| 9 | Pinecones def. Residents 30-14 | | 22 | Pinecones def. Residents 20-17 |
| 10 | Residents def. Pinecones 25-18 | | 23 | Pinecones def. Caddies 33-3 |
| 11 | Strangers def. Pinecones 19-16 | | 24 | Pinecones def. Caddies 17-3 |
| 12 | Residents def. Exoticos 9-6 | | 25 | Pinecones def. Sand Dollars 54-10 |
| 13 | Pinecones def. Sand Dollars 26-13 | | | |

## Title odds

| team | titles | share | reached the Bowl |
|---|---:|---:|---:|
| Vancouver Pinecones | 12 | 48% | 18 (72%) |
| Las Vegas Residents | 5 | 20% | 7 (28%) |
| New York Strangers | 3 | 12% | 4 (16%) |
| Minnesota Pops | 1 | 4% | 1 (4%) |
| Detroit Caddies | 1 | 4% | 4 (16%) |
| San Diego Sand Dollars | 1 | 4% | 3 (12%) |
| St. Louis Waffles | 1 | 4% | 1 (4%) |
| Arizona Dry Heat | 1 | 4% | 2 (8%) |

**8 different clubs won at least one title.** Titles split 13 Corduroy / 12 Flannel — even, despite one league holding the overwhelming favorite.

⚠️ **Pinecones lost 6 of the 7 Bowls they reached and did not win.** They are in the final three times out of four; the 48% is a coin flip conditional on getting there, not a procession.

## Average wins

| team | league / division | roster | avg | SD | range | titles |
|---|---|---:|---:|---:|---|---:|
| Vancouver Pinecones | Flannel / Gingham | 85.0 | 25.6 | 1.83 | 20–28 | 12 |
| Montreal Curd | Flannel / Chambray | 81.2 | 21.0 | 2.86 | 15–26 | 0 |
| Las Vegas Residents | Corduroy / Tweed | 83.7 | 20.2 | 2.37 | 17–25 | 5 |
| Arizona Dry Heat | Corduroy / Tweed | 80.8 | 18.2 | 2.54 | 12–23 | 1 |
| San Diego Sand Dollars | Corduroy / Tweed | 82.5 | 17.6 | 1.47 | 15–20 | 1 |
| New Orleans Tuesdays | Flannel / Houndstooth | 80.5 | 17.4 | 1.55 | 14–21 | 0 |
| Mexico City Exoticos | Flannel / Paisley | 81.5 | 15.9 | 2.18 | 11–20 | 0 |
| St. Louis Waffles | Corduroy / Herringbone | 81.8 | 15.8 | 1.90 | 12–19 | 1 |
| Boston Normals | Corduroy / Denim | 79.3 | 15.6 | 1.60 | 13–19 | 0 |
| New York Strangers | Corduroy / Twill | 82.3 | 15.4 | 1.75 | 11–18 | 3 |
| Georgia Classics | Flannel / Houndstooth | 78.0 | 14.8 | 3.06 | 8–20 | 0 |
| Miami Jetskis | Flannel / Houndstooth | 80.5 | 14.7 | 2.57 | 9–20 | 0 |
| Buffalo Buffalo | Flannel / Chambray | 77.7 | 14.6 | 2.32 | 11–19 | 0 |
| Philadelphia Broads | Corduroy / Twill | 83.3 | 14.3 | 1.95 | 10–18 | 0 |
| Detroit Caddies | Corduroy / Denim | 82.5 | 14.2 | 2.50 | 10–21 | 1 |
| Los Angeles Extras | Flannel / Gingham | 75.3 | 14.1 | 2.21 | 10–19 | 0 |
| San Francisco Phones | Flannel / Gingham | 81.7 | 13.9 | 1.86 | 8–18 | 0 |
| Colorado Oysters | Corduroy / Tweed | 81.5 | 13.6 | 2.06 | 10–19 | 0 |
| Cleveland Rocks | Corduroy / Twill | 80.7 | 13.5 | 2.35 | 9–17 | 0 |
| Minnesota Pops | Corduroy / Herringbone | 80.3 | 13.3 | 3.00 | 7–19 | 1 |
| Seattle Cranes | Flannel / Gingham | 78.3 | 13.2 | 2.18 | 5–16 | 0 |
| Pittsburgh Melons | Corduroy / Herringbone | 80.0 | 13.1 | 2.39 | 7–17 | 0 |
| Salt Lake City Sodas | Corduroy / Herringbone | 78.0 | 12.1 | 2.69 | 7–18 | 0 |
| Anchorage Midnights | Flannel / Chambray | 80.7 | 12.0 | 2.57 | 6–17 | 0 |
| Chicago Beans | Corduroy / Denim | 77.0 | 11.7 | 2.43 | 7–16 | 0 |
| Seoul Trains | Flannel / Paisley | 79.2 | 11.4 | 2.92 | 7–18 | 0 |
| Washington Monuments | Corduroy / Twill | 78.2 | 10.8 | 2.06 | 7–15 | 0 |
| Anaheim Rhyme | Flannel / Paisley | 81.2 | 10.8 | 2.45 | 7–16 | 0 |
| Toronto Raccoons | Flannel / Chambray | 77.7 | 10.4 | 3.12 | 3–16 | 0 |
| Tampa Bay Bees | Flannel / Houndstooth | 79.2 | 10.3 | 2.47 | 7–17 | 0 |
| Hamburg Grillmeisters | Flannel / Paisley | 76.3 | 5.8 | 2.14 | 2–12 | 0 |
| Kansas City Slippers | Corduroy / Denim | 73.2 | 2.9 | 1.65 | 0–7 | 0 |

_Roster = mean player rating across the six roster slots._

## Three things worth knowing

### The favorite is roster strength, not a bug

Vancouver rate **85.0**, best in the league by 1.3, and the shape matters more than the mean: a **96 WR** (Spider Waitress), 87 TE, 84 QB, 83 K. They went 26-2 in season 5 and have won two of the five titles played. 48% is high but it is what the roster says.

### Montreal has the second-best record and no titles in 25 runs

**21.0 average wins, zero championships.** Curd sit in Flannel / Chambray and Vancouver in Flannel / Gingham, so Curd have to get past them in the League Championship every single time — they reached the Bowl once in 25 runs and lost it.

Las Vegas win **5 titles on fewer wins (20.2)** because they are in Corduroy and only meet Vancouver in the Bowl itself, and only if both arrive. That is the bracket working as designed, but it is the season's real competitive story: the second-best team in the league is in the wrong half of it.

⚠️ Corduroy / Tweed is the other half of the same story — **Residents 20.2, Dry Heat 18.2, Sand Dollars 17.6** are three of the league's top five in one division of four, with Oysters at 13.6 behind them. Three teams that would win most divisions will take one berth and two wildcards between them.

| division | avg wins | teams |
|---|---:|---|
| Corduroy / Tweed | 17.4 | Residents 20.2, Dry Heat 18.2, Sand Dollars 17.6, Oysters 13.6 |
| Flannel / Gingham | 16.7 | Pinecones 25.6, Extras 14.1, Phones 13.9, Cranes 13.2 |
| Flannel / Chambray | 14.5 | Curd 21.0, Buffalo 14.6, Midnights 12.0, Raccoons 10.4 |
| Flannel / Houndstooth | 14.3 | Tuesdays 17.4, Classics 14.8, Jetskis 14.7, Bees 10.3 |
| Corduroy / Herringbone | 13.6 | Waffles 15.8, Pops 13.3, Melons 13.1, Sodas 12.1 |
| Corduroy / Twill | 13.5 | Strangers 15.4, Broads 14.3, Rocks 13.5, Monuments 10.8 |
| Corduroy / Denim | 11.1 | Normals 15.6, Caddies 14.2, Beans 11.7, Slippers 2.9 |
| Flannel / Paisley | 10.9 | Exoticos 15.9, Trains 11.4, Rhyme 10.8, Grillmeisters 5.8 |

### The collapse at the bottom has a name

Hamburg went **14-14 in season 5** and forecast **5.8**. They lost **Frig Lagotis, a 96-rated RB**, to Minnesota in free agency and replaced him with a 74-rated rookie. Nothing else on their roster clears 80. Minnesota, who signed him, carry the widest spread in the league (7 to 19) and took one title.

Kansas City at **2.9** is not an anomaly — they went **1-27** in season 5 and their RB rates 64. The forecast is an improvement on what actually happened.

## Reproducing

```bash
fly ssh sftp get /data/floosball.db /tmp/floo_preseason/prod.db
.venv/bin/python tools_preseason.py \
  --db /tmp/floo_preseason/prod.db --season 6 --runs 25 --parallel 5 \
  --json docs/season6_runs.json
```
