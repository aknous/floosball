# Sideline Goals — Design Plan

> A mutable rule (dormant → switched on by a Cores vote, or during Criticality). Owner-specced 2026-07-09.
> Quidditch-style: hoops on the sidelines the QB can throw the ball through for **bonus points mid-drive**. A make
> doesn't end the drive; a miss is a turnover. A distinctive scoring avenue layered onto a normal possession.
> Part of the rule-mutation direction (Tier 2). Tracker: `docs/NEXT_SEASON.md` / memory `rule-changes-feature`.
> NOTE: the **graphical representation is the hardest part** and is scoped as its own phased problem below.

## The mechanic
On any down, the offense may call a **hoop shot** instead of a normal run/pass — the QB throws at a sideline hoop:
- **Make** → the hoop's points bank, the **drive continues**. It's a normal play, so it **consumes the down** and
  gains **no yards** (you spent a down for the point, so repeated attempts march you toward a turnover on downs —
  a real cost even on a make).
- **Miss** (the common failure) → **turnover** at the current line of scrimmage (the ball sails out toward the
  sideline, dead; the defense takes over there, no return — like a turnover on downs).
- The hoop is **worth a fixed number of points** (default e.g. **1**, tunable).

## The hoop
- A single hoop per sideline (one target for the shot). Exact field position + geometry pinned at build with the
  frontend (it drives both the difficulty and the visual).
- **Difficulty scales with the throw** — distance/angle from the ball to the hoop. Comes out of the QB's accuracy
  / arm against that difficulty, so it **emerges from the passer**, not a dial.

## Resolution (natural emergence)
- Base success = **QB accuracy/arm attribute vs the hoop's difficulty** (distance/angle).
- **Defense can contest** — pass rush / coverage lowers the success probability (a pressured or covered shot is
  harder). But because the target is **outside the field of play**, a contested miss is normally just a dead ball
  → turnover at the spot, **no interception/return**.
- **Interception is rare** and only on a **badly errant throw or a tip** — if the ball is knocked back into the
  field of play, a defender can pick it (and potentially return it). Small chance, scaling with how bad the throw
  was + the defensive pressure. Otherwise a miss is a clean turnover-on-downs-style takeover at the spot.

## The decision — when to attempt (natural emergence)
A hoop shot is a **play choice** the coach can call, weighed like any gamble:
- More likely when the drive is **stalling** (a way to salvage points), for an **aggressive** coach, when the
  **bonus point matters** to the game-state math (reuse the scoring-aware helpers — a point that ties/leads/gets to
  a clean total), or when the **shot is makeable** (good QB, short angle, weak coverage).
- Kept rare/situational by default — it's a novelty gamble (spend a down + risk a turnover for a point), not a
  every-down option. The team still mostly runs normal offense.

## The rule (toggle + config) — `constants.py` / `game_rules.py`
- `SIDELINE_GOALS_ENABLED` (bool, default False) — the master gate. Surfaced as the **"Sideline Goals"** dormant
  rule already teased in the Rulebook popover.
- Config: `sidelineGoalPoints` (points per make) + the hoop position/difficulty parameters.
- On/off mechanic → another consumer of the non-scalar-rule vote generalization (with Contested Scoring, Drive
  Clock, Conversion Ladder). During **Criticality**, the hoop value/difficulty can be randomized.
- Tunables: point value, hoop position, the accuracy-vs-difficulty curve, the tip/INT chance.

## Blast radius
- **New scoring avenue + a risky play choice.** Scoring shifts (bonus points), and drives can end on a missed
  hoop. Both intended.
- **Play-caller** gains a new play type + the situational logic to call it (moderate add). The decision tree
  already reasons about game state; this is a new option node, not an inversion.
- **Win probability:** hoop points are cumulative and read normally; a would-be hoop shot that misses reads as a
  turnover to WP. The EP model doesn't know about the hoop, so it slightly under-weights the option — minor, and a
  phase-2 refinement at most.
- **Pick-em / standings / MVP:** unaffected (cumulative score). Stats: a made hoop is its own stat line (hoop
  goals); a miss is a turnover.
- Engine-side it's contained: a **new play type** in the play-calling + resolution path of `floosball_game.py`,
  plus the turnover handling (reuse the existing turnover-on-downs path).

