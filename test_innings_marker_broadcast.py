"""Innings batting-change / try-extended markers must reach the WEBSOCKET.

Reported: "Bottom 4 · PHI up" and similar innings markers don't always arrive over
the socket — closing and reopening the game (which refetches the feed over REST)
is what makes them show up.

Cause: InningsFormat.possessionReceiver inserts the marker straight into
`game.gameFeed` and has no broadcast of its own, then sets `_inningsMarked = True`.
That flag is read by the drive loop to SUPPRESS the "next try" marker — which is
the one that actually calls broadcastGameState. So the transition emitted nothing
over the socket at all, and the line existed only in the feed, reachable via REST.

Fix: the format hands its event over on `_inningsMarkerEvent`; the drive loop
broadcasts that instead of skipping outright.

Run: .venv/bin/python test_innings_marker_broadcast.py
"""
import sys, types
sys.path.insert(0, '/Users/andrew/Projects/floosball')
_stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
sys.modules['floosball_game'] = _stub
import managers.timingManager  # noqa: F401
del sys.modules['floosball_game']
from game_formats import InningsFormat

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


class FakeTeam:
    def __init__(self, abbr):
        self.abbr = abbr


class FakeRules:
    inningsPerGame = 3
    triesPerInning = 3


class FakeGame:
    """Minimal stand-in for the bits InningsFormat.possessionReceiver touches."""
    def __init__(self):
        self.gameRules = FakeRules()
        self.homeTeam = FakeTeam('PHI')
        self.awayTeam = FakeTeam('NYG')
        self.currentQuarter = 1
        self.gameFeed = []
        self._inningsNumber = 1
        self._inningsHalf = 'top'
        self._inningsTries = 0
        self._inningsContinue = False
        self._inningsContinues = 0
        self._inningsMarked = False
        self._inningsMarkerEvent = None
        self.readjusted = []

    def _maybeReadjustGameplans(self, why):
        self.readjusted.append(why)


fmt = InningsFormat()

print("1. Batting change hands its marker to the drive loop")
g = FakeGame()
g._inningsTries = 2          # last try of the at-bat -> the flip happens
fmt.possessionReceiver(g, g.awayTeam, g.homeTeam)
feedTexts = [e.get('event', {}).get('text') for e in g.gameFeed]
expect(f"marker landed in the feed  {feedTexts}",
       any(t and ' up' in t for t in feedTexts))
expect("_inningsMarked set (suppresses the duplicate 'next try')", g._inningsMarked is True)
ev = g._inningsMarkerEvent
expect("_inningsMarkerEvent carries the event for broadcast", ev is not None)
if ev:
    expect(f"the handed-off event IS the feed line: {ev.get('text')!r}",
           ev.get('text') in feedTexts)
    expect("event is typed as an inning marker", ev.get('_type') == 'inning')

print("2. A try-extended continuation also hands its marker over")
g = FakeGame()
g._inningsContinue = True     # a made top conversion keeps the at-bat alive
fmt.possessionReceiver(g, g.awayTeam, g.homeTeam)
texts = [e.get('event', {}).get('text') for e in g.gameFeed]
expect(f"'Try extended!' in the feed  {texts}",
       any(t and 'extended' in t for t in texts))
expect("_inningsMarkerEvent set for the continuation too",
       g._inningsMarkerEvent is not None)

print("3. An ordinary try (no flip, no continuation) hands over nothing")
g = FakeGame()
g._inningsTries = 0           # plenty of tries left -> same team keeps batting
fmt.possessionReceiver(g, g.awayTeam, g.homeTeam)
expect("no marker event (the drive loop emits its own 'next try')",
       g._inningsMarkerEvent is None)
expect("_inningsMarked stays False", not g._inningsMarked)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — innings markers are handed to the drive loop to broadcast.")
