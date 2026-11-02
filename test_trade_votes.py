"""Fan approval votes on trades (managers/tradeVotes.py, owner 2026-10-30).

The rule (`verdict`), the per-team fan bar, a proposal stored and settled later against
the live rosters with the right phase arguments, a team in an open proposal kept out of
the next one, the after-FA-draft settlement filling the seller's hole, and the trade
passes reading the admin switch instead of the constant."""
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

# Import AFTER DATABASE_DIR is set so the engine points at the temp DB.
_tmp = tempfile.mkdtemp(prefix='floos_tradevotes_')
os.environ['DATABASE_DIR'] = _tmp

from database.connection import init_db, get_session                 # noqa: E402
from database.models import User, TradeProposal, TradeVote            # noqa: E402
from managers import tradeVotes, tradeManager                         # noqa: E402
from managers.tradeManager import Listing, Bid                        # noqa: E402

init_db()

A, B, C = 1, 2, 3


class FanBarTests(unittest.TestCase):
    def testScalesWithTheFanbase(self):
        self.assertEqual([tradeVotes.fanBar(n) for n in (0, 1, 3, 6, 14)], [0, 1, 2, 3, 5])


class VerdictTests(unittest.TestCase):
    def v(self, votes, fans):
        return tradeVotes.verdict(A, B, votes, fans)

    def testNoVotesFails(self):
        r = self.v([], {A: 2, B: 2})
        self.assertFalse(r['passed'])
        self.assertEqual(r['reason'], 'no_votes')

    def testBothBarsAndALeagueMajorityPass(self):
        r = self.v([(A, True), (B, True), (None, False)], {A: 1, B: 3})
        self.assertFalse(r['passed'])                     # B has 3 fans: needs 2 yes
        r = self.v([(A, True), (B, True), (B, True), (None, False)], {A: 1, B: 3})
        self.assertTrue(r['passed'])

    def testOwnFansCanVeto(self):
        # League-wide 4-2 yes, but B's own fans vote it down 2-1.
        votes = [(A, True), (None, True), (None, True), (B, True), (B, False), (B, False)]
        r = self.v(votes, {A: 1, B: 3})
        self.assertFalse(r['passed'])
        self.assertEqual(r['reason'], 'team_veto')

    def testFanlessTeamFallsToAnyone(self):
        # Neither team has fans: one yes from anyone passes it.
        self.assertTrue(self.v([(C, True)], {})['passed'])
        # A has fans, B has none: A's bar plus the league majority is enough.
        self.assertTrue(self.v([(A, True)], {A: 1})['passed'])

    def testLeagueCanVoteItDown(self):
        r = self.v([(A, True), (B, True), (C, False), (C, False), (None, False)], {A: 1, B: 1})
        self.assertFalse(r['passed'])
        self.assertEqual(r['reason'], 'league_no')

    def testATieFails(self):
        self.assertFalse(self.v([(A, True), (C, False)], {A: 1})['passed'])


def _player(pid, pos='QB'):
    return SimpleNamespace(id=pid, name=f"P{pid}", position=SimpleNamespace(name=pos, value=1),
                           team=None, playerRating=80)


def _team(tid, roster):
    return SimpleNamespace(id=tid, name=f"Team{tid}", abbr=f"T{tid}", rosterDict=roster,
                           prospects=[])


