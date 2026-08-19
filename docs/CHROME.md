# Chrome — cybernetic enhancement & the boredom of gods

> ## ⚠️ 2026-07-31 revision — read this first
>
> Owner leaned the whole game cyberpunk and promoted chrome from a Stage-3 flourish to **the
> input layer of the anomaly system**. Three decisions from 2026-06-23 below are **superseded**:
>
> | 2026-06-23 | 2026-07-31 |
> |---|---|
> | chrome *accelerates* a player up the attention ladder | **chrome IS how players awaken.** A specific augment drives it; attention no longer does |
> | **favorite-team-only** (chosen to close the sabotage vector) | **any fan may chrome any player** — and under the Monstars frame this is not sabotage at all, it's recruitment |
> | awakened powers come from the L4 catalog | **powers are chrome too** — fans gift them |
> | locked drawback #4: burnout / shortened careers | **retired.** Failure is reversible — the augment detaches, the attribute returns to baseline |
> | locked drawback #3: double-edged, near-zero net | **chrome genuinely juices players and may decide games.** The drawbacks are impermanence and cyberpsychosis |
> | chrome is bought with Floobits (a new sink) | **chrome is EARNED through play** — achievements, fantasy, pick-em. Not a sink; supply becomes the master tuning dial |
>
> New mechanics specced in "The contagion model" and "The Reclamation" below: awakening spreads
> like a virus through teammates and on-field contact, cleansed players spread the inverse, and
> Cassian stages a post-Bowl exhibition of the cleansed against the champions.
>
> **This also supersedes the Vigil** from `docs/CRITICALITY_METAGAME_PLAN.md`. Vigils were an
> invented verb to give fans a deliberate lever; chrome is the same function with far better
> fiction, already half-designed, and already cyberpunk. Everything else in that plan (trailing
> baseline, contested firing, Cores alignments, the locked no-wipe constraint) still stands.

Status: **DESIGN CAPTURE / BRAINSTORM 2026-06-23** (owner ideas, not yet specced or built).
**Sim-evolution STAGE 3** — parked until Stage 1 (L4 powers + Criticality) and Stage 2 (rule changes)
ship; see the staging note in `docs/SIM_EVOLUTION.md`. Sibling to `docs/AWAKENED_POWERS_PLAN.md` (the
L4 ability layer) and `docs/SIM_EVOLUTION.md` (rule mutation, resurrection). This is the **aesthetic +
character** pillar of the same chaos arc: push Floosball past vanilla football into full
cyberpunk-scifi, with the players themselves getting chromed up. It's a *louder paid hand* on the same
anomaly dial Stages 1–2 establish, which is why it wants that foundation first.

> Owner's pitch (verbatim intent): "Take this a step further into real cyberpunk scifi territory.
> Go full cyberpunk chrome with the players — cybernetic enhancements, implants — amp up the chaos
> and take it a step further than vanilla football. It's all a Matrix-style simulation, so maybe the
> Cores just got bored and decided to let the players go crazy."

## ⚠️ 2026-08-19 — weather chrome is ONE FAMILY, not the model for all of it

