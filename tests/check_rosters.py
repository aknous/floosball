"""Check if team rosters are populated in the database"""

from database import get_session
from database.models import Team, Player

def check_rosters():
    session = get_session()
    
    try:
        # Get all teams
        teams = session.query(Team).all()
        
        print(f"\nChecking rosters for {len(teams)} teams:\n")
        
        for team in teams:
            # Count players on this team
            players = session.query(Player).filter(Player.team_id == team.id).all()
            
            print(f"{team.name}: {len(players)} players")
            if players:
                # Show first 3 players
                for i, player in enumerate(players[:3]):
                    pos_names = ['QB', 'RB', 'WR', 'OL', 'TE', 'K']
                    pos = pos_names[player.position] if player.position < len(pos_names) else f'Pos{player.position}'
                    print(f"  - {player.name} ({pos})")
                if len(players) > 3:
                    print(f"  ... and {len(players) - 3} more")
            print()
    
    finally:
        session.close()

if __name__ == '__main__':
    check_rosters()
