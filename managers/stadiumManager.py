"""StadiumManager — venues, and the weather native to each of them.

Every team's home stadium is a fantastical SETTING (a cavern, open water, a moving
train, a permanent full moon), and its weather is whatever is realistic for that
setting. There is deliberately no league-wide weather model: a cavern has no rain, it
has dripping and dust and dark, so each venue carries its own weather table in
`data/templates/stadiums.yaml`.

Two layers reach the sim, and they are different in kind:

  - the VENUE's own effects, always on, because the field really is asphalt;
  - the WEATHER's effects, which vary by game and SCALE WITH THE ANOMALY LEVEL.

⚠️ Intensity rides `Game._criticalityMultiplier`, the dial the game already loads at
kickoff. That is what makes weather the public, number-free barometer of a hidden
system: the aggregate's climb toward its threshold is visible as the weather getting
worse, and nobody has to be told what it means. It also means weather inherits the
anomaly loader's existing fallback — if that system is unavailable the dial is 1.0 and
the league plays in settled conditions.

⚠️ Weather is announced BEFORE kickoff (pick-em and lineups read it), so the roll must
be REPRODUCIBLE: `rollWeather` takes an explicit seed and is a pure function of
(venue, dial, seed). The announcement and the game must never disagree.
"""

import os
import random
from typing import Optional, Dict, Any, List, Tuple

import yaml

from logger_config import get_logger

logger = get_logger("floosball.stadiumManager")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
STADIUMS_FILE = 'stadiums.yaml'

# The modifier vocabulary. ⚠️ Every key here has a REAL call site in floosball_game.py.
# The previous version of this file carried ten keys, none of them read by anything and
# three (clutchVariance / roadDiscipline / homeBoost) with nothing in the sim to attach
# to. A key with no call site is a promise the game does not keep — do not add one here
# until it is wired.
EFFECT_KEYS = (
    'passAccuracy',     # completion roll in passPlay
    'deepPassChance',   # pass-tier weighting
    'runYardage',       # the run gate model
    'fgAccuracy',       # fgMakeProbability — so the ATTEMPT decision moves with it too
    'sackRate',         # calculateSackProbability
    'fumbleRate',       # the fumble check in the shared carrier tail
    'puntDistance',     # resolvePunt
    'returnYards',      # _resolvePuntReturn
    'paceMod',          # pre-snap time
    'visibility',       # SEE BELOW — the only two-sided key in the vocabulary
)

# ⚠️ `visibility` IS NOT A PASSING PENALTY WEARING A NEW NAME, and it is the one key
# here that helps one side of the ball while hurting the other. If nobody can see, the
# BALL CARRIER IS ALSO HARDER TO TRACK. Modeling darkness as pass accuracy alone quietly
# asserts that poor sight only costs the offense, which is why 34 of the league's
# conditions had collapsed into a flat tax on throwing.
#
# 1.0 = normal sight. Below 1.0 = obscured. Above 1.0 = unnaturally clear.
#
# Wiring (all four call sites verified to exist before the key was added):
#   passAccuracy   x visibility ** VISIBILITY_PASS_EXP    (mild)
#   deepPassChance x visibility ** VISIBILITY_DEEP_EXP    (steep — a deep ball needs
#                                                          sight most)
#   punt muff + fair catch  raised as sight falls  (PUNT_MUFF_*, PUNT_FAIRCATCH_*)
#   the tackler's resistance in _runnerMove  LOWERED as sight falls, so a dark field
#   hands yards to the carrier. This is the two-sided half and must not be dropped.
VISIBILITY_PASS_EXP = 0.5
VISIBILITY_DEEP_EXP = 1.5
VISIBILITY_TACKLE_EXP = 0.6   # how much a defender loses by not seeing the carrier

# ⚠️ One `visibility` term replaces TWO authored pass keys and adds two more
# consequences, so counting it once would make a dark venue measure as half the venue it
# is. The fairness bands weight it accordingly.
SEVERITY_WEIGHTS = {'visibility': 2.0}

NEUTRAL_EFFECTS: Dict[str, float] = {k: 1.0 for k in EFFECT_KEYS}

