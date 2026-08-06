"""The four stat-ladder families (docs/CARD_STAT_LADDER.md).

Pins the two properties that make the ladder a ladder, both of which were broken in
the first build and only surfaced by testing a TYPICAL week rather than a good one:

  1. a metallic rung lands on the FP anchor at a mean week, on EVERY position it mints
     on (position-blind rates are what left Safety Blanket at 5.3 FP/reception and
     Possession at 2.7 for the same mechanic);
  2. a holographic rung's conditional bonus pays NOTHING on a mean week — the first
     Territory gate sat at 75 yards against a WR mean of 83.5, so the "bonus" fired
     most weeks, and Grinder's "over half your yards after contact" is the league norm
     at ~80%, not an achievement.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import managers.cardEffects as ce
from managers.cardEffectCalculator import CardCalcContext
from managers.fantasyTracker import _dbStatsToCardFormat

QB, RB, WR, TE, K = 1, 2, 3, 4, 5


def _ctx(stats, pid=1, streak=1):
    c = CardCalcContext()
    c.weekPlayerStats = {pid: stats}
    c.rosterPlayerIds = {pid}
    c.streakCounts = {99: streak}
    c.season, c.weekNumber = 15, 14
    return c


def _score(effect, position, stats, streak=1):
    cfg = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[effect], 82, position,
                               forceEffect=effect)
    r = ce.computeEffect(cfg, _ctx(stats, streak=streak), 1, 99)
    return r.fpBonus, (r.multBonus - 1.0) if r.multBonus else 0.0


# Measured per-game means (docs/CARD_STAT_LADDER.md).
MEAN = {
    'wr': _dbStatsToCardFormat({}, {}, {'yards': 83.5, 'tds': 0.40, 'receptions': 9.35}, {}, 22, 5),
    'te': _dbStatsToCardFormat({}, {}, {'yards': 59.0, 'tds': 0.26, 'receptions': 8.22}, {}, 18, 5),
    'rb': _dbStatsToCardFormat({}, {'yards': 110.5, 'yardsAfterContact': 87.5}, {}, {}, 24, 5),
    'k':  _dbStatsToCardFormat({}, {}, {}, {'puntsInside20': 2.03, 'puntsInside10': 1.0}, 10, 5),
}
P90 = {
    'wr': _dbStatsToCardFormat({}, {}, {'yards': 143, 'tds': 1, 'receptions': 14}, {}, 30, 5),
    'te': _dbStatsToCardFormat({}, {}, {'yards': 94, 'tds': 1, 'receptions': 13}, {}, 26, 5),
    'rb': _dbStatsToCardFormat({}, {'yards': 209, 'yardsAfterContact': 190}, {}, {}, 28, 5),
    'k':  _dbStatsToCardFormat({}, {}, {}, {'puntsInside20': 4, 'puntsInside10': 2}, 12, 5),
}


def testReceptionCardsNoLongerDrift():
    """Possession (WR) and Safety Blanket (TE) are the same mechanic on two positions.
    They drifted to 2.47 and 5.5 FP per reception against volumes of 9.35 and 8.22 a
    game, leaving the TE card measuring 47.0 FP/week and the WR one 21.4."""
    wr, _ = _score('possession', WR, MEAN['wr'])
    te, _ = _score('safety_blanket', TE, MEAN['te'])
    assert abs(wr - te) < 4, f"reception cards still disagree: WR {wr}, TE {te}"
    assert 22 <= wr <= 34 and 22 <= te <= 34


def testMetallicRungsLandOnTheAnchorOnEveryPosition():
    """A TE catches 8.2 balls a game to a WR's 9.4, so one rate cannot serve both."""
    for effect, pos, key in (('frontier', WR, 'wr'), ('frontier', TE, 'te'),
                             ('freight', RB, 'rb'), ('pinpoint', K, 'k')):
        fp, _ = _score(effect, pos, MEAN[key])
        assert 22 <= fp <= 34, f"{effect} at {pos} paid {fp} on a mean week"


def testHolographicBonusDoesNotFireOnATypicalWeek():
    """The bonus is the whole point of the rung. If it pays at the mean it is just a
    bigger metallic card and the typical week stops being flat across tiers."""
    for effect, pos, key in (('territory', WR, 'wr'), ('territory', TE, 'te'),
                             ('grinder', RB, 'rb'), ('coffin_corner', K, 'k')):
        _, mean = _score(effect, pos, MEAN[key])
        _, p90 = _score(effect, pos, P90[key])
        assert 0.07 <= mean <= 0.13, f"{effect} paid {mean:.3f} FPx on a mean week"
        assert p90 > mean * 1.5, f"{effect} p90 {p90:.3f} barely beats mean {mean:.3f}"


def testTerritoryGatesSitAboveATypicalWeek():
    cfg = ce.buildEffectConfig('holographic', 82, WR, forceEffect='territory')
    assert min(cfg['primary']['gates']) > 83.5, cfg['primary']['gates']
    teCfg = ce.buildEffectConfig('holographic', 82, TE, forceEffect='territory')
    assert min(teCfg['primary']['gates']) > 59.0, teCfg['primary']['gates']