class ProposalLifecycleTests(unittest.TestCase):
    def setUp(self):
        s = get_session()
        try:
            for model in (TradeVote, TradeProposal):
                s.query(model).delete()
            s.query(User).delete()
            s.commit()
        finally:
            s.close()
        self.seller = _team(A, {'qb': _player(101)})
        self.buyer = _team(B, {'qb': _player(201)})
        self.other = _team(C, {'qb': _player(301)})
        tm = SimpleNamespace(teams=[self.seller, self.buyer, self.other])
        self.sm = SimpleNamespace(serviceContainer=SimpleNamespace(getService=lambda k: tm))
        self.calls = []

        self.settleable = True
        self.dryRuns = []

        def fakeSettle(sm, entry, season, week, fillHoles=None, dryRun=False):
            if dryRun:
                self.dryRuns.append((entry['listing'].player.id, week, fillHoles))
                return self.settleable
            self.calls.append((entry['listing'].player.id, season, week, fillHoles))
            return {'tradeId': 77}
        self._real = tradeVotes.settleEntry
        tradeVotes.settleEntry = fakeSettle

    def tearDown(self):
        tradeVotes.settleEntry = self._real

    def entry(self, seller, buyer):
        listing = Listing(seller, seller.rosterDict['qb'], 'expiring_surplus', 5.0, 3.0,
                          why='selling')
        bid = Bid(buyer, [{'kind': 'pick', 'id': 9, 'name': 'S2 R1 pick', 'detail': 'slot 4',
                           'value': 5.5}], 5.5, why='buying')
        return {'listing': listing, 'winner': bid}

    def addFans(self, teamId, n, start, lastLogin='now'):
        seen = {'now': datetime.utcnow(), 'gone': datetime.utcnow() - timedelta(days=60),
                'never': None}[lastLogin]
        s = get_session()
        try:
            ids = []
            for i in range(n):
                u = User(username=f"u{start + i}", email=f"u{start + i}@x.test",
                         favorite_team_id=teamId, last_login_at=seen)
                s.add(u)
                s.flush()
                ids.append(u.id)
            s.commit()
            return ids
        finally:
            s.close()

    def vote(self, proposalId, userIds, approve=True):
        s = get_session()
        try:
            for uid in userIds:
                s.add(TradeVote(proposal_id=proposalId, user_id=uid, approve=approve))
            s.commit()
        finally:
            s.close()

    def testAProposalSettlesLaterWithTheRightPhase(self):
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, 16,
                                  tradeVotes.PHASE_IN_SEASON, tradeVotes.CLOSE_DEADLINE)
        self.assertEqual(len(made), 1)
        self.assertEqual(tradeVotes.openTeamIds(), {A, B})
        self.vote(made[0]['id'], self.addFans(A, 1, 0) + self.addFans(B, 1, 10))
        out = tradeVotes.resolve(self.sm, tradeVotes.CLOSE_DEADLINE)
        self.assertEqual([o['status'] for o in out], ['approved'])
        self.assertEqual(self.calls, [(101, 5, 16, None)])   # in season: settled as week 16
        self.assertEqual(tradeVotes.openTeamIds(), set())
        s = get_session()
        try:
            self.assertEqual(s.get(TradeProposal, made[0]['id']).trade_id, 77)
        finally:
            s.close()

    def testWithoutEnoughFanApprovalsItFails(self):
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, None,
                                  tradeVotes.PHASE_OFFSEASON, tradeVotes.CLOSE_ROOKIE_DRAFT)
        self.addFans(B, 3, 20)
        self.vote(made[0]['id'], self.addFans(A, 1, 0))      # B's fans never vote
        out = tradeVotes.resolve(self.sm, tradeVotes.CLOSE_ROOKIE_DRAFT)
        self.assertEqual([o['status'] for o in out], ['rejected'])
        self.assertEqual(self.calls, [])

    def testOnlyActiveFansSetTheBar(self):
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, None,
                                  tradeVotes.PHASE_OFFSEASON, tradeVotes.CLOSE_ROOKIE_DRAFT)
        # B has 6 fans, but 5 have not signed in for two months: its bar is 1, not 2.
        self.addFans(B, 5, 50, lastLogin='gone')
        b = self.addFans(B, 1, 60)
        self.vote(made[0]['id'], self.addFans(A, 1, 70) + b)
        s = get_session()
        try:
            t = tradeVotes.tally(s, s.get(TradeProposal, made[0]['id']))
        finally:
            s.close()
        self.assertEqual((t['teams'][B]['fans'], t['teams'][B]['need']), (1, 1))
        self.assertTrue(t['passed'])

    def testAVoterCountsAsActiveAndLapsedFansLeaveATeamFanless(self):
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, None,
                                  tradeVotes.PHASE_OFFSEASON, tradeVotes.CLOSE_ROOKIE_DRAFT)
        self.addFans(B, 3, 80, lastLogin='never')               # B: fanless for the vote
        self.vote(made[0]['id'], self.addFans(A, 1, 90, lastLogin='gone'))   # a voter
        s = get_session()
        try:
            t = tradeVotes.tally(s, s.get(TradeProposal, made[0]['id']))
        finally:
            s.close()
        self.assertEqual(t['teams'][A]['fans'], 1)
        self.assertEqual(t['teams'][B]['fans'], 0)
        self.assertTrue(t['passed'])

    def testOnlyTheClosingKindResolves(self):
        tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, None,
                           tradeVotes.PHASE_POST_FA, tradeVotes.CLOSE_SEASON_START)
        self.assertEqual(tradeVotes.resolve(self.sm, tradeVotes.CLOSE_ROOKIE_DRAFT), [])

    def testAfterTheFaDraftTheSellerFillsItsHole(self):
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, None,
                                  tradeVotes.PHASE_POST_FA, tradeVotes.CLOSE_SEASON_START)
        self.vote(made[0]['id'], self.addFans(C, 1, 30))     # both teams fanless
        tradeVotes.resolve(self.sm, tradeVotes.CLOSE_SEASON_START)
        self.assertEqual(self.calls, [(101, 5, None, True)])

    def testATeamWithAnOpenVoteSitsOut(self):
        tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, 15,
                           tradeVotes.PHASE_IN_SEASON, tradeVotes.CLOSE_DEADLINE)
        later = tradeVotes.propose(self.sm, [self.entry(self.other, self.buyer)], 5, 16,
                                   tradeVotes.PHASE_IN_SEASON, tradeVotes.CLOSE_DEADLINE)
        self.assertEqual(later, [])

    def testATradeThatCouldNotSettleNeverGoesToAVote(self):
        self.settleable = None
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, None,
                                  tradeVotes.PHASE_POST_FA, tradeVotes.CLOSE_SEASON_START)
        self.assertEqual(made, [])
        # Checked the way it would settle: offseason pricing, holes filled on the spot.
        self.assertEqual(self.dryRuns, [(101, None, True)])
        self.assertEqual(tradeVotes.openTeamIds(), set())

    def testAPlayerWhoMovedFailsInsteadOfSettling(self):
        made = tradeVotes.propose(self.sm, [self.entry(self.seller, self.buyer)], 5, 16,
                                  tradeVotes.PHASE_IN_SEASON, tradeVotes.CLOSE_DEADLINE)
        self.vote(made[0]['id'], self.addFans(C, 1, 40))
        self.seller.rosterDict['qb'] = _player(102)
        out = tradeVotes.resolve(self.sm, tradeVotes.CLOSE_DEADLINE)
        self.assertEqual([o['status'] for o in out], ['failed'])
        self.assertEqual(self.calls, [])


class BackfillTests(unittest.TestCase):
    def testTheOffseasonLeavesTheHoleUnlessToldToFillIt(self):
        fa = _player(900)
        fa.team = 'Free Agent'
        sm = SimpleNamespace(playerManager=SimpleNamespace(freeAgents=[fa]))
        team = _team(A, {})
        leaving = _player(101)
        self.assertIsNone(tradeManager._findBackfill(sm, team, leaving, week=None))
        self.assertEqual(tradeManager._findBackfill(sm, team, leaving, week=None,
                                                    allowSigning=True), ('freeAgent', fa))


class SwitchTests(unittest.TestCase):
    def testTradePassesReadTheAdminSwitch(self):
        src = open(os.path.join(os.path.dirname(__file__), 'managers', 'seasonManager.py')).read()
        self.assertIsNone(re.search(r'import[^\n]*\bTRADING_ENABLED\b', src))


if __name__ == '__main__':
    unittest.main()
