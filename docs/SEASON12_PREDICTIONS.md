# Season 12 — Preseason Simulation Predictions

**Generated:** 2026-06-28 (before season 12 played out)
**Method:** 15 independent fast-sim runs of season 12, each resumed from the end-of-season-11 prod state
(`floosball_prod_latest.db`), with **anomalies + awakened powers + criticality all enabled** and
prod-realistic attention (real ~161 users + season-11 fantasy/card engagement mirrored into season 12).
Each run = full 336-game regular season + playoffs through the Floos Bowl. 0 errors across all 15 runs.

---

## Predicted average regular-season wins (of 28)

| Rank | Team | Avg Wins | Rank | Team | Avg Wins |
|---|---|--:|---|---|--:|
| 1 | **Strangers** | **25.0** | 13 | Melons | 14.3 |
| 2 | Pinecones | 20.9 | 14 | Drivers | 13.9 |
| 3 | Oysters | 20.5 | 15 | Broads | 13.9 |
| 4 | Sand Dollars | 20.3 | 16 | Beans | 12.9 |
| 5 | Caddies | 20.0 | 17 | Moonlight | 12.6 |
| 6 | Phones | 18.4 | 18 | Blouses | 10.3 |
| 7 | Cranes | 18.3 | 19 | Normals | 9.8 |
| 8 | Bachelorettes | 17.7 | 20 | Dry Heat | 8.5 |
| 9 | Classics | 17.7 | 21 | Residents | 6.3 |
| 10 | Rhyme | 17.3 | 22 | Jetskis | 2.9 |
| 11 | Babies | 15.9 | 23 | Lattes | 2.7 |
| 12 | Slippers | 14.7 | 24 | Rocks | 0.9 |

## Predicted Floos Bowl champion (sim odds over 15 runs)

| Team | Titles | Sim odds |
|---|--:|--:|
| **Strangers** | 11 | **73%** |
| Sand Dollars | 2 | 13% |
| Caddies | 1 | 7% |
| Cranes | 1 | 7% |

**Headline:** the Strangers are the clear favorite — ~25 wins (≈89% win rate) and 11/15 titles.

## Simulation context (systems were live)
- Avg awakened players/season: **38** (58 pre-purge — within the prod season-8–11 band of 54–63).
- Avg Criticalities fired/season: **~3** (fast-mode inflated; real `scheduled` prod ≈ 1/season).
- Avg awakened-power fires/season: **~413**.

## Caveats
- **Fast-mode criticality rate (~3) runs higher than prod (~1)** — fast sims use a low anomaly threshold.
  Adds chaos to these runs but doesn't move the win order (outcomes track team attributes/ELO).
- **Attention was seeded statically** (season-11 engagement mirrored uniformly across season 12) —
  realistic in magnitude, not week-to-week dynamic. Affects *which* players awaken, not team win totals.

---

## Actual season 12 results (season complete — through the Floos Bowl)

_Actual W = regular-season wins of 28 (`team_season_stats`, prod). Rows ordered by predicted rank._

| Team | Predicted Avg W | **Actual W** | Diff |
|---|--:|--:|--:|
| Strangers | 25.0 | 26 | +1.0 |
| Pinecones | 20.9 | 20 | −0.9 |
| Oysters | 20.5 | 22 | +1.5 |
| Sand Dollars | 20.3 | 22 | +1.7 |
| Caddies | 20.0 | 19 | −1.0 |
| Phones | 18.4 | 20 | +1.6 |
| Cranes | 18.3 | 16 | −2.3 |
| Bachelorettes | 17.7 | 19 | +1.3 |
| Classics | 17.7 | 17 | −0.7 |
| Rhyme | 17.3 | 18 | +0.7 |
| Babies | 15.9 | 16 | +0.1 |
| Slippers | 14.7 | 11 | −3.7 |
| Melons | 14.3 | 16 | +1.7 |
| Drivers | 13.9 | 15 | +1.1 |
| Broads | 13.9 | 17 | +3.1 |
| Beans | 12.9 | 9 | −3.9 |
| Moonlight | 12.6 | 12 | −0.6 |
| Blouses | 10.3 | 13 | +2.7 |
| Normals | 9.8 | 9 | −0.8 |
| Dry Heat | 8.5 | 5 | −3.5 |
| Residents | 6.3 | 4 | −2.3 |
| Jetskis | 2.9 | 3 | +0.1 |
| Lattes | 2.7 | 5 | +2.3 |
| Rocks | 0.9 | 2 | +1.1 |

**Predicted Floos Bowl champion:** Strangers (73%) — **Actual champion: Strangers ✅**

### Accuracy
- **Champion: nailed.** Strangers were the 73% favorite and won it.
- **Mean absolute error: ~1.65 wins/team** across all 24 — the win-total model held up well.
- **Top tier held:** 4 of the predicted top 5 (Strangers, Sand Dollars, Oysters, Pinecones) finished top 5; Phones (18.4 pred) over-shot into 4th, Caddies slipped to 7th. Bottom tier held too — Rocks predicted last, finished last.
- **Biggest over-predictions:** Beans (−3.9), Slippers (−3.7), Dry Heat (−3.5) all underperformed their projection.
- **Biggest over-performers:** Broads (+3.1), Blouses (+2.7), Lattes (+2.3) beat their projection.
