# The QB under pressure, and marking the plays only good players make

**Status:** measured, not started. **Parts II and III are superseded in part by Part V** —
owned skills become the archetype, and they dissolve Part II's gate problem. Two requests (owner, 2026-08-28), and they turn out to
be the same goal approached from two sides — **making a player's quality visible in the
feed** — which is also what `docs/FIELD_GRAPHIC_PLAN.md` concluded its whole feature was
for. These are the cheap versions of it.

---

# Part I — What a quarterback does when there is nowhere to throw

## The report

> "I haven't been seeing QBs throw the ball away very much anymore. QBs used to throw the
> ball away if there was nobody open and they were getting pressured heavily. What happens
> when either there's nobody open or there's heavy pressure? Does the QB hold the ball too
> long and run into a sack? Force a throw and risk an interception? Immediately throw it
> away? Escape the pocket and find a receiver on the run? Pull it down and run? Escape and
> throw it away? **Who the QB is should determine what they do here.**"

## ⚠️ Measured: the throwaway is ~10x too rare, and it is not a pressure decision at all

Over 30 games / **2,508 dropbacks**:

| outcome | share of dropbacks |
|---|---|
| complete | 72.5% |
| incomplete | 22.8% |
| sack | 2.9% |
| **throwaway** | **0.4%** |
| interception | 0.8% |
| scramble | 0.6% |

`selectPassTarget`'s own comment names the target: *"real NFL throwaway rate is ~3-5% of
attempts"*. It is running at **0.4%** — an order of magnitude under the number the code
says it is calibrated to.

⚠️ **AND PRESSURE IS NOT AN INPUT.** The signature is
`selectPassTarget(targetList, qbVision, qbDiscipline, mustThrow, aggression)` — there is no
`rushDifferential`, no pressure term, nothing about the pocket. So the second half of the
owner's sentence, *"and they were getting pressured heavily"*, **cannot be modeled today**:
the decision literally cannot see it. The throwaway is a pure coverage decision.

## Why it is so rare

Two gates in series, and the first swallows nearly everything:

1. The target loop returns the most-open receiver on a **"force it anyway" roll** that
   runs `50 + aggrBonus` at discipline 90+, `70` at 75-89, `85` at 60-74, and **`95` below
   60**. A low-discipline QB therefore almost never reaches the bail branch at all.
2. The bail itself requires `qbDiscipline >= 80` **and** `topOpenness < 50 - aggression·k`.

Measured by discipline band:

| band | dropbacks | throwaway | sack | scramble |
|---|---|---|---|---|
| 90+ | 41 | 2.4% | 2.4% | 2.4% |
| 80-89 | 1,397 | 0.3% | 3.3% | 0.7% |
| 70-79 | 1,070 | 0.5% | 2.4% | 0.4% |

⚠️ **The 70-79 band should be structurally incapable of throwing it away** — it is below
the `>= 80` gate — yet it shows the same rate as 80-89. Those are not decisions: they are
`selectedTarget is None`, the empty-target-list path. So **almost every throwaway in the
sim today is an accident of having no targets, not a quarterback choosing.**

## ⚠️ WHY THIS PART WAS THIN: the pocket has no TIME, so "held it too long" cannot exist

The owner's list is not six branches of one choice. Read it again and it is a **sequence** —
what a quarterback does at different POINTS in a collapsing pocket:

| when | what |
|---|---|
| immediately | first read gone, pressure already there → throw it away |
| middle | slide, climb, escape the pocket |
| late | tuck and run, or force it into coverage |
| too late | **the sack** |

⚠️ **THE SIM HAS NO WITHIN-PLAY CLOCK, SO EVERY ONE OF THOSE IS THE SAME INSTANT.**
`dropbackDepth` is a property of the PLAY CALL (3-step / 5-step / 7-step), not of what the
QB does, and `calculateSackProbability` fires **once**, before the throw resolves. There is
no duration, no degradation, nothing that "too long" could be long relative to.