# ─── The intensity ladder ─────────────────────────────────────────────────────
# Maps the anomaly dial onto a named level and a SCALE applied to how far each
# authored effect sits from neutral. Authored numbers are "Rough" strength, so scale
# 1.0 is the file as written; everything else stretches or shrinks it.
#
#   dial 0.45 = a suppression window (the Cores just patched a near-miss)
#   dial 1.0  = quiet league
#   1.0 - 2.6 = the instability ramp toward the hidden threshold
#   dial 5.0  = an actually-fired Criticality (CRITICALITY_MULTIPLIER)
#
# (maxDial, key, label, scale, unlocksUnreal)
INTENSITY_LADDER: List[Tuple[float, str, str, float, bool]] = [
    (0.50, 'still',     'Still',     0.00, False),
    (1.05, 'settled',   'Settled',   0.25, False),
    (1.60, 'unsettled', 'Unsettled', 0.60, False),
    (2.20, 'rough',     'Rough',     1.00, False),
    (4.50, 'severe',    'Severe',    1.40, False),
    (float('inf'), 'unreal', 'Unreal', 2.00, True),
]

# How strongly each level prefers a rougher condition. Index into the venue's weather
# list is weighted by this: at 'still' only the calm state can come up; by 'unreal' the
# criticality-only states dominate.
_CALM_WEIGHT = {
    'still': 50.0, 'settled': 4.0, 'unsettled': 1.5,
    'rough': 0.7, 'severe': 0.35, 'unreal': 0.1,
}
_UNREAL_WEIGHT = 3.0   # relative weight of an unrealOnly state once unlocked


def intensityFor(dial: float) -> Dict[str, Any]:
    """Resolve the anomaly dial onto a named intensity level."""
    try:
        d = float(dial)
    except (TypeError, ValueError):
        d = 1.0
    for maxDial, key, label, scale, unlocksUnreal in INTENSITY_LADDER:
        if d <= maxDial:
            return {'level': key, 'levelLabel': label, 'scale': scale,
                    'unlocksUnreal': unlocksUnreal, 'dial': d}
    last = INTENSITY_LADDER[-1]
    return {'level': last[1], 'levelLabel': last[2], 'scale': last[3],
            'unlocksUnreal': last[4], 'dial': d}


def scaleEffects(authored: Dict[str, float], scale: float) -> Dict[str, float]:
    """Stretch each authored effect's DEVIATION from neutral by `scale`.

    One authored number per effect covers every intensity level, so a venue is never
    written out six times. scale 0.0 collapses to no weather at all, which is what the
    suppression window is supposed to feel like.
    """
    out: Dict[str, float] = {}
    for key, value in (authored or {}).items():
        if key not in EFFECT_KEYS:
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        out[key] = 1.0 + (v - 1.0) * scale
    return out


def combineEffects(*layers: Dict[str, float]) -> Dict[str, float]:
    """Multiply layers together into a full effects dict (venue x weather)."""
    out = dict(NEUTRAL_EFFECTS)
    for layer in layers:
        for key, value in (layer or {}).items():
            if key in out:
                out[key] = out[key] * float(value)
    return out


# ─── Phase bias: does this venue favor the run or the pass? ───────────────────
# Positive = PASSING is suppressed here more than running, so build and call for the
# run. Negative = the reverse.
#
# ⚠️ MEASURED RELATIVE TO THE LEAGUE, NOT TO NEUTRAL, and that is not a detail. Real
# weather suppresses throwing far more often than it suppresses running — fog, wind,
# rain, glare and dark all land on the passing game — so the RAW bias came out
# 20 venues run-favoring against 1 pass-favoring. Fed to the front office that is not
# 32 identities, it is a league-wide instruction to stop drafting quarterbacks, and it
# would devalue the position measured as the most impactful in the sim (+2.52 wins).
# Centering on the league mean turns "everywhere is hard to throw in" into "this place
# is harder to throw in THAN MOST", which is the only version a GM can act on.
_PASS_KEYS = (('passAccuracy', 1.0), ('deepPassChance', 0.5), ('sackRate', -1.0))
_RUN_KEYS = (('runYardage', 1.0),)
_BIAS_FULL_SCALE = 0.11   # centered bias at which phaseBias() reaches +/-1


