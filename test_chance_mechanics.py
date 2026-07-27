"""Chance-mechanics verification for the fusion chance rework (2026-07-26).

The power bar on a chance card IS the enhanced-payout trigger probability, filled
additively from the depicted player's FP (Group A) plus the card's own condition, and
capped at 0.99. Group C (crescendo/traverse/bonsai) fill it from the on-card stat alone.

Covers: additive-odds math, every surviving chance card, edge cases, a statistical check
that the seeded roll actually respects the odds, and the projection expected-value path.

Run: .venv/bin/python test_chance_mechanics.py
"""
import sys, logging
sys.path.insert(0, '/Users/andrew/Projects/floosball')
logging.disable(logging.CRITICAL)
from managers.cardEffects import buildEffectConfig, computeEffect
from managers.cardEffectCalculator import CardCalcContext
from constants import (CARD_GATE_FP_THRESHOLDS, CARD_CHANCE_FP_WEIGHT,
                       CARD_CHANCE_CONDITION_WEIGHT, CARD_CHANCE_CONDITION_FULL_COUNT)

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

CARD = 1  # depicted player id

def mkCtx(cardFP, ratings, stats, week=5, chanceBonus=0.0, gamesActive=False,
          teamId=10, position=1):
    c = CardCalcContext()
    ids = set(ratings.keys()) | {CARD}
    c.rosterPlayerIds = ids
    c.rosterPlayerPositions = {pid: (position if pid == CARD else 3) for pid in ids}
    c.rosterPlayerRatings = dict(ratings); c.rosterPlayerRatings.setdefault(CARD, 88)
    c.rosterPlayerTeamIds = {pid: teamId for pid in ids}
    c.weekPlayerStats = dict(stats)
    c.weekPlayerStats.setdefault(CARD, {"fantasyPoints": cardFP})
    c.teamResults = {teamId: True}
    c.gamesActive = gamesActive
    c.userId = 1; c.season = 16; c.weekNumber = week
    c.streakCounts = {}
    return c

def run(effect, ctx, edition='prismatic', position=1, eqId=1):
    cfg = buildEffectConfig(edition, 88, position, 10, forceEffect=effect)
    return computeEffect(cfg, ctx, CARD, eqId), cfg


# ── 1. Additive odds math is exact ──────────────────────────────────────────────
print("1. Additive odds = FP-fill x weight + condition-fill x weight (capped 0.99)")
def expectedOdds(cardFP, position, condCount, chanceBonus=0.0):
    thr = CARD_GATE_FP_THRESHOLDS[position]
    fpFill = min(1.0, cardFP / thr)
    condFill = min(1.0, condCount / CARD_CHANCE_CONDITION_FULL_COUNT)
    return round(min(0.99, CARD_CHANCE_FP_WEIGHT * fpFill
                     + CARD_CHANCE_CONDITION_WEIGHT * condFill + chanceBonus), 4)

# scrappy: QB (thr 8), condition = players rated <= 2 stars. Give 2 low-rated teammates.
lowRatings = {2: 62, 3: 64, 4: 80, 5: 80}
lowStats = {2: {"fantasyPoints": 3.0}, 3: {"fantasyPoints": 4.0},
            4: {"fantasyPoints": 12.0}, 5: {"fantasyPoints": 10.0}}
for cardFP, cond in [(16, 2), (8, 2), (4, 2), (0, 2)]:
    ctx = mkCtx(cardFP, lowRatings, lowStats)
    r, _ = run('scrappy', ctx)
    exp = expectedOdds(cardFP, 1, cond)
    expect(f"scrappy FP={cardFP}, 2 low-rated -> odds {r.chanceThreshold} (expect {exp})",
           abs((r.chanceThreshold or 0) - exp) < 0.005)

# hand-synergy bonus (chanceBonus) adds on top
ctx = mkCtx(16, lowRatings, lowStats); ctx.chanceBonus = 0.10
r, _ = run('scrappy', ctx)
expect(f"chanceBonus stacks additively -> {r.chanceThreshold} (expect {expectedOdds(16,1,2,0.10)})",
       abs((r.chanceThreshold or 0) - expectedOdds(16, 1, 2, 0.10)) < 0.005)


# ── 2. Every surviving chance card computes cleanly + sets the bar ───────────────
print("\n2. All surviving chance cards: isChance, odds in [0,0.99], base always pays")
GROUP_A = ['scrappy', 'sleeper', 'babysitter', 'consolation_prize', 'last_resort']
GROUP_C = ['crescendo', 'traverse', 'bonsai']
for eff in GROUP_A:
    ctx = mkCtx(16, lowRatings, lowStats)
    r, cfg = run(eff, ctx, position=1)
    prim = cfg['primary']
    paid = (r.fpBonus or 0) > 0 or (r.floobits or 0) > 0
    expect(f"{eff}: isChance & 0<=odds<=0.99 ({r.chanceThreshold}) & base pays ({paid})",
           prim.get('isChanceEffect') and 0 <= (r.chanceThreshold or 0) <= 0.99 and paid)
for eff in GROUP_C:
    # Group C keys off the on-card player's own production
    stats = {CARD: {"fantasyPoints": 20.0,
                    "passing_stats": {"passYards": 300, "tds": 3},
                    "rushing_stats": {"runYards": 80, "runTds": 1}}}
    ctx = mkCtx(20, {}, stats, position=1)
    ctx.cardPosition = 1
    r, cfg = run(eff, ctx, position=1)
    expect(f"{eff}: computes cleanly, odds in [0,0.99] ({r.chanceThreshold})",
           0 <= (r.chanceThreshold or 0) <= 0.99)


