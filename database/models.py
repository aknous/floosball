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
    secondary_color: Mapped[Optional[str]] = mapped_column(String(50))
    tertiary_color: Mapped[Optional[str]] = mapped_column(String(50))
    offense_rating: Mapped[int] = mapped_column(Integer)
    defense_rating: Mapped[int] = mapped_column(Integer)
    overall_rating: Mapped[int] = mapped_column(Integer)
    league_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leagues.id"))
    gm_score: Mapped[Optional[int]] = mapped_column(Integer)
    defense_tier: Mapped[Optional[int]] = mapped_column(Integer)
    defense_run_coverage_rating: Mapped[Optional[int]] = mapped_column(Integer)
    defense_pass_coverage_rating: Mapped[Optional[int]] = mapped_column(Integer)
    defense_pass_rush_rating: Mapped[Optional[int]] = mapped_column(Integer)
    defense_season_performance: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Denormalized all-time stats for efficient querying
    all_time_wins: Mapped[int] = mapped_column(Integer, default=0, index=True)
    all_time_losses: Mapped[int] = mapped_column(Integer, default=0)
    all_time_points: Mapped[int] = mapped_column(Integer, default=0)
    all_time_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    all_time_touchdowns: Mapped[int] = mapped_column(Integer, default=0)
    
    # JSON columns for historical data (detailed stats)
    all_time_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    league_championships: Mapped[Optional[list]] = mapped_column(JSON)
    floosbowl_championships: Mapped[Optional[list]] = mapped_column(JSON)
    top_seeds: Mapped[Optional[list]] = mapped_column(JSON)
    playoff_appearances: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    roster_history: Mapped[Optional[dict]] = mapped_column(JSON)
    coach_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coaches.id", use_alter=True, name="fk_teams_coach_id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    league: Mapped[Optional["League"]] = relationship("League", back_populates="teams")
    players: Mapped[list["Player"]] = relationship("Player", back_populates="team")
    season_stats: Mapped[list["TeamSeasonStats"]] = relationship("TeamSeasonStats", back_populates="team")
    home_games: Mapped[list["Game"]] = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games: Mapped[list["Game"]] = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    championships: Mapped[list["Championship"]] = relationship("Championship", back_populates="team")

    # Indexes
    __table_args__ = (
        Index("idx_team_league", "league_id"),
    )

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}', abbr='{self.abbr}')>"


class Coach(Base):
    """Coach table - represents a team's head coach."""
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    seasons_coached: Mapped[int] = mapped_column(Integer, default=0)
    offensive_mind: Mapped[int] = mapped_column(Integer, default=80)
    defensive_mind: Mapped[int] = mapped_column(Integer, default=80)
    adaptability: Mapped[int] = mapped_column(Integer, default=80)
    aggressiveness: Mapped[int] = mapped_column(Integer, default=80)
    clock_management: Mapped[int] = mapped_column(Integer, default=80)
    player_development: Mapped[int] = mapped_column(Integer, default=80)
    overall_rating: Mapped[int] = mapped_column(Integer, default=80)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Coach(id={self.id}, name='{self.name}', overall={self.overall_rating})>"


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
    season_stats: Mapped[list["PlayerSeasonStats"]] = relationship("PlayerSeasonStats", back_populates="player")
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
    
    # Denormalized stats for efficient querying (leaderboards)
    passing_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_tds: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_ints: Mapped[int] = mapped_column(Integer, default=0)
    rushing_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    rushing_tds: Mapped[int] = mapped_column(Integer, default=0)
    receiving_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    receiving_tds: Mapped[int] = mapped_column(Integer, default=0)
    
    # Stats stored as JSON for flexibility (detailed breakdown)
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


