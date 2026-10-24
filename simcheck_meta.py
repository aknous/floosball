"""How strong is each synergy archetype when a player builds it well?

For each archetype, its payoff cards are fixed in the lineup and every other slot is
filled by hill-climbing over every mintable effect valid at that position: try each effect
in each open slot, keep the one that raises the lineup's average week, repeat until
nothing improves. A FREE arm (no fixed cards) finds the best hand overall, which is the
meta the others are measured against.

Players: contender sets (top quarter by rating at each slot), several sets so the search
does not fit one set of players; the TEAM arm draws all six from one team. Rating floors
are ignored, since synthetics put any effect on any player. Every card at tier 1, its
effect's own edition. Real weeks of the season, normal weeks only.

⚠️ Streak cards score at a streak drawn 1-6 (not grown over a season), and favorite-team
cards see a random favorite team, so their archetypes read approximate.

  PROBE_DB=path/to/prod.db PROBE_SEASON=9 .venv/bin/python simcheck_meta.py
  PROBE_ONLY=chance,streak   run some archetypes
  PROBE_SETS=3 player sets, PROBE_NWEEKS=10 weeks per set, PROBE_PASSES=2
"""
import collections
import itertools
import os
import random
import sqlite3
import statistics
import sys

os.environ.setdefault('PROBE_ARM', 'contender')
import simcheck_effect_marginal as sm
import managers.cardEffects as ce
from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
from simcheck_pool_power import loadWeeks, SLOTS

SETS = int(os.environ.get('PROBE_SETS', '3'))
NWEEKS = int(os.environ.get('PROBE_NWEEKS', '10'))
PASSES = int(os.environ.get('PROBE_PASSES', '2'))
SEEDS = int(os.environ.get('PROBE_SEEDS', '8'))
ONLY = set(filter(None, os.environ.get('PROBE_ONLY', '').split(',')))
# PROBE_LIFT="stack=2,synergy=2.5": try a synergy-lift factor without editing the table
# (the factor REPLACES the table's, relative to the card before any synergy lift).
# Keys are the payout keys each effect scales (see cardEffects._SYNERGY_LIFT).
LIFT_KEYS = {
    'stack': {'rewardValue': 'mult'},
    'backfield_buddies': {'rewardValue': 'delta'},
    'synergy': {'perPairMult': 'delta', 'maxMult': 'mult'},
    'homer': {'perPlayerMult': 'delta', 'maxMult': 'mult'},
    'fortitude': {'perCardMult': 'delta'},
    'high_roller': {'perCardMult': 'delta'},
    'charmed': {'perTriggerFP': 'delta'},
    'doubler': {'tdMult': 'mult'},
    'surveyor': {'yardMult': 'mult'},
    'stacked_deck': {'perCardMult': 'delta'},
    'captain': {'perOvershootPct': 'delta'},
    'chain_reaction': {'perCardXMult': 'delta'},
    'anthem': {'tier3FP': 'delta', 'tier4FP': 'delta', 'tier5FP': 'delta'},
    'diversified': {'perTypeFP': 'delta'},
    'wanderer': {'perTeamFP': 'delta'},
    'providence': {'baseMult': 'mult'},
    'catalyst': {'perFpPct': 'delta'},
}
for _item in filter(None, os.environ.get('PROBE_LIFT', '').split(',')):
    _e, _f = _item.split('=')
    ce._SYNERGY_LIFT[_e] = (float(_f), ce._SYNERGY_LIFT.get(_e, (None, LIFT_KEYS.get(_e)))[1])

ARCHETYPES = {
    'free':      [],
    'trigger':   ['bonus_round', 'chain_reaction'],
    'trigger+fh': ['bonus_round', 'full_roster'],
    'copycat':   ['copycat'],
    'lemons':    ['double_down'],
    'fpx_stack': ['stacked_deck', 'captain'],
    'flat_stack': ['anthem', 'conductor'],
    'chance':    ['high_roller', 'advantage'],
    'catalyst':  ['catalyst', 'providence'],
    'charmed':   ['charmed', 'high_roller'],
    'streak':    ['fortitude'],
    'stat_amp':  ['doubler', 'surveyor'],
    'precision': ['sharpshooter'],
    'team':      ['stack', 'synergy'],
    'homer':     ['homer', 'synergy'],
    'diverse':   ['diversified', 'wanderer'],
    'last_resort': ['last_resort'],
}
TEAM_ARCHETYPES = {'team', 'homer'}


