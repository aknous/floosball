"""Database connection and session management."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from .models import Base
from logger_config import get_logger

logger = get_logger("floosball.database")

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
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
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
    logger.info(f"Database initialized at {DB_PATH}")


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
                logger.info(f"  Migration: added seasons.{col}")
            except Exception:
                conn.rollback()  # column already exists — ignore

        # Email preference columns on users (v0.7.1)
        for col in ['email_day_report', 'email_season_report']:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT 1"))
                conn.commit()
                logger.info(f"  Migration: added users.{col}")
            except Exception:
                conn.rollback()

        # Fatigue + funding preference columns (v0.8)
        try:
            conn.execute(text("ALTER TABLE player_attributes ADD COLUMN fatigue REAL DEFAULT 0.0"))
            conn.commit()
            logger.info("  Migration: added player_attributes.fatigue")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN team_funding_pct INTEGER DEFAULT 25"))
            conn.commit()
            logger.info("  Migration: added users.team_funding_pct")
        except Exception:
            conn.rollback()

        # Team funding breakdown columns (v0.8) — clear old records and re-add columns
        try:
            # Check if new columns already exist
            result = conn.execute(text("PRAGMA table_info(team_funding)"))
            existingCols = {row[1] for row in result}
            if 'baseline_funding' not in existingCols:
                # Old funding records are incompatible — clear and re-add columns
                conn.execute(text("DELETE FROM team_funding"))
                conn.commit()
                logger.info("  Migration: cleared old team_funding records (schema change)")
                for col, colDef in [
                    ('baseline_funding', 'INTEGER DEFAULT 0'),
                    ('fan_contributions', 'INTEGER DEFAULT 0'),
                ]:
                    try:
                        conn.execute(text(f"ALTER TABLE team_funding ADD COLUMN {col} {colDef}"))
                        conn.commit()
                        logger.info(f"  Migration: added team_funding.{col}")
                    except Exception:
                        conn.rollback()
        except Exception:
            conn.rollback()

        # Demeanor column on player_attributes (v0.8)
        try:
            conn.execute(text("ALTER TABLE player_attributes ADD COLUMN demeanor VARCHAR(20)"))
            conn.commit()
            logger.info("  Migration: added player_attributes.demeanor")
        except Exception:
            conn.rollback()

        # Archetype + quirk columns on player_attributes (personality system)
        for col, colDef in [
            ('archetype', 'VARCHAR(30)'),
            ('quirk', 'VARCHAR(30)'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE player_attributes ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added player_attributes.{col}")
            except Exception:
                conn.rollback()

        # Ensure denormalized stat columns exist on player_season_stats
        # (create_all only creates tables, doesn't add columns to existing ones)
        for tbl, cols in [
            ('player_season_stats', [
                ('passing_yards', 'INTEGER DEFAULT 0'), ('passing_tds', 'INTEGER DEFAULT 0'),
                ('passing_ints', 'INTEGER DEFAULT 0'), ('passing_completions', 'INTEGER DEFAULT 0'),
                ('passing_attempts', 'INTEGER DEFAULT 0'),
                ('rushing_yards', 'INTEGER DEFAULT 0'), ('rushing_tds', 'INTEGER DEFAULT 0'),
                ('rushing_attempts', 'INTEGER DEFAULT 0'),
                ('receiving_yards', 'INTEGER DEFAULT 0'), ('receiving_tds', 'INTEGER DEFAULT 0'),
                ('receptions', 'INTEGER DEFAULT 0'),
                ('sacks', 'INTEGER DEFAULT 0'), ('interceptions', 'INTEGER DEFAULT 0'),
                ('tackles', 'INTEGER DEFAULT 0'),
            ]),
            ('player_career_stats', [
                ('passing_yards', 'INTEGER DEFAULT 0'), ('passing_tds', 'INTEGER DEFAULT 0'),
                ('passing_ints', 'INTEGER DEFAULT 0'),
                ('rushing_yards', 'INTEGER DEFAULT 0'), ('rushing_tds', 'INTEGER DEFAULT 0'),
                ('receiving_yards', 'INTEGER DEFAULT 0'), ('receiving_tds', 'INTEGER DEFAULT 0'),
            ]),
        ]:
            for col, colDef in cols:
                try:
                    conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {colDef}"))
                    conn.commit()
                    logger.info(f"  Migration: added {tbl}.{col}")
                except Exception:
                    conn.rollback()
    finally:
        conn.close()

    # Refresh stale effect_config text on reworked card effects
    _refreshCardEffectText()

    # One-time data backfills: reconstruct missing data from GamePlayerStats
    _backfillPlayerSeasonTeamIds()
    _backfillPlayerSeasonStatsFromGames()
    _backfillPlayerCareerStatsFromGames()


def _refreshCardEffectText():
    """Update stale tooltip/detail text on card templates whose effects were reworked."""
    import json as _json
    from managers.cardEffects import EFFECT_TOOLTIPS, EFFECT_DETAIL_TEMPLATES
    from sqlalchemy import text

    # Map of effectName → fields to refresh from current definitions
    refreshEffects = {"odometer"}

    conn = engine.connect()
    try:
        rows = conn.execute(text("SELECT id, effect_config FROM card_templates")).fetchall()
        updated = 0
        for row in rows:
            cfg = _json.loads(row[1]) if isinstance(row[1], str) else row[1]
            effectName = cfg.get("effectName", "")
            if effectName not in refreshEffects:
                continue
            currentTooltip = EFFECT_TOOLTIPS.get(effectName, "")
            currentDetail = EFFECT_DETAIL_TEMPLATES.get(effectName, "")
            if cfg.get("tooltip") == currentTooltip and cfg.get("detail") == currentDetail:
                continue
            cfg["tooltip"] = currentTooltip
            cfg["detail"] = currentDetail
            conn.execute(
                text("UPDATE card_templates SET effect_config = :cfg WHERE id = :id"),
                {"cfg": _json.dumps(cfg), "id": row[0]},
            )
            updated += 1
        if updated:
            conn.commit()
            logger.info(f"  Migration: refreshed effect text on {updated} card templates")
        else:
            conn.rollback()
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Migration: failed to refresh card effect text: {e}")
    finally:
        conn.close()


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

        logger.info(f"  Backfill: fixing {nullCount} player_season_stats rows with NULL team_id")

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
        logger.info(f"  Backfill: fixed {fixed} rows, {remaining} still NULL (no game data)")
    except Exception as e:
        conn.rollback()
        logger.info(f"  Backfill warning: {e}")
    finally:
        conn.close()


def _backfillPlayerSeasonStatsFromGames():
    """Reconstruct player_season_stats JSON columns from game_player_stats.

    For rows where all stat JSON columns are NULL (stats were zeroed before save),
    aggregate per-game stats from game_player_stats to rebuild season totals.
    Idempotent — skips rows that already have non-NULL passing_stats.
    """
    import json as _json
    from sqlalchemy import text
    conn = engine.connect()
    try:
        # Diagnostic: count game_player_stats rows to verify data exists
        gpsCount = conn.execute(text("SELECT COUNT(*) FROM game_player_stats")).fetchone()[0]
        logger.info(f"  Backfill diagnostic: game_player_stats has {gpsCount} rows")
        if gpsCount > 0:
            sampleRow = conn.execute(text(
                "SELECT passing_stats, rushing_stats FROM game_player_stats "
                "WHERE passing_stats IS NOT NULL LIMIT 1"
            )).fetchone()
            logger.info(f"  Backfill diagnostic: sample passing_stats = {str(sampleRow[0])[:100] if sampleRow else 'NO ROWS WITH DATA'}")

        # Find season stats rows where all denormalized stat columns are zero or NULL
        # but the player has game data (meaning the stats were zeroed by the save bug)
        result = conn.execute(text(
            "SELECT pss.id, pss.player_id, pss.season FROM player_season_stats pss "
            "WHERE COALESCE(pss.passing_yards, 0) = 0 AND COALESCE(pss.rushing_yards, 0) = 0 "
            "  AND COALESCE(pss.receiving_yards, 0) = 0 AND COALESCE(pss.sacks, 0) = 0 "
            "  AND EXISTS ("
            "    SELECT 1 FROM game_player_stats gps "
            "    JOIN games g ON gps.game_id = g.id "
            "    WHERE gps.player_id = pss.player_id AND g.season = pss.season"
            "  )"
        ))
        emptyRows = result.fetchall()
        if not emptyRows:
            # Log why we found nothing — check total rows and their state
            totalPss = conn.execute(text("SELECT COUNT(*) FROM player_season_stats")).fetchone()[0]
            samplePss = conn.execute(text(
                "SELECT passing_yards, rushing_yards, receiving_yards, passing_stats "
                "FROM player_season_stats LIMIT 1"
            )).fetchone()
            logger.info(f"  Backfill: no empty rows found. Total PSS rows: {totalPss}")
            if samplePss:
                logger.info(f"  Backfill: sample PSS row: passing_yards={samplePss[0]}, rushing_yards={samplePss[1]}, "
                      f"receiving_yards={samplePss[2]}, passing_stats={str(samplePss[3])[:80]}")
            return

        logger.info(f"  Backfill: reconstructing stats for {len(emptyRows)} player_season_stats rows")
        fixed = 0

        for rowId, playerId, season in emptyRows:
            # Get all game stats for this player in this season
            gameRows = conn.execute(text(
                "SELECT gps.passing_stats, gps.rushing_stats, gps.receiving_stats, "
                "       gps.kicking_stats, gps.defense_stats, gps.fantasy_points "
                "FROM game_player_stats gps "
                "JOIN games g ON gps.game_id = g.id "
                "WHERE gps.player_id = :pid AND g.season = :season"
            ), {"pid": playerId, "season": season}).fetchall()

            if not gameRows:
                continue

            # Aggregate stats across games
            passing = {}
            rushing = {}
            receiving = {}
            kicking = {}
            defense = {}
            totalFp = 0
            gamesPlayed = len(gameRows)

            for gPassing, gRushing, gReceiving, gKicking, gDefense, gFp in gameRows:
                totalFp += gFp or 0
                for src, dest in [
                    (gPassing, passing), (gRushing, rushing),
                    (gReceiving, receiving), (gKicking, kicking), (gDefense, defense)
                ]:
                    if src:
                        d = _json.loads(src) if isinstance(src, str) else src
                        for k, v in d.items():
                            if isinstance(v, (int, float)):
                                dest[k] = dest.get(k, 0) + v

            # Recompute derived stats
            if passing.get('att', 0) > 0:
                passing['compPerc'] = round(passing.get('comp', 0) / passing['att'] * 100, 1)
                passing['ypc'] = round(passing.get('yards', 0) / passing['att'], 1)
            if rushing.get('carries', 0) > 0:
                rushing['ypc'] = round(rushing.get('yards', 0) / rushing['carries'], 1)
            if receiving.get('receptions', 0) > 0:
                receiving['ypr'] = round(receiving.get('yards', 0) / receiving['receptions'], 1)
            if receiving.get('targets', 0) > 0:
                receiving['rcvPerc'] = round(receiving.get('receptions', 0) / receiving['targets'] * 100, 1)
            if kicking.get('fgAtt', 0) > 0:
                kicking['fgPerc'] = round(kicking.get('fgs', 0) / kicking['fgAtt'] * 100, 1)

            # Update the row
            sPassing = passing.get('yards', 0)
            conn.execute(text(
                "UPDATE player_season_stats SET "
                "  passing_stats = :passing, rushing_stats = :rushing, "
                "  receiving_stats = :receiving, kicking_stats = :kicking, "
                "  defense_stats = :defense, fantasy_points = :fp, "
                "  games_played = :gp, "
                "  passing_yards = :pyards, passing_tds = :ptds, passing_ints = :pints, "
                "  passing_completions = :pcomp, passing_attempts = :patt, "
                "  rushing_yards = :ryards, rushing_tds = :rtds, rushing_attempts = :ratt, "
                "  receiving_yards = :recyards, receiving_tds = :rectds, receptions = :rec, "
                "  sacks = :sacks, interceptions = :dints, tackles = :tackles "
                "WHERE id = :id"
            ), {
                "passing": _json.dumps(passing) if passing else None,
                "rushing": _json.dumps(rushing) if rushing else None,
                "receiving": _json.dumps(receiving) if receiving else None,
                "kicking": _json.dumps(kicking) if kicking else None,
                "defense": _json.dumps(defense) if defense else None,
                "fp": totalFp, "gp": gamesPlayed, "id": rowId,
                "pyards": passing.get('yards', 0), "ptds": passing.get('tds', 0),
                "pints": passing.get('ints', 0), "pcomp": passing.get('comp', 0),
                "patt": passing.get('att', 0),
                "ryards": rushing.get('yards', 0), "rtds": rushing.get('tds', 0),
                "ratt": rushing.get('carries', 0),
                "recyards": receiving.get('yards', 0), "rectds": receiving.get('tds', 0),
                "rec": receiving.get('receptions', 0),
                "sacks": defense.get('sacks', 0), "dints": defense.get('ints', 0),
                "tackles": defense.get('tackles', 0),
            })
            fixed += 1

        conn.commit()
        logger.info(f"  Backfill: reconstructed stats for {fixed} rows from game data")
    except Exception as e:
        conn.rollback()
        logger.info(f"  Backfill warning (stats): {e}")
    finally:
        conn.close()


def _backfillPlayerCareerStatsFromGames():
    """Reconstruct player_career_stats (season=0 career totals) from game_player_stats.

    For rows where all denormalized stat columns are zero but the player has game data,
    aggregate all games across all seasons to rebuild career totals.
    Also creates missing career rows for players that have game data but no career row.
    """
    import json as _json
    from sqlalchemy import text
    conn = engine.connect()
    try:
        # Find players with game data but zeroed/NULL or missing career stats
        result = conn.execute(text(
            "SELECT DISTINCT gps.player_id FROM game_player_stats gps "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM player_career_stats pcs "
            "  WHERE pcs.player_id = gps.player_id AND pcs.season = 0 "
            "    AND (COALESCE(pcs.passing_yards, 0) > 0 OR COALESCE(pcs.rushing_yards, 0) > 0 "
            "         OR COALESCE(pcs.receiving_yards, 0) > 0)"
            ")"
        ))
        playerIds = [row[0] for row in result.fetchall()]
        if not playerIds:
            return

        logger.info(f"  Backfill: reconstructing career stats for {len(playerIds)} players")
        fixed = 0

        for playerId in playerIds:
            # Aggregate ALL game stats across ALL seasons
            gameRows = conn.execute(text(
                "SELECT gps.passing_stats, gps.rushing_stats, gps.receiving_stats, "
                "       gps.kicking_stats, gps.defense_stats, gps.fantasy_points "
                "FROM game_player_stats gps "
                "JOIN games g ON gps.game_id = g.id "
                "WHERE gps.player_id = :pid AND g.is_playoff = 0"
            ), {"pid": playerId}).fetchall()

            if not gameRows:
                continue

            passing = {}
            rushing = {}
            receiving = {}
            kicking = {}
            defense = {}
            totalFp = 0
            gamesPlayed = len(gameRows)

            for gPassing, gRushing, gReceiving, gKicking, gDefense, gFp in gameRows:
                totalFp += gFp or 0
                for src, dest in [
                    (gPassing, passing), (gRushing, rushing),
                    (gReceiving, receiving), (gKicking, kicking), (gDefense, defense)
                ]:
                    if src:
                        d = _json.loads(src) if isinstance(src, str) else src
                        for k, v in d.items():
                            if isinstance(v, (int, float)):
                                dest[k] = dest.get(k, 0) + v

            # Recompute derived stats
            if passing.get('att', 0) > 0:
                passing['compPerc'] = round(passing.get('comp', 0) / passing['att'] * 100, 1)
                passing['ypc'] = round(passing.get('yards', 0) / passing['att'], 1)
            if rushing.get('carries', 0) > 0:
                rushing['ypc'] = round(rushing.get('yards', 0) / rushing['carries'], 1)
            if receiving.get('receptions', 0) > 0:
                receiving['ypr'] = round(receiving.get('yards', 0) / receiving['receptions'], 1)
            if receiving.get('targets', 0) > 0:
                receiving['rcvPerc'] = round(receiving.get('receptions', 0) / receiving['targets'] * 100, 1)
            if kicking.get('fgAtt', 0) > 0:
                kicking['fgPerc'] = round(kicking.get('fgs', 0) / kicking['fgAtt'] * 100, 1)

            # Check if career row exists
            existing = conn.execute(text(
                "SELECT id FROM player_career_stats WHERE player_id = :pid AND season = 0"
            ), {"pid": playerId}).fetchone()

            if existing:
                conn.execute(text(
                    "UPDATE player_career_stats SET "
                    "  passing_stats = :passing, rushing_stats = :rushing, "
                    "  receiving_stats = :receiving, kicking_stats = :kicking, "
                    "  defense_stats = :defense, fantasy_points = :fp, "
                    "  games_played = :gp, "
                    "  passing_yards = :pyards, passing_tds = :ptds, passing_ints = :pints, "
                    "  rushing_yards = :ryards, rushing_tds = :rtds, "
                    "  receiving_yards = :recyards, receiving_tds = :rectds "
                    "WHERE id = :id"
                ), {
                    "passing": _json.dumps(passing) if passing else None,
                    "rushing": _json.dumps(rushing) if rushing else None,
                    "receiving": _json.dumps(receiving) if receiving else None,
                    "kicking": _json.dumps(kicking) if kicking else None,
                    "defense": _json.dumps(defense) if defense else None,
                    "fp": totalFp, "gp": gamesPlayed, "id": existing[0],
                    "pyards": passing.get('yards', 0), "ptds": passing.get('tds', 0),
                    "pints": passing.get('ints', 0),
                    "ryards": rushing.get('yards', 0), "rtds": rushing.get('tds', 0),
                    "recyards": receiving.get('yards', 0), "rectds": receiving.get('tds', 0),
                })
            else:
                conn.execute(text(
                    "INSERT INTO player_career_stats "
                    "(player_id, season, games_played, fantasy_points, "
                    " passing_yards, passing_tds, passing_ints, rushing_yards, rushing_tds, "
                    " receiving_yards, receiving_tds, "
                    " passing_stats, rushing_stats, receiving_stats, kicking_stats, defense_stats) "
                    "VALUES (:pid, 0, :gp, :fp, :pyards, :ptds, :pints, :ryards, :rtds, "
                    "        :recyards, :rectds, :passing, :rushing, :receiving, :kicking, :defense)"
                ), {
                    "pid": playerId, "gp": gamesPlayed, "fp": totalFp,
                    "pyards": passing.get('yards', 0), "ptds": passing.get('tds', 0),
                    "pints": passing.get('ints', 0),
                    "ryards": rushing.get('yards', 0), "rtds": rushing.get('tds', 0),
                    "recyards": receiving.get('yards', 0), "rectds": receiving.get('tds', 0),
                    "passing": _json.dumps(passing) if passing else None,
                    "rushing": _json.dumps(rushing) if rushing else None,
                    "receiving": _json.dumps(receiving) if receiving else None,
                    "kicking": _json.dumps(kicking) if kicking else None,
                    "defense": _json.dumps(defense) if defense else None,
                })
            fixed += 1

        conn.commit()
        logger.info(f"  Backfill: reconstructed career stats for {fixed} players from game data")
    except Exception as e:
        conn.rollback()
        logger.info(f"  Backfill warning (career): {e}")
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
    logger.info(f"Database cleared (preserved {', '.join(preserveTables)}) at {DB_PATH}")

    # Run migrations for preserved tables (e.g. new columns on users)
    _runPendingMigrations()
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
        logger.info("Card data cleared — templates will regenerate on season start")
    except Exception as e:
        session.rollback()
        logger.info(f"Error clearing card data: {e}")
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
        logger.info("Database cleared successfully")
    except Exception as e:
        session.rollback()
        logger.info(f"Error clearing database: {e}")
        raise
    finally:
        session.close()
