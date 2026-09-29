"""Regression: Captain and Conductor project their boost at its expected value.

⚠️ AN AMPLIFIER'S BAR IS A PROBABILITY IN AN EXPECTED PROJECTION, AND WAS READ AS A MISS.
`gateActive` is `ratio >= 1.0`. Live the ratio is exactly 1 or 0, but in an expected
projection `gateRatio` returns the player's clear PROBABILITY (Laplace-smoothed, never
1.0), so Captain and Conductor read "didn't clear their bar" in every expected projection
and a hand built around them projected below what it scores. Found replaying real
season-7 hands: 26 Captains, 0 projected boosts. Every other gated card projects at
output x p; the amplifiers now project at boost x p (`_ampGateWeight`).

Live scoring must be byte-identical, which is asserted beside the fix.

Run: python3 test_amplifier_projection.py
"""
import unittest
from types import SimpleNamespace

from managers.cardEffectCalculator import calculateWeekCardBonuses, CardCalcContext


def card(eqId, effectName, playerId, primary, gate=None):
    ec = {"effectName": effectName, "primary": primary, "position": 2, "editionScale": 1.0}
    if gate is not None:
        ec["gate"] = {"threshold": gate}
    t = SimpleNamespace(effect_config=ec, position=2, player_id=playerId, player_rating=80,
                        edition="diamond", player_name=f"P{playerId}")
    return SimpleNamespace(id=eqId, user_card=SimpleNamespace(card_template=t, tier=1),
                           slot_number=eqId)


AMP_PLAYER, FILLER_PLAYER = 201, 101
# The amplifier's player cleared a 10-FP bar in 3 of 4 weeks: p = (3+1)/(4+2) = 2/3.
HISTORY = [12, 12, 12, 5]
P = 2 / 3


def run(amp, mode, ampFP=12.0, fillerFP=15.0):
    cards = [card(1, "freebie", FILLER_PLAYER, {"baseFP": 10.0}), amp]
    ctx = CardCalcContext()
    ctx.rosterPlayerIds = {FILLER_PLAYER, AMP_PLAYER}
    ctx.rosterPlayerPositions = {FILLER_PLAYER: 2, AMP_PLAYER: 2}
    ctx.weekPlayerStats = {FILLER_PLAYER: {"fantasyPoints": fillerFP},
                           AMP_PLAYER: {"fantasyPoints": ampFP}}
    if mode != "live":
        ctx.isProjection = True
        ctx.projectionVariant = mode
        ctx.playerWeeklyFP = {AMP_PLAYER: HISTORY}
    r = calculateWeekCardBonuses(cards, ctx)
    return next(b for b in r.cardBreakdowns if b.effectName == "freebie")


def conductor():
    return card(2, "conductor", AMP_PLAYER, {"boostPct": 20}, gate=10)


def captain():
    return card(2, "captain", AMP_PLAYER, {"perOvershootPct": 0.02}, gate=10)


class ConductorProjection(unittest.TestCase):

    def testExpectedProjectionWeightsTheBoostByTheClearChance(self):
        self.assertAlmostEqual(run(conductor(), "expected").primaryFP,
                               round(10.0 * (1 + 0.20 * P), 1), places=1)

    def testOptimisticProjectionGetsTheFullBoost(self):
        self.assertAlmostEqual(run(conductor(), "optimistic").primaryFP, 12.0, places=1)

    def testLiveIsUnchanged(self):
        self.assertAlmostEqual(run(conductor(), "live", ampFP=12.0).primaryFP, 12.0, places=1)
        self.assertAlmostEqual(run(conductor(), "live", ampFP=5.0).primaryFP, 10.0, places=1)


class CaptainProjection(unittest.TestCase):
    """Captain's per-FP rate is tier- and edition-scaled, so the expectations are derived
    from the LIVE full boost rather than restated: the projection must be exactly that
    boost x p, and the ceiling exactly that boost."""

    def fullBoost(self):
        return run(captain(), "live", ampFP=12.0).primaryFP - 10.0

    def testLiveBoostsWhenTheBarIsClearedAndNotOtherwise(self):
        self.assertGreater(self.fullBoost(), 0)
        self.assertAlmostEqual(run(captain(), "live", ampFP=5.0).primaryFP, 10.0, places=1)

    def testExpectedProjectionWeightsTheBoostByTheClearChance(self):
        self.assertAlmostEqual(run(captain(), "expected").primaryFP,
                               10.0 + self.fullBoost() * P, delta=0.1)

    def testOptimisticProjectionGetsTheFullBoost(self):
        self.assertAlmostEqual(run(captain(), "optimistic").primaryFP,
                               10.0 + self.fullBoost(), delta=0.1)


class GroupProjectProjection(unittest.TestCase):
    """⚠️ In an expected projection a gated card outputs value x p, which is above zero
    whenever p is, so COUNTING outputs read every gated card as triggered and projected
    Group Project as firing outright. It is all-or-nothing, so it projects at
    reward x P(4+ others trigger), from each card's own clear chance."""

    def hand(self, mode):
        cards = [card(i, "freebie", 100 + i, {"baseFP": 10.0}, gate=10) for i in range(1, 5)]
        cards.append(card(9, "bonus_round", 900, {"rewardValue": 30.0}))
        ctx = CardCalcContext()
        pids = {100 + i for i in range(1, 5)} | {900}
        ctx.rosterPlayerIds = pids
        ctx.rosterPlayerPositions = {p: 2 for p in pids}
        ctx.weekPlayerStats = {p: {"fantasyPoints": 12.0} for p in pids}
        if mode != "live":
            ctx.isProjection = True
            ctx.projectionVariant = mode
            ctx.playerWeeklyFP = {100 + i: HISTORY for i in range(1, 5)}   # each p = 2/3
        r = calculateWeekCardBonuses(cards, ctx)
        return next(b for b in r.cardBreakdowns if b.effectName == "bonus_round")

    def testExpectedProjectionIsRewardTimesTheChanceAllFourTrigger(self):
        self.assertAlmostEqual(self.hand("expected").primaryFP, round(30.0 * P ** 4, 1), places=1)

    def testOptimisticAndLiveStillCount(self):
        self.assertAlmostEqual(self.hand("optimistic").primaryFP, 30.0, places=1)
        self.assertAlmostEqual(self.hand("live").primaryFP, 30.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
