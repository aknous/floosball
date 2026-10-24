"""The admin can see the league's rule slate and change it (owner, 2026-10-23).

A change goes through the same path as a resolved vote (`applyRuleChange` /
`revertRule`), so the live ruleset and the persisted override map agree; setting a rule
to standard reverts it rather than storing a no-op override.

Run: .venv/bin/python -m pytest -q test_rule_admin.py
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def rules(monkeypatch):
    from database.models import Base, AppSetting
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine, tables=[AppSetting.__table__])
    Session = sessionmaker(bind=engine)
    import database.connection as conn
    monkeypatch.setattr(conn, 'get_session', lambda: Session())
    monkeypatch.setattr(conn, 'SessionLocal', Session)
    from game_rules import GameRules
    return GameRules()


def _overrides():
    from game_rules import loadRuleOverrides
    return loadRuleOverrides()


def _row(slate, key):
    return next(r for r in slate if r['key'] == key)


def test_the_slate_is_the_rulebook_and_starts_standard(rules):
    import rule_admin
    from constants import RULE_VOTE_CANDIDATES
    slate = rule_admin.describeRules(rules)
    assert [r['key'] for r in slate] == list(RULE_VOTE_CANDIDATES)
    assert not any(r['changed'] for r in slate)
    assert _row(slate, 'gameFormat')['current'] == 'standard'
    assert _row(slate, 'driveClock')['current'] == 'off'
    downs = _row(slate, 'downsPerSeries')
    assert downs['default'] == 4 and [o['value'] for o in downs['options']][0] == 4


def test_a_scalar_change_is_live_and_persisted(rules):
    import rule_admin
    rule_admin.setRule(rules, 'downsPerSeries', value=5)
    assert rules.downsPerSeries == 5
    assert _overrides() == {'downsPerSeries': 5}
    assert _row(rule_admin.describeRules(rules), 'downsPerSeries')['changed'] is True


def test_setting_standard_reverts_instead_of_storing_an_override(rules):
    import rule_admin
    rule_admin.setRule(rules, 'touchdownPoints', value=7.5)
    assert rules.touchdownPoints == 7.5
    rule_admin.setRule(rules, 'touchdownPoints', value=6)
    assert rules.touchdownPoints == 6 and _overrides() == {}


def test_values_outside_the_slate_are_refused(rules):
    import rule_admin
    for key, value in (('downsPerSeries', 6), ('touchdownPoints', 12), ('fieldGoalPoints', 'x'),
                       ('firstDownDistance', 7), ('scoringModel', 'bogus'), ('nope', 1)):
        with pytest.raises(ValueError):
            rule_admin.setRule(rules, key, value=value)
    assert _overrides() == {}


def test_toggles_go_on_and_back_off(rules):
    import rule_admin
    rule_admin.setRule(rules, 'clockStopsOnDeadBall', value=False)
    assert rules.clockStopsOnDeadBall is False
    rule_admin.setRule(rules, 'clockStopsOnDeadBall', value=True)
    assert rules.clockStopsOnDeadBall is True and _overrides() == {}


def test_switching_formats_clears_the_old_formats_config(rules):
    import rule_admin
    rule_admin.setRule(rules, 'gameFormat', preset='gf_bust_24')
    assert rules.gameFormat == 'bust' and rules.targetScore == 24
    assert _row(rule_admin.describeRules(rules), 'gameFormat')['current'] == 'gf_bust_24'
    rule_admin.setRule(rules, 'gameFormat', preset='gf_frames_6')
    from game_rules import defaultRuleValue
    assert rules.gameFormat == 'frames' and rules.framesPerGame == 6
    assert rules.targetScore == defaultRuleValue('targetScore')
    ov = _overrides()
    assert ov['gameFormat'] == 'frames' and 'targetScore' not in ov
    rule_admin.setRule(rules, 'gameFormat', preset='standard')
    assert rules.gameFormat == 'standard' and _overrides() == {}


def test_drive_clock_preset_on_and_off(rules):
    import rule_admin
    rule_admin.setRule(rules, 'driveClock', preset='dc_8plays_possession')
    assert rules.driveClockEnabled is True and rules.driveClockLimit == 8
    assert _row(rule_admin.describeRules(rules), 'driveClock')['current'] == 'dc_8plays_possession'
    rule_admin.setRule(rules, 'driveClock', preset='off')
    assert rules.driveClockEnabled is False and _overrides() == {}
    with pytest.raises(ValueError):
        rule_admin.setRule(rules, 'driveClock', preset='dc_nonsense')


def test_reset_puts_every_rule_back(rules):
    import rule_admin
    rule_admin.setRule(rules, 'downsPerSeries', value=3)
    rule_admin.setRule(rules, 'sidelineGoalsEnabled', value=True)
    rule_admin.setRule(rules, 'gameFormat', preset='gf_innings_3')
    rule_admin.resetAllRules(rules)
    assert _overrides() == {}
    assert not any(r['changed'] for r in rule_admin.describeRules(rules))


def test_the_write_endpoints_are_admin_gated_and_refuse_mid_game():
    src = open(os.path.join(HERE, 'api', 'main.py')).read()
    for route in ('@app.get("/api/admin/rules")', '@app.put("/api/admin/rules")',
                  '@app.post("/api/admin/rules/reset")'):
        i = src.index(route)
        body = src[i:src.index('\n@app.', i + 10)]
        assert 'Depends(_checkAdminAuth)' in body, route
        if 'get' not in route:
            assert 'if _gamesLive():' in body, route
