# Drive Clock — Design Plan

> A mutable rule (dormant → switched on by a Cores vote, or during Criticality). Owner-specced 2026-07-09.
> A "shot clock" for possessions: each drive has a limit, and if the offense doesn't succeed before it expires,
> the ball turns over. Forces urgency + aggression, shortens games, and it's visible on the field. Part of the
> rule-mutation direction (Tier 2). Tracker: `docs/NEXT_SEASON.md` / memory `rule-changes-feature`.

## The mechanic
Each possession carries a **drive clock** that counts down. Reset when the offense takes over. If it reaches zero
before the offense **scores** (or, in `series` reset mode, earns a first down), the possession ends in a
**turnover on downs** at the current spot — the defense takes over there. Scoring ends the possession normally.

The clock has **two independent mode knobs** (owner: support both of each):

### Unit — what the clock counts
- **`seconds`** — game-clock seconds. The clock draws down by the game-clock time each play consumes, and
  **pauses when the game clock stops** (so the active clock-stop rules — incompletion / out-of-bounds — affect it
  too, keeping it consistent). Default limit e.g. **60s**.
- **`plays`** — a play counter, decremented once per snap regardless of time. Default limit e.g. **6 plays**.

### Reset — when the clock refills
- **`possession`** — a hard cap on the WHOLE possession (from taking the ball to scoring). No mid-drive reset.
  Brutal, high-impact: strike fast or turn it over.
- **`series`** — refills to full whenever the offense earns a **first down**. Only a *stalled* series (limit hits
  zero with no first down and no score) turns it over. A time/play-pressure layer on top of downs.

> Note: `plays` + `series` closely resembles the existing `downsPerSeries` rule (N plays to convert). It's kept as
> a valid mode for completeness; the other three combos are the genuinely new ground.

So a live Drive Clock is `{ enabled, unit, reset, limit }` — e.g. "60s, possession" or "6 plays, resets on first down".

## On expiry
- **Turnover on downs** at the current line of scrimmage (defense takes over there), via the existing
  `downsPerSeries`-aware turnover path so it stays rule-consistent.
- Yards gained on the possession count as stats normally (nothing is voided — the drive simply ends).

## Play-caller awareness (natural emergence)
When the drive clock is **low**, the offense shifts into **hurry-up + aggressive** calling — no grinding, chunk
plays, clock-stopping routes (sideline/incompletions) in `seconds` mode. This reuses/extends the existing
two-minute-drill logic, but keyed on the drive clock:
- `seconds` mode: few seconds left → same behavior as the late-game hurry-up (urgency scales as it drains).
- `plays` mode: few plays left → treat like a late down (aggressive, go-for-it, chunk-seeking).
The team still just tries to score; the drive clock is another situational input the caller reads (like the game
clock and the down), not a meta-gamed dial. Contained in the situational play-weight layer.

## The rule (toggle + config) — `constants.py` / `game_rules.py`
- `DRIVE_CLOCK_ENABLED` (bool, default False) — the master gate. Surfaced as the **"Drive Clock"** dormant rule
  already teased in the Rulebook popover.
- Config fields: `driveClockUnit` (`'seconds'|'plays'`), `driveClockReset` (`'possession'|'series'`),
  `driveClockLimit` (number — seconds or plays per the unit).
- **Vote integration:** Drive Clock is a compound/enum rule, not a scalar `field = value`. Cleanest is to offer it
  to voters as **presets** (each a full `{unit, reset, limit}`), e.g. "Drive Clock — 60s (whole drive)" vs
  "Drive Clock — 6 plays (resets on first down)". This is a second consumer of the non-scalar-rule vote
  generalization (alongside Contested Scoring's on/off). During **Criticality**, the mode + limit are randomized.
- Tunables: default limits per unit, the low-clock hurry-up thresholds, the preset menu.

## Blast radius
- **More turnovers / more possessions** — stalled drives die on the clock, so games get faster and scoring shifts.
  This is the intended effect.
- **Play-caller** reads the drive clock (moderate add to the situational layer). The decision tree already reasons
  about the game clock + downs, so this is a parallel input.
- **Win probability:** a possession near expiry is worth less; the EP model doesn't know the drive clock, so it
  may slightly overvalue a drive about to die. Minor (score-margin dominates); a drive-clock EP factor is a
  possible phase-2 refinement, not required for v1.
- **Pick-em / standings / MVP:** unaffected — the score is still cumulative and read normally.
- Stays contained in the **possession / down loop** of `floosball_game.py` (where downs + turnovers are handled)
  plus the situational play-weights.

## Frontend
- A **per-possession drive-clock display** on the scoreboard / field, adapting to the unit:
  - `seconds`: a small countdown (e.g. `0:42`), turning amber/red as it drains.
  - `plays`: a "plays left" pip/badge (e.g. `3 left`).
- A clear **turnover-on-the-clock** read in the play feed when a drive expires (*"Drive clock expired — turnover on
  downs at the 34."*).
- During Criticality the display glitches with everything else; the mode itself is hidden like the other chaos rules.

## Build phases
1. **Rule + config** — `DRIVE_CLOCK_ENABLED` + `driveClockUnit`/`driveClockReset`/`driveClockLimit` on `GameRules`,
   the non-scalar/preset toggle in the vote layer, wire the dormant "Drive Clock" pill to the live state.
2. **Clock engine** — track `driveClockRemaining` on the possession: reset on takeover; decrement by play-time
   (`seconds`) or by 1 (`plays`); pause with the game clock in `seconds` mode; refill on first down in `series`
   mode. Unit-tested across the 4 mode combos.
3. **Expiry hook** — in the possession loop, when the drive clock hits zero without a score (or first down in
   `series`), force a turnover on downs at the current spot (reuse the existing turnover path).
4. **Play-caller awareness** — feed the drive clock into the situational play-weights (hurry-up/aggressive as it
   drains), extending the two-minute-drill logic.
5. **Frontend** — the per-possession countdown/pip display + the expiry read in the feed.
6. **Criticality** — randomize the mode + limit during a Criticality (folds into the per-game chaos rulesets).
7. **Validation** — a sim with each mode forced on: confirm turnovers/possessions rise sensibly, drives expire
   correctly, the play-caller hurries up when low, no crashes, and standings/WP read normally.

## Open / revisit
- Default limits per unit (60s / 6 plays are starting guesses — tune in validation).
- Does the `seconds` clock pause on ALL clock stops or keep running on some (e.g. keep running out of bounds to
  crank urgency)? Rec: mirror the active clock-stop rules for consistency.
- Whether to add a drive-clock factor to the EP/WP model (phase 2) if the miscalibration is noticeable.
- Should a made first down in `series` mode also *briefly* reset the game-clock-stop behavior? (Probably not —
  keep it simple.)