## Frontend — the hard part (phased)
This is the mechanic's real cost. The field/drive visualization has to convey hoops on the sidelines and a throw
through one. Phase it:
- **v1 (ship-first):** a clear **play-feed beat** (*"HOOP SHOT — Rennick threads it through the near-side hoop! +1,
  drive continues."* / *"HOOP SHOT — off the rim, turned over at the 34."*) plus a **simple field marker** for the
  hoop and a shot indicator on the existing field graphic. Fully conveys the mechanic without new art.
- **v2 (polish):** a proper field rendering of the sideline hoops + a throw arc/animation through the hoop. Its own
  frontend design task; don't block the mechanic on it.
- During Criticality the hoop (like the other chaos rules) is hidden/glitched in the Rulebook, but a live shot
  still narrates its point value.

## Play-caller refinement (2026-07-19)
Two down/score-aware rules added to `_shouldAttemptHoopShot` (a make or miss both consume
the down with **no yardage**, so the down cost is the whole point):
- **Never on the penultimate down** (previously only the final down was blocked). A hoop on
  3rd-of-4 forces 4th down regardless of the result, so normal play now shoots only on
  1st/2nd down (guard: `down >= downsPerSeries - 1`). The final-down block stays absolute
  (a hoop there forfeits the scoring play).
- **Late-game deficit / tie awareness** (`_hoopPointsNeeded`): when late (Q4 clock ≤
  `SIDELINE_GOAL_DESPERATION_SECS`, or any OT) and a hoop point is what reaches a tie/lead,
  the offense reliably banks BOTH hoops (`SIDELINE_GOAL_DESPERATION_CHANCE` ≈ 0.92). All
  bands derive from `_fgValue()`/`_maxPossession()`, so they stay correct under MUTATED
  FG/TD values (nothing hardcoded to 3/6).
  - `critical` → mandatory, lifts the penultimate-down + hurry-up guards (still never the
    final down — a FG/kick there is safer). Two cases: (a) TRAILING and no single
    conventional score reaches the deficit alone, but score + remaining hoops does
    (default rules: deficit 9–10); (b) TIED in **sudden death** (`_hoopScoreWinsNow`:
    2nd+ OT, or 1st OT after both guaranteed possessions) — a single hoop point wins outright.
  - `helpful` → reliable on the affordable (1st/2nd, non-hurry) downs only; doesn't burn a
    late down a real scoring drive still needs. Cases: a FG can't tie/win but FG + hoops
    can while a TD alone would (deficit 4–5); or TIED and the go-ahead point isn't
    game-ending (1st-OT-before-both-possessions, or a regulation tie late).
  Committed regression suite: `test_sideline_goals.py` (Scenario-based, real engine
  decisions incl. a full-playCaller integration check; covers the down guards, all
  need-tiers, OT tie-break, hurry-up interaction, and mutated fg/td bands). Also
  validated in a headless 400-game STANDARD-format live run with the rule ON: 0 crashes,
  9 games reached OT, hoop shots fire end-to-end, and the invariants held across 5,565
  attempts (no final-down attempts; the only 3rd-down attempts were late+critical
  overrides; OT tie-break shots resolved cleanly). NOTE: base volume ran ~14 shots/game
  on evenly-matched headless teams — higher than the plan's earlier ~2.7/game figure and
  driven entirely by the pre-existing `SIDELINE_GOAL_ATTEMPT_INRANGE` (0.55) base rate,
  not this change; worth a separate balance pass if it holds on real league rosters.

  **Judgment call:** a regulation tie in **hurry-up** (final ~2:30) does NOT force a hoop —
  a mid-drive go-ahead point there hands the opponent the ball back rather than walking it
  off, and burns a down you want for the actual scoring drive. OT sudden-death ties DO force
  it (a make ends the game). Flip regulation-tie to `critical` if maximum aggression is wanted.

## Build status (2026-07-12)
**BUILT (phases 1–6) on `feature/rule-changes`** — backend `f6e5dce`, frontend `6756272`.
Rule gate + config, the hoop-shot play type (make/miss/tip resolution), the play-caller
option, turnover reuse, narration, and frontend v1 (feed badge + dormant pill) are all in.
Validated live: make rate emerges from the QB (42/53/67% by skill, 51% overall), ~2.7
shots/game (rare), tips→returnable INTs, turnovers-on-miss correct, no crashes; OFF by
default is byte-identical. **Deferred:** phase 7 (Criticality randomization) and phase 9
(v2 field art). Tunables live in `constants.py` `SIDELINE_GOAL_*`. This unblocks the
`bust` game format (which bundles Sideline Goals on).

## Build phases
1. **Rule + config** — `SIDELINE_GOALS_ENABLED` + `sidelineGoalPoints`/hoop params on `GameRules`, the non-scalar
   toggle in the vote layer, wire the dormant "Sideline Goals" pill to the live state.
2. **Hoop-shot play type** — a new play in `floosball_game.py`: QB accuracy/arm vs hoop difficulty − defensive
   contest → make (points, consume down, continue) / miss (turnover at spot) / rare tip-INT (returnable).
   Unit-test make-rate vs QB skill + distance + coverage.
3. **Play-caller** — add the hoop-shot option to the situational play-weights (rare, stalled/aggressive/bonus-math
   driven), reusing the scoring-aware helpers.
4. **Stats + turnover** — hoop-goal stat line; reuse the turnover-on-downs path on a miss.
5. **Narration** — hoop-shot PBP phrasing (make / miss / the rare tipped pick).
6. **Frontend v1** — feed beat + simple field marker/indicator.
7. **Criticality** — randomize hoop value/difficulty during a Criticality.
8. **Validation** — sim with it on: make-rate tracks QB skill/coverage, teams attempt it rarely + situationally,
   turnovers-on-miss land correctly, scoring shifts sensibly, no crashes.
9. **Frontend v2 (later)** — the full sideline-hoop field rendering + throw animation.

## Open / revisit
- Exact hoop position + geometry (drives both difficulty and the visual) — settle with the frontend.
- Should there be one hoop per sideline (pick the near one) or a single fixed target? (Rec: near-side hoop,
  difficulty from the angle/distance.)
- The tip/INT chance curve — how rare, and whether a returned pick can score (rec: yes, it's a live ball once
  tipped back in).
- Whether v1's "simple field marker" is enough for launch or the mechanic should wait on v2 art (owner call —
  this is the graphical concern flagged up front).
