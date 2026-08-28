"""Synthetic cards — every player available, any effect grafted on, worth nothing outside
fantasy.

⚠️ THE WHOLE DESIGN IS ONE ASSERTION: a synthetic scores IDENTICALLY to the real pull of
the same effect — same power scale, same gate, same params — and is strictly worse in
every collection surface. You pay a Synth Component for convenience, never for power.

Under owner ruling 8 that identity holds BY CONSTRUCTION rather than by arithmetic: the
template is minted at the EFFECT's own edition, so `EDITION_POWER_SCALE`,
`CARD_GATE_FP_THRESHOLDS_BY_EDITION`, `_tierUpgradeCost` and the client's edition color
all land correctly off one assignment. It is asserted anyway, precisely because it now
looks free — and because minting at the target's `base` edition instead would be
STRONGER than the real card, not weaker (prismatic is the lowest rung of the power scale,
so a prismatic effect at base scale nearly doubles).

Run: DATABASE_DIR=/tmp/floo_synth .venv/bin/python test_synthetic_cards.py
"""
import sys, os, shutil
sys.path.insert(0, '/Users/andrew/Projects/floosball')
os.environ['DATABASE_DIR'] = '/tmp/floo_synth'
import logging; logging.disable(logging.CRITICAL)

shutil.rmtree('/tmp/floo_synth', ignore_errors=True)
os.makedirs('/tmp/floo_synth', exist_ok=True)

from database.connection import init_db, get_session
from database.models import User, Player, CardTemplate, UserCard, UserCurrency
from database.repositories.card_repositories import CurrencyRepository
from managers.cardEffects import buildEffectConfig, EFFECT_EDITION_TIER
from managers.cardManager import CardManager, getSellValue, getCardValue
from constants import TRANSPLANT_COST_BY_EDITION

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond: failures.append(desc)

init_db()
s = get_session()
cm = CardManager(None)

u = User(email='t@t.com', username='tester'); s.add(u); s.flush()
CurrencyRepository(s).addFunds(u.id, 5000, transactionType='test', season=1)

WR, RATING = 3, 85
# A PRISMATIC effect is the sharp case: prismatic is the LOWEST rung of
# EDITION_POWER_SCALE, so minting it at `base` scale nearly doubles it.
EFFECT = 'chain_reaction'
assert EFFECT_EDITION_TIER[EFFECT] == 'prismatic', 'fixture premise'

def mkPlayer(n):
    p = Player(name=n); s.add(p); s.flush(); return p

# ⚠️ `team_id` MUST BE SET. `basePoolTemplates` filters `team_id IS NOT NULL` — the same
# guard the Combine uses — because a null team is an off-roster player (prospect/rookie
# pollution) and cards are for rostered players only. A fixture without it produced an
# empty pool and read as a bug in the code under test.
TEAM = 1
def mkTemplate(player, edition, effect, **kw):
    cfg = buildEffectConfig(edition, RATING, WR, None, forceEffect=effect)
    t = CardTemplate(player_id=player.id, edition=edition, season_created=1,
                     player_name=player.name, player_rating=RATING, position=WR,
                     team_id=TEAM, effect_config=cfg, rarity_weight=10,
                     sell_value=20, **kw)
    s.add(t); s.flush(); return t

def mkCard(t, **kw):
    c = UserCard(user_id=u.id, card_template_id=t.id, acquired_via='test', **kw)
    s.add(c); s.flush(); return c


print("1. Synthesis: a prismatic effect onto a base card")
donorP, baseP = mkPlayer('Donor Guy'), mkPlayer('Any Player')
donor = mkCard(mkTemplate(donorP, 'prismatic', EFFECT))
basePrint = mkCard(mkTemplate(baseP, 'base', 'none'))
balBefore = s.get(UserCurrency, u.id).balance
cm.transplantEffect(s, u.id, donor.id, basePrint.id, currentSeason=1, currentWeek=0)
synth = s.get(UserCard, basePrint.id).card_template

expect("the base card carries the donor's effect",
       synth.effect_config.get('effectName') == EFFECT)
expect("it keeps its OWN player (any player, any effect)",
       synth.player_id == baseP.id)
expect(f"it is minted at the EFFECT's edition, not the target's  (got {synth.edition})",
       synth.edition == 'prismatic')
expect("it is flagged synthetic", synth.is_synthetic is True)
# ⚠️ Pricing reads the effect's edition. Read off the TARGET it resolves through
# `TRANSPLANT_COST_BY_EDITION.get('base', 0)` and the whole operation is FREE.
cost = TRANSPLANT_COST_BY_EDITION['prismatic']
balAfter = s.get(UserCurrency, u.id).balance
expect(f"charged the EFFECT's price, {cost} F  ({balBefore} -> {balAfter})",
       balAfter == balBefore - cost)