class PlayerSeasonStats(Base):
    """Player season stats table - stores player stats by season."""
    __tablename__ = "player_season_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    fantasy_points: Mapped[int] = mapped_column(Integer, default=0)
    
    # Denormalized stats for efficient querying (season leaderboards)
    passing_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_tds: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_ints: Mapped[int] = mapped_column(Integer, default=0)
    passing_completions: Mapped[int] = mapped_column(Integer, default=0)
    passing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    rushing_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    rushing_tds: Mapped[int] = mapped_column(Integer, default=0, index=True)
    rushing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    receiving_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    receiving_tds: Mapped[int] = mapped_column(Integer, default=0, index=True)
    receptions: Mapped[int] = mapped_column(Integer, default=0)
    sacks: Mapped[int] = mapped_column(Integer, default=0, index=True)
    interceptions: Mapped[int] = mapped_column(Integer, default=0, index=True)
    tackles: Mapped[int] = mapped_column(Integer, default=0)
    
    # Stats stored as JSON for flexibility (detailed breakdown)
    passing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    rushing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    receiving_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    kicking_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    defense_stats: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    player: Mapped["Player"] = relationship("Player", back_populates="season_stats")
    team: Mapped["Team"] = relationship("Team")

    # Constraints
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_stats"),
        Index("idx_season_stats_player", "player_id"),
        Index("idx_season_stats_season", "season"),
        Index("idx_season_stats_team", "team_id"),
        Index("idx_season_stats_season_yards", "season", "passing_yards"),
        Index("idx_season_stats_season_rush", "season", "rushing_yards"),
        Index("idx_season_stats_season_rec", "season", "receiving_yards"),
    )

    def __repr__(self):
        return f"<PlayerSeasonStats(player_id={self.player_id}, season={self.season})>"


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
    
    # Denormalized offensive stats for efficient querying
    points: Mapped[int] = mapped_column(Integer, default=0, index=True)
    touchdowns: Mapped[int] = mapped_column(Integer, default=0)
    field_goals: Mapped[int] = mapped_column(Integer, default=0)
    total_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_yards: Mapped[int] = mapped_column(Integer, default=0)
    rushing_yards: Mapped[int] = mapped_column(Integer, default=0)
    passing_tds: Mapped[int] = mapped_column(Integer, default=0)
    rushing_tds: Mapped[int] = mapped_column(Integer, default=0)
    
    # Denormalized defensive stats for efficient querying
    points_allowed: Mapped[int] = mapped_column(Integer, default=0)
    sacks: Mapped[int] = mapped_column(Integer, default=0, index=True)
    interceptions: Mapped[int] = mapped_column(Integer, default=0)
    fumbles_recovered: Mapped[int] = mapped_column(Integer, default=0)
    total_yards_allowed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Stats stored as JSON (detailed breakdown)
    offense_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    defense_stats: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationship
    team: Mapped["Team"] = relationship("Team", back_populates="season_stats")

    # Constraints
    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_team_season"),
        Index("idx_team_stats_team", "team_id"),
        Index("idx_team_stats_season", "season"),
        Index("idx_team_stats_wins", "wins"),
        Index("idx_team_stats_elo", "elo"),
        Index("idx_team_stats_playoffs", "made_playoffs"),
        Index("idx_team_stats_season_wins", "season", "wins"),
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
    status: Mapped[str] = mapped_column(String(20), default='scheduled')

    # Team game stats (populated at game completion; used to rebuild averages on resume)
    home_rush_yards: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_pass_yards: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_rush_tds:   Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_pass_tds:   Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_fgs:        Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_sacks:      Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_ints:       Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_fum_rec:    Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    away_rush_yards: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_pass_yards: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_rush_tds:   Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_pass_tds:   Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_fgs:        Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_sacks:      Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_ints:       Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_fum_rec:    Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    player_stats: Mapped[list["GamePlayerStats"]] = relationship("GamePlayerStats", back_populates="game")

    # Indexes
    __table_args__ = (
        Index("idx_games_season_week", "season", "week"),
        Index("idx_games_home_team", "home_team_id"),
        Index("idx_games_away_team", "away_team_id"),
        Index("idx_games_is_playoff", "is_playoff"),
        Index("idx_games_season_playoff", "season", "is_playoff"),
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


class Championship(Base):
    """Championship table - tracks team championships by season and type."""
    __tablename__ = "championships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    championship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: 'regular_season', 'league', 'floosbowl'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    team: Mapped["Team"] = relationship("Team", back_populates="championships")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("team_id", "season", "championship_type", name="uq_team_season_type"),
        Index("idx_championships_season", "season"),
        Index("idx_championships_type", "championship_type"),
        Index("idx_championships_team", "team_id"),
    )

    def __repr__(self):
        return f"<Championship(team_id={self.team_id}, season={self.season}, type='{self.championship_type}')>"


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

    # Indexes
    __table_args__ = (
        Index("idx_season_champion", "champion_team_id"),
    )

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


