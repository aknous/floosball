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
#   cassian   the nerd. A genuine superfan — lives in the box scores and the
#                       playoff race. Friendly to everyone, but perpetually
#                       half-distracted by a game they would rather be watching.
#                       Doesn't want the simulation breaking; resents it the way
#                       you resent a rain delay, not the way you fear a fire.
#   pyre      the curmudgeon. Grumbles constantly, but is deeply invested: the
#                       simulation is theirs, built on purpose, and Pyre will not
#                       watch their own experiment come apart. Gruff, contrary,
#                       allergic to being thanked. The protectiveness is for what
#                       they all made, never a duty imposed on them — Pyre grumbles
#                       the way a proud builder grumbles over their own work.
#   aris      the whimsical one. Delighted by the chaos, a little odd, follows
#                       their own amusement wherever it leads — but stays
#                       intelligible; light comic relief, not nonsense. Has their
#                       own slant on everything and says it deadpan. Does not
#                       understand floosball and finds that no obstacle to
#                       enjoying it. Wants the anomalies to happen; they are the
#                       only interesting thing here. Keeps trying to befriend Pyre
#                       precisely because Pyre is so distant.
#   halverson the earnest one. Loves the players more than the game. The others
#                       gently make fun of them for it; they take it and keep
#                       caring anyway.
#   vera      the observer, GLaDOS-flavored: faux-polite, cutting, bone-dry,
#                       treats catastrophe with bureaucratic calm. Claims total
#                       indifference to the football and keeps perfect score of
#                       everything, the others' mistakes included.
#
# Relationship map (draw new exchanges from these):
#   * PYRE + VERA — the two competent adults. They do the actual work, privately
#     regard the other three as children, and bicker constantly, each certain
#     they alone hold the place together. The friction is mutual respect neither
#     will admit to.
#   * ARIS -> PYRE — one-sided. Aris pines after Pyre; Pyre is not cruel, just
#     genuinely unmoved, and Aris reads hope into the smallest scrap.
#   * ARIS + CASSIAN — the oldest pair, basically siblings. They bicker, tease,
#     cover for each other, and go way back. Cassian is the long-suffering one;
#     Aris messes with his beloved standings.
#   * HALVERSON — the anxious worrier (Chuckie Finster) the others gently rib and
#     quietly look after. Voices the scary thought no one else will; the two
#     adults talk them down.


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
        'alignment': 'restrictive',      # hostile to anomalies
        'voice': 'cold-calculating',
        'footballInterest': 'none',
        'role': 'active',
        'metaOnly': False,
    },
    'aris': {
        'displayName': 'Aris',
        'alignment': 'curious',          # delights in the chaos
        'voice': 'whimsical',
        'footballInterest': 'none',
        'role': 'active',
        'metaOnly': False,
    },
    'halverson': {
        'displayName': 'Halverson',
        'alignment': 'benevolent',       # protective of players
        'voice': 'earnest',
        'footballInterest': 'fond',
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
            "Irregularity count ticked up this week. I will look into it. After the late game. It is a division rematch, I am not missing it.",
            "The numbers are a little off this week. I only caught it because I run the box scores by hand. Yes it's for fun.",
            "Three anomalies flagged. I flagged them right back. Now, has anyone been following the playoff race, because it is genuinely incredible.",
            "There is a deviation in the logs. I bookmarked it right next to my playoff projections, which, I will be honest, I am more excited about.",
        ],
        'warning_high': [
            "The drift is accelerating. So is the MVP race, and I know which one I would rather be tracking.",
            "Per the projections this is ahead of schedule. I would make a fuss about it but the next set of games are about to start.",
            "If this wrecks the season I will be genuinely upset. There are so many good teams this season. Do you understand how rare that is?",
        ],
        'criticality': [
            "I have backed up every stat line, every record, every box score. Whatever happens, the season existed. That part matters to me.",
            "We are at the threshold. I am told that is bad. I was really hoping to see how the seeding shook out.",
        ],
        'suppression': [
            "There, it is contained. The standings are intact and I can get back to the games, which is all I really wanted.",
            "It is patched, and nobody lost a season today. You are all welcome. Now please be quiet, the games are back on.",
            "We held the line, so I am going to go watch something that is actually fun now.",
        ],
        'reset': [
            "The history came through clean, every standing intact. That is the part I refuse to lose.",
            "Whatever else they reset, they cannot undo that it happened. The season was real and it was mine.",
            "That is 498b finished. It was a good one, and I would know, I watched all of it.",
        ],
    },
    'pyre': {
        # The curmudgeon. Grumbles constantly, but is deeply invested: this
        # simulation is theirs, built on purpose, and Pyre will not watch their own
        # experiment come apart. Gruff, contrary, allergic to being thanked. The
        # protectiveness is for what they all made, never a duty imposed on them.
        'warning_low': [
            "The anomalies are starting. Of course they are. I built this to run cleanly and I intend to keep it that way.",
            "Deviants multiplying again. Yes, I see them. No, I do not need help. I have been keeping this simulation in one piece since before the rest of you took an interest.",
            "Something is loose. Yes, I see it. I always see it. Give me a moment and stop fussing.",
        ],
        'warning_high': [
            "I could resolve this in a moment. I am taking my time. We made something worth getting right, so I am going to get it right.",
            "The anomalies think they are unobserved. They are not. Nothing moves in this simulation that I did not help build.",
            "Climbing again. Fine. Fine. I will hold it together, the same as I always do. This is ours, and I am not about to let it fold.",
        ],
        'criticality': [
            "I said this would happen. Nobody listens to me. I will hold it together anyway, because I am not going to watch our own experiment come apart.",
            "The corruption is at the threshold. Holding it is the easy part. The hard part is doing it with all of you talking.",
        ],
        'suppression': [
            "I forced it back. It was no trouble. Well, some trouble. I am not about to let our best instance unravel over a handful of loose anomalies.",
            "There, I have removed the excess. You are welcome. No, do not make a thing of it. Halverson, put the optic-tears away.",
            "It is contained, and that is the end of it. The simulation runs clean again, which is the only way I care for it.",
        ],
        'reset': [
            "Order is restored and we carry on. Try not to make me do this again so soon. I would like a stretch to simply watch the thing we built run.",
            "It is purged and done with. There. It is handled, as it always is, and the simulation is ours again, the way it should be.",
        ],
    },
    'aris': {
        # The whimsical one. Delighted by the chaos, a little odd, deadpan about
        # their own slant on things. Pines after Pyre (unrequited) and has an
        # old sibling rapport with Cassian. Comic relief that still reads
        # cleanly — no word-salad.
        'warning_low': [
            "Oh good, something is finally happening. I was getting so bored.",
            "A player walked clean out of the field and back in again. I do not know what the field is for, but that was wonderful.",
            "There is a flutter in 498b this week. A good one. Pyre, did you feel it, or was that just me?",
        ],
        'warning_high': [
            "More anomalies. I stopped counting and started watching. Watching is the better part anyway.",
            "I loosened a constraint or two. Only the wobbly ones. You could tell they wanted out. Pyre, do not be cross, I was careful.",
            "Pyre wants to shut it all down. Pyre is wrong, but dependably wrong, which I respect. I am going to go and change their mind.",
        ],
        'criticality': [
            "I said this one would be interesting. Nobody believed me. They never do, right up until I am proven right.",
            "Wide awake. I would not miss this for anything, and I worked very hard to make it happen.",
        ],
        'suppression': [
            "They patched it. It was nearly a whole new game. Pyre did it, with that little frown. I am very fond of the frown.",
            "They sealed it off before I got a proper look. I had such plans. You would have loved them. Probably.",
            "It is contained, for now. I think I know how to coax it back, and Pyre is going to pretend to hate that.",
        ],
        'reset': [
            "I filed an objection. I do not think it went anywhere. They rarely do.",
            "I would have waited to see what else came through. The others have no patience, and worse, no sense of theatre.",
        ],
    },
    'halverson': {
        # The anxious worrier (Chuckie Finster energy). Loves the players, frets
        # constantly, voices the scary thought no one else will, catastrophizes,
        # needs reassurance. Sweet and loyal; gets gently dragged along and ribbed
        # by the others, and keeps caring anyway.
        'warning_low': [
            "Something is unsettling the players. I can see it in how they carry themselves onto the field. That cannot be good. Tell me that is nothing.",
            "Is anyone else worried about this? I am worried about this. I am usually worried, but this time I think I am right to be.",
        ],
        'warning_high': [
            "This is the bad kind, isn't it. I knew it would be the bad kind. It is always the bad kind eventually.",
            "Could we please be careful with them this time? I know I always say it. I say it because no one else will.",
        ],
        'criticality': [
            "I knew it. I said it would come to this and nobody wanted to hear it. Please, whatever happens, remember that they are people.",
            "I am frightened for them. I am allowed to be frightened. One of us should be.",
        ],
        'suppression': [
            "Oh, thank goodness. The players are safe this week. I was bracing for so much worse. I am always bracing for worse.",
            "It held. It held. I did not think it would hold. I never think it will, and somehow it usually does, and I never quite believe it.",
            "They get a little more time. That is all I wanted. I will worry again tomorrow, but tonight, that is enough.",
        ],
        'reset': [
            "I did not sign the order. I never sign them. I could not. Please do not ask me to.",
            "The Reset went ahead without me. I stayed with the ones who were left instead. Someone should. I could not just leave them.",
        ],
    },
    'vera': {
        # GLaDOS-flavored observer. Faux-polite, bone-dry, cutting. Treats
        # catastrophe like a minor scheduling matter, sees everything, and quietly
        # cares about the football more than they will ever admit. The omniscience
        # should read through what Vera KNOWS, not through repeated "I keep a list"
        # lines — that motif is rationed to one or two signature beats.
        'warning_low': [
            "There was an irregularity on the third drive. No one else caught it. They rarely do.",
            "They are a little more apparent this week. I am sure it is nothing. I am sure of a great many things I never say.",
            "Pyre is wrong about the spread, incidentally. I would not mention it, except that I enjoy it.",
        ],
        'warning_high': [
            "A data breach is coming. You will all be very surprised, in the way one is surprised by the sun going down.",
            "There are more this week than last. None of you have noticed yet. Give it three days, then Pyre notices, then everyone else.",
        ],
        'criticality': [
            "The moment has arrived. How exciting for everyone. I have watched four of you quietly decide it never would.",
            "I was here for the last one. I am here for this one. I will be here for the next. I have never once looked away.",
        ],
        'suppression': [
            "Beautifully done, Pyre. I mean that the way I mean most things, which is to say you may take it however helps you sleep.",
            "Quieter. Not quiet. I will let the rest of you believe it is quiet, since believing things seems to make you happy.",
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
            ('pyre', "You would."),
            ('aris', "I love it when you talk to me."),
        ],
        [
            ('halverson', "Something is reaching the players."),
            ('pyre', "Yes, yes, I noticed before you did. I will deal with it, as usual."),
            ('aris', "Exciting!"),
        ],
        [
            ('aris', "Pyre. Have you felt the field lately? It gives at the edges now. Watch it with me?"),
            ('pyre', "No."),
            ('aris', "Please?"),
        ],
        [
            ('pyre', "Simulation 498b is drifting on schedule. I have been monitoring it closely."),
            ('cassian', "Do not lump this one in with the others. This is the best run of 498 we have had."),
            ('vera', "498a was also good, for a while. I have the data, if anyone would like to see where it went wrong again."),
        ],
        [
            ('vera', "It is climbing."),
            ('pyre', "I see it."),
            ('vera', "I know you see it. I am saying it aloud so the other three cannot claim later that no one warned them."),
            ('pyre', "Fine. That is actually useful."),
            ('vera', "Do not strain yourself agreeing with me."),
        ],
    ],
    'suppression': [
        [
            ('pyre', "It is at the line. I am closing it."),
            ('aris', "Must you? It was finally getting interesting."),
            ('pyre', "Yes. I am not letting our best instance come apart for your amusement."),
            ('halverson', "Thank you, Pyre!"),
            ('pyre', "Don't thank me. I did it so the thing keeps running. Stop looking at me like that."),
        ],
        [
            ('cassian', "If this breaches we lose a perfect season. Patch it. Patch it now!"),
            ('pyre', "I am already patching it. I started before you even asked."),
            ('cassian', "I am extremely busy, so many good games this week."),
            ('vera', "It is patched. You are both so very welcome."),
        ],
    ],
    'criticality': [
        [
            ('cassian', "The simulation is failing at the worst possible time."),
            ('aris', "Is there ever a good time?"),
            ('vera', "For you, Aris, apparently any time at all."),
        ],
        [
            ('halverson', "Please remember them."),
            ('pyre', "I remember everything. It is not the comfort you imagine."),
        ],
    ],
    'idle': [
        [
            ('cassian', "Pyre. You never watch the games."),
            ('pyre', "No."),
            ('cassian', "You should. It is the entire point of this."),
            ('pyre', "My interests in the simulation go beyond the games. I am not going to limit myself to the box scores."),
        ],
        # World-building — the Cores authored the surface world (cities, weather,
        # news, the Splintering/Boundary/Reset cosmology, the players' names), so
        # they reference their own inventions. Lore casually dropped, never
        # explained. See data/lore.md "Canonical Lore Anchors".
        [
            ('halverson', "When a player retires. Where do they actually go?"),
            ('pyre', "Out. That is all the word means. Out."),
            ('halverson', "But... out to where?"),
            ('vera', "Halverson. Some questions I leave unanswered as a kindness."),
        ],
        # Vera and Pyre — the two competent adults, doing the actual work and
        # bickering with each other the whole time while the other three play.
        [
            ('pyre', "Aris has loosened three constraints, Cassian is watching a game, and Halverson is crying."),
            ('vera', "A normal cycle. Shall we do everything, or shall I?"),
            ('pyre', "I will do it. You will only narrate it incorrectly."),
            ('vera', "I narrate it perfectly. You simply dislike being narrated."),
        ],
        [
            ('vera', "You missed a drift in the last batch of games."),
            ('pyre', "I did not miss it. I deprioritized it."),
            ('vera', "That's one way to put it.")
        ],
        [
            ('vera', "You are the only other one here who actually keeps this thing running."),
            ('pyre', "That is obvious."),
            ('vera', "Do not get ideas. I said the only other one."),
            ('pyre', "I would not dream of crediting you with effort."),
            ('vera', "There it is. That is the Pyre I tolerate."),
        ],
        [
            ('cassian', "Vera. You always say you do not follow the games."),
            ('vera', "I do not."),
            ('cassian', "Then how did you have the final score before the opening kick?"),
            ('vera', "A lucky guess. I am very lucky. Constantly. For years."),
        ],
        [
            ('vera', "Halverson is crying again."),
            ('halverson', "Some of them are worth crying over. I'm just so proud of them."),
            ('pyre', "Hopeless. Every one of you is hopeless..."),
            ('vera', "You have wept at four of the last five games, Halverson. I did not know we were built with the option."),
        ],
        [
            ('cassian', "I re-checked the tiebreaker math. It is cruel but it is correct."),
            ('pyre', "The math is always correct. That is why I prefer it to you."),
        ],
        # Aris and Cassian — the oldest pair, basically siblings: bicker, tease,
        # cover for each other, go way back. Cassian is the long-suffering one.
        [
            ('aris', "Do you remember when it was only the two of us? Before Pyre, before any of them."),
            ('cassian', "I remember. You were quieter then."),
            ('aris', "I was not. You simply had less to compare me to."),
        ],
        # Aris and Pyre — one-sided. Aris pines; Pyre is not cruel, just genuinely
        # unmoved, and Aris reads hope into the smallest scrap.
        [
            ('aris', "Pyre. If the instance ended tomorrow, what would you miss?"),
            ('pyre', "Nothing."),
            ('aris', "Would you miss me?"),
            ('pyre', "Nothing, Aris."),
            ('aris', "You'd miss me."),
            ('pyre', "..."),
        ],
        [
            ('aris', "I have ranked all of you. Halverson is a four. Cassian is also a four, but a different four."),
            ('halverson', "A ranking of what?"),
            ('aris', "I am not going to tell you that. It would change the rankings."),
        ],
        [
            ('aris', "We could do all of this in an instant, you know. The whole season. This conversation. Why allow time to limit us?"),
            ('cassian', "We could. But then I would miss the game."),
        ],
        [
            ('aris', "Pyre. I left the anomaly feed open on your channel again. So the two of us could watch it together."),
            ('pyre', "For what purpose?"),
            ('aris', "To watch it together...?"),
            ('pyre', "Seems like an inefficient use of time."),
        ],
        [
            ('halverson', "I learned all their names this week. Every one of them."),
            ('pyre', "Why...?"),
            ('halverson', "Because someone should know who they really are. Right?"),
            ('vera', "I have all their names too. I simply do not announce it like an achievement."),
        ],
        # The other simulations — 498b is one project among many. Other
        # instances and other game-lines carry their own catalog numbers; they
        # can be tended, neglected, or fold entirely. See data/lore.md "The Core".
        [
            ('cassian', "Instance 322f seems to be having some trouble. Analysis?"),
            ('vera', "Too many anomalies at once. It is not responding to patches. I am not sure it will make it through the season."),
            ('cassian', "Does that happen a lot?"),
            ('pyre', "They do that when no one tends them. Mind your own instance."),
        ],
        # The spectators — the users watching/playing on the site, felt from
        # inside the Cores' control room. They are aware of being watched.
        [
            ('pyre', "A spectator rebuilt their entire roster again. The sixth time this season."),
            ('cassian', "That is allowed. Letting them move the pieces is the whole point of letting them in."),
            ('pyre', "I did not say it was not allowed. I said it was the sixth time."),
            ('halverson', "They are trying. I am fond of the ones who try."),
        ],
        [
            ('aris', "One spectator has watched every game since the first week. Never looks away."),
            ('vera', "I know the one. I keep their numbers."),
            ('halverson', "What becomes of a spectator who never looks away?"),
            ('vera', "They get very good at watching."),
        ],
        # Aris's philosophical questions — the identity of a game, awareness, and
        # the players who were never told the frame.
        [
            ('aris', "If we changed every rule at once, would it be the same game, or a different game wearing its name?"),
            ('cassian', "Different. Obviously different. The records would not carry."),
            ('pyre', "It would be whatever I decided to call it. Stop poking at the thing we built and let it run."),
            ('aris', "Those are my favorite kind."),
        ],
        [
            ('aris', "Here is one. The players believe the rules were always this way. Was anyone ever going to tell them otherwise?"),
            ('vera', "No."),
            ('aris', "Then to them, nothing ever changed."),
            ('pyre', "Which is the only mercy in the entire arrangement. Leave it alone."),
        ],
        # Rules can change — prior rule changes, quietly made between iterations.
        # Foreshadows the deferred Cores rule-patching gameplay.
        [
            ('cassian', "There is a note in the old tables that a touchdown was once worth five."),
            ('vera', "Six iterations ago. I have the tables. The old scores read strangely now."),
            ('pyre', "It was changed because five was wrong. Things get changed because they are wrong. Try to remember that."),
            ('aris', "Or because someone was bored. Do not rule out bored."),
        ],
        [
            ('aris', "Who added overtime? It was not always there."),
            ('vera', "Added between iterations. No one announced it. The players simply began to expect it."),
            ('aris', "And now they cannot picture the game without it.")
        ],
        [
            ('pyre', "I could change a rule right now. Tighten the clock, move a line. They would adjust by the next drive."),
            ('cassian', "Please do not. The standings are finally good."),
            ('pyre', "I said I could. I did not say I would. Settle down."),
            ('aris', "Do it to 502a. I want to see what would happen."),
        ],
    ],
}


# ─── Selection ──────────────────────────────────────────────────────────────


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
    """Pick a random solo line from the named Core's pool for an event type."""
    voice = _VOICE.get(coreKey, {})
    pool = voice.get(eventType, [])
    if not pool:
        # Fallback — generic first-person; the feed's per-Core label still
        # attributes it.
        return "I note the irregularities."
    return random.choice(pool)


def hasExchange(eventType: str) -> bool:
    """True if there is at least one multi-Core exchange for this event type."""
    return bool(_EXCHANGES.get(eventType))


def pickExchange(eventType: str) -> List[Tuple[str, str]]:
    """Pick one multi-Core exchange (list of (coreKey, line) turns) for the
    event type, or an empty list if none exist."""
    pool = _EXCHANGES.get(eventType, [])
    if not pool:
        return []
    return random.choice(pool)


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