So a plan that says "one `_qbUnderDuress` decision picking between six outcomes"
degenerates into a weighted pick — which is what the first draft of this part proposed, and
why it reads thin against Parts V-VII. **The phenomenon is a progression and the model was
a coin with six faces.**

## The fix: give the pocket gates, the way the run game got them

⚠️ **THE RUN GAME ALREADY SOLVED THIS EXACT PROBLEM AND THE PASS GAME NEVER GOT IT.**
`_resolveRunGates` replaced "a flat pass/fail cascade in which a broken tackle was a
post-hoc yardage bonus" with three staged contests where **the carrier's state carries
between them** — clean, contacted, fought. That is the same shape a pocket needs, and the
same reason: a single roll cannot express a sequence.

**Pocket phases, not a real-time clock.** Three discrete phases, each with a read and a
decision, state carrying forward:

| phase | the pocket | what the QB can do |
|---|---|---|
| **1 — clean** | protection holding | work the progression normally |
| **2 — pressured** | edge is loose | throw it away · check down · **escape** (skill) · hold |
| **3 — collapsing** | it is gone | force it · **tuck and run** (skill) · **escape and throw** (skill) · go down |

⚠️ This is deliberately NOT the real-time spatial model that `FIELD_GRAPHIC_PLAN.md` costed
and deferred. Three phases is enough to make "too long" mean something — a QB who is still
holding at phase 3 held it too long, and that is a fact the feed can state — without any of
the geometry.

**Where each phase comes from** — and note that this is what finally consumes Part IV's
most-wasted attribute:

- **`blocking`** sets how fast the pocket degrades. 37 distinct values, **read once** in the
  entire engine today, and it is the natural source of the pressure signal this part has
  been missing from the start. One inert attribute and one absent input are the same hole.
- **`dropbackDepth`** biases the starting phase, as it already biases the sack roll.
- The defense's rush rating moves the transition odds, as it already moves the sack.

## ⚠️ And the outcomes are SKILLS — this part predates Part V and was never reconciled

Two of the owner's six outcomes are already in the Part V catalogue by name: **tuck and
run** and **escape and throw**. They should not be a bespoke branch inside the passing code;
they are owned abilities like a stiff arm, subject to the same rules:

- **Not everyone has them.** A QB without *escape and throw* cannot make that play, which is
  what makes quarterbacks differ under pressure without a personality table saying so.
- **They fire on a LOSS.** The pocket collapsing IS the lost contest, so the post-loss save
  model applies unchanged — no second mechanic.
- **The player still has to reach** (Part VI), so a checked-out QB with the skill goes down
  anyway.

⚠️ **THE SACK IS THE ANTI-SKILL, AND THAT FALLS OUT RATHER THAN BEING WRITTEN.** A QB who
reaches phase 3, owns nothing, and is not composed enough to bail has one outcome left. The
owner's *"take the sack — kind of an anti-flair, mostly for low rated players"* is not a
behavior to implement; it is **what remains when every other option is absent**. Which is
also why it correctly reads as a low-rated trait without the archetype being a rating proxy
(Part III).

## Calibration guardrail

⚠️ Raising throwaways necessarily lowers something else. Completion rate is already **72.5%
against a real-world ~65%**, so the honest source is *forced throws that currently complete*
— not sacks. Watch the interception rate too: a throwaway is the alternative to a bad
decision, so if picks do not move at all, the forcing branch is not being reached.
`SACK_PROB_CAP` was retuned once by chasing a mean while the tail was the fault; measure the
distribution.

---

# Part II — Marking the plays only good players make

## The report

> "It's really hard to see when players are making plays, and what separates better
> players from average ones. There are things players do — stiff arms, hurdling, diving,
> reaching for yards — based on attributes like xFactor or creativity. It would be
> interesting to mark plays where a player did something out of the ordinary, similar to
> clutch or choke."

## ⚠️ Measured: these are FAR too common to mark as-is

Over 20 games / 3,090 plays:

