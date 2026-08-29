# The QB under pressure, and marking the plays only good players make

**Status:** measured, not started. Two requests (owner, 2026-08-28), and they turn out to
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

## The shape to build

The owner listed six outcomes. Five of the six already exist somewhere in the code; what
is missing is a single decision that chooses between them, and a QB-identity model that
decides how.

| outcome | today |
|---|---|
| hold too long → sack | `calculateSackProbability`, no QB decision involved |
| force a throw → INT risk | the "force it anyway" roll (the default, at 70-95%) |
| throw it away | `PassType.throwAway`, gated at discipline 80+, no pressure term |
| escape and find someone | ❌ **does not exist** |
| pull it down and run | `_qbTucksAndRuns` → `_resolveQbScramble` (0.6%) |
| escape and throw it away | ❌ **does not exist** (escape always ends in a run) |

**The proposal: one `_qbUnderDuress` decision**, reached when the read fails or the pocket
collapses, resolving to one of the six. Three inputs, matching the model this codebase
already uses for every other audacious act (`_flair`, runner moves, punt selection):

- **willingness** — `_undiscipline` (gunslinger vs controlled). ⚠️ NOT `flairOf`, which
  correlates **+0.77** with `instinct` and would collapse the grid onto its diagonal; that
  is settled in `NO_HUDDLE_AUDIBLES_PLAN.md` and applies identically here.
- **ability to escape** — agility and speed, the terms `_qbEscapesSack` already uses.
- **pressure** — the missing input. `rushDifferential` and time-to-throw have to reach the
  decision, or "heavy pressure" stays unmodelable.

⚠️ **THE INTERESTING CELL IS THE BAD ONE.** A gunslinger with poor vision forcing it into
coverage is the interception; a controlled QB with poor mobility taking the sack is the
"held it too long". Those two are what make quarterbacks feel different from one another,
and both are currently near-impossible to observe because the throwaway never fires and
the sack is a pure attribute roll with no decision behind it.

⚠️ **CALIBRATION GUARDRAIL.** Raising throwaways necessarily lowers something else. The
completion rate is already **72.5% against a real-world ~65%**, so the honest place to take
it from is *forced throws that currently complete*, not from sacks — and the interception
rate must be watched, since the whole point of a throwaway is that it is the alternative to
a bad decision. `SACK_PROB_CAP` was retuned once already by chasing a mean while the tail
was the fault; measure the distribution, not just the rate.

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
