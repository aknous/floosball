# Mental Model — design spec & gameplay integration

> Status: **DESIGN SPEC, not built** (2026-06-24). Owner-driven redesign of the player mental /
> personality system. Analyzed against `development`; intended as a between-season build. File:line
> references are the *current* code (the hooks the new model plugs into / replaces).

## Why this exists

A review found the current mental system is **two real levers wrapped in seven attributes** — several
dead (`clutchFactor`, the quirk engine), several invisible (`focus`/`instinct`/`creativity` only exist
laundered inside derived ratings), and `determination` never moves an outcome on its own (it's always
summed with confidence in `_mentalDrift`). It's simultaneously *over-complicated* (too many named dials
with no felt identity) and, in a few spots, *miscalibrated* (kicker FG composure ±18%, rally stacking
~±8 rating/gate). The fix is not "more attributes" — it's to re-center everything on **one dynamic
state (confidence)** with a small set of dials that each have a distinct, legible job.

## The final roster

| Bucket | Attribute | Job |
|---|---|---|
| **Dynamic state** | **Confidence** (`confidenceModifier`) | The master self-belief level. Drives aggression + over/under-performance. The only mental *state* that moves during a game. |
| **Mental dials** (static) | **Discipline** | Shapes *how* confidence expresses: controlled vs wild. The error/control gate. |
| | **Determination** | Shock absorber #1 — resists confidence loss from the **scoreboard** (losing). |
| | **Resilience** | Shock absorber #2 — resists confidence loss from the player's **own mistakes**. |
| | **Attitude** | A **stable trait** → team chemistry (affects *teammates*, not the player's own play). |
| **Clutch axis** (static) | **pressureHandling** | Unchanged. Composure in high-leverage *moments* (the clutch/choke engine). Orthogonal to confidence. |
| **Football IQ** (skill, *not* mental) | **focus / instinct / creativity** | Reclassified as the *processing layer of skill*: execution / reads / improvisation. Feed derived ratings as today; no longer presented as personality. |
| **Folded / removed** | `selfBelief` | Folded — its job (scaling confidence swings) is now Determination + Resilience. |
| | `clutchFactor` | Deleted (already dead, hardcoded 0). |
| | `quirk` engine | Deleted or enabled — currently disabled dead code (`quirk=None`, 0% chance). |

Net felt attributes: **Confidence + 4 dials + pressureHandling**, plus three skill (IQ) inputs. Down
from the current sprawl, each with one clear role.

---

## 1. The core model — Confidence × Discipline

**Confidence `C`** is the dynamic state. Normalize to a signed band `C ∈ [-1, +1]`, neutral `0`
(maps from the existing `confidenceModifier`, currently clamped ±5 — rescale, don't invent a new var).
Confidence drives two outputs, and **Discipline `D`** (use `Dn = clamp((D-80)/20, -1, 1)`, the project's
`(attr-80)/20` convention) gates them.

### Output A — Aggression (decision-time, per player)
`A = C` sets risk appetite at **resolution time** (not play-calling — that stays coach-driven). High `A`
→ the player reaches for the bigger outcome; low `A` → takes what's there.

- **QB:** deep-read / contested-throw willingness. High `C` → throws the deep option more; low `C` →
  checks down. *(hook: target selection + `mustThrow`/read logic inside `passPlay` → `_selectPassPlay`)*
- **WR/TE:** contested-catch attempt + YAC aggression. *(hook: `calculateCatchProbability`, the contested
  branch)*
- **RB:** hit-the-hole decisively vs dance; cut for the big gap vs take the safe yards. *(hook: the gate
  selection in `runPlay`, `floosball_game.py:8960-8990`)*

### Output B — Execution (over/under-perform)
`E = C × execGain` is a small additive term to the quality math (throw quality, catch security, run-gate
differential). High `C` overperforms, low `C` underperforms. **This replaces the flat `_mentalDrift/15`
nudge** currently added at every gate (`floosball_game.py:9328-9338`) — same insertion points, but the
value now comes from the confidence *state* instead of the summed conf+det blob.

### The Discipline gate — the 2×2
Discipline decides whether confidence's energy is *controlled or wild*, across the whole range:

|  | High discipline | Low discipline |
|---|---|---|
| **High C** | Overperforms, no error tax — *surgeon* | Overperforms **and** forces it — *gunslinger* |
| **Low C** | Executes the safe play — *game manager* | Misses the play in front of them — *frozen* |

Two taxes implement the right-hand column:

- **Gunslinger tax (high C, low D):** `errInflate = max(0, C) × (1 - Dn) × K_err`, added to **INT /
  fumble / drop** odds. High `D` → `(1-Dn)≈0` → confidence with no error tax. Low `D` → a real turnover
  tax that scales with how confident they are. *(hooks: INT in `calculateCatchProbability:9648-9653`,
  drop `9655-9657`, fumble `runPlay:9015-9035`.)*
- **Frozen tax (low C, low D):** `missPenalty = max(0, -C) × (1 - Dn) × K_miss`, a hit to execution on
  *available* plays (the open checkdown thrown late, the gap hit a beat slow). High `D` at low `C` →
  competent-safe (no miss tax, just low ceiling); low `D` → tentative misses. *(hook: same execution term
  in Output B, sign-aware.)*

So **Discipline is the control knob at both ends**: at high confidence it's the difference between a
surgeon and a gunslinger; at low confidence it's the difference between a game manager and a frozen
player. Confidence is the *amplitude*; discipline is the *control*.

---

## 2. Determination & Resilience — the two shock absorbers

These do **not** add to any gate (that was the old `_mentalDrift` mistake). They gate the **downward
movement of `C`**, from two different sources. Confidence rises freely on good outcomes; what makes a
player mentally tough is *resisting the fall*.

- **Determination `Det`** — resists scoreboard-driven loss. When the team falls behind, per-play (or
  per scoring event) confidence drifts down by `ΔC_score = baseScoreDrop × (1 - Detn)`. High `Det` →
  no fold when losing; low `Det` → confidence bleeds with the deficit.
  *(Replaces the negative side of the momentum→confidence path for the trailing team,
  `_applyMomentumEffect:5764-5801`, and the `selfBelief`-scaled postgame streak swing,
  `floosball_player.py:276-301`.)*
- **Resilience `Res`** — resists own-mistake loss. After the player's *own* INT / fumble / drop, the
  confidence hit is `ΔC_mistake = baseMistakeDrop × (1 - Resn)`. High `Res` → shakes it off; low `Res`
  → spirals.
  *(Scales the existing per-play confidence drops: INT `10197`, fumble `9041`, catch-fumble `10424` —
  these currently apply unscaled.)*

This is the clean split you described: **Det = vs the scoreboard, Res = vs the mirror.** Both only touch
confidence's *decline*; neither is a flat rating term, so neither double-counts with Output A/B.

---

## 3. Attitude — a stable trait, not a scoreboard reaction

**The bug today:** attitude is too *variable and result-driven* — losing pushes players toxic, winning
pushes them to leader, so by free agency the leaders are re-signed and the pool fills with toxics
(survivorship bias on a volatile attribute). Players blame their TOXIC tags for bad games even though
attitude barely touches individual play.

**The fix — make it a trait:**
- **Anchor** attitude to a per-player baseline set at generation (their actual disposition).
- **Mean-revert + dampen:** only *sustained, multi-season* patterns nudge the trait, and it decays back
  toward baseline. One bad season can't flip a player toxic. *(Replaces the current win/loss-driven swing
  feeding `computeMoodTier`/disposition.)*
- **Separate trait from mood:** the scoreboard moves the transient **mood** (already display-only); the
  **attitude trait** stays steady. Chemistry reads the trait; mood is flavor.

**Effect — teammates, not self; a *peak* gate, not a *win* gate (owner, locked):** attitude feeds a
**team chemistry** value, computed as the **roster average** of attitude (toxics weighted slightly
heavier than leaders, since bad apples spread — but average-based, *not* a per-player sum). It does **not**
drive the toxic player's own outcomes. *(hook: a new term in the pregame stack alongside
`_applyTeamDisposition:6135` / funding morale `5807`.)*

