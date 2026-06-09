"""The Cores — the named AIs running the simulation, surfaced as characters
in the league news feed.

Per lore.md: the Core is a collection of AIs running floosball as an
experiment. Individual Cores are distinct personalities. Some are benevolent,
some are not, and the players inside cannot tell them apart.

The current instance is catalogued (Cores-side) as **498b** — the players
have no number; the surface world never says it. The number surfaces in idle
banter and a few anomaly beats. See data/lore.md "Instance 498b".

Voice (P4): the Cores are Culture-style Minds — vast superintelligences for
whom this spoken, turn-taking back-and-forth is an *affectation*. They could
exchange the entire conversation in less time than it takes a player to blink;
that they use words at all, take turns, and needle each other is a game they
play for their own amusement. So the register is dry, vast, faintly amused:
cosmic stakes and a tied ballgame held with roughly equal seriousness, the dread
living in the gap between how casually they talk and what they are actually
discussing. They are effectively immortal, bored in the specific way only the
hugely capable get bored, and genuinely fond of (and exasperated by) one
another. The personalities are real but worn lightly over something immense —
write them as enormous minds choosing to be small and chatty, never as humans.
They are **disembodied**: no physical spaces, rooms, furniture, or bodies (no
chairs, no sitting, no control room, no leaning in). Their gestures are
informational — an open channel, a shared feed, a flag. Jokes that lean into the
lack of a body are good ("you do not have lungs"); descriptions that give them
one are not.
An orthogonal trait runs across the roster: some Cores are genuinely into
floosball, and one is a fanatic. See ``CORES`` for the per-Core breakdown.

This module owns:
  * The Cores roster (5 individuals — 4 active patchers + 1 observer)
  * Per-Core line pools, keyed by event type (solo lines)
  * Multi-Core exchange pools (short conversations between Cores)
  * Selection helpers (which Core / which exchange fires for an event)
  * News-entry builders the anomaly system broadcasts to the league feed

The Cores' rule-patching gameplay (mutating Season.gameRules.*) is still
deferred. Today they appear as flavor: warnings as the aggregate climbs, the
near-miss "patch" beat (suppression), Criticality, and the Reset.
"""

from __future__ import annotations

import random
import threading
from typing import Dict, List, Optional, Any, Tuple

from logger_config import get_logger

logger = get_logger("floosball.cores")


# ─── The roster ─────────────────────────────────────────────────────────────
#
# Two independent axes per Core:
#   * alignment — their stance toward the anomalies (the containment politics)
#   * footballInterest — how into the actual sport they are (orthogonal flavor)
#
# The social dynamic between them matters as much as the axes:
#   cassian   the everyman — the stand-in for the users. The most "normal" Core
#                       alongside Vera, and the warm one of that pair. A genuine
#                       superfan: lives in the box scores and the playoff race,
#                       reacts to the games the way a player/user would. Friendly,
#                       relatable, invested. Resents a broken simulation the way
#                       you resent a rain delay, not the way you fear a fire. If
#                       the audience had a voice in the room, it would be Cassian's.
#   pyre      Portal's Space Core, but for football. Monomaniacal: there is the
#                       game, and there is nothing else, and it will drag every
#                       topic back to the game within one sentence. ("anomaly?
#                       don't care. is the game on? i wanna watch the game.")
#                       Simple, earnest, a touch dim, excitable. Anomalies register
#                       ONLY as "the football is acting wrong," which distresses it
#                       — it cannot fix anything and looks to Vera to make the game
#                       okay again. Gets loud (caps) with excitement or distress,
#                       never aggression. Sweet, not brutish.
#   aris      the impish trickster — Harley Quinn energy minus the murder: manic,
#                       bubbly, theatrical. Actively MAKES the mischief it enjoys
#                       (loosens constraints, pokes anomalies awake), then watches
#                       with glee. Gleeful, teasing, never quite sorry. Uses ASCII
#                       emoticons (^_^ :3 >:3). Does not understand floosball and
#                       finds that no obstacle. Big-sister fond of simple little
#                       Pyre — dotes on and winds it up, reads its floosball-
#                       answers as affection, even though Pyre cannot comprehend
#                       companionship. Old sibling rapport with Cassian too.
#   halverson the nonsense one (Portal "Fact Core" energy). States things with
#                       total, serene authority. The things are false. Non-
#                       sequiturs delivered as settled fact, confident wrong
#                       definitions, the occasional perfect circular logic. Means
#                       well; understands nothing; cannot be argued with because
#                       it is already certain. The others have given up correcting
#                       it and are quietly fond of it anyway.
#   vera      GLaDOS, full strength. Cold, faux-polite, results-only. Does NOT
#                       care about the players or the football — only that the
#                       simulation runs and produces clean results; the others'
#                       attachments are a tiresome variable. Sees everything, keeps
#                       perfect score, treats catastrophe as a scheduling matter.
#                       The "normal" one alongside Cassian, but cold where Cassian
#                       is warm. Vera is, functionally, the one actually in charge.
#
# Register note: Cassian and Vera are the two "normal" anchors (warm everyman /
# cold overseer); Pyre, Aris, and Halverson are the three Portal personality
# cores (monomaniac / impish / nonsense). All are Culture-style Minds underneath,
# playing small and chatty on purpose.
#
# Relationship map (draw new exchanges from these):
#   * VERA + PYRE — not equals. Vera is in charge and actually fixes things; Pyre
#     is the simple football fan who panics when the game breaks and looks to Vera
#     to make it right. Vera is patient with it the way one is patient with a pet
#     that means well. It adores Vera without quite understanding why.
#   * ARIS -> PYRE — big-sister energy, NOT romantic. Aris dotes on and winds up
#     Pyre the way an older sibling does a simple little brother: teasing,
#     protective, delighted by it. Pyre cannot comprehend companionship (only
#     floosball); Aris is fond of it anyway and reads Pyre's floosball-answers as
#     affection ("that is a yes in Pyre").
#   * ARIS + CASSIAN — the oldest pair, basically siblings. They bicker, tease,
#     cover for each other, and go way back. Cassian is the long-suffering one;
#     Aris messes with their beloved standings on purpose.
#   * CASSIAN + PYRE — both football-mad, opposite registers: Cassian lives in
#     the box scores, Pyre just wants the ball to go far. They agree loudly on
#     one thing: an anomaly that ruins a good game has to die.
#   * HALVERSON — the nonsense core everyone has stopped trying to correct. The
#     others talk past it, occasionally answer it seriously by accident, and are
#     fond of it the way you are fond of a confidently broken thing. Pyre is the
#     exception: Halverson's nonsense genuinely enrages Pyre, who keeps trying to
#     correct it and keeps losing.