| act | per game | share of plays |
|---|---|---|
| runner move attempted | **17.85** | 11.6% |
| ...succeeded | 14.65 | 9.5% |
| stiff arm | 9.40 | 6.1% |
| spin | 6.15 | 4.0% |
| hurdle | 2.30 | 1.5% |
| stretch for the marker | 6.25 | 4.0% |
| diving catch | 2.05 | 1.3% |
| **existing clutch marker** | **0.30** | 0.19% |
| **existing choke marker** | **0.05** | 0.03% |

**A flair act happens roughly 24 times a game. Clutch fires 0.3 times.** Marking every
stiff arm would put a badge on one play in nine — which is not a highlight, it is
wallpaper, and it would drown the clutch marker that already works.

⚠️ **So the whole design problem is the GATE, not the plumbing.** The plumbing already
exists and is proven: `play.isClutchPlay` / `clutchPerformers` / `chokePerformers` ride the
play payload and `GameModalNew.tsx` already renders them. A skill marker is the same
mechanism with a different trigger — which is why this is the cheap version of the field
graphic rather than a second system.

## What "out of the ordinary" should mean

Clutch keys off a **mental-state swing**. The analogue here is not "did something
audacious" — that is 24 a game — but **"did something a lesser player would not have
managed."** Three candidate gates, most likely combined:

1. **The margin was the player's own.** The move succeeded and the deciding term was the
   player's attribute rather than the roll — i.e. an average player at that position
   would probably have failed the same contest. This is the one that literally answers
   "what separates better players from average ones", and every one of these contests
   already computes the number it needs.
2. **Difficulty.** A hurdle (2.30/game) is four times rarer than a stiff arm (9.40) and
   should not be worth the same badge.
3. **Consequence.** The act produced a first down, a score, or an explosive gain. Free to
   compute and it is what a viewer would call a play.

⚠️ **Target rate: about 1-2 a game.** Enough that most games have one and it is worth
looking for, rare enough that it means something. That is 5-10% of flair acts surviving
the gate — so the gate has to be genuinely selective, and gate 1 is the one that carries
the meaning.

⚠️ **DO NOT REUSE THE CLUTCH BADGE.** They answer different questions — clutch is *mental
state under pressure*, this is *skill creating something*. A player can be both on one
play (a rattled star making a great move), and collapsing them would lose exactly the
distinction that makes either interesting. Separate flag, separate colour, same rail.

## Why this is worth doing before the field graphic

`FIELD_GRAPHIC_PLAN.md` measured that quality is invisible because watching the ball is a
biased estimator — the ball goes to whoever won, so a viewer never sees the 47% of
matchups that were lost. Its fix is a large rendering project.

**This is the same goal for a fraction of the cost.** It cannot show the losses, but it can
name the wins, attributably, in a rail that already exists — and it makes `xFactor` and
`creativity` visible for the first time, which is the reason the runner-move feature was
built (those attributes were "nearly inert in resolution" before it).

## Naming

Follows the house rules: formal or durable, one word preferred, timeless. `Clutch` and
`Choke` are the existing pair, so this wants to sit beside them without echoing them.
Candidates worth weighing rather than a recommendation yet — the mechanic should be built
first and named for what it actually rewards.

---

---

# Part III — Archetypes, and flair for the defense

**Owner, 2026-08-28:** an extended catalogue of flair plays, especially for QBs, and
**players should have archetypes** — "not all QBs will pull down the ball and run, some
might just throw the ball away, some might take the sack (kind of an anti-flair, mostly
for low rated players), some might roll out and try to make a play."

## ⚠️ First: defenders have NO flair today, so there is nothing to mark

Checked rather than assumed. `_flair()` is called **four times in the whole engine**, and
every subject is offensive:

| call | subject |
|---|---|
| runner move — elect | carrier |
| break-through | carrier |
| stretch for the marker | carrier |
| diving catch | receiver |
| `flairOf` — coffin-corner punt | kicker |

The only other reads of `creativity` / `xFactor` are `qbMobility` and a QB throw-quality
argument — offensive both — plus two attribute LISTS used for serialization, not
resolution.

