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
        "timeout": 30,  # Driver-level timeout for waiting on a busy DB (was 5s — too short under contention)
        "check_same_thread": False  # Allow multiple threads (needed for async)
    }
)

# Enable WAL mode for better concurrent access
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    # 30s busy_timeout gives plenty of headroom during bursty offseason
    # writes (GM vote resolutions, predraft setup, draft picks all happen
    # in rapid succession). The previous 5s was tripping under load.
    cursor.execute("PRAGMA busy_timeout=30000")
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
    _seedUnusedNames()
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
            # GM threshold snapshot: per-team active fan count frozen at
            # the front-office open (week 22) so post-week-22 logins
            # don't inflate the threshold mid-vote.
            ('front_office_fan_snapshot', 'TEXT'),
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

        # Hall of Fame flag (v0.17). Without this, the in-memory hallOfFame
        # list resets on every restart and the HoF tab goes empty until brand-
        # new retirees get inducted. Stored on the player row so the load path
        # can route HoF members into the right list at boot.
        try:
            conn.execute(text("ALTER TABLE players ADD COLUMN is_hof BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added players.is_hof")
        except Exception:
            conn.rollback()

        # Career awards (v0.17). Same in-memory-only problem as is_hof —
        # MVP / All-Pro / championship lists reset on restart and the
        # player profile page goes empty. Persist as JSON columns.
        for col in ['mvp_awards', 'all_pro_seasons', 'league_championships']:
            try:
                conn.execute(text(f"ALTER TABLE players ADD COLUMN {col} JSON"))
                conn.commit()
                logger.info(f"  Migration: added players.{col}")
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

        # Q4 scoring plays count on game_player_stats — Walk Off card uses this
        try:
            conn.execute(text("ALTER TABLE game_player_stats ADD COLUMN q4_scoring_plays INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added game_player_stats.q4_scoring_plays")
        except Exception:
            conn.rollback()

        # Initial-player snapshot on fantasy_rosters — Loyalty card reads this
        try:
            conn.execute(text("ALTER TABLE fantasy_rosters ADD COLUMN initial_player_ids TEXT"))
            conn.commit()
            logger.info("  Migration: added fantasy_rosters.initial_player_ids")
        except Exception:
            conn.rollback()

        # Drop legacy coaches.team_id column (single-source-of-truth refactor).
        # The new code uses Team.coach_id exclusively. Important: do NOT
        # overwrite a Team.coach_id that already points at a real Coach row —
        # that FK has been the team's actual coach pointer all along, even
        # when the legacy Coach.team_id back-reference got polluted with
        # orphans from buggy code paths (e.g. _saveCoachToDatabase generating
        # a new row alongside the team's original coach).
        #
        # Only fill Team.coach_id when it's NULL or points at a missing row,
        # and even then pick the OLDEST matching Coach (lowest id) since the
        # orphan pattern observed in prod is "real coach is original, newer
        # rows are stray" — the opposite of what auto-increment-newest would
        # imply. Idempotent: skipped once the column is gone.
        try:
            cols = conn.execute(text("PRAGMA table_info(coaches)")).fetchall()
            colNames = {row[1] for row in cols}
            if 'team_id' in colNames:
                conn.execute(text("""
                    UPDATE teams
                    SET coach_id = (
                        SELECT MIN(c.id) FROM coaches c WHERE c.team_id = teams.id
                    )
                    WHERE (
                        coach_id IS NULL
                        OR coach_id NOT IN (SELECT id FROM coaches)
                    )
                    AND EXISTS (
                        SELECT 1 FROM coaches c WHERE c.team_id = teams.id
                    )
                """))
                conn.execute(text("ALTER TABLE coaches DROP COLUMN team_id"))
                conn.commit()
                logger.info("  Migration: dropped coaches.team_id (existing Team.coach_id preserved)")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: coaches.team_id drop skipped: {e}")

        # tier_locked_funding: snapshot of the funding value the row's
        # current tier was computed from. Markets chart needs this to put
        # the filled dot in the right tier band after the offseason recompute
        # (which uses effective_funding instead of season-start funding).
        try:
            conn.execute(text("ALTER TABLE team_funding ADD COLUMN tier_locked_funding INTEGER"))
            conn.commit()
            logger.info("  Migration: added team_funding.tier_locked_funding")
        except Exception:
            conn.rollback()  # column already exists — ignore

        # Schema-level guarantee: a Coach can be assigned to at most ONE Team.
        # SQLite UNIQUE indexes treat NULLs as distinct, so multiple coachless
        # teams (coach_id IS NULL) are allowed; a non-null coach_id has to be
        # unique across teams. Replaces the application-layer "is this coach
        # available" checks with a hard schema constraint. Idempotent via
        # IF NOT EXISTS.
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_coach_id "
                "ON teams(coach_id) WHERE coach_id IS NOT NULL"
            ))
            conn.commit()
            logger.info("  Migration: ensured uq_teams_coach_id (one coach per team)")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: uq_teams_coach_id index skipped: {e}")

        # Play reactions — users react to plays / sideline quotes during live games
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS play_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL REFERENCES games(id),
                    play_number INTEGER NOT NULL,
                    target_type VARCHAR(20) NOT NULL DEFAULT 'play',
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    reaction_type VARCHAR(10) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(game_id, play_number, target_type, user_id)
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_play_reaction_game_play "
                "ON play_reactions(game_id, play_number)"
            ))
            conn.commit()
            logger.info("  Migration: created play_reactions table")
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
        # Plus: single-tier tycoon → tycoon_i so existing user progress
        # carries forward into the new four-tier ladder.
        try:
            renameMap = {
                "windfall_i": "racket_i",
                "windfall_ii": "racket_ii",
                "windfall_iii": "racket_iii",
                "windfall_iv": "racket_iv",
                "crescendo": "zenith",
                "tycoon": "tycoon_i",
            }
            totalRenamed = 0
            sourcesRenamed = 0
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
                # Update any PendingReward.source that still points at the old
                # key — keeps the achievements page from rendering the raw
                # 'tycoon' / 'crescendo' fragments instead of a proper name.
                srcResult = conn.execute(text(
                    "UPDATE pending_rewards SET source = :new "
                    "WHERE source = :old"
                ), {"new": f"achievement:{newKey}", "old": f"achievement:{oldKey}"})
                if srcResult.rowcount:
                    sourcesRenamed += srcResult.rowcount
            if totalRenamed or sourcesRenamed:
                conn.commit()
                if totalRenamed:
                    logger.info(f"  Migration: renamed {totalRenamed} collided achievement keys")
                if sourcesRenamed:
                    logger.info(f"  Migration: rewrote {sourcesRenamed} pending_rewards.source values")
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
            ('will_retire', 'BOOLEAN DEFAULT 0'),
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

        # Flavor fields — pure character flavor on the player detail page.
        # Backfilled at boot for legacy NULL rows, same pattern as personality.
        for col, colDef in [
            ('hometown', 'VARCHAR(60)'),
            ('favorite_category', 'VARCHAR(30)'),
            ('favorite_item', 'VARCHAR(120)'),
            ('motto', 'VARCHAR(160)'),
        ]:
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

        # Coach attitude (locker-room presence: toxic ↔ leader spectrum)
        try:
            conn.execute(text("ALTER TABLE coaches ADD COLUMN attitude INTEGER DEFAULT 80"))
            conn.commit()
            logger.info("  Migration: added coaches.attitude")
        except Exception:
            conn.rollback()

        # Starter pack + selection mechanic (feature/pack-revamp)
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN starter_pack_claimed_season INTEGER"))
            conn.commit()
            logger.info("  Migration: added users.starter_pack_claimed_season")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE pack_types ADD COLUMN cards_kept INTEGER"))
            conn.commit()
            logger.info("  Migration: added pack_types.cards_kept")
        except Exception:
            conn.rollback()

        # app_settings table — admin-editable runtime config (feedback URL,
        # survey URL, button visibility, etc). Created via SQLAlchemy below;
        # this seed step inserts default rows when missing.
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key VARCHAR(60) PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            defaults = [
                ('feedback_url', 'https://forms.gle/s2ycdsBLxTpsWEk4A'),
                ('feedback_visible', 'true'),
                ('survey_url', 'https://forms.gle/s2ycdsBLxTpsWEk4A'),
            ]
            for k, v in defaults:
                conn.execute(text(
                    "INSERT OR IGNORE INTO app_settings (key, value) VALUES (:k, :v)"
                ), {"k": k, "v": v})
            conn.commit()
            logger.info("  Migration: app_settings table ensured with default rows")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: app_settings setup skipped: {e}")

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

        # Phase-aware offseason resume (feature/offseason-checkpoints).
        # offseason_phase mirrors seasonManager._offseasonFlowPhase, target is
        # the next-phase deadline for waiting phases, completed_steps is a
        # JSON array of finished non-idempotent step keys. Together they let
        # a mid-offseason restart pick up where it left off instead of the
        # blunt skip-and-advance.
        for col, ddl in (
            ("offseason_phase",           "VARCHAR(32)"),
            ("offseason_phase_target",    "DATETIME"),
            ("offseason_completed_steps", "TEXT"),
            # Mid-playoff resume (hotfix/playoff-resume): JSON snapshot of the
            # in-progress bracket so a restart resumes at the next unplayed round.
            ("playoff_state",             "TEXT"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE simulation_state ADD COLUMN {col} {ddl}"))
                conn.commit()
                logger.info(f"  Migration: added simulation_state.{col}")
            except Exception:
                conn.rollback()

        # selfBelief on player_attributes — confidence stability axis.
        # Defaults to 80 for existing rows so legacy players sit at the
        # neutral point until the next offseason rolls them through training.
        try:
            conn.execute(text("ALTER TABLE player_attributes ADD COLUMN self_belief INTEGER DEFAULT 80"))
            conn.commit()
            logger.info("  Migration: added player_attributes.self_belief")
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

        # Streak peak-decay state on equipped_cards. peak_output snapshots the
        # in-streak output the last week the streak was active; weeks_since_break
        # counts cold weeks since then. Together they let a broken streak
        # decay from peak rather than dropping straight to base on the first
        # cold week. NULL peak = no prior streak to decay from.
        try:
            conn.execute(text("ALTER TABLE equipped_cards ADD COLUMN peak_output REAL"))
            conn.commit()
            logger.info("  Migration: added equipped_cards.peak_output")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE equipped_cards ADD COLUMN weeks_since_break INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added equipped_cards.weeks_since_break")
        except Exception:
            conn.rollback()
        # Snapshot of the old player's swap-week FP at swap time. Lets the
        # leaderboard preserve weekly FP across post-games-end swaps.
        try:
            conn.execute(text("ALTER TABLE fantasy_roster_swaps ADD COLUMN banked_week_fp REAL DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added fantasy_roster_swaps.banked_week_fp")
        except Exception:
            conn.rollback()
        # Roster /remove support — let fantasy_roster_swaps.old_player_id
        # and new_player_id both accept NULL. A row with new_player_id=NULL
        # represents a "remove" (emptied the slot). A row with
        # old_player_id=NULL represents a paid fill of a previously-emptied
        # slot. SQLite can't drop NOT NULL via ALTER, so we rebuild the
        # table. Idempotent: skip if both columns are already nullable.
        try:
            colInfo = conn.execute(text("PRAGMA table_info(fantasy_roster_swaps)")).fetchall()
            byName = {r[1]: r for r in colInfo}
            oldNN = byName.get('old_player_id', (None,)*6)[3] == 1
            newNN = byName.get('new_player_id', (None,)*6)[3] == 1
            if oldNN or newNN:
                conn.execute(text("""
                    CREATE TABLE fantasy_roster_swaps_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        roster_id INTEGER NOT NULL REFERENCES fantasy_rosters(id),
                        slot VARCHAR(10) NOT NULL,
                        old_player_id INTEGER NULL REFERENCES players(id),
                        new_player_id INTEGER NULL REFERENCES players(id),
                        swap_week INTEGER NOT NULL,
                        banked_fp REAL DEFAULT 0,
                        banked_week_fp REAL DEFAULT 0,
                        created_at DATETIME
                    )
                """))
                conn.execute(text("""
                    INSERT INTO fantasy_roster_swaps_new
                    SELECT id, roster_id, slot, old_player_id, new_player_id, swap_week,
                           banked_fp, COALESCE(banked_week_fp, 0), created_at
                    FROM fantasy_roster_swaps
                """))
                conn.execute(text("DROP TABLE fantasy_roster_swaps"))
                conn.execute(text("ALTER TABLE fantasy_roster_swaps_new RENAME TO fantasy_roster_swaps"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_fantasy_swap_roster ON fantasy_roster_swaps(roster_id)"))
                conn.commit()
                logger.info("  Migration: fantasy_roster_swaps old/new_player_id are now nullable")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration skipped (swap player_id nullable): {e}")
        # Peak streak (longest win-or-loss run, abs value) per team-season.
        # Column add only — backfill runs below via _backfillTeamPeakStreaks
        # so it opens its own connection and can compute idempotently.
        try:
            conn.execute(text("ALTER TABLE team_season_stats ADD COLUMN peak_streak INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added team_season_stats.peak_streak")
        except Exception:
            conn.rollback()
        # Themed-pack columns on pack_types (themed pack rework)
        for col, colDef in [
            ('theme_type', 'VARCHAR(20)'),
            ('theme_value', 'VARCHAR(50)'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE pack_types ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added pack_types.{col}")
            except Exception:
                conn.rollback()
        # Denormalized output_type on card_templates so themed packs can
        # filter the candidate pool without scanning effect_config JSON.
        try:
            conn.execute(text("ALTER TABLE card_templates ADD COLUMN output_type VARCHAR(20)"))
            conn.commit()
            logger.info("  Migration: added card_templates.output_type")
        except Exception:
            conn.rollback()
        # Per-user themed pack rotation: rotation flipped from global to
        # per-user once we added reroll. Old rows have no user_id so they're
        # unusable — drop them rather than backfill.
        try:
            result = conn.execute(text("PRAGMA table_info(featured_pack_rotation)"))
            existingCols = {row[1] for row in result}
            if 'user_id' not in existingCols and existingCols:
                conn.execute(text("DROP TABLE featured_pack_rotation"))
                conn.commit()
                logger.info("  Migration: dropped global featured_pack_rotation (table recreated per-user by create_all)")
        except Exception:
            conn.rollback()
        # Purchased flag for rotation rows so bought packs vanish from the
        # shop within the cycle (mirrors FeaturedShopCard.purchased).
        try:
            conn.execute(text("ALTER TABLE featured_pack_rotation ADD COLUMN purchased BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added featured_pack_rotation.purchased")
        except Exception:
            conn.rollback()
        # Yea/nay GM votes: direction on each vote, against-count on results.
        # Existing rows default to 'yea' / 0 so old data reads as all-support.
        try:
            conn.execute(text("ALTER TABLE gm_votes ADD COLUMN direction VARCHAR(8) DEFAULT 'yea' NOT NULL"))
            conn.commit()
            logger.info("  Migration: added gm_votes.direction")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE gm_vote_results ADD COLUMN votes_against INTEGER DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added gm_vote_results.votes_against")
        except Exception:
            conn.rollback()
        # Playoff bracket challenge: frozen seed field on seasons (the
        # playoff_brackets table itself is created by create_all).
        try:
            conn.execute(text("ALTER TABLE seasons ADD COLUMN playoff_seeds TEXT"))
            conn.commit()
            logger.info("  Migration: added seasons.playoff_seeds")
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
    _backfillTeamPeakStreaks()
    _backfillCardTemplateOutputType()


def _recomputeFundingTiers():
    """Recompute funding_tier / tier_rank for every team_funding row using the
    SEASON-START funding state (baseline + carried_funding) so re-runs are
    actually idempotent across the season.

    The previous version used `effective_funding`, which grows during the
    season as fans contribute (mid-season + season-end tax). Re-running mid-
    or post-season would shift tiers — production saw this when restarting
    right after the Floos Bowl: the post-tax `effective_funding` rebalanced
    the ratios and a team that had been MEGA all season got reassigned to
    LARGE on restart. Tiers are supposed to be locked at season start —
    this migration's job is just to refresh stale labels after a threshold
    constant changes, which is invariant in `baseline + carried`.

    EXCEPTION: when the active season is in offseason, the row for that
    season has already been re-tiered by `_recomputeFundingTiersForOffseason`
    using `effective_funding`. Overwriting that with baseline+carried here
    would silently revert tier upgrades and undo offseason benefits, so we
    skip that one row.
    """
    from sqlalchemy import text
    from constants import FUNDING_TIER_NAMES, FUNDING_TIER_THRESHOLDS

    conn = engine.connect()
    try:
        # Detect active offseason. If we're mid-offseason for season N,
        # the offseason recompute has already set funding_tier on the
        # season-N row using effective_funding — don't undo that here.
        offseasonSeason = None
        try:
            res = conn.execute(text(
                "SELECT current_season, in_offseason FROM simulation_state WHERE id = 1"
            )).fetchone()
            if res and res[1]:
                offseasonSeason = res[0]
        except Exception:
            # simulation_state may not exist yet on a fresh DB — skip the
            # guard and operate on all rows.
            offseasonSeason = None

        seasons = [
            row[0] for row in conn.execute(
                text("SELECT DISTINCT season FROM team_funding")
            ).fetchall()
        ]
        totalUpdated = 0
        for season in seasons:
            if offseasonSeason is not None and season == offseasonSeason:
                # Offseason-active season — its tier is intentionally
                # effective_funding-based right now. Leave it alone.
                continue
            rows = conn.execute(
                text(
                    "SELECT id, baseline_funding, carried_funding, funding_tier, tier_rank "
                    "FROM team_funding WHERE season = :s"
                ),
                {"s": season},
            ).fetchall()
            if not rows:
                continue
            teamCount = len(rows)
            # Season-start funding = baseline + carried (does NOT include
            # in-season fan_contributions, so it stays invariant all season).
            totalFunding = sum(((r[1] or 0) + (r[2] or 0)) for r in rows)
            fairShare = max(1.0, totalFunding / teamCount) if teamCount else 1.0

            def tierFor(seasonStart):
                ratio = (seasonStart or 0) / fairShare
                for idx, name in enumerate(FUNDING_TIER_NAMES):
                    if ratio >= FUNDING_TIER_THRESHOLDS[name]:
                        return name, idx + 1
                last = len(FUNDING_TIER_NAMES) - 1
                return FUNDING_TIER_NAMES[last], last + 1

            for rowId, baseline, carried, oldTier, oldRank in rows:
                # Authoritative writers (_initializeTeamFunding's inherit
                # step + _recomputeFundingTiersForOffseason) set the tier
                # at the right moments using the right inputs. If a row
                # already has a tier, leave it alone — overwriting with
                # baseline+carried here would undo the inheritance chain
                # and cause the baseline-compression flip we just fixed.
                # Only operate on uninitialized rows (NULL tier).
                if oldTier and oldRank is not None:
                    continue
                seasonStart = (baseline or 0) + (carried or 0)
                newTier, newRank = tierFor(seasonStart)
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


def _backfillCardTemplateOutputType():
    """Stamp output_type on card_templates rows that don't have it set yet.
    Resolves effectName → concrete output type via the cardEffects classifier.
    Idempotent: only touches rows where output_type IS NULL."""
    import json as _json
    from managers.cardEffects import getEffectOutputType
    from sqlalchemy import text

    conn = engine.connect()
    try:
        rows = conn.execute(
            text("SELECT id, effect_config FROM card_templates WHERE output_type IS NULL")
        ).fetchall()
        if not rows:
            return
        updated = 0
        for row in rows:
            cfg = _json.loads(row[1]) if isinstance(row[1], str) else row[1]
            effectName = (cfg or {}).get("effectName", "")
            outputType = getEffectOutputType(effectName)
            if outputType is None:
                continue  # leave NULL — mixed/contextual effects are excluded by design
            conn.execute(
                text("UPDATE card_templates SET output_type = :ot WHERE id = :id"),
                {"ot": outputType, "id": row[0]},
            )
            updated += 1
        if updated:
            conn.commit()
            logger.info(f"  Migration: backfilled output_type on {updated} card templates")
        else:
            conn.rollback()
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Migration: output_type backfill skipped ({e})")
    finally:
        conn.close()


def _refreshCardEffectText():
    """Update stale tooltip/detail text on card templates whose effects were reworked.

    Re-runs the same placeholder substitution buildEffectConfig does — so
    templates that reference {primary.fieldName} pick up the current text
    AND the current value (computed from stored primary). Add an effect
    name to refreshEffects when its tooltip / detail template changes
    and existing card descriptions should re-render on next boot.
    """
    import json as _json
    import re as _re
    from managers.cardEffects import EFFECT_TOOLTIPS, EFFECT_DETAIL_TEMPLATES, STAT_DISPLAY_NAMES
    from sqlalchemy import text

    refreshEffects = {
        "odometer", "snake_eyes",
        # FPx delta-notation sweep — existing cards stored 1.x values in
        # their tooltip/detail strings; re-render with the *Delta variants.
        "backfield_buddies", "all_in", "stacked_deck",
        # Full-roster-required tightening — drought/sandbagger/quiet_storm
        # /hedge now refuse to pay on a gutted roster (<6 filled slots),
        # so the description should surface that.
        "drought", "sandbagger", "quiet_storm", "hedge",
        # Fav-team-event cards reworked into roster-trait mechanics +
        # floobits bonus on the rare event. (Note: this refresh only
        # rewrites text — existing dev-DB cards have old primary keys
        # and will render with `?` placeholders until they're rebuilt
        # via fresh start or pack re-open. Fine for next-season's clean
        # slate.)
        "comeback_kid", "domination", "walk_off",
        # Reworked: Believe (per fav-team season win), Showoff (per 5★),
        # Eminence (per top-10 roster player).
        "believe", "showoff", "eminence",
        # FP → FPx conversions for Base FPx variety. Param keys changed.
        "homer", "honor_roll",
    }

    # Same FullMult → Delta synthesis buildEffectConfig does. Keep these
    # two maps in sync.
    _FULL_MULT_FIELDS = {
        'xMultValue':    'xMultDelta',
        'baseXMult':     'baseXDelta',
        'baseMult':      'baseDelta',
        'enhancedMult':  'enhancedDelta',
        'maxMult':       'maxDelta',
        'q4MultFactor':  'q4MultDelta',
    }
    _REWARDVALUE_IS_MULT_EFFECTS = {'bandwagon', 'stack', 'backfield_buddies', 'full_roster'}

    def _renderTemplate(tmpl: str, primary: dict) -> str:
        if not tmpl:
            return ""
        # Synthesize delta variants on a working copy of primary.
        derived = dict(primary or {})
        for fullKey, deltaKey in _FULL_MULT_FIELDS.items():
            if fullKey in derived and isinstance(derived[fullKey], (int, float)):
                derived[deltaKey] = round(derived[fullKey] - 1, 2)
        if 'rewardValue' in derived:
            rv = derived['rewardValue']
            if isinstance(rv, (int, float)) and rv >= 1.0:
                derived['rewardDelta'] = round(rv - 1, 2)
        if derived.get('rewardType') == 'mult' and 'baseReward' in derived:
            br = derived['baseReward']
            if isinstance(br, (int, float)) and br >= 1.0:
                derived['baseRewardDelta'] = round(br - 1, 2)
        out = tmpl
        for key, val in derived.items():
            out = out.replace("{" + key + "}", str(val))
        statKey = derived.get("stat", "")
        if statKey:
            out = out.replace("{statDisplay}", STAT_DISPLAY_NAMES.get(statKey, statKey))
        return _re.sub(r'\{[a-zA-Z_]+\}', '?', out)

    conn = engine.connect()
    try:
        rows = conn.execute(text("SELECT id, effect_config FROM card_templates")).fetchall()
        updated = 0
        for row in rows:
            cfg = _json.loads(row[1]) if isinstance(row[1], str) else row[1]
            effectName = cfg.get("effectName", "")
            if effectName not in refreshEffects:
                continue
            primary = cfg.get("primary", {}) or {}
            newTooltip = _renderTemplate(EFFECT_TOOLTIPS.get(effectName, ""), primary)
            newDetail = _renderTemplate(EFFECT_DETAIL_TEMPLATES.get(effectName, ""), primary)
            if cfg.get("tooltip") == newTooltip and cfg.get("detail") == newDetail:
                continue
            cfg["tooltip"] = newTooltip
            cfg["detail"] = newDetail
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


def _backfillTeamPeakStreaks():
    """Walk regular-season games chronologically per team-season and write
    the longest win-or-loss run into team_season_stats.peak_streak.

    Idempotent: only updates rows where peak_streak is below the computed
    value. The Gone Streaking card reads this field via favoriteTeamPeakStreak,
    so without a backfill, existing seasons would show 0 on cards even
    after weeks of streaks already played out.
    """
    from sqlalchemy import text
    conn = engine.connect()
    try:
        rows = conn.execute(text("""
            SELECT g.season, g.id, g.week, g.game_date,
                   g.home_team_id, g.away_team_id, g.home_score, g.away_score
            FROM games g
            WHERE g.is_playoff = 0
              AND g.status = 'final'
            ORDER BY g.season, g.week, g.game_date, g.id
        """)).fetchall()
        if not rows:
            return
        # streakByTeam: (season, team_id) → current signed streak
        # peakByTeam:   (season, team_id) → max abs streak observed
        streakByTeam = {}
        peakByTeam = {}
        def recordResult(season, teamId, won):
            key = (season, teamId)
            cur = streakByTeam.get(key, 0)
            if won:
                cur = cur + 1 if cur > 0 else 1
            else:
                cur = cur - 1 if cur < 0 else -1
            streakByTeam[key] = cur
            absCur = abs(cur)
            if absCur > peakByTeam.get(key, 0):
                peakByTeam[key] = absCur
        for season, gid, week, gameDate, homeId, awayId, homeScore, awayScore in rows:
            if homeScore is None or awayScore is None or homeScore == awayScore:
                continue
            if homeScore > awayScore:
                recordResult(season, homeId, True)
                recordResult(season, awayId, False)
            else:
                recordResult(season, awayId, True)
                recordResult(season, homeId, False)
        updated = 0
        for (season, teamId), peak in peakByTeam.items():
            result = conn.execute(text("""
                UPDATE team_season_stats
                SET peak_streak = :peak
                WHERE team_id = :team_id AND season = :season
                  AND COALESCE(peak_streak, 0) < :peak
            """), {"team_id": teamId, "season": season, "peak": peak})
            updated += result.rowcount or 0
        if updated:
            conn.commit()
            logger.info(f"  Backfill: set peak_streak on {updated} team_season_stats rows")
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Backfill warning (peak_streak): {e}")
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
        # but the player has game data (meaning the stats were zeroed by the save bug).
        # Kickers also need a fgAtt check — they never accumulate passing/rushing/
        # receiving yards, so the standard zero-check would always fire on them and
        # the reconstruction would wipe per-range FG fields (game_player_stats
        # doesn't track those).
        result = conn.execute(text(
            "SELECT pss.id, pss.player_id, pss.season FROM player_season_stats pss "
            "WHERE COALESCE(pss.passing_yards, 0) = 0 AND COALESCE(pss.rushing_yards, 0) = 0 "
            "  AND COALESCE(pss.receiving_yards, 0) = 0 AND COALESCE(pss.sacks, 0) = 0 "
            "  AND COALESCE(CAST(json_extract(pss.kicking_stats, '$.fgAtt') AS INTEGER), 0) = 0 "
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
            # Per-range FG percentages (under 20 / 20-40 / 40-50 / 50+).
            # Each pair tracks attempts (xxxAtt) and makes (xxx).
            for mkKey, attKey, percKey in (
                ('fgUnder20', 'fgUnder20att', 'fgUnder20perc'),
                ('fg20to40', 'fg20to40att', 'fg20to40perc'),
                ('fg40to50', 'fg40to50att', 'fg40to50perc'),
                ('fgOver50', 'fgOver50att', 'fgOver50perc'),
            ):
                att = kicking.get(attKey, 0) or 0
                if att > 0:
                    kicking[percKey] = round((kicking.get(mkKey, 0) or 0) / att * 100, 1)
                else:
                    kicking[percKey] = 0

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
        # Find players with game data but zeroed/NULL or missing career stats.
        # Kickers don't accumulate passing/rushing/receiving yards, so the
        # check also looks at the kicking_stats JSON for fgAtt — without this,
        # the backfill would fire for every kicker on every startup and
        # overwrite their (correctly-saved) career row with a reconstruction
        # that lacks per-range FG fields (game_player_stats never tracks them).
        result = conn.execute(text(
            "SELECT DISTINCT gps.player_id FROM game_player_stats gps "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM player_career_stats pcs "
            "  WHERE pcs.player_id = gps.player_id AND pcs.season = 0 "
            "    AND (COALESCE(pcs.passing_yards, 0) > 0 OR COALESCE(pcs.rushing_yards, 0) > 0 "
            "         OR COALESCE(pcs.receiving_yards, 0) > 0 "
            "         OR COALESCE(CAST(json_extract(pcs.kicking_stats, '$.fgAtt') AS INTEGER), 0) > 0)"
            ")"
        ))
        playerIds = [row[0] for row in result.fetchall()]
        if not playerIds:
            return

        logger.info(f"  Backfill: reconstructing career stats for {len(playerIds)} players")
        fixed = 0

        for playerId in playerIds:
            try:
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
                        if not src:
                            continue
                        d = _json.loads(src) if isinstance(src, str) else src
                        # _json.loads('null') -> None; some legacy rows store 'null' here
                        if not d:
                            continue
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
                # Per-range FG percentages (under 20 / 20-40 / 40-50 / 50+).
                # Each pair tracks attempts (xxxAtt) and makes (xxx).
                for mkKey, attKey, percKey in (
                    ('fgUnder20', 'fgUnder20att', 'fgUnder20perc'),
                    ('fg20to40', 'fg20to40att', 'fg20to40perc'),
                    ('fg40to50', 'fg40to50att', 'fg40to50perc'),
                    ('fgOver50', 'fgOver50att', 'fgOver50perc'),
                ):
                    att = kicking.get(attKey, 0) or 0
                    if att > 0:
                        kicking[percKey] = round((kicking.get(mkKey, 0) or 0) / att * 100, 1)
                    else:
                        kicking[percKey] = 0

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
            except Exception as perPlayerErr:
                logger.info(f"  Backfill: skipped player {playerId} ({perPlayerErr})")
                continue

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

    # Tables to preserve across fresh starts. app_settings holds
    # admin-editable runtime config (feedback URL, survey toggles, etc.) —
    # those are operator settings, not season data, and should survive
    # a DB wipe. unused_names holds the player/coach name pool, which
    # admins can add to from the dashboard; that curation should not be
    # wiped by a fresh start. New names from config.json are merged in
    # on every boot via _seedUnusedNames().
    preserveTables = {"users", "beta_allowlist", "app_settings", "unused_names"}

    # Drop all non-preserved tables (reverse dependency order), then recreate
    tablesToDrop = [t for t in reversed(Base.metadata.sorted_tables)
                    if t.name not in preserveTables]
    if tablesToDrop:
        Base.metadata.drop_all(bind=engine, tables=tablesToDrop)

    # Recreate all tables (create_all is safe — skips existing preserved tables)
    Base.metadata.create_all(bind=engine)

    # Clear per-season user flags — these are scoped to season number, and
    # fresh start resets the counter to 1.  Without this reset, prior-run
    # stamps (e.g. starter_pack_claimed_season=1) carry over and incorrectly
    # match the new season-1, hiding once-per-season offers.
    try:
        with engine.connect() as conn:
            for col in ('starter_pack_claimed_season', 'favorite_team_locked_season'):
                try:
                    conn.execute(text(f"UPDATE users SET {col} = NULL"))
                except Exception:
                    pass
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to reset per-season user flags on fresh start: {e}")

    logger.info(f"Database cleared (preserved {', '.join(preserveTables)}) at {DB_PATH}")

    # Run migrations for preserved tables (e.g. new columns on users)
    _runPendingMigrations()
    _seedPackTypes()
    _seedBetaAllowlist()
    _seedAchievements()
    _seedUnusedNames()


def _seedPackTypes():
    """Seed default pack types if they don't exist.

    Per-team packs were initially seeded too, but the design walked back
    to a single "Champion Team Pack" (themed_champion) that filters to
    last season's champion roster. Existing per-team rows from older
    builds get pruned here so they can't leak into the rotation.
    """
    from database.repositories.card_repositories import PackTypeRepository
    from database.models import PackType, FeaturedPackRotation
    session = SessionLocal()
    try:
        repo = PackTypeRepository(session)
        repo.seedDefaults()

        # One-time cleanup: drop the deprecated `themed_team_*` rows + any
        # rotation rows referencing them so the rotation pool can't pick
        # them up. Idempotent — no-op once the rows are gone.
        deprecatedTeamPacks = (
            session.query(PackType)
            .filter(PackType.name.like('themed_team_%'))
            .all()
        )
        if deprecatedTeamPacks:
            deprecatedIds = [pt.id for pt in deprecatedTeamPacks]
            session.query(FeaturedPackRotation).filter(
                FeaturedPackRotation.pack_type_id.in_(deprecatedIds)
            ).delete(synchronize_session=False)
            for pt in deprecatedTeamPacks:
                session.delete(pt)
            session.flush()
            logger.info(
                f"  Pruned {len(deprecatedTeamPacks)} deprecated themed_team_* "
                f"pack rows (replaced by themed_champion)"
            )

        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"  Pack type seed/prune failed: {e}")
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
            # Tycoon tiers — floobits earned in a single season. Mirrors
            # Magnate (spent side). Targets reflect post-curve income
            # economy where a typical user earns 2-4k/season.
            {"key": "tycoon_i", "name": "Tycoon I", "category": "guidance", "scope": "per_season", "sort_order": 140, "target": 750,
             "description": "Earn 750 floobits in a single season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "tycoon_ii", "name": "Tycoon II", "category": "guidance", "scope": "per_season", "sort_order": 141, "target": 2500,
             "description": "Earn 2,500 floobits in a single season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "tycoon_iii", "name": "Tycoon III", "category": "guidance", "scope": "per_season", "sort_order": 142, "target": 5500,
             "description": "Earn 5,500 floobits in a single season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "tycoon_iv", "name": "Tycoon IV", "category": "guidance", "scope": "per_season", "sort_order": 143, "target": 10000,
             "description": "Earn 10,000 floobits in a single season.",
             "reward_config": {"floobits": 150, "packs": [], "powerups": ["income_boost"], "deferred": False}},
            {"key": "veteran", "name": "Veteran", "category": "guidance", "scope": "per_season", "sort_order": 150, "target": 20,
             "description": "Set a fantasy roster for 20+ weeks of the regular season.",
             "reward_config": {"floobits": 300, "packs": [], "powerups": ["extra_swap"], "deferred": False}},
            # Banner Week tiers — FP earned in a single week.
            # Rescaled for the Balatro pullback (FP outputs roughly halved
            # via _BAL_FP_MULT = 0.5). Targets dropped ~50% so the tiers
            # remain reachable on optimized hands during an amplify week
            # without being trivial.
            {"key": "banner_week_i", "name": "Banner Week I", "category": "guidance", "scope": "per_season", "sort_order": 160, "target": 300,
             "description": "Earn 300+ fantasy points in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "banner_week_ii", "name": "Banner Week II", "category": "guidance", "scope": "per_season", "sort_order": 161, "target": 1000,
             "description": "Earn 1,000+ fantasy points in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "banner_week_iii", "name": "Banner Week III", "category": "guidance", "scope": "per_season", "sort_order": 162, "target": 2500,
             "description": "Earn 2,500+ fantasy points in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "banner_week_iv", "name": "Banner Week IV", "category": "guidance", "scope": "per_season", "sort_order": 163, "target": 5000,
             "description": "Earn 5,000+ fantasy points in a single week.",
             "reward_config": {"floobits": 75, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Racket tiers — floobits earned from card effects in a single week
            # (renamed from Windfall to avoid clashing with the card effect of
            # the same name). Targets widened (next-season).
            {"key": "racket_i", "name": "Racket I", "category": "guidance", "scope": "per_season", "sort_order": 190, "target": 60,
             "description": "Earn 60+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "racket_ii", "name": "Racket II", "category": "guidance", "scope": "per_season", "sort_order": 191, "target": 150,
             "description": "Earn 150+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "racket_iii", "name": "Racket III", "category": "guidance", "scope": "per_season", "sort_order": 192, "target": 250,
             "description": "Earn 250+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "racket_iv", "name": "Racket IV", "category": "guidance", "scope": "per_season", "sort_order": 193, "target": 400,
             "description": "Earn 400+ floobits from card effects in a single week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Dynamo tiers — cumulative season fantasy points. Targets
            # halved to match the Balatro pullback (_BAL_FP_MULT = 0.5).
            # Tier IV is still a meaningful "great season" milestone given
            # 28 game days of compounding output.
            {"key": "dynamo_i", "name": "Dynamo I", "category": "guidance", "scope": "per_season", "sort_order": 200, "target": 2500,
             "description": "Earn 2,500 total fantasy points this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynamo_ii", "name": "Dynamo II", "category": "guidance", "scope": "per_season", "sort_order": 201, "target": 7000,
             "description": "Earn 7,000 total fantasy points this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynamo_iii", "name": "Dynamo III", "category": "guidance", "scope": "per_season", "sort_order": 202, "target": 15000,
             "description": "Earn 15,000 total fantasy points this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynamo_iv", "name": "Dynamo IV", "category": "guidance", "scope": "per_season", "sort_order": 203, "target": 30000,
             "description": "Earn 30,000 total fantasy points this season.",
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
            # Bracketeer tiers — playoff bracket points this season (28 max).
            {"key": "bracketeer_i", "name": "Bracketeer I", "category": "guidance", "scope": "per_season", "sort_order": 214, "target": 6,
             "description": "Score 6 points in the playoff bracket challenge.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "bracketeer_ii", "name": "Bracketeer II", "category": "guidance", "scope": "per_season", "sort_order": 215, "target": 12,
             "description": "Score 12 points in the playoff bracket challenge.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "bracketeer_iii", "name": "Bracketeer III", "category": "guidance", "scope": "per_season", "sort_order": 216, "target": 18,
             "description": "Score 18 points in the playoff bracket challenge.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "bracketeer_iv", "name": "Bracketeer IV", "category": "guidance", "scope": "per_season", "sort_order": 217, "target": 24,
             "description": "Score 24 points in the playoff bracket challenge.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            # Magnate tiers — cumulative season floobits spent. Targets
            # widened (next-season) so tier IV is a real spender milestone
            # given the floobit-curve income changes.
            {"key": "magnate_i", "name": "Magnate I", "category": "guidance", "scope": "per_season", "sort_order": 220, "target": 750,
             "description": "Spend 750 floobits this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "magnate_ii", "name": "Magnate II", "category": "guidance", "scope": "per_season", "sort_order": 221, "target": 2500,
             "description": "Spend 2,500 floobits this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "magnate_iii", "name": "Magnate III", "category": "guidance", "scope": "per_season", "sort_order": 222, "target": 5500,
             "description": "Spend 5,500 floobits this season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "magnate_iv", "name": "Magnate IV", "category": "guidance", "scope": "per_season", "sort_order": 223, "target": 10000,
             "description": "Spend 10,000 floobits this season.",
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
            # Compound tiers — single-week total FP multiplier (stored as
            # multiplier × 100). Rescaled (Balatro pass): with single FPx
            # cards like Snake Eyes hitting 3.10× and Cornucopia capable of
            # 5×+ on a hot week, the old 3.5× cap is hit by ONE card. Tiers
            # now require actual stacking — Tier IV needs a full FPx hand
            # with elite multipliers.
            # Bumped (next-season): amplify modifier doubles the FPx
            # bonus portion, so a hand of 4-5 modest FPx cards can hit
            # 7x on a hot week. New top tier requires both a heavily
            # stacked FPx hand AND a favorable modifier draw.
            {"key": "compound_i", "name": "Compound I", "category": "guidance", "scope": "per_season", "sort_order": 260, "target": 250,
             "description": "Reach a 2.5x total FP multiplier in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_ii", "name": "Compound II", "category": "guidance", "scope": "per_season", "sort_order": 261, "target": 450,
             "description": "Reach a 4.5x total FP multiplier in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_iii", "name": "Compound III", "category": "guidance", "scope": "per_season", "sort_order": 262, "target": 700,
             "description": "Reach a 7.0x total FP multiplier in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_iv", "name": "Compound IV", "category": "guidance", "scope": "per_season", "sort_order": 263, "target": 1000,
             "description": "Reach a 10.0x total FP multiplier in a single week.",
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
             "description": "Earn a Perfect Week and 800+ fantasy points in the same week.",
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
            {"key": "mutineer", "name": "Scorched Earth", "category": "secret", "scope": "once", "sort_order": 660, "target": 1,
             "description": "Vote to fire your coach and release every player on the roster in a single offseason.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "tribune", "name": "Tribune", "category": "secret", "scope": "once", "sort_order": 665, "target": 1,
             "description": "Cast 6 GM votes in a single season.",
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
            {"key": "anthology", "name": "Anthology", "category": "secret", "scope": "once", "sort_order": 720, "target": 1,
             "description": "Buy one of every pack type in a single season.",
             "reward_config": {"floobits": 250, "packs": ["grand"], "powerups": [], "deferred": False}},
            {"key": "flawless", "name": "Flawless", "category": "secret", "scope": "once", "sort_order": 730, "target": 1,
             "description": "Predict every playoff advancer correctly in a single bracket.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "deferred": False}},
            {"key": "pool_shark", "name": "Pool Shark", "category": "secret", "scope": "once", "sort_order": 740, "target": 1,
             "description": "Finish #1 on the season playoff bracket leaderboard.",
             "reward_config": {"floobits": 0, "packs": [], "powerups": [], "deferred": False}},
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


def _seedUnusedNames():
    """Merge player/coach names from config.json into the unused_names table.

    Idempotent — only inserts names that aren't already in the table AND
    aren't currently held by an active coach or player. Without the active-
    entity filter, names that were promoted from the pool into a coach or
    player slot get silently re-seeded on every boot, leaving the pool
    polluted with names the runtime defensive filter then has to scrub at
    every draw.

    Runs on every startup so new names added to config.json get picked up
    without wiping admin-curated additions. The unused_names table is
    preserved across fresh starts (see clear_db()), so admin additions
    survive.
    """
    from database.models import UnusedName, Coach, Player
    try:
        from config_manager import get_config
        names = get_config().get("players", [])
    except Exception:
        return
    if not names:
        return
    session = SessionLocal()
    try:
        existing = {row.name for row in session.query(UnusedName.name).all()}
        activeCoachNames = {c.name for c in session.query(Coach.name).all() if c.name}
        activePlayerNames = {p.name for p in session.query(Player.name).all() if p.name}
        inUse = activeCoachNames | activePlayerNames
        added = 0
        skipped = 0
        for name in names:
            if name in existing:
                continue
            if name in inUse:
                skipped += 1
                continue
            session.add(UnusedName(name=name))
            existing.add(name)
            added += 1
        if added or skipped:
            session.commit()
            logger.info(
                f"Seeded {added} new names from config into unused_names pool"
                + (f" (skipped {skipped} already in use by coaches/players)" if skipped else "")
            )
    except Exception as exc:
        session.rollback()
        logger.warning(f"Failed to seed unused_names: {exc}")
    finally:
        session.close()


def clear_card_data(currentSeasonOnly: bool = False):
    """Clear card-related data while preserving everything else.

    By default this nukes EVERY card-related row across all seasons —
    historical card collections, equip records, weekly bonuses, the works.
    Used for full system rebuilds where every template must regenerate.

    Pass currentSeasonOnly=True to limit the wipe to the latest season's
    data only. Prior seasons' templates, user_cards, equip records, weekly
    bonuses, modifiers, and shop entries remain intact. The latest season is
    determined from MAX(card_templates.season_created); if no templates
    exist, the function no-ops. CardUpgradeLog and PackOpening (audit logs)
    are skipped in scoped mode — their rows can keep references to deleted
    user_cards/templates without breaking anything (no FK enforcement).
    """
    from sqlalchemy import func
    from .models import (
        CardTemplate, UserCard, EquippedCard, WeeklyCardBonus,
        CardUpgradeLog, PackOpening, FeaturedShopCard,
        WeeklyModifier, UserModifierOverride,
    )

    session = SessionLocal()
    try:
        if currentSeasonOnly:
            currentSeason = session.query(func.max(CardTemplate.season_created)).scalar()
            if currentSeason is None:
                logger.info("Card data scoped-clear: no templates exist; nothing to delete")
                return

            templateIdsSubquery = session.query(CardTemplate.id).filter(
                CardTemplate.season_created == currentSeason
            ).subquery()
            userCardIdsSubquery = session.query(UserCard.id).filter(
                UserCard.card_template_id.in_(session.query(templateIdsSubquery))
            ).subquery()

            # Delete in reverse dependency order, scoped to currentSeason
            session.query(WeeklyCardBonus).filter(
                WeeklyCardBonus.season == currentSeason
            ).delete(synchronize_session=False)
            session.query(FeaturedShopCard).filter(
                FeaturedShopCard.season == currentSeason
            ).delete(synchronize_session=False)
            session.query(UserModifierOverride).filter(
                UserModifierOverride.season == currentSeason
            ).delete(synchronize_session=False)
            session.query(WeeklyModifier).filter(
                WeeklyModifier.season == currentSeason
            ).delete(synchronize_session=False)
            session.query(EquippedCard).filter(
                EquippedCard.season == currentSeason
            ).delete(synchronize_session=False)
            # UserCard has no season column — filter via the template subquery
            session.query(UserCard).filter(
                UserCard.id.in_(session.query(userCardIdsSubquery))
            ).delete(synchronize_session=False)
            session.query(CardTemplate).filter(
                CardTemplate.season_created == currentSeason
            ).delete(synchronize_session=False)
            # CardUpgradeLog + PackOpening intentionally skipped — audit logs
            # with no FK constraint, fine to keep with orphan references
            session.commit()
            logger.info(
                f"Card data cleared for season {currentSeason} — templates will regenerate"
            )
        else:
            # Delete in reverse dependency order — full wipe
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
            logger.info("Card data cleared (all seasons) — templates will regenerate on season start")
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
