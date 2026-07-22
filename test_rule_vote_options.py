"""Rule-vote ballot: format-aware option filtering.

A rule candidate is only offered when it can actually MEAN something under the active
game format. Guards the reported bug: with innings active (a clock-inert format — the
quarter never advances and nothing keys off the game clock), the ballot still offered
"Enable Running Clock".

The gate is `spec['requiresClock']` in RULE_VOTE_CANDIDATES, resolved against the
format's own `GameFormat.consumesRealTime()` rather than a hand-kept list of format
keys, so adding a format can't leave the ballot behind.

Run: .venv/bin/python test_rule_vote_options.py   (exits non-zero on any failure)
"""
import sys, types, random
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa: F401
    del sys.modules['floosball_game']
from game_rules import GameRules
from managers.ruleVoteManager import RuleVoteManager
from constants import GAME_FORMAT_PRESETS, DRIVE_CLOCK_PRESETS

# Derive these from the presets rather than matching key strings — 'dc_6plays_possession'
# and 'dc_120s_possession' are only one character apart in the wrong place.
SECONDS_PRESETS = {p['key'] for p in DRIVE_CLOCK_PRESETS
                   if p['patch'].get('driveClockUnit') == 'seconds'}
PLAYS_PRESETS = {p['key'] for p in DRIVE_CLOCK_PRESETS
                 if p['patch'].get('driveClockUnit') == 'plays'}

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

rv = RuleVoteManager()


def rulesFor(fmtKey):
    gr = GameRules()
    for p in GAME_FORMAT_PRESETS:
        if p['patch'].get('gameFormat') == fmtKey:
            for k, v in p['patch'].items():
                setattr(gr, k, v)
    return gr


def changeKeys(gr, samples=60):
    """Union of offered CHANGE keys (preset candidates pick randomly, so sample)."""
    keys = set()
    random.seed(11)
    for _ in range(samples):
        keys |= {o['key'] for o in rv._changeOptions(gr)}
    return keys


print("1. A clock-inert format never offers a clock rule")
for fmtKey in ('innings', 'play_limit', 'chess_clock'):
    if not any(p['patch'].get('gameFormat') == fmtKey for p in GAME_FORMAT_PRESETS) and fmtKey != 'innings':
        continue   # only assert on formats this build actually ships
    gr = rulesFor(fmtKey)
    if rv._formatHasClock(fmtKey):
        continue   # not a clockless format in this build; nothing to assert
    keys = changeKeys(gr)
    expect(f"{fmtKey}: no running-clock option", 'clockStopsOnDeadBall' not in keys)
    expect(f"{fmtKey}: no SECONDS-unit Drive Clock preset", not (keys & SECONDS_PRESETS))
    # The plays-unit Drive Clock doesn't need a clock, so the candidate survives.
    expect(f"{fmtKey}: the plays-unit Drive Clock is still offered", bool(keys & PLAYS_PRESETS))

print("2. Clock formats are unaffected")
for fmtKey in ('standard', 'frames'):
    if fmtKey != 'standard' and not any(p['patch'].get('gameFormat') == fmtKey for p in GAME_FORMAT_PRESETS):
        continue
    keys = changeKeys(rulesFor(fmtKey))
    expect(f"{fmtKey}: running clock IS offered", 'clockStopsOnDeadBall' in keys)
    expect(f"{fmtKey}: seconds-unit Drive Clock presets ARE offered", bool(keys & SECONDS_PRESETS))

print("3. A stranded clock rule stays REVERTABLE")
# Running clock voted in under standard, then the format swapped to innings: the rule now
# does nothing. It must not be re-proposable, but fans must still be able to clear it.
gr = GameRules(); gr.gameFormat = 'innings'; gr.clockStopsOnDeadBall = False
expect("stranded running clock is not re-offered as a change",
       'clockStopsOnDeadBall' not in changeKeys(gr))
expect("stranded running clock is still revertable",
       'clockStopsOnDeadBall' in [o['key'] for o in rv._revertOptions(gr)])
gr2 = GameRules(); gr2.gameFormat = 'innings'
gr2.driveClockEnabled = True; gr2.driveClockUnit = 'seconds'; gr2.driveClockLimit = 120
expect("stranded seconds-unit Drive Clock is still revertable",
       'revert:driveClock' in [o['key'] for o in rv._revertOptions(gr2)])

print("4. Criticality chaos rulesets honour the same gate")
violations = 0
for i in range(300):
    random.seed(i)
    g = rv.randomChaosRules(GameRules())
    fmt = getattr(g, 'gameFormat', 'standard') or 'standard'
    if rv._formatHasClock(fmt):
        continue
    if getattr(g, 'clockStopsOnDeadBall', True) is False:
        violations += 1
    if getattr(g, 'driveClockEnabled', False) and getattr(g, 'driveClockUnit', '') == 'seconds':
        violations += 1
expect(f"300 chaos rulesets: no clock rule under a clockless format ({violations} violations)",
       violations == 0)

print("5. The gate reads from the format, not a hardcoded list")
import game_formats as GF
mismatch = [k for k in GF._FORMATS
            if rv._formatHasClock(k) != GF.getFormat(k).consumesRealTime()]
expect(f"_formatHasClock agrees with consumesRealTime for every format ({len(GF._FORMATS)} checked)",
       not mismatch)
expect("an unknown format key fails OPEN (offers options rather than silently hiding them)",
       rv._formatHasClock('not_a_real_format') is True)


print()
if failures:
    print(f"FAILED: {len(failures)} check(s):")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("All rule-vote option checks passed.")
