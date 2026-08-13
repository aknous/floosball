"""A GM change has to reach the Season Recap, and say the true thing.

⚠️ NOTHING RECORDED THESE UNTIL 2026-08-13 and the entire reading half already
existed: `SeasonRecapEvent` documents `coach_fire | coach_hire` as valid types,
`src/types/recap.ts` declares them, and `SeasonRecap.tsx` renders a COACHING
CHANGES block that colors them red/green and prints "Fired"/"Hired".
`_recordOffseasonEvent` was never called with either, so the section rendered
nothing from the day it shipped — and because `announce()` returns null on an
empty list it looked ABSENT rather than broken, which is why it survived.

Fourth instance of this pattern in the codebase (the dead fantasy roster tables
account for three): a feature reading a source nothing writes.

⚠️ The labelling rule is the part worth protecting. The frontend prints
`coach_fire` as the literal word "Fired", so a retirement or a resignation routed
through that type would state something untrue about a person. Only a genuine
firing may use it; the other exits carry their reason in the hire line.

Run: .venv/bin/python test_coach_recap_events.py
"""

import logging

logging.disable(logging.CRITICAL)

from managers.teamManager import TeamManager


class Coach:
    def __init__(self, name, seasonsCoached=0):
        self.name = name
        self.seasonsCoached = seasonsCoached


class Team:
    def __init__(self, name, coach):
        self.id = 7
        self.name = name
        self.coach = coach


class RecordingSeasonManager:
    def __init__(self):
        self.events = []

    def _recordOffseasonEvent(self, eventType, **kw):
        self.events.append((eventType, kw.get('detail'), kw.get('team')))


class Container:
    def __init__(self, sm):
        self.sm = sm

    def getService(self, name):
        return self.sm if name == 'season_manager' else None


def _manager(sm):
    tm = TeamManager.__new__(TeamManager)
    tm.logger = logging.getLogger('test')
    tm.serviceContainer = Container(sm)
    return tm


def _run(exitKind, arriving=Coach('Bobbo Montblanc'), departing=('Invader Jim', 3)):
    sm = RecordingSeasonManager()
    tm = _manager(sm)
    team = Team('Broads', arriving)
    tm._recordCoachChange(team, exitKind, departing[0], departing[1])
    return sm.events


def test_a_firing_records_both_the_exit_and_the_arrival():
    events = _run('fired')
    types = [e[0] for e in events]
    assert types == ['coach_fire', 'coach_hire'], types
    assert 'Invader Jim' in events[0][1]
    assert 'after 3 seasons' in events[0][1], events[0][1]
    print(f"PASS a firing records both: 'Fired {events[0][1]}'")


def test_a_retirement_is_never_labelled_fired():
    """⚠️ THE RULE. The frontend prints coach_fire as 'Fired'. A GM who retired
    was not fired, and the recap must not say they were."""
    events = _run('retired')
    assert [e[0] for e in events] == ['coach_hire'], events
    assert '(retired)' in events[0][1], events[0][1]
    print(f"PASS a retirement records only a hire: 'Hired {events[0][1]}'")


def test_stepping_down_is_never_labelled_fired():
    events = _run('left')
    assert [e[0] for e in events] == ['coach_hire'], events
    assert '(stepped down)' in events[0][1], events[0][1]
    print(f"PASS stepping down records only a hire: 'Hired {events[0][1]}'")


def test_a_market_hire_shows_the_gm_s_prior_tenure():
    """The carousel is only legible if a reader can spot the GM they watched get
    fired turning up somewhere else."""
    events = _run('fired', arriving=Coach('Veteran GM', seasonsCoached=6))
    hire = [e for e in events if e[0] == 'coach_hire'][0]
    assert '6 prior seasons' in hire[1], hire[1]
    print(f"PASS a market hire shows tenure: 'Hired {hire[1]}'")


def test_a_first_time_gm_carries_no_tenure_clause():
    events = _run('fired', arriving=Coach('Rookie GM', seasonsCoached=0))
    hire = [e for e in events if e[0] == 'coach_hire'][0]
    assert hire[1] == 'Rookie GM', hire[1]
    print("PASS a first-time GM reads as just their name")


def test_one_season_is_singular():
    events = _run('fired', departing=('Brief Tenure', 1))
    assert 'after 1 season' in events[0][1] and 'seasons' not in events[0][1]
    print("PASS a single season is not pluralized")


def test_the_team_rides_along_so_the_recap_can_link_it():
    """SeasonRecap renders a TeamLink from teamId/teamName on every row."""
    events = _run('fired')
    for _type, _detail, team in events:
        assert team is not None and getattr(team, 'id', None) == 7
    print("PASS both events carry the club")


def test_a_missing_season_manager_does_not_break_the_offseason():
    """A recap line is never worth failing an offseason over."""
    tm = TeamManager.__new__(TeamManager)
    tm.logger = logging.getLogger('test')

    class Dead:
        def getService(self, name):
            raise RuntimeError('no container')
    tm.serviceContainer = Dead()
    tm._recordCoachChange(Team('Broads', Coach('X')), 'fired', 'Y', 2)
    print("PASS an unavailable recorder is survivable")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} coach recap tests passed.")
