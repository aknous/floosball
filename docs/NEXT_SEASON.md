# Next-Season Feature Tracker

> Living list of features targeted for the next season cutover. **Keep this updated as features land** — move items to "Shipped" with the commit/version, and link each in-flight item to its design doc. Owner-curated.

_Last updated: 2026-08-07_

> ⚠️ This file has gone stale before — it once went 11 days saying nothing about the
> Autonomous Front Office while that was the only thing being built. **Verify status
> against code, never against this file or a `*_PLAN.md` header.** Both have misled in both
> directions: plans citing code that does not exist, and headers claiming "not built" for
> things that shipped under a different name.

> ⏱ **A season is ONE REAL WEEK.** Mon–Thu = the 28 regular-season weeks, Friday =
> playoffs, Saturday = offseason. So "next season" is next Monday, a 2-season median
> career is two weeks, and the postseason/offseason window that the Collection Pack
> covers is Friday–Sunday — recurring every single week, not once a year.

## Design pillars (owner, 2026-07-31)

What the game is for. Check features against this before building them.

**What fans want**
1. **Games with meaning, but also chaos** — awakened powers, rule changes. Meaning first: the
   chaos only lands because the results count.
2. **Players who are characters** — personalities exist (`personalityManager`, 432 vibe
   reactions, per-personality flavor/mottos, purge-dodge by meta-awareness tier) but want more
   fleshing out.
3. **Lore and narrative** — the Cores, the simulation. `data/lore.md`, `coresManager`.

**What we're introducing / deepening**
- **Fans interacting with the simulation** — rule votes exist; this is the direction to widen.
- **Gaming the awakening and Criticality events** — `docs/CRITICALITY_METAGAME_PLAN.md`.

**What must never happen** 🔒
- **Games, seasons, and players wiped out, restarted, or losing meaning.**
  → The contest's currency is **control and anomaly, never records.** Fair to lose: an awakened
  ability, who governs a rule, how tight the Cores' grip is. Never at risk: seasons, standings,
  careers, stats, the Hall of Fame, Renown, collections. A cleansed player loses the *power*, not
  the *person*.
  → This vetoed the 498b→498c letter-burn as a mechanic (it implied a restart). The lore survives
  as the Cores' own fear — motive for the opponent, never a thing that happens to your league.

## The list (owner, 2026-08-07)

Eleven items for the next cutover, in the owner's order. Each is annotated with what
already exists in the code, because several are further along (or further behind) than
they read. **Verify status against code, not against this file or a `*_PLAN.md` header** —
both have misled before, in both directions.

### 1. Finalize new team colors and icons

Further along than "needs finalizing". The heraldic pattern set was already extended
24 → 32 at expansion, and a render of all 32 with colours stripped confirms **32 distinct
marks, no duplicates** (`avatar_generator._generateMarbleSvg`). Marks are generated from
each club's two colours + a pattern keyed to `(teamId - 1) % 32`.

What actually needs a decision is **contrast**, and it is mostly NOT the new clubs:

| club | primary vs secondary | |
|---|---|---|
| San Diego Sand Dollars | **1.0:1** | luminance-identical — the pattern vanishes, the mark is a flat disc |
| Colorado Oysters | 1.4:1 | |
| Anaheim Rhyme | 1.4:1 | |
| Seattle Cranes | 1.7:1 | |
| St. Louis Arches (new) | 2.2:1 | grey on red, muddy at the 20px standings size |

The other seven new clubs run 3.2–5.3:1 and are fine. ⚠️ `logoInvert` exists for exactly
this kind of fix, but it only swaps which colour paints field vs figure — it cannot help a
pair with equal luminance, which needs a colour CHANGED rather than reordered.

Also worth knowing: pattern **23 has no explicit branch**. It falls through to the `else`
(a "pale", single vertical band). Output is still unique because nothing else draws a
pale, but it is implicit rather than intended, and it is Georgia Classics that gets it.

### 2. New dashboard page

Design to come from the Claude design tool (owner).

### 3. Renown system for users

