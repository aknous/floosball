"""Awakened (L4) signature powers — catalog + lookup.

Each awakened player carries ONE power for their career (their identity). When charged and they're
the focal point of a play, the power fires and makes that play succeed hugely — narrated with the
flavor for THAT situation. A power only fires in the situations it covers (Magnet works on a catch,
not a run). docs/AWAKENED_POWERS_PLAN.md.

──────────────────────────────────────────────────────────────────────────────────────────────────
EDITING GUIDE — this file is meant to be edited freely:
  • Change text:  edit the flavor lists. Each string is one narration line, rolled at random on fire.
  • Add a situation to a power:  add e.g.  'kick': ['...'],  to that power's block.
  • Remove a situation:  delete its key (the power just won't fire there).
  • Add a brand-new power:  copy a block, give it a unique key + name + concept + situation flavor.
  • Add a whole new SITUATION TYPE:  add it to SITUATIONS, and wire its effect in the engine. _validate()
    runs at import and flags any unknown/typo situation key.
  • A `catch` line may narrate the CATCH itself (Magnet, Flypaper) OR the RUN AFTER THE CATCH (No-Clip,
    Warp, Afterimage) — for speed/evasion/power powers that do not fit "catching", flavor the YAC: the
    player catches a routine ball, then the power breaks them free ("{passer} hits {player} and they
    phase through the tackle for {yards} yards").
  All flavor is GENDER-NEUTRAL (singular they/them/their) and apostrophe-free. Names are placeholders.

TOKENS the engine substitutes into each line (NO apostrophes around them — they are literal):
  {player}    — the awakened player (use in EVERY line; the line's subject)
  {yards}     — the yardage gained; put in OFFENSE lines only (throw/run/catch/scramble), woven "...for {yards} yards"
  {receiver}  — the receiver's name; put in THROW lines (where {player} is the QB)
  {passer}    — the QB's name; put in CATCH lines (where {player} is the receiver)
  kick lines take no yardage; pick/strip lines take no {yards} (the engine appends ", returned N yards").

THE SITUATIONS — what the player is doing when the power fires:
  throw    — the QB completes the pass          run   — the ball-carrier breaks free
  catch    — the receiver hauls it in           kick  — the kicker drills it
  scramble — the QB escapes the pass rush and takes off (QB-only; only mobility/escape powers should
             have one — an arm power does not "use a power" to scramble). Weaves {yards} like a run.
  pick     — DEFENSE vs a pass: they intercept  strip — DEFENSE vs a run: they strip the carrier
  (pick + strip are the two halves of defense — written separately so the line always matches what
   actually happened, an interception vs a forced fumble.)
──────────────────────────────────────────────────────────────────────────────────────────────────
"""
import random as _random

# The situations a player can be the focal point of. A power provides flavor only for the ones it
# covers. To add a new situation type, add it here (and wire its effect in the engine).
SITUATIONS = ('throw', 'run', 'catch', 'kick', 'scramble', 'pick', 'strip')

# A player's PRIMARY situation by offensive position. Assignment rolls a power that COVERS this, so
# the power fires regularly. The power also fires in any OTHER situation it covers (incl. pick/strip).
PRIMARY_SITUATION = {'QB': 'throw', 'RB': 'run', 'WR': 'catch', 'TE': 'catch', 'K': 'kick'}

# The two defensive situations and the takeaway each forces: a pass defended -> interception (pick),
# a run defended -> forced fumble (strip). The engine picks 'pick' on a pass, 'strip' on a run.
DEFENSE_SITUATIONS = ('pick', 'strip')

