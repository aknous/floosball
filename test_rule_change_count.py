"""The Rulebook chip counts RULES, and the Rulebook highlights FIELDS.

Reported from the game board: the chip said three rules had changed when two had.

The cause is that "a rule" and "a field" are different units and `/api/rules` answered
both questions with the same list. A CHANGE the fans vote on is a ballot CANDIDATE, and
a preset candidate patches several fields at once — the Darts format sets `gameFormat`
AND `targetScore`, a Drive Clock preset sets up to four — so a field-level diff reports
one fan-visible change as two or three. Darts plus one other rule counts exactly the
three that was reported.

⚠️ BOTH NUMBERS ARE WANTED, which is why this is not simply a wrong list. The Rulebook
popover highlights per FIELD on purpose, so every row a preset touched lights up and
shows its "was X"; the count has to speak in rules. They must stay separate.

⚠️ The correct implementation already existed and had NO CALLERS: `RuleVoteManager`
carried `_changedCount` over the candidates while the endpoint grew its own field diff.
Both now delegate to `game_rules.changedRuleCandidates`, so there is one definition.

Run: .venv/bin/python test_rule_change_count.py   (exits non-zero on any failure)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

from game_rules import GameRules, changedRuleCandidates
from constants import RULE_VOTE_CANDIDATES, GAME_FORMAT_PRESETS, DRIVE_CLOCK_PRESETS

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

SKIP = {"patchHistory", "fieldGoalUprights"}
DEFAULTS = GameRules().toDict()

def rulesWith(patch):
    g = GameRules()
    for k, v in patch.items():
        setattr(g, k, v)
    return g

def fieldCount(g):
    """What the endpoint used to report — kept here as the thing being guarded against."""
    return len([k for k, v in g.toDict().items()
                if k not in SKIP and DEFAULTS.get(k) != v])

DARTS = next(p for p in GAME_FORMAT_PRESETS if 'Darts' in (p.get('label') or ''))

# ── 1. a standard league is standard ────────────────────────────────────────
print("\n-- an untouched ruleset --")
expect("no rules changed", changedRuleCandidates(GameRules()) == [])

# ── 2. the reported case ────────────────────────────────────────────────────
print("\n-- the case that was reported --")
g = rulesWith({**DARTS['patch'], 'clockStopsOnDeadBall': False})
got = changedRuleCandidates(g)
expect(f"Darts plus a running clock is TWO rules, not three (was {fieldCount(g)}, now {len(got)})",
       len(got) == 2 and fieldCount(g) == 3)
expect(f"and it names them ({sorted(got)})",
       sorted(got) == ['clockStopsOnDeadBall', 'gameFormat'])

# ── 3. every preset counts as exactly one ───────────────────────────────────
# ⚠️ Swept over the presets rather than spot-checked, because the mismatch is invisible
# until a preset happens to patch more than one field OFF ITS DEFAULT: the Darts patch
# is 7 fields and only 2 of them differ from default, and one Drive Clock preset is
# clean while the other two are not. A spot check picks the clean one half the time.
print("\n-- a preset is one rule however many fields it sets --")
for label, presets, key in (('game format', GAME_FORMAT_PRESETS, 'gameFormat'),
                            ('drive clock', DRIVE_CLOCK_PRESETS, 'driveClock')):
    for p in presets:
        g = rulesWith(p['patch'])
        got = changedRuleCandidates(g)
        name = p.get('label') or p.get('key')
        expect(f"{label} '{name}' counts as 1 (touches {fieldCount(g)} fields)",
               got == [key])

# ── 4. scalars are unaffected, so the fix cannot under-count ────────────────
# ⚠️ The failure mode of a fix like this is the opposite error — collapsing genuinely
# separate rules into one — so assert the plain case still counts every one.
print("\n-- separate scalar rules still count separately --")
g = rulesWith({'clockStopsOnDeadBall': False, 'downsPerSeries': 5,
               'touchdownPoints': 8, 'scoringModel': 'spread'})
expect(f"four scalar changes count as four ({len(changedRuleCandidates(g))})",
       len(changedRuleCandidates(g)) == 4)

# ── 5. one definition, not two ──────────────────────────────────────────────
print("\n-- the ballot and the endpoint agree by construction --")
from managers.ruleVoteManager import RuleVoteManager
rv = RuleVoteManager.__new__(RuleVoteManager)
mismatched = []
for patch in [DARTS['patch'], {'clockStopsOnDeadBall': False}, {'downsPerSeries': 5},
              *[p['patch'] for p in DRIVE_CLOCK_PRESETS],
              *[p['patch'] for p in GAME_FORMAT_PRESETS]]:
    g = rulesWith(patch)
    if rv._changedCount(g) != len(changedRuleCandidates(g)):
        mismatched.append(patch)
expect(f"the vote manager's count matches the shared one everywhere ({len(mismatched)} mismatches)",
       not mismatched)

# ⚠️ Every candidate must be reachable by this function, or a rule could be changed and
# never counted — the silent direction of this bug.
print("\n-- and no candidate is invisible to the count --")
unreachable = []
for f, spec in RULE_VOTE_CANDIDATES.items():
    key = spec.get('gate') if 'presets' in spec else f
    if not key or not hasattr(GameRules(), key):
        unreachable.append(f)
expect(f"all {len(RULE_VOTE_CANDIDATES)} candidates resolve to a real field ({unreachable})",
       not unreachable)

print()
if fails:
    print(f"FAIL — {len(fails)} problem(s):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("PASS — the chip counts rules, the Rulebook highlights fields, and one function decides.")