Spec is done and grounded: `docs/RENOWN_PROGRESSION_PLAN.md`, specced against 15 seasons
of real data 2026-07-31. **Zero code.** v1 scope is foundation + career ranks.

The superseded model's code and design are now readable at `docs/recovered/` (see item 9)
rather than only in a git commit.

⚠️ Renown **supersedes** the earlier achievement-derived progression model — settled by
owner, do not re-litigate. But that model was BUILT and then pulled for timing, not on
design grounds, so there is salvage: `2a37f2f` has `managers/progressionManager.py` (172
lines) and `GET /api/profile/{userId?}` with no schema changes. Worth reading before
starting from scratch.

Retention data point from the spec: churn is seasons 1-3, not season 15. Build for the
early game.

### 4. Profile page for users

Pairs with 3 — `GET /api/profile/{userId?}` exists in the pulled commit `2a37f2f` and is
cherry-pickable. Decide whether the profile is Renown's surface or a separate page that
Renown feeds.

### 5. Let users set their own username

Partly built, and the gap is not where it looks. `POST /api/users/me/username` already
accepts an **arbitrary string** — it is not restricted to the generated candidates from
`GET /api/users/me/username-options`. The real limits are:

- **once only** — it hard-rejects when `username is not None`, so there is no rename path;
- **no validation** — no length, charset or profanity rules, only a uniqueness check;
- the frontend may only surface the generated options.

So the work is a rename path (cost? cooldown? free first change?), input rules, and UI.
`POST /api/admin/users/{userId}/reroll-username` exists as an admin escape hatch today.

### 6. Games grid page

Like the current dashboard but games only. Shares the schedule/day model with the pick-em
whole-day view (`GET /api/pickem/day` already returns every slot of the current calendar
day with games and picks).

### 7. Update the game modal

Social posts in the style of the new team page, plus Cores interactions.
`GET /api/cores/conversation` already serves ambient banter and can force a data-aware
beat (`?event=observe`), which reads real teams and scores. ⚠️ That endpoint is the ONLY
place raw anomaly numbers are allowed to surface — the public feed and header stay
number-free. Keep that line if Cores chatter goes in the modal.

### 8. New standings page — divisions + playoff race in one place

Design to come from the owner.

Divisions are real but derived, not configured: `seasonManager._generateDivisionalSchedule`
splits each league in half at schedule generation and stamps `team.division` as
`"{League} East"` / `"{League} West"` — so 2 leagues × 2 divisions = 4. There is no
divisions table and no constant; the names come from that string.

⚠️ **Verify the playoff rule before designing the race view.** `_applyDivisionSeeding`
guarantees a division winner qualifies even on a record that would not have made it, which
is exactly the kind of thing a "playoff race" UI has to model. CLAUDE.md still documents
the 24-team rule (top 6 per league, top 2 get a bye); confirm what 32 clubs actually do.

### 9. Prognostication evolution

✅ **Recovered 2026-08-07** to `docs/recovered/PICKEM_DEPTH_PLAN.md`. It was deleted by
`54a6275`, the revert of the progression commit, and nothing noticed because a missing
markdown file breaks no build. Filed under `recovered/` rather than restored in place, so
it is unambiguous that it is history rather than live design — it predates the
fantasy/cards fusion, the autonomous front office and the 24 → 32 expansion.

Its useful core: depth should come from **skill, progression and story, not staking**
(owner ruled out confidence wagering, parlays, over/unders, spreads and margin lines), and
it must stay compatible with setting a whole day of picks at once. It also notes the real
strategy that already exists but is invisible — backing live underdogs early is a genuine
EV edge that nothing in the UI tells you about.

Related but distinct: the preseason prediction model (run N sims at season start → average
wins + title odds → a "favorites" board). POC exists at `docs/SEASON12_PREDICTIONS.md`.

### 10. Prod fresh start that keeps some history

✅ **BUILT 2026-08-07** — see `docs/FRESH_START_HISTORY_PLAN.md`. Scope settled to "light
data": one archived row per season (champion, league champions, MVP). User progress, records
and the Hall of Fame are deliberately NOT preserved (owner call).

