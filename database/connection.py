"""Database connection and session management."""

import os
import re as _re
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
    _collapseLiveGenerationalNames()
    _normalizeNamePool()
    _seedUnusedNames()
    _seedCuratedNames()
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
            # Champion roster snapshot (player IDs at the Floos Bowl) so the
            # champion classification + pack don't drift to the post-offseason roster.
            ('champion_player_ids', 'TEXT'),
            # Rich All-Pro team (offense+defense split) for durable recap rebuild.
            ('all_pro_team', 'TEXT'),
            # Frozen MVP ballot (top-5 candidate dicts) captured at season end so
            # voting + results show the same candidates after stats reset.
            ('mvp_ballot', 'TEXT'),
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

        # Per-game chaos ruleset — see the note on Game.chaos_rules. Without it a strange
        # play in a Criticality game cannot be judged, because the rules it was played
        # under no longer exist anywhere.
        try:
            conn.execute(text("ALTER TABLE games ADD COLUMN chaos_rules TEXT"))
            conn.commit()
            logger.info("  Migration: added games.chaos_rules")
        except Exception:
            conn.rollback()  # column already exists — ignore

        # Postgame personality lines — see the note on Game.postgame_quotes. They used to
        # live only in the in-memory play feed, which now disappears minutes after the
        # final whistle.
        try:
            conn.execute(text("ALTER TABLE games ADD COLUMN postgame_quotes TEXT"))
            conn.commit()
            logger.info("  Migration: added games.postgame_quotes")
        except Exception:
            conn.rollback()  # column already exists — ignore

        # Who won — see the note on Game.winner_team_id. Formats where points do not
        # decide (frames) make a score comparison the wrong question, so the winner is
        # stored rather than re-derived by every reader.
        try:
            conn.execute(text("ALTER TABLE games ADD COLUMN winner_team_id INTEGER"))
            conn.commit()
            logger.info("  Migration: added games.winner_team_id")
        except Exception:
            conn.rollback()  # column already exists — ignore

        # Glitch marks on owned cards (docs/GLITCH_CARDS.md).
        # ⚠️ `glitch_triggers_used` DEFAULTS TO 0 FOR EVERY EXISTING GLITCH, which hands the
        # 48 already-marked production cards a full lifespan from the day expiry ships
        # rather than retiring them on arrival. That is the intended direction: nobody
        # loses something they were already holding, which is the same rule the glitch
        # system runs on end to end (a glitch never takes anything away).
        for _col, _def in (('glitched', 'BOOLEAN DEFAULT 0 NOT NULL'),
                           ('glitched_season', 'INTEGER'),
                           ('glitched_week', 'INTEGER'),
                           ('glitch_triggers_used', 'INTEGER DEFAULT 0 NOT NULL')):
            try:
                conn.execute(text(f"ALTER TABLE user_cards ADD COLUMN {_col} {_def}"))
                conn.commit()
                logger.info(f"  Migration: added user_cards.{_col}")
            except Exception:
                conn.rollback()  # column already exists — ignore

        # Returning stats blob (punt returns) on the three player stat tables, plus
        # team_season_stats — the model carries the column there too, and without the
        # migration every query against that table breaks on an existing DB.
        for _tbl in ('game_player_stats', 'player_season_stats', 'player_career_stats',
                     'team_season_stats'):
            try:
                conn.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN returning_stats TEXT"))
                conn.commit()
                logger.info(f"  Migration: added {_tbl}.returning_stats")
            except Exception:
                conn.rollback()  # column already exists — ignore

        # Team avatar override: draw the mark with primary/secondary swapped, so a club
        # can flip its kit colors without the logo's figure/ground flipping too.
        for col, colDef in [
            ('logo_invert', 'INTEGER DEFAULT 0'),
            # Continuous form offset (roughly ±FORM_MAX) — where the club sits in
            # its own hot/cold arc. Persisted so a mid-season restart doesn't
            # flatten every team back to neutral form.
            ('form_offset', 'REAL DEFAULT 0'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE teams ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added teams.{col}")
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

        # Anomaly weekly-tick idempotency guard — prevents a mid-week restart
        # from re-running the (non-idempotent) tick and double-counting that
        # week's attention contributions.
        try:
            conn.execute(text("ALTER TABLE league_anomaly_state ADD COLUMN last_tick_week INTEGER"))
            conn.commit()
            logger.info("  Migration: added league_anomaly_state.last_tick_week")
        except Exception:
            conn.rollback()

        # L4 awakened signature abilities (offensive + defensive) on anomaly_state — legacy from an
        # earlier P1 model; the live model stores the single career power on players.signature_power.
        for _col in ("offensive_ability", "defensive_ability"):
            try:
                conn.execute(text(f"ALTER TABLE anomaly_state ADD COLUMN {_col} VARCHAR(40)"))
                conn.commit()
                logger.info(f"  Migration: added anomaly_state.{_col}")
            except Exception:
                conn.rollback()

        # L4 awakened signature power — the player's ONE career power.
        try:
            conn.execute(text("ALTER TABLE players ADD COLUMN signature_power VARCHAR(40)"))
            conn.commit()
            logger.info("  Migration: added players.signature_power")
        except Exception:
            conn.rollback()

        # Cores exchange threading on persisted league-news items, so multi-Core
        # conversations group under one header on refresh (not just live).
        # `team_id` and `stats_json` arrived with the front-page news feed: team events
        # (clinch / elimination / upset) need a crest to link, and a LEAD item needs its
        # four supporting numbers. An item with no stats_json is row-only, which is also
        # how the feed decides what is allowed to lead.
        for col, colDef in [
            ("exchange_id", "VARCHAR(40)"),
            ("turn_index", "INTEGER"),
            ("turn_count", "INTEGER"),
            ("team_id", "INTEGER"),
            ("stats_json", "TEXT"),
            ("lead_weight", "FLOAT"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE league_news_items ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added league_news_items.{col}")
            except Exception:
                conn.rollback()

        # Division membership. In-memory only until now, so a restart mid-season dropped
        # every club out of its division (see the model comment).
        try:
            conn.execute(text("ALTER TABLE teams ADD COLUMN division VARCHAR(50)"))
            conn.commit()
            logger.info("  Migration: added teams.division")
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

        # HoF induction season — drives the "Class of Season N" grouping.
        try:
            conn.execute(text("ALTER TABLE players ADD COLUMN hof_season INTEGER"))
            conn.commit()
            logger.info("  Migration: added players.hof_season")
        except Exception:
            conn.rollback()

        # Retention limit / re-sign-once (parity): times the current team has
        # re-signed this player (resets to 0 on a walk to FA).
        try:
            conn.execute(text("ALTER TABLE players ADD COLUMN team_resign_count INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added players.team_resign_count")
        except Exception:
            conn.rollback()

        # Cores rule-change vote: the applied change (from -> to) on the winning
        # window, JSON-encoded so bool/float/int round-trip. (The table itself is
        # created by create_all; these columns were added after it shipped.)
        for _col in ("winner_prev", "winner_value"):
            try:
                conn.execute(text(f"ALTER TABLE rule_vote_windows ADD COLUMN {_col} TEXT"))
                conn.commit()
                logger.info(f"  Migration: added rule_vote_windows.{_col}")
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

        # Per-game WPA value (offense + defensive unit-share) + snaps on
        # game_player_stats — feeds the season WPA MVP + All-Pro defense metric.
        for _wpaCol, _wpaType in (
            ("wpa", "REAL DEFAULT 0"),
            ("def_wpa", "REAL DEFAULT 0"),
            ("wpa_snaps", "INTEGER DEFAULT 0"),
            ("def_snaps", "INTEGER DEFAULT 0"),
        ):
            try:
                conn.execute(text(f"ALTER TABLE game_player_stats ADD COLUMN {_wpaCol} {_wpaType}"))
                conn.commit()
            except Exception:
                conn.rollback()

        # Initial-player snapshot on fantasy_rosters — Loyalty card reads this
        try:
            conn.execute(text("ALTER TABLE fantasy_rosters ADD COLUMN initial_player_ids TEXT"))
            conn.commit()
            logger.info("  Migration: added fantasy_rosters.initial_player_ids")
        except Exception:
            conn.rollback()

        # Card upgrade tier on user_cards (1-4 / I-IV) — leveled via same-effect
        # duplicate + Floobits; scales the card's output (or a flat dividend for
        # structural/no-output cards).
        try:
            conn.execute(text("ALTER TABLE user_cards ADD COLUMN tier INTEGER DEFAULT 1 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added user_cards.tier")
        except Exception:
            conn.rollback()

        # Card Vault — permanent, irreversible collection (drives collection
        # achievements; vaulted cards can't equip/sell/combine).
        try:
            conn.execute(text("ALTER TABLE user_cards ADD COLUMN vaulted BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added user_cards.vaulted")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE user_cards ADD COLUMN vaulted_at DATETIME"))
            conn.commit()
            logger.info("  Migration: added user_cards.vaulted_at")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE user_cards ADD COLUMN vault_position INTEGER"))
            conn.commit()
            logger.info("  Migration: added user_cards.vault_position")
        except Exception:
            conn.rollback()

        # The component ledger — shared by Synth Components and (later) Chrome
        # Components. A balance is a COUNT of unconsumed rows, never a stored integer.
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS user_components ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER NOT NULL, "
                "component_type VARCHAR(20) NOT NULL, "
                "source VARCHAR(40) NOT NULL, "
                "season INTEGER NOT NULL, "
                "granted_at DATETIME, "
                "consumed_at DATETIME, "
                "consumed_for VARCHAR(80), "
                "earmark_target_id INTEGER)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_user_components_balance "
                "ON user_components (user_id, component_type, season, consumed_at)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_user_components_source "
                "ON user_components (user_id, component_type, season, source)"
            ))
            conn.commit()
            logger.info("  Migration: ensured user_components table")
        except Exception:
            conn.rollback()
        # Card Showcase — seasonal 8-slot featured-card payout (vaulted cards).
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS showcase_slots ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER NOT NULL, "
                "season INTEGER NOT NULL, "
                "slot_number INTEGER NOT NULL, "
                "user_card_id INTEGER NOT NULL, "
                "created_at DATETIME, "
                "UNIQUE(user_id, season, slot_number))"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_showcase_slots_user_season "
                "ON showcase_slots (user_id, season)"
            ))
            conn.commit()
            logger.info("  Migration: ensured showcase_slots table")
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

        # Division titles on teams (8 divisions, owner 2026-08-07).
        try:
            conn.execute(text("ALTER TABLE teams ADD COLUMN division_titles JSON"))
            conn.commit()
            logger.info("  Migration: added teams.division_titles")
        except Exception:
            conn.rollback()

        # Permanent record of admin/Discord-approved names. See CuratedName: config.json
        # cannot hold these because the container copy is ephemeral.
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS curated_names (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(120) NOT NULL UNIQUE,
                    source VARCHAR(20),
                    created_at DATETIME
                )"""))
            conn.commit()
        except Exception:
            conn.rollback()

        # The cross-reset season archive. Must exist before any wipe can populate it.
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS league_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    era INTEGER NOT NULL DEFAULT 1,
                    era_label VARCHAR(80),
                    season INTEGER NOT NULL,
                    champion VARCHAR(120),
                    league_champions TEXT,
                    mvp VARCHAR(120),
                    created_at DATETIME,
                    UNIQUE(era, season)
                )"""))
            conn.commit()
        except Exception:
            conn.rollback()

        # One-change-per-season username renames. Inline migration because alembic is not
        # run on deploy — this is what actually lands the column on the prod DB.
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN username_changed_season INTEGER"))
            conn.commit()
            logger.info("  Migration: added users.username_changed_season")
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

        # Fantasy/Cards fusion: EquippedCard slots become POSITION-LOCKED. Add the `slot`
        # string (QB/RB/WR1/WR2/TE/K/FLEX) + a unique index enforcing one card per position
        # slot per user/week. Pre-fusion rows keep slot=NULL (SQLite treats NULLs as distinct,
        # so they don't collide); new equips always set it.
        try:
            conn.execute(text("ALTER TABLE equipped_cards ADD COLUMN slot TEXT"))
            conn.commit()
            logger.info("  Migration: added equipped_cards.slot")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_equipped_card_slot_pos "
                "ON equipped_cards(user_id, season, week, slot)"))
            conn.commit()
            logger.info("  Migration: created uq_equipped_card_slot_pos index")
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

        # True-skill columns on player_attributes (parity + prospect model,
        # docs/PARITY_PROSPECT_PLAN.md). Default 0 → loader backfills to the
        # current attr until the one-time percentile re-map sets them.
        for col in [
            'true_skill_speed', 'true_skill_hands', 'true_skill_reach',
            'true_skill_agility', 'true_skill_power', 'true_skill_arm_strength',
            'true_skill_accuracy', 'true_skill_leg_strength',
        ]:
            try:
                conn.execute(text(f"ALTER TABLE player_attributes ADD COLUMN {col} INTEGER DEFAULT 0"))
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
                ('wpa', 'REAL DEFAULT 0'), ('def_wpa', 'REAL DEFAULT 0'),
                ('wpa_snaps', 'INTEGER DEFAULT 0'), ('def_snaps', 'INTEGER DEFAULT 0'),
                # Nullable on purpose: 0 would read as "played terribly" on
                # every season that predates the column.
                ('performance_rating', 'INTEGER'), ('defensive_performance_rating', 'INTEGER'),
            ]),
            ('team_feed_posts', [
                # Nullable: a team-page post belongs to no game.
                ('game_id', 'INTEGER'),
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

        # Player sentiment ratings (AFO plan Part D) — the 1-5 standing stance
        # that nudges the autonomous GM brain.
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS player_sentiment_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    UNIQUE (user_id, player_id)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sentiment_player "
                              "ON player_sentiment_ratings (player_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sentiment_user "
                              "ON player_sentiment_ratings (user_id)"))
            conn.commit()
            logger.info("  Migration: player_sentiment_ratings ensured")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: player_sentiment_ratings skipped: {e}")

        # Coach 1-5 ratings (AFO plan Part D) — drives GM fire/leave heat.
        # The table briefly held a binary ±1 `value`; it never shipped, so the
        # old shape is dropped outright rather than migrated.
        try:
            cols = [r[1] for r in conn.execute(text(
                "PRAGMA table_info(coach_sentiment_votes)")).fetchall()]
            if cols and 'value' in cols and 'rating' not in cols:
                conn.execute(text("DROP TABLE coach_sentiment_votes"))
                conn.commit()
                logger.info("  Migration: dropped pre-release coach vote table (±1 -> 1-5)")
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS coach_sentiment_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    coach_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    UNIQUE (user_id, coach_id)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_coach_sentiment_coach "
                              "ON coach_sentiment_votes (coach_id)"))
            conn.commit()
            logger.info("  Migration: coach_sentiment_votes ensured")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: coach_sentiment_votes skipped: {e}")

        # Auto-generated feed posts carry a marker so re-rating can replace the
        # previous one instead of stacking contradictory opinions.
        try:
            conn.execute(text("ALTER TABLE team_feed_posts ADD COLUMN is_auto BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added team_feed_posts.is_auto")
        except Exception:
            conn.rollback()

        # Team feed posts (AFO plan Part D) — the ephemeral, loud half of fan
        # sentiment. Text is never user-supplied (post_key indexes the catalog).
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS team_feed_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    post_key VARCHAR(32) NOT NULL,
                    target_type VARCHAR(8) NOT NULL,
                    target_player_id INTEGER,
                    created_at DATETIME
                )
            """))
            for idx, cols in (("idx_feed_team_created", "team_id, created_at"),
                              ("idx_feed_target_player", "target_player_id"),
                              ("idx_feed_user_created", "user_id, created_at")):
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx} "
                                  f"ON team_feed_posts ({cols})"))
            conn.commit()
            logger.info("  Migration: team_feed_posts ensured")
        except Exception as e:
            conn.rollback()
            logger.warning(f"  Migration: team_feed_posts skipped: {e}")

        # Coach fanTrust (how much fan sentiment moves the GM's roster calls)
        try:
            conn.execute(text("ALTER TABLE coaches ADD COLUMN fan_trust INTEGER DEFAULT 80"))
            conn.commit()
            logger.info("  Migration: added coaches.fan_trust")
        except Exception:
            conn.rollback()

        # Coach attitude (locker-room presence: toxic ↔ leader spectrum)
        try:
            conn.execute(text("ALTER TABLE coaches ADD COLUMN attitude INTEGER DEFAULT 80"))
            conn.commit()
            logger.info("  Migration: added coaches.attitude")
        except Exception:
            conn.rollback()

        # ⚠️ Seasons at THIS club, distinct from the career `seasons_coached`. A fired GM
        # joins the pool and can be hired elsewhere carrying the career count with them, so
        # tenure pressure read off that would blame a new GM for a predecessor's drought.
        # Existing rows seed from the career count, exact for anyone who has only ever had
        # one job — true of every coach in production when this landed.
        # ⚠️ Sentiment ratings carry the season they were cast, so an old verdict decays
        # toward neutral instead of counting forever at full strength. Existing rows are
        # stamped with the CURRENT season — dating them 0 would decay every rating in the
        # league to the floor on the first boot after this ships, silently wiping the
        # standing of every player and GM fans have actually rated.
        try:
            cur = conn.execute(text(
                "SELECT COALESCE((SELECT current_season FROM simulation_state ORDER BY id LIMIT 1),"
                " (SELECT MAX(season_number) FROM seasons), 1)")).scalar() or 1
            for tbl in ("player_sentiment_ratings", "coach_sentiment_votes"):
                try:
                    conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN season INTEGER DEFAULT 0"))
                    conn.execute(text(f"UPDATE {tbl} SET season = :s WHERE COALESCE(season, 0) = 0"),
                                 {"s": int(cur)})
                except Exception:
                    pass
            conn.commit()
            logger.info(f"  Migration: added season to sentiment ratings (seeded {cur})")
        except Exception:
            conn.rollback()

        try:
            conn.execute(text("ALTER TABLE coaches ADD COLUMN seasons_with_team INTEGER DEFAULT 0"))
            conn.execute(text("UPDATE coaches SET seasons_with_team = COALESCE(seasons_coached, 0)"))
            conn.commit()
            logger.info("  Migration: added coaches.seasons_with_team")
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
                ('halftime_show_url', ''),
                ('halftime_show_pause_seconds', '120'),
                # Anomaly / Criticality runtime knobs (override constants.py at runtime).
                ('anomalies_enabled', 'true'),
                ('criticality_enabled', 'false'),
                ('awakened_powers_enabled', 'false'),
                ('anomaly_intensity', 'normal'),
                # Awakened tuning dials (override constants.py): per-position touches-per-game to fill
                # the meter (lower = fires more often) + the defensive fire gate %.
                ('awakened_involve_qb', '31'),
                ('awakened_involve_rb', '19'),
                ('awakened_involve_wr', '5.8'),
                ('awakened_involve_te', '5.5'),
                ('awakened_involve_k', '1.7'),
                ('awakened_def_fire_chance', '35'),
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

        # Supporter income (feature/fan-income): fan-loyalty dividend state.
        # supporter_weeks = tenure backing the current favorite team; persists
        # across seasons, soft-reset on a team change. supporter_unclaimed =
        # accrued Floobits awaiting claim (the idle pool).
        for col, colDef in [
            ('supporter_weeks', 'INTEGER DEFAULT 0 NOT NULL'),
            ('supporter_unclaimed', 'INTEGER DEFAULT 0 NOT NULL'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {colDef}"))
                conn.commit()
                logger.info(f"  Migration: added users.{col}")
            except Exception:
                conn.rollback()

        # Spectator cheer-bar state (feature/fan-income).
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS spectator_progress ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER NOT NULL UNIQUE, "
                "bar_fill REAL NOT NULL DEFAULT 0, "
                "week_marker INTEGER NOT NULL DEFAULT 0, "
                "weekly_floobits INTEGER NOT NULL DEFAULT 0, "
                "weekly_segments INTEGER NOT NULL DEFAULT 0, "
                "updated_at DATETIME)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_spectator_progress_user "
                "ON spectator_progress(user_id)"
            ))
            conn.commit()
            logger.info("  Migration: ensured spectator_progress table")
        except Exception:
            conn.rollback()

        # Supporter dividend ledger — itemized breakdown of the current unclaimed
        # pool (feature/fan-income). Rows are deleted on claim, so it only holds
        # weeks since the last claim.
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS supporter_dividends ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER NOT NULL, "
                "season INTEGER NOT NULL, "
                "week INTEGER NOT NULL, "
                "amount INTEGER NOT NULL, "
                "breakdown_json TEXT, "
                "created_at DATETIME, "
                "UNIQUE(user_id, season, week))"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_supporter_dividends_user "
                "ON supporter_dividends(user_id)"
            ))
            conn.commit()
            logger.info("  Migration: ensured supporter_dividends table")
        except Exception:
            conn.rollback()

        # Fan-voted awards — MVP & Hall of Fame (feature/awards-voting).
        # League-wide votes (no team_id) + rolling HoF ballot state.
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS award_votes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER NOT NULL, "
                "season INTEGER NOT NULL, "
                "award_type VARCHAR(8) NOT NULL, "
                "target_player_id INTEGER NOT NULL, "
                "created_at DATETIME, "
                "UNIQUE(user_id, season, award_type, target_player_id))"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_award_votes_season_type "
                "ON award_votes(season, award_type)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_award_votes_user_season "
                "ON award_votes(user_id, season)"
            ))
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS hof_ballot_entries ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "player_id INTEGER NOT NULL UNIQUE, "
                "first_eligible_season INTEGER NOT NULL, "
                "seasons_remaining INTEGER NOT NULL, "
                "status VARCHAR(12) NOT NULL DEFAULT 'on_ballot', "
                "inducted_season INTEGER, "
                "created_at DATETIME, "
                "updated_at DATETIME)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_hof_ballot_status "
                "ON hof_ballot_entries(status)"
            ))
            conn.commit()
            logger.info("  Migration: ensured award_votes + hof_ballot_entries tables")
        except Exception:
            conn.rollback()

        # Team facilities (Markets→Facilities system, feature/facilities).
        # Persistent per-(team, facility_key) level. Seeded from legacy
        # funding_tier by _seedTeamFacilitiesFromTiers (backfill, gated flag).
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS team_facilities ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "team_id INTEGER NOT NULL, "
                "facility_key VARCHAR(32) NOT NULL, "
                "level INTEGER NOT NULL DEFAULT 0, "
                "UNIQUE(team_id, facility_key))"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_team_facility_team "
                "ON team_facilities(team_id)"
            ))
            conn.commit()
            logger.info("  Migration: ensured team_facilities table")
        except Exception:
            conn.rollback()

        # pending_names — recycled retiree names held until available_season
        # before they re-enter the usable pool (NAME_REUSE_DELAY_SEASONS).
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS pending_names ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name VARCHAR(100) NOT NULL, "
                "available_season INTEGER NOT NULL)"
            ))
            conn.commit()
            logger.info("  Migration: ensured pending_names table")
        except Exception:
            conn.rollback()

        # Facility economy (Phase 2): projects queue, treasury, upkeep funding.
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS facility_projects ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "team_id INTEGER NOT NULL, "
                "facility_key VARCHAR(32) NOT NULL, "
                "kind VARCHAR(8) NOT NULL, "
                "target_level INTEGER NOT NULL, "
                "cost_shares FLOAT NOT NULL, "
                "funded INTEGER NOT NULL DEFAULT 0, "
                "opened_season INTEGER NOT NULL, "
                "status VARCHAR(8) NOT NULL DEFAULT 'open', "
                "built_season INTEGER)"
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facility_project_team ON facility_projects(team_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facility_project_status ON facility_projects(status)"))
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS team_treasury ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "team_id INTEGER NOT NULL UNIQUE, "
                "balance INTEGER NOT NULL DEFAULT 0)"
            ))
            # upkeep_funded on team_facilities (ADD COLUMN is a no-op if present)
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(team_facilities)")).fetchall()]
            if 'upkeep_funded' not in cols:
                conn.execute(text("ALTER TABLE team_facilities ADD COLUMN upkeep_funded INTEGER NOT NULL DEFAULT 0"))
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS facility_votes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "team_id INTEGER NOT NULL, "
                "user_id INTEGER NOT NULL, "
                "facility_key VARCHAR(32) NOT NULL, "
                "season INTEGER NOT NULL, "
                "UNIQUE(team_id, user_id, season))"
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_facility_vote_team_season ON facility_votes(team_id, season)"))
            conn.commit()
            logger.info("  Migration: ensured facility_projects + team_treasury + upkeep_funded + facility_votes")
        except Exception:
            conn.rollback()

        # Clear stale will_retire on already-retired players. The flag is set at
        # week 22 and (historically) never reset, so retirees kept carrying it.
        # Idempotent.
        try:
            res = conn.execute(text(
                "UPDATE players SET will_retire = 0 "
                "WHERE service_time = 'Retired' AND will_retire = 1"
            ))
            conn.commit()
            if res.rowcount:
                logger.info(f"  Migration: cleared stale will_retire on {res.rowcount} retired player(s)")
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

        # attitude_baseline — the disposition anchor the drift mean-reverts toward.
        # Existing players have DRIFTED attitudes (a decade of losing-team souring),
        # so anchoring to their current value would lock in the manufactured toxicity.
        # Backfill estimates disposition by pulling the current attitude halfway back
        # toward neutral (80): a drifted toxic recovers, a genuine sour stays low-ish.
        # In the same try as the ADD COLUMN so the backfill runs ONCE (re-boots throw
        # on the existing column and skip it).
        try:
            conn.execute(text("ALTER TABLE player_attributes ADD COLUMN attitude_baseline INTEGER DEFAULT 80"))
            conn.execute(text(
                "UPDATE player_attributes SET attitude_baseline = "
                "CAST(ROUND(attitude + (80 - attitude) * 0.5) AS INTEGER) WHERE attitude IS NOT NULL"))
            # One-time rebalance: snap the CURRENT attitude to the recovered baseline so the
            # decade of manufactured toxicity clears immediately on deploy, rather than healing
            # gradually over ~1.5 seasons of reversion. (Removes both the down-drift on soured
            # players AND the up-drift inflation on perennial winners — everyone resets to their
            # estimated disposition.) Validated on a prod copy: toxic 18% -> 2%.
            conn.execute(text(
                "UPDATE player_attributes SET attitude = attitude_baseline WHERE attitude IS NOT NULL"))
            conn.commit()
            logger.info("  Migration: added player_attributes.attitude_baseline (+ disposition backfill + rebalance)")
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
            # Veteran's powerup was extra_swap, retired in the fusion — map to income_boost
            # so this legacy 'random' remap never resurrects the dead slug.
            conn.execute(text(
                "UPDATE pending_rewards SET slug = 'income_boost' "
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
        # Featured-shop rows gain a kind so the fantasy daily selection and the
        # collection selection can share one table without mixing.
        try:
            conn.execute(text(
                "ALTER TABLE featured_shop_cards ADD COLUMN kind VARCHAR(20) DEFAULT 'fantasy' NOT NULL"))
            conn.commit()
            logger.info("  Migration: added featured_shop_cards.kind")
        except Exception:
            conn.rollback()
        # Showpiece: collected, never fielded. Default 0 so every existing card
        # stays a normal fantasy card.
        try:
            conn.execute(text(
                "ALTER TABLE card_templates ADD COLUMN is_showpiece BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added card_templates.is_showpiece")
        except Exception:
            conn.rollback()
        # Synthetic: equippable, never collectible. Default 0 so every existing card
        # stays a real pull — nothing minted before this column existed can be one,
        # since the only path that creates them is the base-target transplant.
        try:
            conn.execute(text(
                "ALTER TABLE card_templates ADD COLUMN is_synthetic BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("  Migration: added card_templates.is_synthetic")
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
        # FA ballot position priority: a fan's preferred order to fill open slots
        # once all voted players are taken (JSON array of position values 1-5).
        # NULL = no preference (falls back to best-available-by-rating).
        try:
            conn.execute(text("ALTER TABLE gm_fa_ballots ADD COLUMN position_priority TEXT"))
            conn.commit()
            logger.info("  Migration: added gm_fa_ballots.position_priority")
        except Exception:
            conn.rollback()
        # Per-format display state at completion (innings line score, frames results,
        # chess-clock budgets) as JSON — the box-score breakdown that has no dedicated
        # columns. NULL for standard games and for anything already final (that state
        # only ever lived in the live broadcast, so there's nothing to backfill from).
        try:
            conn.execute(text("ALTER TABLE games ADD COLUMN format_state TEXT"))
            conn.commit()
            logger.info("  Migration: added games.format_state")
        except Exception:
            conn.rollback()
        # Full per-team box score at completion as JSON. The dedicated home_/away_ stat
        # columns miss first downs and third/fourth-down conversions, which are TEAM
        # events and so are not recoverable from game_player_stats. NULL for anything
        # already final — those totals only lived on the live game object.
        try:
            conn.execute(text("ALTER TABLE games ADD COLUMN team_stats TEXT"))
            conn.commit()
            logger.info("  Migration: added games.team_stats")
        except Exception:
            conn.rollback()
        # Body prose for hand-written league-news announcements. NULL for every
        # system-published item, which is all of them before this column existed.
        try:
            conn.execute(text("ALTER TABLE league_news_items ADD COLUMN body TEXT"))
            conn.commit()
            logger.info("  Migration: added league_news_items.body")
        except Exception:
            conn.rollback()
        # Pinned announcements are fetched outside the feed's newest-N window, so a
        # notice can outlive a busy slate. Defaulted at the column so existing rows
        # read as unpinned rather than NULL.
        try:
            conn.execute(text(
                "ALTER TABLE league_news_items ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added league_news_items.pinned")
        except Exception:
            conn.rollback()
        # An achievement whose system was removed is retired rather than deleted — the
        # row has to stay so the people who earned it keep it. Defaulted at the column
        # so every existing template reads as live.
        try:
            conn.execute(text(
                "ALTER TABLE achievements ADD COLUMN retired BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added achievements.retired")
        except Exception:
            conn.rollback()
        # Division and league records, which drive the playoff tiebreaker and had no
        # home in the database at all. Defaulted at the column; the backfill below
        # reconstructs them for a season already in progress.
        for _col in ('div_wins', 'div_losses', 'div_ties',
                     'lg_wins', 'lg_losses', 'lg_ties'):
            try:
                conn.execute(text(
                    f"ALTER TABLE team_season_stats ADD COLUMN {_col} INTEGER NOT NULL DEFAULT 0"))
                conn.commit()
                logger.info(f"  Migration: added team_season_stats.{_col}")
            except Exception:
                conn.rollback()
        # Loyalty override for the auto-picker. Defaulted at the column so every
        # existing account reads as opted out rather than NULL.
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN auto_pick_never_against_favorite "
                "BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
            logger.info("  Migration: added users.auto_pick_never_against_favorite")
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
    _backfillAllProGates()      # before the text refresh: all_in / honor_roll print the threshold
    _refreshCardEffectText()

    # One-time data backfills: reconstruct missing data from GamePlayerStats
    _backfillPlayerSeasonTeamIds()
    _backfillPlayerSeasonStatsFromGames()
    _backfillPlayerCareerStatsFromGames()
    # Repair historically under-counted career rows (orphaned stat-tracker ref,
    # fixed forward in d3825a9) by rebuilding career = SUM(player_season_stats).
    # Runs BEFORE players load into memory so the corrected rows hydrate
    # careerStatsDict and the in-memory dict can't clobber the fix.
    _recomputeCareerStatsFromSeasons()
    # Reconstruct champion roster snapshots for seasons that ended before the
    # snapshot existed — so the Champion classification + pack key off who actually
    # won, even for past titles. Sourced from players.league_championships (stamped
    # at the Floos Bowl, before any offseason churn). Runs BEFORE the next season's
    # card generation so newly-generated Champion cards are correct.
    _backfillChampionRosterSnapshots()
    _backfillGameWinners()
    _backfillTeamPeakStreaks()
    _backfillCoachFanTrust()
    _backfillCurrencyTransactionSeason()
    _migrateEditionRename()          # rename slugs BEFORE any edition-keyed backfill
    _backfillCardTemplateOutputType()
    _backfillFloorTemplates()
    # Tier→facilities migration: seed team_facilities from current market tiers
    # so facility-derived effects reproduce today's tier perks at launch.
    _seedTeamFacilitiesFromTiers()


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


def _migrateEditionRename():
    """Rename edition slugs to match the display (fusion): the first effect tier 'base'
    (Metallic) becomes 'metallic', and the old no-effect FLOOR print 'standard' (where it
    exists) becomes 'base'. Runs the swaps in order (metallic first) so they never collide.

    Guarded on the ABSENCE of any 'metallic' row = not yet migrated. This is the reliable
    trigger for BOTH shapes of legacy DB: (a) pre-floor prod, which has 'base'=Metallic and
    no floor edition at all, and (b) a DB that already grew a 'standard' floor. After the
    migration, 'base' means the floor and must never be renamed again — the 'metallic'-exists
    guard makes that idempotent. Only card_templates carries an edition column; user cards
    resolve their edition through the template, so this is the only table to touch."""
    from sqlalchemy import text
    conn = engine.connect()
    try:
        if conn.execute(text("SELECT COUNT(*) FROM card_templates WHERE edition = 'metallic'")).scalar():
            conn.rollback()  # already migrated (or a fresh DB generated with the new slugs)
            return
        hasOldBase = conn.execute(text("SELECT COUNT(*) FROM card_templates WHERE edition = 'base'")).scalar()
        hasStandard = conn.execute(text("SELECT COUNT(*) FROM card_templates WHERE edition = 'standard'")).scalar()
        if not (hasOldBase or hasStandard):
            conn.rollback()  # empty / nothing to rename
            return
        # 'base' (Metallic) -> 'metallic' FIRST (empties 'base'), then legacy 'standard' floor
        # -> 'base'. The floor backfill (next) tops up any player still missing a 'base' floor.
        conn.execute(text("UPDATE card_templates SET edition = 'metallic' WHERE edition = 'base'"))
        conn.execute(text("UPDATE card_templates SET edition = 'base' WHERE edition = 'standard'"))
        conn.commit()
        logger.info("  Migration: renamed card editions (base->metallic; standard->base floor)")
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Migration: edition rename skipped ({e})")
    finally:
        conn.close()


def _backfillFloorTemplates():
    """Ensure every season that has card templates also has the no-effect 'base' FLOOR
    template per player. The floor edition (effectName='none') was added after some DBs
    generated their season templates, and the per-season regen guard (existingCount > 0)
    prevents re-minting the missing floor. Without it the starter's floor-first query falls
    back to Metallic. Create the missing floor templates from each player's existing
    'metallic' template. Runs AFTER _migrateEditionRename, so it uses the new slugs.
    Idempotent (only creates where absent)."""
    import json as _json
    from datetime import datetime as _dt
    from managers.cardEffects import buildEffectConfig
    from managers.cardManager import getSellValue
    from sqlalchemy import text
    conn = engine.connect()
    try:
        rows = conn.execute(text('''
            SELECT t1.season_created, t1.player_id, t1.player_name, t1.team_id,
                   t1.player_rating, t1.position, t1.is_rookie
            FROM card_templates t1
            WHERE t1.edition = 'metallic' AND t1.is_upgraded = 0
              AND NOT EXISTS (
                SELECT 1 FROM card_templates t2
                WHERE t2.player_id = t1.player_id
                  AND t2.season_created = t1.season_created
                  AND t2.edition = 'base')
        ''')).fetchall()
        if not rows:
            conn.rollback()
            return
        created = 0
        for r in rows:
            season, pid, pname, teamId, rating, position, isRookie = r
            cfg = buildEffectConfig('base', rating, position, teamId)
            conn.execute(text('''
                INSERT INTO card_templates
                  (player_id, edition, season_created, is_rookie, classification,
                   player_name, team_id, player_rating, position, effect_config,
                   rarity_weight, sell_value, is_upgraded, output_type, created_at)
                VALUES
                  (:pid, 'base', :season, :isRookie, NULL,
                   :pname, :teamId, :rating, :position, :cfg,
                   0, :sell, 0, '', :now)
            '''), {
                "pid": pid, "season": season, "isRookie": bool(isRookie),
                "pname": pname, "teamId": teamId, "rating": rating, "position": position,
                "cfg": _json.dumps(cfg), "sell": getSellValue('base', True),
                "now": _dt.utcnow(),
            })
            created += 1
        if created:
            conn.commit()
            logger.info(f"  Migration: backfilled {created} base floor templates")
        else:
            conn.rollback()
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Migration: base floor backfill skipped ({e})")
    finally:
        conn.close()


def _backfillEffectParams(primary: dict, effectName: str) -> bool:
    """Add a param an effect's CURRENT text needs onto an ALREADY-MINTED template.

    ⚠️ RE-RENDERING TEXT IS NOT ENOUGH WHEN THE PARAM KEYS CHANGED. Effect values are
    frozen at mint and templates are minted once a season, so a rework that introduces a
    new key leaves every existing card's text asking for something its `primary` does not
    have — and `_renderTemplate` prints `?` where the number belongs. Reported from
    production: Honor Roll reading "+? FPx once this player reaches 15 FP", on 10 of 10
    minted templates.

    Honor Roll is also the case where the missing param was not merely cosmetic:
    `_computeHonorRoll` falls back to `baseMult = 1.0`, which is the OLD behavior of
    paying nothing at the exact moment the bar fills. So a card without it was both
    printing `?` and quietly still doing the thing the rework existed to stop.

    Derived from what IS stored rather than rebuilt from the player — `rebuildPrimaryParams`
    works off the raw rating and would not reproduce the mint-time dampening, so it would
    hand these cards different numbers than they were minted with. `baseMult` needs no
    guesswork: it is a fixed share of the maximum, which is stored.

    Returns True if `primary` was changed. Add a case when an effect's keys change; a
    key RENAME with the same meaning belongs here too.
    """
    if effectName == 'honor_roll' and 'baseMult' not in primary:
        maxMult = primary.get('maxMult')
        if isinstance(maxMult, (int, float)) and maxMult > 1.0:
            from managers.cardEffects import HONOR_ROLL_BASE_SHARE
            primary['baseMult'] = round(1 + (maxMult - 1) * HONOR_ROLL_BASE_SHARE, 2)
            return True
    # Updraft's detail used to interpolate `gates` directly, which put a raw Python list
    # on the card face: "bonus at each of [299, 391, 483]". `gatesText` is the same
    # numbers written as prose. Derived from what IS stored, so an already-minted card
    # keeps the exact gates it was minted with.
    if effectName == 'updraft' and 'gatesText' not in primary:
        gates = primary.get('gates')
        if isinstance(gates, (list, tuple)) and gates:
            primary['gatesText'] = _joinNumbers(gates)
            return True
    return False


def _joinNumbers(values) -> str:
    """`[299, 391, 483]` -> `"299, 391 and 483"`. Card text, not a repr."""
    nums = [str(int(v)) for v in values]
    if len(nums) == 1:
        return nums[0]
    return f"{', '.join(nums[:-1])} and {nums[-1]}"


def _refreshCardEffectText():
    """Update stale tooltip/detail text on card templates whose effects were reworked.

    Re-runs the same placeholder substitution buildEffectConfig does — so
    templates that reference {primary.fieldName} pick up the current text
    AND the current value (computed from stored primary). Add an effect
    name to refreshEffects when its tooltip / detail template changes
    and existing card descriptions should re-render on next boot.

    ⚠️ Params are backfilled FIRST (`_backfillEffectParams`), because a text refresh
    against a primary that lacks the key the new text asks for renders `?` — which is how
    this shipped to production once already.
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
        # Gunslinger was re-pointed from pass yards onto well-placed throws and the
        # COMPUTE was updated with a legacy fallback, but both its texts were left
        # describing the retired mechanic — so the card scored on throws while its
        # detail promised FP per 100 passing yards, and asked for a param no
        # currently-minted card has.
        "gunslinger",
        # Legibility sweep (2026-08-16) — text only, no mechanic moved. Bonus Round
        # advertised a threshold of 4 that the fusion had raised to 6, so a user who
        # assembled exactly 4 triggers was told they had earned it and paid nothing.
        # Chain Reaction's detail said "every card in your hand" where the compute counts
        # OTHERS, and its tooltip named a stale hand size. Updraft put a raw Python list
        # on the card face and its tooltip quoted round numbers the detail contradicted
        # (300/400/500 against 299/391/483). The rest were garbled or fragmentary.
        # ⚠️ Updraft needs `gatesText`, a NEW key — `_backfillEffectParams` derives it
        # from the stored `gates`, so already-minted cards re-render with their own
        # numbers instead of a `?`.
        "bonus_round", "chain_reaction", "updraft", "lead_blocker",
        "spotlight_moment", "bonsai", "barrage", "promised_land", "rng",
        # ⚠️ spotlight_moment is doing double duty in this set. Its old detail carried a
        # PRE-FUSION clause ("a TD by either of your WRs counts") describing behavior the
        # compute never had, and the card is now WR-exclusive. Templates already minted on
        # QB/RB/TE keep scoring — the compute reads the card's own player at any position,
        # so they are correct, just no longer obtainable — and this refresh is what stops
        # them describing a two-WR rule that was never real.
        # The stat-ladder families (2026-08-16). `threshold` is a WEEKLY BAR the card's
        # own player must clear for the streak to survive, enforced at week end via
        # STREAK_CONFIGS.resetCondition — and the old wording, "a streak growing X FPx
        # per week past 32", conveyed none of that. It left the number unitless (32 what?)
        # and "per week past N" reads as though the GROWTH is per-week rather than the
        # bar. Same unitless-N problem one clause shorter on the holo two-tier cards.
        # Text only; no threshold or rate moved.
        "clockwork", "dead_eye", "dominion", "getaway", "iron_man", "landslide",
        "odyssey", "stratosphere", "tenure", "undertaker",
        "beast_of_burden", "custody", "rhythm",
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
            paramsChanged = _backfillEffectParams(primary, effectName)
            if paramsChanged:
                cfg["primary"] = primary
            newTooltip = _renderTemplate(EFFECT_TOOLTIPS.get(effectName, ""), primary)
            newDetail = _renderTemplate(EFFECT_DETAIL_TEMPLATES.get(effectName, ""), primary)
            if (not paramsChanged and cfg.get("tooltip") == newTooltip
                    and cfg.get("detail") == newDetail):
                continue
            cfg["tooltip"] = newTooltip
            cfg["detail"] = newDetail
            # A '?' here means the CURRENT text asks for a param this card was never
            # minted with, and it is about to be shown to a reader exactly like that.
            # Say so at boot rather than waiting for someone to report the card.
            if '?' in f"{newTooltip} {newDetail}" and '?' not in f"{EFFECT_TOOLTIPS.get(effectName, '')} {EFFECT_DETAIL_TEMPLATES.get(effectName, '')}":
                logger.warning(
                    f"  Migration: '{effectName}' text still has an unresolved placeholder "
                    f"after refresh — add a case to _backfillEffectParams (stored keys: "
                    f"{sorted(primary.keys())})")
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


