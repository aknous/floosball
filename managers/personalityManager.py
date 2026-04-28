"""PersonalityManager — assignment, mood, and reaction wrapper.

Thin wrapper around PersonalityReactionEngine. Provides:
- Player-aware personality/quirk assignment (OVR-tiered)
- Mood updates from confidence + determination
- Reaction composition for game events (event-key mapping)
- Sideline cutaway picks for downtime moments
- Mood-name lookup for UI display

The engine owns the templates and core logic; this manager handles the
integration with player attributes and game-event keys.
"""

from typing import List, Optional, Dict, Any

from logger_config import get_logger

from managers.personalityReactionEngine import PersonalityReactionEngine

logger = get_logger("floosball.personalityManager")


# Maps in-game event keys to (yaml_event_key, polarity). The engine pulls
# from event_key + polarity_generic both, so reactions feel context-flavored
# but don't repeat across many similar plays in a season.
# Used when game.py fires a personality reaction so the manager knows
# which YAML pool to draw from.
EVENT_MAP: Dict[str, tuple] = {
    'td_scored':              ('scored_td', 'positive'),
    'td_thrown':              ('threw_td', 'positive'),
    'fg_made':                ('made_fg', 'positive'),
    'fg_missed':              ('missed_fg', 'negative'),
    'sack_taken':             ('got_sacked', 'negative'),
    'sack_made':              ('made_sack', 'positive'),
    'int_thrown':             ('threw_int', 'negative'),
    'int_made':               ('made_int', 'positive'),
    'fumble_lost':            ('fumbled', 'negative'),
    'fumble_recovered':       ('recovered_fumble', 'positive'),
    # Generic events fall back to positive_generic / negative_generic
    'big_gain':               ('', 'positive'),
    'third_down_conversion':  ('', 'positive'),
    'turnover_on_downs':      ('', 'negative'),
    'safety_taken':           ('', 'negative'),
    'safety_made':            ('', 'positive'),
    'choke_play':             ('', 'negative'),
    'clutch_play':            ('', 'positive'),
}


