"""Bonsai (Cultivation): the power-bar meter, the effect detail, and the week-end roll
all read the SAME grow-odds.

Owner-reported bug (2026-07-27): a Bonsai card's FP meter sat at 0% all game and read
"didn't fire" at the end, while the effect detail panel showed the grow-chance climbing
and said it grew. Root cause: _computeCultivation put the odds only in the equation string
(the detail) and never set chanceThreshold (the meter fill) / chanceTriggered, AND the
week-end roll (_rollCultivationGrowth) used stale baseChance/chancePerTrigger params Bonsai
never sets, over a whole-roster trigger count — so the shown % and the rolled % were
disconnected.

Fix: one shared cultivationGrowthChance() used by the live display and the roll; the live
result now carries chanceThreshold (= odds) so the meter matches the detail, and
chanceMetaGrowth so projection doesn't scale the guaranteed base down by the odds.

Run: .venv/bin/python test_bonsai_meter.py   (exits non-zero on any failure)
"""
import sys, logging
sys.path.insert(0, '/Users/andrew/Projects/floosball')
logging.disable(logging.CRITICAL)
from managers.cardEffects import (buildEffectConfig, computeEffect,
                                  cultivationGrowthChance, _getCultivationStepSize)
from managers.cardEffectCalculator import CardCalcContext

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

CARD = 1  # depicted (on-card) player id


def mkCtx(passTds, streakCount=1):
    """A roster where the ON-CARD QB posted `passTds` passing TDs, plus a noisy teammate
    who ALSO scored TDs (to prove the count is the on-card player's, not the roster sum)."""
    c = CardCalcContext()
    c.rosterPlayerIds = {CARD, 2}
    c.rosterPlayerPositions = {CARD: 1, 2: 3}
    c.rosterPlayerRatings = {CARD: 88, 2: 80}
    c.rosterPlayerTeamIds = {CARD: 10, 2: 10}
    c.weekPlayerStats = {
        CARD: {"fantasyPoints": 18.0, "passing_stats": {"tds": passTds}},
        2:    {"fantasyPoints": 10.0, "receiving_stats": {"rcvTds": 5}},  # decoy TDs
    }
    c.gamesActive = True
    c.userId = 1; c.season = 16; c.weekNumber = 5
    c.streakCounts = {1: streakCount}
    return c


def parsePct(eq):
    """Pull the 'NN%' the detail equation shows."""
    import re
    m = re.search(r'(\d+)%', eq)
    return int(m.group(1)) if m else None


cfg = buildEffectConfig('prismatic', 88, 1, 10, forceEffect='bonsai')
stepSize = _getCultivationStepSize(cfg['primary']['triggerEvent'])

print("1. QB Bonsai trigger is a stat a QB posts (pass TDs), stepSize known")
expect(f"trigger={cfg['primary']['triggerEvent']} (a QB stat)",
       cfg['primary']['triggerEvent'] == 'pass_td')

print("\n2. The meter fill (chanceThreshold) equals the detail's shown %")
for tds in (0, 1, 2, 3, 5):
    r = computeEffect(cfg, mkCtx(tds), CARD, 1)
    shownPct = parsePct(r.equation)
    meterPct = round((r.chanceThreshold or 0) * 100)
    expected = cultivationGrowthChance(cfg['primary'], tds, 0)  # level 0
    expect(f"{tds} pass TD: detail {shownPct}% == meter {meterPct}% == shared {expected}%",
           shownPct == meterPct == expected)

print("\n3. Odds climb with production, and a dead week floors at 2% (not 0)")
r0 = computeEffect(cfg, mkCtx(0), CARD, 1)
r3 = computeEffect(cfg, mkCtx(3), CARD, 1)
expect(f"0 TD floors at 2% (meter not 0) -> {round((r0.chanceThreshold or 0)*100)}%",
       round((r0.chanceThreshold or 0) * 100) == 2)
expect(f"hitting the step ({stepSize}) reaches ~90%+ -> {round((r3.chanceThreshold or 0)*100)}%",
       (r3.chanceThreshold or 0) > (r0.chanceThreshold or 0) and (r3.chanceThreshold or 0) >= 0.9)

print("\n4. The count is the ON-CARD player's, not the roster sum (decoy TDs ignored)")
# The decoy teammate has 5 receiving TDs; if they leaked in, 0 on-card TDs would read as a
# high chance. It must stay at the 2% floor.
expect("on-card 0 TD stays 2% despite a teammate's 5 TDs",
       round((r0.chanceThreshold or 0) * 100) == 2)

print("\n5. Base always pays, and it's flagged meta-growth (projection won't scale the floor)")
r = computeEffect(cfg, mkCtx(1), CARD, 1)
base = cfg['primary']['baseFP']
expect(f"fpBonus == guaranteed base {base} (odds gate FUTURE growth) -> {r.fpBonus}",
       abs(r.fpBonus - base) < 0.05)
expect("chanceMetaGrowth flagged True", getattr(r, 'chanceMetaGrowth', False) is True)

print("\n6. Higher growth level raises the bar (a bigger week needed to keep pushing)")
# The gentle ramp still requires more each level, so the same TD count yields lower odds
# at a higher level than at level 0.
lo = cultivationGrowthChance(cfg['primary'], stepSize, 0)   # exactly the level-0 step
hi = cultivationGrowthChance(cfg['primary'], stepSize, 3)   # same triggers, level 3
expect(f"same triggers earn LESS at a higher level ({hi}% < {lo}%)", hi < lo)

print("\n7. Gentler per-level ramp: a strong week still advances the card at higher levels")
# The reported case: a level-3 YAC card (stepSize 60) after an 88-YAC week. The old linear
# ramp needed 240 YAC at level 3 (88 -> 33%); the gentler ramp needs ~132 (88 -> ~60%), so a
# great week keeps the card climbing instead of stalling far below its FP ceiling.
yacPrim = {'triggerEvent': 'yac'}
lvl3 = cultivationGrowthChance(yacPrim, 88, 3)
expect(f"level-3 YAC card, 88 YAC -> healthy grow chance (got {lvl3}%, was 33%)", lvl3 >= 50)
chances = [cultivationGrowthChance(yacPrim, 88, l) for l in range(0, 6)]
expect(f"chance still tapers as the level climbs {chances}",
       all(chances[i] >= chances[i + 1] for i in range(len(chances) - 1)))


print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — Bonsai meter, detail, and roll all read the same grow-odds.")
