# Chrome — cybernetic enhancement & the boredom of gods

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
