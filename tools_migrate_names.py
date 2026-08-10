"""Fold every name a live database knows about back into config.json's pool.

WHY THIS EXISTS
---------------
`config.json`'s `players` list is the seed the code ships with, and it is the ONLY
name source a brand-new database has. Everything added after a deploy lives in the
database instead: names typed into the admin portal, names accepted from Discord
`/name` submissions, and names that were drawn out of the pool onto a player or a
coach and are therefore no longer sitting in `unused_names` at all.

A fresh start loses all of it. `clear_db()` preserves `unused_names`, so the names
nobody has drawn yet survive a `.fresh` restart — but a name currently worn by a
player or a coach is deleted with that row, and a brand-new volume loses even the
pool. Either way the curated additions evaporate and the league quietly shrinks
back to whatever shipped.

This walks a database, collects every name it can find, reduces each to its BASE
form, and reports the ones config.json has never heard of.

⚠️ THE BASE FORM IS THE WHOLE TRICK
-----------------------------------
`seasonManager._recyclePlayerName` walks a retiring player's name up a generational
ladder and returns the variant to the pool:

    Base -> Jr. -> III -> IV -> V -> VI -> VII -> VIII -> IX -> X -> XI

So a database holds "Freed Marinara Jr." while config holds "Freed Marinara". Those
are the same pooled name at different points in its life, and writing the variant
into config.json would seed a pool that starts partway up the ladder, producing a
league of Juniors with no parents. Measured on the season-17 production database:
187 names looked new, and only 97 of them actually were. The other 90 were
generational variants of names config already had.

Coaches draw from the SAME pool as players (`_seedUnusedNames` filters against both
tables), so a coach's name is a pooled name and belongs here too.

There is no fallback name generator to worry about: the draw returns None when the
pool runs dry rather than inventing anything, so every name in a database came from
the pool or from a human.

USAGE
-----
    python3 tools_migrate_names.py <database.db>            # report only
    python3 tools_migrate_names.py <database.db> --apply    # rewrite config.json
"""

import json
import os
import re
import sqlite3
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

# The ladder from `_recyclePlayerName`, longest-first so "VIII" is not eaten as "V"
# followed by a stranded "III".
_SUFFIXES = ('Jr.', 'VIII', 'XII', 'XI', 'IX', 'VII', 'VI', 'IV', 'III', 'II', 'X', 'V')
_SUFFIX_RE = re.compile(r'\s+(' + '|'.join(re.escape(s) for s in _SUFFIXES) + r')$')


def baseName(name: str) -> str:
    """Strip generational suffixes until the name stops shrinking.

    Repeated because the ladder can stack in stored data ("Foo Jr. III" has been
    seen), and one pass would leave the outer rung attached.
    """
    previous = None
    while previous != name:
        previous = name
        name = _SUFFIX_RE.sub('', name).strip()
    return name


def collect(dbPath: str) -> dict:
    """Every name the database holds, keyed by where it was found."""
    conn = sqlite3.connect(os.path.abspath(dbPath))
    have = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}

    def column(table: str, where: str = '') -> set:
        if table not in have:
            return set()
        rows = conn.execute(f"select name from {table} {where}")
        return {r[0].strip() for r in rows if r and r[0] and r[0].strip()}

    found = {
        # Never drawn — the pool as it stands.
        'unused_names': column('unused_names'),
        # Drawn onto someone. These are the ones a fresh start silently drops.
        'players': column('players'),
        'coaches': column('coaches'),
        # Approved through the admin portal / Discord but possibly not yet pooled.
        'name_submissions': column('name_submissions', "where status='approved'"),
        # The durable home for admin additions in newer code. Absent on older
        # deployments, which is exactly why the tables above have to be read too.
        'curated_names': column('curated_names'),
    }
    conn.close()
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    dbPath = sys.argv[1]
    apply = '--apply' in sys.argv

    if not os.path.exists(dbPath):
        print(f"No such database: {dbPath}")
        return 1

    config = json.load(open(CONFIG_PATH))
    pooled = config.get('players', [])
    known = set(pooled)

    found = collect(dbPath)
    everything = set().union(*found.values()) if found else set()

    # Reduce to base names and drop anything config already ships.
    additions = sorted({baseName(n) for n in everything} - known)

    print(f"config.json pool          : {len(pooled)}")
    for source, names in sorted(found.items()):
        label = f"{source} " + ("(absent)" if not names else "")
        print(f"  {label:26}: {len(names)}")
    print(f"distinct names in database: {len(everything)}")
    print(f"raw names not in config   : {len(everything - known)}")
    print(f"BASE names not in config  : {len(additions)}  <- the real additions")
    print()

    if not additions:
        print("Nothing to add. config.json already covers every name in that database.")
        return 0

    for name in additions:
        origins = [s for s, names in found.items() if any(baseName(n) == name for n in names)]
        print(f"  + {name:34} ({', '.join(sorted(origins))})")

    if not apply:
        print(f"\nDRY RUN. {len(additions)} name(s) would be appended to config.json's "
              f"players pool, taking it from {len(pooled)} to {len(pooled) + len(additions)}.")
        print("Re-run with --apply to write it.")
        return 0

    # ⚠️ APPEND, never re-sort. The list is in the order it was written over years and
    # a sort would turn a 97-line addition into a 789-line diff nobody can review.
    config['players'] = pooled + additions
    with open(CONFIG_PATH, 'w') as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    print(f"\nWrote config.json: {len(pooled)} -> {len(config['players'])} names.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
