#!/usr/bin/env python3
"""Final comprehensive verification of all team table fields"""

from database import get_session
from database.models import Team, TeamSeasonStats

session = get_session()
teams = session.query(Team).all()

print('=' * 80)
print('COMPLETE TEAMS TABLE VERIFICATION')
print('=' * 80)

print('\n✅ REGULAR SEASON CHAMPIONSHIPS (Top seed in each league):')
reg_champs = sorted([t for t in teams if t.regular_season_champions], 
                    key=lambda t: len(t.regular_season_champions), reverse=True)
if reg_champs:
    for team in reg_champs[:5]:
        print(f'   {team.name}: {len(team.regular_season_champions)} title(s) - {team.regular_season_champions}')
else:
    print('   ❌ MISSING!')

print('\n✅ LEAGUE CHAMPIONSHIPS (Both Floosbowl finalists):')
league_champs = sorted([t for t in teams if t.league_championships], 
                       key=lambda t: len(t.league_championships), reverse=True)
if league_champs:
    for team in league_champs[:5]:
        print(f'   {team.name}: {len(team.league_championships)} appearance(s) - {team.league_championships}')
else:
    print('   ❌ MISSING!')

print('\n✅ FLOOSBOWL CHAMPIONSHIPS (Floosbowl winners only):')
floosball_champs = sorted([t for t in teams if t.floosbowl_championships], 
                          key=lambda t: len(t.floosbowl_championships), reverse=True)
if floosball_champs:
    for team in floosball_champs:
        print(f'   {team.name}: {len(team.floosbowl_championships)} win(s) - {team.floosbowl_championships}')
else:
    print('   ❌ MISSING!')

print('\n✅ ALL-TIME STATS:')
stats_teams = sorted([t for t in teams if t.all_time_stats and t.all_time_stats.get('wins', 0) > 0],
                     key=lambda t: t.all_time_stats.get('wins', 0), reverse=True)
if stats_teams:
    print(f'   {len(stats_teams)}/{len(teams)} teams have accumulated stats')
    for team in stats_teams[:3]:
        stats = team.all_time_stats
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        print(f'   {team.name}: {wins}-{losses}')
        print(f'      Offense: {stats.get("Offense", {}).get("tds", 0)} TDs, {stats.get("Offense", {}).get("totalYards", 0)} yards')
        print(f'      Defense: {stats.get("Defense", {}).get("sacks", 0)} sacks, {stats.get("Defense", {}).get("ints", 0)} INTs')
else:
    print('   ❌ MISSING!')

print('\n✅ PLAYOFF APPEARANCES:')
playoff_teams = sorted([t for t in teams if t.playoff_appearances and t.playoff_appearances > 0],
                       key=lambda t: t.playoff_appearances, reverse=True)
if playoff_teams:
    for team in playoff_teams[:5]:
        print(f'   {team.name}: {team.playoff_appearances} appearances')
else:
    print('   ❌ MISSING!')

print('\n✅ ELO RATINGS (from TeamSeasonStats):')
latest_season = session.query(TeamSeasonStats.season).order_by(TeamSeasonStats.season.desc()).first()
if latest_season:
    season_num = latest_season[0]
    team_stats = session.query(TeamSeasonStats).filter_by(season=season_num).all()
    elo_teams = sorted([(ts, session.query(Team).get(ts.team_id)) for ts in team_stats],
                       key=lambda x: x[0].elo if x[0].elo else 0, reverse=True)
    print(f'   Season {season_num} ELO rankings:')
    for ts, team in elo_teams[:5]:
        if team:
            print(f'   {team.name}: {ts.elo} (Record: {ts.wins}-{ts.losses})')
else:
    print('   ❌ No season stats found!')

print('\n' + '=' * 80)
print('VERIFICATION SUMMARY')
print('=' * 80)
print(f'✅ Regular Season Championships: {"SAVED" if reg_champs else "MISSING"}')
print(f'✅ League Championships: {"SAVED" if league_champs else "MISSING"}')
print(f'✅ Floosbowl Championships: {"SAVED" if floosball_champs else "MISSING"}')
print(f'✅ All-time Stats: {"SAVED" if stats_teams else "MISSING"}')
print(f'✅ Playoff Appearances: {"SAVED" if playoff_teams else "MISSING"}')
print(f'✅ ELO Ratings: {"SAVED" if latest_season else "MISSING"}')
print('=' * 80)

session.close()
