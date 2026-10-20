"""An explicitly emptied lineup stays empty: no older lineup is carried past it.

Between weeks, currentWeek still names the week just played, so a user who unequips
everything then empties THAT week (and is marked last_equipped_set_week = it). At the
next week's lock, the carry-forward used to skip the empty week and bring back the
lineup from the week before, locking in cards the user had removed. The user's last
explicit set now bounds every lookback:

  - the game-start lock (SeasonManager._carryForwardEquippedCards)
  - the site's GET /api/cards/equipped
  - the bot's /api/bot/lineup and /api/bot/unsubmitted (lineup reminder)

Users: A emptied week 2 (week 1 had cards). B never set anything this way (week 1 has
cards, no marker). C emptied the current week 3. D set a new lineup in week 2.

Uses the dev DB under a made-up season (9999); restores the borrowed users' Discord
fields and deletes the template, cards, equipped rows and rosters it adds.

Run: .venv/bin/python test_lineup_explicit_empty.py   (exits non-zero on any failure)
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
from database.repositories.card_repositories import EquippedCardRepository
from managers.seasonManager import SeasonManager
from constants import ROSTER_MIN_PLAYERS

fails=[]
def expect(d,c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

M.app.dependency_overrides[M._checkBotAuth] = lambda: None
SEASON, WEEK = 9999, 3
class FakeSeason: seasonNumber = SEASON; currentWeek = WEEK; schedule = []; activeGames = None
class FakeSM:
    currentSeason = FakeSeason()
    def _getPickemWeek(self): return WEEK
class FakePM:
    def getPlayerById(self, pid): return None
class FakeApp: seasonManager = FakeSM(); playerManager = FakePM(); serviceContainer = None
M.floosball_app = FakeApp()

DIDS = {'A': '999000555001', 'B': '999000555002', 'C': '999000555003', 'D': '999000555004'}
s = get_session()
for did in DIDS.values():
    for u in s.query(User).filter(User.discord_id == did).all(): u.discord_id = None
s.commit()
users = dict(zip('ABCD', s.query(User).order_by(User.id).limit(4).all()))
saved = [(u.id, u.discord_id, u.discord_dm_reminders) for u in users.values()]
for k, u in users.items():
    u.discord_id, u.discord_dm_reminders = DIDS[k], True
s.commit()

src = s.query(CardTemplate).order_by(CardTemplate.id.desc()).first()
tmpl = CardTemplate(**{a.key: getattr(src, a.key) for a in CardTemplate.__mapper__.column_attrs if a.key != 'id'})
tmpl.season_created = SEASON
s.add(tmpl); s.commit()
cards = {k: [UserCard(user_id=u.id, card_template_id=tmpl.id, acquired_via='starter') for _ in range(ROSTER_MIN_PLAYERS)]
         for k, u in users.items()}
s.add_all([c for cs in cards.values() for c in cs]); s.commit()

def equip(k, week):
    for i, uc in enumerate(cards[k]):
        s.add(EquippedCard(user_id=users[k].id, season=SEASON, week=week, slot_number=i + 1, user_card_id=uc.id))
    s.commit()
def marker(k, week):
    s.add(FantasyRoster(user_id=users[k].id, season=SEASON, last_equipped_set_week=week)); s.commit()

for k in 'ABCD': equip(k, 1)
marker('A', 2)
marker('C', 3)
equip('D', 2); marker('D', 2)

def weekRows(k, week):
    return s.query(EquippedCard).filter_by(user_id=users[k].id, season=SEASON, week=week).count()

c = TestClient(M.app)
try:
    print("1. Bot: /api/bot/lineup and the lineup reminder (before the lock)")
    lineup = {k: c.get('/api/bot/lineup', params={'discordId': DIDS[k]}).json()['data'] for k in 'ABCD'}
    expect("A (emptied week 2) shows no lineup", lineup['A']['slots'] == [])
    expect("B (no marker) shows week 1 carried", len(lineup['B']['slots']) == ROSTER_MIN_PLAYERS)
    expect("C (emptied this week) shows no lineup", lineup['C']['slots'] == [])
    expect("D shows its week 2 lineup", len(lineup['D']['slots']) == ROSTER_MIN_PLAYERS)
    missing = [d for d in c.get('/api/bot/unsubmitted').json()['data']['rosterMissing'] if d in DIDS.values()]
    expect(f"reminder goes to A and C only ({sorted(missing)})", sorted(missing) == sorted([DIDS['A'], DIDS['C']]))

    print("2. Site: GET /api/cards/equipped")
    M._areGamesStarted = lambda: False
    for k, want in (('A', 0), ('C', 0)):
        M.app.dependency_overrides[M._getCurrentUser] = lambda u=users[k]: u
        r = c.get('/api/cards/equipped')
        expect(f"{k}: {r.status_code}, nothing carried into week {WEEK}", r.status_code == 200 and weekRows(k, WEEK) == want)
    M.app.dependency_overrides.pop(M._getCurrentUser, None)
    s.expire_all()

    print("3. The game-start lock")
    SeasonManager._carryForwardEquippedCards(object(), s, EquippedCardRepository(s), SEASON, WEEK)
    s.commit()
    expect("A: not carried (emptied week 2)", weekRows('A', WEEK) == 0)
    expect("B: week 1 carried", weekRows('B', WEEK) == ROSTER_MIN_PLAYERS)
    expect("C: not carried (emptied this week)", weekRows('C', WEEK) == 0)
    expect("D: week 2 carried", weekRows('D', WEEK) == ROSTER_MIN_PLAYERS)
finally:
    s.rollback()
    s.query(EquippedCard).filter(EquippedCard.season == SEASON).delete(synchronize_session=False)
    s.query(FantasyRoster).filter(FantasyRoster.season == SEASON).delete(synchronize_session=False)
    for cs in cards.values():
        for uc in cs: s.delete(uc)
    s.flush(); s.delete(tmpl)
    for uid, did, dm in saved:
        u = s.get(User, uid); u.discord_id = did; u.discord_dm_reminders = dm
    s.commit(); s.close()

print(f"\n{'ALL PASSED' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)
