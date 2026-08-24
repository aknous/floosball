"""Once the regular season is over, only collection products are buyable.

Reported: after the season ended the shop and the fantasy page were still fully open --
fantasy packs and singles on sale, powerups on sale, and the fantasy page showing a live
season instead of the locked view and the season leaderboard.

⚠️ ONE ROOT CAUSE FOR BOTH HALVES. `_isRegularSeason` decided the phase from
`Season.currentWeek` and `Season.isComplete`. Measured on production: `seasons.current_week`
read **0** with 28 weeks of season-2 games already final, and there is **no is_complete
column at all**, so that flag lives only in memory and returns False on every load. After
any restart the API reported "regular season" forever, which made every purchase gate
inert AND told the frontend the season was live -- and the frontend's season-over view was
already built and simply never triggered.

The games table is the thing that actually moves, so the phase is derived from it.

Run: ./run_tests.sh offseason_shop_lock
"""
import sys, os, io, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

src = io.open('api/main.py', encoding='utf-8').read()

# ── the phase no longer trusts the stale counters alone ────────────────────
block = src[src.index('def _isRegularSeason'):]
block = block[:block.index('def _isShopOpen')]
expect("the phase is derived from games played, not just the season counters",
       '_regularSeasonWeeksPlayed' in block)
expect("...and 28 weeks in the books ends it regardless of the counters",
       'played >= 28' in block)

helper = src[src.index('def _regularSeasonWeeksPlayed'):src.index('def _isRegularSeason')]
expect("it reads FINAL regular-season games", "LOWER(status) = 'final'" in helper)
expect("...and excludes playoff rounds, which would inflate the week",
       'is_playoff' in helper)
expect("it fails soft rather than raising into a purchase path", 'except Exception' in helper)

# ── every purchase path is gated ───────────────────────────────────────────
def gatedAfter(marker, span=60):
    i = src.index(marker)
    seg = src[i:i + span * 80]
    seg = seg[:seg.index('@app.', 5)] if '@app.' in seg[5:] else seg
    return '_showpieceOnly' in seg or '_requireCollectionOnly' in seg

for ep in ['@app.post("/api/packs/reveal")',
           '@app.post("/api/shop/buy-card")',
           '@app.post("/api/shop/powerups/buy")']:
    expect(f"{ep.split('/api/')[1][:-2]} is gated outside the regular season", gatedAfter(ep))

# ⚠️ Singles need their OWN check: `_requireCollectionOnly` takes a pack type, and a
# single is a card. It has to look at the shelf the card came from.
buy = src[src.index('@app.post("/api/shop/buy-card")'):]
buy = buy[:buy.index('@app.post', 5)]
expect("the single-card gate distinguishes the collection shelf",
       "'collection'" in buy and 'FeaturedShopCard' in buy)
expect("...using the real column name, card_template_id",
       'card_template_id' in buy and 'FSC.template_id' not in buy)

# ── the frontend flag comes from the same source ───────────────────────────
expect("regular_season_over is published from _isRegularSeason, not its own arithmetic",
       "'regular_season_over': not _isRegularSeason()" in src)
expect("no inline week arithmetic is left in the season payload",
       "'regular_season_over': current_season.currentWeek" not in src)

# ── the query the gate depends on actually runs ────────────────────────────
from database.connection import get_session
from database.models import FeaturedShopCard as F
s = get_session()
try:
    s.query(F.kind).filter(F.user_id == 1, F.season == 1, F.card_template_id == 1).first()
    ok = True
except Exception as e:
    ok = False
    print('        query error:', e)
finally:
    s.close()
expect("the single-card gate's query is valid against the live schema", ok)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — the season being over is read from the games, and every till honours it.")