class User(Base):
    """User table - stores registered users with auth credentials and preferences."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clerk_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    favorite_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    pending_favorite_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    favorite_team_locked_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auto_fill_roster: Mapped[bool] = mapped_column(Boolean, default=True)
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)
    email_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    fantasy_rosters: Mapped[list["FantasyRoster"]] = relationship("FantasyRoster", back_populates="user")
    user_cards: Mapped[list["UserCard"]] = relationship("UserCard", back_populates="user")
    currency: Mapped[Optional["UserCurrency"]] = relationship("UserCurrency", back_populates="user", uselist=False)

    # Indexes
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_favorite_team", "favorite_team_id"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class FantasyRoster(Base):
    """Fantasy roster table - stores a user's fantasy roster for a season."""
    __tablename__ = "fantasy_rosters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_points: Mapped[float] = mapped_column(Float, default=0.0)
    card_bonus_points: Mapped[float] = mapped_column(Float, default=0.0)
    swaps_available: Mapped[int] = mapped_column(Integer, default=0)
    purchased_swaps: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="fantasy_rosters")
    players: Mapped[list["FantasyRosterPlayer"]] = relationship("FantasyRosterPlayer", back_populates="roster", cascade="all, delete-orphan")
    swaps: Mapped[list["FantasyRosterSwap"]] = relationship("FantasyRosterSwap", back_populates="roster", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "season", name="uq_fantasy_roster_user_season"),
        Index("idx_fantasy_roster_season", "season"),
        Index("idx_fantasy_roster_user", "user_id"),
    )

    def __repr__(self):
        return f"<FantasyRoster(id={self.id}, user_id={self.user_id}, season={self.season}, locked={self.is_locked})>"


class FantasyRosterPlayer(Base):
    """Fantasy roster player table - stores a player slot in a fantasy roster."""
    __tablename__ = "fantasy_roster_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roster_id: Mapped[int] = mapped_column(Integer, ForeignKey("fantasy_rosters.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    slot: Mapped[str] = mapped_column(String(10), nullable=False)  # QB, RB, WR1, WR2, TE, K
    points_at_lock: Mapped[float] = mapped_column(Float, default=0.0)
    stats_at_lock: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: player gameStatsDict at lock time

    # Relationships
    roster: Mapped["FantasyRoster"] = relationship("FantasyRoster", back_populates="players")
    player: Mapped["Player"] = relationship("Player")

    # Constraints
    __table_args__ = (
        UniqueConstraint("roster_id", "slot", name="uq_fantasy_roster_slot"),
        Index("idx_fantasy_player_roster", "roster_id"),
    )

    def __repr__(self):
        return f"<FantasyRosterPlayer(roster_id={self.roster_id}, slot='{self.slot}', player_id={self.player_id})>"


class FantasyRosterSwap(Base):
    """Fantasy roster swap table - tracks player swaps within a locked roster."""
    __tablename__ = "fantasy_roster_swaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roster_id: Mapped[int] = mapped_column(Integer, ForeignKey("fantasy_rosters.id"), nullable=False)
    slot: Mapped[str] = mapped_column(String(10), nullable=False)
    old_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    new_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    swap_week: Mapped[int] = mapped_column(Integer, nullable=False)
    banked_fp: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    roster: Mapped["FantasyRoster"] = relationship("FantasyRoster", back_populates="swaps")
    old_player: Mapped["Player"] = relationship("Player", foreign_keys=[old_player_id])
    new_player: Mapped["Player"] = relationship("Player", foreign_keys=[new_player_id])

    # Constraints
    __table_args__ = (
        Index("idx_fantasy_swap_roster", "roster_id"),
    )

    def __repr__(self):
        return f"<FantasyRosterSwap(roster_id={self.roster_id}, slot='{self.slot}', old={self.old_player_id}, new={self.new_player_id})>"


