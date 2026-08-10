"""Return player names to the pool before a fresh start, minus the lineage variants.

A fresh start preserves `unused_names`, so the obvious assumption is that the name pool is
safe. It is not. A name is REMOVED from the pool when a player is created and never put
back — retirement returns a *variant* ("Name Jr.", then III, IV...) via
`seasonManager._recyclePlayerName`, not the original. So every name currently attached to a
living player exists only on a `players` row, and `players` is dropped.

⚠️ MOST of those come back on their own, and the first version of this docstring said
otherwise. `_seedUnusedNames` runs on EVERY boot and re-merges `config.json`'s 789-name
players list, skipping anything already pooled or held by a live player. After a wipe there
are no live players, so every config name is restored automatically.

What config cannot restore is a name added AFTER the seed — through the admin box or
Discord `/name` — because `_acceptNamesIntoPool` writes to the DB pool, not to config.json.
If such a name has since been assigned to a player it exists in exactly one place: that
player's row.

Measured on the prod snapshot, of 426 names on player rows and not in the pool:
    385  also in config.json      -> restored automatically, no action needed
     25  lineage variants         -> deliberately dropped (owner)
     16  REAL, unrecoverable      -> Leggy Bogard, Wet Kevin, Savvy Cabbages, ...

Sixteen, not four hundred. Still worth running: they are the fan-submitted ones, they are
the only names with a story attached, and nothing would have reported their loss.

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
    # Backfill curated_names with anything config.json cannot restore. Going forward
    # _acceptNamesIntoPool records these at approval time, but names approved BEFORE that
    # existed only on a player row — this is their one chance to get a durable home.
    try:
        import json as _json, os as _os
        cfg = set()
        if _os.path.exists('config.json'):
            cfg = {n.lower() for n in _json.load(open('config.json')).get('players', [])}
        conn.execute("""CREATE TABLE IF NOT EXISTS curated_names (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(120) NOT NULL UNIQUE,
            source VARCHAR(20), created_at DATETIME)""")
        known = {r[0] for r in conn.execute("select name from curated_names")}
        orphans = [n for n in harvested if n.lower() not in cfg and n not in known]
        if orphans:
            from datetime import datetime as _dt
            conn.executemany(
                "insert or ignore into curated_names (name, source, created_at) values (?,?,?)",
                [(n, 'backfill', _dt.utcnow()) for n in orphans])
            print(f"\n  curated_names backfilled with {len(orphans)} name(s) that "
                  f"config.json cannot restore")
            for n in orphans[:8]:
                print(f"      * {n}")
    except Exception as e:
        print(f"\n  (curated_names backfill skipped: {e})")

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
