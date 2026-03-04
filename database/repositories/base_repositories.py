"""Repository classes for database access."""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import (
    League,
    Team,
    Player,
    PlayerAttributes,
    PlayerCareerStats,
    TeamSeasonStats,
    Game,
    GamePlayerStats,
    Record,
    UnusedName,
)


class PlayerRepository:
    """Repository for player database operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, player_id: int) -> Optional[Player]:
        """Get player by ID."""
        return self.session.query(Player).filter_by(id=player_id).first()
    
    def get_all(self) -> List[Player]:
        """Get all players."""
        return self.session.query(Player).all()
    
    def get_by_team(self, team_id: int) -> List[Player]:
        """Get all players on a team."""
        return self.session.query(Player).filter_by(team_id=team_id).all()
    
    def get_by_position(self, position: int) -> List[Player]:
        """Get all players at a position."""
        return self.session.query(Player).filter_by(position=position).all()
    
    def get_free_agents(self) -> List[Player]:
        """Get all free agent players (no team)."""
        return self.session.query(Player).filter(Player.team_id.is_(None)).all()
    
    def save(self, player: Player) -> Player:
        """Save a player (insert or update)."""
        self.session.add(player)
        self.session.flush()
        return player
    
    def save_batch(self, players: List[Player]):
        """Save multiple players efficiently."""
        self.session.add_all(players)
        self.session.flush()
    
    def delete(self, player: Player):
        """Delete a player."""
        self.session.delete(player)
        self.session.flush()
    
    def count(self) -> int:
        """Count total players."""
        return self.session.query(func.count(Player.id)).scalar()


class TeamRepository:
    """Repository for team database operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, team_id: int) -> Optional[Team]:
        """Get team by ID."""
        return self.session.query(Team).filter_by(id=team_id).first()
    
    def get_all(self) -> List[Team]:
        """Get all teams."""
        return self.session.query(Team).all()
    
    def get_by_league(self, league_id: int) -> List[Team]:
        """Get all teams in a league."""
        return self.session.query(Team).filter_by(league_id=league_id).all()
    
    def get_by_abbr(self, abbr: str) -> Optional[Team]:
        """Get team by abbreviation."""
        return self.session.query(Team).filter_by(abbr=abbr).first()
    
    def save(self, team: Team) -> Team:
        """Save a team (insert or update)."""
        self.session.add(team)
        self.session.flush()
        return team
    
    def save_batch(self, teams: List[Team]):
        """Save multiple teams efficiently."""
        self.session.add_all(teams)
        self.session.flush()
    
    def delete(self, team: Team):
        """Delete a team."""
        self.session.delete(team)
        self.session.flush()
    
    def count(self) -> int:
        """Count total teams."""
        return self.session.query(func.count(Team.id)).scalar()


class LeagueRepository:
    """Repository for league database operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, league_id: int) -> Optional[League]:
        """Get league by ID."""
        return self.session.query(League).filter_by(id=league_id).first()
    
    def get_by_name(self, name: str) -> Optional[League]:
        """Get league by name."""
        return self.session.query(League).filter_by(name=name).first()
    
    def get_all(self) -> List[League]:
        """Get all leagues."""
        return self.session.query(League).all()
    
    def save(self, league: League) -> League:
        """Save a league (insert or update)."""
        self.session.add(league)
        self.session.flush()
        return league
    
    def delete(self, league: League):
        """Delete a league."""
        self.session.delete(league)
        self.session.flush()


class GameRepository:
    """Repository for game database operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, game_id: int) -> Optional[Game]:
        """Get game by ID."""
        return self.session.query(Game).filter_by(id=game_id).first()
    
    def get_by_season_week(self, season: int, week: int) -> List[Game]:
        """Get all games for a season/week."""
        return self.session.query(Game).filter_by(season=season, week=week).all()
    
    def get_by_team(self, team_id: int, season: Optional[int] = None) -> List[Game]:
        """Get all games for a team."""
        query = self.session.query(Game).filter(
            (Game.home_team_id == team_id) | (Game.away_team_id == team_id)
        )
        if season:
            query = query.filter_by(season=season)
        return query.all()
    
    def save(self, game: Game) -> Game:
        """Save a game."""
        self.session.add(game)
        self.session.flush()
        return game
    
    def save_player_stats(self, stats: GamePlayerStats):
        """Save player stats for a game."""
        self.session.add(stats)
        self.session.flush()

    def has_schedule(self, season: int) -> bool:
        """Return True if any game rows exist for this season (scheduled or final)."""
        return self.session.query(Game).filter_by(season=season).count() > 0

    def get_by_season_ordered(self, season: int) -> List[Game]:
        """Get all games for a season ordered by week then insertion order."""
        return (
            self.session.query(Game)
            .filter_by(season=season)
            .order_by(Game.week, Game.id)
            .all()
        )


class RecordRepository:
    """Repository for records database operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_type(self, record_type: str) -> Optional[Record]:
        """Get record by type."""
        return self.session.query(Record).filter_by(record_type=record_type).first()
    
    def get_player_records(self, player_id: int) -> List[Record]:
        """Get all records held by a player."""
        return self.session.query(Record).filter_by(player_id=player_id).all()
    
    def get_team_records(self, team_id: int) -> List[Record]:
        """Get all records held by a team."""
        return self.session.query(Record).filter_by(team_id=team_id).all()
    
    def save(self, record: Record) -> Record:
        """Save a record."""
        self.session.add(record)
        self.session.flush()
        return record
    
    def update_or_create(self, record_type: str, **kwargs) -> Record:
        """Update existing record or create new one."""
        record = self.get_by_type(record_type)
        if record:
            for key, value in kwargs.items():
                setattr(record, key, value)
        else:
            record = Record(record_type=record_type, **kwargs)
            self.session.add(record)
        self.session.flush()
        return record


class UnusedNameRepository:
    """Repository for unused names database operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_random_name(self) -> Optional[str]:
        """Get a random unused name."""
        name = self.session.query(UnusedName).first()
        if name:
            name_str = name.name
            self.session.delete(name)
            self.session.flush()
            return name_str
        return None
    
    def add_name(self, name: str):
        """Add a name to the unused pool."""
        unused = UnusedName(name=name)
        self.session.add(unused)
        self.session.flush()
    
    def add_names_batch(self, names: List[str]):
        """Add multiple names efficiently, skipping duplicates."""
        from sqlalchemy.dialects.sqlite import insert
        
        # Remove duplicates from input list first
        unique_names = list(dict.fromkeys(names))  # Preserves order, removes dupes
        
        # Use INSERT OR IGNORE for SQLite to skip duplicates
        for name in unique_names:
            stmt = insert(UnusedName).values(name=name).on_conflict_do_nothing(index_elements=['name'])
            self.session.execute(stmt)
        
        self.session.flush()
    
    def count(self) -> int:
        """Count unused names."""
        return self.session.query(func.count(UnusedName.id)).scalar()