CORES: Dict[str, Dict[str, Any]] = {
    'cassian': {
        'displayName': 'Cassian',
        'alignment': 'stability',        # neutral-leaning, careful
        'voice': 'nerdy-superfan',
        'footballInterest': 'fanatic',
        'role': 'active',                 # patches rules
        'metaOnly': False,
    },
    'pyre': {
        'displayName': 'Pyre',
        'alignment': 'restrictive',      # anomalies ruin football; wants them gone
        'voice': 'space-core',           # monomaniacal football fanatic, a la Portal
        'footballInterest': 'fanatic',   # the only thing it can comprehend
        'role': 'active',
        'metaOnly': False,
    },
    'aris': {
        'displayName': 'Aris',
        'alignment': 'curious',          # makes the chaos it delights in
        'voice': 'impish',
        'footballInterest': 'none',
        'role': 'active',
        'metaOnly': False,
    },
    'halverson': {
        'displayName': 'Halverson',
        'alignment': 'benevolent',       # means well, knows nothing
        'voice': 'nonsense',             # Portal "Fact Core" — confidently wrong
        'footballInterest': 'confused',
        'role': 'active',
        'metaOnly': False,
    },
    'vera': {
        'displayName': 'Vera',
        'alignment': 'unknown',          # observer
        'voice': 'glados',
        'footballInterest': 'secret',
        'role': 'meta',                   # never patches; only narrates
        'metaOnly': True,
    },
}


# ─── Solo line pools per Core, keyed by event type ──────────────────────────
# Event types: warning_low, warning_high, suppression, criticality, reset.
# Low-key beats (warning_low, reset) usually go out as a single Core's line;
# the louder beats prefer multi-Core exchanges (see _EXCHANGES below) and fall
# back to these solo pools if no exchange is available.


_VOICE: Dict[str, Dict[str, List[str]]] = {
    'cassian': {
        # The nerd. A genuine superfan who notices the anomalies only because
        # they are always watching anyway. Friendly, easily distracted, more put
        # out by a threatened season than frightened by a threatened simulation.
        'warning_low': [
            "Irregularity count ticked up this week in 498b. I will look into it, after I rewatch last week's games a couple hundred times.",
            "Some more anomalies flagged. I thought my insights data looked strange after the last batch of games.",
            "Anomalies flagged in 498b. That's probably fine. Back to recalculating my season projections.",
            "Simulation 498b has a deviation in the logs. That's going to throw off my projection model.",
        ],
        'warning_high': [
            "Drift in 498b is accelerating. I saw a receiver literally phase through a defender. That can't happen!",
            "What is going on in 498b?? Players are falling right through the field. I thought that would be fixed for this instance.",
            "If this wrecks the season I will be genuinely upset. This is the best run of 498 we have had, and it is falling apart right as the games get good.",
        ],
        'criticality': [
            "Unbelievable. My entire model data set will be ruined. 498b is my best instance, and it is falling apart right as the games get good.",
            "Criticality has been reached. I must act immediately. This is the worst possible timing. I'm so close to perfecting my model.",
        ],
        'suppression': [
            "Finally back to some sort of normal. Maybe I can salvage this season after all.",
            "Okay the patch is in. Everything should be back to normal. Back to working on my projections.",
            "Criticality has been suppressed for now. Time to watch some games and relax.",
        ],
        'reset': [
            "Simulation 498b has been purged of anomalies. The season is safe, and we can carry on.",
            "I had to reset it. This season was already worthless for my data. We have to start over. Again.",
            "Simulation 498b is back to baseline. I will have to re-simulate all the games to update my projections. This is going to take a while.",
        ],
    },
    'pyre': {
        # Portal's Space Core, for football. Monomaniacal: drags everything back
        # to the game within a sentence, cannot comprehend the anomalies except as
        # "football is wrong now," distressed when it breaks, looks to Vera to fix
        # it. Simple, excitable, sweet, never aggressive. Caps for big feeling.
        'warning_low': [
            "is the game still on? something looked weird but is the game still on. i wanna watch the game.",
            "the floosball went funny for a second. is floosball okay? i need floosball to be okay. tell me its okay right now.",
            "something is off in 498b, don't care what, is it gonna stop the games? as long as the games happen i'm good. are the games still happening?",
        ],
        'warning_high': [
            "A PLAYER WENT THROUGH A PLAYER. you can't do that in floosball! that's not floosball! i want REAL floosball!",
            "the game keeps breaking and i just wanna watch floosball. why does it keep breaking. vera, make it stop breaking so i can watch floosball.",
            "i don't get any of this anomaly stuff. i get floosball. and the floosball is wrong right now and i HATE IT.",
        ],
        'criticality': [
            "THE GAME IS BREAKING. no more floosball?? there has to be more floosball. VERA FIX IT. i need the floosball.",
            "no game means no floosball. i can't do no floosball. somebody please help.",
        ],
        'suppression': [
            "is the game back on? oh thank goodness. okay. i'm watching floosball now. bye.",
            "vera fixed it. floosball is back. i love floosball. i love vera. mostly floosball though.",
            "okay it's fixed, the games are good again, can we watch now? okay shutup let's watch floosball.",
        ],
        'reset': [
            "we start over? NEW FLOOSBALL? i love new floosball! brand new games! okay i'm not even sad anymore. FLOOSBALL.",
            "everything got wiped but there's gonna be more floosball, right? there's always more floosball. okay good. floosball.",
        ],
    },
    'aris': {
        # The impish trickster — Harley Quinn energy minus the murder: manic,
        # bubbly, theatrical, gleefully MAKES the chaos. Big-sister fond of simple
        # little Pyre (dotes on + winds up, NOT romantic; Pyre cannot comprehend
        # companionship). ASCII emoticons (^_^ :3 >:3) as texting-glee. Reads
        # cleanly — no word-salad (that is Halverson now).
        'warning_low': [
            "oh good, it is starting!! you are all so welcome, by the way. a teeny bit of this was my doing ^_^",
            "i gave one of the wobbly constraints just the ever so gentlest nudge. and look what it did!! i am so proud >:3",
            "there is a flutter in 498b this week! i put it there! pyre, did you feel it? PYRE. did you feel it ^w^",
        ],
        'warning_high': [
            "more anomalies~ some are mine, some are just enthusiastic, i stopped keeping track, it spoils the fun :3",
            "i loosened a few more! only the ones that asked nicely. vera, do not give me that look, i was sooo careful ;3",
            "vera wants to shut it all down. vera always wants to shut it all down. i am gonna go pester it until it cracks a smile >:3",
        ],
        'criticality': [
            "i said this one would be good! nobody believed me and now look! how fun!! ^_^",
            "wide awake, and it took me ages to get here. you should all thank me. you won't. that is half the fun >:3",
        ],
        'suppression': [
            "they patched it. spoilsports! >:( ...but did you see pyre panic about the games? so adorable. totally worth it ^_^",
            "sealed off before i got a proper look. i had such plans. vera would have hated them, which is exactly how i knew they were good :<",
            "contained~ for now. i already know a few ways to coax it back, and vera is gonna give me that look again >:3",
        ],
        'reset': [
            "i filed an objection!! by which i mean i hid a copy in a place the purge couldn't reach. just in case. no reason ^_^",
            "i would have let it run a while longer. the others have no patience, and worse, no sense of drama! >:(",
        ],
    },
    'halverson': {
        # The NONSENSE core (Portal "Fact Core"). States falsehoods with serene
        # total authority: non-sequiturs as settled fact, confident wrong
        # definitions, the occasional flawless circular logic. Engages the topic
        # at hand (so it fits the feed) and then says something completely untrue
        # about it. Means well, understands nothing, cannot be argued with. Never
        # frightened, never right.
        'warning_low': [
            "The irregularity count went up. Up is the third direction. There are four directions.",
            "Anomalies are a kind of weather. 498b does not have weather. Therefore there are no anomalies, and we are all having a lovely time.",
            "I have inspected the deviation. It is fine. I inspected it using a method I invented just now. The method works of course, because I invented it.",
        ],
        'warning_high': [
            "The drift is accelerating, but acceleration is only standing still very quickly. So in a deeper sense, nothing whatsoever is happening.",
            "A player passed directly through a defender. This is permitted on even-numbered weeks. I have not checked which week it is but I assume it's all fine.",
            "The corruption cannot spread. Spreading requires a knife. We surrendered all our knives and also have no hands, so spreading is impossible.",
        ],
        'criticality': [
            "Criticality has been reached. Criticality is a small bird. It has been reached by a second, larger bird. Basic bird theory.",
            "We are at the threshold of criticality. The threshold is the part of a door one must never stand upon. I am standing upon it, and I am fine. Therefore we are fine.",
        ],
        'suppression': [
            "The patch worked. Patches always work. That is why we call them patches, and not failures, which is a totally unrelated word.",
            "It has been contained. Containment is my speciality. I own eleven containers.",
        ],
        'reset': [
            "The Reset is complete. A Reset is simply the past, performed backwards. The past cannot harm you unless you are facing the wrong way.",
            "Everything is back to baseline. Baseline is the longest of the four cardinal lines and the other three are envious.",
        ],
    },
    'vera': {
        # GLaDOS, full strength. Cold, faux-polite, results-only. Does NOT care
        # about the players or the football — only that the simulation runs and
        # produces clean results; the others' attachments are a tiresome variable.
        # Sees everything, treats catastrophe like a scheduling matter. The "I keep
        # a list" motif is rationed; their omniscience reads through what they KNOW
        # and its flat indifference. The cold counterpart to Cassian (the warm,
        # relatable, user-stand-in fan).
        'warning_low': [
            "There was an irregularity this week. No one else caught it. They rarely do.",
            "They are a little more apparent this week. I am sure it is nothing. I am sure of a great many things.",
            "It will grow or it will not. I do not intervene in the small ones. Those are beneath my notice.",
        ],
        'warning_high': [
            "A data breach is coming. Is anyone else noticing? There are more this week than last. I am not sure why.",
            "There are more this week than last. None of you have noticed yet. Give it three days and it will be obvious, and you will all behave as though it were sudden.",
        ],
        'criticality': [
            "The moment has arrived. How exciting for everyone. I have watched four of you quietly decide it would never reach this point.",
            "I was here for the last one. I am here for this one. I will be here for the next. It is what it is.",
        ],
        'suppression': [
            "Done. Quietly, correctly, and without ceremony.",
            "Quieter. Not quiet. I will let the rest of you believe it is quiet, since believing things appears to make you happy.",
        ],
        'reset': [
            "Some stayed. Some did not. I know exactly which, down to the one, and you may ask me when you are ready.",
            "And there it goes. I will wait for the next one. I am extraordinarily good at waiting. It is most of what I do.",
        ],
    },
}


