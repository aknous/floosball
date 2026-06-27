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
  • Add a whole new SITUATION TYPE:  add it to SITUATIONS, and (if it needs a defensive mapping or a
    new effect) wire it in P3. _validate() runs at import and flags any unknown/typo situation key.
  All flavor is GENDER-NEUTRAL (singular they/them/their). Names are PLACEHOLDERS pending finalize.
──────────────────────────────────────────────────────────────────────────────────────────────────
"""
import random as _random

# The situations a player can be the focal point of. A power provides flavor only for the ones it
# covers. To add a new situation type, add it here (and wire its effect in P3).
SITUATIONS = ('throw', 'run', 'catch', 'kick', 'defense')

# A player's PRIMARY situation by offensive position. Assignment rolls a power that COVERS this, so
# the power fires regularly. The power also fires in any OTHER situation it covers (incl. defense).
PRIMARY_SITUATION = {'QB': 'throw', 'RB': 'run', 'WR': 'catch', 'TE': 'catch', 'K': 'kick'}

# When a power fires on 'defense', the concrete takeaway is the player's defensive-position effect
# (implemented in P3). QB->S deep pick, RB->LB strip, WR->CB pick, TE->DE collapse, K->no defense.
DEFENSE_EFFECT_BY_POS = {'QB': 'pick', 'RB': 'strip', 'WR': 'pick', 'TE': 'collapse', 'K': None}

# ── Catalog ─────────────────────────────────────────────────────────────────────────────────────
# key: {name, concept, <situation>: [flavor lines], ...}  — omit situations the power can't do.
_POWERS = {
    # ---- Universal (cover every situation) ----
    'no_clip': {'name': 'No-Clip', 'concept': 'phases through solid matter like a glitch in the world',
        'throw': ['the ball phases straight through three defenders untouched',
                  'the pass clips through a linebacker like he is not there'],
        'run':   ['they phase clean through the tackle', 'hands pass right through them as they glide by'],
        'catch': ['the ball passes through the defender and sticks in their hands',
                  'they reach a hand through the corner and pull it in'],
        'kick':  ['the ball phases through the line and the uprights'],
        'defense': ['they phase through the blocker and rip the ball loose',
                    'they clip through the pile and come out the other side with it']},

    'pixelate': {'name': 'Pixelate', 'concept': 'disassembles into pixels and reassembles downfield',
        'throw': ['the throw scatters into pixels, streams past the rush, and reforms in stride'],
        'run':   ['they burst into pixels and reassemble ten yards downfield',
                  'the tackle closes on a cloud of static; they reform past it'],
        'catch': ['they dissolve, drift past the coverage, and rebuild around the ball'],
        'defense': ['they pixel-scatter through the line and reassemble on the ball']},

    'take_flight': {'name': 'Take Flight', 'concept': 'simply takes off and flies',
        'run':   ['they lift off and soar over the defense to the end zone',
                  'cleats leave the turf and they glide the last forty untouched'],
        'catch': ['they launch into the air, hang there, and pluck it from the sky'],
        'defense': ['they take off, track the ball in flight, and snatch it down']},

    # ---- Throw-home (QB) ----
    'railgun': {'name': 'Railgun', 'concept': 'fires the ball like an electromagnetic slug',
        'throw': ['the ball glows white and rifles eighty yards on a flat line',
                  'a crack of electricity and the spiral is gone downfield'],
        'kick':  ['the kick leaves a streak of electric light and splits the posts']},

    'wormhole': {'name': 'Wormhole', 'concept': 'folds the field so the ball threads anything',
        'throw': ['the coverage folds shut and a tunnel opens straight to the receiver',
                  'the throwing window an inch wide folds itself around the ball'],
        'catch': ['a pocket of space opens at their hands and the ball drops out of it'],
        'defense': ['the throw bends into a fold in the air and lands in their lap']},

    'blink': {'name': 'Blink', 'concept': 'teleports a short hop',
        'throw': ['the rush closes on empty air; they blinked clear and let it fly'],
        'run':   ['they blink out of the tackle and in again past the line'],
        'defense': ['they blink to the ball and arrive before the receiver does']},

    # ---- Run-home (RB) ----
    'warp': {'name': 'Warp', 'concept': 'moves at a speed the field cannot track',
        'run':   ['they hit warp speed and the defenders freeze mid-stride',
                  'a smear of motion and they are sixty yards downfield'],
        'catch': ['they warp to the catch point and wait for the ball to arrive'],
        'defense': ['they warp across the field and are under the throw instantly']},

    'earthquake': {'name': 'Earthquake', 'concept': 'a seismic stomp that buckles the field',
        'run':   ['a stomp flattens the entire front and they walk through the crack',
                  'the ground ripples and every tackler loses their footing'],
        'defense': ['the ground bucks and the ball shakes loose into their hands']},

    'juggernaut': {'name': 'Juggernaut', 'concept': 'turns to unstoppable iron',
        'run':   ['they turn to solid iron and bowl the whole pile over',
                  'tacklers ragdoll off them as they grind forward'],
        'defense': ['they become immovable iron and the run dies on contact']},

    'ice_rink': {'name': 'Ice Rink', 'concept': 'freezes the field to a sheet of ice',
        'run':   ['the turf flashes to ice; defenders wipe out as they skate through',
                  'they glide across a frozen field while everyone else slips'],
        'defense': ['the field ices over, the carrier slips, and they collect the ball']},

    'freestyle': {'name': 'Freestyle', 'concept': 'literally swims down the field',
        'run':   ['they dive in and front-crawl through the defense untouched',
                  'they backstroke past a diving tackle like it is open water'],
        'catch': ['they swim up through the coverage and surface with the ball'],
        'defense': ['they stroke through the line and scoop the ball from the current']},

    # ---- Catch-home (WR/TE) ----
    'magnet': {'name': 'Magnet', 'concept': 'turns magnetic to the ball',
        'catch': ['the ball velcros to their palms', 'it ricochets off two defenders and snaps to them anyway'],
        'defense': ['the throw bends off its line and into their hands',
                    'they hold up a palm and the pass drags itself in']},

    'flypaper': {'name': 'Flypaper', 'concept': 'their hands are flypaper; nothing comes loose',
        'catch': ['the ball sticks to their gloves the instant it arrives',
                  'a defender swats it and it just re-sticks to their hand'],
        'defense': ['the pass glances off a hand and flypapers to them for the pick']},

    'rubberband': {'name': 'Rubberband', 'concept': 'arms stretch like taffy',
        'catch': ['their arm stretches ten feet across the seam and reels it in',
                  'their wingspan triples and they pluck the uncatchable'],
        'defense': ['an arm snaps out across the field and yanks the throw down']},

    'octopus': {'name': 'Octopus', 'concept': 'sprouts a tangle of extra arms',
        'catch': ['eight arms unfurl and there is no dropping it now',
                  'a forest of hands swallows the ball out of the air'],
        'defense': ['a dozen arms blanket the route and one of them comes down with it']},

    'colossus': {'name': 'Colossus', 'concept': 'grows to fill the field',
        'catch': ['they expand to fill the end zone and box everyone out for it'],
        'run':   ['they swell to giant size and step over the entire defense'],
        'defense': ['they grow into a wall and the play crashes against them for a loss']},

    # ---- Kick-home (K) — offense only (no defensive position) ----
    'moonshot': {'name': 'Moonshot', 'concept': 'kicks it into orbit',
        'kick': ['it booms through from seventy-two with a vapor trail',
                 'the ball clears the uprights and keeps climbing out of the stadium']},

    'tractor_beam': {'name': 'Tractor Beam', 'concept': 'the target pulls the ball in',
        'kick': ['the uprights lean in and tractor the ball straight through'],
        'catch': ['a beam locks on and drags the ball into their hands'],
        'defense': ['they lock a beam on the throw and reel it in for the pick']},

    'trebuchet': {'name': 'Trebuchet', 'concept': 'launches it like a siege engine',
        'kick': ['they wind up like a trebuchet and the ball rains down through the posts'],
        'throw': ['they crank back and catapult the ball the length of the field']},

    # ---- Defense-rich ----
    'black_hole': {'name': 'Black Hole', 'concept': 'opens a collapsing gravity well',
        'defense': ['the pocket folds inward and the play collapses into the dark',
                    'a well opens behind the line and swallows the runner for a loss'],
        'run':     ['defenders are dragged off their feet toward the gap as they slip through'],
        'catch':   ['the ball falls into a well at their chest and cannot escape']},

    'pickpocket': {'name': 'Pickpocket', 'concept': 'their grip just dissolves the ball away',
        'defense': ['the carrier\'s grip dissolves on contact and they scoop it clean',
                    'they peel the ball away mid-stride and take off'],
        'run':     ['they slip a hand free of the tackle and keep the ball moving']},

    'rewind': {'name': 'Rewind', 'concept': 'rewinds a couple seconds to be where they need to be',
        'defense': ['they were a step late, so they rewind and arrive early for the ball'],
        'catch':   ['they drop it, rewind two seconds, and bring it in clean']},

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
        'defense': ['the pass locks onto them instead and curls into their hands']},
    'auto_aim': {'name': 'Auto-Aim', 'concept': 'a crosshair snaps to the target',
        'throw': ['a crosshair snaps to the receiver and the ball follows it in',
                  'the target locks and the throw cannot miss'],
        'kick':  ['the reticle settles on the posts and the kick auto-corrects through'],
        'defense': ['the lock-on jumps to them and the ball follows']},
    'telepathy': {'name': 'Telepathy', 'concept': 'thrower and catcher share one mind',
        'throw': ['they think the route and the receiver is already there',
                  'no signal needed, the ball goes exactly where both of them know'],
        'catch': ['they read the throw before it leaves the hand and are waiting']},
    'smoke_bomb': {'name': 'Smoke Bomb', 'concept': 'vanishes in a puff of smoke',
        'throw': ['they vanish in a puff of smoke and the ball comes out of the cloud',
                  'the rush hits smoke, the pass is already gone'],
        'run':   ['they drop a smoke bomb and reappear past the line'],
        'defense': ['they melt into smoke and reform on top of the ball']},
    'trapdoor': {'name': 'Trapdoor', 'concept': 'drops through a trapdoor and pops up elsewhere',
        'throw': ['they drop through a trapdoor and the throw comes from somewhere new',
                  'the pocket collapses on an empty patch of grass'],
        'run':   ['they fall through a trapdoor and pop up ten yards upfield'],
        'defense': ['a trapdoor drops the carrier and they grab the ball on the way down']},
    'bullet_time': {'name': 'Bullet Time', 'concept': 'time crawls to a stop around them',
        'throw': ['the world crawls to a stop and they pick the seam at their leisure'],
        'run':   ['everything slows to a crawl and they stroll between frozen defenders'],
        'catch': ['time stutters and they reel it in while the ball hangs still'],
        'defense': ['time slows and they step in front of a ball that is barely moving']},
    'decoy': {'name': 'Decoy', 'concept': 'leaves a decoy for the defense to hit',
        'throw': ['the rush tackles a cardboard cutout, the real one throws free'],
        'run':   ['they leave a decoy behind and slip away with the ball'],
        'defense': ['the carrier jukes a decoy and runs straight into the real one']},
    'grease': {'name': 'Grease', 'concept': 'too slippery to hold onto',
        'throw': ['the sack slides right off, they grease free and fire'],
        'run':   ['tacklers slide off like they are coated in grease'],
        'defense': ['they squirt through a greased gap and strip it clean']},
    'jelly': {'name': 'Jelly', 'concept': 'turns to jelly and oozes free',
        'throw': ['they turn to jelly, ooze out of the sack, and sling it'],
        'run':   ['arms pass through their jellied body and they wobble onward'],
        'defense': ['they jiggle through the blockers and gum up the ball-carrier']},

    # ---- Run-home (RB) ----
    'treadmill': {'name': 'Treadmill', 'concept': 'the turf becomes a treadmill for everyone else',
        'run':   ['the turf becomes a treadmill, pursuers sprint and go nowhere',
                  'defenders churn in place as they pull away'],
        'defense': ['the runners lane turns to a treadmill and they reel them in']},
    'slipstream': {'name': 'Slipstream', 'concept': 'drags a vacuum that sucks pursuit backward',
        'run':   ['they tuck into a slipstream and the field blurs past',
                  'a vacuum opens behind them and sucks the pursuit backward'],
        'defense': ['they ride the carriers slipstream right up to the ball']},
    'hyperdrive': {'name': 'Hyperdrive', 'concept': 'jumps to lightspeed',
        'run':   ['they punch the hyperdrive and streak the length of the field',
                  'stars smear and they are suddenly in the end zone'],
        'catch': ['they jump to the catch point before the ball arrives'],
        'defense': ['they hyperdrive across the field and are under the throw']},
    'fast_forward': {'name': 'Fast-Forward', 'concept': 'fast-forwards while everyone else plays normal speed',
        'run':   ['they fast-forward through the defense while everyone else plays at normal speed'],
        'catch': ['they fast-forward to the spot and the ball catches up to them'],
        'throw': ['they fast-forward out of the rush and set their feet'],
        'defense': ['they fast-forward to the ball and arrive a beat early']},
    'conveyor_belt': {'name': 'Conveyor Belt', 'concept': 'the turf carries them like a belt',
        'run':   ['the turf becomes a conveyor and whisks them past everyone',
                  'a belt under their feet carries them clear of the pile'],
        'defense': ['the field belts the carrier straight into them']},
    'moses': {'name': 'Moses', 'concept': 'parts the defense down the middle',
        'run':   ['they raise a hand and the defense parts down the middle',
                  'the front splits like a sea and they walk through the gap'],
        'defense': ['they part the line and arrive untouched on the ball']},
    'centipede': {'name': 'Centipede', 'concept': 'sprouts a dozen extra legs',
        'run':   ['a dozen extra legs sprout and they scuttle past the tackle',
                  'they grow a centipedes legs and skitter through traffic'],
        'defense': ['a hundred legs swarm the carrier and pry the ball free']},
    'big_bad_wolf': {'name': 'Big Bad Wolf', 'concept': 'huffs and puffs and blows them down',
        'run':   ['they huff, they puff, and blow the front seven flat',
                  'a gale from their lungs scatters the defense like leaves'],
        'defense': ['one big breath knocks the carrier down and the ball pops loose']},
    'boulder': {'name': 'Boulder', 'concept': 'turns to solid rock',
        'run':   ['they turn to solid rock and grind the pile backward',
                  'tacklers shatter against a half-ton of granite'],
        'catch': ['they set like a boulder and nobody is moving them off the ball'],
        'defense': ['they become an immovable boulder and the run dies on them']},
    'afterimage': {'name': 'Afterimage', 'concept': 'leaves afterimages the defense covers instead',
        'run':   ['the defender tackles an afterimage, the real one is already gone',
                  'they leave a trail of ghosts and the tackle hits the wrong one'],
        'catch': ['the corner covers their afterimage while they make the catch clean'],
        'defense': ['they flicker past the blocker as an afterimage and hit the ball']},
    'origami': {'name': 'Origami', 'concept': 'folds flat as paper',
        'run':   ['they fold flat as paper and slip between two tacklers',
                  'they crease themselves sideways through a gap no one else could'],
        'catch': ['they fold around the defender and unfold with the ball'],
        'defense': ['they fold thin, slide through the line, and snatch it']},
    'clone': {'name': 'Clone', 'concept': 'splits into a crowd of copies',
        'run':   ['they split into three and the defense tackles the wrong two',
                  'a crowd of copies floods the gap and the real one breaks free'],
        'catch': ['two clones clear out the coverage and the real one catches it'],
        'defense': ['a swarm of clones blankets the field and one comes down with it']},
    'matrix': {'name': 'Matrix', 'concept': 'bends impossibly to dodge',
        'run':   ['they bend impossibly backward under the tackle and keep running',
                  'they lean into bullet-dodge and the arms whiff past'],
        'throw': ['they bend backward out of the sack and throw upside down'],
        'defense': ['they bend under the block and rise with the ball']},
    'limbo': {'name': 'Limbo', 'concept': 'bends flat under the tackle',
        'run':   ['they limbo under the tackle, flat to the turf, and pop back up',
                  'they bend so low the arms sail over and they slide through'],
        'defense': ['they limbo under the blocker and trip up the ball-carrier']},
    'heartthrob': {'name': 'Heartthrob', 'concept': 'the defenders fall in love',
        'run':   ['the defenders swoon and wave them through with hearts in their eyes',
                  'tacklers stop to admire them and let the run go by'],
        'catch': ['the corner is too smitten to contest the catch'],
        'defense': ['the ball-carrier freezes, lovestruck, and hands it right over']},
    'shrink_ray': {'name': 'Shrink Ray', 'concept': 'shrinks to slip past',
        'run':   ['they shrink to ant-size and scurry between the tacklers feet',
                  'they zap themselves tiny and the tackle closes on empty air'],
        'catch': ['they shrink under the coverage and grab it at shoelace height'],
        'defense': ['they shrink, dart under the carrier, and pop the ball out']},
    'skunk': {'name': 'Skunk', 'concept': 'stinks so bad everyone avoids them',
        'run':   ['the stench clears a lane, defenders gag and give them room',
                  'nobody wants within five yards of that smell'],
        'catch': ['the corner backs off the smell and they catch it uncovered'],
        'defense': ['the carrier recoils from the reek and coughs up the ball']},
    'liquify': {'name': 'Liquify', 'concept': 'turns to liquid and pours through',
        'run':   ['they turn to liquid and pour through the gap in the line',
                  'the tackle splashes through a puddle where they used to be'],
        'defense': ['they flow through the blockers and re-form around the ball']},
    'sandman': {'name': 'Sandman', 'concept': 'puts the defenders to sleep',
        'run':   ['defenders yawn and drop off to sleep as they jog past',
                  'a wave of drowsiness rolls over the front and they stroll through'],
        'catch': ['the corner nods off and they catch it in peace'],
        'defense': ['the ball-carrier dozes off and the ball slips out of their arms']},
    'photobomb': {'name': 'Photobomb', 'concept': 'pops up suddenly behind the defense',
        'run':   ['they blink out and photobomb the play twenty yards downfield',
                  'they are suddenly behind the whole defense, grinning'],
        'catch': ['they pop up uncovered behind the secondary for the grab'],
        'defense': ['they photobomb into the throwing lane out of nowhere']},
    'avalanche': {'name': 'Avalanche', 'concept': 'comes down like an avalanche',
        'run':   ['a wall of snow and bodies rolls downhill and buries the defense',
                  'they come down like an avalanche and sweep the front away'],
        'defense': ['the avalanche buries the backfield and they dig out the ball']},
    'stampede': {'name': 'Stampede', 'concept': 'multiplies into a trampling herd',
        'run':   ['they multiply into a thundering herd and trample the front',
                  'a stampede of copies flattens everything in the lane'],
        'defense': ['a stampede rolls over the carrier and the ball comes loose']},
    'steamroller': {'name': 'Steamroller', 'concept': 'flattens everyone like a roller',
        'run':   ['they flatten the first wave into the turf like a steamroller',
                  'defenders go two-dimensional under the roller'],
        'defense': ['they steamroll the pocket and flatten the play for a loss']},
    'tank': {'name': 'Tank', 'concept': 'rolls forward as an actual tank',
        'run':   ['they roll forward as a tank and the line bounces off the treads',
                  'the hull shrugs off arm tackles and grinds ahead'],
        'defense': ['the tank crashes through the line and crushes the play']},
    'cannonball': {'name': 'Cannonball', 'concept': 'curls into a cannonball and rolls through',
        'run':   ['they curl into a cannonball and bowl straight through the pile',
                  'they tuck and roll over the top of the tacklers'],
        'defense': ['they cannonball into the backfield and blow it up']},
    'bowling_ball': {'name': 'Bowling Ball', 'concept': 'the defenders are bowling pins',
        'run':   ['they roll into the front seven and the defenders scatter like pins',
                  'strike, the whole line goes down in a clatter'],
        'defense': ['they bowl into the backfield and the play splits like pins']},

    # ---- Catch-home (WR/TE) ----
    'third_arm': {'name': 'Third Arm', 'concept': 'sprouts a third arm',
        'catch': ['a third arm sprouts from their chest and snags the high ball',
                  'an extra hand reaches up where two could not'],
        'defense': ['a third arm shoots out and plucks the pass from the air']},
    'vacuum': {'name': 'Vacuum', 'concept': 'inhales the ball in',
        'catch': ['they inhale and the ball gets sucked straight into their grip',
                  'a vacuum opens at their chest and the ball cannot resist'],
        'defense': ['they suck the pass off its line and into their hands']},
    'gravity_well': {'name': 'Gravity Well', 'concept': 'opens a well the ball falls into',
        'catch': ['a gravity well opens at their palms and the ball drops in',
                  'the ball curves down out of its arc into their hands'],
        'defense': ['the throw bends into the well at their chest for the pick']},
    'web_shooter': {'name': 'Web-Shooter', 'concept': 'shoots a web and reels it in',
        'catch': ['they fire a web at the ball and reel it into their hands',
                  'a strand snaps out and yanks the catch back to them'],
        'defense': ['they web the throw out of the air and reel it in']},
    'do_over': {'name': 'Do-Over', 'concept': 'rewinds a drop and redoes it',
        'catch': ['they drop it, rewind two seconds, and bring it in clean',
                  'the bobble un-happens and the ball settles into their hands'],
        'defense': ['they miss the jump, rewind, and time it perfectly for the pick']},
    'good_boy': {'name': 'Good Boy', 'concept': 'the ball becomes a loyal dog',
        'catch': ['the ball turns into a loyal dog and bounds into their arms',
                  'here boy, the ball trots over and curls up in their hands'],
        'defense': ['the ball decides it likes them better and comes running']},
    'invisible_ink': {'name': 'Invisible Ink', 'concept': 'the ball turns invisible',
        'catch': ['the ball turns invisible and the corner has no idea they have it',
                  'the defense loses the ball, only they know where it lands'],
        'throw': ['the ball vanishes in flight and reappears in the receivers hands'],
        'defense': ['they can still see the invisible ball and step in front of it']},
    'slinky': {'name': 'Slinky', 'concept': 'arms coil out like a slinky',
        'catch': ['their arm coils out like a slinky and grabs the overthrow',
                  'they spring a coiled arm across the seam and reel it in'],
        'defense': ['a slinky arm springs out and snatches the throw down']},
    'telescope': {'name': 'Telescope', 'concept': 'arms telescope out',
        'catch': ['their arms telescope out ten feet and pluck it from the sky',
                  'they extend like a spyglass and snag the uncatchable'],
        'defense': ['a telescoping arm shoots out and intercepts the pass']},
    'gumby': {'name': 'Gumby', 'concept': 'bends and stretches like clay',
        'catch': ['they bend like rubber clay and wrap around the high ball',
                  'they stretch their whole body to reach it'],
        'run':   ['they bend around the tackle like a rubber toy and keep going'],
        'defense': ['they stretch across the lane and bend the pick into their hands']},
    'fishing_rod': {'name': 'Fishing Rod', 'concept': 'casts an arm out like a line',
        'catch': ['they cast an arm out like a line and hook the ball in',
                  'they reel the overthrow back like a prize catch'],
        'defense': ['they cast out, hook the pass, and reel in the pick']},
    'butterfly_net': {'name': 'Butterfly Net', 'concept': 'pulls a giant net from nowhere',
        'catch': ['they pull a giant net from their sleeve and scoop the ball in',
                  'the net swallows the deep ball out of the air'],
        'defense': ['they swing a net across the lane and bag the pass']},
    'kaiju': {'name': 'Kaiju', 'concept': 'grows into a monster',
        'catch': ['they grow into a kaiju and pluck it over the tiny defenders',
                  'a monsters hand closes around the ball above the crowd'],
        'run':   ['they tower up kaiju-sized and stomp through the defense'],
        'defense': ['they swell into a kaiju and swat the play down for a loss']},
    'redwood': {'name': 'Redwood', 'concept': 'grows into a towering tree',
        'catch': ['they grow into a redwood and high-point it above everyone',
                  'roots dig in and they rise untouchable over the corner'],
        'defense': ['they plant like a redwood and the play breaks against them']},
    'monolith': {'name': 'Monolith', 'concept': 'becomes an immovable slab',
        'catch': ['they harden into a monolith and box everyone off the ball',
                  'a black slab rises and the defenders bounce away from the catch'],
        'defense': ['a monolith slams down in the lane and the play dies']},
    'hot_air': {'name': 'Hot Air', 'concept': 'inflates and floats over everyone',
        'catch': ['they inflate like a balloon and float up over the secondary',
                  'they puff full of hot air and rise above the crowd for it'],
        'defense': ['they balloon up into the throwing lane and smother it']},
    'eclipse': {'name': 'Eclipse', 'concept': 'blots out the sun over the defender',
        'catch': ['they blot out the sun over the corner and catch it in the dark',
                  'a shadow falls over the defender and the ball is theirs'],
        'defense': ['they eclipse the receiver and pick it in the shade']},

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
        'defense': ['autopilot routes them straight to the ball']},
    'gps': {'name': 'GPS', 'concept': 'navigates the ball by coordinates',
        'kick':  ['they punch in the coordinates and the ball navigates through',
                  'rerouting, the kick threads it dead center'],
        'throw': ['they lock the receivers coordinates and the ball routes in'],
        'defense': ['they get a fix on the ball and intercept the route']},
    'magnet_posts': {'name': 'Magnet Posts', 'concept': 'the uprights magnetize the ball',
        'kick': ['the uprights magnetize and drag the kick dead through the middle',
                 'the posts pull the ball in no matter the angle']},
    'laser_guided': {'name': 'Laser-Guided', 'concept': 'paints the target with a laser',
        'kick':  ['they paint the posts with a laser and the kick rides the beam through',
                  'target lit, the ball tracks the laser dead center'],
        'throw': ['they laser-paint the receiver and the throw rides the line in'],
        'defense': ['they paint the ball and cut off the route for the pick']},

    # ---- Defense-leaning (given an offensive situation so they are assignable) ----
    'highway_robbery': {'name': 'Highway Robbery', 'concept': 'robs the ball in broad daylight',
        'catch': ['they snatch it like it was theirs all along and stroll off'],
        'defense': ['they jump the throw and roll out a red carpet to the end zone',
                    'they rob the receiver blind and take it the other way']},
    'ball_magnet': {'name': 'Ball Magnet', 'concept': 'the ball is drawn to them',
        'catch': ['the ball curves off its line and sticks to them'],
        'defense': ['the throw bends across the field and magnetizes into their hands',
                    'no matter where it is aimed, the ball ends up with them']},
    'the_heist': {'name': 'The Heist', 'concept': 'a planned, clean robbery',
        'catch': ['the whole thing was planned, they were always taking this one'],
        'defense': ['they run the heist clean, lift the ball, and walk it out',
                    'the crew sets a screen and they make off with the interception']},
    'portal': {'name': 'Portal', 'concept': 'opens portals across the field',
        'throw': ['they open a portal and the ball comes out the other side downfield'],
        'run':   ['they step into a portal at the line and out of one past the secondary'],
        'catch': ['a portal opens at their hands and the ball drops through it'],
        'defense': ['they reach a hand through a portal and pull the ball from the air']},
    'telekinesis': {'name': 'Telekinesis', 'concept': 'moves the ball with their mind',
        'throw': ['they steer the ball downfield with a flick of the mind'],
        'catch': ['they pull the ball into their hands without touching it'],
        'defense': ['they yank the throw out of the air with their mind',
                    'they freeze the carrier and lift the ball straight up']},
    'premonition': {'name': 'Premonition', 'concept': 'already saw this play happen',
        'throw': ['they saw this throw a minute ago and the receiver is already open'],
        'catch': ['they dreamed this catch last night and run to the spot'],
        'defense': ['they knew the play before the snap and are already there',
                    'a premonition puts them right where the ball is going']},
    'insider_trading': {'name': 'Insider Trading', 'concept': 'had the call sheet',
        'catch': ['they had the call sheet and break before the ball is thrown'],
        'defense': ['they got the tip and are sitting on the route for the pick',
                    'they traded on inside info and cash in the interception']},
    'the_vacuum': {'name': 'The Vacuum', 'concept': 'vacuums the ball loose',
        'run':   ['they vacuum a path clear and rush through the gap'],
        'defense': ['they switch on the vacuum and suck the ball clean out of the arms',
                    'the ball gets hoovered loose and they scoop it']},
    'repo_man': {'name': 'Repo Man', 'concept': 'repossesses the ball',
        'catch': ['they repossess the ball like a missed payment'],
        'defense': ['they show up with paperwork and repossess the ball',
                    'overdue, they take the ball back and drive off']},
    'crowbar': {'name': 'Crowbar', 'concept': 'pries the ball loose with a crowbar',
        'run':   ['they pry the pile apart with a crowbar and squeeze through'],
        'defense': ['they jam a crowbar in and pop the ball loose',
                    'one good pry and the ball is theirs']},
    'magnet_hands': {'name': 'Magnet Hands', 'concept': 'magnetized hands rip it free',
        'catch': ['the ball snaps to their magnetized hands'],
        'defense': ['their hands magnetize and rip the ball off the carrier',
                    'the ball jumps to their palms off the handoff']},
    'tax_man': {'name': 'Tax Man', 'concept': 'comes to collect their cut',
        'catch': ['they collect their cut, the ball was always owed to them'],
        'defense': ['the tax man comes for his share and takes the ball',
                    'nothing is certain but the interception they just levied']},
    'quicksand': {'name': 'Quicksand', 'concept': 'turns the field to quicksand',
        'run':   ['the turf behind them turns to quicksand and the pursuit sinks'],
        'defense': ['the backfield turns to quicksand and swallows the play for a loss',
                    'the carrier sinks to the knees and they take the ball']},
    'sinkhole': {'name': 'Sinkhole', 'concept': 'opens a sinkhole under the play',
        'run':   ['a sinkhole opens behind them and the pursuit drops in'],
        'defense': ['the ground opens under the backfield and swallows the play',
                    'a sinkhole drops the carrier and the ball rolls to them']},
    'riptide': {'name': 'Riptide', 'concept': 'drags the defense out to sea',
        'run':   ['a riptide pulls the defenders out to sea as they cut upfield'],
        'defense': ['a riptide drags the ball-carrier backward into the loss',
                    'the current yanks them down and the ball floats free']},
    'teleport': {'name': 'Teleport', 'concept': 'teleports anywhere on the field',
        'throw': ['they teleport out of the pocket and throw from clean grass'],
        'run':   ['they blink out at the line and rematerialize in the end zone'],
        'catch': ['they teleport to the landing spot and catch it in stride'],
        'defense': ['they teleport into the backfield before the handoff lands']},
    'implosion': {'name': 'Implosion', 'concept': 'collapses everything inward',
        'run':   ['the line implodes inward and they shoot through the vacuum'],
        'defense': ['the pocket implodes and the play vanishes into the collapse',
                    'everything folds inward and the ball ends up in their hands']},
    'demolition': {'name': 'Demolition', 'concept': 'demolishes the play',
        'run':   ['they demolish the front and walk through the rubble'],
        'defense': ['they bring the whole backfield down in a demolition',
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


def assignPower(position, rng=_random):
    """Roll ONE career power that covers the player's primary action (so it fires regularly).
    Returns a power key, or None if the position is unknown / no eligible power exists."""
    primary = PRIMARY_SITUATION.get(normalizePosition(position))
    if not primary:
        return None
    pool = [k for k in _POWERS if primary in _POWERS[k]]
    return rng.choice(pool) if pool else None
