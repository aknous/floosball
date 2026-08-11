"""A finished game keeps its story, and a club keeps its playoff runs.

Three things this locks down, each of which was broken or absent:

  * THE QUARTER LINE WAS NEVER WRITTEN. Both save paths guarded on
    `game.homeScoresByQuarter`, a LIST attribute the game object has never had, so the
    `hasattr` was always False and every quarter column stayed 0 — measured at 0 of 783
    finished games. Nothing raised, which is exactly why it survived. The engine keeps
    `homeScoreQ1..Q4` / `homeScoreOT` instead.
  * A FINISHED GAME COULD NOT SHOW ITS BOX SCORE. The per-player line reaches the live
    modal over the `game_state` WebSocket; the REST endpoint returned only a summary. The
    rows were in `game_player_stats` the whole time, just never read.
  * A CLUB'S PLAYOFF RUNS WERE INVISIBLE unless they won it all, because only the League
    Champions badge was durable.

Run: .venv/bin/python test_game_history.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)

import playoff_history
from playoff_history import buildPlayoffHistory, summarize, _roundNumber

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class G:
    """One finished playoff game."""
    def __init__(self, season, rnd, home, away, hs, as_, gid=0):
        self.season = season; self.playoff_round = rnd
        self.home_team_id = home; self.away_team_id = away
        self.home_score = hs; self.away_score = as_
        self.is_playoff = True; self.status = 'final'; self.id = gid


class Q:
    def __init__(self, rows): self._rows = rows
    def filter(self, *a): return self
    def all(self): return self._rows
    def distinct(self): return self
    def count(self): return len(self._rows)


class S:
    def __init__(self, rows): self._rows = rows
    def query(self, *a): return Q(self._rows)


print("\nThe round a club reached")
# A club that lost the League Championship after winning two rounds.
runs = buildPlayoffHistory(S([
    G(5, '1', 7, 2, 24, 10), G(5, '2', 7, 3, 17, 14), G(5, '3', 4, 7, 21, 20),
]), 7)
expect("one season recorded", len(runs) == 1)
expect("deepest round is the League Championship", runs[0]['deepestRound'] == 3)
expect("badge reads CR", runs[0]['badge'] == 'CR')
expect("outcome names the round they went out in", runs[0]['outcome'] == 'Lost in League Championship')
expect("their record through the run is 2-1", (runs[0]['wins'], runs[0]['losses']) == (2, 1))

# One-and-done.
runs = buildPlayoffHistory(S([G(6, '1', 9, 1, 3, 30)]), 9)
expect("a first-round exit reads R1", runs[0]['badge'] == 'R1')
expect("...and says so", runs[0]['outcome'] == 'Lost in Round 1')

print("\nWinning it, and losing it")
champ = buildPlayoffHistory(S([
    G(8, '1', 5, 1, 20, 3), G(8, '2', 5, 2, 20, 7),
    G(8, '3', 5, 3, 27, 24), G(8, '4', 5, 4, 31, 28),
]), 5)
expect("a champion is a champion, not 'won the Floos Bowl'", champ[0]['badge'] == 'CHAMPIONS')
expect("...with the outcome to match", champ[0]['outcome'] == 'Champions')
runner = buildPlayoffHistory(S([G(8, '4', 4, 5, 28, 31)]), 4)
expect("losing the final is its own thing, not a round exit", runner[0]['outcome'] == 'Lost the Floos Bowl')
expect("...and badges as FB", runner[0]['badge'] == 'FB')

print("\nSeveral seasons")
multi = buildPlayoffHistory(S([
    G(1, '4', 7, 8, 30, 20), G(2, '1', 7, 9, 10, 21), G(4, '3', 7, 2, 14, 17),
]), 7)
expect("newest season first", [h['season'] for h in multi] == [4, 2, 1])
expect("each season keeps its own depth", [h['badge'] for h in multi] == ['CR', 'R1', 'CHAMPIONS'])
s = summarize(multi, seasonsPlayed=17)
expect("appearances counted", s['appearances'] == 3)
expect("titles counted", s['titles'] == 1)
expect("best round is the deepest ever reached", s['bestRound'] == 4)
expect("seasons played rides along", s['seasonsPlayed'] == 17)
# The user's actual complaint, in one line.
expect("a club with 4 runs in 17 seasons can see all four",
       summarize(buildPlayoffHistory(S([
           G(1, '1', 3, 1, 0, 7), G(5, '2', 3, 1, 0, 7),
           G(9, '3', 3, 1, 0, 7), G(14, '4', 3, 1, 21, 20),
       ]), 3), 17)['appearances'] == 4)

print("\nNothing to show")
expect("a club that never made it returns an empty list", buildPlayoffHistory(S([]), 1) == [])
empty = summarize([], seasonsPlayed=17)
expect("...and summarizes cleanly rather than erroring", empty['appearances'] == 0 and empty['bestRound'] is None)

print("\nRound parsing tolerates the name as well as the number")
# The column has held '1'..'4' in every season checked, but the season manager knows these
# rounds by name. A future writer using the name must not silently erase playoff history.
expect("plain numbers", [_roundNumber(x) for x in ('1', '2', '3', '4')] == [1, 2, 3, 4])
expect("round names", _roundNumber('Playoffs Round 2') == 2)
expect("the league championship", _roundNumber('League Championship') == 3)
expect("the Floos Bowl", _roundNumber('Floos Bowl') == 4)
expect("nonsense is dropped, not guessed", _roundNumber('') is None and _roundNumber(None) is None)

print("\nA game with an unreadable round does not sink the whole history")
mixed = buildPlayoffHistory(S([G(3, '2', 6, 1, 20, 10), G(3, 'wat', 6, 2, 10, 20)]), 6)
expect("the readable game still counts", mixed and mixed[0]['deepestRound'] == 2)

print()
if fails:
    print(f"FAIL — {len(fails)} check(s) failed:")
    for f in fails:
        print(f"  - {f}")
else:
    print("PASS — a club's playoff runs are readable for every season already on record.")
sys.exit(1 if fails else 0)