⚠️ **AND THE ASYMMETRY IS SHARPER THAN "NOT YET DONE".** In the runner-move contest a
defender resists with `tackling × 0.65 + discipline × 0.35`: skill and composure, no
creativity, no xFactor. **Defenders are the thing flair is used AGAINST, never a thing
that has any.** They can nullify a hurdle; they cannot do anything a marker would notice.

So this is not a gate change, it is the same feature the runner moves were — those
attributes were "nearly inert in resolution", and that was fixed **for the offense only**.
The defensive half was never built. Candidate acts, each with a contest already in place
to hang off: jumping a route for the interception, the strip attempt at the tackle, a
gambling break on the ball that either takes it away or surrenders the completion.

⚠️ **`players.archetype` / `players.demeanor` DO NOT EXIST.** CLAUDE.md calls them
"legacy-nullable"; the columns are absent from the model and from a live database. The real
precedent for an assigned trait is `personality` (1 of 28) and `quirk` (1 of ~20).

## ⚠️ Measured: an archetype CAN be derived from attributes — but only from a CONTRAST

The obvious risk is that any attribute-derived archetype collapses into a rating ladder,
because generation makes good players good at everything. That risk is real and this
codebase has already been bitten by it (`flairOf` correlates **+0.77** with `instinct`,
which is why the audible grid uses `_undiscipline` instead). Measured over 32 production
QBs, every single attribute correlates with overall rating:

| | corr with rating |
|---|---|
| vision | +0.53 |
| instinct | +0.51 |
| xFactor | +0.47 |
| creativity | +0.39 |
| accuracy | +0.38 |
| discipline | +0.35 |
| agility | +0.33 |
| **pressure handling** | **−0.11** |

**So any single-attribute archetype is a rating ladder wearing a costume.** But the
attributes form two clusters that correlate **negatively with each other** (−0.20 to
−0.34): a MENTAL/pocket group (creativity, xFactor, discipline, instinct, focus, vision)
and a PHYSICAL group (agility, speed, accuracy). And the contrast between them is nearly
free of quality:

| axis | corr with rating |
|---|---|
| mental cluster alone | **+0.53** — a ladder |
| physical cluster alone | **+0.29** — a ladder |
| **mental − physical** | **+0.14** — a STYLE axis |
| **pressure handling** | **−0.11** — a second style axis |
| the two axes against each other | **−0.01** — genuinely independent |

⚠️ **THAT IS THE WHOLE DESIGN CONSTRAINT IN ONE LINE: build the archetype from the
CONTRAST, never from a cluster.** Both axes are rating-neutral and orthogonal to each
other, which is exactly what an archetype needs and what no single attribute provides.

The 2×2 populates on the live league, and the owner's four examples land in it
unprompted — which is the encouraging part, since the axes were chosen from the
correlation structure rather than from the list:

| quadrant | QBs | mean rating | what they do under duress |
|---|---|---|---|
| athlete / composed | 7 | 73.4 | rolls out and makes a play |
| athlete / rattled | 10 | 73.4 | pulls it down and runs |
| pocket / composed | 9 | 73.8 | throws it away |
| pocket / rattled | 6 | 79.7 | takes the sack |

Three of the four sit within 0.4 rating points of each other. The fourth is 6 higher on
**n = 6**, which is small-sample noise rather than signal — but it is the number to re-check
at league scale before committing.

### ⚠️ How to keep "taking the sack is for low-rated players" true anyway

The owner's intuition and rating-neutrality look contradictory and are not. Resolve it as:

> **The archetype decides WHAT you do under duress. The rating decides HOW OFTEN you are
> under duress at all.**

A well-rated pocket/rattled QB rarely faces a collapsed pocket with nobody open; when he
does, he goes down. A poorly-rated one faces it on a third of his dropbacks. The
sack-taker therefore reads as a low-rated trait in the box score — which is what a viewer
notices — without the archetype itself being a rating proxy. That also keeps the axis
honest: if archetypes were assigned by rating, every bad QB would be the same bad QB.

