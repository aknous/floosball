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
    _seedPackTypes()
    _seedBetaAllowlist()
    print(f"Database initialized at {DB_PATH}")


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
