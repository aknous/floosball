# Awakened Powers (L4) — Design Spec & Build Plan

Status: **DESIGN LOCKED 2026-06-14**, not yet built. Backend `next-season`. The
feature is the mechanical L4 layer of the anomaly system — see
`docs`/CLAUDE.md "Anomaly System" + the `sim_evolution_anomaly` /
`criticality_event_design` memories for the surrounding context (ladder, Cores,
suppression cycle, instability dial, all already shipped + gated).

## The reframe vs. the old design
The earlier locked design had L4 powers as **Criticality-exclusive** (awakened
players only bend the sim during a league Criticality). **That is superseded.**
New model: an awakened player is **permanently powered up** — they wield a
signature ability whenever they're charged, any week. A **Criticality** is no
longer the *source* of powers; it's the **overdrive** (powers fire far more
often → the sim visibly breaks).

## Core model
- **Awakening = graduation from glitching to power.** A player on the attention
  ladder glitches (L1→L3, involuntary, double-edged) through `stirring/erratic/
  rampant`. On reaching **`awakened`**, they **stop glitching entirely** and gain
  permanent **signature abilities** instead. (Glitch rolls must skip awakened
  players — see Build P3.)
- **One fixed signature per side, assigned once at awakening:**
  - **Offensive ability** = the broken expression of the player's **best
    offensive attribute** at awakening (frozen thereafter).
  - **Defensive ability** = their **defensive position's takeaway**, flavored by
    the same best attribute.
  - **Kickers** are special-teams only (no defensive position) → offense ability
    only.
  - Surfaced as the player's awakened identity, e.g. *"Awakened · Glue Hands /
    Pick-Six."*
- **Shared charge meter (per-game).** One bar per awakened player, fed by
  **impact-weighted positive involvement on either side of the ball**. Resets
  each game. When full, the player unleashes the ability matching whichever
  phase they're the focal point of next (has the ball → offensive ability; a
  play comes at them on D → defensive takeaway), then the meter resets. Tuned for
  **~1–2 powers/game** in normal play.
  - **Kickers charge faster.** A kicker only touches the ball on FG/XP attempts
    (a handful a game, not the dozens of snaps a skill player gets), so their
    charge-per-kick is much higher (or their fill threshold lower) so the meter
    still fills ~1–2×/game. Without this a kicker would essentially never power up.
- **Criticality = overdrive.** During a Criticality the **charge-per-play is
  scaled up** (driven by the existing `getCriticalityMultiplier` instability
  dial), so the meter refills fast and powers fire constantly = haywire. Normal
  weeks ≈ 1–2/game; deep Criticality ≈ many/game.
- **Effect = guaranteed success, magnitude varies with situation.** When a power
  fires the impossible thing *happens* (the catch is made, the kick is good), but
  the size scales with context (a Cannon from your own 5 is a 70-yd gain, not
  always a 95-yd TD). No leverage gate — a Criticality stealing a playoff game is
  the point; the Reset is the cost.
- **Offense priority.** If both the offensive focal player and a defender on the
  same play are charged, the **offensive** power fires; the defender stays charged
  for next time (keeps defensive powers from feeling like offense-cancellers).
- **Results count.** Haywire outcomes are permanent (standings/seeding/pick-em).
  The Reset purges *players*, not results.

## Catalog
Each entry = **trigger (best attribute) → named ability → mechanical effect →
surreal flavor pool** (a few hand-written reality-bending lines, rolled per fire,
expandable — like the Cores line pools). Names are placeholders pending owner
finalization. In the play feed a power shows as a **named status badge (L4
shimmer) + a rolled flavor line + the result.**

**All flavor lines are GENDER-NEUTRAL (singular they/them/their)** — players are
any gender. This applies to all player-facing copy. A few names below are still
owner-flagged (Mismatch / Strip & Score / Blow-Up / Burner).

### Offense — by best attribute

**QB · Cannon** *(Arm Strength)* — guaranteed deep-bomb completion, full field
- the ball sprouts wings and soars the length of the field
- they wind up and fire a guided missile downfield
- the throw breaks the sound barrier and lands 80 yards out
- the pass leaves a vapor trail straight to the end zone
- they flick their wrist and the ball teleports into waiting hands

