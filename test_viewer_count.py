"""Viewer counts: how many DISTINCT USERS have a game open.

Feature (2026-07-22): show at the top of each game how many people are watching it.

"Watching" means the game modal is open — the client sends `watch`/`unwatch` on the
season socket and the server keeps a viewer set per game. Counted by USER, so:
  * one person with several tabs is ONE viewer, and
  * a socket that never identified (logged out) isn't counted at all.

Run: .venv/bin/python test_viewer_count.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from api.websocket_manager import ConnectionManager

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)


class FakeSocket:
    """Stand-in — the manager only uses sockets as dict keys here."""
    _n = 0
    def __init__(self):
        FakeSocket._n += 1
        self.name = f"ws{FakeSocket._n}"
    def __repr__(self):
        return self.name


def mgr():
    return ConnectionManager()


print("1. Distinct users, not connections")
m = mgr()
a1, a2, b = FakeSocket(), FakeSocket(), FakeSocket()
m.identify(a1, 100); m.identify(a2, 100); m.identify(b, 200)
m.watch(a1, '5086'); m.watch(a2, '5086'); m.watch(b, '5086')
expect(f"user 100 on two tabs + user 200 = 2 viewers (got {m.get_viewer_count('5086')})",
       m.get_viewer_count('5086') == 2)

print("2. A logged-out socket isn't counted")
m = mgr()
anon, known = FakeSocket(), FakeSocket()
m.identify(known, 300)
m.watch(anon, '5086'); m.watch(known, '5086')
expect(f"anonymous viewer not counted (got {m.get_viewer_count('5086')})",
       m.get_viewer_count('5086') == 1)

print("3. Counts are per game")
m = mgr()
x, y = FakeSocket(), FakeSocket()
m.identify(x, 1); m.identify(y, 2)
m.watch(x, '5086'); m.watch(y, '5099')
expect("game 5086 has 1", m.get_viewer_count('5086') == 1)
expect("game 5099 has 1", m.get_viewer_count('5099') == 1)
expect("an unwatched game has 0", m.get_viewer_count('1234') == 0)

print("4. watch() reports which games changed, so only those broadcast")
m = mgr()
s = FakeSocket(); m.identify(s, 7)
expect(f"first watch → just the joined game",
       m.watch(s, '5086') == ['5086'])
changed = m.watch(s, '5099')
expect(f"switching games → both the left and joined game {changed}",
       changed == ['5086', '5099'])
expect(f"re-watching the same game → no change reported",
       m.watch(s, '5099') == ['5099'])
expect(f"unwatch → just the left game", m.watch(s, None) == ['5099'])
expect("after unwatch the count is 0", m.get_viewer_count('5099') == 0)

print("5. Leaving and disconnecting both drop the count")
m = mgr()
p, q = FakeSocket(), FakeSocket()
m.identify(p, 10); m.identify(q, 11)
m.watch(p, '5086'); m.watch(q, '5086')
expect("two viewers", m.get_viewer_count('5086') == 2)
m.watch(p, None)
expect("one leaves → 1", m.get_viewer_count('5086') == 1)
m.disconnect(q, 'season')
expect("the other disconnects → 0", m.get_viewer_count('5086') == 0)
expect("disconnect clears the watch entry", q not in m.connection_watching)

print("6. Game ids compare as strings (payloads send them either way)")
m = mgr()
s = FakeSocket(); m.identify(s, 42)
m.watch(s, 5086)
expect("int watch is found by string lookup", m.get_viewer_count('5086') == 1)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — viewer counts are per game, per distinct user, and clean up on exit.")
