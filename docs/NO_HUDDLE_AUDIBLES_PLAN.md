# No-Huddle & Audibles — tempo the offense chooses, plays the QB changes

**Status:** design (2026-08-12). Owner-approved direction: **no-huddle is a consequence of the clock, not a coach preference**; audibles are a **QB-attribute** contest against the defense's alignment.

Two gaps, one shared root: **the offense has no presence between the whistle and the snap.** Everything in that window today is the COACH's, resolved as a single number.

## What exists today

**Tempo is one function and three intents.** `Game._classifyTempoIntent` (`floosball_game.py:~10662`) returns `('hurryUp' | 'burnClock' | 'neutral' | 'setupFG', baseTime)`, and `calculatePreSnapTime` scales that base by the coach's `clockManagement` (±3s across the IQ range). The result is consumed once per play in the PRE-SNAP block (`~:7529`) via `consumeGameTime(preSnapTime)`.

So "hurry-up" means **a 12-second huddle instead of a 25-40 second one**. The team still huddles. There is no state in which they do not, and the players have no say in how long it takes.

**The QB does nothing before the snap.** `_applyPreSnapRead` (added with the pre-snap recognition layer) has the DEFENSE committing run-or-pass before the play resolves, with accuracy from the D-coach's `defensiveMind` (60%) and the on-field readers' `instinct`/`focus` (40%), minus a per-fake disguise penalty (`PRESNAP_DISGUISE`: rpo .30 / trick .32 / sneakLook .28 / playAction .22 / draw .24). That is a real per-play decision by the defense — and **the offense has no equivalent**. Every deception in the sim is an offensive EXECUTION roll against the defense's standing gameplan numbers; nothing lets the quarterback look at what he sees and change it.

**Attributes already sized for this and barely used.** `xFactor` and `creativity` were nearly inert until runner moves and punt placement retro-fitted them through `flairOf()`. `instinct` and `focus` currently feed the DEFENSE's pre-snap read (as the LB/S) and almost nothing on the offensive side. An audible is the natural consumer.

---

## Part 1 — No-huddle

### The trigger is the clock, not the coach

Owner's rule, and it is better than a coach preference because it needs no new tuning knob:

> **If the clock did not stop on the last play and the offense is in hurry-up, the next play is no-huddle. If the clock stopped, they may huddle.**

That falls straight out of state the engine already has: `self.clockRunning` after the previous play, and the `hurryUp` intent from `_classifyTempoIntent`. No new decision, no new coach attribute — a running clock in a two-minute drill *is* the reason you stay at the line.

It also composes correctly with what shipped this week: the Q2 end-of-half drill now fires at any score, so no-huddle inherits that window for free rather than needing its own score logic.

**Interaction with the timeout.** `_maybeCallTimeoutToSaveSnap` (`~:2257`) already spends a timeout when the huddle would burn the clock before the snap. No-huddle is the cheaper alternative to that: **check no-huddle first, spend the timeout only if even the no-huddle snap does not fit.** Otherwise the offense burns three timeouts doing what standing at the line would have done free.

### The cost model

The point of no-huddle is that the pre-snap drain nearly vanishes:

| state | pre-snap | why |
|---|---|---|
| huddle, neutral | 25-40s | as today |
| huddle, hurry-up | ~12s | as today (`LAST_SNAP_HUDDLE_SECS`) |
| **no-huddle** | **~5-8s** | line up and go; QB calls it at the line |

⚠️ **This directly changes `_lastSnapBeforeBreak`.** That helper computes "is there a snap after this one" from `LAST_SNAP_HUDDLE_SECS + LAST_SNAP_LIVE_SECS + FINAL_SNAP_SECS`. If a no-huddle snap costs 6s instead of 12, the running-clock window drops from ~19s to ~13s, and the helper must read the tempo state rather than assume a huddle. Same for `_estimateAvailablePlays`, whose per-play charge is already known-wrong (see below).

### The playbook shrinks — and that is the trade

Owner: *"exclusively short-medium passes that target the sideline to stop the clock"*, and *"the plays that can be called are limited here."*

No-huddle menu:
- **`short` and `medium` passes only.** `long`/`deep` need protection and a route stem the offense has not lined up for; `PASS_DEPTH_MEANS` already gives the four tiers.
- **Sideline targeting forced on.** `_shouldTargetSideline` currently returns a probability; in no-huddle it is the point of the play, so it is set, not rolled.
- **No run concepts, no trick plays, no RPO, no sneak-look.** Every one of those is a huddle call. `_selectSneakLook` and the trick-play selectors should decline outright in no-huddle rather than be weighted down.
- **QB sneak stays available** on the short-yardage trigger — it is the one run that needs no call.

