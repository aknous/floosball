"""SQLAlchemy models for Floosball database."""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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
    # Single source of truth for "which coach does this team have".
    # UNIQUE enforces the 1:1 invariant at the schema level — a Coach can be
    # assigned to AT MOST one Team. Multiple teams pointing at the same
    # coach_id (a bug class) is impossible. Multiple NULLs are allowed
    # (a coachless team is fine). See migration in connection.py that
    # backfills the constraint via unique index on existing prod DBs.
    coach_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coaches.id", use_alter=True, name="fk_teams_coach_id"), nullable=True, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    league: Mapped[Optional["League"]] = relationship("League", back_populates="teams")
    # Players disambiguates by team_id because Player also has a drafting_team_id
    # FK (prospect pipeline ownership). Only the active-roster FK participates in
    # Team.players — prospects are accessed via a separate runtime list.
    players: Mapped[list["Player"]] = relationship(
        "Player", back_populates="team", foreign_keys="[Player.team_id]"
    )
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
    """Coach table - represents a team's head coach.

    Note: there is intentionally no team_id column here. The single source
    of truth for "what coach does this team have" is Team.coach_id. The
    previous schema kept both directions (Team.coach_id + Coach.team_id)
    which created a class of orphan-row bugs when the two diverged on a
    failed write. The legacy column may still exist on older databases — the
    inline migration in connection.py drops it on boot when present.
    """
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    seasons_coached: Mapped[int] = mapped_column(Integer, default=0)
    offensive_mind: Mapped[int] = mapped_column(Integer, default=80)
    defensive_mind: Mapped[int] = mapped_column(Integer, default=80)
    adaptability: Mapped[int] = mapped_column(Integer, default=80)
    aggressiveness: Mapped[int] = mapped_column(Integer, default=80)
    clock_management: Mapped[int] = mapped_column(Integer, default=80)
    player_development: Mapped[int] = mapped_column(Integer, default=80)
    # Scouting — accuracy with which fans can see upcoming rookies' potential.
    # Stacks with funding tier to determine the attribute-range blur on /api/rookies/upcoming.
    scouting: Mapped[int] = mapped_column(Integer, default=80)
    # Locker-room presence on toxic→leader spectrum. Drives attitude contagion
    # control + 'play hard for them' game-day effect.
    attitude: Mapped[int] = mapped_column(Integer, default=80)
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
    # Times the CURRENT team has re-signed this player (retention limit / re-sign-once;
    # resets to 0 when the player walks to FA). See docs/PARITY_PROSPECT_PLAN.md.
    team_resign_count: Mapped[int] = mapped_column(Integer, default=0)
    player_rating: Mapped[Optional[int]] = mapped_column(Integer)
    offensive_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    defensive_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    defensive_position: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    # Awakened (L4) signature power — the player's ONE career power, assigned once at first awakening
    # (managers/awakenedPowers.py key) and kept for their career. Null until awakened. Gated by
    # ANOMALY_AWAKENED_POWERS_ENABLED.
    signature_power: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    free_agent_years: Mapped[Optional[int]] = mapped_column(Integer)
    service_time: Mapped[Optional[str]] = mapped_column(String(20))
    # Prospect pipeline (see constants.PROSPECT_*)
    is_prospect: Mapped[bool] = mapped_column(Boolean, default=False)
    is_undrafted: Mapped[bool] = mapped_column(Boolean, default=False)
    prospect_seasons: Mapped[int] = mapped_column(Integer, default=0)
    drafting_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    # True after _generateRookieClass, before the offseason rookie draft.
    # Upcoming rookies are visible to fans all season for scouting/voting but
    # aren't on any roster or pipeline yet. Cleared at draft time.
    is_upcoming_rookie: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set during the regular season when an end-of-contract player has decided
    # to retire after this season. Surfaces in UI so users see retirements
    # coming and can vote on replacements via FA ballot.
    will_retire: Mapped[bool] = mapped_column(Boolean, default=False)
    # Persisted Hall of Fame induction flag. Set when inductHallOfFame()
    # accepts a newly-retired player. Without this, the in-memory
    # hallOfFame list resets on every server restart and the HoF tab
    # goes empty until brand-new retirees are inducted.
    is_hof: Mapped[bool] = mapped_column(Boolean, default=False)
    # Season the player was inducted (the just-ended season at offseason
    # induction time) — drives the "Class of Season N" grouping in the Hall of
    # Fame gallery. Null for players inducted before this column existed.
    hof_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Career awards — same in-memory-only problem as is_hof. The player
    # profile page reads these to render the awards section; without
    # persistence they reset on every server restart.
    mvp_awards: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    # All-Pro is a combined offense+defense team (defense slots picked by the
    # WPA defensive-value metric); a season here means the player made either side.
    all_pro_seasons: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    league_championships: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team: Mapped[Optional["Team"]] = relationship(
        "Team", back_populates="players", foreign_keys=[team_id]
    )
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
    reach: Mapped[int] = mapped_column(Integer, default=0)
    agility: Mapped[int] = mapped_column(Integer)
    power: Mapped[int] = mapped_column(Integer)
    arm_strength: Mapped[int] = mapped_column(Integer)
    accuracy: Mapped[int] = mapped_column(Integer)
    leg_strength: Mapped[int] = mapped_column(Integer)
    skill_rating: Mapped[int] = mapped_column(Integer)

    # Potential attributes
    potential_speed: Mapped[int] = mapped_column(Integer)
    potential_hands: Mapped[int] = mapped_column(Integer)
    potential_reach: Mapped[int] = mapped_column(Integer, default=0)
    potential_agility: Mapped[int] = mapped_column(Integer)
    potential_power: Mapped[int] = mapped_column(Integer)
    potential_arm_strength: Mapped[int] = mapped_column(Integer)
    potential_accuracy: Mapped[int] = mapped_column(Integer)
    potential_leg_strength: Mapped[int] = mapped_column(Integer)
    potential_skill_rating: Mapped[int] = mapped_column(Integer)

    # True-skill attributes — the mature level a player develops INTO (the
    # generated attr value). current <= trueSkill <= potential. Rookies debut
    # below trueSkill and grow into it. See docs/PARITY_PROSPECT_PLAN.md.
    true_skill_speed: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_hands: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_reach: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_agility: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_power: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_arm_strength: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_accuracy: Mapped[int] = mapped_column(Integer, default=0)
    true_skill_leg_strength: Mapped[int] = mapped_column(Integer, default=0)

    # Mental/skill attributes
    route_running: Mapped[int] = mapped_column(Integer)
    vision: Mapped[int] = mapped_column(Integer)
    blocking: Mapped[int] = mapped_column(Integer)
    discipline: Mapped[int] = mapped_column(Integer)
    attitude: Mapped[int] = mapped_column(Integer)
    # Per-player attitude anchor (their disposition). Drift mean-reverts toward THIS,
    # not a global neutral, so a bad season is a recoverable dip, not a slide to toxic.
    attitude_baseline: Mapped[int] = mapped_column(Integer, default=80)
    focus: Mapped[int] = mapped_column(Integer)
    instinct: Mapped[int] = mapped_column(Integer)
    creativity: Mapped[int] = mapped_column(Integer)
    resilience: Mapped[int] = mapped_column(Integer)
    clutch_factor: Mapped[int] = mapped_column(Integer)
    # Volatility of confidence response to results. High = stable, low = volatile.
    self_belief: Mapped[int] = mapped_column(Integer, default=80)
    pressure_handling: Mapped[int] = mapped_column(Integer)
    longevity: Mapped[int] = mapped_column(Integer)
    play_making_ability: Mapped[int] = mapped_column(Integer)
    x_factor: Mapped[int] = mapped_column(Integer)
    
    # Modifiers
    confidence_modifier: Mapped[int] = mapped_column(Integer)
    determination_modifier: Mapped[int] = mapped_column(Integer)
    luck_modifier: Mapped[int] = mapped_column(Integer)
    defensive_talent: Mapped[int] = mapped_column(Integer, default=0)

    # Fatigue (0.0 = fresh, 1.0 = fully fatigued)
    fatigue: Mapped[float] = mapped_column(Float, default=0.0)

    # Personality
    # personality: name of the assigned vibe or variant (1 of 28)
    # quirk: optional sideline-flavor trait (1 of ~20, may be null)
    # mood: 1-5, recomputed periodically from confidence + determination
    personality: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    quirk: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    mood: Mapped[int] = mapped_column(Integer, default=3)

    # Flavor fields — assigned once at player creation, never change.
    # Pure character flavor for the player detail page; no gameplay effect.
    hometown: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    favorite_category: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    favorite_item: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    motto: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)

    # Relationship
    player: Mapped["Player"] = relationship("Player", back_populates="attributes")

    def __repr__(self):
        return f"<PlayerAttributes(player_id={self.player_id}, overall={self.overall_rating})>"


