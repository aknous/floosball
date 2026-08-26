"""Frames 4th-down calls answer the MATCH question, not a scalar margin.

Frames is decided by FRAMES WON, with total points breaking a frames tie — so a scalar
"am I ahead" cannot express it. Tying a frame HALVES it, and a halved frame can leave the
match level and throw it to the points tiebreak, where three points may be exactly what
wins. A team "down 3 in the frame" can therefore be one kick from the title.

`_framesMatchResultIfAdd(points)` asks the real question ('win' | 'draw' | 'loss' if the
offense scores `points` and the frame ends now). Two rules ride on it, and they are
mirrors:

  _framesFgWins    — the kick WINS the match, so take it; do not gamble a decided result.
  _framesFgFutile  — the kick cannot avoid a loss but a touchdown can, so it is a wasted
                     last chance; go for it.

⚠️ BOTH ARE GATED ON THE FRAME CLOSING. Earlier in a frame the match is not decidable
from here: the frame can still swing, and a kick that cuts the margin now has value with
time to get the ball back. Ungated, the futile veto fired on EVERY possession and an
offense with nine minutes of frame left refused a routine field goal (measured: 100% go,
where the identical board in standard kicks 100%).

Run: .venv/bin/python test_frames_decision.py
"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import managers
from scenario import Scenario, PlayType
from game_rules import GameRules

FRAMES = 6
fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


def build(*, framesH, framesA, frameIdx, frameMargin, aggMargin, secsLeft,
          ballOn=20, fmt='frames'):
    """⚠️ The CLOCK must match the frame index. `_frameSecsRemaining` derives the frame
    from elapsed game time, so setting `_frameIndex` alone leaves the two disagreeing and
    the frame reads wide open — a first sweep measured hundreds of "closing" states that
    were 325s from the end."""
    gr = GameRules(); gr.gameFormat = fmt; gr.framesPerGame = FRAMES
    s = Scenario(gameRules=gr)
    frameLen = (gr.quarterLengthSeconds * 4) / FRAMES
    elapsed = frameLen * (frameIdx + 1) - secsLeft
    q = min(4, int(elapsed // gr.quarterLengthSeconds) + 1)
    s.situation(quarter=q, clock=max(1, int(gr.quarterLengthSeconds * q - elapsed)),
                offense='home', offScore=0, defScore=0, down=4, distance=2, ballOn=ballOn)
    g = s.g
    entry = aggMargin - frameMargin
    g._frameStartHome, g._frameStartAway = max(0, entry), max(0, -entry)
    g.homeScore = g._frameStartHome + max(0, frameMargin)
    g.awayScore = g._frameStartAway + max(0, -frameMargin)
    g._framesWonHome, g._framesWonAway = framesH, framesA
    g._frameIndex = frameIdx
    return s, g


def rate(trials=30, **kw):
    """Fraction of trials the offense GOES for it rather than kicking."""
    go = 0
    random.seed(7)
    for _ in range(trials):
        s, _g = build(**kw)
        if s.fourthDownPlay() in (PlayType.Run, PlayType.Pass):
            go += 1
    return go / trials


# The canonical state: final frame, frames LEVEL, down 3 inside the frame. A field goal
# ties the frame -> halves it -> frames stay level -> total points decide. Whether that
# kick wins or loses is decided entirely by the AGGREGATE, which the frame margin cannot
# see. Same frame margin, opposite correct calls.
LEVEL_FINAL = dict(framesH=2, framesA=2, frameIdx=FRAMES - 1, frameMargin=-3, secsLeft=25)

print("1. Same frame margin, opposite calls — the aggregate is what decides")
s, g = build(aggMargin=+3, **LEVEL_FINAL)
expect("down 3 in-frame but UP on aggregate: the kick WINS the match",
       g._framesMatchResultIfAdd(g._fgValue()) == 'win')
expect("...so it is taken, not gambled (go rate 0.00)",
       rate(aggMargin=+3, **LEVEL_FINAL) == 0.0)

s, g = build(aggMargin=-10, **LEVEL_FINAL)
expect("down 3 in-frame and DOWN 10 on aggregate: the kick LOSES the match",
       g._framesMatchResultIfAdd(g._fgValue()) == 'loss')
expect("...and a touchdown wins the frame outright",
       g._framesMatchResultIfAdd(max(7, g._maxPossession())) == 'win')
expect("...so the kick is refused and it goes for it (go rate 1.00)",
       rate(aggMargin=-10, **LEVEL_FINAL) == 1.0)

print("\n2. Both rules are gated on the frame CLOSING")
early = dict(LEVEL_FINAL); early['secsLeft'] = 540
s, g = build(aggMargin=-10, **early)
expect("with 540s of frame left, the futile veto does not fire",
       g._framesFgFutile() is False)
expect("...nor does the winning-kick rule", g._framesFgWins() is False)
expect("...so a field goal to cut the deficit stays available (go rate < 1.00)",
       rate(aggMargin=-10, **early) < 1.0)

print("\n3. The two rules are mirrors and never both true")
both = 0
for am in (-10, -3, -1, 0, 1, 3, 10):
    for fm in (-7, -3, -1, 0, 3):
        _s, _g = build(framesH=2, framesA=2, frameIdx=FRAMES - 1,
                       frameMargin=fm, aggMargin=am, secsLeft=25)
        if _g._framesFgWins() and _g._framesFgFutile():
            both += 1
expect(f"no state has the kick both winning and futile ({both} found)", both == 0)

print("\n4. Off frames both are inert, so every other format is untouched")
_s, g = build(framesH=2, framesA=2, frameIdx=FRAMES - 1, frameMargin=-3,
              aggMargin=+3, secsLeft=25, fmt='standard')
expect("standard: _framesFgWins is False", g._framesFgWins() is False)
expect("standard: _framesFgFutile is False", g._framesFgFutile() is False)
expect("standard: the match-result helper is None", g._framesMatchResultIfAdd(3) is None)

print("\n5. KNOWN GAP, asserted so a change to it is deliberate")
# A kick that DRAWS the match while a touchdown WINS it is still taken: `_framesFgFutile`
# fires only on a 'loss'. Trading a certain draw for a shot at a win is a real strategic
# choice (and a coach-aggressiveness question), not an obvious defect, so it is left as
# an owner call rather than hardcoded either way. Measured: 39 such states in a
# 490-state closing-frame sweep, all kicked.
found = None
for am in (-10, -7, -4, -3, -1, 0):
    for fm in (-7, -4, -3, -1):
        _s, _g = build(framesH=2, framesA=2, frameIdx=FRAMES - 1,
                       frameMargin=fm, aggMargin=am, secsLeft=25)
        if (_g._framesMatchResultIfAdd(_g._fgValue()) == 'draw'
                and _g._framesMatchResultIfAdd(max(7, _g._maxPossession())) == 'win'):
            found = (fm, am)
            break
    if found:
        break
expect(f"a draw-vs-win state exists and is reachable {found}", found is not None)
if found:
    expect("the drawing kick is currently taken (documented, not endorsed)",
           rate(framesH=2, framesA=2, frameIdx=FRAMES - 1,
                frameMargin=found[0], aggMargin=found[1], secsLeft=25) < 1.0)

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — frames 4th-down calls read the match, not the margin.")
