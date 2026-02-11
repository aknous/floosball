"""SQLAlchemy models for Floosball database."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Float,
    Text,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class League(Base):
    """League table - represents a league (League 1, League 2)."""
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="league")

    def __repr__(self):
        return f"<League(id={self.id}, name='{self.name}')>"


class Team(Base):
    """Team table - represents a team."""
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100))
    abbr: Mapped[str] = mapped_column(String(10), unique=True)
    color: Mapped[str] = mapped_column(String(50))
    offense_rating: Mapped[int] = mapped_column(Integer)
    defense_rating: Mapped[int] = mapped_column(Integer)
    overall_rating: Mapped[int] = mapped_column(Integer)
    league_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leagues.id"))
    gm_score: Mapped[Optional[int]] = mapped_column(Integer)
    defense_tier: Mapped[Optional[int]] = mapped_column(Integer)
    defense_run_coverage_rating: Mapped[Optional[int]] = mapped_column(Integer)
    defense_pass_coverage_rating: Mapped[Optional[int]] = mapped_column(Integer)
    defense_pass_rush_rating: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    league: Mapped[Optional["League"]] = relationship("League", back_populates="teams")
    players: Mapped[list["Player"]] = relationship("Player", back_populates="team")
    season_stats: Mapped[list["TeamSeasonStats"]] = relationship("TeamSeasonStats", back_populates="team")
    home_games: Mapped[list["Game"]] = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games: Mapped[list["Game"]] = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}', abbr='{self.abbr}')>"


class Player(Base):
    """Player table - represents a player."""
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_number: Mapped[Optional[int]] = mapped_column(Integer)
    preferred_number: Mapped[Optional[int]] = mapped_column(Integer)
    tier: Mapped[Optional[str]] = mapped_column(String(20))
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    position: Mapped[Optional[int]] = mapped_column(Integer)  # Enum: QB=0, RB=1, WR=2, TE=3, K=4
    seasons_played: Mapped[int] = mapped_column(Integer, default=0)
    term: Mapped[Optional[int]] = mapped_column(Integer)
    term_remaining: Mapped[Optional[int]] = mapped_column(Integer)
    cap_hit: Mapped[Optional[int]] = mapped_column(Integer)
    player_rating: Mapped[Optional[int]] = mapped_column(Integer)
    free_agent_years: Mapped[Optional[int]] = mapped_column(Integer)
    service_time: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="players")
    attributes: Mapped[Optional["PlayerAttributes"]] = relationship("PlayerAttributes", back_populates="player", uselist=False)
    career_stats: Mapped[list["PlayerCareerStats"]] = relationship("PlayerCareerStats", back_populates="player")
    game_stats: Mapped[list["GamePlayerStats"]] = relationship("GamePlayerStats", back_populates="player")

    # Indexes
    __table_args__ = (
        Index("idx_players_team", "team_id"),
        Index("idx_players_position", "position"),
    )

    def __repr__(self):
        return f"<Player(id={self.id}, name='{self.name}', position={self.position})>"


class PlayerAttributes(Base):
    """Player attributes table - stores all player attribute ratings."""
    __tablename__ = "player_attributes"

    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), primary_key=True)
    
    # Core attributes
    overall_rating: Mapped[int] = mapped_column(Integer)
    speed: Mapped[int] = mapped_column(Integer)
    hands: Mapped[int] = mapped_column(Integer)
    agility: Mapped[int] = mapped_column(Integer)
    power: Mapped[int] = mapped_column(Integer)
    arm_strength: Mapped[int] = mapped_column(Integer)
    accuracy: Mapped[int] = mapped_column(Integer)
    leg_strength: Mapped[int] = mapped_column(Integer)
    skill_rating: Mapped[int] = mapped_column(Integer)
    
    # Potential attributes
    potential_speed: Mapped[int] = mapped_column(Integer)
    potential_hands: Mapped[int] = mapped_column(Integer)
    potential_agility: Mapped[int] = mapped_column(Integer)
    potential_power: Mapped[int] = mapped_column(Integer)
    potential_arm_strength: Mapped[int] = mapped_column(Integer)
    potential_accuracy: Mapped[int] = mapped_column(Integer)
    potential_leg_strength: Mapped[int] = mapped_column(Integer)
    potential_skill_rating: Mapped[int] = mapped_column(Integer)
    
    # Mental/skill attributes
    route_running: Mapped[int] = mapped_column(Integer)
    vision: Mapped[int] = mapped_column(Integer)
    blocking: Mapped[int] = mapped_column(Integer)
    discipline: Mapped[int] = mapped_column(Integer)
    attitude: Mapped[int] = mapped_column(Integer)
    focus: Mapped[int] = mapped_column(Integer)
    instinct: Mapped[int] = mapped_column(Integer)
    creativity: Mapped[int] = mapped_column(Integer)
    resilience: Mapped[int] = mapped_column(Integer)
    clutch_factor: Mapped[int] = mapped_column(Integer)
    pressure_handling: Mapped[int] = mapped_column(Integer)
    longevity: Mapped[int] = mapped_column(Integer)
    play_making_ability: Mapped[int] = mapped_column(Integer)
    x_factor: Mapped[int] = mapped_column(Integer)
    
    # Modifiers
    confidence_modifier: Mapped[int] = mapped_column(Integer)
    determination_modifier: Mapped[int] = mapped_column(Integer)
    luck_modifier: Mapped[int] = mapped_column(Integer)

    # Relationship
    player: Mapped["Player"] = relationship("Player", back_populates="attributes")

    def __repr__(self):
        return f"<PlayerAttributes(player_id={self.player_id}, overall={self.overall_rating})>"


class PlayerCareerStats(Base):
    """Player career stats table - stores stats by season."""
    __tablename__ = "player_career_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    fantasy_points: Mapped[int] = mapped_column(Integer, default=0)
    
    # Stats stored as JSON for flexibility
    passing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    rushing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    receiving_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    kicking_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    defense_stats: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationship
    player: Mapped["Player"] = relationship("Player", back_populates="career_stats")

    # Constraints
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season"),
        Index("idx_career_stats_player", "player_id"),
        Index("idx_career_stats_season", "season"),
    )

    def __repr__(self):
        return f"<PlayerCareerStats(player_id={self.player_id}, season={self.season})>"


class TeamSeasonStats(Base):
    """Team season stats table - stores team stats by season."""
    __tablename__ = "team_season_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Record
    elo: Mapped[Optional[int]] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_percentage: Mapped[Optional[float]] = mapped_column(Float)
    streak: Mapped[Optional[int]] = mapped_column(Integer)
    score_differential: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Achievements
    made_playoffs: Mapped[bool] = mapped_column(Boolean, default=False)
    league_champion: Mapped[bool] = mapped_column(Boolean, default=False)
    floosball_champion: Mapped[bool] = mapped_column(Boolean, default=False)
    top_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Stats stored as JSON
    offense_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    defense_stats: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationship
    team: Mapped["Team"] = relationship("Team", back_populates="season_stats")

    # Constraints
    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_team_season"),
        Index("idx_team_stats_team", "team_id"),
        Index("idx_team_stats_season", "season"),
    )

    def __repr__(self):
        return f"<TeamSeasonStats(team_id={self.team_id}, season={self.season}, W-L={self.wins}-{self.losses})>"


class Game(Base):
    """Game table - stores game metadata and scores."""
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    
    # Scores
    home_score: Mapped[int] = mapped_column(Integer, default=0)
    away_score: Mapped[int] = mapped_column(Integer, default=0)
    
    # Quarter scores
    home_score_q1: Mapped[int] = mapped_column(Integer, default=0)
    home_score_q2: Mapped[int] = mapped_column(Integer, default=0)
    home_score_q3: Mapped[int] = mapped_column(Integer, default=0)
    home_score_q4: Mapped[int] = mapped_column(Integer, default=0)
    home_score_ot: Mapped[int] = mapped_column(Integer, default=0)
    
    away_score_q1: Mapped[int] = mapped_column(Integer, default=0)
    away_score_q2: Mapped[int] = mapped_column(Integer, default=0)
    away_score_q3: Mapped[int] = mapped_column(Integer, default=0)
    away_score_q4: Mapped[int] = mapped_column(Integer, default=0)
    away_score_ot: Mapped[int] = mapped_column(Integer, default=0)
    
    # Game metadata
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False)
    current_quarter: Mapped[int] = mapped_column(Integer, default=1)
    total_plays: Mapped[Optional[int]] = mapped_column(Integer)
    game_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_playoff: Mapped[bool] = mapped_column(Boolean, default=False)
    playoff_round: Mapped[Optional[str]] = mapped_column(String(50))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    player_stats: Mapped[list["GamePlayerStats"]] = relationship("GamePlayerStats", back_populates="game")

    # Indexes
    __table_args__ = (
        Index("idx_games_season_week", "season", "week"),
        Index("idx_games_home_team", "home_team_id"),
        Index("idx_games_away_team", "away_team_id"),
    )

    def __repr__(self):
        return f"<Game(id={self.id}, S{self.season}W{self.week}, {self.away_team_id}@{self.home_team_id}, {self.away_score}-{self.home_score})>"


class GamePlayerStats(Base):
    """Game player stats table - stores player stats for a specific game."""
    __tablename__ = "game_player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    
    # Stats stored as JSON
    passing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    rushing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    receiving_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    kicking_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    defense_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    
    fantasy_points: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="player_stats")
    player: Mapped["Player"] = relationship("Player", back_populates="game_stats")

    # Constraints
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_game_player"),
        Index("idx_game_stats_game", "game_id"),
        Index("idx_game_stats_player", "player_id"),
    )

    def __repr__(self):
        return f"<GamePlayerStats(game_id={self.game_id}, player_id={self.player_id})>"


class Season(Base):
    """Season table - tracks season metadata."""
    __tablename__ = "seasons"

    season_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    playoffs_started: Mapped[bool] = mapped_column(Boolean, default=False)
    champion_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Season(season={self.season_number}, week={self.current_week})>"


class Record(Base):
    """Records table - stores all-time, season, and game records."""
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_type: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    stat_name: Mapped[str] = mapped_column(String(50), nullable=False)
    
    player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"))
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    value: Mapped[float] = mapped_column(Float, nullable=False)
    season: Mapped[Optional[int]] = mapped_column(Integer)
    game_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("games.id"))

    # Indexes
    __table_args__ = (
        Index("idx_records_type", "record_type"),
        Index("idx_records_category", "category", "subcategory", "scope"),
    )

    def __repr__(self):
        return f"<Record(type='{self.record_type}', value={self.value})>"


class UnusedName(Base):
    """Unused names table - stores available names for new players."""
    __tablename__ = "unused_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<UnusedName(id={self.id}, name='{self.name}')>"