⚠️ **`tools_archive_seasons.py --apply` must be run against prod BEFORE the wipe.** It is
the last moment the old league is readable, and the archive is the only thing that survives.

**The item with real risk — do this deliberately, not at the cutover.**

`clear_db()` preserves exactly four tables: `users`, `beta_allowlist`, `app_settings`,
`unused_names`. Everything else is DROPPED and recreated, which on a fresh start means
losing: `Record`, `Championship`, `Season`, `SeasonRecapEvent`, `PlayerSeasonStats`,
`PlayerCareerStats`, `TeamSeasonStats`, `PlayerRatingHistory`, and the Hall of Fame (which
lives on `players.is_hof` / `players.hof_season`, and the players table goes).

Open questions to settle first:
- **What counts as history worth keeping?** Records and championships are league-level and
  survivable. The Hall of Fame is harder: it is attached to player rows that will not exist
  in the new league, so it needs either a denormalized archive table or an accepted break.
- **Do old records stay comparable?** The league goes 24 → 32 clubs and 28 weeks stays,
  but a rebalanced sim means a preserved record may be unbeatable or trivial.
- Whichever way it goes, it needs a migration path, not a flag — and per standing rule,
  **never `FRESH_START` in prod** (it survives restarts and would wipe on outage recovery).
  The one-shot `touch /data/.fresh` flag file is the supported route.

### 11. Deeper player data page

**Not a priority** (owner). Worth noting the data is already there and unused: the
advanced metrics (`yardsAfterContact`, `brokenTackles`, `contestedCatches`, `bailouts`,
`goodThrows`, `airYardsSum`, returning stats) all persist in the JSON blobs and mostly have
no UI.

## Backlog (owner notes, unspecced — 2026-07-02)
Rough capture; each needs a design pass before building.

- **First iteration of rule changes** (Workstream B — owner mechanic specced 2026-07-07) — take the rule-mutation layer from tooling to an actual live, Cores-driven rule change. **Mechanic:** the Core **Aris** opens a mid-season CHANGE vote (a list of candidate rules, each showing current value → proposed new value; most-voted change goes live); later the Core **Halverson** opens a REVERT vote (pick changed rules to restore). Plumbing already exists (data-driven scoring rules + persisted override layer; mutable `firstDownDistance`/`downsPerSeries`; clock/FG knobs; running-clock rule; `GET /api/rules` + "current rules" UI shipped as foreshadowing) — see `docs/SIM_EVOLUTION.md`, the `Rule mutation:` commits, and memory `rule-mutation-future-ideas`. OPEN: vote timing in the season, how many rules per cycle, who picks the proposed new values, vote cost, Criticality interaction. Blast radius (WP model / pick-em / scoreboard all read rule+score state) is bigger than the parity package — scope after Workstream A's distribution work is underway.
- **New attention sources** — expand what feeds player "attention" beyond the current four (equipped cards, fantasy roster slots, follows, favorite-team fans; all in `anomalyManager._applyWeeklyContributions`). Brainstorm additional user-driven signals so attention concentration has more inputs (keeps it user-generated, not sim-driven).

### Future-season directions (owner thoughts 2026-07-20 — "more like future seasons", revisit before speccing)
Three separable tracks; each needs a design pass. Grounding + open decisions captured so we don't re-derive.

- **Card effects off the ON-CARD player's stats** (fantasy-fusion era) — trigger a card's effect off the stats of the player depicted on THAT card, not the whole fantasy roster. This is the **fusion** direction (each equipped card = a rostered player → natural 1:1 card→player link to hang effects on). Today it's the opposite: `CardCalcContext` (`managers/cardEffectCalculator.py:41`) is entirely **roster-aggregate** (`rosterTotalTds`, `rosterPlayerRatings`, same-team stacking, sub-.500-on-roster, Vanguard "5+ veterans"). Per-card re-basing is tractable (the equipped card already carries its `player_id`). OPEN: re-base **every** effect on the card's player (roster-wide effects like same-team stacking / Rookie Hype / Vanguard get reinterpreted or retired) vs. add a **new "self" effect class** alongside the roster ones (rec: former fits fusion). **Gated on fusion landing first** (`feature/fantasy-cards-fusion`, `docs/FANTASY_CARDS_FUSION_PLAN.md`).

