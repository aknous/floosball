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
    _seedAchievements()
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

        # Admin flag (v0.9)
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added users.is_admin")
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

        # Q4 fantasy points on game_player_stats (v0.9)
        try:
            conn.execute(text("ALTER TABLE game_player_stats ADD COLUMN q4_fantasy_points INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added game_player_stats.q4_fantasy_points")
        except Exception:
            conn.rollback()

        # Discord linking columns (v0.9)
        # Note: SQLite doesn't support UNIQUE in ALTER TABLE ADD COLUMN,
        # so we add the column first, then create a unique index separately.
        for col, colDef in [
            ('discord_id', 'VARCHAR(30)'),
            ('discord_dm_reminders', 'BOOLEAN DEFAULT 0'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added users.{col}")
            except Exception:
                conn.rollback()
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_discord_id ON users(discord_id)"))
            conn.commit()
        except Exception:
            conn.rollback()

        # Pick-em underdog + auto-pick columns (v0.10)
        try:
            conn.execute(text("ALTER TABLE pick_em_picks ADD COLUMN underdog_multiplier REAL"))
            conn.commit()
            logger.info("  Migration: added pick_em_picks.underdog_multiplier")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE pick_em_picks ADD COLUMN is_auto BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added pick_em_picks.is_auto")
        except Exception:
            conn.rollback()

        # Achievement scope + per-season (v0.10)
        try:
            conn.execute(text("ALTER TABLE achievements ADD COLUMN scope VARCHAR(20) DEFAULT 'once' NOT NULL"))
            conn.commit()
            logger.info("  Migration: added achievements.scope")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE user_achievements ADD COLUMN season INTEGER DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added user_achievements.season")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE pending_rewards ADD COLUMN defer_until_season INTEGER"))
            conn.commit()
            logger.info("  Migration: added pending_rewards.defer_until_season")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE fantasy_rosters ADD COLUMN last_equipped_set_week INTEGER"))
            conn.commit()
            logger.info("  Migration: added fantasy_rosters.last_equipped_set_week")
        except Exception:
            conn.rollback()

        # Rename achievement keys that collided with existing card effect names:
        #   windfall_* → racket_*
        #   crescendo  → zenith
        try:
            renameMap = {
                "windfall_i": "racket_i",
                "windfall_ii": "racket_ii",
                "windfall_iii": "racket_iii",
                "windfall_iv": "racket_iv",
                "crescendo": "zenith",
            }
            totalRenamed = 0
            for oldKey, newKey in renameMap.items():
                # If the new key already exists (e.g. from a prior partial migration or fresh seed),
                # delete the stale row instead of renaming on top of it.
                exists = conn.execute(text(
                    "SELECT 1 FROM achievements WHERE key = :k LIMIT 1"
                ), {"k": newKey}).fetchone()
                if exists:
                    conn.execute(text(
                        "DELETE FROM achievements WHERE key = :k"
                    ), {"k": oldKey})
                else:
                    result = conn.execute(text(
                        "UPDATE achievements SET key = :new WHERE key = :old"
                    ), {"new": newKey, "old": oldKey})
                    if result.rowcount:
                        totalRenamed += result.rowcount
            if totalRenamed:
                conn.commit()
                logger.info(f"  Migration: renamed {totalRenamed} collided achievement keys")
            else:
                conn.rollback()
        except Exception as e:
            conn.rollback()
            logger.info(f"  Migration: achievement key rename skipped ({e})")
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN auto_pick_favorites BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added users.auto_pick_favorites")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN auto_pick_mode VARCHAR(20) DEFAULT 'off' NOT NULL"))
            conn.commit()
            logger.info("  Migration: added users.auto_pick_mode")
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

        # Prospect pipeline columns on players (feature/prospects-pipeline)
        for col, colDef in [
            ('is_prospect', 'BOOLEAN DEFAULT 0'),
            ('is_undrafted', 'BOOLEAN DEFAULT 0'),
            ('prospect_seasons', 'INTEGER DEFAULT 0'),
            ('drafting_team_id', 'INTEGER REFERENCES teams(id)'),
            ('is_upcoming_rookie', 'BOOLEAN DEFAULT 0'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE players ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added players.{col}")
            except Exception:
                conn.rollback()

        # Two-way player columns on players (v0.10 defense)
        for col, colDef in [
            ('offensive_rating', 'INTEGER'),
            ('defensive_rating', 'INTEGER'),
            ('defensive_position', 'VARCHAR(5)'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE players ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added players.{col}")
            except Exception:
                conn.rollback()

        # Defensive talent on player_attributes (v0.10 defense)
        try:
            conn.execute(text("ALTER TABLE player_attributes ADD COLUMN defensive_talent INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added player_attributes.defensive_talent")
        except Exception:
            conn.rollback()

        # New personality system: replace archetype/demeanor with personality + mood.
        # Old columns (archetype, demeanor) stay nullable in the schema for back-compat
        # on existing DBs but are unused; the new fields are personality + mood.
        for col, colDef in [('personality', 'VARCHAR(30)'), ('mood', 'INTEGER DEFAULT 3')]:
            try:
                conn.execute(text(f"ALTER TABLE player_attributes ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added player_attributes.{col}")
            except Exception:
                conn.rollback()

        # Rename 'easy' personality to 'chill'. Idempotent — UPDATE no-ops once done.
        try:
            result = conn.execute(text(
                "UPDATE player_attributes SET personality = 'chill' WHERE personality = 'easy'"
            ))
            if result.rowcount > 0:
                conn.commit()
                logger.info(f"  Migration: renamed 'easy' → 'chill' on {result.rowcount} player_attributes rows")
            else:
                conn.rollback()
        except Exception:
            conn.rollback()

        # Refresh detail/tooltip on existing double_down (Lemons) card templates
        # so they pick up the {rewardValue}x scaling text. Templates bake those
        # strings at creation time, so a wording change won't reach mid-season
        # cards without an explicit re-render.
        try:
            import json as _json
            from managers.cardEffects import EFFECT_DETAIL_TEMPLATES, EFFECT_TOOLTIPS
            rows = conn.execute(text(
                "SELECT id, effect_config FROM card_templates WHERE effect_config LIKE '%double_down%'"
            )).fetchall()
            updated = 0
            for row in rows:
                try:
                    cfg = _json.loads(row.effect_config) if row.effect_config else {}
                except Exception:
                    continue
                if cfg.get('effectName') != 'double_down':
                    continue
                primary = cfg.get('primary', {}) or {}
                detail = EFFECT_DETAIL_TEMPLATES.get('double_down', '')
                tooltip = EFFECT_TOOLTIPS.get('double_down', '')
                for k, v in primary.items():
                    placeholder = '{' + k + '}'
                    detail = detail.replace(placeholder, str(v))
                    tooltip = tooltip.replace(placeholder, str(v))
                if detail == cfg.get('detail') and tooltip == cfg.get('tooltip'):
                    continue
                cfg['detail'] = detail
                cfg['tooltip'] = tooltip
                conn.execute(
                    text("UPDATE card_templates SET effect_config = :cfg WHERE id = :id"),
                    {"cfg": _json.dumps(cfg), "id": row.id},
                )
                updated += 1
            if updated > 0:
                conn.commit()
                logger.info(f"  Migration: refreshed Lemons detail/tooltip on {updated} card_templates")
            else:
                conn.rollback()
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: Lemons template refresh skipped: {e}")

        # Coach scouting attribute (feature/prospects-pipeline Phase 7)
        try:
            conn.execute(text("ALTER TABLE coaches ADD COLUMN scouting INTEGER DEFAULT 80"))
            conn.commit()
            logger.info("  Migration: added coaches.scouting")
        except Exception:
            conn.rollback()

        # GmVote.details for structured payloads like ranked ballots (Phase 7)
        try:
            conn.execute(text("ALTER TABLE gm_votes ADD COLUMN details TEXT"))
            conn.commit()
            logger.info("  Migration: added gm_votes.details")
        except Exception:
            conn.rollback()

        # Vacancy fallback preference on users (feature/prospects-pipeline)
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN vacancy_auto_pick VARCHAR(20) DEFAULT 'best_available' NOT NULL"))
            conn.commit()
            logger.info("  Migration: added users.vacancy_auto_pick")
        except Exception:
            conn.rollback()

        # Offseason-in-progress checkpoint flag (feature/prospects-pipeline)
        # Protects against the "deploy during offseason → season replays on
        # restart" bug. Set True just before handleOffseason() runs, cleared
        # once seasonsPlayed has been advanced and saved.
        try:
            conn.execute(text("ALTER TABLE simulation_state ADD COLUMN in_offseason BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added simulation_state.in_offseason")
        except Exception:
            conn.rollback()

        # Retire the 'random' powerup slug on stashed achievement rewards.
        # Tycoon now grants income_boost; Veteran grants extra_swap. Map
        # existing 'random' rows by their achievement source so the user
        # gets the same powerup a freshly-earned reward would give.
        try:
            conn.execute(text(
                "UPDATE pending_rewards SET slug = 'income_boost' "
                "WHERE kind = 'powerup' AND slug = 'random' AND source = 'achievement:tycoon'"
            ))
            conn.execute(text(
                "UPDATE pending_rewards SET slug = 'extra_swap' "
                "WHERE kind = 'powerup' AND slug = 'random' AND source = 'achievement:veteran'"
            ))
            # Any remaining 'random' (unknown source) default to income_boost.
            conn.execute(text(
                "UPDATE pending_rewards SET slug = 'income_boost' "
                "WHERE kind = 'powerup' AND slug = 'random'"
            ))
            conn.commit()
            logger.info("  Migration: replaced 'random' powerup slugs in pending_rewards")
        except Exception:
            conn.rollback()

        # Big plays counter on team_season_stats — used by the Highlight
        # Reel card projection. Counts WPA-based big plays per team per
        # season so the per-game average survives backend restarts.
        try:
            conn.execute(text("ALTER TABLE team_season_stats ADD COLUMN big_plays INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added team_season_stats.big_plays")
        except Exception:
            conn.rollback()
    finally:
        conn.close()

    # Recompute funding tiers with the current share-of-league thresholds.
    # v0.10 changed MEGA from ≥1.75× to ≥2.0×, LARGE from ≥1.0× to ≥1.15×,
    # and MID from ≥0.5× to ≥0.85×. Any team_funding row assigned under the
    # old thresholds has a stale tier label even though its effective_funding
    # is correct. Idempotent: running on already-correct tiers is a no-op.
    _recomputeFundingTiers()

    # Refresh stale effect_config text on reworked card effects
    _refreshCardEffectText()

    # One-time data backfills: reconstruct missing data from GamePlayerStats
    _backfillPlayerSeasonTeamIds()
    _backfillPlayerSeasonStatsFromGames()
    _backfillPlayerCareerStatsFromGames()


def _recomputeFundingTiers():
    """Recompute funding_tier / tier_rank for every team_funding row using the
    current FUNDING_TIER_THRESHOLDS. Safe to run repeatedly — deterministic
    from effective_funding."""
    from sqlalchemy import text
    from constants import FUNDING_TIER_NAMES, FUNDING_TIER_THRESHOLDS

    conn = engine.connect()
    try:
        seasons = [
            row[0] for row in conn.execute(
                text("SELECT DISTINCT season FROM team_funding")
            ).fetchall()
        ]
        totalUpdated = 0
        for season in seasons:
            rows = conn.execute(
                text(
                    "SELECT id, effective_funding, funding_tier, tier_rank "
                    "FROM team_funding WHERE season = :s"
                ),
                {"s": season},
            ).fetchall()
            if not rows:
                continue
            teamCount = len(rows)
            totalFunding = sum((r[1] or 0) for r in rows)
            fairShare = max(1.0, totalFunding / teamCount) if teamCount else 1.0

            def tierFor(effective):
                ratio = (effective or 0) / fairShare
                for idx, name in enumerate(FUNDING_TIER_NAMES):
                    if ratio >= FUNDING_TIER_THRESHOLDS[name]:
                        return name, idx + 1
                last = len(FUNDING_TIER_NAMES) - 1
                return FUNDING_TIER_NAMES[last], last + 1

            for rowId, effective, oldTier, oldRank in rows:
                newTier, newRank = tierFor(effective)
                if newTier != oldTier or newRank != oldRank:
                    conn.execute(
                        text(
                            "UPDATE team_funding SET funding_tier = :t, tier_rank = :r "
                            "WHERE id = :id"
                        ),
                        {"t": newTier, "r": newRank, "id": rowId},
                    )
                    totalUpdated += 1
        if totalUpdated:
            conn.commit()
            logger.info(f"  Migration: recomputed {totalUpdated} funding tier labels")
        else:
            conn.rollback()
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Migration: funding tier recompute skipped ({e})")
    finally:
        conn.close()


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
    _seedAchievements()


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


def _seedAchievements():
    """Seed achievement templates if they don't already exist.

    Achievement keys are the canonical identifier used by achievementManager to
    look up definitions. Safe to re-run — only inserts missing rows.
    Reward config shape: {floobits, packs:[slug,...], powerups:[slug,...], deferred}
    """
    from database.models import Achievement
    session = SessionLocal()
    try:
        defaults = [
            # Onboarding — one-time milestones (floobit-only so the reward is always useful)
            {"key": "rookie", "name": "New Fan", "category": "onboarding", "scope": "once", "sort_order": 10, "target": 1,
             "description": "Pick a favorite team.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "prognosticator", "name": "Prognosticator", "category": "onboarding", "scope": "once", "sort_order": 20, "target": 1,
             "description": "Submit your first prognostication.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "pack_popper", "name": "Pack Popper", "category": "onboarding", "scope": "once", "sort_order": 30, "target": 1,
             "description": "Open your first card pack.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "field_general", "name": "Field General", "category": "onboarding", "scope": "once", "sort_order": 40, "target": 1,
             "description": "Set your first fantasy roster.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "deck_builder", "name": "Deck Builder", "category": "onboarding", "scope": "once", "sort_order": 50, "target": 1,
             "description": "Equip your first card.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "patron", "name": "Patron", "category": "onboarding", "scope": "once", "sort_order": 60, "target": 1,
             "description": "Make your first team contribution.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            # Guidance — re-earn each season, pack/powerup rewards stay relevant
            # Rebalance philosophy (v0.11 prep):
            #   - Tiered families: floobits scale across tiers, ONE pack at the
            #     family-completion tier. Packs are a "finisher" reward, not a
            #     per-tier drip.
            #   - Single-shot milestones: mostly floobits + powerups; packs only
            #     on the few that are genuinely hard to earn.
            #   - Secrets: trimmed pack rarity (proper → humble for easy ones,
            #     proper → none for the niche/easy ones). Reserved grand/proper
            #     for the genuinely difficult secrets.
            {"key": "sharp", "name": "Sharp", "category": "guidance", "scope": "per_season", "sort_order": 110, "target": 1,
             "description": "Earn a Clairvoyant this season (hit the weekly points threshold in prognostications).",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            # Dedicated — manual pick weeks (auto-picks don't count)
            {"key": "dedicated_i", "name": "Dedicated I", "category": "guidance", "scope": "per_season", "sort_order": 120, "target": 5,
             "description": "Submit prognostications for 5 weeks this season (not counting autopicks).",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dedicated_ii", "name": "Dedicated II", "category": "guidance", "scope": "per_season", "sort_order": 121, "target": 10,
             "description": "Submit prognostications for 10 weeks this season (not counting autopicks).",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dedicated_iii", "name": "Dedicated III", "category": "guidance", "scope": "per_season", "sort_order": 122, "target": 15,
             "description": "Submit prognostications for 15 weeks this season (not counting autopicks).",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dedicated_iv", "name": "Dedicated IV", "category": "guidance", "scope": "per_season", "sort_order": 123, "target": 20,
             "description": "Submit prognostications for 20 weeks this season (not counting autopicks).",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dedicated_v", "name": "Dedicated V", "category": "guidance", "scope": "per_season", "sort_order": 124, "target": 25,
             "description": "Submit prognostications for 25 weeks this season (not counting autopicks).",
             "reward_config": {"floobits": 150, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dedicated_vi", "name": "Dedicated VI", "category": "guidance", "scope": "per_season", "sort_order": 125, "target": 28,
             "description": "Submit prognostications every week of the regular season (not counting autopicks).",
             "reward_config": {"floobits": 250, "packs": ["exquisite"], "powerups": [], "deferred": False}},
            {"key": "curator", "name": "Curator", "category": "guidance", "scope": "per_season", "sort_order": 130, "target": 15,
             "description": "Collect 15 unique cards this season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "tycoon", "name": "Tycoon", "category": "guidance", "scope": "per_season", "sort_order": 140, "target": 1000,
             "description": "Earn 1,000 floobits in a single season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": ["income_boost"], "deferred": False}},
            {"key": "veteran", "name": "Veteran", "category": "guidance", "scope": "per_season", "sort_order": 150, "target": 20,
             "description": "Set a fantasy roster for 20+ weeks of the regular season.",
             "reward_config": {"floobits": 300, "packs": [], "powerups": ["extra_swap"], "deferred": False}},
            # Banner Week tiers — FP earned in a single week
            {"key": "banner_week_i", "name": "Banner Week I", "category": "guidance", "scope": "per_season", "sort_order": 160, "target": 150,
             "description": "Earn 150+ fantasy points in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "banner_week_ii", "name": "Banner Week II", "category": "guidance", "scope": "per_season", "sort_order": 161, "target": 200,
             "description": "Earn 200+ fantasy points in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "banner_week_iii", "name": "Banner Week III", "category": "guidance", "scope": "per_season", "sort_order": 162, "target": 250,
             "description": "Earn 250+ fantasy points in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "banner_week_iv", "name": "Banner Week IV", "category": "guidance", "scope": "per_season", "sort_order": 163, "target": 300,
             "description": "Earn 300+ fantasy points in a single week.",
             "reward_config": {"floobits": 75, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Racket tiers — floobits earned from card effects in a single week
            # (renamed from Windfall to avoid clashing with the card effect of the same name)
            {"key": "racket_i", "name": "Racket I", "category": "guidance", "scope": "per_season", "sort_order": 190, "target": 50,
             "description": "Earn 50+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "racket_ii", "name": "Racket II", "category": "guidance", "scope": "per_season", "sort_order": 191, "target": 100,
             "description": "Earn 100+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "racket_iii", "name": "Racket III", "category": "guidance", "scope": "per_season", "sort_order": 192, "target": 150,
             "description": "Earn 150+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "racket_iv", "name": "Racket IV", "category": "guidance", "scope": "per_season", "sort_order": 193, "target": 200,
             "description": "Earn 200+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Dynamo tiers — cumulative season fantasy points
            {"key": "dynamo_i", "name": "Dynamo I", "category": "guidance", "scope": "per_season", "sort_order": 200, "target": 1000,
             "description": "Earn 1,000 total fantasy points this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynamo_ii", "name": "Dynamo II", "category": "guidance", "scope": "per_season", "sort_order": 201, "target": 2000,
             "description": "Earn 2,000 total fantasy points this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynamo_iii", "name": "Dynamo III", "category": "guidance", "scope": "per_season", "sort_order": 202, "target": 3500,
             "description": "Earn 3,500 total fantasy points this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynamo_iv", "name": "Dynamo IV", "category": "guidance", "scope": "per_season", "sort_order": 203, "target": 5000,
             "description": "Earn 5,000 total fantasy points this season.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Oracle tiers — cumulative season prognostication points
            {"key": "oracle_i", "name": "Oracle I", "category": "guidance", "scope": "per_season", "sort_order": 210, "target": 300,
             "description": "Earn 300 total prognostication points this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "oracle_ii", "name": "Oracle II", "category": "guidance", "scope": "per_season", "sort_order": 211, "target": 700,
             "description": "Earn 700 total prognostication points this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "oracle_iii", "name": "Oracle III", "category": "guidance", "scope": "per_season", "sort_order": 212, "target": 1200,
             "description": "Earn 1,200 total prognostication points this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "oracle_iv", "name": "Oracle IV", "category": "guidance", "scope": "per_season", "sort_order": 213, "target": 1800,
             "description": "Earn 1,800 total prognostication points this season.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Magnate tiers — cumulative season floobits spent
            {"key": "magnate_i", "name": "Magnate I", "category": "guidance", "scope": "per_season", "sort_order": 220, "target": 500,
             "description": "Spend 500 floobits this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "magnate_ii", "name": "Magnate II", "category": "guidance", "scope": "per_season", "sort_order": 221, "target": 1500,
             "description": "Spend 1,500 floobits this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "magnate_iii", "name": "Magnate III", "category": "guidance", "scope": "per_season", "sort_order": 222, "target": 3000,
             "description": "Spend 3,000 floobits this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "magnate_iv", "name": "Magnate IV", "category": "guidance", "scope": "per_season", "sort_order": 223, "target": 5000,
             "description": "Spend 5,000 floobits this season.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Podium tiers — weekly fantasy leaderboard top-3 finishes this season
            {"key": "podium_i", "name": "Podium I", "category": "guidance", "scope": "per_season", "sort_order": 230, "target": 5,
             "description": "Place top 3 on the weekly fantasy leaderboard 5 times this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "podium_ii", "name": "Podium II", "category": "guidance", "scope": "per_season", "sort_order": 231, "target": 10,
             "description": "Place top 3 on the weekly fantasy leaderboard 10 times this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "podium_iii", "name": "Podium III", "category": "guidance", "scope": "per_season", "sort_order": 232, "target": 15,
             "description": "Place top 3 on the weekly fantasy leaderboard 15 times this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "podium_iv", "name": "Podium IV", "category": "guidance", "scope": "per_season", "sort_order": 233, "target": 20,
             "description": "Place top 3 on the weekly fantasy leaderboard 20 times this season.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Pundit tiers — weekly pick-em leaderboard top-3 finishes this season
            {"key": "pundit_i", "name": "Pundit I", "category": "guidance", "scope": "per_season", "sort_order": 240, "target": 5,
             "description": "Place top 3 on the weekly prognostication leaderboard 5 times this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "pundit_ii", "name": "Pundit II", "category": "guidance", "scope": "per_season", "sort_order": 241, "target": 10,
             "description": "Place top 3 on the weekly prognostication leaderboard 10 times this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "pundit_iii", "name": "Pundit III", "category": "guidance", "scope": "per_season", "sort_order": 242, "target": 15,
             "description": "Place top 3 on the weekly prognostication leaderboard 15 times this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "pundit_iv", "name": "Pundit IV", "category": "guidance", "scope": "per_season", "sort_order": 243, "target": 20,
             "description": "Place top 3 on the weekly prognostication leaderboard 20 times this season.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Benefactor tiers — cumulative floobits contributed to your favorite team this season
            {"key": "benefactor_i", "name": "Benefactor I", "category": "guidance", "scope": "per_season", "sort_order": 250, "target": 250,
             "description": "Contribute 250 floobits to your team this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "benefactor_ii", "name": "Benefactor II", "category": "guidance", "scope": "per_season", "sort_order": 251, "target": 500,
             "description": "Contribute 500 floobits to your team this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "benefactor_iii", "name": "Benefactor III", "category": "guidance", "scope": "per_season", "sort_order": 252, "target": 1500,
             "description": "Contribute 1,500 floobits to your team this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "benefactor_iv", "name": "Benefactor IV", "category": "guidance", "scope": "per_season", "sort_order": 253, "target": 5000,
             "description": "Contribute 5,000 floobits to your team this season.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Compound tiers — single-week total FP multiplier (stored as multiplier × 100)
            {"key": "compound_i", "name": "Compound I", "category": "guidance", "scope": "per_season", "sort_order": 260, "target": 120,
             "description": "Reach a 1.2x total FP multiplier in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_ii", "name": "Compound II", "category": "guidance", "scope": "per_season", "sort_order": 261, "target": 150,
             "description": "Reach a 1.5x total FP multiplier in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_iii", "name": "Compound III", "category": "guidance", "scope": "per_season", "sort_order": 262, "target": 170,
             "description": "Reach a 1.7x total FP multiplier in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_iv", "name": "Compound IV", "category": "guidance", "scope": "per_season", "sort_order": 263, "target": 200,
             "description": "Reach a 2.0x total FP multiplier in a single week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # ── Secret achievements — hidden until unlocked ────────────────────────
            # Mostly floobits with selective packs for the genuinely hard
            # ones. Easier/niche secrets dropped to floobit-only since they're
            # discoverable rather than difficult.
            {"key": "contrarian", "name": "Contrarian", "category": "secret", "scope": "once", "sort_order": 500, "target": 1,
             "description": "Every one of your pick-em picks this week was on an underdog.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "shoestring", "name": "Shoestring", "category": "secret", "scope": "once", "sort_order": 510, "target": 1,
             "description": "Set a full fantasy roster where every player is rated 3 stars or lower.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "gilded", "name": "Gilded", "category": "secret", "scope": "once", "sort_order": 520, "target": 1,
             "description": "Equip a full set of cards that are all Prismatic or Diamond.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "giant_slayer", "name": "Giant Slayer", "category": "secret", "scope": "once", "sort_order": 530, "target": 1,
             "description": "Finish top 3 on a weekly fantasy leaderboard with every roster player rated 3 stars or lower.",
             "reward_config": {"floobits": 100, "packs": ["humble"], "powerups": [], "deferred": False}},
            {"key": "purist", "name": "Purist", "category": "secret", "scope": "once", "sort_order": 540, "target": 1,
             "description": "Play a full week with zero cards equipped.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "homer", "name": "Homer", "category": "secret", "scope": "once", "sort_order": 550, "target": 1,
             "description": "Set a fantasy roster composed entirely of players on your favorite team.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "blank", "name": "Blank", "category": "secret", "scope": "once", "sort_order": 560, "target": 1,
             "description": "Finish a week with 20 or fewer fantasy points despite a full roster.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "cold_blooded", "name": "Cold-Blooded", "category": "secret", "scope": "once", "sort_order": 570, "target": 1,
             "description": "Pick against your favorite team 5 or more times in a single season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "sovereign", "name": "Sovereign", "category": "secret", "scope": "once", "sort_order": 580, "target": 1,
             "description": "Finish #1 overall on the season fantasy leaderboard.",
             "reward_config": {"floobits": 0, "packs": [], "powerups": [], "deferred": False}},
            {"key": "soothsayer", "name": "Soothsayer", "category": "secret", "scope": "once", "sort_order": 590, "target": 1,
             "description": "Finish #1 overall on the season prognostication leaderboard.",
             "reward_config": {"floobits": 0, "packs": [], "powerups": [], "deferred": False}},
            {"key": "zenith", "name": "Zenith", "category": "secret", "scope": "once", "sort_order": 600, "target": 1,
             "description": "Earn a Perfect Week and 300+ fantasy points in the same week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            {"key": "consecration", "name": "Consecration", "category": "secret", "scope": "once", "sort_order": 610, "target": 1,
             "description": "Your favorite team wins the Floosbowl.",
             "reward_config": {"floobits": 0, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dabbler", "name": "Dabbler", "category": "secret", "scope": "once", "sort_order": 620, "target": 1,
             "description": "Purchase every type of power-up at least once.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "arsenal", "name": "Arsenal", "category": "secret", "scope": "once", "sort_order": 630, "target": 1,
             "description": "Hold 3 or more roster swaps at the same time.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "finicky", "name": "Finicky", "category": "secret", "scope": "once", "sort_order": 640, "target": 1,
             "description": "Re-roll the card shop 5 times in a row without buying anything in between.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "sweep", "name": "Sweep", "category": "secret", "scope": "once", "sort_order": 650, "target": 1,
             "description": "Buy every card featured in your shop in a single day.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "mutineer", "name": "Mutineer", "category": "secret", "scope": "once", "sort_order": 660, "target": 1,
             "description": "Cast the maximum number of fire-coach votes in a single season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "tribune", "name": "Tribune", "category": "secret", "scope": "once", "sort_order": 665, "target": 1,
             "description": "Cast every one of your 20 GM votes in a single season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "monk", "name": "Monk", "category": "secret", "scope": "once", "sort_order": 670, "target": 1,
             "description": "Go an entire season without opening a card pack.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "stalwart", "name": "Stalwart", "category": "secret", "scope": "once", "sort_order": 680, "target": 1,
             "description": "Play an entire season with a full roster and zero roster swaps.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "faithful", "name": "Faithful", "category": "secret", "scope": "once", "sort_order": 690, "target": 1,
             "description": "Your favorite team misses the playoffs three seasons in a row.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "devotee", "name": "Devotee", "category": "secret", "scope": "once", "sort_order": 700, "target": 1,
             "description": "Set team funding to 100% and receive an end-of-season auto-contribution payout.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "completist", "name": "Completist", "category": "secret", "scope": "once", "sort_order": 710, "target": 1,
             "description": "Own all four editions (base, holographic, prismatic, diamond) of the same player.",
             "reward_config": {"floobits": 150, "packs": [], "powerups": [], "deferred": False}},
            {"key": "sparkler", "name": "Sparkler", "category": "guidance", "scope": "per_season", "sort_order": 170, "target": 1,
             "description": "Open your first Diamond card of the season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "perfect_week", "name": "Perfect Week", "category": "guidance", "scope": "per_season", "sort_order": 180, "target": 1,
             "description": "Get every prognostication correct in a single week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
        ]
        added = 0
        updated = 0
        # Template-level fields that are safe to refresh without resetting user progress.
        # reward_config changes affect future grants only; already-completed achievements
        # keep whatever reward the user received at the time of completion.
        refreshFields = ("name", "description", "category", "scope", "target", "sort_order", "reward_config")
        for d in defaults:
            existing = session.query(Achievement).filter(Achievement.key == d["key"]).first()
            if existing:
                changed = False
                for f in refreshFields:
                    if getattr(existing, f) != d[f]:
                        setattr(existing, f, d[f])
                        changed = True
                if changed:
                    updated += 1
                continue
            session.add(Achievement(**d))
            added += 1
        if added or updated:
            session.commit()
            if added:
                logger.info(f"  Seeded {added} achievement templates")
            if updated:
                logger.info(f"  Refreshed {updated} achievement templates")
        else:
            session.rollback()
    except Exception as e:
        session.rollback()
        logger.warning(f"  Achievement seed failed: {e}")
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
