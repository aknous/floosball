"""Where a club finished: division placing recovered from the schedule, and playoff exit.

The season-history FINISH column used to collapse a whole postseason into one word
("Playoffs") and a whole non-playoff season into another ("Missed playoffs"). Both halves
are now derived from games — see season_finish.py.

⚠️ THE DIVISION IS RECOVERED, NOT READ. `teams.division` is the CURRENT alignment and
measurably is NOT the one a past season was played in: on a 20-season database, ZERO of
the 19 prior seasons' derived divisions match it, because `leagueManager` sorts
`league.teamList` in place by record at playoff selection and `_assignDivisions` slices
that same list the next season. So these tests pin the two properties that keep the
recovery honest: it uses the SCHEDULE, and it returns nothing rather than a guess.

Run: .venv/bin/python test_season_finish.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Team, Game, TeamSeasonStats
from season_finish import buildSeasonFinishes, divisionBlock

# Two divisions of four inside one league. Division A is 1-4, division B is 5-8.
DIV_A, DIV_B = [1, 2, 3, 4], [5, 6, 7, 8]
SEASON = 3

engine = create_engine("sqlite://", future=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, future=True)
s = Session()

for tid in DIV_A + DIV_B:
    # Every club's CURRENT division says "Twill" except team 8, which is the realignment
    # case: one member having moved must cost division B its NAME, not produce a wrong one.
    s.add(Team(id=tid, name=f"T{tid}", city="C", abbr=f"T{tid}", color="#123456",
               offense_rating=80, defense_rating=80, overall_rating=80,
               division="Twill" if tid != 8 else "Gingham", league_id=1))

gameId = 0
def play(season, home, away, hs, xs, week=1, playoff=False, rnd=None):
    global gameId
    gameId += 1
    s.add(Game(id=gameId, season=season, week=week, home_team_id=home, away_team_id=away,
               home_score=hs, away_score=xs, status='final',
               is_playoff=playoff, playoff_round=rnd,
               winner_team_id=home if hs > xs else away))

# Division rivals meet FOUR times, everyone else ONCE — the signature the recovery reads.
for div in (DIV_A, DIV_B):
    for i, home in enumerate(div):
        for away in div[i + 1:]:
            for _ in range(2):
                play(SEASON, home, away, 20, 10)
                play(SEASON, away, home, 20, 10)
for home in DIV_A:
    for away in DIV_B:
        play(SEASON, home, away, 20, 10)

# Distinct win percentages so the ordering is unambiguous: team 3 wins division A,
# then 1, then 4, then 2.
WIN_PERC = {3: 0.80, 1: 0.70, 4: 0.60, 2: 0.50, 5: 0.75, 6: 0.65, 7: 0.55, 8: 0.45}
for tid, wp in WIN_PERC.items():
    s.add(TeamSeasonStats(team_id=tid, season=SEASON, wins=int(wp * 28),
                          losses=28 - int(wp * 28), win_percentage=wp,
                          score_differential=int(wp * 100), points=400, elo=1500))

# Team 1 reached the postseason and lost in round 2.
play(SEASON, 1, 5, 30, 10, week=29, playoff=True, rnd='1')
play(SEASON, 1, 6, 10, 30, week=30, playoff=True, rnd='2')
s.commit()

# ── the schedule gives up the division ────────────────────────────────────
from season_finish import _regularSeasonGames
games = _regularSeasonGames(s)
expect("a club's division is the opponents it faced most often",
       divisionBlock(games, SEASON, 1) == set(DIV_A))
expect("and it is recovered independently for the other division",
       divisionBlock(games, SEASON, 8) == set(DIV_B))

finishes = buildSeasonFinishes(s, 1)
row = finishes.get(SEASON, {})
expect("the placing is ranked inside that division, not the league",
       row.get('divisionRank') == 2 and row.get('divisionSize') == 4)
expect("the playoff exit says how far they got",
       row.get('playoffOutcome') == 'Lost in Round 2' and row.get('deepestRound') == 2)

# ── the name is only reported when it is actually knowable ────────────────
expect("a division whose members still agree keeps its name",
       row.get('divisionName') == 'Twill')
expect("a division whose members have since split reports NO name",
       buildSeasonFinishes(s, 8).get(SEASON, {}).get('divisionName') is None)

# ── it declines rather than guesses ───────────────────────────────────────
# A part-played season: everyone has met everyone once, so "faced most often" is the
# whole league. That is not a division and must not be reported as one.
PARTIAL = 9
teams = DIV_A + DIV_B
for i, home in enumerate(teams):
    for away in teams[i + 1:]:
        play(PARTIAL, home, away, 20, 10)
for tid, wp in WIN_PERC.items():
    s.add(TeamSeasonStats(team_id=tid, season=PARTIAL, wins=1, losses=1,
                          win_percentage=wp, score_differential=0, points=10, elo=1500))
s.commit()
partialGames = _regularSeasonGames(s)
expect("a part-played season yields no division rather than one huge one",
       divisionBlock(partialGames, PARTIAL, 1) is None)
expect("so that season reports no placing at all",
       'divisionRank' not in buildSeasonFinishes(s, 1).get(PARTIAL, {}))

# ── the live season is excluded, or a mid-season placing reads as a finish ─
expect("an excluded season is absent entirely",
       SEASON not in buildSeasonFinishes(s, 1, excludeSeasons={SEASON}))

s.close()

print("\nPASS — a season's placing and exit are recovered from the games, or not at all."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
