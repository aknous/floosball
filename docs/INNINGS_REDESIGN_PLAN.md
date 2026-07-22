# Innings Format Redesign — Conversion-Gated Continuation

> **Status: DESIGN ONLY — not built.** Owner-driven design, 2026-07-20. A redesign of the
> existing `InningsFormat` (`game_formats.py`, key `innings`) to remove the comeback ceiling.
> Ties into the Conversion Ladder (`docs/CONVERSION_LADDER_PLAN.md`) and builds on the shipped
> last-scoring-chance FG fix. Format background: `docs/GAME_FORMATS_PLAN.md`.

## The problem
In the current innings format a "try" is consumed by **any** possession that ends — score,
punt, or turnover (`possessionReceiver`, `game_formats.py`). Each team gets exactly 9 tries
(3 innings × 3), so the most it can ever score is `9 × maxPointsPerTry`. That is a **hard
mathematical ceiling**: once the deficit exceeds `remainingTries × maxPoints`, a comeback is
literally impossible. Baseball has no such wall — you bat until you make outs, and **scoring
never ends your at-bat**, so a big rally is always alive. We want that property without letting
games run forever (a pure "out = failure to score" model bloats at-bats because scoring is
relatively easy in football).

## The mechanic — a made top conversion keeps the try alive
Keep **3 tries per at-bat**. Change *which* outcomes consume a try:

| Drive outcome | Try consumed? | Points banked |
|---|---|---|
| Failed drive (punt / turnover / no score) | **Yes** | 0 |
| Field goal | **Yes** | FG value |
| TD + kicked XP (safe point) | **Yes** | TD + 1 |
| TD + **missed** top conversion | **Yes** | TD only |
| TD + **made** top conversion | **No — keep batting** | TD + conversion (the top rung) |

Three try-consuming outcomes end the at-bat; a made top conversion is a **bonus drive** that
doesn't count toward the three (ball spotted at the batting team's own 20 again, as any
continued at-bat drive). Whatever a drive earns is always banked — the conversion gates only
whether the at-bat *continues*, never whether the points count.

- **No hard ceiling** — a trailing team can always keep the at-bat alive by converting.
- **Self-limiting length** — conversions miss, so a streak ends on its own; no arbitrary cap
  needed. Expected streak length is set purely by the conversion success rate (the tuning knob).

## The continuation gate = the single longest conversion available
Across every rule configuration, the gate is the **one hardest / highest-value conversion
option** (`_maxLadderPoints` — the max-points `go` rung). Make it → free continuation. Anything
less — a lesser rung, the safe kick, or a miss — banks what it earned and **consumes a try**.

- **Ladder OFF (standard):** making the 2pt continues; the safe XP kick doesn't.
- **Ladder ON, `conversionKickEnabled=True`:** making the top rung continues; a shorter `go`
  rung or the kick banks its points but consumes the try.
- **Ladder ON, `conversionKickEnabled=False`:** no safe kick — **only the longest rung
  continues**; a made shorter rung scores but still consumes the try, and every TD is a forced
  conversion gamble (make the top rung → continue; anything else → try consumed).

## Strategic layer (why it's balanced)
- **Self-dampening for the leader.** A team that's comfortably ahead just kicks the safe XP (or
  takes an easy rung), ends the drive, and moves on — no incentive to gamble. So blowouts don't
  balloon the way "every TD continues" would.
- **Comeback incentive for the trailer.** A trailing team gambles the top conversion each TD:
  upside is +points *and* a bonus drive (compounding a rally); downside is the safe point
  forgone and no continuation. The risk lands on the side choosing to take it.
- **Rung choice becomes real** (ladder on, kick off): a safer short rung for likely points that
  ends the try, vs. gambling the longest rung for max points *and* a bonus drive.
- Complements the shipped **last-scoring-chance FG fix**: FGs already de-prioritized on a team's
  final chance; here a FG is generally a "settle for points, spend a try, no continuation" play.

## Open decisions
1. **Safety backstop for the no-miss case.** A team that never misses a conversion and never
   fails a drive bats forever in theory. Probability kills that in practice, but add a high
   absolute guardrail (max drives or max bonus-continuations per at-bat) so a freak streak can't
   hang a game. Rarely hit — a backstop, not a balance lever.