class PlayerPersonalityHistory(Base):
    """Tracks personality changes and quirk reassignments over a career.

    With the new system, personality is assigned at creation and rarely
    changes. This table is retained for any future awakening events or
    admin overrides.
    """
    __tablename__ = "player_personality_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'personality' | 'quirk' | 'mood'
    from_value: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_value: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_personality_history_player", "player_id"),
        Index("idx_personality_history_season", "season"),
    )

    def __repr__(self):
        return (f"<PlayerPersonalityHistory(player_id={self.player_id}, "
                f"season={self.season}, week={self.week}, "
                f"{self.change_type}: {self.from_value}->{self.to_value})>")


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
    # Season WPA value totals (offense + defensive unit-share) + snap counts.
    # The MVP + All-Pro defense value metrics read these. See docs/WPA_MVP_PLAN.md.
    wpa: Mapped[float] = mapped_column(Float, default=0.0)
    def_wpa: Mapped[float] = mapped_column(Float, default=0.0)
    wpa_snaps: Mapped[int] = mapped_column(Integer, default=0)
    def_snaps: Mapped[int] = mapped_column(Integer, default=0)

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


class PlayerRatingHistory(Base):
    """Rating snapshot per player per season — powers the progression sparkline.

    Snapshotted at season start, AFTER offseason training has applied for the
    season (so the value is the rating the player carried through that season).
    Captures all players league-wide: rostered, prospects, free agents, even
    upcoming rookies, so every player has a developable trajectory.
    """
    __tablename__ = "player_rating_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    offensive_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    defensive_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_rating_history"),
        Index("idx_rating_history_player", "player_id"),
        Index("idx_rating_history_season", "season"),
    )

    def __repr__(self):
        return f"<PlayerRatingHistory(player={self.player_id}, season={self.season}, rating={self.rating})>"



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

    # Cumulative count of WPA "big plays" (home or away WPA ≥ 7) in
    # games this team participated in. Drives the Highlight Reel card
    # projection (pays per favorite-team big play).
    big_plays: Mapped[int] = mapped_column(Integer, default=0)

    # Longest win-or-loss streak (abs value) this season. Persisted so
    # the Gone Streaking card retains its season-long high after backend
    # restarts — without this, peakStreak lives only on the in-memory
    # Team object and resets to 0 every boot.
    peak_streak: Mapped[int] = mapped_column(Integer, default=0)
    
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


class TeamFunding(Base):
    """Team funding table - tracks season-by-season patronage from user taxes."""
    __tablename__ = "team_funding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_funding: Mapped[int] = mapped_column(Integer, default=0)
    fan_contributions: Mapped[int] = mapped_column(Integer, default=0)
    current_funding: Mapped[int] = mapped_column(Integer, default=0)
    carried_funding: Mapped[int] = mapped_column(Integer, default=0)
    effective_funding: Mapped[int] = mapped_column(Integer, default=0)
    funding_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tier_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Snapshot of the funding value the current tier was computed from.
    # At season start = baseline + carried (the value _initializeTeamFunding
    # ranks against). At offseason recompute = effective_funding at that
    # moment (includes mid-season fan contributions). Markets chart uses
    # this to position the filled "locked" dot so it always sits inside the
    # tier band the badge displays — without it the dot can drift out of
    # band as post-recompute contributions inflate effective_funding.
    tier_locked_funding: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_team_funding_season"),
        Index("idx_team_funding_team", "team_id"),
        Index("idx_team_funding_season", "season"),
    )

    def __repr__(self):
        return f"<TeamFunding(team_id={self.team_id}, season={self.season}, tier={self.funding_tier}, effective={self.effective_funding})>"


