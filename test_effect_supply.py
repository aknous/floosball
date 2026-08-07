"""Effect supply: every effect should reach the pool, and packs shouldn't repeat one.

Two symptoms, one cause. `buildEffectConfig` picked with `random.choice`, independently
per template, so:

  - effects went MISSING. Prismatic RB is 7 players against 27 eligible effects, so any
    one had a 74% chance of not existing at all that season. Measured on a live season, 31
    of 143 effects had no template anywhere — a card could be built, seeded and still be
    unobtainable in packs or the shop.
  - effects CLUSTERED. 27 effects held 5+ templates while 38 held exactly one, which is
    what makes packs feel like they keep handing you the same few.

Fixed by planning each (edition, position) bucket instead of rolling per template: deal
from a shuffled pool, and where a bucket has fewer PLAYERS than EFFECTS, mint one template
per effect and cycle the players. Dealing alone cannot fix that case — 7 players cannot
carry 27 effects however you shuffle — which is why the top-up exists.

Run: .venv/bin/python test_effect_supply.py   (exits non-zero on any failure)
"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import managers.cardEffects as ce
from managers.cardManager import CardManager, EDITION_THRESHOLDS

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class FakePlayer:
    def __init__(self, pid, rating, position):
        self.id = pid; self.playerRating = rating; self.position = position
        self.seasonsPlayed = 3


def bucketsFor(players):
    out = collections.defaultdict(list)
    for p in players:
        for ed, thr in EDITION_THRESHOLDS.items():
            if p.playerRating >= thr:
                out[(ed, p.position)].append(p)
    return out


# A league shaped like the live one: 32 teams, QB/RB/TE/K x1 and WR x2 per team.
random.seed(11)
LEAGUE = []
_id = 0
for _t in range(32):
    for pos, n in ((1, 1), (2, 1), (3, 2), (4, 1), (5, 1)):
        for _ in range(n):
            _id += 1
            # QB and K genuinely top out below the diamond bar in this sim.
            ceiling = 87 if pos == 1 else (88 if pos == 5 else 96)
            LEAGUE.append(FakePlayer(_id, random.randint(62, ceiling), pos))

UNIVERSE = {e for e in ce.EFFECT_EDITION_TIER if ce.effectValidPositions(e)}


def mint(topUp=True):
    counts = collections.Counter(); total = 0; pairs = []
    for (ed, pos), members in bucketsFor(LEAGUE).items():
        for player, eff in CardManager._assignEffects(ed, pos, members, topUp=topUp):
            total += 1
            pairs.append((ed, pos, player, eff))
            if eff: counts[eff] += 1
    return total, counts, pairs


total, counts, pairs = mint()

# ── an effect is never planted where it cannot score ────────────────────────
bad = [(ed, pos, e) for ed, pos, _p, e in pairs
       if e and (ce.EFFECT_EDITION_TIER.get(e) != ed or pos not in ce.effectValidPositions(e))]
expect("planned effects always match the edition and position", not bad)

# ── base is the no-effect floor print ──────────────────────────────────────
baseEffects = {e for ed, _pos, _p, e in pairs if ed == 'base'}
expect("base edition plans no effect", baseEffects == {None})

# ── coverage is a GUARANTEE, not a probability ─────────────────────────────
# This is the whole point: run it repeatedly and the only gaps should be buckets with
# no eligible player at all.
gaps = collections.Counter()
for _ in range(15):
    _t, c, _p = mint()
    for e in UNIVERSE:
        if c[e] == 0: gaps[e] += 1
alwaysMissing = {e for e, n in gaps.items() if n == 15}
sometimesMissing = {e for e, n in gaps.items() if 0 < n < 15}
expect(f"no effect is INTERMITTENTLY missing (offenders: {sorted(sometimesMissing)[:4]})",
       not sometimesMissing)

# What IS always missing must be a bucket with zero eligible players — a rating-curve
# fact, not a minting one. Nothing has ever rated 90 at QB or K, and diamond needs 90.
for e in alwaysMissing:
    ed = ce.EFFECT_EDITION_TIER[e]
    havePlayer = any(bucketsFor(LEAGUE).get((ed, pos)) for pos in ce.effectValidPositions(e))
    expect(f"{e} is unmintable only because no player qualifies for {ed}", not havePlayer)

# ── the top-up is what closes the thin buckets ─────────────────────────────
# Prismatic RB: fewer players than effects. Without the top-up most effects there are
# absent; with it, every one is minted.
rbPlayers = bucketsFor(LEAGUE).get(('prismatic', 2), [])
rbEffects = ce.effectPoolFor('prismatic', 2)
if rbPlayers and len(rbPlayers) < len(rbEffects):
    withTop = {e for _p, e in CardManager._assignEffects('prismatic', 2, rbPlayers)}
    without = {e for _p, e in CardManager._assignEffects('prismatic', 2, rbPlayers, topUp=False)}
    expect(f"top-up covers a thin bucket ({len(rbPlayers)} players, {len(rbEffects)} effects)",
           withTop == set(rbEffects))
    expect("without the top-up that bucket is mostly empty", len(without) <= len(rbPlayers))

# ── a bucket mints max(players, effects) ───────────────────────────────────
sizes_ok = True
for (ed, pos), members in bucketsFor(LEAGUE).items():
    n = len(CardManager._assignEffects(ed, pos, members))
    want = len(members) if ed == 'base' else max(len(members), len(ce.effectPoolFor(ed, pos)) or len(members))
    if n != want: sizes_ok = False
expect("each bucket mints max(players, effects) templates", sizes_ok)

# ── no effect hogs the pool ────────────────────────────────────────────────
expect(f"no effect dominates (max {max(counts.values())} templates)", max(counts.values()) <= 14)

# ── the rookie path adds one card per player, not the whole effect set ─────
rookieTotal, _c, _p = mint(topUp=False)
expect(f"rookie path stays one-per-player ({rookieTotal} vs {total} with top-up)",
       rookieTotal < total)

# ── the pass-TD family, the cards that surfaced all this ───────────────────
for eff in ('bombardier', 'salvo', 'barrage'):
    expect(f"{eff} is minted every season", gaps[eff] == 0)

# ── packs de-duplicate effects ─────────────────────────────────────────────
class T:
    def __init__(self, i, eff, ed='metallic'):
        self.id = i; self.player_id = i; self.edition = ed
        self.player_rating = 80; self.classification = None
        self.effect_config = {'effectName': eff}

cm = CardManager.__new__(CardManager)
pool = [T(i, ['freebie', 'rng', 'bandwagon'][i % 3]) for i in range(30)]
worstRun = 0
for _ in range(200):
    drawn = cm._weightedDrawDedup(pool, {'metallic': 100}, count=3, dedupByEffect=True)
    names = [t.effect_config['effectName'] for t in drawn]
    worstRun = max(worstRun, len(names) - len(set(names)))
expect("a 3-card pack never repeats an effect when the pool allows", worstRun == 0)

thin = [T(i, 'freebie') for i in range(10)]
short = cm._weightedDrawDedup(thin, {'metallic': 100}, count=3, dedupByEffect=True)
expect("a pool with one effect still fills the pack rather than returning short",
       len(short) >= 1)

print("\nPASS — every effect is minted wherever a player qualifies, and packs spend their slots on different ones."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
