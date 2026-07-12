# Game Formats & Win Conditions — Design Plan

> The deferred, deepest tier of the rule-mutation direction: rules that change **who
> wins / when the game ends / how the game is played**, not just how the score reads.
> Owner-designed 2026-07-11. Part of the rule-mutation direction (see
> `docs/SCORING_MODEL_PLAN.md`, memory `rule-changes-feature`). This is the flagship
> next chunk after the three shipped mechanics (Scoring Model, Conversion Ladder,
> Drive Clock).

## Scope
Six formats total; the owner's build set (this doc) is **five**:
- **target** — first to X points (win-condition hook). ← first build
- **bust** — darts: land exactly on X, overshoot is voided (win-condition hook).
- **play limit** — no clock, fixed plays per quarter (game-format rewrite).
- **chess clock** — per-team offense-time budget (game-format rewrite).
- **innings** — baseball-style, out-driven not clock-driven (game-format rewrite).

(`frames` — most-frames-wins, golf match play — was originally out of scope here but
was **built 2026-07-12** at the owner's request; see §6 below.)

## Foundational decisions (owner, 2026-07-11)
1. **Trigger = the normal Cores vote.** A `gameFormat` is a **preset candidate** in
   the existing rule-change vote (same Aris-change / Pyre-revert, escalation, drift).
   Reuses the compound-preset vote generalization built with Drive Clock.
2. **One format at a time, coexisting with scalar rules.** `gameFormat` is a single
   field, so formats are inherently mutually exclusive; but a format runs *alongside*
   any active scalar changes (e.g. `target` with a 7-pt TD and the Drive Clock all at
   once). No format-on-format stacking.
3. **Format swap is DIRECT.** A CHANGE vote can go straight from one format to another
   (target → innings) without first reverting to standard. A REVERT returns to
   `standard`.
4. **Fully-accurate AI + win-probability, up front.** Each format ships only after its
   win-probability and the AI decision tree are **re-derived precisely for that
   format** — not a rough heuristic. This is a real per-format modelling task, called
   out in each section below.

---

## Vote cadence rework (owner, 2026-07-11) — lands WITH the game-format build

The current vote system rolls an **escalating probability** each game day
(`RULE_VOTE_RAMP`), so a day may or may not fire, and the kind (change vs revert) is a
coin flip past the revert gate. Replace that with a **fixed, deterministic weekly
schedule** — a vote fires **every** game day (weeks 1 / 8 / 15 / 22 = day indices
0–3):

| Day idx | Week | Core | Kind | Candidate pool |
|---|---|---|---|---|
| 0 | 1 | Aris | change | **game format only** |
| 1 | 8 | Aris | change | scalars + score display + mechanics (everything EXCEPT game format) |
| 2 | 15 | Aris | change | same as day 1 |
| 3 | 22 | Pyre | revert (**multi-select**) | any active (non-default) rule — the fan safety valve before the last day + playoffs |

Design notes:
- **No probability, no misses** — `maybeOpenWindow` always opens a window on a game
  day. `RULE_VOTE_RAMP` / the escalation math and `RULE_VOTE_REVERT_GATE` (the 50/50
  change-vs-revert) are **removed**; the day index fully determines change-vs-revert
  and the candidate pool.
- **Day 0 = game format only.** The change options are the `gameFormat` presets (and,
  per swap-directly, a format→different-format swap when one is already active). This
  is why the cadence lands with the game-format build — until the `gameFormat`
  candidate exists, day 0 has nothing to offer (fall back to a normal change, or just
  no-fire, until then).
- **Days 1–2 = everything else.** All CHANGE candidates except `gameFormat`: the
  scalars (downs / distances / TD-FG-safety points / clock stops), the score-display
  enum, and the on/off mechanics (Conversion Ladder, Drive Clock).
- **Day 3 = Pyre revert — MULTI-SELECT (approval vote).** Unlike the single-pick change
  votes, the revert is a **spring-cleaning**: each fan selects **any subset** of the
  currently-active (non-default) rules they want undone, and **every rule that lands on
  ≥50% of ballots gets reverted** — so one vote can roll back several rules at once
  before the last day + playoffs. Reuses the **Hall-of-Fame approval-vote pattern**
  (multi-row vote per user, tally per option, act on all clearing
  `AWARD_HOF_APPROVAL_FRACTION = 0.5` of the distinct voters). Below quorum → the
  existing revert fallback (no forced reverts). Implementation: `RuleVote` becomes
  multi-row per (user, window) for a revert window (like `AwardVote` HoF approvals);
  `resolveWindow` applies **all** winners, not just one; the revert modal is checkboxes,
  not radios. The Aris CHANGE votes (days 0–2) stay **single-pick** (a change adds ONE
  rule change).
- Aris on days 0–2, Pyre on day 3 — already how the change/revert Cores split works.
- Idempotency (`hasWindow` once per game day) stays. The same-day resolution timing
  (15 min before the day's first game) stays.

> This is a base vote-system change (`ruleVoteManager.maybeOpenWindow` + constants), not
> game-format-specific, but it's grouped here because day 0 depends on the game-format
> candidate. Sequence it as step 0.5 (right after the shared abstraction gives us the
> `gameFormat` candidate).

---

## The shared `GameFormat` abstraction (build this first)

Today the game loop is hardwired: `while not isGameOver()` keyed on
`gameClockSeconds <= 0`, and the winner is the higher cumulative score. The formats
need a seam. Introduce a small format layer the loop, WP, and the play-caller consult.

### GameRules fields
- `gameFormat: str = 'standard'` — `'standard' | 'target' | 'bust' | 'play_limit' |
  'chess_clock' | 'innings'`. Mutable + exposed; the vote preset sets it.
- Per-format config (all mutable scalars, set by the preset patch):
  - `targetScore: int = 30` — target/bust finish line.
  - `playsPerQuarter: int = 30` — play_limit budget per quarter (starting guess).
  - `offenseClockBudgetSeconds: int = 1200` — chess_clock per-team offense budget.
  - `inningsPerGame: int = 6`, `outsPerInning: int = 3` — innings structure.
- The `standard` default leaves every one of these inert.

### Engine hooks (a `GameFormat` helper keyed on `gameRules.gameFormat`)
A format optionally overrides:
- **`isGameOver(game) -> bool`** — the end condition. `standard`/`target`/`bust`/
  `play_limit`/`chess_clock` still layer on the existing clock/quarter flow;
  `innings` replaces it entirely (out/inning loop).
- **`winner(game)`** — usually the cumulative-highest score (target/play_limit/
  chess_clock/innings all keep cumulative scoring). Kept as a hook for future formats.
- **`onScoreApplied(game, team, points) -> applied: bool`** — a post-score hook.
  Only `bust` uses it (an overshoot voids the points → turnover). Everyone else is a
  no-op that returns True.
- **`gameProgress(game) -> float`** (0..1) — the "how far into the game are we" signal
  WP already uses for time-sensitivity. Time-based for standard/target/chess_clock;
  **play-based** for play_limit; **inning-based** for innings; for target/bust also
  blended with **score-progress toward X** (see below).

### Vote plumbing
- `RULE_VOTE_CANDIDATES['gameFormat']` = a preset candidate (`presets`, `gate`) like
  Drive Clock. Each preset is a full `{gameFormat, ...config}` patch.
- **Swap-directly**: `_changeOptions` for this candidate offers every format whose key
  ≠ the current `gameFormat` (including from a non-standard format → another format),
  not only when standard. `_revertOptions` offers `→ standard`.
- Surfaced in the Rulebook as its own **"Game Format"** row (the active format + its
  key config, e.g. "First to 30"). During Criticality it can be randomized like the
  rest.

### What does NOT change
Scalar rules, the Scoring Model display lenses, the Conversion Ladder, the Drive
Clock, and (in every format except bust) the way points are earned. A format is a
win-condition / loop concern layered over the same football.

---

## 1. `target` — first to X (FIRST BUILD)

**Rule:** the game ends the instant a team's cumulative score reaches **X**
(`targetScore`). **The clock still runs** — if time expires before anyone reaches X,
the normal result stands (highest score; normal OT on a tie). No endless games.

**Config:** `targetScore` default **30** (owner: "reachable, ~28-32"), votable range
~**24–42** (leans reachable; the Cores can push it up). Float-safe (a 6.4-pt TD can
cross X). "Reach X" = `score >= X` (crossing via a big play still wins; you don't have
to land exactly — that's `bust`).

**Win condition / game-over:** add a check to `isGameOver`: if either team's score
`>= targetScore`, the game is over and that team wins immediately (resolved at the
moment the score is applied, so a walk-off TD ends it mid-drive like an OT score).

**Win probability (re-derived, not approximated):**
- The end of the game is now the *earlier* of "clock expires" and "someone reaches X".
  So `gameProgress` = `max(timeProgress, scoreProgress)` where
  `scoreProgress = leaderScore / targetScore`. The time-sensitivity `k` ramps on
  whichever is further along — a 27-3 game at halftime is nearly over even with a half
  left, because the leader is one score from X.
- Possession pull: a team **on offense that can reach X this possession**
  (`targetScore - theirScore <= _maxPossession()`) gets the same strong WP pull the
  current model applies to a late-game go-ahead possession — they're a score from
  winning outright.
- Otherwise the existing ELO-prior + logistic-score blend stands; only the "how close
  to over" and "one score from winning" terms change.

**Decision tree (re-derived):**
- **Offense near X** (within `_maxPossession` of the finish): maximally aggressive —
  go for the score that ends it, kick the FG that reaches X if it does, go for 2/ the
  conversion-ladder rung that lands on/over X. Reuses the scoring-aware helpers
  (`_oneScore`/`_maxPossession`/the live TD/FG values).
- **Defense when the opponent is near X**: play to prevent the game-ending score
  (situational, like defending a late lead) — but the OFFENSE side of that (the
  trailing team racing before the opponent closes it out) is the main new behavior.
- **Clock management flips**: a leader near X wants to *score* (end it), not drain the
  clock — so the "protect a lead by draining" logic is suppressed when a score ends the
  game. A trailing team races both the clock AND the opponent's march to X.

**Ties:** only possible if the clock expires with no one at X → normal tie/OT. A team
reaching X is an outright win (no tie).

**Frontend:** the Rulebook "Game Format" row shows "First to 30"; the scoreboard shows
a small "to X" marker or a progress pip toward the target (nice-to-have); the game-end
reads as a "reached the target" walk-off.

---

## 2. `bust` — darts (land exactly on X)

> **Needs Sideline Goals (fine-grained scoring) to be playable** — you need 1-pt hoops
> + the Conversion Ladder to control your total precisely enough to land on X.
> Build it LAST of the five.
>
> **Dependency resolution (decided 2026-07-11): BUNDLE.** The darts format is a
> compound-preset vote whose patch enables its own prerequisite atomically —
> `{gameFormat:'bust', targetScore:X, sidelineGoalsEnabled:True}`. The vote-option
> model is already a multi-field patch, so this is a one-line `GAME_FORMAT_PRESETS`
> entry; darts is offerable from **day 0** and always playable the moment it wins,
> with no cross-week vote-chain ordering fragility. The day-3 **multi-select** revert
> can still peel `gameFormat` and `sidelineGoalsEnabled` back independently (Sideline
> Goals left on under standard scoring is harmless — just an extra scoring option).
> (Rejected alternatives: gate darts behind Sideline Goals already being live — too
> much friction, may never fire in a short season; engine-implied fine-grained scoring
> — kills Sideline Goals as a standalone mechanic.) Prereq: build Sideline Goals as a
> standalone mechanic candidate (`sidelineGoalsEnabled` in game_rules) BEFORE darts.

**Rule:** first to land **exactly** on X wins. A score that would put you **over** X is
**voided — a turnover** (points not awarded, ball to the defense), reusing the
Contested-Scoring "stuffed score" path. So you can never exceed X; a greedy TD that
overshoots wastes the drive. X kept **low** (owner earlier: ~15–25) so precise scoring
doesn't drag it out. Clock still bounds it; if it expires, the highest score **at or
under X** (closest to X, since none can exceed) wins.

**onScoreApplied hook:** on every score, if `score + points > X` → void (turnover), no
points. If `== X` → win. If `< X` → apply normally.

**WP (re-derived) — the hard one:** inverts near X. Being AT X = won; being able to
land exactly on X = high WP; being at `X-1` with only ≥2-pt scores available = stuck
(can't land, must hope the opponent busts) = *low* despite a high score. WP must model
**reachability of exactly X** given the available scoring increments (which is why it
needs the fine-grained mechanics). Most decision-heavy format.

**Decision tree (re-derived):** score *carefully* near X — pick the increment (1-pt
hoop, low ladder rung) that lands on X; avoid any play that would overshoot (a TD that
busts you is worse than a punt). Inverts the "always maximize points" instinct.

---

## 3. `play_limit` — no clock, fixed plays per quarter (revive the play-count model)

**Rule:** no game clock at all. Each quarter is a fixed number of **plays**
(`playsPerQuarter`); offenses manage the play count (hurry-up near a quarter's end,
know when the last play is). Revives floosball's deprecated play-count model
(`GAME_MAX_PLAYS` / `PLAYS_TO_*_QUARTER` — see CLAUDE.md "Open Questions"). Cumulative
score, highest wins.

**isGameOver / advanceQuarter:** key off a **play counter** instead of
`gameClockSeconds`. A quarter ends at `playsThisQuarter >= playsPerQuarter`; the game
ends after the last quarter. OT = an extra fixed-play period on a tie.

**WP (re-derived):** the current model's `gameProgress` is `timeElapsed/totalGameTime`
— replace with `playsRun / totalPlays`. Everything else (ELO prior, score logistic)
carries over. The "possession pull" keys off plays remaining, not seconds.

**Decision tree (re-derived):** all the clock-management logic (2-min drill, kneel,
spike, FG-drain, the Drive-Clock hurry-up) is **time-based** and must be re-expressed
in **plays remaining** — "last play of the quarter" replaces "≤2:00", a leader
"drains" by using safe plays not by running clock. This is the biggest decision-tree
rewrite of the timed formats. (Note the Drive Clock's `plays` unit already reasons in
plays — reuse that plumbing.)

---

## 4. `chess_clock` — per-team offense-time budget

**Rule:** each team gets a total **offense-time budget** (`offenseClockBudgetSeconds`,
e.g. 20:00). Their budget runs only while they possess the ball; when it hits 0 they
**can no longer be on offense** — the other team keeps the ball to the end. Turnovers
just restart the offense at their own 20. Cumulative score, highest wins.

**Engine:** per-team offense clocks; possession assignment respects "can this team
still take the ball?" A team whose budget is spent never gets it back.

**WP (re-derived):** expected remaining scoring chances per team ∝ their remaining
offense budget. A team ahead with more offense-clock banked is in great shape; a team
behind that has burned its budget is nearly done regardless of the game clock. Model
expected remaining possessions from the two budgets.

**Decision tree (re-derived):** manage your OWN offense budget — a leader can *drain
their offense clock deliberately* (long, ball-control drives) to deny the opponent
touches (opposite of hurry-up); a trailer conserves budget for more possessions. A new
strategic axis.

---

## 5. `innings` — baseball-style, out-driven

**Rule:** no game clock. Each team **bats until 3 outs**, then teams switch; play
**N innings** (`inningsPerGame`), most total points wins. An **out = any possession
that ends** — a score, a punt, OR a turnover (scores MUST count as outs, or a dominant
team bats forever). So a half-inning is up to `outsPerInning` (3) possessions; the team
banks whatever it scores across those, then hands over.

**isGameOver / the loop:** the deepest rewrite — **replace the clock/quarter loop with
an inning/out loop**. Track outs within a half-inning, half-innings within an inning,
innings within the game. OT = extra innings on a tie.

**WP (re-derived) — baseball-flavored:** reason in outs and innings remaining, not
time. A lead is safer with fewer outs/innings left for the opponent to bat. Expected
remaining possessions = (innings left × outs) per team.

**Decision tree (re-derived):** every possession is precious (only 3 per half-inning),
so "punt to flip field position" is *much* worse (a punt is an out — you burn a bat for
nothing). Teams go for it far more; the risk/reward of every 4th down shifts hard.

---

## Build order
0. **Shared `GameFormat` abstraction** — GameRules fields, the format-keyed hook layer,
   the vote preset candidate (swap-directly), the Rulebook "Game Format" row.
1. **`target`** — DONE. The proving slice: game-over hook + re-derived WP + decision
   tree + frontend.
2. **`play_limit`** — DONE. No game clock: each quarter is a fixed `playsPerQuarter`
   plays via a SYNTHETIC clock (the format drives `gameClockSeconds` from a per-period
   scrimmage-play counter in `onPlayTick`; `consumeGameTime` is neutralized). The
   entire time-based decision tree + WP are reused UNCHANGED because plays-remaining is
   proportional to seconds-remaining — no decision-tree rewrite was needed after all.
3. **`chess_clock`** — DONE. Per-team offense-time budget (18:00 each) on a synthetic
   clock scaled to the total (like play_limit, so WP/quarters stay accurate). Owner
   rules: a depleted team plays perpetual defense (possession gate keeps the ball with
   the giver at its own 20 when the receiver is locked out); the team that depletes
   first while LOSING ends the game immediately (can't catch up); when a team is locked
   out the opponent never punts (a failed 4th just returns the ball at its own 20).
   Budgets floor at 0 and only in-budget time advances the synthetic clock (no overshoot
   / stranded budget). chess_clock doesn't latch Final mid-play (a defensive score can
   flip a decided game within a play). Ties → OT.
4. **`innings`** — DONE. Baseball-style, try-driven, no clock. Each team bats until
   `triesPerInning` (3) TRIES then teams switch; `inningsPerGame` (3) innings, most points
   wins; OT = extra innings on a tie. A TRY = any possession that ENDS, so the batting
   team keeps the ball at its own 20 (banking points) until 3 tries. NOT a loop rewrite:
   the clock/quarter loop is left INERT (consumeTime no-op) and the try/inning counters
   drive the game via `possessionReceiver` (try-count + half-inning flip) + `checkEarlyEnd`.
   AWAY bats first (top); HOME bats last (bottom) via the `openingOffense` hook and can
   WALK IT OFF (checkEarlyEnd ends the moment HOME leads in the bottom of the final/extra
   inning — winning team needn't bat). suppressPunt=True (never punt), every at-bat starts
   at own 20 (`newDriveYardsToEndzone`), WP progress = innings played.
5. **`bust`** — after Sideline Goals ships (needs fine-grained scoring); inverts WP +
   decisions near X. LAST remaining format. See §2 (BUNDLE decision).
6. **`frames`** — DONE (owner-requested 2026-07-12; originally out of scope). Golf/snooker
   MATCH PLAY: the game splits into `framesPerGame` (6) equal TIME frames; whoever outscores
   the other within a frame wins it (+1), a tied frame is HALVED (½). Most frames won wins
   the match — TOTAL POINTS ARE IRRELEVANT to the result (a team can win the match with
   fewer points). Frames tied at the end → total-points tiebreak → still tied → OT. It's the
   ONLY format that decouples the winner from total points, so it added the winner seam:
   base hooks `winnerSide` / `resultDisplay` / `eloScores` (default = most points, so the
   other formats are byte-identical). The clock/quarter/OT loop runs NORMALLY — frames are a
   time-based OVERLAY (`consumeTime` drains the clock then awards frames at time boundaries;
   the engine winner block + both `updateEloAfterGame` calls route through the hooks; ELO
   margin uses frames-won). WP is frames-lead based (points-WP is meaningless here). New
   `framesPerGame` field + "Frames (6, match play)" preset; frontend shows "Frames 3-2 ·
   Frame 4/6". Validated live: winner is frames-won incl. teams winning with fewer points,
   points-tiebreak + OT resolve frame ties, standard regression unchanged.

### Architecture (BUILT 2026-07-11): `game_formats.py` strategy layer
One `Game` engine; format-specific logic lives in per-format policy objects
(`GameFormat` base = standard/pass-through, `TargetFormat`, `PlayLimitFormat`) that
the engine delegates to via `Game.format` (resolved from `gameRules.gameFormat`,
cached). Seams: `checkEarlyEnd` / `adjustGameProgress` / `adjustWinProbability` /
`consumesRealTime` / `onPeriodStart` / `onPlayTick` / `matchPoint` / `shouldPush` /
`stateExtra`. Every base method is the standard behavior, so standard stays
byte-identical (validated live). New formats subclass `GameFormat` + register in
`_FORMATS` — no new `if gameFormat ==` branches in the 9,400-line engine. Chess_clock
/ innings / bust each add their seam overrides here.

Each remaining format is its own spec + build once we reach it; every format ships
with its WP + decision-tree re-derivation (owner: fully accurate up front).

## Open / revisit
- `targetScore` exact default + votable range (30 / ~24–42 to start; tune in sim).
- `playsPerQuarter` default (30 guess — tune so a play-limit game ≈ a normal game's
  play count).
- `offenseClockBudgetSeconds` default (20:00 guess).
- `inningsPerGame` / `outsPerInning` defaults (6 × 3 guess).
- Does the Drive Clock combine sensibly with each format? (It should — one format +
  scalar rules — but chess_clock + drive_clock is two clocks; innings has no game clock
  so the drive clock's `seconds` unit is moot there — prefer/force `plays` unit under
  innings.) Flag per format at build.
- Frontend: each format needs a scoreboard treatment (target marker, play counter,
  two offense clocks, inning/out indicator). Phased like the mechanics.