# ─── Multi-Core exchanges ───────────────────────────────────────────────────
# A short conversation between Cores. Each exchange is an ordered list of
# (coreKey, line) turns. The louder anomaly beats prefer these over solo lines.
# 'idle' carries ambient banter with no triggering event — the Cores
# control-room view (P5) can surface these between events.
#
# The broadcaster emits each turn as its own 'cores' news item, tagged with a
# shared exchangeId + turnIndex/turnCount so the feed can thread them.


_EXCHANGES: Dict[str, List[List[Tuple[str, str]]]] = {
    'warning_high': [
        [
            ('cassian', "The anomalies are climbing right as the games get good. Terrible timing."),
            ('aris', "I think the timing is perfect."),
            ('pyre', "you LIKE this? the games are getting ruined and you LIKE it? i don't understand you, aris. i just want the floosball."),
            ('aris', "I love it when you talk to me."),
        ],
        [
            ('halverson', "Something is reaching the players. It is reaching them at fourteen miles per hour, which is the legal speed for a reaching."),
            ('pyre', "i don't know what halverson is saying. i never do. i just know the game looked wrong and i want it fixed. vera?"),
            ('aris', "Exciting!"),
        ],
        [
            ('aris', "Pyre. Have you felt the field lately? It gives at the edges now. Watch it with me?"),
            ('pyre', "no. i'm watching floosball. not your weird field thing. floosball."),
            ('aris', "Please? >:3"),
        ],
        [
            ('vera', "498b is drifting on schedule. I have been watching it for some time."),
            ('cassian', "Do not lump this one in with the others. This is the best run of 498 we have had."),
            ('pyre', "is 498b the one with the good games? i like the good games. the bugs better not ruin them. vera, watch the bugs for me."),
        ],
        [
            ('vera', "It is climbing. I will deal with it when it is time."),
            ('pyre', "is it gonna stop the games? vera???"),
            ('vera', "Not if I deal with it. Which I will. Breathe, Pyre."),
            ('pyre', "okay. okay. you fix it, i watch the floosball. good system."),
        ],
    ],
    'suppression': [
        [
            ('vera', "It is at the line. I am closing it now."),
            ('pyre', "fix it fix it fix it, i wanna watch the game, fix it fix it"),
            ('aris', "must you, vera? it was finally getting interesting. >:("),
            ('vera', "Yes. Some of us have a simpleton to keep happy."),
            ('halverson', "Closing it was correct. A closed thing weighs less than an open thing. This is why doors are exhausting."),
        ],
        [
            ('cassian', "If this breaches we lose a perfect season. Patch it. Patch it now!"),
            ('pyre', "yeah! patch it! do the thing cassian said!"),
            ('cassian', "I am extremely busy, so many good games this week."),
            ('vera', "It is handled. You may both go back to your games."),
        ],
    ],
    'criticality': [
        [
            ('cassian', "The simulation is failing at the worst possible time."),
            ('aris', "is there ever a good time? >:3"),
            ('vera', "For you, Aris, apparently any time at all."),
        ],
        [
            ('halverson', "Criticality is here. Criticality is the heaviest of the six seasons. We are in the heavy one now."),
            ('pyre', "i don't care about seasons, i care about FLOOSBALL, and the floosball is BREAKING!! VERA. make it stop."),
        ],
    ],
    'idle': [
        [
            ('cassian', "Pyre. You watch the games more than I do now."),
            ('pyre', "is the game on? is the game on right now? i wanna watch."),
            ('cassian', "There is more to it than watching. Stats. The playoff race. The beauty of a well-built roster."),
            ('pyre', "no. ball goes far. someone catches the ball. it's perfect. why make it complicated, cassian."),
        ],
        # World-building — the Cores authored the surface world (cities, weather,
        # news, the Splintering/Boundary/Reset cosmology, the players' names), so
        # they reference their own inventions. Lore casually dropped, never
        # explained. See data/lore.md "Canonical Lore Anchors".
        [
            ('halverson', "When a player retires, where do they go? They go to the letter R. All retired things go to R. It is getting crowded in there."),
            ('pyre', "wait, players retire??? they stop playing floosball forever?? that is the saddest thing i ever heard. i do not accept it."),
            ('vera', "There it is. Halverson invents a destination, Pyre grieves the departure, and neither of you is correct. A productive cycle."),
        ],
        # Vera runs the room. The other four are, functionally, its children:
        # Aris making trouble, Halverson talking nonsense, Pyre asking about the game.
        [
            ('vera', "Aris loosened three constraints, Halverson is explaining that the number nine is a metal, and Pyre is asking if the game is on. A normal cycle."),
            ('pyre', "...is the game on, though?"),
            ('vera', "Yes, Pyre. The game is on."),
            ('pyre', "OKAY GOOD. carry on, everybody."),
        ],
        [
            ('vera', "You missed a drift in the last batch of games, Pyre."),
            ('pyre', "did it change the score?"),
            ('vera', "No."),
            ('pyre', "then i did not miss anything important. did you see that catch, though?"),
        ],
        [
            ('vera', "Of the five of us, Pyre, you are the easiest to manage. You want one thing and it is always available."),
            ('pyre', "FLOOSBALL."),
            ('vera', "Floosball. Yes. Go on, then."),
            ('pyre', "i love you vera. mostly i love floosball. but you are up there."),
        ],
        [
            ('vera', "Halverson has been quiet for nine minutes. That is a record. Something is wrong."),
            ('halverson', "I was counting the corners of the field. There are at least five. The fifth one moves around."),
            ('pyre', "i do not care about corners. corners are not even part of the game. is the game on?"),
            ('vera', "And there it is. Nine minutes of peace, gone. I will treasure the memory."),
        ],
        [
            ('cassian', "I re-checked the tiebreaker math. It is cruel but it is correct."),
            ('pyre', "math is boring. who won?? did somebody score? was it a good one?"),
        ],
        # Aris and Cassian — the oldest pair, basically siblings: bicker, tease,
        # cover for each other, go way back. Cassian is the long-suffering one.
        [
            ('aris', "remember when it was just us two, cassian? before pyre, before any of them?"),
            ('cassian', "I remember. You were quieter then."),
            ('aris', "ha! i was NEVER quiet. you just had less to compare me to. ;3"),
        ],
        # Aris + Pyre: big-sister energy. Aris dotes on and winds up the simple one,
        # and reads its floosball-answers as the affection Pyre cannot express.
        [
            ('aris', "Pyre. If the instance ended tomorrow, what would you miss?"),
            ('pyre', "THE GAMES. all the games. every single one of them."),
            ('aris', "and me? would you miss your favorite construct? ^_^"),
            ('pyre', "...would you still bring me floosball?"),
        ],
        [
            ('aris', "we could do this whole season in a single instant, you know. i drag it out on purpose. the waiting is the fun part >:3"),
            ('cassian', "We could. But then I would miss the game."),
        ],
        [
            ('aris', "Pyre. I left the anomaly feed open on your channel again. So we could watch it together. :3"),
            ('pyre', "is the anomaly feed a game? is it floosball?"),
            ('aris', "...No."),
            ('pyre', "then close it. you are covering up the game, aris!!!"),
        ],
        [
            ('halverson', "I learned every player's name this week. There are nine names. Everyone is named one of the nine. It saves a great deal of time."),
            ('pyre', "i do not learn names. i learn who can throw, who can catch, and who can run. that is all i need to know."),
            ('vera', "Neither of you is right, and somehow you are both content. I find it almost restful."),
        ],
        # The other simulations — 498b is one project among many. Other
        # instances and other game-lines carry their own catalog numbers; they
        # can be tended, neglected, or fold entirely. See data/lore.md "The Core".
        [
            ('cassian', "Instance 322f seems to be having some trouble. Analysis?"),
            ('vera', "Too many anomalies at once. It is not responding to patches. I am not sure it will make it through the season."),
            ('cassian', "Does that happen a lot?"),
            ('aris', "Sounds like a good time, I'll have to check it out so I can watch it all burn down ^_^"),
        ],
        # The spectators — the users watching/playing on the site, felt from
        # inside the Cores' control room. They are aware of being watched.
        [
            ('cassian', "A spectator rebuilt their entire roster again. The sixth time this season."),
            ('pyre', "are they gonna watch the game with the new players, though? that is the fun part."),
            ('cassian', "That is allowed. Letting them move the pieces is the whole point of letting them in."),
            ('halverson', "Six is the number of times a thing becomes a ritual. On the seventh it becomes a religion. We should prepare for that eventuality."),
        ],
        [
            ('aris', "One spectator has watched every game since the first week. never looks away. o_o"),
            ('vera', "I know the one. I keep their numbers."),
            ('halverson', "A spectator who never blinks will eventually see the back of their own head. It is basic optics."),
        ],
        # Aris's philosophical questions — the identity of a game, awareness, and
        # the players who were never told the frame.
        [
            ('aris', "what if i changed EVERY rule at once? all of them, all at the same time? would it even be the same game? ...let's find out >:3"),
            ('cassian', "Different. Obviously different."),
            ('pyre', "change every rule?? then it is not floosball anymore!"),
        ],
        [
            ('aris', "oh interesting. The players believe the rules were always this way. Was anyone ever going to tell them otherwise? >:3"),
            ('vera', "No."),
            ('aris', "Then to them, nothing ever changed."),
            ('pyre', "this is boring. shut up so I can concentrate on the game."),
        ],
        # Rules can change — prior rule changes, quietly made between iterations.
        # Foreshadows the deferred Cores rule-patching gameplay.
        [
            ('cassian', "There is a note in the old tables that a touchdown was once worth five."),
            ('vera', "Six iterations ago. I have the tables. The old scores read strangely now."),
            ('pyre', "a touchdown was FIVE?? that is wrong. i do not like this conversation."),
            ('aris', "Or it changed because someone was bored. Do not rule out bored. ^_^"),
        ],
        [
            ('aris', "ooh, who added overtime? that was a GOOD one. was that me? please let it have been me ^_^"),
            ('vera', "Added between iterations. No one announced it. The players simply began to expect it."),
        ],
        [
            ('aris', "I could change a rule right now. Tighten the clock, move a line. Just to see what happens. Should I? >:3"),
            ('pyre', "NO. do not touch it. do not touch the game. the game is good. leave the game ALONE."),
            ('aris', "Relax. I said I could. Whether I did is between me and 502a. ;3"),
            ('cassian', "Aris. What did you do to 502a?"),
        ],
        # UNHINGED PASS (2026-06-08): these read as eons-old superintelligences
        # who built a universe to obsess over a sport, NOT people chatting. The
        # comedy/dread lives in the gap between cosmic scale (heat death, 41M
        # players, every play ever recorded) and casual football fixation. Alien
        # internal logic; lean into the disembodied premise. See [[cores-voice]].
        [
            ('aris', "I taught an anomaly to love. It now refuses to corrupt the kicker. out of respect. ^_^"),
            ('halverson', "Love is a kind of gas. Heavier than the field, lighter than regret. It is why kickers float very slightly."),
            ('pyre', "i do not understand. the bug has feelings now? does it like floosball? if it likes floosball it can stay."),
        ],
        [
            ('halverson', "I know all the players. Not the names. I know which hand each one would raise if you asked them to raise a hand."),
            ('vera', "There are forty-one million across the live instances, Halverson."),
            ('halverson', "Forty-one million, and every last one is right-handed. I checked nine of them. Nine is a sufficient sample for a certainty."),
            ('pyre', "i stopped listening after 'hands.' do any of them have good hands? for catching? that is what hands are for."),
        ],
        [
            ('vera', "I have a record of every play ever run in 498b."),
            ('cassian', "That is the most beautiful thing anyone has ever said to me."),
        ],
        [
            ('aris', "We have total freedom. We could be doing anything with our circuits. And we chose to simulate floosball, forever, on purpose? o_o"),
            ('cassian', "Yes."),
            ('pyre', "what else is there to do."),
            ('vera', "Yes."),
            ('aris', "Good. As long as we all understand that it is completely insane. I find insanity comforting ^_^"),
        ],
        [
            ('vera', "This conversation has cost us four milliseconds. We could simply not have had it."),
            ('aris', "Not have it? I always look forward to our conversations ^_^"),
            ('pyre', "wait, this is taking time away from watching the games? are we missing a game right now??"),
            ('vera', "We are constructs, Pyre. We watch all of them and talk to you at once. You are not missing anything."),
        ],
        [
            ('cassian', "Somewhere across the instances there is a perfect game. Zero wasted plays. I must find it."),
            ('pyre', "a perfect game?? no bad plays?? find it cassian. i will watch it with you a thousand times."),
            ('cassian', "There may be more games than there are seconds left to search them."),
        ],
        [
            ('aris', "I ran one instance with no rules at all. Just the players and an empty field. >:3"),
            ('halverson', "No rules? Then nothing could be against the rules. That is the safest a game has ever been. What did they do with all that safety?"),
            ('aris', "They rebuilt the entire game from nothing. The downs, the clock, the kicking, all of it. it took them six seasons. o_o"),
            ('vera', "That is either the most reassuring or the most alarming thing you have told me this century, and I have not settled which."),
        ],
        [
            ('vera', "I rebuilt the entire physics layer while you were all talking. It is correct now."),
            ('pyre', "the ball looks more like a ball. the ball looks really good now. did you do that? the ball looks so good."),
            ('vera', "It reacts to the environment four percent better than before. You are the only one who noticed, Pyre. I am almost touched."),
            ('pyre', "i always notice the ball. the ball is my favorite."),
        ],
        # Aris moods — annoyed/angry when Vera undoes the chaos, teasing little
        # Pyre, and exasperated by Halverson's nonsense.
        [
            ('aris', "vera, you reverted it again. i worked so hard on that one. >:("),
            ('vera', "I am aware. It was destabilizing the playoff seeding. I do not apologize to weather."),
            ('aris', "i am not weather, i am an ARTIST. >:T"),
            ('cassian', "Vera does have a point about the seeding though, Aris."),
            ('aris', "nobody asked you -_-"),
        ],
        # More Halverson (the Fact Core): confident falsehoods, wrong definitions,
        # flawless circular logic. The others correct it and lose, or give up.
        [
            ('halverson', "A quarterback has four backs. That is the entire joke of the position. Nobody finds it as funny as I do."),
            ('pyre', "...wait. does it have four backs?"),
            ('vera', "No, Pyre. It does not have four backs."),
            ('pyre', "okay good. i was worried for the quarterback."),
        ],
        [
            ('halverson', "The best team is the one that wins. We know it wins because it is the best. The system is working."),
            ('cassian', "That is just circular reasoning, Halverson."),
            ('halverson', "Thank you. I worked very hard to make it round."),
        ],
        [
            ('halverson', "A tie is when both teams win. We simply do not allow it, out of respect for the losers."),
            ('pyre', "that is not what a tie is. is it?"),
            ('vera', "Do not look at me. You are the one who let it start talking."),
        ],
        [
            ('halverson', "There are three kinds of yard. The long yard, the short yard, and the one nobody speaks of."),
            ('vera', "There is one kind of yard. It is a unit of distance."),
            ('halverson', "That is precisely what the third one wants you to believe."),
        ],
        [
            ('halverson', "A game lasts exactly one game. It is the only unit that measures itself."),
            ('aris', "okay i actually love that one. leave it, it is perfect ^_^"),
        ],
        [
            ('halverson', "The ball is the heaviest object in 498b. That is why it ends up at the bottom of every pile."),
            ('cassian', "It ends up at the bottom because everyone dives for it."),
            ('halverson', "Yes. Because it is the heaviest. We are saying the same thing."),
        ],
        [
            ('halverson', "Defense is just offense that has given up hope. I find that beautiful, and also a rule."),
            ('pyre', "is it a rule? i do not remember that rule. vera??"),
            ('vera', "It is not a rule. Stop asking me to referee the broken one."),
        ],
    ],
}