2. **`conversionKickEnabled=False` composition** — named above (every TD a forced top-rung
   gamble). Confirm that's the intended behavior when both rules are on.
3. **AI conversion decision** — today the XP-vs-go-for-2 choice is ~cosmetic; here it's
   strategic (trailing → gamble to extend; comfortable leader → kick and move on) plus, with a
   deep ladder + kick off, *which* rung to attempt. This is the main new play-calling logic.
4. **Mercy rule** — optional. Length is now self-limiting, so a mercy rule is only a nicety for
   lopsided games (end early when insurmountable), not a length control.
5. **Tuning knob** — the required (top) conversion's success rate is *the* dial for
   comeback-headroom vs. game length + scoring inflation. Measure the sim's innings TD-per-drive
   and conversion rates to calibrate.

## Follow-ons this reshapes
- **Progress / WP model** keys off tries consumed (the "outs"), not raw possessions. The shipped
  WP-chart fix already positions plays by `inningTry`; a bonus drive shares a try bucket
  (multiple plays per bucket — fine). `adjustGameProgress` already uses tries, so it mostly
  holds; revisit once outs ≠ possessions.
- **Supersedes** the earlier "fractional outs" idea (this reuses existing conversion machinery
  instead of a new outs currency).

## Build status (2026-07-20) — BUILT + validated (uncommitted)
Implemented on the innings format (no new toggle beyond the A/B master
`INNINGS_CONTINUATION_ENABLED`, default True). Off for every other format (byte-identical).
- **Flag** set in `floosball_game._attemptConversion`: a made TOP rung (`>= _maxLadderPoints()`)
  by the batting team → `game._inningsContinue`.
- **Consumption** in `game_formats.InningsFormat.possessionReceiver`: a flagged continuation
  returns the batting team without incrementing the try; a per-at-bat safety cap
  (`INNINGS_MAX_CONTINUATIONS` 6) and a counter reset on the at-bat flip / `onPeriodStart`.
- **AI decision** `floosball_game._chooseInningsConversion`: the standard Q3/Q4 comeback gate
  never fires in innings (quarter is always 1), so innings has its own policy — go for the top
  rung (the only continuation gate) with a desire that rises when trailing, falls when leading,
  tempered by the top rung's make odds + coach aggressiveness. Tunables `INNINGS_CONVERSION_*`.
  Two MANDATORY overrides on the last scoring chance (`isLastScoringChance`): (a) if the safe
  kick still trails but the top rung ties/wins → force the top rung (never kick a losing
  conversion — the reported down-2-on-the-last-try bug); (b) if the safe kick walks it off
  (bottom of the last inning, takes the lead) → take the guaranteed win, don't gamble it.
- **Tests**: `test_innings_continuation.py` (unit + full-game integration, 17 checks).

**Validation (headless, 150 games/config):** all games complete, no crashes/timeouts, cap never
binds (max 2 continuations in any at-bat). Ladder-off ~0.9 continuations/game, skewed to trailing
teams (86 vs 49) after a leader-dampener tune, with margins back to the baseline (no blowout
inflation). Ladder-on continuations are rarer (~0.33/game) because the 5pt@15 top-rung gate is
genuinely hard — intended (harder gate = riskier/rarer), but see tuning below.

**Open tuning (owner-feel, not blockers):**
- Ladder-on continuation frequency is low (the top rung is near-unmakeable at 15 yds), so the
  comeback lever is weak there — revisit the ladder difficulty or whether the *longest reachable*
  rung should gate rather than the absolute longest.
- Ladder-on still shows mild margin inflation (no safe-kick fallback, so leaders always score
  *something*); acceptable but worth an owner look.
- Mercy rule for lopsided games still unbuilt (optional — length is self-limiting).

## Build sketch (when greenlit)
- `possessionReceiver` (`game_formats.py`): don't increment `_inningsTries` on a TD whose top
  conversion was made; increment on every other resolution. Needs the conversion result on the
  play/possession.
- Conversion resolution: surface whether the attempt was the top rung and whether it was made.
- Play-caller: a real XP-vs-top-conversion (and rung-selection) decision keyed on game state.
- The high-cap backstop in the possession/try loop.
