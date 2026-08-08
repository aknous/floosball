# Fresh start that keeps some history

**Next-season item 10.** Owner intent: restart the simulation totally fresh for the 32-club
expansion, but not lose everything.

**Status:** ✅ **BUILT 2026-08-07.** Scope settled by the owner the same day: *"losing user
progress is fine. I'm not looking to save too much. just light data like who won the
floosbowl each season."*

So the shipped scope is one row per completed season — champion, league champions, MVP —
and nothing else. Sections B and C below are recorded as the analysis that led here, not as
work outstanding. The three ❓ decisions are moot under this scope: user progress is not
preserved, records are not carried forward, and the Hall of Fame is not archived.

  `database/models.py`          LeagueArchive (no foreign keys, by design)
  `database/connection.py`      inline migration + added to preserveTables
  `tools_archive_seasons.py`    dry-run by default; --apply writes
  `GET /api/league-archive`     grouped by era, newest first
  `test_league_archive.py`      18 assertions
  `tools_harvest_names.py`      returns player names to the pool, drops lineage variants
  `test_name_harvest.py`        10 assertions

## ⚠️ The name pool is NOT as safe as it looks

`unused_names` is preserved by `clear_db`, so the pool appears to survive. It does not, in
the way that matters. A name is REMOVED from the pool when a player is created and never
returned — retirement adds a *variant* ("Name Jr.", then III, IV...) via
`seasonManager._recyclePlayerName`, not the original. So every name attached to a player
exists only on a `players` row, and `players` is dropped.

Measured on the prod snapshot: **401 base names sat on player rows and nowhere else**,
including every name submitted through Discord `/name` or added by an admin that had since
been assigned to somebody. Preserving `unused_names` alone would have lost all of them
silently, and nothing would have reported it.

`tools_harvest_names.py` returns them, and drops the 43 pooled + 35 held lineage variants
(owner, 2026-08-07: keep the names, not the Jr artifacts). Pool goes 353 → 711.

Curiosity worth not "fixing": the suffix-stripping path recovers zero extra names, because
`players` KEEPS retired rows, so the original is still there under its own name and is
harvested directly. Verified — "Chick Neriardi" (Retired) and "Chick Neriardi Jr."
(Veteran3) are both rows.

## What a fresh start does today

`clear_db()` preserves exactly four tables — `users`, `beta_allowlist`, `app_settings`,
`unused_names` — and drops the other **68 non-empty tables, 508,433 rows**.

## ⚠️ The real problem is not deletion, it is MIS-ATTRIBUTION

The instinct is "just add the history tables to `preserveTables`." That would be **worse
than losing them**, and it is the single most important finding here.

Nothing in the history tables is denormalized. `records` stores `player_id` and `team_id`
and **no names at all**. `championships` stores `team_id`. `seasons` stores
`champion_team_id` / `mvp_player_id`. The Hall of Fame is not even its own table — it is
`players.is_hof` + `players.hof_season`, and `players` is dropped.

Ids restart from 1. Today: players 1-579, teams 1-24. A fresh 32-club league mints ids
from 1 again, so a preserved `records` row pointing at `player_id 292` would silently
attach a 15-season passing record to whichever rookie happens to get id 292. Every
championship would be reassigned to an unrelated club.

**So preservation means denormalizing into an archive, not keeping the tables.**

## What is actually at stake, in three categories

### A. League history — preservable only as a snapshot

| what | rows | lives in | problem |
|---|---|---|---|
| League records | 64 | `records` | player_id/team_id only, no names |
| Championships | 75 | `championships` | team_id only |
| Season summaries | 15 | `seasons` | champion/MVP/All-Pro as ids |
| Hall of Fame | 21 | `players.is_hof` | the table itself is dropped |
| All-Pro honours | 57 | `players.all_pro_seasons` | same |

### B. User progress — genuinely preservable, and nothing depends on the league

| what | rows | note |
|---|---|---|
| Floobit balances | 170 | `user_currency`: balance, lifetime_earned, lifetime_spent |
| Achievements | 22,534 | `user_achievements` |
| Login streaks | 1,364 | `user_login_days` |

**This is the category that matters most for what comes next.** Renown (item 3) is specced
against lifetime achievement and earning data — if this is wiped, Renown launches with
every user at zero and 15 seasons of engagement erased. Preserving B is a prerequisite for
item 3 being worth building, not a sentimental nicety.

⚠️ `user_achievements.achievement_id` is an FK to `achievements.id`, and `achievements` is
NOT currently preserved — it is dropped, recreated and re-seeded. `_seedAchievements`
upserts by `key`, but on a *recreated* table ids are assigned by insertion order, so every
preserved `user_achievements` row would point at the wrong achievement. **`achievements`
must be preserved alongside it, or the rows remapped by key.** This is the same class of
bug as the mis-attribution above and is easy to miss.

### C. Cannot survive, by nature

Cards (`user_cards`, `card_templates`), fantasy rosters, pick-em picks, weekly FP, shop
purchases. All of it depicts or references players, teams and games that will not exist.
A card of a player who never played in this league is not a card. This should be stated to
users plainly rather than discovered.

## Proposal

**1. Add an era-scoped archive, written BEFORE the wipe.** One table with no foreign keys,
holding denormalized names and values, added to `preserveTables` so it survives this reset
and every future one:

    league_archive(era, era_label, kind, season, subject_name, subject_position,
                   team_name, stat, value, detail_json, created_at)

`kind` covers `record` / `championship` / `season_summary` / `hof` / `all_pro`. Era 1 is
"The 24-Club Era, seasons 1-15". A future reset appends Era 2 rather than overwriting.

**2. Preserve user progress**: add `user_currency`, `user_achievements`, `achievements`
and `user_login_days` to `preserveTables`.

**3. Surface the archive** as a read-only "history" view. It is the only place the old
league exists afterwards, and it is what makes the reset feel like a new era rather than
a deletion.

## ❓ Owner decisions needed

1. **Floobit balances — keep, reset, or partial?** Keeping them means a user with a large
   balance can buy out the new card economy on day one. Resetting the balance while keeping
   `lifetime_earned` preserves the Renown substrate without the economic distortion.
   Recommendation: **reset balance to the standard starter grant, keep lifetime totals.**
2. **Do old records stay comparable?** The league goes 24 → 32 clubs and the sim has been
   rebalanced substantially (scoring, sacks, the run gate model). A preserved single-game
   passing record may be unbeatable or trivial under the new engine. Recommendation:
   **archive them as an era, do not carry them forward as live records to chase.**
3. **Hall of Fame — archive only, or re-inductable?** The 21 inductees cannot exist as
   players again. Recommendation: **archive only**, displayed as a historical wing.

## Execution notes

- This runs as a **script before the wipe**, not as part of `clear_db` — the archive needs
  the old data present to read, and doing it inline would make a failed archive silently
  produce a wiped DB.
- Dry-run first, print the row counts it would write, then confirm. No off-box backup
  exists, so `fly ssh` + a copy of `/data/floosball.db` is a prerequisite, not optional.
- Never `FRESH_START` in prod — it survives restarts and would wipe on outage recovery.
  The supported route is the one-shot `touch /data/.fresh` flag file.
