"""Delete an erroneously started season and roll back seasonsPlayed.

Usage:
    fly ssh console -C "python3 delete_season.py 4"

Or locally:
    python delete_season.py 4
"""
import sys
from sqlalchemy import text

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 4

from database.connection import init_db, get_session
init_db()
session = get_session()

# ── Safety checks ──────────────────────────────────────────────────────
print(f"\n=== Safety check for season {SEASON} ===\n")

# Check user_cards referencing season 4 card_templates
s4TemplateIds = session.execute(
    text("SELECT id FROM card_templates WHERE season_created = :s"), {"s": SEASON}
).fetchall()
templateCount = len(s4TemplateIds)
print(f"Card templates created for season {SEASON}: {templateCount}")

if templateCount > 0:
    templateIdList = [r[0] for r in s4TemplateIds]
    placeholders = ",".join(str(tid) for tid in templateIdList)

    # user_cards referencing these templates
    affectedCards = session.execute(
        text(f"SELECT uc.id, uc.user_id, u.username, u.email, ct.player_name "
             f"FROM user_cards uc "
             f"JOIN card_templates ct ON uc.card_template_id = ct.id "
             f"JOIN users u ON uc.user_id = u.id "
             f"WHERE uc.card_template_id IN ({placeholders})")
    ).fetchall()

    if affectedCards:
        print(f"\nWARNING: {len(affectedCards)} user cards reference season {SEASON} templates:")
        for card in affectedCards:
            print(f"  card_id={card[0]}, user={card[2] or card[3]}, player={card[4]}")

        # equipped_cards referencing these user_cards
        cardIdList = ",".join(str(c[0]) for c in affectedCards)
        equippedCount = session.execute(
            text(f"SELECT COUNT(*) FROM equipped_cards WHERE user_card_id IN ({cardIdList})")
        ).scalar()
        if equippedCount:
            print(f"  ({equippedCount} of these are currently equipped)")

        print(f"\nThese user cards will be DELETED. Users will lose these cards.")
        confirm = input("Continue? (type 'yes' to proceed): ")
        if confirm.strip().lower() != 'yes':
            print("Aborted.")
            session.close()
            sys.exit(1)

        # Delete equipped_cards referencing affected user_cards first
        session.execute(
            text(f"DELETE FROM equipped_cards WHERE user_card_id IN ({cardIdList})")
        )
        # Delete the user_cards themselves
        result = session.execute(
            text(f"DELETE FROM user_cards WHERE card_template_id IN ({placeholders})")
        )
        print(f"  user_cards: deleted {result.rowcount} rows")
    else:
        print(f"No user cards reference season {SEASON} templates. Safe to proceed.")

# Count rows in each table for the bad season
print(f"\n=== Rows to delete for season {SEASON} ===\n")

SEASON_TABLES = [
    "games",
    "game_player_stats",
    "player_season_stats",
    "player_career_stats",
    "team_season_stats",
    "team_funding",
    "championships",
    "records",
    "fantasy_rosters",
    "fantasy_roster_players",
    "fantasy_roster_swaps",
    "equipped_cards",
    "weekly_card_bonuses",
    "card_upgrade_logs",
    "weekly_modifiers",
    "weekly_player_fp",
    "featured_shop_cards",
    "shop_purchases",
    "user_modifier_overrides",
    "gm_votes",
    "gm_vote_results",
    "gm_fa_ballots",
    "pick_em_picks",
]

totalRows = 0
for table in SEASON_TABLES:
    try:
        count = session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE season = :s"), {"s": SEASON}
        ).scalar()
        if count > 0:
            print(f"  {table}: {count} rows")
            totalRows += count
    except Exception:
        pass

print(f"  card_templates (season_created={SEASON}): {templateCount} rows")
totalRows += templateCount

seasonRow = session.execute(
    text("SELECT COUNT(*) FROM seasons WHERE season_number = :s"), {"s": SEASON}
).scalar()
if seasonRow:
    print(f"  seasons: {seasonRow} rows")
    totalRows += seasonRow

print(f"\nTotal rows to delete: {totalRows}")

# ── Confirm and execute ───────────────────────────────────────────────
confirm = input(f"\nDelete all season {SEASON} data? (type 'yes' to proceed): ")
if confirm.strip().lower() != 'yes':
    print("Aborted.")
    session.close()
    sys.exit(1)

print(f"\nDeleting all data for season {SEASON}...")

for table in SEASON_TABLES:
    try:
        result = session.execute(
            text(f"DELETE FROM {table} WHERE season = :s"), {"s": SEASON}
        )
        if result.rowcount > 0:
            print(f"  {table}: deleted {result.rowcount} rows")
    except Exception as e:
        print(f"  {table}: skipped ({e})")
        session.rollback()

# Delete card_templates for this season
try:
    result = session.execute(
        text("DELETE FROM card_templates WHERE season_created = :s"), {"s": SEASON}
    )
    if result.rowcount > 0:
        print(f"  card_templates: deleted {result.rowcount} rows")
except Exception as e:
    print(f"  card_templates: skipped ({e})")
    session.rollback()

# Delete the season record itself
try:
    result = session.execute(
        text("DELETE FROM seasons WHERE season_number = :s"), {"s": SEASON}
    )
    print(f"  seasons: deleted {result.rowcount} rows")
except Exception as e:
    print(f"  seasons: skipped ({e})")
    session.rollback()

# Roll back simulation_state so next boot starts the season fresh
try:
    session.execute(
        text(
            "UPDATE simulation_state SET current_season = :s, current_week = 0, "
            "in_playoffs = 0, playoff_round = NULL WHERE id = 1"
        ),
        {"s": SEASON}
    )
    print(f"  simulation_state: reset to season {SEASON}, week 0")
except Exception as e:
    print(f"  simulation_state: skipped ({e})")
    session.rollback()

session.commit()
session.close()
print(f"\nSeason {SEASON} deleted. Next restart will start season {SEASON} fresh.")