# ── Catalog ─────────────────────────────────────────────────────────────────────────────────────
# key: {name, concept, <situation>: [flavor lines], ...}  — omit situations the power can't do.
_POWERS = {
    # ---- Universal ----
    'no_clip': {'name': 'No-Clip', 'concept': 'phases through solid matter like a glitch in the world',
        'throw': ['{player} altered the balls programming and it phased through defenders to find {receiver} for {yards} yards',
                  '{player} clips the ball clean through the defense untouched and hits {receiver} for {yards} yards'],
        'scramble': ['{player} phases straight through the collapsing rush and runs untouched for {yards} yards'],
        'run':   ['{player} phases clean through the tacklers and runs untouched for {yards} yards',
                  '{player} turns off their collision detection and glides right through the defense for {yards} yards'],
        'catch': ['{passer} lets it fly and {player} jumps through the defender to grab the ball for {yards} yards',
                  '{passer} throws it up and {player} reaches a hand through the corner\'s head to pull it in for {yards} yards'],
        'pick':  ['{player} phases a hand through the receiver\'s body and snatches the ball out of the air',
                  '{player} jumps through the receiver and comes down with the ball'],
        'strip': ['{player} reaches a hand clean through the runner\'s midsection and pulls the ball out',
                  '{player} clips through the pile and comes out the other side with the ball']},

    'pixelate': {'name': 'Pixelate', 'concept': 'disassembles into pixels and reassembles downfield',
        'throw': ['{player} scatters the throw into a million pixels, streams it downfield and reforms it in stride for {receiver} for {yards} yards'],
        'scramble': ['{player} scatters into pixels to avoid the pass rush and reforms downfield for {yards} yards'],
        'run':   ['{player} bursts into pixels and reassembles downfield for {yards} yards',
                  '{player} scatters into static and reforms past the defense for {yards} yards'],
        'catch': ['{passer} throws it up and {player} dissolves, drifts past the coverage, and rebuilds around the ball for {yards} yards'],
        'pick':  ['{player} pixel-scatters into the throwing lane and reassembles around the pass'],
        'strip': ['{player} dissolves through the runner and reassembles in the backfield with the ball in hand']},

    'take_flight': {'name': 'Take Flight', 'concept': 'simply takes off and flies',
        'run':   ['{player} lifts off and soars over the defense for {yards} yards',
                  '{player} takes to the sky and glides over the defense for {yards} yards'],
        'scramble': ['{player} takes flight to avoid the pressure and flies for {yards} yards'],
        'catch': ['{passer} lofts it up and {player} launches way up into the air, plucks it from the sky and soars downfield for {yards} yards'],
        'pick':  ['{player} takes flight and snatches the ball from the air'],
        'strip': ['{player} dive bombs the runner and forces the ball loose']},

    # ---- Throw-home (QB) ----
    'railgun': {'name': 'Railgun', 'concept': 'fires the ball like an electromagnetic slug',
        'throw': ['{player}\'s arm morphs into a railgun and fires to {receiver} on a flat line for {yards} yards',
                  '{player} becomes a literal railgun and fires to {receiver} for {yards} yards']},

    'wormhole': {'name': 'Wormhole', 'concept': 'folds the field so the ball threads anything',
        'throw': ['{player} opens a wormhole between themselves and {receiver} and threads the ball through it for {yards} yards'],
        'scramble': ['{player} can\'t find anyone open and hops into a wormhole to escape for {yards} yards'],
        'run':   ['{player} hops into a wormhole and emerges downfield for {yards} yards'],
        'catch': ['{passer} lets it fly and {player} pops out of a wormhole to snatch it for {yards} yards'],
        'pick':  ['{player} reaches through a wormhole and snatches the ball from the air'],
        'strip': ['{player} opens a wormhole behind the runner and forces the ball loose into it']},

    # ---- Run-home (RB) ----
    'warp': {'name': 'Warp', 'concept': 'moves at a speed the field cannot track',
        'run':   ['{player} hits warp speed and is gone for {yards} yards',
                  'in the blink of an eye, {player} is downfield for {yards} yards'],
        'scramble': ['{player} warps to avoid the pressure and reappears in the blink of an eye downfield for {yards} yards'],
        'catch': ['{passer} throws it up and {player} warps downfield and waits for it to arrive, good for {yards} yards'],
        'pick':  ['{player} warps under the throw and is waiting when it arrives'],
        'strip': ['{player} warps to the runner, strips the ball loose and warps away']},

    'juggernaut': {'name': 'Juggernaut', 'concept': 'turns to unstoppable iron',
        'run':   ['{player} turns to literal wrecking ball and bowls the whole defense over for {yards} yards',
                  '{player} turns to solid iron and grinds forward as the tacklers ragdoll off for {yards} yards'],
        'scramble': ['{player} turns to solid iron and barrels through the pocket for {yards} yards'],
        'pick':  ['{player} bulldozes into the pocket and snatches the rushed throw in their iron grip'],
        'strip': ['{player} turns into a wall of iron and the ball pops free as the runner bounces off']},

    'ice_rink': {'name': 'Ice Rink', 'concept': 'freezes the field to a sheet of ice',
        'run':   ['{player} flashes the turf to ice and skates for {yards} yards as the defenders slip and slide behind them',
                  '{player} skates across a frozen field while everyone else slips, good for {yards} yards'],
        'scramble': ['{player} turns the pocket into ice and skates across the frozen field to avoid the pressure for {yards} yards'],
        'pick':  ['{player} ices the field over, the receiver slips, and {player} slides in for the pick'],
        'strip': ['{player} turns the turf to ice, the runner wipes out, and {player} skates off with the ball']},

    'freestyle': {'name': 'Freestyle', 'concept': 'literally swims down the field',
        'run':   ['{player} dives into the field like its a pool and swims past the defense untouched for {yards} yards',
                  '{player} backstrokes past a diving tackle like it is open water, good for {yards} yards',
                  '{player} breaststrokes through the defensive line as the field ripples like water, gliding past tacklers for {yards} yards'],
        'scramble': ['{player} leaps into the grass like it is water and swims past the defenders for {yards} yards'],
        'catch': ['{passer} lets it fly, {player} swims under the surface and comes up in time to catch the ball for {yards} yards'],
        'pick':  ['{player} backstrokes into the passing lane and pulls the pass out of the air'],
        'strip': ['{player} swims under the line and wrestles the ball away from the runner']},

    'broomstick': {'name': 'Broomstick', 'concept': 'rides a broomstick down the field',
        'run':   ['{player} mounts a broomstick and flies past the defense for {yards} yards',
                  '{player} conjures a broomstick and sweeps past the defense for {yards} yards'],
        'scramble': ['{player} conjures a broomstick and flees the pocket for {yards} yards'],
        'catch': ['{passer} throws it up and {player} mounts a broomstick to sweep downfield and catch it for {yards} yards'],
        'pick':  ['{player} conjures a broomstick and sweeps into the passing lane to snatch the ball'],
        'strip': ['{player} conjures a broomstick, sweeps into the runner, and pries the ball loose']},

    'hacker': {'name': 'Hacker', 'concept': 'hacks the ball and the field to their advantage',
        'throw': ['{player} reprograms to make it just appear at {receiver} for {yards} yards',
                  '{player} hacks the field and the ball curves around the defenders to find {receiver} for {yards} yards'],
        'scramble': ['{player} bypasses the firewall and slips out of the pocket for {yards} yards'],
        'run':   ['{player} hacks the playing field program to open a path and runs past the defense for {yards} yards'],
        'catch': ['{passer} throws it up and {player} runs a script to curve the ball around the coverage and makes the catch for {yards} yards'],
        'pick':  ['{player} alters the trajectory calculation of the ball and it redirects into their hands for a pick'],
        'strip': ['{player} reprograms the ball to make it fall out of the runner\'s hands and into their own']},

    'sword': {'name': 'Sword', 'concept': 'summons a sword and everyone backs away',
        'run':   ['{player} brandishes a broadsword and everyone just backs away slowly as they run past for {yards} yards',
                  '{player} conjures a giant sword and the defense scatters as they run past for {yards} yards'],
        'scramble': ['{player} conjures a sword that stops the pass rush in their tracks as they escape the pocket for {yards} yards'],
        'catch': ['{passer} throws it up and {player} whips out a sword and waves it at the defender. The defender concedes and they make the catch for {yards} yards'],
        'pick':  ['{player} pulls a sword from their pants and the receiver just lets them have the ball'],
        'strip': ['{player} conjures a sword and the runner backs away and hands the ball over']},

    # ---- Catch-home (WR/TE) ----
    'magnet': {'name': 'Magnet', 'concept': 'turns magnetic to the ball',
        'catch': ['{passer} throws it up and {player}\'s hands turn into a giant magnet out to attract the ball into their hands for {yards} yards',
                  '{passer} throws it to {player} who uses a cartoon magnet to pull the ball down for {yards} yards'],
        'pick':  ['{player} redirects the throw into their hands with a very large magnet'],
        'strip': ['{player} magnetizes their hands and tears the ball off the runner']},

    'rubberband': {'name': 'Rubberband', 'concept': 'arms stretch like taffy',
        'catch': ['{passer} throws it up and {player} stretches their arm into the air to reel it in for {yards} yards',
                  '{passer} lets it fly and {player} triples their wingspan to pluck the uncatchable for {yards} yards'],
        'scramble': ['{player} stretches their arms and legs to slip past the defenders for {yards} yards'],
        'pick':  ['{player} whips an arm across the field and plucks the throw out of the air'],
        'strip': ['{player} stretches both arms out and lassos the runner, squeezing the ball loose']},

    'octopus': {'name': 'Octopus', 'concept': 'sprouts a tangle of extra arms',
        'catch': ['{passer} lets it fly, {player} unfurls eight tentacles and one of them makes the catch for {yards} yards',
                  '{passer} throws it up and {player} swallows it out of the air with a forest of hands for {yards} yards'],
        'scramble': ['{player} sprouts extra arms and legs to wriggle past the defenders for {yards} yards'],
        'pick':  ['{player} blankets the receiver with eight tentacles and comes down with the pass'],
        'strip': ['{player} wraps the runner in tentacles and peels the ball away']},

    'colossus': {'name': 'Colossus', 'concept': 'grows to fill the field',
        'catch': ['{passer} throws it to {player} who has grown to triple their size and boxes everyone out for it, good for {yards} yards'],
        'scramble': ['{player} grows to giant size and stomps past the defenders for {yards} yards'],
        'run':   ['{player} swells to giant size and steps over the entire defense for {yards} yards'],
        'pick':  ['{player} grows into a human wall and bats the pass down into their own hands'],
        'strip': ['{player} grows to giant size, plucks the runner off the turf and takes the ball away']},

    # ---- Kick-home (K) — offense only (no defensive position) ----
    'moonshot': {'name': 'Moonshot', 'concept': 'kicks it into orbit',
        'kick': ['{player} launches the ball into orbit and it arcs down through the uprights',
                 '{player} kicks the ball so hard it clears the uprights by a mile and continues into the atmosphere forever']},

    'tractor_beam': {'name': 'Tractor Beam', 'concept': 'the target pulls the ball in',
        'kick': ['{player}\'s kick locks onto the uprights and the ball is pulled through'],
        'catch': ['{passer} lets it fly and {player} locks a tractor beam on it to drag the ball into their hands for {yards} yards'],
        'pick':  ['{player} locks a tractor beam on the throw and reels it in'],
        'strip': ['{player} latches a tractor beam on the ball and drags it off the runner']},

    'trebuchet': {'name': 'Trebuchet', 'concept': 'launches it like a siege engine',
        'kick': ['{player} summons a trebuchet and launches the ball through the uprights'],
        'throw': ['{player} cranks back and catapults the ball to {receiver} for {yards} yards']},

    'missile': {'name': 'Missile', 'concept': 'launches a guided missile',
        'kick': ['{player} hits the launch button and the ball rockets through the uprights.'],
        'throw': ['{player} transforms the ball into a guided missile and it homes in on {receiver} for {yards} yards'],},

    # ---- Defense-rich ----
    'black_hole': {'name': 'Black Hole', 'concept': 'opens a collapsing gravity well',
        'run':     ['{player} drags the defenders off their feet toward the gap and slips through for {yards} yards'],
        'scramble': ['{player} opens a gravity well under the defenders and runs past them as they fall into the abyss for {yards} yards'],
        'catch':   ['{passer} throws to {player} who opens a gravity well on their chest the ball cannot escape to make the catch for {yards} yards'],
        'pick':    ['{player} opens a well in the passing lane and the pass spirals through the dark and into their hands'],
        'strip':   ['{player} opens a gravity well behind the line that swallows the runner and spits the ball out']},

    # ---- Throw-home (QB) ----
    'slingshot': {'name': 'Slingshot', 'concept': 'fires the ball off a giant slingshot',
        'throw': ['{player} loads the ball into a slingshot and snaps it to {receiver} across the field for {yards} yards',
                  '{player} takes a slingshot out and snaps it to {receiver} for {yards} yards'],
        'kick':  ['{player} mounts a giant slingshot in the field and fires the ball through the uprights']},
    'orbital': {'name': 'Orbital', 'concept': 'sends the ball to low orbit and back',
        'throw': ['{player} lofts it into low orbit and it drops down to {receiver} for {yards} yards',
                  '{player} sends the ball out of the atmosphere and it re-enters into {receiver} for {yards} yards'],
        'kick':  ['{player} kicks high into low orbit and it drops back down through the posts']},
    'heat_seeker': {'name': 'Heat-Seeker', 'concept': 'the ball locks on and homes in',
        'throw': ['{player} locks the ball onto {receiver}\'s heat signature and it homes in mid-flight for {yards} yards',
                  '{player} twists the ball around a defender to {receiver} like it has a guidance chip, good for {yards} yards'],
        'pick':  ['{player} locks the ball onto their heat signature and it redirects into their hands']},
    'auto_aim': {'name': 'Auto-Aim', 'concept': 'a crosshair snaps to the target',
        'throw': ['{player} snaps a crosshair to {receiver} and the ball follows it in for {yards} yards',
                  '{player} locks onto {receiver} and throws the ball the complete opposite direction. The throw finds {receiver} anyway for {yards} yards'],
        'kick':  ['{player} aims a reticle at the posts and the kick auto-corrects mid-flight through the uprights'],
        'pick':  ['{player} hacks the ball and it auto-corrects into their hands'],
        'strip': ['{player} paints the runner with their targeting system and the ball auto-ejects into their hands']},
    'smoke_bomb': {'name': 'Smoke', 'concept': 'vanishes in a puff of smoke',
        'throw': ['{player} vanishes in a puff of smoke as the pass rush closes in and slings it out of the cloud to {receiver} for {yards} yards',
                  '{player} leaves the rush grabbing at smoke and is already gone, hitting {receiver} for {yards} yards'],
        'scramble': ['{player} dissolves into a cloud of smoke and drifts past the defenders for {yards} yards'],
        'run':   ['{player} bursts into smoke as the defenders attempt a tackle and reappears past them for {yards} yards'],
        'pick':  ['{player} collapses into a cloud of smoke and floats into the passing lane to snatch the ball'],
        'strip': ['{player} disorients the runner with a cloud of smoke and pops the ball free']},
    'trapdoor': {'name': 'Trapdoor', 'concept': 'drops through a trapdoor and pops up elsewhere',
        'throw': ['{player} drops the ball through a trapdoor in the ground and it falls out of the sky onto {receiver} for {yards} yards'],
        'scramble': ['{player} falls through a trapdoor and pops out of thin air past the defenders for {yards} yards'],
        'run':   ['{player} falls through a trapdoor and pops out upfield for {yards} yards'],
        'pick':  ['{player} reaches through a trapdoor and snatches the ball out of the air'],
        'strip': ['{player} drops the runner through a trapdoor and grabs the ball on the way down']},
    'bullet_time': {'name': 'Bullet Time', 'concept': 'time crawls to a stop around them',
        'throw': ['{player} slows time to a crawl, the defenders moving like molasses, and zips it to {receiver} for {yards} yards'],
        'scramble': ['{player} slows time to a crawl and walks casually past the defenders for {yards} yards'],
        'run':   ['{player} slows everything to a crawl and strolls between frozen defenders for {yards} yards'],
        'catch': ['{passer} lets it fly, {player} stutters time, and reels it in while the ball hangs still for {yards} yards'],
        'pick':  ['{player} slows time and steps in front of a ball that is barely moving'],
        'strip': ['{player} slows time and plucks the ball from the frozen runner']},
    'decoy': {'name': 'Decoy', 'concept': 'leaves a decoy for the defense to hit',
        'throw': ['{player} deploys a cardboard cutout of themselves for the defense to tackle and throws free to {receiver} for {yards} yards'],
        'run':   ['{player} leaves a decoy behind and slips away with the ball for {yards} yards while the defense celebrates tackling the decoy'],
        'catch': ['{passer} throws it up and {player} leaves a decoy for the corner to tackle and snags the ball for {yards} yards']},
    'grease': {'name': 'Grease', 'concept': 'too slippery to hold onto',
        'throw': ['{player} slips free as the defenders slide right off and fires to {receiver} for {yards} yards'],
        'scramble': ['{player} squirts past the defenders as they slip and slide for {yards} yards'],
        'run':   ['{player} sheds the tacklers who can\'t grip their greasy body for {yards} yards']},
    'jelly': {'name': 'Jelly', 'concept': 'turns to jelly and oozes free',
        'throw': ['{player} turns to jelly as the defenders reach for them, reforms, and slings it to {receiver} for {yards} yards'],
        'scramble': ['{player} turns to jelly and oozes past the defenders for {yards} yards'],
        'run':   ['{player} turns to jelly and the defenders\' arms pass through their body as they wobble onward for {yards} yards'],
        'pick':  ['{player} jiggles into the lane and the ball sticks in the jelly'],
        'strip': ['{player} turns into jelly around the runner and the ball oozes free into their hands']},

    # ---- Run-home (RB) ----
    'hyperdrive': {'name': 'Hyperdrive', 'concept': 'jumps to lightspeed',
        'run':   ['{player} punches the hyperdrive and streaks downfield for {yards} yards',
                  'stars smear and {player} is suddenly gone for {yards} yards'],
        'scramble': ['{player} tucks the ball, punches the hyperdrive and streaks past the defenders for {yards} yards'],
        'catch': ['{passer} throws it to {player} who makes the catch and jumps to light speed down the field for {yards} yards'],
        'pick':  ['{player} hyperdrives across the field and is under the throw before it arrives'],
        'strip': ['{player} hyperdrives into the runner and the ball is gone in a blur']},
    'fast_forward': {'name': 'Fast-Forward', 'concept': 'fast-forwards while everyone else plays normal speed',
        'run':   ['{player} fast-forwards through the defense while everyone else plays at normal speed for {yards} yards'],
        'scramble': ['{player} can\'t find an open receiver and fast-forwards through the defenders while everyone else plays at normal speed for {yards} yards'],
        'catch': ['{passer} lets it fly and {player} fast-forwards to the spot for the ball to catch up to them for {yards} yards'],
        'throw': ['{player} fast-forwards out of the rush, sets their feet, and fires to {receiver} for {yards} yards'],
        'pick':  ['{player} fast-forwards to the ball and arrives a beat early for the pick'],
        'strip': ['{player} fast-forwards to the runner and the ball pops out they knew they had it']},
    'conveyor_belt': {'name': 'Conveyor Belt', 'concept': 'the turf carries them like a belt',
        'run':   ['{player} turns the turf to a conveyor and leisurely rides it past everyone for {yards} yards',
                  '{player} conjures a conveyor under their feet and hops onto it for {yards} yards'],
        'scramble': ['{player} conjures a conveyor under their feet and rides it past the defenders for {yards} yards'],
        'pick':  ['{player} conjures a conveyor under their feet and rides it to the ball for the pick'],
        'strip': ['{player} conjures a conveyor under their feet and rides it to the runner, prying the ball free']},
    'centipede': {'name': 'Centipede', 'concept': 'sprouts a dozen extra legs',
        'scramble': ['{player} sprouts a dozen extra legs and escapes the pocket for {yards} yards'],
        'run':   ['{player} sprouts a dozen extra legs and scuttles past the tackle for {yards} yards',
                  '{player} grows centipede legs and skitters past horrified defenders for {yards} yards'],
        'pick':  ['{player} swarms the route with a hundred legs and snags the pass'],
        'strip': ['{player} swarms the carrier with a hundred legs and pries the ball free']},
    'wind_blast': {'name': 'Wind Blast', 'concept': 'conjures wind to blow the defense away',
        'run':   ['{player} conjures a powerful gust of wind and blows past the defense for {yards} yards',
                  '{player} scatters the defense like leaves with an ominous gust and runs past them for {yards} yards'],
        'scramble': ['{player} conjures a gust of wind to knock defenders aside and escapes for {yards} yards'],
        'pick':  ['{player} blows the pass off course and into their hands with one big breath'],
        'strip': ['{player} knocks the carrier down with one big breath and the ball pops loose']},
    'boulder': {'name': 'Boulder', 'concept': 'turns to solid rock',
        'run':   ['{player} turns to solid rock and grinds the pile backward for {yards} yards',
                  '{player} turns to a half-ton of granite and the tacklers shatter against them as they run for {yards} yards'],
        'scramble': ['{player} turns to solid rock and pushes through the pocket for {yards} yards'],
        'strip': ['{player} becomes an immovable boulder, the runner hits them and the ball jars loose']},
    'origami': {'name': 'Origami', 'concept': 'folds flat as paper',
        'run':   ['{player} folds flat as paper and slips between two tacklers for {yards} yards',
                  '{player} folds themselves into a paper crane and flits past the defenders for {yards} yards'],
        'throw': ['{player} folds the ball into a paper airplane and sails it to {receiver} for {yards} yards'],
        'scramble': ['{player} folds flat and slides under the pass rush for {yards} yards'],
        'catch': ['{passer} throws it up and {player} folds around the defender and unfolds with the ball for {yards} yards'],
        'pick':  ['{player} folds flat, slides into the passing lane, and snatches the pass'],
        'strip': ['{player} folds thin through the line and creases the ball out of the runner']},
    'clone': {'name': 'Clone', 'concept': 'splits into a crowd of copies',
        'run':   ['{player} splits into three and the defense tackles the wrong two while the real one slips by for {yards} yards',
                  '{player} floods the gap with clones and breaks free for {yards} yards'],
        'throw': ['{player} splits into multiple copies and one of the clones finds {receiver} for {yards} yards'],
        'scramble': ['{player} splits into multiple clones and one of them pushes through the pocket for {yards} yards'],
        'catch': ['{passer} lets it fly and {player} clears out the coverage with two clones to catch it clean for {yards} yards'],
        'pick':  ['{player} blankets the route with a swarm of clones and picks it off'],
        'strip': ['{player} swarms the runner with clones and comes away with the ball']},
    'heartthrob': {'name': 'Heartthrob', 'concept': 'the defenders fall in love',
        'run':   ['{player} bats their eyes and the defenders swoon and wave them through for {yards} yards',
                  '{player} charms the tacklers into stopping to admire them and strolls by for {yards} yards'],
        'scramble': ['{player} flashes some leg and the defenders are too distracted to collapse the pocket, allowing {player} to scramble for {yards} yards'],
        'catch': ['{passer} throws it up and {player} leaves the corner too smitten to contest the catch, which is complete for {yards} yards'],
        'pick':  ['{player} flirts with the receiver who is too smitten to fight for it and {player} swoops in for the pick'],
        'strip': ['{player} leaves the ball-carrier so lovestruck that they just hand the ball over']},
    'shrink_ray': {'name': 'Shrink Ray', 'concept': 'shrinks to slip past',
        'run':   ['{player} shrinks to ant-size and scurries between the tacklers feet for {yards} yards',
                  '{player} zaps the whole defense with a shrink ray and runs over them for {yards} yards'],
        'scramble': ['{player} shrinks down below the defenders\' knees and scurries through the collapsing pocket for {yards} yards'],
        'catch': ['{passer} throws it up and {player} shrinks the defender to make the uncontested catch for {yards} yards'],
        'pick':  ['{player} hits the receiver with a shrink ray and snatches the pass that was intended for them'],
        'strip': ['{player} shrinks the ball so it falls out of the unsuspecting runner\'s hands and picks it up']},
    'skunk': {'name': 'Skunk', 'concept': 'stinks so bad everyone avoids them',
        'run':   ['{player} unleashes a stench that clears a lane as the defenders gag and give room for {yards} yards',
                  '{player} reeks so badly nobody touches them as they run for {yards} yards'],
        'scramble': ['{player} unleashes a stench and the defenders scatter, allowing {player} to scramble for {yards} yards'],
        'catch': ['{passer} finds {player} who is uncovered due to a terrible stench and goes for {yards} yards'],
        'pick':  ['{player} makes the receiver running the route gag with an unholy stench and takes the pass uncontested'],
        'strip': ['{player} reeks so badly the carrier recoils and coughs up the ball']},
    'liquify': {'name': 'Liquify', 'concept': 'turns to liquid and pours through',
        'run':   ['{player} turns to liquid and pours through the gap in the line for {yards} yards',
                  '{player} liquefies and slips through the defenders for {yards} yards',
                  '{player} runs for {yards} yards as they splash through would be tacklers'],
        'scramble': ['{player} turns to liquid and flows through the collapsing pocket for {yards} yards'],
        'pick':  ['{player} pours into the passing lane and the ball drops into the puddle'],
        'strip': ['{player} flows around the runner and re-forms holding the ball']},
    'avalanche': {'name': 'Avalanche', 'concept': 'comes down like an avalanche',
        'run':   ['{player} creates an avalanche of snow that clears a path through the defense for {yards} yards',
                  '{player} summons an avalanche and rides a wave of snow for {yards} yards']},
    'stampede': {'name': 'Stampede', 'concept': 'multiplies into a trampling herd',
        'run':   ['{player} multiplies into a thundering herd and tramples through the defense for {yards} yards',
                  '{player} floods the lane with a stampede of clones and flattens everything, runs for {yards} yards'],
        'pick':  ['{player} floods the secondary with a stampede and one of the herd snags the pass'],
        'strip': ['{player} rolls a stampede over the carrier and the ball comes loose']},

    # ---- Catch-home (WR/TE) ----
    'vacuum': {'name': 'Vacuum', 'concept': 'inhales the ball in',
        'catch': ['{passer} lets it fly to {player} who pulls out a vacuum to suck the ball into their hands for {yards} yards',
                  '{passer} throws it up, {player} uses their mom\'s vacuum cleaner to suck the ball out of the air for {yards} yards'],
        'pick':  ['{player} uses the immense suction of a vacuum to yank the ball out of the air'],
        'strip': ['{player} switches on the vacuum and inhales the ball off the runner']},
    'remote': {'name': 'Remote Control', 'concept': 'uses a remote to rewind and retry or puause and slow down',
        'scramble': ['{player} hits the pause button on their remote just before getting sacked and strolls past for {yards} yards'],
        'catch': ['{passer} lets it fly, but {player} drops it. {player} pulls out a remote control, hits the rewind button, and brings it in clean this time for {yards} yards',
                  '{passer} tosses it to {player}, {player} hits pause on their remote and plucks the ball out of the air for {yards} yards'],
        'pick':  ['{player} just misses the interception, hits the rewind button on their remote, and times it perfectly on the second try for the pick'],
        'strip': ['{player} hits the stop button on their remote and rips the ball loose from the runner']},
    'slinky': {'name': 'Slinky', 'concept': 'arms coil out like a slinky',
        'catch': ['{passer} overthrows it and {player} coils an arm out like a slinky to grab it for {yards} yards',
                  '{passer} lets it fly and {player} springs a coiled arm across the seam to reel it in for {yards} yards'],
        'pick':  ['{player} springs a slinky arm out and snatches the throw'],
        'strip': ['{player} coils a slinky arm around the runner and springs back with the ball']},
    'telescope': {'name': 'Telescope', 'concept': 'arms telescope out',
        'catch': ['{passer} throws it up and {player} telescopes both arms out ten feet to pluck it from the sky for {yards} yards',
                  '{passer} lets it fly and {player} extends like a spyglass to snag the otherwise uncatchable pass for {yards} yards'],
        'pick':  ['{player} shoots a telescoping arm out and intercepts the pass'],
        'strip': ['{player} reaches a telescoping arm in and plucks the ball from the runner']},
    'fishing_rod': {'name': 'Fishing Rod', 'concept': 'casts an arm out like a line',
        'catch': ['{passer} throws it to {player} who pulls out a fishing rod and casts a hook to reel the ball in for {yards} yards',
                  '{passer} overthrows it and {player} whizzes the fishing rod and reels in a big catch for {yards} yards'],
        'pick':  ['{player} whips out a fishing rod, casts out, hooks the pass, and reels in the pick'],
        'strip': ['{player} uses a fishing rod to cast a line around the runner and reel the ball in']},
    'butterfly_net': {'name': 'Butterfly Net', 'concept': 'pulls a giant net from nowhere',
        'catch': ['{passer} passes to {player} who pulls a giant net from their sleeve and scoops the ball out of the air for {yards} yards',
                  '{passer} throws the deep ball to {player} who catches it with a giant butterfly net for {yards} yards'],
        'pick':  ['{player} swings a bug net across the passing lane and snags the pass'],
        'strip': ['{player} drops a net over the runner and scoops the ball out']},
    'blackout': {'name': 'Blackout', 'concept': 'blinds everyone but them on the field',
        'run':   ['{player} turns off the lights and runs through the darkness for {yards} yards',
                  '{player} blinds the defense and runs through the darkness for {yards} yards'],
        'scramble': ['{player} turns off the lights and scrambles through the darkness for {yards} yards',
                     '{player} blinds the defense and scrambles through the darkness for {yards} yards'],
        'catch': ['{passer} passes to {player}, who turns off the lights and blinds everyone else while they run for {yards} yards'],
        'pick':  ['{player} switches off the lights and snatches the pass while others flail in the darkness'],
        'strip': ['{player} uses a blackout to strip the ball from the blinded runner']},
}


