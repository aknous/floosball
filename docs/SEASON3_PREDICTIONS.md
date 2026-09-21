# Season 3 — Preseason Simulation

_Generated from 20 independent runs of season 3 (`tools_season_montecarlo.py`). Raw: `docs/season3_runs.json`._

## Method
- Live prod snapshot pulled 2026-08-24 (`fly ssh sftp get /data/floosball.db`), engine at `3642d46`.
- Start state: seasons 1-2 complete, season 3 **scheduled but unplayed** (448 games, 0 finals).
  So every run replays the same fixture list from week 1 — no shared history inside season 3.
- Each run gets its own copy of the snapshot and its own port; runs cannot see each other.
- Simulated to the Floos Bowl `--timing=fast`, 5 concurrent, ~105s per run.

⚠️ **Read the win column, not the title column.** 20 runs puts the standard error on a mean
win total at about ±0.5, which is solid; it leaves title share at roughly ±10 points, which
is not. Titles say who is live, not who is favoured.

⚠️ **The noise floor is 2.1 wins** (mean within-team SD below). Two teams inside ~2 wins of
each other are indistinguishable over a single season, however they are ordered here.

⚠️ PF/PA were not captured this run — only wins, playoff berths and titles. Add them to
`extract()` in the tool if the next board wants them.

## Favorites board

| Rank | Team | W | L | Best | Worst | SD | Playoffs | Titles | Title% |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Rocks | 22.2 | 5.8 | 25 | 16 | 2.1 | 100% | 1 | 5% |
| 2 | Classics | 20.6 | 7.4 | 25 | 16 | 2.4 | 100% | 2 | 10% |
| 3 | Curd | 20.1 | 7.9 | 24 | 17 | 1.8 | 100% | 5 | 25% |
| 4 | Residents | 17.9 | 10.1 | 22 | 15 | 2.0 | 100% | 3 | 15% |
| 5 | Dry Heat | 17.9 | 10.1 | 21 | 15 | 1.7 | 95% | 4 | 20% |
| 6 | Pinecones | 17.8 | 10.2 | 22 | 14 | 2.4 | 95% | 2 | 10% |
| 7 | Exoticos | 17.8 | 10.2 | 20 | 14 | 1.9 | 95% | 0 | 0% |
| 8 | Bees | 17.6 | 10.4 | 22 | 14 | 2.2 | 95% | 0 | 0% |
| 9 | Buffalo | 16.5 | 11.5 | 19 | 12 | 1.8 | 85% | 0 | 0% |
| 10 | Normals | 16.0 | 12.0 | 19 | 12 | 1.8 | 75% | 0 | 0% |
| 11 | Sand Dollars | 15.9 | 12.1 | 20 | 13 | 2.0 | 70% | 0 | 0% |
| 12 | Beans | 15.8 | 12.2 | 19 | 13 | 1.6 | 70% | 0 | 0% |
| 13 | Grillmeisters | 15.7 | 12.3 | 21 | 9 | 2.9 | 60% | 0 | 0% |
| 14 | Midnights | 15.2 | 12.8 | 18 | 12 | 1.7 | 60% | 0 | 0% |
| 15 | Oysters | 15.1 | 12.9 | 19 | 11 | 2.1 | 55% | 1 | 5% |
| 16 | Caddies | 15.0 | 13.0 | 17 | 12 | 1.4 | 60% | 0 | 0% |
| 17 | Raccoons | 14.8 | 13.2 | 17 | 12 | 1.5 | 40% | 0 | 0% |
| 18 | Phones | 13.9 | 14.1 | 19 | 11 | 2.5 | 30% | 1 | 5% |
| 19 | Broads | 13.8 | 14.2 | 18 | 10 | 2.0 | 30% | 0 | 0% |
| 20 | Monuments | 12.6 | 15.4 | 16 | 9 | 2.2 | 25% | 0 | 0% |
| 21 | Melons | 12.1 | 15.9 | 15 | 7 | 2.0 | 50% | 1 | 5% |
| 22 | Slippers | 12.0 | 16.0 | 17 | 3 | 3.0 | 15% | 0 | 0% |
| 23 | Waffles | 11.8 | 16.2 | 16 | 8 | 2.5 | 30% | 0 | 0% |
| 24 | Strangers | 11.7 | 16.4 | 14 | 8 | 1.7 | 0% | 0 | 0% |
| 25 | Cranes | 11.6 | 16.4 | 17 | 8 | 2.2 | 10% | 0 | 0% |
| 26 | Extras | 11.3 | 16.7 | 16 | 6 | 2.7 | 15% | 0 | 0% |
| 27 | Sodas | 11.1 | 16.9 | 16 | 7 | 2.7 | 25% | 0 | 0% |
| 28 | Tuesdays | 10.9 | 17.1 | 14 | 7 | 2.0 | 0% | 0 | 0% |
| 29 | Rhyme | 10.9 | 17.1 | 15 | 7 | 2.7 | 15% | 0 | 0% |
| 30 | Pops | 5.2 | 22.8 | 11 | 2 | 2.1 | 0% | 0 | 0% |
| 31 | Jetskis | 3.9 | 24.1 | 11 | 1 | 2.4 | 0% | 0 | 0% |
| 32 | Trains | 3.3 | 24.7 | 7 | 1 | 1.5 | 0% | 0 | 0% |

League mean **14.0** wins of 28. Best 22.2, worst 3.3. Mean within-team SD **2.1**.

## Champions

**9 different champions in 20 runs.**

| Team | Titles | Share |
|---|---:|---:|
| Curd | 5 | 25% |
| Dry Heat | 4 | 20% |
| Residents | 3 | 15% |
| Pinecones | 2 | 10% |
| Classics | 2 | 10% |
| Melons | 1 | 5% |
| Rocks | 1 | 5% |
| Phones | 1 | 5% |
| Oysters | 1 | 5% |

## Observations

- **The best regular-season team is not the favourite.** Rocks average the most wins in the
  league and made the postseason in every run, and took the title once. Curd win it most
  often on two fewer wins a season. The postseason carries real variance, which is the
  intent.
- **Three tiers.** Rocks / Classics / Curd (20+ wins, 100% playoffs) are genuinely
  separated. The middle 26 run from ~18 down to ~11 with heavy overlap — that band is
  mostly noise. Pops, Jetskis and Trains are a floor of their own and missed the postseason
  in every run.
- **A sub-.500 division winner is normal.** Melons average 12.1 wins and reach the playoffs
  50% of the time, while Raccoons average 14.8 and reach it 40%. That is the division-winner
  berth doing what it is designed to do, and this is the clearest example of it in the data.
- **Six teams never qualified** across all 20 runs: Strangers, Tuesdays, Pops, Jetskis,
  Trains — with Slippers close behind at 15%. Strangers won season 1.
- **Widest swings:** Slippers (3 to 17 wins, SD 3.0) and Grillmeisters (9 to 21, SD 2.9).

## Reproducing

```bash
mkdir -p /tmp/mc/pristine && cd /tmp/mc/pristine
fly ssh sftp get /data/floosball.db ./floosball.db -a floosball-api
python tools_season_montecarlo.py --base /tmp/mc --season 3 --runs 20 --parallel 5
```

