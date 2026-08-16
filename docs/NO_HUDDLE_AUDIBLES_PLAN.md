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

## Part 4 — Pre-snap commentary (without this, none of the above exists)

**Owner direction, 2026-08-12:** *"there's a lot that is happening between plays that happens silently. there needs to be some kind of commentary going on between snaps that tells fans what is happening. the QB audibles, they start going no huddle, the defense is showing blitz, etc."*

⚠️ **THIS IS NOT POLISH, IT IS THE DELIVERABLE.** Parts 1-3 add three layers of decision-making that resolve entirely between the whistle and the snap, and the feed today reports only what happened AFTER the snap. Built without this, the whole system is invisible work: the QB audibles into a trap and the reader sees a 2-yard gain with no idea why. Every mechanic here earns its keep only if a fan can watch it happen.

### The plumbing already exists

`gameFeed` carries two entry kinds today — `{'play': ...}` and `{'event': {...}}`, the latter with `text` / `_type` / `quarter` / `timeRemaining` (see the chess-clock lockout and timeout announcers). The frontend already distinguishes them: `GameModalNew` filters on `!p.event` for the box score and the win-probability chart, and `isSidelineCutaway` is a third kind that renders differently again. So a pre-snap beat is **a new `_type` on the existing event entry**, not new plumbing.

It should also flow into the interleaved Bleachers timeline alongside the sideline cutaways, which already sort correctly by UTC timestamp.

### ⚠️ The reveal rule — this settles the open question

The pre-snap line reports **what the QB SEES, including when that is a lie.** The truth arrives with the play.

> *"They're showing blitz..."* → snap → *"...and they dropped eight. Rodrigo never saw it."*

That is the whole design in two lines, and it means the pre-snap commentary is never a spoiler. **The reader is fooled alongside the quarterback and learns the truth alongside him**, which is strictly better drama than either revealing early (no tension) or never revealing (no payoff). It also means the same line can be honest or a lie with no change to the writer's side — the disguise decides, not the phrasing.

### Cadence — silence is the default

A line on every snap is noise, and would bury the play-by-play it sits next to. Pre-snap beats fire only on a **state change or a decision**, not on a state:

| beat | when | fires |
|---|---|---|
| going no-huddle | on ENTERING the state | once, not every snap in it |
| defense shows blitz / soft | when a disguise is shown | rate-limited; not every disguised snap |
| QB audibles | on a check, either way | always — it is the most interesting thing that can happen pre-snap |
| QB sniffs it out | on a good read against a disguise | always, and this is the line that sells `instinct` |
| defense tips its hand | on a blown disguise (`discipline` failed) | always — the reader should see the mistake |

Everything else stays silent. ⚠️ The Bleachers taught this lesson already: an exchange per beat buried a busy week under the Cores talking to themselves, and the fix was one exchange per tick taking the most significant crossing. Same rule here — **at most one pre-snap line per snap**, taking the most significant.

### What it unlocks beyond this plan

- **`defensiveMind` becomes visible.** It currently does per-play work that no reader can see. A defense that disguises well and gets caught doing it is a coach with a personality.
- **Anticipation.** The sim has no tension between plays at all right now; the feed goes from result to result. A "they're showing blitz" line is the first thing that makes a reader wait for the next snap.
- **It is where personality could land later.** A cocky QB and a rattled one should audible differently, and `personalityManager` already voices players. Out of scope here, noted so the hook is deliberate.

### Where it hooks

1. A `_presnapBeat()` writer alongside `formatPlayText` / `_puntPlayText`, taking the tempo state, the shown look and the audible outcome.
2. `gameFeed.insert(0, {'event': {'_type': 'presnap', ...}})` in the PRE-SNAP block (`~:7529`), after the tempo and read are resolved and BEFORE the play executes — so it lands in the feed ahead of its own play.
3. `play.insights` carries the structured version (shown vs actual, read outcome) for the insights panel and for any future investigation.
4. Frontend: render it lighter than a play — it is a state, not a result. The `schedule` band treatment in the league news feed is the closest existing precedent.

⚠️ **The broadcast path must be checked.** `_presnapBeat` fires between plays, and the timing modes that suppress game events (`turbo-silent`, `fast-weekly`) must suppress these too, or a silent sim starts narrating.

### ⚠️ Two delivery mechanisms, not one (owner, 2026-08-16)

The audible and no-huddle beats are **prepended to the play text**, not emitted as their
own feed entry:

