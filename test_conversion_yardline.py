"""A post-TD try must report ITS OWN line of scrimmage, not the touchdown's.

Reported symptom: on the field graphic a 5-point Conversion-Ladder try looked
like it started further back than it should.

Cause: `Play.__init__` snapshots `game.yardLine`, and the drive loop is what
normally refreshes that before each snap. The post-TD plays (PAT kick, 2-pt, any
ladder rung) build their own line of scrimmage OUTSIDE that loop — they set
`yardsToEndzone` but left `yardLine` holding the touchdown's spot. The frontend
derives the try's LOS from `yardLine`, so it drew the attempt from wherever the
TD happened instead of from the rung's snap.

The error scales with the rung: invisible on a 2-pt from the 2, obvious on the
5-pt from the 15, which is what got noticed.

Run: .venv/bin/python test_conversion_yardline.py
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401
del sys.modules['floosball_game']
from scenario import Scenario
from game_rules import GameRules

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


def _rules(ladder=True):
    gr = GameRules()
    gr.conversionLadderEnabled = ladder
    return gr


def deriveYardsToEndzone(yardLine, defAbbr):
    """The frontend's derivation (GameModalNew.deriveYardsToEndzone), mirrored so
    this test fails if the two ever disagree about what yardLine means."""
    if not isinstance(yardLine, str) or ' ' not in yardLine:
        return None
    team, num = yardLine.rsplit(' ', 1)
    n = int(num)
    return n if team == defAbbr else 100 - n


def _armBroadcast(g):
    """Scenario builds a Game without the live-broadcast WPA state, which the
    conversion's broadcastGameState() reads. Seed it so the real code path runs."""
    g.previousHomeWinProbability = 50.0
    g.previousAwayWinProbability = 50.0


def losFromConversion(distance, points):
    """Run a real conversion from `distance` and report the LOS the play carries,
    as the frontend would read it."""
    s = Scenario(gameRules=_rules())
    s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
                down=1, distance=10, ballOn=40)   # a spot far from the try's LOS
    g = s.g
    _armBroadcast(g)
    # Stale yard line from the "touchdown" that preceded the try — exactly what
    # the drive loop would have left behind.
    g.yardLine = f"{g.defensiveTeam.abbr} 3"
    g._simulateConversionPlay(g.homeTeam, g.awayTeam, points, distance)
    play = g.play
    return deriveYardsToEndzone(getattr(play, 'yardLine', None), g.awayTeam.abbr), play


print("1. Each ladder rung reports its own snap distance")
for pts, dist in ((2, 2), (3, 5), (4, 10), (5, 15)):
    los, play = losFromConversion(dist, pts)
    expect(f"{pts}-pt from the {dist}: LOS reads {los} (expected {dist})", los == dist)
    expect(f"{pts}-pt: play.yardsToEndzone == {dist}",
           getattr(play, 'yardsToEndzone', None) == dist)

print("2. The stale touchdown yard line is not carried through")
los, _ = losFromConversion(15, 5)
expect(f"5-pt try does NOT report the TD's spot (3): got {los}", los != 3)

print("3. The PAT kick reports the 15 too")
s = Scenario(gameRules=_rules(ladder=False))
s.situation(quarter=2, clock=600, offense='home', offScore=0, defScore=0,
            down=1, distance=10, ballOn=40)
g = s.g
_armBroadcast(g)
g.yardLine = f"{g.defensiveTeam.abbr} 3"
g._simulateExtraPointPlay(g.homeTeam, g.awayTeam)
los = deriveYardsToEndzone(getattr(g.play, 'yardLine', None), g.awayTeam.abbr)
expect(f"PAT kick LOS reads {los} (expected 15)", los == 15)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — post-TD tries report their own line of scrimmage.")