- **League restructure — 2 divisions of 6 per league, new 28-game schedule** — each league (12) splits into 2 divisions of 6. Schedule (still 28 games, math exact): **10** intra-division (play each of your 5 division rivals ×2) + **6** other-division-same-league (×1) + **12** other league (all 12 ×1) = 28. Notes: (1) **divisions don't exist structurally yet** — zero `division` refs in `leagueManager.py` (the CLAUDE.md mention is stale); introduces a division layer (assignment + standings). (2) Rewrites schedule gen — `seasonManager._generateSchedule` (`:3733`) currently = intra-league round-robin (22) + inter-league (6); new mix roughly halves intra-league and **doubles inter-league 6→12** (big flavor shift — leagues become far more intertwined). OPEN: **playoffs** — division-winner auto-berths / division-based seeding vs. keep "top 6 by record per league"; **realignment** — does `leagueManager.realignByRecentPerformance` now also seed the 4 divisions, or do divisions stay fixed while leagues rebalance; division tiebreakers.

- **Remove prospect/rookie draft → periodic FA-pool injection** — ✅ **SETTLED 2026-07-27 (owner): do it.** Specced as **Part F of `docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md`**, not as a standalone track. The collision below is resolved: the autonomous FO's aggression dial reads the worst-first **FA** order (`FO_FA_CONTENTION`), never the rookie draft, so the already-built GM brain needs no rework; and `playerManager.ensurePositionSupply` already guarantees the per-position roster floor, so it gets promoted from safety net to primary intake. The three-tier prospect true-skill model is recommended to SURVIVE (it's an entry-independent parity lever the GM brain's arc reading depends on). Original note follows. ⚠️ **Collided with in-flight work**: (a) the just-shipped **parity prospect true-skill model** (three-tier `current < trueSkill < potential`, rookies debut low and grow in — itself a skill-creep/parity lever, `docs/PARITY_PROSPECT_PLAN.md`); (b) the **autonomous Front Office plan** is built on the draft — "draft-position → aggression dial", worst-first rookie/FA drafts, cut-for-upgrade thresholds scaled by draft slot (`docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md:91`). Woven through the offseason flow (`rookie_draft` phase, `playerManager.rookieDraftPickGenerator`, rookie ballots, prospect promotions, Rookie Pack `is_rookie`). OPEN: does injection **replace** the debut-low-grow-in model or do entrants still arrive underdeveloped just via FA; what replaces "draft position" as the FO aggression signal (worst-first **FA priority order**?); injection cadence. **Settle this before building the autonomous FO** — it's the track that most affects other plans.

### The Deeper Game — fans vs the Cores (owner framing, 2026-07-31)
The anomaly/Criticality layer reframed: **football is the scenery, the real contest is fans
against the five Cores.** Vigils as a deliberate attention lever, a trailing-baseline bar a
coordinated surge can actually cross, contested firing (the Cores spend finite patches) instead
of a dice roll, Cores with alignments — Aris leaks, Pyre contains, Cassian is distractible so
dramatic weeks are cover — and the **498b → 498c** letter-burn from `data/lore.md` as the
long-game scoreboard.
- **Plan:** `docs/CRITICALITY_METAGAME_PLAN.md` — specced, nothing built.
- **Why it's a prerequisite:** `SIM_EVOLUTION.md` Stage 2 (fan-voted rule mutation) is the
  Criticality *aftermath*, so it can't land until the trigger is a contest rather than weather.

**Ball-carrier moves + pre-snap recognition.** ✅ **SHIPPED 2026-08-01** — not on the original
four-item list; came out of the same thread. Stiff arm / spin / hurdle keyed off a shared `_flair`
(creativity + xFactor) and the new determination state, retro-fitted to the stretch and diving
catch so those attributes matter everywhere (`c2ef406`, `db7b522`). Plus a pre-snap run/pass read
that gives `defensiveMind` its first per-play job and gives the fakes something real to fool
(`4515ce9`, `b041642`). Regressions `test_runner_moves.py` / `test_presnap_read.py`.

