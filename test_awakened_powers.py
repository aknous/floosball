"""Awakened (L4) powers — catalog + one-career-power assignment.

Verifies the situation-keyed catalog (assignPower covers a player's primary action; coverage + flavor
lookups), and that anomalyManager.assignSignaturePower gives a player ONE power, stored on the Player,
kept for their career (idempotent across re-awakenings).

Run: python test_awakened_powers.py  (throwaway temp DB)
"""
import os, sys, tempfile, shutil, random
sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_l4_")
os.environ["DATABASE_DIR"] = _tmp

from database.connection import init_db, get_session
init_db()
import managers.awakenedPowers as ap
from managers import anomalyManager
from database.models import Player

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

# ── 1. Catalog: situation-keyed, validates, assignment covers the primary action ──
print("1. Catalog — assignPower covers each position's primary action; coverage + flavor lookups")
expect("import-time _validate() passed (no malformed powers)", len(ap.allPowerKeys()) > 0)
for pos, primary in ap.PRIMARY_SITUATION.items():
    rng = random.Random(7)
    keys = {ap.assignPower(pos, rng) for _ in range(60)}
    expect(f"{pos}: every rolled power covers '{primary}'",
           keys and all(k and ap.powerCoversSituation(k, primary) for k in keys))
expect("a narrow power (Magnet) covers catch+defense, NOT run",
       ap.powerCoversSituation('magnet', 'catch') and ap.powerCoversSituation('magnet', 'defense')
       and not ap.powerCoversSituation('magnet', 'run'))
expect("a universal power (No-Clip) covers every situation",
       all(ap.powerCoversSituation('no_clip', s) for s in ap.SITUATIONS))
expect("situationFlavor returns a line for a covered situation", bool(ap.situationFlavor('magnet', 'catch')))
expect("situationFlavor returns '' for an uncovered situation", ap.situationFlavor('magnet', 'run') == '')
expect("powerName / powerConcept resolve", ap.powerName('no_clip') == 'No-Clip' and bool(ap.powerConcept('no_clip')))

# ── 2. assignSignaturePower — one power, on the Player, career-persistent ──
print("\n2. assignSignaturePower — one career power per player, stored on the Player, idempotent")
s = get_session()
s.add(Player(id=1, name='Awoke RB', position=1))   # RB -> a run-capable power
s.add(Player(id=2, name='Awoke WR', position=2))   # WR -> a catch-capable power
s.commit()

p1 = anomalyManager.assignSignaturePower(s, 1)
p2 = anomalyManager.assignSignaturePower(s, 2)
s.commit()
expect("RB got a power that covers 'run'", p1 and ap.powerCoversSituation(p1, 'run'))
expect("WR got a power that covers 'catch'", p2 and ap.powerCoversSituation(p2, 'catch'))
expect("the power is stored on the Player",
       s.query(Player).get(1).signature_power == p1 and s.query(Player).get(2).signature_power == p2)

# Re-awakening keeps the SAME power (career identity, never re-rolled).
p1again = anomalyManager.assignSignaturePower(s, 1)
expect("a second awakening returns the same career power (idempotent)", p1again == p1)

# Reload in a fresh session — the career power persists through the migration column.
s2 = get_session()
expect("signature_power persists + reloads", s2.query(Player).get(1).signature_power == p1)

# ── 3. Distribution — least-used assignment avoids duplicates ──
print("\n3. Distribution — assigned powers go to the back; no duplicates until the pool is exhausted")
from collections import Counter
s3 = get_session()
for i in range(100, 130):                    # 30 RBs (run pool is far larger than 30)
    s3.add(Player(id=i, name=f'RB{i}', position=1))
s3.commit()
got = []
for i in range(100, 130):
    got.append(anomalyManager.assignSignaturePower(s3, i))
    s3.commit()
dups = [k for k, c in Counter(got).items() if c > 1]
expect("30 same-position awakenings -> all distinct powers (no duplicates)", not dups)

shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED-POWERS TESTS PASS")