- **Average, not count** — so a single toxic in a good room is absorbed and can't be scapegoated; only a
  genuinely sour *room* suffers. This is the deliberate fix for the over-blame problem (linear-per-player
  would make each toxic "cost" something visible, feeding exactly the over-attribution we're killing).
- **Ceiling, not baseline; low magnitude** — chemistry modulates the team's confidence **ceiling**, not
  its baseline. A toxic room's players can't quite reach their confidence peak (cap a touch below max); a
  leader room reaches it more easily. Baseline performance (and thus *winning*) is untouched: a great team
  with a toxic locker room still wins — it just never catches fire.

Result: a TOXIC tag means "this room can't peak," not "was on a losing team," and the FA pool shows a
natural spread of dispositions.

---

## 4. pressureHandling — kept, orthogonal

No redesign. `getPressureModifier` (`floosball_player.py:664`) stays the **big-moment composure** axis,
gated by `gamePressure ≥ CLUTCH_PRESSURE_THRESHOLD` (`calculateGamePressure:5506`). Different time scale
and trigger from confidence: confidence is the *running state* across the game; pressureHandling is *innate
composure in leverage spikes*, independent of how the game's gone. A low-confidence / high-pressureHandling
player still drills the game-winner — that combination is a feature.

**Guardrail:** keep it from stacking absurdly with the confidence error tax in clutch moments. The earlier
review flagged the kicker FG composure (±18%) as over-tuned; pull that ceiling down so a great-but-shaky
kicker isn't beaten by a mediocre-but-icy one as often. Pressure handles the *spike*; confidence handles
the *baseline*; tune the sum.

---

## 5. Football IQ — focus / instinct / creativity (skill, not mental)

These move out of the personality conversation and become the **processing layer of skill** — the
difference between a physically gifted player and one who also *plays smart*. They keep their current
derived-rating feeds (`xFactor:654`, `vision:660`, `playMakingAbility:653`, the defensive formulas
`868-922`), just relabeled and given a clear identity:

- **focus → execution consistency.** The *floor*: drop rate, assignment soundness, penalty avoidance,
  holding up when *un*pressured.
- **instinct → reads & anticipation.** Where the play's going: defensive ball-hawking (INTs, jumping
  routes), RB vision (gap selection), pre-snap / coverage recognition.
