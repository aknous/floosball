"""A shared effect retired MID-season must still be transplantable.

Loyalty Bonus was dropped from the mint pool on 2026-11-01 with copies already minted that
season. `effectValidPositions` reads the live pools, so it reported the effect as valid
nowhere; the card serialized `validPositions: []` and the transplant picker
(`TransplantModal.fitsTarget`) dropped every one of them as a donor.
"""
from managers import cardEffects as ce


def testRetiredSharedEffectStaysOutOfThePool():
    # The mint-pool reading is unchanged: supply checks rely on a retired effect being empty.
    assert ce.effectValidPositions('loyalty_bonus') == set()


def testRetiredSharedEffectTransplantsAnywhere():
    for effect in ce.RETIRED_SHARED_EFFECTS:
        expected = {p for p in range(1, 6)
                    if effect not in ce.POSITION_EXCLUDED_EFFECTS.get(p, set())}
        assert ce.transplantPositions(effect) == expected, effect
        assert ce.transplantPositions(effect), f'{effect} would be dropped by the picker'


def testRetiredSharedEffectsAreRealEffects():
    for effect in ce.RETIRED_SHARED_EFFECTS:
        assert effect in ce.EFFECT_EDITION_TIER, effect
        assert effect not in ce.SHARED_EFFECT_POOL, f'{effect} is not retired'


def testLiveEffectsUnchanged():
    for effect in ce.EFFECT_EDITION_TIER:
        if effect in ce.RETIRED_SHARED_EFFECTS:
            continue
        assert ce.transplantPositions(effect) == ce.effectValidPositions(effect), effect


def testSerializedCardCarriesThePositions():
    import inspect
    from managers import cardManager
    src = inspect.getsource(cardManager.CardManager.serializeCard)
    assert '_transplantPositions(effectName)' in src
