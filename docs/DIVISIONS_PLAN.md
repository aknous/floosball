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

# Addendum: Team Form Oscillation (BUILT + measured 2026-08-04)

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

`form_oscillation_check.py run <leagues> <seasons> <portBase> <out.json>` then
`report`. Splits each club's regular season into four equal blocks and takes the sd of
its wins across them. `FLOOS_FORM=off` runs the control arm; `FLOOS_FORM_PULL` /
`_REVERSION` / `_NOISE` / `_MAX` sweep the amplitude.

Do NOT tune this against win spread. That was the wrong objective; see the session's
parity work, where every distribution lever came back null at 96 seasons per arm.

## RESULT — built, measured, and redesigned (2026-08-04)

The specced mean-reverting design was built first and **failed**: form variance moved
1.06 -> 1.11. The reason is structural, not a tuning miss. **An arc IS a sustained
multi-week deviation, and negative feedback exists to cancel sustained deviation.** No
amplitude fixes that: the bigger the deviation, the harder the restoring pull. Modelled
against the measured transfer coefficient, even a pure forced sine wave of amplitude
0.16 tops out at ~1.18.

Flipping to **momentum** — a run feeds itself, bounded by an unconditional weekly decay
(`FORM_DECAY`) rather than by a restoring force — is what produced arcs. The decay is
what stops it running away, and measured win-sd is unchanged versus the reverting design.

### The number that unlocked all of this

`FLOOS_FORM_FORCE` pins half the league at +X and half at -X for whole seasons, so the
win-rate gap measures the rating-multiplier -> win-probability transfer directly. Over
16,128 team-games:

    +-10% roster-wide multiplier  =  0.324 win-probability spread  =  +-4.5 wins/season
    => 1.619 win probability per 1.0 of multiplier

The transfer is *steep*. The original layer under-delivered because its offset never sat
anywhere near its clamp, not because the lever was weak. Measure this before tuning any
rating-multiplier layer.

### Measured arms (8 fresh 32-club leagues x 5 seasons each, ~1,275 team-seasons)

| arm | form var | flat (<1.0) | win spread | corr(day1,final) |
|---|---|---|---|---|
| control (no form) | 1.06 | 45% | 22.3 | +0.750 |
| mean-reverting (as specced) | 1.11 | 39% | 22.0 | +0.752 |
| **momentum** | **1.36** | **25%** | 21.5 | **+0.593** |
| momentum + parity package | **1.46** | **18%** | **19.4** | **+0.502** |

Momentum clears the 1.32 coin-flip line, which was the plan's own stated bar for "real
oscillation". Clubs with a visibly flat season more than halve. The full package cuts
corr(day-1, final) from 0.750 to 0.502 — the season stops being legible from the opening
game day, which was the actual complaint.

1.6-1.9 remains out of reach and the target should be retired: at 7 games a block,
binomial noise alone has sd 1.32 and dominates. Reaching 1.75 needs a systematic swing
of ~1.2 wins per block on top of that, i.e. a club genuinely becoming a different-quality
team for seven straight weeks.

## Parity — the separate finding that came out of this

**Every pre-game modifier was offense-only.** Team defense ratings are derived from
PROFILE attributes at roster setup (`deriveDefenseFromRoster`) and never recomputed, and
the per-defender lookups in `runPlay`/`passPlay` read `.attributes` too. So league
compression, fatigue, funding morale, disposition and form all moved the offense and left
the defense untouched. `LEAGUE_COMPRESSION_FACTOR`, whose entire job is closing the
auto-win gap between stars and scrubs, had never touched half the game.

This explains why the six distribution levers came back null: **compression alone does
nothing because talent still flows through an uncompressed defensive channel.** Measured
directly — dialling compression from 0.7 to 0.45 left the win spread at 22.3, and even a
drastic 0.25 only reached 21.4.

Neither half works alone. Enabling defensive modifiers on their own made things *worse*
(best-record champions 28% -> 45%, Cinderella 12% -> 5%) because it also hands the
confidence / disposition / funding boosts to defenders, and those correlate with already
being good. Only the **pair** works:

