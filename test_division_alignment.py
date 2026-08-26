"""Division membership is defined in config and does not move.

Owner, 2026-08-23: "divisions need to be defined in config. either a list of teams per
division, or each team config includes the assigned division."

⚠️ WHAT WENT WRONG. `_assignDivisions` used to slice `league.teamList` into fours, and its
docstring claimed that was stable ("nothing here reshuffles annually"). `league.teamList`
is a mutable list, and the playoff seeding overwrote it with SEED order — so the next
season's divisions were the previous season's final standings in fours. Measured on a
fresh database over three seasons, membership changed at BOTH boundaries; on a 20-season
database, at 19 of 20. Production was masked only because `createLeagues` restores the
saved order at boot and a deploy usually lands between the playoffs and the next schedule
generation.

Two independent fixes, and this pins both:
  1. membership comes from config's `divisionDistribution`, BY NAME — so no list order
     can affect it;
  2. the playoff seeding no longer writes seed order back into `league.teamList` — so the
     positional fallback is stable too.

Run: .venv/bin/python test_division_alignment.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import json

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from managers.seasonManager import SeasonManager

NAMES = {'A': ['A1', 'A2', 'A3', 'A4'], 'B': ['B1', 'B2', 'B3', 'B4']}
DIST = {
    'A1': ['t1', 't2', 't3', 't4'],     'A2': ['t5', 't6', 't7', 't8'],
    'A3': ['t9', 't10', 't11', 't12'],  'A4': ['t13', 't14', 't15', 't16'],
    'B1': ['u1', 'u2', 'u3', 'u4'],     'B2': ['u5', 'u6', 'u7', 'u8'],
    'B3': ['u9', 'u10', 'u11', 'u12'],  'B4': ['u13', 'u14', 'u15', 'u16'],
}


class _Team:
    def __init__(self, name): self.name, self.division = name, None

class _League:
    def __init__(self, name, teams): self.name, self.teamList = name, teams

class _Stub(SeasonManager):
    """`_assignDivisions` only reaches leagueManager, the division helpers and the
    service container, so it can be exercised without booting the app."""
    def __init__(self, leagues, dist):
        self._dist = dist
        self.leagueManager = type('LM', (), {'leagues': leagues})()
        self.serviceContainer = type('SC', (), {'getService': staticmethod(lambda _n: None)})()
    def _divisionNames(self, leagueName): return list(NAMES[leagueName])
    def _divisionDistribution(self): return dict(self._dist)


def build(orderA=None, orderB=None):
    a = [_Team(n) for n in (orderA or [n for d in NAMES['A'] for n in DIST[d]])]
    b = [_Team(n) for n in (orderB or [n for d in NAMES['B'] for n in DIST[d]])]
    return [_League('A', a), _League('B', b)]


def divisionsOf(leagues):
    out = {}
    for lg in leagues:
        for t in lg.teamList:
            out.setdefault(t.division, set()).add(t.name)
    return out


# ── config decides, and list order cannot ─────────────────────────────────
leagues = build()
expect("a valid config map assigns divisions", _Stub(leagues, DIST)._assignDivisions())
fromConfig = divisionsOf(leagues)
expect("membership matches config exactly",
       fromConfig == {d: set(v) for d, v in DIST.items()})

# The exact failure that shipped: the list arrives in some OTHER order (seed order, after
# a playoff run). Membership must not notice.
shuffledA = ['t16', 't1', 't9', 't5', 't2', 't13', 't10', 't6',
             't3', 't14', 't11', 't7', 't4', 't15', 't12', 't8']
reordered = build(orderA=shuffledA)
_Stub(reordered, DIST)._assignDivisions()
expect("⚠️ a REORDERED teamList produces the SAME divisions",
       divisionsOf(reordered) == fromConfig)

# ── it refuses a map that disagrees with the live leagues ─────────────────
# A one-time realignment can move a club between leagues, leaving config's map stale. A
# division spanning two leagues is worse than a wrong-but-shaped one.
crossLeague = dict(DIST)
crossLeague['A1'] = ['t1', 't2', 't3', 'u1']          # u1 is in league B
crossLeague['B1'] = ['u2', 'u3', 'u4', 't4']
mixed = build()
expect("a cross-league map still returns a division-shaped league",
       _Stub(mixed, crossLeague)._assignDivisions())
expect("...by FALLING BACK, so no division spans two leagues",
       all(len({t.name[0] for t in lg.teamList if t.division == d}) == 1
           for lg in mixed for d in NAMES[lg.name]))

wrongSize = dict(DIST)
wrongSize['A1'] = ['t1', 't2', 't3', 't4', 't5']       # five in one, three in another
wrongSize['A2'] = ['t6', 't7', 't8']
sized = build()
_Stub(sized, wrongSize)._assignDivisions()
expect("a map with the wrong division size falls back too",
       all(len([t for t in sized[0].teamList if t.division == d]) == 4 for d in NAMES['A']))

# ── no config map at all still yields a division-shaped league ────────────
plain = build()
expect("an absent config map keeps the positional split working",
       _Stub(plain, {})._assignDivisions()
       and len(divisionsOf(plain)) == len(NAMES['A']) + len(NAMES['B']))

# ── the source of the corruption is gone ──────────────────────────────────
sm = open('/Users/andrew/Projects/floosball/managers/seasonManager.py').read()
# ⚠️ CODE ONLY — the fix's own comment quotes the offending line to explain it, so a
# blanket substring search matches the explanation and reports the bug as still present.
code = [ln for ln in sm.splitlines() if not ln.lstrip().startswith('#')]
expect("⚠️ playoff seeding no longer writes seed order into league.teamList",
       not any('teamList[:] = self._seedTeams(' in ln for ln in code))
expect("nothing else overwrites teamList with an ordering either",
       not any('.teamList[:] =' in ln and '_applyPersistedAlignment' not in ln
               and 'byId[i]' not in ln for ln in code))
expect("it uses a local instead", "seeded = self._seedTeams(league.teamList)" in sm)

# ⚠️ The one-time league realignment is REMOVED (owner, 2026-08-23). It predates
# divisions and moves clubs BETWEEN leagues, which invalidates a curated
# divisionDistribution and forces the positional fallback — measured on a fresh league
# it moved 16 teams at season 2 and re-formed every division. `_applyPersistedAlignment`
# deliberately stays, so a database that already realigned keeps the leagues it has.
lm = open('/Users/andrew/Projects/floosball/managers/leagueManager.py').read()
expect("realignByRecentPerformance is gone", "def realignByRecentPerformance" not in lm)
expect("and nothing calls it",
       "realignByRecentPerformance(" not in lm and "realignByRecentPerformance(" not in sm)
expect("_maybeRealignLeagues is gone", "_maybeRealignLeagues" not in sm)
expect("but the persisted alignment still applies, so live leagues are untouched",
       "_applyPersistedAlignment" in lm)

# ── config carries the map, and it is complete ────────────────────────────
cfg = json.load(open('/Users/andrew/Projects/floosball/config.json'))
dist = cfg.get('divisionDistribution') or {}
divs = cfg.get('divisions') or {}
allNamed = [n for names in divs.values() for n in names]
expect("config.json defines divisionDistribution", bool(dist))
expect("every division name has a member list", sorted(dist) == sorted(allNamed))
members = [t for v in dist.values() for t in v]
expect("every club appears exactly once", len(members) == len(set(members)))
expect("and every club in teamDistribution is placed",
       set(members) == {t for v in (cfg.get('teamDistribution') or {}).values() for t in v})

print("\nPASS — divisions come from config, by name, and no list order can move them."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
