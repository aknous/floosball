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

from standings_view import clinchStatus, playoffSpots, seedLeague


class Team:
    def __init__(self, tid, wins, losses, ties=0, division=None):
        self.id = tid
        self.division = division
        # ⚠️ `winPerc` IS REQUIRED. `seeding._baseKey` sorts on it, so a fixture
        # without it gives every club 0 and the whole league ties — which silently
        # seeded 2-26 clubs ahead of 19-9 ones and made a regression test look like
        # a bug in the code under test.
        played = wins + losses + ties
        self.seasonTeamStats = {
            'wins': wins, 'losses': losses, 'ties': ties,
            'winPerc': ((wins + 0.5 * ties) / played) if played else 0.0,
        }


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
    """Uncatchable means no rival can even DRAW LEVEL, not merely that few sit above it.

    ⚠️ This was 14-0 against 0-14 with fourteen games left, where every rival winning out
    finishes 14-14 and TIES — all eight berths then go to tiebreakers and this club can
    genuinely miss. That is the third fixture in this suite to treat a reachable tie as a
    settled lead, and the live version of the same mistake put a wildcard badge on a club
    that was out of the playoffs a week later. Six games left, floor of 20 against a
    ceiling of 6.
    """
    teams = _league([(20, 2)] + [(0, 22)] * 15)
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
    division there is no title to win, and that badge must not appear.

    ⚠️ The TOP SEED still can be clinched though: with no division winners there is
    nobody who can be seeded above this club on a guarantee, so an uncatchable
    record IS the 1 seed. The old rule required a division clinch and so could
    never award it here, which was a limitation of the record-count test rather
    than a fact about the league."""
    teams = _league([(20, 0)] + [(0, 20)] * 15)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is False
    assert status[0]['clinchedTopSeed'] is True
    assert status[0]['clinchedPlayoffs'] is True
    print("PASS an undivisioned league claims no division titles, but does seed")


def test_winning_the_division_auto_clinches_the_berth():
    """⚠️ A division winner takes a GUARANTEED top-four seed, so the berth does not
    depend on the record race. This club wins a weak division while plenty of
    league rivals could still finish above it on record — it is in anyway."""
    divisions = {i: ('North' if i < 4 else ('South' if i < 8 else
                     ('East' if i < 12 else 'West'))) for i in range(16)}
    # North is settled: leader 10-8, rivals buried. Everyone OUTSIDE North is
    # 14-4 and could finish above the leader on record.
    # ⚠️ North must be settled BEYOND A TIE. This was 10-8 against 0-18 with ten games
    # left, where a rival winning out reaches 10 and the leader losing out stays at 10 —
    # level, and a level finish goes to a tiebreak the leader can lose. Twenty games in,
    # the rivals top out at 8 against a floor of 12.
    records = [(12, 8), (0, 20), (0, 20), (0, 20)] + [(14, 4)] * 12
    teams = _league(records, divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is True
    assert status[0]['clinchedPlayoffs'] is True, \
        'a division winner must be in the field regardless of the record race'
    print("PASS winning the division auto-clinches a berth")


def test_a_division_winner_is_never_eliminated():
    """⚠️ REPORTED FROM THE LIVE BOARD: a club that had WON ITS DIVISION was greyed
    out as eliminated, because its record was poor enough that `spots` rivals sat
    above it. That is precisely what a guaranteed division seed exists to prevent.
    The mirror of the auto-clinch, and it was missed alongside it."""
    divisions = {i: ('North' if i < 4 else ('South' if i < 8 else
                     ('East' if i < 12 else 'West'))) for i in range(16)}
    # A weak North: leader 6-16 but its rivals are buried and cannot reach it.
    # Everyone outside North is 18-4 and far beyond the leader's ceiling.
    # ⚠️ Buried beyond a TIE, not merely behind: four games left puts the rivals'
    # ceiling at 4 against a floor of 8. It was 6-16 against 0-22, where a rival
    # winning out reached exactly 6 and could draw level.
    records = [(8, 16), (0, 24), (0, 24), (0, 24)] + [(18, 4)] * 12
    teams = _league(records, divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['clinchedDivision'] is True
    assert status[0]['eliminated'] is False, \
        'a division winner was eliminated on record'
    assert status[0]['clinchedPlayoffs'] is True
    print("PASS a division winner is never eliminated")


def test_a_live_division_race_keeps_a_club_alive():
    """Not yet won, but still winnable: the club is far down the league table and
    cannot wildcard in, yet the division is a road and it is not out."""
    divisions = {i: ('North' if i < 4 else ('South' if i < 8 else
                     ('East' if i < 12 else 'West'))) for i in range(16)}
    # North is a two-way race at 6-16 and 7-15; the rest of the league is 18-4.
    records = [(6, 16), (7, 15), (0, 22), (0, 22)] + [(18, 4)] * 12
    teams = _league(records, divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['eliminated'] is False, \
        'eliminated while its division was still winnable'
    print("PASS a winnable division keeps a club alive")


def test_losing_the_division_and_the_wildcard_is_elimination():
    """Both roads gone: a division rival is out of reach AND the field is full."""
    divisions = {i: ('North' if i < 4 else ('South' if i < 8 else
                     ('East' if i < 12 else 'West'))) for i in range(16)}
    # This club is 0-26 with 2 to play; its own division rival is 20-6.
    records = [(0, 26), (20, 6), (20, 6), (20, 6)] + [(18, 8)] * 12
    teams = _league(records, divisions)
    status = clinchStatus(teams, totalGames=28)
    assert status[0]['eliminated'] is True
    print("PASS losing both roads is elimination")


def test_a_division_winner_takes_a_berth_from_a_better_record():
    """⚠️ REPORTED FROM THE LIVE BOARD. Counting "clubs above me on record" misses
    that a DIVISION WINNER holds a guaranteed top-four seed with any record at all,
    so it occupies a berth without ever appearing above you in the table.

    Measured on production: BOS, DET and PHI all finished 14-14 with only seven
    clubs holding more points, so a `canPassMe < spots` test read all three as
    CLINCHED — while 13-15 MIN had won its division, taken seed 4, and pushed them
    out of the field entirely."""
    divisions = {i: ('North' if i < 4 else ('South' if i < 8 else
                     ('East' if i < 12 else 'West'))) for i in range(16)}
    # North's winner is 13-15. Seven clubs are better than the 14-14 pack.
    records = [(13, 15), (2, 26), (2, 26), (2, 26)]      # North: weak winner
    records += [(20, 8), (19, 9), (18, 10), (18, 10)]    # South: strong
    records += [(16, 12), (15, 13), (15, 13), (14, 14)]  # East
    records += [(14, 14), (14, 14), (12, 16), (11, 17)]  # West
    teams = _league(records, divisions)
    status = clinchStatus(teams, totalGames=28)

    assert status[0]['clinchedDivision'] is True, 'the weak division winner'
    assert status[0]['clinchedPlayoffs'] is True, 'a division winner is in the field'

    # A 14-14 club outside the field must NOT read as clinched.
    seeded = seedLeague(teams)['seeds']
    for tid, st in status.items():
        if tid not in seeded:
            assert st['clinchedPlayoffs'] is False, \
                f'team {tid} is not seeded yet reads as clinched'
    print("PASS a division winner takes a berth from better records")


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