class TeamFacility(Base):
    """A team's standing facility and its level (Markets→Facilities system).

    PERSISTENT, not season-scoped — facilities are the team's lasting
    infrastructure, carried across seasons (subject to decay). One row per
    (team, facility_key). Levels are seeded once from the legacy funding_tier
    by the migration (see docs/MARKETS_FACILITIES_PLAN.md) and change as fans
    fund upgrades / let upkeep lapse in later phases.
    """
    __tablename__ = "team_facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    facility_key: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Floobits put toward THIS season's upkeep (direct contributions). Reset to 0
    # each season start; the season-end waterfall tops it up from the deposit.
    upkeep_funded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "facility_key", name="uq_team_facility"),
        Index("idx_team_facility_team", "team_id"),
    )

    def __repr__(self):
        return f"<TeamFacility(team_id={self.team_id}, facility={self.facility_key}, level={self.level})>"


class FacilityProject(Base):
    """An open (in-progress) facility build/upgrade in a team's queue.

    Created when a project is opened (Phase 3: by fan vote). Fans fund it
    directly all season; the season-end waterfall tops up the OLDEST open
    project. Persists across seasons until fully funded (then it builds in the
    offseason and status→built). See docs/MARKETS_FACILITIES_PLAN.md §3.
    """
    __tablename__ = "facility_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    facility_key: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)        # 'upgrade' | 'new'
    target_level: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_shares: Mapped[float] = mapped_column(Float, nullable=False)   # share-denominated; Floobit target = cost_shares × shareUnit(season)
    funded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Floobits accumulated
    opened_season: Mapped[int] = mapped_column(Integer, nullable=False)      # FIFO key
    status: Mapped[str] = mapped_column(String(8), default="open", nullable=False)  # 'open' | 'built'
    built_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_facility_project_team", "team_id"),
        Index("idx_facility_project_status", "status"),
    )

    def __repr__(self):
        return f"<FacilityProject(team={self.team_id}, {self.facility_key}→Lv{self.target_level}, funded={self.funded}, {self.status})>"


class TeamTreasury(Base):
    """A team's persistent facility Treasury balance (Markets→Facilities).

    Separate from the legacy TeamFunding ledger (which still drives the Market
    label + FA order during the transition). Funded by carry-forward + baseline +
    fan contributions; spent on upkeep and projects by the season-end waterfall.
    """
    __tablename__ = "team_treasury"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False, unique=True)
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<TeamTreasury(team={self.team_id}, balance={self.balance})>"


class FacilityVote(Base):
    """A fan's vote for which facility a team should invest in NEXT (Markets→
    Facilities, Phase 3). One vote per fan per team per season, changeable
    (single-vote plurality). Resolved at season end — the plurality winner gets
    an upgrade/build project opened into the queue.
    """
    __tablename__ = "facility_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    facility_key: Mapped[str] = mapped_column(String(32), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", "season", name="uq_facility_vote"),
        Index("idx_facility_vote_team_season", "team_id", "season"),
    )

    def __repr__(self):
        return f"<FacilityVote(team={self.team_id}, user={self.user_id}, {self.facility_key}, S{self.season})>"


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

    # Format-specific display state at completion, as JSON (the payload GameFormat.stateExtra
    # emits live: the innings line score, frames results, chess-clock budgets...). Quarter
    # scores get dedicated columns, but a format's breakdown is shaped per format, so it's a
    # blob. Without this the innings/frames box score only existed in the live WS stream and
    # vanished on a restart. NULL for standard games and for anything finished before this
    # column existed (the state is gone — not backfillable).
    format_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    q4_fantasy_points: Mapped[int] = mapped_column(Integer, default=0)
    # Count of TDs + FGs scored by this player during Q4/OT of this game.
    # Drives the Walk Off card effect (pays per late-game scoring play
    # by a roster player).
    q4_scoring_plays: Mapped[int] = mapped_column(Integer, default=0)
    # Win Probability Added credited to this player in this game (offense + the
    # defensive unit-share), with snap counts. Feeds the season WPA value metric
    # (MVP + All-Pro defense). See docs/WPA_MVP_PLAN.md.
    wpa: Mapped[float] = mapped_column(Float, default=0.0)
    def_wpa: Mapped[float] = mapped_column(Float, default=0.0)
    wpa_snaps: Mapped[int] = mapped_column(Integer, default=0)
    def_snaps: Mapped[int] = mapped_column(Integer, default=0)

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


class GameRally(Base):
    """Live in-game fan rally — fans spend floobits during games to push
    their team's collective confidence (and determination if trailing).

    Records the individual rally action for audit + cumulative tracking.
    The sim engine reads per-(game, team) totals to apply a real-time
    bump on every per-play mental-drift calculation. Diminishing returns
    on the cumulative rally count prevent unlimited stacking.
    """
    __tablename__ = "game_rallies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    # Tier: 'small' / 'medium' / 'large'
    cost_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    # Bumps actually applied after diminishing returns + comeback weighting.
    confidence_delta: Mapped[float] = mapped_column(Float, default=0.0)
    determination_delta: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_game_rallies_game", "game_id"),
        Index("idx_game_rallies_user", "user_id"),
        Index("idx_game_rallies_game_team", "game_id", "team_id"),
        Index("idx_game_rallies_game_user", "game_id", "user_id"),
    )


