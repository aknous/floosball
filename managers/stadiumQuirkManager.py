"""StadiumQuirkManager — loads and serves home-stadium quirks.

Each team's home stadium has a unique flavor (field condition, atmosphere,
or weird quirk) tied to the team name. Quirks live in
data/templates/stadium_quirks.yaml and are looked up by team name.

Quirks have:
- Identity: tagline + description + icon key (for frontend SVG)
- Effects: small multiplicative modifiers on simulation rolls
- Flavor: pools of ambient/big-play/miss lines for the play feed

The manager is a read-only singleton. Reload at startup; quirks don't
change mid-season.
"""

import os
import random
from typing import Optional, List, Dict, Any

import yaml

from logger_config import get_logger

logger = get_logger("floosball.stadiumQuirkManager")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
QUIRKS_FILE = 'stadium_quirks.yaml'

# All effect keys that may appear in a quirk's `effects` dict. Anything missing
# defaults to 1.0 (no change). Listed here so callers can iterate or validate.
EFFECT_KEYS = (
    'passAccuracy',
    'runYardage',
    'fgAccuracy',
    'fumbleRate',
    'sackRate',
    'deepPassChance',
    'paceMod',
    'roadDiscipline',
    'homeBoost',
    'clutchVariance',
)

# Default effect dict — applied when no quirk is found for a team.
NEUTRAL_EFFECTS: Dict[str, float] = {k: 1.0 for k in EFFECT_KEYS}


class StadiumQuirkManager:
    def __init__(self) -> None:
        self._quirks: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        path = os.path.join(TEMPLATE_DIR, QUIRKS_FILE)
        if not os.path.exists(path):
            logger.warning(f"stadium quirks file not found at {path}; quirks disabled")
            return
        try:
            with open(path, 'r') as f:
                raw = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error(f"failed to load {path}: {exc}")
            return
        if not isinstance(raw, dict):
            logger.error(f"stadium_quirks.yaml must be a mapping, got {type(raw).__name__}")
            return
        for teamName, payload in raw.items():
            if not isinstance(payload, dict):
                logger.warning(f"quirk for {teamName!r} is not a mapping; skipping")
                continue
            self._quirks[teamName] = {
                'name': teamName,
                'icon': payload.get('icon') or 'default',
                'tagline': payload.get('tagline') or '',
                'description': (payload.get('description') or '').strip(),
                'effects': self._normalizeEffects(payload.get('effects') or {}),
                'flavor': self._normalizeFlavor(payload.get('flavor') or {}),
            }
        logger.info(f"loaded {len(self._quirks)} stadium quirks")

    @staticmethod
    def _normalizeEffects(raw: Dict[str, Any]) -> Dict[str, float]:
        """Coerce into the canonical effects dict with neutral defaults."""
        out = dict(NEUTRAL_EFFECTS)
        for key, value in raw.items():
            if key not in EFFECT_KEYS:
                logger.warning(f"unknown effect key {key!r} (ignored)")
                continue
            try:
                out[key] = float(value)
            except (TypeError, ValueError):
                logger.warning(f"non-numeric effect {key}={value!r} (ignored)")
        return out

    @staticmethod
    def _normalizeFlavor(raw: Dict[str, Any]) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for category, lines in raw.items():
            if not isinstance(lines, list):
                continue
            out[category] = [str(line) for line in lines if line]
        return out

    # -------- public API --------

    def hasQuirk(self, teamName: str) -> bool:
        return teamName in self._quirks

    def getQuirk(self, teamName: str) -> Optional[Dict[str, Any]]:
        return self._quirks.get(teamName)

    def getEffects(self, teamName: str) -> Dict[str, float]:
        """Return the effects dict for a team. Always returns a full dict
        keyed by EFFECT_KEYS; missing entries fall back to 1.0."""
        quirk = self._quirks.get(teamName)
        if not quirk:
            return dict(NEUTRAL_EFFECTS)
        return dict(quirk['effects'])

    def getFlavorLine(self, teamName: str, category: str, rng: Optional[random.Random] = None) -> Optional[str]:
        """Pick a random flavor line for a team + category. Returns None if
        no lines are available."""
        quirk = self._quirks.get(teamName)
        if not quirk:
            return None
        pool = quirk['flavor'].get(category) or []
        if not pool:
            return None
        return (rng or random).choice(pool)

    def serialize(self, teamName: str) -> Optional[Dict[str, Any]]:
        """Return a JSON-safe dict for API responses (omits effects, since
        the front office shouldn't need to read raw multipliers)."""
        quirk = self._quirks.get(teamName)
        if not quirk:
            return None
        return {
            'name': quirk['name'],
            'icon': quirk['icon'],
            'tagline': quirk['tagline'],
            'description': quirk['description'],
        }


# Module-level singleton
_instance: Optional[StadiumQuirkManager] = None


def getStadiumQuirkManager() -> StadiumQuirkManager:
    global _instance
    if _instance is None:
        _instance = StadiumQuirkManager()
    return _instance