def _backfillAllProGates():
    """Repair the frozen power-bar gate on All-Pro cards built by a path that dropped the tag.

    ⚠️ THE ROW KNEW IT WAS ALL-PRO AND THE GATE DID NOT. `_createUpgradedTemplate`
    (transplant and promote) and `blendCards` stamped `classification` onto the new
    template row but never passed it to `buildEffectConfig`, so the gate frozen inside
    `effect_config` was built as if the card were ordinary. The card WORE the All-Pro badge
    while its bar was undiscounted: measured on a prismatic WR Copycat, 12 FP instead of 8.
    It also left `gate.allPro` false, which is the flag the lineup reads to draw the AP
    accent and the "All-Pro: bar lowered 30%" note — which is how it was reported.

    ⚠️ Long-standing, but only reachable from season 2. `all_pro` is stamped from the
    PRIOR season's All-Pro team, so a league's first season mints none: production had 823
    `rookie` templates and zero `all_pro` when season 1 ended. The bug could not be hit
    until season 2's templates existed.

    ⚠️ SCOPED TO THE ALL-PRO DISCREPANCY ON PURPOSE. A blanket "recompute every gate" would
    also rewrite cards whose gate legitimately differs because it was frozen under older
    rules — production has six `all_in` rookie templates in exactly that state, left from
    before Bet Big's bar was made to match its payout line. Those are owned cards frozen at
    mint, and re-pricing them is a balance change, not a repair.

    Runs before `_refreshCardEffectText`, so effects that print the threshold in their own
    text (`all_in`, `honor_roll` — both already in its refresh set) re-render against the
    corrected gate on the same boot.
    """
    import json as _json
    from sqlalchemy import text
    from datetime import datetime as _dt
    conn = engine.connect()
    try:
        done = conn.execute(text(
            "SELECT value FROM app_settings WHERE key = 'allpro_gate_backfilled_v1'"
        )).fetchone()
        if done:
            return
        from managers.cardEffects import buildGateSpec
        rows = conn.execute(text(
            "SELECT id, edition, position, classification, effect_config FROM card_templates "
            "WHERE classification LIKE '%all_pro%' AND effect_config IS NOT NULL")).fetchall()
        fixed = 0
        for tid, edition, position, classification, cfgRaw in rows:
            try:
                cfg = _json.loads(cfgRaw) if isinstance(cfgRaw, str) else cfgRaw
            except Exception:
                continue
            stored = (cfg or {}).get('gate')
            if not stored:
                continue
            want = buildGateSpec(cfg.get('effectName'), position, classification, edition)
            if not want or not want.get('allPro'):
                continue
            if stored.get('threshold') == want.get('threshold') and stored.get('allPro'):
                continue
            cfg['gate'] = want
            conn.execute(text("UPDATE card_templates SET effect_config = :c WHERE id = :i"),
                         {"c": _json.dumps(cfg), "i": tid})
            fixed += 1
        conn.execute(text(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
            "VALUES ('allpro_gate_backfilled_v1', '1', :ts)"), {"ts": _dt.utcnow()})
        conn.commit()
        if fixed:
            logger.info(f"  Backfill: restored the All-Pro discount on {fixed} card gates")
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Backfill: All-Pro gate repair skipped: {e}")
    finally:
        conn.close()