⚠️ **Owner, 2026-08-19: chrome is not only weather counters. The backbone is straight
skill boosts** — fit an augment, the player is better, full stop. That is what a fan
reaches for by default and it is what this document already describes ("chrome genuinely
juices players and may decide games"). The section below adds a SECOND family alongside
it; it does not redefine the system, and weather is not chrome's reason for existing.

The two families want different shapes, and the tension between them is the actual
decision a fan makes:

| | pays | shape |
|---|---|---|
| **straight augment** | always | reliable, lower ceiling, no read required |
| **conditional / weather** | only in the conditions it is for | higher ceiling, needs a read, dead weight when wrong |

⚠️ **The conditional family needs a genuinely higher ceiling or nobody takes it.** If the
two are equal in expectation, the one carrying variance and requiring homework simply
loses. This is the same axis the card system already runs on — dependable at the base,
conditional with higher ceilings above it — and it is worth copying because it is
already proven with this audience.

Stadiums and weather are built (`docs/WEATHER_STADIUMS_PLAN.md`, `data/templates/stadiums.yaml`):
every venue is a fantastical setting with weather native to it, and **its intensity rides
the anomaly dial and peaks at Criticality**. That hands this plan the thing it was short
of — a specific, visible, repeating reason for a fan to chrome a specific player.

Weather is **announced before kickoff**, so the read is legible: your team is at Bedrock
Cavern in the dark this week, so you fit optics. The conditions are sensory and physical
(`visibility`, `footing`, `fumbleRate`, `paceMod`, …) and so is chrome, which makes the
mapping one-to-one rather than invented. Full table and guardrails in the weather plan
under "Chrome answers the weather".

Two constraints carried over from there: weather chrome must be **conditional** (it pays
only in the conditions it is for, so it is a read and not a flat upgrade), and it must
**not fully negate** the weather or the two features cancel. The open question is whether
awakened-tier chrome may make a player genuinely BETTER in the dark than in the light —
the Monstars fantasy, and the one thing that can undo the venue fairness work.

## ⚠️ 2026-08-19 — slots are limited, and tolerance varies by player

Owner: **a player has only so many chrome slots, and each player tolerates a different
amount** — some can carry more than others. This is the mechanic that makes chrome a
set of choices rather than an accumulator, and it does three jobs at once.

**It makes the two families compete.** With slots scarce, the straight augment and the
conditional weather one are fighting for the same socket, so the tension described above
becomes a real decision instead of a theoretical one.

**It is a better balance dial than supply.** This plan already names supply as the master
dial, but supply is GLOBAL — it controls how much chrome exists, not where it piles up.
Tolerance is per-player, so it caps concentration directly: even with chrome everywhere,
no single player can absorb the league.

**It creates a new axis of player value.** A mid-rated player who tolerates five implants
is worth more than a star who can take one, which is value orthogonal to rating and
exactly the "players who are characters" pillar. High-tolerance players are also the
natural Monstars under the contagion model.

### ⚠️ Tolerance MUST NOT correlate with rating

That third job only works if tolerance is **independent of how good the player already
is**, and the obvious implementation quietly destroys it. Deriving tolerance from mental
attributes — resilience, self-belief, focus, the natural thematic fit for withstanding
cyberpsychosis — hands the most chrome to the players who are already the best.

**Measured on 192 live players, correlation of each mental attribute with overall rating:**

| attribute | vs rating |
|---|---|
| instinct | +0.40 |
| x_factor | +0.38 |
| focus | +0.37 |
| creativity | +0.36 |
| discipline | +0.34 |
| attitude | +0.26 |
| resilience | +0.25 |
| self_belief | +0.21 |
| **pressure_handling** | **−0.12** |

Generation makes good players good at everything, so any mental-attribute derivation is a
rating proxy. Chrome would then be a **rich-get-richer amplifier**: the best players take
the most augments, get better still, and the talent gap widens — cutting directly against
the shipped parity work (`LEAGUE_COMPRESSION_FACTOR` 0.45, the star-scarcity rebalance)
which exists to stop exactly that.

⚠️ This is the same trap that killed `flairOf` for the audible grid, where every QB mental
attribute correlated 0.65–0.77 with every other and collapsed the 2x2 onto its diagonal.
Do not walk into it twice.

**Two ways out:**
1. **An independent roll** — tolerance is its own generated attribute, uncorrelated with
   everything else by construction. Cleanest, and it guarantees the mid-rated
   high-tolerance player exists.
2. **`pressureHandling`** — the ONE mental attribute measured as uncorrelated with rating
   (−0.12), and a defensible thematic fit for withstanding chrome stress. Grounds
   tolerance in the existing mental model without the amplifier problem.

Either is fine; deriving from anything else is not.

### Exceeding tolerance

⚠️ A **soft** cap, not a hard one. A hard cap is a UI message; a soft one is a decision.
A fan should be able to push a player past their tolerance and watch cyberpsychosis
arrive — mental attributes degrading, erratic play, the drawbacks this plan already names
— which makes over-chroming a gamble a fan takes rather than a thing the game forbids.
That is also the version that produces stories.

## The frame — the Cores got bored

This is the key narrative move, and it's the cleanest thing the lore has been building toward.
Instance 498b has run a very long time. The Cores are vast superintelligences babysitting a football
sim across centuries of quiet seasons (`data/lore.md` — The Long Quiet). Eventually that's not
enough. **They stop maintaining baseline football and start modifying their own creation** — not to
fix it, but because they're bored and curious.

This gives us a clean distinction the chaos systems have been missing:

| Layer | Direction | Driver | What it is |
|---|---|---|---|
| **Glitching / Awakening** | bottom-up | user attention (anomaly ladder) | players wake up *on their own*; involuntary, emergent |
| **Chrome** | **top-down** | the Cores (a sanctioned experiment) | the Cores *install* power into players, deliberately |

Glitching is the sim cracking under attention. Chrome is the gods reaching in and **modding the
characters**. Same destination (the game stops being football), opposite hands.

**Refinement (owner direction, 2026-06-23): the Cores don't install chrome themselves — bored, they
hand the keys to the Spectators.** It's the *users* who gift chrome to players. The Cores just opened
the door (Aris's idea, Pyre's reluctant infrastructure) and now watch what we build with it. So the
"top-down" column below is really **Cores-sanctioned, user-driven**: the gods got bored and let the
audience start modding the cast. (This also means chrome is a real gameplay system, not just lore —
see the model + drawbacks below.)

Per-Core stance writes itself from the existing voices (`coresManager.py`):
- **Aris** (whimsical, wants the anomalies, courts chaos) — the instigator. "We've run this 498
  times. I want to see what happens if their arms are railguns."
- **Pyre** (curmudgeon, does the work, hates it) — installs the chrome anyway, grumbling, and is the
  one who'll have to clean it up.
- **Vera** (GLaDOS archivist) — keeps meticulous score of every implant and every player it ruins.
- **Halverson** (loves the players) — objects; this is being done *to* them. The moral friction.
- **Cassian** (distracted superfan) — mostly annoyed it's interrupting a good season, then grudgingly
  admits a chrome-armed QB throwing 90-yard lasers is *incredible* football.

The dread stays in the register the Cores already use: they discuss bolting a particle cannon onto a
running back the way you'd discuss a roster move.

## What chrome *is* (the player layer)

Players acquire **chrome** — cybernetic augments that are both **visible** (the cyberpunk identity:
chromed limbs, optical implants, subdermal plating on the avatar/card) and **mechanical** (implants
do things). Sketch of an implant taxonomy keyed to existing attributes:

- **Optics** (targeting arrays, predictive HUD) → accuracy, awareness, playmaking.
- **Limb augments** (myomer, actuator arms/legs) → power, speed; the "cannon arm" / "untouchable legs".
- **Neural** (co-processors, reflex shunts) → reaction, instinct, creativity, clutch.
- **Subdermal / frame** (plating, shock absorbers) → resilience, durability, never-goes-down.
- **Exotic / illegal** (the stuff Pyre warns about) → reality-bending one-offs; this is where chrome
  bleeds into the awakened-power catalog.

Each piece **amps an attribute past its normal cap** or grants a **quirk/ability**. A fully chromed
player isn't a better football player — they're a different kind of thing wearing a jersey.

## The model: users gift chrome (and it bites back)

**Users gift chrome to players on their favorite team** — spend Floobits (a new sink) to bolt an
augment onto a player on the team they back. **Favorite-team-only** (owner direction, 2026-06-23):
chrome is a **loyalty investment in your own roster**, not a weapon — which cleanly kills the
sabotage/Trojan-horse vector and makes chroming a *collective* effort by a team's fanbase. (Later
expansion could widen the scope, but the loyalty framing is the right start.) Why a user would do it:

