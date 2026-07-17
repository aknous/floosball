# Autonomous Front Office + Fan Sentiment Redesign

**Branch:** `next-season` (season-cutover feature)
**Status:** Design — not yet built
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
  `playerRating` — so those two are close to ready.
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
   leveraging the existing three-tier prospect model (`current < trueSkill < potential`,
   from last season's parity package) + the age/retirement curve
   (`computeRetirementOdds`, `playerManager.py:1195`):
   - **developing** (young, `current < potential`, about to rise),
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
   each slot weigh the **incumbent vs. the best available replacement** (FA pool +
   rookies). If `(replacementValue − incumbentValue)` clears an **upgrade threshold**, CUT
   the incumbent (in anticipation of drafting a replacement); else stand pat. **The
   threshold scales with the team's worst-first draft slot** — this is the aggression dial:
   - **Early pick (bad teams) → aggressive:** confident of landing the replacement, so a
     *smaller* edge justifies a cut (lower threshold). Churn to climb.
   - **Late pick (good teams) → conservative:** cutting is a gamble when you pick last and
     may get leftovers, so a *bigger* edge is required (higher threshold; lean toward
     re-signing your own).

   Cuts are purposeful churn toward improvement, high-value needs first. **The actual
   signing happens later** in the separate worst-first FA + rookie drafts — steps 3 and 5
   only DECIDE re-sign/cut. (Note the pro-parity loop: bad teams churn aggressively, good
   teams stand pat; and a high-scouting late-drafter still eats well because the ascending
   players it values are the ones lesser scouts pass on, so they survive to its pick.)
6. **Sentiment tilt** — throughout, fan sentiment × `fanTrust` nudges close calls (keep a
   fan-favorite marginal player as a re-sign; cut a fan-villain the GM would otherwise
   keep). See Part D.

> **Sweep vs. drafts:** steps 1–6 are the best-first **assessment sweep** and produce only
> cut/re-sign **decisions** (no signing). Vacancies are filled afterward in the existing
> **worst-first** rookie + FA drafts (best-*value*-available, position-need aware; no fan
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
worst-to-best step**, and the rookie draft stays worst-first. So the best teams do NOT
get first crack at free agents — best-first only sets the order in which teams finalize
their own keep/cut lists and feed cuts into the pool. No anti-parity effect.

**Reordered offseason.** Old: (vote-driven frontoffice) → rookie draft → FA draft. New:
`GM turnover → best-first assessment sweep (cut/re-sign only) → worst-first rookie draft
→ worst-first FA draft → training`. GM turnover (fire/retire/leave + replacement)
resolves FIRST so the GM making a team's calls is the one who'll coach it. (Rookie-then-FA
draft ordering kept as today.)

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

## Still open

- **Position value: universal vs small per-GM biases** (start universal; biases are a
  later flavor option).
- **Rookie/FA draft order relative to the sweep** — kept as today (sweep → rookie → FA,
  both worst-first); revisit only if sim suggests otherwise.

_(Parity of the assessment sweep is a non-issue: it makes cut/re-sign decisions only;
actual FA + rookie acquisition stays worst-first.)_
