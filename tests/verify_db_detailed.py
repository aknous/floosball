#!/usr/bin/env python3
"""Detailed verification of all database migration features"""

from database import get_session
from database.models import Team, Game, Player, Season, TeamSeasonStats

session = get_session()

print("=" * 70)
print("COMPREHENSIVE DATABASE MIGRATION VERIFICATION")
print("=" * 70)

# Check Seasons table
seasons = session.query(Season).all()
print(f'\n✅ SEASONS TABLE: {len(seasons)} seasons saved')
if seasons:
    for season in seasons[:3]:
        print(f'   Season {season.season_number}: Week {season.current_week}, ' +
              f'Champion Team ID: {season.champion_team_id}, ' +
              f'Playoffs: {season.playoffs_started}')

# Check TeamSeasonStats (includes ELO)
team_stats = session.query(TeamSeasonStats).all()
print(f'\n✅ TEAM SEASON STATS TABLE: {len(team_stats)} team-season records')
if team_stats:
    # Group by season
    seasons_found = set()
    for ts in team_stats:
        seasons_found.add(ts.season)
    print(f'   Seasons with stats: {sorted(seasons_found)}')
    
    # Show sample with ELO
    sample = team_stats[0]
    sample_team = session.query(Team).get(sample.team_id)
    print(f'\n   📊 Sample Team Season Stats: {sample_team.name if sample_team else "Unknown"} Season {sample.season}')
    print(f'      ELO: {sample.elo} ⭐')
    print(f'      Record: {sample.wins}-{sample.losses} (Win%: {sample.win_percentage})')
    print(f'      Score Diff: {sample.score_differential}')
    print(f'      Made Playoffs: {sample.made_playoffs}')
    print(f'      League Champion: {sample.league_champion}')
    print(f'      Floosball Champion: {sample.floosball_champion}')
    print(f'      Top Seed: {sample.top_seed}')
    if sample.offense_stats:
        print(f'      Offensive TDs: {sample.offense_stats.get("tds", 0)}')
    if sample.defense_stats:
        print(f'      Sacks: {sample.defense_stats.get("sacks", 0)}')

# Check Teams - All-time stats and championships
teams = session.query(Team).all()
print(f'\n✅ TEAMS TABLE: {len(teams)} teams')

# Find teams with championships
champs = []
reg_champs = []
for team in teams:
    if team.league_championships:
        champs.append((team, len(team.league_championships)))
    if team.regular_season_champions:
        reg_champs.append((team, len(team.regular_season_champions)))

print(f'\n   🏆 LEAGUE CHAMPIONSHIPS:')
if champs:
    champs.sort(key=lambda x: x[1], reverse=True)
    for team, count in champs[:5]:
        print(f'      {team.name}: {count} championship(s)')
        print(f'         Seasons: {team.league_championships}')
else:
    print('      ❌ No league championships found!')

print(f'\n   🥇 REGULAR SEASON CHAMPIONSHIPS:')
if reg_champs:
    reg_champs.sort(key=lambda x: x[1], reverse=True)
    for team, count in reg_champs[:5]:
        print(f'      {team.name}: {count} title(s)')
        print(f'         Seasons: {team.regular_season_champions}')
else:
    print('      ❌ No regular season championships found!')

print(f'\n   📊 ALL-TIME STATS VERIFICATION:')
# Check if all-time stats are accumulating
stats_populated = []
for team in teams:
    if team.all_time_stats:
        wins = team.all_time_stats.get('wins', 0)
        losses = team.all_time_stats.get('losses', 0)
        total_games = wins + losses
        if total_games > 0:
            stats_populated.append((team, total_games, wins, losses))

if stats_populated:
    stats_populated.sort(key=lambda x: x[1], reverse=True)
    print(f'      Teams with accumulated stats: {len(stats_populated)}/{len(teams)}')
    for team, total, wins, losses in stats_populated[:3]:
        stats = team.all_time_stats
        print(f'      {team.name}: {wins}-{losses}')
        print(f'         Total Yards: {stats.get("Offense", {}).get("totalYards", 0)}')
        print(f'         Total TDs: {stats.get("Offense", {}).get("tds", 0)}')
        print(f'         Total Sacks: {stats.get("Defense", {}).get("sacks", 0)}')
else:
    print('      ❌ No teams have accumulated all-time stats!')

# Check Games
total_games = session.query(Game).count()
playoff_games = session.query(Game).filter_by(is_playoff=True).count()
print(f'\n✅ GAMES: {total_games} total ({playoff_games} playoff, {total_games - playoff_games} regular season)')

# Check if seasons are realistic
distinct_seasons = session.query(Game.season).distinct().count()
if distinct_seasons > 0:
    avg_games = total_games / distinct_seasons
    avg_playoff = playoff_games / distinct_seasons
    print(f'   Average games per season: {avg_games:.1f}')
    print(f'   Average playoff games per season: {avg_playoff:.1f}')

print(f'\n{"=" * 70}')
print("SUMMARY OF FIXES:")
print("=" * 70)
print(f'✅ Seasons table populated: {len(seasons) > 0}')
print(f'✅ TeamSeasonStats table populated (includes ELO): {len(team_stats) > 0}')
print(f'✅ All-time stats accumulating: {len(stats_populated) > 0}')
print(f'✅ League championships tracked: {len(champs) > 0}')
print(f'✅ Regular season championships tracked: {len(reg_champs) > 0}')
print(f'✅ Playoff games marked correctly: {playoff_games > 0}')
print("=" * 70)

session.close()
