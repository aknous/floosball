# Renown — Meta-Progression Spine

**Branch:** `next-season` (spec parked here; build targets the cutover AFTER next)
**Status:** Design — **specced against real data 2026-07-31**. Not built; zero code.
**Scope decided 2026-07-31 (owner):** retention-led, v1 = **foundation + career ranks**,
ships at the season-after-next cutover.
**Related:** Supporter/Spectator income (memory `fan-income-supporter-spectator`), the
social-feed team page (`AUTONOMOUS_FRONT_OFFICE_PLAN.md` Part D), Survivor.
⚠️ Earlier revisions referenced `docs/PICKEM_DEPTH_PLAN.md` for the general progression
layer and Survivor. **That file does not exist** — either never written or lost. Survivor
survives only as the one-paragraph entry in `docs/NEXT_SEASON.md`.

## The problem

Floosball is a set of good-but-parallel systems — pick-em, fantasy, cards/showcase,
team/GM — that all dump into **one terminal loop**: play → Floobits → cards/powerups →
slightly better at playing → more Floobits → … then nothing. Floobits are **consumable**,
so effort evaporates when spent, and **no persistent identity accumulates**. A correct pick
in week 3 leaves no trace — no status, no permanence, nothing anyone sees.

### Measured, not assumed (dev DB, prod-derived, seasons 1–15)

Engaged users per season, counting deliberate actions only:

| | S1 | S5 | S10 | S15 |
|---|---|---|---|---|
| engaged users | 28 | 28 | 22 | **14** |

**And the leak is at the front, not the back.** Career length across 152 users with any
recorded activity:

| seasons active | 1 | 2 | 3–9 | 10+ |
|---|---|---|---|---|
| users | **65** | **31** | 20 | 36 |

**Median career = 2 seasons. 63% are gone by season 3.** There is also a hard core of 13
users active in all 16.

This relocates the design. The original spec aimed at "make season 15 matter" — but a
career track rewarding season 15 serves the ~13 people who already stayed. **The retention
window that matters is seasons 1–3**, which makes the *early* ranks the entire mechanism
and the late ranks a tail for the loyal few. The ladder's "fast early / aspirational late"
shape was already right; the data says it is load-bearing rather than a nicety.

### The siloing premise was wrong

The original crux assumed players silo into one system, making a **breadth bonus** the
glue. In the data, every user active in the last three seasons touches **at least three of
five systems**; most touch four or five. Nobody is siloed. Breadth is the observed
behavior, not the goal. **The breadth bonus is cut** — see "Why there is no breadth bonus".

## The frame: Renown

A single account-level standing — **Renown** — that every system contributes to. Fan-side
mirror of the culture the game already celebrates: players get awards and a Hall of Fame,
**you** get renown, ranks, and eventually enshrinement.

## Principles

- **Cosmetic-only rewards → no pay-to-win, ever.** Rewards are cosmetic (badges, frames,
  flair, titles) plus recognition. The meta layer can never distort competitive balance.
- **Earned, never bought.** The same activities produce Floobits *and* Renown in parallel,
  but Floobits cannot buy Renown. Buyable prestige is worthless prestige.
  → This has a sharp consequence the first draft missed: **card/pack purchases cannot be a
  renown source**, because they are literally bought. Cards pay renown through *showcase
  performance*, not acquisition.
- **Renown never decays and is never spent.** It is the one number that only goes up. That
  property is the whole point — it is what Floobits are not.

## How this differs from achievements

Achievements are the discrete-quest layer; Renown is the standing they ladder into.
**Complementary** — achievements become renown-granting quests, reusing the existing tiered
progression and trigger plumbing as-is.

| | Achievements (today) | Renown |
|---|---|---|
| Shape | discrete checkboxes | continuous score everything feeds |
| Lifespan | reset/once, no accrual | accumulates forever |
| Social | private completion | public rank / badge |
| Reward | Floobits → back into the loop | prestige — non-consumable |

## Unit and scale (locked)

The first draft never defined what a renown point was worth, which left every downstream
number unspecifiable. Pinned:

