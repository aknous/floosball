"""Regression: a trade records the roster moves it FORCED, not just the assets.

Reported by the owner (2026-09-30): "when teams make midseason trades, we need to see
what other transactions the team did to get a new player on the roster. did they cut a
player? promote a prospect? none of that is shown". The buyer's cut
(`_cutToMakeRoom`) and the seller's backfill (`_installBackfill`) went to the server log
and nowhere else, so the ledger showed a team trading for a quarterback and never said
it had released one to make room.

Runs the real `settleTrade`; only the backfill SEARCH, the cut fee and card minting are
stubbed (not what this checks). Persistence runs against a throwaway database.
"""
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_forced_moves_')

from managers import tradeManager                      # noqa: E402
import managers.frontOfficeBrain as fob                # noqa: E402
from database.connection import init_db, get_session   # noqa: E402
from database.models import Trade                      # noqa: E402

init_db()
fails = []


def expect(desc, ok):
    print(("  [OK] " if ok else "  [FAIL] ") + desc)
    if not ok:
        fails.append(desc)


class Pos:
    def __init__(self, name, value):
        self.name, self.value = name, value


class Guy:
    def __init__(self, pid, name, rating, team=None, prospect=False):
        self.id, self.name = pid, name
        self.position = Pos('QB', 1)
        self.playerRating, self.term, self.termRemaining = rating, 2, 2
        self.team, self.previousTeam = team, None
        self.willRetire, self.freeAgentYears, self.teamResignCount = False, 0, 0
        self.is_prospect, self.prospect_seasons, self.drafting_team_id = prospect, 0, None


class Club:
    def __init__(self, tid, name):
        self.id, self.name = tid, name
        self.rosterDict, self.prospects = {}, []

    def assignPlayerNumber(self, p):
        pass


class PM:
    def __init__(self, freeAgents):
        self.freeAgents = list(freeAgents)

    def promotionTerm(self, p):
        return 2

    def releasePlayerToFreeAgency(self, player, team, _h):
        self.freeAgents.append(player)
        player.team = 'Free Agent'


class SM:
    def __init__(self, pm):
        self.playerManager = pm
        self.currentSeason = type('S', (), {'seasonNumber': 8})()
        self.recap = []

    def _chargeCutFee(self, team, fee):
        return True

    def _recordOffseasonEvent(self, eventType, **kw):
        self.recap.append((eventType, kw))


def settle(backfillKind):
    seller, buyer = Club(1, 'Sellers'), Club(2, 'Buyers')
    sold = Guy(101, 'Sold QB', 85, seller)
    old = Guy(102, 'Old QB', 70, buyer)
    seller.rosterDict = {'qb': sold}
    buyer.rosterDict = {'qb': old}
    if backfillKind == 'prospect':
        repl = Guy(103, 'Kid QB', 68, prospect=True)
        seller.prospects.append(repl)
    else:
        repl = Guy(103, 'Street QB', 66, 'Free Agent')
    pm = PM([] if backfillKind == 'prospect' else [repl])
    sm = SM(pm)
    tradeManager._findBackfill = lambda *a, **kw: (backfillKind, repl)
    winner = type('W', (), {'pieces': [], 'value': 10.0, 'team': buyer, 'why': None})()
    listing = type('L', (), {'team': seller, 'player': sold, 'trigger': 'expiring_surplus',
                             'ask': 1.0, 'floor': 1.0, 'why': None})()
    return tradeManager.settleTrade(sm, listing, winner, season=8, week=18), sm


fob.cutFeeFor = lambda p: 120
tradeManager._mintTradedCard = lambda *a, **kw: None

for kind, label, recapType in (('free_agent', 'signing', 'fa_pick'),
                               ('prospect', 'promotion', 'promotion')):
    print(f"Trade with a buyer cut and a seller {label}")
    manifest, sm = settle(kind)
    expect("the trade settled", manifest is not None)
    moves = manifest.get('moves') or []
    cut = next((m for m in moves if m['kind'] == 'cut'), None)
    fill = next((m for m in moves if m['kind'] == label), None)
    expect("the buyer's cut is in the manifest, with its fee and team",
           cut and cut['name'] == 'Old QB' and cut['fee'] == 120 and cut['teamName'] == 'Buyers')
    expect(f"the seller's {label} is in the manifest",
           fill and fill['teamName'] == 'Sellers' and 'Sold QB' in (fill['note'] or ''))

    s = get_session()
    row = s.get(Trade, manifest['tradeId'])
    stored = (row.assets_json or {}).get('moves') or []
    s.close()
    expect("both moves are saved on the trade row", {m['kind'] for m in stored} == {'cut', label})

    recap = {(t, kw.get('playerName'), kw.get('tradeId')) for t, kw in sm.recap}
    expect("the cut is a recap event carrying the trade id",
           ('cut', 'Old QB', manifest['tradeId']) in recap)
    expect(f"the {label} is a '{recapType}' recap event carrying the trade id",
           (recapType, fill and fill['name'], manifest['tradeId']) in recap)

if fails:
    print(f"FAIL ({len(fails)})")
    raise SystemExit(1)
print("ALL PASS")