def substrates(pool):
    """Each archetype's supporting cast: the cards its payoffs count or act on."""
    allEffects = set().union(*pool.values())
    detail = lambda e: (ce.EFFECT_DETAIL_TEMPLATES.get(e) or '').lower()
    cfg = lambda e: ce.buildEffectConfig(ce.EFFECT_EDITION_TIER[e], 85, min(
        ce.effectValidPositions(e) or {1}), forceEffect=e).get('primary', {})
    chance = {e for e in allEffects if cfg(e).get('isChanceEffect')}
    streak = {e for e in allEffects if ce.EFFECT_CATEGORY.get(e) == 'streak'}
    fpx = {e for e in allEffects if ce.EFFECT_OUTPUT_TYPE.get(e) == 'fpx'}
    fp = {e for e in allEffects if ce.EFFECT_OUTPUT_TYPE.get(e) == 'fp'}
    stat = {e for e in allEffects if ' td' in detail(e) or 'yard' in detail(e)}
    return {'streak': streak, 'chance': chance, 'catalyst': chance, 'charmed': chance, 'fpx_stack': fpx,
            'flat_stack': fp, 'stat_amp': stat}


def mintable():
    pool = collections.defaultdict(set)
    for ed in sm.EDITIONS:
        for pos in (1, 2, 3, 4, 5):
            for e in ce.effectPoolFor(ed, pos):
                if ce.EFFECT_OUTPUT_TYPE.get(e) != 'floobits':
                    pool[pos].add(e)
    return pool


CFG_CACHE = {}


def cfgFor(effect, pid, pos, rating):
    key = (effect, pid, pos)
    if key not in CFG_CACHE:
        if effect is None:
            CFG_CACHE[key] = (sm.blankConfig(), 'base')
        else:
            ed = ce.EFFECT_EDITION_TIER[effect]
            CFG_CACHE[key] = (ce.buildEffectConfig(ed, rating, pos, forceEffect=effect), ed)
    return CFG_CACHE[key]


class World:
    def __init__(self, conn, season):
        self.byWeek, self.meta = loadWeeks(conn, season)
        self.seasonsPlayed = dict(conn.execute("select id, seasons_played from players"))
        self.seasonInfo = sm.seasonContext(self.byWeek, self.meta)
        self.extras = sm.loadExtras(conn, season)
        self.weeks = sorted(w for w in self.byWeek if w >= 3)
        self.teamOf = {}
        for (pid, wk), tid in self.extras[0].items():
            self.teamOf[pid] = tid
        ratings = collections.defaultdict(list)
        self.played = collections.defaultdict(set)
        for wk, byPos in self.byWeek.items():
            for p, rows in byPos.items():
                for pid, _ in rows:
                    ratings[p].append(self.meta.get(pid, ('', 0))[1])
                    self.played[pid].add(wk)
        self.floor = {p: sorted(r)[int(0.75 * (len(r) - 1))] for p, r in ratings.items()}
        self.lastTeam = 0
        self.posOf = {pid: p for byPos in self.byWeek.values() for p, rows in byPos.items()
                      for pid, _ in rows}

    def regulars(self, pos):
        return [pid for pid, p in self.posOf.items() if p == pos
                and len(self.played[pid]) >= 0.8 * len(self.weeks)]

    def playerSet(self, rng, team=False):
        """Six players for SLOTS. team=True draws all six from one team's regulars."""
        if team:
            byTeam = collections.defaultdict(lambda: collections.defaultdict(list))
            for pid, p in self.posOf.items():
                if len(self.played[pid]) >= 0.8 * len(self.weeks):
                    byTeam[self.teamOf.get(pid)][p].append(pid)
            ok = [t for t, d in byTeam.items()
                  if all(len(d[p]) >= (2 if p == 3 else 1) for p in (1, 2, 3, 4, 5))]
            team = rng.choice(ok)
            d = byTeam[team]
            wr = rng.sample(d[3], 2)
            self.lastTeam = team
            return [rng.choice(d[1]), rng.choice(d[2]), wr[0], wr[1], rng.choice(d[4]), rng.choice(d[5])]
        out, used = [], set()
        for _, pos in SLOTS:
            pool = [pid for pid in self.regulars(pos) if pid not in used
                    and self.meta.get(pid, ('', 0))[1] >= self.floor[pos]]
            pid = rng.choice(pool)
            used.add(pid)
            out.append(pid)
        return out

    def score(self, effects, players, weeks, users):
        """Mean card bonus (total - raw) of the lineup over `weeks`."""
        out = []
        for wk, user, seed in zip(weeks, users, range(len(weeks))):
            byPid = {pid: st for rows in self.byWeek[wk].values() for pid, st in rows}
            cards = []
            for (eff, pid), (_, pos) in zip(zip(effects, players), SLOTS):
                if pid not in byPid:
                    break
                name, rating = self.meta.get(pid, ('Probe', 80))
                cfg, ed = cfgFor(eff, pid, pos, rating)
                cards.append((pid, pos, byPid[pid], cfg, ed, rating, name, 3))
            else:
                random.seed(seed)
                eq, ctx = sm.buildContext(cards, wk, self.seasonInfo, self.seasonsPlayed,
                                         self.extras, user)
                res = calculateWeekCardBonuses(eq, ctx)
                m = aggregateMultFactors(res.multFactors or [])
                out.append((ctx.weekRawFP + res.totalBonusFP) * m - ctx.weekRawFP)
        return statistics.mean(out) if out else 0.0