def testGrinderBarSitsAboveTheLeagueNorm():
    """Yards after contact are ~80% of rushing yards league-wide."""
    cfg = ce.buildEffectConfig('holographic', 82, RB, forceEffect='grinder')
    assert cfg['primary']['ratioBar'] > 0.80


def testPrismaticStreakRampsRatherThanPayingFlat():
    for effect, pos, key in (('dominion', WR, 'wr'), ('landslide', RB, 'rb'),
                             ('undertaker', K, 'k')):
        _, fresh = _score(effect, pos, MEAN[key], streak=1)
        _, mature = _score(effect, pos, MEAN[key], streak=6)
        assert mature > fresh, f"{effect} does not grow with the streak"


def testPromisedLandSurvivesFractionalTds():
    """The projection path feeds PER-GAME AVERAGES, so TDs arrive fractional there and
    an int-only loop raised TypeError."""
    fp, _ = _score('promised_land', WR, MEAN['wr'])
    assert fp > 0


QB_MEAN = _dbStatsToCardFormat(
    {'yards': 229.9, 'goodThrows': 13.4, 'badThrows': 1.56, 'throws': 37.8}, {}, {}, {}, 24, 5)
QB_P90 = _dbStatsToCardFormat(
    {'yards': 332, 'goodThrows': 28, 'badThrows': 0, 'throws': 51}, {}, {}, {}, 34, 5)


def testQbFamiliesHoldTheirTypicalWeek():
    for effect in ('gunslinger', 'updraft'):
        fp, _ = _score(effect, QB, QB_MEAN)
        assert 22 <= fp <= 34, f"{effect} paid {fp} on a mean week"
    for effect in ('slipstream', 'marksman'):
        _, d = _score(effect, QB, QB_MEAN)
        assert 0.07 <= d <= 0.13, f"{effect} paid {d:.3f} FPx on a mean week"


def testMarksmanCleanSheetDoesNotFireOnATypicalWeek():
    """A QB throws ~1.6 bad balls a game, so a clean sheet is genuinely rare."""
    _, mean = _score('marksman', QB, QB_MEAN)
    _, p90 = _score('marksman', QB, QB_P90)      # 0 bad throws
    assert p90 > mean * 2, f"clean-sheet bonus barely registers: {mean:.3f} -> {p90:.3f}"


def testGunslingerStillScoresOnAPreRepointCard():
    """Params are frozen at mint, so a card minted before Gunslinger moved from pass
    yards to throw quality still carries perHundredYardsFP. Without the fallback it
    would silently read zero for a whole season."""
    legacy = {'effectName': 'gunslinger',
              'primary': {'rewardType': 'fp', 'perHundredYardsFP': 13.5}}
    r = ce.computeEffect(legacy, _ctx(QB_MEAN), 1, 99)
    assert r.fpBonus > 0, "a pre-re-point Gunslinger scores nothing"


def testEveryLadderEffectIsFullyRegistered():
    NEW = ['frontier', 'territory', 'dominion', 'freight', 'grinder', 'landslide',
           'pinpoint', 'coffin_corner', 'undertaker', 'paydirt', 'end_zone',
           'promised_land', 'slipstream', 'updraft', 'stratosphere', 'marksman',
           'dead_eye']
    for e in NEW:
        assert e in ce.EFFECT_REGISTRY, f"{e} missing from EFFECT_REGISTRY"
        assert e in ce.EFFECT_EDITION_TIER, f"{e} missing an edition"
        assert e in ce.EFFECT_DISPLAY_NAMES, f"{e} missing a display name"
        assert e in ce.EFFECT_DETAIL_TEMPLATES, f"{e} missing a detail template"
        assert ce.effectValidPositions(e), f"{e} mints on no position"


def testLadderEffectsOnlyMintWhereTheStatExists():
    """A card must never sit on one position and read another's stats."""
    expect = {'frontier': {WR, TE}, 'territory': {WR, TE}, 'dominion': {WR, TE},
              'paydirt': {WR, TE}, 'end_zone': {WR, TE}, 'promised_land': {WR, TE},
              'freight': {RB}, 'grinder': {RB}, 'landslide': {RB},
              'pinpoint': {K}, 'coffin_corner': {K}, 'undertaker': {K},
              'slipstream': {QB}, 'updraft': {QB}, 'stratosphere': {QB},
              'marksman': {QB}, 'dead_eye': {QB}, 'gunslinger': {QB}}
    for e, positions in expect.items():
        assert ce.effectValidPositions(e) == positions, \
            f"{e} mints on {ce.effectValidPositions(e)}, expected {positions}"


if __name__ == '__main__':
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test') and callable(fn):
            try:
                fn()
                print(f"  [OK] {name}")
            except AssertionError as e:
                fails += 1
                print(f"  [FAIL] {name}: {e}")
    print("\nPASS — the ladder holds its typical week and saves the bonus for a big one."
          if not fails else f"\n{fails} FAILED")
    sys.exit(1 if fails else 0)