class PersonalityManager:
    """Owns player personality assignment, mood updates, and reaction firing."""

    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        self.engine = PersonalityReactionEngine()
        logger.info("PersonalityManager initialized")

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assignPersonality(self, player, forceRefresh: bool = False) -> None:
        """Assign personality + quirk + mood + flavor to a player.

        Idempotent unless forceRefresh=True. OVR-tiered: low-rated players
        get base vibes only, high-rated players have a chance at variants.
        Flavor (hometown, favorite, motto) is rolled once and never changes.
        """
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return

        if not forceRefresh and getattr(attrs, 'personality', None):
            # Personality already set — still backfill flavor if missing,
            # since flavor was added later and existing players need it.
            self.assignFlavor(player, forceRefresh=False)
            return

        ovr = getattr(attrs, 'overallRating', 0) or 70
        attrs.personality = self.engine.assignPersonality(ovr)
        attrs.quirk = self.engine.assignQuirk(attrs.personality)
        if getattr(attrs, 'mood', None) is None:
            attrs.mood = 3
        # Roll flavor alongside personality. Idempotent — only fills if NULL.
        self.assignFlavor(player, forceRefresh=forceRefresh)

    def assignFlavor(self, player, forceRefresh: bool = False) -> None:
        """Assign hometown, favorite, and motto. Idempotent: skips if any
        flavor field is already set unless forceRefresh=True."""
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return
        # Skip if any flavor field is already set (treat as a unit)
        if not forceRefresh and getattr(attrs, 'hometown', None):
            return
        personality = getattr(attrs, 'personality', None) or 'chill'
        flavor = self.engine.assignFlavor(personality)
        attrs.hometown = flavor.get('hometown')
        attrs.favorite_category = flavor.get('favorite_category')
        attrs.favorite_item = flavor.get('favorite_item')
        attrs.motto = flavor.get('motto')

    def assignToPlayerPool(self, players: List, forceRefresh: bool = False) -> dict:
        """Bulk assignment with summary stats."""
        from collections import Counter
        personalityCounts: Counter = Counter()
        quirkCounts: Counter = Counter()
        for player in players:
            self.assignPersonality(player, forceRefresh=forceRefresh)
            attrs = getattr(player, 'attributes', None)
            if attrs is None:
                continue
            if attrs.personality:
                personalityCounts[attrs.personality] += 1
            if attrs.quirk:
                quirkCounts[attrs.quirk] += 1
        return {
            'total': len(players),
            'personalities': dict(personalityCounts),
            'quirks': dict(quirkCounts),
        }

    # ------------------------------------------------------------------
    # Mood
    # ------------------------------------------------------------------

    def updateMood(self, player) -> Optional[int]:
        """Recompute mood (1-5) from confidence + determination modifiers."""
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return None
        combined = (getattr(attrs, 'confidenceModifier', 0) +
                    getattr(attrs, 'determinationModifier', 0))
        if combined >= 6:
            mood = 5
        elif combined >= 3:
            mood = 4
        elif combined >= -2:
            mood = 3
        elif combined >= -5:
            mood = 2
        else:
            mood = 1
        attrs.mood = mood
        return mood

    def getMoodName(self, player) -> Optional[str]:
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return None
        personality = getattr(attrs, 'personality', None)
        mood = getattr(attrs, 'mood', 3) or 3
        return self.engine.getMoodName(personality, mood) if personality else None

    # ------------------------------------------------------------------
    # Reaction firing
    # ------------------------------------------------------------------

    def composeReaction(self, player, gameEventKey: str,
                         ctx: Optional[Dict] = None) -> Optional[Dict]:
        """Compose a play reaction for a player.

        Returns a dict shaped for the WebSocket game feed, or None if no
        line fires (missing personality, missing template, etc).
        """
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return None
        personality = getattr(attrs, 'personality', None)
        if not personality:
            return None
        quirk = getattr(attrs, 'quirk', None)

        eventKey, polarity = EVENT_MAP.get(gameEventKey, ('', 'positive'))

        renderCtx = dict(ctx or {})
        renderCtx.setdefault('name', getattr(player, 'name', ''))

        text = self.engine.composeReaction(personality, quirk, eventKey, polarity, renderCtx)
        if not text:
            return None

        return {
            'text': text,
            'playerId': getattr(player, 'id', None),
            'playerName': getattr(player, 'name', ''),
            'personality': personality,
            'quirk': quirk,
            'event': gameEventKey,
        }

    def composePolarityReaction(self, player, polarity: str,
                                ctx: Optional[Dict] = None) -> Optional[Dict]:
        """Compose a reaction tied to a polarity rather than a specific game
        event — used for postgame win/loss reactions where the player just
        won/lost the game and we want a generic positive/negative line."""
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return None
        personality = getattr(attrs, 'personality', None)
        if not personality:
            return None
        quirk = getattr(attrs, 'quirk', None)

        renderCtx = dict(ctx or {})
        renderCtx.setdefault('name', getattr(player, 'name', ''))

        text = self.engine.composeReaction(personality, quirk, '', polarity, renderCtx)
        if not text:
            return None

        team = getattr(player, 'team', None)
        return {
            'text': text,
            'playerId': getattr(player, 'id', None),
            'playerName': getattr(player, 'name', ''),
            'teamId': getattr(team, 'id', None) if team else None,
            'teamAbbr': getattr(team, 'abbr', None) if team else None,
            'personality': personality,
            'quirk': quirk,
            'event': 'postgame',
        }

    def pickSidelineCutaway(self, player, ctx: Optional[Dict] = None) -> Optional[Dict]:
        """Pick a downtime sideline cutaway for a player."""
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return None
        personality = getattr(attrs, 'personality', None)
        if not personality:
            return None
        quirk = getattr(attrs, 'quirk', None)

        renderCtx = dict(ctx or {})
        renderCtx.setdefault('name', getattr(player, 'name', ''))

        text = self.engine.pickSidelineCutaway(personality, quirk, renderCtx)
        if not text:
            return None

        team = getattr(player, 'team', None)
        teamId = getattr(team, 'id', None) if team else None
        teamAbbr = getattr(team, 'abbr', None) if team else None

        return {
            'text': text,
            'playerId': getattr(player, 'id', None),
            'playerName': getattr(player, 'name', ''),
            'teamId': teamId,
            'teamAbbr': teamAbbr,
            'personality': personality,
            'quirk': quirk,
            'event': 'sideline',
        }

    # ------------------------------------------------------------------
    # Hot-reload (development helper)
    # ------------------------------------------------------------------

    def reloadTemplates(self) -> None:
        self.engine.reload()
