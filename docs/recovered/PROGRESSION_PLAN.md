# Player Progression — ranks from achievement families + a profile page

**Status:** designing 2026-06-16, not built. Branch: next-season. Grew out of pick-em
depth Idea #2. **No new XP/level system** (that would duplicate achievements) — the
existing **tiered achievement families ARE the per-season ranks**. We just surface them.

## The model (final)
- Each activity already has tiered achievement families (per-season, I–IV, escalating
  targets), e.g. **Oracle** (cumulative season pick-em points: 300/700/1200/1800) and
  **Dynamo** (season fantasy points). These ARE the per-activity, per-season levels.
- **A player's rank in an activity = the name of their highest completed tier this season**,
  shown verbatim: **"Oracle II"**. No invented title ladder — the achievement name + tier
  IS the rank.
- **Only ONE primary family per activity surfaces as a rank** (each activity has several
  families; the rest stay regular achievements). Launch set: **Oracle = Prognostication,
  Dynamo = Fantasy**. Others (cards, GM, supporter) added later by listing their primary
  family in the config.
- **Ranks are per-season** (the families are `per_season`, progress resets). **Reaching the
  top tier (capstone, e.g. `oracle_iv`) is a permanent trophy** — and that's already durable:
  per-season `UserAchievement` rows aren't wiped, so a capstone completed in S12 persists as
  a record forever. The trophy case just queries capstone completions across all seasons.

## What's actually new (small)
1. **A rank-family config** (the only new "data"): which families are rank-bearing, their
   activity label, ordered tier keys, and the capstone key. e.g.
   `RANK_FAMILIES = [{activity:'Prognostication', tierKeys:['oracle_i'..'oracle_iv']},
   {activity:'Fantasy', tierKeys:['dynamo_i'..'dynamo_iv']}]`.
2. **Rank derivation** (pure query): for a user + family, highest tier with a completed
   `UserAchievement` this season → its `name` ("Oracle II"); none → unranked.
3. **`GET /api/profile/{userId?}`** returning: current-season ranks (per rank-family),
   the trophy case (capstone completions any season + competitive finishes), and headline
   stats per activity.
4. **Profile page** (`/profile` + nav): ranks row ("Oracle II · Dynamo III"), trophy case,
   stat blocks. Own + other-user views (show off).
5. Surface the current rank lightly elsewhere (next to the username in pick-em/leaderboards).

**Trophy case contents** (correction — these are USER trophies, not sim-player accolades):
maxed-family capstones (Oracle IV — S12), pick-em/fantasy **season leaderboard finishes**,
bracket prizes, notable/secret achievements. (HoF/All-Pro/MVP are sim *players*, not the
user — they live on the Players page, not here.)

## Overall level (permanent career layer)
The per-activity ranks above are per-season. The **overall level is permanent** and is the
career identity. Same principle — derived, no parallel XP-event system:
- **Overall level = lifetime achievement score.** Every completed achievement (once + every
  per-season tier across every season) carries a **point weight**; sum over the account's
  whole history → an overall level via a deep curve. Purely a query over `UserAchievement`.
- **Point weighting (derived in code, no DB change):** by category + parsed tier, e.g.
  onboarding ≈ 2, guidance tier I/II/III/IV ≈ 3/5/8/12, secret ≈ 15. Harder/deeper = more.
  Tunable in one map.
- **Curve:** deep / multi-season so veterans visibly outrank newcomers and top levels take
  years. Permanent (never resets).
- **Title:** a clean number + light general bands — **"Level 32 · Veteran"**
  (Rookie / Regular / Veteran / Sharp / Stalwart / Legend over the range). Flavorful names
  stay on the per-activity ranks (Oracle II); the overall is the number.
- **Profile header:** `Level 32 · Veteran` (permanent) above the current-season ranks row
  (`Oracle II · Dynamo III`) above the trophy case.

`GET /api/profile` returns overallLevel + overallTitle + points-to-next alongside the ranks.

## Optional (not required for v1)
- **Expand tiers** beyond I–IV for a longer seasonal climb (owner said "maybe"). The rank
  system works fine at I–IV; treat tier-count as a separate tuning pass.

## Build order
1. Backend: `RANK_FAMILIES` config + rank-derivation helper + capstone/trophy query
   (all off existing `UserAchievement`); `GET /api/profile`.
2. Frontend: `/profile` page + nav; show ranks + trophy case + stats; surface rank by
   the username.
3. Validate on a prod copy (ranks/trophies resolve correctly from real achievement data).

## Why this isn't redundant with achievements
Achievements stay the discrete "did you do X" feats. This adds NO new mechanic — it just
**reads** the primary tiered family as a legible per-activity RANK and gives the player a
**profile** to wear it. The redundant path (a parallel XP/level system) is explicitly
rejected.
