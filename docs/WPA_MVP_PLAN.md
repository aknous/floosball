# WPA-based MVP — Build-Ready Implementation Plan

> Status: **planned, not built** (designed 2026-06-13, `next-season`). Replaces the current MVP
> selection (position-pooled z-score of `seasonPerformanceRating`) with a value metric driven by
> **Win Probability Added (WPA)**, blended with the existing performance rating.
> Grounded in a multi-agent audit of the win-probability model + exact code-anchor extraction.

## 0. Goal & headline decision

Today's MVP = "who was statistically furthest above their positional peers" (`_computeMvpCandidates`,
`playerManager.py:2502-2568`). It has **no notion of value to winning** — an MVP can come from a
last-place team, a kicker can win, and dominance magnitude is flattened by percentiles.

The engine already computes **WPA per play** (how much each play swung win probability) but throws it
away (only a team-level `big_plays` count survives). The plan: **attribute per-play WPA to players,
accumulate a season total, and blend its position-pooled z-score with the existing performance rating
(0.6 perf + 0.4 WPA).**

**Verdict from the WP audit:** the regulation-time WP model is *sound enough to build on* (pre-game WP
matches the ELO logistic; monotonic in lead and clock-drain; continuous quarter boundaries; sane
late-game pull — all empirically confirmed). The blockers are **infrastructure, not WP accuracy**:
WPA is never persisted, only computed when broadcasting is on, and has no per-player attribution layer.
A handful of real WP bugs concentrate in **overtime** and are worth fixing first (Phase 0), but the
scary-looking monotonicity findings (big WP jumps at OT/possession boundaries) **land on player-less
event broadcasts**, so an accumulator that credits only real `Play` objects never lets them reach a
player.

---

## Phase 0 — WP accuracy fixes (do FIRST, so we never accumulate against a bad baseline)

All in `floosball_game.py`. Small, isolated, improve WP regardless of MVP.

### Fix A — OT-tied FG estimate must use the real `fieldGoalTry` constants
The OT-tied-game branch in `calculateWinProbability` (lines **7404-7416**) estimates FG make
probability with constants that diverge sharply from the real model (`fieldGoalTry`, lines 8054-8070):
slope `0.12` vs `0.18`, skill `(0.4 + skill*1.5)` vs `(0.52 + skill*0.85)`, chip `+0.15` vs `+0.10`,
cap `1.0` vs `0.96`. An 80-ovr kicker's 40-yarder reads **1.000 vs the real 0.927**. This corrupts OT
kicker WPA on their highest-leverage kicks. Replace 7404-7416 with the real constants:
```python
                yte = self.yardsToEndzone
                fgDist = yte + 17
                # Estimate FG make probability using the SAME constants as fieldGoalTry()
                baseFgProb = 1 / (1 + math.exp(0.18 * (fgDist - 52)))
                kicker = self.offensiveTeam.rosterDict.get('k')
                if kicker:
                    normalizedSkill = (kicker.gameAttributes.overallRating - 50) / 50
                    fgProb = baseFgProb * (0.52 + normalizedSkill * 0.85)
                    if fgDist < 30:
                        fgProb = min(0.96, fgProb + 0.10)
                    fgProb = max(0.05, min(0.96, fgProb))
                else:
                    fgProb = baseFgProb
```

### Fix B — OT uses the regulation 900s clock for time math
The OT branch (lines 7273-7274) sets `total_seconds = self.gameClockSeconds` but the surrounding
`gameProgress`/`k`/`eloWeight` math is anchored to regulation (3600/900), so at OT kickoff
`gameProgress≈0.833` (not ~1.0) → `eloWeight≈0.21` leaks an ELO prior into OT, and `k` is depressed.
Use the real OT period length (`self.gameRules.overtimeLengthSeconds` = 600, `game_rules.py:54`):
```python
        else:  # Overtime
            total_seconds = self.gameRules.overtimeLengthSeconds  # OT period length (600), not regulation 900
```

### Fix C — `isSuddenDeath` one-liner (match `checkOvertimeEnd`)
Line **7384** uses `isSuddenDeath = self.otSecondPossComplete`, but `checkOvertimeEnd` (7513-7530)
treats `otPeriod >= 2` as sudden death too. Align:
```python
            isSuddenDeath = self.otPeriod >= 2 or self.otSecondPossComplete
```

