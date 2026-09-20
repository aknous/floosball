"""Nose Picker sits in the streak class, and its streak costs something to hold.

Reported: the card is too strong and trivial to max out. Two separate causes.

⚠️ IT WAS THE ONLY STREAK EFFECT IN THE GAME BELOW PRISMATIC. Edition IS the effect
tier, so being holographic drew `EDITION_POWER_SCALE` 1.70 against the 0.70 every card
it competes with mechanically draws — a 2.43x dial nobody chose. Moving it to the tier
its peers occupy fixes the size by construction rather than by picking a smaller number:
the power scale, the gate bar and the mint pool all follow the tier.

⚠️ AND IT IS THE ONE STREAK WHOSE CONDITION IS NOT A PERFORMANCE OUTCOME. Every peer
asks the game for something. This one asks the user to submit picks by hand — free, and
guaranteed. That is why it belongs at the BOTTOM of its class rather than the middle: a
card that always pays should pay less than one that sometimes does.

⚠️ AND THE CONDITION DID NOT MEAN WHAT IT SAID. Four separate sites decided "did they
submit manually" with an inline `any(not p.is_auto ...)`, which asks whether ONE pick
was manual — so a single hand-made pick alongside fifteen auto-fills held the streak,
against the card's own tooltip and its own code comment.

⚠️ NOT TOUCHED: the break penalty. `growthPerTick = 0` looks like it disables the
peak-carry machinery, and it does — but that makes a break HARSHER here than for peers,
not softer: `newPeak` collapses to `baseReward`, `peak_output` is cleared, and the card
drops to flat base. There was nothing to restore.

⚠️ Values are frozen at mint, so this reaches newly-minted templates only — landing it
at a season boundary applies it uniformly with no migration.

Run: .venv/bin/python test_nose_picker_rails.py   (exits non-zero on any failure)
"""
import math
import managers  # noqa: F401  resolve circular import
from managers.cardEffects import (EFFECT_EDITION_TIER, STREAK_CONFIGS,
                                  buildEffectConfig, picksWereSubmittedManually)

fails = []


def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        fails.append(desc)


class Pick:
    def __init__(self, auto):
        self.is_auto = auto


# ── the condition means what the card says ──────────────────────────────────
# Bite check: restore `any(not p.is_auto for p in picks)` and the mixed case flips.
expect("a full slate submitted by hand holds the streak",
       picksWereSubmittedManually([Pick(False)] * 16))
expect("ONE hand-made pick beside fifteen auto-fills does NOT",
       not picksWereSubmittedManually([Pick(False)] + [Pick(True)] * 15))
expect("an all-auto week does not", not picksWereSubmittedManually([Pick(True)] * 16))
expect("a week with no picks at all does not", not picksWereSubmittedManually([]))
expect("nor does None", not picksWereSubmittedManually(None))

# ⚠️ ONE DEFINITION, FOUR READERS. The week-end settle, the live display and both
# projection paths each had their own copy and all four carried the same bug. A new
# reader writing its own is how this comes back.
#
# Scoped to the flag itself rather than the whole file: `not p.is_auto` appears legitimately
# in the Contrarian and Jinx achievement hooks, which are not streak code and already read
# the slate correctly.
FLAGS = ('userManualPickSubmittedThisWeek', 'hasManualSubmit')
for path in ('managers/seasonManager.py', 'managers/fantasyTracker.py',
             'managers/cardProjection.py'):
    bad = []
    for line in open(path).read().splitlines():
        stripped = line.strip()
        for flag in FLAGS:
            if not stripped.startswith(f'{flag} ='):
                continue
            rhs = stripped.split('=', 1)[1].strip()
            if rhs in ('True', 'False') or 'picksWereSubmittedManually(' in rhs:
                continue
            # The projection's historical fallback FORECASTS whether this user usually
            # submits by hand, for a week that has not happened. It classifies each prior
            # week through the shared predicate and then thresholds the count, which is a
            # different question from "was this week manual" and legitimately not a
            # direct call.
            if rhs.startswith('manualWeeks >='):
                continue
            bad.append(stripped)
    expect(f"{path.split('/')[-1]} sets manual-submit only from the shared predicate "
           f"({bad[0][:48] if bad else 'clean'})", not bad)
    expect(f"  ...and actually calls it",
           'picksWereSubmittedManually' in open(path).read())


# ── it lives in the streak class ────────────────────────────────────────────
expect("nose_picker is a streak effect", 'nose_picker' in STREAK_CONFIGS)
expect("and it is prismatic, where the streak class lives",
       EFFECT_EDITION_TIER['nose_picker'] == 'prismatic')

# ⚠️ THE REAL ASSERTION: no streak effect sits below prismatic. Written over the whole
# table rather than over this one name, so the next streak card minted a tier too cheap
# fails here instead of shipping at 2.43x its peers.
TIER_ORDER = ['base', 'metallic', 'holographic', 'prismatic', 'diamond']
tooCheap = [n for n in STREAK_CONFIGS
            if n in EFFECT_EDITION_TIER
            and TIER_ORDER.index(EFFECT_EDITION_TIER[n]) < TIER_ORDER.index('prismatic')]
expect(f"no streak effect is cheaper than prismatic (found {tooCheap or 'none'})",
       not tooCheap)


# ── and the numbers land in its class, at the bottom ────────────────────────
def curve(name, rating=80):
    cfg = buildEffectConfig('prismatic', rating, 1, forceEffect=name)
    p = cfg['primary']
    base = p.get('baseReward', p.get('baseFP', 0))
    if 'coef' in p:
        return [base + p['coef'] * math.log(1 + n / p['kStreak']) for n in (1, 17)]
    g = p.get('growthPerTick', 0)
    return [base, base + g * 16]


nose1, nose17 = curve('nose_picker')
print(f"      nose_picker at rating 80: week 1 {nose1:.1f} FP, week 17 {nose17:.1f} FP")

expect(f"week 1 is no longer the highest in the class ({nose1:.1f} FP)", nose1 < 40.9)
expect(f"the ceiling is inside the class, not above it ({nose17:.1f} FP)", nose17 < 80)
# It still has to be worth equipping — a free trigger means it is realized nearly every
# week, where a contingent peer's streak keeps resetting.
expect(f"but it still pays a real amount ({nose17:.1f} FP)", nose17 > 25)
expect("the streak still grows", nose17 > nose1)


# ── the break is already a hard reset, and must stay one ────────────────────
cfg = buildEffectConfig('prismatic', 80, 1, forceEffect='nose_picker')
expect("growthPerTick is 0, so a break clears the peak and drops to flat base",
       cfg['primary'].get('growthPerTick', 0) == 0)

print("\nPASS — a free trigger pays the bottom of its class, not the top."
      if not fails else f"\n{len(fails)} FAILED")
raise SystemExit(1 if fails else 0)
