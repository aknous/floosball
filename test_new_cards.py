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

print("\nA2. Deeper checks — magnitude, scaling, and edges on the value cards")

# winners_circle: pays EXACTLY its frozen winFloobits on a win; nothing while the game is pending.
wcWin = buildEffectConfig("prismatic", 82, 5, 10, forceEffect="winners_circle")["primary"]
expect(f"winners_circle pays its winFloobits ({wcWin['winFloobits']}), not some other amount",
       wc.floobitsEarned == wcWin["winFloobits"])
ctxN = baseCtx(); ctxN.rosterPlayerIds = {2}; ctxN.rosterPlayerPositions = {2: 5}
ctxN.rosterPlayerTeamIds = {2: 11}; ctxN.rosterPlayerRatings = {2: 82}
ctxN.weekPlayerStats = {2: {"fantasyPoints": 8.0}}; ctxN.teamResults = {11: None}  # not final
wcPend = byEffect(calculateWeekCardBonuses([mkEq("winners_circle", "prismatic", 5, 2, 82, 11, 1)], ctxN))["winners_circle"]
expect("winners_circle pays nothing while the game is pending", wcPend.floobitsEarned == 0)

# no_passengers: the FPx scales with the roster's LOWEST FP; a 0-floor (a benched player) pays nothing.
def npMult(floorFP):
    c = baseCtx(); c.rosterPlayerIds = {1, 2}; c.rosterPlayerPositions = {1: 1, 2: 3}
    c.rosterPlayerTeamIds = {1: 10, 2: 10}; c.rosterPlayerRatings = {1: 85, 2: 85}
    c.weekPlayerStats = {1: {"fantasyPoints": 40.0}, 2: {"fantasyPoints": float(floorFP)}}
    c.teamResults = {}
    return byEffect(calculateWeekCardBonuses([mkEq("no_passengers", "prismatic", 1, 1, 85, 10, 1)], c))["no_passengers"].primaryMult
npLow, npHigh = npMult(5), npMult(25)
print(f"    no_passengers floor 5 -> {npLow}x ; floor 25 -> {npHigh}x")
expect("no_passengers FPx scales up with a higher roster floor", npHigh > npLow > 1.0)
expect("no_passengers pays nothing when a roster player scored 0 (a passenger)", npMult(0) <= 1.0)

# franchise: fires on >= the roster top (ties count), off below it, and never at 0 FP.
def frMult(myFP, otherFP):
    c = baseCtx(); c.rosterPlayerIds = {1, 2}; c.rosterPlayerPositions = {1: 2, 2: 3}
    c.rosterPlayerTeamIds = {1: 10, 2: 11}; c.rosterPlayerRatings = {1: 85, 2: 85}
    c.weekPlayerStats = {1: {"fantasyPoints": float(myFP)}, 2: {"fantasyPoints": float(otherFP)}}
    c.teamResults = {}
    return byEffect(calculateWeekCardBonuses([mkEq("franchise", "prismatic", 2, 1, 85, 10, 1)], c))["franchise"].primaryMult
expect("franchise fires when tied for the roster top", frMult(20, 20) > 1.0)
expect("franchise off when below the top", frMult(10, 20) <= 1.0)
expect("franchise off at 0 FP even if nominally top", frMult(0, 0) <= 1.0)

# metronome: FP grows with the streak count, and freezes (noReset) so a cold week never zeros it.
from managers.cardEffects import STREAK_CONFIGS, checkStreakCondition
def metFP(streak):
    c = baseCtx(); c.rosterPlayerIds = {3}; c.rosterPlayerPositions = {3: 3}
    c.rosterPlayerRatings = {3: 80}; c.rosterPlayerTeamIds = {3: 11}
    c.weekPlayerStats = {3: {"fantasyPoints": 20.0}}; c.teamResults = {}
    eq = mkEq("metronome", "prismatic", 3, 3, 80, 11, 4)
    c.streakCounts = {eq.id: streak}
    return byEffect(calculateWeekCardBonuses([eq], c))["metronome"].totalFP
m0, m5 = metFP(0), metFP(5)
print(f"    metronome streak 0 -> {m0} FP ; streak 5 -> {m5} FP")
expect("metronome FP grows with the streak count", m5 > m0 > 0)
expect("metronome freezes on cold weeks (noReset config)", STREAK_CONFIGS["metronome"].get("noReset") is True)
mc = baseCtx(); mc.rosterPlayerPositions = {3: 3}; mc.weekPlayerStats = {3: {"fantasyPoints": 20.0}}
expect("metronome streak advances when the player clears the bar", checkStreakCondition("metronome", mc, 3) is True)
mc.weekPlayerStats = {3: {"fantasyPoints": 2.0}}
expect("metronome streak does NOT advance on a cold week (it holds)", checkStreakCondition("metronome", mc, 3) is False)


