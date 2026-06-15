# QB Scrambles — Scope

A standalone sim feature: a mobile QB under pressure takes off and **runs**
instead of taking a sack (or throwing it away). Fills the "QBs can't run at all"
gap, improves the base game for every mobile QB, and becomes the substrate for
the awakened **QB-Agility power** (which = a guaranteed/amplified scramble).

Status: **scoped 2026-06-14**, not built. Backend `next-season`.

## Why it's small
The sim is already QB-run-ready (per the feasibility trace): rushing stats are
per-player (not RB-gated), and clock / TD / WPA / play-by-play / box-score /
fantasy all key off `playType == Run` + whoever `play.runner` is. The only
RB-hardwiring is in `runPlay()`, which a scramble **does not call**. A scramble
is just a new sub-outcome of a pass play that flips `playType=Run`,
`runner=passer`, computes yardage inline, and reuses the run-crediting tail.

## Attribute model: agility escapes, speed runs
- **Agility GATES the escape** (the scramble chance). A low-agility QB basically
  never escapes the rush → takes the sack. So **agility decides *whether* they
  scramble.**
- **Speed DRIVES the yardage.** Once out of the pocket, the gain is keyed to
  speed (with a small agility contribution for shaking the first defender). A
  low-speed QB who escapes gets a limited gain.
- Result: **high-agility + high-speed = elite scrambler** (escapes often, big
  yards); **agile-only = escapes often, short gains**; **fast-but-not-agile =
  moot** (rarely escapes, so speed never gets used).

## Where it hooks (`floosball_game.py`, inside `passPlay()`)
- **Primary — the sack branch (~`:9300`).** When a sack would occur, first roll a
  **scramble chance scaled by the QB's AGILITY** (and the pressure,
  `rushDifferential` `:9282`). Use agility specifically (not the blended
  `qbMobility` at `:9262`, which lets speed substitute — we don't want that). On
  success, scramble instead of sacking.
- **(Optional, P3) — the throwaway branch (`:9483`/`:9509`).** "No one open"
  currently becomes a 0-yd throwaway; a mobile QB could scramble there too.

## Scramble resolution (inline, do NOT call `runPlay()`)
On a successful scramble:
1. `self.playType = PlayType.Run`; `self.runner = self.passer`.
2. Compute scramble yardage inline — a modest positive distribution **keyed on
   SPEED** (small agility contribution for the first defender); mostly
   short-to-medium with a rare breakaway, with the breakaway tail unlocked by
   high speed. Do **not** route through `runPlay()` (its gates are RB-attribute-
   tuned).
3. Set in-bounds; on a TD the central `playType==Run` path credits `addRushTd`.
4. Crediting tail: `runner.addRushYards(...)`, `runner.addCarry()` (the same
   methods the run path uses; defined on the base player class, so a QB can call
   them).
5. **Bookkeeping (the landmines):**
   - Keep `self.isSack = False`; do **not** write the sack stats (`sackByTier`,
     `sackedBy`) — branch before `:9360`.
   - Do **not** charge a pass attempt (only the completion branch does, `:9388`).
   - Credit a **tackler** on the scramble (`self.tackledBy`), not a sacker.
   - Optional small fumble chance (scrambling QBs fumble) — reuse the run fumble
     path or an inline roll; `rushing.fumblesLost` already persists for QBs.

Everything downstream then "just works": clock runs for an in-bounds run
(`shouldClockRun` `:7271`), WPA credits the QB runner (`_attributeWpa` `:6596`),
box score + DB persist (QB carries pass the `carries>0` gate), fantasy awards
rush FP (position-agnostic `stat_tracker`).

## Tunables (new constants)
- `QB_SCRAMBLE_AGILITY_THRESHOLD` — below this agility, QBs basically never
  escape (pocket QBs still take the sack).
- `QB_SCRAMBLE_BASE_CHANCE` + agility/pressure scaling — how often a pressured
  *agile* QB escapes-and-runs vs. takes the sack.
- Scramble yardage curve (mean/spread keyed on **speed**, breakaway tail unlocked
  by high speed).
- `QB_SCRAMBLE_FUMBLE_CHANCE` (small, optional).

## Awakened QB-Agility integration (powers feature, noted here)
The awakened QB-Agility power = **guaranteed scramble** (escape always succeeds)
with **amplified yardage**, firing on the next pressured dropback. Same code
path, with the power flag forcing success + boosting the yardage curve. So
QB-Agility stops being narrow "sack-negation" and becomes "this QB is suddenly a
dangerous runner."

## Build phases (small)
- **P1** — scramble in the sack branch: mobility-gated chance, inline yardage,
  crediting tail, the isSack/pass-attempt/defensive-credit bookkeeping.
- **P2** — scramble play-by-play text (a small phrase pool, e.g. "{name} escapes
  the rush and scrambles for N").
- **P3 (optional)** — throwaway-branch scrambles (no-one-open).
- **P4** — tests + validation: scramble frequency tracks mobility, QB rush stats
  persist + surface, clock runs, no phantom sacks/pass-attempts, fantasy FP
  awarded. Update CLAUDE.md (sim now has QB scrambles).

## Decisions to confirm before building
1. **Trigger:** sack branch only to start (recommended), or include throwaway
   (no-one-open) in P1?
2. **Frequency/threshold:** how mobile before a QB scrambles, and how often
   (it should be occasional, not every pressure — pocket QBs still mostly sack).
3. **Yardage profile:** modest short-to-medium with a rare breakaway (recommended)?
4. **Fumble risk:** include a small scramble-fumble chance, or none for v1?
5. **Gating:** build it live (it's a real sim improvement), with a constant to
   disable if needed — or behind a flag for staged rollout? (Leaning: live, since
   it changes base-game behavior for the better and is easy to tune.)

## Orthogonal note
Pre-existing key mismatch: the season-stat rollup reads `s_rushing.get('atts')`
for the flat `rushing_attempts` column but the dict key is `carries`
(`seasonManager.py:1728`) — so that flat column is likely already 0 for everyone
(RBs included). The `rushing_stats` JSON is correct, so box scores are fine. Only
matters if QB-run *leaderboards by that column* are wanted; cheap to fix, but
out of scope here.
