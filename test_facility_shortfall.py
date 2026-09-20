"""
A SHORTFALL BUYS THE MOST IT CAN, AND NEVER PAYS PART OF A BILL.

⚠️ A FACILITY DECAYS UNLESS ITS UPKEEP IS MET IN FULL, and `prepareSeasonStart` resets
`upkeep_funded` to 0 every season — so Floobits poured into a shortfall the pot cannot
close are gone, and bought nothing.

The waterfall used to pay highest-level-first in full-shortfall order, which in a genuine
shortfall spent the whole pot on the most expensive bill and let it decay anyway. Measured
on production: Pinecones, 200F against 383F owed, put all 200F into a 247F locker room,
lost it regardless, and lost the three cheaper facilities too — 136F would have saved all
three. Four levels gone, nothing bought.

The choice is now made over SUBSETS: the affordable set preserving the most value, paid in
full, with everything else paid nothing. Value = the cost to rebuild the level at risk, so
a level-3 building outranks a level-1 in real Floobits rather than by counting levels.
"""
from managers.facilitiesManager import resolveSeasonEnd, upkeepCostFloobits, upgradeCostFloobits

SU = 5485.0


def _fac(pairs):
    return [{'key': k, 'level': l, 'upkeep_funded': 0} for k, l in pairs]


# The exact production shape that surfaced this.
PINECONES = [('locker_room', 3), ('training', 2), ('recovery', 1), ('scouting', 1), ('stadium', 0)]


def testTheProductionShortfallLosesOneLevelNotFour():
    res = resolveSeasonEnd(_fac(PINECONES), [], 200, SU, 6)
    decayed = sorted(f['key'] for f in res['facilities'] if not f['upkeepMet'])
    assert decayed == ['locker_room'], decayed
    # 136F buys training + recovery + scouting; the 247F locker room is unaffordable.
    assert res['leftover'] == 200 - (
        upkeepCostFloobits(2, SU) + upkeepCostFloobits(1, SU) * 2), res['leftover']


def testNoPartialPaymentIsEverMade():
    """Every facility is paid its FULL bill or nothing at all — part of a bill is worth 0."""
    for pot in (0, 27, 50, 136, 200, 300, 383, 1000):
        res = resolveSeasonEnd(_fac(PINECONES), [], pot, SU, 6)
        for f in res['facilities']:
            paid, cost = f['upkeepPaid'], f['upkeepCost']
            assert paid == 0 or paid >= cost, (pot, f['key'], paid, cost)


def testAffordingEverythingStillPaysEverything():
    res = resolveSeasonEnd(_fac(PINECONES), [], 10_000, SU, 6)
    assert all(f['upkeepMet'] for f in res['facilities'])


def testAPotOfZeroSpendsNothingAndDecaysEverythingThatCosts():
    res = resolveSeasonEnd(_fac(PINECONES), [], 0, SU, 6)
    assert res['leftover'] == 0
    decayed = {f['key'] for f in res['facilities'] if not f['upkeepMet']}
    # stadium is level 0 — its upkeep is 0, so it is met for free and cannot decay.
    assert decayed == {'locker_room', 'training', 'recovery', 'scouting'}, decayed


def testValueBeatsCount():
    """
    ⚠️ The objective is VALUE PRESERVED, not facilities saved. Given a pot that can buy
    either one expensive level or two cheap ones, it takes whichever is worth more to
    rebuild — which is the whole reason the choice is a knapsack and not cheapest-first.
    """
    # One lv5 (upkeep 2194, rebuild 4662) vs two lv3 (upkeep 247 each, rebuild 1097 each).
    fac = _fac([('a', 5), ('b', 3), ('c', 3)])
    pot = upkeepCostFloobits(5, SU)          # exactly enough for the lv5 alone
    twoCheap = upgradeCostFloobits(2, SU) * 2
    oneRich = upgradeCostFloobits(4, SU)
    res = resolveSeasonEnd(fac, [], pot, SU, 6)
    saved = {f['key'] for f in res['facilities'] if f['upkeepMet']}
    if oneRich > twoCheap:
        assert saved == {'a'}, (saved, oneRich, twoCheap)
    else:
        assert saved == {'b', 'c'}, (saved, oneRich, twoCheap)


def testFanFundedUpkeepCostsThePotNothing():
    """A bill already covered by direct fan funding must not consume budget."""
    fac = _fac(PINECONES)
    for f in fac:
        if f['key'] == 'locker_room':
            f['upkeep_funded'] = upkeepCostFloobits(3, SU)   # fans pre-paid it
    res = resolveSeasonEnd(fac, [], 200, SU, 6)
    assert all(f['upkeepMet'] for f in res['facilities']), \
        [f['key'] for f in res['facilities'] if not f['upkeepMet']]


def testAFacilityUnderConstructionStillWaivesUpkeep():
    """The pre-existing waiver must survive the rewrite."""
    projects = [{'id': 1, 'facility_key': 'locker_room', 'target_level': 4,
                 'cost_shares': 0.42, 'funded': 0, 'opened_season': 6}]
    res = resolveSeasonEnd(_fac(PINECONES), projects, 0, SU, 6)
    lr = next(f for f in res['facilities'] if f['key'] == 'locker_room')
    assert lr['upkeepMet'] and lr['upkeepCost'] == 0


if __name__ == '__main__':
    for n, f in sorted(globals().items()):
        if n.startswith('test') and callable(f):
            f(); print('ok', n)