### Why derive rather than assign

`personality` and `quirk` are assigned strings, and that is right for flavor which should
not follow from ability. An archetype is different: it describes how a player *plays*, so
it should be readable off who they are — a scout looking at the attributes should be able
to see it coming, and a player's style should shift if their attributes shift with age.
Deriving it also means no column, no migration, and no generation change.

⚠️ Derive it **once per player per season and cache it**, not per snap: `_scoutError`
already sets the precedent that a belief re-rolled every call produces incoherent
behavior, and an archetype that flickers between snaps is the same failure.

---

# Part IV — Do we need new attributes? No. Eight already exist with no job.

**Owner, 2026-08-28:** "I also wonder if there are attributes we can add to flesh out
archetypes and flair for each player."

⚠️ **MEASURED, AND THE ANSWER IS THE OPPOSITE OF ADDING.** Comments and docstrings stripped
(prose like "reaches the marker" otherwise inflates `reach` from 11 to 65), here is how
hard each attribute actually works in `floosball_game.py`:

| attribute | reads | spread in the live league |
|---|---|---|
| `blocking` | **1** | 55-93, 37 distinct |
| `clutchFactor` | 2 | **0 for all 480 players — deprecated on purpose** |
| `resilience` | **2** | 33-100, 61 distinct |
| `selfBelief` | **2** | 32-100, 61 distinct |
| `attitude` | **3** | 32-100, 63 distinct |
| `creativity` | **3** | 60-100, 41 distinct |
| `luckModifier` | 3 | −5..+5, 11 distinct |
| `xFactor` | **3** | 52-100, 47 distinct |
| `routeRunning` | 5 | |
| `vision` | 6 | |
| `pressureHandling` | 7 | −10..+10, 21 distinct |
| `hands` / `determinationModifier` | 8 | |
| …then the workhorses | | |
| `power` | 30 | |
| `discipline` | 26 | |
| `agility` | 19 | |

**Eight attributes are read four times or fewer.** Three of them — `resilience`,
`selfBelief` and `attitude` — carry the **widest spreads in the entire set** (a 68-point
range across 61-63 distinct values) and are read **two or three times each**. That variety
is being generated, stored, shown on the player page, and then thrown away at resolution.

⚠️ **`blocking` is the single most wasted**: a whole skill dimension, 37 distinct values,
**read once**.

⚠️ **`clutchFactor` is NOT a candidate — it is deliberately dead.** `floosball_player.py`
hardcodes `self.clutchFactor = 0` with a comment saying the column is kept only so DB sync
does not break. Do not revive it on the strength of its name; the clutch marker that exists
is computed from mental-state swings, not from this.

## Why adding would make archetypes WORSE, not better

