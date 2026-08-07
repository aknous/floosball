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
MEAN['rb2'] = _dbStatsToCardFormat(
    {}, {'yards': 110.5, 'carries': 25.9, 'tds': 0.69, '20+': 0.88,
     'brokenTackles': 0.64, 'yardsAfterContact': 87.5},
    {}, {}, 24, 5, {'puntReturnYards': 23.0})
MEAN['wr2'] = _dbStatsToCardFormat(
    {}, {}, {'yards': 83.5, 'receptions': 9.35, 'yac': 23.0, 'targets': 9.9,
             'tds': 0.40, 'contestedCatches': 1.02, 'bailouts': 0.31}, {}, 22, 5,
    {'puntReturnYards': 23.0})
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
    {'yards': 229.9, 'comp': 27.7, 'goodThrows': 13.4, 'badThrows': 1.56,
     'throws': 37.8, 'airYardsSum': 256.6, '20+': 1.75}, {}, {}, {}, 24, 5)
QB_P90 = _dbStatsToCardFormat(
    {'yards': 332, 'comp': 38, 'goodThrows': 28, 'badThrows': 0,
     'throws': 51, 'airYardsSum': 420, '20+': 4}, {}, {}, {}, 34, 5)


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


ALL_LADDER = [
    'frontier', 'territory', 'dominion', 'freight', 'grinder', 'landslide',
    'pinpoint', 'coffin_corner', 'undertaker', 'paydirt', 'end_zone', 'promised_land',
    'slipstream', 'updraft', 'stratosphere', 'marksman', 'dead_eye',
    'cadence', 'rhythm', 'clockwork', 'beast_of_burden', 'iron_man', 'odyssey',
    'battering_ram', 'custody', 'tenure', 'getaway', 'runback', 'house_call',
    'attention', 'altitude', 'haymaker', 'highpoint', 'breakaway', 'houdini',
    'custodian',
]


def testNoLadderCardIsDeadOnATypicalWeek():
    """A card paying nothing on an ordinary week is a dead card however good its
    ceiling. Altitude sat its bar exactly AT league-average aDOT and paid 0; House
    Call leaned on return TDs, which run ~3 per 100 games and carry no EV at all."""
    means = {1: QB_MEAN, 2: MEAN['rb2'], 3: MEAN['wr2']}
    for effect in ALL_LADDER:
        positions = ce.effectValidPositions(effect)
        pos = next((p for p in (1, 2, 3) if p in positions), None)
        if pos is None:
            continue          # K and TE-only cards are covered by the anchor test
        fp, fpx = _score(effect, pos, means[pos])
        assert fp > 0 or fpx > 0, f"{effect} pays nothing on a typical week"


def testStampedeDisplaysAsTrailblazer():
    """A stale duplicate key later in EFFECT_DISPLAY_NAMES silently shadowed this."""
    assert ce.EFFECT_DISPLAY_NAMES['stampede'] == 'Trailblazer'


def testRatesDoNotRenderAbsurdPrecision():
    """A rate is user-facing text. "+13.935 FP per punt downed inside the 20" reads as a
    bug even though the arithmetic is fine — three decimals is noise on a big per-unit
    number, though a per-yard rate genuinely needs them."""
    for effect, pos in (('pinpoint', K), ('three_pointer', K), ('possession', WR),
                        ('cadence', QB), ('frontier', WR), ('freight', RB)):
        cfg = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[effect], 82, pos,
                                   forceEffect=effect)
        for key, val in cfg['primary'].items():
            if not isinstance(val, float):
                continue
            decimals = len(str(val).split('.')[-1]) if '.' in str(val) else 0
            if val >= 10:
                assert decimals <= 1, f"{effect}.{key} = {val}"
            elif val >= 1:
                assert decimals <= 2, f"{effect}.{key} = {val}"


def testStreakRungsAreCategorisedAsStreaks():
    """The UI labels a card from its CATEGORY, and the breakdown only fills
    streakActive/streakCount when category == 'streak'. These carried 'multiplier' for
    param dispatch, so they behaved as streaks and never said so."""
    for effect in ('dominion', 'landslide', 'undertaker', 'stratosphere', 'dead_eye',
                   'clockwork', 'iron_man', 'odyssey', 'tenure', 'getaway'):
        assert ce.EFFECT_CATEGORY.get(effect) == 'streak', effect
        assert effect in ce.STREAK_CONFIGS, effect
        pos = sorted(ce.effectValidPositions(effect))[0]
        cfg = ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[effect], 82, pos,
                                   forceEffect=effect)
        assert cfg['primary'], f"{effect} lost its params to the category change"


def testEveryLadderCardNamesTheStatItReads():
    """A card paying on YAC showing "3 rec / 32 yd / 0 TD" hides the only number that
    explains the payout, which makes a working card look broken."""
    from managers.cardEffects import LADDER_STAT_READS, ladderStatLine
    for effect in ALL_LADDER:
        assert effect in LADDER_STAT_READS, f"{effect} has no stat line"
    line = ladderStatLine('getaway', MEAN['wr2'])
    assert 'YAC' in line, line


def testEveryLadderEffectIsFullyRegistered():
    for e in ALL_LADDER:
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