⚠️ **THE RESTRICTION IS THE BALANCE, NOT A LIMITATION TO ENGINEER AROUND.** A no-huddle offense buys ~6 seconds a snap and pays by being predictable — and the sim already has the mechanism to charge for that. `_applyPreSnapRead` is the defense committing run-or-pass; a no-huddle offense that can only throw short should hand the defense a large **negative disguise** (the mirror of `PRESNAP_DISGUISE`), so a sharp defensive staff reads it and the drill costs yards per play. That is what stops no-huddle being a free win and makes `defensiveMind` matter in the two-minute drill, which is exactly where a fan would expect it to.

### Where it hooks

1. `Game._classifyTempoIntent` — return a fourth intent `noHuddle` (or a companion flag; a flag is likely cleaner since the existing intents map to huddle LENGTHS and this is a different axis).
2. `calculatePreSnapTime` — the reduced drain.
3. `playCaller` — restrict the menu when the flag is set, before `_computePlayWeights`.
4. `_shouldTargetSideline` — forced true.
5. `_applyPreSnapRead` — negative disguise for a telegraphed no-huddle.
6. `_lastSnapBeforeBreak` / `_estimateAvailablePlays` — tempo-aware snap cost.
7. PBP — the feed should say the offense is at the line without huddling; it is one of the most legible things in real football and currently invisible.

---

## Part 2 — Audibles

### The shape

An audible is the **offensive mirror of `_applyPreSnapRead`**: the QB looks at how the defense is set and changes the call. The defense's version is already built and measured, so this is a symmetric addition rather than a new subsystem.

**The read.** The QB is trying to detect the defense's *commitment* — the same `runStopFocus` / `blitzPackage` / `coverageType` the scheme already exposes via `gameplan.getDefensiveScheme()`, which is in scope at resolution in both `runPlay` and `passPlay`.

**Accuracy, from the QB directly** (owner: *"this can use QB attributes directly"*):

| term | attribute | note |
|---|---|---|
| recognition | `instinct` | the primary read — does he see it |
| composure | `focus` | does he see it under a clock |
| improvisation | `creativity` + `xFactor` | via the existing `flairOf()`, shared with runner moves and punt placement |
| staff | coach `offensiveMind` | secondary — he installed the checks |

Weighting to settle in build, but the QB should dominate: this is the one place in the sim where the player, not the coach, makes the call. Suggest QB ~70% / coach ~30%, the inverse of the defense's read (which is coach 60 / players 40) — and that asymmetry is the point.

**The outcome.** Three, not two:
- **Good check** — the call flips to something that beats what he saw (run into a light box, quick game into a blitz, a sneak into a soft front). Small edge.
- **No check** — he does not see it, or does not like his options. Play as called.
- **Bad check** — he checks INTO the defense's strength. This is what makes it a skill rather than a bonus, and it is where a low-`instinct` QB with high `xFactor` should live: bold and wrong.

⚠️ **An audible must be able to LOSE.** The sim's existing deception layers all follow this (`conceptTelegraphed`, the diving catch, runner moves) and it is why they read as football rather than as buffs.

### Where it hooks

Between play selection and resolution — after `_executeWeightedPlay` has chosen, before `runPlay`/`passPlay` resolve, and **after** `_applyPreSnapRead` has fixed the defense's commitment, so the QB is reading a decision that has actually been made.

⚠️ **Order matters and creates a real interaction.** If the QB audibles out of a run into a pass AFTER the defense has committed to run, that is the payoff. The two layers together give a genuine pre-snap game: the defense guesses, the QB reads the guess, and the better staff/player wins more often. Neither layer alone does that.

### Interaction with no-huddle

They compose, and this is the reason to build them together: **no-huddle is what creates the audible opportunity.** In a huddle the call is made in the huddle; at the line it is made by the QB. So no-huddle should raise the audible rate substantially — and since no-huddle also hands the defense a read (above), a QB who can check out of it is the counter to the counter. That is a three-layer loop with no new mechanic:

> defense reads the telegraphed no-huddle → QB reads the defense's commitment → the check beats it, or does not.

---

## Part 3 — Defensive disguise (the reason any of this is interesting)

**Owner direction, 2026-08-12:** *"defenses start getting into deception, making the QB think they're doing one thing and then do something else, and bad QBs can audible into a trap, smart QBs can sniff it out. this is where coach defensive mind can really shine."*

