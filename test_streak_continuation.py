"""A streak's growth pays only on a week the streak was continued.

⚠️ THE LADDER STREAK CARDS PAID THEIR GROWTH ON A WEEK THE BAR WAS MISSED.
`_ladderStreakDelta` read the carried `streakCounts` and paid `growth x (count - 1)`
unconditionally. The streak was only reset afterwards, at week end, by
`checkStreakCondition` — so the miss week itself still collected the whole run.

Measured on Clockwork (bar 32 completions, growth 0.03, streak carried at 6 weeks):

    completions   bar      growth paid
       18        miss        +0.15      <- the entire six-week run
       31        miss        +0.15      <- one short of the bar
       32        MET         +0.15
       44        MET         +0.15

Only the base rate term moved across the bar. The streak half was flat.

⚠️ IT HID BEHIND THE CARD GATE, which is why it survived. On a genuinely blank week the
gate closes and the whole card pays nothing, so the leak is invisible; on a big week the
bar is cleared anyway, so it looks correct. It paid full value through the entire middle
band — which is where real weeks land, and is exactly the band a player notices.

The data was already there: these cards are category `streak`, and
`fantasyTracker._evaluateLiveStreakConditions` evaluates every one of their reset
conditions into `ctx.liveStreakConditionsMet`. Nothing read it.

⚠️ NOT COVERED HERE: the GENERIC streak handler (`_computeStreakEffect`, 11 mintable
cards) pays `carriedBase + growth x (count - 1)` on a break week under a
"streak broke, paying peak" branch — the identical symptom, and a full-value one rather
than a partial. That is deliberate, documented behavior tied to the peak/decay carry
system, so changing it is a design decision rather than a bug fix. Measured: Metronome
pays 53.1 FP on a break week against 41.6 FP of base.

Run: .venv/bin/python test_streak_continuation.py
"""

import logging
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from managers.cardEffects import buildEffectConfig  # noqa: E402
from managers.cardEffectCalculator import (  # noqa: E402
    CardCalcContext, calculateWeekCardBonuses,
)

# Every prismatic rung built on `_ladderRateStreak`, with the stat that feeds its bar.
LADDER = {
    'clockwork':    (1, 'passing_stats',   'comp'),
    'stratosphere': (1, 'passing_stats',   'passYards'),
    'dead_eye':     (1, 'passing_stats',   'goodThrows'),
    'iron_man':     (2, 'rushing_stats',   'carries'),
    'odyssey':      (2, 'rushing_stats',   'runYards'),
    'landslide':    (2, 'rushing_stats',   'yardsAfterContact'),
    'dominion':     (3, 'receiving_stats', 'rcvYards'),
    'tenure':       (3, 'receiving_stats', 'receptions'),
    'getaway':      (3, 'receiving_stats', 'yac'),
    'undertaker':   (5, 'kicking_stats',   'puntsInside20'),
}

EQ_ID = 900