class SpectatorProgress(Base):
    """Per-user cheer-bar state (feature/fan-income, Spectator).

    The ACTIVE non-fantasy income path: watching live games fills a segmented
    bar, each completed segment pays Floobits. bar_fill is the current partial
    segment; the weekly counters bound the payout (reset when the week rolls).
    Per-game witnessed-play tracking lives in memory (SpectatorManager), not
    here — this row only persists the durable bar + the weekly cap.
    """
    __tablename__ = "spectator_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    bar_fill: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Week marker the weekly counters belong to (season*100 + week); on change
    # the weekly counters reset.
    week_marker: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weekly_floobits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weekly_segments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_spectator_progress_user", "user_id"),
    )

    def __repr__(self):
        return f"<GameRally(game={self.game_id}, user={self.user_id}, team={self.team_id}, tier={self.tier})>"


class SupporterDividend(Base):
    """Itemized UNCLAIMED Supporter dividends — one row per fan per week credited,
    holding that week's amount + its bonus breakdown (base/win/upset/shutout/…
    and the applied Tenure×Funding multiplier).

    These rows represent only what's currently sitting in the pool: they're
    deleted when the fan claims. So the table stays tiny (weeks since the last
    claim) and the UI can show *why* the pool is what it is, without keeping a
    full lifetime ledger. The authoritative pool total stays on
    `users.supporter_unclaimed`; these rows are the breakdown of it.
    """
    __tablename__ = "supporter_dividends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "season", "week", name="uq_supporter_dividend_week"),
        Index("idx_supporter_dividends_user", "user_id"),
    )


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
    # JSON list of player IDs on the champion's roster AT the Floos Bowl — snapshotted
    # at season end before the offseason churns it, so the Champion classification + pack
    # reflect who actually won (not whoever's on the team next season).
    champion_player_ids: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mvp_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    all_pro_player_ids: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # JSON list of player IDs (offense+defense union)
    # Rich, durable All-Pro team: JSON list of {id, side, position, value} so the
    # recap can rebuild the offense/defense split (the flat id list above can't).
    all_pro_team: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Frozen MVP ballot: JSON list of the top-5 candidate dicts (no player object)
    # captured at season end, so the voting view and the post-announcement results
    # show the same candidates even after the offseason resets season stats.
    mvp_ballot: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Snapshot of per-team active fan counts taken when the Front Office
    # opens (week 22). JSON object: {teamId: activeFanCount}. Used as the
    # GM vote threshold so a fan who logs in for the first time after the
    # voting window opens doesn't inflate the bar mid-vote.
    front_office_fan_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Frozen playoff field for the bracket challenge, set when seeding locks.
    # JSON: {"conferences": {confName: [{teamId, seed, winPct, scoreDiff, bye}]}}.
    # The bracket projects matchups from this + a user's picks (re-seeding is
    # deterministic once seeds are frozen).
    playoff_seeds: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_season_champion", "champion_team_id"),
    )

    def __repr__(self):
        return f"<Season(season={self.season_number}, week={self.current_week})>"


class SeasonRecapEvent(Base):
    """Durable per-season log of offseason transactions + announcements that
    feed the Season Recap. Written live as the offseason resolves (so the recap
    survives the in-memory lists clearing) and queried per season. Awards,
    standings, and stat leaders are NOT stored here — they're derivable from the
    Season row / games / player_season_stats; only this movement/announcement
    log needed new persistence."""
    __tablename__ = "season_recap_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # rookie_pick | fa_pick | cut | resign | promotion | retirement |
    # hof_induction | coach_fire | coach_hire
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    team_abbr: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    team_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    player_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    player_name: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # coach name, skip reason, seasons, etc.
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # stable display order within a season
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_recap_event_season", "season", "sort_order"),
    )

    def __repr__(self):
        return f"<SeasonRecapEvent(season={self.season}, type={self.event_type}, player={self.player_name})>"


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
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    favorite_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    pending_favorite_team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    favorite_team_locked_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auto_fill_roster: Mapped[bool] = mapped_column(Boolean, default=True)
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)
    email_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    email_day_report: Mapped[bool] = mapped_column(Boolean, default=True)
    email_season_report: Mapped[bool] = mapped_column(Boolean, default=True)
    discord_id: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    discord_dm_reminders: Mapped[bool] = mapped_column(Boolean, default=False)
    # Auto-pick mode for pick-em: "off" | "favorites" | "underdogs" | "random".
    # Replaces the old boolean auto_pick_favorites. Default "off" = user opts in manually.
    auto_pick_mode: Mapped[str] = mapped_column(String(20), default="off", nullable=False)
    # Vacancy fallback preference: prospect | fa | best_available (default)
    vacancy_auto_pick: Mapped[str] = mapped_column(String(20), default="best_available", nullable=False)
    team_funding_pct: Mapped[int] = mapped_column(Integer, default=25)
    # Supporter income (feature/fan-income): a non-fantasy, idle Floobit path.
    # supporter_weeks = tenure backing the current favorite team (drives the
    # loyalty multiplier; persists across seasons, soft-reset on a team change).
    # supporter_unclaimed = accrued Floobits awaiting claim (the idle pool).
    supporter_weeks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    supporter_unclaimed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Season number the user last claimed their free starter pack in.
    # Resets each season — null means never claimed.
    starter_pack_claimed_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
    # Last week the user explicitly set their equipped-card slots via PUT. Used so an
    # intentional "unequip everything" doesn't get undone by the GET auto-carry-forward.
    last_equipped_set_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Snapshot of the original player_ids the user committed to on their first
    # roster save. Used by the Loyalty card to reward keeping any of these
    # players on roster. JSON list of integers.
    initial_player_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    # old_player_id NULL = filling a previously-emptied slot (no prior occupant).
    # new_player_id NULL = removing the current occupant without immediate replacement.
    # Either, but not both, may be NULL.
    old_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    new_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    swap_week: Mapped[int] = mapped_column(Integer, nullable=False)
    banked_fp: Mapped[float] = mapped_column(Float, default=0.0)
    # Snapshot of the old player's swap-week FP at the moment of the swap.
    # Used so the leaderboard's weekly FP doesn't drop when a user swaps
    # post-games-end — the old player's current-week contribution is
    # preserved here rather than being lost when they leave roster.players.
    banked_week_fp: Mapped[float] = mapped_column(Float, default=0.0)
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