def _backfillCurrencyTransactionSeason():
    """Stamp a season onto grants that were written without one.

    ⚠️ `currency_transactions.season` is nullable and four grant paths never passed it,
    so nothing ever complained. Measured on production: 1,100 positive grants worth
    82,534F carried NULL against 212,614F stamped to season 1 — a 28% UNDERCOUNT of the
    faucet. `facilitiesManager.computeShareUnit` is exactly "last season's grants / team
    count", so every unstamped grant quietly made every facility in the league cheaper
    than the economy warranted. Sources were `achievement` (883 rows), `starter_bonus`
    (185) and `card_sell` (32); `addFunds` now defaults the season so this cannot recur.

    A row is assigned to the LATEST season that had already started when it was written
    (`seasons.start_date <= created_at`). That is the same question the sim would have
    answered at the time, it needs no heuristic about season boundaries, and it is
    deterministic — re-running it can only ever produce the same answer.

    ⚠️ Only touches rows where season IS NULL, so it can never rewrite a stamped grant,
    and it is additionally gated on a marker so a healthy database does no work. Rows
    written BEFORE the first season started keep their NULL: there is no season they
    could honestly belong to, and inventing one would put pre-league grants into the
    faucet that prices season 1.
    """
    from sqlalchemy import text
    from datetime import datetime as _dt
    conn = engine.connect()
    try:
        done = conn.execute(text(
            "SELECT value FROM app_settings WHERE key = 'currency_season_backfilled_v1'"
        )).fetchone()
        if done:
            return
        seasons = conn.execute(text(
            "SELECT season_number, start_date FROM seasons "
            "WHERE start_date IS NOT NULL ORDER BY start_date")).fetchall()
        if not seasons:
            return  # nothing to date rows against; leave them and try again next boot
        updated = 0
        for i, (num, start) in enumerate(seasons):
            nextStart = seasons[i + 1][1] if i + 1 < len(seasons) else None
            if nextStart is None:
                res = conn.execute(text(
                    "UPDATE currency_transactions SET season = :n "
                    "WHERE season IS NULL AND created_at >= :s"), {"n": num, "s": start})
            else:
                res = conn.execute(text(
                    "UPDATE currency_transactions SET season = :n "
                    "WHERE season IS NULL AND created_at >= :s AND created_at < :e"),
                    {"n": num, "s": start, "e": nextStart})
            updated += res.rowcount or 0
        conn.execute(text(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
            "VALUES ('currency_season_backfilled_v1', '1', :ts)"), {"ts": _dt.utcnow()})
        conn.commit()
        logger.info(f"  Backfill: stamped a season onto {updated} currency transactions")
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Backfill: currency transaction season skipped: {e}")
    finally:
        conn.close()


