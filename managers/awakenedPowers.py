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
        'throw': ['the ball phases straight through three defenders untouched',
                  'the pass clips through a linebacker like he is not there'],
        'run':   ['they phase clean through the tackle', 'hands pass right through them as they glide by'],
        'catch': ['the ball passes through the defender and sticks in their hands',
                  'they reach a hand through the corner and pull it in'],
        'kick':  ['the ball phases through the line and the uprights'],
        'pick':  ['they phase a hand through the receiver and the pass sticks to it',
                  'the throw clips through them and they are suddenly holding it'],
        'strip': ['they phase a hand into the runner and pull the ball back out',
                  'they clip through the pile and come out the other side with it']},

    'pixelate': {'name': 'Pixelate', 'concept': 'disassembles into pixels and reassembles downfield',
        'throw': ['the throw scatters into pixels, streams past the rush, and reforms in stride'],
        'run':   ['they burst into pixels and reassemble ten yards downfield',
                  'the tackle closes on a cloud of static; they reform past it'],
        'catch': ['they dissolve, drift past the coverage, and rebuild around the ball'],
        'pick':  ['they pixel-scatter into the throwing lane and reassemble around the pass'],
        'strip': ['they dissolve through the line and rebuild in the backfield, ball in hand']},

    'take_flight': {'name': 'Take Flight', 'concept': 'simply takes off and flies',
        'run':   ['they lift off and soar over the defense to the end zone',
                  'cleats leave the turf and they glide the last forty untouched'],
        'catch': ['they launch into the air, hang there, and pluck it from the sky'],
        'pick':  ['they take off, track the throw in flight, and snatch it from the air'],
        'strip': ['they swoop down on the runner and carry the ball off']},

    # ---- Throw-home (QB) ----
    'railgun': {'name': 'Railgun', 'concept': 'fires the ball like an electromagnetic slug',
        'throw': ['the ball glows white and rifles eighty yards on a flat line',
                  'a crack of electricity and the spiral is gone downfield'],
        'kick':  ['the kick leaves a streak of electric light and splits the posts']},

    'wormhole': {'name': 'Wormhole', 'concept': 'folds the field so the ball threads anything',
        'throw': ['the coverage folds shut and a tunnel opens straight to the receiver',
                  'the throwing window an inch wide folds itself around the ball'],
        'catch': ['a pocket of space opens at their hands and the ball drops out of it'],
        'pick':  ['the throw bends into a fold in the air and drops into their lap'],
        'strip': ['a fold opens at the runner and the ball falls through it to them']},

    'blink': {'name': 'Blink', 'concept': 'teleports a short hop',
        'throw': ['the rush closes on empty air; they blinked clear and let it fly'],
        'run':   ['they blink out of the tackle and in again past the line'],
        'pick':  ['they blink to the ball and arrive before the receiver does'],
        'strip': ['they blink in behind the runner and blink out holding the ball']},

    # ---- Run-home (RB) ----
    'warp': {'name': 'Warp', 'concept': 'moves at a speed the field cannot track',
        'run':   ['they hit warp speed and the defenders freeze mid-stride',
                  'a smear of motion and they are sixty yards downfield'],
        'catch': ['they warp to the catch point and wait for the ball to arrive'],
        'pick':  ['they warp under the throw and are waiting when it arrives'],
        'strip': ['they warp to the runner and the ball is gone before the tackle lands']},

    'earthquake': {'name': 'Earthquake', 'concept': 'a seismic stomp that buckles the field',
        'run':   ['a stomp flattens the entire front and they walk through the crack',
                  'the ground ripples and every tackler loses their footing'],
        'pick':  ['a tremor knocks the receiver off the ball and they scoop the pick'],
        'strip': ['the ground bucks under the runner and the ball shakes loose into their hands']},

    'juggernaut': {'name': 'Juggernaut', 'concept': 'turns to unstoppable iron',
        'run':   ['they turn to solid iron and bowl the whole pile over',
                  'tacklers ragdoll off them as they grind forward'],
        'pick':  ['they bulldoze into the pocket and the rushed throw flutters into their iron grip'],
        'strip': ['the runner meets a wall of iron and the ball pops free']},

    'ice_rink': {'name': 'Ice Rink', 'concept': 'freezes the field to a sheet of ice',
        'run':   ['the turf flashes to ice; defenders wipe out as they skate through',
                  'they glide across a frozen field while everyone else slips'],
        'pick':  ['the field ices over, the receiver slips, and they slide in for the pick'],
        'strip': ['the turf flashes to ice, the runner wipes out, and they skate off with the ball']},

    'freestyle': {'name': 'Freestyle', 'concept': 'literally swims down the field',
        'run':   ['they dive in and front-crawl through the defense untouched',
                  'they backstroke past a diving tackle like it is open water'],
        'catch': ['they swim up through the coverage and surface with the ball'],
        'pick':  ['they backstroke into the lane and pull the pass out of the air'],
        'strip': ['they swim through the line and wrestle the ball away from the runner']},

    # ---- Catch-home (WR/TE) ----
    'magnet': {'name': 'Magnet', 'concept': 'turns magnetic to the ball',
        'catch': ['the ball velcros to their palms', 'it ricochets off two defenders and snaps to them anyway'],
        'pick':  ['the throw bends off its line and into their hands',
                  'they hold up a palm and the pass drags itself in'],
        'strip': ['the ball tears off the runner and snaps to their magnetized hands']},

    'flypaper': {'name': 'Flypaper', 'concept': 'their hands are flypaper; nothing comes loose',
        'catch': ['the ball sticks to their gloves the instant it arrives',
                  'a defender swats it and it just re-sticks to their hand'],
        'pick':  ['the pass glances off a hand and flypapers to them'],
        'strip': ['they slap the ball and it flypapers off the runner into their grip']},

    'rubberband': {'name': 'Rubberband', 'concept': 'arms stretch like taffy',
        'catch': ['their arm stretches ten feet across the seam and reels it in',
                  'their wingspan triples and they pluck the uncatchable'],
        'pick':  ['their arm whips across the field and plucks the throw out of the air'],
        'strip': ['their arms stretch out and lasso the runner, squeezing the ball loose']},

    'octopus': {'name': 'Octopus', 'concept': 'sprouts a tangle of extra arms',
        'catch': ['eight arms unfurl and there is no dropping it now',
                  'a forest of hands swallows the ball out of the air'],
        'pick':  ['a dozen arms blanket the route and one comes down with the pass'],
        'strip': ['eight arms wrap the runner and peel the ball away']},

    'colossus': {'name': 'Colossus', 'concept': 'grows to fill the field',
        'catch': ['they expand to fill the end zone and box everyone out for it'],
        'run':   ['they swell to giant size and step over the entire defense'],
        'pick':  ['they grow into a wall and bat the pass down into their own hands'],
        'strip': ['they swell to giant size and pluck the runner and the ball off the turf']},

    # ---- Kick-home (K) — offense only (no defensive position) ----
    'moonshot': {'name': 'Moonshot', 'concept': 'kicks it into orbit',
        'kick': ['it booms through from seventy-two with a vapor trail',
                 'the ball clears the uprights and keeps climbing out of the stadium']},

    'tractor_beam': {'name': 'Tractor Beam', 'concept': 'the target pulls the ball in',
        'kick': ['the uprights lean in and tractor the ball straight through'],
        'catch': ['a beam locks on and drags the ball into their hands'],
        'pick':  ['they lock a beam on the throw and reel it in'],
        'strip': ['a tractor beam latches the ball and drags it off the runner']},

    'trebuchet': {'name': 'Trebuchet', 'concept': 'launches it like a siege engine',
        'kick': ['they wind up like a trebuchet and the ball rains down through the posts'],
        'throw': ['they crank back and catapult the ball the length of the field']},

    # ---- Defense-rich ----
    'black_hole': {'name': 'Black Hole', 'concept': 'opens a collapsing gravity well',
        'run':     ['defenders are dragged off their feet toward the gap as they slip through'],
        'catch':   ['the ball falls into a well at their chest and cannot escape'],
        'pick':    ['a well opens in the lane and the pass spirals into the dark, into their hands'],
        'strip':   ['a well opens behind the line and swallows the runner, the ball rolling out to them']},

    'pickpocket': {'name': 'Pickpocket', 'concept': 'lifts the ball clean like a wallet',
        'run':     ['they slip a hand free of the tackle and keep the ball moving'],
        'pick':    ['they pick the pass clean out of the air, smooth as lifting a wallet'],
        'strip':   ['their grip dissolves the ball away and they scoop it clean',
                    'they peel the ball off the runner mid-stride and take off']},

    'rewind': {'name': 'Rewind', 'concept': 'rewinds a couple seconds to be where they need to be',
        'catch':   ['they drop it, rewind two seconds, and bring it in clean'],
        'pick':    ['they were a step late, so they rewind and arrive early for the pick'],
        'strip':   ['they replay the handoff and arrive in time to take the ball']},

    # ---- Throw-home (QB) ----
    'comet': {'name': 'Comet', 'concept': 'the ball ignites into a comet',
        'throw': ['the ball ignites and streaks downfield trailing fire',
                  'a comet tail follows the spiral sixty yards into stride'],
        'kick':  ['the ball flares into a comet and burns through the uprights']},
    'slingshot': {'name': 'Slingshot', 'concept': 'fires the ball off a giant slingshot',
        'throw': ['they load the ball into a slingshot and snap it across the field',
                  'the ball rockets off an invisible band into the receiver'],
        'kick':  ['they slingshot it off the laces and it screams through']},
    'orbital': {'name': 'Orbital', 'concept': 'sends the ball to low orbit and back',
        'throw': ['they loft it into low orbit and it drops sixty yards downfield',
                  'the ball leaves the atmosphere and re-enters into a receiver'],
        'kick':  ['the kick climbs out of sight and drops back through the posts']},
    'heat_seeker': {'name': 'Heat-Seeker', 'concept': 'the ball locks on and homes in',
        'throw': ['the ball locks onto the receiver and corrects mid-flight',
                  'it banks around a defender like it has a guidance chip'],
        'catch': ['the ball homes in and thumps into their chest'],
        'pick':  ['the pass locks onto them instead and curls into their hands'],
        'strip': ['the ball heat-seeks off the runner and homes straight to them']},
    'auto_aim': {'name': 'Auto-Aim', 'concept': 'a crosshair snaps to the target',
        'throw': ['a crosshair snaps to the receiver and the ball follows it in',
                  'the target locks and the throw cannot miss'],
        'kick':  ['the reticle settles on the posts and the kick auto-corrects through'],
        'pick':  ['the lock-on jumps to them and the throw follows it in'],
        'strip': ['they paint the runner and the ball auto-ejects into their hands']},
    'telepathy': {'name': 'Telepathy', 'concept': 'thrower and catcher share one mind',
        'throw': ['they think the route and the receiver is already there',
                  'no signal needed, the ball goes exactly where both of them know'],
        'catch': ['they read the throw before it leaves the hand and are waiting']},
    'smoke_bomb': {'name': 'Smoke Bomb', 'concept': 'vanishes in a puff of smoke',
        'throw': ['they vanish in a puff of smoke and the ball comes out of the cloud',
                  'the rush hits smoke, the pass is already gone'],
        'run':   ['they drop a smoke bomb and reappear past the line'],
        'pick':  ['they vanish in smoke and step out of it under the throw'],
        'strip': ['a smoke bomb blinds the runner and they lift the ball in the haze']},
    'trapdoor': {'name': 'Trapdoor', 'concept': 'drops through a trapdoor and pops up elsewhere',
        'throw': ['they drop through a trapdoor and the throw comes from somewhere new',
                  'the pocket collapses on an empty patch of grass'],
        'run':   ['they fall through a trapdoor and pop up ten yards upfield'],
        'pick':  ['a trapdoor drops them into the lane right as the ball arrives'],
        'strip': ['a trapdoor drops the runner and they grab the ball on the way down']},
    'bullet_time': {'name': 'Bullet Time', 'concept': 'time crawls to a stop around them',
        'throw': ['the world crawls to a stop and they pick the seam at their leisure'],
        'run':   ['everything slows to a crawl and they stroll between frozen defenders'],
        'catch': ['time stutters and they reel it in while the ball hangs still'],
        'pick':  ['time slows and they step in front of a ball that is barely moving'],
        'strip': ['time slows and they pluck the ball from the frozen runner']},
    'decoy': {'name': 'Decoy', 'concept': 'leaves a decoy for the defense to hit',
        'throw': ['the rush tackles a cardboard cutout, the real one throws free'],
        'run':   ['they leave a decoy behind and slip away with the ball'],
        'pick':  ['the receiver breaks on a decoy and the real one takes the throw'],
        'strip': ['the runner cuts off a decoy into the real one, who lifts the ball']},
    'grease': {'name': 'Grease', 'concept': 'too slippery to hold onto',
        'throw': ['the sack slides right off, they grease free and fire'],
        'run':   ['tacklers slide off like they are coated in grease'],
        'pick':  ['the throw skids off a greased receiver and into their hands'],
        'strip': ['they squirt through a greased gap and the ball slides out of the runner into them']},
    'jelly': {'name': 'Jelly', 'concept': 'turns to jelly and oozes free',
        'throw': ['they turn to jelly, ooze out of the sack, and sling it'],
        'run':   ['arms pass through their jellied body and they wobble onward'],
        'pick':  ['they jiggle into the lane and the ball sticks in the jelly'],
        'strip': ['they gum up the runner and the ball oozes free into their hands']},

    # ---- Run-home (RB) ----
    'treadmill': {'name': 'Treadmill', 'concept': 'the turf becomes a treadmill for everyone else',
        'run':   ['the turf becomes a treadmill, pursuers sprint and go nowhere',
                  'defenders churn in place as they pull away'],
        'pick':  ['the route turns to a treadmill and they walk in front for the pick'],
        'strip': ['the runner lane turns to a treadmill and they reel them in for the ball']},
    'slipstream': {'name': 'Slipstream', 'concept': 'drags a vacuum that sucks pursuit backward',
        'run':   ['they tuck into a slipstream and the field blurs past',
                  'a vacuum opens behind them and sucks the pursuit backward'],
        'pick':  ['they ride a slipstream into the lane and snatch the throw'],
        'strip': ['they ride the runner slipstream right up and lift the ball']},
    'hyperdrive': {'name': 'Hyperdrive', 'concept': 'jumps to lightspeed',
        'run':   ['they punch the hyperdrive and streak the length of the field',
                  'stars smear and they are suddenly in the end zone'],
        'catch': ['they jump to the catch point before the ball arrives'],
        'pick':  ['they hyperdrive across the field and are under the throw'],
        'strip': ['they hyperdrive into the runner and the ball is gone in a blur']},
    'fast_forward': {'name': 'Fast-Forward', 'concept': 'fast-forwards while everyone else plays normal speed',
        'run':   ['they fast-forward through the defense while everyone else plays at normal speed'],
        'catch': ['they fast-forward to the spot and the ball catches up to them'],
        'throw': ['they fast-forward out of the rush and set their feet'],
        'pick':  ['they fast-forward to the ball and arrive a beat early for the pick'],
        'strip': ['they fast-forward to the runner and the ball pops out before the tackle forms']},
    'conveyor_belt': {'name': 'Conveyor Belt', 'concept': 'the turf carries them like a belt',
        'run':   ['the turf becomes a conveyor and whisks them past everyone',
                  'a belt under their feet carries them clear of the pile'],
        'pick':  ['the field belts the ball off its line into their hands'],
        'strip': ['the field belts the carrier straight into them and the ball comes loose']},
    'moses': {'name': 'Moses', 'concept': 'parts the defense down the middle',
        'run':   ['they raise a hand and the defense parts down the middle',
                  'the front splits like a sea and they walk through the gap'],
        'pick':  ['they part the coverage and walk into the throwing lane for the pick'],
        'strip': ['they part the line, meet the runner, and lift the ball as they pass']},
    'centipede': {'name': 'Centipede', 'concept': 'sprouts a dozen extra legs',
        'run':   ['a dozen extra legs sprout and they scuttle past the tackle',
                  'they grow a centipedes legs and skitter through traffic'],
        'pick':  ['a hundred legs swarm the route and snag the pass'],
        'strip': ['a hundred legs swarm the carrier and pry the ball free']},
    'big_bad_wolf': {'name': 'Big Bad Wolf', 'concept': 'huffs and puffs and blows them down',
        'run':   ['they huff, they puff, and blow the front seven flat',
                  'a gale from their lungs scatters the defense like leaves'],
        'pick':  ['one big breath blows the pass off course and into their hands'],
        'strip': ['one big breath knocks the carrier down and the ball pops loose']},
    'boulder': {'name': 'Boulder', 'concept': 'turns to solid rock',
        'run':   ['they turn to solid rock and grind the pile backward',
                  'tacklers shatter against a half-ton of granite'],
        'catch': ['they set like a boulder and nobody is moving them off the ball'],
        'pick':  ['they set like a boulder in the lane and the pass caroms into their hands'],
        'strip': ['the runner hits an immovable boulder and the ball jars loose']},
    'afterimage': {'name': 'Afterimage', 'concept': 'leaves afterimages the defense covers instead',
        'run':   ['the defender tackles an afterimage, the real one is already gone',
                  'they leave a trail of ghosts and the tackle hits the wrong one'],
        'catch': ['the corner covers their afterimage while they make the catch clean'],
        'pick':  ['the receiver breaks on an afterimage and the real one takes the ball'],
        'strip': ['they flicker past the blocker as an afterimage and pop the ball from the runner']},
    'origami': {'name': 'Origami', 'concept': 'folds flat as paper',
        'run':   ['they fold flat as paper and slip between two tacklers',
                  'they crease themselves sideways through a gap no one else could'],
        'catch': ['they fold around the defender and unfold with the ball'],
        'pick':  ['they fold flat, slide into the lane, and snatch the pass'],
        'strip': ['they fold thin through the line and crease the ball out of the runner']},
    'clone': {'name': 'Clone', 'concept': 'splits into a crowd of copies',
        'run':   ['they split into three and the defense tackles the wrong two',
                  'a crowd of copies floods the gap and the real one breaks free'],
        'catch': ['two clones clear out the coverage and the real one catches it'],
        'pick':  ['a swarm of clones blankets the route and one picks it off'],
        'strip': ['a crowd of clones swarms the runner and one comes away with the ball']},
    'matrix': {'name': 'Matrix', 'concept': 'bends impossibly to dodge',
        'run':   ['they bend impossibly backward under the tackle and keep running',
                  'they lean into bullet-dodge and the arms whiff past'],
        'throw': ['they bend backward out of the sack and throw upside down'],
        'pick':  ['they bend backward into the lane and lift the pass out of the air'],
        'strip': ['they bend under the block and rise with the ball stripped from the runner']},
    'limbo': {'name': 'Limbo', 'concept': 'bends flat under the tackle',
        'run':   ['they limbo under the tackle, flat to the turf, and pop back up',
                  'they bend so low the arms sail over and they slide through'],
        'pick':  ['they limbo under the throw and pop up cradling it'],
        'strip': ['they limbo under the blocker, trip the runner, and take the ball']},
    'heartthrob': {'name': 'Heartthrob', 'concept': 'the defenders fall in love',
        'run':   ['the defenders swoon and wave them through with hearts in their eyes',
                  'tacklers stop to admire them and let the run go by'],
        'catch': ['the corner is too smitten to contest the catch'],
        'pick':  ['the receiver is too smitten to fight for it and they take the pick'],
        'strip': ['the ball-carrier freezes, lovestruck, and hands it right over']},
    'shrink_ray': {'name': 'Shrink Ray', 'concept': 'shrinks to slip past',
        'run':   ['they shrink to ant-size and scurry between the tacklers feet',
                  'they zap themselves tiny and the tackle closes on empty air'],
        'catch': ['they shrink under the coverage and grab it at shoelace height'],
        'pick':  ['they shrink, dart under the throw, and snatch it at shoelace height'],
        'strip': ['they shrink, dart under the runner, and pop the ball out']},
    'skunk': {'name': 'Skunk', 'concept': 'stinks so bad everyone avoids them',
        'run':   ['the stench clears a lane, defenders gag and give them room',
                  'nobody wants within five yards of that smell'],
        'catch': ['the corner backs off the smell and they catch it uncovered'],
        'pick':  ['the receiver gags and backs off, and they take the pass uncontested'],
        'strip': ['the carrier recoils from the reek and coughs up the ball']},
    'liquify': {'name': 'Liquify', 'concept': 'turns to liquid and pours through',
        'run':   ['they turn to liquid and pour through the gap in the line',
                  'the tackle splashes through a puddle where they used to be'],
        'pick':  ['they pour into the lane and the ball drops into the puddle'],
        'strip': ['they flow around the runner and re-form holding the ball']},
    'sandman': {'name': 'Sandman', 'concept': 'puts the defenders to sleep',
        'run':   ['defenders yawn and drop off to sleep as they jog past',
                  'a wave of drowsiness rolls over the front and they stroll through'],
        'catch': ['the corner nods off and they catch it in peace'],
        'pick':  ['the receiver nods off and they pluck the pass from sleeping hands'],
        'strip': ['the ball-carrier dozes off and the ball slips out of their arms']},
    'photobomb': {'name': 'Photobomb', 'concept': 'pops up suddenly behind the defense',
        'run':   ['they blink out and photobomb the play twenty yards downfield',
                  'they are suddenly behind the whole defense, grinning'],
        'catch': ['they pop up uncovered behind the secondary for the grab'],
        'pick':  ['they pop up uncovered in the lane and take the throw'],
        'strip': ['they photobomb into the backfield and lift the ball before the runner sees them']},
    'avalanche': {'name': 'Avalanche', 'concept': 'comes down like an avalanche',
        'run':   ['a wall of snow and bodies rolls downhill and buries the defense',
                  'they come down like an avalanche and sweep the front away'],
        'pick':  ['an avalanche of bodies crashes down and the pass tumbles into their hands'],
        'strip': ['the avalanche buries the runner and they dig the ball out']},
    'stampede': {'name': 'Stampede', 'concept': 'multiplies into a trampling herd',
        'run':   ['they multiply into a thundering herd and trample the front',
                  'a stampede of copies flattens everything in the lane'],
        'pick':  ['a stampede floods the route and one of the herd snags the pass'],
        'strip': ['a stampede rolls over the carrier and the ball comes loose']},
    'steamroller': {'name': 'Steamroller', 'concept': 'flattens everyone like a roller',
        'run':   ['they flatten the first wave into the turf like a steamroller',
                  'defenders go two-dimensional under the roller'],
        'pick':  ['they flatten the pocket and the rushed throw wobbles into their hands'],
        'strip': ['they steamroll the runner flat and peel the ball off the turf']},
    'tank': {'name': 'Tank', 'concept': 'rolls forward as an actual tank',
        'run':   ['they roll forward as a tank and the line bounces off the treads',
                  'the hull shrugs off arm tackles and grinds ahead'],
        'pick':  ['the tank rolls into the lane and the pass clanks off the hull into their hands'],
        'strip': ['the tank crashes through, crushes the run, and the ball spills out']},
    'cannonball': {'name': 'Cannonball', 'concept': 'curls into a cannonball and rolls through',
        'run':   ['they curl into a cannonball and bowl straight through the pile',
                  'they tuck and roll over the top of the tacklers'],
        'pick':  ['they cannonball into the lane and the ball ricochets into their arms'],
        'strip': ['they cannonball into the backfield and blast the ball loose']},
    'bowling_ball': {'name': 'Bowling Ball', 'concept': 'the defenders are bowling pins',
        'run':   ['they roll into the front seven and the defenders scatter like pins',
                  'strike, the whole line goes down in a clatter'],
        'pick':  ['they roll into the route, scatter it, and the ball rolls to them'],
        'strip': ['they bowl into the backfield, the runner goes down like a pin, ball loose']},

    # ---- Catch-home (WR/TE) ----
    'third_arm': {'name': 'Third Arm', 'concept': 'sprouts a third arm',
        'catch': ['a third arm sprouts from their chest and snags the high ball',
                  'an extra hand reaches up where two could not'],
        'pick':  ['a third arm shoots out and plucks the pass from the air'],
        'strip': ['a third arm reaches in and tears the ball from the runner']},
    'vacuum': {'name': 'Vacuum', 'concept': 'inhales the ball in',
        'catch': ['they inhale and the ball gets sucked straight into their grip',
                  'a vacuum opens at their chest and the ball cannot resist'],
        'pick':  ['they suck the pass off its line and into their hands'],
        'strip': ['they switch on the vacuum and inhale the ball off the runner']},
    'gravity_well': {'name': 'Gravity Well', 'concept': 'opens a well the ball falls into',
        'catch': ['a gravity well opens at their palms and the ball drops in',
                  'the ball curves down out of its arc into their hands'],
        'pick':  ['the throw bends into the well at their chest'],
        'strip': ['a well opens under the runner and the ball drops out of their arms into it']},
    'web_shooter': {'name': 'Web-Shooter', 'concept': 'shoots a web and reels it in',
        'catch': ['they fire a web at the ball and reel it into their hands',
                  'a strand snaps out and yanks the catch back to them'],
        'pick':  ['they web the throw out of the air and reel it in'],
        'strip': ['they web the ball off the runner and yank it back']},
    'do_over': {'name': 'Do-Over', 'concept': 'rewinds a drop and redoes it',
        'catch': ['they drop it, rewind two seconds, and bring it in clean',
                  'the bobble un-happens and the ball settles into their hands'],
        'pick':  ['they miss the jump, rewind, and time it perfectly for the pick'],
        'strip': ['they whiff the strip, rewind, and rip it loose on the second try']},
    'good_boy': {'name': 'Good Boy', 'concept': 'the ball becomes a loyal dog',
        'catch': ['the ball turns into a loyal dog and bounds into their arms',
                  'here boy, the ball trots over and curls up in their hands'],
        'pick':  ['the ball decides it likes them better and leaps into their arms'],
        'strip': ['the ball wriggles loose from the runner and trots over to them']},
    'invisible_ink': {'name': 'Invisible Ink', 'concept': 'the ball turns invisible',
        'catch': ['the ball turns invisible and the corner has no idea they have it',
                  'the defense loses the ball, only they know where it lands'],
        'throw': ['the ball vanishes in flight and reappears in the receivers hands'],
        'pick':  ['they can still see the invisible ball and step in front of it'],
        'strip': ['the ball goes invisible, the runner loses it, and they scoop it up']},
    'slinky': {'name': 'Slinky', 'concept': 'arms coil out like a slinky',
        'catch': ['their arm coils out like a slinky and grabs the overthrow',
                  'they spring a coiled arm across the seam and reel it in'],
        'pick':  ['a slinky arm springs out and snatches the throw down'],
        'strip': ['a slinky arm coils around the runner and springs back with the ball']},
    'telescope': {'name': 'Telescope', 'concept': 'arms telescope out',
        'catch': ['their arms telescope out ten feet and pluck it from the sky',
                  'they extend like a spyglass and snag the uncatchable'],
        'pick':  ['a telescoping arm shoots out and intercepts the pass'],
        'strip': ['a telescoping arm reaches in and plucks the ball from the runner']},
    'gumby': {'name': 'Gumby', 'concept': 'bends and stretches like clay',
        'catch': ['they bend like rubber clay and wrap around the high ball',
                  'they stretch their whole body to reach it'],
        'run':   ['they bend around the tackle like a rubber toy and keep going'],
        'pick':  ['they stretch across the lane and bend the pick into their hands'],
        'strip': ['they stretch around the runner and pull the ball free']},
    'fishing_rod': {'name': 'Fishing Rod', 'concept': 'casts an arm out like a line',
        'catch': ['they cast an arm out like a line and hook the ball in',
                  'they reel the overthrow back like a prize catch'],
        'pick':  ['they cast out, hook the pass, and reel in the pick'],
        'strip': ['they cast a line around the runner and reel the ball in']},
    'butterfly_net': {'name': 'Butterfly Net', 'concept': 'pulls a giant net from nowhere',
        'catch': ['they pull a giant net from their sleeve and scoop the ball in',
                  'the net swallows the deep ball out of the air'],
        'pick':  ['they swing a net across the lane and bag the pass'],
        'strip': ['they drop a net over the runner and scoop the ball out']},
    'kaiju': {'name': 'Kaiju', 'concept': 'grows into a monster',
        'catch': ['they grow into a kaiju and pluck it over the tiny defenders',
                  'a monsters hand closes around the ball above the crowd'],
        'run':   ['they tower up kaiju-sized and stomp through the defense'],
        'pick':  ['they swell into a kaiju and swat the pass out of the air into their hands'],
        'strip': ['a kaiju hand closes over the runner and plucks the ball away']},
    'redwood': {'name': 'Redwood', 'concept': 'grows into a towering tree',
        'catch': ['they grow into a redwood and high-point it above everyone',
                  'roots dig in and they rise untouchable over the corner'],
        'pick':  ['they grow into a redwood and the pass lodges in the branches'],
        'strip': ['they plant like a redwood, the runner crumples against the trunk, ball loose']},
    'monolith': {'name': 'Monolith', 'concept': 'becomes an immovable slab',
        'catch': ['they harden into a monolith and box everyone off the ball',
                  'a black slab rises and the defenders bounce away from the catch'],
        'pick':  ['a monolith rises in the lane and the pass rebounds into their hands'],
        'strip': ['a monolith slams down on the runner and the ball squirts free']},
    'hot_air': {'name': 'Hot Air', 'concept': 'inflates and floats over everyone',
        'catch': ['they inflate like a balloon and float up over the secondary',
                  'they puff full of hot air and rise above the crowd for it'],
        'pick':  ['they balloon up into the lane and smother the throw'],
        'strip': ['they inflate over the runner and the ball pops out as they go down']},
    'eclipse': {'name': 'Eclipse', 'concept': 'blots out the sun over the defender',
        'catch': ['they blot out the sun over the corner and catch it in the dark',
                  'a shadow falls over the defender and the ball is theirs'],
        'pick':  ['they eclipse the receiver and pick it in the shade'],
        'strip': ['darkness falls over the runner and they take the ball in the black']},

    # ---- Kick-home (K) — offense only ----
    'mortar': {'name': 'Mortar', 'concept': 'drops it in like a mortar round',
        'kick': ['they drop it in like a mortar round and it craters through the posts',
                 'a high arcing shell that comes straight down through the uprights']},
    'big_bertha': {'name': 'Big Bertha', 'concept': 'fires the giant cannon',
        'kick': ['Big Bertha goes off and the ball booms eighty yards through',
                 'a cannon blast and the kick is good from the other end zone']},
    'autopilot': {'name': 'Autopilot', 'concept': 'the kick steers itself',
        'kick':  ['they flip on autopilot and the kick steers itself through',
                  'hands off, the ball corrects course and splits the posts'],
        'throw': ['they set it to autopilot and the throw flies itself to the receiver'],
        'pick':  ['autopilot routes them under the throw for the pick'],
        'strip': ['autopilot steers them to the runner and the ball off into their hands']},
    'gps': {'name': 'GPS', 'concept': 'navigates the ball by coordinates',
        'kick':  ['they punch in the coordinates and the ball navigates through',
                  'rerouting, the kick threads it dead center'],
        'throw': ['they lock the receivers coordinates and the ball routes in'],
        'pick':  ['they get a fix on the throw and intercept the route'],
        'strip': ['they navigate straight to the runner and reroute the ball to themselves']},
    'magnet_posts': {'name': 'Magnet Posts', 'concept': 'the uprights magnetize the ball',
        'kick': ['the uprights magnetize and drag the kick dead through the middle',
                 'the posts pull the ball in no matter the angle']},
    'laser_guided': {'name': 'Laser-Guided', 'concept': 'paints the target with a laser',
        'kick':  ['they paint the posts with a laser and the kick rides the beam through',
                  'target lit, the ball tracks the laser dead center'],
        'throw': ['they laser-paint the receiver and the throw rides the line in'],
        'pick':  ['they paint the ball and cut off the route for the pick'],
        'strip': ['they laser-paint the carrier and the ball tracks off them into their hands']},

    # ---- Defense-leaning (given an offensive situation so they are assignable) ----
    'highway_robbery': {'name': 'Highway Robbery', 'concept': 'robs the ball in broad daylight',
        'catch': ['they snatch it like it was theirs all along and stroll off'],
        'pick':  ['they jump the throw and roll out a red carpet to the end zone',
                  'they rob the receiver blind and take it the other way'],
        'strip': ['they stick up the runner in broad daylight and make off with the ball']},
    'ball_magnet': {'name': 'Ball Magnet', 'concept': 'the ball is drawn to them',
        'catch': ['the ball curves off its line and sticks to them'],
        'pick':  ['the throw bends across the field and magnetizes into their hands',
                  'no matter where it is aimed, the ball ends up with them'],
        'strip': ['the ball tears off the runner and flies straight to them']},
    'the_heist': {'name': 'The Heist', 'concept': 'a planned, clean robbery',
        'catch': ['the whole thing was planned, they were always taking this one'],
        'pick':  ['they run the heist clean, lift the pass, and walk it out',
                  'the crew sets a screen and they make off with the interception'],
        'strip': ['the job goes off without a hitch and the runner never feels the ball leave']},
    'portal': {'name': 'Portal', 'concept': 'opens portals across the field',
        'throw': ['they open a portal and the ball comes out the other side downfield'],
        'run':   ['they step into a portal at the line and out of one past the secondary'],
        'catch': ['a portal opens at their hands and the ball drops through it'],
        'pick':  ['they reach a hand through a portal and pull the pass from the air'],
        'strip': ['a portal opens at the runner and the ball drops through it to them']},
    'telekinesis': {'name': 'Telekinesis', 'concept': 'moves the ball with their mind',
        'throw': ['they steer the ball downfield with a flick of the mind'],
        'catch': ['they pull the ball into their hands without touching it'],
        'pick':  ['they yank the throw out of the air with their mind'],
        'strip': ['they freeze the carrier and lift the ball straight out of their arms']},
    'premonition': {'name': 'Premonition', 'concept': 'already saw this play happen',
        'throw': ['they saw this throw a minute ago and the receiver is already open'],
        'catch': ['they dreamed this catch last night and run to the spot'],
        'pick':  ['they knew the play before the snap and are already there for the pick'],
        'strip': ['a premonition puts them on the runner and the ball is theirs before it happens']},
    'insider_trading': {'name': 'Insider Trading', 'concept': 'had the call sheet',
        'catch': ['they had the call sheet and break before the ball is thrown'],
        'pick':  ['they got the tip and are sitting on the route for the pick',
                  'they traded on inside info and cash in the interception'],
        'strip': ['they knew the handoff was coming and pick the runner clean']},
    'the_vacuum': {'name': 'The Vacuum', 'concept': 'vacuums the ball loose',
        'run':   ['they vacuum a path clear and rush through the gap'],
        'pick':  ['they switch on the vacuum and suck the pass out of the air'],
        'strip': ['they switch on the vacuum and suck the ball clean out of the arms',
                  'the ball gets hoovered loose and they scoop it']},
    'repo_man': {'name': 'Repo Man', 'concept': 'repossesses the ball',
        'catch': ['they repossess the ball like a missed payment'],
        'pick':  ['they show up with paperwork and repossess the pass mid-air'],
        'strip': ['overdue, they repossess the ball off the runner and drive off']},
    'crowbar': {'name': 'Crowbar', 'concept': 'pries the ball loose with a crowbar',
        'run':   ['they pry the pile apart with a crowbar and squeeze through'],
        'pick':  ['they pry the pass out of the air with a crowbar'],
        'strip': ['they jam a crowbar in and pop the ball loose from the runner',
                  'one good pry and the ball is theirs']},
    'magnet_hands': {'name': 'Magnet Hands', 'concept': 'magnetized hands rip it free',
        'catch': ['the ball snaps to their magnetized hands'],
        'pick':  ['the throw snaps to their magnetized hands'],
        'strip': ['their hands magnetize and rip the ball off the runner',
                  'the ball jumps to their palms off the handoff']},
    'tax_man': {'name': 'Tax Man', 'concept': 'comes to collect their cut',
        'catch': ['they collect their cut, the ball was always owed to them'],
        'pick':  ['the tax man comes for his share and intercepts it',
                  'nothing is certain but the interception they just levied'],
        'strip': ['the tax man collects, taking the ball right off the runner']},
    'quicksand': {'name': 'Quicksand', 'concept': 'turns the field to quicksand',
        'run':   ['the turf behind them turns to quicksand and the pursuit sinks'],
        'pick':  ['the lane turns to quicksand, the receiver bogs down, and they take the ball'],
        'strip': ['the backfield turns to quicksand, the runner sinks, and they lift the ball',
                  'the carrier sinks to the knees and they take the ball']},
    'sinkhole': {'name': 'Sinkhole', 'concept': 'opens a sinkhole under the play',
        'run':   ['a sinkhole opens behind them and the pursuit drops in'],
        'pick':  ['a sinkhole drops the receiver and they snatch the pass over the hole'],
        'strip': ['the ground opens under the runner and the ball rolls to them',
                  'a sinkhole drops the carrier and the ball rolls to them']},
    'riptide': {'name': 'Riptide', 'concept': 'drags the defense out to sea',
        'run':   ['a riptide pulls the defenders out to sea as they cut upfield'],
        'pick':  ['a riptide drags the route out to sea and they collect the floating ball'],
        'strip': ['a riptide drags the carrier backward and the ball floats free',
                  'the current yanks them down and the ball floats free']},
    'teleport': {'name': 'Teleport', 'concept': 'teleports anywhere on the field',
        'throw': ['they teleport out of the pocket and throw from clean grass'],
        'run':   ['they blink out at the line and rematerialize in the end zone'],
        'catch': ['they teleport to the landing spot and catch it in stride'],
        'pick':  ['they teleport into the lane before the throw arrives'],
        'strip': ['they teleport into the backfield before the handoff lands and take the ball']},
    'implosion': {'name': 'Implosion', 'concept': 'collapses everything inward',
        'run':   ['the line implodes inward and they shoot through the vacuum'],
        'pick':  ['the lane implodes and the ball collapses inward into their hands'],
        'strip': ['the backfield implodes and the ball ends up in their hands',
                  'everything folds inward and the ball is theirs']},
    'demolition': {'name': 'Demolition', 'concept': 'demolishes the play',
        'run':   ['they demolish the front and walk through the rubble'],
        'pick':  ['they blow up the pocket and the wounded throw drops to them'],
        'strip': ['they bring the whole backfield down in a demolition',
                  'the play comes apart in a cloud of dust and they have the ball']},
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