| | baseline | compression 0.45 only | def-mods only | **both** |
|---|---|---|---|---|
| win spread | 22.3 | 22.3 | 21.9 | **19.9** |
| best team's wins | 24.7 | 25.4 | 25.1 | **24.3** |
| corr(day1, final) | +0.750 | +0.738 | +0.763 | **+0.652** |

## Cinderella runs — form has to carry into the bracket

Form was initially gated to the regular season, which quietly made the playoffs *more*
predictable: a club that surged late earned a good seed, then had its surge removed at
kickoff. `FORM_PLAYOFFS_ENABLED` carries the arc into the bracket (the offset stops
UPDATING at season end either way), scaled by `FORM_PLAYOFF_SCALE`:

| playoff form | champion had best record | champion from outside top 8 | mean champ rank | most titles / 40 |
|---|---|---|---|---|
| off (0.0) | 35% | 8% | 3.1 | 5 |
| **half (0.5)** | **20%** | **35%** | **6.1** | **4** |
| full (1.0) | 8% | 40% | 7.8 | 5 |

Full weight is too loose — a top seed winning 8% of the time reads as the regular season
not mattering. Half is the shipped value: a best-record champion about 20% of the time,
roughly real-football-like, with the lowest title concentration of any arm measured.

## Shipped configuration

    FORM_FEEDBACK = 'momentum'   FORM_PULL 0.50   FORM_REVERSION 0.45
    FORM_NOISE 0.050   FORM_MAX 0.14   FORM_DECAY 0.80
    FORM_PLAYOFFS_ENABLED = True   FORM_PLAYOFF_SCALE = 0.5
    DEFENSE_MODIFIERS_ENABLED = True
    LEAGUE_COMPRESSION_FACTOR = 0.45   (was 0.7)

Side effects, measured on a full fresh season: combined scoring **29.3 -> 33.0** per game
(closer to the ~36 the docs target, not away from it), but game-level variance widens at
both ends — shutouts 5.8% -> 9.0% of team-games, and 40+ point games 12 -> 46. The
shutout rate is the one number worth an owner eye; it is the cost of a club in a genuine
slump being genuinely bad on the day.

See the confirmation run below, which supersedes the 40-season figures above.

## CONFIRMATION RUN (8 leagues x 12 seasons per arm = 96 seasons, ~3,060 team-seasons)

The earlier arms were 40 seasons and the champion-rank figures in them were
**materially optimistic about the baseline**. At full power the control league is worse
than those numbers suggested: one club took 10 of 96 titles, a team went 28-0, and the
opening game day explained 61% of the final table. Trust these numbers, not the 40-season
ones. Proportions carry 95% Wilson intervals.

| metric | control | shipped | verdict |
|---|---|---|---|
| form variance (sd of wins across the 4 game days) | 1.03 | **1.44** | past the 1.32 chance line |
| clubs with a flat season (sd < 1.0) | 48% | **20%** | |
| corr(day-1 wins, final wins) | +0.784 (r2 0.61) | **+0.504 (r2 0.25)** | early season explains half as much |
| win spread | 23.1 +/-0.4 | **18.7 +/-0.5** | CIs do not overlap |
| best team's wins (of 28) | 25.8 | **23.3** | |
| champion had the best record | 38.5% [29-49] | **16.7% [11-25]** | CIs do not overlap |
| champion from outside the top 8 | 6.2% [3-13] | **24.0% [17-33]** | CIs do not overlap |
| most titles by one club | 10 / 96 | **6 / 96** | |

### The variance is actually shaped like a story

Block-win sd is only a proxy — it rises for week-to-week jitter as readily as for a real
arc. These are the things a user would narrate, and they moved together:

| | control | shipped |
|---|---|---|
| avg longest win streak | 5.25 | **6.05** |
| avg longest losing streak | 5.09 | **6.07** |
| best-to-worst game-day win% swing | 0.368 | **0.520** |
| turnarounds (bottom half after day 1 -> top quarter) | 2.1% | **6.0%** |
| collapses (top quarter after day 1 -> bottom half) | 2.3% | **6.4%** |