class UnusedName(Base):
    """Unused names table - stores available names for new players."""
    __tablename__ = "unused_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<UnusedName(id={self.id}, name='{self.name}')>"


class BetaAllowlist(Base):
    """Beta allowlist - emails permitted to access the app during beta."""
    __tablename__ = "beta_allowlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BetaAllowlist(email='{self.email}')>"


class BetaAccessRequest(Base):
    """Tracks requests from users who want access to the closed beta."""
    __tablename__ = "beta_access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)  # pending | approved | denied
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<BetaAccessRequest(email='{self.email}', status='{self.status}')>"


class UserNotification(Base):
    """In-app notifications for users (leaderboard prizes, team bonuses, etc.)."""
    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserNotification(id={self.id}, user_id={self.user_id}, type='{self.type}')>"


class SimulationState(Base):
    """Simulation state table - stores current simulation progress for resumability."""
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_season: Mapped[int] = mapped_column(Integer, default=0)
    current_week: Mapped[int] = mapped_column(Integer, default=0)
    in_playoffs: Mapped[bool] = mapped_column(Boolean, default=False)
    playoff_round: Mapped[Optional[str]] = mapped_column(String(50))
    total_seasons: Mapped[int] = mapped_column(Integer, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_saved: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SimulationState(season={self.current_season}, week={self.current_week}, playoffs={self.in_playoffs})>"


# ─── Trading Card System ───────────────────────────────────────────────────────


class CardTemplate(Base):
    """Card template table - blueprint for every card (one per player/edition/season)."""
    __tablename__ = "card_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    edition: Mapped[str] = mapped_column(String(20), nullable=False)  # base, holographic, prismatic, gold, chrome, diamond
    season_created: Mapped[int] = mapped_column(Integer, nullable=False)
    is_rookie: Mapped[bool] = mapped_column(Boolean, default=False)
    classification: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # rookie, mvp, champion, all_pro, or compound e.g. mvp_champion

    # Snapshot of player at creation time
    player_name: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    player_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # QB=1, RB=2, WR=3, TE=4, K=5

    # Effect configuration (JSON)
    effect_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    rarity_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_value: Mapped[int] = mapped_column(Integer, nullable=False)
    is_upgraded: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    player: Mapped["Player"] = relationship("Player")
    team: Mapped[Optional["Team"]] = relationship("Team")
    user_cards: Mapped[list["UserCard"]] = relationship("UserCard", back_populates="card_template")

    __table_args__ = (
        # Partial unique index created in migration (WHERE is_upgraded = 0)
        # Upgraded templates are exempt from uniqueness constraint
        Index("idx_card_template_season", "season_created"),
        Index("idx_card_template_edition", "edition"),
        Index("idx_card_template_player", "player_id"),
    )

    def __repr__(self):
        return f"<CardTemplate(id={self.id}, player='{self.player_name}', edition='{self.edition}', S{self.season_created})>"


class UserCard(Base):
    """User card table - a card instance in a user's collection."""
    __tablename__ = "user_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    card_template_id: Mapped[int] = mapped_column(Integer, ForeignKey("card_templates.id"), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acquired_via: Mapped[str] = mapped_column(String(20), nullable=False)  # pack_standard, pack_premium, pack_elite, starter
    last_swap_grant_cycle: Mapped[int] = mapped_column(Integer, default=0)  # Tracks All-Pro swap bonus exhaustion per cycle

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_cards")
    card_template: Mapped["CardTemplate"] = relationship("CardTemplate", back_populates="user_cards")

    __table_args__ = (
        Index("idx_user_cards_user", "user_id"),
        Index("idx_user_cards_template", "card_template_id"),
    )

    def __repr__(self):
        return f"<UserCard(id={self.id}, user_id={self.user_id}, template_id={self.card_template_id})>"


class EquippedCard(Base):
    """Equipped card table - cards in play for a given week (max 5 per user)."""
    __tablename__ = "equipped_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    user_card_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_cards.id"), nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    card_bonus_at_lock: Mapped[float] = mapped_column(Float, default=0.0)  # Card bonus snapshot at lock time
    streak_count: Mapped[int] = mapped_column(Integer, default=1)
    swap_bonus_active: Mapped[bool] = mapped_column(Boolean, default=False)  # All-Pro swap bonus tracking

    # Relationships
    user: Mapped["User"] = relationship("User")
    user_card: Mapped["UserCard"] = relationship("UserCard")

    __table_args__ = (
        UniqueConstraint("user_id", "season", "week", "slot_number", name="uq_equipped_card_slot"),
        Index("idx_equipped_cards_user_week", "user_id", "season", "week"),
    )

    def __repr__(self):
        return f"<EquippedCard(user_id={self.user_id}, S{self.season}W{self.week}, slot={self.slot_number})>"