# ── 3. Edge cases ───────────────────────────────────────────────────────────────
print("\n3. Edge cases")
# Benched card player, no condition -> odds ~0
ctx = mkCtx(0, {2: 80, 3: 80, 4: 80, 5: 80},
            {p: {"fantasyPoints": 20.0} for p in (2, 3, 4, 5)})
r, _ = run('scrappy', ctx)
expect(f"benched player + strong roster -> ~0 odds ({r.chanceThreshold})", (r.chanceThreshold or 0) < 0.02)
expect("but base FP still pays (floor is guaranteed)", (r.fpBonus or 0) > 0)

# Maxed FP + maxed condition -> capped at 0.99
manyLow = {2: 60, 3: 60, 4: 60, 5: 60}
manyLowStats = {p: {"fantasyPoints": 1.0} for p in (2, 3, 4, 5)}
ctx = mkCtx(40, manyLow, manyLowStats)
r, _ = run('scrappy', ctx)
expect(f"maxed FP + 4 low-rated -> capped near 0.99 ({r.chanceThreshold})", (r.chanceThreshold or 0) >= 0.95)

# gamesActive -> never marked triggered yet (awaiting the week-end roll), base still pays
ctx = mkCtx(40, manyLow, manyLowStats, gamesActive=True)
r, _ = run('scrappy', ctx)
expect(f"live games -> not yet triggered ({r.chanceTriggered}) but base pays ({(r.fpBonus or 0)>0})",
       r.chanceTriggered is False and (r.fpBonus or 0) > 0)


# ── 4. Statistical: the seeded roll respects the odds ───────────────────────────
print("\n4. Statistical — empirical trigger rate ~ computed odds over 3000 weeks")
def triggerRate(effect, cardFP, ratings, stats, position=1, trials=3000):
    hits = 0; odds = None
    for wk in range(1, trials + 1):
        ctx = mkCtx(cardFP, ratings, stats, week=wk, position=position)
        r, _ = run(effect, ctx, position=position, eqId=1)
        odds = r.chanceThreshold
        if r.chanceTriggered:
            hits += 1
    return hits / trials, odds

for cardFP, cond in [(16, 2), (4, 2)]:
    rate, odds = triggerRate('scrappy', cardFP, lowRatings, lowStats)
    expect(f"scrappy FP={cardFP}: empirical {rate:.3f} ~ odds {odds:.3f} (within 0.03)",
           abs(rate - odds) < 0.03)


# ── 5. Group C: odds respond to the on-card stat, no FP contribution ────────────
print("\n5. Group C condition-only — traverse odds rise with the card player's yards")
def traverseOdds(yards):
    stats = {CARD: {"fantasyPoints": 5.0, "passing_stats": {"passYards": yards, "tds": 0}}}
    ctx = mkCtx(5, {}, stats, position=1); ctx.cardPosition = 1
    r, _ = run('traverse', ctx, position=1)
    return r.chanceThreshold or 0
lo, hi = traverseOdds(20), traverseOdds(400)
print(f"    traverse: 20 yds -> {lo:.3f} odds ; 400 yds -> {hi:.3f} odds")
expect("more yards -> higher trigger odds (condition drives the bar)", hi > lo)


# ── 6. Projection expected-value path (through the real pipeline) ────────────────
print("\n6. Projection (expected variant) — does the EV account for the guaranteed floor?")
from types import SimpleNamespace as NS
from managers.cardEffectCalculator import calculateWeekCardBonuses
def mkEq(effect, edition, position, playerId, rating, teamId, slot, eqId):
    cfg = buildEffectConfig(edition, rating, position, teamId, forceEffect=effect)
    tmpl = NS(player_id=playerId, edition=edition, position=position, player_name=f"P{playerId}",
              player_rating=rating, effect_config=cfg, classification=None)
    return NS(id=eqId, slot_number=slot, user_card=NS(card_template=tmpl, tier=1)), cfg

prim = buildEffectConfig('prismatic', 88, 1, 10, forceEffect='scrappy')['primary']
base, enh = prim['baseFP'], prim['enhancedFP']
liveOdds = run('scrappy', mkCtx(4, lowRatings, lowStats))[0].chanceThreshold
trueEV = base + (enh - base) * liveOdds

pctx = mkCtx(4, lowRatings, lowStats)   # low FP -> low odds, so the floor dominates EV
pctx.isProjection = True; pctx.projectionVariant = 'expected'
eq, _ = mkEq('scrappy', 'prismatic', 1, CARD, 88, 10, 1, 1)
proj = {b.effectName: b for b in calculateWeekCardBonuses([eq], pctx).cardBreakdowns}['scrappy']
print(f"    base={base} enhanced={enh} odds={liveOdds:.3f}")
print(f"    projected fp={proj.totalFP:.1f}   true EV (floor + upside*odds)={trueEV:.1f}   enhanced*odds={enh*liveOdds:.1f}")
expect("projection returns a value (does not crash)", proj.totalFP is not None)
# Documents the projection model: it scales the ENHANCED payout by the odds and does NOT add
# the guaranteed floor, so it under-states EV when the floor is large / odds low.
gap = trueEV - proj.totalFP
if abs(gap) > 1.0:
    print(f"    NOTE: projection under-states true EV by {gap:.1f} FP (it scales enhanced x odds "
          f"= {enh*liveOdds:.1f} and ignores the guaranteed floor). Flag for the projection fix.")

print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILURE(S): " + "; ".join(failures)))
sys.exit(1 if failures else 0)
