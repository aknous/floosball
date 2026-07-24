"""Detailed coaching-decision log + runPassRatio verification.

Boots a fresh league, instruments the decision points, plays N games, and prints:
  (A) a verbose TRACE of one game — every concept call and gameplan adjustment
      with the situation that drove it;
  (B) a runPassRatio VERIFICATION — bucket the actual run-rate by the active
      offensive gameplan's runPassRatio, to confirm the wiring drives play mix;
  (C) a season-level SUMMARY — concept distribution, adjustment counts, and a
      few defensive counter-adaptation examples.

Usage: PYTHONPATH=. DATABASE_DIR=/tmp/floo_declog .venv/bin/python decision_log.py [nGames]
"""
import os, sys, logging, asyncio
os.environ.setdefault('DATABASE_DIR', '/tmp/floo_declog')
os.environ['TIMING_MODE'] = 'fast'
logging.disable(logging.CRITICAL)

import managers
from database.connection import init_db, clear_db
from service_container import container
from config_manager import get_config
from managers.floosballApplication import FloosballApplication
import floosball_game as fg
import gameplan
from game_rules import GameRules

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12

clear_db(); init_db()
cfg = get_config(); cfg['timingMode'] = 'fast'
app = FloosballApplication(container)
asyncio.run(app.initializeLeague(cfg, force_fresh=True))
teams = app.teamManager.teams

# ---- instrumentation state ----
STATE = {'game': None, 'gameNo': 0, 'traceGame': 0}
concepts = []           # (gameNo, team, concept, down, dist, scoreDiff, qtr, oppBlitz)
offAdj = []             # (gameNo, team, boundary, dRPR, dBias, ypc, ypa)
defAdj = []             # (gameNo, team, dBlitz, dRun, dAggr, oppConceptTop)
plays = []              # (rpr, isRun)  — for runPassRatio verification
trace = []              # human-readable lines for the trace game


def _teamForOff(plan):
    g = STATE['game']
    if g is None: return '?'
    return g.homeTeam.name if plan is g.homeOffGameplan else (g.awayTeam.name if plan is g.awayOffGameplan else '?')

def _teamForDef(plan):
    g = STATE['game']
    if g is None: return '?'
    return g.homeTeam.name if plan is g.homeDefGameplan else (g.awayTeam.name if plan is g.awayDefGameplan else '?')


# concept selection
_realSel = fg.Game._selectRunConcept
def _selSpy(self):
    c = _realSel(self)
    isHome = self.offensiveTeam is self.homeTeam
    oppDef = self.awayDefGameplan if isHome else self.homeDefGameplan
    sd = (self.homeScore - self.awayScore) if isHome else (self.awayScore - self.homeScore)
    row = (STATE['gameNo'], self.offensiveTeam.name, c, self.down, self.yardsToFirstDown,
           sd, self.currentQuarter, getattr(oppDef, 'blitzFrequency', 0.25))
    concepts.append(row)
    if STATE['gameNo'] == STATE['traceGame'] and c != 'power':
        trace.append("  [{} Q{} {}&{} {:+d}] {} calls a {} (opp blitz rate {:.0%})".format(
            self.offensiveTeam.abbr, self.currentQuarter, self.down, self.yardsToFirstDown,
            sd, self.offensiveTeam.abbr, c.upper(), getattr(oppDef, 'blitzFrequency', 0.25)))
    return c
fg.Game._selectRunConcept = _selSpy

# offensive adjustment
_realOff = gameplan.adjustOffensiveGameplan
def _offSpy(plan, coach, stats, confidence=1.0):
    b0, d0 = plan.runPassRatio, plan.passDepthBias
    _realOff(plan, coach, stats, confidence)
    dR, dD = plan.runPassRatio - b0, plan.passDepthBias - d0
    if abs(dR) > 0.005 or abs(dD) > 0.005:
        ypc = stats['runYards'] / max(1, stats['runPlays']); ypa = stats['passYards'] / max(1, stats['passAttempts'])
        team = _teamForOff(plan)
        offAdj.append((STATE['gameNo'], team, dR, dD, ypc, ypa))
        if STATE['gameNo'] == STATE['traceGame']:
            drivers = []
            if abs(dR) > 0.005: drivers.append("run/pass {:+.2f} (ypc {:.1f} vs ypa {:.1f} -> lean {})".format(dR, ypc, ypa, 'RUN' if dR > 0 else 'PASS'))
            if abs(dD) > 0.005: drivers.append("quick-game bias {:+.2f} (offense stalling)".format(dD))
            trace.append("  [{}] OFF adjust: {}".format(team, '; '.join(drivers)))
