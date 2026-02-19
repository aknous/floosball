"""
Example API data extraction using SQLAlchemy relationships.
Shows how to efficiently build API responses from database models.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from database.models import Team, Player, League, PlayerAttributes
from database.connection import get_session


def get_team_with_roster(team_id: int) -> Optional[Dict[str, Any]]:
    """
    Get team data with full roster for API response.
    Uses relationships to avoid manual joins.
    """
    session = get_session()
    
    # Eager load players and their attributes in one query
    team = session.query(Team).options(
        joinedload(Team.league),  # Load league in same query
        selectinload(Team.players).joinedload(Player.attributes)  # Load players and their attributes
    ).filter_by(id=team_id).first()
    
    if not team:
        return None
    
    return {
        'id': team.id,
        'name': team.name,
        'city': team.city,
        'abbr': team.abbr,
        'color': team.color,
        'ratings': {
            'offense': team.offense_rating,
            'defense': team.defense_rating,
            'overall': team.overall_rating,
        },
        'league': {
            'id': team.league.id,
            'name': team.league.name
        } if team.league else None,
        'roster': [
            {
                'id': player.id,
                'name': player.name,
                'number': player.current_number,
                'position': player.position,
                'rating': player.player_rating,
                'attributes': {
                    'speed': player.attributes.speed if player.attributes else None,
                    'hands': player.attributes.hands if player.attributes else None,
                    'power': player.attributes.power if player.attributes else None,
                } if player.attributes else None
            }
            for player in team.players  # Using the relationship!
        ],
        'stats': {
            'championships': team.league_championships or [],
            'playoff_appearances': team.playoff_appearances or [],
        }
    }


def get_league_with_teams(league_id: int) -> Optional[Dict[str, Any]]:
    """
    Get league data with all teams for API response.
    Uses relationships for clean data access.
    """
    session = get_session()
    
    # Eager load all teams in the league
    league = session.query(League).options(
        selectinload(League.teams)
    ).filter_by(id=league_id).first()
    
    if not league:
        return None
    
    return {
        'id': league.id,
        'name': league.name,
        'teams': [
            {
                'id': team.id,
                'name': team.name,
                'city': team.city,
                'abbr': team.abbr,
                'ratings': {
                    'offense': team.offense_rating,
                    'defense': team.defense_rating,
                    'overall': team.overall_rating,
                }
            }
            for team in league.teams  # Using the relationship!
        ]
    }


def get_player_with_team(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Get player data with team info for API response.
    Uses relationships to get related data.
    """
    session = get_session()
    
    # Eager load team and attributes
    player = session.query(Player).options(
        joinedload(Player.team).joinedload(Team.league),
        joinedload(Player.attributes),
        selectinload(Player.career_stats)
    ).filter_by(id=player_id).first()
    
    if not player:
        return None
    
    return {
        'id': player.id,
        'name': player.name,
        'number': player.current_number,
        'position': player.position,
        'rating': player.player_rating,
        'team': {
            'id': player.team.id,
            'name': player.team.name,
            'city': player.team.city,
            'abbr': player.team.abbr,
            'league': player.team.league.name if player.team.league else None
        } if player.team else None,  # Using the relationship!
        'attributes': {
            'speed': player.attributes.speed,
            'hands': player.attributes.hands,
            'power': player.attributes.power,
            'vision': player.attributes.vision,
            'blocking': player.attributes.blocking,
            'route_running': player.attributes.route_running,
            'overall_rating': player.attributes.overall_rating,
        } if player.attributes else None,
        'career_stats': [
            {
                'season': stat.season,
                'games_played': stat.games_played,
                'fantasy_points': stat.fantasy_points,
                'passing': stat.passing_stats,
                'rushing': stat.rushing_stats,
                'receiving': stat.receiving_stats,
            }
            for stat in player.career_stats  # Using the relationship!
        ]
    }


def get_all_teams_with_player_counts() -> List[Dict[str, Any]]:
    """
    Get all teams with their player counts.
    Shows how to use hybrid properties or computed values.
    """
    session = get_session()
    
    # Load all teams with their players
    teams = session.query(Team).options(
        selectinload(Team.players),
        joinedload(Team.league)
    ).all()
    
    return [
        {
            'id': team.id,
            'name': team.name,
            'city': team.city,
            'abbr': team.abbr,
            'league': team.league.name if team.league else None,
            'player_count': len(team.players),  # Using the relationship!
            'ratings': {
                'offense': team.offense_rating,
                'defense': team.defense_rating,
                'overall': team.overall_rating,
            }
        }
        for team in teams
    ]


def get_free_agents() -> List[Dict[str, Any]]:
    """
    Get all players without a team (free agents).
    """
    session = get_session()
    
    # Filter players where team_id is NULL
    free_agents = session.query(Player).options(
        joinedload(Player.attributes)
    ).filter(Player.team_id.is_(None)).all()
    
    return [
        {
            'id': player.id,
            'name': player.name,
            'position': player.position,
            'rating': player.player_rating,
            'free_agent_years': player.free_agent_years,
            'attributes': {
                'speed': player.attributes.speed if player.attributes else None,
                'hands': player.attributes.hands if player.attributes else None,
                'power': player.attributes.power if player.attributes else None,
            } if player.attributes else None
        }
        for player in free_agents
    ]


# Example usage:
if __name__ == "__main__":
    # Example 1: Get a team with full roster
    team_data = get_team_with_roster(team_id=1)
    if team_data:
        print(f"Team: {team_data['city']} {team_data['name']}")
        print(f"League: {team_data['league']['name'] if team_data['league'] else 'None'}")
        print(f"Roster size: {len(team_data['roster'])} players")
        print(f"First player: {team_data['roster'][0]['name']}" if team_data['roster'] else "No players")
    
    # Example 2: Get a league with all teams
    league_data = get_league_with_teams(league_id=1)
    if league_data:
        print(f"\nLeague: {league_data['name']}")
        print(f"Teams: {len(league_data['teams'])}")
        for team in league_data['teams'][:3]:
            print(f"  - {team['city']} {team['name']} ({team['abbr']})")
    
    # Example 3: Get a player with team info
    player_data = get_player_with_team(player_id=1)
    if player_data:
        print(f"\nPlayer: {player_data['name']}")
        if player_data['team']:
            print(f"Team: {player_data['team']['city']} {player_data['team']['name']}")
            print(f"League: {player_data['team']['league']}")
    
    # Example 4: Get all teams with counts
    teams_summary = get_all_teams_with_player_counts()
    print(f"\nAll teams ({len(teams_summary)}):")
    for team in teams_summary[:5]:
        print(f"  {team['city']} {team['name']}: {team['player_count']} players, League: {team['league']}")
    
    # Example 5: Get free agents
    free_agents = get_free_agents()
    print(f"\nFree agents: {len(free_agents)}")