- **creativity → improvisation.** Something from nothing: YAC / elusiveness, broken-play recovery, QB
  off-script.

**The clean decision chain** — IQ is skill, confidence/discipline are the dials on it:

> **IQ (do they *see* the right play?)** → **Confidence (do they have the belief to *pull the trigger*?)**
> → **Discipline (do they stay in *control* or force it?)**

A high-IQ / low-confidence player reads it perfectly but checks down. A low-IQ / high-confidence /
low-discipline player fires into triple coverage he never should have seen. That interaction is the whole
point, and it falls out of the model for free.

---

## 6. Team form / disposition — emergent, not a separate system

Today, team form is a **parallel** system: `computeFormState` (`api_response_builders.py:111`) reads
streak + record + the collective mental composites (avg `complacencyVulnerability`, collective
`adversityResolve`) to pick a status, which maps to a flat team rating multiplier
(`FORM_STATE_RATING_MULT`, constants.py:443 — 0.92–1.00) applied pregame in `_applyTeamDisposition`
(`floosball_game.py:6135`). That multiplier stacks *on top of* per-player mental and momentum — the
double-count the review flagged.

Under the new model, **the form statuses are just team-aggregate confidence, labeled.** Each maps onto
mechanics we already defined:

| Status | Emergent from (new model) |
|---|---|
| **Getting Hot / Hot Streak** | aggregate `C` **rising** (winning lifts confidence) |
| **Steady** | neutral aggregate `C` |
| **Shaky** | `C` **dipping** from recent losses / own mistakes |
| **Cooling Off** | `C` **fading from a high** (winning team losing its grip) |
| **Spiraling** | `C` **collapse** — low **Determination** + losing |
| **Complacent** | high `C` + **low collective Discipline** → a *gunslinger team* |
| **Resolute** | high **Determination** holding `C` despite a losing record |

