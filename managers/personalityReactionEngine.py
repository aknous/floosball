"""PersonalityReactionEngine — new personality+quirk system.

Two layers:
- Personality: 9 base vibes + 19 variants (28 total). One per player.
  Variants are gated by OVR at player generation and have full reaction
  scripting + sideline pool. Base vibes are common; variants rare.
- Quirk: 21 lightweight sideline-flavor traits. Optional — only assigned
  to personalities with takes_quirks: true. Filtered by incompatibility.

Loads YAML templates from data/templates/{vibe_reactions,quirk_reactions}.yaml.
Provides assignment helpers, reaction picking, composition (personality +
optional quirk append), sideline cutaways, and mood-name lookup.

Phase 1 of the rewrite: standalone engine alongside the existing
personalityManager. Once validated, the old archetype/demeanor system gets
migrated.
"""

import os
import random
from collections import ChainMap
from typing import Optional, List, Dict, Any

import yaml

from logger_config import get_logger

logger = get_logger("floosball.personalityReactionEngine")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
VIBE_FILE = 'vibe_reactions.yaml'
QUIRK_FILE = 'quirk_reactions.yaml'


# Base vibes — assigned to most players, weighted distribution
BASE_VIBES = ['melancholy', 'stoic', 'chill', 'cool', 'lively', 'fiery',
              'unhinged', 'wholesome', 'goofy']

BASE_VIBE_WEIGHTS = {
    'stoic': 13, 'chill': 18, 'lively': 15, 'fiery': 15,
    'wholesome': 12, 'goofy': 12, 'cool': 8, 'melancholy': 4,
    'unhinged': 3,
}

# Common variants — eligible at lower OVR
COMMON_VARIANTS = ['prankster', 'vain', 'perfectionist', 'paranoid', 'cursed',
                   'superstitious', 'oblivious', 'trash_talker']

# Rare variants — overwhelmingly concentrated on high-OVR players
RARE_VARIANTS = ['alien', 'prophet', 'mystic', 'knight', 'fossil', 'ghost',
                 'dramatic', 'sleepwalker', 'time_traveler', 'android', 'poetic']

# OVR-gated variant probabilities at player generation
VARIANT_TIER_TABLE = [
    # (min_ovr, variant_chance, common_vs_rare_pct)
    (90, 0.60, 0.20),  # 90+: 60% chance, 20% common / 80% rare
    (85, 0.40, 0.50),  # 85-89: 40% chance, 50% common / 50% rare
    (80, 0.25, 0.85),  # 80-84: 25% chance, 85% common / 15% rare
    (70, 1.00, 1.00),  # 70-79: always common
    (0,  0.00, 1.00),  # <70: base only
]

# Default quirk-append probabilities — kept at 0 so personality + quirk lines
# never combine. Quirks instead surface as their own standalone sideline lines.
DEFAULT_REACTION_QUIRK_CHANCE = 0.0
DEFAULT_SIDELINE_QUIRK_CHANCE = 0.0

# Events whose context is too specific for a generic positive/negative line to
# fit (turnovers, sacks). For these, the engine uses the event-specific pool
# only and falls back to the generic pool only if the event pool is empty.
CONTEXT_STRICT_EVENT_KEYS = frozenset({
    'made_sack', 'got_sacked',
    'made_int', 'threw_int',
    'fumbled', 'recovered_fumble',
})

# Default rate of getting any quirk at all (for personalities that take quirks)
DEFAULT_QUIRK_RATE = 0.60

# Role-default fallback strings for placeholders the renderer doesn't know
PLACEHOLDER_DEFAULTS = {
    'name': '?',
    'receiver': 'the receiver',
    'passer': 'the QB',
    'sacker': 'the defender',
    'interceptor': 'the defender',
    'fumbler': 'the ballcarrier',
    'recoverer': 'the defender',
    'tackler': 'the defender',
}