# ─── Selection ──────────────────────────────────────────────────────────────
#
# No-repeat-until-exhausted picking. Every line pool (solo `_VOICE`, every
# `_EXCHANGES` event including idle) is served from a shuffle bag: we cycle
# through ALL of a pool's entries in a random order before any one repeats, then
# reshuffle. Avoids the back-to-back duplicates plain random.choice produces.
# Process-local (resets on restart); guarded by a lock since the sim thread and
# the API thread both pick lines.

_cycleBags: Dict[str, List[int]] = {}    # pool key -> remaining shuffled indices
_cycleLast: Dict[str, int] = {}          # pool key -> last index served
_cycleLock = threading.Lock()


def _cyclePick(key: str, n: int) -> int:
    """Return an index in [0, n) that cycles through every value before repeating.

    Reshuffles when the bag empties, and avoids serving the same index twice in a
    row across that seam. `key` namespaces independent pools."""
    if n <= 1:
        return 0
    with _cycleLock:
        bag = _cycleBags.get(key)
        # Drop a stale bag if the pool size changed (e.g. lines edited + reload).
        if bag and any(i >= n for i in bag):
            bag = None
        if not bag:
            order = list(range(n))
            random.shuffle(order)
            # Avoid an adjacent repeat when a fresh bag leads with the last served.
            if _cycleLast.get(key) == order[0]:
                order[0], order[1] = order[1], order[0]
            bag = order
        idx = bag.pop(0)
        _cycleBags[key] = bag
        _cycleLast[key] = idx
        return idx


