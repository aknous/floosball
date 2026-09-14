"""The drive's starting spot, which the compact drive line on a game card is drawn from.

⚠️ IT IS DERIVED, NOT STAMPED. `offensiveTeam` is assigned in TEN places -- turnovers,
kickoffs, the opening drive, and both conversion paths, which swap it and swap it back -- so
writing the spot at each is how this file has repeatedly ended up with one site missed and a
silently wrong value. `_noteDriveStart` asks "is the offense the one I saw last play" at the
top of the play loop instead, which cannot be forgotten by a new possession site and reads
AFTER a conversion's temporary swap has been undone.

Run: .venv/bin/python test_drive_start.py
"""
import sys, os, random, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from scenario import Scenario
from game_rules import GameRules

def playOne(seed):
    """One full game; returns every drive-start transition it recorded."""
    random.seed(seed)
    s = Scenario(gameRules=GameRules())
    g = s.game
    drives, states = [], []
    orig = g._noteDriveStart
    idx = [0]
    def spy():
        before = g._driveTeam
        orig()
        if g._driveTeam is not before:
            idx[0] += 1
            drives.append((g._driveTeam.abbr, g.driveStartYardsToEZ, g.currentQuarter))
        if g.driveStartYardsToEZ is not None:
            # ⚠️ KEYED ON A DRIVE INDEX, NOT ON THE START VALUE. Two drives in a row very
            # often begin on the SAME yard -- a touchback is the common case -- so watching
            # the value change counts 17 where there were 20 drives, which is the test
            # measuring the wrong thing rather than the code being wrong.
            states.append((idx[0], g.driveStartYardsToEZ, g.yardsToEndzone))
    g._noteDriveStart = spy
    asyncio.run(g.playGame())
    return g, drives, states

print("\n1. Drives are detected, and alternate")
g, drives, states = playOne(4)
expect(f"a full game produces a sensible number of drives ({len(drives)} over {g.totalPlays} plays)",
       8 <= len(drives) <= 40)
sameTwice = sum(1 for a, b in zip(drives, drives[1:]) if a[0] == b[0])
expect(f"possession alternates (only {sameTwice} back-to-back by one team)",
       sameTwice <= 2)

print("\n2. Every start is a spot a drive could really begin")
bad = [d for d in drives if d[1] is None or not (0 < d[1] <= 100)]
expect(f"none is missing or off the field ({len(bad)} bad)", not bad)
# ⚠️ THE OPENING DRIVE IS THE ONE THAT WAS WRONG. The loop's first pass runs BEFORE the
# opening kickoff has placed anybody, so `yardsToEndzone` was still 0 and the first drive
# recorded a start on its own goal line -- which is not a place a drive can start.
expect(f"the opening drive is not recorded at the goal line (it was {drives[0][1]})",
       drives[0][1] != 0)

print("\n3. The start HOLDS while the ball moves -- that is what makes it a drive")
byDrive = {}
for i, start, now in states:
    byDrive.setdefault(i, {'starts': set(), 'spots': set()})
    byDrive[i]['starts'].add(start)
    byDrive[i]['spots'].add(now)
wobbled = [i for i, v in byDrive.items() if len(v['starts']) != 1]
expect(f"the start never moves WITHIN a drive ({len(wobbled)} of {len(byDrive)} wobbled)",
       not wobbled)
longest = max((len(v['spots']) for v in byDrive.values()), default=0)
expect(f"and the ball does move under it (longest drive touched {longest} spots)",
       longest >= 3)

print("\n4. It survives several games unchanged")
for seed in (7, 12, 21):
    _g, d, st = playOne(seed)
    bad = [x for x in d if x[1] is None or not (0 < x[1] <= 100)]
    expect(f"seed {seed}: {len(d)} drives, none off the field", d and not bad)

print("\n5. It reaches the broadcast payload under its own name")
import floosball_game as FG, inspect
src = inspect.getsource(FG.Game.broadcastGameState)
expect("gameStateData carries driveStartYardsToEndzone",
       "'driveStartYardsToEndzone'" in src)

print("\n" + ("FAIL" if fails else "PASS") + " — the drive start is derived, holds, and ships.")
for f in fails: print("   -", f)
sys.exit(1 if fails else 0)