def _rawBias(effects: Dict[str, float]) -> float:
    import math
    p = sum(w * math.log(effects[k]) for k, w in _PASS_KEYS if effects.get(k, 0) > 0)
    r = sum(w * math.log(effects[k]) for k, w in _RUN_KEYS if effects.get(k, 0) > 0)
    return (-p) - (-r)   # penalty to passing, less penalty to running


class StadiumManager:
    def __init__(self) -> None:
        self._venues: Dict[int, Dict[str, Any]] = {}
        self._bias: Dict[int, float] = {}
        self._load()
        self._computeBias()

    def _load(self) -> None:
        path = os.path.join(TEMPLATE_DIR, STADIUMS_FILE)
        if not os.path.exists(path):
            logger.warning(f"stadiums file not found at {path}; venues disabled")
            return
        try:
            with open(path, 'r') as f:
                raw = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error(f"failed to load {path}: {exc}")
            return
        if not isinstance(raw, dict):
            logger.error(f"stadiums.yaml must be a mapping, got {type(raw).__name__}")
            return

        for teamId, payload in raw.items():
            try:
                tid = int(teamId)
            except (TypeError, ValueError):
                logger.warning(f"stadium key {teamId!r} is not a team id; skipping")
                continue
            if not isinstance(payload, dict):
                logger.warning(f"stadium for team {tid} is not a mapping; skipping")
                continue
            # ⚠️ The venue's own name, NOT the team's. The previous loader stored the
            # team name here, so every venue name in the file went unread.
            self._venues[tid] = {
                'teamId': tid,
                'team': payload.get('team') or '',
                'name': payload.get('name') or f"Stadium {tid}",
                'setting': (payload.get('setting') or '').strip(),
                'icon': payload.get('icon') or 'default',
                'tagline': payload.get('tagline') or '',
                'description': (payload.get('description') or '').strip(),
                'effects': self._normalizeEffects(payload.get('effects') or {}),
                'weather': self._normalizeWeather(payload.get('weather') or [], tid),
            }
        logger.info(f"loaded {len(self._venues)} stadiums")

    @staticmethod
    def _normalizeEffects(raw: Dict[str, Any]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for key, value in (raw or {}).items():
            if key not in EFFECT_KEYS:
                logger.warning(f"unknown stadium effect key {key!r} (ignored)")
                continue
            try:
                out[key] = float(value)
            except (TypeError, ValueError):
                logger.warning(f"non-numeric stadium effect {key}={value!r} (ignored)")
        return out

    @classmethod
    def _normalizeWeather(cls, raw: List[Any], tid: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for entry in raw or []:
            if not isinstance(entry, dict) or not entry.get('key'):
                continue
            text = (entry.get('text') or '').strip()
            if not text:
                # ⚠️ The description is a requirement, not a garnish: a game must be
                # able to say accurately what it was played in.
                logger.warning(f"weather {entry.get('key')!r} at team {tid} has no text")
            out.append({
                'key': entry['key'],
                'label': entry.get('label') or entry['key'],
                'text': text,
                'unrealOnly': bool(entry.get('unrealOnly')),
                'effects': cls._normalizeEffects(entry.get('effects') or {}),
            })
        return out

    def _computeBias(self) -> None:
        """Per-venue run/pass lean, centered on the league so it sums to ~zero."""
        raw: Dict[int, float] = {}
        for tid, v in self._venues.items():
            always = _rawBias(v['effects'])
            ordinary = [w for w in v['weather']
                        if not w['unrealOnly'] and w['effects']]
            wx = (sum(_rawBias(w['effects']) for w in ordinary) / len(ordinary)) if ordinary else 0.0
            raw[tid] = always + wx
        if not raw:
            return
        mean = sum(raw.values()) / len(raw)
        for tid, value in raw.items():
            centered = (value - mean) / _BIAS_FULL_SCALE
            self._bias[tid] = max(-1.0, min(1.0, centered))

    # -------- public API --------

    def phaseBias(self, teamId: Optional[int]) -> float:
        """-1 (this venue favors the PASS) .. +1 (favors the RUN), vs the league.

        Consumed by the front office, which weights RB/TE against QB/WR for the team
        that lives here, and by play-calling, which leans toward the phase that works.
        ⚠️ A team plays only half its games at home, so whatever reads this must stay
        modest: over-fitting the venue is paid for in the other fourteen games.
        """
        return self._bias.get(teamId, 0.0)

    def has(self, teamId: Optional[int]) -> bool:
        return teamId in self._venues

    def venue(self, teamId: Optional[int]) -> Optional[Dict[str, Any]]:
        return self._venues.get(teamId)

    def serialize(self, teamId: Optional[int]) -> Optional[Dict[str, Any]]:
        """JSON-safe venue identity for API responses. Omits raw multipliers."""
        v = self._venues.get(teamId)
        if not v:
            return None
        return {'name': v['name'], 'setting': v['setting'], 'icon': v['icon'],
                'tagline': v['tagline'], 'description': v['description']}

    def rollWeather(self, teamId: Optional[int], dial: float,
                    seed: Optional[int] = None) -> Dict[str, Any]:
        """Pick this game's condition at the venue. PURE in (teamId, dial, seed).

        ⚠️ Reproducibility is load-bearing, not tidiness: the condition is announced
        before kickoff so it can be read for pick-em and lineups, and the game must
        arrive at the same one. Pass the same seed at both ends.
        """
        intensity = intensityFor(dial)
        venue = self._venues.get(teamId)
        if not venue or not venue['weather']:
            return self._neutral(intensity)

        states = venue['weather']
        # ⚠️ At scale 0 the calm state is FORCED, not merely likely. Every effect
        # collapses to neutral there, so reporting "Heavy Swell" while nothing swells
        # would be exactly the lie this feature is not allowed to tell.
        if intensity['scale'] <= 0.0:
            return self._describe(venue, states[0], intensity)

        unlocked = [s for s in states if not s['unrealOnly'] or intensity['unlocksUnreal']]
        if not unlocked:
            unlocked = states[:1]

        rng = random.Random(seed) if seed is not None else random
        calmWeight = _CALM_WEIGHT.get(intensity['level'], 0.2)
        weights = []
        for i, s in enumerate(unlocked):
            if s['unrealOnly']:
                weights.append(_UNREAL_WEIGHT)
            elif i == 0:
                weights.append(calmWeight)
            else:
                weights.append(1.0)
        state = rng.choices(unlocked, weights=weights, k=1)[0]
        return self._describe(venue, state, intensity)

    @staticmethod
    def _describe(venue: Dict[str, Any], state: Dict[str, Any],
                  intensity: Dict[str, Any]) -> Dict[str, Any]:
        weatherEffects = scaleEffects(state['effects'], intensity['scale'])
        return {
            'venueName': venue['name'],
            'venueIcon': venue['icon'],
            'setting': venue['setting'],
            'key': state['key'],
            'label': state['label'],
            'text': state['text'],
            'level': intensity['level'],
            'levelLabel': intensity['levelLabel'],
            'unreal': state['unrealOnly'],
            # The venue's own character is NOT scaled — the field is asphalt whatever
            # the anomaly aggregate is doing. Only the weather rides the dial.
            'effects': combineEffects(venue['effects'], weatherEffects),
        }

    @staticmethod
    def _neutral(intensity: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'venueName': None, 'venueIcon': 'default', 'setting': '',
            'key': 'clear', 'label': 'Clear', 'text': 'Clear conditions.',
            'level': intensity['level'], 'levelLabel': intensity['levelLabel'],
            'unreal': False, 'effects': dict(NEUTRAL_EFFECTS),
        }

    def neutralWeather(self) -> Dict[str, Any]:
        return self._neutral(intensityFor(1.0))


_instance: Optional[StadiumManager] = None


def getStadiumManager() -> StadiumManager:
    global _instance
    if _instance is None:
        _instance = StadiumManager()
    return _instance
