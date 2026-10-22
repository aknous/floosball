"""A pass to a receiver splits its WPA between passer and receiver whatever the result.

A targeted incompletion or interception used to go 100% on the QB while a completion gave
him only WPA_PASS_QB_SHARE (60%). Once the fitted WP model priced a lost down (-1.86) and a
pick (-8.36) at what they cost, QBs averaged -7.4 WPA a game while passing as a whole netted
+8.3 and their receivers sat well positive. Now 60/40 on every targeted throw; a drop keeps
its own receiver-heavy split, and a sack or throwaway (no target) stays on the QB.

  .venv/bin/python test_pass_wpa_split.py      (or with pytest)
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)
os.environ.setdefault('TIMING_MODE', 'fast')

from scenario import Scenario                                        # noqa: E402
import floosball_game as FG                                          # noqa: E402
from constants import WPA_PASS_QB_SHARE, WPA_DROP_RECEIVER_SHARE     # noqa: E402


def _credit(**flags):
    """Home throws; the play costs home 5 WPA. Returns (passer, receiver) game WPA."""
    sc = Scenario().situation(quarter=2, clock=400, offense='home', down=2, distance=8, ballOn=60)
    g = sc.game
    qb, wr = sc.home.rosterDict['qb'], sc.home.rosterDict['wr1']
    for p in (qb, wr):
        p._gameWpa = 0.0
    play = g.play
    play.playType = FG.PlayType.Pass
    play.passer = qb
    play.receiver = wr if flags.pop('targeted', True) else None
    for k, v in flags.items():
        setattr(play, k, v)
    g._attributeWpa(play, -5.0, 5.0)
    return qb._gameWpa, wr._gameWpa


def test_a_targeted_incompletion_splits_like_a_completion():
    qb, wr = _credit()
    assert abs(qb - (-5.0 * WPA_PASS_QB_SHARE)) < 1e-9 and abs(wr - (-5.0 * (1 - WPA_PASS_QB_SHARE))) < 1e-9


def test_an_interception_on_a_target_splits_too():
    qb, wr = _credit(isInterception=True)
    assert abs(qb - (-5.0 * WPA_PASS_QB_SHARE)) < 1e-9 and wr < 0


def test_a_drop_keeps_its_receiver_heavy_split():
    qb, wr = _credit(passIsDropped=True)
    assert abs(wr - (-5.0 * WPA_DROP_RECEIVER_SHARE)) < 1e-9


def test_a_sack_or_throwaway_stays_on_the_qb():
    qb, wr = _credit(isSack=True)
    assert qb == -5.0 and wr == 0.0
    qb, wr = _credit(targeted=False)
    assert qb == -5.0 and wr == 0.0


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