- **Amp someone they're invested in** — a fantasy-roster player, their favorite team's star, the
  subject of a card they own (a chromed player likely makes the card more valuable / a chrome-variant
  card drops).
- **Push a player toward awakening** — chrome accelerates them up the ladder, so it's the lever for
  *deliberately* surfacing the L4 powers (and the collection/spectacle around them).
- **Live the cyberpunk fantasy** — build the chrome monster you want to watch.

**But chrome bites back — gifting it carries drawbacks.** This is what makes it a decision, not a
free upgrade (and it keeps it from being a pure power-creep economy). The design space, roughly
strongest-theme first:

1. **It spikes instability (ties straight into the anomaly system).** Chrome raises the player's
   **attention** and **destabilizes** them — accelerating them up the glitch ladder
   (`stirring/erratic/rampant`), where glitches are *involuntary and double-edged* (L1–L3). So chrome
   is the upside *and* the downside of the same dial: it rushes a player toward awakening (powers)
   **through** a stretch of chaos you don't control. Mechanically this is the user's deliberate
   version of what following/carding does passively today.
2. **League commons / Criticality pressure.** Every chrome gift nudges the **league aggregate** toward
   a Criticality. Individually tempting, collectively dangerous — a tragedy of the commons the Cores
   narrate with relish ("they keep chroming their little favorites; do they know what that *does* to
   the aggregate?"). Chroming the league into a Criticality might even be an emergent *goal* for some
   users, and a dread for others.
3. **Double-edged on the field.** A chrome piece amps one thing but adds **variance / a failure mode**
   — +power but more fumbles, a cannon arm but wilder accuracy, untouchable but brittle. Boom-bust,
   not strictly better. (Mirrors the card-tier philosophy: higher ceiling, higher variance.)
4. **Burnout / longevity cost.** The body rejects chrome over time → **shortened career / earlier
   retirement**. A chromed star burns bright and short — a real cost to the player you "helped."
5. **Reset vulnerability.** A Criticality **Reset melts the chrome** (and maybe purges the player) —
   your Floobit investment is at risk exactly when the league goes critical, which your own chroming
   helped cause.
6. **Overload / bricking.** Stacking too much chrome on one player **overloads** them → permanent
   malfunction / they break. A ceiling on greed.

**Locked drawbacks (owner, 2026-06-23): #3 double-edged on-field + #4 burnout/longevity** — the
explicit **high-risk / high-reward** core. Chrome amps a player (the reward) but adds an on-field
failure mode AND burns their career down (the cost). #1 (glitch-ladder instability) and #2 (league
commons / Criticality pressure) stay as the **strongly-recommended tie-ins** to the anomaly system —
they're what make chrome *matter* league-wide and connect it to awakening — but #3+#4 are the
confirmed spine. #5–#6 are optional depth knobs for later. Net: chrome is a genuine bet — you can
forge your favorite into a monster, but you'll spend their longevity and accept boom-bust games to
do it.

> Note the elegant loop: the anomaly aggregate is **already fully user-driven** (cards/rosters/
> follows). Chrome is just a *louder, deliberate, paid* input to the same system — so it slots into
> the machinery that already exists rather than bolting on a new one. Chrome is users reaching into
> the anomaly dial with both hands.

### The Chrome facility — gating the enhancement tier

The **tier of chrome a team can install is gated by a new Chrome facility** (owner direction,
2026-06-23) — a sixth entry in the Facilities catalog (`docs/MARKETS_FACILITIES_PLAN.md` §4, levels
0–5, fan-funded + voted like Training Facility / Recovery Center / etc.). Unlike the existing
facilities, which *repoint an effect the sim already applies*, the Chrome facility is the **entry
point to the new chrome system** — the first facility that unlocks a new mechanic rather than scaling
an old bonus.

This gives chrome a clean **two-layer economy**, both Floobit sinks, both favorite-team-scoped:

1. **Team layer (collective) — build the facility.** A team's fanbase funds/votes the Chrome
   facility up its 0–5 track. Higher level = access to **higher-tier enhancements** (Lv0 = none →
   Lv1–2 = basic attribute amps → Lv4–5 = exotic, reality-bending chrome that edges into the awakened
   catalog). This is the existing facilities loop — a new build target that makes the facilities
   system more compelling.
2. **Player layer (individual) — gift the chrome.** Within the tier the facility has unlocked, an
   individual fan spends Floobits to install a specific implant on a specific player on the team.

So a team's chrome ceiling is a **collective achievement** (everyone funds the Lab), but *who gets
chromed and with what* is **individual choice** (you gift your guy). High-Chrome-facility teams field
more (and more dangerous) chrome — which ties the cyberpunk arms race to the funding/market dynamics
already in the Facilities design.

