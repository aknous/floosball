"""The offseason collection shelf must be BUYABLE, not just visible.

⚠️ THE SHELF AND THE TILL HAD TWO DIFFERENT DEFINITIONS OF "COLLECTION CARD", and they
disagreed for exactly the cards the offseason shelf exists to sell.

The shelf is built with `includeCurrentSeason=regularSeasonOver(currentWeek)`, so once
the regular season is over it deliberately stocks CURRENT-season prestige prints: they
can no longer be fielded, which is what turns them from fantasy cards into collectibles.
But `buyFeaturedCard` re-derived the answer from the template as
`is_showpiece or season_created < currentSeason`, which is False for precisely those —
so the shop offered them and the till refused them with

    "Only collection cards are available outside the regular season"

an error whose own wording contradicts the card it is refusing. Reported from production:
in the offseason NO collection card could be bought at all.

The fix is to read `featuredRow.kind` — the shelf's own verdict, recorded when the row
was stocked — so the two agree by construction instead of by keeping two copies of one
rule in sync.

Run: .venv/bin/python test_offseason_collection_buy.py
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DATABASE_DIR', tempfile.mkdtemp(prefix='floo_offseason_buy_'))
import logging; logging.disable(logging.WARNING)

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)

from database.connection import init_db, get_session
from database.models import CardTemplate, FeaturedShopCard, User, UserCurrency
from managers.cardManager import CardManager

init_db()
s = get_session()
SEASON = 5

user = User(username='shopper', clerk_id='ck_shopper', email='shopper@example.test')
s.add(user); s.flush()
s.add(UserCurrency(user_id=user.id, balance=100000)); s.flush()


def template(**kw):
    t = CardTemplate(
        player_id=kw.pop('pid'), player_name=kw.pop('name', 'Prestige Print'),
        position=1, edition='holographic', season_created=kw.pop('season'),
        effect_config={'effectName': 'none'}, sell_value=100, player_rating=88, rarity_weight=10,
        is_showpiece=kw.pop('showpiece', False),
        classification=kw.pop('classification', None),
    )
    s.add(t); s.flush()
    return t


def shelve(t, kind):
    row = FeaturedShopCard(user_id=user.id, season=SEASON, card_template_id=t.id,
                           kind=kind, purchased=False)
    s.add(row); s.flush()
    return row


def buy(t):
    """Attempt an OUTSIDE-the-regular-season purchase. Returns None on success."""
    cm = CardManager(None)
    try:
        cm.buyFeaturedCard(s, user.id, t.id, SEASON, showpieceOnly=True)
        return None
    except ValueError as e:
        return str(e)


print("1. THE REPORTED BUG — a CURRENT-season print stocked on the collection shelf")
# This is what the offseason shelf actually stocks: season_created == currentSeason,
# not a showpiece. Both of the old template-side terms are False for it.
cur = template(pid=101, season=SEASON, classification='mvp')
shelve(cur, 'collection')
err = buy(cur)
expect(f"it is buyable in the offseason (err={err!r})", err is None)

print("\n2. A past-season legacy print still sells")
past = template(pid=102, season=SEASON - 2, classification='champion')
shelve(past, 'collection')
expect("legacy print buyable", buy(past) is None)

print("\n3. A purpose-built showpiece still sells")
show = template(pid=103, season=SEASON, showpiece=True)
shelve(show, 'collection')
expect("showpiece buyable", buy(show) is None)

print("\n4. THE GUARD STILL BITES — a current-season FANTASY card is still a brick")
# Same template shape as case 1; the ONLY difference is the shelf it was stocked on.
# That is the point: the shelf decides, so this must still be refused.
fan = template(pid=104, season=SEASON)
shelve(fan, 'fantasy')
err = buy(fan)
expect(f"current-season fantasy card refused (err={err!r})",
       err is not None and 'collection cards' in err)

print("\n5. During the REGULAR season the gate is off entirely")
fan2 = template(pid=105, season=SEASON)
shelve(fan2, 'fantasy')
cm = CardManager(None)
try:
    cm.buyFeaturedCard(s, user.id, fan2.id, SEASON, showpieceOnly=False)
    ok = True
except ValueError as e:
    ok = False
    print(f"      unexpected: {e}")
expect("a fantasy card sells normally in season", ok)

s.close()
print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — the shelf decides what is collectible and the till honours it.")
