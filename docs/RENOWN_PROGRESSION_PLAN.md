# Renown — Meta-Progression Spine

**Branch:** `next-season` (parked here for preservation)
**Status:** Design — **FUTURE**, NOT targeted for the next cutover. Larger than a
one-season build; captured now so the spec doesn't rot.
**Related planned pieces that plug in:** general progression layer + Survivor
(`docs/PICKEM_DEPTH_PLAN.md`), Supporter/Spectator income (memory
`fan-income-supporter-spectator`), the social-feed team page (`AUTONOMOUS_FRONT_OFFICE_PLAN.md`).

## The problem

Floosball is a collection of good-but-parallel systems — pick-em, fantasy, cards/showcase,
team/GM interactions — that all dump into **one terminal loop**: play → Floobits →
cards/powerups → slightly better at playing → more Floobits → … then nothing. Floobits are
**consumable**, so effort evaporates when spent, and **no persistent identity accumulates
across the systems.** A correct pick in week 3 leaves no lasting trace — no status, no
permanence, nothing anyone sees — so pick-em (and eventually everything) "feels pointless"
once the novelty fades and the collection is "done."

The missing piece isn't another activity. It's a **spine**: one durable thing every system
feeds that never gets spent.

## The frame: Renown

A single account-level standing — **Renown** — that every system contributes to.
Fan-side mirror of the culture the game already celebrates (players get awards + a Hall of
Fame; **you** get renown, titles, and enshrinement). Two timescales:

1. **Seasonal race (renewable):** a resetting Renown leaderboard each season that crowns a
   **Fan of the Season**. Fresh goals every year so novelty renews.
2. **Career track (permanent):** all-time Renown → **ranks → cosmetic unlocks → a Fan Hall
   of Fame** capstone. The long arc that makes season 15 matter more than season 5.

Every Renown point counts twice — once on the **this-season** tally (resets), once on the
**all-time** career track (permanent). Same currency, two ledgers.

## Three principles (locked)

- **Cosmetic-only rewards → no pay-to-win, ever.** Career/seasonal rewards are cosmetic
  (card frames, team-page flair, avatar borders, feed-post styles, titles) + recognition.
  The meta layer can never distort competitive balance.
- **Earned, never bought.** The same activities produce Floobits *and* Renown in parallel,
  but Floobits cannot buy Renown. Buyable prestige is worthless prestige.
- **Seasonal reset = the newcomer-fairness valve.** All-time renown favors veterans, so the
  seasonal race wipes clean yearly — everyone starts even, a first-year player can win Fan
  of the Season. The two-layer design solves its own accessibility problem.

## How this differs from the existing achievements

Season achievements are the discrete-quest layer; Renown is the score/standing/legacy they
ladder into. **Complementary, not competing** — achievements become **Renown-granting
quests** (reuse the existing tiered-progression + trigger plumbing as-is).

| | Season achievements (today) | Renown |
|---|---|---|
| Shape | discrete checkboxes | continuous score everything feeds |
| Lifespan | reset/once, no accrual | accumulates forever (a career) |
| Social | private completion | ranked standing / titles / Fan HoF |
| Reward | Floobits → back into the loop | prestige/status — non-consumable |
| Structure | parallel silos | one composite spine |

The single highest-leverage change: **what achievements (and good play) PAY.** Today
achievements pay Floobits, which is *why* the loop dead-ends. Paying Renown makes the exact
same activities matter, with zero new content required.

## THE CRUX — how Renown is sourced (get this right or it's paint over silos)

If any one system out-pays the others, players grind that one and we're back to silos. The
source design must actively prevent dominance:

- **Comparable ceilings per system** — a pick-em savant and a fantasy shark reach *similar*
  renown, so no lane is "the" farm.
- **Diminishing returns within a system** — the 40th great fantasy week is worth less than
  your first; maxing one lane hits a soft wall.
- **A breadth bonus** — doing all systems out-earns going deep on one. **This is the actual
  glue**: the optimal play pattern becomes "dabble across everything."
- **Earned-only** (see principles).

Nail this formula in `simcheck` against real earn-rates — it's the load-bearing decision.

### Sources (the composite)
| System | Renown from |
|---|---|
| **Pick-em / Survivor** | accuracy, streaks, survivor deep-runs |
| **Fantasy** | weekly/season finishes, leaderboard placement |
| **Cards / Showcase** | collection milestones, set completion, showcase performance — cards become a *flex that counts*, not just a Floobit engine |
| **Team / GM sentiment** | active-fan influence, "your nudges shaped a title team" |
| **Awards / achievements** | correct MVP calls; the existing achievement scaffold |

## Layer 1 — the seasonal race (Fan of the Season)

- A resetting Renown leaderboard. Top finishers earn **permanent titles** (*"Fan of the
  Season · S14"*) + cosmetics that stamp onto the career track. Prestige/cosmetic only —
  **not power, not Floobits.**
- **Global race + per-favorite-team race** ("Top Supporter of the [Team]") — the per-team
  race is more accessible and leans into fan identity, so a player can be *somebody*
  without being #1 in the whole league.

## Layer 2 — the career track (ranks + cosmetics)

- Themed rank ladder (Floosball-flavored names, NOT "Level 1–50"), **fast early /
  aspirational late** so newcomers feel momentum and veterans have a long tail.
- Each rank unlocks **cosmetics** (card frames, team-page flair, avatar borders, feed-post
  styles, profile badges).
- Capped by a **Fan Hall of Fame** for all-time greats + multi-title winners — the fan-side
  mirror of the player HoF.

## Narrative hook

The Cores could **recognize** top fans — a line in the `league_news`/`cores` feed, a nod
during a Criticality. The league acknowledging you is something no generic XP bar can do,
and it's cheap to wire onto the existing Cores voice system.

## Open questions

- **Renown source formula** — exact per-system weights, diminishing-returns curve, breadth
  bonus shape. (The crux; sim-tuned.)
- **Rank curve + names** — how many ranks, the fast-early/aspirational-late shape, the
  themed naming.
- **Seasonal → career conversion** — does the seasonal tally *become* career renown 1:1, or
  does the career track accrue separately (seasonal is just the race)?
- **Per-team race** — ship alongside the global race, or global-only first?
- **Fan HoF criteria** — all-time renown threshold vs. title count vs. both.
- **Cosmetic catalog scope** — how many cosmetics, which surfaces, generation cadence.
- **Anti-inactivity** — does seasonal renown decay for absent players, or purely accumulate
  within the season?
