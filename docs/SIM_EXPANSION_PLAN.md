# Sim expansion — RB pass option, blocked kicks, turnover returns

**Status:** designed 2026-06-16, not built. Branch: `next-season`. Follows the QB-scramble
pattern (`docs/QB_SCRAMBLES_PLAN.md`): per-feature `*_ENABLED` flag + tunables in
`constants.py`, gender-neutral PBP, reuse existing stat/score tails, validate via a fast sim.

Engine: `floosball_game.py` (~9,400 lines). Line refs below are approximate — verify before
editing.

---

## Feature 1 — RB pass option (checkdown + screen)
**Goal:** RBs catch passes — mostly a checkdown when the QB is under pressure, plus an
occasional designed screen.

**Current state:** `rbStatsDict` (floosball_player.py:134) ALREADY carries receiving fields
(`receptions/passTargets/rcvYards/rcvTds/ypr/pass20+`), and `fantasyTracker` already scores
receiving for whoever has it. The sim simply never targets the RB (`passPlayBook` targets
`rb` slot is always None). So the plumbing exists; we only add the targeting + crediting.

**⚠️ Balance ripple:** this gives RBs receiving FP they currently earn zero of — a real RB
fantasy buff. Keep volume realistic (a pass-catching back ~2-4 catches/game, mostly short)
so it's flavor + a modest bump, not a new dominant FP source. Tune via sim.

**Build:**
- **Checkdown under pressure** — in `passPlay`, in the sack branch (~9438, where QB scrambles
  hook in): when the QB would be sacked, does NOT scramble, and `not mustThrow`, a tuned
  chance to dump to the RB instead of taking the sack → short completion. Flag `play.isCheckdown`.
- **Screen** — a small play-call weight for a designed RB screen (`PassType.screen` or reuse
  short), scaled by coach (more for pass-happy/aggressive). Slightly negative-to-modest air
  yards + YAC upside.
- Credit via existing `addRcvPassTarget / addReception / addReceiveYards` on the RB. Reuse the
  completion/YAC tail.
- PBP: gender-neutral checkdown/screen phrasing ("dumps it off to", "checks down to",
  "screen to").
- Constants: `RB_CHECKDOWN_ENABLED`, `RB_CHECKDOWN_PRESSURE_CHANCE`, `RB_SCREEN_ENABLED`,
  `RB_SCREEN_BASE_WEIGHT`, YAC/yardage tunables.

---

## Feature 2 — blocked FGs and punts
**Goal:** rare blocks — a handful per season league-wide, but possible.

**Current state:** no block concept. `fieldGoalTry` (~8304) rolls make/miss; punt resolution
(~4765) sets net distance. Defensive-TD/safety/possession infra exists (see Feature 3).

**Build:**
- **Blocked FG** — in `fieldGoalTry`, before the make/miss roll, a small block chance (scaled
  down for longer attempts / strong leg). If blocked → loose ball, defense usually recovers,
  optional short return, rare scoop-and-score (route through the existing turnover/return tail).
- **Blocked punt** — in punt resolution, a small block chance. Blocked punts are usually
  recovered by the defense near the line, sometimes returned/scored.
- New `Play` fields: `isFgBlocked`, `isPuntBlocked`, `blockedBy`, return fields shared with F3.
- Credit blocker (`add_blocked_kick` / new defensive stat); PBP block + recovery/return lines.
- Constants: `FG_BLOCK_ENABLED`, `FG_BLOCK_CHANCE`, `FG_BLOCK_LONG_FALLOFF`, `PUNT_BLOCK_ENABLED`,
  `PUNT_BLOCK_CHANCE`. **Tune to ~a handful of blocks per league season** (verify in sim).

---

## Feature 3 — interception & fumble returns (REFINE)
**Goal:** the defense runs after recovering — real return yardage, occasional pick-six /
scoop-and-score.

**Current state (PARTIAL — user was right):** defensive-TD (`_addScore(defensiveTeam, 6)` at
4852/4957), safety (4991), PAT-as-defense, and possession-flip ALL exist and key off
`play.yardage` as the return distance. BUT the return yardage itself is crude: an INT sets
`self.yardage = randint(-5, 10)` (9771) — no returner, no speed factor, wrong shape, so
pick-sixes are essentially impossible. Fumble-lost return spot is similarly thin.

**Build (refine, don't rebuild the scoring path):**
- Add `_resolveDefensiveReturn(...)`: pick the recovering defender (INT → `interceptedBy`;
  fumble → recoverer), generate a speed-driven return distance (model on the QB-scramble
  yardage approach), set `play.yardage` with the correct sign so a long return reduces
  `yardsToSafety` toward 0 and naturally triggers the existing defensive-TD branch.
- `play.returner` + return-yard stat credit; rare return fumble (ball back to offense); keep
  safety-on-return possible.
- WPA: add `returner` to the playmaker candidates (~6659) so big returns boost defensive WPA.
- PBP: append return yardage / "to the house" pick-six + scoop-and-score lines (gender-neutral).
- Constants: `RETURN_ENABLED`, `INT_RETURN_*` (speed pivot, base, max), `FUMBLE_RETURN_*`,
  `RETURN_FUMBLE_CHANCE`. Tune so most returns are short, pick-sixes rare-but-real.

---

## Build order & validation
1. **Feature 3** first — self-contained refine of existing code, no fantasy ripple.
2. **Feature 2** — blocked kicks (uses F3's return tail).
3. **Feature 1** — RB pass option (the one with a fantasy-balance ripple; validate RB FP).
Each behind its `*_ENABLED` flag. After each: a fast full-season sim (`/simcheck`) to confirm
volumes (RB catches/game, blocks/season, returns + pick-six rate) and league/economy sanity.
