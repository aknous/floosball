"""Database connection and session management."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from .models import Base

# Database file path — configurable via DATABASE_DIR env var (for Fly.io volume mount)
_defaultDbDir = Path(__file__).parent.parent / "data"
DB_DIR = Path(os.environ.get('DATABASE_DIR', str(_defaultDbDir)))
DB_PATH = DB_DIR / "floosball.db"
DB_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(
    DB_URL,
    echo=False,  # Set to True for SQL debugging
    future=True,
    connect_args={
        "timeout": 5,  # Timeout for busy database
        "check_same_thread": False  # Allow multiple threads (needed for async)
    }
)

# Enable WAL mode for better concurrent access
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
    cursor.close()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def init_db():
    """Initialize the database by creating all tables."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _runPendingMigrations()
    _seedPackTypes()
    _seedBetaAllowlist()
    print(f"Database initialized at {DB_PATH}")


def _runPendingMigrations():
    """Apply schema changes that create_all() can't handle (new columns on existing tables)."""
    from sqlalchemy import text
    conn = engine.connect()
    try:
        # Season award columns (v0.7)
        for col, colDef in [
            ('mvp_player_id', 'INTEGER REFERENCES players(id)'),
            ('all_pro_player_ids', 'TEXT'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE seasons ADD COLUMN {col} {colDef}"))
                conn.commit()
                print(f"  Migration: added seasons.{col}")
            except Exception:
                conn.rollback()  # column already exists — ignore
    finally:
        conn.close()

    # One-time data backfill: reconstruct PlayerSeasonStats.team_id from GamePlayerStats
    _backfillPlayerSeasonTeamIds()


def _backfillPlayerSeasonTeamIds():
    """Fill in NULL team_id on player_season_stats using game_player_stats records.

    For each row with team_id IS NULL, find the team the player appeared on most
    frequently in that season's games. Idempotent — skips rows that already have a team_id.
    """
    from sqlalchemy import text
    conn = engine.connect()
    try:
        # Check if there are any rows to fix
        result = conn.execute(text(
            "SELECT COUNT(*) FROM player_season_stats WHERE team_id IS NULL"
        ))
        nullCount = result.scalar()
        if nullCount == 0:
            return

        print(f"  Backfill: fixing {nullCount} player_season_stats rows with NULL team_id")

        # For each NULL row, find the most common team_id from that player's game stats
        # in that season. Uses a correlated subquery with GROUP BY to pick the mode.
        conn.execute(text("""
            UPDATE player_season_stats
            SET team_id = (
                SELECT gps.team_id
                FROM game_player_stats gps
                JOIN games g ON gps.game_id = g.id
                WHERE gps.player_id = player_season_stats.player_id
                  AND g.season = player_season_stats.season
                GROUP BY gps.team_id
                ORDER BY COUNT(*) DESC
                LIMIT 1
            )
            WHERE team_id IS NULL
        """))
        conn.commit()

        # Report results
        result = conn.execute(text(
            "SELECT COUNT(*) FROM player_season_stats WHERE team_id IS NULL"
        ))
        remaining = result.scalar()
        fixed = nullCount - remaining
        print(f"  Backfill: fixed {fixed} rows, {remaining} still NULL (no game data)")
    except Exception as e:
        conn.rollback()
        print(f"  Backfill warning: {e}")
    finally:
        conn.close()


def clear_db():
    """Clear game/simulation data while preserving user accounts and beta allowlist.

    Drops and recreates non-preserved tables so schema changes (new columns,
    altered types) are picked up — SQLAlchemy create_all() skips existing tables.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)

    # Tables to preserve across fresh starts
    preserveTables = {"users", "beta_allowlist"}

    # Drop all non-preserved tables (reverse dependency order), then recreate
    tablesToDrop = [t for t in reversed(Base.metadata.sorted_tables)
                    if t.name not in preserveTables]
    if tablesToDrop:
        Base.metadata.drop_all(bind=engine, tables=tablesToDrop)

    # Recreate all tables (create_all is safe — skips existing preserved tables)
    Base.metadata.create_all(bind=engine)
    print(f"Database cleared (preserved {', '.join(preserveTables)}) at {DB_PATH}")

    _seedPackTypes()
    _seedBetaAllowlist()


def _seedPackTypes():
    """Seed default pack types if they don't exist."""
    from database.repositories.card_repositories import PackTypeRepository
    session = SessionLocal()
    try:
        repo = PackTypeRepository(session)
        repo.seedDefaults()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _seedBetaAllowlist():
    """Seed beta allowlist emails from config if they don't already exist."""
    from database.models import BetaAllowlist
    from sqlalchemy import func
    try:
        from config_manager import get_config
        emails = get_config().get("betaAllowlist", [])
    except Exception:
        return
    if not emails:
        return
    session = SessionLocal()
    try:
        for email in emails:
            normalizedEmail = email.lower().strip()
            exists = session.query(BetaAllowlist).filter(
                func.lower(BetaAllowlist.email) == normalizedEmail
            ).first()
            if not exists:
                session.add(BetaAllowlist(email=normalizedEmail))
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def clear_card_data():
    """Clear all card-related data while preserving everything else.

    Used when deploying card system changes that require regeneration
    of templates (e.g., new drop rates, classification rules).
    Preserves players, teams, seasons, games, users, fantasy rosters, etc.
    """
    from .models import (
        CardTemplate, UserCard, EquippedCard, WeeklyCardBonus,
        CardUpgradeLog, PackOpening, FeaturedShopCard,
        WeeklyModifier, UserModifierOverride,
    )

    session = SessionLocal()
    try:
        # Delete in reverse dependency order
        session.query(WeeklyCardBonus).delete()
        session.query(CardUpgradeLog).delete()
        session.query(PackOpening).delete()
        session.query(FeaturedShopCard).delete()
        session.query(UserModifierOverride).delete()
        session.query(WeeklyModifier).delete()
        session.query(EquippedCard).delete()
        session.query(UserCard).delete()
        session.query(CardTemplate).delete()
        session.commit()
        print("Card data cleared — templates will regenerate on season start")
    except Exception as e:
        session.rollback()
        print(f"Error clearing card data: {e}")
        raise
    finally:
        session.close()


def get_session() -> Session:
    """Get a new database session.
    
    Usage:
        session = get_session()
        try:
            # Use session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    """
    return SessionLocal()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations.
    
    Usage:
        with session_scope() as session:
            # Use session
            session.add(obj)
            # Automatically commits on success, rolls back on exception
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_stats():
    """Get database statistics."""
    from sqlalchemy import inspect, func
    from .models import (
        League, Team, Player, PlayerAttributes, PlayerCareerStats,
        TeamSeasonStats, Game, GamePlayerStats, Season, Record, UnusedName
    )
    
    session = get_session()
    try:
        stats = {
            "leagues": session.query(func.count(League.id)).scalar(),
            "teams": session.query(func.count(Team.id)).scalar(),
            "players": session.query(func.count(Player.id)).scalar(),
            "player_attributes": session.query(func.count(PlayerAttributes.player_id)).scalar(),
            "player_career_stats": session.query(func.count(PlayerCareerStats.id)).scalar(),
            "team_season_stats": session.query(func.count(TeamSeasonStats.id)).scalar(),
            "games": session.query(func.count(Game.id)).scalar(),
            "game_player_stats": session.query(func.count(GamePlayerStats.id)).scalar(),
            "seasons": session.query(func.count(Season.season_number)).scalar(),
            "records": session.query(func.count(Record.id)).scalar(),
            "unused_names": session.query(func.count(UnusedName.id)).scalar(),
        }
        return stats
    finally:
        session.close()


def clear_database():
    """Clear all data from database (for fresh start).
    
    This is useful for testing or when regenerating all data.
    Preserves the schema, just deletes all records.
    """
    from .models import (
        GamePlayerStats, Game, PlayerCareerStats, PlayerAttributes, 
        Player, TeamSeasonStats, Team, League, Season, Record, UnusedName
    )
    
    session = get_session()
    try:
        # Delete in reverse dependency order
        session.query(GamePlayerStats).delete()
        session.query(Game).delete()
        session.query(PlayerCareerStats).delete()
        session.query(PlayerAttributes).delete()
        session.query(Player).delete()
        session.query(TeamSeasonStats).delete()
        session.query(Team).delete()
        session.query(League).delete()
        session.query(Season).delete()
        session.query(Record).delete()
        session.query(UnusedName).delete()
        
        session.commit()
        print("Database cleared successfully")
    except Exception as e:
        session.rollback()
        print(f"Error clearing database: {e}")
        raise
    finally:
        session.close()
