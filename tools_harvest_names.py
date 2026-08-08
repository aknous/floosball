"""Return player names to the pool before a fresh start, minus the lineage variants.

A fresh start preserves `unused_names`, so the obvious assumption is that the name pool is
safe. It is not. A name is REMOVED from the pool when a player is created and never put
back — retirement returns a *variant* ("Name Jr.", then III, IV...) via
`seasonManager._recyclePlayerName`, not the original. So every name currently attached to a
living player exists only on a `players` row, and `players` is dropped.

Measured on the prod snapshot: 401 base names sat on player rows and nowhere else. Those
include every name submitted through Discord `/name` or added by an admin that has since
been assigned to somebody. They would have been lost silently.

This harvests them back, and while it is there it drops the lineage variants (owner,
2026-08-07: keep the names, not the Jr artifacts) — those are bookkeeping from a league
that is about to stop existing, and a fresh league re-earns its own dynasties.

    .venv/bin/python tools_harvest_names.py                  # dry run
    .venv/bin/python tools_harvest_names.py --apply
    .venv/bin/python tools_harvest_names.py --keep-variants  # leave Jr./III alone

Run BEFORE the wipe, alongside tools_archive_seasons.py. Idempotent.
"""
import sys, re, sqlite3

args = sys.argv[1:]
DB = args[args.index('--db') + 1] if '--db' in args else 'data/floosball.db'
APPLY = '--apply' in args
DROP_VARIANTS = '--keep-variants' not in args

# Matches what _recyclePlayerName produces: Jr. then III, IV, V ... XI.
SUFFIX = re.compile(r'\s+(Jr\.|III|IV|V|VI|VII|VIII|IX|X|XI)$')


def baseName(n: str) -> str:
    """Strip a lineage suffix back to the original name.

    "Loretta Brioche Jr." recovers "Loretta Brioche" — the name someone actually submitted,
    which was consumed the first time it was used.

    ⚠️ On the prod snapshot this recovers ZERO extra names, and that is correct rather than
    a broken regex. `players` KEEPS retired rows (service_time = 'Retired'), so the original
    is still sitting there under its own name and gets harvested directly; the stripping
    only matters if a retired row is ever purged. Verified: "Chick Neriardi" (Retired) and
    "Chick Neriardi Jr." (Veteran3) both exist as rows. Do not "fix" the zero.
    """
    prev = None
    while prev != n:
        prev, n = n, SUFFIX.sub('', n).strip()
    return n


conn = sqlite3.connect(DB)
have = {r[0] for r in conn.execute("select name from unused_names")}
pending = {r[0] for r in conn.execute("select name from pending_names")} \
    if conn.execute("select count(*) from sqlite_master where name='pending_names'").fetchone()[0] else set()
players = [r[0] for r in conn.execute("select name from players where name is not null")]

lowerHave = {n.lower() for n in have}
harvested, fromVariant = [], 0
for raw in players:
    n = baseName(raw) if DROP_VARIANTS else raw
    if not n or n.lower() in lowerHave:
        continue
    lowerHave.add(n.lower())
    harvested.append(n)
    if n != raw:
        fromVariant += 1

variantsInPool = sorted(n for n in have if SUFFIX.search(n))
variantsPending = sorted(n for n in pending if SUFFIX.search(n))

print(f"\n{DB}   ({'APPLY' if APPLY else 'DRY RUN'})\n")
print(f"  pool today                {len(have)}")
print(f"  held (pending) today      {len(pending)}")
print(f"  names on player rows      {len(players)}")
print(f"\n  RECOVERED from players    {len(harvested)}"
      f"   ({fromVariant} by stripping a lineage suffix)")
for n in harvested[:8]:
    print(f"      + {n}")
if len(harvested) > 8:
    print(f"      ... and {len(harvested) - 8} more")
if DROP_VARIANTS:
    print(f"\n  DROPPED lineage variants  {len(variantsInPool)} in pool, {len(variantsPending)} held")
    for n in variantsInPool[:5]:
        print(f"      - {n}")
    if len(variantsInPool) > 5:
        print(f"      ... and {len(variantsInPool) - 5} more")
after = len(have) - (len(variantsInPool) if DROP_VARIANTS else 0) + len(harvested)
print(f"\n  pool after                {after}")

if APPLY:
    if DROP_VARIANTS:
        for n in variantsInPool:
            conn.execute("delete from unused_names where name=?", (n,))
        for n in variantsPending:
            conn.execute("delete from pending_names where name=?", (n,))
    conn.executemany("insert into unused_names (name) values (?)", [(n,) for n in harvested])
    conn.commit()
    print(f"\nwritten. unused_names now holds "
          f"{conn.execute('select count(*) from unused_names').fetchone()[0]}")
else:
    print("\ndry run only — re-run with --apply to write")
conn.close()
