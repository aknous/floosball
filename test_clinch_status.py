"""Clinching a berth, a division, and the top seed.

⚠️ THE ERROR DIRECTION IS THE WHOLE DESIGN. Clinch math that fires EARLY puts a
badge on a club and then takes it away, which reads as the table lying. Firing
LATE just means the badge shows up a week after the fact. So every test here
checks the conservative direction: the moment a rival can still catch you, you
are not clinched, whatever the tiebreakers would say.

⚠️ IT DOES NOT REUSE `leagueManager.checkPlayoffClinching`. That function is dead
code and would be wrong if revived: it takes the top half BY RECORD as the
playoff field, which stopped being true when divisions arrived — a division
winner is guaranteed a top-four seed regardless of record, so the field and the
record order are different sets. It also hardcodes a 28 game season and compares
raw WINS, which a club with ties can beat you on while holding fewer wins.

Run: .venv/bin/python test_clinch_status.py
"""

import logging

logging.disable(logging.CRITICAL)

from standings_view import clinchStatus, playoffSpots


class Team:
    def __init__(self, tid, wins, losses, ties=0, division=None):
        self.id = tid
        self.division = division
        self.seasonTeamStats = {'wins': wins, 'losses': losses, 'ties': ties}


def _league(records, divisions=None, size=16):
    """A league of `size` clubs; `records` sets the first few, the rest are 0-0."""
    teams = []
    for i in range(size):
        div = (divisions or {}).get(i)
        if i < len(records):
            w, l, *rest = records[i]
            teams.append(Team(i, w, l, rest[0] if rest else 0, div))
        else:
            teams.append(Team(i, 0, 0, 0, div))
    return teams


# ------------------------------------------------------------- playoff berth

def test_a_club_nobody_can_catch_has_clinched():
    """14-0 with 14 to play: the 8 berths cannot all be taken by clubs above it."""
    teams = _league([(14, 0)] + [(0, 14)] * 15)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedPlayoffs'] is True
    print("PASS an uncatchable club has clinched a berth")


def test_nobody_clinches_on_day_one():
    teams = _league([], size=16)
    status = clinchStatus(teams, totalGames=28)
    assert not any(s['clinchedPlayoffs'] for s in status.values())
    assert not any(s['eliminated'] for s in status.values())
    print("PASS an unplayed season clinches and eliminates nobody")


def test_it_fires_late_rather_than_early():
    """⚠️ THE DIRECTION THAT MATTERS. Exactly enough rivals can still pass, so the
    club is NOT clinched — even though the tiebreakers would almost certainly
    save it."""
    # 8 berths. This club is 8-6; eight rivals are 7-7 and can each finish above.
    teams = _league([(8, 6)] + [(7, 7)] * 8 + [(0, 14)] * 7)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedPlayoffs'] is False, \
        'clinched while eight clubs could still finish ahead'
    print("PASS a club with enough live rivals is not yet clinched")


def test_ties_cannot_sneak_past_a_win_count():
    """⚠️ A club can hold MORE WINS and a WORSE record than one with ties, so
    clinching off raw wins would claim a berth that is not secured."""
    # Leader 10-8-0 (10.0 pts). Rival 9-5-4 (11.0 pts) with 10 to play.
    leader = Team(0, 10, 8, 0)
    rival = Team(1, 9, 5, 4)
    teams = [leader, rival] + [Team(i, 0, 18, 0) for i in range(2, 16)]
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedTopSeed'] is False, \
        'a club with fewer points clinched the top seed on a raw win count'
    print("PASS ties are counted as half a win, not ignored")


def test_elimination_is_the_mirror():
    teams = _league([(0, 20)] + [(14, 6)] * 9 + [(10, 10)] * 6)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['eliminated'] is True
    assert status[1]['eliminated'] is False
    print("PASS a club that can no longer reach a berth is eliminated")


# ---------------------------------------------------------------- division

def test_a_division_is_won_when_no_rival_can_reach_you():
    divisions = {0: 'North', 1: 'North', 2: 'North', 3: 'North'}
    teams = _league([(20, 0), (5, 15), (5, 15), (5, 15)], divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is True
    assert status[1]['clinchedDivision'] is False
    print("PASS a division is clinched once no rival can reach the leader")


def test_a_division_rival_still_alive_blocks_it():
    divisions = {0: 'North', 1: 'North', 2: 'North', 3: 'North'}
    # Leader 14-4, rival 10-8 with 10 to play — the rival tops out at 20 to 14.
    teams = _league([(14, 4), (10, 8), (2, 16), (2, 16)], divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is False
    print("PASS a live division rival blocks the title")


def test_no_division_stamp_means_no_division_clinch():
    """Divisions are persisted but a league mid-migration may have none. Absent a
    division there is no title to win, and the badge must not appear."""
    teams = _league([(20, 0)] + [(0, 20)] * 15)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is False
    assert status[0]['clinchedTopSeed'] is False
    print("PASS an undivisioned league claims no division titles")


# ---------------------------------------------------------------- top seed

def test_the_top_seed_needs_the_division_too():
    """⚠️ Division winners take the top four seeds, so the best record in the
    league is NOT the 1 seed while its own division is unsettled — it could be
    seeded behind a winner it out-performed."""
    divisions = {0: 'North', 1: 'North', 2: 'South', 3: 'South'}
    # Best record in the league, but its own division rival is still live.
    teams = _league([(15, 3), (12, 6), (2, 16), (2, 16)], divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is False
    assert status[0]['clinchedTopSeed'] is False, \
        'claimed the top seed with its own division still in play'
    print("PASS the top seed waits on the division being settled")


def test_the_top_seed_when_everything_is_settled():
    divisions = {i: ('North' if i < 4 else 'South') for i in range(8)}
    teams = _league([(24, 0)] + [(2, 22)] * 15, divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is True
    assert status[0]['clinchedTopSeed'] is True
    assert status[0]['clinchedPlayoffs'] is True
    print("PASS an unchallenged leader clinches division, berth and top seed")


def test_only_one_club_can_clinch_the_top_seed():
    divisions = {i: ('North' if i < 4 else 'South') for i in range(16)}
    teams = _league([(24, 0), (20, 4)] + [(2, 22)] * 14, divisions)
    status = clinchStatus(teams, totalGames=28)
    tops = [tid for tid, s in status.items() if s['clinchedTopSeed']]
    assert len(tops) <= 1, tops
    print("PASS at most one club holds the top seed")


def test_spots_track_league_size():
    assert playoffSpots(16) == 8
    assert playoffSpots(12) == 6
    print("PASS berths are half the league, whatever its size")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in tests:
        fn()
    print(f"\nAll {len(tests)} clinch tests passed.")