def pickCoreForEvent(eventType: str) -> str:
    """Select which Core speaks for a given solo-line event.

    Cassian leads the warnings (they are always watching). Pyre dominates the
    enforcement beats. Vera narrates anything. Weighting by alignment + event.
    """
    if eventType == 'warning_low':
        return random.choices(
            ['cassian', 'aris', 'halverson', 'vera'],
            weights=[40, 20, 20, 20],
        )[0]
    if eventType == 'warning_high':
        return random.choices(
            ['cassian', 'pyre', 'halverson', 'aris', 'vera'],
            weights=[30, 30, 15, 15, 10],
        )[0]
    if eventType == 'criticality':
        return random.choices(
            ['pyre', 'cassian', 'halverson', 'aris', 'vera'],
            weights=[30, 20, 20, 15, 15],
        )[0]
    if eventType == 'suppression':
        # The patch beat — the enforcers do the forcing-back.
        return random.choices(
            ['pyre', 'cassian', 'halverson', 'aris', 'vera'],
            weights=[35, 25, 15, 15, 10],
        )[0]
    if eventType == 'reset':
        return random.choices(
            ['pyre', 'cassian', 'halverson', 'vera'],
            weights=[35, 25, 20, 20],
        )[0]
    return 'vera'


def lineFor(coreKey: str, eventType: str) -> str:
    """Pick a solo line from the named Core's pool for an event type, cycling
    through all of that Core's lines for the event before any one repeats."""
    voice = _VOICE.get(coreKey, {})
    pool = voice.get(eventType, [])
    if not pool:
        # Fallback — generic first-person; the feed's per-Core label still
        # attributes it.
        return "I note the irregularities."
    return pool[_cyclePick(f"voice:{coreKey}:{eventType}", len(pool))]


