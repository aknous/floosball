"""Regression: a HoF-ballot candidate who is no longer retiring (willRetire
reverted, or re-signed in FA) must NOT be inducted while active, and must be
dropped from the ballot. A genuine retiree is still inducted.

Reproduces the Chili Arthur bug (inducted into the HoF while an active Pinecone
after a longevity-retune script reverted his willRetire)."""
import logging
logging.disable(logging.CRITICAL)

from floosball_player import PlayerServiceTime
from managers.awardsManager import AwardsManager


class FakePlayer:
    def __init__(self, pid, name, *, willRetire=False, retired=False, pts=50):
        self.id = pid
        self.name = name
        self.willRetire = willRetire
        self.serviceTime = PlayerServiceTime.Retired if retired else PlayerServiceTime.Veteran2
        self.is_hof = False
        self.hof_season = None
        self.previousTeam = 'TST'
        self._pts = pts


class Entry:
    def __init__(self, pid, pts_season=11):
        self.player_id = pid
        self.status = 'on_ballot'
        self.seasons_remaining = 4
        self.first_eligible_season = pts_season
        self.inducted_season = None


class FakeBallotRepo:
    def __init__(self, entries):
        self.entries = {e.player_id: e for e in entries}
    def getActive(self):
        return [e for e in self.entries.values() if e.status == 'on_ballot']
    def getEntry(self, pid):
        return self.entries.get(pid)
    def markInducted(self, pid, season):
        e = self.entries.get(pid)
        if e: e.status, e.inducted_season = 'inducted', season
    def markDropped(self, pid):
        e = self.entries.get(pid)
        if e and e.status == 'on_ballot':
            e.status = 'dropped'; return True
        return False
    def decrementAndDrop(self):
        for e in self.getActive():
            e.seasons_remaining -= 1
            if e.seasons_remaining <= 0: e.status = 'dropped'
        return []


class FakeVoteRepo:
    def getVoterCount(self, season, kind): return 0     # below quorum → slam-dunk path
    def getTally(self, season, kind): return {}


class FakePM:
    def __init__(self, players):
        self.players = {p.id: p for p in players}
        self.hallOfFame = []
        self.serviceContainer = None
    def getPlayerById(self, pid): return self.players.get(pid)
    def _computeHofPoints(self, player):
        return (getattr(player, '_pts', 0), {}) if player is not None else (0, {})


def run():
    # Two slam-dunk-pointed (>=40) candidates: one active (reverted willRetire),
    # one genuinely retired.
    active = FakePlayer(145, 'Chili Arthur', willRetire=False, retired=False, pts=50)
    retired = FakePlayer(200, 'Real Retiree', willRetire=True, retired=True, pts=50)
    pm = FakePM([active, retired])
    am = AwardsManager(session=None, playerManager=pm)
    am.voteRepo = FakeVoteRepo()
    am.ballotRepo = FakeBallotRepo([Entry(145), Entry(200)])

    inducted = am.resolveHofInductions(season=12)

    ok = True
    # 1. Active player NOT inducted
    if 145 in inducted or active.is_hof:
        print("FAIL: active player Chili Arthur was inducted"); ok = False
    # 2. Active player's ballot entry dropped
    if am.ballotRepo.getEntry(145).status != 'dropped':
        print(f"FAIL: active player's entry status = {am.ballotRepo.getEntry(145).status}, expected dropped"); ok = False
    # 3. Genuine retiree inducted
    if 200 not in inducted or not retired.is_hof:
        print("FAIL: genuine retiree was NOT inducted"); ok = False
    if retired.hof_season != 12:
        print(f"FAIL: retiree hof_season = {retired.hof_season}"); ok = False

    # 4. Defense-in-depth: _induct refuses an active player directly.
    lone = FakePlayer(300, 'Sneaky Active', willRetire=False, retired=False, pts=99)
    pm.players[300] = lone
    am.ballotRepo.entries[300] = Entry(300)
    am._induct(lone, 300, 12)
    if lone.is_hof:
        print("FAIL: _induct stamped is_hof on an active player"); ok = False

    print("PASS: active candidates dropped & never inducted; retiree inducted" if ok else "TEST FAILED")
    return ok


def run_repo():
    """The ballot repo must reactivate a DROPPED entry (a candidate pulled for
    going active who later retires for real) but never re-open an INDUCTED one."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base
    from database.repositories.award_repository import HofBallotRepository

    eng = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    repo = HofBallotRepository(s)
    ok = True

    e = repo.addEntry(99, 5, 5)
    if not (e and e.status == 'on_ballot'): print("FAIL: initial addEntry"); ok = False
    if repo.addEntry(99, 6, 5) is not None: print("FAIL: re-add of on_ballot should be None"); ok = False
    if not repo.markDropped(99): print("FAIL: markDropped"); ok = False
    if repo.getEntry(99).status != 'dropped': print("FAIL: status not dropped"); ok = False

    e2 = repo.addEntry(99, 8, 5)   # retires for real later → reactivate
    if not (e2 and e2.status == 'on_ballot' and e2.first_eligible_season == 8
            and e2.seasons_remaining == 5 and e2.inducted_season is None):
        print(f"FAIL: dropped entry not reactivated: {e2 and (e2.status, e2.first_eligible_season)}"); ok = False

    repo.markInducted(99, 8)
    if repo.addEntry(99, 9, 5) is not None:
        print("FAIL: inducted entry must NOT be reactivated"); ok = False

    print("PASS: ballot repo reactivates dropped, never inducted" if ok else "REPO TEST FAILED")
    return ok


if __name__ == '__main__':
    import sys
    sys.exit(0 if (run() and run_repo()) else 1)