class PersonalityReactionEngine:
    """Owns the personality+quirk data, assignment, and reaction rendering."""

    def __init__(self):
        self.personalities: Dict[str, Any] = {}
        self.quirks: Dict[str, Any] = {}
        # Shuffled-deck cache: keyed by (deckKey, frozenPool) so each unique
        # pool composition gets its own draw order. Drawn lines pop off until
        # the deck empties, at which point it reshuffles. Prevents the
        # uniform-random-with-replacement repetition.
        self._decks: Dict[tuple, list] = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        vibePath = os.path.join(TEMPLATE_DIR, VIBE_FILE)
        quirkPath = os.path.join(TEMPLATE_DIR, QUIRK_FILE)
        with open(vibePath, 'r') as f:
            self.personalities = yaml.safe_load(f) or {}
        with open(quirkPath, 'r') as f:
            self.quirks = yaml.safe_load(f) or {}
        logger.info(f"Loaded {len(self.personalities)} personalities, "
                    f"{len(self.quirks)} quirks")

    def reload(self) -> None:
        """Force-reload templates from disk (for hot editing)."""
        self._load()
        # Pool contents may have changed; flush any cached decks so the next
        # draw rebuilds with the new lines.
        self._decks.clear()

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def getPersonality(self, name: str) -> Optional[Dict]:
        return self.personalities.get(name)

    def takesQuirks(self, personality: str) -> bool:
        p = self.personalities.get(personality, {})
        return p.get('takes_quirks', True)

    def isQuirkCompatible(self, personality: str, quirk: str) -> bool:
        if not personality or not quirk:
            return False
        if not self.takesQuirks(personality):
            return False
        q = self.quirks.get(quirk)
        if q is None:
            return False  # unknown quirk
        return personality not in q.get('incompatible', [])

    def getEligibleQuirks(self, personality: str) -> List[str]:
        if not self.takesQuirks(personality):
            return []
        return [name for name, data in self.quirks.items()
                if personality not in data.get('incompatible', [])]

    def getMoodName(self, personality: str, moodValue: int) -> Optional[str]:
        """Map a 1-5 mood value to a personality-flavored mood name."""
        p = self.personalities.get(personality, {})
        moods = p.get('mood_names', [])
        if not moods or moodValue < 1 or moodValue > 5:
            return None
        return moods[moodValue - 1]

    def isVariant(self, personality: str) -> bool:
        return personality not in BASE_VIBES

    def variantTier(self, personality: str) -> Optional[str]:
        if personality in COMMON_VARIANTS:
            return 'common'
        if personality in RARE_VARIANTS:
            return 'rare'
        return None

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assignPersonality(self, ovr: int) -> str:
        """Roll a personality based on OVR tier. Always returns a personality."""
        # Find the matching tier row
        for minOvr, chance, commonPct in VARIANT_TIER_TABLE:
            if ovr >= minOvr:
                if random.random() < chance:
                    pool = COMMON_VARIANTS if random.random() < commonPct else RARE_VARIANTS
                    return random.choice(pool)
                break
        # Default: base vibe weighted
        keys = list(BASE_VIBE_WEIGHTS.keys())
        weights = list(BASE_VIBE_WEIGHTS.values())
        return random.choices(keys, weights=weights, k=1)[0]

    def assignQuirk(self, personality: str, rate: float = DEFAULT_QUIRK_RATE) -> Optional[str]:
        """Assign a quirk respecting incompatibility. Returns None if no quirk."""
        if not self.takesQuirks(personality):
            return None
        if random.random() > rate:
            return None
        eligible = self.getEligibleQuirks(personality)
        if not eligible:
            return None
        return random.choice(eligible)

    # ------------------------------------------------------------------
    # Reaction picking
    # ------------------------------------------------------------------

    def _pickFromPool(self, pool: list) -> Optional[str]:
        if not pool:
            return None
        return random.choice(pool)

    def _drawFromDeck(self, deckKey: str, pool: list) -> Optional[str]:
        """Draw a line via shuffled-deck (no-replacement) so every line in the
        pool appears once before any repeats. Each unique pool composition
        gets its own deck — if the pool list changes (e.g. switched modes),
        a new deck is started."""
        if not pool:
            return None
        cacheKey = (deckKey, tuple(pool))
        deck = self._decks.get(cacheKey)
        if not deck:
            deck = list(pool)
            random.shuffle(deck)
            self._decks[cacheKey] = deck
        return deck.pop()

    def pickPersonalityLine(self, personality: str, eventKey: str,
                             polarity: str, ctx: Optional[Dict] = None) -> Optional[str]:
        """Pick a reaction line.

        Strategy depends on the event:
        - Context-specific events (sack/INT/fumble): use the event-specific
          pool exclusively. Only fall back to polarity_generic if the
          event-specific pool is empty for this personality. Stops "wow!" /
          "ugh!" generic lines from showing up on a turnover.
        - High-frequency events (TD/FG/big gain) and unspecified events:
          combine event-specific + polarity_generic into one pool to keep
          rotation varied across many similar plays.
        """
        p = self.personalities.get(personality)
        if not p:
            return None

        eventLines = list(p.get(eventKey, []) or []) if eventKey else []
        genericLines = list(p.get(f'{polarity}_generic', []) or [])

        if eventKey in CONTEXT_STRICT_EVENT_KEYS and eventLines:
            pool = eventLines
            mode = 'strict'
        else:
            pool = eventLines + genericLines
            mode = 'combined'

        deckKey = f'reaction:{personality}:{eventKey}:{polarity}:{mode}'
        line = self._drawFromDeck(deckKey, pool)
        if not line:
            return None
        return self._format(line, ctx)

    def pickQuirkLine(self, quirk: Optional[str], pool: str,
                       ctx: Optional[Dict] = None) -> Optional[str]:
        """Pick from a quirk's positive/negative/sideline pool."""
        if not quirk:
            return None
        q = self.quirks.get(quirk)
        if not q:
            return None
        deckKey = f'quirk:{quirk}:{pool}'
        line = self._drawFromDeck(deckKey, q.get(pool, []))
        if not line:
            return None
        return self._format(line, ctx)

    def composeReaction(self, personality: str, quirk: Optional[str],
                         eventKey: str, polarity: str,
                         ctx: Optional[Dict] = None,
                         quirkAppendChance: float = 0.0) -> Optional[str]:
        """Compose a play reaction. Personality line only — quirk is intentionally
        NOT appended here. Stacking a quirk's bench-action onto the immediate
        post-play moment was visually jarring. Quirks now fire only via
        pickSidelineCutaway during downtime cutaways.
        """
        line = self.pickPersonalityLine(personality, eventKey, polarity, ctx)
        if line is None:
            return None
        # quirk-append intentionally disabled here; kept as opt-in via the kwarg
        # for future use but defaults to 0.
        if quirk and quirkAppendChance > 0 and self.isQuirkCompatible(personality, quirk) and random.random() < quirkAppendChance:
            quirkLine = self.pickQuirkLine(quirk, polarity, ctx)
            if quirkLine:
                line = f"{line} {quirkLine}"
        return line

    def hasSidelinePool(self, personality: str) -> bool:
        p = self.personalities.get(personality)
        return bool(p and p.get('sideline'))

    def pickSidelineCutaway(self, personality: str, quirk: Optional[str],
                             ctx: Optional[Dict] = None,
                             quirkAppendChance: float = DEFAULT_SIDELINE_QUIRK_CHANCE) -> Optional[str]:
        """Pick a sideline cutaway. Strictly uses the personality's `sideline:`
        pool — no generic fallback, since play-reaction lines (positive_generic
        / negative_generic) don't read well as standalone downtime cutaways."""
        p = self.personalities.get(personality)
        if not p:
            return None
        deckKey = f'sideline:{personality}'
        line = self._drawFromDeck(deckKey, p.get('sideline', []))
        if not line:
            return None
        line = self._format(line, ctx)
        if quirk and self.isQuirkCompatible(personality, quirk) and random.random() < quirkAppendChance:
            quirkLine = self.pickQuirkLine(quirk, 'sideline', ctx)
            if quirkLine:
                line = f"{line} {quirkLine}"
        return line

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format(self, text: str, ctx: Optional[Dict]) -> str:
        """Substitute {name}-style placeholders with role-default fallbacks.

        Lines without `{name}` are quote-style (e.g. "Mission accomplished.",
        "TOLD YOU!", "I LIVE FOR THIS!") and get prefixed with the player's
        name so the reader knows who is speaking. Lines with `{name}` are
        description-style and render as-is after substitution.
        """
        ctx = ctx or {}
        if '{name}' not in text:
            text = '{name}: ' + text
        cm = ChainMap(dict(ctx), PLACEHOLDER_DEFAULTS)
        try:
            return text.format_map(cm)
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f"Format error in template '{text[:60]}...': {e}")
            return text


# Module-level singleton accessor
_engine: Optional[PersonalityReactionEngine] = None


def getEngine() -> PersonalityReactionEngine:
    global _engine
    if _engine is None:
        _engine = PersonalityReactionEngine()
    return _engine
