"""The deep ball: called more, read first, and no longer a free lunch.

⚠️ THE DEEP BALL WAS TOO GOOD, NOT JUST TOO RARE. Against NFL 2021-25 by air yards, sim
deep throws completed 58% (NFL 33%) for 15.9 yards an attempt (NFL 11.9) and long throws
66% (NFL 52%) for 12.4 (NFL 10.7), while coaches rarely called them. Three changes:
  * the play-call depth shapes ask for more long and deep throws;
  * on a long or deep call the QB's read starts with the route at the called depth
    (openness had no depth term, so he took whatever short route was open);
  * long and deep throws are harder to place (PASS_TYPE_DIFFICULTY), fitted so each
    tier's yards per attempt lands on the NFL's.

⚠️ THE READ BONUS IS PERCEPTION ONLY. A first harness version added it to the target's
openness, which the catch model also reads, so the called receiver became genuinely more
open and the completion numbers came out optimistic.

Run: .venv/bin/python test_pass_depth.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.disable(logging.CRITICAL)

from scenario import Scenario  # noqa: E402
import floosball_game as FG  # noqa: E402
import constants  # noqa: E402

PassType = FG.PassType


class TheCalledDepthRead(unittest.TestCase):

    def _choices(self, called, n=2000):
        s = Scenario()
        s.situation(quarter=2, clock=600, down=1, distance=10, ballOn=60)
        play = s.game.play
        play.insights['playCall'] = called
        wr1, wr2 = s.home.rosterDict['wr1'], s.home.rosterDict['wr2']
        deepPicks, actualSeen = 0, set()
        for _ in range(n):
            targets = [
                {'receiver': wr1, 'openness': 62, 'route': PassType.short},
                {'receiver': wr2, 'openness': 55, 'route': PassType.deep},
            ]
            picked, _away = play.selectPassTarget(targets, 80, 80)
            if picked is not None and picked['route'] is PassType.deep:
                deepPicks += 1
                actualSeen.add(picked['actualOpenness'])
        return deepPicks / n, actualSeen

    def testADeepCallLooksDeepFirst(self):
        onDeepCall, _ = self._choices('deep')
        onShortCall, _ = self._choices('short')
        self.assertGreater(onDeepCall, onShortCall + 0.25,
                           'a deep call still takes the open short route as often as a short call')

    def testTheBonusNeverChangesHowOpenTheReceiverReallyIs(self):
        _, actual = self._choices('deep', n=300)
        self.assertEqual(actual, {55}, 'the read bonus leaked into the openness the throw uses')


class TheDifficulty(unittest.TestCase):

    def testDeepThrowsAreHarderThanLongThanMedium(self):
        d = constants.PASS_TYPE_DIFFICULTY
        self.assertGreater(d['medium'], d['long'])
        self.assertGreater(d['long'], d['deep'])

    def testThrowQualityReadsTheConstants(self):
        s = Scenario()
        s.situation(quarter=2, clock=600, down=1, distance=10, ballOn=60)
        play = s.game.play
        saved = dict(constants.PASS_TYPE_DIFFICULTY)
        try:
            constants.PASS_TYPE_DIFFICULTY['deep'] = 1.0
            easy = sum(play.calculateThrowQuality(PassType.deep, 85, 85, 85, 0.0, 0.0) for _ in range(400))
            constants.PASS_TYPE_DIFFICULTY['deep'] = 0.4
            hard = sum(play.calculateThrowQuality(PassType.deep, 85, 85, 85, 0.0, 0.0) for _ in range(400))
        finally:
            constants.PASS_TYPE_DIFFICULTY.clear()
            constants.PASS_TYPE_DIFFICULTY.update(saved)
        self.assertGreater(easy, hard * 1.5)


if __name__ == '__main__':
    unittest.main()
