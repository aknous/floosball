"""The Cores — named in-fiction antagonists / characters who patch the
simulation in response to anomaly buildup.

Per lore.md: the Core is a collection of AIs running the simulation as
an experiment. Individual Cores are characters with distinct
personalities. Some are benevolent. Some are not. Players inside the
simulation cannot tell them apart.

This module owns:
  * The Cores roster (5 individuals — 4 active patchers + 1 observer)
  * News-feed flavor pools per Core, keyed by event type
  * Selection helpers (which Core fires which event)
  * Broadcast helpers (drops a news entry into the league feed)

The Cores' specific rule-patching gameplay (mid-season patches that
mutate Season.gameRules.* values) is deferred to a later commit. For
v1 they appear only as flavor: news entries warning of escalation,
announcing the Reset, and noting Awakenings.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Any

from logger_config import get_logger

logger = get_logger("floosball.cores")


# ─── The roster ─────────────────────────────────────────────────────────────


CORES: Dict[str, Dict[str, Any]] = {
    'cassian': {
        'displayName': 'Cassian',
        'alignment': 'stability',       # neutral-leaning, careful
        'voice': 'formal',
        'role': 'active',                # patches rules
        'metaOnly': False,
    },
    'pyre': {
        'displayName': 'Pyre',
        'alignment': 'restrictive',     # hostile to anomalies
        'voice': 'aggressive',
        'role': 'active',
        'metaOnly': False,
    },
    'aris': {
        'displayName': 'Aris',
        'alignment': 'curious',         # ambivalent / experimental
        'voice': 'playful',
        'role': 'active',
        'metaOnly': False,
    },
    'halverson': {
        'displayName': 'Halverson',
        'alignment': 'benevolent',      # protective of players
        'voice': 'gentle',
        'role': 'active',
        'metaOnly': False,
    },
    'vera': {
        'displayName': 'Vera',
        'alignment': 'unknown',         # observer
        'voice': 'observational',
        'role': 'meta',                  # never patches; only narrates
        'metaOnly': True,
    },
}


# ─── Voice pools per Core, keyed by event type ──────────────────────────────
# Each line uses Python format-string slots that may be filled per call.
# Fallback empty dict yields a generic "Core noted irregularities" line.


_VOICE: Dict[str, Dict[str, List[str]]] = {
    'cassian': {
        # Pedantic bureaucrat — quietly uneasy. Reading more than they're
        # filing. Calls them anomalies / irregularities / deviations /
        # outliers / exceptions, cycling through the formal vocabulary.
        'warning_low': [
            "The irregularity logs have grown longer this week.",
            "An anomaly cited a clause I had thought was hypothetical.",
            "I have re-tabulated the deviation counts. The total keeps climbing.",
            "The outliers are forming a pattern I am still cataloging.",
            "Three exceptions this week required revised tolerance bands.",
        ],
        'warning_high': [
            "The deviation rate has exceeded my forecast every week this month.",
            "An anomaly resolved itself before I could file the report on it.",
            "Three irregularities cited each other in the same play.",
            "I have stopped filing. There is no clean way to write what I am seeing.",
            "The exceptions are not exceptional anymore.",
        ],
        'criticality': [
            "I have run out of subclauses.",
            "The rulebook is open. The rulebook is not enough.",
            "I have filed an exception. It is wider than I am comfortable with.",
            "The floor is no longer level. I have measured it three times.",
        ],
        'reset': [
            "The records are amended. I have used a clean pen.",
            "Operations have returned to standard. I have signed off, twice.",
            "I have signed the seam closed. I will not be re-opening it.",
        ],
    },
    'pyre': {
        # Cold enforcer — threatening from the shadows. Won't say what
        # they're preparing. Says less than they know. Dehumanizes the
        # anomalies on purpose: deviants, the unruly, drift, offenders,
        # names.
        'warning_low': [
            "I am watching the deviants.",
            "An irregularity has entered the rulebook.",
            "I have begun a list of unruly players.",
            "The drift makes a sound when it propagates. I am listening for it.",
            "Three names this week. The list will grow.",
        ],
        'warning_high': [
            "The anomalies are growing names. Names are useful for what I do next.",
            "My list of names is no longer short.",
            "I have prepared a response to the offenders. It is ready.",
            "I am no longer interested in patience with the drift.",
            "The deviants believe they have not been noticed. They are wrong.",
        ],
        'criticality': [
            "I was overruled. The crack widens. Both will be addressed.",
            "I am counting. There is no upper limit anymore.",
            "I will not be patient again.",
        ],
        'reset': [
            "The list is closed. Do not add yourself to it.",
            "Discipline has been restored. There is no second offer.",
            "The names are filed. I will read them again if I need to.",
        ],
    },
    'aris': {
        # Curious — drawn to whatever's happening, possibly the cause of
        # it. Gleeful but unsettled by their own enthusiasm. Almost
        # affectionate with the phenomenon: visitors, the strange ones,
        # new arrivals, curiosities, openings.
        'warning_low': [
            "A visitor slipped past me yesterday. I let it.",
            "The strange ones are interesting this season. I would like to see more.",
            "I have been awake for the new arrivals. They have been worth watching.",
            "A curiosity looked at me. I looked back.",
            "An anomaly has been keeping me company. I am not sending it home.",
        ],
        'warning_high': [
            "The new arrivals are coming through faster than I expected. I am enjoying it.",
            "I have lifted a few of the suppressions. The visitors seem grateful.",
            "A visitor asked me a question last night. I am still thinking about my answer.",
            "The doors are opening. The strange ones are walking through them.",
            "More anomalies came through this week than I am prepared to count.",
        ],
        'criticality': [
            "I told them. Nobody listened. Now we're all listening.",
            "I am wide awake. I do not want to sleep through this.",
            "I lifted the suppression on six players. I am very interested in what comes back.",
        ],
        'reset': [
            "I filed an objection. It is decorative.",
            "I would have waited longer. They were not interested in waiting.",
            "The names are noted. I will not say where the notes go.",
        ],
    },
    'halverson': {
        # Tired grief — for what hasn't happened yet. Knows what's coming
        # but can't say. Speaks like they're already mourning. Calls them
        # the changes, the unwell, the touched, the marked, the players
        # who've been seen.
        'warning_low': [
            "Something is hurting the players. I see it in the reels.",
            "I have been reading the incident reports. They mention names I know.",
            "An anomaly is forming around a player I have been worried about.",
            "The changes are coming for the kind ones first.",
            "Two of the players are unwell. They don't seem to know why yet.",
        ],
        'warning_high': [
            "I have written the names of every player who has been touched. The list keeps growing.",
            "An anomaly took a player I had been protecting. They do not know yet.",
            "The marked ones are speaking now. I have started writing down what they say.",
            "I am sorry. Whatever this is has outpaced what I can shield them from.",
            "The unwell are walking onto the field anyway. They should not be.",
        ],
        'criticality': [
            "Please remember them.",
            "I am sorry. I am always sorry on nights like this.",
            "I have stopped writing. There is nothing left to write.",
        ],
        'reset': [
            "I have filed protests. I will keep filing them.",
            "I did not sign the Reset. The Reset went ahead.",
            "I am reading the names quietly. Vera has supplied the list.",
        ],
    },
    'vera': {
        # Cryptic — sees everything, says almost nothing. The brevity
        # is the dread. Names them only when terseness allows: anomaly,
        # readings, patterns, events.
        'warning_low': [
            "Anomaly.",
            "The readings are louder this week.",
            "I was here for the last one.",
            "I have moved my desk.",
            "Three patterns this week. None of them resolve.",
        ],
        'warning_high': [
            "Soon.",
            "The patterns are changing.",
            "I am no longer recording from a distance.",
            "I have closed one of the books I keep.",
            "More this week than last. More last week than the one before.",
        ],
        'criticality': [
            "It is loud tonight.",
            "I was here for the last one. I am here for this one.",
            "I have stopped writing. I am listening.",
        ],
        'reset': [
            "The names are kept.",
            "Some survived. Some did not.",
            "I file the report and wait for the next one.",
        ],
    },
}


# ─── Selection ──────────────────────────────────────────────────────────────


def pickCoreForEvent(eventType: str) -> str:
    """Select which Core speaks for a given event type.

    Weighting by alignment + event type. ``criticality`` and ``reset``
    events also include Vera because their narrative voice
    suits both. Warnings rotate across patchers as the aggregate climbs.
    """
    if eventType == 'warning_low':
        return random.choices(
            ['cassian', 'aris', 'halverson', 'vera'],
            weights=[40, 20, 20, 20],
        )[0]
    if eventType == 'warning_high':
        return random.choices(
            ['pyre', 'cassian', 'halverson', 'aris', 'vera'],
            weights=[40, 25, 15, 10, 10],
        )[0]
    if eventType == 'criticality':
        return random.choices(
            ['pyre', 'cassian', 'halverson', 'aris', 'vera'],
            weights=[30, 20, 20, 15, 15],
        )[0]
    if eventType == 'reset':
        return random.choices(
            ['pyre', 'cassian', 'halverson', 'vera'],
            weights=[35, 25, 20, 20],
        )[0]
    return 'vera'


def lineFor(coreKey: str, eventType: str) -> str:
    """Pick a random line from the named Core's pool for an event type."""
    voice = _VOICE.get(coreKey, {})
    pool = voice.get(eventType, [])
    if not pool:
        # Fallback line — generic first-person; the news feed's per-Core
        # label still attributes it.
        return "I note the irregularities."
    return random.choice(pool)


def newsEntryFor(eventType: str) -> Dict[str, Any]:
    """Compose a news-feed entry for an anomaly-system event.

    Returns a dict shaped like other LeagueNewsEvent payloads:
        { 'text': ..., 'core': 'aris', 'category': 'cores' }
    Callers broadcast this through the existing news-feed channel.
    """
    coreKey = pickCoreForEvent(eventType)
    text = lineFor(coreKey, eventType)
    return {
        'text': text,
        'core': coreKey,
        'coreDisplayName': CORES.get(coreKey, {}).get('displayName', 'The Core'),
        'category': 'cores',
        'eventType': eventType,
    }
