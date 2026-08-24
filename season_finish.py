"""Where a club actually finished each season: its division placing and its playoff exit.

The season-history table showed a W-L line and one of five flags — Floos Bowl, League
champions, Top seed, Playoffs, Missed playoffs. That collapses everything that matters:
a club beaten in Round 1 reads identically to one beaten in the League Championship, and
a 13-1 side edged out of a division reads identically to a 2-12 one.

⚠️ DERIVED, NOT STORED, for both halves — the same trade `playoff_history` makes. A stored
column only starts answering the season it ships; this answers for every season already in
the database, which for a league on season 20 is the entire point.

  PLAYOFF EXIT comes from `playoff_history.buildPlayoffHistory` (games carry `is_playoff`
  and `playoff_round`).

  DIVISION PLACING is recovered from the SCHEDULE. Nothing records which division a club
  was in for a past season, and ⚠️ **`teams.division` IS NOT A SUBSTITUTE — IT IS
  MEASURABLY THE WRONG ANSWER.** On a 20-season database, ZERO of the 19 prior seasons'
  divisions match it; only the season being played does. Divisions are re-formed every
  year because `leagueManager` sorts `league.teamList` IN PLACE by record at playoff
  selection and `_assignDivisions` then slices that same list positionally the next
  season — the reshuffle that `_assignDivisions`'s own docstring says cannot happen
  ("nothing here reshuffles annually"). That is a sim defect, reported separately; this
  module has to read past seasons correctly either way.

  The schedule gives the division away: `_generateDivisionalSchedule` plays each division
  rival twice home and away (4 times) and everyone else at most twice, so a club's
  division is exactly the set of opponents it faced most often. Verified across all 20
  seasons of a production-shaped database: every season partitions into 8 mutual blocks
  of 4.

⚠️ THE DERIVATION IS SELF-CHECKING AND FAILS TO SILENCE, NOT TO A GUESS. A block is used
only when the "played most often" relation is MUTUAL and those rivals are a STRICT subset
of the clubs faced — part-way through a season everyone has met everyone once, so there is
no division signal at all, and a size bound alone would let that through in a small
league. The division's NAME is reported only when every member of the block still shares
one, which for a past season is usually nobody: the reshuffle means the honest answer is
"3rd in division", not "3rd in Twill".

Ordering inside the division goes through `seeding.orderTeams`, the same function the
standings board and the playoff seeding use, rather than a local sort on win percentage —
the tiebreaker chain is contextual (division record inside a division race) and a second
copy of it would drift from the one that decides the real thing.
"""
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import logging

logger = logging.getLogger(__name__)

# A derived block is only trusted at a plausible division size. The league has run 8
# divisions of 4 and, before that, 2 of 8; anything outside this band means the heuristic
# has not found a division (most often a season that is still being played).
MIN_DIVISION_SIZE = 2
MAX_DIVISION_SIZE = 8


def _regularSeasonGames(session, teamIds: Optional[set] = None) -> List[Tuple]:
    """Every final REGULAR-SEASON game, as (season, home, away, homeScore, awayScore).

    Filtered on `is_playoff` rather than a week number: the season length has already
    moved once (24 clubs / 14 weeks -> 32 / 28) and the flag is what the rest of the app
    trusts. The same rows serve both the division derivation and the head-to-head
    tiebreaker, so the two cannot disagree about which games counted.
    """
    from database.models import Game
    rows = (
        session.query(Game.season, Game.home_team_id, Game.away_team_id,
                      Game.home_score, Game.away_score)
        .filter(Game.status == 'final',
                (Game.is_playoff == False) | (Game.is_playoff.is_(None)))  # noqa: E712
        .all()
    )
    return [(r[0], r[1], r[2], r[3] or 0, r[4] or 0) for r in rows]