def _validate():
    for key, p in _POWERS.items():
        unknown = [s for s in p if s not in ('name', 'concept') and s not in SITUATIONS]
        assert not unknown, f"awakened power {key!r} has unknown situation keys {unknown}"
        assert p.get('name') and p.get('concept'), f"awakened power {key!r} missing name/concept"
        assert any(s in p for s in SITUATIONS), f"awakened power {key!r} covers no situations"


_validate()


# ── Lookup / assignment ─────────────────────────────────────────────────────────────────────────
def allPowerKeys():
    return list(_POWERS)


def powerName(key):
    return _POWERS.get(key, {}).get('name', '')


def powerConcept(key):
    return _POWERS.get(key, {}).get('concept', '')


def coveredSituations(key):
    p = _POWERS.get(key, {})
    return [s for s in SITUATIONS if s in p]


def powerCoversSituation(key, situation):
    return situation in _POWERS.get(key, {})


def situationFlavor(key, situation, rng=_random):
    """A random narration line for this power firing in this situation (''. if it doesn't cover it)."""
    lines = _POWERS.get(key, {}).get(situation) or []
    return rng.choice(lines) if lines else ''


def normalizePosition(position):
    p = str(getattr(position, 'name', position) or '').upper()
    for base in ('QB', 'RB', 'WR', 'TE', 'K'):
        if p.startswith(base):
            return base
    return ''


