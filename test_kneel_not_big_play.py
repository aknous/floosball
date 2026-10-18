"""A kneel or a spike is never tagged BIG PLAY, however far the win probability moves.

Late in Q4 the leader's kneels carry real WP swings: the leader-with-the-ball pull ramps
toward 99 as the clock drains, and a trailing team's failed last drive is priced on the
leader's next snap because turnover branches broadcast before possession switches.
Measured over 150 games, a kneel was tagged big in 10% of games (swings up to 55 points).
A kneel only runs the clock, so it gets no tag and fires no momentum bonus.

  .venv/bin/python test_kneel_not_big_play.py      (or with pytest)
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('TIMING_MODE', 'fast')

from scenario import Scenario                     # noqa: E402
import floosball_game as FG                       # noqa: E402
from constants import BIG_PLAY_WPA_THRESHOLD      # noqa: E402


def _resolve(playType, homeWpBefore):
    """Leader (home, up 7) snaps with 0:30 left; WP moves from `homeWpBefore` to wherever
    the model puts it. Returns the resolved play."""
    sc = Scenario().situation(quarter=4, clock=30, offense='home', offScore=21, defScore=14,
                              down=2, distance=10, ballOn=60, defTimeouts=0)
    g = sc.game
    g.play.playType = playType
    g.previousHomeWinProbability = homeWpBefore
    g.previousAwayWinProbability = 100 - homeWpBefore
    g._applyMomentumEvent = lambda *a, **k: setattr(g, '_momentumFired', True)
    g._resolvePlayWpa()
    return g


def test_kneel_with_a_big_swing_is_not_a_big_play():
    g = _resolve(FG.PlayType.Kneel, 50.0)
    assert g.play.homeWpa >= BIG_PLAY_WPA_THRESHOLD, f'fixture must produce a big swing, got {g.play.homeWpa}'
    assert g.play.isBigPlay is False
    assert not getattr(g, '_momentumFired', False), 'a kneel must not fire the big-play momentum bonus'


def test_spike_with_a_big_swing_is_not_a_big_play():
    g = _resolve(FG.PlayType.Spike, 50.0)
    assert g.play.homeWpa >= BIG_PLAY_WPA_THRESHOLD
    assert g.play.isBigPlay is False


def test_the_same_swing_on_a_run_is_still_a_big_play():
    g = _resolve(FG.PlayType.Run, 50.0)
    assert g.play.homeWpa >= BIG_PLAY_WPA_THRESHOLD
    assert g.play.isBigPlay is True
    assert getattr(g, '_momentumFired', False)


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
