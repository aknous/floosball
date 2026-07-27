"""End-to-end scoring test for the fusion-era NEW cards + chance rework, run through the
REAL calculateWeekCardBonuses pipeline (not the single-effect path): winners_circle,
no_passengers, franchise, metronome, captain (Diamond amplifier), plus a reworked chance
card (scrappy). Builds faithful fake EquippedCard/CardTemplate/UserCard objects and a
populated CardCalcContext, exactly as the calculator reads them.

Run: .venv/bin/python test_new_cards.py
"""
import sys, logging
sys.path.insert(0, '/Users/andrew/Projects/floosball')
logging.disable(logging.CRITICAL)
from types import SimpleNamespace as NS
from managers.cardEffects import buildEffectConfig
from managers.cardEffectCalculator import CardCalcContext, calculateWeekCardBonuses

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

_eqId = [0]
def mkEq(effect, edition, position, playerId, rating, teamId, slot, tier=1, classification=None):
    """Build a fake equipped card the calculator can read like an ORM row."""
    _eqId[0] += 1
    cfg = buildEffectConfig(edition, rating, position, teamId, forceEffect=effect,
                            classification=classification)
    tmpl = NS(player_id=playerId, edition=edition, position=position,
              player_name=f"P{playerId}", player_rating=rating,
              effect_config=cfg, classification=classification)
    uc = NS(card_template=tmpl, tier=tier)
    return NS(id=_eqId[0], slot_number=slot, user_card=uc)

def baseCtx():
    c = CardCalcContext()
    c.gamesActive = False
    c.streakCounts = {}
    return c

def byEffect(result):
    return {b.effectName: b for b in result.cardBreakdowns}


# ── Scenario A: the four new value/amplifier effects in one hand ────────────────
print("A. New value effects through the full calculator")
# Roster: RB is the clear top scorer; K's team won; everyone cleared their floor.
ctx = baseCtx()
ctx.rosterPlayerIds = {1, 2, 3, 4, 5}
ctx.rosterPlayerPositions = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
ctx.rosterPlayerTeamIds = {1: 10, 2: 10, 3: 11, 4: 12, 5: 10}
ctx.rosterPlayerRatings = {1: 85, 2: 90, 3: 80, 4: 78, 5: 82}
ctx.weekPlayerStats = {
    1: {"fantasyPoints": 18.0}, 2: {"fantasyPoints": 34.0},  # RB top scorer
    3: {"fantasyPoints": 14.0}, 4: {"fantasyPoints": 9.0}, 5: {"fantasyPoints": 11.0},
}
ctx.teamResults = {10: True, 11: False, 12: None}  # team 10 (K's team) won

hand = [
    mkEq("no_passengers", "prismatic", 1, 1, 85, 10, 1),   # QB
    mkEq("franchise",     "prismatic", 2, 2, 90, 10, 2),   # RB (top scorer)
    mkEq("winners_circle","prismatic", 5, 5, 82, 10, 3),   # K (team won)
    mkEq("metronome",     "prismatic", 3, 3, 80, 11, 4),   # WR
]
res = byEffect(calculateWeekCardBonuses(hand, ctx))
np_, fr, wc, me = res["no_passengers"], res["franchise"], res["winners_circle"], res["metronome"]
print(f"    no_passengers: mult={np_.primaryMult}  eq='{np_.equation}'")
print(f"    franchise:     mult={fr.primaryMult}  eq='{fr.equation}'")
print(f"    winners_circle:floo={wc.floobitsEarned}  eq='{wc.equation}'")
print(f"    metronome:     fp={me.totalFP}  eq='{me.equation}'")
expect("no_passengers pays FPx off the roster floor (9 FP > 0)", np_.primaryMult > 1.0)
expect("franchise fires — RB (34 FP) is the top scorer", fr.primaryMult > 1.0)
expect("winners_circle pays Floobits — K's team won", wc.floobitsEarned > 0)
expect("metronome pays its base FP at streak 0", me.totalFP > 0)

# Franchise must NOT fire when the on-card player isn't the top scorer
ctx2 = baseCtx()
ctx2.rosterPlayerIds = {1, 2}; ctx2.rosterPlayerPositions = {1: 2, 2: 3}
ctx2.rosterPlayerTeamIds = {1: 10, 2: 11}; ctx2.rosterPlayerRatings = {1: 85, 2: 85}
ctx2.weekPlayerStats = {1: {"fantasyPoints": 10.0}, 2: {"fantasyPoints": 30.0}}
ctx2.teamResults = {}
frMiss = byEffect(calculateWeekCardBonuses([mkEq("franchise", "prismatic", 2, 1, 85, 10, 1)], ctx2))["franchise"]
expect(f"franchise stays off when not top scorer  ('{frMiss.equation}')", frMiss.primaryMult <= 1.0)

