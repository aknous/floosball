"""Fix coach/player AND player/player name collisions.

Resolution rules:
  Coach + player collisions:
    1. Coach is unhired (POOL, team_id IS NULL) → rename the COACH.
       Clears any number of player collisions sharing the coach name.
    2. Coach on a team AND player is a free agent → rename the PLAYER.
       Preserves coach identity that fans may have voted on or hired.
    3. Both coach and player are rostered → SKIP for manual review.

  Player + player duplicates (multiple Player rows with same .name):
    4. ≥1 rostered + ≥1 FA → rename every FA among the duplicates.
    5. 0 rostered + ≥2 FA → keep one FA, rename the rest.
    6. ≥2 rostered → SKIP for manual review.

Renames pull a fresh name from unused_names and delete that row in
one transaction. Old (collided) name is NOT returned to the pool —
at least one entity still uses it.

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


def _resolvePlayerDupes(name, playerList, takeName, playerRenames, skipped):
    """Apply rules 4-6 for a set of Player rows sharing a name.
    Mutates playerRenames / skipped in place.
    """
    rostered = [p for p in playerList if p.team_id is not None]
    fas = [p for p in playerList if p.team_id is None]
    # Rule 4: ≥1 rostered + ≥1 FA → rename every FA, leave the rostered alone.
    if rostered and fas:
        for p in fas:
            newName = takeName(f"FA player rename {p.name!r}")
            if newName is None:
                return
            playerRenames.append((p, p.name, newName, "FA vs rostered"))
        return
    # Rule 5: 0 rostered + ≥2 FA → keep one, rename the rest.
    if not rostered and len(fas) >= 2:
        keeper = fas[0]
        for p in fas[1:]:
            newName = takeName(f"FA player rename {p.name!r}")
            if newName is None:
                return
            playerRenames.append((p, p.name, newName, "FA-only dupe"))
        return
    # Rule 6: ≥2 rostered → skip.
    if len(rostered) >= 2:
        skipped.append((name, "player+player", [], playerList))


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

        coachPlayerCollisions = sorted(set(coachByName.keys()) & set(playerByName.keys()))
        playerOnlyDupes = sorted(
            n for n, plist in playerByName.items()
            if len(plist) > 1 and n not in coachByName
        )
        if not coachPlayerCollisions and not playerOnlyDupes:
            print("No name collisions found.")
            return

        unusedByName: dict = {r.name: r for r in unusedRows}
        # Defensive guard: skip names that are themselves coach OR
        # duplicated player names so we don't pick a known-collided name.
        coachNames = set(coachByName.keys())
        dupePlayerNames = {n for n, plist in playerByName.items() if len(plist) > 1}
        availablePool = [
            name for name in unusedByName.keys()
            if name not in coachNames and name not in dupePlayerNames
        ]
        random.shuffle(availablePool)

        coachRenames: list = []   # (Coach, oldName, newName)
        playerRenames: list = []  # (Player, oldName, newName, reason)
        skipped: list = []        # (name, kind, coachList, playerList)
        consumed: list = []       # UnusedName rows to delete

        def takeName(reasonLabel: str) -> str | None:
            if not availablePool:
                print(f"!! pool exhausted before {reasonLabel} — abort")
                return None
            name = availablePool.pop()
            consumed.append(unusedByName[name])
            return name

        # ── Coach / player collisions ────────────────────────────────
        for name in coachPlayerCollisions:
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
                # If players ALSO duplicate among themselves under this name
                # (mix of rostered + FA), still need rule 4/5 to handle that
                # second tier of dupes — fall through after the coach rename
                # via the player-only path below.
                if len(playerList) > 1:
                    _resolvePlayerDupes(name, playerList, takeName, playerRenames, skipped)
                continue

            # Rule 2: coach on team + player is FA → rename the FA.
            faPlayers = [p for p in playerList if p.team_id is None]
            teamPlayers = [p for p in playerList if p.team_id is not None]
            if faPlayers and not teamPlayers:
                for player in faPlayers:
                    newName = takeName(f"player rename {player.name!r}")
                    if newName is None:
                        return
                    playerRenames.append((player, player.name, newName, "coach+FA"))
                continue

            # Rule 3: any rostered player AND no pool coach → leave it.
            skipped.append((name, "coach+player", coachList, playerList))

        # ── Player / player duplicates (no coach involvement) ────────
        for name in playerOnlyDupes:
            _resolvePlayerDupes(
                name, list(playerByName[name]), takeName, playerRenames, skipped,
            )

        print(f"Found {len(coachPlayerCollisions)} coach+player collision(s) and "
              f"{len(playerOnlyDupes)} player+player duplicate(s)")
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
            for player, oldName, newName, reason in playerRenames:
                print(f"  player(id={player.id}, FA, pos={player.position}) [{reason}]  {oldName!r}  →  {newName!r}")
            print()

        if skipped:
            print(f"Skipped ({len(skipped)} — leave for manual review):")
            for name, kind, coachList, playerList in skipped:
                if kind == "coach+player":
                    cTeams = ", ".join(f"team_id={c.team_id}" for c in coachList)
                    pTeams = ", ".join(f"team_id={p.team_id}" for p in playerList)
                    print(f"  {name!r} [{kind}]: coach({cTeams})  +  player({pTeams})")
                else:
                    pTeams = ", ".join(f"team_id={p.team_id}" for p in playerList)
                    print(f"  {name!r} [{kind}]: player({pTeams})")
            print()

        if not apply:
            return

        for coach, _old, newName in coachRenames:
            coach.name = newName
        for player, _old, newName, _reason in playerRenames:
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
