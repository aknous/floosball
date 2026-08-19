"""Stadiums and weather: the data holds together, and the roll cannot lie.

Weather is announced BEFORE kickoff so it can be read for pick-em and card lineups,
and it scales with the anomaly dial. Two properties carry the whole feature and both
are easy to break silently:

  - REPRODUCIBILITY. The announcement and the game must agree. rollWeather is pure in
    (venue, dial, seed); if it ever stops being, the slate promises one thing and the
    game plays another.
  - THE DESCRIPTION MATCHES THE MECHANICS. A condition that reports "Heavy Swell" must
    actually swell. At scale 0 every effect collapses to neutral, so the calm state is
    FORCED there rather than merely likely — otherwise the venue narrates weather that
    is doing nothing, which is the "flavor on top" failure this feature is most at risk
    of shipping.

Run: .venv/bin/python test_stadium_weather.py   (exits non-zero on any failure)
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import yaml
from managers.stadiumManager import (getStadiumManager, intensityFor, scaleEffects,
                                     combineEffects, EFFECT_KEYS, NEUTRAL_EFFECTS,
                                     INTENSITY_LADDER)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

m = getStadiumManager()
raw = yaml.safe_load(open('data/templates/stadiums.yaml'))
cfg = json.load(open('config.json'))
teams = [t['name'] if isinstance(t, dict) else t for t in cfg['teams']]

# ── the data covers the league ─────────────────────────────────────────────
expect(f"every one of the {len(teams)} teams has a venue",
       all(m.has(i) for i in range(1, len(teams) + 1)))
expect("no venue is keyed to a team that does not exist",
       all(1 <= k <= len(teams) for k in raw))
# ⚠️ Keyed by ID because names change: six entries in the previous file had already
# gone stale that way. This asserts the readability field still lines up with config
# order, which is where a mis-keyed venue would show up.
mismatched = [(k, raw[k].get('team'), teams[k - 1]) for k in raw
              if raw[k].get('team') != teams[k - 1]]
expect(f"the readability `team:` field matches config order ({mismatched[:2]})",
       not mismatched)

# ── the description requirement ────────────────────────────────────────────
expect("every weather state has descriptive text",
       all(w.get('text') for v in raw.values() for w in v['weather']))
expect("every venue has a calm state listed first",
       all(not (v['weather'][0].get('effects') or {}) for v in raw.values()))
expect("every venue has at least one Criticality-only state",
       all(any(w.get('unrealOnly') for w in v['weather']) for v in raw.values()))

# ── the modifier vocabulary ────────────────────────────────────────────────
used = set()
for v in raw.values():
    used |= set(v.get('effects') or {})
    for w in v['weather']:
        used |= set(w.get('effects') or {})
expect(f"no effect key outside the wired vocabulary ({sorted(used - set(EFFECT_KEYS))})",
       not (used - set(EFFECT_KEYS)))

# ── the intensity ladder ───────────────────────────────────────────────────
scales = [intensityFor(d)['scale'] for d in (0.45, 1.0, 1.5, 2.1, 2.6, 5.0)]
expect(f"scale rises monotonically with the dial {scales}",
       all(a <= b for a, b in zip(scales, scales[1:])))
expect("a suppression window (dial 0.45) scales to zero", intensityFor(0.45)['scale'] == 0.0)
expect("only Criticality unlocks the unreal states",
       intensityFor(5.0)['unlocksUnreal'] and not intensityFor(2.6)['unlocksUnreal'])
expect("a garbage dial falls back to a real level rather than raising",
       intensityFor(None)['level'] in {lvl[1] for lvl in INTENSITY_LADDER})

# ── scaling math ───────────────────────────────────────────────────────────
scaled = scaleEffects({'passAccuracy': 0.90}, 0.5)
expect(f"scale stretches the deviation, not the value ({scaled['passAccuracy']:.3f} == 0.950)",
       abs(scaled['passAccuracy'] - 0.95) < 1e-9)
expect("scale 0 collapses every effect to neutral",
       scaleEffects({'fumbleRate': 1.5, 'passAccuracy': 0.7}, 0.0) == {'fumbleRate': 1.0, 'passAccuracy': 1.0})
expect("combine multiplies layers and fills the rest with neutral",
       abs(combineEffects({'runYardage': 1.1}, {'runYardage': 0.5})['runYardage'] - 0.55) < 1e-9
       and combineEffects({})['sackRate'] == 1.0)

# ── the two load-bearing properties ────────────────────────────────────────
# 1. reproducible: the pre-kickoff announcement and the game must agree.
same = all(m.rollWeather(t, 2.6, seed=99)['key'] == m.rollWeather(t, 2.6, seed=99)['key']
           for t in range(1, 33))
expect("the same (venue, dial, seed) always yields the same condition", same)
differs = len({m.rollWeather(21, 2.6, seed=s)['key'] for s in range(200)}) > 1
expect("different seeds do vary the condition", differs)

# 2. the description cannot lie: at scale 0 the state is calm AND neutral.
lied = []
for t in range(1, 33):
    w = m.rollWeather(t, 0.45, seed=t * 7)
    calmish = all(abs(w['effects'][k] - v) < 1e-9
                  for k, v in combineEffects(m.venue(t)['effects']).items())
    if not calmish:
        lied.append((t, w['label']))
expect(f"in a suppression window every venue reports its calm state only ({lied[:2]})",
       not lied)

# ⚠️ The venue's own character is NOT scaled by the dial — the field is asphalt
# whatever the anomaly aggregate is doing. Only the weather rides it.
v6 = m.venue(6)['effects']
still = m.rollWeather(6, 0.45, seed=1)['effects']
expect("venue baseline survives at zero intensity (the field does not change)",
       all(abs(still[k] - val) < 1e-9 for k, val in v6.items()))

# ── unreal states are genuinely gated ──────────────────────────────────────
# ⚠️ A weather key is scoped to its VENUE, not global: 7 keys are deliberately reused
# across the league (4 venues have a `glare`), and Pittsburgh's ordinary "Burst Fruit"
# shares `burst` with Minnesota's Criticality-only "The Line Bursts". Compare (team, key)
# pairs. Anything that PERSISTS a condition must store the venue alongside it for the
# same reason — a bare key does not identify a condition.
unrealKeys = {(t, w['key']) for t, v in raw.items() for w in v['weather'] if w.get('unrealOnly')}
belowCrit = {(t, m.rollWeather(t, d, seed=s)['key'])
             for t in range(1, 33) for d in (1.0, 1.6, 2.2, 2.6) for s in range(6)}
expect(f"no Criticality-only condition appears below Criticality ({sorted(belowCrit & unrealKeys)[:3]})",
       not (belowCrit & unrealKeys))
atCrit = collections.Counter(m.rollWeather(21, 5.0, seed=s)['key'] for s in range(400))
expect(f"at Criticality the unreal condition is the most common one ({atCrit.most_common(1)})",
       (21, atCrit.most_common(1)[0][0]) in unrealKeys)

# ── COMPETITIVE FAIRNESS: equal magnitude, different shape ─────────────────
# ⚠️ A team plays 14 games a season at its own venue, so a venue that is harsher than
# the others is a season-long tax on whoever lives there. Weather is symmetric within a
# game, so this is not about one side gaining — it is about repeated exposure. Venues
# must therefore differ in WHICH keys they touch, never in HOW HARD they hit.
#
# ⚠️ The ALWAYS-ON layer is the dangerous one and gets the tighter band: it is paid at
# full strength in every home game, where weather is scaled to a quarter in a settled
# league and varies game to game, so it averages out. Measured before this was pinned:
# always-on ran 0.070 to 0.263, a 3.8x spread.
import math
from managers.stadiumManager import SEVERITY_WEIGHTS
def severity(eff):
    """Distance from neutral in log space, so 0.80 and 1.25 weigh the same.

    ⚠️ `visibility` is weighted up: one term replaces two authored pass keys AND adds
    muff, fair-catch and missed-tackle consequences, so counting it once would make a
    dark venue measure as half the venue it actually is.
    """
    return sum(SEVERITY_WEIGHTS.get(k, 1.0) * abs(math.log(v))
               for k, v in eff.items() if v > 0)

always = {t: severity(raw[t].get('effects') or {}) for t in raw}
lo, hi = min(always.values()), max(always.values())
worst = sorted(always.items(), key=lambda kv: -kv[1])[:2]
expect(f"no venue carries a heavier permanent load than another ({hi/lo:.2f}x, worst {worst})",
       hi / lo <= 1.25)

rough = {}
for t in raw:
    base = m.venue(t)['effects']
    vals = []
    for k in range(120):
        w = m.rollWeather(t, 2.1, seed=k)
        vals.append(severity({key: v / base.get(key, 1.0) for key, v in w['effects'].items()}))
    rough[t] = sum(vals) / len(vals)
rlo, rhi = min(rough.values()), max(rough.values())
expect(f"no venue's weather is systematically rougher than another's ({rhi/rlo:.2f}x)",
       rhi / rlo <= 1.6)

# Shape is what makes a venue itself, so it must NOT be equalized. If every venue hit
# the same keys, the whole feature would be one weather system with 32 names on it.
shapes = {frozenset((raw[t].get('effects') or {}).keys()) for t in raw}
expect(f"venues still differ in WHICH keys they touch ({len(shapes)} distinct shapes)",
       len(shapes) >= 12)

# ── SOME WEATHER HAS TO HELP ───────────────────────────────────────────────
# ⚠️ Measured when this file was first written: 92% of every effect in it was a penalty,
# and in the weather layer passAccuracy was lowered in 40 of 40 conditions and
# deepPassChance in 32 of 32. Not one condition in the league helped anything. Three
# things follow from that and all three are bad:
#   - weather can only ever SUBTRACT offense, and subtracts more as the anomaly climbs,
#     so Criticality becomes a scoring drought instead of a spectacle;
#   - a "pass-favoring venue" is a lie — it only hurts running MORE, so a GM building a
#     passing team for one is building for somewhere merely less bad;
#   - 32 places collapse into 32 amounts of difficulty.
# The answers are physical and the league already had the geography: thin air at
# altitude carries the ball (Colorado, Mexico City), heat thins it the same way
# (Arizona), a sealed room has no wind at all (Las Vegas, San Francisco), and a tower
# has a standing updraft (Seattle).
HELPFUL = {'passAccuracy', 'deepPassChance', 'runYardage', 'fgAccuracy',
           'puntDistance', 'returnYards'}
def helps(k, v): return v > 1.0 if k in HELPFUL else v < 1.0

def isBoost(eff):
    """A condition that helps on balance, not one lucky key inside a penalty."""
    good = sum(1 for k, v in (eff or {}).items() if helps(k, v))
    return good >= 2 and good > len(eff or {}) - good

boostVenues = [t for t, v in raw.items() if any(isBoost(w.get('effects')) for w in v['weather'])]
expect(f"some venues are genuinely GOOD to play in ({len(boostVenues)} of 32)",
       len(boostVenues) >= 5)

passLifted = [(t, w['label']) for t, v in raw.items() for w in v['weather']
              if (w.get('effects') or {}).get('passAccuracy', 1.0) > 1.0
              or (w.get('effects') or {}).get('deepPassChance', 1.0) > 1.0]
expect(f"the passing game is helped somewhere, not merely hurt less ({len(passLifted)} conditions)",
       len(passLifted) >= 5)

# ⚠️ Criticality must not be uniformly a slog. Exactly one venue's top rung snaps to
# spec instead of degrading, which is far more unsettling than another penalty.
critBoost = [(t, w['label']) for t, v in raw.items() for w in v['weather']
             if w.get('unrealOnly') and isBoost(w.get('effects'))]
expect(f"at least one Criticality condition makes things BETTER, wrongly ({critBoost})",
       len(critBoost) >= 1)

# ── SIGHT IS ITS OWN DIMENSION, AND IT CUTS BOTH WAYS ─────────────────────
# ⚠️ Darkness was originally modeled as pass accuracy, which quietly asserts that poor
# sight only costs the OFFENSE. It does not: if nobody can see, the ball carrier is
# also harder to track. 34 of the league's conditions had collapsed into a flat tax on
# throwing because of it.
visUsers = [(t, w['label']) for t, v in raw.items() for w in v['weather']
            if 'visibility' in (w.get('effects') or {})]
expect(f"sight-caused conditions use the visibility term ({len(visUsers)} of them)",
       len(visUsers) >= 25)

# A condition should express its cause ONCE. Carrying visibility and a raw passing
# penalty together double-counts the same darkness.
doubled = [(t, w['label']) for t, v in raw.items() for w in v['weather']
           if 'visibility' in (w.get('effects') or {})
           and ({'passAccuracy', 'deepPassChance'} & set(w['effects']))]
expect(f"no condition charges for the same darkness twice ({doubled[:2]})", not doubled)

# ⚠️ The two-sided half is the whole point and is the part most likely to be quietly
# dropped during wiring. These exponents are what the engine must consume.
from managers.stadiumManager import (VISIBILITY_PASS_EXP, VISIBILITY_DEEP_EXP,
                                     VISIBILITY_TACKLE_EXP)
expect("a deep ball needs sight more than a short one does",
       VISIBILITY_DEEP_EXP > VISIBILITY_PASS_EXP)
expect("the defense loses something in the dark too, or it is just a passing penalty",
       VISIBILITY_TACKLE_EXP > 0)

# ── an unknown venue degrades to neutral rather than raising ───────────────
w = m.rollWeather(9999, 5.0, seed=1)
expect("an unknown team plays in neutral conditions rather than crashing",
       w['effects'] == NEUTRAL_EFFECTS and w['venueName'] is None)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — 32 venues, weather scales with the anomaly dial, and what it reports is what it does.")