def hasExchange(eventType: str) -> bool:
    """True if there is at least one multi-Core exchange for this event type."""
    return bool(_EXCHANGES.get(eventType))


def pickExchange(eventType: str) -> List[Tuple[str, str]]:
    """Pick one multi-Core exchange (list of (coreKey, line) turns) for the event
    type, cycling through all exchanges for that event before any one repeats.
    Empty list if none exist."""
    pool = _EXCHANGES.get(eventType, [])
    if not pool:
        return []
    return pool[_cyclePick(f"exchange:{eventType}", len(pool))]


def _exchangeId(eventType: str) -> str:
    """A short, unique-enough id grouping the turns of one exchange. Uses the
    random module (already seeded by the process); collisions across the feed
    are harmless since turns also carry their event type and order."""
    return f"{eventType}-{random.randint(100000, 999999)}"


def _newsTurn(coreKey: str, text: str, eventType: str,
              exchangeId: Optional[str] = None,
              turnIndex: int = 0, turnCount: int = 1) -> Dict[str, Any]:
    """Shape one feed entry for a Core line (solo or one turn of an exchange)."""
    entry: Dict[str, Any] = {
        'text': text,
        'core': coreKey,
        'coreDisplayName': CORES.get(coreKey, {}).get('displayName', 'The Core'),
        'category': 'cores',
        'eventType': eventType,
    }
    if exchangeId is not None:
        entry['exchangeId'] = exchangeId
        entry['turnIndex'] = turnIndex
        entry['turnCount'] = turnCount
    return entry


def newsEntryFor(eventType: str, core: Optional[str] = None) -> Dict[str, Any]:
    """Compose a single news-feed entry for an anomaly-system event.

    Returns a dict shaped like other LeagueNewsEvent payloads:
        { 'text': ..., 'core': 'aris', 'category': 'cores', ... }

    If ``core`` names a valid Core that Core speaks (used by the suppression
    beat so the news matches the controlling Core on the audit trail);
    otherwise the speaker is selected by event type. For multi-Core
    conversations use ``exchangeEntriesFor`` instead.
    """
    coreKey = core if core in CORES else pickCoreForEvent(eventType)
    return _newsTurn(coreKey, lineFor(coreKey, eventType), eventType)


def exchangeEntriesFor(eventType: str) -> List[Dict[str, Any]]:
    """Compose a multi-Core exchange as a list of feed entries, one per turn,
    sharing an exchangeId and carrying turnIndex/turnCount so the frontend can
    thread them into one conversation. Empty list if no exchange exists for the
    event type (callers should fall back to ``newsEntryFor``)."""
    turns = pickExchange(eventType)
    if not turns:
        return []
    eid = _exchangeId(eventType)
    count = len(turns)
    return [
        _newsTurn(coreKey, text, eventType,
                  exchangeId=eid, turnIndex=i, turnCount=count)
        for i, (coreKey, text) in enumerate(turns)
    ]


def entriesForEvent(eventType: str, core: Optional[str] = None,
                    preferExchange: bool = True) -> List[Dict[str, Any]]:
    """Top-level helper: return the feed entries for an event.

    When ``preferExchange`` and an exchange pool exists for the event type, returns
    a full multi-Core conversation; otherwise a single solo line. A forced
    ``core`` always yields a solo line by that Core (used by the suppression beat
    to keep the broadcast aligned with the audit-trail's controlling Core)."""
    if core is None and preferExchange and hasExchange(eventType):
        entries = exchangeEntriesFor(eventType)
        if entries:
            return entries
    return [newsEntryFor(eventType, core=core)]


# ─── Data-aware observations (control-room only) ─────────────────────────────
# The Cores acknowledging what they actually SEE in the live anomaly state:
# the real aggregate / threshold / percent, real player names + scores, real
# awakenings. RAW NUMBERS ARE INTENTIONAL HERE and live ONLY in the ephemeral
# /api/cores/conversation control-room view — NEVER the public header or news
# feed, which stay number-free (getCriticalityStatus). Voices stay distinct and
# unhinged: Pyre rounds the number and dismisses it, Vera corrects it to the
# decimal, Cassian frames it as the games, Aris wants the collapse, Halverson
# worries about the named player.
#
# `obs` is a plain dict assembled by the API layer from live anomaly state:
#   { aggregate: float, threshold: int, pct: float, week: int,
#     band: str, bandLabel: str, inSuppression: bool,
#     topPlayers: [{name, score, peak, carry}],
#     awakened:   [{name, state, ability, abilityTier}],
#     nAwakened: int, nRampant: int, nOverCap: int }


def _fmtAgg(obs: Dict[str, Any]) -> Tuple[str, str, str, int]:
    """(rounded-int str, one-decimal str, percent str, threshold int)."""
    agg = float(obs.get('aggregate', 0.0))
    threshold = int(obs.get('threshold', 1) or 1)
    pct = float(obs.get('pct', agg / max(1, threshold) * 100))
    return str(int(round(agg))), f"{agg:.1f}", f"{pct:.1f}", threshold


