"""A seller values a prospect it receives against its roster WITHOUT the player it is
selling (fixed 2026-11-05). Measured against the man leaving, a same-position replacement
looked worth almost nothing exactly where he matters most.

Run: .venv/bin/python -m pytest -q test_trade_seller_need_bar.py
"""
import inspect
from types import SimpleNamespace

from constants import REPLACEMENT_RATING
from floosball_player import Position
from managers.playerManager import PlayerManager
from managers.tradeManager import TradeMarket


def _pm():
    pm = PlayerManager.__new__(PlayerManager)
    pm.rookieCeiling = lambda brain, team, p: 0.0
    return pm


def test_the_player_being_sold_counts_as_gone():
    starter = SimpleNamespace(playerRating=90, termRemaining=3, willRetire=False)
    team = SimpleNamespace(rosterDict={'qb': starter}, prospects=[])
    rookie = SimpleNamespace(position=Position.QB)
    pm = _pm()
    assert pm._rookieNeedBar(None, team, rookie) == 90
    assert pm._rookieNeedBar(None, team, rookie, leaving=starter) == float(REPLACEMENT_RATING)


def test_the_seller_side_of_a_bid_passes_the_player_leaving():
    src = inspect.getsource(TradeMarket._assemble)
    assert 'valuingTeam=seller, swapPosition=swapPosition, leaving=leaving' in src
    src = inspect.getsource(TradeMarket._tradeableAssets)
    assert 'self._needBar(valuer, prospect, leaving)' in src