# winners_circle must NOT pay when the team lost
wcLoss = byEffect(calculateWeekCardBonuses([mkEq("winners_circle", "prismatic", 5, 2, 82, 11, 1)], ctx2))["winners_circle"]
expect(f"winners_circle stays off when team didn't win  ('{wcLoss.equation}')", wcLoss.floobitsEarned == 0)


# ── Scenario B: Captain (Diamond) overshoot amplifier + self-gate ──────────────
print("\nB. Captain amplifier — self-gate + overshoot boost")
def captainScenario(captainFP):
    c = baseCtx()
    c.rosterPlayerIds = {1, 2}; c.rosterPlayerPositions = {1: 1, 2: 3}
    c.rosterPlayerTeamIds = {1: 10, 2: 10}; c.rosterPlayerRatings = {1: 92, 2: 88}
    # Player 2 (the boosted freebie card) overshoots its WR bar (8) by a lot.
    c.weekPlayerStats = {1: {"fantasyPoints": captainFP}, 2: {"fantasyPoints": 30.0,
                         "receiving_stats": {"rcvYards": 40, "receptions": 3}}}
    c.teamResults = {}
    hand = [
        mkEq("captain", "diamond", 1, 1, 92, 10, 1),   # QB captain
        mkEq("freebie", "prismatic", 3, 2, 88, 10, 2),  # WR flat-FP card to be boosted
    ]
    return byEffect(calculateWeekCardBonuses(hand, c))

# B1: captain clears its QB bar (8) and the freebie's player overshoots -> boosted
on = captainScenario(20.0)
cap, fb = on["captain"], on["freebie"]
print(f"    captain(clears): eq='{cap.equation}'   freebie fp={fb.totalFP}")
baseFreebie = byEffect(calculateWeekCardBonuses(
    [mkEq("freebie", "prismatic", 3, 2, 88, 10, 1)],
    (lambda: (lambda c: (setattr(c, 'rosterPlayerIds', {2}), setattr(c, 'rosterPlayerPositions', {2: 3}),
              setattr(c, 'rosterPlayerTeamIds', {2: 10}), setattr(c, 'rosterPlayerRatings', {2: 88}),
              setattr(c, 'weekPlayerStats', {2: {"fantasyPoints": 30.0, "receiving_stats": {"rcvYards": 40, "receptions": 3}}}),
              setattr(c, 'teamResults', {}), c)[-1])(baseCtx()))()
))["freebie"]
expect(f"Captain amplified the freebie ({baseFreebie.totalFP} -> {fb.totalFP})", fb.totalFP > baseFreebie.totalFP)
expect("Captain reports it amplified a card", "amplified" in cap.equation)

# B2: captain's own player UNDER its bar (3 < 8) -> no boost
off = captainScenario(3.0)
capOff, fbOff = off["captain"], off["freebie"]
print(f"    captain(under bar): eq='{capOff.equation}'   freebie fp={fbOff.totalFP}")
expect("Captain gives NO boost when its own player is under the bar", "didn't clear" in capOff.equation)
expect("the freebie is unboosted when Captain sat", abs(fbOff.totalFP - baseFreebie.totalFP) < 0.05)


# ── Scenario C: reworked chance card through the full calculator ────────────────
print("\nC. Chance card (scrappy) end-to-end — additive odds surfaced on the breakdown")
c = baseCtx()
c.rosterPlayerIds = {1, 2, 3, 4, 5}
c.rosterPlayerPositions = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
c.rosterPlayerTeamIds = {i: 10 for i in range(1, 6)}
c.rosterPlayerRatings = {1: 88, 2: 62, 3: 64, 4: 80, 5: 80}  # 2,3 low-rated (<=2 stars)
c.weekPlayerStats = {1: {"fantasyPoints": 16.0}, 2: {"fantasyPoints": 3.0},
                     3: {"fantasyPoints": 4.0}, 4: {"fantasyPoints": 12.0}, 5: {"fantasyPoints": 10.0}}
c.teamResults = {}
scr = byEffect(calculateWeekCardBonuses([mkEq("scrappy", "prismatic", 1, 1, 88, 10, 1)], c))["scrappy"]
print(f"    scrappy: isChance={scr.isChanceEffect}  odds={scr.chanceThreshold}  "
      f"triggered={scr.chanceTriggered}  fp={scr.totalFP}  gateThr={scr.gateThreshold}")
print(f"      eq='{scr.equation}'")
expect("scrappy flagged as a chance effect", scr.isChanceEffect is True)
expect("scrappy exempt from the on/off gate (threshold 0)", (scr.gateThreshold or 0) == 0)
expect("scrappy odds are the additive bar (QB 16FP full + 2 low-rated ~= 0.83)",
       0.75 <= (scr.chanceThreshold or 0) <= 0.90)
expect("scrappy paid its floor or enhanced FP (base always pays)", scr.totalFP > 0)

print("\n" + ("ALL PASS" if not failures else f"{len(failures)} FAILURE(S): " + "; ".join(failures)))
sys.exit(1 if failures else 0)
