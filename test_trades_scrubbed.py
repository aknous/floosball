"""Trading is off and every trade surface is hidden while it is (owner, 2026-10-03:
"scrub the site of trades altogether"). The records stay in the database.

Run: .venv/bin/python -m pytest -q test_trades_scrubbed.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def _src(path):
    return open(os.path.join(HERE, path)).read()


def test_trading_is_off_by_default():
    import constants
    assert constants.TRADING_ENABLED is False


def test_every_trade_endpoint_is_gated():
    src = _src('api/main.py')
    for route in ('/api/transactions/recent', '/api/transactions"', '/api/teams/{team_id}/trades',
                  '/api/teams/{team_id}/picks'):
        i = src.index('@app.get("' + route.rstrip('"') + ('")' if route.endswith('"') else '"'))
        body = src[i:src.index('\n@app.', i + 10)]
        assert '_tradesHidden()' in body, route


def test_trade_news_and_recap_rows_are_filtered():
    api = _src('api/main.py')
    assert "LeagueNewsItem.category != 'trade'" in api
    assert "e.event_type == 'trade'" in api
    assert "t.get('type') != 'trade'" in api
    assert "!= 'trade'" in _src('front_page.py')
    assert re.search(r"if cs is None or _tradesHidden\(\):\s+return False", api), \
        "the Transactions nav entry must stay closed while trading is off"


def test_with_trading_off_every_team_drafts_in_its_own_slot():
    """Owner: "make sure future rookie drafts use the correct order"."""
    import types
    import managers.seasonManager as SM
    sm = SM.SeasonManager.__new__(SM.SeasonManager)
    sm.currentSeason = types.SimpleNamespace(seasonNumber=9)
    teams = [types.SimpleNamespace(id=i, name=f'T{i}') for i in (3, 1, 2)]
    # Never reaches the pick table: no database is set up in this test.
    assert sm._rookieDraftSlots(teams) == [(t, t) for t in teams]


def test_with_trading_off_an_unusable_slot_is_not_sold():
    src = _src('managers/playerManager.py')
    assert 'if season is not None and tradingEnabled():' in src


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
