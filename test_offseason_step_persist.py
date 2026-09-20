"""An offseason step is marked done only after its player changes are in the database.

⚠️ THE MARKER MAKES A RESTART SKIP THE STEP, and the offseason steps change players in
memory only — contract decrements, expirations, retirements, trades. The one full save
used to come at `_saveSeasonState`, after the WHOLE offseason, so a deploy between a step
and that save reloaded pre-offseason rosters and then skipped the step that changes them.
Measured on production, season 6: all 2 retirements and all 35 expired contracts were
still on their old teams in the database behind a completed `frontoffice_decisions`.
"""
import ast

SEASON = 'managers/seasonManager.py'


def _funcSource(path, name):
    src = open(path).read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ''
    raise AssertionError(f'{name} not found in {path}')


def test_playersAreSavedBeforeTheStepIsMarked():
    """Bite check: move `savePlayerData()` below `_persistOffseasonFlow()` and this fails."""
    body = _funcSource(SEASON, '_markOffseasonStepComplete')
    assert 'savePlayerData()' in body, 'marking a step done must save the players'
    assert body.index('savePlayerData()') < body.index('self._persistOffseasonFlow()'), \
        'the players must be saved BEFORE the marker is persisted'


def test_everyStepGoesThroughTheSavingMarker():
    """Nothing writes a completed step by hand, around the save."""
    src = open(SEASON).read()
    body = _funcSource(SEASON, '_markOffseasonStepComplete')
    outside = src.replace(body, '')
    assert '_offseasonCompletedSteps.add(' not in outside, \
        'a step marked complete outside _markOffseasonStepComplete skips the player save'