class UserLoginDay(Base):
    """One row per (user, calendar date) the user logged in.

    Lets the admin DAU chart count distinct users per day instead of
    relying on User.last_login_at, which only stores each user's MOST
    RECENT login — so when a user returns the next day, the previous
    day's count silently drops by one. Inserts are UPSERT-ignore so a
    user logging in multiple times in one day produces one row.
    """
    __tablename__ = "user_login_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    login_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "login_date", name="uq_user_login_day"),
    )


class CoachCandidate(Base):
    """A coach offered as a candidate to a specific team during a hire cycle.

    Per-team coach hiring (replaces the shared coach pool):
      - Generated lazily when a team needs a new coach (post-fire or
        post-retirement) — 3 candidates per vacancy with a quality spread
        (premium/solid/developmental) so users always have at least one
        attractive option.
      - GM hire_coach votes target the coach_id of one of these candidates.
      - On hire resolution, the winning candidate becomes the team's coach;
        the other rows are deleted and their coach names returned to the
        unused-name pool. No cross-team contention.
    """
    __tablename__ = "coach_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    coach_id: Mapped[int] = mapped_column(Integer, ForeignKey("coaches.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 0..2
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped["Team"] = relationship("Team")
    coach: Mapped["Coach"] = relationship("Coach")

    __table_args__ = (
        Index("idx_coach_candidates_team_season", "team_id", "season"),
    )


class UnusedName(Base):
    """Unused names table - stores available names for new players."""
    __tablename__ = "unused_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<UnusedName(id={self.id}, name='{self.name}')>"


class PendingName(Base):
    """Recycled retiree names held out of the usable pool until available_season.
    Kept separate from unused_names because the unused-name save path full-replaces
    that table; pending names must survive it. Released into unused_names at the
    season start where season >= available_season (see playerManager.releaseDueNames)."""
    __tablename__ = "pending_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    available_season: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self):
        return f"<PendingName(name='{self.name}', available_season={self.available_season})>"


class NameSubmission(Base):
    """A name suggested by a user through the Discord bot, held for admin review.

    Submissions do NOT go into `unused_names` — they wait here until an admin approves
    them, at which point the name is added to the pool exactly as a direct admin add
    would be (same in-use / duplicate checks). Rejected rows are KEPT rather than
    deleted, so the same name can't be resubmitted on a loop and there's a record of
    what was turned down. `name` is unique for that reason: one row per name ever
    submitted, whatever its outcome."""
    __tablename__ = "name_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default='pending', nullable=False, index=True)
    # Who sent it. Only Discord-linked users may submit, so there's always a real user
    # behind a row; the username is snapshotted so the queue still reads correctly if
    # they later change it, and user_id stays nullable so deleting a user can't orphan.
    discord_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_username: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<NameSubmission(name='{self.name}', status='{self.status}')>"


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
    # True while handleOffseason() is executing. Set before offseason starts,
    # cleared after seasonsPlayed is advanced. If a crash lands mid-offseason,
    # the resume logic uses offseason_phase + offseason_completed_steps to
    # pick up where it left off rather than replaying the whole offseason.
    in_offseason: Mapped[bool] = mapped_column(Boolean, default=False)
    # Top-level offseason flow phase for resume: post_bowl, frontoffice,
    # rookie_draft, pre_fa, fa_draft, training. Mirrors seasonManager
    # _offseasonFlowPhase so the in-memory state survives a restart.
    offseason_phase: Mapped[Optional[str]] = mapped_column(String(32))
    # ISO datetime (UTC) the current waiting phase is counting down to. Lets
    # post-restart resume restore the timer instead of recomputing.
    offseason_phase_target: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # JSON array of completed step keys (e.g. ["frontoffice_decisions",
    # "training"]). Lets phase resume skip non-idempotent batch work.
    offseason_completed_steps: Mapped[Optional[str]] = mapped_column(Text)
    # JSON snapshot of in-progress playoff bracket state (last completed round,
    # surviving teams per league, accumulated free-agency/draft order). Written
    # at the end of each playoff round so a mid-playoff restart resumes at the
    # next unplayed round instead of replaying the bracket from Round 1.
    playoff_state: Mapped[Optional[str]] = mapped_column(Text)
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
    edition: Mapped[str] = mapped_column(String(20), nullable=False)  # base, holographic, prismatic, diamond
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
    # Denormalized output type for themed-pack filtering.
    # Values: "fp" | "fpx" | "floobits" | NULL (mixed/in-between).
    output_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

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
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # Upgrade tier 1-4 (I-IV); leveled via same-effect duplicate + Floobits
    vaulted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Permanent collection — irreversible; can't equip/sell/combine
    vaulted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When it was vaulted
    vault_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Manual sort order within the Vault (null = unset)

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
    # Streak peak-decay state. peak_output captures the in-streak output of
    # the card the last week the streak was active; weeks_since_break counts
    # cold weeks since then. Together they feed the decay tail formula:
    # output = max(base, peak_output * decay**weeks_since_break) when streak
    # is broken. Both reset to 0/null when a new streak starts. Only used by
    # streak-type cards; ignored for other categories.
    peak_output: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    weeks_since_break: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship("User")
    user_card: Mapped["UserCard"] = relationship("UserCard")

    __table_args__ = (
        UniqueConstraint("user_id", "season", "week", "slot_number", name="uq_equipped_card_slot"),
        Index("idx_equipped_cards_user_week", "user_id", "season", "week"),
    )

    def __repr__(self):
        return f"<EquippedCard(user_id={self.user_id}, S{self.season}W{self.week}, slot={self.slot_number})>"


