"""/api/bot/lineup: a linked Discord user's fantasy lineup (the equipped cards).

Shows what the site's lineup shows: this week's cards, or with none written yet, the
latest earlier week's carried forward minus vaulted / other-season cards. An explicit
"unequip everything" this week stays empty. Each slot has the player, the card effect
and the edition; the live player's name/team win over the card's snapshot.

Exercises the real handler via TestClient with bot auth and the season stubbed. Uses
the dev DB under a made-up season (9999), restores the borrowed user's Discord field and
deletes the template, cards, equipped rows and roster it adds.

Run: .venv/bin/python test_bot_lineup.py   (exits non-zero on any failure)
"""
import sys, types
sys.path.insert(0,'/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
if 'floosball_game' not in sys.modules:
    _s=types.ModuleType('floosball_game'); _s.Game=type('G',(),{})
    sys.modules['floosball_game']=_s
    import managers.timingManager  # noqa
    del sys.modules['floosball_game']
from fastapi.testclient import TestClient
import api.main as M
from database.connection import get_session
from database.models import User, UserCard, EquippedCard, CardTemplate, FantasyRoster

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkBotAuth] = lambda: None

SEASON = 9999
class FakeSeason: seasonNumber = SEASON; currentWeek = 1
class FakeTeam: name = 'Live Team'; abbr = 'LIV'
class FakePlayer: name = 'Live Name'; team = FakeTeam()
class FakePM:
    live = set()
    def getPlayerById(self, pid): return FakePlayer() if pid in self.live else None
class FakeSM: currentSeason = FakeSeason()
class FakeApp: seasonManager = FakeSM(); playerManager = FakePM()
M.floosball_app = FakeApp()

DID = '999000999001'
s = get_session()
for u in s.query(User).filter(User.discord_id==DID).all(): u.discord_id = None
s.commit()
user = s.query(User).order_by(User.id).first()
savedDid = user.discord_id
user.discord_id = DID
s.commit()

src = s.query(CardTemplate).filter(CardTemplate.effect_config.isnot(None)).order_by(CardTemplate.id.desc()).first()
tmpl = CardTemplate(**{a.key: getattr(src, a.key) for a in CardTemplate.__mapper__.column_attrs if a.key != 'id'})
tmpl.season_created = SEASON
tmpl.edition = 'prismatic'
tmpl.effect_config = {"displayName": "Captain", "detail": "Amplifies the others", "tagline": "Set the tone"}
s.add(tmpl); s.commit()
qb, k = (UserCard(user_id=user.id, card_template_id=tmpl.id, acquired_via='starter') for _ in range(2))
s.add_all([qb, k]); s.commit()
roster = FantasyRoster(user_id=user.id, season=SEASON)
s.add(roster); s.commit()
c = TestClient(M.app)

def get(did=DID):
    r = c.get('/api/bot/lineup', params={'discordId': did})
    return r.status_code, (r.json().get('data') or {})

try:
    print("1. Basics")
    expect("unlinked → 404", get('999000999999')[0] == 404)
    code, d = get()
    expect(f"no cards at all → empty lineup ({code})", code == 200 and d['slots'] == [] and d['username'] == user.username)

    print("2. This week's cards")
    s.add_all([EquippedCard(user_id=user.id, season=SEASON, week=1, slot_number=6, slot='K', user_card_id=k.id, streak_count=3),
               EquippedCard(user_id=user.id, season=SEASON, week=1, slot_number=1, user_card_id=qb.id)])
    s.commit()
    code, d = get()
    slots = d['slots']
    expect("two slots, in slot order (a missing slot string comes from the ordinal)",
           [x['slot'] for x in slots] == ['QB', 'K'])
    expect("player, effect and edition", slots[0]['playerName'] == tmpl.player_name
           and slots[0]['effectName'] == 'Captain' and slots[0]['effectDetail'] == 'Amplifies the others'
           and slots[0]['edition'] == 'prismatic')
    expect("streak carried through", slots[1]['streakCount'] == 3)
    expect("not locked yet", d['locked'] is False and d['week'] == 1)
    s.query(EquippedCard).filter_by(season=SEASON, week=1).update({'locked': True}); s.commit()
    expect("locked once games start", get()[1]['locked'] is True)
    FakePM.live = {tmpl.player_id}
    x = get()[1]['slots'][0]
    expect("live player's name and team win over the snapshot", x['playerName'] == 'Live Name' and x['teamAbbr'] == 'LIV')
    FakePM.live = set()

    print("3. Nothing written this week yet → last week carries")
    FakeSeason.currentWeek = 2
    code, d = get()
    expect("week 2 shows week 1's lineup, unlocked", [x['slot'] for x in d['slots']] == ['QB', 'K']
           and d['week'] == 2 and d['locked'] is False)
    qb.vaulted = True; s.commit()
    expect("a card vaulted since doesn't carry", [x['slot'] for x in get()[1]['slots']] == ['K'])
    qb.vaulted = False; s.commit()
    roster.last_equipped_set_week = 2; s.commit()
    expect("unequipped everything this week → empty", get()[1]['slots'] == [])
    roster.last_equipped_set_week = None; s.commit()
    s.add(EquippedCard(user_id=user.id, season=SEASON, week=2, slot_number=1, slot='QB', user_card_id=qb.id)); s.commit()
    expect("this week's own cards win", [x['slot'] for x in get()[1]['slots']] == ['QB'])

    print("4. Week unknown (reads 0 after a restart)")
    FakeSeason.currentWeek = 0
    d = get()[1]
    expect("shows the latest week's lineup", [x['slot'] for x in d['slots']] == ['QB'] and d['week'] == 2)
finally:
    s.query(EquippedCard).filter(EquippedCard.season == SEASON).delete(synchronize_session=False)
    s.query(FantasyRoster).filter(FantasyRoster.season == SEASON).delete(synchronize_session=False)
    s.delete(qb); s.delete(k); s.flush(); s.delete(tmpl)
    u = s.get(User, user.id); u.discord_id = savedDid
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)
