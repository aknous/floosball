"""Frames must not end EARLY by draining the game clock past a frame boundary.

Owner-reported bug (prod game 5254): a frames match ended ~10 minutes early. A frame-
ending field goal drained the ENTIRE remaining game clock before the snap (the setupFG
tempo drain used the raw game clock, ~600s, while _isFgDrainMode only gated on the FRAME
clock <= 60s). That jump blew past the frame boundary, so awardFrames committed the
remaining frame(s) EMPTY (0 plays, 0-0), handing the leader a phantom half-frame and
deciding the match on unplayed frames.

Fix: the setupFG drain reads _offenseEffectiveSecs() (the FRAME buzzer in frames, the game
clock in standard, the chess budget in chess) instead of the raw game clock, so the drain
is bounded to the deadline actually in play.

Guards: over a batch of full frames games, NO frame is committed with zero plays UNLESS the
match was genuinely clinched at that point (a leader too far ahead to be caught — the legit
"golf 3&2" early end), and no single play drains an outsized chunk of the game clock.

Run: .venv/bin/python test_frames_no_early_end.py   (exits non-zero on any failure)
"""
import sys, types, asyncio, random
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']
import floosball_game as FG
from collections import Counter
from managers.timingManager import TimingManager, TimingMode
from game_rules import GameRules
from scenario import _makeTeam

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
FRAMES = 6
# A single play should never drain a big slice of the game clock. End-of-half/quarter/frame
# drains legitimately reach the ~40s play clock; anything past this is a runaway drain.
MAX_SANE_DRAIN = 90

nonClinchEmpty = 0
bigJumpGames = 0
spikeEndGames = 0
worstJump = (0, None)

for i in range(N):
    rr = random.Random(1000 + i)
    home = _makeTeam('H', 'HOM', 1000 + i * 10, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    away = _makeTeam('A', 'AWY', 5000 + i * 10, phys=rr.randint(74, 92), ment=rr.randint(74, 92))
    gr = GameRules(); gr.gameFormat = 'frames'; gr.framesPerGame = FRAMES
    g = FG.Game(home, away, gameRules=gr, timingManager=TimingManager(TimingMode.FAST))
    g.id = i

    # Record the largest single-play game-clock drain.
    g._maxConsume = 0; g._maxCtx = None
    _origCG = g.consumeGameTime
    def _cg(seconds, _g=g, _orig=_origCG):
        if seconds and seconds > _g._maxConsume:
            _g._maxConsume = seconds
            _g._maxCtx = (f"Q{_g.currentQuarter}", f"clk={_g.gameClockSeconds}",
                          str(getattr(getattr(_g, 'play', None), 'playType', None)))
        return _orig(seconds)
    g.consumeGameTime = _cg

    asyncio.run(asyncio.wait_for(g.playGame(), timeout=60))

    fc = Counter()
    for entry in g.gameFeed:
        if isinstance(entry, dict) and 'play' in entry:
            fr = getattr(entry['play'], 'frame', None)
            if fr is not None:
                fc[fr] += 1
    empty = [idx for idx in range(1, FRAMES + 1) if fc.get(idx, 0) == 0]
    fh = getattr(g, '_framesWonHome', 0.0); fa = getattr(g, '_framesWonAway', 0.0)
    # A clinch legitimately leaves later frames empty. If the final frames margin is <= 1
    # the match was NOT clinched, so an empty frame means it ended early — the bug.
    if empty and abs(fh - fa) <= 1.0:
        nonClinchEmpty += 1
        print(f"    game {i}: NON-CLINCH empty {empty} frames {fh}-{fa} plays/frame={dict(sorted(fc.items()))}")
    if g._maxConsume > MAX_SANE_DRAIN:
        bigJumpGames += 1
        print(f"    game {i}: RUNAWAY DRAIN {g._maxConsume}s @ {g._maxCtx}")
    if g._maxConsume > worstJump[0]:
        worstJump = (g._maxConsume, g._maxCtx)
    # A spike STOPS the clock to buy another snap; ending the game ON a spike means the spike
    # forfeited the down and burned the last of the clock for nothing.
    lastType = None
    for entry in g.gameFeed:
        if isinstance(entry, dict) and 'play' in entry and getattr(entry['play'], 'playResult', None) is not None:
            lastType = getattr(getattr(entry['play'], 'playType', None), 'value', None)
            break
    if lastType == 'Spike':
        spikeEndGames += 1
        print(f"    game {i}: game ENDED ON A SPIKE (bought no follow-up play)")

print(f"\n1. No frame ends early in a still-live match (across {N} games)")
expect(f"no non-clinch empty frames (got {nonClinchEmpty})", nonClinchEmpty == 0)
print("2. No single play drains an outsized slice of the clock")
expect(f"no runaway clock drains (got {bigJumpGames}; worst {worstJump[0]}s @ {worstJump[1]})",
       bigJumpGames == 0)
print("3. No game ends on a spike (a spike must buy a follow-up snap)")
expect(f"no game ends on a wasted spike (got {spikeEndGames})", spikeEndGames == 0)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — frames games run their full slate; no clock drain skips a frame.")
