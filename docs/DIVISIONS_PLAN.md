# 32 Teams + 4 Divisions

**Branch:** `next-season` (season-cutover change — roster/schedule shape cannot change mid-season)
**Status:** PLANNED, not started
**Goal:** kill the playoff-bye chalk, and give the regular season divisional rivalries.

## Why

Measured this session across 64 auto-GM seasons: **seeds 1-2 (the bye teams) win 89% of Floos Bowls; seeds 3-6 win 11%.** The bye is structurally forced — 6 playoff teams per league can't make a clean bracket — so the top two teams skip the round most likely to upset them. 24 teams cannot fix this. 32 can.

Standings churn is already healthy under the autonomous FO (median top-6 run = 1 season, 21 of 24 teams reach contention). The bracket is what converts that churn back into concentration.

## Shape

**32 teams = 2 leagues × 2 divisions × 8 teams.**

### Regular season — still exactly 28 weeks

The current scheduler (`_generateIntraleagueGames`) is generic: `2×(n−1)` intraleague + `n/2` interleague. At n=16 that's **38 weeks**, which does not fit the 4-game-day × 7-hourly-slot calendar (28). The divisional split is what lands it back on 28:

| Bucket | Games |
|---|---|
| Division rivals (7 opponents × 2) | 14 |
| Other division in own league (8 × 1) | 8 |
| Interleague (6 × 1) | 6 |
| **Total** | **28** |

Same 4 game days, same 12:00-18:00 ET slots, same playoff weeks. **Nothing downstream of the calendar changes.**

Half a team's season is against 7 rivals it plays twice. That is where the rivalry comes from — no new systems needed.

### Ordering — the season ENDS on division games

Required (owner): the run-in must be divisional, so the division race decides the season's last games.

The buckets land on the game-day boundaries exactly:

| Weeks | Game day | Content |
|---|---|---|
| 1-7 | Day 1 (Mon) | Division round-robin, first pass (7) |
| 8-14 | Day 2 (Tue) | Cross-division, own league (8) — spills 1 week |
| 15-21 | Day 3 (Wed) | remainder of cross-division + interleague (6) |
| **22-28** | **Day 4 (Thu)** | **Division round-robin, second pass (7)** |

7 + 8 + 6 + 7 = 28. **The entire final game day is divisional** — every team spends the last seven slots playing the seven clubs it is racing for the division title. That is the drama, and it costs nothing structurally because the second round-robin is already a discrete 7-week block (`_generateIntraleagueGames` builds it as the reversed copy of the first).

Note `GM_ACTIVE_WEEK = 22` lands on exactly this boundary: the Front Office opens the same week the divisional run-in starts.

**Terminology check:** "interdivision" was the word used, but the drama comes from games against your *own* division (they decide the title), so this plan schedules the intra-division second round-robin last. If cross-division games were meant instead, swap the day-2 and day-4 blocks.

### Playoffs — 8 per league, no byes

| Round | Week | Games |
|---|---|---|
| Playoffs Round 1 | 29 | 8 (1v8, 2v7, 3v6, 4v5 per league) |
| Playoffs Round 2 | 30 | 4 |
| League Championship | 31 | 2 |
| Floos Bowl | 32 | 1 |

Four rounds, identical to today's calendar. **Seeding: each league's 2 division winners take seeds 1 and 2** (by record between them); seeds 3-8 are the next 6 best records league-wide, any division. Re-seeding each round stays as-is.

Winning a division is therefore worth a top-2 seed but **not** a bye — the prize is a favourable matchup, not a free round.

## Realignment — RETIRED (owner decision)

`leagueManager.realignByRecentPerformance` serpentine-split the two leagues by 2-season win% so neither stayed perpetually stronger. It is **not carried forward**: prod restarts fresh at 32 teams, so there is no accumulated imbalance to correct, and a competitive reshuffle would move teams between leagues and dissolve divisions annually — a rivalry needs the same 7 opponents every year.

