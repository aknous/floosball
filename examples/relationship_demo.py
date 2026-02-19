"""
Demo showing how SQLAlchemy relationships work under the hood.
The database only stores IDs, but SQLAlchemy makes it feel like you have objects.
"""

from database.connection import get_session
from database.models import Player, Team, League
import logging

# Enable SQLAlchemy query logging to see what SQL is executed
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

print("=" * 80)
print("RELATIONSHIP DEMO: How SQLAlchemy turns IDs into objects")
print("=" * 80)

session = get_session()

# Example 1: Lazy Loading (separate queries)
print("\n" + "=" * 80)
print("EXAMPLE 1: LAZY LOADING (default behavior)")
print("=" * 80)
print("\nCode: player = session.query(Player).first()")
player = session.query(Player).first()
print(f"\nResult: Got player '{player.name}'")
print(f"In database, player.team_id = {player.team_id} (just an integer!)")

print("\nCode: team = player.team")
print("Watch the SQL query that SQLAlchemy automatically runs:")
team = player.team  # This triggers a query!
print(f"\nResult: Got team object '{team.name}'")
print(f"In database, team.league_id = {team.league_id} (just an integer!)")

print("\nCode: league = team.league")
print("Watch another automatic query:")
league = team.league  # This triggers another query!
print(f"\nResult: Got league object '{league.name}'")

print("\n" + "-" * 80)
print("Summary: Lazy loading did 3 separate queries (1 for player, 1 for team, 1 for league)")
print("-" * 80)

# Example 2: Eager Loading (one optimized query)
print("\n" + "=" * 80)
print("EXAMPLE 2: EAGER LOADING (optimized for APIs)")
print("=" * 80)

from sqlalchemy.orm import joinedload

print("\nCode: player = session.query(Player).options(")
print("    joinedload(Player.team).joinedload(Team.league)")
print(").first()")
print("\nWatch: SQLAlchemy does ONE query with JOINs:")

# Close and reopen session to clear cache
session.close()
session = get_session()

player = session.query(Player).options(
    joinedload(Player.team).joinedload(Team.league)
).first()

print(f"\nResult: Got player '{player.name}'")
print("\nCode: team = player.team (NO additional query!)")
team = player.team
print(f"Result: Got team '{team.name}' (already loaded)")

print("\nCode: league = team.league (NO additional query!)")
league = team.league
print(f"Result: Got league '{league.name}' (already loaded)")

print("\n" + "-" * 80)
print("Summary: Eager loading did 1 query total - much better for APIs!")
print("-" * 80)

# Example 3: Show raw SQL queries
print("\n" + "=" * 80)
print("EXAMPLE 3: What the actual SQL looks like")
print("=" * 80)

print("\nLazy loading equivalent SQL:")
print("""
-- First query (get player):
SELECT * FROM players WHERE id = 1;

-- Second query (get team via team_id):
SELECT * FROM teams WHERE id = 14;

-- Third query (get league via league_id):
SELECT * FROM leagues WHERE id = 2;
""")

print("Eager loading equivalent SQL:")
print("""
-- Single query with JOINs:
SELECT 
    players.*, 
    teams.*, 
    leagues.*
FROM players
LEFT JOIN teams ON players.team_id = teams.id
LEFT JOIN leagues ON teams.league_id = leagues.id
WHERE players.id = 1;
""")

# Example 4: Reverse relationship
print("\n" + "=" * 80)
print("EXAMPLE 4: REVERSE RELATIONSHIP (team.players)")
print("=" * 80)

session.close()
session = get_session()

print("\nCode: team = session.query(Team).first()")
team = session.query(Team).first()
print(f"Result: Got team '{team.name}'")

print("\nCode: players = team.players")
print("Watch: SQLAlchemy queries all players with this team_id:")
players = team.players  # This triggers: SELECT * FROM players WHERE team_id = ?
print(f"Result: Got {len(players)} players")
for p in players:
    print(f"  - {p.name}")

print("\n" + "=" * 80)
print("KEY TAKEAWAYS:")
print("=" * 80)
print("""
1. Database stores only IDs (team_id, league_id) - foreign keys
2. SQLAlchemy relationship definitions tell it how to JOIN tables
3. When you access player.team, SQLAlchemy runs: SELECT * FROM teams WHERE id = player.team_id
4. When you access team.players, SQLAlchemy runs: SELECT * FROM players WHERE team_id = team.id
5. Use joinedload() for APIs to avoid multiple queries (N+1 problem)
6. The relationships make code clean while SQLAlchemy handles the SQL

Bottom line: You write Python like you have objects, SQLAlchemy translates to SQL!
""")

session.close()
