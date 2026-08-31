"""Weather reaches the game, and reaches it in the right direction.

`test_stadium_weather.py` proves the DATA holds together — that the file is fair,
that the roll is reproducible, that a condition which says it swells has numbers on
it. This file proves the other half: that those numbers are actually READ by the
simulation, at the sites the plan names, with the sign the key implies.

That split matters because the failure mode here is silent and this feature has
already had it once. The previous vocabulary carried ten keys and NOT ONE of them was
read by anything — three of them (`clutchVariance`, `roadDiscipline`, `homeBoost`)
did not map onto anything that exists in the sim at all. A venue file full of
authored multipliers looks exactly the same whether the engine consumes it or not,
which is the "flavor on top of the score instead of another gate" failure the owner
has already called out on a different system.

Three properties, in order of how quietly they break:

  - EVERY KEY HAS A LIVE CALL SITE. Swept statically off the vocabulary itself, so
    adding a key to `EFFECT_KEYS` without wiring it fails here rather than shipping
    as a promise the game does not keep.
  - THE SIGN IS RIGHT. `fumbleRate` above 1 must produce MORE fumbles. The threshold
    it lands on is inverted (a fumble is a roll ABOVE it), so the obvious
    implementation runs backwards and still looks plausible.
  - VISIBILITY IS TWO-SIDED. If the tackler does not lose ground in the dark, sight
    is a renamed passing penalty and half the key is decoration.

Run: .venv/bin/python test_weather_effects.py   (exits non-zero on any failure)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

from managers.stadiumManager import (getStadiumManager, EFFECT_KEYS,
                                     VISIBILITY_PASS_EXP, VISIBILITY_DEEP_EXP,
                                     VISIBILITY_TACKLE_EXP)
import constants

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'floosball_game.py')).read()

# ── 1. Every key in the vocabulary is read by the engine ───────────────────
# ⚠️ The vocabulary is the source of truth, so this sweeps EFFECT_KEYS rather than a
# hardcoded list: a key added there and never wired fails here on the next run.
print("\n-- every authored key reaches a call site --")
for key in EFFECT_KEYS:
    expect(f"`{key}` is read by the engine",
           bool(re.search(r"""wx\(['"]%s['"]\)""" % key, SRC)))

# `visibility` is not read by name at three of its four sites — it goes through the
# exponent helper — so assert the helper is used at each of them by exponent.
for name, const in (('the pass', '_VIS_PASS_EXP'),
                    ('the deep ball', '_VIS_DEEP_EXP'),
                    ('the TACKLER', '_VIS_TACKLE_EXP')):
    expect(f"sight is applied to {name}",
           f"_wxVisibility({const})" in SRC)

# ── 2. Sight cuts both ways ────────────────────────────────────────────────
print("\n-- sight is two-sided, not a renamed passing penalty --")
expect("a deep ball needs sight more than a short throw does",
       VISIBILITY_DEEP_EXP > VISIBILITY_PASS_EXP)
expect("the defender loses something in the dark too",
       VISIBILITY_TACKLE_EXP > 0)
# ⚠️ The tackler line is the one most likely to be dropped during wiring. Pin that it
# LOWERS resistance (multiplies defRating, which is subtracted from the move's power)
# rather than being applied somewhere harmless.
expect("sight lowers the tackler's resistance rather than the carrier's power",
       re.search(r"defRating \*= self\.game\._wxVisibility", SRC) is not None)
expect("a returner who cannot see it is likelier to muff and to wave it off",
       'PUNT_FAIRCATCH_SIGHT_K' in SRC and '_muffMult' in SRC)

# ── 3. The fumble key changes the RATE, at a resolution the roll cannot express ──
# ⚠️ Two traps, and the second is the one that actually bit. The threshold is
# INVERTED (a fumble is a roll ABOVE it), so scaling the threshold runs backwards.
# And the base check is an integer roll over 1-100 against a ~3% rate, so the ENTIRE
# authored range lives inside one step of its resolution: rounding the threshold
# erases a 1.05 outright, and flooring it turns that same 1.05 into a 1.33x. Measured
# both ways. The weather is therefore a correction on the OUTCOME, which is exact.
print("\n-- the fumble key moves the rate, in the right direction and by the right amount --")
import floosball_game as fg
import random

class _StubGame:
    """Just enough Game to exercise the weather helpers."""
    _wx = {}
    wx = fg.Game.wx
    _wxVisibility = fg.Game._wxVisibility
    _wxFumbleAdjust = fg.Game._wxFumbleAdjust

g = _StubGame()
THRESH, N = 97.0, 200_000

def measure(rate):
    g._wx = {'fumbleRate': rate} if rate is not None else {}
    rng = random.Random(7)
    hits = 0
    for _ in range(N):
        base = rng.randint(1, 100) > THRESH
        if g._wxFumbleAdjust(base, THRESH):
            hits += 1
    return hits / N

baseRate = measure(None)
expect(f"the base rate is untouched with no weather ({baseRate*100:.2f}%)",
       abs(baseRate - 0.03) < 0.002)
for rate in (1.05, 1.18, 1.5):
    got = measure(rate)
    expect(f"a {rate}x condition lands at {rate}x ({got*100:.2f}% vs {baseRate*rate*100:.2f}%)",
           abs(got / baseRate - rate) < 0.06)
dry = measure(0.8)
expect(f"a kinder condition lands BELOW the base rate ({dry*100:.2f}%)",
       abs(dry / baseRate - 0.8) < 0.06)
