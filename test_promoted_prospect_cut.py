"""A prospect promoted in the offseason starts the season on that roster.

Reported live: a team drafted a prospect, promoted him, and cut him again — all inside
one offseason. The club paid a pick, a roster spot and a cut fee to end up exactly where
it started, and a fan watched a player arrive and vanish before a snap was played.

The FA draft already carried the right rule for its OWN signings — `_draftFilledSlots`,
"a slot filled during this draft is off limits" — but that set is stamped only when a
FREE AGENT is signed. A promoted prospect was never in it, so he walked straight past the
guard that exists for exactly this.

⚠️ FOUR DECIDERS REACH A ROSTER, and the rule has to hold at all of them:

  * `playerManager._upgradeCandidates`   — the FA draft's cut-for-an-upgrade (the report)
  * `frontOfficeBrain.rankCutCandidates` — the GM's cut-for-upgrade sweep
  * `seasonManager._cutToMakeRoomForProspect` — cutting to promote ANOTHER prospect
  * `tradeManager._cutToMakeRoom`        — cutting to make room for a trade

The last one is the subtle one: its existing rule deliberately EXEMPTS the offseason, so
that a gap-filler signed mid-season can be replaced once the season ends. That exemption
is correct, and it is exactly what leaves a promotion unprotected.

Run: .venv/bin/python test_promoted_prospect_cut.py   (exits non-zero on any failure)
"""
import ast
import managers  # noqa: F401  resolve circular import
from managers.playerManager import stampPromotion, wasPromotedThisOffseason

fails = []


def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        fails.append(desc)


class P:
    """Bare stand-in — the predicate reads attributes, nothing more."""
    def __init__(self, name='Prospect'):
        self.name = name


# ── the predicate itself ────────────────────────────────────────────────────
p = P()
expect("an unstamped player is cuttable", not wasPromotedThisOffseason(p, 6))

stampPromotion(p, 6)
expect("promoted this offseason -> not cuttable", wasPromotedThisOffseason(p, 6))

# ⚠️ THE RULE RELEASES ITSELF. "He starts the season there" is satisfied the moment the
# season number moves on, so this must NOT become a permanent no-cut brand.
expect("the NEXT season he is cuttable again", not wasPromotedThisOffseason(p, 7))
expect("and he was never protected in an EARLIER one",
       not wasPromotedThisOffseason(p, 5))

# The offseason runs under the number of the season it follows, which is why the season
# alone is enough here — every promotion path is offseason-only, unlike trades.
expect("None is not a season match", not wasPromotedThisOffseason(P(), 6))
expect("a None player is never protected", not wasPromotedThisOffseason(None, 6))

stampPromotion(P(), None)      # must not raise
expect("an unreadable season stamps harmlessly", True)


# ── every promotion site stamps ─────────────────────────────────────────────
# ⚠️ A stamp nobody applies is worse than no rule at all: the guards below would all
# pass while the bug stayed live. Checked against source so a NEW promotion path that
# forgets to stamp fails here rather than in production.
def _funcSource(path, name):
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(open(path).read(), node)
    raise AssertionError(f"{name} not found in {path}")


PROMOTERS = [
    ('managers/seasonManager.py', '_promoteProspectsAutonomously'),
    ('managers/playerManager.py', '_attemptRosterFill'),
]
for path, fn in PROMOTERS:
    expect(f"{fn} stamps the promotion", 'stampPromotion(' in _funcSource(path, fn))


# ── every cut site consults it ──────────────────────────────────────────────
CUTTERS = [
    ('managers/playerManager.py', '_attemptRosterFill',
     'the FA draft upgrade cut (the reported path)'),
    ('managers/frontOfficeBrain.py', 'rankCutCandidates',
     "the GM's cut-for-upgrade sweep"),
    ('managers/seasonManager.py', '_cutToMakeRoomForProspect',
     'cutting to promote another prospect'),
    ('managers/tradeManager.py', '_cutToMakeRoom',
     'cutting to make room for a trade'),
]
for path, fn, desc in CUTTERS:
    expect(f"{desc} refuses a just-promoted player",
           'wasPromotedThisOffseason(' in _funcSource(path, fn))


# ── the trade rule's offseason exemption is still there ─────────────────────
# ⚠️ Bite check in the other direction. `_cutToMakeRoom` exempts the offseason ON PURPOSE
# (a mid-season gap-filler should be replaceable once the season ends), and the fix must
# not have "tidied" that away — the blockbuster path is offseason-only and needs this
# function to make room at all.
body = _funcSource('managers/tradeManager.py', '_cutToMakeRoom')
expect("the trade rule still exempts the offseason for in-season acquisitions",
       "phase = 'season' if week is not None else 'offseason'" in body)

print("\nPASS — promoted in the offseason means he starts the season there."
      if not fails else f"\n{len(fails)} FAILED")
raise SystemExit(1 if fails else 0)