gameplan.adjustOffensiveGameplan = _offSpy
fg.adjustOffensiveGameplan = _offSpy  # engine imports it into fg's namespace

# defensive adjustment
_realDef = gameplan.adjustDefensiveGameplan
def _defSpy(plan, coach, stats, confidence=1.0, oppConcepts=None):
    b0, r0, a0 = plan.blitzFrequency, plan.runStopFocus, plan.aggressiveness
    _realDef(plan, coach, stats, confidence, oppConcepts)
    dB, dR, dA = plan.blitzFrequency - b0, plan.runStopFocus - r0, plan.aggressiveness - a0
    top = max(oppConcepts, key=oppConcepts.get) if oppConcepts and sum(oppConcepts.values()) else '-'
    if abs(dB) > 0.005 or abs(dR) > 0.005 or abs(dA) > 0.005:
        team = _teamForDef(plan)
        defAdj.append((STATE['gameNo'], team, dB, dR, dA, top))
        if STATE['gameNo'] == STATE['traceGame']:
            parts = []
            if abs(dB) > 0.005: parts.append("blitz {:+.2f}".format(dB))
            if abs(dR) > 0.005: parts.append("run-stop {:+.2f}".format(dR))
            if abs(dA) > 0.005: parts.append("aggression {:+.2f}".format(dA))
            note = " (opp leans {})".format(top.upper()) if top != '-' else ""
            trace.append("  [{}] DEF adjust: {}{}".format(team, ', '.join(parts), note))
gameplan.adjustDefensiveGameplan = _defSpy
fg.adjustDefensiveGameplan = _defSpy

# per-play run/pass for runPassRatio verification
_realExec = fg.Game._executeWeightedPlay
def _execSpy(self, weights, targetSideline=False):
    isHome = self.offensiveTeam is self.homeTeam
    offPlan = self.homeOffGameplan if isHome else self.awayOffGameplan
    rpr = getattr(offPlan, 'runPassRatio', 0.5) if offPlan else 0.5
    before = self.play.insights.get('playCall')
    _realExec(self, weights, targetSideline)
    call = self.play.insights.get('playCall')
    if call:
        plays.append((rpr, call == 'run'))
fg.Game._executeWeightedPlay = _execSpy


async def go():
    _realPlay = fg.Game.playGame
    for i in range(N):
        h, a = teams[i % len(teams)], teams[(i * 5 + 3) % len(teams)]
        if h is a: a = teams[(i + 1) % len(teams)]
        STATE['gameNo'] = i; STATE['game'] = None
        g = fg.Game(h, a, gameRules=GameRules())
        STATE['game'] = g
        if i == STATE['traceGame']:
            trace.append("=== GAME 1 decision trace: {} (home) vs {} (away) ===".format(h.name, a.name))
        await g.playGame()
asyncio.run(go())

# ---------- (A) trace ----------
print("\n" + "=" * 78)
for line in trace[:60]:
    print(line)

# ---------- (B) runPassRatio verification ----------
print("\n" + "=" * 78)
print("runPassRatio VERIFICATION — run-rate bucketed by the active runPassRatio")
print("(higher runPassRatio should drive a higher actual run share)\n")
buckets = {}
for rpr, isRun in plays:
    key = round(rpr * 20) / 20  # 0.05 bins
    buckets.setdefault(key, [0, 0])
    buckets[key][0] += 1 if isRun else 0
    buckets[key][1] += 1
print(f"  {'runPassRatio':>13}{'plays':>9}{'run%':>8}")
for k in sorted(buckets):
    runs, tot = buckets[k]
    if tot >= 20:
        print(f"  {k:>13.2f}{tot:>9}{runs/tot*100:>7.1f}%")

# ---------- (C) summary ----------
from collections import Counter
print("\n" + "=" * 78)
cc = Counter(c[2] for c in concepts)
tot = sum(cc.values())
print(f"SEASON SUMMARY — {N} games, {len(concepts)} run concepts, "
      f"{len(offAdj)} offensive + {len(defAdj)} defensive adjustments")
print("  concept mix: " + "  ".join(f"{k} {cc[k]/tot*100:.0f}%" for k in ('power', 'draw', 'counter', 'sweep')))
dc = Counter(d[5] for d in defAdj if d[5] != '-')
print("  defenses countered a leaning offense {} times; most-countered concept: {}".format(
    sum(dc.values()), dc.most_common(1)[0] if dc else '-'))