## Bugs / smaller fixes
- **League scoring sits ~27.5 in a fresh sim vs the ~36 documented in CLAUDE.md** ⚠️ OPEN — measured
  repeatedly on 2026-08-01 and unchanged by any of that day's work. Either the parity package's
  lower generation seed showing up in a season-1 league, or real drift. ⚠️ **Note for whoever picks
  this up:** paired fresh sims CANNOT resolve small effects here — each regenerates the whole player
  pool and the run-to-run spread was 27.4–31.1 pts/g across four runs. Measure mechanics directly.
- **Docs describe a stale attention model** — `docs/CHROME.md` and `docs/CRITICALITY_METAGAME_PLAN.md`
  still say four attention sources with cards at 10/wk. Development's `5dcc8dd`/`1078e7f` cut it to
  three with cards at 18, and equipped cards were contributing NOTHING on prod before that fix.
- **Criticality threshold is outrun by the season** ⚠️ OPEN — folded into the Deeper Game plan
  above (the trailing baseline). Needs a design call — the bar
  sits at 0.92× the expected resting level (permanently crossed by construction) AND is
  estimated once at week 6 from an estimator that assumes constant input, so it under-reads
  a growing league ~3×. Result: the crossing carries no information and the 30% dice roll is
  the whole trigger, so Criticality **is** random. A fixed bar can't work (the aggregate
  grows 2-3× a season); it needs a trailing baseline. Can't be validated by `simcheck` —
  FAST mode bypasses the adaptive threshold entirely. Full audit in
  `docs/AWAKENED_POWERS_PLAN.md` "Known defects".
- **Awakening has no deliberate lever** — design work, not a bug; same audit, last section.
- **`PURGE_MAX_CHANCE` (0.45) wants an owner balance pass** — the purge curve was fixed from
  a 10% ceiling to a real one, but the prod-mode value is reasoned, not sim-measured.
- **Showcase dividend rate balance pass** — `SHOWCASE_DIVIDEND_RATE` (0.13) was a calibrated starting point (sustained S ≈ the old ~3000 lump/season, top end uncapped); still wants an owner balance pass.