def score(effect, position, statGroup, statKey, statValue, streakCount, conditionMet):
    cfg = buildEffectConfig('prismatic', 85, position, 10, forceEffect=effect)
    tmpl = NS(player_id=1, edition='prismatic', position=position, player_name='P',
              player_rating=85, effect_config=cfg, classification=None, team_id=10)
    eq = NS(id=EQ_ID, slot_number=1, user_card=NS(card_template=tmpl, tier=1))

    ctx = CardCalcContext()
    ctx.gamesActive = False
    ctx.isProjection = False
    ctx.rosterPlayerIds = {1}
    ctx.rosterPlayerPositions = {1: position}
    ctx.rosterPlayerTeamIds = {1: 10}
    ctx.rosterPlayerRatings = {1: 85}
    # A solid week everywhere, so the card gate is open and cannot mask the result —
    # then the one stat under test is set to whatever the case needs.
    stats = {
        'fantasyPoints': 24.0,
        'passing_stats': {'comp': 24, 'passYards': 260, 'yards': 260, 'tds': 2,
                          'goodThrows': 19, 'badThrows': 2, 'throws': 34},
        'rushing_stats': {'carries': 18, 'runYards': 90, 'rushYards': 90, 'runTds': 1,
                          'yardsAfterContact': 60},
        'receiving_stats': {'receptions': 7, 'rcvYards': 95, 'recYards': 95, 'rcvTds': 1,
                            'yac': 45, 'targets': 10},
        'kicking_stats': {'fgMade': 2, 'fgAtt': 2, 'puntsInside20': 2, 'punts': 4,
                          'puntsIn20': 2},
    }
    stats[statGroup][statKey] = statValue
    ctx.weekPlayerStats = {1: stats}
    ctx.weekRawFP = 24.0
    ctx.teamResults = {10: True}
    ctx.streakCounts = {EQ_ID: streakCount}
    ctx.liveStreakConditionsMet = {EQ_ID: conditionMet}

    result = calculateWeekCardBonuses([eq], ctx)
    row = next((b for b in result.cardBreakdowns if b.effectName == effect), None)
    return row, cfg['primary']


class GrowthRequiresContinuation(unittest.TestCase):
    def testAMissedWeekPaysNoStreakGrowth(self):
        """⚠️ The reported bug. Same stat line, same carried streak — the ONLY difference
        is whether this week's bar was cleared."""
        for effect, (pos, group, key) in LADDER.items():
            with self.subTest(effect=effect):
                _, primary = score(effect, pos, group, key, 1, 1, True)
                bar = primary.get('threshold')
                # Sit just under the bar so the base rate still produces something and
                # the gate stays open: any growth that appears is the leak.
                under = max(0, int(bar) - 1) if bar else 0
                broke, _ = score(effect, pos, group, key, under, 6, False)
                fresh, _ = score(effect, pos, group, key, under, 1, False)
                self.assertAlmostEqual(
                    broke.primaryMult, fresh.primaryMult, places=3,
                    msg=f'{effect}: a 6-week carried streak paid more than no streak '
                        f'on a week the bar was MISSED '
                        f'({broke.primaryMult} vs {fresh.primaryMult})')

    def testAContinuedWeekStillPaysGrowth(self):
        """The fix must not kill the feature."""
        for effect, (pos, group, key) in LADDER.items():
            with self.subTest(effect=effect):
                _, primary = score(effect, pos, group, key, 1, 1, True)
                bar = int(primary.get('threshold') or 1)
                over = max(bar, 1) * 2
                withStreak, _ = score(effect, pos, group, key, over, 6, True)
                without, _ = score(effect, pos, group, key, over, 1, True)
                self.assertGreater(
                    withStreak.primaryMult, without.primaryMult,
                    f'{effect}: a continued 6-week streak paid no more than none')

    def testGrowthScalesWithTheLengthOfTheRun(self):
        """⚠️ Not an exact multiple of `growthPerTick`: the card gate scales the whole
        result by how well the depicted player performed, so the realized step is the
        nominal one times the gate ratio. Assert the shape — strictly increasing, and in
        the right neighborhood — rather than an equality the gate will always break."""
        _, primary = score('clockwork', 1, 'passing_stats', 'comp', 1, 1, True)
        bar = int(primary['threshold'])
        growth = primary['growthPerTick']
        mults = [score('clockwork', 1, 'passing_stats', 'comp', bar + 4, n, True)[0].primaryMult
                 for n in (1, 3, 5, 7)]
        self.assertEqual(mults, sorted(mults), f'growth is not monotonic in run length: {mults}')
        self.assertGreater(mults[-1], mults[0], 'a seven-week run pays no more than one week')
        step = (mults[-1] - mults[0]) / 6.0
        self.assertGreater(step, growth * 0.5, f'per-week step {step:.4f} is far below {growth}')
        self.assertLessEqual(step, growth + 1e-6, f'per-week step {step:.4f} exceeds {growth}')


