"""Rule votes can be switched off from the Admin panel (owner, 2026-10-23: "run the league
in standard for a while, with criticality still randomizing rules").

Off means: no ballot opens, an open one closes with no rule change, the API reports no
vote open, and Criticality's per-game chaos rules are untouched.

Run: .venv/bin/python -m pytest -q test_rule_votes_switch.py
"""
import datetime
import os
import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def db(monkeypatch):
    from database.models import Base, AppSetting, RuleVoteWindow
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine, tables=[AppSetting.__table__, RuleVoteWindow.__table__])
    Session = sessionmaker(bind=engine)
    import database.connection as conn
    monkeypatch.setattr(conn, 'get_session', lambda: Session())
    return Session


def _setSwitch(Session, value):
    from database.models import AppSetting
    s = Session()
    row = s.query(AppSetting).filter_by(key='rule_votes_enabled').first()
    if row is None:
        s.add(AppSetting(key='rule_votes_enabled', value=value))
    else:
        row.value = value
    s.commit()
    s.close()


def _openWindow(Session, season=12, day=0):
    from database.models import RuleVoteWindow
    s = Session()
    w = RuleVoteWindow(season=season, day_index=day, fired=True, kind='change', core='aris',
                       option_keys='["touchdownValue"]',
                       closes_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1))
    s.add(w)
    s.commit()
    wid = w.id
    s.close()
    return wid


def test_an_absent_row_reads_the_constant(db):
    import constants
    assert constants.ruleVotesEnabled() is bool(constants.RULE_VOTE_ENABLED)


def test_the_admin_setting_overrides_the_constant(db):
    import constants
    _setSwitch(db, 'false')
    assert constants.ruleVotesEnabled() is False
    _setSwitch(db, 'true')
    assert constants.ruleVotesEnabled() is True


def test_an_unreachable_database_fails_open_to_the_constant(monkeypatch):
    import constants
    import database.connection as conn

    def _boom():
        raise RuntimeError('locked')
    monkeypatch.setattr(conn, 'get_session', _boom)
    assert constants.ruleVotesEnabled() is bool(constants.RULE_VOTE_ENABLED)


def test_switched_off_no_ballot_opens(db):
    from database.models import RuleVoteWindow
    from game_rules import GameRules
    from managers.ruleVoteManager import RuleVoteManager
    _setSwitch(db, 'false')
    RuleVoteManager(None).maybeOpenWindow(12, 1, GameRules())   # week 1 = game day 0
    s = db()
    assert s.query(RuleVoteWindow).count() == 0, 'no window, fired or not, is recorded'
    s.close()


def test_switched_off_an_open_ballot_closes_with_no_rule_change(db):
    from database.models import RuleVoteWindow
    from game_rules import GameRules
    from managers.ruleVoteManager import RuleVoteManager
    wid = _openWindow(db)
    _setSwitch(db, 'false')
    rules = GameRules()
    before = rules.toDict()
    assert RuleVoteManager(None).resolveOpenWindow(12, rules, requireClosed=True,
                                                   currentWeek=1) is None
    s = db()
    w = s.get(RuleVoteWindow, wid)
    assert w.resolved is True and w.winner_key == 'none' and w.applied is False
    s.close()
    assert rules.toDict() == before


def test_every_open_ballot_read_in_the_api_honors_the_switch():
    """status, ballot, cast, withdraw and the Discord reminder list all read the open
    window; a direct `getOpenWindow` call would show a ballot while votes are off."""
    src = open(os.path.join(HERE, 'api', 'main.py')).read()
    i = src.index('def _openRuleVote(')
    helper = src[i:src.index('\n@app.', i)]
    rest = src[:i] + src[i + len(helper):]
    assert 'ruleVotesEnabled' in helper
    assert 'getOpenWindow(' not in rest
    assert len(re.findall(r'_openRuleVote\(', rest)) >= 5


def test_criticality_chaos_rules_do_not_read_the_switch():
    src = open(os.path.join(HERE, 'managers', 'ruleVoteManager.py')).read()
    i = src.index('def randomChaosRules(')
    body = src[i:src.index('\n    def ', i + 10)]
    assert '_enabled' not in body and 'ruleVotesEnabled' not in body


def test_the_manager_reads_the_live_switch_not_the_constant():
    src = open(os.path.join(HERE, 'managers', 'ruleVoteManager.py')).read()
    assert 'RULE_VOTE_ENABLED' not in src
