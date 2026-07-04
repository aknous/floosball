# Playbook Diversification — Play Concepts, Deception & Reads

**Status:** design (2026-07-04). Owner-approved direction: **strategic depth first**, **run concepts as the foundation**, then play-action/RPO, then trick plays.

Today the offensive playbook is thin: one monolithic run (`runPlay`, gap-targeted via `gapDistribution`) and pass-by-depth (`passPlayBook` = 24 route-*depth* maps, no route *shapes*). `PlayType` = `Run/Pass/FG/Punt/XP/Spike/Kneel`. There is **no** concept / formation / personnel / deception layer. This plan adds one.

## Vision — a three-layer system

Every added play (draw, counter, RPO, flea flicker) works the same way: **it exploits, or is punished by, the defense's commitment.** That makes offense-vs-defense a rock-paper-scissors, and it rewards the smarter staff. Three layers:

1. **The call (offensive coach).** Concepts belong to the **COACH's** playbook (not the team — it travels with the coach; a hook for coach identity/specialties later). A good coach calls the right concept for (a) *his own personnel* and (b) *the expected defense*. Calling a draw because he reads blitz is the skill. Gated by `offensiveMind` / `scouting` / `aggressiveness`.
2. **The counter (defensive coach).** The defensive adaptation tracks the offense's concept *tendencies* and adjusts to take them away (offense leans on draws → the D stops blitzing; leans on counters → the D plays disciplined). Cat-and-mouse; gated by the D-coach's `adaptability` / `scouting`. Extends `adjustDefensiveGameplan`.
3. **The execution (players).** The concept sets the *potential* (the matchup edge). Whether the deception actually lands is a **player-skill roll — deceive vs telegraph.** Sell the fake → full edge; telegraph it → the edge is lost or *reversed* (the defense reads it). So a high-deception concept is high-ceiling but **risky** with the wrong personnel — which is why the coach must match concept to player.

**Design principle:** the matchup (coach vs coach) sets the stakes; execution (players) decides if you collect. Flavor follows the mechanic.

## The concept ↔ scheme matchup (rock-paper-scissors)

The deception surface already exists: `gameplan.getDefensiveScheme()` returns `{runDefMult, passDefMult, passRushMult, coverageType, blitzPackage}`, and that `scheme` dict is **in scope at resolution** in `runPlay` (~`:9684`) and `passPlay` (~`:10703`). Concepts are a **modifier layer keyed to that dict** — not a rewrite.

**One structural gap to fix (also a realism bug):** `runPlay` is currently *blind to the blitz* — `scheme['blitzPackage']` only affects `passRushMult`/`passDefMult`, never the run. A run into an all-out blitz should gash a vacated front; today it doesn't. Fixing this (bias `effectiveRunDef` down / gate-2/3 up when a blitz is on) is the attach point for "draw beats blitz" AND a standalone improvement.

## Phase 1 — Run concepts

**Build status (2026-07-04):** Phase 1a (offense) BUILT — concept table (`constants.RUN_CONCEPTS`), `Game._selectRunConcept` (coach call), `runPlay` resolution (concept edge × execution roll + the blitz-vs-run realism fix), and PBP flavor. Validated: distribution power ~50% / draw·counter·sweep ~16-19%; draws outgain (5.5 vs 4.2 ypc, called + executed in blitz spots); deception concepts telegraph ~9%; overall ypc ~4.45 (realistic); full-season health clean (0 errors), league scoring +~1.6 combined pts/gm (the one-sided blitz-vs-run buff — tunable). Master toggle `RUN_CONCEPT_ENABLED`. **Phase 1b (defensive counter-adaptation — the D-coach reading concept tendencies and countering) NOT yet built.**

Concept set (start ~4–5; `power` is the vanilla baseline):

| Concept | Beats | Loses to | Deception (execution weight) |
|---|---|---|---|
| **Power / Dive** | light box (low runStopFocus) | stacked box | low — reliable baseline |
| **Draw** | blitz / pass-rush sell-out | run-committed front | **high** — sell the pass |
| **Counter** | aggressive over-pursuit / flow | disciplined / zone-disciplined | high — misdirection |
| **Sweep / Toss** | interior-focused front | fast edge pursuit / contain | medium — edge speed + blocking |
| *(maybe)* **Zone** | varied fronts (patient, RB vision) | penetration | low-medium |

