"""Regression: settling a move into a top-3 slot that is paid for with a roster star.

The star rule (`TradeMarket._starPaymentFor`) means a top-3 trade-up carries a roster
player, and `settlePickTrade` used to move picks and prospects only. A star needs a slot
on the seller's roster: its open one at his position, or its weakest player there is cut
(fee and move recorded). The buyer's emptied slot is left for the FA draft.

Runs the real `settlePickTrade` against a throwaway database; card minting is stubbed.
"""
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_star_settle_')

from managers import tradeManager                      # noqa: E402
import managers.frontOfficeBrain as fob                # noqa: E402
from database.connection import init_db, get_session   # noqa: E402
from database.models import DraftPick                  # noqa: E402
from floosball_player import Position                  # noqa: E402
from test_trade_market import FakeTeam, FakePlayer     # noqa: E402

init_db()
SEASON = 70
fails = []


def expect(desc, ok):
    print(("  [OK] " if ok else "  [FAIL] ") + desc)
    if not ok:
        fails.append(desc)


class PM:
    def __init__(self):
        self.freeAgents = []

    def releasePlayerToFreeAgency(self, player, team, _h):
        self.freeAgents.append(player)
        player.team = 'Free Agent'


class SM:
    def __init__(self):
        self.playerManager = PM()
        self.currentSeason = type('S', (), {'seasonNumber': SEASON})()
        self.recap = []

    def _chargeCutFee(self, team, fee):
        return True

    def _recordOffseasonEvent(self, eventType, **kw):
        self.recap.append((eventType, kw))


fob.cutFeeFor = lambda p: 90
tradeManager._mintTradedCard = lambda *a, **kw: None

seller, buyer = FakeTeam(1, 'Sellers'), FakeTeam(2, 'Buyers')
oldQB = FakePlayer(10, 70, Position.QB, termRemaining=3, name='Old QB')
star = FakePlayer(20, 90, Position.QB, termRemaining=3, name='Star QB')
seller.rosterDict = {'qb': oldQB}
buyer.rosterDict = {'qb': star}
oldQB.team, star.team = seller, buyer

s = get_session()
top = DraftPick(season=SEASON, round_number=1, original_team_id=1, current_owner_id=1)
swap = DraftPick(season=SEASON, round_number=1, original_team_id=2, current_owner_id=2)
s.add_all([top, swap]); s.commit()
topId, swapId = top.id, swap.id
s.close()

listing = type('L', (), {'team': seller, 'pick': {'id': topId, 'season': SEASON, 'round': 1, 'slot': 1},
                         'floor': 10.0, 'why': None})()
pieces = [{'kind': 'pick', 'id': swapId, 'name': f'S{SEASON} R1 pick'},
          {'kind': 'player', 'id': 20, 'name': 'Star QB'}]
winner = type('W', (), {'team': buyer, 'pieces': pieces, 'value': 50.0, 'why': None})()

sm = SM()
manifest = tradeManager.settlePickTrade(sm, listing, winner, SEASON)
expect("the trade settled", manifest is not None)
expect("the star is on the seller's roster at QB", seller.rosterDict.get('qb') is star and star.team is seller)
expect("the seller's weaker QB was cut to make room", oldQB.team == 'Free Agent')
expect("the cut is recorded with its fee",
       any(m['kind'] == 'cut' and m['name'] == 'Old QB' and m.get('fee') == 90
           for m in (manifest or {}).get('moves', [])))
expect("the buyer's slot is left open for the FA draft", buyer.rosterDict.get('qb') is None)
s = get_session()
expect("the top pick now belongs to the buyer", s.get(DraftPick, topId).current_owner_id == 2)
expect("the buyer's own pick went to the seller", s.get(DraftPick, swapId).current_owner_id == 1)
s.close()

if fails:
    print(f"FAIL ({len(fails)})")
    raise SystemExit(1)
print("ALL PASS")