The archetype axes in Part III are built from `creativity` + `xFactor` (**3 reads each**)
against the physical cluster, with `pressureHandling` (**7 reads**) as the second axis. So
**the archetype work already IS the plan for putting inert attributes to work** — it is the
same project, and the runner-move feature was the first instalment of it ("xFactor and
creativity were nearly inert in play resolution before this").

Adding a ninth unused attribute does not create style. It creates another number on the
player page that nothing reads, and it dilutes the ones that could be carrying the
distinction. **The variety is already generated; the engine simply does not consult it.**

## What to give the inert ones, if a job is wanted

Each of these has a natural home in exactly the work Parts I-III describe, which is the
argument for using them rather than inventing more:

| attribute | the job it is missing |
|---|---|
| `resilience` | how a player carries a FAILED flair attempt — a missed hurdle should cost a brittle player more than a resilient one |
| `selfBelief` | whether they try again after failing one, this drive or this game |
| `attitude` | whether a flair act is selfish or situational (hero-ball vs taking what is there) |
| `blocking` | the pocket's integrity — which is precisely the pressure term Part I needs and cannot currently see |
| `luckModifier` | the coin-flip tail on an audacious act, where a small nudge is exactly right |

⚠️ **`blocking` is the one to do first**, because it is not merely underused — Part I
established that the QB duress decision **cannot see pressure at all**, and an offensive
line's blocking is the most natural source of that signal. One inert attribute and one
missing input turn out to be the same hole.

---

# Part V — Skills as owned abilities: what a player has learned

**Owner, 2026-08-28/29.** Players roll on BASE attributes (speed, power, agility, arm
strength, accuracy, hands, reach). On top of that they own **skills** — stiff arm, hurdle,
spin, one-armed catch, diving catch, stutter step, tuck and run, escape and throw — learned
at higher skill levels and unlockable in offseason training. **If a player LOSES the base
head-to-head, a skill can give them a boost to make the play anyway.** Average and
below-average players have one skill or none.

> "Players now have more than just attribute numbers — they have skills that they've
> learned, and fans can see what they are capable of."

## ⚠️ Why "lose first, THEN spend the skill" is the load-bearing part

It is not how the sim works today. A runner move is currently folded into the roll as a
PRE-EMPTIVE bonus (`carrierRating = bestVal + RUN_MOVE_BONUS`), one roll decides
everything, and `_miss` is a relabel applied afterwards. A post-loss save is materially
different and better on three counts:

- **It cannot inflate the baseline.** A player who WINS the contest never spends the skill,
  so league rates barely move and the recalibration is small. A pre-roll bonus lifts
  everything, which is why the run gates needed seven tuning passes.
- **It only fires in the moments worth watching.** The near-miss becomes the highlight.
- **It is legible.** "He lost that rep and got out of it anyway" is a sentence a fan can
  read; "+7 to his contact rating" is not.

## ⚠️ THIS DISSOLVES PART II'S ENTIRE PROBLEM

Part II's difficulty was that flair acts happen ~24 times a game — runner moves alone are
one play in nine — against a clutch marker that fires 0.3 times, so a badge on every stiff
arm would be wallpaper. The whole design there was the GATE: how do you pick the
exceptional ones out of the ordinary ones?

**Under this model the question disappears.** A skill only fires on a rep the player was
LOSING, so **every skill use is by construction a play they would otherwise have failed.**
There is nothing to select — the mechanic is its own filter. The marker becomes "a skill
fired", which is nameable ("stiff arm", "one-armed catch") rather than a generic badge.

Volume drops on two independent axes at once — ownership, and the loss condition — which
takes runner moves from 17.85 a game toward a few, exactly the band a marker wants.

## ⚠️ The rating trap, and why the owner's version does NOT fall into it

Part IV measured that every attribute correlates **+0.33 to +0.53** with overall rating, so
anything derived from attributes drifts into a rating ladder. Skills unlocked "at higher
skill levels" look like they should trip that — and they do not, because of the split the
owner drew:

> **Quality decides HOW MANY skills you have. Identity decides WHICH ones.**

That is the same resolution Part III reached for the sack-taker (archetype = what you do,
rating = how often you must). A 94-rated back has three skills and is genuinely more
capable; *which* three is who he is, and among the many players holding two, the pair is
the archetype. ⚠️ **Never let rating pick WHICH** — that is the version that collapses,
and it is the version where every elite back is the same elite back.

Offseason training choosing the unlock is ideal here: it makes the choice a player's own
history rather than a derivation, and it gives training something concrete to grant.

## Measured: what a skill-count curve does to the real league

192 rostered players, ratings 60-94 (p25 70, median 74, p75 80). A candidate curve —
**0 skills below 72, 1 at 72+, 2 at 80+, 3 at 88+**:

| skills | players | share |
|---|---|---|
| **0** | 62 | **32%** |
| 1 | 77 | 40% |
| 2 | 45 | 23% |
| **3** | **8** | **4%** |

**Eight three-skill players in the entire league.** That is rare enough that a fan could
name them, which is the point. And a third of the league owning nothing is a real
population rather than a rounding error — the baseline that makes the rest legible.

**64% of ball-handling starters would own at least one skill**, so roughly a third of
touches come from a player with no save at all.

⚠️ Both thresholds are design calls, not derivations. At 88 the top tier is 8 players; at
86 it would be perhaps twice that. Choose them against how often a fan should see something
special, then hold them — the curve is the feature.

## The three layers, and where the inert attributes land

This does not replace the flair model, it completes it — and it gives Part IV's unused
attributes their jobs:

| layer | decided by | question |
|---|---|---|
| the contest | base attributes | did you win the rep |
| the reach | `creativity` / `xFactor` | do you TRY something (3 reads each today) |
| **the save** | **the owned skill** | what you can try, and how well |
| the cost | `resilience` / `selfBelief` | what a FAILED save does to you, and whether you reach again |

## Catalogue — the acts that exist, and the ones that do not

| skill | today |
|---|---|
| stiff arm / spin / hurdle | BUILT, but **every carrier can elect all three** |
| diving catch | BUILT (`_diveCatch`), universal |
| stretch for the marker | BUILT, universal |
| coffin-corner punt | BUILT, `flairOf`-gated, universal |
| **one-armed catch** | ❌ |
| **stutter step** (receiver separation) | ❌ |
| **tuck and run** | exists as `_qbTucksAndRuns`, not owned |
| **escape and throw** | ❌ — escaping always ends in a run (Part I) |
| **any defensive skill** | ❌ — defenders have no flair at all (Part III) |

So the conversion is smaller than it sounds for the offense (the acts exist; ownership is
what is new) and is genuinely new work for the QB duress set and the whole defensive side.

---

# Part VI — The player still chooses, and right now that choice barely exists

**Owner, 2026-08-29:** the player still has to decide whether to reach for a skill —
"it's the difference between a completely locked in player and one who has checked out."

⚠️ That points at mental **STATE**, not the trait, and the code does not currently give it
that authority — in one of the two paths it gives it none at all.

## Measured: two election paths, and they disagree about whether state exists

| path | formula | state weight |
|---|---|---|
| `_runnerMove` | `0.05 + 0.18·flair + 0.06·state` | **0.06** |
| `_contactContest` | `0.18 + 0.55·flair` | **none** |

⚠️ **`flairOf` IS PURE TRAIT.** It is creativity + xFactor and nothing else. CLAUDE.md
describes willingness as *"`_flair` … plus mental state (`_confidenceState` +
`_determinationState`)"* — that is the DESIGN; the function never sees state. Only
`_runnerMove` adds it, separately, at `RUNNER_MOVE_STATE_K = 0.06`.

