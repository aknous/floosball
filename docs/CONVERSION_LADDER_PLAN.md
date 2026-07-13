# Conversion Ladder — Design Plan

> A mutable rule (dormant → switched on by a Cores vote, or during Criticality). Owner-specced 2026-07-09.
> Extends the post-touchdown try: the safe 1-pt kick and 2-pt conversion still exist, but a team can go for MORE
> points from FURTHER out — a risk/reward ladder. Builds on the reserved `extraPointPoints` /
> `twoPointConversionPoints` fields + the existing conversion-play machinery. Part of the rule-mutation direction
> (Tier 2). Tracker: `docs/NEXT_SEASON.md` / memory `rule-changes-feature`.

## The ladder
After a touchdown, the offense picks ONE rung to attempt. Higher rungs are worth more but are snapped from
further out (harder to convert). The bottom two rungs are today's behavior; the ladder adds the rest.

| Points | Line of scrimmage | Type | Notes |
|---|---|---|---|
| **1** | PAT spot (~15 yd, `patSnapDistance`) | Kick | The safe option — near-automatic for a decent kicker |
| **2** | ~2 yd (`twoPointConversionDistance`) | Run / pass | Today's 2-pt try |
| **3** | ~5 yd | Run / pass | |
| **4** | ~10 yd | Run / pass | |
| **5** | ~15 yd | Run / pass | Hardest — the goal line is a long way off |

Yardages are approximate/tunable; the ladder is a configurable list of `{points, distance}` rungs. Only 1 and 2
exist when the rule is off.

## Resolution (per rung)
- The chosen rung spots the ball at its distance and runs **one play** (run or pass) toward the end zone —
  exactly the existing `_simulate2PointConversionPlay` flow, generalized to any distance.
- **Success** = reach the end zone → those points bank. **Failure** = no points (a stuffed try, as today).
- **Harder from further** emerges naturally: more field for the defense to defend, so conversion probability
  falls with distance and rises with the offense's run/pass strength vs the defense. No dial — it comes out of
  the same play resolution as a real snap.
- The **kick (1)** stays its own near-automatic path (kicker-driven), the safe floor.

## The decision — which rung (natural emergence)
Generalize the existing `_shouldGoForTwo` into a `_chooseConversion` that ranks the rungs by:
- **Game-state math** — does a rung reach a meaningful target (tie, take-the-lead, get to a clean number of
  scores behind)? This reuses the scoring-aware helpers we already built (`_fgValue`/`_oneScore`/`_maxPossession`,
  the live TD/XP/2-pt values) — the ladder just adds more point totals a team can aim for.
- **Expected value** — `points × P(convert at that distance)`; higher rungs pay more but convert less.
- **Coach appetite + situation** — aggressiveness and risk tolerance, deficit, and time. Default behavior stays
  conservative (mostly the safe kick, like real football), and teams climb the ladder when trailing, when the
  math wants a specific total, when the coach is aggressive, or when the defense is weak (high convert odds).
The team still just tries to score; the ladder is a richer version of the existing XP-vs-2pt call, not a new dial.

## The rule (toggle + config) — `constants.py` / `game_rules.py`
- `CONVERSION_LADDER_ENABLED` (bool, default False) — the master gate. Surfaced as the **"Conversion Ladder"**
  dormant rule already teased in the Rulebook popover.
- Config: `conversionLadder` = an ordered list of `{points, distance}` rungs (the 3/4/5 rungs; 1 = the PAT and 2 =
  the existing 2-pt come from `extraPointPoints` / `twoPointConversionPoints` + `patSnapDistance` /
  `twoPointConversionDistance`, all already on `GameRules`).
- On/off mechanic + list config → another consumer of the non-scalar-rule vote generalization (with Contested
  Scoring's on/off and Drive Clock's presets). During **Criticality**, the ladder can be randomized (weird rungs).
- Tunables: the rung list (points + distances), and the conversion-probability curve vs distance.

## Blast radius
- **Higher-variance scoring** — a TD possession can now yield up to `touchdownPoints + maxRung` (e.g. 6 + 5 = 11),
  and higher rungs miss more often. Scoring spread widens; that's the point.
- **Decision-tree "one score" shifts** — `_maxPossession()` (today `touchdownPoints + twoPointConversionPoints`)
  becomes `touchdownPoints + maxLadderPoints` when the ladder is on, so the catch-up/"how many scores behind"
  logic we just made scoring-aware must read the ladder max. Small, localized update to that helper.
- **Float-safe** — rungs are integers, but `touchdownPoints` can be a float (6.4), so a TD+conversion total can be
  fractional (6.4 + 3 = 9.4). The formatScore work already handles fractional totals everywhere.
- **Pick-em / standings / MVP** — unaffected (cumulative score, read normally).
- Contained in the **post-TD conversion path** of `floosball_game.py` (`_shouldGoForTwo` /
  `_simulate2PointConversionPlay`) plus the `_maxPossession` helper.

## Frontend
- The conversion narrates like the XP/2-pt does today, extended: *"Going for 4 — from the 10!"* then the play +
  result. The play feed already renders conversion plays; add the rung to the phrasing.
- Optional: a small "ladder" indicator on the scoreboard during the try showing the target (2 / 3 / 4 / 5).
- During Criticality the ladder (like the other chaos rules) is hidden/glitched in the Rulebook, but the live try
  still narrates its point value.

## Build phases
1. **Rule + config** — `CONVERSION_LADDER_ENABLED` + `conversionLadder` rung list on `GameRules`, the non-scalar
   toggle in the vote layer, wire the dormant "Conversion Ladder" pill to the live state.
2. **Conversion play generalization** — extend `_simulate2PointConversionPlay` to take a distance + point value
   (any rung), reusing the run/pass resolution. Unit-test convert-probability falls with distance.
3. **Decision** — generalize `_shouldGoForTwo` → `_chooseConversion` that ranks rungs (EV + game-state + coach),
   defaulting conservative. Reuses the scoring-aware helpers.
4. **Decision-tree hook** — update `_maxPossession()` (and any "max points from a possession" assumption) to use
   the ladder max when enabled, so catch-up logic stays correct.
5. **Narration** — per-rung PBP phrasing ("going for N from the M").
6. **Criticality** — randomize the rung list during a Criticality (folds into the chaos rulesets).
7. **Validation** — sim with the ladder on: convert rates fall with distance, teams mostly kick but climb when
   trailing/aggressive, scoring spread widens sensibly, catch-up decisions stay right, no crashes.

## Open / revisit
- Exact distances + the convert-probability curve (5/10/15 are starting guesses — tune in validation).
- Should a FAILED higher rung ever cost field position / carry a consequence beyond 0 points? (Rec: no — same as
  a missed 2-pt today; simplest and consistent.)
- Do we cap the ladder at 5, or allow the Cores to add even wilder rungs (6-pt from midfield) during Criticality?
- Whether the kick (1) value itself should stay fixed or also be laddered (rec: leave the kick as the safe floor).