Turnarounds and collapses both roughly TRIPLE, and they move symmetrically — which is
what rules out the variance being noise. Longer runs in both directions plus a wider
swing between phases is the mechanical signature of an arc, not of jitter.

### Still not validated

* Economy, cards and fantasy have not been exercised under the wider scoring
  distribution. Nothing suggests a problem; nothing has checked.
* No long-run drift check beyond 12 seasons.
* Shutouts: diagnosed and fixed — see the section below.

## Shutouts — diagnosed and fixed at the source (owner insight)

The first shipped config raised shutouts from ~7% to ~9.5% of team-games. Decomposed
across five arms, the cause was **entirely the form layer** and it was pure tail-widening
— form-only moved shutouts 7.0% -> 10.2% while leaving mean scoring untouched
(30.4 -> 30.2). Defensive modifiers (6.9%) and compression (7.4%) were innocent.

The owner's diagnosis was better than damping the form downside: **winning teams never
took their foot off the gas.** The sim modeled the trailing team giving up
(`_isGarbageTime` stops them hurrying and spiking) but had no model of the LEADING team
easing off. A club building a blowout pressed at full intensity for four quarters, so the
trailing side often finished with nothing. In real football a settled game has the leader
rushing three, keeping everything in front and trading yards for clock — which is exactly
why a blowout usually still has the loser scoring at least once.

Two fixes, both real-football behavior rather than a damper:

1. **`Game.leadEaseOffFactor()`** (`LEAD_EASE_OFF_MAX` 0.15) — scales the LEADING team's
   effective run D, pass D and pass rush down in the second half when they are up more
   than two scores. Ramps with lead size and quarter.
2. **Q3 blowout drain** — the lead-protection floor was Q4-only, so a team building a rout
   in Q3 kept airing it out. A 3+ score Q3 lead now leans run and suppresses deep/long.

A third, smaller lever is kept as a knob: `FORM_DOWNSIDE_SCALE` (0.6) damps only the
NEGATIVE half of the form offset, on the grounds that arcs are driven by the swing rather
than by the depth of the trough.

### Scope of the ease-off (worth being precise about)

* It is **DEFENSE-only** — the leading team's effective run D, pass D and pass rush.
* The leading **offense** is affected separately and only through play-CALLING (the Q3
  drain + the Q4 lead-protection floor lean run and suppress deep/long). Its execution
  is untouched: a leading team still runs the ball just as well, it just runs it more.
* **WHO eases off is a coaching trait.** `0.5*(1-aggressiveness) + 0.5*clockManagement`
  maps to a 0.4x .. 1.6x multiplier on the ease-off, centered at 1.0 for a neutral coach
  so league-average behavior stays the measured one and the spread is character. A
  killer coach with poor clock sense keeps the defense at 94% of full and runs the score
  up; a conservative professional drops to 76% and lets the other side have the
  underneath. The Q3 drain is likewise coach-scaled (`_mul`), unlike the Q4 floor, which
  stays deliberately flat because nobody should be firing deep on a Q4 lead.

### Verification (6 leagues x 5-6 seasons per arm, 26,880+ team-games each)

With the ease-off coach-scaled:

| | control | shipped |
|---|---|---|
| **shutouts** | 7.6% | **7.1%** |
| team-games <= 3 points | 16.7% | **16.3%** |
| 40+ point games | 2.3% | 3.2% |
| combined scoring | 30.5 | 32.1 |
| form variance | 1.08 | **1.37** |
| flat clubs | 44% | **24%** |
| corr(day-1, final) | +0.749 | **+0.507** |
| win spread | 23.0 | **18.8** |
| turnarounds / collapses | 2.8% / 2.9% | **5.6% / 5.8%** |

Shutouts and the <=3-point rate now land BELOW control (from +2.5pp before the fix),
while every arc and parity gain survives. Blowouts stay somewhat elevated
(2.3% -> 3.2%), which is the honest residual cost of a club genuinely running hot.