def _backfillCoachFanTrust():
    """Spread existing coaches across the fanTrust axis.

    The ALTER lands every pre-existing coach on the neutral default (80), which
    would make the whole axis inert until the league happened to turn its
    coaches over. Draw the same independent distribution `generateAttributes`
    uses so current GMs differ from each other immediately.

    Runs ONCE, gated on an app_settings marker. Keying off "value == 80"
    instead would re-roll every coach who legitimately drew 80 on each boot,
    quietly changing a GM's personality on restart.
    See docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md Part B.
    """
    from sqlalchemy import text
    from datetime import datetime as _dt
    import numpy as np
    conn = engine.connect()
    try:
        done = conn.execute(text(
            "SELECT value FROM app_settings WHERE key = 'coach_fan_trust_backfilled_v1'"
        )).fetchone()
        if done:
            return
        rows = conn.execute(text("SELECT id FROM coaches")).fetchall()
        for (coachId,) in rows:
            value = int(np.clip(np.random.normal(80, 10), 60, 100))
            conn.execute(text("UPDATE coaches SET fan_trust = :v WHERE id = :i"),
                         {"v": value, "i": coachId})
        conn.execute(text(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
            "VALUES ('coach_fan_trust_backfilled_v1', '1', :ts)"),
            {"ts": _dt.utcnow()})
        conn.commit()
        logger.info(f"  Backfill: spread fan_trust across {len(rows)} coaches")
    except Exception as e:
        conn.rollback()
        logger.warning(f"  Backfill: coach fan_trust skipped: {e}")
    finally:
        conn.close()