This is the piece that turns Parts 1 and 2 from two features into a system. Without it, the QB reads an honest defense and an audible is just a skill check the good QB always passes.

### Split what the defense SHOWS from what it DOES

`_applyPreSnapRead` today has the defense committing (`isRun` guess) and being right or wrong. Add one field above it: the **shown look**, which may be a lie.

```
scheme['commit']  = what the defense is actually doing   (exists today)
scheme['shows']   = what it is standing in to look like  (new)
```

Two classic disguises, and they are the two the scheme dict can already express:

| shown | actual | the trap it sets |
|---|---|---|
| **blitz** | coverage drop (fire zone) | QB checks to quick game / hot route into a defense that dropped eight |
| **soft coverage** | pressure | QB checks to a longer developing play with no protection for it |

### Who can lie, and what it costs

⚠️ **A DISGUISE MUST COST SOMETHING, OR EVERY DEFENSE DISGUISES EVERY PLAY.** The offensive concepts already follow this rule — a high-deception concept is high-ceiling but risky with the wrong personnel — and the defense gets the same treatment:

- **The call** is the D-coach's `defensiveMind`. A sharp staff installs and calls disguises; a poor one plays what it lines up in. This is the attribute finally doing per-play work on the side of the ball it is named for.
- **Holding the look** is the defenders' `discipline` and `focus` (both real attributes; `discipline` already carries 40% weight in the player's own professionalism composite and resists runner moves). A disciplined unit holds the disguise to the snap; an undisciplined one **tips early**, and a tipped disguise is worse than no disguise at all — the QB now has a free read AND the defense has committed late.
- **The cost of being wrong** is alignment. A defense that shows blitz and drops is, for that play, slightly out of position against what it did not prepare for. So disguise should carry a small execution penalty when the offense runs a play the disguise did not anticipate.

That gives `defensiveMind` a genuine two-sided role: **reading the offense's intent** (already built) and **hiding its own** (this). A defense strong in one and weak in the other should feel different to play against, which is what makes coaches worth scouting.

### The three-body resolution

Order matters, and this is the whole design:

