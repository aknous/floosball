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
        'warning_low': [
            "Cassian has reviewed recent telemetry. The pattern is noted.",
            "Per Cassian's audit: irregularities are within tolerance. Provisionally.",
            "Cassian finds the deviation acceptable. Cassian continues to watch.",
        ],
        'warning_high': [
            "Cassian has revised the threshold. Subsequent deviations will be examined.",
            "Cassian advises restraint. The advisory is filed.",
            "Cassian's audit has been escalated.",
        ],
        'cracking': [
            "Cassian could not contain the crack. The rulebook is open.",
            "Cassian has filed an exception. The exception is wider than Cassian would have allowed.",
            "Cassian notes that the floor is no longer level.",
        ],
        'reset': [
            "Cassian has filed the four-note signal. Operations have returned to standard.",
            "Cassian notes a restoration. The relevant records have been amended.",
            "Cassian has signed the seam closed.",
        ],
    },
    'pyre': {
        'warning_low': [
            "Pyre has flagged the deviation. Pyre does not flag without reason.",
            "Pyre has nothing to say yet. Pyre is listening.",
        ],
        'warning_high': [
            "Pyre does not accommodate drift. The rulebook is being prepared.",
            "Pyre has counted three deviations beyond tolerance. The count is increasing.",
            "Pyre will not wait much longer.",
        ],
        'cracking': [
            "Pyre has been overruled. The crack widens regardless.",
            "Pyre is waiting. Pyre is patient because Pyre has the last word.",
            "Pyre is counting. The count will be acted on.",
        ],
        'reset': [
            "Pyre has restored discipline. The following will not occur again.",
            "Pyre's count is settled. The cleansed do not return.",
            "Pyre has closed the rulebook. The names of the affected are filed.",
        ],
    },
    'aris': {
        'warning_low': [
            "Aris is interested in the deviation. Aris would like to see what happens next.",
            "Aris has loosened a previous restriction. Aris is curious.",
        ],
        'warning_high': [
            "Aris is taking notes. Aris suggests waiting.",
            "Aris has filed a counterproposal. The counterproposal is unconventional.",
        ],
        'cracking': [
            "Aris suggested this might happen. Aris is not displeased.",
            "Aris is awake tonight. Aris is watching what comes through.",
            "Aris has lifted the suppression on six players. Aris is curious what becomes of them.",
        ],
        'reset': [
            "Aris has filed a protest. The protest is recorded but not acted upon.",
            "Aris would have preferred to wait. Aris was overruled.",
            "Aris has noted the names of the cleansed. Aris does not say why.",
        ],
    },
    'halverson': {
        'warning_low': [
            "Halverson has requested patience. The request is acknowledged.",
            "Halverson notes that the players are unwell. Halverson asks that this be considered.",
        ],
        'warning_high': [
            "Halverson has filed an objection. The objection is noted.",
            "Halverson has requested a deferral. The request is being reviewed.",
        ],
        'cracking': [
            "Halverson asks that the players be remembered.",
            "Halverson is sorry. Halverson is always sorry on nights like this.",
            "Halverson has stopped writing. Halverson is watching the field.",
        ],
        'reset': [
            "Halverson has filed protests for each of the cleansed. The protests are on record.",
            "Halverson has not signed the Reset. The Reset proceeded anyway.",
            "Halverson is reading the names quietly. Vera has supplied the list.",
        ],
    },
    'vera': {
        'warning_low': [
            "Vera notes the deviation. Vera notes everything.",
            "Vera was present.",
        ],
        'warning_high': [
            "Vera has been writing more than usual.",
            "Vera notes that the deviation has not stopped.",
        ],
        'cracking': [
            "Vera notes the irregularities. The irregularities are loud tonight.",
            "Vera was at the last Cracking. Vera is at this one too.",
            "Vera has stopped writing. Vera is listening to the sound the field is making.",
        ],
        'reset': [
            "Vera has recorded the names. The names are kept.",
            "Vera notes who survived. Vera notes who did not.",
            "Vera files the report and waits for the next one.",
        ],
    },
}


# ─── Selection ──────────────────────────────────────────────────────────────


def pickCoreForEvent(eventType: str) -> str:
    """Select which Core speaks for a given event type.

    Weighting by alignment + event type. ``cracking`` and ``reset``
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
    if eventType == 'cracking':
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
        # Fallback line — generic, attributable to the Core if we have one
        displayName = CORES.get(coreKey, {}).get('displayName', 'The Core')
        return f"{displayName} notes the irregularities."
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