So a carrier at rock bottom and one on fire elect a move at **the same rate** whenever the
contest runs through `_contactContest`, and differ by at most **six percentage points**
elsewhere — against a flair term worth 18 to 55. "Locked in versus checked out" is
currently a rounding error on one path and literally nothing on the other.

⚠️ **The duplicated decision is a defect on its own merits**, independent of any redesign:
the same question is answered two ways and only one of them knows how the player feels.
Same class as the two copies of the transplant price.

## What Part VI needs

1. **Teach `_contactContest` to see state.** Non-negotiable — it is the path that cannot.
2. **Give state real authority.** At 0.06 it cannot express "checked out"; a genuinely
   disengaged player should approach *never reaching*, which means state must be able to
   drive the elect chance toward zero on its own rather than shading it.
3. **⚠️ Add `attitude` as the disposition underneath.** 32-100 spread, 63 distinct values,
   **3 reads** — one of Part IV's most-wasted attributes, and it is the trait version of
   exactly this axis. Confidence and determination are in-game STATE; attitude is the
   standing disposition. High attitude in a bad state reaches anyway; low attitude checks
   out sooner. That is "locked in versus checked out" as both a person and a moment.

⚠️ **The consequence worth having: ownership and USE come apart.** If checked-out genuinely
suppresses reaching, a three-skill star having a bad afternoon plays like a one-skill
player — visibly, in the feed. That is a thing a fan notices and talks about, and it is
free once state has authority.

