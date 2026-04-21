# Floosball Achievements

Complete list of achievements, grouped by category. **77 total**: 6 Rookie Goals + 48 Season Goals + 23 Secret Achievements.

- **Rookie Goals** — one-time onboarding milestones, floobit-only rewards
- **Season Goals** — per-season, re-earnable each year; tiered families + single milestones
- **Secret Achievements** — hidden until unlocked, one-time; weird feats or genuine challenges

---

## Rookie Goals (6)

One-time, floobit-only. Total pool: 150 floobits.

| Name | Trigger | Reward |
|---|---|---|
| New Fan | Pick a favorite team | 25F |
| Prognosticator | Submit your first prognostication | 25F |
| Pack Popper | Open your first card pack | 25F |
| Field General | Set your first fantasy roster | 25F |
| Deck Builder | Equip your first card | 25F |
| Patron | Make your first team contribution | 25F |

---

## Season Goals (48)

Re-earnable each season. Progress resets on season rollover.

**Reward philosophy (v0.11 rebalance):** Packs are the "finisher" for
tiered families — completing the full family at the top tier drops a
Grand (or Exquisite for Dedicated). Intermediate tiers pay floobits
that scale up. Single-shot milestones are mostly floobit + powerup
grants with packs reserved for the genuinely hard challenges.

### Single-shot milestones (6)

| Name | Trigger | Reward |
|---|---|---|
| Sharp | Earn a Clairvoyant in pick-em this season | 100F |
| Curator | Collect 15 unique cards this season | 150F |
| Tycoon | Earn 1,000 floobits this season | 150F + 1 powerup |
| Veteran | Set a fantasy roster for 20+ regular-season weeks | 500F + 1 powerup |
| Sparkler | Open your first Diamond card of the season | 150F |
| Perfect Week | Get every prognostication correct in a single week | 250F + Grand pack |

### Dedicated — manual pick-em weeks (6 tiers)

Autopicks don't count. Pack only at the VI completion tier.

| Tier | Target | Reward |
|---|---|---|
| I | 5 weeks | 50F |
| II | 10 weeks | 100F |
| III | 15 weeks | 150F |
| IV | 20 weeks | 200F |
| V | 25 weeks | 300F |
| VI | 28 weeks (every week of regular season) | 500F + Exquisite pack |

### 4-tier families — Banner Week, Racket, Dynamo, Oracle, Magnate, Podium, Pundit, Benefactor, Compound

All follow the same reward shape: floobits scale up per tier, pack only at the IV completion tier.

| Tier | Reward |
|---|---|
| I | 50F |
| II | 100F |
| III | 150F |
| IV (family completion) | 250F + Grand pack |

Targets per family:

| Family | Tier I | Tier II | Tier III | Tier IV |
|---|---|---|---|---|
| Banner Week (single-week FP) | 150 FP | 200 FP | 250 FP | 300 FP |
| Racket (single-week card-effect floobits) | 50F | 100F | 150F | 200F |
| Dynamo (season FP) | 1,000 FP | 2,000 FP | 3,500 FP | 5,000 FP |
| Oracle (season prognostication pts) | 300 pts | 700 pts | 1,200 pts | 1,800 pts |
| Magnate (season floobits spent) | 500F | 1,500F | 3,000F | 5,000F |
| Podium (top-3 weekly fantasy finishes) | 5 | 10 | 15 | 20 |
| Pundit (top-3 weekly pick-em finishes) | 5 | 10 | 15 | 20 |
| Benefactor (season team contributions) | 250F | 500F | 1,500F | 5,000F |
| Compound (single-week total FPx) | 1.2x | 1.5x | 1.7x | 2.0x |

---

## Secret Achievements (23)

Hidden until unlocked. One-time. Display as "???" on the achievements page until revealed.

Most secrets pay floobits only. Packs reserved for the two genuinely
difficult ones (Zenith and Giant Slayer).

| Name | Trigger | Reward |
|---|---|---|
| Contrarian | Every pick-em pick this week on an underdog (≥2 picks) | 150F |
| Shoestring | Full fantasy roster where every player is rated 3★ or lower | 150F |
| Gilded | Equip a full set of Prismatic/Diamond cards only | 200F |
| Giant Slayer | Top-3 weekly fantasy finish with all 3★-or-lower roster | 200F + Humble |
| Purist | Play a full week with zero cards equipped | 150F |
| Homer | Full fantasy roster entirely of players on your favorite team | 150F |
| Blank | ≤20 fantasy points in a week with a full roster | 100F |
| Cold-Blooded | Pick against your favorite team 5+ times in a season | 150F |
| Sovereign | Finish #1 on the season fantasy leaderboard | — (bragging rights) |
| Soothsayer | Finish #1 on the season prognostication leaderboard | — (bragging rights) |
| Zenith | Perfect Week + 300+ fantasy points in the same week | 250F + Grand |
| Consecration | Your favorite team wins the Floosbowl | — (bragging rights) |
| Dabbler | Purchase every type of power-up at least once (lifetime) | 150F |
| Arsenal | Hold 3+ roster swaps at the same time | 150F |
| Finicky | 5 shop rerolls in a row without buying a card between | 150F |
| Sweep | Buy every card featured in your shop in a single day | 150F |
| Mutineer | Cast the maximum fire-coach votes in a single season | 150F |
| Tribune | Cast all 20 of your GM votes in a single season | 200F |
| Monk | Never open a card pack all season (engaged users only) | 200F |
| Stalwart | No fantasy roster swaps all season (with a full roster) | 200F |
| Faithful | Favorite team misses the playoffs 3 seasons in a row | 200F |
| Devotee | 100% team funding % + end-of-season auto-contribution paid | 200F |
| Completist | Own all 4 editions (base, holographic, prismatic, diamond) of the same player | 300F |

---

## Implementation Notes

- Achievement data: seeded in [`database/connection.py::_seedAchievements()`](../database/connection.py), refreshed on every startup
- Backend manager: [`managers/achievementManager.py`](../managers/achievementManager.py)
- Toast events pushed per-user via `broadcaster.broadcast_to_user_sync` on unlock
- Secret achievements are masked in `GET /api/achievements` until completed (name = "???", description/rewards hidden)
- Rewards: floobits credited immediately; packs/powerups queued as `PendingReward` rows, claimable by the user
- Late-season pack rewards can be deferred to next season via `defer_until_season`
- Onboarding achievements backfill retroactively for existing users on their first visit to `/api/achievements`

## Admin metrics

`GET /api/admin/achievements` returns unlock counts, completion percentage, and average progress per achievement. Surfaced in the admin panel's Achievements tab.
