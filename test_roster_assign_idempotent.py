"""Placing a team's players on its roster twice must not duplicate anyone.

Prod, season 8 offseason: at boot `teamManager._rebuildTeamRosters` fills the rosters and
`playerManager.assignPlayersToTeams` then places every player again. A team with ONE
receiver had him in `wr1`, so the second pass put him in `wr2` as well: ten teams showed
the same WR in both slots, and the FA draft (which only fills empty slots) would never
have signed them a second one.

Run: .venv/bin/python -m pytest -q test_roster_assign_idempotent.py
"""
import types

import managers.playerManager as PM
from floosball_player import Position


def _player(pid, pos, team):
    return types.SimpleNamespace(id=pid, name=f'P{pid}', position=pos, team=team,
                                 term=2, termRemaining=2, is_prospect=False,
                                 is_upcoming_rookie=False)


def _setup():
    team = types.SimpleNamespace(id=20, name='Midnights',
                                 rosterDict={'qb': None, 'rb': None, 'wr1': None, 'wr2': None,
                                             'te': None, 'k': None})
    players = [_player(1, Position.QB, 20), _player(2, Position.WR, 20), _player(3, Position.TE, 20)]
    pm = PM.PlayerManager.__new__(PM.PlayerManager)
    pm.activePlayers = players
    pm.freeAgents = []
    pm.db_session = None
    tm = types.SimpleNamespace(teams=[team])
    pm.serviceContainer = types.SimpleNamespace(getService=lambda name: tm)
    return pm, team, players


def test_a_lone_receiver_fills_one_slot_however_many_times_rosters_are_placed():
    pm, team, players = _setup()
    pm.assignPlayersToTeams()
    pm.assignPlayersToTeams()
    assert team.rosterDict['wr1'] is players[1]
    assert team.rosterDict['wr2'] is None, "the same receiver went into both WR slots"
    assert team.rosterDict['qb'] is players[0] and team.rosterDict['te'] is players[2]


def test_two_receivers_still_fill_both_slots():
    pm, team, players = _setup()
    second = _player(4, Position.WR, 20)
    pm.activePlayers.append(second)
    pm.assignPlayersToTeams()
    pm.assignPlayersToTeams()
    slots = [team.rosterDict['wr1'], team.rosterDict['wr2']]
    assert slots == [players[1], second] or slots == [second, players[1]]


if __name__ == '__main__':
    import sys, pytest
    sys.exit(pytest.main(['-q', __file__]))