def divisionBlock(games: List[Tuple], season: int, teamId: int) -> Optional[set]:
    """The set of clubs sharing `teamId`'s division that season, or None if unrecoverable.

    None rather than a best guess: a wrong division placing is worse than no placing,
    since the reader has no way to tell one from the other.
    """
    opponents: Dict[int, Counter] = defaultdict(Counter)
    for s, home, away, _hs, _as in games:
        if s != season:
            continue
        opponents[home][away] += 1
        opponents[away][home] += 1
    if teamId not in opponents:
        return None

    def rivalsOf(t: int) -> set:
        counts = opponents.get(t)
        if not counts:
            return set()
        most = max(counts.values())
        return {other for other, n in counts.items() if n == most}

    rivals = rivalsOf(teamId)
    block = rivals | {teamId}
    # ⚠️ THE REAL TEST IS "SOME OPPONENTS MORE THAN OTHERS", NOT A SIZE. Part-way through
    # a season every club has met everyone once, so "faced most often" is the entire
    # league and there is no division signal at all — and a size bound alone lets that
    # through whenever the league happens to be small enough to fit. The rivals must be a
    # STRICT subset of the clubs faced.
    if len(rivals) >= len(opponents[teamId]):
        return None
    if not (MIN_DIVISION_SIZE <= len(block) <= MAX_DIVISION_SIZE):
        return None
    # Mutual, or it is not a division. A club that merely happens to have played someone
    # twice in an interrupted schedule fails here.
    for other in rivals:
        if teamId not in rivalsOf(other):
            return None
    return block


class _SeedShim:
    """The duck type `seeding.orderTeams` reads: `.id`, `.division`, `.seasonTeamStats`.

    Built from a stored `team_season_stats` row so a past season can be ordered by the
    live tiebreaker chain without loading the whole league into memory.
    """

    __slots__ = ('id', 'division', 'seasonTeamStats')

    def __init__(self, teamId: int, division: Optional[str], row: Any):
        self.id = teamId
        self.division = division
        self.seasonTeamStats = {
            'winPerc': row.win_percentage or 0.0,
            'scoreDiff': row.score_differential or 0,
            'divWins': row.div_wins or 0,
            'divLosses': row.div_losses or 0,
            'divTies': row.div_ties or 0,
            'lgWins': row.lg_wins or 0,
            'lgLosses': row.lg_losses or 0,
            'lgTies': row.lg_ties or 0,
            'Offense': {'pts': row.points or 0},
        }


def buildSeasonFinishes(session, teamId: int,
                        excludeSeasons: Optional[set] = None) -> Dict[int, Dict[str, Any]]:
    """Per-season finish detail for one club, keyed by season number.

    `excludeSeasons` is for the season still being played: its division placing would read
    as a final standing, and its playoff run has not happened.
    """
    excludeSeasons = excludeSeasons or set()
    out: Dict[int, Dict[str, Any]] = {}

    try:
        from database.models import TeamSeasonStats, Team
        from seeding import orderTeams
    except Exception as e:
        logger.debug(f"Season finishes unavailable: {e}")
        return out

    try:
        games = _regularSeasonGames(session)
        seasons = {s for s, *_rest in games} - excludeSeasons
        if not seasons:
            return out

        statRows = (
            session.query(TeamSeasonStats)
            .filter(TeamSeasonStats.season.in_(seasons))
            .all()
        )
        statsBySeason: Dict[int, Dict[int, Any]] = defaultdict(dict)
        for r in statRows:
            statsBySeason[r.season][r.team_id] = r

        # Today's alignment, used ONLY to name a block whose members still agree on it.
        currentDivision = {
            tid: div for tid, div in session.query(Team.id, Team.division).all()
        }

        playoffBySeason = {}
        try:
            from playoff_history import buildPlayoffHistory
            playoffBySeason = {h['season']: h for h in buildPlayoffHistory(session, teamId)}
        except Exception as e:
            logger.debug(f"Playoff history unavailable for team {teamId}: {e}")

        for season in sorted(seasons):
            entry: Dict[str, Any] = {}

            run = playoffBySeason.get(season)
            if run:
                entry['playoffOutcome'] = run['outcome']
                entry['playoffBadge'] = run['badge']
                entry['deepestRound'] = run['deepestRound']

            block = divisionBlock(games, season, teamId)
            stats = statsBySeason.get(season) or {}
            if block and all(t in stats for t in block):
                h2h = [(h, a, hs, ass) for s, h, a, hs, ass in games if s == season]
                shims = [
                    _SeedShim(t, currentDivision.get(t), stats[t]) for t in sorted(block)
                ]
                ordered = orderTeams(shims, h2h)
                rank = next((i + 1 for i, t in enumerate(ordered) if t.id == teamId), None)
                if rank:
                    entry['divisionRank'] = rank
                    entry['divisionSize'] = len(block)
                    names = {currentDivision.get(t) for t in block}
                    entry['divisionName'] = names.pop() if len(names) == 1 else None

            if entry:
                out[season] = entry
    except Exception as e:
        logger.debug(f"Season finishes failed for team {teamId}: {e}")
        return {}

    return out
