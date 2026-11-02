"""Free agents are priced over the contract they would sign, not next season alone.

owner, 2026-11-01: a team priced a 31-year-old on a three-year deal at what he would be
next season, ignoring the declining years after it, and a rising 24-year-old the same way,
missing the years he would still be improving. `FrontOfficeBrain.contractValue` is the
average projected value across the contract's seasons.

Run: .venv/bin/python -m pytest -q test_contract_value.py
"""
from constants import FO_CEILING_CREDIT, POSITION_VALUE
from floosball_player import Position
from test_starter_standing import Brain, _coach, _team, _player, _rising


def test_aOneSeasonDealIsPricedOnNextSeason():
    brain = Brain()
    vet = _player(1, 83, nextSeason=81.0)
    assert brain.contractValue(vet, 1, _coach(), _team()) == brain.decisionValue(vet)


def test_aVeteransDecliningYearsCostOverALongerDeal():
    brain, coach, team = Brain(), _coach(), _team()
    vet = _player(1, 83, nextSeason=81.0)
    one = brain.contractValue(vet, 1, coach, team)
    three = brain.contractValue(vet, 3, coach, team)
    four = brain.contractValue(vet, 4, coach, team)
    assert four < three < one
    # Average of seasons 1..3 at 0, -2, -4 below next season, seen at 0.5 + 0.5 x 0.5.
    expected = -2.0 * (3 - 1) / 2.0 * 0.75 * POSITION_VALUE['RB']
    assert abs((three - one) - expected) < 1e-6


def test_aRisingPlayersLaterYearsCount():
    brain, coach, team = Brain(), _coach(), _team()
    young = _rising(2, 78, 92)
    one = brain.contractValue(young, 1, coach, team)
    three = brain.contractValue(young, 3, coach, team)
    assert three > one
    f = FO_CEILING_CREDIT * brain.developmentLean(coach, team)
    levels = [14 * ((1 - f) - (1 - f) ** k) for k in (1, 2, 3)]
    expected = sum(levels) / 3 * brain.scoutingVision(coach, team) * POSITION_VALUE['TE']
    assert abs((three - one) - expected) < 1e-6
    # Never more than the gap to his ceiling, however long the deal.
    assert brain.contractTermAdjustment(young, 20, coach, team) < 14 * POSITION_VALUE['TE']


def test_aPrimePlayerIsTheSameOverAnyTerm():
    brain = Brain()
    prime = _player(3, 85)
    assert brain.contractTermAdjustment(prime, 4, _coach(), _team()) == 0.0


def test_aBetterScoutSeesMoreOfTheRise():
    brain, team = Brain(), _team()
    young = _rising(4, 76, 92)
    poor = brain.contractTermAdjustment(young, 3, _coach(scouting=60), team)
    sharp = brain.contractTermAdjustment(young, 3, _coach(scouting=100), team)
    assert sharp > poor > 0


def test_onTheSameSheetTheRisingPlayerOutranksTheFadingOneOnALongDeal():
    brain, coach, team = Brain(), _coach(), _team()
    fading = _player(5, 84, nextSeason=82.5, position=Position.TE)
    rising = _rising(6, 84, 94)
    assert brain.contractValue(rising, 3, coach, team) > brain.contractValue(fading, 3, coach, team)