> **A season of strong, all-round engagement pays ~1,000 Renown.** Five systems × 200 max.

Validated against 15 real seasons — see "Validation" below. A median engaged season pays
~300–400; the best season on record under this formula scores 1,000 (the cap binds, as
intended).

## Data model — a ledger, not a counter

**`renown_events`** — append-only.

| column | notes |
|---|---|
| `user_id`, `season`, `week` | week is the award cadence (see below) |
| `source` | `pickem` / `fantasy` / `cards` / `team` / `goals` |
| `amount` | int, always positive |
| `detail_json` | the production figure + target that produced it, for display and audit |

Plus **`user_renown`** as a materialized read cache (`career_total`, `rank_key`,
`updated_at`) — fully recomputable from the ledger, never authoritative.

**Why a ledger is not optional.** The source formula is the risky part and will be retuned.
A running total means the first retune silently orphans everyone's standing with no way to
recompute it. A ledger makes a retune a replay. It also makes the two-ledger split free
(one row set, two aggregations) if the seasonal race is added later, and the backfill writes
the same rows the live path writes — one code path, not two.

## Award cadence — weekly, and this is a requirement not a preference

Renown accrues **weekly**, scored on running season totals, awarding the delta.

Season-end scoring would be simpler and is **wrong for this feature**: a player who churns
during their first season would never see a single rank. Since seasons 1–3 are the entire
retention window, renown that only lands at season end misses the people it exists to keep.

## The source formula

Per user, per system, per week, on the running season total:

```
renown = FLOOR + SHARE × min(1, (production / TARGET) ** 0.5)
FLOOR = 40      SHARE = 160      per-system cap = 200
```

- **FLOOR** pays for showing up at all. It is what makes season 1 feel immediately
  productive, and it is what serves the churn window.
- **SHARE** pays for how much you did, against a **fixed target** — not a percentile.
- **`** 0.5`** is the diminishing-returns curve the original spec asked for, made explicit.
- Identical FLOOR/SHARE across systems *is* "comparable ceilings".

### Targets (calibrated to observed p90 of per-user-season production)

| source | production measure | TARGET |
|---|---|---|
| `pickem` | manual pick-em points earned | 1,500 |
| `fantasy` | `fantasy_rosters.total_points` | 2,800 |
| `cards` | showcase dividend Floobits earned | 2,000 |
| `team` | team + facility contributions | 7,000 |
| `goals` | achievements completed this season | 30 |

### Absolute, not percentile — a tested decision

The first prototype scored each system by **percentile within that season's cohort**. It
fails on real data: as the cohort grew 27 → 42 users, the median yield fell **209 → 63 for
no change in behavior**, because percentile scoring is zero-sum and a growing league dilutes
everyone. For a career track that is backwards — doing the same thing must pay the same.
Absolute scoring holds the p10 flat at ~112 across all fifteen seasons.

Keep percentile in reserve for the **seasonal race** if it is ever built: ranking against
peers is exactly what a race is for. The two ledgers want different scoring philosophies,
which also answers the old open question about seasonal→career conversion — **they are
scored separately, not converted.**

### Auto-picks are excluded

**80–85% of all pick-em points come from auto-picks.** Paying renown on raw pick-em points
would make the single largest source a reward for a setting toggled once. Only manual picks
count, and only if made in ≥3 distinct weeks.

### Why there is no breadth bonus

Per-system FLOORs already produce a near-linear breadth reward with no extra mechanism.
Measured on S15 under this formula:

| systems touched | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| median renown | 63 | 233 | 397 | 613 | 775 |

A separate breadth bonus would be a second mechanism doing a job the floors already do.

### Known weak link — `team`

Team contributions are denominated in Floobits, which correlate with fantasy income. It is
the one source that partially double-counts, and the one closest to the "earned, not bought"
line. Kept for v1 because it is the only source representing the club-support axis, but it
is the first candidate to be re-based (onto something like contribution *consistency*
rather than volume) if the distribution looks wrong live.

## The rank ladder

