"""The trade reasoning is USER-FACING PROSE and obeys the app's copy rules.

⚠️ THESE STRINGS ARE PERSISTED. `sellerWhy` / `buyerWhy` are written into `trades` at
settlement and rendered on the transactions page, so a wrong word is not just displayed —
it is stored, and every trade already settled keeps it. There is no re-render that fixes
them later, which is why this sweeps the SOURCE rather than a sample of output.

Two house rules:
  - the word is TEAM, never "club" (owner, standing)
  - no gendered pronouns; the league is not all men (owner, standing)
"""
import ast
import re

SOURCE = 'managers/tradeManager.py'
# ⚠️ EVERY FUNCTION THAT WRITES A `why`, not just the two obvious ones. Sweeping only
# `sellerWhy`/`buyerWhy` passed while the PICK-SWAP reasoning — written in
# `pickInquiriesFor` and `bidForPick`, and shown on the same page — still said "club".
# A copy rule that covers most of the copy is a rule nobody can rely on.
FUNCS = ('sellerWhy', 'buyerWhy', 'pickInquiriesFor', 'bidForPick')
GENDERED = re.compile(r"\b(he|him|his|she|her|hers|man|men)\b", re.IGNORECASE)
# ⚠️ An em or en dash reads as AI-written in this app's voice (owner, standing). It is a
# separate rule from the two below and was missed by the first version of this sweep, which
# is how three of them reached the page.
DASHES = ('\u2014', '\u2013')


def _stringsIn(funcName):
    """Every string literal inside one method, from the AST.

    ⚠️ FROM THE AST, NOT A REGEX OVER THE FILE. A regex cannot tell a user-facing f-string
    from the comment above it, and the comments here legitimately say "club" in the
    codebase's own internal voice — sweeping those would make the test unpassable and it
    would be disabled rather than fixed.
    """
    tree = ast.parse(open(SOURCE).read())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == funcName:
            # ⚠️ EXCLUDE THE DOCSTRING BY NODE, NOT BY VALUE. `ast.get_docstring` returns a
            # CLEANED, dedented copy, so `is not` against it never matches and the
            # docstring sweeps in — where the word "club" and the phrase "not all men"
            # legitimately appear in the codebase's own internal voice, failing the test
            # on the comment that explains the rule.
            docNode = None
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docNode = first.value
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                        and sub is not docNode):
                    out.append(sub.value)
    return out


def test_theReasoningSaysTeamNotClub():
    for fn in FUNCS:
        for text in _stringsIn(fn):
            assert not re.search(r"\bclubs?\b", text, re.IGNORECASE), \
                f"{fn} says 'club' in user-facing copy: {text!r}"


def test_theReasoningUsesNoGenderedPronouns():
    for fn in FUNCS:
        for text in _stringsIn(fn):
            hit = GENDERED.search(text)
            assert not hit, f"{fn} has a gendered word {hit.group(0)!r}: {text!r}"


def test_theSweepActuallySeesTheStrings():
    """⚠️ A SWEEP THAT FINDS NOTHING PASSES EVERYTHING. If the AST walk stops matching —
    a rename, a move to a helper — both tests above go quietly green while the copy rots."""
    for fn in FUNCS:
        found = _stringsIn(fn)
        assert len(found) >= 3, f"{fn}: only {len(found)} strings found; the sweep is broken"
    # and at least one function must carry the recognisable reasoning prose, or the sweep
    # is walking the right names and finding the wrong thing
    allText = ' '.join(t for fn in FUNCS for t in _stringsIn(fn))
    assert any(w in allText for w in ('contract', 'window', 'hole', 'draft')), \
        'the strings found do not look like the reasoning copy'


def test_theReasoningHasNoEmDashes():
    """⚠️ SEPARATE FROM THE OTHER TWO RULES AND MISSED BY THE FIRST SWEEP. Three dashed
    clauses reached the page and had to be normalized out of already-settled rows, which is
    the cost of a persisted string: there is no re-render that fixes it later.

    Bite check: put " \u2014 " back in any reasoning string and this fails.
    """
    for fn in FUNCS:
        for text in _stringsIn(fn):
            for d in DASHES:
                assert d not in text, f"{fn} has an em/en dash in user-facing copy: {text!r}"