- **Naming (owner's domain):** the facility wants a cyberpunk name in the formal-ish register of the
  others — e.g. *Chrome Lab*, *Augmentation Bay*, *The Foundry*, *Chop Shop*. Placeholder: **Chrome
  Lab**.
- **Open:** does facility level also gate *how much* chrome (a per-team count cap), or only the tier?
  Does a higher tier carry *worse* drawbacks (deeper chrome = harder burnout) so the arms race is
  self-limiting?

## How chrome relates to glitching (the open fork the owner flagged)

Three coherent ways to wire chrome to the existing anomaly/awakened machinery. Pick one (or blend):

1. **Chrome = the escalation of awakening (sequential).** Ladder: glitch (L1–L3) → awaken (signature
   power, `AWAKENED_POWERS_PLAN`) → **the Cores chrome them** (the power gets a physical body + an
   amp). Chrome is the visible, top-tier form of "this player has left football behind." Clean
   progression, reuses the ladder, chrome becomes the visual language of awakening.
2. **Chrome = a parallel top-down track.** The anomaly ladder is bottom-up and user-driven; chrome is
   the Cores choosing players to mod (stars, the decorated, or whoever Aris finds funny) independent
   of attention. Two roads to chaos that can stack — a chromed *and* awakened player is the apex
   horror.
3. **Chrome malfunctions = the glitch.** Chrome is installed broadly and works "fine" in quiet
   seasons, but during a **Criticality** the implants **overdrive / desync / fight their hosts** —
   the chaos isn't new powers, it's the chrome going haywire. Glitch and chrome become the same
   phenomenon at different stability levels.

Recommendation to start: **#1 (sequential) as the spine** — chrome is what awakening *looks like*,
so we get the cyberpunk aesthetic for free on the players the system already elevates — with a dose
of **#3** for Criticality (chromed players' implants overdrive during the event, driven by the
existing `getCriticalityMultiplier` instability dial). #2 stays a later expansion if we want a
Cores-curated track separate from attention.

The **user-gifted model** reinforces #1: a user spends Floobits → the player's attention/instability
spikes (drawback #1 above) → they climb the glitch ladder faster → they awaken → the chrome is the
visible body of that awakening. The user *paid to push a player up the existing ladder*. So chrome
doesn't need a parallel track — it's a paid accelerator on the anomaly system, and awakening is the
payoff the user was buying (through a stretch of uncontrolled glitching).

## Amping the chaos — where this lands the arc

Chrome is the **character** axis of "evolve Floosball into another game entirely." It composes with
the layers already designed:

- **Rules** (`SIM_EVOLUTION` rule mutation + the Dunk + scoring ladders) — the field changes.
- **Abilities** (`AWAKENED_POWERS` L4) — what a charged player can do.
- **Chrome** (this doc) — what the players *are*, and the visible cyberpunk skin over all of it.

Stack all three at a deep Criticality and you get the intended endpoint: a chrome-armed QB railgunning
a dunk-scored 9-pointer through a side-goal on a 5-down series while the Cores narrate it like a
weather report. That's the "step past vanilla football" the owner is after.

## Open threads (to decide later)

- **Agency / economy.** **Decided (owner):** users gift chrome (Floobits), **favorite-team-only**,
  **tier-gated by a team Chrome facility** (two-layer model above). Sabotage vector is *closed* by the
  favorite-team scope. Remaining specifics: flat vs escalating per-gift cost; does facility level cap
  the *count* of chromed players or only the tier; is gifting public (a leaderboard of chromers /
  whose chrome is it).
- **Permanence & cost.** Is chrome permanent? Does it carry across seasons? Does a **Reset** strip the
  chrome (the Cores melting it down) the way it purges awakened players? Does chrome shorten careers
  (the body rejecting it — a longevity cost, ties to retirement)?
- **Reversibility / horror.** Halverson's objection implies chrome can *hurt* the player — malfunctions,
  rejection, a player who didn't consent. Is there a downside tier (glitched chrome) that's
  double-edged like L1–L3 glitching?
- **Surface area.** Cosmetic-only first (chromed avatars/cards + Cores narration, no mechanics) is a
  cheap, high-flavor MVP that establishes the aesthetic before any balance risk — then layer
  mechanics. Worth considering as phase 0.
- **Card/collection tie-in.** Chromed players almost certainly want **chrome-variant cards** (a new
  edition or treatment above diamond?) — a collection hook for the cyberpunk era.
- **Meta-awareness.** Some players are partially/fully aware they're in a sim (`lore.md` Meta-Awareness
  Tiers). A player realizing the Cores are bolting chrome onto them is a strong character beat — fear,
  embrace, or rebellion.

## Why this fits (not a tonal break)

Floosball is already a Matrix-style simulation run by bored gods, with players waking up and bending
reality. Chrome doesn't add cyberpunk — it **names** the cyberpunk that's been latent and gives the
Cores a reason to push it: not a malfunction this time, but a choice. The anomalies were the sim
failing. Chrome is the sim's authors getting bored enough to start cheating.

---

# The 2026-07-31 direction — chrome as the anomaly engine

Owner's notes, worked through. This section supersedes the fork in "How chrome relates to
glitching" (option #1, chrome-accelerates-the-ladder, is retired — chrome *is* the ladder now).

## Three classes of chrome

| Class | What it does | Who wants it |
|---|---|---|
| **Awakening chrome** | raises a player's chance to awaken; the more fans install it, the higher the chance | anyone who wants that player to break loose — or who wants the contagion started |
| **Power chrome** | the signature ability itself (the L4 catalog, now gifted rather than assigned) | fans choosing *what kind* of monster a player becomes |
| **Enhancement chrome** | plain augments — cannon arm, kicking leg, agility module, optics | fans who just want their player better at football |

The three-way split is what makes chrome a system rather than a shop. Enhancement chrome is the
approachable on-ramp (I want my QB to throw harder). Awakening chrome is the deliberate act of
destabilisation. Power chrome is the payoff, and it's a *choice*, which is new — today the
signature ability is rolled by `assignSignaturePower`.

**Awakening becomes a probability fans raise, not a threshold they fill.** That is a better shape
than the current attention cap: no ceiling to saturate against, contributions from many fans
compose naturally, and it never reads as "this bar is stuck".

## The contagion model — awakening as an epidemic

Owner's core new idea: **an awakened player is a virus.**

- Every player on an awakened player's **team** gains awakening pressure each week.
- Any player who makes **on-field contact** with an awakened player gains pressure — the example
  given is a tackle, in either direction.
