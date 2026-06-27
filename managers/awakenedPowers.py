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
  All flavor is GENDER-NEUTRAL (singular they/them/their) and apostrophe-free. Names are placeholders.

THE SITUATIONS — what the player is doing when the power fires:
  throw  — the QB completes the pass            run   — the ball-carrier breaks free
  catch  — the receiver hauls it in             kick  — the kicker drills it
  pick   — DEFENSE vs a pass: they intercept    strip — DEFENSE vs a run: they strip the carrier
  (pick + strip are the two halves of defense — written separately so the line always matches what
   actually happened, an interception vs a forced fumble.)
──────────────────────────────────────────────────────────────────────────────────────────────────
"""
import random as _random

# The situations a player can be the focal point of. A power provides flavor only for the ones it
# covers. To add a new situation type, add it here (and wire its effect in the engine).
SITUATIONS = ('throw', 'run', 'catch', 'kick', 'pick', 'strip')

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
        'throw': ['{player} fires it clean through three defenders, good for {yards} yards',
                  'the pass clips through the rush untouched and {player} hits the receiver for {yards} yards'],
        'run':   ['{player} phases clean through the tackle and is gone for {yards} yards',
                  'hands pass right through {player} as they glide {yards} yards downfield'],
        'catch': ['{player} lets the ball pass through the defender and into their hands, good for {yards} yards',
                  '{player} reaches a hand through the corner and pulls it in for {yards} yards'],
        'kick':  ['{player} sends it phasing clean through the line and the uprights'],
        'pick':  ['{player} phases a hand through the receiver and the ball sticks to it',
                  'the throw clips right through {player} and they are suddenly holding it'],
        'strip': ['{player} reaches a hand clean through the runner and pulls the ball out',
                  '{player} clips through the pile and comes out the other side with it']},

    'pixelate': {'name': 'Pixelate', 'concept': 'disassembles into pixels and reassembles downfield',
        'throw': ['{player} scatters the throw into pixels, streams it past the rush, and reforms it in stride for {yards} yards'],
        'run':   ['{player} bursts into pixels and reassembles downfield for {yards} yards',
                  'the tackle closes on a cloud of static and {player} reforms past it, good for {yards} yards'],
        'catch': ['{player} dissolves, drifts past the coverage, and rebuilds around the ball for {yards} yards'],
        'pick':  ['{player} pixel-scatters into the throwing lane and reassembles around the pass'],
        'strip': ['{player} dissolves through the line and rebuilds in the backfield, the ball in hand']},

    'take_flight': {'name': 'Take Flight', 'concept': 'simply takes off and flies',
        'run':   ['{player} lifts off and soars over the defense for {yards} yards',
                  '{player} leaves the turf and glides untouched for {yards} yards'],
        'catch': ['{player} launches into the air, hangs there, and plucks it from the sky for {yards} yards'],
        'pick':  ['{player} takes off, tracks the throw in flight, and snatches it from the air'],
        'strip': ['{player} swoops down on the runner and carries the ball off']},

    # ---- Throw-home (QB) ----
    'railgun': {'name': 'Railgun', 'concept': 'fires the ball like an electromagnetic slug',
        'throw': ['{player} glows white and rifles the spiral on a flat line for {yards} yards',
                  'a crack of electricity and {player} sends it downfield for {yards} yards'],
        'kick':  ['{player} fires it through with a streak of electric light']},

    'wormhole': {'name': 'Wormhole', 'concept': 'folds the field so the ball threads anything',
        'throw': ['{player} folds the coverage shut and threads it through a tunnel for {yards} yards',
                  '{player} folds the throwing window around the ball and drops it in for {yards} yards'],
        'catch': ['{player} opens a pocket of space and the ball drops into their hands, good for {yards} yards'],
        'pick':  ['{player} bends the throw into a fold in the air and it drops into their lap'],
        'strip': ['{player} opens a fold at the runner and the ball falls through it to them']},

    'blink': {'name': 'Blink', 'concept': 'teleports a short hop',
        'throw': ['{player} blinks clear of the rush and lets it fly for {yards} yards'],
        'run':   ['{player} blinks out of the tackle and in again past the line for {yards} yards'],
        'pick':  ['{player} blinks to the ball and arrives before the receiver does'],
        'strip': ['{player} blinks in behind the runner and blinks out holding the ball']},

    # ---- Run-home (RB) ----
    'warp': {'name': 'Warp', 'concept': 'moves at a speed the field cannot track',
        'run':   ['{player} hits warp speed and the defenders freeze mid-stride, gone for {yards} yards',
                  'a smear of motion and {player} is downfield for {yards} yards'],
        'catch': ['{player} warps to the catch point and waits for the ball to arrive, good for {yards} yards'],
        'pick':  ['{player} warps under the throw and is waiting when it arrives'],
        'strip': ['{player} warps to the runner and the ball is gone before the tackle lands']},

    'earthquake': {'name': 'Earthquake', 'concept': 'a seismic stomp that buckles the field',
        'run':   ['{player} stomps once and walks through the flattened front for {yards} yards',
                  '{player} ripples the ground, every tackler falls, and they rumble {yards} yards'],
        'pick':  ['{player} sets off a tremor, the receiver stumbles, and they snatch it'],
        'strip': ['{player} buckles the ground, the ball shakes loose, and they scoop it up']},

    'juggernaut': {'name': 'Juggernaut', 'concept': 'turns to unstoppable iron',
        'run':   ['{player} turns to solid iron and bowls the whole pile over for {yards} yards',
                  'tacklers ragdoll off {player} as they grind forward for {yards} yards'],
        'pick':  ['{player} bulldozes into the pocket and the rushed throw flutters into their iron grip'],
        'strip': ['the runner meets {player} as a wall of iron and the ball pops free']},

    'ice_rink': {'name': 'Ice Rink', 'concept': 'freezes the field to a sheet of ice',
        'run':   ['{player} flashes the turf to ice and skates through the wiping-out defenders for {yards} yards',
                  '{player} glides across a frozen field while everyone else slips, good for {yards} yards'],
        'pick':  ['{player} ices the field over, the receiver slips, and they slide in for the pick'],
        'strip': ['{player} flashes the turf to ice, the runner wipes out, and they skate off with the ball']},

    'freestyle': {'name': 'Freestyle', 'concept': 'literally swims down the field',
        'run':   ['{player} dives in and front-crawls through the defense untouched for {yards} yards',
                  '{player} backstrokes past a diving tackle like it is open water, good for {yards} yards'],
        'catch': ['{player} swims up through the coverage and surfaces with the ball for {yards} yards'],
        'pick':  ['{player} backstrokes into the lane and pulls the pass out of the air'],
        'strip': ['{player} swims through the line and wrestles the ball away from the runner']},

    # ---- Catch-home (WR/TE) ----
    'magnet': {'name': 'Magnet', 'concept': 'turns magnetic to the ball',
        'catch': ['{player} magnetizes the ball out of the air, good for {yards} yards',
                  'the ball ricochets off two defenders and snaps to {player} anyway, {yards} yards'],
        'pick':  ['{player} bends the throw off its line and into their hands',
                  '{player} holds up a palm and the pass drags itself in'],
        'strip': ['{player} tears the ball off the runner and it snaps to their magnetized hands']},

    'flypaper': {'name': 'Flypaper', 'concept': 'their hands are flypaper; nothing comes loose',
        'catch': ['the ball sticks to {player} the instant it arrives, good for {yards} yards',
                  'a defender swats it and it just re-sticks to {player}, who is gone for {yards} yards'],
        'pick':  ['the pass glances off a hand and flypapers to {player}'],
        'strip': ['{player} slaps the ball and it flypapers off the runner into their grip']},

    'rubberband': {'name': 'Rubberband', 'concept': 'arms stretch like taffy',
        'catch': ['{player} stretches an arm ten feet across the seam and reels it in for {yards} yards',
                  '{player} triples their wingspan and plucks the uncatchable, good for {yards} yards'],
        'pick':  ['{player} whips an arm across the field and plucks the throw out of the air'],
        'strip': ['{player} stretches both arms out and lassos the runner, squeezing the ball loose']},

    'octopus': {'name': 'Octopus', 'concept': 'sprouts a tangle of extra arms',
        'catch': ['{player} unfurls eight arms and there is no dropping it now, good for {yards} yards',
                  '{player} swallows the ball out of the air with a forest of hands for {yards} yards'],
        'pick':  ['{player} blankets the route with a dozen arms and comes down with the pass'],
        'strip': ['{player} wraps the runner in eight arms and peels the ball away']},

    'colossus': {'name': 'Colossus', 'concept': 'grows to fill the field',
        'catch': ['{player} expands to fill the end zone and boxes everyone out for it, good for {yards} yards'],
        'run':   ['{player} swells to giant size and steps over the entire defense for {yards} yards'],
        'pick':  ['{player} grows into a wall and bats the pass down into their own hands'],
        'strip': ['{player} swells to giant size and plucks the runner and the ball off the turf']},

    # ---- Kick-home (K) — offense only (no defensive position) ----
    'moonshot': {'name': 'Moonshot', 'concept': 'kicks it into orbit',
        'kick': ['{player} boots it through with a vapor trail',
                 '{player} sends it clearing the uprights and climbing out of the stadium']},

    'tractor_beam': {'name': 'Tractor Beam', 'concept': 'the target pulls the ball in',
        'kick': ['{player} leans the uprights in and tractors the ball straight through'],
        'catch': ['{player} locks a beam on and drags the ball into their hands for {yards} yards'],
        'pick':  ['{player} locks a beam on the throw and reels it in'],
        'strip': ['{player} latches a tractor beam on the ball and drags it off the runner']},

    'trebuchet': {'name': 'Trebuchet', 'concept': 'launches it like a siege engine',
        'kick': ['{player} winds up like a trebuchet and the ball rains down through the posts'],
        'throw': ['{player} cranks back and catapults the ball the length of the field for {yards} yards']},

    # ---- Defense-rich ----
    'black_hole': {'name': 'Black Hole', 'concept': 'opens a collapsing gravity well',
        'run':     ['{player} drags the defenders off their feet toward the gap and slips through for {yards} yards'],
        'catch':   ['{player} opens a well at their chest and the ball cannot escape it, good for {yards} yards'],
        'pick':    ['{player} opens a well in the lane and the pass spirals into the dark, into their hands'],
        'strip':   ['{player} opens a well behind the line that swallows the runner, the ball rolling out to them']},

    'pickpocket': {'name': 'Pickpocket', 'concept': 'lifts the ball clean like a wallet',
        'run':     ['{player} slips a hand free of the tackle and keeps the ball moving for {yards} yards'],
        'pick':    ['{player} picks the pass clean out of the air, smooth as lifting a wallet'],
        'strip':   ['{player} dissolves the grip and scoops the ball clean',
                    '{player} peels the ball off the runner mid-stride and takes off']},

    'rewind': {'name': 'Rewind', 'concept': 'rewinds a couple seconds to be where they need to be',
        'catch':   ['{player} drops it, rewinds two seconds, and brings it in clean for {yards} yards'],
        'pick':    ['{player} was a step late, so they rewind and arrive early for the pick'],
        'strip':   ['{player} replays the handoff and arrives in time to take the ball']},

    # ---- Throw-home (QB) ----
    'comet': {'name': 'Comet', 'concept': 'the ball ignites into a comet',
        'throw': ['{player} ignites the ball and streaks it downfield trailing fire for {yards} yards',
                  '{player} sends a comet tail chasing the spiral into stride, good for {yards} yards'],
        'kick':  ['{player} flares the ball into a comet and burns it through the uprights']},
    'slingshot': {'name': 'Slingshot', 'concept': 'fires the ball off a giant slingshot',
        'throw': ['{player} loads the ball into a slingshot and snaps it across the field for {yards} yards',
                  '{player} rockets the ball off an invisible band into the receiver for {yards} yards'],
        'kick':  ['{player} slingshots it off the laces and it screams through']},
    'orbital': {'name': 'Orbital', 'concept': 'sends the ball to low orbit and back',
        'throw': ['{player} lofts it into low orbit and it drops downfield for {yards} yards',
                  '{player} sends the ball out of the atmosphere and it re-enters into a receiver for {yards} yards'],
        'kick':  ['{player} climbs it out of sight and it drops back through the posts']},
    'heat_seeker': {'name': 'Heat-Seeker', 'concept': 'the ball locks on and homes in',
        'throw': ['{player} locks the ball onto the receiver and it corrects mid-flight for {yards} yards',
                  '{player} banks it around a defender like it has a guidance chip, good for {yards} yards'],
        'catch': ['{player} homes the ball in and it thumps into their chest for {yards} yards'],
        'pick':  ['{player} locks the pass onto themselves and curls it into their hands'],
        'strip': ['{player} heat-seeks the ball off the runner and homes it straight in']},
    'auto_aim': {'name': 'Auto-Aim', 'concept': 'a crosshair snaps to the target',
        'throw': ['{player} snaps a crosshair to the receiver and the ball follows it in for {yards} yards',
                  '{player} locks the target and the throw cannot miss, good for {yards} yards'],
        'kick':  ['{player} settles the reticle on the posts and the kick auto-corrects through'],
        'pick':  ['{player} jumps the lock-on and the throw follows it in'],
        'strip': ['{player} paints the runner and the ball auto-ejects into their hands']},
    'telepathy': {'name': 'Telepathy', 'concept': 'thrower and catcher share one mind',
        'throw': ['{player} thinks the route and the receiver is already there for {yards} yards',
                  '{player} needs no signal and puts it exactly where both of them know, good for {yards} yards'],
        'catch': ['{player} reads the throw before it leaves the hand and is waiting for {yards} yards']},
    'smoke_bomb': {'name': 'Smoke Bomb', 'concept': 'vanishes in a puff of smoke',
        'throw': ['{player} vanishes in a puff of smoke and the ball comes out of the cloud for {yards} yards',
                  'the rush hits smoke and {player} is already gone, hitting the receiver for {yards} yards'],
        'run':   ['{player} drops a smoke bomb and reappears past the line for {yards} yards'],
        'pick':  ['{player} vanishes in smoke and steps out of it under the throw'],
        'strip': ['{player} blinds the runner with a smoke bomb and lifts the ball in the haze']},
    'trapdoor': {'name': 'Trapdoor', 'concept': 'drops through a trapdoor and pops up elsewhere',
        'throw': ['{player} drops through a trapdoor and the throw comes from somewhere new for {yards} yards',
                  '{player} leaves the pocket collapsing on an empty patch of grass and hits the receiver for {yards} yards'],
        'run':   ['{player} falls through a trapdoor and pops up upfield for {yards} yards'],
        'pick':  ['{player} drops a trapdoor into the lane right as the ball arrives'],
        'strip': ['{player} drops the runner through a trapdoor and grabs the ball on the way down']},
    'bullet_time': {'name': 'Bullet Time', 'concept': 'time crawls to a stop around them',
        'throw': ['{player} crawls the world to a stop and picks the seam at their leisure for {yards} yards'],
        'run':   ['{player} slows everything to a crawl and strolls between frozen defenders for {yards} yards'],
        'catch': ['{player} stutters time and reels it in while the ball hangs still, good for {yards} yards'],
        'pick':  ['{player} slows time and steps in front of a ball that is barely moving'],
        'strip': ['{player} slows time and plucks the ball from the frozen runner']},
    'decoy': {'name': 'Decoy', 'concept': 'leaves a decoy for the defense to hit',
        'throw': ['{player} lets the rush tackle a cardboard cutout and throws free for {yards} yards'],
        'run':   ['{player} leaves a decoy behind and slips away with the ball for {yards} yards'],
        'pick':  ['{player} lets the receiver break on a decoy and takes the throw'],
        'strip': ['{player} sends a decoy at the runner, who cuts into the real one, and lifts the ball']},
    'grease': {'name': 'Grease', 'concept': 'too slippery to hold onto',
        'throw': ['{player} greases free as the sack slides right off and fires for {yards} yards'],
        'run':   ['{player} sheds the tacklers like they are coated in grease for {yards} yards'],
        'pick':  ['{player} lets the throw skid off a greased receiver and into their hands'],
        'strip': ['{player} squirts through a greased gap and the ball slides out of the runner into them']},
    'jelly': {'name': 'Jelly', 'concept': 'turns to jelly and oozes free',
        'throw': ['{player} turns to jelly, oozes out of the sack, and slings it for {yards} yards'],
        'run':   ['arms pass through the jellied body of {player} and they wobble onward for {yards} yards'],
        'pick':  ['{player} jiggles into the lane and the ball sticks in the jelly'],
        'strip': ['{player} gums up the runner and the ball oozes free into their hands']},

    # ---- Run-home (RB) ----
    'treadmill': {'name': 'Treadmill', 'concept': 'the turf becomes a treadmill for everyone else',
        'run':   ['{player} turns the turf to a treadmill and the pursuers sprint nowhere, gone for {yards} yards',
                  '{player} pulls away while the defenders churn in place, good for {yards} yards'],
        'pick':  ['{player} turns the route to a treadmill and walks in front for the pick'],
        'strip': ['{player} turns the runner lane to a treadmill and reels them in for the ball']},
    'slipstream': {'name': 'Slipstream', 'concept': 'drags a vacuum that sucks pursuit backward',
        'run':   ['{player} tucks into a slipstream and the field blurs past for {yards} yards',
                  '{player} opens a vacuum behind them that sucks the pursuit backward, good for {yards} yards'],
        'pick':  ['{player} rides a slipstream into the lane and snatches the throw'],
        'strip': ['{player} rides the runner slipstream right up and lifts the ball']},
    'hyperdrive': {'name': 'Hyperdrive', 'concept': 'jumps to lightspeed',
        'run':   ['{player} punches the hyperdrive and streaks downfield for {yards} yards',
                  'stars smear and {player} is suddenly gone for {yards} yards'],
        'catch': ['{player} jumps to the catch point before the ball arrives, good for {yards} yards'],
        'pick':  ['{player} hyperdrives across the field and is under the throw'],
        'strip': ['{player} hyperdrives into the runner and the ball is gone in a blur']},
    'fast_forward': {'name': 'Fast-Forward', 'concept': 'fast-forwards while everyone else plays normal speed',
        'run':   ['{player} fast-forwards through the defense while everyone else plays at normal speed for {yards} yards'],
        'catch': ['{player} fast-forwards to the spot and the ball catches up to them for {yards} yards'],
        'throw': ['{player} fast-forwards out of the rush, sets their feet, and fires for {yards} yards'],
        'pick':  ['{player} fast-forwards to the ball and arrives a beat early for the pick'],
        'strip': ['{player} fast-forwards to the runner and the ball pops out before the tackle forms']},
    'conveyor_belt': {'name': 'Conveyor Belt', 'concept': 'the turf carries them like a belt',
        'run':   ['{player} turns the turf to a conveyor and is whisked past everyone for {yards} yards',
                  'a belt under the feet of {player} carries them clear of the pile for {yards} yards'],
        'pick':  ['{player} belts the ball off its line into their hands'],
        'strip': ['{player} belts the carrier straight in and the ball comes loose']},
    'moses': {'name': 'Moses', 'concept': 'parts the defense down the middle',
        'run':   ['{player} raises a hand and the defense parts down the middle for {yards} yards',
                  'the front splits like a sea and {player} walks through the gap for {yards} yards'],
        'pick':  ['{player} parts the coverage and walks into the throwing lane for the pick'],
        'strip': ['{player} parts the line, meets the runner, and lifts the ball as they pass']},
    'centipede': {'name': 'Centipede', 'concept': 'sprouts a dozen extra legs',
        'run':   ['{player} sprouts a dozen extra legs and scuttles past the tackle for {yards} yards',
                  '{player} grows centipede legs and skitters through traffic for {yards} yards'],
        'pick':  ['{player} swarms the route with a hundred legs and snags the pass'],
        'strip': ['{player} swarms the carrier with a hundred legs and pries the ball free']},
    'big_bad_wolf': {'name': 'Big Bad Wolf', 'concept': 'huffs and puffs and blows them down',
        'run':   ['{player} huffs, puffs, and blows the front seven flat for {yards} yards',
                  '{player} scatters the defense like leaves with a gale from the lungs, good for {yards} yards'],
        'pick':  ['{player} blows the pass off course and into their hands with one big breath'],
        'strip': ['{player} knocks the carrier down with one big breath and the ball pops loose']},
    'boulder': {'name': 'Boulder', 'concept': 'turns to solid rock',
        'run':   ['{player} turns to solid rock and grinds the pile backward for {yards} yards',
                  'tacklers shatter against the half-ton of granite that is {player}, gone for {yards} yards'],
        'catch': ['{player} sets like a boulder and nobody is moving them off the ball, good for {yards} yards'],
        'pick':  ['{player} sets like a boulder in the lane and the pass caroms into their hands'],
        'strip': ['the runner hits {player} like an immovable boulder and the ball jars loose']},
    'afterimage': {'name': 'Afterimage', 'concept': 'leaves afterimages the defense covers instead',
        'run':   ['the defender tackles an afterimage and {player} is already gone for {yards} yards',
                  '{player} leaves a trail of ghosts and the tackle hits the wrong one, good for {yards} yards'],
        'catch': ['{player} lets the corner cover an afterimage and makes the catch clean for {yards} yards'],
        'pick':  ['{player} lets the receiver break on an afterimage and takes the ball'],
        'strip': ['{player} flickers past the blocker as an afterimage and pops the ball from the runner']},
    'origami': {'name': 'Origami', 'concept': 'folds flat as paper',
        'run':   ['{player} folds flat as paper and slips between two tacklers for {yards} yards',
                  '{player} creases sideways through a gap no one else could, gone for {yards} yards'],
        'catch': ['{player} folds around the defender and unfolds with the ball for {yards} yards'],
        'pick':  ['{player} folds flat, slides into the lane, and snatches the pass'],
        'strip': ['{player} folds thin through the line and creases the ball out of the runner']},
    'clone': {'name': 'Clone', 'concept': 'splits into a crowd of copies',
        'run':   ['{player} splits into three and the defense tackles the wrong two, gone for {yards} yards',
                  '{player} floods the gap with copies and breaks free for {yards} yards'],
        'catch': ['{player} clears out the coverage with two clones and catches it clean for {yards} yards'],
        'pick':  ['{player} blankets the route with a swarm of clones and picks it off'],
        'strip': ['{player} swarms the runner with clones and comes away with the ball']},
    'matrix': {'name': 'Matrix', 'concept': 'bends impossibly to dodge',
        'run':   ['{player} bends impossibly backward under the tackle and keeps running for {yards} yards',
                  '{player} leans into a bullet-dodge and the arms whiff past, gone for {yards} yards'],
        'throw': ['{player} bends backward out of the sack and throws upside down for {yards} yards'],
        'pick':  ['{player} bends backward into the lane and lifts the pass out of the air'],
        'strip': ['{player} bends under the block and rises with the ball stripped from the runner']},
    'limbo': {'name': 'Limbo', 'concept': 'bends flat under the tackle',
        'run':   ['{player} limbos under the tackle, flat to the turf, and pops back up for {yards} yards',
                  '{player} bends so low the arms sail over and slides through for {yards} yards'],
        'pick':  ['{player} limbos under the throw and pops up cradling it'],
        'strip': ['{player} limbos under the blocker, trips the runner, and takes the ball']},
    'heartthrob': {'name': 'Heartthrob', 'concept': 'the defenders fall in love',
        'run':   ['the defenders swoon and wave {player} through with hearts in their eyes for {yards} yards',
                  'the tacklers stop to admire {player} and let the run go by for {yards} yards'],
        'catch': ['{player} leaves the corner too smitten to contest the catch, good for {yards} yards'],
        'pick':  ['{player} leaves the receiver too smitten to fight for it and takes the pick'],
        'strip': ['{player} leaves the ball-carrier lovestruck and frozen, and the ball comes right over']},
    'shrink_ray': {'name': 'Shrink Ray', 'concept': 'shrinks to slip past',
        'run':   ['{player} shrinks to ant-size and scurries between the tacklers feet for {yards} yards',
                  '{player} zaps tiny and the tackle closes on empty air, gone for {yards} yards'],
        'catch': ['{player} shrinks under the coverage and grabs it at shoelace height for {yards} yards'],
        'pick':  ['{player} shrinks, darts under the throw, and snatches it at shoelace height'],
        'strip': ['{player} shrinks, darts under the runner, and pops the ball out']},
    'skunk': {'name': 'Skunk', 'concept': 'stinks so bad everyone avoids them',
        'run':   ['the stench off {player} clears a lane and the defenders gag and give room for {yards} yards',
                  'nobody wants within five yards of {player} and the smell, gone for {yards} yards'],
        'catch': ['{player} backs the corner off the smell and catches it uncovered for {yards} yards'],
        'pick':  ['{player} gags the receiver off and takes the pass uncontested'],
        'strip': ['{player} reeks so badly the carrier recoils and coughs up the ball']},
    'liquify': {'name': 'Liquify', 'concept': 'turns to liquid and pours through',
        'run':   ['{player} turns to liquid and pours through the gap in the line for {yards} yards',
                  'the tackle splashes through a puddle where {player} used to be, gone for {yards} yards'],
        'pick':  ['{player} pours into the lane and the ball drops into the puddle'],
        'strip': ['{player} flows around the runner and re-forms holding the ball']},
    'sandman': {'name': 'Sandman', 'concept': 'puts the defenders to sleep',
        'run':   ['the defenders yawn and drop off to sleep as {player} jogs past for {yards} yards',
                  '{player} rolls a wave of drowsiness over the front and strolls through for {yards} yards'],
        'catch': ['{player} lets the corner nod off and catches it in peace for {yards} yards'],
        'pick':  ['{player} lets the receiver nod off and plucks the pass from sleeping hands'],
        'strip': ['{player} dozes the ball-carrier off and the ball slips out of their arms']},
    'photobomb': {'name': 'Photobomb', 'concept': 'pops up suddenly behind the defense',
        'run':   ['{player} blinks out and photobombs the play downfield for {yards} yards',
                  '{player} is suddenly behind the whole defense, grinning, gone for {yards} yards'],
        'catch': ['{player} pops up uncovered behind the secondary for the grab, good for {yards} yards'],
        'pick':  ['{player} pops up uncovered in the lane and takes the throw'],
        'strip': ['{player} photobombs into the backfield and lifts the ball before the runner sees them']},
    'avalanche': {'name': 'Avalanche', 'concept': 'comes down like an avalanche',
        'run':   ['{player} rolls a wall of snow and bodies downhill and buries the defense for {yards} yards',
                  '{player} comes down like an avalanche and sweeps the front away for {yards} yards'],
        'pick':  ['{player} crashes an avalanche of bodies down and the pass tumbles into their hands'],
        'strip': ['{player} buries the runner in an avalanche and digs the ball out']},
    'stampede': {'name': 'Stampede', 'concept': 'multiplies into a trampling herd',
        'run':   ['{player} multiplies into a thundering herd and tramples the front for {yards} yards',
                  '{player} floods the lane with a stampede of copies and flattens everything, gone for {yards} yards'],
        'pick':  ['{player} floods the route with a stampede and one of the herd snags the pass'],
        'strip': ['{player} rolls a stampede over the carrier and the ball comes loose']},
    'steamroller': {'name': 'Steamroller', 'concept': 'flattens everyone like a roller',
        'run':   ['{player} flattens the first wave into the turf like a steamroller for {yards} yards',
                  'the defenders go two-dimensional under {player} the roller, gone for {yards} yards'],
        'pick':  ['{player} flattens the pocket and the rushed throw wobbles into their hands'],
        'strip': ['{player} steamrolls the runner flat and peels the ball off the turf']},
    'tank': {'name': 'Tank', 'concept': 'rolls forward as an actual tank',
        'run':   ['{player} rolls forward as a tank and the line bounces off the treads for {yards} yards',
                  'the hull of {player} shrugs off arm tackles and grinds ahead for {yards} yards'],
        'pick':  ['{player} rolls the tank into the lane and the pass clanks off the hull into their hands'],
        'strip': ['{player} crashes the tank through, crushes the run, and the ball spills out']},
    'cannonball': {'name': 'Cannonball', 'concept': 'curls into a cannonball and rolls through',
        'run':   ['{player} curls into a cannonball and bowls straight through the pile for {yards} yards',
                  '{player} tucks and rolls over the top of the tacklers for {yards} yards'],
        'pick':  ['{player} cannonballs into the lane and the ball ricochets into their arms'],
        'strip': ['{player} cannonballs into the backfield and blasts the ball loose']},
    'bowling_ball': {'name': 'Bowling Ball', 'concept': 'the defenders are bowling pins',
        'run':   ['{player} rolls into the front seven and the defenders scatter like pins for {yards} yards',
                  '{player} strikes and the whole line goes down in a clatter, gone for {yards} yards'],
        'pick':  ['{player} rolls into the route, scatters it, and the ball rolls to them'],
        'strip': ['{player} bowls into the backfield, the runner goes down like a pin, and the ball comes loose']},

    # ---- Catch-home (WR/TE) ----
    'third_arm': {'name': 'Third Arm', 'concept': 'sprouts a third arm',
        'catch': ['{player} sprouts a third arm from the chest and snags the high ball for {yards} yards',
                  '{player} reaches an extra hand up where two could not, good for {yards} yards'],
        'pick':  ['{player} shoots a third arm out and plucks the pass from the air'],
        'strip': ['{player} reaches a third arm in and tears the ball from the runner']},
    'vacuum': {'name': 'Vacuum', 'concept': 'inhales the ball in',
        'catch': ['{player} inhales and the ball gets sucked straight into their grip for {yards} yards',
                  '{player} opens a vacuum at the chest and the ball cannot resist, good for {yards} yards'],
        'pick':  ['{player} sucks the pass off its line and into their hands'],
        'strip': ['{player} switches on the vacuum and inhales the ball off the runner']},
    'gravity_well': {'name': 'Gravity Well', 'concept': 'opens a well the ball falls into',
        'catch': ['{player} opens a gravity well at their palms and the ball drops in for {yards} yards',
                  '{player} curves the ball down out of its arc into their hands, good for {yards} yards'],
        'pick':  ['{player} bends the throw into the well at their chest'],
        'strip': ['{player} opens a well under the runner and the ball drops out of their arms into it']},
    'web_shooter': {'name': 'Web-Shooter', 'concept': 'shoots a web and reels it in',
        'catch': ['{player} fires a web at the ball and reels it into their hands for {yards} yards',
                  '{player} snaps a strand out and yanks the catch back for {yards} yards'],
        'pick':  ['{player} webs the throw out of the air and reels it in'],
        'strip': ['{player} webs the ball off the runner and yanks it back']},
    'do_over': {'name': 'Do-Over', 'concept': 'rewinds a drop and redoes it',
        'catch': ['{player} drops it, rewinds two seconds, and brings it in clean for {yards} yards',
                  '{player} un-happens the bobble and settles the ball into their hands for {yards} yards'],
        'pick':  ['{player} misses the jump, rewinds, and times it perfectly for the pick'],
        'strip': ['{player} whiffs the strip, rewinds, and rips it loose on the second try']},
    'good_boy': {'name': 'Good Boy', 'concept': 'the ball becomes a loyal dog',
        'catch': ['{player} turns the ball into a loyal dog and it bounds into their arms for {yards} yards',
                  'the ball trots over and curls up in the hands of {player}, good for {yards} yards'],
        'pick':  ['the ball decides it likes {player} better and leaps into their arms'],
        'strip': ['the ball wriggles loose from the runner and trots over to {player}']},
    'invisible_ink': {'name': 'Invisible Ink', 'concept': 'the ball turns invisible',
        'catch': ['{player} turns the ball invisible and the corner has no idea they have it, good for {yards} yards',
                  'the defense loses the ball and only {player} knows where it lands, gone for {yards} yards'],
        'throw': ['{player} vanishes the ball in flight and it reappears in the receiver hands for {yards} yards'],
        'pick':  ['{player} can still see the invisible ball and steps in front of it'],
        'strip': ['{player} turns the ball invisible, the runner loses it, and they scoop it up']},
    'slinky': {'name': 'Slinky', 'concept': 'arms coil out like a slinky',
        'catch': ['{player} coils an arm out like a slinky and grabs the overthrow for {yards} yards',
                  '{player} springs a coiled arm across the seam and reels it in for {yards} yards'],
        'pick':  ['{player} springs a slinky arm out and snatches the throw down'],
        'strip': ['{player} coils a slinky arm around the runner and springs back with the ball']},
    'telescope': {'name': 'Telescope', 'concept': 'arms telescope out',
        'catch': ['{player} telescopes both arms out ten feet and plucks it from the sky for {yards} yards',
                  '{player} extends like a spyglass and snags the uncatchable for {yards} yards'],
        'pick':  ['{player} shoots a telescoping arm out and intercepts the pass'],
        'strip': ['{player} reaches a telescoping arm in and plucks the ball from the runner']},
    'gumby': {'name': 'Gumby', 'concept': 'bends and stretches like clay',
        'catch': ['{player} stretches a rubber arm up and reels the high ball in for {yards} yards',
                  '{player} bends like clay and wraps around the ball, good for {yards} yards'],
        'run':   ['{player} bends around the tackle like a rubber toy and keeps going for {yards} yards'],
        'pick':  ['{player} stretches a rubber arm across the lane and snags the pass'],
        'strip': ['{player} stretches around the runner and peels the ball free']},
    'fishing_rod': {'name': 'Fishing Rod', 'concept': 'casts an arm out like a line',
        'catch': ['{player} casts an arm out like a line and hooks the ball in for {yards} yards',
                  '{player} reels the overthrow back like a prize catch, good for {yards} yards'],
        'pick':  ['{player} casts out, hooks the pass, and reels in the pick'],
        'strip': ['{player} casts a line around the runner and reels the ball in']},
    'butterfly_net': {'name': 'Butterfly Net', 'concept': 'pulls a giant net from nowhere',
        'catch': ['{player} pulls a giant net from their sleeve and scoops the ball in for {yards} yards',
                  '{player} swallows the deep ball out of the air with the net, good for {yards} yards'],
        'pick':  ['{player} swings a net across the lane and bags the pass'],
        'strip': ['{player} drops a net over the runner and scoops the ball out']},
    'kaiju': {'name': 'Kaiju', 'concept': 'grows into a monster',
        'catch': ['{player} grows into a kaiju and plucks it over the tiny defenders for {yards} yards',
                  '{player} closes a monster hand around the ball above the crowd for {yards} yards'],
        'run':   ['{player} towers up kaiju-sized and stomps through the defense for {yards} yards'],
        'pick':  ['{player} swells into a kaiju and swats the pass out of the air into their hands'],
        'strip': ['{player} closes a kaiju hand over the runner and plucks the ball away']},
    'redwood': {'name': 'Redwood', 'concept': 'grows into a towering tree',
        'catch': ['{player} grows into a redwood and high-points it above everyone for {yards} yards',
                  '{player} digs roots in and rises untouchable over the corner, good for {yards} yards'],
        'pick':  ['{player} grows into a redwood and the pass lodges in the branches'],
        'strip': ['{player} plants like a redwood, the runner crumples against the trunk, and the ball comes loose']},
    'monolith': {'name': 'Monolith', 'concept': 'becomes an immovable slab',
        'catch': ['{player} hardens into a monolith and boxes everyone off the ball for {yards} yards',
                  '{player} rises like a black slab and the defenders bounce away from the catch, good for {yards} yards'],
        'pick':  ['{player} rises like a monolith in the lane and the pass rebounds into their hands'],
        'strip': ['{player} slams down like a monolith on the runner and the ball squirts free']},
    'hot_air': {'name': 'Hot Air', 'concept': 'inflates and floats over everyone',
        'catch': ['{player} inflates like a balloon and floats up over the secondary for {yards} yards',
                  '{player} puffs full of hot air and rises above the crowd for it, good for {yards} yards'],
        'pick':  ['{player} balloons up into the lane and smothers the throw'],
        'strip': ['{player} inflates over the runner and the ball pops out as they go down']},
    'eclipse': {'name': 'Eclipse', 'concept': 'blots out the sun over the defender',
        'catch': ['{player} blots out the sun over the corner and catches it in the dark for {yards} yards',
                  '{player} drops a shadow over the defender and the ball is theirs, good for {yards} yards'],
        'pick':  ['{player} eclipses the receiver and picks it in the shade'],
        'strip': ['{player} drops darkness over the runner and takes the ball in the black']},

    # ---- Kick-home (K) — offense only ----
    'mortar': {'name': 'Mortar', 'concept': 'drops it in like a mortar round',
        'kick': ['{player} drops it in like a mortar round and it craters through the posts',
                 '{player} lofts a high arcing shell that comes straight down through the uprights']},
    'big_bertha': {'name': 'Big Bertha', 'concept': 'fires the giant cannon',
        'kick': ['{player} sets off Big Bertha and the ball booms through',
                 '{player} fires a cannon blast and the kick is good from the other end zone']},
    'autopilot': {'name': 'Autopilot', 'concept': 'the kick steers itself',
        'kick':  ['{player} flips on autopilot and the kick steers itself through',
                  '{player} takes their hands off and the ball corrects course and splits the posts'],
        'throw': ['{player} sets it to autopilot and the throw flies itself to the receiver for {yards} yards'],
        'pick':  ['{player} lets autopilot route them under the throw for the pick'],
        'strip': ['{player} lets autopilot steer them to the runner and the ball pops into their hands']},
    'gps': {'name': 'GPS', 'concept': 'navigates the ball by coordinates',
        'kick':  ['{player} punches in the coordinates and the ball navigates through',
                  '{player} reroutes and the kick threads it dead center'],
        'throw': ['{player} locks the receiver coordinates and the ball routes in for {yards} yards'],
        'pick':  ['{player} gets a fix on the throw and intercepts the route'],
        'strip': ['{player} navigates straight to the runner and reroutes the ball to themselves']},
    'magnet_posts': {'name': 'Magnet Posts', 'concept': 'the uprights magnetize the ball',
        'kick': ['{player} magnetizes the uprights and drags the kick dead through the middle',
                 '{player} lets the posts pull the ball in no matter the angle']},
    'laser_guided': {'name': 'Laser-Guided', 'concept': 'paints the target with a laser',
        'kick':  ['{player} paints the posts with a laser and the kick rides the beam through',
                  '{player} lights the target and the ball tracks the laser dead center'],
        'throw': ['{player} laser-paints the receiver and the throw rides the line in for {yards} yards'],
        'pick':  ['{player} paints the ball and cuts off the route for the pick'],
        'strip': ['{player} laser-paints the carrier and the ball tracks off them into their hands']},

    # ---- Defense-leaning (given an offensive situation so they are assignable) ----
    'highway_robbery': {'name': 'Highway Robbery', 'concept': 'robs the ball in broad daylight',
        'catch': ['{player} snatches it like it was theirs all along and strolls off for {yards} yards'],
        'pick':  ['{player} jumps the throw and rolls out a red carpet for the pick',
                  '{player} robs the receiver blind and takes the pick'],
        'strip': ['{player} sticks up the runner in broad daylight and makes off with the ball']},
    'ball_magnet': {'name': 'Ball Magnet', 'concept': 'the ball is drawn to them',
        'catch': ['{player} curves the ball off its line and sticks it to their hands for {yards} yards'],
        'pick':  ['{player} bends the throw across the field and magnetizes it into their hands',
                  'no matter where it is aimed, the ball ends up with {player}'],
        'strip': ['{player} tears the ball off the runner and it flies straight to them']},
    'the_heist': {'name': 'The Heist', 'concept': 'a planned, clean robbery',
        'catch': ['{player} planned the whole thing and was always taking this one, good for {yards} yards'],
        'pick':  ['{player} runs the heist clean and lifts the pass',
                  'the crew sets a screen and {player} makes off with the interception'],
        'strip': ['{player} pulls the job off without a hitch and the runner never feels the ball leave']},
    'portal': {'name': 'Portal', 'concept': 'opens portals across the field',
        'throw': ['{player} opens a portal and the ball comes out the other side downfield for {yards} yards'],
        'run':   ['{player} steps into a portal at the line and out of one past the secondary for {yards} yards'],
        'catch': ['{player} opens a portal at their hands and the ball drops through it for {yards} yards'],
        'pick':  ['{player} reaches a hand through a portal and pulls the pass from the air'],
        'strip': ['{player} opens a portal at the runner and the ball drops through it to them']},
    'telekinesis': {'name': 'Telekinesis', 'concept': 'moves the ball with their mind',
        'throw': ['{player} steers the ball downfield with a flick of the mind for {yards} yards'],
        'catch': ['{player} pulls the ball into their hands without touching it for {yards} yards'],
        'pick':  ['{player} yanks the throw out of the air with their mind'],
        'strip': ['{player} freezes the carrier and lifts the ball straight out of their arms']},
    'premonition': {'name': 'Premonition', 'concept': 'already saw this play happen',
        'throw': ['{player} saw this throw a minute ago and the receiver is already open, good for {yards} yards'],
        'catch': ['{player} dreamed this catch last night and runs to the spot for {yards} yards'],
        'pick':  ['{player} knew the play before the snap and is already there for the pick'],
        'strip': ['a premonition puts {player} on the runner and the ball is theirs before it happens']},
    'insider_trading': {'name': 'Insider Trading', 'concept': 'had the call sheet',
        'catch': ['{player} had the call sheet and breaks before the ball is thrown, good for {yards} yards'],
        'pick':  ['{player} got the tip and is sitting on the route for the pick',
                  '{player} traded on inside info and cashes in the interception'],
        'strip': ['{player} knew the handoff was coming and picks the runner clean']},
    'the_vacuum': {'name': 'The Vacuum', 'concept': 'vacuums the ball loose',
        'run':   ['{player} vacuums a path clear and rushes through the gap for {yards} yards'],
        'pick':  ['{player} switches on the vacuum and sucks the pass out of the air'],
        'strip': ['{player} switches on the vacuum and sucks the ball clean out of the arms',
                  '{player} hoovers the ball loose and scoops it']},
    'repo_man': {'name': 'Repo Man', 'concept': 'repossesses the ball',
        'catch': ['{player} repossesses the ball like a missed payment, good for {yards} yards'],
        'pick':  ['{player} shows up with paperwork and repossesses the pass mid-air'],
        'strip': ['{player} calls the ball overdue and repossesses it off the runner']},
    'crowbar': {'name': 'Crowbar', 'concept': 'pries the ball loose with a crowbar',
        'run':   ['{player} pries the pile apart with a crowbar and squeezes through for {yards} yards'],
        'pick':  ['{player} pries the pass out of the air with a crowbar'],
        'strip': ['{player} jams a crowbar in and pops the ball loose from the runner',
                  '{player} gives it one good pry and the ball is theirs']},
    'magnet_hands': {'name': 'Magnet Hands', 'concept': 'magnetized hands rip it free',
        'catch': ['the ball snaps to the magnetized hands of {player} for {yards} yards'],
        'pick':  ['the throw snaps to the magnetized hands of {player}'],
        'strip': ['{player} magnetizes their hands and rips the ball off the runner',
                  'the ball jumps to the palms of {player} off the handoff']},
    'tax_man': {'name': 'Tax Man', 'concept': 'comes to collect their cut',
        'catch': ['{player} collects their cut, the ball was always owed to them, good for {yards} yards'],
        'pick':  ['{player} comes for their share and intercepts it',
                  'nothing is certain but the interception {player} just levied'],
        'strip': ['{player} collects, taking the ball right off the runner']},
    'quicksand': {'name': 'Quicksand', 'concept': 'turns the field to quicksand',
        'run':   ['{player} turns the turf behind them to quicksand and the pursuit sinks, gone for {yards} yards'],
        'pick':  ['{player} turns the lane to quicksand, the receiver bogs down, and they take the ball'],
        'strip': ['{player} turns the backfield to quicksand, the runner sinks, and they lift the ball',
                  '{player} sinks the carrier to the knees and takes the ball']},
    'sinkhole': {'name': 'Sinkhole', 'concept': 'opens a sinkhole under the play',
        'run':   ['{player} opens a sinkhole behind them and the pursuit drops in, gone for {yards} yards'],
        'pick':  ['{player} drops the receiver into a sinkhole and snatches the pass over the hole'],
        'strip': ['{player} opens the ground under the runner and the ball rolls to them',
                  '{player} drops the carrier into a sinkhole and the ball rolls to them']},
    'riptide': {'name': 'Riptide', 'concept': 'drags the defense out to sea',
        'run':   ['{player} pulls the defenders out to sea with a riptide and cuts upfield for {yards} yards'],
        'pick':  ['{player} drags the route out to sea with a riptide and collects the floating ball'],
        'strip': ['{player} drags the carrier backward with a riptide and the ball floats free',
                  '{player} yanks the carrier down in the current and the ball floats free']},
    'teleport': {'name': 'Teleport', 'concept': 'teleports anywhere on the field',
        'throw': ['{player} teleports out of the pocket and throws from clean grass for {yards} yards'],
        'run':   ['{player} blinks out at the line and rematerializes downfield for {yards} yards'],
        'catch': ['{player} teleports to the landing spot and catches it in stride for {yards} yards'],
        'pick':  ['{player} teleports into the lane before the throw arrives'],
        'strip': ['{player} teleports into the backfield before the handoff lands and takes the ball']},
    'implosion': {'name': 'Implosion', 'concept': 'collapses everything inward',
        'run':   ['{player} implodes the line inward and shoots through the vacuum for {yards} yards'],
        'pick':  ['{player} implodes the lane and the ball collapses inward into their hands'],
        'strip': ['{player} implodes the backfield and the ball ends up in their hands',
                  '{player} folds everything inward and the ball is theirs']},
    'demolition': {'name': 'Demolition', 'concept': 'demolishes the play',
        'run':   ['{player} demolishes the front and walks through the rubble for {yards} yards'],
        'pick':  ['{player} blows up the pocket and the wounded throw drops to them'],
        'strip': ['{player} brings the whole backfield down in a demolition',
                  '{player} blows the play apart in a cloud of dust and comes out with the ball']},
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