**QB · Pinpoint** *(Accuracy)* — guaranteed completion into any coverage
- the defenders blur out and a clean lane snaps open
- the ball threads a keyhole between three defenders
- a glowing target locks onto the receiver and the ball homes in
- they draw a line in the air and the pass follows it exactly
- the window was an inch wide, so the ball folds itself to fit

**QB · Escape Artist** *(Agility)* — escapes the sack → big scramble / strike
- they teleport out of the collapsing pocket
- the rushers grab a cardboard cutout; the real QB is already gone
- the pocket becomes a trampoline and they bounce free
- time slows to a crawl while they stroll out of trouble
- the sack glitches out and they reappear ten yards downfield

**RB · Afterburner** *(Speed)* — breakaway, outruns the defense
- roller skates snap onto their cleats and they're gone
- a jetpack flares to life and they rocket through the gap
- the turf turns to ice behind them; everyone else wipes out
- they hit warp speed and the defenders freeze mid-stride
- they run so fast they lap the play and arrive early

**RB · Battering Ram** *(Power)* — trucks through all contact
- they turn to solid iron and bowl the line over
- they double in size and truck the entire pile
- tacklers bounce off them like they're made of rubber
- they sprout a cattle-catcher and plow everyone aside
- they lower a shoulder and the tacklers ragdoll away

**RB · Ghost** *(Agility)* — untouched, phases through
- they phase clean through the tackle like a ghost
- they split into three; the defenders grab the decoys
- hands pass right through them as they glide past
- they flicker out of existence and reappear past the line
- they sidestep into another dimension and back

**WR · Burner** *(Speed)* — guaranteed deep catch
- they leave the corner standing on a pair of roller skates
- they shift into a gear the defense doesn't have
- a green streak trails them down the sideline
- they blur past the safety before the ball's even thrown
- they outrun the spiral and wait for it in the end zone

**WR/TE · Glue Hands** *(Hands)* — guaranteed catch, never drops
- the ball velcros to their palms
- their gloves flash and the ball just sticks
- they magnetize the ball out of the air
- it ricochets off three defenders and glues to them anyway
- their hands turn to flypaper; nothing's getting loose

**WR · Stretch** *(Reach)* — guaranteed catch, impossible radius
- they conjure a ten-foot net and scoop it in
- their arms stretch like taffy across the seam
- they sprout a third hand to haul it down
- their wingspan triples and they pluck it from the sky
- the ball was uncatchable until their arm simply extended to it

**TE · The Wall** *(Power)* — guaranteed contested catch, boxes out
- they become an actual brick wall and box everyone out
- they expand to fill the entire end zone
- defenders bounce off their back as they reel it in
- they plant like a redwood; nobody's moving them
- the contested catch isn't contested — they're just bigger now

**TE · Mismatch** *(Agility)* — guaranteed catch + separation
- they're suddenly too quick for anyone on the field
- the linebacker trips over a seam in the turf
- the defense covers where they were, not where they are
- they run a route that loops back on itself and loses everyone
- they shrink to slip the coverage, then pop back open

**K · Howitzer** *(Leg Strength)* — automatic FG, extends range to 70+
- the ball turns to a cannonball and booms through from 72
- they wind up like a trebuchet and launch it
- the kick leaves a crater in the turf and a vapor trail
- it clears the uprights and keeps going into the parking lot
- the ball sonic-booms through the posts

**K · Dead Center** *(Accuracy)* — automatic FG, any angle/pressure
- the uprights lean in to catch it
- the ball curves on command and splits the middle
- a glowing crosshair locks onto the posts
- it banks off an invisible wall and drops straight through
- the kick can't miss; the geometry won't allow it

### Defense — position-keyed takeaway, attribute-flavored

**CB · Pick-Six** — forced INT + return (return-TD chance)
- they snag it with a giant baseball mitt and zoom back
- they read the throw before the QB does and jump it
- they pluck it one-handed and the field clears ahead
- they intercept it and the turf rolls out a red carpet to the house
- they were covering another route, then teleported to the ball

**S · Ballhawk** — forced INT + return (deep)
- they cover the whole deep field in one stride
- the ball drifts off course and into their arms
- they were a step late, so they simply rewound to be early
- they materialize under the pass like they always knew
- they read the code — they were always going to be there

