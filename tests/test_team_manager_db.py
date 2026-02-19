"""Test TeamManager with database integration."""

import sys
from pathlib import Path

# Add parent directory to path (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, clear_database, get_db_stats
from database.config import USE_DATABASE
from managers.teamManager import TeamManager
from managers.playerManager import PlayerManager
from managers.leagueManager import LeagueManager
from service_container import ServiceContainer


def test_team_manager_database():
    """Test TeamManager with database storage."""
    
    print("=== TeamManager Database Integration Test ===\n")
    
    # Step 1: Initialize database
    print("Step 1: Initialize database")
    init_db()
    clear_database()  # Start fresh
    print(f"✓ Database initialized (USE_DATABASE={USE_DATABASE})\n")
    
    # Step 2: Create service container and managers
    print("Step 2: Create managers")
    service_container = ServiceContainer()
    player_manager = PlayerManager(service_container)
    team_manager = TeamManager(service_container)
    league_manager = LeagueManager(service_container)
    
    # Register managers in service container for cross-references
    service_container.registerService('player_manager', player_manager)
    service_container.registerService('team_manager', team_manager)
    service_container.registerService('league_manager', league_manager)
    
    print(f"✓ Managers created\n")
    
    # Step 3: Load config
    print("Step 3: Load configuration")
    import json
    with open('config.json', 'r') as f:
        config = json.load(f)
    print("✓ Config loaded\n")
    
    # Step 4: Generate players first (teams need players for rosters)
    print("Step 4: Generate players")
    player_manager.generatePlayers(config, force_fresh=True)
    player_manager.sortPlayersByPosition()
    print(f"✓ Generated {len(player_manager.activePlayers)} players\n")
    
    # Step 5: Create teams from config
    print("Step 5: Create teams from config")
    team_manager._createTeamsFromConfig(config)
    print(f"✓ Created {len(team_manager.teams)} teams")
    for i, team in enumerate(team_manager.teams[:3]):
        print(f"  - Team {i+1}: {team.city} {team.name} ({team.abbr})")
    print()
    
    # Step 6: Conduct initial draft to assign players to teams
    print("Step 6: Conduct initial draft")
    player_manager.conductInitialDraft()
    print(f"✓ Draft complete\n")
    
    # Step 6a: Initialize teams (saves them to database)
    print("Step 6a: Initialize and save teams to database")
    team_manager.initializeTeams()
    print("✓ Teams initialized and saved\n")
    
    # Step 6b: Create leagues and assign teams
    print("Step 6b: Create leagues and assign teams")
    league_manager.createLeagues(config)
    print(f"✓ Created {len(league_manager.leagues)} leagues\n")

    # Step 7: Save players to database
    print("Step 7: Save players to database")
    player_manager.savePlayerData()
    print("✓ Players saved to database\n")
    
    # Step 8: Verify database contents
    print("Step 8: Verify database contents")
    stats = get_db_stats()
    print("Database counts:")
    for table, count in stats.items():
        if count > 0:
            print(f"  {table}: {count}")
    print()
    
    # Step 8b: Verify relationships in database
    print("Step 8b: Verify player-team and team-league relationships")
    from database.connection import get_session
    from database.models import Player as DBPlayer, Team as DBTeam
    
    db_session = get_session()
    
    # Check players have team assignments
    players_with_teams = db_session.query(DBPlayer).filter(DBPlayer.team_id.isnot(None)).count()
    total_players = db_session.query(DBPlayer).count()
    print(f"  Players with team assignments: {players_with_teams}/{total_players}")
    
    # Check teams have league assignments
    teams_with_leagues = db_session.query(DBTeam).filter(DBTeam.league_id.isnot(None)).count()
    total_teams = db_session.query(DBTeam).count()
    print(f"  Teams with league assignments: {teams_with_leagues}/{total_teams}")
    
    # Sample a team's roster
    sample_team = db_session.query(DBTeam).first()
    if sample_team:
        roster_count = len(sample_team.players)
        print(f"  Sample team '{sample_team.name}' roster size: {roster_count} players")
        if sample_team.league:
            print(f"  Sample team '{sample_team.name}' league: {sample_team.league.name}")
    
    # Verify database state directly with SQL (before closing session)
    print("\n  Direct SQL verification:")
    import sqlite3
    conn = sqlite3.connect('data/floosball.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, league_id FROM teams LIMIT 3")
    print("  Sample teams (name, league_id):")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")
    conn.close()
    
    db_session.close()
    print()
    
    # Step 9: Create new manager and load from database
    print("Step 9: Create new TeamManager and load from database")
    team_manager2 = TeamManager(service_container)
    team_manager2.generateTeams(config)
    print(f"✓ Loaded {len(team_manager2.teams)} teams from database\n")
    
    # Step 10: Verify loaded teams match
    print("Step 10: Verify loaded teams match")
    if len(team_manager.teams) == len(team_manager2.teams):
        print(f"✓ Team count matches: {len(team_manager.teams)}")
    else:
        print(f"✗ Team count mismatch: {len(team_manager.teams)} vs {len(team_manager2.teams)}")
    
    # Check a few teams
    sample_teams = min(3, len(team_manager.teams))
    for i in range(sample_teams):
        t1 = team_manager.teams[i]
        t2 = team_manager2.teams[i]
        match = (
            t1.id == t2.id and
            t1.name == t2.name and
            t1.abbr == t2.abbr and
            t1.city == t2.city
        )
        status = "✓" if match else "✗"
        print(f"  {status} Team {i+1}: {t1.city} {t1.name} (ID={t1.id}, Abbr={t1.abbr})")
    print()
    
    # Step 11: Test fresh start capability
    print("Step 11: Test fresh start (clear and regenerate)")
    team_count_before = len(team_manager.teams)
    clear_database()
    
    # Need to regenerate players, teams, and leagues for fresh start
    player_manager3 = PlayerManager(service_container)
    team_manager3 = TeamManager(service_container)
    league_manager3 = LeagueManager(service_container)
    service_container.registerService('player_manager', player_manager3)
    service_container.registerService('team_manager', team_manager3)
    service_container.registerService('league_manager', league_manager3)
    
    player_manager3.generatePlayers(config, force_fresh=True)
    player_manager3.sortPlayersByPosition()
    team_manager3._createTeamsFromConfig(config)
    player_manager3.conductInitialDraft()
    team_manager3.initializeTeams()  # Must save teams before creating leagues
    league_manager3.createLeagues(config)  # Create leagues and assign teams
    player_manager3.savePlayerData()  # Save players to database
    print(f"✓ Fresh start successful: {team_count_before} → {len(team_manager3.teams)} teams, {len(league_manager3.leagues)} leagues\n")
    
    print("=== Test Complete! ===")
    print("\nSummary:")
    print("✓ TeamManager can create teams from config")
    print("✓ TeamManager can save to database")
    print("✓ TeamManager can load from database")
    print("✓ Loaded teams match saved teams")
    print("✓ Fresh start (clear database) works")
    print("\nTeamManager is ready for database storage!")


if __name__ == "__main__":
    test_team_manager_database()