---

# Part VII — Luck

**Owner, 2026-08-29:** "lucky players just seem to have things go their way more often than
not **when they shouldn't**, and unlucky just the opposite."

## ⚠️ It already exists, and it is well-positioned

`luck_modifier` is on `player_attributes` today: assigned `randint(-5, 5)` at generation,
**uniformly distributed** (14-20 players at each of the eleven values across a 192-player
league), and — measured — **`corr(luck, rating) = −0.02`**. Completely free of quality,
which is exactly what an axis like this needs and what no other attribute in Part IV's
table manages. Do not add a column.

⚠️ **But its three uses are FLAT ADDITIVE BONUSES** — two fumble-resist calculations and
one sack check, each adding luck straight into a rating sum. **A flat bonus is not luck, it
is a small attribute.** It shifts the mean, which is the one thing luck should not do.

⚠️ **And it is invisible.** Nothing in the frontend surfaces it, so nobody can perceive the
thing whose entire point is being perceived.

## "When they shouldn't" is the whole design constraint

Luck has to act on the **tail, not the mean** — on outcomes that were going the other way.
Which makes it **exactly the same shape as an owned skill**: both fire only *after* the
player has lost the contest.

> **A skill is a save you EARNED and can name. Luck is a save you were BORN with and
> cannot.**

That is the synthesis, and it falls out of the two ideas meeting rather than being designed.
It also supplies the guardrails:

- **Luck must be far weaker than a skill.** A skill is a real rescue; luck is a nudge at
  the margin. If they are comparable, luck becomes a free skill and the ownership model
  the whole of Part V rests on stops meaning anything.
- **Luck applies where skills do not** — which is what stops a zero-skill player being
  purely hopeless. A third of the league owns nothing (Part V); luck is what still lets
  one of them come up with something, rarely, and it is the reason those players are not
  simply worse in every frame.
- **Do not display the number.** The owner's word is *"seem"* — the perception is the
  feature. Showing `Luck: +4` turns a run of fortune into an explanation and kills it.

## Where it should be felt

The play marker from Part II gains a natural pair, and the distinction is exactly the one
a fan would draw watching:

| what happened | marker |
|---|---|
| lost the rep, spent an owned skill | **made a play** — named ("stiff arm", "one-armed catch") |
| lost the rep, no skill, luck intervened | **got away with one** — unnamed |

⚠️ Unnamed on purpose. A named luck event is an explanation; an unnamed one is a shrug,
which is what luck feels like. Over a season the tally is what makes it visible — "this
club has got away with eleven of those" — rather than any single play.

## Open questions

1. **Part I: what is the target throwaway rate?** The code says 3-5%; that is the NFL
   number and this is not the NFL. 3% of dropbacks is ~1.4 a game per team.
2. **Part I: does the escape-and-throw path need a new resolution**, or can it reuse the
   scramble's tail with a pass at the end?
3. **Part II: does the marker need a per-player season tally** ("12 playmaking plays this
   season") or is the per-play badge enough? A tally is what would make it accumulate into
   a reputation, which is the stated goal.
4. ~~**Part II: defenders.**~~ **ANSWERED** — see Part III. There is nothing to mark
   because defenders have no flair at all; it needs the ACTS built first, and the owner
   has asked for them.
5. **Part III: is the pocket/rattled rating bump real?** 79.7 against ~73.5 on n = 6.
   Re-measure at league scale (all positions, several seasons) before the axis is trusted.
6. **Part IV: is `pressureHandling` big enough to be an axis?** It is a MODIFIER
   (−10..+10, 21 distinct), not a 60-100 attribute like the rest — narrower than the
   contrast axis it is paired with. It measured rating-neutral and independent, so it
   works, but it may want widening if it is to carry half an archetype.
7. **Part III: do archetypes apply beyond QB?** The contrast axis is computed from
   attributes every position has, so it generalizes mechanically — but "what a receiver
   does under duress" is a different and thinner question than it is for a quarterback.