### What changes
- **Delete `FORM_STATE_RATING_MULT`.** The performance swing is now produced by the **aggregate of
  per-player confidence** (Execution + the discipline taxes), so there's no separate team multiplier to
  layer on. No double-count.
- **The status badge stays** (good UX) but becomes a **readout**: compute it from team-aggregate `C`
  (level), its trajectory (rising/falling), and collective discipline (controlled vs wild). It describes
  the model's state; it doesn't impose its own.
- **Complacent gets better.** It's specifically **high `C` + low Discipline** → the team overperforms on
  execution but pays the **gunslinger tax** (real turnovers). The trap game emerges as actual giveaways,
  and it only fires on *undisciplined* overconfident teams — a high-`C`, high-Discipline elite stays a
  "surgeon" and doesn't trap-game. (Replaces the flat −8% on any elite team.)
- **Spiraling / Getting Hot stop double-counting ELO.** The current code carries hand-tuning notes about
  exactly this (Spiraling cut to −1% because the multiplier double-counted the ELO underdog signal;
  Getting Hot's boost removed because selection effect already covers it). In the new model that's **one
  knob** — Determination governs how far a losing team's confidence falls — not a multiplier stacked on
  ELO. Structural fix, not a patch.
- **Composites fold away.** `complacencyVulnerability` → confidence×discipline; `adversityResolve` →
  determination/resilience. Both can be deleted.

### Keep
The **situational context** the disposition layer blends in — *trap game*, *playoff push*, *underdog
hunger* — is opponent/stakes-based, not internal confidence, so it's genuinely separate. Keep it as a
thin context layer (or feed it into `gamePressure`), independent of the form badge.

## 7. How it plugs into the gameplay loop

The loop is unchanged in shape; the mental terms change at five touchpoints.

```
PREGAME (per game, per player) ──────────────────────────────────────────────
  existing stack stays: compression(5929) → funding morale(5807) → fatigue
                        → team disposition(6135) → mental soft-cap(5977, guardrail)
  NEW: set in-game Confidence C from the season-carried baseline.
  NEW: compute team Chemistry from ATTITUDE traits → small nudge to teammates' C baseline.

PER PLAY ─────────────────────────────────────────────────────────────────────
  1. DECISION (resolution-time, per player)
       Aggression A = C  → risk appetite in: QB deep-read vs checkdown,
       WR contested-catch attempt, RB hit-the-gap vs take-what's-there.
       IQ (instinct) → is the read correct / matchup targeted.        [skill]
  2. RESOLUTION (outcome math)
       Execution  E = C × execGain   → added to throw quality(9504) /
                                        catch security(9554) / run gates(8960-8990).
                                        REPLACES flat _mentalDrift/15(9328).
       Gunslinger tax (C>0, low D)   → + INT(9648)/drop(9655)/fumble(9015).
       Frozen tax     (C<0, low D)   → − execution on available plays.
       IQ (focus/instinct/creativity)→ drop floor, reads, improvisation. [skill]
       pressureHandling(664)         → clutch/choke in high-leverage moments. [unchanged]
  3. CONFIDENCE UPDATE
       good play (completion/conv/TD)→ C up   (small, ungated)
       own mistake (INT/fumble/drop) → C down × (1 - Resn)         [Resilience]
       falling behind (scoreboard)   → C down × (1 - Detn)         [Determination]
       momentum(5764) / rally(297)   → feed C  (rally capped per the review)

POSTGAME / SEASON ────────────────────────────────────────────────────────────
  Carry C baseline toward the game's end state (existing 251-252),
    swing magnitude governed by Det/Res (replaces selfBelief scaling, 276-301).
  Attitude trait mean-reverts toward baseline; only sustained patterns move it.
```

### Current → intended, hook by hook
| Hook (file:line) | Today | Intended |
|---|---|---|
| `_mentalDrift` (9328-9338) | summed conf+det, flat add `/15` to every gate | **Replaced** by Execution `E = C×execGain` (confidence only) |
| INT/fumble/drop odds (9648/9015/9655) | mental only via clutch override | **+ Gunslinger tax** `max(0,C)×(1-Dn)` |
| per-play conf drops (10197/9041/10424) | unscaled | **× (1-Resn)** (Resilience) |
| trailing-team conf drift (5764-5801, 276-301) | momentum + selfBelief streak swing | **× (1-Detn)** (Determination) |
| play resolution choices (passPlay/runPlay) | no confidence input | **Aggression `A=C`** drives risk appetite |
| attitude → mood/disposition | volatile, win/loss-driven, self-affecting | **Stable trait → teammate chemistry** |
| `focus/instinct/creativity` | "mental intangibles" in xFactor | **Football IQ (skill)**, relabeled |
| `selfBelief` / `clutchFactor` / quirk | scattered / dead | **Folded / deleted** |
| kicker FG composure (8537-8573) | ±18% under pressure | **Ceiling pulled down** (over-tuned) |

---

## 8. Tuning targets & validation

Calibrate so confidence is **meaningful but not dominant** vs the ~21-point league skill spread:

- A full confidence swing (`C: 0→±1`) should be worth roughly **a third to half a skill tier** at the
  gates — felt, but skill still wins most matchups.
- Max gunslinger tax (`C=+1`, `D` floor) should add on the order of **a few pp** to turnover odds — enough
  that an undisciplined hot QB is visibly riskier, not enough to swamp skill.
- Rally + momentum into `C` must stay **capped** (the review flagged ~±8 rating/gate as too hot).

**Validate with the scenario harness** (`scenario.py` / `test_scenarios.py`): construct the four
quadrants deterministically — high/low `C` × high/low `D` — and assert the expected style (gunslinger
INT rate, game-manager checkdown rate, frozen missed-play rate, surgeon clean overperformance) rather than
waiting for them to emerge in a fast sim. Same for Det (confidence holds when down 14) and Res (confidence
holds after a pick).

## 9. Migration / removal checklist

- Rescale `confidenceModifier` → `C ∈ [-1,1]`; route it through Aggression + Execution + the Discipline taxes.
- Move `determination` off `_mentalDrift`; make it gate scoreboard confidence drop.
- Scale the own-mistake confidence drops by `resilience`.
- Re-anchor `attitude` to a baseline + mean-revert; repoint its effect to teammate chemistry.
- Relabel `focus/instinct/creativity` as Football IQ; keep their derived-rating feeds.
- Delete `clutchFactor`; delete or enable the quirk engine; fold `selfBelief`.
- Consolidate the three overlapping composites (`complacencyVulnerability` / `adversityResolve` /
  disposition) — Det/Res now do the explicit work, so the composites can shrink.
- Pull down the kicker FG composure ceiling.

## 10. Resolved decisions (owner, 2026-06-24)

- **`C` representation → clean `[-1,1]` state var.** Same dynamics as the legacy ±5 modifier, but it
  separates the *state* from the *effects* (which the ±5 entangles across `xFactor` ×2.2 + `_mentalDrift`
  + `/15` gates). Derive a display number / legacy modifier from it for the UI.
- **Aggression → resolution-time only.** Play-calling stays the coach's job; confidence drives the
  *player's* in-play risk choices, not the called play.
- **Quirk engine → delete.** It's disabled dead code; remove the whole path (`pickQuirkLine` /
  `getEligibleQuirks` / `quirk_reactions.yaml` wiring), don't revive it.