# ── Scenario B: Captain (Diamond) overshoot amplifier — self-gate, scaling, cap, all outputs
print("\nB. Captain amplifier — self-gate + overshoot scaling + 2x cap + FP/FPx/Floobits")

# Score ONE boost card (at position `pos`, its player scoring `boostFP`), optionally with a
# Diamond Captain fielded alongside it. Captain's own player scores captainFP.
def boostedCard(effect, ed, pos, boostFP, captainFP=40.0, withCaptain=True):
    c = baseCtx()
    ids, positions, teams, ratings = {2}, {2: pos}, {2: 10}, {2: 88}
    stats = {2: {"fantasyPoints": float(boostFP),
                 "passing_stats": {"passYards": 300, "tds": 2},
                 "receiving_stats": {"rcvYards": 60, "receptions": 4}}}
    hand = [mkEq(effect, ed, pos, 2, 88, 10, 2)]
    if withCaptain:
        ids.add(1); positions[1] = 1; teams[1] = 10; ratings[1] = 92
        stats[1] = {"fantasyPoints": float(captainFP)}
        hand.insert(0, mkEq("captain", "diamond", 1, 1, 92, 10, 1))
    c.rosterPlayerIds = ids; c.rosterPlayerPositions = positions
    c.rosterPlayerTeamIds = teams; c.rosterPlayerRatings = ratings
    c.weekPlayerStats = stats; c.teamResults = {10: True}
    return byEffect(calculateWeekCardBonuses(hand, c))[effect]

# B1: self-gate — Captain's own player must clear its bar (Diamond QB = 15) to amplify.
base = boostedCard("freebie", "prismatic", 3, 30, withCaptain=False)
sat = boostedCard("freebie", "prismatic", 3, 30, captainFP=3.0)   # captain under its own bar
lifts = boostedCard("freebie", "prismatic", 3, 30, captainFP=40.0)  # captain clears
print(f"    freebie base={base.totalFP}  captain-sat={sat.totalFP}  captain-clears={lifts.totalFP}")
expect("Captain under its own bar gives NO boost", abs(sat.totalFP - base.totalFP) < 0.05)
expect("Captain over its bar amplifies the card", lifts.totalFP > base.totalFP)

# B2: overshoot scaling — the further the boosted card's player clears ITS bar, the bigger the
# lift. Both must clear the boosted card's own bar (prismatic WR = 12) so its effect fires.
small = boostedCard("freebie", "prismatic", 3, 14)   # overshoot ~2
big = boostedCard("freebie", "prismatic", 3, 45)     # overshoot ~33
print(f"    overshoot small(14FP)={small.totalFP}  big(45FP)={big.totalFP}")
expect("bigger overshoot -> bigger boost", big.totalFP > small.totalFP > base.totalFP - 0.01)

# B3: 2x cap — a huge overshoot caps the lift at +100% (2x the base output).
capped = boostedCard("freebie", "prismatic", 3, 400)
print(f"    huge overshoot(400FP)={capped.totalFP}  (base {base.totalFP}, 2x = {round(base.totalFP*2,1)})")
expect("boost caps at 2x the base output", abs(capped.totalFP - base.totalFP * 2) < 0.2)

# B4: FPx output boosted — a multiplier card's delta grows under Captain.
mBase = boostedCard("big_deal", "prismatic", 1, 30, withCaptain=False)
mCapt = boostedCard("big_deal", "prismatic", 1, 400)
print(f"    big_deal FPx base={mBase.primaryMult}  captain={mCapt.primaryMult}")
expect("Captain boosts an FPx card's multiplier", mCapt.primaryMult > mBase.primaryMult > 1.0)

# B5: Floobits output boosted — a floobits card pays more under Captain.
fBase = boostedCard("allowance", "prismatic", 3, 30, withCaptain=False)
fCapt = boostedCard("allowance", "prismatic", 3, 400)
print(f"    allowance floobits base={fBase.floobitsEarned}  captain={fCapt.floobitsEarned}")
expect("Captain boosts a Floobits card's payout", fCapt.floobitsEarned > fBase.floobitsEarned > 0)


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
