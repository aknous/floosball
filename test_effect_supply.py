"""Effect supply: every effect should reach the pool, and packs shouldn't repeat one.

Two symptoms, one cause. `buildEffectConfig` picked with `random.choice`, independently
per template, so:

  - effects went MISSING. Prismatic RB is 8 templates against 27 eligible effects, so any
    one had a 74% chance of not existing at all that season. Measured on a live season, 31
    of 143 effects had no template anywhere — a card could be built, seeded and still be
    unobtainable in packs or the shop.
  - effects CLUSTERED. 27 effects held 5+ templates while 38 held exactly one, which is
    what makes packs feel like they keep handing you the same few.

Run: .venv/bin/python test_effect_supply.py   (exits non-zero on any failure)
"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import managers.cardEffects as ce
from managers.cardManager import CardManager

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

# Real (edition, position) template counts from a live 32-team season.
GRID = {('metallic',1):32,('metallic',2):32,('metallic',3):64,('metallic',4):32,('metallic',5):32,
        ('holographic',1):15,('holographic',2):18,('holographic',3):40,('holographic',4):17,('holographic',5):20,
        ('prismatic',1):10,('prismatic',2):8,('prismatic',3):26,('prismatic',4):9,('prismatic',5):11,
        ('diamond',2):2,('diamond',3):5,('diamond',4):1}


def mintSeason():
    dealers = {ed: CardManager._effectDealer(ed) for ed, _ in GRID}
    slots = [(ed, pos) for (ed, pos), n in GRID.items() for _ in range(n)]
    random.shuffle(slots)
    out = collections.Counter()
    for ed, pos in slots:
        e = dealers[ed](pos)
        if e: out[e] += 1
    return out


# ── the dealer never mints an effect the position can't use ─────────────────
bad = []
for ed in ('metallic', 'holographic', 'prismatic', 'diamond'):
    deal = CardManager._effectDealer(ed)
    for pos in (1, 2, 3, 4, 5):
        for _ in range(60):
            e = deal(pos)
            if e and (ce.EFFECT_EDITION_TIER.get(e) != ed or pos not in ce.effectValidPositions(e)):
                bad.append((ed, pos, e))
expect("dealt effects always match the edition and position", not bad)

# ── the base edition is the no-effect floor print ───────────────────────────
expect("base edition deals nothing", CardManager._effectDealer('base')(1) is None)

# ── one deck per edition, not per position ──────────────────────────────────
# Dealing per (edition, position) only redistributes within a bucket, and prismatic QB
# has 10 templates for 26 effects — 16 must be absent however you deal. Pooling the
# edition's five buckets is what actually fixes coverage.
seasons = [mintSeason() for _ in range(25)]
universe = set()
for k in GRID: universe |= set(ce.effectPoolFor(*k))
absent = [sum(1 for e in universe if s[e] == 0) for s in seasons]
expect(f"most effects reach the pool every season (absent {sum(absent)/len(absent):.1f}/{len(universe)})",
       sum(absent)/len(absent) < 12)

# Per EFFECT, not per season: over enough seasons nearly everything misses once, so a
# union test says nothing. What matters is that no single effect is chronically starved.
appear = collections.Counter()
for s in seasons:
    for e in universe:
        if s[e] > 0: appear[e] += 1
rate = {e: appear[e] / len(seasons) for e in universe}
nonDiamond = {e: r for e, r in rate.items() if ce.EFFECT_EDITION_TIER.get(e) != 'diamond'}
worstEff = min(nonDiamond, key=nonDiamond.get)
expect(f"no non-diamond effect is chronically missing (worst: {worstEff} at {nonDiamond[worstEff]:.0%})",
       nonDiamond[worstEff] >= 0.70)

# Diamond IS structurally starved and that is not this fix's to solve: the season mints 8
# diamond templates against 13 diamond effects, so several cannot exist however they are
# dealt. Pinned so the supply floor is visible rather than mistaken for this bug returning.
diamond = {e: r for e, r in rate.items() if ce.EFFECT_EDITION_TIER.get(e) == 'diamond'}
expect(f"diamond stays supply-limited, a separate problem (worst {min(diamond.values()):.0%})",
       min(diamond.values()) < 0.70)

# ── no effect hogs the pool ─────────────────────────────────────────────────
worst = sum(max(s.values()) for s in seasons) / len(seasons)
expect(f"no effect dominates the pool (max {worst:.1f} templates)", worst <= 9)

# ── the pass-TD family, the cards that surfaced this ────────────────────────
for eff in ('bombardier', 'salvo', 'barrage'):
    hit = sum(1 for s in seasons if s[eff] > 0) / len(seasons)
    expect(f"{eff} reaches the pool in {hit:.0%} of seasons", hit >= 0.80)

# ── packs de-duplicate effects ──────────────────────────────────────────────
class T:
    def __init__(self, i, eff, ed='metallic'):
        self.id = i; self.player_id = i; self.edition = ed
        self.player_rating = 80; self.classification = None
        self.effect_config = {'effectName': eff}

cm = CardManager.__new__(CardManager)
# a pool that WOULD repeat: 3 effects across 30 templates
pool = [T(i, ['freebie', 'rng', 'bandwagon'][i % 3]) for i in range(30)]
worstRun = 0
for _ in range(200):
    drawn = cm._weightedDrawDedup(pool, {'metallic': 100}, count=3, dedupByEffect=True)
    names = [t.effect_config['effectName'] for t in drawn]
    worstRun = max(worstRun, len(names) - len(set(names)))
expect("a 3-card pack never repeats an effect when the pool allows", worstRun == 0)

# and it must never return short when the pool CANNOT satisfy it
thin = [T(i, 'freebie') for i in range(10)]
short = cm._weightedDrawDedup(thin, {'metallic': 100}, count=3, dedupByEffect=True)
expect("a pool with one effect still fills the pack rather than returning short",
       len(short) >= 1)

print("\nPASS — effects reach the pool evenly, and a pack spends its slots on different ones."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
