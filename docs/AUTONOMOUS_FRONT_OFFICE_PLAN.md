# Autonomous Front Office + Fan Sentiment Redesign

**Branch:** `next-season` (season-cutover feature)
**Status:** Steps 1-9 and Parts A-E are BUILT + sim-validated. The brain is
LIVE (`AUTONOMOUS_FO_ENABLED=True`), the binding-vote system is deleted, and
Part F's draft removal is now CODE, not just a flag (wave 1, 2026-07-29).

**Remaining — three items, none blocking a deploy:**
1. **Part F wave 2** — the prospect half (`is_prospect`, `drafting_team_id`,
   `prospect_seasons`, promotion, `_advanceProspectWindow`, `PROSPECT_*`).
   Deliberately deferred: prospects are still draining on deployed DBs and
   promotion is load-bearing until they hit zero (~3 seasons). Owner ruled the
   COLUMNS stay permanently — code only, no table rebuild.
2. ~~**Team page redesign** — PAUSED by owner 2026-07-29.~~ ✅ **DONE 2026-07-31**
   (frontend `088daca`).
3. **Step 10** — team mood as a morale/atmosphere consumer. Optional, never
   started. (An earlier revision claimed `teamMood` was "computed and surfaced
   but wired to nothing" — that is WRONG: no such value exists anywhere.)

See "Build status" at the bottom.
**Ships:** next-season boundary
**Related:** `docs/FANTASY_CARDS_FUSION_PLAN.md` (same "simplify / de-intimidate" thrust)

## Motivation (survey)

Users find team management confusing and intimidating. A large share said they'd
prefer player acquisition/retention happen **autonomously**, with **less** direct
control — no votes to sign/cut/re-sign players, no free-agent or rookie ballots.
Fans become **just fans**: they express how they *feel* about players and the GM, and
that sentiment **gently nudges** the sim's decisions — it never dictates them.

## The core shift

Today, binding fan votes are the ONLY thing that changes roster/coach outcomes, and
the sim's own "no-vote" path is weak (see below). We flip it:

> **The sim decides. Fans express sentiment. Sentiment tips the sim's hand in
> proportion to each GM's own personality.**

Four pillars:
1. **An autonomous GM brain** — the roster/coach decisions the sim must now make well.
2. **Coaches become GMs** — specialist attribute profiles (no more star ratings).
3. **GM turnover** — fired / retire / leave, each a sim call, each a replacement gamble.
4. **A fan-sentiment layer** — 1–5 player ratings + a social-feed team page — that
   nudges the brain.

---

## Part A — The autonomous GM brain

### Current reality (why this is the bulk of the work)
The offseason is **NOT** meaningfully autonomous today. Verified:
- **Re-signs:** default is *"everyone on a walk year leaves."* No auto-keep. The only
  stand-in is a sim-only env flag `SIMULATE_FAN_RESIGNS` (`seasonManager.py:6300`),
  off in prod. Hard limits: `RESIGN_ONCE_LIMIT=1`, `RESIGN_LIMIT_PER_OFFSEASON=2`
  (`constants.py:874`).
- **Cuts:** **no autonomous cut logic exists at all.** Players leave only by fan vote,
  expiry, or retirement.
- **Coach fire:** no autonomous fire — coaches only turn over by retirement today.
- **FA signing** (`playerManager._attemptRosterFill`, `:3502`) and **rookie draft**
  (`rookieDraftPickGenerator`, `:4072`) DO run autonomously — best-available by
  `playerRating` — so those two are close to ready. (Describes TODAY. The rookie
  draft is being removed outright — see Part F — leaving FA signing as the single
  acquisition path.)
- Autonomous logic today is **rating-only**: team record, ELO, and morale feed **no**
  roster decision.

### Hard constraints (KEEP from last season's parity package — do NOT re-tune)
- **Max 2 re-signs per offseason** (`RESIGN_LIMIT_PER_OFFSEASON=2`, `constants.py:874`).
- **Each player re-signable only once** (`RESIGN_ONCE_LIMIT=1`).

These carry over unchanged. The only thing that changes is the *driver*: last season the
2 keepers were chosen by fan vote; now the **GM picks its 2 most valuable walk-year
keepers** by its own assessment (sentiment-tilted). Same guardrails, new decider.

### What to build — a comparative, value-weighted GM model
Run per team in the offseason. It must manage the roster like an actual GM, not just
value players in the abstract:

1. **Value the roster — FORWARD-LOOKING, scouting sees the career ARC.** Value is a
   *projection*, not the current number, `× POSITION_VALUE`. Scouting doesn't just add
   noise to `playerRating` — it determines how well the GM reads a player's **trajectory**,
   from POTENTIAL headroom on the way up + the age/retirement curve on the way down
   (`computeRetirementOdds`, `playerManager.py:1195`). (The three-tier
   `current < trueSkill < potential` model this originally leaned on was REMOVED —
   see Part F consequence 1 — so the arc reads off potential.):
   - **developing** (young, real headroom below `potential`, about to rise),
   - **prime** (at peak),
   - **regressing** (past longevity, declining next season).

   **High scouting** values the forward projection: **buys low** on an ascending youngster
   (mediocre now, about to pop) and **sells high** on a vet before the cliff (looks fine
   today, falls off next year). **Low scouting** judges on the current number only:
   overpays to keep a declining vet, cuts a developing player who looks unremarkable, and
   misses the ascender — genuinely bad personnel decisions, emergent from the attribute.
   Second-order: paired with `playerDevelopment`, a sharp GM reasons "this kid will rise
   AND I can develop him," so development-minded GMs rationally take on raw talent.
2. **Positional value weighting** — a `POSITION_VALUE` table (QB highest → RB/WR → TE →
   K lowest). All fill/upgrade/need decisions rank by `ratingDelta × positionValue`, NOT
   raw rating — this is what stops "best available = a great kicker" when there's a
   QB/RB hole. Start **universal** (shared table); optional small per-GM biases later.
3. **Re-sign (COMPARATIVE vs the market — not auto-best-2)** — a walk-year incumbent
   gets one of the ≤2 re-sign slots ONLY if he beats the best available replacement at
   his position (value-weighted, scouting-noised) AND is worth locking up over an FA
   move. Otherwise let him walk and chase the upgrade / spend the slot elsewhere. Slots
   are scarce (cap 2, once each), so they're spent only where the incumbent genuinely
   wins. This is the same incumbent-vs-pool comparison as cut-for-upgrade (step 5).
4. **Detect needs** — weak/vacant slots, weighted by positional value (a weak QB is a
   bigger need than a weak K).
5. **Cut-for-upgrade DECISION (COMPARATIVE, threshold scaled by DRAFT POSITION)** — for
   each slot weigh the **incumbent vs. the best available replacement** (the FA
   pool; rookies are gone — see Part F). If `(replacementValue − incumbentValue)` clears an
   **upgrade threshold**, CUT the incumbent (in anticipation of signing a replacement); else
   stand pat. **The threshold scales with the team's worst-first FA-draft slot** — this is
   the aggression dial (already implemented for re-sign as `FO_FA_CONTENTION`):
   - **Early pick (bad teams) → aggressive:** confident of landing the replacement, so a
     *smaller* edge justifies a cut (lower threshold). Churn to climb.
   - **Late pick (good teams) → conservative:** cutting is a gamble when you pick last and
     may get leftovers, so a *bigger* edge is required (higher threshold; lean toward
     re-signing your own).

   Cuts are purposeful churn toward improvement, high-value needs first. **The actual
   signing happens later** in the separate worst-first FA draft — steps 3 and 5
   only DECIDE re-sign/cut. (Note the pro-parity loop: bad teams churn aggressively, good
   teams stand pat; and a high-scouting late-drafter still eats well because the ascending
   players it values are the ones lesser scouts pass on, so they survive to its pick.)
6. **Sentiment tilt** — throughout, fan sentiment × `fanTrust` nudges close calls (keep a
   fan-favorite marginal player as a re-sign; cut a fan-villain the GM would otherwise
   keep). See Part D.

> **Sweep vs. drafts:** steps 1–6 are the best-first **assessment sweep** and produce only
> cut/re-sign **decisions** (no signing). Vacancies are filled afterward in the existing
> **worst-first** FA draft (best-*value*-available, position-need aware; no fan
> ballot). See "Offseason ordering" below.

**Churn:** re-signs are hard-capped at 2; cuts are not. Lean is to let churn
**self-limit** (real upgrades are scarce, every team fishes the same finite FA pool, and
worst-first FA order means a cut may not be replaced) and add a soft per-season cap only
if `simcheck` shows thrash.

### Per-team behavior (no global nudge knob)
Each GM manages differently, driven by **their own attributes** — this is the design's
main source of emergent identity:
- `scouting` → **career-arc vision** (reads developing/prime/regressing, values the
  forward projection) — the difference between buying low on an ascender and overpaying a
  vet about to fall off.
- `fanTrust` (**new**) → how much sentiment moves them: 0 = ignores the fans entirely,
  high = populist who over-churns fan-villains and regrets it.
- `playerDevelopment` → patience with young/declining talent (and, with scouting, the
  confidence to take on raw talent it can grow).
- **Draft position** (not an attribute — the team's worst-first draft slot) → aggression:
  early pickers churn boldly, late pickers hold.

Same inputs, different weights → the stubborn GM, the populist, the shrewd evaluator.

### Offseason ordering — the "invisible draft board" (best-first ASSESSMENT sweep)

Before the drafts, a **sequential assessment sweep** runs one team at a time in
**best-to-worst** order: **Floos Bowl champion first, then by win% descending** (same
tiebreaker chain as standings). **This sweep makes CUT and RE-SIGN decisions ONLY — it
does NOT sign free agents.** Each team, on its turn, evaluates the market for context,
decides who to re-sign (≤2) and who to cut, and its **cut players drop into the shared FA
pool LIVE** — purely so the teams after it assess with the *full* market visible.
Deterministic: walk the order, mutate one shared pool.

**Actual acquisition is unchanged and parity-safe.** The **FA draft is still its own
worst-to-best step**. So the best teams do NOT
get first crack at free agents — best-first only sets the order in which teams finalize
their own keep/cut lists and feed cuts into the pool. No anti-parity effect.

**Reordered offseason.** Old: (vote-driven frontoffice) → rookie draft → FA draft. New:
`GM turnover → best-first assessment sweep (cut/re-sign only) → worst-first FA draft
→ training`. GM turnover (fire/retire/leave + replacement) resolves FIRST so the GM
making a team's calls is the one who'll coach it. The rookie draft is REMOVED entirely
(Part F); new players enter the FA pool by periodic injection.

**Emergent risk (a feature).** Because the FA draft is worst-first, a team that cuts or
lets a decent player walk *hoping to upgrade* picks LATER in the draft and may not land
the replacement — a champion cutting for an upgrade gambles the target survives ~23 picks.
So cut/re-sign decisions carry real risk, and a sharp GM (high `scouting`) weighs its own
FA-draft slot before dumping someone; a cautious GM holds a decent incumbent rather than
risk the leftovers. Front-office tension for free.

---

## Part B — Coaches become GMs: specialist profiles, no star ratings

### The change to generation (coupled to dropping stars)
Today each coach's attributes are drawn from `normal(center, 10)` around **one
per-coach `center`** (`floosball_coach.py:61`), so a coach is *uniformly* good or bad
and the overall rating (`:55`, averages 6 of 8 attributes) actually **is** meaningful.

We want coaches to be **specialists** — great offensive mind / weak defense / sharp
scout / poor developer — so:
1. **Regenerate with wide, largely-independent per-attribute spread**, plus a **small
   shared component** so a rare all-around **elite or bust** still exists (owner-approved
   lean). Most GMs are specialists near ~average overall; the tail is rare.
2. **Then the aggregate is statistically noise** (central-limit pulls the average to the
   middle) → **drop the star / `overallRating`.** The two ship together — the star is
   only useless *after* step 1.

Extra reasons the current aggregate is a poor summary: it **excludes `scouting` and
`attitude`** (the two most GM-critical traits), and its only real consumer is the
hire-vote fallback (`gmManager.py:258`, "highest `overall_rating`"), which is deleted
with the votes anyway.

### What replaces the star: a scouting-report profile
A GM reads as their **attribute spread + derived tags**, not a scalar:
- Top attribute → specialty (*Offensive Guru*, *Sharp Eye*).
- Bottom attribute → flaw (*Can't Scout*, *Poor Developer*).
- Fan-trust axis surfaced plainly (*Players' Coach* / *Old School* / *Populist*).

Legible identity, no misleading number, and it tells fans exactly what to expect from
their front office.

### Attribute → role mapping (one entity, two hats)
The coach still coaches in-game (existing play-calling reads the gameday attributes) AND
now manages the roster:

| Attribute | Gameday role (unchanged) | GM role (new) |
|---|---|---|
| offensiveMind / defensiveMind / clockManagement / aggressiveness / adaptability | play-calling | — |
| **scouting** | rookie-potential visibility | **roster valuation accuracy** |
| **playerDevelopment** | player growth | **patience with young/declining talent** |
| **attitude** | locker-room contagion | (input to leave-risk / room) |
| **`fanTrust`** (new) | — | **sentiment weight** |

---

## Part C — GM turnover: fired / retire / leave (all sim-decided)

Three exit paths, each rolling the **replacement gamble**. No fan hire vote; the
replacement is sim-generated and — because coaches are specialists — **better or worse
per-dimension** (fire a GM for botching the roster, land a superb evaluator who's a
worse gameday coach). Real tradeoffs, not a scalar up/down.

1. **Fired** — sim decision when negative fan sentiment toward the GM + poor record
   cross the GM's threshold (threshold itself can vary by GM). Replaces the old
   `fire_coach` vote.
2. **Retire** — keep the existing tenure curve (`shouldRetire()`,
   `floosball_coach.py:79`; replacement via `handleCoachRetirement`,
   `teamManager.py:1507`); optionally let the profile matter.
3. **Leave** — voluntary departure. Hook to sentiment so a GM in a **hostile** fanbase
   can walk **even while winning** — fans can drive a GM out by firing OR by poisoning
   the well, and even a well-run team can lose a beloved GM (attachment / gut-punch).
   No poaching / destination modeling — they simply step away.

**Tuning:** three exit paths risk over-cycling — target only a few GM changes
league-wide per season, not a carousel.

---

## Part D — The fan sentiment layer

### Signal 1: player ratings (1–5)
- Fans rate individual players **1–5** (chosen over binary: same cost to the fan, but it
  yields a clean **"Fan Favorites / Most Hated"** board per team and league-wide, and a
  richer signal for the GM brain).
- Persistent, changeable, **net one rating per fan per player** (anti-brigade).
- Aggregated as an average with a **minimum sample size** before it counts.
- This is the quiet signal the GM brain reads.

### Signal 2: the social-feed team page (Rocket-League quick-chat)
- The team page becomes a **social feed**: fans "post" **pre-made** supportive/angry
  reactions (no free text = no moderation problem), targeted at **players** ("Trade
  him!", "Franchise cornerstone!"), the **GM** ("Fire the GM", "In [name] we trust"),
  or general hype.
- Ephemeral + loud; the community-vibe layer that makes expressing sentiment *fun*
  (the survey's actual ask).

### Relationship (owner decision pending — lean: two layers)
- **Ratings** = the quiet, persistent per-player signal that drives the GM brain + the
  favorite/villain boards.
- **Posts** = the loud social layer that *also* nudges (an angry post ticks that
  target's sentiment down, a hype post up), and is the **main channel for GM feeling**
  and overall **team mood**.
- Alternative (simpler, less clean): posting *is* the sentiment, no separate rating.

### How sentiment reaches the sim
`decisionScore = brainValue(player) + fanSentiment(player) × GM.fanTrust`, and
GM-fire/leave risk rises with aggregate **negative GM sentiment**. The tilt tips close
calls; it never forces a clearly-bad move.

### Open second consumer: team mood → morale/funding/attendance?
Aggregate fan sentiment could also feed **team morale / funding / attendance** (a
beloved team plays looser; a toxic fanbase weighs on the room). Natural, optional —
decide whether to wire it.

### Economy
- Posting + rating are **free** (Rocket-League-free vibe) → this **removes the GM-vote
  Floobit sink** entirely (see Part E). Size the hole and decide on a backfill.
- Rate-limit posts (spammy-fun in the feed, but bounded); ratings are net-one-per-target.

---

## Part E — Removal checklist (delete with the binding votes)

- **Vote types** (`constants.py:1574` `GM_VOTE_TYPES`): fire_coach, cut_player,
  resign_player, hire_coach, sign_fa — and their resolution in `gmManager.py`
  (`resolveFireCoachVotes` :133, `resolveHireCoachVotes` :185, `resolveResignVotes`
  :328, `resolveCutVotes` :391, `resolveSignFaVotes` :474).
- **Ballots:** FA ranked ballot (`GmFaBallot`), rookie ballot (`draft_rookie` GmVotes),
  **position fill-priority** (`_aggregatePositionPriorities`, `gmManager.py:450`).
- **Thresholds + snapshot:** `calculateThreshold` (`gmManager.py:35`), `GM_PASS_FRACTION`,
  `front_office_fan_snapshot` + `_snapshotActiveFanCounts` (`seasonManager.py:6676`).
  (Note: the just-shipped facilities `activeFanCount` reuses this same "active this
  season" definition — keep that query, drop only the vote-threshold usage.)
- **API (~11 endpoints, `api/main.py`):** `/api/gm/vote` (11488), `/vote/undo` (11649),
  `/team/{id}/summary` (11724), `/team/{id}/eligible` (11787), `/fa-scouting` (11930),
  `/fa-ballot` (12365), `/rookies/upcoming` (12466), `/rookie-ballot` (12531/12627),
  `/gm/votes` (12704), `/gm/results` (12737). (Awards MVP/HoF ballots are a **separate**
  system — leave them.)
- **WebSocket events:** `gm_vote_resolved`, `gm_fa_window_open/close`,
  `gm_fa_directives` (`event_models.py` `GmEvent` :682).
- **Achievements** (retire or repurpose): **Tribune** (cast ≥6 votes,
  `api/main.py:11585`) and **Scorched Earth / mutineer** (fire coach + gut roster,
  `seasonManager.py:6865`).
- **Coach:** `overallRating` (`floosball_coach.py:55`) + any star display.

---

## Part F — Remove the rookie draft; players enter via periodic FA injection

**Owner decision, 2026-07-27.** This settles the collision the tracker flagged
between the autonomous FO and the "remove prospect draft" future direction. The
draft goes; new players enter the **free-agent pool** periodically, sized to
REPLACE retirees rather than to grow the league.

Owner's requirements, verbatim in intent:
1. No rookie draft at all.
2. Add new players only every so often, so the player pool doesn't inflate.
3. When players retire, add replacements.
4. Guarantee every position has enough active players for every team to field a
   full roster.

### Why this is cheaper than it looks
Requirement 4 is **already built**: `playerManager.ensurePositionSupply`
(`:3799`) guarantees enough draftable players AT EACH POSITION to fill every
roster slot (numTeams x slots, WR x2, plus `ROSTER_SUPPLY_BUFFER_PER_POSITION`),
generating only the per-position deficit into the FA pool. It is idempotent and
already runs twice (week `GM_ACTIVE_WEEK` and again just before the FA draft).

Today it is a **safety floor** that stays dormant. Under this change it becomes
the **primary intake**, which is a promotion of existing, validated code rather
than new machinery. Note it currently EXCLUDES `is_prospect` players from supply
counts — once prospects are gone that exclusion simply stops mattering.

### What survives untouched (verified against code, not assumed)
- **The whole card surface.** The Rookie Pack's pool filter and the rookie card
  classification key off `seasonsPlayed == 0` (`cardManager.py:430`), never off
  the draft. `cardProjection` / `fantasyTracker` use `seasonsPlayed <= 1` or the
  service-name check. New FA entrants have `seasonsPlayed == 0`, so the Rookie
  Pack keeps a valid pool and rookie effects keep firing.
- **The autonomous FO brain (step 1, already built).** Its aggression dial reads
  the worst-first **FA** order, not the rookie draft — deliberately, for exactly
  this reason. No rework.
- **Worst-first parity.** The FA draft is already the worst-first acquisition
  step; removing the rookie draft leaves it as the single acquisition path.
- **Rookie ballots**, which Part E deletes anyway. No incremental cost.

### What has to change
- **Offseason flow** — drop the `rookie_draft` phase and its completion gate.
  New ordering: `GM turnover -> best-first assessment sweep (cut/re-sign) ->
  worst-first FA draft -> training`. (`_offseasonFlowPhase`, `run_api.py`,
  `timingManager`, `constants` all name `rookie_draft`.)
- **Prospect pipeline retires** — `is_prospect`, `drafting_team_id`, prospect
  promotion, `rookieDraftPickGenerator`. Entrants are ordinary free agents from
  birth, owned by nobody.
- **`GET /api/rookies/upcoming`** loses its subject (a rookie class locked to
  drafting teams). Either retire it or repoint it at "recent entrants".
- **Injection cadence** — a new periodic step. Recommended trigger: run the
  supply floor at a fixed cadence and let RETIREMENT COUNT set the volume, so
  the pool is replacement-sized by construction and can't inflate.

### Consequences worth deciding before building
1. **Three-tier prospect progression — REMOVED (owner, 2026-07-27).** An earlier
   draft of this plan recommended keeping it. **The owner's counter-argument is
   correct and is confirmed in code:** debut-below-trueSkill only works if the
   player is on a roster, because development is coach-driven. Entrants now
   start as free agents by definition, so an underdeveloped entrant nobody signs
   never grows in.

   It is in fact worse than "doesn't develop". Training bias is
   `devBias = round((coachDevRating - 60) / 10) + facilityBonus`
   (`player_development.apply_offseason_training`). Rostered players are keyed to
   their coach's `playerDevelopment` (60-100; neutral 80 -> **+2**). Free agents
   are absent from that map and fall to the default `devRating = 50` ->
   **devBias = -1**, i.e. WORSE than the worst possible coach (60 -> 0). An
   unsigned player actively decays away from their true skill. Debut-low would
   be a trap with no exit.

   **So:** no prospects, no `trueSkill` tier. New players enter the FA pool at
   their real current ability.

   ⚠️ **Related latent issue this change promotes to a real one.** Under Part F
   *every* new player starts unrostered, so every entrant takes the -1 FA decay
   until signed, entry discount or not. The FA pool is currently a decay
   chamber. Recommend giving unrostered players a NEUTRAL bias (treat "no coach"
   as 60 -> devBias 0, not 50 -> -1) so sitting in the pool is stagnation rather
   than punishment. Cheap fix, and it matters much more once the draft is gone.
2. **`scouting` loses its gameday role** (blurred rookie-potential visibility)
   but is NOT orphaned — under the autonomous FO it becomes the GM's central
   attribute (roster valuation accuracy). This is a repoint, not a loss, and it
   arguably sharpens the attribute's identity.
3. **Talent drift — measured, not assumed (16-season prod-copy sim).** An
   earlier draft of this section warned the league would slowly COOL under
   replacement-rate injection. **That was wrong**, and the data says the
   opposite:
   - Individual players RISE: avg first-to-last rating delta **+1.59** across
     555 players with 3+ seasons (340 rose, 150 fell). Development comfortably
     outruns the debut-below-trueSkill entry discount, which is a per-player
     TRANSIENT, not a league-level drift — it washes out in steady state.
   - Entering cohorts are NOT weakening: first-season ratings sit ~69-76 across
     S3-S15 with no trend (noise on n=24/season).
   - **On-field (rostered) talent RISES**: 77.4 (S2) -> 83.6 (S9) -> 78.6 (S11,
     a step consistent with the parity package's one-time percentile re-map)
     -> 80.6 (S16). Net **+3.2**.

   The league-WIDE average does fall (75.9 -> 75.5), but that is a composition
   artifact of pool inflation, not talent decay: the pool grew 243 -> 603 while
   entrants arrive below the mean. At S16 the sim holds **94 free agents**
   behind 144 rostered players averaging 80.6. (An earlier revision said 417 —
   that count wrongly included retired players; see the corrected table below.)

   **So this change fixes the observed decline rather than causing it** — the
   inflation driving it is precisely what replacement-rate injection removes.
   The genuine long-run risk points the OTHER way: on-field talent creeps
   upward, which is the skill creep the parity package exists to fight. A
   fixed-distribution intake sized to retirements acts as a brake on that creep.
   Still worth watching in `simcheck`, but watch for WARMING, not cooling.
4. **Pool buffer under retention limits.** Re-sign-once forces circulation, so
   the FA pool must stay deep enough for every team to fill 6 slots each
   offseason. `ROSTER_SUPPLY_BUFFER_PER_POSITION` is the knob; validate it holds
   across a multi-season sim now that the draft isn't also feeding the pool.
5. **The "draft class" as a fan-facing beat disappears.** The rookie draft is a
   visible offseason event users follow. Injection is invisible by comparison —
   worth considering whether entrants should arrive as an announced "intake"
   class to keep the beat.

### Part F — LIVE, wave 1 excised (2026-07-29)
`ROOKIE_DRAFT_ENABLED = False`. No rookie class is generated, the draft has
nothing to draft, and new players enter only as the position-supply deficit
fill. Existing prospects drain through and are never replaced.

**Verified** over a 5-season fresh sim with the GM brain also live: 0 errors,
**active pool pinned at exactly 159** (144 rostered + the 15-player buffer),
prospects down to **0**, every roster full, top-ups sized to the retirement wave
(+15 in the season the pool first needed it, nothing when it didn't).

**Wave 1 — DONE.** Removed: the `rookie_draft` offseason phase,
`rookieDraftPickGenerator`, `_generateRookieClass`, the fan rookie ballot and
its tally, `GET /api/rookies/upcoming`, `scoutRookie`, `RookiesSection.tsx`,
and the panel's five `rookie_draft_*` handlers. The offseason now runs
post_bowl -> frontoffice -> pre_fa -> fa_draft -> training.

**Wave 2 — deferred, and it must stay deferred.** The prospect half is NOT
dead code: promotion is what drains the prospects a deployed DB still owns.
Delete it now and every team loses its prospects on deploy day. It comes out
once prod prospects reach zero. The COLUMNS stay permanently (owner call) —
dropping them means a SQLite table rebuild on a live DB for zero gain.

⚠️ **Two stranding bugs the removal exposed** (both fixed, both the same shape:
a flag whose ONLY clearing path was the code being deleted):
- **Prospect promotion had no working path.** `_tryPromoteProspect` was never
  called by anything; the live path, `_promoteFanVotedProspect`, read
  `_gmFaDirectives` — populated only by the `sign_fa` ballot that step 7
  deleted. Prospects would have sat out their window and washed out to free
  agency, never promoted. Promotion now runs through the GM brain
  (`_promoteProspectsAutonomously`, `FO_PROSPECT_PROMOTE_EDGE`).
- **Upcoming rookies would have been stranded.** They are held out of BOTH
  rosters and the FA pool, and the draft was the only thing that cleared the
  flag. The dev DB's 24 would have become permanently inert rows. They are now
  released into free agency on load — what the draft did with the undrafted.

⚠️ **A third bug was in the removal itself:** dropping the phase also dropped
its `waitUntilNoonEt()` hold, which was what pushed the offseason to the day
AFTER the Floos Bowl. Free agency would have fired at the next top of the hour
(+0.9h, overnight) instead of draft day (+20.9h). Free agency now inherits the
slot (`_computeDraftDayTarget`, delay renamed `rookie_draft_wait` ->
`draft_day_wait`). Only reproducible in SCHEDULED mode — every `fast` sim
passed clean, which is why it survived the first round of validation.

### Starting condition: there is already a large FA backlog
The 16-season sim ends with **94 free agents** for 144 roster spots — roughly
0.65 per starting job (corrected; an earlier revision said 417 by counting
retirees). Injection is therefore NOT the first problem
to solve: the pool is already deep enough to field every roster many times over,
and `ensurePositionSupply` (a floor, only firing on a genuine per-position
shortfall) would stay dormant for many seasons.

Practical implication: at switch-on the intake should be **throttled to zero or
near-zero and allowed to drain**, with retirement-replacement injection only
becoming load-bearing once the backlog approaches the supply floor. Sizing the
intake to retirements from day one would preserve the bloat rather than fix it.
Worth confirming the backlog on the real prod DB before picking a cadence — the
figure above is from a dev sim.

### Intake mechanism — SETTLED 2026-07-27 (owner): a trickle
New players **trickle in**; no lump intake class. The pool must not inflate.

**This needs no new intake system.** The trickle IS
`playerManager.ensurePositionSupply` run once per offseason with a tuned buffer:

```
per position: generate max(0, targetDraftableSupply - currentDraftableSupply)
targetDraftableSupply = numTeams x slotsAtPosition + ROSTER_SUPPLY_BUFFER_PER_POSITION
```

That single rule delivers every requirement at once, which is why it's the whole
design rather than a component of it:

- **Never inflates.** Generation is a deficit fill. When supply is at or above
  target, it generates NOTHING — by construction, not by tuning.
- **Drains any backlog automatically.** With the pool above target the rule
  stays dormant while retirement pulls it down. No special "throttle at launch" mode is needed; the
  deficit fill is already zero. (This supersedes the throttling note above —
  the mechanism throttles itself.)
- **Replaces retirees.** Once the pool reaches target, each season's retirements
  open exactly that much deficit, and exactly that much is generated. Intake
  self-sizes to the retirement rate with no explicit coupling.
- **Guarantees full rosters** at each position — its original purpose, unchanged.
- **Is already written, validated, and idempotent.** The only changes are
  raising the buffer to set the steady-state pool depth, and dropping the
  `is_prospect` exclusion once prospects are gone.

`ROSTER_SUPPLY_BUFFER_PER_POSITION` therefore becomes **the** dial governing
league-wide pool depth — worth calling out, since it's currently a minor
safety-margin constant and will silently become load-bearing.

**Accepted tradeoff:** a trickle gives up the draft class as a fan-facing
offseason beat (see consequence 5). Entrants simply appear in the FA pool.
Nothing stops a "new arrivals" surface later if the beat is missed.

### Measured starting state (16-season dev sim) — CORRECTED
⚠️ An earlier revision of this section reported a **+402** surplus and **417**
free agents. Those figures were WRONG: the query counted retired players, which
are RETAINED as rows in `players` (there is no `is_retired` column; retirees are
marked `service_time = 'Retired'`). Of 603 rows, **323 are retired**. Any pool
query MUST exclude them.

Corrected, at `ROSTER_SUPPLY_BUFFER_PER_POSITION = 3`:

| Pos | Target | Active draftable | Surplus |
|-----|--------|------------------|---------|
| QB  | 27     | 42               | +15     |
| RB  | 27     | 41               | +14     |
| WR  | 51     | 79               | +28     |
| TE  | 27     | 37               | +10     |
| K   | 27     | 39               | +12     |
| **Total** | **159** | **238**     | **+79** |

Active pool = 280 (144 rostered + 42 prospects + 94 free agents) — not the ~560
implied before. So the backlog is real but MODEST: ~94 free agents for 144
starting jobs, and once prospects are retired (Part F) the surplus over target is
~79. A passive drain is entirely reasonable at that size; the earlier worry about
decades-long dormancy was an artifact of the bad count.

**SETTLED (owner):** keep the target near the roster minimum, drain passively,
no cull. That holds — and at +79 rather than +402 it is comfortably achievable.

### Validation: the trickle mechanic WORKS (fresh-DB sims)
Two fresh `--fresh --timing=fast` runs with `NO_ROOKIE_DRAFT=1`, one with the GM
brain on and one without, both instrumented (`SUPPLY_DEBUG=1`):

- **Active pool pinned at exactly 159 every season** through 13 seasons — the
  target (144 + 3x5). Never drifted up or down.
- Per-position supply lands exactly on demand each season
  (`QB=27/27, RB=27/27, WR=51/51, TE=27/27, K=27/27`).
- Top-ups vary with the retirement wave (+1 to +16/season) and are exactly
  absorbed; the deficit fill replaces retirees and nothing more.
- **All 24 rosters full, zero errors**, prospects 0, upcoming rookies 0.
- Enabling the GM brain changed nothing about pool size — confirmed by running
  the same sim with and without it.

(An interim report of the pool "inflating to 303" was the same retiree
miscount — 303 rows minus 144 retired = 159 active. The mechanic was correct the
whole time.)

**Measurement note for anyone re-checking this:** always filter
`service_time != 'Retired'`. Counting raw `players` rows silently conflates the
cumulative all-time roster with the live pool, and the error grows every season.

### Coupling to watch: pool depth IS the GM brain's market
A near-minimum pool has a direct effect on the already-built re-sign decider
(and on cut-for-upgrade when it lands). `bestReplacementValue` measures an
incumbent against the free agent still available at the team's FA slot; at
target 159 there are only ~15 spare players across 5 positions, so after the
`FO_FA_CONTENTION` depth discount most teams will see **no available
replacement at all** — which by design returns 0 and means "keep him".

Predicted equilibrium behaviour: re-signs approach the cap for everyone, cuts
approach zero, and the comparative market test goes quiet because there is no
market. Rosters still fill (the supply floor guarantees it), but front-office
decisions become largely forced rather than chosen.

This is not an argument against the thin pool — it is the honest tradeoff to
measure. `ROSTER_SUPPLY_BUFFER_PER_POSITION` trades **pool bloat** against
**front-office meaningfulness**, and those are the two things to read off a
multi-season `simcheck` when tuning it: pool size on one side, re-sign/cut
churn on the other. Worth re-checking once the pool actually reaches target,
since today's +79 surplus masks the effect until the pool reaches target.

### Open
- ~~Steady-state pool depth~~ — settled: near-minimum, buffer stays small.
  Revisit only if the coupling above makes the front office too inert.
- ~~Drain strategy~~ — settled: passive drain, no cutover cull.
- Retire vs repoint `/api/rookies/upcoming`.
- Instrument the retirement rate (currently unmeasurable — retirees are deleted,
  not flagged) so the drain can actually be observed rather than assumed.

## Build sequencing (proposed)

1. **GM brain** — build autonomous re-sign + cut valuation (attribute + scouting-gated),
   extend FA/rookie; add `fanTrust`; wire per-team behavior. Validate with `simcheck`
   (rosters stay full, sensible churn) BEFORE removing votes.
2. **Coach generation** — specialist spread + rare elite/bust tail; drop `overallRating`;
   add derived profile tags.
3. **GM turnover** — fired (sentiment+record) + leave (sentiment-hostile) triggers;
   keep/refine retire; replacement gamble. Tune churn rate.
4. **Sentiment data** — 1–5 ratings + aggregation; favorite/villain boards.
5. **Social feed** — pre-made post catalog + team-page feed; post→sentiment wiring.
6. **Wire sentiment → brain** (`× fanTrust`) + GM-fire/leave risk.
7. **Remove** the binding-vote machinery (Part E).
8. **Economy** — size the removed sink; decide backfill.
9. **Frontend** — team page → social feed + rating UI + GM scouting-report profile;
   remove all vote/ballot UI.
10. **(Optional)** team-mood → morale/funding second consumer.

## Decisions (resolved in refinement)

- **Sentiment vs attention (Q7)** — **separate axes, shared inputs.** Attention =
  *magnitude* (unchanged, drives awakening); sentiment = *valence* (new, drives the GM
  brain). A hated player still draws attention, so don't overload it. Emergent combos:
  high attention + split sentiment = *polarizing*; high attention + disapproval =
  *lightning rod*.
- **Ratings vs posts (Q1)** — **two layers split by tempo.** Ratings (1–5) = standing
  stance (slow, persistent, one per fan) → drives roster valuation + favorite/villain
  boards. Posts = emotional pulse (fast, decaying, spammy-fun) → drives the feed + GM
  fire/leave heat + team mood.
- **`fanTrust` (Q3)** — **new independent coach attribute** (don't conflate with
  `attitude`, the locker-room axis).
- **Team mood (Q2)** — **phase it, and funding stays PURELY fan-contributed** (owner
  confirmed — sentiment never touches the budget). Phase 1: sentiment → GM decisions +
  fire/leave heat only. Phase 2 (optional): team mood → atmosphere / attendance + a small
  morale nudge only — NOT funding dollars.
- **Economy backfill (Q6)** — **let the sink shrink** (owner confirmed). No replacement
  sink; core rating/posting is free.
- **Position value (Part A)** — **universal `POSITION_VALUE` table** first; optional
  small per-GM biases later.
- **Churn cap (Part A)** — **none initially**; let it self-limit, add a soft cap only if
  sim shows thrash.

## Tuning targets (nail in `simcheck`, not on paper)

- **Coach generation / elite-bust tail (Q4)** — start `attr = clip(80 + s + N(0, ~9))`
  with a small shared shift `s ~ N(0, ~3.5)`. σ_shared ≪ σ_indep → mostly specialists
  near-average-overall, rare all-around elites/busts (~3–5% each tail). Tune σ_shared.
- **Churn rate (Q5)** — target ~3–5 GM changes league-wide per season (~12–20% of 24
  teams) across fire + retire + leave. Tune fire/leave thresholds against the retire
  curve.
- **Upgrade threshold (Part A)** — base "how much better" to justify a cut, and **how
  hard draft position swings it** (aggressive early ↔ conservative late).
- **Scouting → arc visibility** — how much a high vs low `scouting` GM sees of the true
  `current/trueSkill/potential` trajectory (perfect foresight at the top end would be too
  strong; poor scouts should be genuinely wrong, not just noisy).

**The model in one line:** `perceivedValue(player)` = a **scouting-gated, arc-aware,
forward-looking** projection (via `current<trueSkill<potential` + age curve) `×
POSITION_VALUE`; every re-sign/cut compares `perceivedValue(incumbent)` vs
`perceivedValue(best available)`, with the **upgrade threshold scaled by draft position**
and the result tilted by **fan sentiment × `fanTrust`**.

## Build status

### Step 1 — GM brain: valuation + re-sign ✅ (sim-validated)
`managers/frontOfficeBrain.py` (new). Everything is gated behind
`AUTONOMOUS_FO_ENABLED` (default **False**) so the existing fan-vote path still
decides until the binding votes are removed in Part E; `AUTONOMOUS_FO=1` in the
env turns the brain on for a sim without flipping the constant.

- **`perceivedValue(player, coach)`** — the model in one line from above.
  `classifyArc` reads the three-tier prospect model for the rise and
  `computeRetirementOdds` for the fall (one definition of "old" in the
  codebase), decline outranking an unmet trueSkill. `trueForwardRating` is
  ground truth; `scouting` then gates how much of it the GM SEES, with the
  unseen remainder becoming real error, so a poor scout is wrong in a direction
  rather than merely noisy. `playerDevelopment` credits part of the ceiling gap
  (`FO_CEILING_CREDIT`). Position weighting via `POSITION_VALUE`.
- **`fanTrust`** — new coach attribute (`floosball_coach.py`, `coaches.fan_trust`
  + inline migration + one-shot backfill gated on the
  `coach_fan_trust_backfilled_v1` app_setting). Drawn INDEPENDENTLY of the
  coach quality seed. Currently inert: `sentimentTilt()` is a documented no-op
  seam until the Part D ratings layer exists.
- **Re-sign decider** — `_applyRetentionLimits` (`seasonManager.py`) keeps its
  machinery and guardrails; only the DECIDER swaps. `RESIGN_ONCE_LIMIT` /
  `RESIGN_LIMIT_PER_OFFSEASON` are untouched, per the hard constraints above.
- **Tests:** `test_front_office_brain.py` (14 checks).

### The FA-contention correction (found by simcheck, not on paper)
The first implementation benchmarked each incumbent against the single
league-best free agent at his position. A full sim showed the consequence:
**0 re-signs across all 24 teams**. All 24 correctly concluded their starter was
replaceable by the same top free agent — whom only one of them could sign — so
the entire league shed its incumbents.

Fix: a team benchmarks against the free agent expected to survive to ITS slot in
the worst-first FA order — `effectiveDepth = floor(faOrderIndex x
FO_FA_CONTENTION)` (0.30, since not every team ahead needs the same position).
This is the plan's **aggression dial** landing in its natural home: an early
picker shops the top of the board and churns boldly, a late picker sees thin
leftovers and holds. A position picked clean before a team's turn yields no
replacement, which correctly means "keep him".

Note this uses the **FA** order, not the rookie draft, so it does NOT depend on
the prospect draft surviving the "periodic FA injection" question.

**Validation** (fresh fast sim, 2.5 seasons, `AUTONOMOUS_FO=1`): no
errors/tracebacks; seasons 1-3 completed with full playoffs (4/4/2/1 games) and
every offseason gate; rosters **144/144, zero teams off 6 slots**; scoring flat
vs baseline (season 1 predates any brain decision at 27.3 combined, so the level
is pre-existing).

**Open tuning:** in season 2 every team spent both re-sign slots, so the cap —
not the market test — is the binding constraint. The comparative test currently
only decides WHICH two, never WHETHER to spend a slot. Raising
`FO_RESIGN_SURPLUS_MARGIN` would let a team decline to use one; owner call.

### Step 2 — Coach specialist profiles ✅ (built + validated)
Built BEFORE the rest of Part A, deliberately: cut-for-upgrade against uniform
coaches and a near-minimum pool would produce almost no cuts, and a simcheck
couldn't tell correct-and-quiet from broken-and-quiet. Specialist spread makes
the brain's behaviour observable first.

- **Generation** (`floosball_coach.generateAttributes`): each attribute now
  `clip(center + shared + N(0, COACH_ATTR_INDEP_SIGMA=9), 60, 100)` with one
  small per-coach `shared ~ N(0, COACH_ATTR_SHARED_SIGMA=4.5)`. `seed` still
  sets the center, so the hire slate keeps its premium/mid/budget tiers
  (`COACH_CANDIDATE_SEEDS` 90/80/72) with each candidate now a specialist at
  that level.
- **Measured over 4k draws:** within-coach attribute spread **24.4 pts** vs
  overall SD **5.5** — the aggregate is noise while the profile is sharp.
  All-around elites **3.6%**, busts **5.8%** (target 3-5% each). Offensive vs
  defensive mind correlation **r = 0.20** (was ~1.0 by construction).
  σ_shared was swept: 3.5 gave only a 2.1% elite tail, 5.5+ starts making
  coaches uniformly good/bad again.
- **`overallRating` deprecated, not deleted.** Removed from all display; kept as
  a property purely to populate the legacy `coaches.overall_rating` column.
  ⚠️ The `gmManager` no-votes hire fallback still ranks on it **correctly** —
  candidates are seeded, so it tracks the intended tier there even though it is
  meaningless for the seedless league population. Left in place with a comment;
  it dies with the votes in Part E. (An initial attempt to "fix" it to slot
  order was wrong and was reverted.)
- **Scouting report** replaces the star: `buildCoachProfile` derives a specialty
  (top attribute ≥ `COACH_PROFILE_SPECIALTY_MIN` 88), a flaw (bottom ≤
  `COACH_PROFILE_FLAW_MAX` 70), and a fan-trust label (Populist / Old School).
  An unremarkable coach reads as **Generalist** rather than being handed a
  dramatic label. `profileFromDbRow` gives raw `coaches` rows an identical
  report so the hire slate can't drift from the live view.
- **API**: `profile` added to the coach serializer, the team-detail coach block,
  and the coach-candidate payload.
- **Frontend**: new `CoachProfile.tsx` (`CoachProfileTags`); coach stars
  replaced in `CoachHoverCard`, `HireCoachCard`, `FireCoachCard`,
  `FrontOfficePage`, `TeamPage`. The hover card's misleading "Overall" bar is
  gone, and it now surfaces **Attitude** and **Fan Trust**, the two GM-critical
  attributes it previously omitted. Player star ratings are untouched.
- **NO RATING NUMBERS SURFACED** (owner, 2026-07-27). A GM is a character, not
  a stat line. The API sends `profile` and nothing else — every raw coach
  attribute value and `overallRating` was removed from the coach serializer,
  the team-detail block, and the candidate payload. `profile` carries the
  headline archetype tags plus per-attribute **qualitative bands**
  (`Elite / Sharp / Capable / Limited`, `floosball_coach.attributeBand`),
  deliberately reusing the vocabulary `PlayInsightsPanel.coachMindLabel`
  already used for coaches so the same GM can't read 'Elite' in one place and
  'Sharp' in another. Frontend numeric bars replaced everywhere:
  `CoachHoverCard` (now band rows), `TeamHoverCard`, `TeamPage` and
  `FrontOfficePage` attribute grids, plus the `GmCoachInfo` type.
  ⚠️ Known remaining spot: the play-insights WS payload still ships raw
  `coachOffMind` / `coachDefMind` numbers, though the panel has always
  displayed them as labels only. Band them server-side if the payload matters.
- **Tests**: `test_coach_profiles.py` (11 checks) covering the specialist
  property, the rare tails, attribute independence, seed tiering, fanTrust
  independence, label correctness, the Generalist fallback, and DB-row parity.

### Step 3 — GM turnover ✅ (built + sim-validated)
`managers/gmTurnover.py` (new), resolved inside the existing offseason coach
step (`teamManager.handleCoachRetirement`, now handling all three exits).

- **Retire** takes precedence (existing tenure curve, untouched) — a GM going
  out on their own terms isn't also fired.
- **Fired**: pressure comes ONLY from falling below `GM_FIRE_BASELINE_WINPCT`
  (0.45), so a .500-or-better GM is never rolled on — competence is real job
  security. Two things buy rope: **tenure grace** (a first-season GM inherited
  the roster) and **goodwill** from coach `attitude`. Goodwill is deliberately
  capped BELOW a typical fire chance — at the initial 0.18 it could zero out the
  roll entirely, making a well-liked GM unfireable rather than harder to fire.
  This is the plan's "threshold varies by GM", sourced from a visible attribute
  instead of a hidden per-coach roll.
- **Leave**: record-INDEPENDENT by design, so a hostile fanbase can drive out a
  GM who is winning.
- **Replacement gamble**: reuses `generateCoach`, so post-Part-B the new GM is
  better-or-worse per dimension rather than a scalar up/down.
- **Sentiment is a neutral no-op** until Part D — every entry point takes a
  `sentiment` argument defaulting to 0, mirroring `sentimentTilt`. A test
  asserts neutral changes nothing AND that the seam already responds, so Part D
  is a wiring job rather than a restructure.

**Tuning.** `GM_FIRE_SENSITIVITY` swept over 2.5k simulated seasons against a
realistic 24-team record spread; the initial 1.30 gave only 1.47 exits/season.
Settled at 2.60 with goodwill 0.14 and baseline 0.45. Rejected baseline 0.50
(3.95/season) because it puts half the league on the hot seat by construction —
0.45 keeps a roughly .500 GM genuinely safe.

**Live sim, 10 seasons:** 3.60 changes/season (2.70 fired, 0.90 stepped down),
squarely in the 3-5 target, zero errors, every team always staffed.

⚠️ **Emergent: retirement is now rare.** 0 retirements across those 10 seasons —
firing churns GMs before they reach the 10-season tenure curve (max tenure
observed: 12). Not a defect, and arguably good flavour (surviving to retirement
becomes the mark of a successful career), but the retire path is now close to
vestigial. Revisit if GM longevity should mean more.

**Tests**: `test_gm_turnover.py` (11 checks).

### Part A completed — cut-for-upgrade + the assessment sweep ✅
The other half of step 1, built once Part B made GMs actually differ (against
uniform coaches a simcheck couldn't tell correct-and-quiet from broken-and-quiet).

- **Cut-for-upgrade** (`brain.rankCutCandidates` / `chooseCuts`): only players
  still UNDER CONTRACT are considered — a walk-year player who loses the re-sign
  comparison already leaves, and a retiree vacates, so cutting either is
  redundant churn. Same incumbent-vs-realistic-replacement comparison as
  re-sign, with a larger margin (`FO_CUT_UPGRADE_MARGIN` 6.0): letting someone
  walk is free, cutting someone under contract opens a hole the worst-first
  draft may not fill.
- **DEVIATION from the plan, deliberate.** The plan scales the upgrade threshold
  by draft position and calls that the aggression dial. That dial is ALREADY
  expressed by `FO_FA_CONTENTION` — an early picker is measured against the top
  of the board, a late picker against thin leftovers. Scaling the threshold too
  would double-count it and, with a near-minimum pool, suppress cuts almost
  entirely. The threshold is flat; the dial lives in one place. A test asserts
  an early picker cuts where a late picker holds, same roster and same pool.
- **Assessment sweep** (`seasonManager._applyRetentionLimits`): with the brain
  driving, teams are evaluated **best-first** — Floos Bowl champion, then win%
  descending — and each team's cuts drop into the shared FA pool IMMEDIATELY, so
  later teams assess the fuller market. Verified in-sim: the S2 sweep led with
  the Caddies (Floos Bowl winners, 23-5) ahead of Rhyme (27-1), which is exactly
  the specified champion-first ordering. Decision order only — acquisition stays
  the worst-first FA draft, so there's no anti-parity effect.

**Churn cap added — the plan's contingency fired.** Cuts were left uncapped on
the expectation that churn self-limits. A fresh-league sim produced **70 cuts in
one offseason** (half the league), because a brand-new FA pool is fat and every
roster has an upgrade available. `FO_CUT_MAX_PER_TEAM` (2, mirroring the
re-sign cap) bounds it.

**Live sim after tuning:** 41 cuts in season 1 (the fresh-league transient,
capped), then **0, 4, 2, 4** — a couple of decisive moves league-wide per year.
Rosters 144/144 every season, zero errors.

Worth noting against the earlier worry that a near-minimum pool would make cuts
never fire: in steady state they fire 2-4 times a season, which is purposeful
churn rather than silence. **Tests**: 21 checks in `test_front_office_brain.py`.

### Free-agent development penalty ✅ (fixed)
Flagged under Part F consequence 1 and now fixed. Unrostered players fell to a
default `coachDevRating` of 50 => `devBias -1`, WORSE than the worst possible
coach (60 => 0), so an unsigned player actively decayed. Latent while most
players were rostered; a real problem under Part F where every new player enters
the FA pool.

Unrostered players now train off their own mental makeup —
`PlayerDevelopment.selfDevelopmentBias`, averaging `discipline / focus /
resilience / selfBelief` onto the same scale coaches use, damped by
`FA_SELF_DEV_SCALE` (0.7) and floored at 0. `coachDevRating=None` is now the
signal for "no staff" throughout (the old default of 50 is gone).

Result: unrostered bias spans **0 to +3** (league-average makeup => **+1**),
never negative, and never beats an equivalently-rated coach. Sitting in the pool
is stagnation, never punishment. **Tests**: `test_fa_self_development.py` (6).

### Step 4 + the player half of step 6 — fan sentiment ✅ (built)
`PlayerSentimentRating` model + inline migration, `SentimentRepository`,
API, and the brain wiring. `sentimentTilt` is no longer a no-op.

- **Storage**: fans rate players **1-5**, net ONE per fan per player (re-rating
  UPDATES the row, never stacks — anti-brigade). Persistent across seasons on
  purpose: a standing stance, not a season-scoped ballot, which is what
  separates it from `AwardVote`. Free to cast.
- **Rater floor** (`SENTIMENT_MIN_RATERS` 3): below it a player reads NEUTRAL
  and the aggregate is withheld from the API — one loud fan cannot move a roster
  decision, and there's no small number to brigade.
- **Normalization**: 1-5 average -> -1.0..+1.0 with 3 as neutral.
- **The tilt**: `sentiment x fanTrust x SENTIMENT_MAX_VALUE_SWING` (5.0 value
  points). The two extremes are the design's point — `fanTrust` 60 yields
  **exactly 0** (this GM ignores the fans entirely), 100 yields the full swing
  (a populist). Deliberately small so sentiment TIPS CLOSE CALLS: a test asserts
  a maximally-hated star still out-values a beloved scrub, so fans can't wreck a
  roster.
- **Bulk-loaded once per sweep** (`getSentimentMap`), not per player — the sweep
  values every roster on every team, so per-player queries would be an N+1 in
  the offseason hot path.
- **API**: `POST/GET/DELETE /api/players/{id}/rating`, plus
  `GET /api/sentiment/boards` (Fan Favorites / Most Hated, rater-gated).

**Validated** in a live sim (0 errors, rosters 144/144, sweeps unaffected) AND
end-to-end against the real migrated schema: three fans adoring a player yields
+1.00 sentiment => +5.00 value points for a populist GM and **+0.00 for an
independent one**, while a single-rater player stays gated at neutral.

A league where nobody rates anything behaves exactly as before — a test pins
that, so this is safe to ship dark.

### Step 5 + the GM half of step 6 — social feed ✅ (backend built)
`TeamFeedPost` model + inline migration, `FeedRepository`, API, and wiring into
BOTH the brain and GM turnover. Steps 4-6 are now complete on the backend.

- **Pre-made catalog only** (`FEED_POST_CATALOG`, 17 posts across player /
  GM / team targets). `post_key` indexes the catalog, so text is never
  user-supplied and there is **no moderation surface at all** — a test tries to
  post free text, including SQL, and is rejected. `{name}` renders the target.
- **Ephemeral**: posts age out at `FEED_POST_TTL_HOURS` (72) and their influence
  decays LINEARLY to zero across that window — legible ("recent posts matter,
  old ones fade") rather than an exponential long tail. `purgeExpired` keeps the
  table bounded.
- **Saturating pulse**: a 500-post pile-on lands at exactly -1.0 rather than
  running away, so one brigaded target can't dominate the model.
- **Rate limited** per fan per window, not per team, so spam is bounded without
  blocking other fans.
- **Ratings LEAD, posts NUDGE** (`combineSentiment`): the two signals are split
  by tempo per the plan's Q1. A considered star rating outweighs an emotional
  spike (`FEED_PULSE_SENTIMENT_WEIGHT` 0.35), so a pile-on can't override the
  deliberate signal. `buildSentimentMap` merges them in ONE place so a caller
  can't read half the signal by accident.
- **GM heat now reaches turnover.** Per the plan, GM feeling comes from POSTS,
  not the player star ratings. `gmPulseMap` is loaded once per offseason and
  passed into `evaluateExit`. Measured:

  | Fanbase | Winning GM (20-8) | Losing GM (8-20) |
  |---|---|---|
  | quiet     | fire 0.0%, leave 3.0%  | fire 35.7% |
  | restless  | fire 5.5%, leave 20.5% | — |
  | hostile   | fire 18.0%, leave 38.0% | fire 60.7% |

  So a hostile fanbase **can drive out a GM who is winning** — mostly by making
  them walk rather than by getting them fired, which is exactly the plan's
  "poison the well" path. Supportive fans deliberately do NOT rescue a bad
  record (a losing GM is 35.7% either way); goodwill protection comes from coach
  `attitude`, not from cheering.
- **API**: `GET /api/feed/catalog`, `POST/GET /api/teams/{id}/feed`. Mood and GM
  standing are returned as **number-free bands** (`fervent / warm / quiet /
  restless / hostile`) — the raw pulse is a model input, not a scoreboard for
  fans to game.

**Validated**: 15 tests, a clean regression sim (0 errors, rosters 144/144, no
fallback warnings), and end-to-end against the real migrated schema — 6 fans
posting "Fire the GM" produced a -0.50 GM standing feeding turnover, and
"Trade him" moved that player's combined sentiment to -0.17 (nudged, not
dominated, because he had no star ratings against him).

### Step 9 (additive half) — sentiment UI ✅ (built)
The layer is now reachable by users. Three new components under
`src/Components/Sentiment/`, plus a per-team scope on the boards endpoint
(the plan asked for per-team AND league-wide; only league-wide existed).

- **`PlayerRating.tsx`** — the 1-5 control, on the PLAYER PAGE beside his
  identity rather than buried in the attribute panel: it's how you feel about
  him, not a stat. Deliberately restrained, because this is the QUIET signal —
  hover to preview, click to set, click your current rating again to withdraw
  (no separate clear button). Below the rater floor it says "N more ratings
  until this counts" instead of showing an average one or two people control.
- **`TeamFeed.tsx`** — the loud half, on the team page. Target tabs
  (The Team / The GM / A Player), a player picker, and one-tap posting from the
  catalog with buttons tinted by valence. Posts animate in (`feedPostIn`) and
  the tapped button pops (`feedPostSent`) so posting feels responsive before the
  refetch lands. Mood and GM standing show as **bands with a plain-English
  blurb** ("The fanbase has turned"), never numbers.
- **`SentimentBoards.tsx`** — Fan Favorites / Most Hated, team-scoped on the
  team page. Renders nothing at all when no one has been rated yet, rather than
  showing two empty columns.

Keyframes live in `index.css` beside the existing `cheerPayout*` ones, matching
the house idiom.

**Verified**: `tsc` clean (the 6 pre-existing errors are in untouched files) and
a full `npm run build` succeeds with **zero warnings from any of the new files**.
Note the build must be run via `npm run build` (react-app-rewired) — plain
`react-scripts build` skips `config-overrides.js` and the `@/` alias fails to
resolve.

**Not verified interactively**: rating and posting both require a signed-in
Clerk user, so the write paths could not be exercised end-to-end in a browser
here. The read paths, aggregation, and every backend rule are covered by the
76 backend tests.

### Changes since first build (steps 4-6 revised on owner feedback)
- **GMs are rated 1-5, not liked/disliked.** They're judged on the same scale as
  players, so they share the model: one `PlayerRating` control with a `subject`
  prop (the separate `GmVote` component is deleted), and
  `CoachSentimentRepository` shares `normalizeSentiment` + the quorum helper
  with players so the two can't drift onto different curves. The unshipped
  binary `value` column was dropped and recreated as `rating`.
- **No aggregate mood band.** How the fanbase feels should come across by
  READING the feed, not from a computed label above it. `teamMood`/`gmPulse`
  were removed.
- **Ratings generate the posts.** Rating a player or GM auto-posts in that fan's
  voice; re-rating REPLACES the post rather than stacking a contradiction; a 3
  says nothing. The manual catalog is general team support/frustration only.
  Auto posts are display-only and never re-enter the model, and they don't
  consume the manual post allowance.
- **Interaction is gated to your own team**, enforced server-side on all four
  write paths — these signals drive the GM brain, so a UI-only gate would let
  anyone brigade a rival.
- **Quorum scales with the fanbase**: `max(3, ceil(activeFans x 0.05))`, reusing
  the awards' `_countActiveUsers`. The fraction is far below the awards' 0.20 on
  purpose — an award is one league-wide vote, ratings spread across 144 players
  and 24 GMs, so 0.20 would hide everything permanently.
- **Vocabulary is bounded to mechanics that exist.** No trades in Floosball, so
  "Trade them" and "Untouchable" (trade-protected) are out; a regression test
  enforces it. Language is gender-neutral and American football, not English
  football ("The Bleachers", team/franchise, fan — not terraces/club/supporter).

### Team page redesign ✅ (done 2026-07-31, frontend `088daca`)
Paused on 2026-07-29 at "still feels messy and incohesive", then rebuilt from a
design handoff spec and iterated to done. The page is now one continuous read:
hero band → trophy case → five-cell facts row (ratings / coach / locker room /
stadium / next up) → roster beside The Bleachers → season history + schedule →
`FrontOfficeBand`. `SectionRail` adds right-edge section nav plus proximity
scroll-snap. `/front-office` still redirects here.

All three known-unresolved items from the pause are closed: the fan controls
were redesigned into the page rather than left in old components; gauges follow
the house 0–100 style used on the player page; the compact rating control now
fills from the fanbase average with the hint line restored, so an unrated player
no longer reads as broken.

Two things found and fixed along the way that were real bugs, not styling:
locker-room gauge domains were read off `computeLockerRoom`'s docstring, which
describes a roster average rather than the league spread (a third of the league
pegged full); and 10 of 24 team colours failed 4.5:1 as text on the dark page
(Detroit's navy at 1.41:1), now lifted by `readableOnDark()`.

### Still open in the sentiment layer
- **Team mood as a second consumer** (step 10, optional) — never started. NOTE:
  an earlier revision of this section claimed `teamMood` is "computed and
  surfaced but wired to nothing"; that is wrong, no such value exists anywhere.
  Owner already ruled funding stays purely fan-contributed, so this would be
  atmosphere/morale only.

_(The step-9 deletion half — `VoteControls`, `FaBallotModal`, `CutPlayerCard`,
`ResignPlayerCard`, `FireCoachCard`, `HireCoachCard` — was listed here as
pending long after step 7 removed all nine components. Closed.)_

### Step 7 — vote removal ✅ (done, sim-verified)
Done in TWO stages deliberately: flip `AUTONOMOUS_FO_ENABLED` on and prove the
brain can run a whole offseason FIRST, so the deletion was dead-code excision
rather than a swap-and-hope.

Removed: 10 `/api/gm/*` endpoints (1,264 lines); `managers/gmManager.py` in full
(all 5 resolvers — nothing referenced it once the call sites went); the 4
offseason wrappers (`_resolveGmFireCoachVotes`, `_resolveGmResignVotes`,
`_resolveGmCutVotes`, `_runFaVotingWindow`) and their call sites; 9 frontend
vote components plus the unrouted `FrontOfficePage`; `GM_VOTE_TYPES` (now an
empty set so a stray reader degrades rather than raising); and the Scorched
Earth grant, which could never fire again.

⚠️ `OffseasonPanel` had a live "Submit Requisition" button posting to
`/api/gm/fa-ballot`. Deleting the endpoint alone would have left a 404 button,
so the modal, trigger, handler and state were unpicked too — it now builds to
exactly its pre-step-7 warning baseline.

**Deliberately NOT deleted**: the `GmVote` / `GmFaBallot` tables and models
(account-deletion cleanup still references them, and dropping tables risks a
prod migration for no gain), and the Tribune / Scorched Earth achievement
templates — anyone who earned them keeps them; they're simply unobtainable now.

**Verified**: fresh fast sim, 0 errors, rosters 144/144, every team staffed,
turnover ~4 changes/season, 88 tests passing.

### Step 8 — economy ✅ (measured; no backfill needed)
Owner's call was to let the sink shrink. The data says that's comfortably right:

| | |
|---|---|
| GM votes drained | **28,410 F over 16 seasons** (~1,775/season) |
| Share of all spending | **1.1%** |
| Shift in net flow | **0.92% of all income** |

For scale, the sinks that remain are far larger: `season_end_tax` 904,672,
`team_contribution` 438,671, `facility_contribution` 343,589, `card_purchase`
258,365, `pack_purchase` 249,940. Removing ~1,800 F/season of drain is inside
the noise — no replacement sink is warranted, and inventing one would add a
cost to a layer that is deliberately free.

### Steps 9-10 — remaining
Step 9 frontend is largely built (rating control, feed, boards, GM rating, and
the vote UI now deleted); the team page redesign is PAUSED (see above).
Step 10 (team mood as a morale/atmosphere consumer) is optional and untouched.
Coach specialist generation + dropping `overallRating`, GM turnover,
sentiment data, social feed, sentiment->brain wiring, vote removal, economy,
frontend. Cut-for-upgrade + the best-first assessment sweep (the rest of Part A)
also remain.

## Still open

- **Position value: universal vs small per-GM biases** (start universal; biases are a
  later flavor option).
- ~~Rookie/FA draft order relative to the sweep~~ — **settled 2026-07-27**: the rookie
  draft is removed (Part F). Ordering is sweep (best-first, decisions only) → FA draft
  (worst-first, the single acquisition step).

_(Parity of the assessment sweep is a non-issue: it makes cut/re-sign decisions only;
actual FA acquisition stays worst-first.)_