Fast early, aspirational late. Names are a **draft** — owner's call, per the naming
philosophy (durable, no internet-era phrasing, sounds right with a suffix). Deliberately
avoids collisions with existing Patron/Benefactor/Underwriter achievements, the powerup
catalog, and pack tiers.

| # | Rank | At | Reached by (of 79 users, 15 seasons) | Median seasons |
|---|---|---|---|---|
| 1 | Walk-Up | 0 | 79 | — |
| 2 | Regular | 60 | 76 | 1 |
| 3 | The Faithful | 180 | 69 | 1 |
| 4 | Season Ticket | 400 | 53 | 2 |
| 5 | Booster | 800 | 42 | 3 |
| 6 | Stalwart | 1,500 | 33 | 4 |
| 7 | Standard-Bearer | 2,600 | 25 | |
| 8 | Fixture | 4,200 | 18 | |
| 9 | Institution | 6,500 | 11 | |
| 10 | Immortal | 9,500 | 5 | |

The curve is deliberately shaped around the churn data: **two ranks land inside season 1**
(median first season pays 315), and the median first-season player finishes just short of
Season Ticket — a near-miss at the exact moment they would otherwise drift, which is the
strongest available return hook.

## Cosmetic surface for v1 — one, not five

The original spec listed card frames, team-page flair, avatar borders, feed-post styles and
profile badges in a single bullet. That is five separate rendering surfaces and is very
likely the largest build cost in the whole plan.

**v1 ships exactly one: a rank badge attached to the username**, rendered by one shared
component wherever usernames already appear — The Bleachers feed, fantasy leaderboard,
pick-em leaderboard. One build, three surfaces, and it is the recognition mechanic itself
rather than decoration around it. Everything else is a later catalog.

## Backfill — and why it is also the tuning harness

Four of the five sources are historically complete (`pick_em_picks`, `fantasy_rosters`,
`currency_transactions`, `user_achievements` all carry `season`). Only sentiment is too new.

So the source formula gets written as a **pure function over historical rows first**, run
across 15 real seasons, and tuned against the actual distribution — *then* wired live. The
same run writes the seed ledger.

This matters because the original plan said to tune the formula in `simcheck`, which cannot
work: simcheck simulates the **league**, and pick-em accuracy, fantasy finishes and card
performance are **user** behavior no sim produces. The historical replay is the only real
harness available, and it is a good one.

Backfilling also means the career track **launches non-empty**. A career track where every
15-season veteran starts level with a newcomer has no career in it for a year.

## Validation (prototype, 15 real seasons)

Scripts: `renown_proto.py` (percentile variant, rejected) and `renown_abs.py` (absolute
variant, adopted) — scratch only, to be rewritten as the real backfill.

| | |
|---|---|
| per-season yield | p10 ~112 (stable across all 15), p50 117–449, p90 ~800, max 1,000 (cap binds) |
| career totals | p10 158, p50 1,077, p90 8,764, max 10,561 |
| first season | p10 98, p50 315, p90 523 |
| ladder | 76/79 reach rank 2, 5/79 reach rank 10 |

## Explicitly OUT of v1

Deferred, not cancelled: the **seasonal race** and Fan of the Season; the **per-team race**
(the data kills this outright for now — 14–28 engaged fans across 24 teams means most teams
would have zero or one supporter, and "Top Supporter" of a fanbase of one is an
anti-reward); the **Fan Hall of Fame** capstone; the **cosmetic catalog** beyond the rank
badge; **Cores recognition** of top fans; **Survivor**.

## Open questions

- **Rank names** — the ladder above is a draft; naming is the owner's call.
- **Is `team` the right fifth source**, given the Floobit double-count? Alternatives:
  contribution consistency, or replacing it with the sentiment/social axis once that layer
  has history.
- **Does the rank badge show rank name, or name + a progress hint** toward the next rank?
  The near-miss hook argues for showing progress.
- **New-player floor** — a player joining at week 20 has fewer weeks to earn in. Career
  renown is cumulative so this self-corrects, unlike a seasonal race; confirm that is
  sufficient rather than pro-rating.
- **Fan HoF criteria** (when built) — all-time renown threshold vs. title count vs. both.