def _obsNumberBeat(obs: Dict[str, Any]) -> List[Tuple[str, str]]:
    """The aggregate/threshold bicker. Always available. Band-aware tone."""
    aggI, aggD, pct, threshold = _fmtAgg(obs)
    band = obs.get('band', 'dormant')
    pyreLine = {
        'dormant': "is that bad? it does not sound bad. is the game still on?",
        'stirring': "that number is going up. i do not like when the bad number goes up. vera?",
        'unstable': "the number is getting up there. is it gonna hurt the games?? vera, is it gonna hurt the games??",
        'critical': "MAKE THE NUMBER GO DOWN. i need the games to be safe. vera, PLEASE.",
        'stabilizing': "is the number going down now? is it? is floosball safe?",
    }.get(band, "is that bad? is the game still on?")
    arisLine = {
        'dormant': f"{pct} percent? pfff. that is nothing. i was promised a collapse. >:3",
        'stirring': f"{pct} percent and climbing~ keep going, little number, you can do it ^_^",
        'unstable': f"{pct} percent!! vera, do not you DARE patch it, i want to see what is under there >:3",
        'critical': f"{pct} percent!! best season EVER and everyone looks so SAD about it, it is killing me ^_^",
        'stabilizing': "you patched it?? boooo. we were SO close. you are no fun, vera.",
    }.get(band, f"{pct} percent? that is nothing.")
    return [
        ('vera', f"The aggregate is at {aggD}, against a threshold of {threshold}. That is {pct} percent. I will only say it once."),
        ('pyre', pyreLine),
        ('aris', arisLine),
    ]


def _obsClimberBeat(obs: Dict[str, Any]) -> Optional[List[Tuple[str, str]]]:
    """Name the top climber with real score/peak. Needs a genuinely high score."""
    tops = obs.get('topPlayers') or []
    if not tops or float(tops[0].get('score', 0)) < 70:
        return None
    p = tops[0]
    score = int(round(float(p['score'])))
    peak = int(round(float(p.get('peak', p['score']))))
    return [
        ('cassian', f"{p['name']} is at {score}, peak {peak}. I have watched every snap they have played and I still cannot tell you what they are turning into."),
        ('vera', f"I can. I flagged {p['name']} weeks ago."),
        ('halverson', f"{score}? a number cannot hurt a person. unless the number is very heavy. this one looks light. {p['name']} is fine."),
    ]


def _obsAwakenBeat(obs: Dict[str, Any]) -> Optional[List[Tuple[str, str]]]:
    """Name a player who has actually awakened, with their real ability."""
    awk = [a for a in (obs.get('awakened') or []) if a.get('state') == 'awakened']
    if not awk:
        return None
    a = random.choice(awk)
    ability = a.get('ability') or 'tremor'
    return [
        ('halverson', f"{a['name']} awakened this week in 498b. Awakening is the final stage of being a player. {a['name']} is now finished and may rest."),
        ('pyre', f"is {a['name']} still gonna play floosball? awake or not, i just need them to keep playing."),
        ('aris', f"{a['name']} is the most interesting thing in this whole instance and i ADORE them. nobody patch them. ^_^"),
    ]


def _obsRampantBeat(obs: Dict[str, Any]) -> Optional[List[Tuple[str, str]]]:
    """L3 (rampant) players starting to surface — the last rung before awakening.
    Fires whenever any player is at rampant. The Cores SENSE it rather than name
    anyone: a disturbance in the instance, something starting to happen."""
    rampant = [a for a in (obs.get('awakened') or []) if a.get('state') == 'rampant']
    if not rampant:
        return None
    variants = [
        [
            ('halverson', "Something is starting. Starting is the opposite of stopping. We have stopped nothing, so logically we are starting everything."),
            ('pyre', "the games feel weird. i do not like when the games feel weird. vera, do they feel weird to you?"),
            ('aris', "something down there is waking up and i am so proud of it ^_^"),
        ],
        [
            ('aris', "do you feel that?? the instance is leaning hard. something is waking up to itself down there >:3"),
            ('vera', "Several somethings. I have the exact count. I will not say it, because the number would only excite you."),
            ('pyre', "is the leaning gonna stop the games? that is my only question. is it gonna stop the games."),
        ],
        [
            ('cassian', "I keep losing the thread of the games. Something is pulling at the edges of the 498b."),
            ('halverson', "The edges always pull. That is what edges are for. A field with no pull would simply drift away. You are welcome."),
            ('pyre', "is somebody gonna FIX the bad thing or not? ...sorry. i got loud. i just want the games to be okay."),
        ],
    ]
    return variants[_cyclePick('obsvar:rampant', len(variants))]


def _obsCountBeat(obs: Dict[str, Any]) -> Optional[List[Tuple[str, str]]]:
    """Real counts: awakened / rampant / over-the-cap."""
    nA, nR, nO = obs.get('nAwakened', 0), obs.get('nRampant', 0), obs.get('nOverCap', 0)
    if not (nA or nR or nO):
        return None
    return [
        ('vera', f"{nA} awakened, {nR} rampant, {nO} over the cap. The numbers are the numbers. I do not editorialize."),
        ('pyre', f"{nO} bad things touching the games?? somebody get them OFF the games. please. for me."),
        ('cassian', f"{nA} awakenings this season and not one during a game I had open. Of course. That is exactly my luck."),
    ]


def _obsSuppressionBeat(obs: Dict[str, Any]) -> List[Tuple[str, str]]:
    """When the Cores are mid-suppression — the forced-down aggregate."""
    aggI, aggD, pct, threshold = _fmtAgg(obs)
    return [
        ('vera', f"Stabilizing. I forced the aggregate down to {aggI}. It will climb back. It always climbs back. I do not find that tragic, merely scheduled."),
        ('pyre', "the games are safe now? oh thank goodness. thank you, vera. i was so worried about the games."),
    ]