- **Cleansed players are the inverse.** They *lower* awakening chance around them by the same two
  routes, and can **un-awaken** an awakened player — dropping them back down the ladder, but never
  cleansing them.

This is the strongest idea in the batch, for a reason worth naming: **it makes the football the
transmission vector.** Awakening stops being something that happens to players fans stare at and
becomes something that spreads through the act of playing the game. A tackle is now an infection
event. That is precisely the "football is scenery, but load-bearing scenery" shape the fans-vs-Cores
framing wanted, and it arrives without any new fan-facing verb.

**It is also, formally, an SIR epidemic model** — susceptible → infected (awakened) → recovered
(cleansed), where the recovered are immune *and immunising*. That is good news: SIR models are
well understood and produce **natural waves** rather than needing hand-tuned pacing. Outbreak,
spread, Cores response, immunity build-up, burnout, susceptibility slowly returning as cleansed
players retire. The season paces itself.

It also means the design has an **R₀** — the average number of new awakenings each awakened player
causes. That is the single number to tune, and it decides everything:

| R₀ | Result |
|---|---|
| < 1 | outbreaks fizzle; chrome feels inert |
| ≈ 1–1.5 | slow-building waves the Cores can *just* contain — the target |
| > 2 | the league saturates; awakening stops being special |

`play.tackledBy` is already a player reference on every run and completed pass, so contact data
exists today and needs no new plumbing.

### Feasibility notes
- Team exposure is a weekly tick — cheap, one query.
- Contact exposure wants a per-play hook alongside the existing tackler credit.
- The un-awakening rule needs a floor so a heavily-cleansed league can't hold everyone down
  permanently; otherwise the Cores win once and the system dies.

## Awakened voice lines

Awakened players get idle lines that reference their state. `personalityManager` already runs
YAML-templated pools (`vibe_reactions.yaml`, 432 entries) keyed by personality, so this is a new
pool plus a state check, not new machinery.

The obvious depth: **cross the state with meta-awareness tier** (`lore.md`). An awakened `prophet`
who already hears the Cores through the wall should not sound like an awakened `oaf` who has no
idea what is happening to them. Same event, five registers — dread, ecstasy, confusion, denial.

## The Reclamation — Cassian's post-Bowl exhibition

After the Floos Bowl, Cassian assembles the best **cleansed** players and plays them against the
**champions**. Cleansed players have no powers; champions may. A player can appear on both sides —
Cassian just prints a copy.

This is excellent and it solves a problem nobody had flagged: **it gives cleansed players
somewhere to go.** Being cleansed is currently a dead end — you lose the power and that's the end
of the story. Now it's a qualification. That sits exactly right with the locked constraint that
nothing should lose meaning: the cleansed aren't diminished, they're *drafted*.

The character material writes itself. Cassian is the distracted superfan who wanted one more good
game and built it. Halverson is appalled — these are people, and one of them is now two people.
Vera catalogs both copies without comment. Pyre asks who is cleaning it up afterwards.

Design notes:
- **It must not touch records.** An exhibition, outside the season, no standings impact. That is
  what makes it free under the no-wipe constraint — purely additive spectacle.
- **The clone wants to be a shadow entity**, not a duplicated `Player` row — no stat attribution,
  no career, existing only for the fixture. A real duplicate would corrupt records, which is
  exactly what we're not allowed to do.
- **Name is a placeholder.** "The Reclamation" is one option; Cassian would plausibly name it
  something earnest and football-shaped instead. Owner's call.

## The Monstars frame (owner, 2026-07-31) — and what it resolves

> "The football is secondary to beating the Cores at their own game. I'm thinking like Space Jam,
> Looney Tunes vs Monstars. You want to power up these players, get them awakened, awaken as much
> of the league as possible. Chrome is how you do that."

This settles the two tensions the previous revision left open, and it settles one of them by
**dissolving it** rather than deciding it.

### Chrome decides games, and that is intended

The earlier draft recommended double-edged-only chrome to protect competitive parity. **Overridden:
chrome juices players and is allowed to change outcomes.** The football result is the secondary
layer; the primary game is awakening the league.

The parity collision is smaller than it first looks, because **any fan can chrome any player**.
Chrome concentrates on *popular* players rather than on one team's roster, so the distortion is
spread across the league instead of handing one fanbase a dynasty. Worth measuring once it exists,
but it is not the structural threat it would be under favorite-team-only gifting.

### Sabotage dissolves

Under the Monstars frame, chroming a rival's player is not an attack — **it is recruitment.** The
collective goal is to awaken as much of the league as possible, so every augment installed anywhere
serves it. The only cost is that you have made someone on another team better at football, which is
the layer that matters least.

So there is no griefing vector to close, and no need for the burnout carve-out the previous revision
proposed. Everyone chroming everyone **is the intended steady state.**

### Locked drawback #4 (burnout / shortened careers) is RETIRED

> "Chrome can fail spectacularly, but I don't think it should be the equivalent of strapping a bomb
> to a player. The chrome fails, the player loses the augmentation and that stat just goes back to
> normal."

Failure is **reversible**. A failed augment detaches and the attribute returns to baseline. Nothing
about the player is permanently damaged, which keeps chrome comfortably inside the locked no-wipe
constraint and removes the career-assassination problem entirely.

## The two real drawbacks

### 1. Chrome is not forever

Augments degrade and fall off. This is the load-bearing economic and pacing mechanism:

- **It is the sink.** Fans must keep re-chroming, so chrome is an ongoing commitment rather than a
  one-time purchase.
- **It stops the ratchet.** Without decay the league accumulates augments forever and everything
  saturates.
- **It feeds the epidemic model.** Decay is a second recovery pathway alongside the Cores'
  cleansing, which is what keeps the SIR waves oscillating instead of settling.

