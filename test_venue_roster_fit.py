"""A GM builds for the stadium it plays fourteen games a year in.

Where the venue suppresses the passing game the front office should value the run --
backs, and tight ends for their blocking -- over quarterbacks and receivers, and the
inverse where the air is clean. Two things this must NOT do, and both are easy to ship
by accident:

  - devalue quarterbacks league-wide. Real weather suppresses throwing far more often
    than running, so an ABSOLUTE reading of each venue made 20 of 32 run-favoring
    against 1 pass-favoring. Fed to the front office that is not 32 identities, it is
    an instruction to stop drafting the position the sim measures as most impactful
    (+2.52 wins). The bias is therefore centered on the LEAGUE.
  - invert the position hierarchy. A team plays half its games away, so a roster fitted
    hard to one venue is paid for in the other fourteen. The weight tips close calls
    and nothing more.

Run: .venv/bin/python test_venue_roster_fit.py   (exits non-zero on any failure)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
from managers.stadiumManager import getStadiumManager
from managers.frontOfficeBrain import positionValue, venueBiasFor
from constants import POSITION_VALUE, VENUE_POSITION_WEIGHT

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

m = getStadiumManager()
class P:
    def __init__(self, pos): self.position = pos
class Team:
    def __init__(self, tid): self.id = tid

bias = {t: m.phaseBias(t) for t in range(1, 33)}

# ── the league is not pushed off one way ───────────────────────────────────
total = sum(bias.values())
expect(f"the bias is centered, so no position is devalued league-wide (sum {total:+.2f})",
       abs(total) < 3.0)
run = sum(1 for v in bias.values() if v > 0.2)
pas = sum(1 for v in bias.values() if v < -0.2)
expect(f"both leanings are well represented ({run} run, {pas} pass)",
       run >= 8 and pas >= 8)
expect("every bias is inside the usable range", all(-1.0 <= v <= 1.0 for v in bias.values()))

# ── the weighting does what it says ────────────────────────────────────────
runVenue, passVenue = 1.0, -1.0
expect("a run venue values RB and TE up, QB and WR down",
       positionValue(P('RB'), runVenue) > POSITION_VALUE['RB']
       and positionValue(P('TE'), runVenue) > POSITION_VALUE['TE']
       and positionValue(P('QB'), runVenue) < POSITION_VALUE['QB']
       and positionValue(P('WR'), runVenue) < POSITION_VALUE['WR'])
expect("a pass venue does the exact inverse",
       positionValue(P('QB'), passVenue) > POSITION_VALUE['QB']
       and positionValue(P('WR'), passVenue) > POSITION_VALUE['WR']
       and positionValue(P('RB'), passVenue) < POSITION_VALUE['RB'])
expect("kickers are unaffected by the venue's phase",
       positionValue(P('K'), runVenue) == positionValue(P('K'), passVenue) == POSITION_VALUE['K'])
expect("a neutral venue changes nothing at all",
       all(positionValue(P(p), 0.0) == POSITION_VALUE[p] for p in POSITION_VALUE))

# ── it tips close calls, it does not rewrite the hierarchy ────────────────
# ⚠️ The single most important assertion here. At the most extreme run venue in the
# league a quarterback must STILL be worth more than a back, or the venue has stopped
# being a lean and become a different sport.
worst = min(bias, key=lambda t: -bias[t])
extreme = max(abs(v) for v in bias.values())
expect(f"even at the most run-favoring venue, QB still outranks RB (bias {extreme:+.2f})",
       positionValue(P('QB'), extreme) > positionValue(P('RB'), extreme))
expect("even at the most pass-favoring venue, RB still outranks TE",
       positionValue(P('RB'), -extreme) > positionValue(P('TE'), -extreme))
swing = positionValue(P('QB'), 1.0) / POSITION_VALUE['QB']
expect(f"the swing stays modest ({(1-swing)*100:.0f}% at full bias)",
       abs(1 - swing) <= 0.15)

# ── it degrades to neutral rather than raising ────────────────────────────
expect("an unknown team has no venue lean", venueBiasFor(Team(9999)) == 0.0)
expect("no team at all has no venue lean", venueBiasFor(None) == 0.0)
expect("a real team resolves its own stadium", venueBiasFor(Team(7)) == bias[7])
class Broken:
    @property
    def id(self): raise RuntimeError("boom")
expect("a valuation never depends on the venue file being readable",
       venueBiasFor(Broken()) == 0.0)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — GMs build for their own stadium, without any position losing league-wide.")
