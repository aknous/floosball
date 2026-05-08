"""Fix coach/player name collisions caused by the stale _coachNamePool
reference bug.

Strategy: keep the coach (they have history, votes, hires tied to that
identity). Rename the colliding player by pulling a fresh name from the
unused_names pool and removing it from the pool atomically. If multiple
players share the coach's name, rename all of them.

Dry-run by default — prints proposed changes. Pass --apply to commit.

Run on Fly:
    fly ssh console -C "cd /app && python scripts/fix_name_collisions.py"          # preview
    fly ssh console -C "cd /app && python scripts/fix_name_collisions.py --apply"  # commit
"""

import sys
import random
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_session
from database.models import Coach, Player, UnusedName


def main(apply: bool) -> None:
    session = get_session()
    try:
        coaches = session.query(Coach).all()
        players = session.query(Player).all()
        unusedRows = session.query(UnusedName).all()

        coachByName: dict = defaultdict(list)
        for c in coaches:
            coachByName[c.name].append(c)
        playerByName: dict = defaultdict(list)
        for p in players:
            playerByName[p.name].append(p)

        collidingNames = sorted(set(coachByName.keys()) & set(playerByName.keys()))
        if not collidingNames:
            print("No coach/player name collisions found.")
            return

        # Build a working pool of fresh names. We mutate this list in memory
        # while assigning, then commit by deleting the chosen UnusedName rows.
        unusedByName: dict = {r.name: r for r in unusedRows}
        # Skip names that are themselves coach names — defensive guard against
        # the same bug producing chained collisions.
        coachNames = set(coachByName.keys())
        availablePool = [name for name in unusedByName.keys() if name not in coachNames]
        random.shuffle(availablePool)

        print(f"Found {len(collidingNames)} colliding names")
        print(f"Available fresh names in pool: {len(availablePool)}")
        if not apply:
            print("(dry run — pass --apply to commit changes)")
        print()

        renames = []  # list of (Player, oldName, newName)
        consumed = []  # UnusedName rows to delete

        for name in collidingNames:
            playersToRename = list(playerByName[name])
            for player in playersToRename:
                if not availablePool:
                    print(f"!! pool exhausted before renaming {player.name} (id={player.id}) — abort")
                    return
                newName = availablePool.pop()
                renames.append((player, player.name, newName))
                consumed.append(unusedByName[newName])

        for player, oldName, newName in renames:
            teamPart = f"team_id={player.team_id}" if player.team_id else "FA"
            print(f"  player(id={player.id}, {teamPart}, pos={player.position})")
            print(f"    {oldName!r}  →  {newName!r}")

        if not apply:
            return

        for player, oldName, newName in renames:
            player.name = newName
        for row in consumed:
            session.delete(row)
        session.commit()
        print(f"\n✓ committed {len(renames)} rename(s); pool size now "
              f"{session.query(UnusedName).count()}")
    finally:
        session.close()


if __name__ == "__main__":
    apply = "--apply" in sys.argv[1:]
    main(apply)