class ShowcaseSlot(Base):
    """A featured card in a user's seasonal Showcase (8 slots, vaulted cards only).

    Season-scoped: a new season starts with no rows, so the showcase "clears"
    automatically each season after the end-of-season payout. Only vaulted cards
    may be featured (enforced at the API layer)."""
    __tablename__ = "showcase_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–8
    user_card_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_cards.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    user_card: Mapped["UserCard"] = relationship("UserCard")

    __table_args__ = (
        UniqueConstraint("user_id", "season", "slot_number", name="uq_showcase_slot"),
        Index("idx_showcase_slots_user_season", "user_id", "season"),
    )

    def __repr__(self):
        return f"<ShowcaseSlot(user_id={self.user_id}, S{self.season}, slot={self.slot_number})>"


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
    # Number of cards the user keeps from cards_per_pack revealed. Null/equal-to
    # cards_per_pack = no selection (user keeps everything, e.g. starter pack).
    cards_kept: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    guaranteed_rarity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rarity_weights: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    # Themed pack metadata. NULL on standard tiers (humble/grand/exquisite/starter).
    # theme_type ∈ {"position", "team", "output"}; theme_value is the discriminator:
    #   position → "QB" | "RB" | "WR" | "TE" | "K"
    #   team     → stringified team id (e.g. "12")
    #   output   → "fp" | "fpx" | "floobits"
    theme_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    theme_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def __repr__(self):
        return f"<PackType(name='{self.name}', cost={self.cost})>"


class PendingPackOpening(Base):
    """Pack opens where the user has paid + revealed cards but hasn't yet
    chosen which to keep. Closed when user selects, or auto-closed (random
    pick) by the stale-pending sweep on app startup.
    """
    __tablename__ = "pending_pack_openings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    pack_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("pack_types.id"), nullable=False)
    # Revealed card-template ids the user is choosing from. Order is preserved;
    # frontend references cards by index in this list when submitting selection.
    revealed_template_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    cost_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")
    pack_type: Mapped["PackType"] = relationship("PackType")

    __table_args__ = (
        Index("idx_pending_pack_openings_user", "user_id"),
    )


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


class PlayReaction(Base):
    """User reaction on a play (or its sideline-quote personality event)
    within a live game. One row per (game, play, target_type, user). Reacting
    again with the same type removes the row; reacting with a different type
    swaps it. Public counts only — UI may surface usernames via the
    relationship.
    """
    __tablename__ = "play_reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    # Stable sequence within a game (game.totalPlays at the time the play ran).
    play_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'play' = the play row itself; 'sideline_quote' = the personality
    # event attached to the play (player reaction quote on the sideline).
    target_type: Mapped[str] = mapped_column(String(20), nullable=False, default='play')
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    # One of: 'hype', 'love', 'wow', 'laugh', 'cry', 'mad'
    reaction_type: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")
    game: Mapped["Game"] = relationship("Game")

    __table_args__ = (
        UniqueConstraint("game_id", "play_number", "target_type", "user_id",
                         name="uq_play_reaction_user_target"),
        Index("idx_play_reaction_game_play", "game_id", "play_number"),
    )

    def __repr__(self):
        return (f"<PlayReaction(game={self.game_id} play={self.play_number} "
                f"target={self.target_type} user={self.user_id} type={self.reaction_type})>")


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


class FeaturedPackRotation(Base):
    """Per-user themed-pack rotation. Each user sees their own 3 themed packs
    for a given (season, shop_day) cycle. Generated lazily on first read;
    regenerated when the shop_day advances (every 7 in-game weeks) or when
    the user rerolls. Once a pack is opened, its rotation row is marked
    purchased=True and disappears from the shop view (mirrors FeaturedShopCard)."""
    __tablename__ = "featured_pack_rotation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    shop_day: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..4
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 0..2
    pack_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("pack_types.id"), nullable=False)
    purchased: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    generated_at_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship("User")
    pack_type: Mapped["PackType"] = relationship("PackType")

    __table_args__ = (
        Index("idx_pack_rotation_user_season_day", "user_id", "season", "shop_day"),
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
    # 'yea' (support) or 'nay' (oppose). Only the threshold directives
    # (fire_coach / cut_player / resign_player) carry 'nay'; hire_coach and the
    # ranked ballots are always 'yea'. Existing rows default to 'yea'.
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="yea")
    # Optional JSON payload for vote types that need structured data beyond a
    # single target_player_id — e.g. draft_rookie carries the ranked ballot here.
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    total_votes: Mapped[int] = mapped_column(Integer, nullable=False)  # 'yea' (for) count
    votes_against: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 'nay' count; net = total_votes - votes_against
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
    # Fan's preferred order to fill open slots once all voted players are taken
    # (JSON array of position values 1-5). NULL = no preference.
    position_priority: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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


class AwardVote(Base):
    """Fan vote for a league-wide season award (MVP / Hall of Fame).

    League-wide, so unlike GmVote there is no team_id. Single net vote per
    (user, award_type, target_player) — withdraw to change. MVP is a single
    pick per user (one row); HoF is approval (one 'yea' row per approved
    player). See docs/AWARDS_VOTING_PLAN.md.
    """
    __tablename__ = "award_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    award_type: Mapped[str] = mapped_column(String(8), nullable=False)  # 'mvp' | 'hof'
    target_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    target_player: Mapped["Player"] = relationship("Player")

    __table_args__ = (
        # MVP: one pick per user per season (enforced in the repo by replacing).
        # HoF: at most one approval per (user, player) per season.
        UniqueConstraint("user_id", "season", "award_type", "target_player_id",
                         name="uq_award_vote"),
        Index("idx_award_votes_season_type", "season", "award_type"),
        Index("idx_award_votes_user_season", "user_id", "season"),
    )

    def __repr__(self):
        return (f"<AwardVote(user={self.user_id}, season={self.season}, "
                f"type='{self.award_type}', player={self.target_player_id})>")


