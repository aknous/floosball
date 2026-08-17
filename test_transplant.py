"""Effect transplant — graft a donor card's effect onto a target player card.

Same edition + position; target keeps identity + tier, donor consumed, Floobits charged.
Run: DATABASE_DIR=/tmp/floo_transplant .venv/bin/python test_transplant.py
"""
import sys, os, shutil
sys.path.insert(0, '/Users/andrew/Projects/floosball')
os.environ['DATABASE_DIR'] = '/tmp/floo_transplant'
import logging; logging.disable(logging.CRITICAL)

shutil.rmtree('/tmp/floo_transplant', ignore_errors=True)
os.makedirs('/tmp/floo_transplant', exist_ok=True)

from database.connection import init_db, get_session
from database.models import User, Player, CardTemplate, UserCard, UserCurrency
from database.repositories.card_repositories import CurrencyRepository
from managers.cardEffects import buildEffectConfig
from managers.cardManager import CardManager
from constants import TRANSPLANT_COST_BY_EDITION

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond: failures.append(desc)

init_db()
s = get_session()

u = User(email='t@t.com', username='tester'); s.add(u); s.flush()
CurrencyRepository(s).addFunds(u.id, 500, transactionType='test', season=1)

WR, HOLO = 3, 'holographic'
p1 = Player(name='Donor Guy'); p2 = Player(name='Keeper Guy'); s.add_all([p1, p2]); s.flush()

def mkTemplate(player, effect):
    cfg = buildEffectConfig(HOLO, 85, WR, None, forceEffect=effect)
    t = CardTemplate(player_id=player.id, edition=HOLO, season_created=1, player_name=player.name,
                     player_rating=85, position=WR, effect_config=cfg, rarity_weight=10, sell_value=20)
    s.add(t); s.flush(); return t

tDonor = mkTemplate(p1, 'possession')
tTarget = mkTemplate(p2, 'slippery')
donor = UserCard(user_id=u.id, card_template_id=tDonor.id, acquired_via='test')
target = UserCard(user_id=u.id, card_template_id=tTarget.id, acquired_via='test', tier=3)
s.add_all([donor, target]); s.flush()
donorId, targetId, oldTargetTemplateId = donor.id, target.id, tTarget.id
balBefore = s.get(UserCurrency, u.id).balance

print("Transplant 'possession' (donor) onto the Keeper (target), holographic WR")
cm = CardManager(None)
result = cm.transplantEffect(s, u.id, donorId, targetId, currentSeason=1, currentWeek=0)

target = s.get(UserCard, targetId)
newTpl = target.card_template
expect("target now points at a NEW template", target.card_template_id != oldTargetTemplateId)
expect(f"target carries the donor's effect (possession)  got={newTpl.effect_config.get('effectName')}",
       newTpl.effect_config.get('effectName') == 'possession')
expect("target keeps its own player (Keeper Guy)", newTpl.player_id == p2.id and newTpl.player_name == 'Keeper Guy')
expect("target keeps its edition (holographic)", newTpl.edition == HOLO)
expect("target keeps its upgrade tier (III)", target.tier == 3)
expect("donor card is consumed", s.get(UserCard, donorId) is None)
cost = TRANSPLANT_COST_BY_EDITION[HOLO]
s.refresh(s.get(UserCurrency, u.id)); balAfter = s.get(UserCurrency, u.id).balance
expect(f"charged {cost} F  ({balBefore} -> {balAfter})", balAfter == balBefore - cost)

print("\nGuards")
for desc, dt, tt, err in [
    ("same-card rejected", targetId, targetId, "different"),
]:
    try:
        cm.transplantEffect(s, u.id, dt, tt, 1, 0); expect(desc, False)
    except ValueError as e:
        expect(f"{desc}  ({e})", err.lower() in str(e).lower())

# cross-edition guard: make a prismatic WR and try to donate to the holo target
p3 = Player(name='Prism Guy'); s.add(p3); s.flush()
tPrism = CardTemplate(player_id=p3.id, edition='prismatic', season_created=1, player_name='Prism Guy',
                      player_rating=85, position=WR, effect_config=buildEffectConfig('prismatic', 85, WR, None, forceEffect='chain_reaction'),
                      rarity_weight=8, sell_value=30)
s.add(tPrism); s.flush()
prismCard = UserCard(user_id=u.id, card_template_id=tPrism.id, acquired_via='test'); s.add(prismCard); s.flush()
try:
    cm.transplantEffect(s, u.id, prismCard.id, targetId, 1, 0); expect("cross-edition rejected", False)
