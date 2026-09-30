"""Regression: the one-shot boot backfill of roster moves on older in-season trades.

Trades settled before 2026-09-30 never recorded the buyer's cut or the seller's
replacement. `connection._backfillTradeMoves` reconstructs them from the game log.
Checked on a production copy before writing this test: 7 trades each got one cut and
one signing, the swap got an empty list, no offseason trade was touched.
"""
import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_trade_moves_bf_')

from database import connection                                       # noqa: E402
from database.connection import init_db, get_session                   # noqa: E402
from database.models import (AppSetting, Game, GamePlayerStats, Player,  # noqa: E402
                             Trade)

init_db()
fails = []


def expect(desc, ok):
    print(("  [OK] " if ok else "  [FAIL] ") + desc)
    if not ok:
        fails.append(desc)


s = get_session()
# Team rows carry many required rating columns this test does not care about; fill every
# NOT NULL column without a default from the live schema rather than hardcoding the list.
from sqlalchemy import text                                           # noqa: E402
cols = [r for r in s.execute(text("PRAGMA table_info(teams)")).fetchall()
        if r[3] and r[4] is None and r[1] != 'id']


def addTeam(name):
    vals = {c[1]: (name if c[2].upper().startswith(('VARCHAR', 'TEXT')) else 0) for c in cols}
    s.execute(text(f"INSERT INTO teams ({', '.join(vals)}) VALUES ({', '.join(':' + k for k in vals)})"), vals)
    return s.execute(text("SELECT id FROM teams WHERE name = :n"), {'n': name}).scalar()


S, B, O = addTeam('Sellers'), addTeam('Buyers'), addTeam('Others')

QB, WR = 1, 3
players = {}
for key, pos in [('sold', QB), ('bQB', QB), ('fa', QB), ('kid', QB),
                 ('sWR', WR), ('bWR1', WR), ('bWR2', WR), ('swapWR', WR), ('offQB', QB)]:
    p = Player(name=key, position=pos)
    s.add(p); s.flush()
    players[key] = p.id

games = {}


def game(season, week):
    if (season, week) not in games:
        g = Game(season=season, week=week, home_team_id=S, away_team_id=B, is_playoff=False)
        s.add(g); s.flush()
        games[(season, week)] = g.id
    return games[(season, week)]


def played(key, team, season, weeks):
    for w in weeks:
        s.add(GamePlayerStats(game_id=game(season, w), player_id=players[key], team_id=team))


# Season 1 history: the free agent has played before, the kid never has.
played('fa', O, 1, [1, 2])
# Season 2, trade A at week 15 (QB): buyer cuts bQB; seller signs fa.
played('sold', S, 2, range(1, 16)); played('sold', B, 2, range(16, 20))
played('bQB', B, 2, range(1, 16))
played('fa', S, 2, range(16, 20))
# Season 2, trade B at week 15 (WR): two buyer WRs both stop at 15 -> ambiguous, skip.
played('sWR', S, 2, range(1, 16))
played('bWR1', B, 2, range(1, 16)); played('bWR2', B, 2, range(1, 16))
# Season 3, trade C at week 15 (QB): the seller promotes the kid (no prior games).
played('offQB', S, 3, range(1, 16))
played('kid', S, 3, range(16, 20))


def trade(season, phase, soldKey, pos, pieces=(), moves=None):
    assets = {'aGave': [{'kind': 'player', 'id': players[soldKey], 'name': soldKey, 'detail': pos}],
              'bGave': [{'kind': 'player', 'id': players[k], 'name': k} for k in pieces]}
    if moves is not None:
        assets['moves'] = moves
    t = Trade(season=season, week=15 if phase == 'in_season' else 0, phase=phase,
              team_a_id=S, team_b_id=B, assets_json=assets)
    s.add(t); s.flush()
    return t.id


tA = trade(2, 'in_season', 'sold', 'QB')
tB = trade(2, 'in_season', 'sWR', 'WR')
tSwap = trade(2, 'in_season', 'sWR', 'WR', pieces=['swapWR'])
tC = trade(3, 'in_season', 'offQB', 'QB')
tOff = trade(2, 'offseason', 'sold', 'QB')
tDone = trade(2, 'in_season', 'sold', 'QB', moves=[{'kind': 'cut', 'name': 'already'}])
s.query(AppSetting).filter(AppSetting.key == connection._TRADE_MOVES_MARKER).delete()
s.commit(); s.close()

connection._backfillTradeMoves()


def movesOf(tid):
    s2 = get_session()
    try:
        return (s2.get(Trade, tid).assets_json or {}).get('moves')
    finally:
        s2.close()


a = movesOf(tA)
expect("clean trade: one cut and one signing",
       a is not None and [(m['kind'], m['name'], m['teamName']) for m in a]
       == [('cut', 'bQB', 'Buyers'), ('signing', 'fa', 'Sellers')])
expect("...notes name the traded player", a and all('sold' in m['note'] for m in a))
expect("...no fee and no rating (not recoverable)",
       a and all('fee' not in m and m['rating'] is None for m in a))
expect("ambiguous trade (two possible cuts) is left alone", movesOf(tB) is None)
expect("a same-position swap gets an empty list", movesOf(tSwap) == [])
c = movesOf(tC)
expect("a replacement with no prior games is a promotion",
       c is not None and [(m['kind'], m['name']) for m in c] == [('promotion', 'kid')])
expect("an offseason trade is not touched", movesOf(tOff) is None)
expect("a trade that already has moves is not touched",
       movesOf(tDone) == [{'kind': 'cut', 'name': 'already'}])

# Runs once: clear A's moves, boot again, nothing is rewritten.
s = get_session()
t = s.get(Trade, tA)
t.assets_json = {k: v for k, v in t.assets_json.items() if k != 'moves'}
s.commit(); s.close()
connection._backfillTradeMoves()
expect("the marker stops a second run", movesOf(tA) is None)

if fails:
    print(f"FAIL ({len(fails)})")
    raise SystemExit(1)
print("ALL PASS")
