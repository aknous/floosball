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

### What to build
A per-team GM decision model, run in the offseason, that:

1. **Values its own roster** by player attributes — accuracy **gated by the GM's
   `scouting`** (a poor scout misjudges who's actually good, so their roster decays
   even with zero fan input). Reuse `playerRating` as the truth; the GM sees a
   scouting-noised estimate of it.
2. **Decides per player:** re-sign (walk-year), let walk, or actively cut — against
   contract cost, age / `computeRetirementOdds` (`playerManager.py:1195`), positional
   need, and roster balance. (Build the re-sign AND cut logic that don't exist.)
3. **Fills holes:** extend the existing best-available FA + rookie paths; no fan ballot.
4. **Then tilts every call by fan sentiment × the GM's `fanTrust`** (see Part D).

Respect the existing retention limits (`RESIGN_ONCE_LIMIT`, `RESIGN_LIMIT_PER_OFFSEASON`)
or re-tune them for the autonomous world.

### Per-team behavior (no global nudge knob)
Each GM manages differently, driven by **their own attributes** — this is the design's
main source of emergent identity:
- `scouting` → valuation accuracy (sharp eye vs. misjudges talent).
- `fanTrust` (**new**) → how much sentiment moves them: 0 = ignores the fans entirely,
  high = populist who over-churns fan-villains and regrets it.
- `playerDevelopment` → patience with young/declining talent.
- (optional) a `patience`/`aggressiveness` axis → how fast they churn the roster.

Same inputs, different weights → the stubborn GM, the populist, the shrewd evaluator.

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

## Open questions

- **Ratings vs posts** — two layers (lean) or posts-are-sentiment?
- **Team mood** — does aggregate sentiment feed morale/funding/attendance too?
- **`fanTrust` source** — a brand-new coach attribute, or derived from `attitude`?
- **Elite/bust tail size** — how rare should all-around great/terrible GMs be?
- **Churn rate** — target GM changes per league per season across fire/retire/leave.
- **Economy backfill** — what replaces the removed GM-vote Floobit sink?
- **Sentiment reuse** — extend the anomaly "attention" signal (love-only today) into a
  signed approval score, or keep a dedicated ratings/posts system separate?
