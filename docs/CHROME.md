# Chrome — cybernetic enhancement & the boredom of gods

Status: **DESIGN CAPTURE / BRAINSTORM 2026-06-23** (owner ideas, not yet specced or built).
Sibling to `docs/AWAKENED_POWERS_PLAN.md` (the L4 ability layer) and `docs/SIM_EVOLUTION.md`
(rule mutation, resurrection). This is the **aesthetic + character** pillar of the same chaos arc:
push Floosball past vanilla football into full cyberpunk-scifi, with the players themselves getting
chromed up.

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

- **Agency / economy.** Who installs chrome? Options, not exclusive: (a) the Cores assign it (pure
  top-down, no user input — most on-theme); (b) **fans fund it** as a Floobit sink, like resurrection
  is paid in facility levels (`SIM_EVOLUTION` Idea 2) — gives users a lever; (c) earned by
  performance/awakening. Leaning (a) for theme + a touch of (b) for engagement.
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