- **Chemistry → roster *average*, ceiling not baseline, low magnitude.** See §3 — average so one toxic
  can't be scapegoated; gates *peak* (a touch off the confidence ceiling) not *winning*.

## 11. Still open

- **Chemistry magnitude / curve:** exactly how far below max the confidence ceiling drops for a fully
  toxic room (and how far above for a leader room) — a tuning task for `/simcheck` + the scenario harness.
- **Toxic-vs-leader weighting in the average:** how much heavier toxics weigh than leaders.

## Skill-player situational decisions (P2b — owner direction 2026-06-24)

Beyond the QB read, ball-carriers make situational micro-decisions that the model should drive,
surfaced in the play text so they're *felt*. The clock-aware sideline decision is the first built.

- **Out of bounds (clock-aware).** Was pure RNG, situation-blind — a leading team could randomly
  step out late and stop its own clock. Now `_sidelineDecision`: the SITUATION sets intent
  (trailing+late → get out to stop the clock; leading+late → stay in to burn it), football IQ
  (instinct) gates whether the player acts on it, and DISCIPLINE decides clean exit vs greedy
  squeeze-for-more-yards (which risks a tackle in bounds, clock running). Narrated:
  *gets out of bounds to stop the clock / fights for extra yards and gets out / tries for more and
  is dragged down in bounds — the clock keeps running / stays in bounds, keeping the clock moving /
  steps out of bounds, stopping the clock*. **Built + tested** (run + catch sites).
