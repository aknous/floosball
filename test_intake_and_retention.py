"""Intake has a top end, free agency has an exit, and a club cannot keep a player forever.

Three levers that arrived together because they answer one measurement: over five
simulated seasons the league's 85+ population fell 47 -> 22 while every retiree was
replaced on schedule. Attrition was fine; the REPLACEMENTS had no top end.

⚠️ CLASS SIZE IS NOT AVAILABLE AS A LEVER and that is the whole reason the blue chip
exists. `ensurePositionSupply` fills a DEFICIT against fixed 32x6 rosters, so the class
size IS the retirement count. Raising ROSTER_SUPPLY_BUFFER_PER_POSITION does not make a
bigger class, it makes a deeper pool of players nobody signs.

Run: .venv/bin/python test_intake_and_retention.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import constants
from managers.playerManager import PlayerManager
import floosball_player as FloosPlayer
from player_development import PlayerDevelopment


def bareManager():
    """A PlayerManager with just enough wired for generation. Avoids booting the app;
    generation touches names and the three collections and nothing else."""
    pm = PlayerManager.__new__(PlayerManager)
    pm.activePlayers = []
    pm.freeAgents = []
    # `addToPositionList` writes into these; without them the injection raises.
    pm.activeQbs, pm.activeRbs, pm.activeWrs = [], [], []
    pm.activeTes, pm.activeKs = [], []
    pm.unusedNames = [f"Blue Chip{i}" for i in range(4000)]
    pm.db_session = None
    return pm


class FakeAttrs:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class FakePlayer:
    def __init__(self, years=0, drive=74):
        self.freeAgentYears = years
        self.attributes = FakeAttrs(discipline=drive, focus=drive,
                                    resilience=drive, selfBelief=drive)


class BlueChipTests(unittest.TestCase):

    def setUp(self):
        self.pm = bareManager()

    def makeClass(self, n, seed=78):
        out = []
        for _ in range(n):
            p = self.pm.createPlayer(FloosPlayer.Position.QB, seed, seed)
            if p:
                out.append(p)
        return out

    def testAWeakClassGetsATopEnd(self):
        players = self.makeClass(8, seed=70)     # deliberately poor seeds
        self.assertTrue(players, "generation produced nothing")
        self.assertLess(max(p.playerRating for p in players),
                        constants.BLUE_CHIP_RATING_FLOOR,
                        "the fixture was supposed to start below the floor")
        self.pm._promoteBlueChip(players)
        self.assertGreaterEqual(max(p.playerRating for p in players),
                                constants.BLUE_CHIP_RATING_FLOOR,
                                "no blue chip was produced")

    def testItReplacesRatherThanAdds(self):
        """⚠️ The load-bearing property. An added player puts the pool above its target
        depth, and a player above target is one nobody signs."""
        players = self.makeClass(8, seed=70)
        before = len(players)
        self.pm._promoteBlueChip(players)
        self.assertEqual(before, len(players), "the class changed size")

    def testItPromotesTheBestNotARandomOne(self):
        players = self.makeClass(8, seed=70)
        best = max(players, key=lambda p: p.playerRating)
        others = {id(p): p.playerRating for p in players if p is not best}
        self.pm._promoteBlueChip(players)
        for p in players:
            if p is not best:
                self.assertEqual(others[id(p)], p.playerRating,
                                 "a player other than the best was altered")

    def testAStrongClassIsLeftAlone(self):
        """A floor, not a quota: in a good year it must do nothing."""
        players = self.makeClass(8, seed=96)
        if max(p.playerRating for p in players) < constants.BLUE_CHIP_RATING_FLOOR:
            self.skipTest("seed 96 did not clear the floor; nothing to assert")
        snapshot = [p.playerRating for p in players]
        self.pm._promoteBlueChip(players)
        self.assertEqual(snapshot, [p.playerRating for p in players],
                         "a class that already had a top end was modified")

    def testTheFlagTurnsItOff(self):
        players = self.makeClass(8, seed=70)
        snapshot = [p.playerRating for p in players]
        original = constants.BLUE_CHIP_ENABLED
        constants.BLUE_CHIP_ENABLED = False
        try:
            self.pm._promoteBlueChip(players)
            self.assertEqual(snapshot, [p.playerRating for p in players])
        finally:
            constants.BLUE_CHIP_ENABLED = original

    def testAnEmptyClassIsSafe(self):
        self.assertEqual({}, self.pm._promoteBlueChip([]))

    def testTheKeptPlayerIsTheSameObject(self):
        """It must mutate in place: the player is already registered in freeAgents,
        activePlayers and the position lists, and holds a name drawn from the pool."""
        players = self.makeClass(8, seed=70)
        best = max(players, key=lambda p: p.playerRating)
        name = best.name
        self.pm._promoteBlueChip(players)
        self.assertIn(best, players, "the promoted player was swapped for a new object")
        self.assertEqual(name, best.name, "promotion drew a second name from the pool")


class FreeAgentDevelopmentTests(unittest.TestCase):

    def testUnsignedYearsRaiseTheBias(self):
        fresh = PlayerDevelopment.selfDevelopmentBias(FakePlayer(years=0))
        stuck = PlayerDevelopment.selfDevelopmentBias(FakePlayer(years=3))
        self.assertGreater(stuck, fresh,
                           "a player stuck in the pool develops no faster than a new one")

    def testTheBonusIsCapped(self):
        """⚠️ Uncapped, a player could train out of the pool into stardom, which beats
        being coached and makes going unsigned the better career move."""
        capped = PlayerDevelopment.selfDevelopmentBias(FakePlayer(years=99))
        atCap = PlayerDevelopment.selfDevelopmentBias(
            FakePlayer(years=constants.FA_SELF_DEV_YEARS_CAP))
        self.assertEqual(atCap, capped, "the unsigned-years bonus is not capped")

    def testNeverNegative(self):
        """Sitting in the pool is stagnation at worst, never decay."""
        for drive in (0, 40, 60, 100):
            p = FakePlayer(years=0, drive=drive)
            self.assertGreaterEqual(PlayerDevelopment.selfDevelopmentBias(p),
                                    constants.FA_SELF_DEV_MIN)

    def testItStaysBelowAGoodCoach(self):
        """The road back must be real without beating actual coaching, or a GM's
        development staff stops mattering."""
        best = PlayerDevelopment.selfDevelopmentBias(FakePlayer(years=99, drive=100))
        eliteCoach = round((100 - 60) / 10)      # the coached formula, dev 100
        self.assertLessEqual(best, eliteCoach,
                             "an unsigned player can out-develop an elite coach")


class ResignLimitTests(unittest.TestCase):
    """⚠️ TRIED AT 2 AND REVERTED ON MEASUREMENT. The sizing was right (14 forced walks
    against 99 at a limit of 1) and the cap demonstrably bound in the sim, but over
    three 5-season arms the BOTTOM of the league got worse: worst record 6.3 -> 3.7 with
    non-overlapping run ranges, and the win spread widened. The forced walks land on 14
    different teams including the two weakest, and a 76 is a starter for a weak club and
    depth for a strong one — so uniform circulation costs the bottom more."""

    def testItIsOff(self):
        self.assertFalse(constants.RESIGN_ONCE_ENABLED,
                         "re-enabling this needs a measurement showing the bottom of "
                         "the league is not made worse; the last one showed it was")

    def testTheReaderStillHonoursTheLimitWhenOn(self):
        """The machinery stays intact so re-enabling is one flag, not a rebuild."""
        pm = bareManager()
        original = constants.RESIGN_ONCE_ENABLED
        constants.RESIGN_ONCE_ENABLED = True
        try:
            under = type('P', (), {'teamResignCount': constants.RESIGN_ONCE_LIMIT - 1})()
            at = type('P', (), {'teamResignCount': constants.RESIGN_ONCE_LIMIT})()
            self.assertFalse(pm.hasReachedResignLimit(under))
            self.assertTrue(pm.hasReachedResignLimit(at))
        finally:
            constants.RESIGN_ONCE_ENABLED = original


class FreeAgentInjectionTests(unittest.TestCase):
    """New players arrive on a schedule. ⚠️ `ensurePositionSupply` cannot do this: it
    fills a DEFICIT against fixed demand, so a league where nobody has retired yet
    generates nobody at all — prod ran four seasons and created none."""

    def setUp(self):
        self.pm = bareManager()

    def testItAddsAClass(self):
        before = len(self.pm.freeAgents)
        self.pm.injectFreeAgentClass(count=8)
        self.assertEqual(before + 8, len(self.pm.freeAgents))

    def testTheClassIsRegisteredEverywhere(self):
        """A player in freeAgents but not activePlayers is invisible to the supply
        count, which would make the floor generate a second class on top."""
        self.pm.injectFreeAgentClass(count=6)
        for p in self.pm.freeAgents:
            self.assertIn(p, self.pm.activePlayers)
            self.assertEqual('Free Agent', p.team)
            self.assertEqual(0, p.freeAgentYears)

    def testIdsAreUnique(self):
        self.pm.injectFreeAgentClass(count=8)
        ids = [p.id for p in self.pm.freeAgents]
        self.assertEqual(len(ids), len(set(ids)), "the class collided on player ids")

    def testTheClassGetsATopEnd(self):
        """The whole reason the injection exists: it is what lets the blue-chip
        guarantee actually fire, since a deficit-only intake never generates a class."""
        self.pm.injectFreeAgentClass(count=8)
        self.assertGreaterEqual(max(p.playerRating for p in self.pm.freeAgents),
                                constants.BLUE_CHIP_RATING_FLOOR)

    def testPositionsFollowRosterSlots(self):
        """⚠️ WR is two slots of every six. A uniform draw starves it by half against
        demand, and the league drifts toward spare kickers and no receivers."""
        from collections import Counter
        for _ in range(40):
            self.pm.injectFreeAgentClass(count=8)
        got = Counter(p.position.name for p in self.pm.freeAgents)
        self.assertGreater(got['WR'], got['QB'],
                           f"WR should be drawn about twice as often as QB: {dict(got)}")

    def testTheFlagTurnsItOff(self):
        original = constants.FA_INJECTION_ENABLED
        constants.FA_INJECTION_ENABLED = False
        try:
            self.assertEqual({}, self.pm.injectFreeAgentClass(count=8))
            self.assertEqual(0, len(self.pm.freeAgents))
        finally:
            constants.FA_INJECTION_ENABLED = original

    def testZeroIsSafe(self):
        self.assertEqual({}, self.pm.injectFreeAgentClass(count=0))


class BlueChipTargetingTests(unittest.TestCase):
    """⚠️ Position match, not the confidence gate, is what kept the guaranteed star away
    from the bottom of the table. `upgradeConfidence` already returns 1.00 for the club
    picking first; what it never had was a star at a position it was weak in. Measured
    across three untargeted configurations, the share landing in the bottom half ran
    44% / 40% / 46% — a coin flip every time."""

    def setUp(self):
        self.pm = bareManager()

    def testTheClassContainsTheTargetPosition(self):
        """The target is worthless as a preference: with five positions a random draw
        misses it most of the time, so one player is forced to it."""
        self.pm.injectFreeAgentClass(count=8, targetPosition=FloosPlayer.Position.QB)
        self.assertTrue(any(p.position == FloosPlayer.Position.QB
                            for p in self.pm.freeAgents))

    def testTheBlueChipLandsAtTheTargetPosition(self):
        for pos in (FloosPlayer.Position.QB, FloosPlayer.Position.RB,
                    FloosPlayer.Position.WR, FloosPlayer.Position.TE):
            pm = bareManager()
            pm.injectFreeAgentClass(count=8, targetPosition=pos)
            # ⚠️ Assert the guarantee AT THE TARGET, not that the target holds the
            # class maximum. An ordinary draw clears 88 about 4% of the time, so over
            # seven other players another position out-rolls the promoted one roughly a
            # quarter of the time — asserting the global max makes this flaky rather
            # than wrong.
            atTarget = [p for p in pm.freeAgents if p.position == pos]
            self.assertTrue(atTarget, f"no {pos.name} was generated for the target")
            self.assertGreaterEqual(max(p.playerRating for p in atTarget),
                                    constants.BLUE_CHIP_RATING_FLOOR,
                                    f"no guaranteed star at the target position {pos.name}")

    def testUntargetedStillWorks(self):
        """Targeting returns None on any missing piece, and that path must still
        guarantee a top end — merely uniform, which is the old behaviour."""
        self.pm.injectFreeAgentClass(count=8, targetPosition=None)
        self.assertGreaterEqual(max(p.playerRating for p in self.pm.freeAgents),
                                constants.BLUE_CHIP_RATING_FLOOR)

    def testKickerIsExcludedFromTargeting(self):
        """⚠️ A guaranteed 88 kicker is the least useful star the league can make —
        POSITION_VALUE prices K at 0.35 — and weak clubs are weak at K as often as
        anywhere, so raw need would nominate it regularly."""
        self.assertEqual(0.0, constants.BLUE_CHIP_NEED_WEIGHTS.get('K'),
                         "kicker must not be targetable")

    def testTheSkillPositionsOutweighTightEnd(self):
        w = constants.BLUE_CHIP_NEED_WEIGHTS
        for pos in ('QB', 'RB', 'WR'):
            self.assertGreater(w[pos], w['TE'],
                               f"{pos} should be weighted above TE")


class IncumbentKnowledgeTests(unittest.TestCase):
    """⚠️ A GM knows its own roster better than the open market. `FO_SCOUT_NOISE_MAX` is
    large on purpose — it was raised from 6.0 so per-team boards differ — but it was
    applied to a club's own walk-year starter as heavily as to a stranger, so a
    league-average GM misjudged its own player by ±5.7 rating points.

    Measured over three 5-season runs: in 65% of team-seasons where somebody was kept
    and somebody walked, a walked player out-rated a kept one. Position weighting
    explains 75% of those; a quarter were not explicable, e.g. a 74 TE kept while an
    85 RB walked."""

    class _Team:
        def __init__(self, name): self.name = name

    class _Player:
        def __init__(self, team): self.team = team

    def testAnIncumbentIsRecognisedByName(self):
        """⚠️ `player.team` is sometimes the Team and sometimes its name — a free agent
        carries the literal string 'Free Agent'. An identity test returns False for half
        the league and the discount would apply to nobody."""
        from managers.frontOfficeBrain import FrontOfficeBrain as B
        team = self._Team('Pinecones')
        self.assertTrue(B._isIncumbent(self._Player('Pinecones'), team))
        self.assertTrue(B._isIncumbent(self._Player(self._Team('Pinecones')), team))

    def testAFreeAgentIsNotAnIncumbent(self):
        from managers.frontOfficeBrain import FrontOfficeBrain as B
        team = self._Team('Pinecones')
        self.assertFalse(B._isIncumbent(self._Player('Free Agent'), team))
        self.assertFalse(B._isIncumbent(self._Player('Slippers'), team))

    def testMissingPiecesAreSafe(self):
        from managers.frontOfficeBrain import FrontOfficeBrain as B
        self.assertFalse(B._isIncumbent(None, self._Team('X')))
        self.assertFalse(B._isIncumbent(self._Player('X'), None))
        self.assertFalse(B._isIncumbent(self._Player(None), self._Team('X')))

    def testTheDiscountIsPartialNotPerfect(self):
        """GM skill must still show in retention. The owner asked for tightening, not
        for removing the variance."""
        self.assertGreater(constants.FO_SCOUT_INCUMBENT_NOISE_SCALE, 0.0,
                           "a zero scale makes every GM a perfect judge of its own roster")
        self.assertLess(constants.FO_SCOUT_INCUMBENT_NOISE_SCALE, 1.0,
                        "the discount must actually reduce the error")


class FacilityCurveTests(unittest.TestCase):
    """⚠️ THE LOW LEVELS PAID NOTHING, AND MOST OF THE LEAGUE WAS IN THEM. The ladders
    were back-loaded so a one-time tier migration reproduced the old perks, and the
    smoothing was left as a pending task. Measured on the live league: 25 of 32 clubs
    held a Scouting Department at level 1 or 2, where the ladder read 0."""

    def testNoFacilityHasADeadPaidLevel(self):
        from constants import FACILITY_CATALOG
        for key, cfg in FACILITY_CATALOG.items():
            levels = cfg.get('levels') or []
            for lvl in (1, 2):
                if lvl < len(levels):
                    self.assertGreater(levels[lvl], 0,
                                       f"{key} level {lvl} costs Floobits and returns nothing")

    def testTheLaddersStillRise(self):
        from constants import FACILITY_CATALOG
        for key, cfg in FACILITY_CATALOG.items():
            levels = cfg.get('levels') or []
            for a, b in zip(levels, levels[1:]):
                self.assertGreaterEqual(b, a, f"{key} ladder goes backwards: {levels}")

    def testMigrationLevelsAreUnchanged(self):
        """⚠️ Levels 3-5 are what the tier migration pinned. Smoothing must not move
        them, or a club that migrated in at Lv3/Lv4 silently changes strength."""
        from constants import FACILITY_CATALOG
        expected = {'scouting': [3, 5, 7],
                    'recovery': [0.15, 0.30, 0.35],
                    'locker_room': [0.0025, 0.0075, 0.01]}
        for key, tail in expected.items():
            self.assertEqual(tail, list(FACILITY_CATALOG[key]['levels'][3:]),
                             f"{key} levels 3-5 moved")


if __name__ == '__main__':
    unittest.main(verbosity=2)
