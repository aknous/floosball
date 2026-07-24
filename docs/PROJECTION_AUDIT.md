# Card Projection System — Audit (2026-07-24)

Audit of `cardProjection.py` + the projection path through `cardEffectCalculator` and the
frontend preview, after the fusion card changes (FP power-bar gate, per-edition power dial,
Full House / Bet Big, Champion gate reduction, Dream Team set bonus, power-bar UI).

## How projection works today
`computeEquippedProjections` (`cardProjection.py:903`) runs the **real** two-pass calculator
twice against the equipped lineup:
- **Expected** — `buildProjectionContext` sets `weekPlayerStats` to each depicted player's
  **season per-game average** (`_perGameAverageStats`, FP = `fantasy_points / games_played`),
  `isProjection=True`, `projectionVariant='expected'`.
- **Ceiling** — `_peakContext` clones it with per-player stats inflated by
  `_PEAK_STAT_INFLATION` (a hot week) for the "up to +Y" number.

Chance effects are **expected-value scaled** in projection (`cardEffectCalculator.py:678` —
output × trigger probability). The total uses `result.multFactors` via `computeFinalOutput`,
so lineup-wide factors (synergy modifier, **Dream Team**) are included in the projected total.

## Findings (severity-ranked)

### 1. [HIGH] The FP power-bar gate is applied BINARY against the season average — not expected value — **FIXED 2026-07-24**
**Fix shipped (option a).** The expected projection now weights each gated card by
`P(player clears the bar)` — the Laplace-smoothed empirical clear rate over their weekly FP
history (`WeeklyPlayerFP`), stashed on `ctx.playerWeeklyFP` in `buildProjectionContext`.
`gateRatio` returns that fraction in the expected variant (binary in live + the optimistic
ceiling), and `_applyGateRatio` SCALES the output by it. Full House (#2) scales by the
PRODUCT of its first-pass cards' clear probabilities (`ctx._firstPassGateProduct`). Live
scoring is untouched (ratios stay 1.0/0.0 → the product is exactly 1.0/0.0 → exact
fire/no-fire). Validated: `test_projection_ev_gate.py` + all live-behavior tests unchanged.

_Original finding:_
The gate (`gateRatio`) is a hard on/off, applied in `computeEffect` regardless of
`isProjection`, reading the projected `weekPlayerStats` FP. In the expected variant that FP is
the **season average**, so:
- player averages **above** the threshold → card projects at **100%** of its value, even
  though it actually fires only ~55-95% of weeks (per-week FP varies around the mean);
- player averages **below** → card projects at **0** ("dead", red in the UI), even though it
  clears the bar some weeks.
This is inconsistent with the chance-card handling, which *is* EV-scaled. The gate zeros
~25-35% of cards each week, so the error is material — worst for players near their threshold
(a 9-FP-avg WR over an 8 bar projects full but is ~a coin flip). The old varied-stat gate was
a *scaling* ramp (partial ratio → ~EV on the average); the FP power-bar redesign made it a
hard step, which is correct for LIVE scoring but wrong for an expected-value projection.

**Fix options:** (a) EV-scale the gate in projection — estimate `P(player clears the bar this
week)` from the player's weekly FP distribution (`WeeklyPlayerFP` rows exist) and scale the
card's projected output by it, exactly as chance cards are scaled; (b) cheaper interim — a
logistic on `avg − threshold` instead of the hard step; (c) at minimum, surface the gate
context so the number isn't presented as certain (see #5).

### 2. [HIGH] Full House (full_roster) projects all-or-nothing — **FIXED 2026-07-24** (see #1: scales by the joint clear probability now)
Full House fires only if EVERY first-pass card clears its bar that week. In projection the
snapshot (`_firstPassGatedCount/_On`) is computed on the season averages, so it projects
**full value if all players average above their bars, 0 otherwise** — whereas its true weekly
odds are ≈ `Π P(each clears)` ≈ ~15-20% even when every player averages above. A specific,
severe case of #1: the projected number is essentially never what the card actually returns.
Same fix — the projection needs the per-card clear probabilities to estimate the joint.

### 3. [MED] Bet Big (all_in) projects ~0 expected
`all_in` pays only above a high per-position stud line (QB22/RB22/WR20/TE14/K15). A player's
season average is usually **below** its stud line, so the expected variant projects ~0; the
peak variant (inflated stats) shows the upside. So Bet Big reads "0 expected, up to +Y" — a
fair boom-or-bust representation, but combined with #1's binary gate it can read as fully dead
when it's really a low-probability jackpot. Acceptable if #5 lands (label the uncertainty).

### 4. [LOW] Dream Team is in the projected total but unlabeled in the preview
The Dream Team FPx flows through `result.multFactors` into `projectedTotalFP` (correct), but
the projection preview doesn't render a "Dream Team" line (the *scoring* breakdown does). Add
the label to the projection's synergy display for parity.

### 5. [LOW] The projected payload carries no gate context
`_shapeCardPayload` emits `projectedFP/Mult/Floobits` + `bestCase*` but **no gate info**
(`useCardProjection` has no gate fields either). So a gated card just shows a number (or 0 =
"dead") with no signal that it's gated on the depicted player clearing N FP. Even without the
EV fix, threading `gateThreshold` + the player's projected FP into the payload lets the UI
show "projects on 9 avg vs 8 bar" so users understand the on/off.

### 6. [INFO] Champion gate reduction projects correctly but inherits #1
A Champion card's lower minted threshold is in its frozen `gate.threshold`, so projection uses
it (a champion card near its lower bar is over/understated the same way as #1).

### 7. [INFO/FIXED] Conductor crash also hit projection
The `_applyConductorBoost` `matched`-undefined crash (fixed this session) runs in the
projection path too (`calculateWeekCardBonuses` is shared) — so any projection of a lineup with
a Conductor + flat-FP card would have crashed. The fix covers projection.

## Recommendation
**#1 (+#2) SHIPPED 2026-07-24** — the projection now EV-scales the gate (and Full House by the
joint probability), the load-bearing fix. Remaining, optional: **#4** (Dream Team label in the
projection preview) and **#5** (thread `gateThreshold` + projected FP into the payload so the UI
can show the clear odds behind the number). #3/#6 need no code beyond #5.

None of these are correctness bugs in LIVE scoring — they're projection-accuracy issues: the
preview systematically over/understates gated cards because it hard-gates the average instead
of weighting by the odds.