**LB · Strip & Score** — forced fumble + recovery + return
- they rip the ball loose with a magnet and scoop it
- they punch it out and it bounces right back to them
- the ball-carrier's grip just dissolves on contact
- the fumble rolls uphill into their waiting hands
- they peel the ball away mid-stride and take off

**DE · Blow-Up** — TFL for an extreme loss / sack-strip
- the line evaporates and they're in the backfield instantly
- they teleport past the tackle before the snap finishes
- the play blows up in a puff of pixels
- they meet the runner four yards deep like they were waiting there
- they fold the pocket inward and the play collapses

Attribute modulates defensive magnitude: Speed → longer return (TD chance up);
Power → bigger loss / harder strip; Hands/Reach → cleaner, surer pick. A
defender's power waits for the appropriate play type (DBs → next pass; LB → next
run/reception; DE → run for TFL or pass for sack-strip).

### Kicker play-calling hook (required for the K powers to fire)
A charged kicker (Howitzer / Dead Center) only gets to show off if the **coach
actually attempts the kick**. The 4th-down logic (`_fourthDownCaller` / the FG
decision in `floosball_game.py`) must be altered: when the team's kicker is
**awakened + charged**, the coach will call a FG from **beyond normal range**
(out to the power's extended range, ~70+), because the make is guaranteed. This
is the delivery mechanism for the absurd long FG — without it the kicker's power
has no opportunity to fire (the coach would never call a 65-yarder normally).

## Open decisions (need owner sign-off)
1. **Gating.** The powers affect real game results, so they should ship behind
   their own flag (e.g. `ANOMALY_AWAKENED_POWERS_ENABLED`, default False) so they
   can be built + tested on `next-season` without going live until the owner says
   go. Criticality stays behind `ANOMALY_CRITICALITY_ENABLED`. **Decide:** one
   flag or two; default off.
2. **Magnitude tuning** per ability (yard curves, TD rates) — set during P3, tune
   in playtest.
3. **Meter constants** — base charge per impact unit, fill threshold, defensive
   charge rate (slower), Criticality charge multiplier curve off the instability
   dial. Set in P2/P5.
4. **Names** — finalize the placeholder ability names (owner's call).

## Phased build (high effort; gated throughout; tests + docs each phase)
- **P1 — Assignment + identity.** At the ladder→awakened transition, compute best
  offensive attribute → assign offensive + defensive ability; persist on the
  anomaly state (replace the stub `ability`/`ability_tier`). Surface the awakened
  identity (API + profile/badge). No game effect yet. Tie-break → position
  signature attr (QB Arm, RB Speed, WR Speed, TE Hands, K Leg).
- **P2 — Charge meter.** Per-game shared meter; impact-weighted charge sources
  (offense + defense); fill threshold; reset each game; expose charge state.
  **Kicker faster-charge path** (higher charge-per-kick / lower threshold) so a K
  fills ~1–2×/game despite few involvements. No fire yet (meter visibly charges).
- **P3 — Effect resolution** (`floosball_game.py`). Detect awakened + charged
  focal player at play resolution → force the ability's outcome (offense-priority);
  reset meter; attach a power payload to the play `{abilityKey, name, side,
  flavorLine, result}`. **Make glitch rolls skip awakened players.** **Kicker FG
  play-calling change:** extend `_fourthDownCaller` FG-attempt range when the
  team's K is awakened + charged (so the long FG actually gets called).
- **P4 — Flavor pools + feed presentation.** Hand-write the per-ability surreal
  line pools; play-feed named status badge + line + result.
- **P5 — Criticality overdrive.** Scale charge-per-play by the instability dial so
  Criticality weeks erupt; normal weeks stay ~1–2/game.
- **P6 — Frontend.** Charge-meter UI (profile + live game), awakened identity
  (both abilities), the **L4 shimmer** visual (radiant/in-control — the opposite
  of the L1–L2 glitch corruption) on power plays.

## Self-balancing loop (unchanged, now stronger)
Awakened players are reliably game-swinging every week → they accelerate the
league aggregate (more attention/awakening) → Criticality → **Reset purges the
awakened**. Rostering an awakened star = a Faustian deal: huge upside now, the
cull later.
