"""Facilities economy harness — does fair-share cost scaling cause teams to bunch
at the same upgrade level, and how would a per-team cost tilt change that?

Drives the REAL managers.facilitiesManager.resolveSeasonEnd over many seasons for
24 teams under a per-team funding distribution, and reads the equilibrium spread
of total facility levels.

Funding can be sourced from the actual prod DB (data/floosball_prod_latest.db:
per-team current_funding + the season's distributed-Floobits shareUnit) so the
numbers are grounded, not assumed.

Scenarios:
  1. Equilibrium on the REAL prod funding distribution.
  2. Evenness sweep — flatten funding toward the mean; watch the spread collapse
     (confirms: bunching is driven by funding EVENNESS, not the cost model).
  3. Per-team cost TILT — scale each team's facility costs by its fair-share ratio
     R = funding / league-average. Two directions:
       - equalizer (cost x R^t): rich pay more -> lifts the floor, caps the top.
       - amplifier (cost x R^-t): rich pay less -> widens the spread.
     Prints the per-team cost table AND the effect on the level spread, under both
     today's skew and a flattened (even-engagement) league.

Run: .venv/bin/python facilities_econ_harness.py
"""
import os, sys, sqlite3, statistics, importlib.util
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import (FACILITY_CATALOG, FACILITY_MAX_LEVEL, FACILITY_UPGRADE_COST_SHARES,
                       FACILITY_UPKEEP_SHARES, FUNDING_BASELINE_PER_TEAM, FUNDING_DECAY_RATE)

# Load facilitiesManager directly (skip the heavy managers/__init__ chain).
_spec = importlib.util.spec_from_file_location("facilitiesManager", "managers/facilitiesManager.py")
FM = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(FM)

KEYS = list(FACILITY_CATALOG.keys())
NUM_TEAMS = 24
SEASONS = 30
MAX_TOTAL = FACILITY_MAX_LEVEL * len(KEYS)     # 25
SUSTAIN_FRAC = 0.55                             # a team won't commit > this fraction of income to upkeep
PROD_DB = "data/floosball_prod_latest.db"

# ── Funding source ───────────────────────────────────────────────────────────
def loadProdFunding(season=10):
    """Real per-team inflow (baseline + fan_contributions = current_funding) and
    the share unit (total Floobits distributed that season / 24). Falls back to a
    synthetic skew if the prod DB isn't present."""
    if not os.path.exists(PROD_DB):
        share = 7558.0
        incomes = [int(share * r) for r in
                   (.03,.03,.05,.08,.08,.14,.22,.25,.33,.57,.70,.73,.75,.80,.90,.96,1.31,1.38,1.40,1.48,1.59,1.74,1.78,2.46)]
        return incomes, share, "SYNTHETIC (prod DB absent)"
    c = sqlite3.connect(PROD_DB)
    share = c.execute("select sum(amount) from currency_transactions where season=? and amount>0",
                      (season,)).fetchone()[0] / NUM_TEAMS
    incomes = [v for (v,) in c.execute("select current_funding from team_funding where season=?", (season,))]
    c.close()
    return incomes, share, f"PROD S{season}"

# ── Per-team cost tilt ───────────────────────────────────────────────────────
def tiltMult(funding, leagueMean, mode, t):
    """Cost multiplier for a team given its fair-share ratio R = funding/mean.
    flat -> 1; equalizer -> R^t (rich pay more); amplifier -> R^-t (rich pay less)."""
    R = (funding / leagueMean) if leagueMean > 0 else 1.0
    if mode == "equalizer": return R ** t
    if mode == "amplifier": return R ** (-t)
    return 1.0