print("\n2. THE WHOLE DESIGN: identical in play to the real pull")
realP = mkPlayer('Real Puller')
real = mkTemplate(realP, 'prismatic', EFFECT)
sc, rc = synth.effect_config, real.effect_config
expect(f"same effect name ({sc.get('effectName')})", sc.get('effectName') == rc.get('effectName'))
expect(f"same primary params  synth={sc.get('primary')} real={rc.get('primary')}",
       sc.get('primary') == rc.get('primary'))
expect(f"same gate  synth={sc.get('gate')} real={rc.get('gate')}",
       sc.get('gate') == rc.get('gate'))
expect("same output type", sc.get('outputType') == rc.get('outputType'))
# The tier ladder reads template.edition too, so ruling 7 (upgradeable) is priced off
# the effect rather than off base — the cheapest rung in the game.
expect("tier upgrades cost the EFFECT's edition price",
       cm._tierUpgradeCost(s.get(UserCard, basePrint.id), 2)
       == cm._tierUpgradeCost(mkCard(real), 2))


print("\n3. ...and worth nothing outside fantasy")
synthCard = s.get(UserCard, basePrint.id)
expect(f"sells for 1, not a prismatic's price  (got {getSellValue(synth.edition, True, True)})",
       getSellValue(synth.edition, isActive=True, isSynthetic=True) == 1)
expect("the DISPLAYED value agrees with the PAID value",
       cm.serializeCard(synthCard, 1)['sellValue'] == getCardValue(synthCard, 1))
expect("Combine fuel value is 1, so a missed refusal is cheap not catastrophic",
       getCardValue(synthCard, 1) == 1)
expect("it carries no classification it did not earn", not synth.classification)
expect("the payload flags it so the client can mute it and label it SNTH",
       cm.serializeCard(synthCard, 1).get('synthetic') is True)

for desc, fn, err in [
    ("cannot be vaulted", lambda: cm.vaultCard(s, u.id, synthCard.id, 1, 0), 'synthetic'),
]:
    try:
        fn(); expect(desc, False)
    except ValueError as e:
        expect(f"{desc}  ({e})", err in str(e).lower())

# ⚠️ Refusing the vault refuses the Showcase for free — only vaulted cards can be
# featured there — so no Showcase rule is written anywhere.
expect("and therefore never reaches the Showcase (it rides the vault)",
       not synthCard.vaulted)

fodderP = mkPlayer('Fodder')
fodder = mkCard(mkTemplate(fodderP, 'prismatic', 'all_in'))
try:
    cm.blendCards(s, u.id, [synthCard.id, fodder.id], 1, 0); expect("Combine refuses it", False)
except ValueError as e:
    expect(f"Combine refuses it  ({e})", 'synthetic' in str(e).lower())


print("\n4. Donor only, never a target")
otherP = mkPlayer('Other Prism')
other = mkCard(mkTemplate(otherP, 'prismatic', 'all_in'))
try:
    cm.transplantEffect(s, u.id, other.id, synthCard.id, 1, 0)
    expect("a synthetic cannot RECEIVE an effect", False)
except ValueError as e:
    expect(f"a synthetic cannot RECEIVE an effect  ({e})", "fixed" in str(e).lower())

# Donating needs no exemption: a synthetic already IS its effect's edition, so it
# satisfies the same-edition rule on its own.
targetP = mkPlayer('Real Target')
realTarget = mkCard(mkTemplate(targetP, 'prismatic', 'all_in'))
cm.transplantEffect(s, u.id, synthCard.id, realTarget.id, 1, 0)
expect("a synthetic CAN donate its effect onto a real card",
       s.get(UserCard, realTarget.id).card_template.effect_config.get('effectName') == EFFECT)
expect("...and is consumed doing it", s.get(UserCard, synthCard.id) is None)
expect("the receiving card is NOT synthetic — it was pulled",
       s.get(UserCard, realTarget.id).card_template.is_synthetic is False)


print("\n5. The guards that must still bite")
noEffectP = mkPlayer('Floor Print')
floorPrint = mkCard(mkTemplate(noEffectP, 'base', 'none'))
floor2 = mkCard(mkTemplate(mkPlayer('Floor Two'), 'base', 'none'))
try:
    cm.transplantEffect(s, u.id, floorPrint.id, floor2.id, 1, 0)
    expect("a no-effect card still has nothing to donate", False)
except ValueError as e:
    expect(f"a no-effect card still has nothing to donate  ({e})", 'nothing' in str(e).lower())

