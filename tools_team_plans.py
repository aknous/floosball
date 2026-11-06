"""Print teams' saved roster plans (docs/TEAM_PLAN.md) from a database file.

    .venv/bin/python tools_team_plans.py --db data/floosball.db            # every team, latest step
    .venv/bin/python tools_team_plans.py --db prod.db --team PIT --step rookie_draft
    .venv/bin/python tools_team_plans.py --db prod.db --steps               # what is saved

Reads read-only and needs nothing but the standard library, so it also runs on prod
(`fly ssh console`, then `python3 tools_team_plans.py --db /data/floosball.db`).
Plans are saved after these offseason steps: frontoffice_decisions (step 3),
prospect_window (the 3.78 last look), rookie_draft, fa_draft.
"""
import argparse
import json
import sqlite3


def holder(h):
    src, name, rating = h.get('source'), h.get('name'), h.get('rating')
    if src == 'typical':
        return f"typical FA {rating:.0f}"
    if src == 'market':
        return f"FA {name} {rating:.0f}" if name else "nobody (replacement)"
    tag = {'prospect': ' [prospect]', 'rookie': ' [rookie]'}.get(src, '')
    return f"{name} {rating:.0f}{tag}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--season', type=int)
    ap.add_argument('--step')
    ap.add_argument('--team', help='team abbreviation, e.g. PIT')
    ap.add_argument('--steps', action='store_true', help='list the saved steps')
    a = ap.parse_args()
    db = sqlite3.connect(f'file:{a.db}?mode=ro', uri=True)
    season = a.season or db.execute('select max(season) from team_plans').fetchone()[0]
    if season is None:
        print('No plans saved yet.')
        return
    steps = [r[0] for r in db.execute(
        'select step from team_plans where season=? group by step order by max(created_at)', (season,))]
    if a.steps:
        print(f'season {season}: ' + ', '.join(steps))
        return
    step = a.step or steps[-1]
    teams = {r[0]: (r[1], r[2]) for r in db.execute('select id, name, abbr from teams')}
    rows = db.execute('select team_id, plan_json, created_at from team_plans where season=? and step=? '
                      'order by team_id', (season, step)).fetchall()
    print(f'Season {season}, after {step}. Seasons shown are the next three.')
    for teamId, raw, savedAt in rows:
        name, abbr = teams.get(teamId, ('?', '?'))
        if a.team and abbr != a.team.upper():
            continue
        plan = json.loads(raw) if isinstance(raw, str) else raw
        tilt = plan.get('tilt', 0.0)
        lean = 'defense' if tilt > 0.05 else 'offense' if tilt < -0.05 else 'balanced'
        print(f"\n{name} ({abbr}): tilt {tilt:+.2f} ({lean}), FA pick depth {plan.get('faDepth')}")
        for pos, entry in plan.get('positions', {}).items():
            seasons = entry.get('seasons', [])
            line = '  |  '.join(f"+{i + 1}: " + ' + '.join(holder(h) for h in s)
                                for i, s in enumerate(seasons))
            print(f"   {pos:2}  {line}")
            keep = entry.get('keep') or {}
            if keep:
                ids = {str(h.get('id')): h.get('name') for s in seasons for h in s}

                def read(pid, k):
                    if isinstance(k, dict):
                        return f"{k.get('name') or ids.get(pid, pid)} {'kept' if k.get('kept') else 'let go'}"
                    return f"{ids.get(pid, pid)} {'kept' if k else 'let go'}"
                print('       re-sign read (deals ending after next season): '
                      + ', '.join(read(pid, k) for pid, k in keep.items()))
        if plan.get('commitments'):
            print(f"   commitments (player ids): {', '.join(plan['commitments'])}")


if __name__ == '__main__':
    main()
