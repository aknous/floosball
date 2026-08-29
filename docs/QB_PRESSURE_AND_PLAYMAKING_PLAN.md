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

## Open questions

1. **Part I: what is the target throwaway rate?** The code says 3-5%; that is the NFL
   number and this is not the NFL. 3% of dropbacks is ~1.4 a game per team.
2. **Part I: does the escape-and-throw path need a new resolution**, or can it reuse the
   scramble's tail with a pass at the end?
3. **Part II: does the marker need a per-player season tally** ("12 playmaking plays this
   season") or is the per-play badge enough? A tally is what would make it accumulate into
   a reputation, which is the stated goal.
4. **Part II: defenders.** Every act measured here is offensive. A cornerback breaking up a
   throw is exactly as much "skill creating a play", and the clutch system already credits
   defensive risers — so the gate should be built where it can reach both.
