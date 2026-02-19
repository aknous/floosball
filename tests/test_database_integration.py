"""
Test script to demonstrate database integration with Floosball.

This shows how to:
1. Generate players and teams
2. Save them to database
3. Load them back from database
4. Clear database for fresh start
"""

from database import get_session, clear_database, get_db_stats, init_db
from database.models import Player, Team, League, PlayerAttributes, UnusedName
from database.repositories import PlayerRepository, TeamRepository, LeagueRepository, UnusedNameRepository
import floosball_player as FloosPlayer


def test_database_workflow():
    """Demonstrate complete database workflow."""
    
    print("=== Floosball Database Integration Test ===\n")
    
    # Step 1: Initialize database
    print("Step 1: Initialize database")
    init_db()
    print("✓ Database initialized\n")
    
    # Step 2: Clear any existing data (for fresh start)
    print("Step 2: Clear existing data")
    clear_database()
    print("✓ Database cleared\n")
    
    # Step 3: Create session and repositories
    print("Step 3: Create database session")
    session = get_session()
    league_repo = LeagueRepository(session)
    team_repo = TeamRepository(session)
    player_repo = PlayerRepository(session)
    name_repo = UnusedNameRepository(session)
    print("✓ Repositories created\n")
    
    try:
        # Step 4: Create leagues
        print("Step 4: Create leagues")
        league1 = League(name="League 1")
        league2 = League(name="League 2")
        league_repo.save(league1)
        league_repo.save(league2)
        session.commit()
        print(f"✓ Created {len(league_repo.get_all())} leagues\n")
        
        # Step 5: Create teams
        print("Step 5: Create teams")
        teams = []
        for i in range(1, 5):  # Just 4 teams for demo
            team = Team(
                id=i,
                name=f"Team {i}",
                city=f"City {i}",
                abbr=f"T{i}",
                color="blue",
                offense_rating=80 + i,
                defense_rating=80 - i,
                overall_rating=80,
                league_id=league1.id if i <= 2 else league2.id
            )
            teams.append(team)
        team_repo.save_batch(teams)
        session.commit()
        print(f"✓ Created {len(teams)} teams\n")
        
        # Step 6: Create players using existing Player classes
        print("Step 6: Create players")
        
        # Generate a few players using the existing FloosPlayer classes
        # This shows how to convert game Player objects to database Player objects
        game_players = []
        for i in range(1, 11):  # 10 players for demo
            # Create a game player using existing class
            if i % 5 == 1:
                game_player = FloosPlayer.PlayerQB(75 + i)
            elif i % 5 == 2:
                game_player = FloosPlayer.PlayerRB(75 + i)
            elif i % 5 == 3:
                game_player = FloosPlayer.PlayerWR(75 + i)
            elif i % 5 == 4:
                game_player = FloosPlayer.PlayerTE(75 + i)
            else:
                game_player = FloosPlayer.PlayerK(75 + i)
            
            game_player.name = f"Player {i}"
            game_player.id = i
            game_player.currentNumber = 10 + i
            game_player.team = teams[i % len(teams)].id  # Assign to teams
            
            game_players.append(game_player)
            
            # Convert to database Player
            db_player = Player(
                id=game_player.id,
                name=game_player.name,
                current_number=game_player.currentNumber,
                team_id=game_player.team,
                position=game_player.position.value if hasattr(game_player.position, 'value') else 1,
                player_rating=game_player.playerRating,
                seasons_played=0
            )
            player_repo.save(db_player)
            
            # Also save attributes
            db_attrs = PlayerAttributes(
                player_id=game_player.id,
                overall_rating=game_player.attributes.overallRating,
                speed=game_player.attributes.speed,
                hands=game_player.attributes.hands,
                agility=game_player.attributes.agility,
                power=game_player.attributes.power,
                arm_strength=game_player.attributes.armStrength,
                accuracy=game_player.attributes.accuracy,
                leg_strength=game_player.attributes.legStrength,
                skill_rating=game_player.attributes.skillRating,
                potential_speed=game_player.attributes.potentialSpeed,
                potential_hands=game_player.attributes.potentialHands,
                potential_agility=game_player.attributes.potentialAgility,
                potential_power=game_player.attributes.potentialPower,
                potential_arm_strength=game_player.attributes.potentialArmStrength,
                potential_accuracy=game_player.attributes.potentialAccuracy,
                potential_leg_strength=game_player.attributes.potentialLegStrength,
                potential_skill_rating=game_player.attributes.potentialSkillRating,
                route_running=game_player.attributes.routeRunning,
                vision=game_player.attributes.vision,
                blocking=game_player.attributes.blocking,
                discipline=game_player.attributes.discipline,
                attitude=game_player.attributes.attitude,
                focus=game_player.attributes.focus,
                instinct=game_player.attributes.instinct,
                creativity=game_player.attributes.creativity,
                resilience=game_player.attributes.resilience,
                clutch_factor=game_player.attributes.clutchFactor,
                pressure_handling=game_player.attributes.pressureHandling,
                longevity=game_player.attributes.longevity,
                play_making_ability=game_player.attributes.playMakingAbility,
                x_factor=game_player.attributes.xFactor,
                confidence_modifier=game_player.attributes.confidenceModifier,
                determination_modifier=game_player.attributes.determinationModifier,
                luck_modifier=game_player.attributes.luckModifier,
            )
            session.add(db_attrs)
        
        session.commit()
        print(f"✓ Created {len(game_players)} players with attributes\n")
        
        # Step 7: Add some unused names
        print("Step 7: Add unused names")
        unused_names = ["John Smith", "Jane Doe", "Bob Johnson", "Alice Williams"]
        name_repo.add_names_batch(unused_names)
        session.commit()
        print(f"✓ Added {len(unused_names)} unused names\n")
        
        # Step 8: Verify data was saved
        print("Step 8: Verify data in database")
        stats = get_db_stats()
        print("Database contents:")
        for table, count in stats.items():
            if count > 0:
                print(f"  {table}: {count}")
        print()
        
        # Step 9: Load data back (demonstrate reading)
        print("Step 9: Load data from database")
        
        # Load all players
        all_players = player_repo.get_all()
        print(f"  Loaded {len(all_players)} players")
        
        # Load players by team
        team1_players = player_repo.get_by_team(1)
        print(f"  Team 1 has {len(team1_players)} players")
        
        # Load teams with their leagues
        all_teams = team_repo.get_all()
        for team in all_teams[:2]:  # Show first 2
            print(f"  {team.name} (League: {team.league.name if team.league else 'None'})")
        print()
        
        # Step 10: Demonstrate clear for fresh start
        print("Step 10: Demonstrate fresh start capability")
        print("  Current player count:", player_repo.count())
        clear_database()
        print("  After clear:", player_repo.count())
        print("✓ Database can be cleared for fresh start\n")
        
        print("=== Test Complete! ===")
        print("\nSummary:")
        print("✓ Database initialization works")
        print("✓ Can save leagues, teams, players, attributes")
        print("✓ Can load data back with relationships")
        print("✓ Can clear database for fresh start")
        print("\nNext step: Integrate with PlayerManager/TeamManager")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    test_database_workflow()