# ── One league, run to equilibrium ───────────────────────────────────────────
def runLeague(incomes, share, tiltMode="flat", tilt=0.5):
    mean = statistics.mean(incomes)
    teams = [{"lv": {k: 0 for k in KEYS}, "carry": 0.0, "inc": inc,
              "mult": tiltMult(inc, mean, tiltMode, tilt), "proj": None} for inc in incomes]

    def upk(level, m): return FACILITY_UPKEEP_SHARES[level] * share * m
    def bld(target, m): return FACILITY_UPGRADE_COST_SHARES[target] * share * m

    def decide(t):
        cur = sum(upk(t["lv"][k], t["mult"]) for k in KEYS)
        cands = []
        for k in KEYS:
            l = t["lv"][k]
            if l >= FACILITY_MAX_LEVEL:
                continue
            newUp = cur - upk(l, t["mult"]) + upk(l + 1, t["mult"])
            if newUp > t["inc"] * SUSTAIN_FRAC:
                continue
            if (t["carry"] + t["inc"]) < bld(l + 1, t["mult"]) * 0.5:
                continue
            cands.append((l + 1, newUp, k))
        cands.sort()
        return cands[0][2] if cands else None

    for s in range(1, SEASONS + 1):
        for t in teams:
            treasury = int(t["carry"] + t["inc"])
            if t["proj"] is None:
                k = decide(t)
                if k is not None:
                    tg = t["lv"][k] + 1
                    # cost_shares carries the tilt so resolveSeasonEnd charges the tilted price
                    t["proj"] = {"id": 1, "facility_key": k, "target_level": tg,
                                 "cost_shares": FACILITY_UPGRADE_COST_SHARES[tg] * t["mult"],
                                 "funded": 0, "opened_season": s}
            # upkeep_funded pre-pays the tilt delta so resolveSeasonEnd's (untilted) upkeep waterfall
            # charges the tilted amount: it bills UPKEEP_SHARES[level]*share; we top it to *mult.
            facilities = []
            for k in KEYS:
                lvl = t["lv"][k]
                tiltDelta = FACILITY_UPKEEP_SHARES[lvl] * share * (t["mult"] - 1.0)
                facilities.append({"key": k, "level": lvl,
                                   "upkeep_funded": 0})
                treasury -= max(0, int(round(tiltDelta)))      # pay the tilt surcharge up front
            treasury = max(0, treasury)
            projects = [t["proj"]] if t["proj"] else []
            res = FM.resolveSeasonEnd(facilities, projects, treasury, share, s)
            for f in res["facilities"]:
                t["lv"][f["key"]] = f["level"]
            if t["proj"]:
                pr = res["projects"][0]
                t["proj"] = None if pr["built"] else {**t["proj"], "funded": pr["funded"]}
            t["carry"] = res["leftover"] * FUNDING_DECAY_RATE
    return [sum(t["lv"].values()) for t in teams]

def spread(tot):
    return (f"min={min(tot)} max={max(tot)} range={max(tot)-min(tot)} "
            f"stdev={statistics.pstdev(tot):.1f}")

def flatten(incomes, alpha):
    """alpha=0 -> original distribution; alpha=1 -> every team at the mean."""
    m = statistics.mean(incomes)
    return [m + (1 - alpha) * (v - m) for v in incomes]

# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    incomes, share, src = loadProdFunding()
    incomes = sorted(incomes)
    mean = statistics.mean(incomes)
    print(f"Funding source: {src}   shareUnit={share:.0f}F   mean inflow={mean:.0f}F "
          f"({mean/share:.2f} shares)")

    print("\n[1] EQUILIBRIUM ON REAL FUNDING")
    tot = runLeague(incomes, share)
    print(f"    levels: {sorted(tot)}")
    print(f"    {spread(tot)}  full-max(25): {sum(1 for x in tot if x == MAX_TOTAL)}")

    print("\n[2] EVENNESS SWEEP (flatten funding toward the mean; total held constant)")
    print(f"    {'alpha':>6} {'fund range(sh)':>15} {'levels':>14} {'stdev':>6}  verdict")
    for a in (0.0, 0.25, 0.5, 0.7, 0.85, 1.0):
        inc = flatten(incomes, a)
        tt = runLeague(inc, share)
        sd = statistics.pstdev(tt)
        v = "WIDE" if sd > 4 else "compressing" if sd > 1.5 else "BUNCHED"
        print(f"    {a:>6.2f} {min(inc)/share:>6.2f}-{max(inc)/share:<7.2f} "
              f"{min(tt):>5}-{max(tt):<7} {sd:>6.1f}  {v}")

    print("\n[3] PER-TEAM COST TILT — how the price differs by fair-share ratio R")
    print(f"    (R = team funding / league average; tilt strength t=0.5; shareUnit={share:.0f}F)")
    print(f"    {'R':>5} {'flat Lv5 upkeep':>16} {'equalizer (xR^t)':>22} {'amplifier (xR^-t)':>22}")
    for R in (0.25, 0.5, 1.0, 2.0, 4.0):
        base = FACILITY_UPKEEP_SHARES[5] * share
        eq = base * (R ** 0.5)
        am = base * (R ** -0.5)
        print(f"    {R:>5.2f} {base:>13.0f}F   {eq:>16.0f}F ({R**0.5:.2f}x)   {am:>16.0f}F ({R**-0.5:.2f}x)")

    print("\n    Effect on the SPREAD (today's skew vs a flattened/even-engagement league):")
    for label, inc in (("today's skew", incomes), ("70% flattened", flatten(incomes, 0.70))):
        line = f"      {label:>14}: "
        for mode in ("flat", "equalizer", "amplifier"):
            tt = runLeague(inc, share, tiltMode=mode)
            line += f"{mode}={spread(tt).split('range=')[1].split(' ')[0]}/sd{statistics.pstdev(tt):.1f}  "
        print(line)
    print("\n    (range/stdev of total levels. Note: under a flattened league every R->1, so a")
    print("     fair-share tilt barely moves — it acts only when funding is already skewed.)")
