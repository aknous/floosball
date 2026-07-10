# Contested Scoring — Design Plan

> A mutable rule (dormant → switched on by a Cores vote, or during Criticality). Owner-specced 2026-07-09.
> Rugby-flavored: crossing the goal line is only a *provisional* touchdown — the scorer must **complete an
> action** to bank the points, and the defense gets one **last-resort contest** to cancel it. Emerges from
> player attributes, narrates as a distinct beat, and stays self-contained in the scoring resolution.
> Tracker: `docs/NEXT_SEASON.md` / memory `rule-changes-feature`. Part of the rule-mutation direction (Tier 2).

## The core loop
1. A ball-carrier crosses the goal line for a TD → **provisional score** (not yet on the board).
2. A **contest** fires: a contest *type* is rolled; the scorer attempts the action; the best-suited defender tries to stop it.
3. **Scorer wins (the common case)** → the TD banks its points, then the normal PAT / 2-pt flow runs.
4. **Defense wins (rare — a last resort)** → **no points**. The ball returns to the play's **starting line of
   scrimmage**, the **down advances**, and the offense keeps possession (a stuffed 3rd-down score → 4th down
   from the old spot; on the LAST down it's a **turnover on downs**). The rushing/receiving **yards still count
   as stats**; no TD is credited and there's no field-position gain.

Because it resolves instantly at the moment of scoring, the final score is correct immediately — so WP,
pick-em, standings, and MVP all just read the real outcome. No score-*model* ripple.

## Trigger — which scores are contested
- **Rushing, receiving, and QB-scramble touchdowns only.**
- **Not** contested: field goals (a kick, no "action"), extra points / 2-pt tries (their own resolution),
  safeties, and defensive/return TDs (v1 — the defense already made the play).
- Gated by the `CONTESTED_SCORING_ENABLED` rule (off by default).

## The contest
A small **pool of contest types** is rolled per score, each keyed to a *different* attribute so different
players shine, and each narrated distinctly. (Exact attribute names pinned at build against `floosball_player.py`;
the themes below map to real stats: `speed`, `power`, `agility`, `xFactor`, `creativity`.)

| Type | The action | Scorer attribute | Defender / resolution |
|---|---|---|---|
| **Dunk** | Slam the ball over the crossbar | `power` (+ `xFactor`) | vs the defending team's best leaper (`power`/`agility`) — head-to-head |
| **Race** | Sprint sideline-to-sideline across the end zone before a defender tags you | `speed` | vs the defending team's **fastest** player (`speed`) — head-to-head |
| **Arm wrestle** | Pin the last defender at the goal line | `power` | vs the defending team's **strongest** player (`power`) — head-to-head |
| **Beauty contest** | Scorer and defender strike a pose; "judges" score it | `xFactor` (+ `creativity`) | vs the defending team's flashiest player; judges = attribute + randomness |
| **Backflip** | Backflip over the goal line and **stick the landing** | `agility` | **solo skill check** — the defense wins only if the scorer *botches* it (fails to stick it) |

- **Head-to-head types** (dunk / race / arm wrestle / beauty): one roll, scorer's attribute vs the best-suited
  defender's attribute + randomness.
- **Solo types** (backflip): the scorer attempts alone; the defense "wins" on a botch — `P(botch)` keys off the
  scorer's attribute only. Keeps the pool varied (not every contest is a matchup).
- **Defender selection:** the single best-suited defender on the field for that type (fastest for a race,
  strongest for an arm wrestle, etc.), from the defending team's roster.

### Balance — offense wins most; defense is a last resort
- The defense winning is meant to be **rare and dramatic**, not a scoring nerf. Target an even-matchup
  defense-win rate of **~10–15%**, scaling with the attribute ratio: a star scorer vs a weak defender should
  almost always bank (~5%); a weak scorer vs a stud defender is the danger zone (~25–30%).
- Shape: `P(defense wins) = clamp(CONTEST_DEFENSE_BASE × (defenderAttr / scorerAttr) ** CONTEST_RATIO_POWER, floor, ceil)`.
  All three are tunable constants. Solo types use `P(botch) = clamp(CONTEST_BOTCH_BASE × (100 / scorerAttr) ** …, …)`.
- **Mental modifiers (optional, phase 2):** the scorer's `pressureHandling` / `selfBelief` nudges their side
  (a clutch star finishes; a choker fumbles the dunk) — same natural-emergence principle as the rest of the sim.

## Outcome on a stuff (defense wins)
- **No points**; the provisional TD is voided.
- Ball spotted at the **play's original line of scrimmage**; **down += 1**; possession retained.
- If the play was already the **last down** (`down >= downsPerSeries`) → **turnover on downs** (defense takes over
  at that spot, per the normal rules-aware down logic).
- **Stats:** rush/receive/scramble **yards count**; **no TD** credited to the scorer, kicker, or team; the play
  is logged as a "contested stop" for the defender.
- **WPA / fantasy:** the play didn't score, so WPA reflects the actual (no-score) result and fantasy TD points
  are not awarded (yards-based fantasy still counts).

## Awakened / Criticality interaction
- An **awakened** scorer **auto-wins** the contest (their L4 power trumps it) — the contest still narrates, but
  the finish is never in doubt. (Keys off the existing `_awakenedReadyFor` / awakened membership.)
- During a **Criticality**, contests go **haywire**: the defense-win rate is boosted and the contest types can
  glitch (odd pairings, reality-bending narration) — folds into the existing per-play chaos layer.

## The rule (toggle + tunables) — `constants.py`
- `CONTESTED_SCORING_ENABLED` (bool, default False) — the master gate. Surfaced as the **"Contested Scoring"**
  dormant rule already teased in the Rulebook popover; flips to live when a Cores vote / Criticality enables it.
- **Making it votable:** it's an ON/OFF mechanic, not a `field = value`, so the vote layer needs the small
  non-scalar-rule generalization noted in the roadmap (a rule that toggles a mechanic). This is the first
  consumer of that generalization.
- Tunables: `CONTEST_DEFENSE_BASE`, `CONTEST_RATIO_POWER`, `CONTEST_BOTCH_BASE`, win-rate floor/ceil, the
  contest-type weight table, and the Criticality boost.

## Blast radius — why it stays contained
- Lives entirely in the **scoring-resolution step** of `floosball_game.py` (where a TD is currently booked) plus
  the **down/possession/LOS-return** handling. Score is final immediately → WP/pick-em/standings/MVP read truth.
- The **decision tree is untouched**: teams still call plays to score; the contest is a *resolution* layer, not a
  play-call input (natural emergence — no meta-gaming the contest). A would-be-TD that gets stuffed just reads as
  a no-score play to WP.
- One thing to verify at build: the down/LOS-return path reuses the existing `downsPerSeries`-aware turnover
  logic so it's already rule-aware.

## PBP narration + frontend
- The contest is its **own play-feed beat**, styled distinctly (a "contest" chip): the provisional TD, the rolled
  action, and the result — e.g. *"TOUCHDOWN — CONTESTED! Backflip… and he sticks it! Six points."* or
  *"CONTESTED! Pyre out-poses him at the goal line. No good — back to the 8, 4th down."* Per-type phrasing pools.
- A stuffed score should read clearly as **no points + drive continues** so users aren't confused by a TD that
  "disappears."

## Build phases
1. **Rule + gate** — `CONTESTED_SCORING_ENABLED` constant + the non-scalar toggle in the vote layer + wire the
   dormant "Contested Scoring" pill to the live state.
2. **Contest engine** — the contest-type pool, attribute mapping, resolution roll + balance constants, defender
   selection. Unit-tested for the win-rate targets across matchups.
3. **Scoring-resolution hook** — intercept TDs before they book; on a stuff, void the points, return to LOS,
   advance the down (turnover-on-downs on the last down), keep yards-as-stats.
4. **Narration** — per-type PBP phrasing pools + the "contested stop" defensive log.
5. **Awakened / Criticality** — auto-win for awakened scorers + the Criticality haywire boost.
6. **Frontend** — the contest beat styling in the play feed + a clear "no points, drive continues" read.
7. **Validation** — a sim with it forced on: confirm win-rate ~offense-heavy, scoring dips modestly, no crashes,
   downs/turnover-on-downs correct, stats (yards yes / TD no) correct.

## Open / revisit
- Should a stuffed score on the last down be a turnover *on downs* (defense at that spot) or a *touchback-style*
  reset? (Rec: turnover on downs — simplest + consistent.)
- Mental modifiers (phase 2) — include from the start or add after the base engine feels right?
- Whether to also contest 2-pt tries later (the "Conversion Ladder" mechanic may absorb that).
