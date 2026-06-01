---
description: Generate a prod SQLite query script for fly ssh console (no sqlite3 binary on prod)
argument-hint: [what to query, e.g. "user UnlicensedSteamroller36's roster + equipped cards"]
---

The user wants to investigate prod data: $ARGUMENTS

Prod is a Fly.io app with SQLite at `/data/floosball.db`. There is **no sqlite3 binary** on the prod machine — queries must be wrapped in a `python3` heredoc.

Write a self-contained Python script the user can paste into `fly ssh console` (they'll already be logged in). Requirements:

- Open with `import sqlite3, json` and `conn = sqlite3.connect('/data/floosball.db')` with `conn.row_factory = sqlite3.Row`
- Wrap in `python3 << 'PYEOF' ... PYEOF`
- Use parameterized queries (`?` placeholders) — never string-interpolate user-controlled values
- Print readable formatted output, not raw row tuples — column-aligned with `f"{col:<width}"` formatting
- For multi-step investigations, do them in one script: look up the user/roster, then dump related rows (roster players, equipped cards, swaps, weekly bonuses, etc.) — don't make the user run multiple round-trips
- If the data could be sensitive, prefer aggregations over dumping rows wholesale
- Don't include any write/UPDATE/DELETE statements unless the user explicitly asked for it
- End the script with a clear summary line so the user knows what to look at

Reference the schema in `database/models.py` if uncertain about column names. Common joins:
- `users` → `fantasy_rosters` (via `user_id`) → `fantasy_roster_players` (via `roster_id`)
- `users` → `equipped_cards` (via `user_id`) → `user_cards` → `card_templates`
- `fantasy_rosters` → `fantasy_roster_swaps` (via `roster_id`)
- `weekly_player_fp` keyed by `(player_id, season, week)`
- `weekly_card_bonus` keyed by `(roster_id, season, week)` with `breakdowns_json`

After writing the script, give it to the user in a single fenced bash block so they can copy-paste in one shot.
