"""Winning a division is an award, like a league title or a Floos Bowl.

Owner, 2026-08-07. With 8 divisions the division race is the main thing most clubs are
playing for — 24 of 32 will never win a league title — so it needs to be recorded and
displayed like the honours it sits alongside.

Run: .venv/bin/python test_division_titles.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


sm = open('/Users/andrew/Projects/floosball/managers/seasonManager.py').read()
tm = open('/Users/andrew/Projects/floosball/managers/teamManager.py').read()
md = open('/Users/andrew/Projects/floosball/database/models.py').read()
cn = open('/Users/andrew/Projects/floosball/database/connection.py').read()
api = open('/Users/andrew/Projects/floosball/api/main.py').read()

# Read as text — floosball_team has a circular import with floosball_player.
tsrc = open('/Users/andrew/Projects/floosball/floosball_team.py').read()

# ── recorded on the club, in the same shape as the other honours ───────────
expect("clubs carry a divisionTitles list", "self.divisionTitles = []" in tsrc)
expect("and a per-season divisionChamp flag", "'divisionChamp': False," in tsrc)

# ── awarded off the DIVISION standing, not the playoff field ───────────────
# A club can win a weak division without being top-4 overall, and it has still won it.
expect("the winner is the top of its own division", "_ranked = self._seedTeams(list(_members))" in sm)
expect("awarded per division, not per league", "for _divName, _members in divisions.items():" in sm)
expect("announced like other honours", "_divText" in sm and "leagueHighlights.insert" in sm)
expect("idempotent — a resume cannot award it twice",
       "if season_str_div not in _wonSeasons:" in sm)

# ── the DIVISION'S NAME rides with the title ───────────────────────────────
# There is one league title a season and EIGHT division titles, so 'Season 4'
# alone does not say what was won. The name is only knowable at award time:
# teams.division is the CURRENT alignment, so a reader years later would be
# describing today's divisions rather than the one the banner was won in.
expect("the title records the division it was won in",
       "{'season': season_str_div, 'division': _divName}" in sm)
expect("dedupe reads the season out of both entry shapes",
       "_e.get('season') if isinstance(_e, dict) else _e" in sm)
# ⚠️ LEGACY TITLES ARE DELIBERATELY LEFT NAMELESS. A backfill stamping the club's
# CURRENT division was written and removed: divisions do not survive a season (see
# leagueManager's in-place sort of league.teamList at playoff selection), so measured on
# a 20-season database NONE of the 19 prior seasons' divisions match teams.division. The
# backfill would have put a confident wrong name on every historic banner.
expect("no backfill invents a name for a historic title",
       "_backfillDivisionTitleNames" not in cn)

# ── persisted through every layer, or it dies at the next restart ──────────
expect("model column", "division_titles" in md)
expect("inline migration (alembic does not run on deploy)",
       "ALTER TABLE teams ADD COLUMN division_titles" in cn)
expect("loaded from the DB", "team.divisionTitles = db_team.division_titles or []" in tm)
expect("saved to the DB", "db_team.division_titles = getattr(team, 'divisionTitles', []) or []" in tm)
expect("in the team serializer", "'divisionTitles': getattr(team, 'divisionTitles', []) or []," in tm)
expect("exposed by the API", "team_dict['divisionTitles']" in api)

# ── written to the Championship table alongside the others ─────────────────
expect("persisted as championship_type='division'", "('divisionTitles', 'division')," in sm)
# The three original blocks were near-identical copy-paste; a fourth by hand is exactly
# where a title type gets half-added.
expect("all four title types go through ONE loop",
       "TITLE_KINDS = (" in sm and sm.count("('floosbowlChampionships', 'floosbowl')") == 1)
expect("the loop still de-duplicates against existing rows",
       "championship_type=kind," in sm and "if not existing:" in sm)
# ⚠️ A dict entry reaching int() raises ValueError and `continue`s, so the title
# would sit on the club and never reach the queryable table — written, and
# invisible to anything counting championships.
expect("the loop unwraps a dict entry before parsing the season",
       "season_str = entry.get('season') if isinstance(entry, dict) else entry" in sm)
expect("and a non-parsing entry cannot raise out of the loop",
       "except (ValueError, TypeError):" in sm)


print("\nPASS — a division title is recorded, persisted and served like any other honour."
      if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