Supporting evidence: the win spread survives a 55% change in effective talent spread (this session's compression sweep), so league-level balance was never where parity was decided. Realignment was treating a symptom that isn't the disease.

**Divisions are geographic and fixed**, persisted like `league_alignment` so they survive restarts. Work to do: remove/disable `realignByRecentPerformance` and `seasonManager._maybeRealignLeagues`, and retire the `league_realigned` app_setting gate.

## Build order

1. **Config + data model.** 8 new teams in `config.json`. `division` column on `teams` (inline migration in `connection.py`, per the four-step pattern) + a `Division` concept in `leagueManager`. Note: **there is no division support in the code today** — `grep division` returns nothing in `leagueManager.py` or `models.py`, despite CLAUDE.md claiming otherwise. That claim needs fixing regardless.
2. **Division assignment.** Geographic, fixed, persisted like `league_alignment` so it survives restarts.
3. **Scheduler.** New `_generateDivisionalSchedule` producing the 14/8/6 split into 28 weeks. Keep the existing round-robin helper for the within-division double.
4. **Playoffs.** Qualification + seeding: division winners to 1-2, then best records. Round 1 becomes 8 games; drop the bye path (`_applyByeFatigueRecovery`, `playoffsByeTeams`).
5. **Standings/API/frontend.** Division standings, "clinched division" moment.
6. **Expansion stocking.** 48 generated players at the normal distribution (owner decision: fresh rosters, no expansion draft). Expect new teams to start below average.

## Scaling side effects

- **Names.** 192 rostered vs 144; ~25 new players/season. Prod has 352 names left (~14 seasons), the config seed is 789 (~30). Now the coach-candidate leak is fixed this holds, but top up the seed list at the cutover.
- **Position supply.** `ensurePositionSupply` demand goes 51 → 67 at WR (`32×2 + ROSTER_SUPPLY_BUFFER_PER_POSITION`). The floor must actually deliver it — this is the code path that failed silently when names ran out.
- **Anomaly threshold.** `THRESHOLD_FLOOR=120` and the plateau estimate are calibrated against a 144-player attention pool. 192 changes the aggregate scaling; re-tune.
- **Cards.** 32 themed team packs instead of 24; template counts scale with the player pool.
- **Avatars.** 8 new team avatars (`avatar_generator.py` handles generation; disk cache).

## What this does NOT fix

Expansion addresses **title concentration via the bracket**. It does nothing about the amplifier: roster rating predicts wins at **1.92 wins per rating point**, and that slope is unchanged by compression. It may also worsen the tail short-term — the league already produces ~2.08 teams with ≤4 wins per season, and 8 fresh rosters start below average.

Track separately:
- The amplifier (what converts a 6-point effective talent gap into a 23-win spread — the confidence/pressure/momentum layer is the prime suspect).
- `POSITION_VALUE` recalibration (QB paid 1.00 but predicts wins worse than RB at 0.72).
- The QB profile-vs-in-game rating bug (see CLAUDE.md Open Questions).

---

# Addendum: Team Form Oscillation (specced, NOT built)

**Goal (owner, 2026-08-04):** drama, not parity. Teams should run hot and cold across a
season so storylines develop — a slow start that becomes a playoff push, a fast start
that fades. Explicitly NOT "hot teams get hotter": a hot team is at its apex and should
come down. The missing half is the CLIMB, and the recovery from a slump.

## Measured baseline (3 seasons, 96 team-seasons, 32-club league)

| Metric | Value |
|---|---|
| corr(day-1 wins, final wins) | +0.604 (r2 0.36) |
| Day-1 leader finishes #1 overall | 1 of 3 |
| Form variance: sd of wins across the 4 game days | **1.13** |
| Same metric for a pure coin-flip league | **1.32** |
| Teams flatter than sd 1.0 | 42% |

**Team form varies LESS than chance.** There is no oscillating layer — each team plays
at a fixed level all season, so four game days read as four samples of one number.
The season is not "decided on day 1" (day 1 explains only 36%); the problem is that
nothing ever moves.

## Why the existing system doesn't produce it

`FORM_STATE_RATING_MULT` is deliberately one-sided — every positive state sits at 1.00
(apex-and-decline by design, to avoid a runaway) and only the negatives bite. That is
correct for its purpose but it can only push a team DOWN from its level. Nothing lifts a
struggling team beyond RESOLUTE 1.04, so slumps end by reverting to flat, never by
overshooting into a run.

## Design

A continuous, mean-reverting per-team `formOffset` applied in the pre-game chain
(alongside `_applyLeagueCompression` / `_applyFundingMorale`), replacing nothing —
`FORM_STATE_RATING_MULT` stays as the discrete badge/flavour layer.

    formOffset  in roughly [-0.06, +0.06]  (a multiplier on gameAttributes, so +-4-5 rating pts)

    each game week:
        recent   = win rate over the last FORM_WINDOW games, minus the team's own
                   season-to-date baseline        # riding high (+) or struggling (-)
        pull     = -recent * FORM_PULL            # NEGATIVE feedback: above your level
                                                  # pulls you down, below pulls you up
        # trait modulation, team means over the 6 rostered players:
        if recent > 0:  pull *= (0.5 + collective complacencyVulnerability)   # apex decay
        if recent < 0:  pull *= (0.5 + collective adversityResolve)           # the climb
        formOffset += (pull - formOffset) * FORM_REVERSION + gauss(0, FORM_NOISE)
        clamp to +-FORM_MAX

Key property: the feedback is NEGATIVE, so it oscillates around each team's true level
rather than running away. A vulnerable team crashes harder off a peak; a resolute team
climbs out of a hole faster. Both directions are trait-earned, and neither compounds.

## Integration points

1. `constants.py` — FORM_WINDOW, FORM_PULL, FORM_REVERSION, FORM_NOISE, FORM_MAX,
   FORM_OSCILLATION_ENABLED.
2. `floosball_team.py` — `formOffset` field + `collectiveResolve()` /
   `collectiveVulnerability()` (means of the existing per-player methods over rosterDict).
3. `seasonManager` week rollover — update `formOffset` for every team once per week.
4. `floosball_game.playGame` — apply as a multiplier in the pre-game chain.
5. Persist `teams.form_offset` (inline migration) so it survives restarts mid-season.

## How to validate

Re-run the day-level harness and compare against the baseline above. Targets:

* form variance **1.13 -> 1.6-1.9** (above the 1.32 chance line = real oscillation)
* day-1 correlation drifts DOWN from 0.604
* win spread and title concentration should NOT move much — this is a variance change,
  not a parity change. If the spread collapses, the amplitude is too high.

Do NOT tune this against win spread. That was the wrong objective; see the session's
parity work, where every distribution lever came back null at 96 seasons per arm.
