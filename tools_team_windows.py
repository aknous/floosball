"""Where every team sits in its contention cycle, read straight from the database.

`TradeMarket.teamWindow` computes the window live and never stores it, so a listing's
reason can be read on the transactions page but the state behind it cannot. Every input
IS persisted, so this recomputes it:

  contending   win% (team_season_stats for the latest season) >= the league mean
  decline      position-weighted share of the six starters with seasons_played >= longevity
  window       contending -> 'closing' if decline >= 0.22 else 'open'   <- the Timeline gate
               otherwise  -> 'closed' if decline >= 0.22, 'opening' if ascent >= 0.70,
                             else 'middling'

⚠️ THE DECLINE AXIS IS EXACT; THE ASCENT AXIS IS A PROXY. `classifyArc` calls a player
'developing' when their POTENTIAL rating beats today's by 2, and that ceiling re-runs the
whole per-position rating formula including the defensive half, which is not stored. Here
it is approximated from the offensive half only (potential_skill_rating vs skill_rating),
which is marked in the output. It only affects non-contenders ('opening' vs 'middling') —
for a contender the window turns on the decline share alone, which is exact.

Usage:
    .venv/bin/python tools_team_windows.py
    DATABASE_DIR=/data .venv/bin/python tools_team_windows.py

On production there is no sqlite3 binary, so run it through the app's own python:
    fly ssh console -C "python3 /app/tools_team_windows.py"
"""
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.environ.get('DATABASE_DIR', os.path.join(HERE, 'data')), 'floosball.db')

POSITION_VALUE = {1: 1.00, 2: 0.78, 3: 0.72, 4: 0.60, 5: 0.35}   # QB RB WR TE K
POSITION_NAME = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K'}
DECLINE_HIGH = 0.22      # TRADE_WINDOW_DECLINE_HIGH
ASCENT_HIGH = 0.70       # TRADE_WINDOW_ASCENT_HIGH
DEVELOPING_HEADROOM = 2  # FO_DEVELOPING_HEADROOM
HORIZON_TERM = 3         # _horizonMismatch: a contender's long deals


def main() -> int:
    db = sqlite3.connect(DB)
    season = db.execute('select max(season) from team_season_stats').fetchone()[0]
    if season is None:
        print('no season stats in this database')
        return 1

    contention, records = {}, {}
    for teamId, wins, losses in db.execute(
            'select team_id, wins, losses from team_season_stats where season = ?', (season,)):
        played = (wins or 0) + (losses or 0)
        contention[teamId] = ((wins or 0) / played) if played else 0.5
        records[teamId] = (wins or 0, losses or 0)
    mean = (sum(contention.values()) / len(contention)) if contention else 0.0

    rows = db.execute("""
        select p.team_id, p.position, p.name, p.seasons_played, p.player_rating, p.term_remaining,
               a.longevity, a.skill_rating, a.potential_skill_rating
        from players p join player_attributes a on a.player_id = p.id
        where p.team_id is not null and p.is_prospect = 0 and p.service_time != 'Retired'
    """).fetchall()
    names = dict(db.execute('select id, name from teams'))

    teams = {}
    for teamId, pos, name, seasons, rating, term, longevity, skill, potSkill in rows:
        t = teams.setdefault(teamId, {'total': 0.0, 'decline': 0.0, 'ascent': 0.0, 'old': [], 'long': []})
        weight = POSITION_VALUE.get(pos, 1.0)
        t['total'] += weight
        yearsPast = (seasons or 0) - (longevity if longevity is not None else 99)
        if yearsPast >= 0:
            t['decline'] += weight
            t['old'].append(f"{name} ({POSITION_NAME.get(pos, '?')}, {yearsPast:+d})")
        elif (potSkill or 0) - (skill or 0) >= DEVELOPING_HEADROOM:
            t['ascent'] += weight
        if (term or 0) >= HORIZON_TERM:
            t['long'].append(f"{name} ({POSITION_NAME.get(pos, '?')}, {term}y, {rating})")

    print(f'Season {season}. League mean win rate {mean:.3f}. '
          f'Decline threshold {DECLINE_HIGH:.0%}, ascent {ASCENT_HIGH:.0%} (ascent approximate).\n')
    print(f'{"team":<16}{"rec":>7}{"win%":>7}{"cont":>6}{"decline":>9}{"ascent":>8}  {"window":<9} Timeline-eligible')
    out = []
    for teamId, t in teams.items():
        if t['total'] <= 0:
            continue
        decline, ascent = t['decline'] / t['total'], t['ascent'] / t['total']
        contending = contention.get(teamId, 0.5) >= mean
        if contending:
            window = 'closing' if decline >= DECLINE_HIGH else 'open'
        elif decline >= DECLINE_HIGH:
            window = 'closed'
        elif ascent >= ASCENT_HIGH:
            window = 'opening'
        else:
            window = 'middling'
        out.append((-contention.get(teamId, 0), teamId, decline, ascent, contending, window, t))
    for _s, teamId, decline, ascent, contending, window, t in sorted(out):
        w, l = records.get(teamId, (0, 0))
        # ⚠️ ONLY A CLOSING WINDOW CAN LIST ON TIMELINE (`_horizonMismatch`). A contender
        # whose core is intact will be contending again next year, so its long contracts
        # are an asset — that gate is what stopped champions listing good players.
        eligible = ', '.join(t['long']) if window == 'closing' else '—'
        print(f'{names.get(teamId, teamId)[:15]:<16}{f"{w}-{l}":>7}{contention.get(teamId, 0):>7.3f}'
              f'{"yes" if contending else "no":>6}{decline:>9.0%}{ascent:>8.0%}  {window:<9} {eligible}')
    print('\nTimeline (horizon_mismatch) lists players with 3+ years left, and only for a '
          'contender whose window is CLOSING.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