> *"Rodrigo Vance calls an audible! Hands off to Tuck Marlow for 6 yards."*
> *"Buffalo goes no-huddle. Quick out to Sim Pallas for 8."*

**This is better than a separate entry for these two, and the reason is the reveal rule.**
An audible and a tempo change are FACTS about what the offense did. They are not lies, so
there is no tension to preserve between the beat and the outcome — putting them in one
sentence loses nothing and reads better.

It is also structurally cheaper, in ways that matter:

- **One hook.** `self.play.playText = text` (`floosball_game.py:6621`) is the single
  assignment point, and every play type flows through it — `_puntPlayText` returns into
  the same `text` variable, so punts are covered without a second site.
- **No broadcast-suppression path.** The plan flagged that `turbo-silent` and
  `fast-weekly` must suppress pre-snap beats or a silent sim starts narrating. A prefix
  rides its own play, so those modes already handle it. A separate feed entry would need
  its own guard.
- **Cannot be orphaned or mis-sorted.** The beat is physically attached to the play it
  describes; a separate entry has to be ordered correctly against it.
- **The one-line-per-snap cadence rule enforces itself** — one play text, one prefix.

⚠️ **IT DOES NOT EXTEND TO THE DISGUISE BEAT.** "They're showing blitz" is a LIE that the
play text exists to reveal. Prepending puts the lie and its reveal in the same sentence,
read at once, and the tension the reveal rule was designed around evaporates:

> prepended:  *"The defense shows blitz! They dropped eight and Vance never saw it."*
> as written: *"They're showing blitz…"* → snap → *"…and they dropped eight."*

So **Part 3 keeps the separate pre-snap entry** described above. That splits the work along
its natural seam: Parts 1-2 get the cheap prefix, Part 3 gets the entry it actually needs.

⚠️ **No-huddle announces on ENTERING the state, once.** The cadence table already says so,
and a prefix makes it easy to get wrong — a six-play drill would otherwise say "goes
no-huddle" six times. Needs a latch cleared on possession change and on leaving the state.

⚠️ **When both would fire on one snap, the audible wins.** They can collide only on the
first no-huddle snap (since no-huddle announces once), but the rule has to exist: an
audible is the more significant event, and the cadence rule is one line per snap.

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
6. **Pre-snap commentary (Part 4).** ⚠️ Not last in importance — it is what makes 1-3 exist for a reader, and it should be built incrementally ALONGSIDE each layer rather than saved up: a no-huddle line with Part 1, an audible line with Part 2, the disguise lines with Part 3. Saving it to the end means three layers land invisible and unverifiable by eye.

Flags: `NO_HUDDLE_ENABLED`, `AUDIBLE_ENABLED`, `DEFENSIVE_DISGUISE_ENABLED`, each default-on once measured, so any one can be switched off for an A/B without unpicking the others.

---

## Open questions (owner)

All settled 2026-08-16, against measurements taken on the production roster (34 active
QBs) and a 1,620-sample sweep of the tempo classifier's state space.

### 1. Does a bad QB decline to audible, or audible badly? — **SETTLED: both, and the
willingness term is `_undiscipline`, NOT `flairOf`**

⚠️ **`flairOf` COLLAPSES THE GRID, because willingness and reading ability are the same
axis in this league.** Measured correlation with `instinct` across 34 QBs:

| candidate willingness term | r with `instinct` |
|---|---|
| `flairOf` (creativity + xFactor) | **+0.77** |
| focus | +0.74 |
| creativity | +0.74 |
| xFactor | +0.65 |
| `discipline` | **+0.42** |

Every QB mental attribute correlates 0.65-0.77 with every other, because generation makes
good players good at everything. So the 2x2 the design depends on lands almost entirely on
its diagonal, and the mind game degenerates into a rating check — good QBs audible well,
bad QBs do not audible.

The resulting grids, same 34 QBs, split at the median of each term:

| cell | willingness = `flairOf` | willingness = LOW discipline |
|---|---|---|
| bold + sharp | 44% | 24% |
| **bold + blind — THE TRAP** | **6%** | **26%** |
| cautious + sharp | 9% | 29% |
| cautious + blind | 41% | 21% |

⚠️ **The direction is why this works, not merely the weaker correlation.** Willingness is
LOW discipline, and discipline correlates *positively* with instinct — so willingness
correlates NEGATIVELY with reading ability. Sharp QBs tend to be disciplined and stand pat;
blind QBs tend to be gunslingers and check anyway. The trap becomes a common outcome
rather than a 6% rarity, and all four cells are populated.