def assignPower(position, rng=_random, usedCounts=None):
    """Roll ONE career power that covers the player's primary action (so it fires regularly).

    To spread the catalog and avoid duplicates, pass `usedCounts` = {powerKey: how many current
    players already hold it}; assignment then rolls only among the LEAST-held eligible powers (an
    already-assigned power effectively goes to the back of the line and isn't reused until every
    eligible power has been handed out an equal number of times). Returns a power key, or None if
    the position is unknown / no eligible power exists.
    """
    primary = PRIMARY_SITUATION.get(normalizePosition(position))
    if not primary:
        return None
    pool = [k for k in _POWERS if primary in _POWERS[k]]
    if not pool:
        return None
    if usedCounts:
        fewest = min(usedCounts.get(k, 0) for k in pool)
        pool = [k for k in pool if usedCounts.get(k, 0) == fewest]
    return rng.choice(pool)


# ── Charge-status feed beats ────────────────────────────────────────────────────────────────────
# Short play-feed messages as an awakened player's power meter fills. 'powering_up' fires once when
# the meter crosses the midpoint; 'fully_charged' once when it tops out (then it holds, ready to fire).
# {player} is substituted with the player's name. Edit / add variations freely.
CHARGE_STATUS_MESSAGES = {
    'powering_up': [
        '{player} is powering up...',
        '{player} is charging up...',
        '{player} feels the power building...',
        'the air around {player} begins to shimmer...',
    ],
    'fully_charged': [
        '{player} is fully charged...',
        '{player} is at full power...',
        '{player} is ready to unleash their power...',
        '{player} is brimming with power...',
    ],
}


def chargeStatusMessage(status, rng=_random):
    """Return a random feed beat for a charge status ('powering_up' / 'fully_charged'), or '' if none."""
    lines = CHARGE_STATUS_MESSAGES.get(status)
    return rng.choice(lines) if lines else ''