## Shipped (this cycle)
- **League parity + prospect true-skill package** ✅ — the top-heavy-league fix (Cranes ~26-2, 80% titles in S13 sims). **Distribution levers:** lower/wider generation seed + flattened dev rise (target ~15-20% 4-5★) and a one-time **rank-preserving percentile re-map** of the live pool at the cutover (Phase 3). **Prospect true-skill model:** three-tier ratings (`current` < `trueSkill` < `potential`) — rookies debut below their mature target and grow into it over 2-3 seasons (Phases 1-2). **Salary cap SCRATCHED** — Phase 5 built model B (`3a30b60`), then **pivoted to retention limits** as the parity model instead (re-signs are fan-vote-driven; cap code removed). Commits `674ed92`/`7e687e3`/`3a30b60`→`c8e1ec7`/`af9d51c`. Plan: `docs/PARITY_PROSPECT_PLAN.md`.
- **Playbook diversification** ✅ — a real offensive playbook layered on the sim: run concepts (power/draw/counter/sweep) with deception + execution rolls, gap coherence, and defensive counter-adaptation; play-action; route concepts (mesh/flood/screen vs coverage); RPO (QB reads the box pre-snap); trick plays (flea flicker / statue / reverse) as rare called shots. Coach-gated (aggressiveness = experimental adoption / offensiveMind = standard sophistication), situationally aware, balance-measured (concept ON/OFF for inflation), self-describing PBP with the scheme detail in the Play Insights "Play Design" row. Commits `a3e92ef`…`5c7d077`. Plan: `docs/PLAYBOOK_PLAN.md`. (Tuning `5c7d077`: flood out of PBP → insights only; trick plays cut to ~3.4/team/season from ~42.)
- **Coaching / play-calling depth** ✅ — gameplan wiring made real: `runPassRatio` + a master gameplan switch, situational pass-depth quick-game lever, adaptable coaches re-plan mid-game (not just at halftime), and a Q4 lead-protection floor so every team runs the clock better with a lead. Commits `67e60f3`/`dd03fef`/`6d93c2f`/`20b75ea`.
- **Clock / kneel / FG fixes** ✅ — score before the half + never let a scoring snap die with timeouts; kneel rules (no 4th-down kneel, no draining a stopped clock); cap awakened-kicker range; PBP: a diving catch no longer also stretches for the marker. Commits `deb11ee`/`26328c9`/`6c69afb`/`0c5cb25`/`1cab194`.
- **HoF: never induct an active player** ✅ — a ballot candidate whose `willRetire` was cleared after seeding (longevity retune / re-signed in FA) can no longer be enshrined while rostered; induction guards on actual retirement and drops stale candidates, with reactivation if they later retire for real. Regression `test_hof_active_guard.py`. Commit `445350d`. (Prod records for Chili Arthur / Briam Flumpton repaired.)
- **Rookie Pack** ✅ — a themed card pack for the current draft class (`is_rookie` templates), rotating in the shop. Commit `d9c3819`.
- **Rulebook backend** ✅ — `GET /api/rules` surfacing the current ruleset (foreshadowing the rule-mutation layer). Merged `a8844ce`.
- **Team Markets → Facilities rework** ✅ — fan-funded, fan-voted Facilities (Market = fanbase / Treasury = money / Facilities = built perks driving Appeal → FA order); live-wired funding, contribution achievements (Patron/Benefactor/Underwriter), fully-funded projects build immediately mid-season. Merged via `03bb474`. Plan: `docs/MARKETS_FACILITIES_PLAN.md`.
- **Sim Evolution — Layer 4 (Criticality)** ✅ — awakened powers + the league-wide Criticality fire framework; event paced to ~1/season, uncapped suppressions, `criticality_enabled` admin toggle drives the whole event. Merged via `a690f87`/`6e1e1d1`. Plan: `docs/AWAKENED_POWERS_PLAN.md`.
- **Card Vault + Showcase** ✅ — permanent Vault (trash/reorder/team-sort, vault-aware Level Up + equip exclusion), Showcase weekly-dividend payout + per-card scoring transparency + sets paytable. Merged via `fdc8a6f`/`763daf8`. (Dividend rate balance pass still open — see Bugs.)
- Card-effect tuning pass (Showoff base card OP) ✅
- Bracket achievement tiers unlock only at Floos-Bowl end (not incrementally) ✅
- Day-end site slowness (synchronous email sending off the hot path) ✅
- Playoffs: team streak/form keep moving; games-played tracks regular season only; round-1 bye fatigue reprieve ✅
- Reactions: pointerdown gesture-gate (phantom-reaction fix) ✅
- Front Office: FA Requisition reworked — **thresholdless ranked-choice** (any ballots resolve via IRV to the most-wanted available targets; no probability roll, no pass/fail). Front Office shows the ranked **priority target list**, not a "RATIFIED X/Y votes %" tally. Makes the old floor-2-vs-1 concern moot (no threshold at all). ✅ (backend `ac36be7`, frontend `afebc8a`)
- FA Requisition — **position fill-priority** ✅ (committed `ee47fdc`): new optional `position_priority` on the FA ballot — fans drag-rank all 5 positions (QB/RB/WR/TE/K) for which slot to fill FIRST once voted players run out. Borda-aggregated per team (`gmManager._aggregatePositionPriorities`), consumed by `playerManager._attemptRosterFill` to OVERRIDE best-rated in the fallback (so a team that ranked QB/WR above K won't auto-grab a higher-rated kicker). New `gm_fa_ballots.position_priority` column + migration; `resolveSignFaVotes` now returns a 3-tuple; resolved order surfaced as `faPositionPriority`. UI: a "Set fill priority" toggle + reorder rows in `FaBallotModal`. Full ranked voted list already shown ("Free Agent Vote Tallies" in the FO). Validated via simcheck (rosters 6/6, best-available fallback unchanged with no ballots). ✅
