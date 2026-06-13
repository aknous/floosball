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

**Defense is in scope (added 2026-06-13).** The same 6 roster players double as the defense
(QB→S, RB→LB, WR→CB×2, TE→DE; K sits), so "defensive performance" is those players' defensive
contribution. Box stats undervalue coverage (a shutdown CB generates no stats), so the backbone is
**defensive WPA**: WPA is zero-sum, so every play's defense-side swing is the mirror of the offense
side, and the 5 on-field defenders are always known — credit the defense-side WPA across them. A
player's **total MVP value = offensive value + defensive value**, and defensive value also drives a
new **Defensive Player of the Year + All-Defense** award. See **Phase 4**.

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

### Fix B — OT `gameProgress` should be 1.0 (DONE — corrected from the original plan)
The OT bug: `gameProgress = min(1.0, (3600 - total_seconds)/3600)` with `total_seconds = gameClockSeconds`
(OT-remaining, ≤600) leaves `gameProgress ≈ 0.833` at OT kickoff → `eloWeight ≈ 0.21` leaks an ELO prior
into the implicit-else OT path (first team scored, second responding), and `k` is depressed.
**Correction:** the original plan said set `total_seconds = overtimeLengthSeconds` — but that pins
`gameProgress` at a static 0.833 (doesn't fix it) and breaks the OT possession/clock math that correctly
uses `gameClockSeconds`. The right fix is to **clamp `gameProgress = 1.0` in OT** and leave
`total_seconds = gameClockSeconds` for the EP/possession math:
```python
        gameProgress = min(1.0, timeElapsed / totalGameTime)
        if self.currentQuarter >= 5:   # OT is past regulation → ELO floors, k maxes
            gameProgress = 1.0
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

**Change (DONE — corrected location):** the plan originally said call a helper from `playGame()` at
`totalPlays += 1` (4627). But that point is **before** the play executes (4642+: fieldGoalTry/run/pass),
so WPA there would be ~0 (no outcome yet). The actual post-resolution point is `broadcastGameState`
itself, which is already called after each play resolves — the only bug was the early returns skipping
the WPA math. So the refactor lives **inside `broadcastGameState`**: a `_resolvePlayWpa()` helper
(compute WP/WPA + store on play + momentum big-play bonus + clutch/choke WP-impact filter + attribute to
players + advance the WP baseline) is called **above the early returns**, gated to real-play broadcasts
(`includeLastPlay and self.play and eventMessage is None`), and **idempotent per play** (`_wpaResolved`
guard). It now runs in every timing mode. The old compute/store/advance lines were removed; the broadcast
code reads the stored values. The prev-WP advance moved into the helper, so non-play event broadcasts no
longer advance the baseline (fixes the clock-drift leak `wpa-derive-1`/`math-7`). Attribution is
`_attributeWpa(play, homeWpa, awayWpa)` (offense table + defensive unit-share, 1c). Constants
`WPA_PASS_QB_SHARE=0.6`, `DEF_PLAYMAKER_BONUS=2.0` in `constants.py`.

**Validated:** a headless single game (broadcasting off — the no-broadcast path) confirmed attribution
runs with zero errors, scrimmage-down WPA is exactly zero-sum (net = the kickers' special-teams WPA),
and results are intuitive (winners +, losers −, the game's star RB leads). A broadcast-mode fast season
+ playoffs ran clean.

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

### 1c. Defensive WPA (unit-share) — the defense side of the same plays
WPA is zero-sum, so the **defending team's** signed WPA on a scrimmage play is `-offenseSignedWpa`
(when the defense forces a bad outcome, the offense's WPA is negative → the defense's is positive).
The defending team is `homeTeam`/`awayTeam` ≠ `self.offensiveTeam`; its **5 defenders are always known** —
the roster players with a `defensivePosition` (QB→S, RB→LB, WR1/WR2→CB, TE→DE; K excluded). No new
lineup tracking is needed because it's always the same five.

Distribute `defenseSignedWpa` across the 5 defenders, weighted by each player's `defensiveRating`
(set at player init: QB 932 / RB 989 / WR 1034 / TE 1079 in `floosball_player.py`), with a **bonus
multiplier for the tagged play-maker** (`sackedBy`/`interceptedBy`/`forcedFumbleBy`/`tackledBy`):
```python
# only on real scrimmage downs (PlayType.Run / PlayType.Pass) — skip punts/kickoffs/FG attempts,
# whose WP swings are special-teams, not defense
defenders = [p for p in defendingTeam.rosterDict.values()
             if p is not None and getattr(p, 'defensivePosition', None) is not None]
playMaker = play.sackedBy or play.interceptedBy or play.forcedFumbleBy or play.tackledBy
weights = {d: max(1.0, getattr(d, 'defensiveRating', 60)) for d in defenders}
if playMaker in weights:
    weights[playMaker] *= DEF_PLAYMAKER_BONUS   # e.g. 2.0
totalW = sum(weights.values())
for d in defenders:
    d.seasonDefWpa += defenseSignedWpa * (weights[d] / totalW)
    d.defSnaps += 1
```
This gives **every defender a share on every scrimmage snap** (stuffs, incompletions, forced punts —
not just splashy plays), weighted by skill + playmaking. Negative shares on plays the defense got beaten
on are kept (net defensive WPA = value added). Constant `DEF_PLAYMAKER_BONUS` in `constants.py`.

---

## Phase 2 — persist + aggregate

### New columns (mirror the `q4_scoring_plays` migration pattern)
**DONE (Phase 2).** Columns named `wpa` / `def_wpa` / `wpa_snaps` / `def_snaps` (clearer than the
original `season_wpa`; on `GamePlayerStats` they're per-game, on `PlayerSeasonStats` season totals):
- `GamePlayerStats` (after `q4_scoring_plays`): `wpa`/`def_wpa` (Float), `wpa_snaps`/`def_snaps` (Integer).
- `PlayerSeasonStats` (after `tackles`): same four. The defensive box stats (`sacks`/`interceptions`/
  `tackles` denormalized + `defense_stats` JSON: `tfl`/`forcedFumbles`/`passBreakups`) already persist —
  no new columns for the box-stat rating, only for WPA.
- Accumulation: `_attributeWpa` writes per-game `_gameWpa`/`_gameDefWpa`(+snaps); `_accumulatePostgameStats`
  preserves `_lastGameWpa` (for the per-game DB row), rolls into `player.seasonWpa`/`seasonDefWpa`
  (regular season only — playoff WPA stays a separate track), and resets the per-game accumulators
  (mirrors the `_lastGameFantasyPoints` flow). Persisted via `_extractPlayerStatsFromGame` /
  `_savePlayerGameStats` (per-game) and `_savePlayersToDatabase` (season rollup). Restored on
  mid-season resume in `restorePlayerSeasonStatsFromDb`; reset at season start (STEP 9). Inline
  migrations mirror the `q4_*` pattern. **WPA not backfillable for S1–S8** — current-season-forward only.

> **Important for Phase 3/4:** raw `def_wpa` skews **negative leaguewide** (offenses net-positive on
> scrimmage downs, so the mirrored defense side nets negative). Do NOT use raw def WPA in the MVP total —
> z-score it **within the defensive position group** (Phase 4), which re-centers it so a defender above
> the defensive mean scores positive. Validated: persistence clean, values sane (stars lead, kickers
> offense-only/zero def snaps), scrimmage WPA zero-sum (net = special-teams FG/XP).
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
   `offenseScore = MVP_PERF_WEIGHT*perfZ + MVP_WPA_WEIGHT*wpaZ`. Add `wpaScore`, `offenseScore`,
   `seasonWpa` to the candidate dict; keep `zScore` = `perfZ`.
4. **Total value = offense + defense:** `mvpScore = offenseScore + defValue` where `defValue` is the
   defensive blend from **Phase 4** (`defValue = 0.7*defWpaZ + 0.3*defBoxZ`, z-scored within defensive
   position group). Both terms are ~standard-normal z-scores so they sum on a comparable scale; a
   pure-offense QB has `defValue ≈ 0`, a two-way standout gets both. Add `defValue`, `mvpScore` to the
   dict. **Eligibility now spans both phases** — a player qualifies if they cleared the offense filter
   *or* have meaningful defensive snaps.
5. Re-sort on `mvpScore`.
6. **Eligibility gate:** require a min snaps/games floor (reuse the `seasonPerformanceRating > 0` filter
   + a games-played minimum) so a 3-week hot streak can't top a full season.
7. Constants in `constants.py`: `MVP_PERF_WEIGHT = 0.6`, `MVP_WPA_WEIGHT = 0.4` (offense blend);
   `MVP_DEF_WPA_WEIGHT = 0.7`, `MVP_DEF_BOX_WEIGHT = 0.3` (defensive blend); `DEF_PLAYMAKER_BONUS = 2.0`.
8. WPA **reset** (offensive + defensive) alongside `seasonPerformanceRating = 0`
   (`seasonManager.py:5243-5244` and `6061`).
9. Surface **WPA-per-snap** as a secondary (exposes good-player-on-a-bad-team); keep **playoff WPA on a
   separate track** (don't fold wk29-32 into the regular-season MVP total — it advantages contenders).

---

## Phase 4 — defensive value, DPOY & All-Defense

The same 6 players are the defense (QB→S, RB→LB, WR1/WR2→CB, TE→DE; K none — map at
`floosball_player.py:29-35`). Defensive value has two parts, blended.

### 4a. Defensive box-stat rating (`seasonDefensivePerformanceRating`)
Mirror `calculatePerformanceRatings` (`playerManager.py:2068-2326`, currently offense-only) but pool by
**defensive position group** (S / LB / CB / DE) over the tracked per-player defensive stats — the
`defense` dict (`floosball_player.py:111-118`: `sacks`, `ints`, `tackles`, `tfl`, `forcedFumbles`,
`passBreakups`; denormalized `sacks`/`interceptions`/`tackles` + `defense_stats` JSON already persist).
Position-appropriate percentile weights (tunable):
- **DE** (pass rush): sacks + tfl heavy, forced fumbles, tackles.
- **LB** (run D / blitz): tackles + tfl + sacks + forced fumbles.
- **CB** (coverage): pass breakups + INTs (few tackles — box can't see coverage; WPA carries it).
- **S** (coverage / center field): INTs + pass breakups + tackles.

Box stats *systematically miss* shutdown coverage, which is exactly why box-stat is only **30%** of the
blend — the WPA backbone (4b) carries the value that box scores can't see.

### 4b. Defensive value = blend, z-scored within position group
Per defender: `defWpaZ` = pooled-z of `seasonDefWpa` within defensive position group;
`defBoxZ` = pooled-z of `seasonDefensivePerformanceRating` within group. Then
`defValue = MVP_DEF_WPA_WEIGHT*defWpaZ + MVP_DEF_BOX_WEIGHT*defBoxZ` (0.7 / 0.3). This `defValue` is the
term Phase 3 step 4 adds to `mvpScore`, and it's the ranking key for the defensive awards below.
(Pool within group so a CB is compared to CBs, an LB to LBs — same structural defense against
cross-position bias the offense side uses.)

### 4c. Awards: Defensive Player of the Year + All-Defense
Mirror the existing **All-Pro** selection (`seasonManager.py:9923-9977`, which crowns the top
`_computeMvpCandidates` candidate per offensive position and stores `Season.allProPlayerIds` /
`Player.allProSeasons`):
- **DPOY** = highest `defValue` across all defenders (one award), parallel to the MVP at
  `_selectSeasonMVP` (`seasonManager.py:7276-7316`). Store `Player.dpoyAwards` (mirror `mvpAwards`,
  persisted JSON column like `mvp_awards` at `models.py:188`).
- **All-Defense team** = top `defValue` at each defensive group: **S, LB, CB, CB, DE** (5 players,
  two CBs). Store `Player.allDefenseSeasons` (mirror `all_pro_seasons`).
- New helpers `_computeDefensiveCandidates()` (the 4b z-score, pooled by defensive group) and
  `selectDpoy()` / All-Defense selection alongside the existing offensive ones in `playerManager.py`.
- Broadcast + recap: add `dpoy_announcement` / `all_defense_announcement` events (mirror
  `mvp_announcement`/`all_pro_announcement`) and surface in the Season Recap awards section + a defensive
  block in `MvpRankings.tsx`-style UI. Persist via the migrate-skill pattern (`dpoy_awards`,
  `all_defense_seasons` JSON columns, load/save mirroring `mvpAwards`/`allProSeasons`).

### Defensive WPA caveats (design-honest)
- Shared credit means **the same unit's 5 defenders get correlated WPA** — the `defensiveRating`
  weighting + the play-maker bonus are what differentiate them; tune `DEF_PLAYMAKER_BONUS`.
- "Good unit" correlates with "good roster," so defensive WPA partly tracks team strength (true of real
  defenses too). The per-snap secondary helps separate a great defender on a weak unit.
- Only scrimmage downs (Run/Pass) accrue defensive WPA; special-teams swings are excluded (no defense).

---

## Test / validation plan
- **Unit:** `attributeWpa` — per-play offense+defense credits sum to zero-sum WPA; no-player plays
  yield no credits; negative WPA charged to the right actor; throwaway/None receiver handled.
- **simcheck (fresh fast sim):** season WPA roughly telescopes to game WP swings; defenders + kickers
  register non-trivial totals; no single QB runs away on the blended ranking; MVP looks plausible.
- **Mode independence:** confirm WPA accumulates in a non-broadcasting mode (e.g. `turbo-silent`) after
  the Phase-1 move.
- **WP regression:** after Phase 0, OT WP (tied FG range, sudden death) behaves sanely.
- **Defensive WPA:** per play, the 5 defenders' shares sum to `defenseSignedWpa`; over a season a strong
  defensive unit's players show clearly positive net defWPA, a sieve shows negative. DPOY + All-Defense
  picks look plausible (the All-Defense S/LB/CB/CB/DE are genuinely good defenders, not just tackle
  volume). A dominant two-way player can crack the MVP top-5.

## Open design decisions (owner)
- **Pure net-WPA vs blend** — recommended **blend 0.6/0.4** (anchors in box-score, adds leverage). Pure
  net cumulative WPA is the alternative if you want a "true value" headline; needs the eligibility gate
  + per-snap secondary to stay sane.
- **Defensive credit sharing** (RESOLVED 2026-06-13): defensive WPA = the defense-side swing of every
  scrimmage play, **shared across the 5 on-field defenders weighted by `defensiveRating` + a play-maker
  bonus** (Phase 1c). Surfaced **both** ways — folded into MVP total value (offense+defense) AND a
  dedicated **DPOY + All-Defense** (Phase 4). Defensive value itself = **0.7 defensive-WPA + 0.3
  box-stat** blend.
- **Tunables to validate against simulated seasons:** pass split (60/40), offense blend (0.6/0.4),
  defense blend (0.7/0.3), `DEF_PLAYMAKER_BONUS` (2.0), and whether to weight the defensive share by
  `defensiveRating` vs even-split.
- **Defensive WPA tracks team strength** somewhat (good unit ⇒ all 5 share) — the per-snap secondary and
  the box-stat term are the differentiators; accept it as a feature (real defenses work the same).

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
- Defense: position map `floosball_player.py:29-35`; `defensiveRating` set QB 932 / RB 989 / WR 1034 /
  TE 1079; defense box dict `floosball_player.py:111-118`; mirror `calculatePerformanceRatings` for the
  defensive rating; All-Pro selection to mirror for All-Defense `seasonManager.py:9923-9977`
  (`Season.allProPlayerIds` / `Player.allProSeasons`, `mvp_awards` JSON col `models.py:188`).