**Resolution model (in `runPlay`):**
1. `conceptEdge` = f(concept, scheme) — e.g. Draw: `+edge` when `blitzPackage` set or `passRushMult` high, `−edge` when `runStopFocus` high. Counter: `+edge` vs high aggressiveness/blitz, `−edge` vs disciplined. Power: small `+edge` vs light box. Sweep: `+edge` vs interior focus, `−edge` vs edge speed.
2. **Execution roll** (CONFIRMED attribute mapping): `execQ` = normalized weighted player attributes per concept — Draw: `creativity`+`focus`+`vision`; Counter: `agility`+`creativity`; Sweep: `speed`+`agility`+`blocking`; Power: `power`+`discipline`. Each concept has a `deception` weight (Power ~0.1 → execution-flat; Draw/Counter ~0.7-0.8 → execution swings hard). `execFactor = (1-d) + d·lerp(-0.4, +1.2, execQ)` scales `conceptEdge`: a great executor on a deception concept gets full+ edge; a poor one *telegraphs* → negative edge (defense reads it). `pressureHandling` adds a clutch/choke swing in big moments. `clutchFactor` is deprecated — do not use.
3. Apply the net edge to `effectiveRunDef` / gate chances, then the existing three-gate yardage model runs unchanged.

**Play-calling (new `runConcept` selection step):** when a `run` is chosen, pick the concept — weighted by coach tendencies + situation + a *read* of the expected defense (anticipated blitz → draw) + *own personnel* (shifty back → more deception). Analogous to `_selectPassPlay` but for runs (runs have no playbook today). Gated by `offensiveMind`/`scouting`.

**Defensive adaptation:** track per-offense concept usage (like the existing cumulative half-stats) and feed it into `adjustDefensiveGameplan` so the D-coach counters a tendency (lots of draws → lower `blitzFrequency`; lots of counters → lower `aggressiveness`). Gated by D-coach `adaptability`.

**PBP:** narrate the concept + the execution outcome ("Draw — and the blitz bites, he's gone!" vs "Draw, but the back tips it early — stuffed"). New `formatPlayText` branch (the `isScramble` branch ~`:3888` is the template).

**Attach points (from engine map):** `runPlay` `~:9638` (concept edge + execution + blitz hook), `_executeWeightedPlay` `~:3127` / a new run-concept selector (selection), `adjustDefensiveGameplan` in `gameplan.py` (counter-adaptation), `formatPlayText` `~:3787` (PBP), a `runConcept` tag + concept flags on `Play`.

## Phase 2 — Play-action & RPO
**Play-action BUILT (2026-07-04).** `Game._selectPlayAction` (coach call — more on early downs, deeper shots, a scouting read of a run-keying D, sharp offensive minds; ~15% of passes, never on short/quick). In `passPlay`: a QB execution roll (`PLAY_ACTION_EXEC`: creativity/focus/agility) × the D's run-commitment (runStopFocus + blitz) = `paEffect`; a sold fake vs a run-committed D adds REAL receiver openness (`_paOpennessBonus` into `calculateReceiverOpenness`, the actual completion driver — NOT the fallback `effectivePassDef`) and slows the rush (LBs frozen); vs a pass-committed D it backfires (wasted fake → more rush). Validated: fake works 88% vs run-committed Ds, +6.3% completion (medium) / +5.2% (deep) there; **net-neutral overall** (PA on/off completion 69.0/68.7) — redistributes, doesn't inflate. PBP weaves it in ("fakes the handoff and..." / "off play-action..."). Consts `PLAY_ACTION_*`, master toggle `PLAY_ACTION_ENABLED`.
**Route concepts BUILT (2026-07-04).** mesh beats MAN, flood beats ZONE, screen beats the BLITZ; MATCH coverage damps them (`PASS_CONCEPT_MATCH_DAMP`). `Game._selectPassConcept` — the coach reads the D's `coverageTendency` + blitz rate (scouting) and calls the concept that beats it (screens skew short, mesh shorter, deep stays standard). In `passPlay` the matchup is resolved once (coverageType is rolled for the play) into a per-play receiver-openness bonus (`_passConceptOpennessBonus`) added in `calculateReceiverOpenness` — same proven lever as play-action (modifying `rcvDefRating` was too diluted). Consts `PASS_CONCEPT_*`. Validated: bonus fires on ~56-60% of mesh/flood throws (matched), net-neutral overall (no inflation), mesh +2.8 net completion. PBP: "works the mesh and...", "floods the zone and...", "sets up a screen and...".
**RPO BUILT (2026-07-04).** The structural piece: the defensive scheme is now rolled PRE-SNAP in `Game._executeRpo` and reused by the resolver (both scheme-roll sites take a `_preRolledScheme` if present — no double-roll). On a run look the QB reads the box: a loaded front (`runStopFocus >= RPO_LOADED_RUNFOCUS` or a blitz) -> pull it and throw a quick pass; a light box -> hand it off. **The READ is the QB's vision + instinct** (`RPO_EXEC`): a sharp QB reads correctly ~82%, a poor one ~68%. A correct read gets the numbers advantage (a give into a light box gets `RPO_BONUS` run relief; a throw into vacated coverage gets `RPO_OPENNESS`). `_selectRpo` gates on QB fit (instinct/vision/agility — a mobile, heads-up QB) + offensiveMind; skipped in short-yardage/goal-line. Give-first (loaded threshold 0.63) + trimmed frequency so it stays run-first, not pass-heavy. Validated: net-neutral scoring, run/pass unchanged (37/63 = baseline), 0 errors. PBP: "takes the give on the RPO and...", "reads the box, pulls it and...". Consts `RPO_*`.