def _backfillGameWinners():
    """Fill `games.winner_team_id` for games that finished before the column existed.

    ⚠️ A SCORE COMPARISON IS NOT ENOUGH, which is the whole reason the column was added.
    For frames the match is decided by FRAMES WON, points only breaking a level match, so
    those rows are read out of the persisted `format_state` blob — which already carries
    `framesWonHome`/`framesWonAway` for every completed frames game, so nothing is lost to
    history. Every other format is points-decided and takes the score.

    Idempotent: only touches final games whose winner is still NULL, and a draw is left
    NULL by design so it cannot be repeatedly "fixed".
    """
    import json as _json
    # ⚠️ `text` IS NOT MODULE-LEVEL IN THIS FILE — every neighbouring backfill imports it
    # inside its own body, and this one did not. It therefore raised NameError on its first
    # statement on every boot, and the function's own `except Exception` turned that into a
    # one-line warning, so the migration log looked healthy while zero rows were repaired.
    # Measured on production after the deploy: 575 final games, 0 with a winner set.
    from sqlalchemy import text
    session = get_session()
    try:
        rows = session.execute(text(
            "SELECT id, home_team_id, away_team_id, home_score, away_score, format_state "
            # ⚠️ LOWER(status), because the column holds 'final' and a literal 'Final'
            # matched nothing — the backfill would have run clean and repaired zero rows,
            # which is the worst kind of failure since the log line says it did its job.
            "FROM games WHERE winner_team_id IS NULL AND LOWER(status) = 'final'"
        )).fetchall()
        framesFixed = pointsFixed = 0
        for gid, homeId, awayId, homeScore, awayScore, formatState in rows:
            homeScore, awayScore = homeScore or 0, awayScore or 0
            winner = None
            frames = None
            if formatState:
                try:
                    frames = (_json.loads(formatState) or {}).get('frames')
                except Exception:
                    frames = None
            if frames and frames.get('active'):
                fh = float(frames.get('framesWonHome') or 0)
                fa = float(frames.get('framesWonAway') or 0)
                if fh != fa:
                    winner = homeId if fh > fa else awayId
                    framesFixed += 1
                elif homeScore != awayScore:      # level on frames → points decide
                    winner = homeId if homeScore > awayScore else awayId
                    framesFixed += 1
            elif homeScore != awayScore:
                winner = homeId if homeScore > awayScore else awayId
                pointsFixed += 1
            if winner is not None:
                session.execute(text("UPDATE games SET winner_team_id = :w WHERE id = :i"),
                                {"w": winner, "i": gid})
        if framesFixed or pointsFixed:
            session.commit()
            logger.info(f"  Backfill: game winners — {pointsFixed} by points, "
                        f"{framesFixed} by frames")
    except Exception as e:
        session.rollback()
        logger.warning(f"Game-winner backfill skipped: {e}")
    finally:
        session.close()


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
                   g.home_team_id, g.away_team_id, g.home_score, g.away_score,
                   g.winner_team_id
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
        for (season, gid, week, gameDate, homeId, awayId,
             homeScore, awayScore, winnerId) in rows:
            # ⚠️ The stored winner decides; the scores are only the fallback for rows that
            # predate the column. Frames games are not decided by points, so a score
            # comparison builds the wrong streak — see Game.winner_team_id.
            if winnerId is not None:
                won, lost = (homeId, awayId) if winnerId == homeId else (awayId, homeId)
            elif homeScore is None or awayScore is None or homeScore == awayScore:
                continue
            elif homeScore > awayScore:
                won, lost = homeId, awayId
            else:
                won, lost = awayId, homeId
            recordResult(season, won, True)
            recordResult(season, lost, False)
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


# Rate/derived stat keys that must be RECOMPUTED from summed components, never
# summed (adding percentages/averages is meaningless). 'longest' takes the MAX.
_CAREER_RATE_KEYS = {
    'compPerc', 'ypc', 'ypr', 'rcvPerc', 'fgPerc', 'fgAvg',
    'fgUnder20perc', 'fg20to40perc', 'fg40to50perc', 'fgOver50perc', 'xpPerc',
}


def _sumStatBlobs(blobs):
    """Sum a list of per-season stat dicts for one category. Counting keys add,
    'longest' takes the MAX, rate/derived keys are skipped (recomputed by caller)."""
    out = {}
    for b in blobs:
        if not isinstance(b, dict):
            continue
        for k, v in b.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if k in _CAREER_RATE_KEYS:
                continue
            if k == 'longest':
                out[k] = max(out.get(k, 0), v)
            else:
                out[k] = out.get(k, 0) + v
    return out


def _recomputeCareerRates(passing, rushing, receiving, kicking):
    """Recompute rate fields on the summed career blobs from their components."""
    def pct(made, att):
        return round(made / att * 100) if att else 0
    if passing:
        passing['compPerc'] = pct(passing.get('comp', 0), passing.get('att', 0))
        passing['ypc'] = round(passing.get('yards', 0) / passing['comp'], 2) if passing.get('comp') else 0
    if rushing:
        rushing['ypc'] = round(rushing.get('yards', 0) / rushing['carries'], 2) if rushing.get('carries') else 0
    if receiving:
        receiving['rcvPerc'] = pct(receiving.get('receptions', 0), receiving.get('targets', 0))
        receiving['ypr'] = round(receiving.get('yards', 0) / receiving['receptions'], 2) if receiving.get('receptions') else 0
    if kicking:
        kicking['fgPerc'] = pct(kicking.get('fgs', 0), kicking.get('fgAtt', 0))
        kicking['fgAvg'] = round(kicking.get('fgYards', 0) / kicking['fgs'], 1) if kicking.get('fgs') else 0
        kicking['xpPerc'] = pct(kicking.get('xps', 0), kicking.get('xpAtt', 0))
        for tier in ('Under20', '20to40', '40to50', 'Over50'):
            kicking[f'fg{tier}perc'] = pct(kicking.get(f'fg{tier}', 0), kicking.get(f'fg{tier}att', 0))


