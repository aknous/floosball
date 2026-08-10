"""Compare what a CARD sees against what the STAT LINE shows, for one player-week.

Built for a specific contradiction: a Paydirt card read "2 rec TD" while the stat line
beside it showed "17/18 rec · 150 yd · 0 TD". Both claim to describe the same player in the
same week, so one of them is wrong, and the two travel through different code:

    stat line   allPlayerRawStats -> raw GamePlayerStats sub-dicts -> compactStatLine
    card        weekPlayerStats   -> _dbStatsToCardFormat          -> _ladderStat

Ruled out already: duplicate GamePlayerStats rows per player-week (there are none in prod).

    PROBE_DB=<sim.db> PROBE_WEEK=14 PROBE_PLAYER="Tincan Ferguson" \\
      .venv/bin/python tools_card_stat_diff.py

Omit PROBE_PLAYER to scan the whole week and list every player where the two disagree,
which is the faster way to tell whether this is one card or something systemic.
"""
import os, sys, json, sqlite3

DB = os.environ.get('PROBE_DB', 'data/floosball_prod_latest.db')
WEEK = int(os.environ.get('PROBE_WEEK', '14'))
NAME = os.environ.get('PROBE_PLAYER')
SEASON = os.environ.get('PROBE_SEASON')

os.environ.setdefault('DATABASE_DIR', os.path.dirname(os.path.abspath(DB)) or '.')
import logging
logging.disable(logging.WARNING)
from managers.fantasyTracker import _dbStatsToCardFormat

conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
season = int(SEASON) if SEASON else conn.execute(
    "select max(season) from games where status='final'").fetchone()[0]

# returning_stats only exists on DBs that have run the punt-returns migration, so select
# it optionally rather than failing on an older snapshot.
_cols = {r[1] for r in conn.execute("PRAGMA table_info(game_player_stats)")}
_ret = "g.returning_stats" if "returning_stats" in _cols else "NULL"
q = f"""select p.id, p.name, g.passing_stats, g.rushing_stats, g.receiving_stats,
               g.kicking_stats, {_ret}, g.fantasy_points, gm.id
        from game_player_stats g
        join games gm on gm.id = g.game_id
        join players p on p.id = g.player_id
        where gm.season = ? and gm.week = ?"""
rows = conn.execute(q, (season, WEEK)).fetchall()
if not rows:
    print(f"no stat rows for season {season} week {WEEK} in {DB}")
    sys.exit(1)


def J(x):
    return (json.loads(x) if isinstance(x, str) else (x or {})) or {}


print(f"{DB}  season {season}  week {WEEK}  ({len(rows)} stat rows)\n")
mismatches = 0
for pid, name, pa, ru, rc, ki, re_, fp, gameId in rows:
    if NAME and NAME.lower() not in (name or '').lower():
        continue
    raw = J(rc)
    card = _dbStatsToCardFormat(J(pa), J(ru), raw, J(ki), fp or 0,
                                returningStats=J(re_))['receiving_stats']
    # what each side reports
    lineTds = raw.get('tds', 0)          # compactStatLine reads receiving.tds
    cardTds = card.get('rcvTds', 0)      # _computePaydirt reads receiving_stats.rcvTds
    lineRec = raw.get('receptions', 0)
    cardRec = card.get('receptions', 0)
    disagree = (lineTds != cardTds) or (lineRec != cardRec)
    if disagree:
        mismatches += 1
    if NAME or disagree:
        flag = '  <-- MISMATCH' if disagree else ''
        print(f"{name} (player {pid}, game {gameId}){flag}")
        print(f"   stat line reads : {lineRec} rec · {raw.get('yards', 0)} yd · {lineTds} TD")
        print(f"   card reads      : {cardRec} rec · {card.get('rcvYards', 0)} yd · {cardTds} TD")
        print(f"   raw receiving   : {raw}")
        print()

if not NAME:
    print(f"players where the two paths disagree: {mismatches} of {len(rows)}")
    if not mismatches:
        print("\nThe two agree everywhere in the DB, so a live mismatch is coming from the")
        print("LIVE path (playerManager.gameStatsDict) rather than stored stats — run this")
        print("against the sim's DB while the discrepancy is on screen.")