class HofBallotEntry(Base):
    """Rolling Hall of Fame ballot state for one player across seasons.

    Seeded the season a qualifying player retires; carries forward each
    offseason until inducted, dropped (tenure exhausted), and re-runs the vote
    each year. See docs/AWARDS_VOTING_PLAN.md.
    """
    __tablename__ = "hof_ballot_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    first_eligible_season: Mapped[int] = mapped_column(Integer, nullable=False)
    seasons_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'on_ballot' | 'inducted' | 'dropped'
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="on_ballot")
    inducted_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    player: Mapped["Player"] = relationship("Player")

    __table_args__ = (
        UniqueConstraint("player_id", name="uq_hof_ballot_player"),
        Index("idx_hof_ballot_status", "status"),
    )

    def __repr__(self):
        return (f"<HofBallotEntry(player={self.player_id}, "
                f"status='{self.status}', left={self.seasons_remaining})>")


class PlayoffBracket(Base):
    """A user's playoff bracket-challenge entry for a season.

    predictions JSON: {round_key: [teamId,...]} — teams the user picks to
    advance PAST each round (round1 / round2 / league_championship /
    floosbowl). The floosbowl list's single team is the predicted champion.
    Scored per-advancer (see playoff_bracket.scoreBracket). One per user/season.
    """
    __tablename__ = "playoff_brackets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    predictions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON {round_key: [teamId,...]}
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "season", name="uq_playoff_bracket_user_season"),
        Index("idx_playoff_brackets_season", "season"),
    )

    def __repr__(self):
        return f"<PlayoffBracket(user={self.user_id}, season={self.season}, points={self.points})>"


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
    underdog_multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    points_earned: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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


class FollowedPlayer(Base):
    """Per-user watchlist — players the user has chosen to follow.

    Drives the Players page 'Followed' filter and surfaces those players'
    personality/off-day lines in the highlight feed alongside the user's
    favorite team and fantasy roster.
    """
    __tablename__ = "followed_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "player_id", name="uq_followed_player_user"),
        Index("idx_followed_players_user", "user_id"),
    )

    def __repr__(self):
        return f"<FollowedPlayer(user={self.user_id}, player={self.player_id})>"


class Achievement(Base):
    """Achievement template — static definition of an unlockable goal."""
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # programmatic lookup (e.g. "rookie", "prognosticator")
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # display name
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # onboarding, guidance
    scope: Mapped[str] = mapped_column(String(20), default="once", nullable=False)  # "once" | "per_season"
    target: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # progress needed to complete
    reward_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # {floobits, packs:[slug], powerups:[slug], deferred}
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Achievement(key='{self.key}', name='{self.name}', scope='{self.scope}')>"


class UserAchievement(Base):
    """Per-user progress and completion state for an achievement.
    season=0 for one-time ('once' scope) achievements; per_season achievements store
    the season they were earned for, so users can re-earn them each year."""
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id: Mapped[int] = mapped_column(Integer, ForeignKey("achievements.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # when reward actually granted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    achievement: Mapped["Achievement"] = relationship("Achievement")

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", "season", name="uq_user_achievement_season"),
        Index("idx_user_achievements_user", "user_id"),
        Index("idx_user_achievements_achievement", "achievement_id"),
    )

    def __repr__(self):
        return f"<UserAchievement(user={self.user_id}, achievement={self.achievement_id}, season={self.season}, progress={self.progress}, completed={self.completed_at is not None})>"


class PendingReward(Base):
    """A pack or powerup owed to a user. Created on achievement completion (or other grants).
    Claimed via a dedicated endpoint — packs open like a regular pack, powerups activate as ShopPurchases.
    available_at lets us defer rewards by timestamp (legacy). defer_until_season lets the
    user choose to hold a pack reward until a future season — the claim endpoint blocks
    until current season >= defer_until_season."""
    __tablename__ = "pending_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "pack" | "powerup"
    slug: Mapped[str] = mapped_column(String(30), nullable=False)  # pack name or powerup slug ("random" allowed)
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "achievement:prognosticator"
    available_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    defer_until_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_pending_rewards_user_claimed", "user_id", "claimed_at"),
    )

    def __repr__(self):
        return f"<PendingReward(user={self.user_id}, {self.kind}={self.slug}, claimed={self.claimed_at is not None})>"


class AppSetting(Base):
    """Key-value app settings editable by admins at runtime.
    Used for things like the feedback button URL/visibility and the active
    survey link — anything we want to flip without a redeploy."""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AppSetting({self.key}={self.value!r})>"


# ─── Anomaly system ─────────────────────────────────────────────────────────
# User-attention-driven simulation-criticality layer. Players accumulate
# "attention" from being equipped on cards, rostered in fantasy, followed,
# etc. Past a threshold they enter a state ladder (stirring → erratic →
# rampant → awakened). At awakened, they roll a signature ability that
# fires in games. League-wide attention drives the Thinning event — one or
# two rounds where anomalies spike league-wide. After a Thinning the Cores
# fire a Reset which may purge awakened players permanently.


class PlayerAttention(Base):
    """Per-player per-season rolling attention score.

    Mutated by the weekly aggregation tick. Decays 10%/week absent input.
    Excess past the soft cap (100) accumulates into ``over_cap_carry``
    which flows into the league aggregate toward the Thinning threshold.
    """
    __tablename__ = "player_attention"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    over_cap_carry: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    peak_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship("Player")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='_player_attention_season_uc'),
        Index('idx_attention_season_score', 'season', 'score'),
    )

    def __repr__(self):
        return f"<PlayerAttention(player={self.player_id}, season={self.season}, score={self.score:.1f})>"