**Phase 2 COMPLETE** (play-action + route concepts + RPO). Remaining: Phase 3 trick plays.
- **RPO**: a pre-snap read that branches run/pass on the box. **Structural hook:** the defensive `scheme` is currently rolled *after* the run/pass decision (only inside the resolvers). RPO needs `getDefensiveScheme` lifted to pre-snap (`_executeWeightedPlay`) so the read can pick the resolver, with the rolled scheme threaded down (no double-roll). Both resolvers reused verbatim.

## Phase 3 — Trick plays — BUILT (2026-07-04)
**flea flicker** (deep-ish pass, beats a run-committed D), **statue of liberty** (edge run, beats a BLITZ), **reverse** (WR run, beats over-PURSUIT). Halfback pass intentionally skipped (owner). `Game._selectTrickPlay` returns a trick or None; `_executeTrickPlay` rolls the scheme pre-snap (reuses the RPO `_preRolledScheme` path), checks whether the targeted commitment is actually there, gates on the key player's execution, and applies a big payoff (works) or backfire (blown — negative openness + sack risk on the flicker, negative `effectiveRunDef` relief on the runs). The reverse swaps in a WR carrier via `_forcedRunner` (runPlay honors it; stat methods position-agnostic). **"When" (called shots only, owner-confirmed):** only bold coaches (aggressiveness), keyed to the D's tendency, field-position band `TRICK_FIELD_MIN/MAX_YTE` (not red zone / not backed up), NOT in hurry-up / short-yardage, and NOT a desperation heave (down 2+ scores late → standard offense). Validated: ~1.4/game, all three fire, high variance (WORKED +10.1 vs BLOWN +2.7 avg gain), health clean (0 errors, avg 32.2). PBP: "pulls off a flea flicker and...", "takes the Statue of Liberty and...", "takes the reverse and...". Consts `TRICK_*`; toggle `TRICK_PLAY_ENABLED`.

**PLAYBOOK DIVERSIFICATION COMPLETE** — run concepts + defensive counter, play-action, route concepts, RPO, trick plays; all situationally + coach-gated, balanced, with self-describing play-by-play.

## Balance & validation
- **Spice, not the norm:** power/dive stays the baseline; deception concepts are situational; trick plays rare. League scoring must stay ~stable (current prod-resume ≈ 42 combined pts/game — validated 2026-07-04).
- **Roughly zero-sum:** right call vs wrong defense gains, wrong call loses; on average it washes, but good coaches + good execution net positive. Validate the *variance/attribution* shift, not a scoring inflation.
- Validate with the `coach_experiment.py` harness pattern: isolate the concept layer (master toggle), paired multi-subject; confirm a high-`offensiveMind`/good-personnel team gains from concepts while a poor one doesn't, and that league scoring is unmoved.