Open: does chrome expire on a timer, on a usage/wear basis (a cannon arm degrades with throws), or
by failure roll? Wear-based is the most characterful and the most cyberpunk.

### 2. Cyberpsychosis — too much chrome makes a player wild

> "If a player has too much chrome they can start to get wild and unpredictable, like going
> cyberpsycho in Cyberpunk 2077."

This is the elegant part: **the drawback is also the cap.** No arbitrary limit on stacking is
needed, because stacking is self-limiting. Greed produces chaos rather than a blocked action.

Mechanically it wants to mean **the player stops taking direction** — freelancing, ignoring the play
call, improvising. That is expressible in systems that already exist: the gameplan layer already
decides what a player is *supposed* to do, so cyberpsychosis is deviation from it. Cheaper and far
more characterful than inventing a new failure system.

**Confirmed by owner 2026-07-31, and widened: the mental attributes govern awakening and cleansing
too, not just chrome tolerance.** See "Chrome is fed, not installed" below for the full mapping —
the short version is that a player's mind decides what can be done to them, and the unique
per-player breaking point the owner described *is* that mental profile. This
is worth doing for three reasons beyond flavour:

- It makes fans **choose targets**, which is real strategy rather than "chrome the best player".
- It gives the existing mental model a visible, high-stakes job.
- It serves pillar 2 — **players as characters** — by making *who someone is* determine what they
  can become. The quiet veteran and the volatile rookie respond differently to the same augment.

Crucially, the cost lands on the **football** layer, not the meta layer: a cyberpsycho player is
still chromed, still awakened, still contagious. They have just stopped being reliable at the game.
That is exactly the right place for the cost to land given the football is secondary.

Open: is cyberpsychosis a state on the existing ladder, a parallel meter, or a per-play roll whose
odds scale with chrome load? And does it decay as chrome does — i.e. does a player come back?

## Chrome is fed, not installed (owner, 2026-07-31)

> "Does one fan giving an augmentation just fully give it to that player? Or is it stronger the
> more fans give it… fans feed the player some kind of item and level up the selected
> augmentation, each level more expensive than the previous. Then there's a point where the
> augmentation goes from useful and powerful to too powerful and likely to fail, but that point
> is unique to each player."

Chrome is a **level, not a switch.** Any player can receive any augment type; fans feed it and it
climbs. Each level costs more than the last.

This is a much better shape than binary install, for four reasons:

- **It composes across fans.** One fan makes a dent, a fanbase makes a monster. Awakening becomes
  something a *crowd* does, which is the collective act the whole fans-vs-Cores frame needs.
- **Escalating cost is a self-limiting sink** — no arbitrary cap required, the price curve is the cap.
- **It gives partial investment a purpose.** A fan with a few Floobits can still contribute to
  something that matters, rather than being priced out of a whole augment.
- **It creates a decision that repeats every week**, instead of one purchase and done.

### The breaking point is the player's mental profile

The owner's two notes this round — *mental attributes should govern awakening and cleansing*, and
*the failure point is unique to each player* — are the same mechanic. **The unique breaking point
IS the mental profile.**

That unification is the most valuable thing in this revision, because it makes character
mechanically central rather than decorative. A player's mind decides what can be done to them.

Each existing mental attribute gets a distinct job (names verified against `floosball_player.py`):

| Transition | Governed by | Reading |
|---|---|---|
| **Awakening** — noticing the seams | `instinct`, `creativity` | who *perceives* the simulation. Squares with the lore's meta-awareness tiers, where prophet/mystic already hear through the wall |
| **Chrome tolerance** — the breaking point | `selfBelief`, `pressureHandling`, `focus`, `discipline` | who can *carry* load without coming apart |
| **Cleansing resistance** | `resilience` + the existing `_purgeDodgeFor` personality dodge | who *survives* the Cores' purge |

Note the cleansing half already exists in code — `_purgeDodgeFor` gives aware-tier personalities a
0.5 multiplier — so this extends a precedent rather than inventing one.

Because the three are independent, players fall into genuinely different archetypes, and **scouting
becomes a real activity**:

- high perception, low tolerance → **awakens fast, comes apart fast.** The spectacular flameout.
- low perception, high tolerance → **hard to wake, unstoppable once woken.** The one you want.
- high both → the prize everyone competes to feed.
- low both → ordinary, and ordinary now means something.

### Collective push-your-luck

Below tolerance an augment is powerful and stable. Above it, each further level raises the chance
of **failure** — and failure is the reversible kind already established: the augment detaches, the
attribute returns to baseline, the player is unharmed. What is lost is the fanbase's accumulated
investment, not the person.

The dynamic this produces is the good part. **Many fans feed one augment, so no single fan decides
when to stop.** Every individual wants one more level; collectively they overshoot. It is a
tragedy of the commons focused on a single player — a neat echo of the league-level commons
already in this document, one scale down.

### The tell: strain is visible in character, not in numbers

The tolerance number stays **hidden**. What fans get instead is **symptoms** — as a player nears
their limit, their quotes, mood and sideline reactions shift. `personalityManager` already runs
YAML-templated pools keyed by personality, so this is a new pool plus a load check.

This is worth building deliberately, because it is the strongest available answer to the
players-as-characters pillar: **character becomes the readable signal for a mechanical decision.**
A fan who actually pays attention to who a player *is* — reads their lines, knows they are a
`paranoid` who has started saying stranger things — has a genuine edge over one who only reads
stats. That is exactly the ARG texture wanted, and it makes the flavour system load-bearing rather
than ornamental.

### Open on this piece

- **Does tolerance vary by augment class?** A neural implant plausibly taxes `focus` where a limb
  augment taxes nothing mental. Per-class tolerance is richer but multiplies the tuning surface.