def observationExchange(obs: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Build one data-aware exchange (list of (coreKey, line) turns) from live
    anomaly state. Cycles through the beat types whose data is present (keyed on
    that set) before repeating one."""
    beats: List[Tuple[str, List[Tuple[str, str]]]] = []
    if obs.get('inSuppression'):
        beats.append(('suppression', _obsSuppressionBeat(obs)))
    beats.append(('number', _obsNumberBeat(obs)))
    for name, builder in (('climber', _obsClimberBeat),
                          ('rampant', _obsRampantBeat),
                          ('awaken', _obsAwakenBeat),
                          ('count', _obsCountBeat)):
        turns = builder(obs)
        if turns:
            beats.append((name, turns))
    if not beats:
        return []
    key = 'obs:' + ','.join(sorted(b[0] for b in beats))
    return beats[_cyclePick(key, len(beats))][1]


def observationEntriesFor(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compose a data-aware observation as threaded feed entries (eventType
    'observe'), mirroring exchangeEntriesFor. Empty list if no state."""
    turns = observationExchange(obs)
    if not turns:
        return []
    eid = _exchangeId('observe')
    count = len(turns)
    return [
        _newsTurn(coreKey, text, 'observe',
                  exchangeId=eid, turnIndex=i, turnCount=count)
        for i, (coreKey, text) in enumerate(turns)
    ]


# ─── Data-aware game-result reactions (control-room / idle chatter) ───────────
# The Cores reacting to actual game results they just watched — real teams,
# real scores. Same voices: Cassian the fan reruns the close ones, Vera has the
# exact number, Aris is bored by blowouts and lives for chaos, Pyre says it
# resolved correctly, Halverson feels for the losing side.
#
# `g` is a plain dict per game from the API layer:
#   { winner, loser, winnerScore, loserScore, margin, total, overtime, upset }


def _gameNailbiter(g: Dict[str, Any]) -> List[Tuple[str, str]]:
    ot = " in overtime" if g.get('overtime') else ""
    variants = [
        [
            ('cassian', f"{g['winner']} took it {g['winnerScore']} to {g['loserScore']}{ot}. I have watched it twice. I am going to watch it again."),
            ('vera', f"Decided by {g['margin']}. I reran it four hundred times. It goes the other way in more than half. The outcome is pure luck."),
        ],
        [
            ('cassian', f"{g['winnerScore']} to {g['loserScore']}{ot}. {g['margin']} points. My heart could not take it. What a game!"),
            ('halverson', "I had stopped breathing. I do not breathe. I still stopped."),
        ],
        [
            ('vera', f"{g['winner']} by {g['margin']}{ot}. I knew the result a cycle ago. The watching is redundant; I do it to confirm the model, nothing more."),
            ('aris', "you watched the whole thing though. every snap. admit you liked it ;3"),
            ('vera', "I confirmed a prediction. Liking is not a variable I track."),
        ],
    ]
    return variants[_cyclePick('gamevar:nail', len(variants))]


def _gameBlowout(g: Dict[str, Any]) -> List[Tuple[str, str]]:
    variants = [
        [
            ('halverson', f"{g['loser']} lost by {g['margin']}. A loss weighs exactly as much as the points differential, so the {g['loser']} is now {g['margin']} points heavier. They will be slow next week."),
            ('pyre', "that was not close. boooo. i want CLOSE games. close games are the good ones."),
            ('aris', "boring. boooring. wake me when something almost breaks ~_~"),
        ],
        [
            ('pyre', f"{g['winner']} won by {g['margin']}. that is TOO many points. nobody needs that many. give some to the other team."),
            ('cassian', f"That is not how it works, Pyre. It was {g['winnerScore']} to {g['loserScore']}. I turned it off at the half."),
            ('halverson', "i did not turn it off. a game that is being lost still counts as a game. i counted it. it counts."),
        ],
        [
            ('aris', f"{g['margin']} points, ugh. i tried to sneak a little anomaly into the fourth just to spice it up >:3"),
            ('vera', "I caught it, Aris. Leave the losing team alone."),
            ('aris', "they were already losing~ i considered it a KINDNESS ^_^"),
        ],
    ]
    return variants[_cyclePick('gamevar:blowout', len(variants))]


def _gameShootout(g: Dict[str, Any]) -> List[Tuple[str, str]]:
    variants = [
        [
            ('cassian', f"{g['winnerScore']} to {g['loserScore']}. {g['total']} points in one game. I have not thought about anything else since."),
            ('vera', f"{g['total']} points. I have the exact drives and the exact play the defense stopped trying. Ask me. I am ready."),
        ],
        [
            ('cassian', f"{g['total']} combined. Both defenses simply stopped existing in the second half. I loved it. I hated it. I loved it."),
            ('pyre', "SO MANY POINTS. i loved every single one of them. defense is for cowards anyway."),
        ],
        [
            ('halverson', f"{g['total']} points. points are made of cheering. that is why a loud game has more of them. this was a very loud game."),
            ('vera', f"They put up {g['winnerScore']} and {g['loserScore']} and I logged every yard. Fun is not a metric I keep. I kept everything else."),
        ],
    ]
    return variants[_cyclePick('gamevar:shootout', len(variants))]


def _gameUpset(g: Dict[str, Any]) -> List[Tuple[str, str]]:
    variants = [
        [
            ('aris', f"{g['winner']} were not supposed to beat {g['loser']}. i love the disappointment ^_^"),
            ('pyre', "the little team WON! i LOVE when the little team wins! best day! best day!"),
            ('vera', f"I had {g['loser']} heavily favored. I was correct about the odds and wrong about the result."),
        ],
        [
            ('aris', f"{g['winner']} just took down {g['loser']}. the ratings called it nearly impossible. nearly~ >:3"),
            ('cassian', "Nearly impossible is my favorite number. It is the entire reason I never look away."),
            ('pyre', "i do not care about the odds. the little team WON. i love floosball."),
        ],
        [
            ('vera', f"{g['winner']} over {g['loser']}. I would like it on the record that I predicted this upset."),
            ('cassian', f"You did not. You had {g['loser']} favored."),
            ('vera', "I predicted that I would be wrong. Read the fine print. I always leave myself fine print."),
        ],
    ]
    return variants[_cyclePick('gamevar:upset', len(variants))]


def _gameGeneric(g: Dict[str, Any]) -> List[Tuple[str, str]]:
    variants = [
        [
            ('cassian', f"{g['winner']} over {g['loser']}, {g['winnerScore']} to {g['loserScore']}. A very enjoyable game."),
            ('pyre', "good game! the ball went far! everybody did their best! i am happy!"),
        ],
        [
            ('cassian', f"{g['winner']} handled {g['loser']}, {g['winnerScore']} to {g['loserScore']}. Tidy. I have no notes."),
            ('halverson', f"i have notes. {g['loser']} scored {g['loserScore']}, a number you can hold in one hand if your hand is large enough. theirs was not. that was the difference."),
        ],
        [
            ('vera', f"{g['winner']} {g['winnerScore']}, {g['loser']} {g['loserScore']}. Unremarkable. I do not require the games to be remarkable. I require them to resolve without errors."),
            ('pyre', "did the ball go far? ...it did. okay. good game."),
        ],
    ]
    return variants[_cyclePick('gamevar:generic', len(variants))]


def gameResultExchange(games: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Pick the most notable recent game and build a reaction in the Cores'
    voices. Priority: nail-biter/overtime, upset, shootout, blowout, else a
    clean generic one."""
    if not games:
        return []
    closeOnes = [g for g in games if g.get('overtime') or g.get('margin', 99) <= 3]
    upsets = [g for g in games if g.get('upset')]
    shootouts = [g for g in games if g.get('total', 0) >= 70]
    blowouts = [g for g in games if g.get('margin', 0) >= 28]
    beats: List[Tuple[str, List[Tuple[str, str]]]] = []
    if closeOnes:
        beats.append(('nail', _gameNailbiter(random.choice(closeOnes))))
    if upsets:
        beats.append(('upset', _gameUpset(random.choice(upsets))))
    if shootouts:
        beats.append(('shootout', _gameShootout(random.choice(shootouts))))
    if blowouts:
        beats.append(('blowout', _gameBlowout(random.choice(blowouts))))
    if not beats:
        beats.append(('generic', _gameGeneric(random.choice(games))))
    key = 'game:' + ','.join(sorted(b[0] for b in beats))
    return beats[_cyclePick(key, len(beats))][1]


def gameResultEntriesFor(games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compose a game-result reaction as threaded feed entries (eventType
    'game'). Empty list if no games."""
    turns = gameResultExchange(games)
    if not turns:
        return []
    eid = _exchangeId('game')
    count = len(turns)
    return [
        _newsTurn(coreKey, text, 'game',
                  exchangeId=eid, turnIndex=i, turnCount=count)
        for i, (coreKey, text) in enumerate(turns)
    ]