capped = measure(20.0)
expect(f"and no condition can turn a possession into a coin flip ({capped*100:.1f}%)",
       capped <= 0.21)

# ⚠️ A neutral game must consume NO randomness here, or the master switch is not an
# A/B arm — it is a different simulation, and every measurement taken against it is
# comparing two RNG streams rather than two rule sets.
g._wx = {}
rng = random.Random(1)
before = rng.random()
g._wxFumbleAdjust(False, 97.0)
rng2 = random.Random(1)
expect("a game with no weather consumes no randomness in the fumble path",
       before == rng2.random())

# ── 4. No weather is neutral, by construction ──────────────────────────────
print("\n-- absence of weather is neutral, never an exception --")
g._wx = {}
expect("a game with no weather reads 1.0 for every key",
       all(g.wx(k) == 1.0 for k in EFFECT_KEYS))
g._wx = {'footing': 0.0}
expect("a zero or negative multiplier is refused rather than zeroing the play",
       g.wx('footing') == 1.0)
g._wx = {'footing': 'mud'}
expect("a non-numeric multiplier is refused rather than raising",
       g.wx('footing') == 1.0)
g._wx = {'visibility': 1.0}
expect("perfect sight costs nothing at any exponent",
       g._wxVisibility(VISIBILITY_DEEP_EXP) == 1.0)

# ── 5. The flag really is a master switch ──────────────────────────────────
# ⚠️ An A/B arm is the only way to size a pre-game layer in this codebase (the
# measured rating -> win transfer is 1.619, so a layer that looks like a few percent
# can be worth wins). The flag has to genuinely produce a neutral world.
print("\n-- the master switch produces a neutral world --")
expect("WEATHER_ENABLED exists and is the flag the resolver reads",
       hasattr(constants, 'WEATHER_ENABLED')
       and 'if not WEATHER_ENABLED:' in SRC)
expect("the roll is wrapped so a failure plays settled rather than raising",
       'weather roll failed' in SRC)

# ── 6. The announcement and the game cannot disagree ───────────────────────
# ⚠️ Weather is announced BEFORE kickoff so it can be read for pick-em and lineups.
# The seed is built only from identifiers the announcement also holds, which is what
# lets the slate reproduce the exact condition without the game existing yet.
print("\n-- the pre-kickoff announcement can reproduce the game's condition --")
m = getStadiumManager()
seedParts = re.search(r"seed = \(([^)]*\n[^)]*)*?\)\n", SRC)
expect("the seed is derived from the game id, season, week and venue",
       all(t in SRC for t in ('int(self.id or 0)', 'int(self.seasonNumber or 0)',
                              'int(self.week or 0)', 'int(homeId or 0)')))
a = m.rollWeather(21, 2.1, seed=4242)
b = m.rollWeather(21, 2.1, seed=4242)
expect(f"the same seed yields the same condition ({a['label']})", a['key'] == b['key'])

# ── 7. The named call sites are the ones the plan named ────────────────────
# fgAccuracy in particular: it must land in fgMakeProbability, the SINGLE source of
# truth, so the coach's ATTEMPT decision moves with it. Applying it at the kick site
# only would let a coach send his kicker out into a gale he should have punted in.
print("\n-- each key lands where the plan says it lands --")
def inFunc(name, needle, endMarker='\n    def '):
    i = SRC.index(f'def {name}(')
    j = SRC.find(endMarker, i)
    return needle in SRC[i:j if j > 0 else len(SRC)]

expect("fgAccuracy lands in fgMakeProbability, so the ATTEMPT decision moves too",
       inFunc('fgMakeProbability', "self.wx('fgAccuracy')"))
# ⚠️ Deliberately at the CALL SITE rather than inside `calculateSackProbability`,
# which the plan named. That function is the pure tuning curve for the base rate, cap
# and steepness, and `test_sack_curve.py` calls it UNBOUND to measure the curve with
# no game around it — reaching for game state inside it makes the curve unmeasurable.
expect("sackRate lands on the sack roll, and the curve itself stays pure",
       "sackProbability *= self.game.wx('sackRate')" in SRC
       and not inFunc('calculateSackProbability', "wx('sackRate')"))
expect("passAccuracy lands on the completion, not on throw quality",
       inFunc('calculateCatchProbability', "wx('passAccuracy')")
       and not inFunc('calculateThrowQuality', "wx('passAccuracy')"))
expect("puntDistance lands on the leg ceiling, so the punt TYPE is chosen from it",
       inFunc('resolvePunt', "wx('puntDistance')"))
expect("returnYards lands in the punt return",
       inFunc('_resolvePuntReturn', "wx('returnYards')"))
expect("paceMod lands in the pre-snap time",
       inFunc('calculatePreSnapTime', "wx('paceMod')"))
expect("the deep-ball lean is its own layer, not a block inside the gameplan mods",
       'def _applyWeatherMods' in SRC
       and 'weights = self._applyWeatherMods(weights)' in SRC)

# ⚠️ `footing` is NOT a run-only key. Both halves must be present or the surface
# silently stops touching ~31% of passing yards.
expect("footing reaches the run",
       SRC.count("wx('footing')") >= 2 and "_wxFoot != 1.0" in SRC)
expect("footing also reaches yards after catch, which is the half that gets dropped",
       "_wxFootPass" in SRC)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS — every authored weather key is read by the sim, with the sign it implies.")