except ValueError as e:
    expect(f"cross-edition rejected  ({e})", 'edition' in str(e).lower())

# ⚠️ THE DONOR MUST BE FROM THIS SEASON. Nothing checked it, so a previous season's
# card could be fed in to graft its effect onto a live one. That defeated two rules at
# once: only current-season cards can be equipped or score (an expired card is a
# collectible, not a parts bin), and a RETIRED effect is dropped from the MINT POOL
# rather than deleted — but a transplant mints with `forceEffect=`, which bypasses the
# pool, so an old donor could put a deliberately-retired effect back into live play,
# freshly priced at today's values. Verified against the live map: comeback_kid,
# domination, castaway and reclamation are all absent from `effectPoolFor` and all four
# force-mint without complaint. Gating the DONOR closes both, because an effect retired
# at a season boundary cannot appear on a card minted this season.
p4 = Player(name='Last Year Guy'); s.add(p4); s.flush()
tOld = CardTemplate(player_id=p4.id, edition=HOLO, season_created=0, player_name='Last Year Guy',
                    player_rating=85, position=WR,
                    effect_config=buildEffectConfig(HOLO, 85, WR, None, forceEffect='slippery'),
                    rarity_weight=8, sell_value=30)
s.add(tOld); s.flush()
oldCard = UserCard(user_id=u.id, card_template_id=tOld.id, acquired_via='test')
s.add(oldCard); s.flush()
try:
    cm.transplantEffect(s, u.id, oldCard.id, targetId, 1, 0)
    expect("expired donor rejected", False)
except ValueError as e:
    expect(f"expired donor rejected  ({e})", 'previous season' in str(e).lower())

# ...and the same card IS accepted once it is current-season, so the guard is about the
# season and not about something incidental to how this fixture was built.
tOld.season_created = 1
s.flush()
try:
    cm.transplantEffect(s, u.id, oldCard.id, targetId, 1, 0)
    expect("same donor accepted once current-season", True)
except ValueError as e:
    expect(f"same donor accepted once current-season  (got {e})", False)



# ── The All-Pro gate survives a transplant ────────────────────────────────────
#
# ⚠️ THE ROW KNEW IT WAS ALL-PRO AND THE GATE DID NOT. `_createUpgradedTemplate`
# (transplant + promote) and `blendCards` stamped `classification` onto the new template
# row but never passed it to `buildEffectConfig`. The gate is FROZEN into effect_config at
# mint and `buildGateSpec` applies the All-Pro discount only if it is told, so the card
# wore the All-Pro badge with an undiscounted bar: a prismatic WR Copycat gated at 12 FP
# instead of 8. It also left `gate.allPro` false, the flag the lineup reads to draw the AP
# accent and the "All-Pro: bar lowered 30%" note. Reported by a user who transplanted
# Copycat onto an All-Pro card and found that text missing.
#
# ⚠️ Long-standing, but unreachable until season 2: `all_pro` comes from the PRIOR season's
# All-Pro team, so a league's first season mints none. Production ended season 1 with 823
# `rookie` templates and zero `all_pro`.
print()
print("All-Pro gate")

_plain = buildEffectConfig('holographic', 88, 3, None, forceEffect='copycat')
_ap = buildEffectConfig('holographic', 88, 3, None, forceEffect='copycat',
                        classification='all_pro')
expect("All-Pro lowers its own bar",
       _ap['gate']['threshold'] < _plain['gate']['threshold'])
expect("gate.allPro set (drives the accent + the lowered-bar note)",
       bool(_ap['gate'].get('allPro')))

_src = open('managers/cardManager.py').read()
expect("transplant/promote passes the classification",
       'classification=sourceTemplate.classification,\n            forceEffect=forceEffect' in _src)
expect("blend passes the classification",
       'classification=resultClassification,\n        )' in _src)

# ⚠️ The repair is scoped to All-Pro on purpose. A blanket gate recompute would also
# rewrite cards frozen under older rules -- production has six all_in rookie templates in
# exactly that state. Those are owned cards; re-pricing them is a balance change.
_conn = open('database/connection.py').read().split('def _backfillAllProGates')[1].split('\ndef ')[0]
expect("backfill only touches All-Pro templates", "LIKE '%all_pro%'" in _conn)
expect("backfill leaves non-All-Pro gates alone", "want.get('allPro')" in _conn)

print(f"\n{'ALL PASS' if not failures else f'{len(failures)} FAILED: ' + '; '.join(failures)}")
sys.exit(1 if failures else 0)