def _recomputeCareerStatsFromSeasons():
    """Rebuild player_career_stats (season=0) = SUM(player_season_stats) per
    player, repairing the historically under-counted career rows. One-shot via an
    app_settings flag. Both career and season stats are regular-season-only, so
    career should exactly equal the sum of the player's season rows."""
    import json as _json
    from sqlalchemy import text
    conn = engine.connect()
    try:
        done = conn.execute(text(
            "SELECT value FROM app_settings WHERE key = 'career_stats_recomputed_v1'"
        )).fetchone()
        if done:
            return
        playerIds = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT player_id FROM player_season_stats")).fetchall()]
        fixed = 0
        for pid in playerIds:
            rows = conn.execute(text(
                "SELECT games_played, fantasy_points, passing_stats, rushing_stats, "
                "receiving_stats, kicking_stats, defense_stats "
                "FROM player_season_stats WHERE player_id = :pid"), {'pid': pid}).fetchall()
            if not rows:
                continue
            gp = sum(int(r[0] or 0) for r in rows)
            fp = sum(float(r[1] or 0) for r in rows)

            def blobs(idx):
                out = []
                for r in rows:
                    raw = r[idx]
                    if not raw:
                        continue
                    try:
                        out.append(_json.loads(raw) if isinstance(raw, str) else raw)
                    except Exception:
                        pass
                return out

            passing = _sumStatBlobs(blobs(2))
            rushing = _sumStatBlobs(blobs(3))
            receiving = _sumStatBlobs(blobs(4))
            kicking = _sumStatBlobs(blobs(5))
            defense = _sumStatBlobs(blobs(6))
            _recomputeCareerRates(passing, rushing, receiving, kicking)

            params = {
                'pid': pid, 'gp': gp, 'fp': fp,
                'py': passing.get('yards', 0), 'ptd': passing.get('tds', 0), 'pint': passing.get('ints', 0),
                'ry': rushing.get('yards', 0), 'rtd': rushing.get('tds', 0),
                'recy': receiving.get('yards', 0), 'rectd': receiving.get('tds', 0),
                'pj': _json.dumps(passing), 'rj': _json.dumps(rushing), 'recj': _json.dumps(receiving),
                'kj': _json.dumps(kicking), 'dj': _json.dumps(defense),
            }
            exists = conn.execute(text(
                "SELECT 1 FROM player_career_stats WHERE player_id = :pid AND season = 0"),
                {'pid': pid}).fetchone()
            if exists:
                conn.execute(text(
                    "UPDATE player_career_stats SET games_played=:gp, fantasy_points=:fp, "
                    "passing_yards=:py, passing_tds=:ptd, passing_ints=:pint, "
                    "rushing_yards=:ry, rushing_tds=:rtd, receiving_yards=:recy, receiving_tds=:rectd, "
                    "passing_stats=:pj, rushing_stats=:rj, receiving_stats=:recj, "
                    "kicking_stats=:kj, defense_stats=:dj "
                    "WHERE player_id=:pid AND season=0"), params)
            else:
                conn.execute(text(
                    "INSERT INTO player_career_stats (player_id, season, games_played, fantasy_points, "
                    "passing_yards, passing_tds, passing_ints, rushing_yards, rushing_tds, "
                    "receiving_yards, receiving_tds, passing_stats, rushing_stats, receiving_stats, "
                    "kicking_stats, defense_stats) "
                    "VALUES (:pid, 0, :gp, :fp, :py, :ptd, :pint, :ry, :rtd, :recy, :rectd, "
                    ":pj, :rj, :recj, :kj, :dj)"), params)
            fixed += 1
        conn.execute(text(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES ('career_stats_recomputed_v1', '1', CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value='1', updated_at=CURRENT_TIMESTAMP"))
        conn.commit()
        logger.info(f"  Backfill: recomputed career stats from season rows for {fixed} players")
    except Exception as e:
        conn.rollback()
        logger.info(f"  Backfill warning (career-from-seasons): {e}")
    finally:
        conn.close()


def _backfillChampionRosterSnapshots():
    """Reconstruct seasons.champion_player_ids for seasons that ended before the
    snapshot was added. The Champion classification + pack key off this; without it
    they fall back to the champion team's CURRENT roster, which has churned. Source
    is players.league_championships ({"Season": N, ...} stamped on each champion AT
    the Floos Bowl, before any offseason churn) — the authoritative title roster.

    Idempotent: only fills seasons that have a champion but no snapshot yet. Touches
    NO card classifications or values — just stores the roster so generation/packs can
    read it. Runs before the next season's card generation."""
    import json as _json
    from sqlalchemy import text
    conn = engine.connect()
    try:
        rows = conn.execute(text(
            "SELECT season_number FROM seasons WHERE champion_team_id IS NOT NULL "
            "AND (champion_player_ids IS NULL OR champion_player_ids = '')"
        )).fetchall()
        targetSeasons = {r[0] for r in rows}
        if not targetSeasons:
            return
        champBySeason = {}
        for pid, lc in conn.execute(text(
                "SELECT id, league_championships FROM players "
                "WHERE league_championships IS NOT NULL")).fetchall():
            try:
                entries = _json.loads(lc) if isinstance(lc, str) else lc
                for e in (entries or []):
                    s = e.get('Season')
                    if s in targetSeasons:
                        champBySeason.setdefault(s, []).append(pid)
            except Exception:
                pass
        filled = 0
        for s, ids in champBySeason.items():
            conn.execute(text(
                "UPDATE seasons SET champion_player_ids = :ids WHERE season_number = :s"),
                {'ids': _json.dumps(sorted(ids)), 's': s})
            filled += 1
        conn.commit()
        if filled:
            logger.info(f"  Backfill: reconstructed champion_player_ids for {filled} "
                        f"season(s) from league_championships")
    except Exception as e:
        conn.rollback()
        logger.info(f"  Backfill warning (champion snapshots): {e}")
    finally:
        conn.close()


def _seedTeamFacilitiesFromTiers():
    """One-time tier→facilities migration (Markets→Facilities, feature/facilities).

    Seeds team_facilities from each team's CURRENT market tier so nobody
    launches nerfed: MEGA→Lv4, LARGE→Lv3, MID→Lv2, SMALL→Lv1 on the four
    legacy-perk facilities, Stadium at Lv0. The per-level effect curves
    (constants.FACILITY_CATALOG) are calibrated so these levels reproduce the
    current FUNDING_* perks. Idempotent: gated by an app_settings flag AND a
    per-row INSERT OR IGNORE on the (team_id, facility_key) unique constraint.
    """
    from sqlalchemy import text
    from constants import (FACILITY_CATALOG, MIGRATION_TIER_START_LEVEL,
                           MIGRATION_STADIUM_START_LEVEL)
    conn = engine.connect()
    try:
        done = conn.execute(text(
            "SELECT value FROM app_settings WHERE key = 'facilities_seeded_v1'"
        )).fetchone()
        if done:
            return
        teamIds = [r[0] for r in conn.execute(text("SELECT id FROM teams")).fetchall()]
        if not teamIds:
            return  # fresh DB with no teams yet — season start will seed funding first
        # Current tier = the latest season's team_funding row per team.
        tierByTeam = {}
        for tid, tier in conn.execute(text(
            "SELECT tf.team_id, tf.funding_tier FROM team_funding tf "
            "JOIN (SELECT team_id, MAX(season) AS s FROM team_funding GROUP BY team_id) m "
            "ON tf.team_id = m.team_id AND tf.season = m.s")).fetchall():
            tierByTeam[tid] = tier or 'MID_MARKET'
        seeded = 0
        for tid in teamIds:
            tier = tierByTeam.get(tid, 'MID_MARKET')
            for key in FACILITY_CATALOG:
                level = (MIGRATION_STADIUM_START_LEVEL if key == 'stadium'
                         else MIGRATION_TIER_START_LEVEL.get(tier, 2))
                conn.execute(text(
                    "INSERT OR IGNORE INTO team_facilities (team_id, facility_key, level) "
                    "VALUES (:tid, :key, :lvl)"),
                    {'tid': tid, 'key': key, 'lvl': level})
            seeded += 1
        conn.execute(text(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES ('facilities_seeded_v1', '1', CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value='1', updated_at=CURRENT_TIMESTAMP"))
        conn.commit()
        logger.info(f"  Backfill: seeded facilities from market tiers for {seeded} teams")
    except Exception as e:
        conn.rollback()
        logger.info(f"  Backfill warning (facilities-from-tiers): {e}")
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
    # ⚠️ league_archive is the ONLY history that survives a wipe, and it survives because
    # it holds resolved NAMES with no foreign keys. The other history tables must NOT be
    # added here: `records` and `championships` store player_id/team_id with no names, and
    # ids restart from 1, so preserving them would reattach a 15-season record to whichever
    # rookie inherited the id rather than saving anything. See
    # docs/FRESH_START_HISTORY_PLAN.md.
    # curated_names is the durable home for admin/Discord names — config.json re-seeds
    # itself on boot, but names added after the seed have no other permanent store.
    preserveTables = {"users", "beta_allowlist", "app_settings", "unused_names",
                      "league_archive", "curated_names"}

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
    # ⚠️ `text` IS NOT IN SCOPE HERE either — it is imported locally inside other
    # functions in this module, never at module level. This raised NameError on every
    # fresh start, and the inner bare `except: pass` swallowed it WITHOUT EVEN A
    # WARNING, so the reset the comment above describes has never once run: a user's
    # `starter_pack_claimed_season=1` survived the wipe, matched the new season 1, and
    # hid the starter pack from them permanently.
    try:
        from sqlalchemy import text as _text
        with engine.connect() as conn:
            for col in ('starter_pack_claimed_season', 'favorite_team_locked_season'):
                try:
                    conn.execute(_text(f"UPDATE users SET {col} = NULL"))
                except Exception as colErr:
                    # A genuinely missing column is fine (older DB); anything else is not.
                    logger.warning(f"  Could not reset {col}: {colErr}")
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to reset per-season user flags on fresh start: {e}")

    # ⚠️ Same hazard one table over: `app_settings` is preserved WHOLESALE, so a key
    # describing data that was just dropped survives and goes on being believed. Keys
    # scoped to a SEASON must be cleared here, exactly like the user flags above.
    #
    # `lineup_snapshot_complete_from` holds "season:week" of the first week whose lineup
    # snapshot was complete. After a wipe it points at a week that no longer exists, and
    # because the counter restarts at 1 a stale "1:2" leaves the NEW week 1 sitting
    # before the boundary — permanently exempt from the no-games-no-points gate. That
    # survived every fresh start, which is why the leak kept reproducing on clean runs.
    #
    # Deliberately selective: `generational_names_collapsed` and the name-pool markers
    # describe the PRESERVED pool and must NOT be cleared.
    try:
        # ⚠️ `text` IS NOT IN SCOPE HERE WITHOUT THIS IMPORT. It is imported locally inside
        # other functions in this module, never at module level, so this block raised
        # NameError on every fresh start and the bare `except` below logged it as a
        # warning and moved on. The clear NEVER RAN — which is precisely why the leak
        # described above "kept reproducing on clean runs". The fix was written and has
        # never once executed.
        from sqlalchemy import text as _text
        from managers.fantasyTracker import COMPLETE_SNAPSHOT_SETTING
        with engine.connect() as conn:
            conn.execute(_text("DELETE FROM app_settings WHERE key = :k"),
                         {"k": COMPLETE_SNAPSHOT_SETTING})
            conn.commit()
        logger.info(f"  Cleared season-scoped app setting: {COMPLETE_SNAPSHOT_SETTING}")
    except Exception as e:
        logger.warning(f"Failed to clear season-scoped app settings on fresh start: {e}")

    logger.info(f"Database cleared (preserved {', '.join(preserveTables)}) at {DB_PATH}")

    # Run migrations for preserved tables (e.g. new columns on users)
    _runPendingMigrations()
    _seedPackTypes()
    _seedBetaAllowlist()
    _seedAchievements()
    # ⚠️ Every player and coach was just dropped, so any generational variant left in
    # the preserved pool has no parent anywhere and never will. Collapse before seeding.
    _normalizeNamePool(resetLadders=True)
    _seedUnusedNames()
    _seedCuratedNames()


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
            # ⚠️ RETIRED: the fantasy/cards fusion made "set your first fantasy roster"
            # and "equip your first card" the SAME act. Both hooks fired back to back
            # off one `if req.cards` in the equip handler, so nobody could ever hold one
            # without the other and a single click popped two toasts. Deck Builder is
            # the survivor because it describes what actually happens now; there is no
            # separate fantasy roster to set. Retired rather than deleted so the people
            # who earned it keep it (see achievements.retired).
            {"key": "field_general", "name": "Field General", "category": "onboarding", "scope": "once", "sort_order": 40, "target": 1,
             "description": "Set your first fantasy roster.", "retired": True,
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
             "reward_config": {"floobits": 250, "packs": ["exquisite"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "curator", "name": "Curator", "category": "guidance", "scope": "per_season", "sort_order": 130, "target": 15,
             "description": "Collect 15 unique cards this season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            # Collection — permanent goals on the Vault (once-scope, never reset).
            {"key": "hometown_hero", "name": "Hometown Hero", "category": "collection", "scope": "once", "sort_order": 310, "target": 5,
             "description": "Vault 5 cards of players on your favorite team.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "full_spectrum", "name": "Full Spectrum", "category": "collection", "scope": "once", "sort_order": 320, "target": 1,
             "description": "Vault the base, holographic, prismatic and diamond print of a single player.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "all_pro_set", "name": "All-Pro Set", "category": "collection", "scope": "once", "sort_order": 330, "target": 1,
             "description": "Vault every All-Pro card from a single season.",
             "reward_config": {"floobits": 400, "packs": ["exquisite"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "ice_cold_i", "name": "Ice Cold I", "category": "collection", "scope": "once", "sort_order": 340, "target": 3,
             "description": "Vault 3 Diamond cards.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "ice_cold_ii", "name": "Ice Cold II", "category": "collection", "scope": "once", "sort_order": 341, "target": 8,
             "description": "Vault 8 Diamond cards.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "ice_cold_iii", "name": "Ice Cold III", "category": "collection", "scope": "once", "sort_order": 342, "target": 20,
             "description": "Vault 20 Diamond cards.",
             "reward_config": {"floobits": 250, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "archivist_i", "name": "Archivist I", "category": "collection", "scope": "once", "sort_order": 350, "target": 10,
             "description": "Vault cards of 10 different players.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "archivist_ii", "name": "Archivist II", "category": "collection", "scope": "once", "sort_order": 351, "target": 50,
             "description": "Vault cards of 50 different players.",
             "reward_config": {"floobits": 200, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "archivist_iii", "name": "Archivist III", "category": "collection", "scope": "once", "sort_order": 352, "target": 150,
             "description": "Vault cards of 150 different players.",
             "reward_config": {"floobits": 600, "packs": ["exquisite"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            # Card upgrades — seasonal (tiers reset each season unless vaulted).
            {"key": "artificer_i", "name": "Artificer I", "category": "guidance", "scope": "per_season", "sort_order": 260, "target": 1,
             "description": "Level up a card this season.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "artificer_ii", "name": "Artificer II", "category": "guidance", "scope": "per_season", "sort_order": 261, "target": 5,
             "description": "Level up cards 5 times this season.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "artificer_iii", "name": "Artificer III", "category": "guidance", "scope": "per_season", "sort_order": 262, "target": 12,
             "description": "Level up cards 12 times this season.",
             "reward_config": {"floobits": 100, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "ascendant", "name": "Ascendant", "category": "guidance", "scope": "per_season", "sort_order": 263, "target": 1,
             "description": "Bring a card to its max tier (IV) this season.",
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
             "reward_config": {"floobits": 150, "packs": [], "powerups": ["income_boost"], "components": {"synth": 1}, "deferred": False}},
            {"key": "veteran", "name": "Veteran", "category": "guidance", "scope": "per_season", "sort_order": 150, "target": 20,
             "description": "Set a fantasy roster for 20+ weeks of the regular season.",
             # extra_swap retired in the fusion (swaps are gone); rolled its 50F shop value
             # into floobits (300 -> 350).
             "reward_config": {"floobits": 350, "packs": [], "powerups": [], "deferred": False}},
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
             "reward_config": {"floobits": 75, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
            {"key": "compound_i", "name": "Compound I", "category": "guidance", "scope": "per_season", "sort_order": 260, "target": 220,
             "description": "Reach a 2.2x total FP multiplier in a single week.",
             "reward_config": {"floobits": 25, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_ii", "name": "Compound II", "category": "guidance", "scope": "per_season", "sort_order": 261, "target": 400,
             "description": "Reach a 4.0x total FP multiplier in a single week.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_iii", "name": "Compound III", "category": "guidance", "scope": "per_season", "sort_order": 262, "target": 600,
             "description": "Reach a 6.0x total FP multiplier in a single week.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "compound_iv", "name": "Compound IV", "category": "guidance", "scope": "per_season", "sort_order": 263, "target": 850,
             "description": "Reach a 8.5x total FP multiplier in a single week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
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
             "reward_config": {"floobits": 100, "packs": ["humble"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "purist", "name": "Purist", "category": "secret", "scope": "once", "sort_order": 540, "target": 1,
             "description": "Play a full week with zero cards equipped.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}, "retired": True},
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
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "consecration", "name": "Consecration", "category": "secret", "scope": "once", "sort_order": 610, "target": 1,
             "description": "Your favorite team wins the Floosbowl.",
             "reward_config": {"floobits": 0, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dabbler", "name": "Dabbler", "category": "secret", "scope": "once", "sort_order": 620, "target": 1,
             "description": "Purchase every type of power-up at least once.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "arsenal", "name": "Arsenal", "category": "secret", "scope": "once", "sort_order": 630, "target": 1,
             "description": "Hold 3 or more roster swaps at the same time.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}, "retired": True},
            {"key": "finicky", "name": "Finicky", "category": "secret", "scope": "once", "sort_order": 640, "target": 1,
             "description": "Re-roll the card shop 5 times in a row without buying anything in between.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "sweep", "name": "Sweep", "category": "secret", "scope": "once", "sort_order": 650, "target": 1,
             "description": "Buy every card featured in your shop in a single day.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "mutineer", "name": "Scorched Earth", "category": "secret", "scope": "once", "sort_order": 660, "target": 1,
             "description": "Vote to fire your coach and release every player on the roster in a single offseason.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}, "retired": True},
            {"key": "tribune", "name": "Tribune", "category": "secret", "scope": "once", "sort_order": 665, "target": 1,
             "description": "Cast 6 GM votes in a single season.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}, "retired": True},
            {"key": "monk", "name": "Monk", "category": "secret", "scope": "once", "sort_order": 670, "target": 1,
             "description": "Go an entire season without opening a card pack.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "stalwart", "name": "Stalwart", "category": "secret", "scope": "once", "sort_order": 680, "target": 1,
             "description": "Play an entire season with a full roster and zero roster swaps.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}, "retired": True},
            {"key": "underwriter", "name": "Underwriter", "category": "secret", "scope": "once", "sort_order": 685, "target": 5,
             "description": "Single-handedly fund five facility bars, upkeep or project, from empty to full.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            # Card-upgrade secrets
            {"key": "overclocked", "name": "Overclocked", "category": "secret", "scope": "once", "sort_order": 690, "target": 1,
             "description": "Hold three max-tier (IV) cards in a single season.",
             "reward_config": {"floobits": 150, "packs": [], "powerups": [], "deferred": False}},
            {"key": "dynasty", "name": "Dynasty", "category": "secret", "scope": "once", "sort_order": 695, "target": 1,
             "description": "Vault a fully upgraded (tier IV) card.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "crown_jewel", "name": "Crown Jewel", "category": "secret", "scope": "once", "sort_order": 700, "target": 1,
             "description": "Take a Diamond card to its max tier (IV).",
             "reward_config": {"floobits": 200, "packs": [], "powerups": [], "deferred": False}},
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
             "reward_config": {"floobits": 250, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "flawless", "name": "Flawless", "category": "secret", "scope": "once", "sort_order": 730, "target": 1,
             "description": "Predict every playoff advancer correctly in a single bracket.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
            {"key": "pool_shark", "name": "Pool Shark", "category": "secret", "scope": "once", "sort_order": 740, "target": 1,
             "description": "Finish #1 on the season playoff bracket leaderboard.",
             "reward_config": {"floobits": 0, "packs": [], "powerups": [], "deferred": False}},
            {"key": "jinx", "name": "Jinx", "category": "secret", "scope": "once", "sort_order": 745, "target": 1,
             "description": "Whiff on every single pick in a full pick-em week.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "greenhorn", "name": "Greenhorn", "category": "secret", "scope": "once", "sort_order": 750, "target": 1,
             "description": "Field a full fantasy roster made up entirely of rookies.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "superfan", "name": "Superfan", "category": "secret", "scope": "once", "sort_order": 755, "target": 1,
             "description": "Follow 10 or more players at once.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "alchemist", "name": "Alchemist", "category": "secret", "scope": "once", "sort_order": 760, "target": 1,
             "description": "Forge a new card at the Combine.",
             "reward_config": {"floobits": 50, "packs": [], "powerups": [], "deferred": False}},
            {"key": "liquidator", "name": "Liquidator", "category": "secret", "scope": "once", "sort_order": 765, "target": 1,
             "description": "Sell a Diamond card.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "lightning_strike", "name": "Lightning Strike", "category": "secret", "scope": "once", "sort_order": 770, "target": 1,
             "description": "Pull a Diamond card out of a Humble pack.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "diehard", "name": "Diehard", "category": "secret", "scope": "once", "sort_order": 775, "target": 1,
             "description": "Rally your favorite team while they trail by 20 or more.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "lifer", "name": "Lifer", "category": "secret", "scope": "once", "sort_order": 780, "target": 1,
             "description": "Back the same favorite team for five straight seasons.",
             "reward_config": {"floobits": 100, "packs": [], "powerups": [], "deferred": False}},
            {"key": "sparkler", "name": "Sparkler", "category": "guidance", "scope": "per_season", "sort_order": 170, "target": 1,
             "description": "Open your first Diamond card of the season.",
             "reward_config": {"floobits": 75, "packs": [], "powerups": [], "deferred": False}},
            {"key": "perfect_week", "name": "Perfect Week", "category": "guidance", "scope": "per_season", "sort_order": 180, "target": 1,
             "description": "Get every prognostication correct in a single week.",
             "reward_config": {"floobits": 150, "packs": ["grand"], "powerups": [], "components": {"synth": 1}, "deferred": False}},
        ]
        added = 0
        updated = 0
        # Template-level fields that are safe to refresh without resetting user progress.
        # reward_config changes affect future grants only; already-completed achievements
        # keep whatever reward the user received at the time of completion.
        # ⚠️ `retired` is refreshed like everything else, and `.get` supplies the default
        # so a template without the key reads as live. That is what lets an achievement be
        # UN-retired by deleting one flag here, and what makes retiring one land on an
        # existing prod DB on the next boot rather than only on a fresh seed.
        refreshFields = ("name", "description", "category", "scope", "target", "sort_order",
                         "reward_config", "retired")
        defaultsFor = {"retired": False}
        for d in defaults:
            existing = session.query(Achievement).filter(Achievement.key == d["key"]).first()
            if existing:
                changed = False
                for f in refreshFields:
                    value = d.get(f, defaultsFor.get(f))
                    if getattr(existing, f) != value:
                        setattr(existing, f, value)
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


def _seedCuratedNames():
    """Merge admin/Discord-approved names back into the usable pool.

    The exact counterpart of `_seedUnusedNames`, which does this for config.json. Config
    gets that for free because it is a file that ships with the code; names added after the
    seed have no such home — see CuratedName for why config.json cannot be written to in
    prod. Without this, a fan-submitted name is removed from `unused_names` the moment it
    is drawn onto a player, and then dies with that player row at the next reset.

    Same filter as the config path: skip anything already pooled or held by a live player
    or coach, so a name in active use is not re-pooled and drawn twice.
    """
    from database.models import UnusedName, CuratedName, Coach, Player
    session = SessionLocal()
    try:
        curated = [row.name for row in session.query(CuratedName.name).all()]
        if not curated:
            return
        existing = {row.name for row in session.query(UnusedName.name).all()}
        inUse = {c.name for c in session.query(Coach.name).all() if c.name}
        inUse |= {p.name for p in session.query(Player.name).all() if p.name}
        added = 0
        for name in curated:
            if name in existing or name in inUse:
                continue
            session.add(UnusedName(name=name))
            existing.add(name)
            added += 1
        if added:
            session.commit()
            logger.info(f"  Restored {added} curated name(s) to the pool")
    except Exception as e:
        session.rollback()
        logger.warning(f"  Could not merge curated names: {e}")
    finally:
        session.close()


# The generational ladder from seasonManager._recyclePlayerName:
#     Base -> Jr. -> III -> IV -> V -> VI -> VII -> VIII -> IX -> X -> XI
# Longest-first so "VIII" is not eaten as "V" followed by a stranded "III".
_NAME_SUFFIXES = ('Jr.', 'VIII', 'XII', 'XI', 'IX', 'VII', 'VI', 'IV', 'III', 'II', 'X', 'V')
# app_setting key for the one-shot live-name collapse below.
_COLLAPSE_MARKER = 'generational_names_collapsed'
_NAME_SUFFIX_RE = _re.compile(
    r'\s+(' + '|'.join(_re.escape(s) for s in _NAME_SUFFIXES) + r')$'
)


def baseName(name: str) -> str:
    """Reduce a player/coach name to the base form of its lineage.

    "Freed Marinara Jr." and "Freed Marinara III" are the SAME pooled name at
    different points in its life, not three names. Repeated until it stops
    shrinking because the ladder can stack in stored data ("Foo Jr. III").
    """
    previous = None
    while previous != name:
        previous = name
        name = _NAME_SUFFIX_RE.sub('', name).strip()
    return name


def _collapseLiveGenerationalNames():
    """ONE-SHOT: drop the generational suffix from players and coaches wearing one.

    ⚠️ THIS RUNS EXACTLY ONCE, EVER, and it has to. A player named "Bob Jr." is
    normally CORRECT — the ladder exists so a newcomer can debut as the next
    generation of a name the league remembers. Collapsing on every boot would
    delete that feature outright. The marker is the whole safety mechanism.

    It exists because the fork documented on `_seedUnusedNames` seeded orphaned
    variants into the pool, and player generation then drew them: production came
    out of its season-1 wipe with ten players and a coach carrying a "Jr." whose
    father had never played a down in that league.

    ⚠️ WHEN THE BASE IS ALREADY WORN by another live player or coach, the junior
    gets a FRESH NAME FROM THE POOL instead. That collision is not a rare edge — it
    is the fork's own signature, both forms of a lineage generated into the same
    league, and production has three. Collapsing there would put two identical
    names on the field, so the junior is reassigned (owner, 2026-08-10: the league
    is new, so no history is attached to the name being replaced). The replacement
    must be BASE-FORM and an unused lineage: this runs before `_normalizeNamePool`,
    so the pool can still be holding the orphaned variants that caused all this.
    If the pool cannot supply one, the name is left alone rather than blanked.

    ⚠️ MUST RUN BEFORE PLAYERS LOAD. `savePlayerData` writes `db_player.name` from
    the in-memory Player on every week and season boundary, so a rename applied to
    a running league is silently overwritten by the next save. init_db() is called
    at run_api.py:358, before floosballApplication builds its managers, which is
    what makes the new name the one the sim picks up.
    """
    from database.models import UnusedName, Coach, Player, AppSetting
    session = SessionLocal()
    try:
        marker = session.query(AppSetting).filter(AppSetting.key == _COLLAPSE_MARKER).first()
        if marker is not None:
            return
        players = session.query(Player).all()
        coaches = session.query(Coach).all()
        live = {p.name for p in players if p.name} | {c.name for c in coaches if c.name}

        def drawReplacement():
            """First pooled name that is base-form and whose lineage is free."""
            for candidate in session.query(UnusedName).order_by(UnusedName.id).all():
                pooled = candidate.name or ''
                if not pooled or _NAME_SUFFIX_RE.search(pooled):
                    continue
                if pooled in live:
                    continue
                session.delete(candidate)
                return pooled
            return None

        renamed, reassigned, skipped = [], [], []
        for row in list(players) + list(coaches):
            name = row.name or ''
            if not _NAME_SUFFIX_RE.search(name):
                continue
            lineage = baseName(name)
            if not lineage:
                continue
            if lineage in live:
                replacement = drawReplacement()
                if replacement is None:
                    skipped.append(name)
                    continue
                reassigned.append((name, replacement))
                live.discard(name)
                live.add(replacement)
                row.name = replacement
                continue
            renamed.append((name, lineage))
            live.discard(name)
            live.add(lineage)
            row.name = lineage
            # The pool copy is now a duplicate of a name on the field.
            # _normalizeNamePool runs next and would catch it anyway; doing it here
            # keeps the two consistent inside one transaction.
            for dupe in session.query(UnusedName).filter(UnusedName.name == lineage).all():
                session.delete(dupe)

        session.add(AppSetting(key=_COLLAPSE_MARKER,
                               value=str(len(renamed) + len(reassigned))))
        session.commit()
        if renamed:
            logger.info(f"Collapsed {len(renamed)} generational name(s) on live players/coaches:")
            for was, now in sorted(renamed):
                logger.info(f"    {was} -> {now}")
        if reassigned:
            logger.info(
                f"Reassigned {len(reassigned)} name(s) whose base was already on the field:")
            for was, now in sorted(reassigned):
                logger.info(f"    {was} -> {now}")
        if skipped:
            logger.warning(
                f"Left {len(skipped)} generational name(s) alone — the base was taken and "
                f"the pool had no replacement: {', '.join(sorted(skipped))}"
            )
    except Exception as exc:
        session.rollback()
        logger.warning(f"Failed to collapse live generational names: {exc}")
    finally:
        session.close()


def _normalizeNamePool(resetLadders: bool = False):
    """Drop pooled names that duplicate a lineage already in circulation.

    ⚠️ THE INVARIANT IS ONE FORM OF A LINEAGE AT A TIME. A name goes up a rung
    precisely BECAUSE its previous holder is gone (`_recyclePlayerName` runs at
    retirement), so a base and its Junior are never both live. When they are, one
    of them is an artifact:

      * `clear_db()` preserves `unused_names` but drops every player and coach, so
        a variant left in the pool has no parent anywhere and never will — a
        Junior with no father.
      * `_seedUnusedNames` compared EXACT strings, so a pool holding "Bob Jr."
        looked to config's "Bob" like a name it had never seen, and re-seeded the
        base on EVERY boot. That one is the bigger source: it forks a lineage on a
        perfectly healthy long-running database, not just after a wipe.

    Measured on the season-1 production database: 712 pooled names of which 39
    were variants, 32 with the base also pooled and the other 7 with the base worn
    by a player or coach.

    Deletes the VARIANT and keeps the base — an orphaned Junior is the row that
    reads wrong. A variant whose base is genuinely absent is a legitimate recycled
    name and is left alone, which is what makes this safe to run on every boot
    rather than needing a one-shot marker.

    `resetLadders` collapses those survivors back to the base form too, and is for
    `clear_db()` ALONE. It is safe there and only there: the wipe has just dropped
    every player and coach, so no lineage has a living member and no variant can
    still be pointing at a real parent. Without it a wiped league keeps circulating
    Juniors whose father never existed in it.
    """
    from database.models import UnusedName, Coach, Player
    session = SessionLocal()
    try:
        rows = session.query(UnusedName).order_by(UnusedName.id).all()
        if not rows:
            return
        inUse = {baseName(n) for (n,) in session.query(Player.name).all() if n}
        inUse |= {baseName(n) for (n,) in session.query(Coach.name).all() if n}

        seen = set()
        # Base-form rows first, so a variant is always judged against every base
        # in the pool rather than against whatever happened to sort ahead of it.
        ordered = sorted(rows, key=lambda r: _NAME_SUFFIX_RE.search(r.name or '') is not None)
        removed = []
        collapsed = []
        for row in ordered:
            lineage = baseName(row.name or '')
            if not lineage:
                continue
            if lineage in seen or lineage in inUse:
                # A second form of a lineage that is already accounted for. The
                # tie between two variants of an absent base is arbitrary (id
                # order) — that case only arises from the artifacts above.
                removed.append(row.name)
                session.delete(row)
                continue
            seen.add(lineage)
            if resetLadders and row.name != lineage:
                collapsed.append(row.name)
                row.name = lineage
        if removed or collapsed:
            session.commit()
            if removed:
                logger.info(
                    f"Name pool: dropped {len(removed)} duplicate lineage name(s) "
                    f"(e.g. {', '.join(sorted(removed)[:3])})"
                )
            if collapsed:
                logger.info(
                    f"Name pool: collapsed {len(collapsed)} orphaned generational "
                    f"name(s) to base (e.g. {', '.join(sorted(collapsed)[:3])})"
                )
    except Exception as exc:
        session.rollback()
        logger.warning(f"Failed to normalize unused_names: {exc}")
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

    ⚠️ THE COMPARISON IS BY LINEAGE, NOT BY EXACT STRING. It used to be exact,
    and that quietly forked a lineage every time one advanced a rung: once
    `_recyclePlayerName` had turned a retiree into "Bob Jr.", config's "Bob"
    matched nothing in the pool and was re-seeded on the NEXT BOOT, so the
    father and the son both sat in the pool waiting to debut. Repeat per
    restart and per generation. A name goes up a rung precisely because its
    holder is gone, so at most one form of a lineage should be in circulation
    at a time. `_normalizeNamePool` clears up the duplicates already made.

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
        existing = {baseName(row.name) for row in session.query(UnusedName.name).all()}
        activeCoachNames = {baseName(c.name) for c in session.query(Coach.name).all() if c.name}
        activePlayerNames = {baseName(p.name) for p in session.query(Player.name).all() if p.name}
        inUse = activeCoachNames | activePlayerNames
        added = 0
        skipped = 0
        for name in names:
            lineage = baseName(name)
            if lineage in existing:
                continue
            if lineage in inUse:
                skipped += 1
                continue
            session.add(UnusedName(name=name))
            existing.add(lineage)
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
