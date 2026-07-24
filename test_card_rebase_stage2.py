"""Stage-2 re-base: 9 roster-aggregate effects now read the DEPICTED card player.

docs/CARD_REBASE_AUDIT.md. Each was rewritten from a roster sum/count to the card
player's own stat, and dropped from the stat gate (a re-based card is already tied to
its player). Over/under-performance effects were deliberately NOT re-based.

Run: .venv/bin/python test_card_rebase_stage2.py
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
from managers.cardEffects import computeEffect, buildEffectConfig, buildGateSpec
from managers.cardEffectCalculator import CardCalcContext

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond:
        failures.append(desc)

CARD = 500      # the depicted player
OTHER = 501     # another roster player, whose stats must NOT count anymore


def ctx(cardStats, otherStats=None):
    c = CardCalcContext()
    c.rosterPlayerIds = {CARD, OTHER}
    c.rosterPlayerPositions = {CARD: 3, OTHER: 2}
    c.rosterPlayerNames = {CARD: "Card Guy", OTHER: "Other Guy"}
    c.weekPlayerStats = {CARD: cardStats, OTHER: (otherStats or {})}
    c.gamesActive = False
    return c


def run(effect, cardStats, otherStats=None, edition='base', position=3):
    cfg = buildEffectConfig(edition, 80, position, forceEffect=effect)
    return computeEffect(cfg, ctx(cardStats, otherStats), CARD, 1)


print("1. Closers — this player's Q4 FP only, not the roster's")
r = run('closer', {"fantasyPoints": 20, "q4FantasyPoints": 10}, otherStats={"q4FantasyPoints": 40})
expect(f"scores off the card player's 10 Q4 FP, ignoring the other's 40  (+{r.fpBonus})",
       r.fpBonus and r.fpBonus < 40)

print("2. Piggy Bank — a cut of this player's FP, not roster FP")
r = run('piggy_bank', {"fantasyPoints": 100}, otherStats={"fantasyPoints": 100})
r2 = run('piggy_bank', {"fantasyPoints": 0}, otherStats={"fantasyPoints": 100})
expect(f"pays on the card player's FP  (+{r.floobits}F)", r.floobits > 0)
expect(f"card player at 0 FP -> ~0 even if the other scored 100  (+{r2.floobits}F)",
       r2.floobits == 0)

print("3. Bizarro (snake_eyes) — inverse to THIS player's FP")
low = run('snake_eyes', {"fantasyPoints": 0}, edition='diamond')
high = run('snake_eyes', {"fantasyPoints": 30}, edition='diamond')
expect(f"card player at 0 FP -> big multiplier  (x{low.multBonus})", low.multBonus > 1.0)
expect(f"card player at 30 FP -> no bonus  (x{high.multBonus})", high.multBonus <= 1.0)

print("4. Odometer — this player's own yards, single-player gates")
r = run('odometer', {"fantasyPoints": 20, "receiving_stats": {"rcvYards": 90}})
expect(f"90 rec yds clears a couple of single-player gates  (+{r.fpBonus} FP)",
       r.fpBonus and r.fpBonus > 0)
r0 = run('odometer', {"receiving_stats": {"rcvYards": 5}},
         otherStats={"rushing_stats": {"runYards": 500}})
expect(f"5 own yds pays ~nothing, ignoring the other's 500  (+{r0.fpBonus} FP)",
       not r0.fpBonus)

print("5. Honor Roll — fires on THIS player clearing the FP bar")
hit = run('honor_roll', {"fantasyPoints": 25})
miss = run('honor_roll', {"fantasyPoints": 5}, otherStats={"fantasyPoints": 99})
expect(f"card player at 25 FP -> FPx bonus  (x{hit.multBonus})", hit.multBonus > 1.0)
expect(f"card player at 5 FP -> nothing, even if the other scored 99  (x{miss.multBonus})",
       not miss.multBonus or miss.multBonus <= 1.0)

print("6. Hedge — tops up a bad game by THIS player")
bad = run('hedge', {"fantasyPoints": 2})
good = run('hedge', {"fantasyPoints": 40})
expect(f"a 2 FP game gets a hedge top-up  (+{bad.fpBonus} FP)", bad.fpBonus and bad.fpBonus > 0)
expect(f"a 40 FP game needs no hedge  (+{good.fpBonus} FP)", not good.fpBonus)

print("7. Re-based effects still read the card player; ALL cards get the FP power bar now")
# The power-bar redesign gates every effect uniformly (owner call 2026-07-23), so the
# re-bases are no longer exempt — they read 'this player' AND carry a bar.
for e in ('closer', 'walk_off', 'odometer', 'honor_roll', 'piggy_bank',
          'catalyst', 'hedge', 'bonsai', 'snake_eyes'):
    cfg = buildEffectConfig('base', 80, 3, forceEffect=e)
    expect(f"{e}: carries the FP power bar", cfg.get('gate', {}).get('threshold'))

print("8. Over/under-performance effects were NOT re-based (still roster-scoped)")
for e in ('rising_tide', 'buy_low', 'reclamation', 'babysitter', 'consolation_prize'):
    expect(f"{e}: still carries a gate", buildGateSpec(e, 3) is not None)

print()
if failures:
    print(f">>> {len(failures)} FAILURE(S)")
    for f in failures:
        print("   -", f)
    sys.exit(1)
print("PASS — Stage-2 effects read the card player; all cards carry the FP bar.")