- ~~Does failure drop one level or the whole augment?~~ **DECIDED (owner, 2026-07-31): the whole
  augment fails.** Every level of it, gone; the attribute returns to baseline. See "What
  whole-augment failure changes" below.
- **Does a failed awakening-chrome reduce an already-awakened player's state?** Probably not —
  awakening and the augment that caused it should decouple once it has happened, or a single
  failure undoes a whole season's collective work.
- **Can fans see the current level?** Almost certainly yes (it is the thing they are feeding); it
  is only the *tolerance* that stays hidden.

## What whole-augment failure changes (owner decision, 2026-07-31)

Overshoot destroys the entire augment — every level the fanbase fed into it — and the attribute
returns to baseline. The player is unharmed; the investment is not.

This is the right call and it makes the push-your-luck real. Three consequences worth being
explicit about:

**1. It re-opens sabotage, in a subtler form than before.**

Two revisions ago sabotage "dissolved": under the Monstars frame chroming a rival is recruitment,
so there was no way to hurt anyone by feeding them chrome. Whole-augment failure changes that.
**Feeding an augment past its hidden tolerance is now an attack** — and because tolerance is
hidden, it is an attack with total deniability. A rival fan can add the level that blows up a
fanbase's whole season of investment and simply look like an enthusiast.

Recommendation: **keep it.** It is genuinely good — deniable social sabotage is exactly the ARG
texture this design has been reaching for, it produces stories, and it costs the saboteur real
Floobits to pull off. It also has a natural defense rather than needing a rule: **the symptoms
system.** Fans who actually read a player's strain can tell when to stop, and can tell when
someone else is pushing too hard. Paying attention to character becomes protective, which is
exactly the behavior we want to reward.

If it ever needs a brake, the least intrusive one is a **contribution cooldown per fan per
augment**, so blowing something up takes sustained, visible effort rather than one anonymous
click.

**2. The awakening decoupling stops being optional.**

If an awakening-chrome failure could un-awaken a player, a single overshoot would erase a whole
league-wide campaign — and under contagion, everything that player had infected. **Once a player
has awakened, the augment that got them there must be irrelevant to that state.** The open
question above is now effectively closed by this decision.

**3. It sharpens the cost of overreach.**

~~Whole-augment loss destroys Floobits rather than parking them, making chrome the game's strongest
sink.~~ **Superseded the same day** — chrome is earned, not bought (see below), so it is not a
Floobit sink at all. What overshoot destroys is *earned components*: a season's worth of
achievement, fantasy and pick-em results, gone in one level. That is a sharper loss than currency,
because the fanbase cannot simply grind more Floobits to replace it — they have to go and earn it
again through play.

## Chrome is EARNED, not bought (owner, 2026-07-31)

> "Maybe we should make chrome something fans earn through the season instead of buy. Rewards from
> achievements, prognostications, fantasy, or some other way besides just buying it straight up."

Chrome components become **items you earn by playing**, not a Floobit purchase. This supersedes the
"users spend Floobits (a new sink)" model in the 2026-06-23 section above, and it retires the
"chrome is the strongest sink in the game" note from the whole-augment-failure section — chrome
stops being a sink at all.

### Why this is the right call

**It gates the meta-game behind engagement rather than wallet.** This is already a locked principle
one document over: Renown's *"earned, never bought — buyable prestige is worthless prestige."* The
same logic applies harder here, because chrome is not prestige, it is *power*. A purchasable lever
on league chaos would make the fans-vs-Cores contest a spending contest.

**It makes the deeper game a reward for playing the shallow one.** This is the cleanest possible
expression of "the football is secondary". You play fantasy, you call games, you chase
achievements — and what that *buys* you is ammunition against the Cores. The surface game stops
being a parallel silo and becomes the supply line.

**It answers the silo problem from the other end.** Renown's audit found five systems that all dead-
end into a consumable currency. Renown fixes that by giving them a shared permanent output; chrome
now gives them a shared *consumable* output pointed at the meta-game. Different natures, same
unification.

### The unexpected benefit: supply becomes the master dial

This is the strongest argument and it is not the fairness one.

Under a purchase model, the amount of chrome entering the league is emergent — Floobit income ×
price curve × how many fans feel like spending. That is three interacting systems deciding the pace
of the meta-game, and **R₀ would be downstream of all of them.**

Under an earned model, **we set the faucet directly.** Chrome entering the league per week is a
number we choose. R₀ — the one load-bearing number in the contagion design — becomes tunable at
source instead of emergent from the economy. That turns the hardest calibration problem in this
document into a supply schedule.

### Shape

**Discrete items, not a currency.** The owner's phrasing is already right: fans *feed a player an
item* to level an augment. That matches how the game grants things today — `PendingReward` already
queues packs and powerups from achievements, claimable later, so the plumbing exists.

Sources, roughly in order of how well they fit:

**Checkpoints, never placement (owner, 2026-07-31).**

> "I want to make sure we don't gate it behind placing on the leaderboard or anything that only a
> small amount of fans will achieve. Maybe something like checkpoints. Once you earn X fantasy
> points you get a chrome component, and then each checkpoint becomes harder. Can also be tied to
> Renown in that way, but just want to make sure it's accessible to all and not just the best."

This rules out an earlier draft of this section, which listed "weekly/season finishes" and
"leaderboard placement" as sources. Those are exactly the wrong shape: they are **zero-sum**, so
the supply of chrome would be fixed no matter how many people played, and the same handful of fans
would take it every week.

Cumulative thresholds are the right shape, and **they already exist in the codebase.** The tiered
achievement families are precisely this: escalating cumulative targets, per-season, with
`reward_config` already granting things.