**Deferred WP nits (ship after MVP, low impact):** EP added to scoreDiff in the same logistic
(`math-1`, intra-drive credit tilt), terminal game-over snap ~95→100 on the last play (`cont-2`),
expected-PAT +0.95 on go-for-two (`pat-1`). None materially move a season total.

After Phase 0: re-run the WP sweep / a fast sim and confirm OT WP looks sane.

---

## Phase 1 — make WPA durable + mode-independent + attributed

### 1a. Move WPA computation out of `broadcastGameState` into an always-run hook
Today WPA is computed inside `broadcastGameState` (`floosball_game.py`) at **6522-6527** and assigned
to the play at **6595-6598** — but two early returns gate it:
- `6509-6510`: `if not BROADCASTING_AVAILABLE or not broadcaster.is_enabled(): return`
- `6514-6515`: TURBO non-final → `return`

So WPA is silently absent in `turbo`, `turbo-silent`, `test-scheduled`, `offseason-test`. (Prod
`scheduled`/`catchup`/`fast-catchup` DO broadcast, so prod isn't silently broken — but the metric must
be mode-independent.) The "previous WP" baseline is also advanced on *every* broadcast incl. non-play
events (`6750-6754`), and seeded once in `playGame()` at `4043-4045`.

**Change:** extract a helper `_resolvePlayWpa()` containing the 6522-6527 math + the
`self.play.homeWpa/awayWpa/isBigPlay/...` assignments + the `previousHomeWinProbability` advance, and
call it from the **always-run play-resolution point** in `playGame()`, right after the play is counted:
```python
4627                self.totalPlays += 1
4628                self.play.playNumber = self.totalPlays
                    self._resolvePlayWpa()          # NEW: compute + store WPA on every play, all modes
```
`broadcastGameState` then *reads* `self.play.homeWpa/awayWpa` instead of computing them. **Critical:**
the prev-WP advance must move with it — non-play event broadcasts must STOP advancing prev-WP (else an
event between plays zeroes the next play's delta). Tying the advance to play resolution is more correct
than today. (Optionally capture a dedicated pre-play WP snapshot so WPA is fully broadcast-cadence
invariant — `wpa-derive-1`, nice-to-have.)

### 1b. Per-play attribution: `attributeWpa(play, homeWpa, awayWpa) -> list[(playerId, signedWpa)]`
Credit only off real `Play` objects with real actors — **never event broadcasts** (this is what
shields the metric from the OT/possession-swing WP jumps). Offense's signed WPA is
`homeWpa if offense is home else awayWpa`; defense gets the negative of that.

`Play` role fields (all `Player` objects or `None`, in `floosball_game.py`; null-check everything):

| Role | field | set @ | notes |
|---|---|---|---|
| runner | `play.runner` | 8372 | run ball-carrier |
| passer | `play.passer` | 9048 | QB |
| receiver | `play.receiver` | 9351 | **`None` on throwaway (9348)** — gate on `isPassCompletion` |
| kicker | `play.kicker` | 8048 (FG) / 8192 (XP) | shared field; disambiguate via `playType` |
| sack defender | `play.sackedBy` | 9174-9206 | `None` on all-out blitz |
| INT defender | `play.interceptedBy` | 9499/9501 | |
| forced-fumble defender | `play.forcedFumbleBy` | 8570/9244/9706 | |
| tackler | `play.tackledBy` | 8566/8568/9691 | |

Play type via `PlayType` enum (`Run/Pass/FieldGoal/Punt/ExtraPoint/Spike/Kneel`) + flags
`isPassCompletion`(9675), `isSack`(9224), `isInterception`(9492), `isFumbleLost`(8557/9243/9715),
`isFgGood`(8124), `isXpGood`(8204), `isTd`. **Vestigial — do not use:** `isXpTry`, `isFumbleRecovered`
(never set True).

**No field exists for:** fumble recoverer, any returner (punt/kick/INT return), punter. The sim has no
return modeling — pick-sixes and return TDs store no scoring player.

**Attribution table:**

| Play | Credit | Rule |
|---|---|---|
| Run | `runner` | 100% offense WPA |
| Completed pass | `passer` + `receiver` | **60/40 QB/receiver split** (no air-yards data to do better) |
| Incomplete / throwaway / QB sack | `passer` | offense WPA (negative) to QB |
| FG / XP | `kicker` | 100% |
| Sack | `sackedBy` gets `+`, `passer` gets `−` | `sackedBy None` (all-out blitz) → defensive unit / drop |
| Interception | `interceptedBy` gets `+`, `passer` gets `−` | |
| Forced/lost fumble | `forcedFumbleBy` gets `+`, ballcarrier gets `−` | recovery is team-level (no field) |
| Return-runback portion | **no player** | no returner field; drop or credit takeaway defender |
| Punt / kickoff / onside | **no player** | possession-swing WP has no owner — do not attribute |
| Penalty / kneel / spike / clock | **no player** | kneels set no player fields → naturally unattributed |

**Negative WPA counts** — charge it to the responsible offensive actor (QB on INT/sack, ballcarrier on
fumble, kicker on missed FG/XP). Do NOT drop negatives: net WPA is what makes this a *value* metric and
the main counter to QB volume bias. Unit-test: per-play offense+defense credits sum to the zero-sum
WPA; event/no-player plays produce no credits.

**Snaps:** count a "snap" for each player credited on a real play (for the per-snap secondary + min gate).

---

## Phase 2 — persist + aggregate

### New columns (mirror the `q4_scoring_plays` migration pattern)
- `GamePlayerStats` (`models.py:623-658`): add after `q4_scoring_plays` (line 644):
  ```python
      season_wpa: Mapped[float] = mapped_column(Float, default=0.0)   # net WPA credited this game
      snaps: Mapped[int] = mapped_column(Integer, default=0)
  ```
  (`Float` already imported.)
- `PlayerSeasonStats` (`models.py:361-411`): add `season_wpa` / `snaps` after `tackles` (line 386).
- **Inline migrations** (`connection.py::_runPendingMigrations`, def @66): mirror the
  `q4_*` ALTERs at `connection.py:195-209` for `game_player_stats` (`ADD COLUMN season_wpa REAL DEFAULT 0`,
  `ADD COLUMN snaps INTEGER DEFAULT 0`); append the season columns to the batched
  `player_season_stats` block at `connection.py:494-497`.

### Accumulation hooks
- **In-memory season total:** accumulate into `player.seasonStatsDict` inside
  `floosball_game._accumulatePostgameStats` (the recordManager hook `recordManager.py:1004` is a no-op
  stub). Per-game WPA comes from summing `attributeWpa` credits over the game's plays.
- **Per-game DB write:** add `seasonWpa`/`snaps` keys to the per-player dict in
  `_extractPlayerStatsFromGame` (`seasonManager.py:3017-3027`, after line 3021, mirroring the
  `q4FP`/`q4Scores` pattern), and to the `DBGamePlayerStats(...)` constructor in `_savePlayerGameStats`
  (`seasonManager.py:3035-3047`, after line 3041).
- **Season rollup DB write:** add the fields to the `PlayerSeasonStats(...)` INSERT branch
  (`playerManager.py:1702-1734`, near `tackles=` @1726) and the UPDATE branch (`1735-1756`, near 1756),
  reading `season_dict.get('seasonWpa'/'snaps')`.
- **Backfill:** `_backfillPlayerSeasonStatsFromGames()` (`connection.py:1374`) can sum the new
  `game_player_stats` columns into `player_season_stats` for existing rows. **WPA cannot be backfilled
  for S1–S8** (per-play WP was never stored) — `season_wpa` is **current-season-forward only**; snaps
  could be reconstructed but WPA can't.

---

## Phase 3 — rewire MVP

All in `_computeMvpCandidates` (`playerManager.py:2502-2568`); downstream consumers need **no edits**
because they read `candidates[0]`/sorted order (`selectMVP` 2570, `getMvpRankings` 2579,
`_selectSeasonMVP` `seasonManager.py:7276`, endpoint `main.py:3470`). Keep the `zScore` key (the MVP
log line at `seasonManager.py:7305` reads it).

1. First pass: alongside `ratings`, collect per-position WPA + global `allWpas`; store
   `positionData[pos] = (eligible, ratingMean, wpaMean)`.
2. After `pooledStd`: `pooledWpaStd = float(np.std(allWpas)) or 1.0` (degrade to perf-only if 0).
3. Second pass: `perfZ = (rating - posMean)/pooledStd`; `wpaZ = (seasonWpa - posWpaMean)/pooledWpaStd`;
   `blendedScore = MVP_PERF_WEIGHT*perfZ + MVP_WPA_WEIGHT*wpaZ`. Add `wpaScore`, `blendedScore`,
   `seasonWpa` to the candidate dict; keep `zScore` = `perfZ`.
4. Re-sort on `blendedScore`.
5. **Eligibility gate:** require a min snaps/games floor (reuse the `seasonPerformanceRating > 0` filter
   + a games-played minimum) so a 3-week hot streak can't top a full season.
6. Constants in `constants.py`: `MVP_PERF_WEIGHT = 0.6`, `MVP_WPA_WEIGHT = 0.4`.
7. WPA **reset** alongside `seasonPerformanceRating = 0` (`seasonManager.py:5243-5244` and `6061`).
8. Surface **WPA-per-snap** as a secondary (exposes good-player-on-a-bad-team); keep **playoff WPA on a
   separate track** (don't fold wk29-32 into the regular-season MVP total — it advantages contenders).

---

## Test / validation plan
- **Unit:** `attributeWpa` — per-play offense+defense credits sum to zero-sum WPA; no-player plays
  yield no credits; negative WPA charged to the right actor; throwaway/None receiver handled.
- **simcheck (fresh fast sim):** season WPA roughly telescopes to game WP swings; defenders + kickers
  register non-trivial totals; no single QB runs away on the blended ranking; MVP looks plausible.
- **Mode independence:** confirm WPA accumulates in a non-broadcasting mode (e.g. `turbo-silent`) after
  the Phase-1 move.
- **WP regression:** after Phase 0, OT WP (tied FG range, sudden death) behaves sanely.

## Open design decisions (owner)
- **Pure net-WPA vs blend** — recommended **blend 0.6/0.4** (anchors in box-score, adds leverage). Pure
  net cumulative WPA is the alternative if you want a "true value" headline; needs the eligibility gate
  + per-snap secondary to stay sane.
- **Defense representation** — named defenders get sack/INT/forced-fumble WPA, but routine
  coverage/run-stuffing/forced-punts land on no-player events, so defenders are **structurally
  under-credited**. Consider crediting forced-three-and-out WP swings to the defensive *unit* and/or a
  separate offensive/defensive value track rather than one raw sum.
- **Pass split ratio** (60/40) and the **blend weights** — tune against a few simulated seasons.

## File / anchor index
- WP model + Phase-0 fixes: `floosball_game.py` — `calculateWinProbability` 7256-7465 (OT FG 7404-7416,
  OT clock 7273-7274, `isSuddenDeath` 7384), real `fieldGoalTry` 8054-8070; OT length `game_rules.py:54`.
- WPA derivation + hook: `floosball_game.py` — compute 6522-6527, assign 6595-6598, early returns
  6509-6515, prev-WP advance 6750-6754 + seed 4043-4045, always-run point 4627-4628.
- Play role fields: `floosball_game.py` `Play` class 7937 (init 7938-8024).
- Persistence: `models.py` GamePlayerStats 623-658 / PlayerSeasonStats 361-411; per-game write
  `seasonManager.py` `_extractPlayerStatsFromGame` 2980-3028 + `_savePlayerGameStats` 3030-3050;
  season rollup `playerManager.py` 1702-1756; in-memory `_accumulatePostgameStats` (floosball_game.py);
  migrations `connection.py` 66 / example 195-209 / batched 494-497; backfill `connection.py:1374`.
- MVP: `playerManager.py` `_computeMvpCandidates` 2502-2568, `calculatePerformanceRatings` set-sites
  2111/2155/2209/2263/2305; `_selectSeasonMVP` `seasonManager.py:7276-7316`; endpoint `main.py:3470-3485`.
