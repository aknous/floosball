"""One-off: extend short contracts on players who fall into the new TierA/S
bands but were classified under the old (misaligned) tier thresholds.

Background: tier-to-star-band alignment shifted in playerManager.sortPlayersByPosition.
Old thresholds (S≥93, A≥87, B≥77, C≥69) left a gap: rating 84-86 displayed
as 4 stars in the UI but contracted as TierB — yielding 1-year deals on
visually 4-star players. New thresholds align 1:1 with the UI:
  TierS ≥ 92 (floor 3yr) — 5★
  TierA ≥ 84 (floor 2yr) — 4★ ← players in 84-91 may have under-floor deals
  TierB ≥ 76 (floor 1yr) — 3★
  TierC ≥ 68 (floor 1yr) — 2★
  TierD <  68 (floor 1yr) — 1★

This script walks every rostered player (team_id not null, not retired/prospect)
and extends their contract to the tier floor when current term is below it.
Both `term` and `term_remaining` are bumped — but only if `term_remaining` is
ALSO below the floor (so a player partway through a long deal isn't given
extra years they didn't sign for).

Idempotent via /data/tier_aligned_contracts.consumed marker file.

Usage (production):
    fly ssh sftp shell
    put scripts/adjust_tier_aligned_contracts.py /data/adjust_tier_aligned_contracts.py
    exit
    fly ssh console
    cd /data
    python3 -c "import sqlite3; src=sqlite3.connect('/data/floosball.db'); dst=sqlite3.connect('/data/floosball.db.pretieradjust'); src.backup(dst); src.close(); dst.close()"
    python3 /data/adjust_tier_aligned_contracts.py
"""

import os
import sqlite3
import sys

DB_PATH = os.environ.get('FLOOSBALL_DB', '/data/floosball.db')
MARKER = os.environ.get('FLOOSBALL_MARKER', '/data/tier_aligned_contracts.consumed')

# Mirror playerManager._getPlayerTerm tier floors for veterans.
# Rookies (seasonsPlayed==0) are excluded — their rookie deal already
# matches the new bands via the fixed-term branch in _getPlayerTerm.
TIER_FLOORS = {
    'TierS': 3,
    'TierA': 2,
    'TierB': 1,
    'TierC': 1,
    'TierD': 1,
}


def tierFor(rating):
    """Return tier name for a rating, matching the NEW (aligned) bands."""
    if rating is None:
        return 'TierC'
    if rating >= 92:
        return 'TierS'
    if rating >= 84:
        return 'TierA'
    if rating >= 76:
        return 'TierB'
    if rating >= 68:
        return 'TierC'
    return 'TierD'


def main():
    if os.path.exists(MARKER):
        print(f'Marker present at {MARKER} — already ran. Delete to re-apply.')
        sys.exit(0)
    if not os.path.exists(DB_PATH):
        print(f'No DB at {DB_PATH}', file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Only rostered, non-prospect, non-rookie players. Rookies on their first
    # contract should NOT be adjusted — their rookie deals are tier-specific
    # already and shouldn't be retroactively lengthened.
    cur.execute("""
        SELECT id, name, player_rating, term, term_remaining,
               seasons_played, team_id
        FROM players
        WHERE team_id IS NOT NULL
          AND (is_prospect IS NULL OR is_prospect = 0)
          AND (is_upcoming_rookie IS NULL OR is_upcoming_rookie = 0)
          AND seasons_played > 0
    """)
    rows = cur.fetchall()

    adjusted = 0
    skipped = 0
    examined = len(rows)
    byTier = {}

    for row in rows:
        rating = row['player_rating']
        term = row['term'] or 0
        termRem = row['term_remaining'] or 0
        tier = tierFor(rating)
        floor = TIER_FLOORS[tier]

        # Only extend when BOTH term and term_remaining are below the floor —
        # that's the smoking-gun "short deal" pattern. A player who signed a
        # long deal and has played some of it down (term=4, termRemaining=1)
        # is mid-contract and shouldn't be retroactively extended.
        if term >= floor and termRem >= floor:
            skipped += 1
            continue
        if term < floor and termRem < floor:
            newTerm = floor
            newRem = floor
            cur.execute(
                "UPDATE players SET term = ?, term_remaining = ? WHERE id = ?",
                (newTerm, newRem, row['id']),
            )
            adjusted += 1
            byTier[tier] = byTier.get(tier, 0) + 1
            print(f'  +{floor - term} yr -> {row["name"]:30s} '
                  f'(rating={rating}, {tier}, was {term}/{termRem}, now {newTerm}/{newRem})')
        else:
            # Edge case — term was high but term_remaining low (or vice
            # versa). Likely user mid-contract; leave alone.
            skipped += 1

    conn.commit()
    conn.close()

    print()
    print(f'Examined {examined} rostered veterans')
    print(f'Adjusted {adjusted} contracts:')
    for tier, n in sorted(byTier.items()):
        print(f'  {tier}: {n}')
    print(f'Skipped {skipped} (already at or above tier floor)')

    # Write marker so we can't re-run by accident.
    try:
        with open(MARKER, 'w') as f:
            f.write(f'examined={examined} adjusted={adjusted}\n')
        print(f'Marker written: {MARKER}')
    except OSError as e:
        print(f'Warning: could not write marker: {e}', file=sys.stderr)


if __name__ == '__main__':
    main()
