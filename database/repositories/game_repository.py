"""
Game repository - handles game data persistence.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from database.models import Game, GamePlayerStats


class GameRepository:
    """Repository for game data access."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def save(self, game: Game) -> Game:
        """Save a game to the database."""
        self.session.add(game)
        return game
    
    def get_by_id(self, game_id: int) -> Optional[Game]:
        """Get a game by ID."""
        return self.session.query(Game).filter_by(id=game_id).first()
    
    def get_by_season(self, season: int) -> List[Game]:
        """Get all games for a season."""
        return self.session.query(Game).filter_by(season=season).order_by(Game.week).all()
    
    def get_by_season_and_week(self, season: int, week: int) -> List[Game]:
        """Get all games for a specific week in a season."""
        return self.session.query(Game).filter_by(season=season, week=week).all()
    
    def get_team_games(self, team_id: int, season: Optional[int] = None) -> List[Game]:
        """Get all games for a team, optionally filtered by season."""
        query = self.session.query(Game).filter(
            (Game.home_team_id == team_id) | (Game.away_team_id == team_id)
        )
        if season is not None:
            query = query.filter_by(season=season)
        return query.order_by(Game.season, Game.week).all()
    
    def get_playoff_games(self, season: int) -> List[Game]:
        """Get all playoff games for a season."""
        return self.session.query(Game).filter_by(
            season=season,
            is_playoff=True
        ).order_by(Game.week).all()
    
    def get_with_teams(self, game_id: int) -> Optional[Game]:
        """Get a game with home and away teams eagerly loaded."""
        return self.session.query(Game).options(
            joinedload(Game.home_team),
            joinedload(Game.away_team)
        ).filter_by(id=game_id).first()
    
    def get_with_player_stats(self, game_id: int) -> Optional[Game]:
        """Get a game with all player stats eagerly loaded."""
        return self.session.query(Game).options(
            joinedload(Game.home_team),
            joinedload(Game.away_team),
            joinedload(Game.player_stats)
        ).filter_by(id=game_id).first()
    
    def delete(self, game: Game) -> None:
        """Delete a game from the database."""
        self.session.delete(game)
    
    def count_by_season(self, season: int) -> int:
        """Count total games in a season."""
        return self.session.query(Game).filter_by(season=season).count()


class GamePlayerStatsRepository:
    """Repository for game player stats data access."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def save(self, stats: GamePlayerStats) -> GamePlayerStats:
        """Save player game stats to the database."""
        self.session.add(stats)
        return stats
    
    def get_by_game(self, game_id: int) -> List[GamePlayerStats]:
        """Get all player stats for a game."""
        return self.session.query(GamePlayerStats).filter_by(game_id=game_id).all()
    
    def get_by_player(self, player_id: int, season: Optional[int] = None) -> List[GamePlayerStats]:
        """Get all game stats for a player, optionally filtered by season."""
        query = self.session.query(GamePlayerStats).filter_by(player_id=player_id)
        if season is not None:
            query = query.join(Game).filter(Game.season == season)
        return query.all()
    
    def get_by_player_and_game(self, player_id: int, game_id: int) -> Optional[GamePlayerStats]:
        """Get a player's stats for a specific game."""
        return self.session.query(GamePlayerStats).filter_by(
            player_id=player_id,
            game_id=game_id
        ).first()
