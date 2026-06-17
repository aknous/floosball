"""Unit test for the shared seeding/standings tiebreaker (seeding.orderTeams).

Chain: winPerc -> scoreDiff -> head-to-head point diff (mini round-robin) ->
points-for -> points-against.

Run: python3 test_seeding.py
"""
from types import SimpleNamespace
from seeding import orderTeams


def team(tid, winPerc, scoreDiff, pf=0):
    return SimpleNamespace(id=tid, seasonTeamStats={
        'winPerc': winPerc, 'scoreDiff': scoreDiff, 'Offense': {'pts': pf},
    })


def ids(teams):
    return [t.id for t in teams]


def main():
    ok = True

    def check(label, got, want):
        nonlocal ok
        status = 'OK' if got == want else 'FAIL'
        if got != want:
            ok = False
        print(f"  [{status}] {label}: got {got}, want {want}")

    # 1. Primary: win percentage
    check("win% ordering",
          ids(orderTeams([team(1, 0.4, 0), team(2, 0.8, 0), team(3, 0.6, 0)])),
          [2, 3, 1])

    # 2. Tiebreak by score differential when win% equal
    check("scoreDiff tiebreak",
          ids(orderTeams([team(1, 0.6, 10), team(2, 0.6, 25), team(3, 0.6, -5)])),
          [2, 1, 3])

    # 3. Head-to-head point diff (2-team tie): team 1 beat team 2 by 10 head-to-head
    h2h2 = [(1, 2, 30, 20)]  # team1 home, beat team2 30-20
    check("2-team head-to-head",
          ids(orderTeams([team(2, 0.6, 0), team(1, 0.6, 0)], h2h2)),
          [1, 2])

    # 4. Head-to-head point diff (3-team tie, mini round-robin):
    #    1 beat 2 by 10, 2 beat 3 by 7, 3 beat 1 by 3
    #    diffs: t1 = +10 -3 = +7 | t2 = -10 +7 = -3 | t3 = -7 +3 = -4
    h2h3 = [(1, 2, 30, 20), (2, 3, 27, 20), (3, 1, 23, 20)]
    check("3-team head-to-head round-robin",
          ids(orderTeams([team(1, 0.7, 5), team(2, 0.7, 5), team(3, 0.7, 5)], h2h3)),
          [1, 2, 3])

    # 5. H2H level (no games among them) -> points-for breaks it
    check("points-for fallback",
          ids(orderTeams([team(1, 0.6, 0, pf=300), team(2, 0.6, 0, pf=320)], [])),
          [2, 1])

    print("PASS — seeding tiebreaker chain correct." if ok
          else ">>> SEEDING TIEBREAKER BROKEN <<<")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