- **Stretch for the first down / pylon** (ball-carrier) — `_stretchForFirst`: a confident carrier
  ending JUST short of the marker (or goal line) reaches the ball across to convert; an undisciplined
  reach exposes the ball (a fumble bump fed into the existing fumble check); tentative carriers take
  the spot. Narrated *reaches across the marker for the first down! / stretches across the goal line!
  / lunges but comes up just short*. **Built + tested** (runs; catch-side reach not yet wired).
- **Dive for a catch** (WR/TE) — on a CONTESTED ball (catch prob 15–60), a confident receiver lays
  out, extending their catch range (`MENTAL_DIVE_K`); the gunslinger drop tax is the reckless-lay-out
  risk; tentative receivers don't dive. Narrated *a diving grab!*. **Built + tested.**

All three: Confidence × Discipline for the *risk/reward* choices, Football IQ for the *awareness*
ones, the game situation as the trigger, and a play-text line on every one.

## Build status & remaining backlog (as of 2026-06-24, branch `feature/mental-model`)

The CORE model is built and tested — `feature/mental-model` off `development`, last build commit
`feb8264`, 14 deterministic sections in `test_scenarios.py` (helper unit tests across QB/RB/WR/TE/K
plus emergent + situational frequency checks). Determinism via `reseed()` (random + numpy +
`clear_all_batch_caches`). **NOTE:** all the mental helpers live on the `Play` class (next to
`_mentalDrift`), NOT `Game` — tests must call them on `scenario.game.play`.

**Built + validated:**
- **P1 — Confidence × Discipline core.** `_confExecution` (execution = C × `MENTAL_EXEC_GAIN`, minus
  a frozen tax for low-C × undisciplined), `_gunslingerTax` (turnover bump for high-C × undisciplined),
  via the redefined `_mentalDrift` = confidence-only execution × 15. Applies at every gate, all
  positions. Catch-site INT/drop gunslinger taxes; run-fumble gunslinger bump.
- **P2 — QB aggression.** `selectPassTarget(aggression=...)`: confidence shifts the force-it rolls
  (`MENTAL_AGGR_ROLL_K`) and the throw-away bail threshold (`MENTAL_AGGR_BAIL_K`).
- **P2b/c/d — situational ball-carrier decisions** (above): clock-aware OOB, stretch-for-first
  (runs), dive-for-a-catch — all with play-text narration.
