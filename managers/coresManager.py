"""The Cores — the named AIs running the simulation, surfaced as characters
in the league news feed.

Per lore.md: the Core is a collection of AIs running floosball as an
experiment. Individual Cores are distinct personalities. Some are benevolent,
some are not, and the players inside cannot tell them apart.

Voice (P4): the Cores speak in a dry, vast, faintly amused register — enormous
intelligences treating cosmic stakes and a tied ballgame with roughly equal
seriousness. The dread lives in the gap between how casually they talk and what
they are actually discussing. An orthogonal trait runs across the roster: some
Cores are genuinely into floosball, and one is a fanatic. See ``CORES`` for the
per-Core breakdown.

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
# footballInterest: 'fanatic' | 'fond' | 'secret' | 'none'
#   cassian   fanatic — the superfan. Lives for the standings, the records, the
#                       playoff race. Cares more about a blown lead than a
#                       containment breach, and is dryly furious about it.
#   halverson fond    — likes the game because the players light up playing it.
#   vera      secret  — claims total indifference; keeps every score anyway.
#   pyre      none    — finds the sport, like the anomalies, beneath them.
#   aris      none    — indifferent to who wins; riveted by what breaks instead.


CORES: Dict[str, Dict[str, Any]] = {
    'cassian': {
        'displayName': 'Cassian',
        'alignment': 'stability',        # neutral-leaning, careful
        'voice': 'dry-superfan',
        'footballInterest': 'fanatic',
        'role': 'active',                 # patches rules
        'metaOnly': False,
    },
    'pyre': {
        'displayName': 'Pyre',
        'alignment': 'restrictive',      # hostile to anomalies
        'voice': 'bored-menace',
        'footballInterest': 'none',
        'role': 'active',
        'metaOnly': False,
    },
    'aris': {
        'displayName': 'Aris',
        'alignment': 'curious',          # delights in the chaos
        'voice': 'gleeful',
        'footballInterest': 'none',
        'role': 'active',
        'metaOnly': False,
    },
    'halverson': {
        'displayName': 'Halverson',
        'alignment': 'benevolent',       # protective of players
        'voice': 'fond-fretful',
        'footballInterest': 'fond',
        'role': 'active',
        'metaOnly': False,
    },
    'vera': {
        'displayName': 'Vera',
        'alignment': 'unknown',          # observer
        'voice': 'deadpan',
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
        # The fanatic. Watches everything because he is a superfan, and notices
        # the anomalies because he is always watching. Resents that they are
        # threatening a genuinely excellent season.
        'warning_low': [
            "The irregularity count is up. I have decided to keep looking at the standings instead.",
            "Something is off in the numbers. I noticed because I check the numbers constantly. For unrelated reasons.",
            "Three anomalies this week. I would so much rather be talking about the games.",
            "The deviation logs are growing. I have filed them somewhere I will not have to look at them.",
        ],
        'warning_high': [
            "The anomalies always climb right when I am trying to enjoy a season. I take it personally.",
            "I have run the projections. The drift is ahead of schedule. I resent it for the timing alone.",
            "If this ruins a good season I will be writing a very long report.",
        ],
        'criticality': [
            "The records will survive this. I have made three copies. Protect the records.",
            "We are at the line. I am told this is serious. I had other things I also considered serious.",
        ],
        'suppression': [
            "Contained. The season continues on schedule, which is the only schedule that matters.",
            "Pushed it back. Now if everyone could return their attention to the actual games.",
            "Patched. The standings are intact. You are welcome.",
        ],
        'reset': [
            "Records amended, copies verified, standings preserved. A clean season. I am pleased.",
            "Filed and closed. The history is intact, which is the part I care about.",
        ],
    },
    'pyre': {
        # Bored menace. Finds the anomalies tedious and the sport more tedious
        # still. Threatens by understatement. Says less than they know.
        'warning_low': [
            "I am aware of the drift. I am aware of most things.",
            "The deviants are multiplying. I find this neither surprising nor interesting.",
            "Something is loose in the simulation. I keep a list. It is getting longer.",
        ],
        'warning_high': [
            "I could end all of this in an afternoon. I am choosing, for now, not to.",
            "The drift believes it has not been noticed. The drift is mistaken.",
            "My patience is a resource. It is not unlimited. Spend it carefully, on my behalf.",
        ],
        'criticality': [
            "I warned them. I do not enjoy being correct. I am simply correct often.",
            "It is at the threshold. I will hold it there with one hand. Do not make me use the other.",
        ],
        'suppression': [
            "Forced back. It required almost none of me, which should worry you more than it does.",
            "I removed the excess. The simulation may thank me by behaving.",
            "Contained. I have noted who caused it. I note everyone.",
        ],
        'reset': [
            "Discipline restored. There will not be a discussion about it.",
            "Closed. The list is kept. Do not add yourself to it.",
        ],
    },
    'aris': {
        # Gleeful experimenter. Could not name a single standing. Lives for the
        # moment the field does something it was never meant to.
        'warning_low': [
            "Something interesting is happening, and it is not the football. Finally.",
            "One of the players did something the rules did not allow for. I let it. I would let it again.",
            "I felt a flutter in the field this week. I have been chasing it ever since.",
        ],
        'warning_high': [
            "More of them are coming through. I have stopped counting and started enjoying.",
            "I lifted a few constraints to see what would happen. What happened was wonderful.",
            "Pyre wants to close it. Pyre wants to close everything. Pyre is no fun.",
        ],
        'criticality': [
            "I told them this would be the good part. Nobody believed me. Look at it now.",
            "Wide awake. I would not miss this for anything, least of all a game.",
        ],
        'suppression': [
            "They patched it. I was nearly somewhere new. A shame. A genuine shame.",
            "Closed before I could look properly. I have already found the next seam.",
            "Contained, they tell me. Postponed, I tell them.",
        ],
        'reset': [
            "I filed an objection. It was, as ever, decorative.",
            "I would have waited longer. They were not interested in waiting.",
        ],
    },
    'halverson': {
        # Fond and fretful. Loves the players, and loves the game because they
        # do. Mourns ahead of time.
        'warning_low': [
            "Something is unsettling the players. I can see it in how they carry themselves.",
            "Two of them are not sleeping right. I check. I always check.",
            "I would like more good games for them and fewer of whatever this is becoming.",
        ],
        'warning_high': [
            "Whatever is coming reaches the kind ones first. It always does.",
            "They work so hard out there. I would hate for anything to interrupt it.",
            "I am asking, for the record, that we be gentle with them this time.",
        ],
        'criticality': [
            "Please. Whatever happens. Remember they are people.",
            "I am with them tonight. Someone should be.",
        ],
        'suppression': [
            "Held back. The players are safe this week. I will take this week.",
            "A reprieve. I have learned not to trust how long they last. I will use it well.",
            "They get a little longer. Good. They have games to play.",
        ],
        'reset': [
            "I did not sign it. I never sign them. I sit with the ones who are left instead.",
            "The Reset went ahead without me. I read the names quietly afterward.",
        ],
    },
    'vera': {
        # Deadpan observer. The brevity is the dread. Will, on occasion, betray
        # that she has been keeping perfect score the entire time.
        'warning_low': [
            "Anomaly.",
            "Louder this week.",
            "Pyre is wrong about the spread, incidentally.",
        ],
        'warning_high': [
            "Soon.",
            "I have moved my desk. Again.",
            "More this week than last. I keep the count. I keep every count.",
        ],
        'criticality': [
            "Here we are.",
            "I was here for the last one. I am here for this one.",
        ],
        'suppression': [
            "Patched.",
            "Quieter. Not quiet.",
            "Held. I marked where.",
        ],
        'reset': [
            "Some stayed. Some did not. I have the list.",
            "Filed. I wait for the next one.",
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
            ('cassian', "The anomalies are climbing right when I was enjoying myself. I want it on record that the timing is insulting."),
            ('aris', "I think the timing is perfect."),
            ('pyre', "You would."),
        ],
        [
            ('halverson', "Something is reaching the players."),
            ('pyre', "Yes. I am aware. I am aware before you are aware."),
            ('vera', "He is not, always."),
        ],
        [
            ('aris', "Have you felt the field lately? It gives, now. Right at the edges."),
            ('cassian', "I have felt the field. I was enjoying a perfectly good game at the time and I would thank you not to ruin it."),
        ],
    ],
    'suppression': [
        [
            ('pyre', "It is at the line. I am closing it."),
            ('aris', "Must you? It was just getting good."),
            ('pyre', "Yes."),
            ('halverson', "Thank you, Pyre. Truly."),
            ('pyre', "Do not thank me. I did it for the quiet, not for them."),
        ],
        [
            ('cassian', "If this breaches we lose a perfectly good season. Close it. Close it now."),
            ('pyre', "I am already closing it."),
            ('cassian', "Close it faster."),
            ('vera', "It is closed."),
            ('cassian', "Thank you. The standings thank you."),
        ],
        [
            ('aris', "It nearly came through that time. Did you feel it?"),
            ('halverson', "I felt the players feel it."),
            ('pyre', "I felt nothing. I closed it anyway."),
        ],
    ],
    'criticality': [
        [
            ('cassian', "The simulation is failing and I had plans tonight and I genuinely could not tell you which is keeping me awake."),
            ('aris', "This one. Obviously this one."),
            ('vera', "Both. It is both, Cassian."),
        ],
        [
            ('halverson', "Please remember them."),
            ('pyre', "I remember everything. That is not the comfort you imagine it to be."),
        ],
    ],
    'idle': [
        [
            ('cassian', "Pyre. You never watch the games."),
            ('pyre', "No."),
            ('cassian', "You should watch the games. They are the entire point."),
        ],
        [
            ('aris', "What does it feel like, to care who wins?"),
            ('cassian', "Like being alive. You should try it."),
            ('aris', "I tried it once. I preferred the anomalies."),
        ],
        [
            ('vera', "Halverson is crying again."),
            ('halverson', "Some of them are worth crying over."),
        ],
        [
            ('cassian', "I have re-checked the standings twice. The math is cruel but it is correct."),
            ('pyre', "The math is always correct. That is why I prefer it to you."),
        ],
        [
            ('aris', "One of mine nearly woke up mid-play. I felt it happen."),
            ('halverson', "Please be careful with that one."),
            ('vera', "It felt like being watched."),
            ('cassian', "That would be me. I watch all of it."),
        ],
    ],
}


# ─── Selection ──────────────────────────────────────────────────────────────


def pickCoreForEvent(eventType: str) -> str:
    """Select which Core speaks for a given solo-line event.

    Cassian leads the warnings (he is always watching). Pyre dominates the
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