class AnomalyState(Base):
    """Per-player per-season state on the anomaly ladder.

    Created when a player first crosses to stirring. State transitions
    happen during the weekly tick. ``awakened`` is sticky — once reached,
    the player stays awakened until purged in a Reset, even if their
    attention later decays below the threshold.
    """
    __tablename__ = "anomaly_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'stable' | 'stirring' | 'erratic' | 'rampant' | 'awakened' | 'cleansed'
    state: Mapped[str] = mapped_column(String(16), default='stable', nullable=False)
    # Ability slug — only populated once the player has awakened. (Legacy single-ability stub;
    # the L4 powers model uses offensive_ability/defensive_ability below.)
    ability: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    # 'tremor' | 'disturbance' | 'breach' | 'singularity'
    ability_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # L4 signature abilities (docs/AWAKENED_POWERS_PLAN.md) — one fixed key per side, assigned once
    # at awakening (managers/awakenedPowers.py catalog). defensive_ability is null for kickers.
    # Only populated when ANOMALY_AWAKENED_POWERS_ENABLED.
    offensive_ability: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    defensive_ability: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    awakened_at_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # How many seasons this player has carried an ability forward.
    # Drives end-of-season tier decay.
    seasons_carried: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_purged_season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship("Player")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='_anomaly_state_season_uc'),
        Index('idx_anomaly_state_season_state', 'season', 'state'),
    )

    def __repr__(self):
        return f"<AnomalyState(player={self.player_id}, s={self.season}, state={self.state}, ability={self.ability})>"


class LeagueAnomalyState(Base):
    """Singleton-per-season row tracking league-wide anomaly aggregate.

    Aggregate is computed each weekly tick as sum of over-cap attention
    across all players plus recent anomaly activity plus baseline pressure.
    When it crosses ``threshold`` (randomized per season, hidden from users)
    the Thinning fires.
    """
    __tablename__ = "league_anomaly_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    aggregate_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Hidden threshold for this season. Randomized in 600-1200 range.
    threshold: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    # How many Thinnings have fired this season.
    thinnings_this_season: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_thinning_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_reset_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Week through which the post-Reset suppression dampener is in effect.
    suppression_window_ends_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Last (season, week) the weekly tick processed. weeklyTick is NOT idempotent
    # — it re-adds the week's attention contributions on every call — so this
    # guards against a mid-week restart re-running it and double-counting.
    last_tick_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Audit trail of every Core-issued rule patch this season (mirrors
    # GameRules.patchHistory but persisted). Each entry includes the Core
    # responsible, the news-text payload, the field touched, and old/new.
    cores_patches_applied: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LeagueAnomalyState(season={self.season}, agg={self.aggregate_score:.1f}/{self.threshold})>"


class LeagueNewsItem(Base):
    """Persisted league-news feed item — Cores voice lines and anomaly state
    transitions. WebSocket events for these are ephemeral; this table is the
    fetch-on-load source for users who weren't connected when they fired.

    Categories:
        'cores'              — voice line from one of the Cores
        'anomaly_transition' — player crossed into stirring/erratic/rampant/awakened
    """
    __tablename__ = "league_news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Attribution (Cores items)
    core: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    core_display_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    # Attribution (anomaly transitions)
    player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    player_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    anomaly_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Exchange threading — set when this item is one turn of a multi-Core
    # conversation, so the feed can group the turns under a single header on
    # refresh (not just live over WS).
    exchange_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    turn_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    turn_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_league_news_season_week', 'season', 'week'),
        Index('idx_league_news_created', 'created_at'),
    )

    def __repr__(self):
        return f"<LeagueNewsItem(s={self.season}w{self.week} {self.category}/{self.event_type})>"


class AnomalyEvent(Base):
    """Every fired anomaly — universal micro-glitch, personality-keyed, or
    signature ability — logged for analytics, replay, and audit.

    Powers the highlights feed's glitch markers and feeds the player-profile
    'Recent Anomalies' surface. In-memory ring buffer for hot reads, DB row
    for persistence.
    """
    __tablename__ = "anomaly_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    game_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    play_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 'micro' | 'personality' | 'signature'
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    # Ability slug — only set when layer='signature'.
    ability: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    # The glitch-flavored line that surfaced in the play feed.
    play_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Whether this fired during a Thinning round (boosted intensity).
    during_thinning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship("Player")

    __table_args__ = (
        Index('idx_anomaly_event_season_week', 'season', 'week'),
        Index('idx_anomaly_event_player', 'player_id'),
    )

    def __repr__(self):
        return f"<AnomalyEvent(player={self.player_id}, layer={self.layer}, ability={self.ability})>"


class RuleVoteWindow(Base):
    """One Cores rule-change vote window per (season, game day).

    A row is recorded for EVERY game day we process (fired or not) so the daily
    escalation roll is idempotent on restart. When fired=True the window holds a
    live vote: kind ('change'=Aris / 'revert'=Pyre), the offered candidate field
    keys, the Core's stored conversation lines, and (once resolved) the winner.
    See docs/RULE_CHANGES_PLAN.md.
    """
    __tablename__ = "rule_vote_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-3 (weeks 1/8/15/22)
    fired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kind: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # 'change' | 'revert'
    core: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # 'aris' | 'pyre'
    option_keys: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of field keys
    prompt_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    react_pick_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    react_none_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    winner_key: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # field key | 'none'
    # The applied change (JSON-encoded so bool/float/int round-trip) — the value the
    # winning field held just before vs after resolution. Drives the Rulebook pill.
    winner_prev: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    winner_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("season", "day_index", name="uq_rule_vote_window"),
        Index("idx_rule_vote_windows_season", "season"),
    )

    def __repr__(self):
        return (f"<RuleVoteWindow(season={self.season}, day={self.day_index}, "
                f"fired={self.fired}, kind={self.kind}, resolved={self.resolved})>")


class RuleVote(Base):
    """A user's single pick in a rule-change vote window (free, changeable).

    One row per (user, window); the pick is 'none' or a candidate field key.
    See docs/RULE_CHANGES_PLAN.md.
    """
    __tablename__ = "rule_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    window_id: Mapped[int] = mapped_column(Integer, ForeignKey("rule_vote_windows.id"), nullable=False)
    option_key: Mapped[str] = mapped_column(String(40), nullable=False)  # 'none' | field key
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "window_id", name="uq_rule_vote"),
        Index("idx_rule_votes_window", "window_id"),
    )

    def __repr__(self):
        return f"<RuleVote(user={self.user_id}, window={self.window_id}, pick='{self.option_key}')>"