- **P3 — Determination & Resilience shock absorbers.** Centralized in
  `Player.updateInGameConfidence(value, source)`: `source='mistake'` scales the down-drift by
  RESILIENCE; `source='scoreboard'` scales it by DETERMINATION (mapped to the existing `selfBelief`
  attribute). Neutral attr (80) preserves today's drop; 100 shrugs off (0×), 60 spirals (2×); positive
  drift never scaled. Tagged sites: fumble/INT/catch-fumble/drop = `mistake`; momentum drag = `scoreboard`.

**Remaining — each is consolidation/tuning of an EXISTING, entangled system, not a clean build.
Do them as focused, measured passes, not a marathon-session rush:**
- **P4 — Attitude → chemistry (TUNING, deferred).** The machinery already exists: `_driftAttitudes`
  (win/loss drift + mean-reversion + resilience cushion + coach influence) and
  `_propagateAttitudeContagion` (leader/toxic room effect). The "everyone toxic at FA" symptom is a
  balance problem: drift (`ATTITUDE_DRIFT_MAGNITUDE=3`) outpaces reversion (`ATTITUDE_REVERT_RATE=0.01`),
  and generation centers attitude ~73 (`lrCenter = mentalSeed-7`) while the system reverts toward 80,
  so a chunk start below the toxic line and survivorship keeps leaders rostered. Fix = a measured
  multi-season tuning pass (read the rostered-vs-FA attitude spread before/after). Gotchas: the
  multi-season sim is slow (>700 games), and attitude isn't a plain `players` column (it's in the
  attributes blob) — the measurement needs setup. Best via `/tune`.
- **P5 — Football IQ (BUILD, balance-affecting).** focus/instinct/creativity already feed the derived
  ratings (vision/playMaking/xFactor/defensive). Giving them NEW distinct hooks (focus→execution
  consistency, instinct→reads, creativity→improvisation) adds mechanics and shifts balance → needs
  tuning, and risks the re-complication this redesign set out to avoid. Decide first whether the
  conceptual reclassification (keep existing feeds, just document the identity) is enough.
- **P6 — Team form emergent (CONSOLIDATION, risky).** Goal: delete `FORM_STATE_RATING_MULT` + the two
  composites and recompute the form badge from aggregate confidence. But `complacencyVulnerability` /
  `adversityResolve` also feed disposition and the attitude contagion, so removal must unwind those
  consumers carefully.
- **P7 — Cleanup (ENTANGLED, low-value).** `clutchFactor` is permanently 0 but is load-bearing for the
  DB `clutch_factor` sync AND emitted into the play-insights the frontend reads — removing it touches
  persistence (3 sites) + risks a frontend `undefined`. The quirk engine is dead but threaded through
  the reaction engine's `composeReaction`/`pickSidelineCutaway` signatures. Also retire `selfBelief`'s
  old postgame confidence swing now that it's the P3 Determination dial. None is a clean one-line delete.

## End-to-end validation (2026-06-24, 2.1-season fast sim)

Beyond the 14 deterministic unit/frequency sections, the model was validated at SEASON SCALE on a
fresh fast sim (778 games, ~2.1 seasons):
- **Stability:** 0 tracebacks / 0 ERROR / 0 DB-lock over the whole run.
- **Confidence stays bounded:** `confidence_modifier` spans exactly −5.00..+5.00 — the Det/Res
  scaling did not break the clamp or cause runaway.
- **Gunslinger tax emerges:** low-discipline QBs (61–75) throw **2.03%** INTs vs high-discipline
  (83–99) **1.55%**; `corr(discipline, INT%) = −0.49`. Real and sensibly-sized.
- **Shock absorbers emerge:** high-resilience players end at **+1.67** mean confidence vs
  low-resilience **+0.14** (`corr(resilience, confidence)=+0.18`, `corr(selfBelief, confidence)=+0.19`)
  — resilient/determined players resist the downswings as designed.
- **Note:** league ppg ~15.2 — the situational-decision creep (stretch/dive convert a few extra
  plays) persists; flagged for the tuning pass, still in a sane band.