class WeeklyCardBonus(Base):
    """Stores per-week card bonus FP for each roster, enabling weekly leaderboard breakdown."""
    __tablename__ = "weekly_card_bonuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    roster_id: Mapped[int] = mapped_column(Integer, ForeignKey("fantasy_rosters.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_fp: Mapped[float] = mapped_column(Float, default=0.0)
    breakdowns_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("roster_id", "week", name="uq_weekly_card_bonus_roster_week"),
        Index("idx_weekly_card_bonus_season_week", "season", "week"),
    )

    def __repr__(self):
        return f"<WeeklyCardBonus(user_id={self.user_id}, S{self.season}W{self.week}, fp={self.bonus_fp})>"


class CardUpgradeLog(Base):
    """Audit log for card upgrades in The Combine."""
    __tablename__ = "card_upgrade_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    upgrade_type: Mapped[str] = mapped_column(String(20), nullable=False)  # promotion, blend, transplant
    subject_user_card_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL for blend (result is new)
    offering_user_card_ids: Mapped[dict] = mapped_column(JSON, nullable=False)  # list of sacrificed card IDs
    old_template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL for blend
    new_template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    floobits_spent: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_upgrade_log_user", "user_id"),
    )

    def __repr__(self):
        return f"<CardUpgradeLog(user_id={self.user_id}, type='{self.upgrade_type}')>"


class WeeklyModifier(Base):
    """Tracks the active weekly modifier for each season/week."""
    __tablename__ = "weekly_modifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    modifier: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("season", "week", name="uq_weekly_modifier_season_week"),
    )

    def __repr__(self):
        return f"<WeeklyModifier(S{self.season}W{self.week}, modifier='{self.modifier}')>"


class WeeklyPlayerFP(Base):
    """Stores per-week per-player fantasy points, banked by FantasyTracker at week end.

    This is the source of truth for fantasy roster FP — completely decoupled from
    the player stat dict lifecycle (gameStatsDict zeroing, seasonStatsDict accumulation).
    """
    __tablename__ = "weekly_player_fp"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_weekly_player_fp"),
        Index("idx_weekly_player_fp_season", "season"),
    )

    def __repr__(self):
        return f"<WeeklyPlayerFP(player_id={self.player_id}, S{self.season}W{self.week}, fp={self.fantasy_points})>"


class UserCurrency(Base):
    """User currency table - tracks Floobit balance per user."""
    __tablename__ = "user_currency"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifetime_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifetime_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="currency")

    def __repr__(self):
        return f"<UserCurrency(user_id={self.user_id}, balance={self.balance})>"


class CurrencyTransaction(Base):
    """Currency transaction table - audit log for all Floobit changes."""
    __tablename__ = "currency_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # positive = earned, negative = spent
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_currency_tx_user", "user_id"),
        Index("idx_currency_tx_user_season", "user_id", "season"),
        Index("idx_currency_tx_type", "transaction_type"),
    )

    def __repr__(self):
        return f"<CurrencyTransaction(user_id={self.user_id}, amount={self.amount}, type='{self.transaction_type}')>"


class PackType(Base):
    """Pack type table - static configuration for available card packs."""
    __tablename__ = "pack_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # standard, premium, elite
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    cards_per_pack: Mapped[int] = mapped_column(Integer, nullable=False)
    guaranteed_rarity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rarity_weights: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    def __repr__(self):
        return f"<PackType(name='{self.name}', cost={self.cost})>"


