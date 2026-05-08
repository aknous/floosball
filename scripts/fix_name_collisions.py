"""Fix coach/player name collisions caused by the stale _coachNamePool
reference bug.

Resolution rules:
  1. Coach is unhired (in POOL, team_id IS NULL) → rename the COACH
     (no game-history attribution to disturb).
  2. Coach is on a team AND player is a free agent → rename the PLAYER
     (preserve coach identity that fans may have voted on / hired).
  3. Both coach and player are on a team → SKIP (leave for manual review).

Renames pull a fresh name from unused_names, delete that row, and
update the entity's .name in one transaction. Old (collided) name is
NOT returned to the pool — at least one of the duplicates still uses
it, so it's not "unused".

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

        unusedByName: dict = {r.name: r for r in unusedRows}
        # Defensive guard: skip names that are themselves coach names so we
        # don't pick a name that's already known-collided.
        coachNames = set(coachByName.keys())
        availablePool = [name for name in unusedByName.keys() if name not in coachNames]
        random.shuffle(availablePool)

        coachRenames: list = []   # (Coach, oldName, newName)
        playerRenames: list = []  # (Player, oldName, newName)
        skipped: list = []        # (name, coachList, playerList) — both on teams
        consumed: list = []       # UnusedName rows to delete

        def takeName(reasonLabel: str) -> str | None:
            if not availablePool:
                print(f"!! pool exhausted before {reasonLabel} — abort")
                return None
            name = availablePool.pop()
            consumed.append(unusedByName[name])
            return name

        for name in collidingNames:
            coachList = list(coachByName[name])
            playerList = list(playerByName[name])

            # Rule 1: any pool coach → rename the coach. One rename clears
            # every player collision sharing the coach's name.
            poolCoaches = [c for c in coachList if c.team_id is None]
            if poolCoaches:
                for coach in poolCoaches:
                    newName = takeName(f"coach rename {coach.name!r}")
                    if newName is None:
                        return
                    coachRenames.append((coach, coach.name, newName))
                # Pool-coach rename also resolves any team-coach collision
                # under the same name, so we're done with this name. Move on.
                continue

            # Rule 2: coach on team + player is FA → rename the FA.
            faPlayers = [p for p in playerList if p.team_id is None]
            teamPlayers = [p for p in playerList if p.team_id is not None]
            if faPlayers and not teamPlayers:
                for player in faPlayers:
                    newName = takeName(f"player rename {player.name!r}")
                    if newName is None:
                        return
                    playerRenames.append((player, player.name, newName))
                continue

            # Rule 3: any rostered player AND no pool coach → leave it.
            skipped.append((name, coachList, playerList))

        print(f"Found {len(collidingNames)} colliding names")
        print(f"Available fresh names in pool: {len(availablePool) + len(consumed)}")
        if not apply:
            print("(dry run — pass --apply to commit changes)")
        print()

        if coachRenames:
            print(f"Coach renames ({len(coachRenames)}):")
            for coach, oldName, newName in coachRenames:
                print(f"  coach(id={coach.id}, POOL)  {oldName!r}  →  {newName!r}")
            print()

        if playerRenames:
            print(f"Player renames ({len(playerRenames)}):")
            for player, oldName, newName in playerRenames:
                print(f"  player(id={player.id}, FA, pos={player.position})  {oldName!r}  →  {newName!r}")
            print()

        if skipped:
            print(f"Skipped ({len(skipped)} — both on teams, leave for manual review):")
            for name, coachList, playerList in skipped:
                cTeams = ", ".join(f"team_id={c.team_id}" for c in coachList)
                pTeams = ", ".join(f"team_id={p.team_id}" for p in playerList)
                print(f"  {name!r}: coach({cTeams})  +  player({pTeams})")
            print()

        if not apply:
            return

        for coach, _old, newName in coachRenames:
            coach.name = newName
        for player, _old, newName in playerRenames:
            player.name = newName
        for row in consumed:
            session.delete(row)
        session.commit()
        print(
            f"✓ committed {len(coachRenames)} coach rename(s) + "
            f"{len(playerRenames)} player rename(s); pool size now "
            f"{session.query(UnusedName).count()}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    apply = "--apply" in sys.argv[1:]
    main(apply)
