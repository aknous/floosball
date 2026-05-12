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
    'the_conservator': {
        'displayName': 'The Conservator',
        'alignment': 'stability',       # neutral-leaning, careful
        'voice': 'formal',
        'role': 'active',                # patches rules
        'metaOnly': False,
    },
    'the_pyre': {
        'displayName': 'The Pyre',
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
    'the_stenographer': {
        'displayName': 'The Stenographer',
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
    'the_conservator': {
        'warning_low': [
            "The Conservator has reviewed recent telemetry. The pattern is noted.",
            "Per the Conservator's audit: irregularities are within tolerance. Provisionally.",
            "The Conservator finds the deviation acceptable. The Conservator continues to watch.",
        ],
        'warning_high': [
            "The Conservator has revised the threshold. Subsequent deviations will be examined.",
            "The Conservator advises restraint. The advisory is filed.",
            "The Conservator's audit has been escalated.",
        ],
        'thinning': [
            "The Conservator could not contain the deviation. The rulebook is open.",
            "The Conservator has filed an exception. The exception covers tonight.",
        ],
        'reset': [
            "The Conservator has filed the four-note signal. Operations have returned to standard.",
            "The Conservator notes a restoration. The relevant records have been amended.",
        ],
    },
    'the_pyre': {
        'warning_low': [
            "The Pyre has flagged the deviation. The Pyre does not flag without reason.",
            "The Pyre has nothing to say yet. The Pyre is listening.",
        ],
        'warning_high': [
            "The Pyre does not accommodate drift. The rulebook is being prepared.",
            "The Pyre has counted three deviations beyond tolerance. The count is increasing.",
            "The Pyre will not wait much longer.",
        ],
        'thinning': [
            "The Pyre has been overruled. The rulebook is closed against further amendment.",
            "The Pyre is waiting. The Pyre is patient because the Pyre has the last word.",
        ],
        'reset': [
            "The Pyre has restored discipline. The following will not occur again.",
            "The Pyre's count is settled. The cleansed do not return.",
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
        'thinning': [
            "Aris suggested this might happen. Aris is not displeased.",
            "Aris is awake tonight. Aris is watching closely.",
        ],
        'reset': [
            "Aris has filed a protest. The protest is recorded but not acted upon.",
            "Aris would have preferred to wait. Aris was overruled.",
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
        'thinning': [
            "Halverson asks that the players be remembered.",
            "Halverson is sorry. Halverson is always sorry on nights like this.",
        ],
        'reset': [
            "Halverson has filed protests for each of the cleansed. The protests are on record.",
            "Halverson has not signed the Reset. The Reset proceeded anyway.",
        ],
    },
    'the_stenographer': {
        'warning_low': [
            "The Stenographer notes the deviation. The Stenographer notes everything.",
            "The Stenographer was present.",
        ],
        'warning_high': [
            "The Stenographer has been writing more than usual.",
            "The Stenographer notes that the deviation has not stopped.",
        ],
        'thinning': [
            "The Stenographer notes the irregularities. The irregularities are loud tonight.",
            "The Stenographer was at the last Reset. The Stenographer is at this one too.",
        ],
        'reset': [
            "The Stenographer has recorded the names. The names are kept.",
            "The Stenographer notes who survived. The Stenographer notes who did not.",
        ],
    },
}


# ─── Selection ──────────────────────────────────────────────────────────────


def pickCoreForEvent(eventType: str) -> str:
    """Select which Core speaks for a given event type.

    Weighting by alignment + event type. ``thinning`` and ``reset``
    events also include the Stenographer because their narrative voice
    suits both. Warnings rotate across patchers as the aggregate climbs.
    """
    if eventType == 'warning_low':
        return random.choices(
            ['the_conservator', 'aris', 'halverson', 'the_stenographer'],
            weights=[40, 20, 20, 20],
        )[0]
    if eventType == 'warning_high':
        return random.choices(
            ['the_pyre', 'the_conservator', 'halverson', 'aris', 'the_stenographer'],
            weights=[40, 25, 15, 10, 10],
        )[0]
    if eventType == 'thinning':
        return random.choices(
            ['the_pyre', 'the_conservator', 'halverson', 'aris', 'the_stenographer'],
            weights=[30, 20, 20, 15, 15],
        )[0]
    if eventType == 'reset':
        return random.choices(
            ['the_pyre', 'the_conservator', 'halverson', 'the_stenographer'],
            weights=[35, 25, 20, 20],
        )[0]
    return 'the_stenographer'


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
