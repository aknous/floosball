"""Exactly one team is the reigning champion, and it is the latest Floos Bowl winner.

Reported on prod: the previous champions (Strangers) still read "Champions" on their
team page after being eliminated in the playoffs. `floosbowlChampion` means REIGNING
champion and is set on last season's winner at season start. Two backend faults kept it
wrong: crowning a new champion never cleared the old one, and a restart after the Bowl
re-crowned LAST season's winner. (The team page also checked it before `eliminated`.)

Run: .venv/bin/python test_reigning_champion.py
"""

import os
import sys
import types
import logging
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

import managers.seasonManager as SM  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, season_number):
        self.season = season_number
        return self

    def first(self):
        return self.rows.get(self.season)


def _manager(champions):
    teams = [types.SimpleNamespace(id=i, city='C', name=f'T{i}', floosbowlChampion=False)
             for i in range(1, 5)]
    tm = types.SimpleNamespace(teams=teams, getTeamById=lambda i: next((t for t in teams if t.id == i), None))
    rows = {s: types.SimpleNamespace(champion_team_id=tid) for s, tid in champions.items()}
    sm = SM.SeasonManager.__new__(SM.SeasonManager)
    sm.db_session = types.SimpleNamespace(query=lambda model: _Query(rows))
    sm.serviceContainer = types.SimpleNamespace(getService=lambda name: tm)
    return sm, teams


class ReigningChampionTest(unittest.TestCase):
    def setUp(self):
        self._saved = (SM.DB_IMPORTS_AVAILABLE, SM.USE_DATABASE)
        SM.DB_IMPORTS_AVAILABLE, SM.USE_DATABASE = True, True

    def tearDown(self):
        SM.DB_IMPORTS_AVAILABLE, SM.USE_DATABASE = self._saved

    def test_before_the_bowl_last_seasons_winner_reigns(self):
        sm, teams = _manager({6: 1})
        sm._restoreReigningChampion(7)
        self.assertEqual([t.id for t in teams if t.floosbowlChampion], [1])

    def test_after_the_bowl_this_seasons_winner_reigns_alone(self):
        sm, teams = _manager({6: 1, 7: 3})
        teams[0].floosbowlChampion = True           # left over from season start
        sm._restoreReigningChampion(7)
        self.assertEqual([t.id for t in teams if t.floosbowlChampion], [3])

    def test_crowning_clears_the_old_champion(self):
        src = open(os.path.join(HERE, 'managers', 'seasonManager.py')).read()
        i = src.index('game.winningTeam.floosbowlChampion = True')
        self.assertIn('_t.floosbowlChampion = False', src[i - 900:i])


if __name__ == '__main__':
    unittest.main(verbosity=2)