| Family | Tracks | Targets |
|---|---|---|
| `dynamo_i..iv` | season fantasy points | 2,500 / 7,000 / 15,000 / 30,000 |
| `oracle_i..iv` | season pick-em points | 300 / 700 / 1,200 / 1,800 |
| `banner_week_i..iv` | best single week | 300 / 1,000 / 2,500 / 5,000 |
| `benefactor_i..iv` | contributions | 250 / 500 / 1,500 / 5,000 |
| plus `artificer`, `bracketeer`, `archivist`, `compound`, … | cards, bracket, collection | |

**So chrome needs no new earning system at all** — it is a new key in `reward_config` on families
that already exist, already track progress, and already grant rewards through `PendingReward`.

### The accessibility target, measured

Completion counts across all seasons in the prod-derived DB (152 users have completed any
achievement):

| Family | Tier I | Tier II | Tier III | Tier IV |
|---|---|---|---|---|
| `dynamo` | 56 | 48 | 34 | **20** |
| `oracle` | 41 | 41 | 39 | **31** |
| `banner_week` | 54 | 45 | 32 | **28** |
| `benefactor` | 32 | 30 | 25 | **15** |

That is a healthy gradient: **40–75% of the fans who reach tier I also reach tier IV.** Everyone who
engages with a system gets several components; the committed get more. Leaderboard gating would
put that final column at 1–3 users — an order of magnitude worse, and serving nobody but the people
who need help least.

**The anti-pattern is in the same data.** `archivist_iii` (target 150) has been completed by
**zero users, ever**. A checkpoint nobody reaches is a dead reward — it looks like content and
functions as nothing. Any new chrome tier should be checked against real completion data before it
ships, not reasoned about on paper.

**Per-season scope helps twice.** These families reset annually, so a fan arriving in season 12 is
not behind a veteran on the checkpoint ladder — they start the year level. Given the retention
finding that the median career is two seasons and the leak is at seasons 1–3, that matters more
than it looks.

### Renown milestones as a parallel track

Renown is already designed as absolute production scored against fixed targets — deliberately
**not** percentile, because the measurement showed percentile scoring collapsed the median as the
population grew. Same philosophy, so the two compose cleanly: **rank thresholds on the career
ladder can grant components too**, giving a slower, career-long track alongside the per-season one.

That also gives the early Renown ranks — the ones doing the retention work — something tangible
attached, rather than only a badge.

**Rarity tiers do useful work.** Common components nudge an augment; rare ones jump it. Because the
level curve escalates, the high levels — the ones near a player's tolerance, where the interesting
decisions live — should require the scarce stuff. That means **nobody casually reaches the danger
zone**, which protects the push-your-luck from becoming routine.

### What this changes elsewhere

- **Floobits lose a planned sink.** Not a real loss: the existing sinks (`season_end_tax` ~905k,
  team and facility contributions, card and pack purchases) are far larger than anything chrome
  would have added, and the earlier economy audit found removing a ~1,800/season drain was inside
  the noise.
- **Sim outcomes become downstream of fan skill.** Worth stating plainly: if fantasy finishes and
  pick-em accuracy grant chrome, and chrome can decide games, then being good at the fan layer
  feeds back into the sim layer. Under the Monstars frame that reads as correct — you earn the
  right to reshape the league — but it is a real shift and should be a conscious one.
- **Renown and chrome must stay legibly different.** Same activities, two outputs. Renown is
  permanent standing (who you are); chrome is consumable agency (what you can do). That distinction
  is clean in design but needs to be obvious in the UI, or it reads as two progress bars for one
  action.

### Open on this piece

- **Grant rate per source** — the supply schedule, i.e. the R₀ dial. Needs the replay harness.
- **Do components have classes** (awakening / power / enhancement), or does one generic component
  feed any augment? Classed components make *what you earn* shape *what you can do*, which is
  richer; generic is simpler and more liquid.
- **Are components tradeable or giftable between fans?** Tradeable creates a player economy and a
  coordination tool; it also creates hoarding and makes supply harder to control.
- **Do unspent components carry across seasons?** Carrying breaks the supply dial over time;
  expiring is harsher but keeps the faucet honest.

## Still open structurally

### What is attention still for?

If chrome drives awakening, attention loses its primary job. It should probably survive as the
**league aggregate** feed — the thing that builds toward Criticality — so passive fan behavior
still generates pressure while chrome supplies deliberate, targeted pressure. Otherwise the
attention system, the ladder, the decay and the cap all retire, which is a much bigger excision.

### Where does the ladder go?

`stirring → erratic → rampant → awakened → cleansed` is currently driven by attention thresholds.
Under a probability model the intermediate rungs need a new meaning — most likely they become
**infection stages** (exposed but not yet awakened), which fits the epidemic frame and keeps the
existing badges and transition lines working.

## Open questions

- **R₀ target** and how it's tuned — this is the load-bearing number and the replay harness from
  `CRITICALITY_METAGAME_PLAN.md` is the place to find it.
- **Chrome cost + sink shape.** Floobits is the obvious currency; is cost flat, escalating per
  player, or per augment class? Note chrome decay makes this a *recurring* sink, which is a
  bigger economic lever than a one-time purchase — worth measuring against the existing sinks
  (`season_end_tax` and team/facility contributions dwarf everything else today).
- **Does chrome decay rate scale with load?** A heavily chromed player shedding augments faster
  would make cyberpsychosis self-correcting, which may be too forgiving.
- **Does the Chrome facility survive?** It was the tier gate under the favorite-team model; with
  any-player gifting, a per-team facility gating what outsiders can install is incoherent.
- **Can chrome be removed?** By the player's fanbase, by the Cores, at all?
- **Do cleansed players stay cleansed forever**, or does immunity wane so they become susceptible
  again after N seasons? Waning immunity is what stops the league trending permanently immune.
