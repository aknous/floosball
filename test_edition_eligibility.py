"""A strong previous season opens every edition, whatever the rating.

⚠️ SIX PLAYERS OF 192 HELD THE ENTIRE DIAMOND POOL. Measured on production season 20,
diamond-eligible BY RATING was QB 1 / RB 1 / WR 3 / TE 0 / K 1 — and because
`_assignEffects` tops a bucket up to `max(players * k, len(effects))` and splits it across
whoever is present, a ONE-PLAYER bucket mints that bucket's entire effect set onto that
one man. At diamond the card simply IS the player. Diamond TE had nobody at all, so every
TE-exclusive diamond effect was unmintable that season — the same failure CLAUDE.md
records for QB and K in an earlier season, moved position, because it is structural.

The sharpest single case: season 20's All-Pro **Tanuki Batman rates 65**. The league named
him the best at his position and the card system would not mint him above metallic — 65 is
below even the holographic bar of 75.

Measured effect of the rule (season 20, 192 rostered players):

    pos     n    holographic   prismatic     diamond
    QB     32      17 -> 20     10 -> 13      1 -> 7
    RB     32      14 -> 15      7 -> 10      1 -> 8
    WR     64      30 -> 31     21 -> 25      3 -> 13
    TE     32      14 -> 15      5 ->  8      0 -> 6
    K      32      20 -> 20     10 -> 10      1 -> 3
    total          95 -> 101    53 -> 66      6 -> 37

It lands almost entirely on the tier whose scarcity is pathological, and fills the empty
diamond TE bucket.

Run: DATABASE_DIR=/tmp/floo_elig .venv/bin/python test_edition_eligibility.py
"""
import sys, os, shutil
sys.path.insert(0, '/Users/andrew/Projects/floosball')
os.environ['DATABASE_DIR'] = '/tmp/floo_elig'
import logging; logging.disable(logging.CRITICAL)

shutil.rmtree('/tmp/floo_elig', ignore_errors=True)
os.makedirs('/tmp/floo_elig', exist_ok=True)

from database.connection import init_db, get_session
from database.models import Player, PlayerSeasonStats
from managers.cardManager import CardManager, EDITION_THRESHOLDS, _buildClassification
from constants import EDITION_ELIGIBILITY_PERF_BAR

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond: failures.append(desc)

init_db()
s = get_session()
SEASON = 5           # templates are being minted FOR season 5, so the bar reads season 4

def mkPlayer(name, perf=None):
    p = Player(name=name); s.add(p); s.flush()
    if perf is not None:
        s.add(PlayerSeasonStats(player_id=p.id, season=SEASON - 1,
                                performance_rating=perf))
        s.flush()
    return p

print("1. What opens every edition")
strong = mkPlayer('Strong Season', perf=EDITION_ELIGIBILITY_PERF_BAR)
justUnder = mkPlayer('Just Under', perf=EDITION_ELIGIBILITY_PERF_BAR - 1)
noStats = mkPlayer('No Stats')
allPro = mkPlayer('All Pro', perf=60)
mvp = mkPlayer('The MVP', perf=60)
champ = mkPlayer('A Champion', perf=60)

over = CardManager.editionEligibilityOverrides(
    s, SEASON, mvpPlayerId=mvp.id, allProPlayerIds={allPro.id})

expect(f"a previous season at the bar ({EDITION_ELIGIBILITY_PERF_BAR}) qualifies",
       strong.id in over)
expect("one point under does not", justUnder.id not in over)
expect("no previous season does not", noStats.id not in over)
expect("an All-Pro qualifies on the tag alone (rated 60)", allPro.id in over)
expect("the MVP qualifies on the tag alone", mvp.id in over)

print("\n2. ⚠️ Champion is EXCLUDED, and its classification survives anyway")
# ⚠️ THE TRAP THIS FILE EXISTS FOR. `championPlayerIds` feeds TWO things a few lines
# apart: the eligibility gate and `_buildClassification`. Excluding champion means
# keeping it out of the GATE — deleting the set would strip the CH tag off every
# champion card in the league.
overWithChamp = CardManager.editionEligibilityOverrides(
    s, SEASON, mvpPlayerId=mvp.id, allProPlayerIds={allPro.id})
expect("a champion-roster player is NOT made eligible by the ring",
       champ.id not in overWithChamp)
expect("...and the helper takes no champion argument at all, so it cannot creep back",
       'championPlayerIds' not in CardManager.editionEligibilityOverrides.__code__.co_varnames)

cls = _buildClassification(champ.id, False, None, {champ.id}, set(), 'holographic')
expect(f"but a champion card STILL wears its CH tag  (got {cls!r})",
       cls is not None and 'champion' in cls)
clsMvp = _buildClassification(mvp.id, False, mvp.id, set(), set(), 'holographic')
expect(f"and an MVP card still wears its own  (got {clsMvp!r})",
       clsMvp is not None and 'mvp' in clsMvp)

print("\n3. The gate it replaces still applies to everyone else")
expect("the diamond bar itself is unchanged", EDITION_THRESHOLDS['diamond'] == 90)
expect("a 65-rated player with no claim is still metallic-only",
       justUnder.id not in over)

print("\n4. ⚠️ Fails CLOSED")
# A missing or unreadable stats table must leave the rating gate exactly as it was, never
# open every edition to everyone — the failure direction matters more than the failure.
class _Broken:
    def execute(self, *a, **k): raise RuntimeError('no such table')
broken = CardManager.editionEligibilityOverrides(_Broken(), SEASON)
expect(f"an unreadable stats table yields NO overrides, not all of them  (got {broken})",
       broken == set())
brokenWithTags = CardManager.editionEligibilityOverrides(
    _Broken(), SEASON, mvpPlayerId=mvp.id, allProPlayerIds={allPro.id})
expect("...while the accolade half, which needs no query, still stands",
       brokenWithTags == {mvp.id, allPro.id})

print()
if failures:
    print(f"{len(failures)} FAILED"); sys.exit(1)
print("PASS — production opens the tier, a ring does not.")