# Position validity is unchanged by synthesis — a WR-only effect still needs a WR.
qbBase = mkPlayer('A Quarterback')
qbCfg = buildEffectConfig('base', RATING, 1, None, forceEffect='none')
qbT = CardTemplate(player_id=qbBase.id, edition='base', season_created=1,
                   player_name='A Quarterback', player_rating=RATING, position=1,
                   team_id=TEAM, effect_config=qbCfg, rarity_weight=10, sell_value=2)
s.add(qbT); s.flush()
qbCard = mkCard(qbT)
# ⚠️ Pick a GENUINELY restricted effect. `chain_reaction` returns {1,2,3,4,5} — valid
# everywhere — so using it here made the assertion vacuous (the first draft of this test
# did exactly that and reported a failure in the code rather than in itself).
from managers.cardEffects import effectValidPositions
POS_ONLY = 'possession'
assert effectValidPositions(POS_ONLY) == {3}, 'fixture premise: WR-only effect'
wrOnly = mkCard(mkTemplate(mkPlayer('WR Donor'),
                           EFFECT_EDITION_TIER[POS_ONLY], POS_ONLY))
try:
    cm.transplantEffect(s, u.id, wrOnly.id, qbCard.id, 1, 0)
    expect("position validity still refused on the synthesis path", False)
except ValueError as e:
    expect(f"position validity still refused on the synthesis path  ({e})",
           'position-specific' in str(e).lower())

# An expired donor is still refused — that is what stops a RETIRED effect re-entering
# play through `forceEffect=`, which bypasses the mint pool entirely.
oldT = mkTemplate(mkPlayer('Last Season'), 'prismatic', 'all_in')
oldT.season_created = 0; s.flush()
oldCard = mkCard(oldT)
freshBase = mkCard(mkTemplate(mkPlayer('Fresh Base'), 'base', 'none'))
try:
    cm.transplantEffect(s, u.id, oldCard.id, freshBase.id, 1, 0)
    expect("an expired donor is still refused", False)
except ValueError as e:
    expect(f"an expired donor is still refused  ({e})", 'previous season' in str(e).lower())



print("\n6. The base pool: available to field, absent from the collection")
from database.models import EquippedCard
poolP = mkPlayer('Pool Player')
poolT = mkTemplate(poolP, 'base', 'none')
pool = cm.basePoolTemplates(s, 1)
expect(f"the pool lists this season's floor prints ({len(pool)} found)",
       any(t.id == poolT.id for t in pool))
expect("every pool entry is a base card",
       all(t.edition == 'base' for t in pool))

# ⚠️ Nothing is owned until it is fielded — 192 rows of nothing per user is the thing
# this design exists to avoid.
owned = s.query(UserCard).filter_by(user_id=u.id, card_template_id=poolT.id).first()
expect("a pool card is NOT owned before it is fielded", owned is None)

claimed = cm.claimBaseCard(s, u.id, poolT.id, 1)
expect("claiming materializes a UserCard", claimed is not None and claimed.user_id == u.id)
again = cm.claimBaseCard(s, u.id, poolT.id, 1)
# ⚠️ Get-or-create, not create: a second claim must return the SAME row, or equipping the
# same player two weeks running mints duplicates and every streak/peak lookup keyed on
# user_card_id silently restarts.
expect("claiming twice returns the SAME card, never a duplicate", again.id == claimed.id)
expect("only one row exists for it",
       s.query(UserCard).filter_by(user_id=u.id, card_template_id=poolT.id).count() == 1)

try:
    cm.claimBaseCard(s, u.id, real.id, 1)
    expect("a non-base card can't be claimed from the pool", False)
except ValueError as e:
    expect(f"a non-base card can't be claimed from the pool  ({e})", 'base' in str(e).lower())

oldPool = mkTemplate(mkPlayer('Old Pool'), 'base', 'none')
oldPool.season_created = 0; s.flush()
try:
    cm.claimBaseCard(s, u.id, oldPool.id, 1)
    expect("a previous season's floor print can't be claimed", False)
except ValueError as e:
    expect(f"a previous season's floor print can't be claimed  ({e})",
           'not active' in str(e).lower())

# ⚠️ The collection filter is `edition == 'base'`, which is also what makes a SYNTHETIC
# appear there automatically: synthesis moves the card off `base`, so it leaves the pool
# and enters the collection with no second rule written.
expect("a claimed floor print is still a base card (hidden from the collection)",
       claimed.card_template.edition == 'base')
synth2 = s.query(CardTemplate).filter_by(is_synthetic=True).first()
expect("a synthetic is NOT base, so the same filter shows it in the collection",
       synth2 is not None and synth2.edition != 'base')

print()
if failures:
    print(f"{len(failures)} FAILED"); sys.exit(1)
print("PASS — equal in play, worthless in collection.")
