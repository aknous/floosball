"""ELO updates and the upset alert read ELO's own kickoff odds, never a format's display WP.

⚠️ FRAMES AND INNINGS SQUASH THE DISPLAYED KICKOFF WP TOWARD 50%. At 0-0 Frames reported
30% ELO + 70% coin flip and Innings 35% + 65%, so an 84% favorite showed as ~60%. The ELO
update and the upset alert both read that displayed number. Measured on 322 season-9 Frames
games, favorites won at ELO's rate (ELO 62%, actual 64%) against the squashed 54%, so the
squash was wrong: a favorite's win paid ELO as if it were nearly a coin flip, inflating the
strong teams, and the upset alert (which needs a 35/65 split) could never fire.

This plays real Frames and Innings games between mismatched teams and checks that
`preGameEloHomeWinProbability` is ELO's formula whatever the display shows, and that both
season-manager ELO call sites pass it.

Run: .venv/bin/python test_pregame_elo_odds.py
"""
import sys, os, types, asyncio, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _stub = types.ModuleType('floosball_game'); _stub.Game = type('G', (), {})
    sys.modules['floosball_game'] = _stub
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']
import floosball_game as FG
from managers.timingManager import TimingManager, TimingMode
from game_rules import GameRules
from scenario import _makeTeam

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


def eloOdds(h, a):
    return 1.0 / (1.0 + 10 ** (-(h - a) / 400.0))


def play(fmt, homeElo, awayElo, seed):
    home = _makeTeam('H', 'HOM', 7000 + seed, phys=82, ment=82)
    away = _makeTeam('A', 'AWY', 8000 + seed, phys=82, ment=82)
    home.elo, away.elo = homeElo, awayElo
    gr = GameRules(); gr.gameFormat = fmt
    if fmt == 'frames':
        gr.framesPerGame = 6
    g = FG.Game(home, away, gameRules=gr, timingManager=TimingManager(TimingMode.FAST))
    g.id = seed
    asyncio.run(asyncio.wait_for(g.playGame(), timeout=60))
    return g


print("1. Kickoff odds are ELO's, whatever the format displays")
for fmt in ('standard', 'frames', 'innings'):
    g = play(fmt, 1760, 1466, seed=1)
    want = eloOdds(1760, 1466)
    expect(f"{fmt}: ELO odds {g.preGameEloHomeWinProbability:.3f} == formula {want:.3f}",
           abs(g.preGameEloHomeWinProbability - want) < 1e-9)
    expect(f"{fmt}: home + away ELO odds sum to 1",
           abs(g.preGameEloHomeWinProbability + g.preGameEloAwayWinProbability - 1) < 1e-9)
    print(f"      ({fmt} displayed kickoff WP {g.preGameHomeWinProbability:.3f})")

print("2. The squash is real in Frames, which is why the two must be kept apart")
g = play('frames', 1760, 1466, seed=2)
expect("frames display is below ELO's odds for a big favorite",
       g.preGameHomeWinProbability < g.preGameEloHomeWinProbability - 0.1)

print("3. Both ELO call sites and the upset alert read the ELO odds")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'managers', 'seasonManager.py')).read()
calls = re.findall(r"updateEloAfterGame\((.*?)\n\s*\)", src, re.S)
expect(f"found both updateEloAfterGame calls ({len(calls)})", len(calls) == 2)
for c in calls:
    expect("call passes preGameElo*WinProbability",
           'preGameEloHomeWinProbability' in c and 'preGameEloAwayWinProbability' in c
           and 'preGameHomeWinProbability' not in c)
gsrc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'floosball_game.py')).read()
m = re.search(r"isUpsetAlert = False\n(.*?)self\.isUpsetAlert = isUpsetAlert", gsrc, re.S)
expect("upset alert reads preGameEloHomeWinProbability",
       m is not None and 'preGameEloHomeWinProbability' in m.group(1)
       and 'self.preGameHomeWinProbability' not in m.group(1))

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("All passed")
