"""
EVERY `quarterScores` PAYLOAD CARRIES `ot`.

⚠️ THE LINE SCORE IS BUILT IN MORE THAN ONE PLACE AND THEY DRIFT. The WS `game_state`
broadcast has always sent `ot`; the REST live view and the finished-game view each grew
their own copy of the same dict and neither carried it. The consequence is not a missing
column but a WRONG one: every reader derives "did this game go to overtime" from the OT
points (a finished overtime game reports quarter 4, so the points are the only witness),
so omitting the field asserts the game ended in regulation and the points that decided it
appear nowhere while the four quarters fail to sum to the final score.

This is the same two-payload gap that bit `driveStartYardsToEndzone`, which is why it is
swept STATICALLY rather than tested through one endpoint: a third builder added tomorrow
is caught by construction, whereas a behavioural test only covers the door it knocks on.
"""
import ast
import pathlib

FILES = ['api/main.py', 'api_response_builders.py', 'api/event_models.py']
PERIODS = {'q1', 'q2', 'q3', 'q4', 'ot'}


def _dictLiterals(path):
    """Every dict literal that is the value of a 'quarterScores' key, with its line."""
    tree = ast.parse(pathlib.Path(path).read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == 'quarterScores':
                if isinstance(value, ast.Dict):
                    found.append((value, key.lineno))
    return found


def _sideKeys(sideDict):
    return {k.value for k in sideDict.keys if isinstance(k, ast.Constant)}


def testEveryQuarterScoresPayloadCarriesOt():
    checked = 0
    for path in FILES:
        p = pathlib.Path(path)
        if not p.exists():
            continue
        for payload, lineno in _dictLiterals(path):
            sides = {
                k.value: v for k, v in zip(payload.keys, payload.values)
                if isinstance(k, ast.Constant) and isinstance(v, ast.Dict)
            }
            # A payload that forwards a prebuilt value (no literal home/away) is not a
            # second definition of the line score and has nothing to drift.
            if not sides:
                continue
            assert set(sides) == {'home', 'away'}, f'{path}:{lineno} has sides {set(sides)}'
            for side, sideDict in sides.items():
                keys = _sideKeys(sideDict)
                missing = PERIODS - keys
                assert not missing, (
                    f"{path}:{lineno} quarterScores['{side}'] is missing {sorted(missing)}. "
                    "Every line-score payload carries q1-q4 AND ot -- a finished overtime "
                    "game reports quarter 4, so the OT points are the only evidence it "
                    "went there."
                )
            checked += 1
    assert checked >= 2, f'expected to find several quarterScores payloads, found {checked}'


if __name__ == '__main__':
    testEveryQuarterScoresPayloadCarriesOt()
    print('ok')
