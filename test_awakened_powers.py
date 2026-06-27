"""Awakened (L4) powers — P1: signature-ability catalog + assignment at awakening.

Verifies the catalog maps each position to the right offensive ability (by best attribute) and
defensive takeaway, and that anomalyManager.assignAwakenedAbilities persists those onto AnomalyState.

Run: python test_awakened_powers.py  (throwaway temp DB)
"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.getcwd())
_tmp = tempfile.mkdtemp(prefix="floo_l4_")
os.environ["DATABASE_DIR"] = _tmp

from database.connection import init_db, get_session
init_db()
import managers.awakenedPowers as ap
from managers import anomalyManager
from database.models import Player, PlayerAttributes, AnomalyState

failures = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)

# All non-null PlayerAttributes int fields, defaulted so the fixture is valid.
_ATTRS = ['overall_rating','speed','hands','reach','agility','power','arm_strength','accuracy',
          'leg_strength','skill_rating','potential_speed','potential_hands','potential_agility',
          'potential_power','potential_arm_strength','potential_accuracy','potential_leg_strength',
          'potential_skill_rating','route_running','vision','blocking','discipline','attitude',
          'focus','instinct','creativity','resilience','clutch_factor','pressure_handling',
          'longevity','play_making_ability','x_factor']
_FLOAT_ATTRS = {'confidence_modifier': 0.0, 'determination_modifier': 0.0, 'luck_modifier': 0.0}

# ── 1. Catalog: best attribute -> ability per position ──────────────────
print("1. Catalog maps best attribute -> offensive ability + defensive takeaway")
cat = [
    ('QB', {'armStrength': 95, 'accuracy': 80, 'agility': 70}, 'cannon', 'ballhawk'),
    ('QB', {'armStrength': 70, 'accuracy': 92, 'agility': 80}, 'pinpoint', 'ballhawk'),
    ('RB', {'speed': 90, 'power': 95, 'agility': 85}, 'battering_ram', 'strip_score'),
    ('WR', {'speed': 88, 'hands': 94, 'reach': 80}, 'glue_hands', 'pick_six'),
    ('TE', {'hands': 85, 'power': 91, 'agility': 80}, 'the_wall', 'blow_up'),
    ('K',  {'legStrength': 96, 'accuracy': 88}, 'howitzer', None),
]
for pos, attrs, eOff, eDef in cat:
    o, d = ap.assignAbilities(pos, attrs)
    expect(f"{pos} {max(attrs, key=attrs.get)}-best -> {eOff}/{eDef}", o == eOff and d == eDef)
expect("kicker has no defensive ability", ap.assignAbilities('K', {'legStrength': 90, 'accuracy': 80})[1] is None)
expect("key->name lookup (cannon)", ap.abilityName('cannon') == 'Cannon')
expect("key->detail has flavor + side", len(ap.abilityDetail('pick_six')['flavor']) >= 3 and ap.abilityDetail('pick_six')['side'] == 'defense')

# ── 2. assignAwakenedAbilities persists onto AnomalyState (real DB) ──────
print("\n2. assignAwakenedAbilities writes + persists the signature abilities")
s = get_session()
def mkPlayer(pid, name, position, **attrOver):
    s.add(Player(id=pid, name=name, position=position))
    d = {k: 70 for k in _ATTRS}; d.update(_FLOAT_ATTRS); d.update(attrOver)
    s.add(PlayerAttributes(player_id=pid, **d))

mkPlayer(1, 'Arm QB', 0, arm_strength=95)        # QB -> cannon / ballhawk
mkPlayer(2, 'Power RB', 1, power=96)             # RB -> battering_ram / strip_score
mkPlayer(3, 'Hands WR', 2, hands=95)             # WR -> glue_hands / pick_six
mkPlayer(4, 'Leg K', 4, leg_strength=97)         # K  -> howitzer / None
s.commit()

expected = {1: ('cannon', 'ballhawk'), 2: ('battering_ram', 'strip_score'),
            3: ('glue_hands', 'pick_six'), 4: ('howitzer', None)}
for pid, (eOff, eDef) in expected.items():
    st = AnomalyState(player_id=pid, season=1, state='awakened')
    s.add(st)
    res = anomalyManager.assignAwakenedAbilities(s, st, pid)
    expect(f"player {pid}: assigned {eOff}/{eDef}", res == (eOff, eDef)
           and st.offensive_ability == eOff and st.defensive_ability == eDef)
s.commit()

# reload in a fresh session — confirms the new columns persist through the migration
s2 = get_session()
row = s2.query(AnomalyState).filter_by(player_id=1, season=1).first()
expect("persisted + reloaded (QB cannon/ballhawk)",
       row.offensive_ability == 'cannon' and row.defensive_ability == 'ballhawk')

shutil.rmtree(_tmp, ignore_errors=True)
print()
if failures:
    print(f"FAILED ({len(failures)}): " + "; ".join(failures))
    raise SystemExit(1)
print("ALL AWAKENED-POWERS P1 TESTS PASS")
