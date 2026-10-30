"""Clinch announcements and bonuses follow the real seeding, once a season (2026-10-29).

1. ONE DEFINITION OF CLINCHED. `seasonManager.checkForClinches` delegated to the legacy
   `leagueManager.checkPlayoffClinching`, which took the top half BY RECORD as the field
   and compared raw wins with the club 9th by record. A division winner takes a top-four
   seed at any record, so prod season 12 week 25 announced the Broads (8th by record) as
   clinched, and paid their fans, while the 12-15 Sand Dollars led their division; the
   Broads were 9th after week 27. It also set `team.clinchedPlayoffs`, which the engine
   reads (a clinched club with a loose room coasts from week 24). The flags now come from
   `standings_view.clinchStatus`, which the board and the news feed already used.
2. ONCE A SEASON, RESTART OR NOT. The markers that said a clinch was announced or paid
   lived in memory, so every deploy announced and paid every clinch again (the Raccoons'
   berth was published in weeks 21, 23 and 27). The feed and the payout table are checked
   before either happens.

Run: .venv/bin/python test_clinch_announcements.py   (exits non-zero on any failure)
"""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, LeagueNewsItem, CurrencyTransaction, User
from managers.seasonManager import SeasonManager

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class T:
    """⚠️ standings_view reads `seasonTeamStats`, never bare .wins."""
    def __init__(self, tid, name, w, l, division):
        self.id = tid; self.name = name; self.city = 'City'; self.abbr = name[:3].upper()
        self.division = division
        self.clinchedPlayoffs = False; self.clinchedTopSeed = False; self.eliminated = False
        self.inSeasonPressure = 1.0
        self.seasonTeamStats = {
            'wins': w, 'losses': l, 'ties': 0, 'winPerc': w / max(1, w + l), 'scoreDiff': 0,
            'divWins': 0, 'divLosses': 0, 'divTies': 0, 'lgWins': 0, 'lgLosses': 0, 'lgTies': 0,
            'Offense': {'pts': 0}, 'streak': 0}


def league(records):
    """16 clubs, four divisions of four, records (wins, losses) after 25 of 28 games."""
    divs = ['Twill', 'Denim', 'Herringbone', 'Tweed']
    return [T(i + 1, n, w, l, divs[i // 4]) for i, (n, w, l) in enumerate(records)]


# Prod Corduroy League after week 25, reduced to its shape: the 8th-best record (the
# Broads, 14-11) and three clubs at 10-15, one of which (the Sand Dollars) leads the
# Tweed division and so holds seed 4.
records = [
    ('Strangers', 20, 5), ('Rocks', 18, 7), ('Broads', 14, 11), ('Monuments', 9, 16),
    ('Normals', 16, 9), ('Slippers', 15, 10), ('Caddies', 14, 11), ('Beans', 8, 17),
    ('Waffles', 16, 9), ('Sodas', 15, 10), ('Pops', 10, 15), ('Melons', 7, 18),
    ('Sand Dollars', 10, 15), ('Residents', 10, 15), ('Oysters', 9, 16), ('Dry Heat', 5, 20),
]
teams = league(records)
byName = {t.name: t for t in teams}


def manager(teams, session=None):
    """Just enough of a SeasonManager for the clinch methods."""
    m = SeasonManager.__new__(SeasonManager)
    week = {'games': [types.SimpleNamespace(isRegularSeasonGame=True)]}
    m.currentSeason = types.SimpleNamespace(
        seasonNumber=12, currentWeek=25, leagueHighlights=[], schedule=[week] * 28)
    m.leagueManager = types.SimpleNamespace(
        leagues=[types.SimpleNamespace(name='Corduroy League', teamList=teams)])
    m.db_session = session
    return m


print("\n-- 1. clinched means seeded in the worst case, not top half by record --")
m = manager(teams)
events = m.checkForClinches()
clinched = {t.name for t in teams if t.clinchedPlayoffs}
expect(f"the Broads, 8th by record with a 10-15 division leader below them, have not clinched "
       f"(clinched: {sorted(clinched)})", not byName['Broads'].clinchedPlayoffs)
expect("nor have the Caddies", not byName['Caddies'].clinchedPlayoffs)
expect("the Strangers, out of reach, have clinched", byName['Strangers'].clinchedPlayoffs)
expect("every bonus event is for a club that has clinched",
       all(byName[n].clinchedPlayoffs for n in
           {t.name for t in teams for e in events if e['teamId'] == t.id and e['type'] == 'clinch_playoff'}))
expect("the Sand Dollars, leading their division at 10-15, are not eliminated",
       not byName['Sand Dollars'].eliminated)
again = m.checkForClinches()
expect(f"a second pass the same week raises no new bonus events ({len(again)})", again == [])


print("\n-- 2. a restart does not announce a clinch again --")
engine = create_engine('sqlite://')
Base.metadata.create_all(engine)
session = sessionmaker(bind=engine)()
m = manager(league(records), session)
m.serviceContainer = types.SimpleNamespace(getService=lambda name: None)
m._publishClinchNews(25)
first = session.query(LeagueNewsItem).count()
expect(f"the first week end publishes the clinches ({first} lines)", first > 0)
# A restart: fresh team objects, no in-memory markers.
m2 = manager(league(records), session)
m2.serviceContainer = m.serviceContainer
m2._publishClinchNews(25)
second = session.query(LeagueNewsItem).count()
expect(f"after a restart nothing is published twice ({first} -> {second})", second == first)
expect("and nothing is pushed to the game-board highlights again",
       m2.currentSeason.leagueHighlights == [])


print("\n-- 3. a fan is paid each milestone once a season --")
import database.connection as dbc
import managers.supporterManager as sup
fan = User(id=7, clerk_id='c7', email='f@x', username='fan', favorite_team_id=byName['Strangers'].id,
           is_active=True)
session.add(fan); session.commit()
origGet, origEarning = dbc.get_session, sup.isEarning
dbc.get_session = lambda: sessionmaker(bind=engine)()
sup.isEarning = lambda u: True
try:
    paid1 = m._awardFavoriteTeamBonus(byName['Strangers'].id, 50, 'team_clinch_playoff',
                                      description='Favorite team clinched playoffs', season=12)
    paid2 = m2._awardFavoriteTeamBonus(byName['Strangers'].id, 50, 'team_clinch_playoff',
                                       description='Favorite team clinched playoffs', season=12)
    paid3 = m2._awardFavoriteTeamBonus(byName['Strangers'].id, 50, 'team_clinch_playoff',
                                       description='Favorite team clinched playoffs', season=13)
finally:
    dbc.get_session, sup.isEarning = origGet, origEarning
rows = sessionmaker(bind=engine)().query(CurrencyTransaction).filter_by(
    user_id=7, transaction_type='team_clinch_playoff').count()
expect(f"paid on the clinch ({paid1})", paid1 == 1)
expect(f"not paid again after a restart ({paid2})", paid2 == 0)
expect(f"paid again next season ({paid3}; {rows} payouts in all)", paid3 == 1 and rows == 2)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("all passed")
