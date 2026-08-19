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

# ── an unknown venue degrades to neutral rather than raising ───────────────
w = m.rollWeather(9999, 5.0, seed=1)
expect("an unknown team plays in neutral conditions rather than crashing",
       w['effects'] == NEUTRAL_EFFECTS and w['venueName'] is None)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — 32 venues, weather scales with the anomaly dial, and what it reports is what it does.")