**Use the existing `_undiscipline`** (`floosball_game.py`, `(80 - discipline) / 20` clamped
0..1). Its docstring already describes this exact job — *"0 (controlled) .. 1 (gunslinger).
The gate that turns confidence into either production or chaos."* No new helper, and no
inversion of the attribute's meaning: it is already the sim's will-do-something-risky term,
carried by runner moves as the risk of attempting.

⚠️ **`flairOf` is therefore NOT the audible's willingness gate.** If creativity/xFactor
should still consume here, put them on the QUALITY of a good check rather than on whether
he pulls the trigger — otherwise they re-introduce the correlation through the back door.

### 2. Should no-huddle be available OUTSIDE a two-minute drill? — **SETTLED: no, keep the clock trigger**

Measured over 1,620 sampled game states:

| quarter | hurryUp | burnClock | neutral |
|---|---|---|---|
| Q1 | **0.0%** | 0.0% | 100% |
| Q2 | 13.3% | 0.0% | 86.7% |
| Q3 | 14.8% | 3.7% | 81.5% |
| Q4 | 14.8% | 29.6% | 55.6% |
| all | **10.7%** | 8.3% | 80.9% |

⚠️ That is STATE-SPACE coverage, not play coverage — real games do not spend equal time in
every cell, and since Q1 is 0% the true play share is likely LOWER than 10.7%.

⚠️ **Only Part 1 lives in that window.** Audibles and defensive disguise are not gated on
no-huddle; they fire on every snap. So the narrow window bounds the tempo feature, not the
system. Part 1 is also the cheapest piece (see the build note on `_lastSnapBeforeBreak`
below) and the most legible thing in real football, so it does not need to carry the rest.
A coach-preference version needs its own attribute and is tuning surface for a marginal
gain.

### 3. Does the defense get to substitute? — **SETTLED: nothing to model**

Re-confirmed 2026-08-16. No personnel packages exist. Deliberate omission, not an oversight.

### 4. ~~Should a disguise be visible to the READER even when it fools the QB?~~ — **SETTLED by Part 4**

The pre-snap line reports what the QB SEES (the lie included) and the play text reveals the
truth. The reader is fooled alongside him and learns with him.

### 5. Can the offense bait too (hard count)? — **SETTLED: no**

Four layers already resolve before the snap, and the plan's own over-engineering warning
applies hardest here (the run gate model took seven tuning passes; its first build ran ypc
to 9.61). A fifth reciprocal layer buys a rare moment for real calibration risk. Deliberate
omission.

### 6. Fatigue — **SETTLED: out of scope, structurally**

⚠️ Not a scoping preference. Fatigue is applied ONCE pre-game from a season-accumulated
value and never mutates during a game, so there is no within-game fatigue state for a tempo
cost to attach to. Adding one is a separate subsystem.

---

## ⚠️ Build notes added 2026-08-16 (the code moved after this plan was written)

Verified against `floosball_game.py`: all nine hooks named above still exist.

**Item 6 of Part 1 is HALF BUILT.** The chess-clock fix (2026-08-13) already made
`_lastSnapBeforeBreak` tempo-aware — but only in its chess-clock branch, which reads
`_intent, huddle = self._classifyTempoIntent()` and charges that huddle. The
standard-format branch still charges a flat `LAST_SNAP_HUDDLE_SECS` (12) regardless of
tempo. So the pattern to copy is already in the file, and the remaining work is one branch.

**⚠️ DO NOT change `_classifyTempoIntent`'s return arity.** Three sites unpack it as a
2-tuple, including that chess-clock branch, which was written after this plan. The
no-huddle state is derivable anyway (hurry-up AND the clock did not stop), so it wants a
separate `_isNoHuddle()` helper rather than a fourth intent or a changed signature — and
that gives the menu restriction, the disguise penalty and the snap cost one thing to read.

**⚠️ The measurement harness this plan leans on is GONE.** Part 1's measure cites
`scratchpad/q2_tempo.py`; scratchpads are session-scoped and no `simcheck_*tempo*` survives
in the repo. Since step 3 is the balance gate (*"if no-huddle yards per play is not
measurably LOWER, the drill is a free win"*), rebuild the probe as part of step 1 rather
than discovering it missing at step 3. `scenario.py` is the right instrument — it builds a
real `Game` in a target state and was used for the tempo sweep above.
