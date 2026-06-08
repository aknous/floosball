"""Read-only audit for coach/player name collisions caused by the stale
_coachNamePool reference bug.

Reports:
  1. Coach names that exactly match an active player's name
  2. Coach names that are still listed in the unused_names pool
     (would be drawn for the next generated player)
  3. Active player + active coach pairs sharing the same name

Run locally:
    python scripts/check_name_collisions.py

Run on Fly:
    fly ssh console
    cd /app
    python scripts/check_name_collisions.py
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_session
from database.models import Coach, Player, UnusedName


def main() -> None:
    session = get_session()
    try:
        coaches = session.query(Coach).all()
        players = session.query(Player).all()
        unusedRows = session.query(UnusedName).all()

        coachByName = defaultdict(list)
        for c in coaches:
            coachByName[c.name].append(c)

        playerByName = defaultdict(list)
        for p in players:
            playerByName[p.name].append(p)

        unusedSet = {r.name for r in unusedRows}

        # 1. Coaches whose name appears in unused_names — next player draw
        # could pick the coach's name, creating a duplicate.
        coachesInUnused = [c for c in coaches if c.name in unusedSet]

        # 2. Coach + player sharing exact name
        sharedNames = sorted(set(coachByName.keys()) & set(playerByName.keys()))

        print("=== Name collision audit ===")
        print(f"Coaches:        {len(coaches)}")
        print(f"Players:        {len(players)}")
        print(f"Unused names:   {len(unusedRows)}")
        print()
        print(f"Coach names also in unused_names pool: {len(coachesInUnused)}")
        for c in coachesInUnused:
            teamPart = f"team_id={c.team_id}" if c.team_id else "POOL"
            print(f"  - {c.name} ({teamPart})")
        print()
        print(f"Coach + player name collisions: {len(sharedNames)}")
        for name in sharedNames:
            coachList = coachByName[name]
            playerList = playerByName[name]
            for c in coachList:
                cTeam = f"team_id={c.team_id}" if c.team_id else "POOL"
                for p in playerList:
                    pTeam = f"team_id={p.team_id}" if p.team_id else "FA"
                    print(f"  - {name} | coach({cTeam}) + player({pTeam}, pos={p.position})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