class BreakdownTellsTheUser(unittest.TestCase):
    """A user who just lost a six-week run is the one asking what happened."""

    def testABrokenStreakSaysSoRatherThanReadingZero(self):
        _, primary = score('clockwork', 1, 'passing_stats', 'comp', 1, 1, True)
        bar = int(primary['threshold'])
        broke, _ = score('clockwork', 1, 'passing_stats', 'comp', bar - 1, 6, False)
        self.assertIn('streak broken', broke.equation)

    def testNeverHavingAStreakReadsDifferently(self):
        _, primary = score('clockwork', 1, 'passing_stats', 'comp', 1, 1, True)
        bar = int(primary['threshold'])
        fresh, _ = score('clockwork', 1, 'passing_stats', 'comp', bar - 1, 1, False)
        self.assertIn('no streak', fresh.equation)
        self.assertNotIn('broken', fresh.equation)

    def testAnActiveStreakReportsItsLength(self):
        _, primary = score('clockwork', 1, 'passing_stats', 'comp', 1, 1, True)
        bar = int(primary['threshold'])
        live, _ = score('clockwork', 1, 'passing_stats', 'comp', bar + 6, 6, True)
        self.assertIn('5 wk streak', live.equation)


class NothingResolvesUntilTheWeekDoes(unittest.TestCase):
    """⚠️ NOT MET *YET* IS NOT THE SAME AS NOT MET, and the generic handler could not
    tell the difference. `liveStreakConditionsMet` reads False from kickoff until the
    moment the condition actually fires, so the break branch resolved the streak the
    instant the week opened — banking the full broken-streak peak before the player had
    taken a snap.

    Measured on Metronome at a carried streak of 6 (base 41.6 FP):

        games running, condition not met yet    53.1 FP   "streak broke, paying peak"
        week over, condition never met          53.1 FP   "streak broke, paying peak"

    Identical. The first is a payout for an outcome that had not happened.

    A streak resolves exactly twice: when the condition is MET, or when the WEEK ENDS
    without it. Until one of those, the streak portion outputs nothing.
    """

    GENERIC = ('metronome', 'snowball_fight', 'momentum', 'complacency', 'bandwagon_express')

    def _generic(self, effect, streakCount, conditionMet, gamesActive):
        cfg = buildEffectConfig('prismatic', 85, 1, 10, forceEffect=effect)
        tmpl = NS(player_id=1, edition='prismatic', position=1, player_name='P',
                  player_rating=85, effect_config=cfg, classification=None, team_id=10)
        eq = NS(id=EQ_ID, slot_number=1, user_card=NS(card_template=tmpl, tier=1))
        ctx = CardCalcContext()
        ctx.gamesActive = gamesActive
        ctx.isProjection = False
        ctx.rosterPlayerIds = {1}
        ctx.rosterPlayerPositions = {1: 1}
        ctx.rosterPlayerTeamIds = {1: 10}
        ctx.rosterPlayerRatings = {1: 85}
        ctx.weekPlayerStats = {1: {'fantasyPoints': 21.0,
                                   'passing_stats': {'comp': 26, 'yards': 270,
                                                     'passYards': 270, 'tds': 2,
                                                     'goodThrows': 19, 'badThrows': 2,
                                                     'throws': 35}}}
        ctx.weekRawFP = 21.0
        ctx.teamResults = {10: True}
        ctx.streakCounts = {EQ_ID: streakCount}
        ctx.liveStreakConditionsMet = {EQ_ID: conditionMet}
        return next(b for b in calculateWeekCardBonuses([eq], ctx).cardBreakdowns
                    if b.effectName == effect)

    def testAStreakPaysNothingWhileTheWeekIsStillRunning(self):
        """⚠️ The reported bug."""
        for effect in self.GENERIC:
            with self.subTest(effect=effect):
                live = self._generic(effect, 6, False, gamesActive=True)
                self.assertEqual(live.totalFP, 0,
                                 f'{effect} banked FP at kickoff: {live.equation}')
                self.assertLessEqual(live.primaryMult, 1.0,
                                     f'{effect} banked FPx at kickoff: {live.equation}')

    def testTheBrokenStreakStillPaysItsPeakOnceTheWeekIsOver(self):
        """The hold must not delete the payout, only defer it. The decaying peak is what
        keeps these cards viable instead of cliffing to base."""
        for effect in self.GENERIC:
            with self.subTest(effect=effect):
                settled = self._generic(effect, 6, False, gamesActive=False)
                self.assertTrue(settled.totalFP > 0 or settled.primaryMult > 1.0,
                                f'{effect} pays nothing after a failed week')

    def testMeetingTheConditionMidWeekPaysImmediately(self):
        """Holding applies only to the UNRESOLVED case. Once the condition fires the
        counter has incremented and there is nothing left to wait for."""
        for effect in self.GENERIC:
            with self.subTest(effect=effect):
                met = self._generic(effect, 7, True, gamesActive=True)
                self.assertTrue(met.totalFP > 0 or met.primaryMult > 1.0,
                                f'{effect} withheld a streak it had already continued')

    def testALadderCardCallsItUnresolvedRatherThanBroken(self):
        """Same mistake one level down: telling a user their six-week run is broken while
        the week is still live."""
        _, primary = score('clockwork', 1, 'passing_stats', 'comp', 1, 1, True)
        bar = int(primary['threshold'])
        live, _ = score('clockwork', 1, 'passing_stats', 'comp', bar - 8, 6, False)
        self.assertIn('streak', live.equation)
        # score() builds a settled context, so assert the wording contract directly.
        from managers.cardEffects import _streakClause
        self.assertEqual(_streakClause(0, 6, NS(gamesActive=True)), 'streak unresolved')
        self.assertEqual(_streakClause(0, 6, NS(gamesActive=False)), 'streak broken')
        self.assertEqual(_streakClause(0, 0, NS(gamesActive=False)), 'no streak')
        self.assertEqual(_streakClause(4, 4, NS(gamesActive=False)), '4 wk streak')