def place(core):
    """Slot indexes for the core cards, respecting valid positions; None if impossible."""
    for perm in itertools.permutations(range(6), len(core)):
        if all(SLOTS[i][1] in (ce.effectValidPositions(e) or set()) for e, i in zip(core, perm)):
            return dict(zip(perm, core))
    return None


def search(world, core, team, rng, pool, name=None, substrate=None):
    fixed = place(core)
    if fixed is None:
        return None
    trials = []
    for _ in range(SETS):
        players = world.playerSet(rng, team=team)
        weeks = rng.sample(world.weeks, min(NWEEKS, len(world.weeks)))
        _, _, balances, pickem, results = world.extras
        users = [(rng.choice(balances), rng.choice(pickem) if pickem else None,
                  world.lastTeam if team else
                  (rng.choice(sorted(results[w])) if results.get(w) else 0)) for w in weeks]
        trials.append((players, weeks, users))

    def value(effects):
        return statistics.mean(world.score(effects, p, w, u) for p, w, u in trials)

    def climb(effects):
        best = value(effects)
        for _ in range(PASSES):
            improved = False
            for i, (_, pos) in enumerate(SLOTS):
                if i in fixed:
                    continue
                for e in sorted(pool[pos]):
                    if e in effects:
                        continue
                    trial = effects[:i] + [e] + effects[i + 1:]
                    v = value(trial)
                    if v > best + 0.01:
                        best, effects, improved = v, trial, True
            if not improved:
                break
        return best, effects

    results = [climb([fixed.get(i) for i in range(6)])]
    # A single supporting card is worth little until there are several (Fortitude wants
    # three streak cards, not one), so a one-slot-at-a-time climb from an empty hand never
    # finds the family's own build. Also climb from hands pre-filled with its substrate.
    sub = substrate.get(name) if substrate else None
    if sub:
        seeds = []
        for _ in range(SEEDS):
            effects = [fixed.get(i) for i in range(6)]
            for i, (_, pos) in enumerate(SLOTS):
                if i in fixed:
                    continue
                opts = [e for e in sorted(pool[pos]) if e in sub and e not in effects]
                if opts:
                    effects[i] = rng.choice(opts)
            seeds.append((value(effects), effects))
        results.append(climb(max(seeds)[1]))
    return max(results)


def main():
    conn = sqlite3.connect(f'file:{sm.DB}?mode=ro', uri=True)
    season = int(sm.SEASON) if sm.SEASON else conn.execute(
        "select max(season) from games where status='final'").fetchone()[0]
    world = World(conn, season)
    pool = mintable()
    subs = substrates(pool)
    print(f"{sm.DB} season {season}: {SETS} player sets x {NWEEKS} weeks, tier 1, "
          f"bonus = card FP over the lineup's raw FP\n")
    for name, core in ARCHETYPES.items():
        if ONLY and name not in ONLY:
            continue
        rng = random.Random(sm.SEED)
        got = search(world, core, name in TEAM_ARCHETYPES, rng, pool, name, subs)
        if got is None:
            print(f"  {name:12} cannot place {core}")
            continue
        best, effects = got
        hand = ', '.join(f"{SLOTS[i][0]}:{e or '-'}" for i, e in enumerate(effects))
        print(f"  {name:12} {best:7.1f}   {hand}", flush=True)


if __name__ == '__main__':
    main()