1. **Defense picks its commitment** — run/pass, blitz/coverage (today's `_applyPreSnapRead`).
2. **Defense picks its shown look** — honest, or a disguise it can afford.
3. **QB reads the SHOWN look** — not the real one. His `instinct` is what lets him see *through* it; `focus` is whether he can do that on a clock.
4. **QB acts, or does not** — `flairOf()` (`creativity` + `xFactor`) decides whether he pulls the trigger on what he thinks he sees.

The outcomes that fall out of this are exactly the ones asked for:

| QB reads | QB acts | result |
|---|---|---|
| sees through the disguise | audibles | **the payoff.** He checks into the real weakness, and a disguised defense is more vulnerable than an honest one because it committed to a lie |
| fooled | audibles | **the trap.** He checks into the defense's actual strength — worse than the original call |
| fooled | stands pat | the play as called, against a defense that wasted its disguise |
| sees through it | stands pat | a missed opportunity — a cautious QB leaving yards out there |

⚠️ **THE WORST CELL IS A CONFIDENT WRONG READ, AND THAT IS CORRECT.** A QB who never audibles is safer than one who audibles badly. That makes `instinct` gate whether he *should* try and `flairOf` gate whether he *does* — and a bold QB who cannot read becomes a genuine liability rather than a slightly lower number. It is the same shape as the runner-move model, where willingness and ability are deliberately separate terms.

### Interaction with no-huddle — the loop closes

No-huddle telegraphs pass (Part 1), which hands the defense a read. But a defense that is *reading* is also a defense that can be *baited* — and a no-huddle offense snapping fast gives the defense less time to disguise cleanly. So tempo cuts both ways, and neither side has a dominant strategy:

> fast tempo → defense reads pass more easily, but has less time to disguise it → the QB's read is easier but the payoff is smaller.

That is a real trade a good staff can play on both sides, with no new mechanic beyond the three already described.

### ⚠️ The over-engineering risk

This is four interacting layers resolving before the ball is snapped, and the sim's history says that is where calibration goes wrong (the run gate model took seven tuning passes; the first build ran ypc to 9.61). Guards:

- **Every layer independently flagged** (`NO_HUDDLE_ENABLED`, `AUDIBLE_ENABLED`, `DEFENSIVE_DISGUISE_ENABLED`) and independently measurable.
- **Zero-sum by construction where possible**, the way `_applyPreSnapRead` already is — a league-average defense nets nothing from disguise, so the layer redistributes rather than inflating. Measure the league-wide multiplier before shipping, exactly as the pre-snap read did (mean accuracy 0.5173 → 1.0016, i.e. 0.16% stronger defense league-wide).
- **Build the disguise LAST**, against an audible system already measured against honest looks. Otherwise a miscalibrated disguise and a miscalibrated audible mask each other.

## Measurement

The clock work this week established the pattern: a **low-variance targeted probe** beats a noisy aggregate. Per-arm, before/after:

1. **Tempo** — pre-snap seconds by state (huddle / hurry-up / no-huddle), and snaps per drive inside the last 2:00. The Q2 probe (`scratchpad/q2_tempo.py` shape) already does this and can be reused directly.
2. **Menu** — play-type distribution in no-huddle; confirm long/deep and concepts are absent and sideline rate is ~1.0.
3. **The trade** — yards per play in no-huddle vs huddled hurry-up. If it is not measurably LOWER, the predictability penalty is not landing and the drill is a free win.
4. **Audible** — rate, and the split of good / no / bad checks by QB `instinct`. If a poor QB is not visibly worse off, the read is not doing work.
5. **Disguise** — rate, and the split of QB outcomes against a disguised look versus an honest one, by QB `instinct`. The trap cell (fooled + audibled) must be measurably WORSE than standing pat, or the mind game has no teeth. Also the league-wide multiplier: a league-average defense should net ~1.0 from disguise, the way the pre-snap read nets 1.0016.
6. **Guardrail** — league scoring and end-of-half points. ⚠️ The rating-multiplier → win-probability transfer is **1.619**, so a layer that looks small can move wins hard; measure before tuning.

⚠️ **`_estimateAvailablePlays` is a known landmine here.** It counts a play that does not fit (documented in the engine), and no-huddle changes the per-play cost it is silently wrong about. Any tuning of it must be done across all eight call sites at once — tightening it alone measured WORSE (late FG attempts 33 → 18). Best handled as its own pass, after no-huddle lands, when the true per-play cost is actually known per tempo state.

---

## Build order

1. **No-huddle tempo + cost.** Trigger, reduced drain, tempo-aware `_lastSnapBeforeBreak`. Measure 1.
2. **No-huddle menu.** Restriction + forced sideline. Measure 2.
3. **The predictability penalty.** Negative disguise in `_applyPreSnapRead`. Measure 3 — this is the balance gate; do not proceed while no-huddle is a free win.
4. **Audibles against HONEST looks.** The read, the three outcomes, measured while the defense is still telling the truth. Measure 4.
5. **Defensive disguise.** Shown-vs-actual, its cost, and the trap. Measure 6 — and only here, because a miscalibrated disguise and a miscalibrated audible mask each other.
6. **PBP + play insights** for all three, so a reader can see it happen and a future investigation can read the decision. A disguise that worked should be visible in the feed; that is most of the drama.

Flags: `NO_HUDDLE_ENABLED`, `AUDIBLE_ENABLED`, `DEFENSIVE_DISGUISE_ENABLED`, each default-on once measured, so any one can be switched off for an A/B without unpicking the others.

---

## Open questions (owner)

1. **Does a bad QB decline to audible, or audible badly?** Declining is safer and more realistic; audibling badly is more fun and gives `xFactor` somewhere to hurt. Current lean: **both**, split by `instinct` (sees it or not) vs `flairOf` (acts on it or not) — a bold QB who cannot read is the interesting failure case.
2. **Should no-huddle be available OUTSIDE a two-minute drill?** Real offenses use it as a tempo weapon on any down. The clock-driven trigger says no. A `hurryUp`-only rule is simpler and matches the reported need; a coach-preference version is a later layer and would need its own attribute.
3. **Does the defense get to substitute?** Real no-huddle's edge is that it prevents defensive personnel changes. The sim has no personnel packages, so there is nothing to model — noting it so it is not mistaken for an oversight.
4. **Should a disguise be visible to the READER even when it fools the QB?** The feed knowing more than the quarterback is where the drama is ("they showed blitz and dropped eight, and he never saw it"), but it also tells a fan the answer before the play resolves. Lean: reveal it in the play-by-play AFTER resolution, never before.
5. **Can the offense bait too?** A QB who reads a disguise could hard-count to make the defense declare. That is a fourth layer and almost certainly a step too far — noting it so it is a deliberate omission rather than an oversight.
6. **Fatigue.** No-huddle should tire the offense faster. The sim has a fatigue model applied pre-game; a within-game tempo cost is a separate piece of work and is out of scope here.
