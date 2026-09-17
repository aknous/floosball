"""A traded pick moves the ROOKIE draft and nothing else.

⚠️ THE LEAGUE RUNS TWO WORST-FIRST DRAFTS off the SAME order object. `currentSeason.
freeAgencyOrder` is read by the rookie draft and by free agency alike, so the only thing
separating them is that exactly one of the two re-orders itself by pick ownership. That is
a single call, easy to add to the wrong place, and adding it to free agency would silently
let a traded pick decide who signs a free agent — a rule nobody wrote and no error reports.
"""
import ast
import inspect
import re

SEASON = 'managers/seasonManager.py'
PLAYER = 'managers/playerManager.py'
OWNERSHIP = ('DraftPick', 'current_owner_id', 'draft_picks', '_applyPickOwnership')


def _funcSource(path, name):
    src = open(path).read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ''
    raise AssertionError(f'{name} not found in {path} — this sweep is measuring nothing')


def test_onlyTheRookieDraftAppliesPickOwnership():
    """⚠️ EXACTLY ONE CALL SITE. Two would mean free agency had grown one; zero would mean
    the rookie draft lost it, which already happened once — every traded pick was cosmetic,
    a team could buy the first selection, see it on the transactions page, and not get it.

    Bite check: call `_applyPickOwnership` in `_processFreeAgency` and this fails.
    """
    src = open(SEASON).read()
    calls = re.findall(r"self\._applyPickOwnership\(", src)
    assert len(calls) == 1, f'expected exactly one call site, found {len(calls)}'
    assert 'self._applyPickOwnership(' in _funcSource(SEASON, '_runRookieDraftPhase'), \
        'the one call site must be the rookie draft'


def test_freeAgencyNeverConsultsPickOwnership():
    """The FA draft orders itself by record and nothing else."""
    for path, name in ((SEASON, '_processFreeAgency'),
                       (PLAYER, 'freeAgencyPickGenerator'),
                       (PLAYER, 'conductFreeAgencySimulation'),
                       (PLAYER, '_attemptRosterFill')):
        body = _funcSource(path, name)
        found = [w for w in OWNERSHIP if w in body]
        assert not found, f'{name} reads pick ownership {found}; picks must not touch free agency'


def test_ownershipIsScopedToTheSeasonAndFirstRound():
    """⚠️ A traded pick is `(season, round, original team, current owner)`. Without the season
    and round filter the rookie draft would re-order itself using next year's picks too."""
    body = _funcSource(SEASON, '_applyPickOwnership')
    assert 'DraftPick.season == season' in body, 'ownership must be scoped to this season'
    assert 'DraftPick.round_number == 1' in body, 'ownership must be scoped to round 1'
    assert 'DraftPick.used == False' in body, 'a spent pick must not re-order anything'
