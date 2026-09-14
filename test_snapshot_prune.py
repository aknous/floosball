"""
THE OFFSEASON SNAPSHOT PRUNE KEEPS ONLY THE SEASON RUNNING RIGHT NOW.

`seasonManager._snapshotDbForPhase` writes a rollback checkpoint at the entry to each
non-idempotent offseason phase, and prunes older ones first so the volume stays flat.

⚠️ THE PRUNE TESTED `snap_season < seasonNum` AND THAT STRANDED 76MB ON PROD. A fresh
start restarts the season counter at 1, so every snapshot written BEFORE the reset
carries a HIGHER number than anything written after it — `17 < 6` is False, so the
pre-reset files could never be reached by any later offseason and sat on the volume
forever. Found on prod holding two season-17 snapshots against a live season 6, on a
974MB volume already at 59%.

Season numbers are NOT monotonic across the life of a volume. The only safe thing to
keep is "belongs to the season running right now", which is `!=`, not `<`.

⚠️ AND IT MUST STAY `!=` RATHER THAN "DELETE EVERYTHING ELSE FIRST": the three partial
phases (rookie_draft / fa_draft / training) each write their own snapshot within ONE
season and legitimately coexist, so a same-season sibling must survive the prune that
runs when the next phase starts.
"""
import os
import re
import glob
import tempfile


def _prune(outDir, seasonNum):
    """The prune exactly as _snapshotDbForPhase performs it."""
    removed = []
    for old in glob.glob(os.path.join(outDir, 'offseason_s*_*.db')):
        fname = os.path.basename(old)
        try:
            snapSeason = int(fname.split('_')[1].lstrip('s'))
        except (ValueError, IndexError):
            continue
        if snapSeason != seasonNum:
            os.remove(old)
            removed.append(fname)
    return sorted(removed)


def _touch(d, name):
    open(os.path.join(d, name), 'w').write('x')


def testPruneKeepsOnlyTheCurrentSeason():
    d = tempfile.mkdtemp(prefix='floos_prune_')
    # The exact shape found on prod: a live season 6, season-5 leftovers from the
    # offseason just finished, and season-17 files from before a fresh start.
    for n in ('offseason_s17_fa_draft.db', 'offseason_s17_training.db',
              'offseason_s5_fa_draft.db', 'offseason_s5_training.db',
              'offseason_s6_rookie_draft.db'):
        _touch(d, n)

    removed = _prune(d, 6)

    assert removed == ['offseason_s17_fa_draft.db', 'offseason_s17_training.db',
                       'offseason_s5_fa_draft.db', 'offseason_s5_training.db'], removed
    left = sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, '*.db')))
    assert left == ['offseason_s6_rookie_draft.db'], left


def testAHigherSeasonNumberIsStillStale():
    """The regression proper: `<` leaves these behind, `!=` does not."""
    d = tempfile.mkdtemp(prefix='floos_prune_')
    _touch(d, 'offseason_s17_training.db')
    assert _prune(d, 6) == ['offseason_s17_training.db']
    assert glob.glob(os.path.join(d, '*.db')) == []


def testSameSeasonSiblingsSurvive():
    """A later phase's prune must not delete the earlier phase's rollback point."""
    d = tempfile.mkdtemp(prefix='floos_prune_')
    for n in ('offseason_s6_rookie_draft.db', 'offseason_s6_fa_draft.db'):
        _touch(d, n)
    assert _prune(d, 6) == []
    assert len(glob.glob(os.path.join(d, '*.db'))) == 2


def testTheLiveRuleIsTheOneTested():
    """
    Read the prune out of seasonManager itself, so this file cannot pass while the
    shipped rule says something else. The mirror above is a convenience, not the
    authority.
    """
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'managers', 'seasonManager.py')).read()
    block = re.search(r"for old in glob\.glob\(os\.path\.join\(outDir, 'offseason_s\*_\*\.db'\)\):"
                      r".*?os\.remove\(old\)", src, re.S)
    assert block, 'could not find the prune loop in seasonManager'
    assert 'snap_season != seasonNum' in block.group(0), (
        'the shipped prune is not comparing with != — a season number lower than the '
        'current one is not the only kind of stale snapshot, see this file\'s docstring'
    )


if __name__ == '__main__':
    testPruneKeepsOnlyTheCurrentSeason()
    testAHigherSeasonNumberIsStillStale()
    testSameSeasonSiblingsSurvive()
    testTheLiveRuleIsTheOneTested()
    print('ok')