class PackOpening(Base):
    """Pack opening table - records every pack purchase/opening."""
    __tablename__ = "pack_openings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    pack_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("pack_types.id"), nullable=False)
    cards_received: Mapped[list] = mapped_column(JSON, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    pack_type: Mapped["PackType"] = relationship("PackType")

    __table_args__ = (
        Index("idx_pack_openings_user", "user_id"),
    )

    def __repr__(self):
        return f"<PackOpening(user_id={self.user_id}, pack='{self.pack_type_id}')>"


class FeaturedShopCard(Base):
    """Featured shop card — persisted per-user selection of cards for sale each season."""
    __tablename__ = "featured_shop_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    card_template_id: Mapped[int] = mapped_column(Integer, ForeignKey("card_templates.id"), nullable=False)
    purchased: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship("User")
    card_template: Mapped["CardTemplate"] = relationship("CardTemplate")

    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    generated_at_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_featured_shop_user_season", "user_id", "season"),
    )


class ShopPurchase(Base):
    """Tracks power-up purchases from the shop."""
    __tablename__ = "shop_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    item_slug: Mapped[str] = mapped_column(String(30), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_shop_purchase_user_season", "user_id", "season"),
        Index("idx_shop_purchase_item_week", "item_slug", "user_id", "season", "week"),
    )


class UserModifierOverride(Base):
    """Per-user weekly modifier override (from Modifier Nullifier power-up)."""
    __tablename__ = "user_modifier_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    override_modifier: Mapped[str] = mapped_column(String(20), nullable=False)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "season", "week", name="uq_mod_override_user_week"),
        Index("idx_mod_override_user_season_week", "user_id", "season", "week"),
    )


# ─── GM Mode ────────────────────────────────────────────────────────────────────


class GmVote(Base):
    """GM Mode vote — a single vote cast by a user for a team action."""
    __tablename__ = "gm_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    vote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    cost_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    team: Mapped["Team"] = relationship("Team")
    target_player: Mapped[Optional["Player"]] = relationship("Player")

    __table_args__ = (
        Index("idx_gm_votes_team_season", "team_id", "season"),
        Index("idx_gm_votes_user_season", "user_id", "season"),
    )

    def __repr__(self):
        return f"<GmVote(id={self.id}, user={self.user_id}, team={self.team_id}, type='{self.vote_type}')>"


class GmVoteResult(Base):
    """GM Mode vote result — outcome of aggregated votes for a team action."""
    __tablename__ = "gm_vote_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    vote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    total_votes: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    success_probability: Mapped[float] = mapped_column(Float, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    team: Mapped["Team"] = relationship("Team")
    target_player: Mapped[Optional["Player"]] = relationship("Player")

    __table_args__ = (
        Index("idx_gm_vote_results_team_season", "team_id", "season"),
    )

    def __repr__(self):
        return f"<GmVoteResult(team={self.team_id}, type='{self.vote_type}', outcome='{self.outcome}')>"


class GmFaBallot(Base):
    """GM Mode FA ballot — ranked choice ballot for free agent signing."""
    __tablename__ = "gm_fa_ballots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    rankings: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of player IDs
    cost_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    team: Mapped["Team"] = relationship("Team")

    __table_args__ = (
        UniqueConstraint("user_id", "team_id", "season", name="uq_gm_fa_ballot"),
        Index("idx_gm_fa_ballots_team_season", "team_id", "season"),
    )

    def __repr__(self):
        return f"<GmFaBallot(user={self.user_id}, team={self.team_id}, season={self.season})>"


# ─── Pick-Em ("Prognostications") ────────────────────────────────────────────


class PickEmPick(Base):
    """Pick-Em pick — a user's prediction for a single game in a week."""
    __tablename__ = "pick_em_picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    game_index: Mapped[int] = mapped_column(Integer, nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    picked_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    points_multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    points_earned: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "season", "week", "game_index", name="uq_pickem_pick"),
        Index("idx_pickem_user_season", "user_id", "season"),
        Index("idx_pickem_season_week", "season", "week"),
    )

    def __repr__(self):
        return f"<PickEmPick(user={self.user_id}, S{self.season}W{self.week}, game={self.game_index}, picked={self.picked_team_id})>"
