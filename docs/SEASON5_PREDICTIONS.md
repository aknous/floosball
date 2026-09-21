# Season 5 — Preseason Simulation (20 runs)

_Generated 2026-09-07 from `tools_season_montecarlo.py`, seeded from a prod pull with season 5 scheduled and 0 of 448 games played._

## Method

- Prod database pulled live, season 5 **completely unplayed** — so no game is shared between runs and the spread is real.
- 20 independent simulations, each killed the moment a Floos Bowl row exists.
- ⚠️ At 20 runs the standard error is about **±0.5 on a mean win total** and **±10 points on a title share**. Read win averages confidently; read titles as *who is live*, not who wins.

## Floos Bowl winners

| team | titles | share |
|---|---:|---:|
| Arizona Dry Heat | 6 | 30% |
| Vancouver Pinecones | 6 | 30% |
| Montreal Curd | 5 | 25% |
| Las Vegas Residents | 1 | 5% |
| St. Louis Waffles | 1 | 5% |
| Detroit Caddies | 1 | 5% |

**6 different clubs won at least one title in 20 runs.**

⚠️ **THE TITLE IS EFFECTIVELY A THREE-HORSE RACE: Vancouver, Arizona and Montreal took 17 of
20 (85%).** The other three titles are one apiece and, at ±10 points of standard error, are not
distinguishable from zero — read them as "it happened once", not as a 5% chance.

## ⚠️ How separable are these teams, really

- The top three average **23.9 wins**; the other 29 average **13.0**. The gap from 3rd to 4th is
  **5.5 wins** — a genuine tier, not noise.
- But the mean within-team spread across runs is **2.2 wins**, so **two clubs closer than about
  4.3 wins apart are not separable in a single season.** Ranks 4 through 21 all sit inside 4.4
  wins of each other: that whole block is one undifferentiated mass, and whichever of them
  finishes 4th in the real season will have done so mostly by luck.
- The exception at the bottom is real: Kansas City average **1.7 wins** with a range of 0-4,
  which is more than five standard deviations clear of the next club up.

## Average wins

| # | team | avg wins | sd | range | titles | playoffs |
|---:|---|---:|---:|:--:|---:|---:|
| 1 | Vancouver Pinecones | 25.1 | 1.8 | 22-28 | 6 | 100% |
| 2 | Arizona Dry Heat | 23.6 | 1.7 | 20-26 | 6 | 100% |
| 3 | Montreal Curd | 22.9 | 1.9 | 20-27 | 5 | 100% |
| 4 | San Diego Sand Dollars | 17.4 | 2.2 | 14-22 | 0 | 90% |
| 5 | Boston Normals | 17.2 | 1.5 | 14-20 | 0 | 100% |
| 6 | Las Vegas Residents | 16.9 | 1.9 | 14-22 | 1 | 90% |
| 7 | Colorado Oysters | 16.1 | 3.5 | 11-24 | 0 | 65% |
| 8 | St. Louis Waffles | 16.1 | 2.4 | 12-23 | 1 | 90% |
| 9 | San Francisco Phones | 15.8 | 1.8 | 13-19 | 0 | 85% |
| 10 | Toronto Raccoons | 15.7 | 2.2 | 13-21 | 0 | 70% |
| 11 | Mexico City Exoticos | 15.5 | 2.3 | 12-21 | 0 | 80% |
| 12 | New York Strangers | 14.8 | 2.2 | 11-20 | 0 | 65% |
| 13 | Georgia Classics | 14.7 | 1.8 | 11-19 | 0 | 60% |
| 14 | Detroit Caddies | 14.7 | 2.1 | 10-18 | 1 | 60% |
| 15 | Philadelphia Broads | 14.5 | 2.4 | 10-19 | 0 | 45% |
| 16 | Cleveland Rocks | 14.3 | 2.5 | 11-20 | 0 | 45% |
| 17 | Buffalo Buffalo | 14.2 | 2.3 | 10-20 | 0 | 60% |
| 18 | Miami Jetskis | 13.7 | 2.6 | 10-20 | 0 | 60% |
| 19 | Hamburg Grillmeisters | 13.6 | 2.9 | 7-17 | 0 | 65% |
| 20 | Tampa Bay Bees | 13.1 | 3.0 | 8-18 | 0 | 45% |
| 21 | New Orleans Tuesdays | 13.0 | 2.7 | 7-18 | 0 | 30% |
| 22 | Chicago Beans | 12.7 | 1.6 | 9-16 | 0 | 15% |
| 23 | Anchorage Midnights | 12.1 | 2.8 | 7-20 | 0 | 25% |
| 24 | Seattle Cranes | 12.1 | 1.5 | 9-15 | 0 | 15% |
| 25 | Pittsburgh Melons | 11.8 | 2.2 | 7-15 | 0 | 25% |
| 26 | Salt Lake City Sodas | 11.3 | 2.0 | 7-16 | 0 | 5% |
| 27 | Washington Monuments | 11.3 | 1.9 | 7-14 | 0 | 0% |
| 28 | Seoul Trains | 9.0 | 2.3 | 5-15 | 0 | 5% |
| 29 | Minnesota Pops | 8.4 | 2.6 | 4-15 | 0 | 5% |
| 30 | Anaheim Rhyme | 7.2 | 2.5 | 4-12 | 0 | 0% |
| 31 | Los Angeles Extras | 7.2 | 1.1 | 5-9 | 0 | 0% |
| 32 | Kansas City Slippers | 1.7 | 1.0 | 0-4 | 0 | 0% |