class UnknownConditionDefaultsToActive(unittest.TestCase):
    def testAnEmptyConditionMapDoesNotSilentlyBreakEveryStreak(self):
        """Projection contexts carry no live conditions. Defaulting to broken would price
        every streak card at its floor on every shop and lineup preview."""
        _, primary = score('clockwork', 1, 'passing_stats', 'comp', 1, 1, True)
        bar = int(primary['threshold'])
        cfg = buildEffectConfig('prismatic', 85, 1, 10, forceEffect='clockwork')
        tmpl = NS(player_id=1, edition='prismatic', position=1, player_name='P',
                  player_rating=85, effect_config=cfg, classification=None, team_id=10)
        eq = NS(id=EQ_ID, slot_number=1, user_card=NS(card_template=tmpl, tier=1))
        ctx = CardCalcContext()
        ctx.gamesActive = False
        ctx.isProjection = False
        ctx.rosterPlayerIds = {1}
        ctx.rosterPlayerPositions = {1: 1}
        ctx.rosterPlayerTeamIds = {1: 10}
        ctx.rosterPlayerRatings = {1: 85}
        ctx.weekPlayerStats = {1: {'fantasyPoints': 24.0,
                                   'passing_stats': {'comp': bar + 6, 'yards': 300,
                                                     'tds': 2, 'goodThrows': 20,
                                                     'badThrows': 1, 'throws': 40}}}
        ctx.weekRawFP = 24.0
        ctx.teamResults = {10: True}
        ctx.streakCounts = {EQ_ID: 6}
        ctx.liveStreakConditionsMet = {}          # nothing known
        row = next(b for b in calculateWeekCardBonuses([eq], ctx).cardBreakdowns
                   if b.effectName == 'clockwork')
        self.assertIn('wk streak', row.equation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
