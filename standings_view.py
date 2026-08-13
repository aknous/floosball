"""Standings board assembly — divisions, playoff seeds, games back, movement.

The board has to answer three different questions (who leads each division, where
does everyone sit, how close is the wildcard race) off ONE payload, and it has to
agree with how the playoffs will actually seed. So the seeding here is not a second
implementation: it calls `seeding.orderTeams`, the same chain `seasonManager._seedTeams`
runs on, and mirrors `_applyDivisionSeeding`'s rule that a division winner is the best
record inside its own division across the WHOLE league — a club can win a weak division
without being top-half overall and still take a top seed.

⚠️ The seeds a mid-season board shows are a PROJECTION. They are what the field would
look like if the season ended now; nothing here freezes anything.

Two things the live team objects cannot supply, both rebuilt from the games table:

  * `last5` / `streak` — the run of results, which `seasonTeamStats` only keeps as a
    signed counter.
  * `rankLastWeek` / `rankChange` — needs the standings AS OF the end of last week, so
    the finals are re-aggregated up to `week - 1` and re-ordered through the same chain.
    Rebuilding beats snapshotting: no new column, no marker to go stale, and it
    self-heals after a restart or a backfill.
"""

from typing import Any, Dict, List, Optional

from seeding import orderTeams


class _TeamShim:
    """The minimum `seeding.orderTeams` reads: an id, a division, and a stats dict.

    Used to re-rank a past week from raw game rows, where there is no live Team object.
    """

    def __init__(self, teamId: int, division: Optional[str], stats: Dict[str, Any]):
        self.id = teamId
        self.division = division
        self.seasonTeamStats = stats


def divisionsOf(teams: List[Any]) -> Dict[str, List[Any]]:
    """`{divisionName: [teams]}` for clubs carrying a division stamp, in team order."""
    divs: Dict[str, List[Any]] = {}
    for team in teams:
        name = getattr(team, 'division', None)
        if name:
            divs.setdefault(name, []).append(team)
    return divs


def playoffSpots(teamCount: int) -> int:
    """Half the league qualifies — the same slice `_simulatePlayoffRounds` takes."""
    return teamCount // 2


def seedLeague(teams: List[Any], h2hGames=None) -> Dict[str, Any]:
    """Display-ordered league plus the seed each club currently projects to.

    Returns `{'ordered': [...], 'seeds': {teamId: (seed, kind)},
    'divisions': {name: [ids]}, 'recordRanks': {teamId: rank}}`.

    `recordRanks` is position by RECORD, which is deliberately not the display position:
    the movement arrow has to compare like with like across weeks, and a club can shift
    display rows without its record moving at all (a rival winning its division reshuffles
    the seeds around it). Comparing display rows would invent movement nobody earned.

    Display order is the eight qualifiers by SEED, then everyone else by record. Sorting
    the whole league by record instead makes the seed column read 1,2,3,5,6,4 — which
    looks like a bug — and puts the cutline on the wrong row the moment a division winner
    has a losing record, which happens routinely at four clubs per division.
    """
    h2hGames = h2hGames or []
    ordered = orderTeams(list(teams), h2hGames)
    divs = divisionsOf(teams)
    spots = playoffSpots(len(ordered))
    recordRanks = {team.id: i + 1 for i, team in enumerate(ordered)}

    seeds: Dict[int, tuple] = {}

    if len(divs) < 2:
        # No divisions stamped (or one big group): straight record order, every seed a
        # wildcard. Mirrors `_applyDivisionSeeding`'s `len(divs) < 2` fallback.
        for i, team in enumerate(ordered[:spots]):
            seeds[team.id] = (i + 1, 'wildcard')
        return {
            'ordered': ordered,
            'seeds': seeds,
            'divisions': {name: [t.id for t in orderTeams(list(members), h2hGames)]
                          for name, members in divs.items()},
            'recordRanks': recordRanks,
        }

    # A division winner is the best record INSIDE its own division, judged across the
    # whole league rather than among qualifiers — that is what makes winning a weak
    # division worth something.
    winners = []
    divisionOrder: Dict[str, List[int]] = {}
    for name, members in divs.items():
        ranked = orderTeams(list(members), h2hGames)
        divisionOrder[name] = [t.id for t in ranked]
        if ranked:
            winners.append(ranked[0])
    winners = orderTeams(winners, h2hGames)

    winnerIds = {t.id for t in winners}
    for i, team in enumerate(winners):
        seeds[team.id] = (i + 1, 'division')

    wildcardSlots = max(0, spots - len(winners))
    wildcards = [t for t in ordered if t.id not in winnerIds][:wildcardSlots]
    for i, team in enumerate(wildcards):
        seeds[team.id] = (len(winners) + i + 1, 'wildcard')

    qualifierIds = winnerIds | {t.id for t in wildcards}
    display = winners + wildcards + [t for t in ordered if t.id not in qualifierIds]

    return {'ordered': display, 'seeds': seeds, 'divisions': divisionOrder,
            'recordRanks': recordRanks}


def _record(team) -> tuple:
    stats = getattr(team, 'seasonTeamStats', {}) or {}
    return (stats.get('wins', 0) or 0, stats.get('losses', 0) or 0)


def _points(team) -> float:
    """A club's standing in the currency the table is sorted in.

    A tie is half a win, which is why this cannot be a win count: a club can hold
    MORE wins and a WORSE win percentage than a rival with ties, so clinching off
    raw wins would claim berths that are not secured.
    """
    stats = getattr(team, 'seasonTeamStats', {}) or {}
    wins = stats.get('wins', 0) or 0
    ties = stats.get('ties', 0) or 0
    return float(wins) + 0.5 * float(ties)


def _played(team) -> int:
    stats = getattr(team, 'seasonTeamStats', {}) or {}
    return int((stats.get('wins', 0) or 0) + (stats.get('losses', 0) or 0)
               + (stats.get('ties', 0) or 0))


def clinchStatus(teams: List[Any], totalGames: int) -> Dict[int, Dict[str, bool]]:
    """Who is mathematically IN, who has won their division, who owns the top seed.

    `{teamId: {'clinchedPlayoffs', 'clinchedDivision', 'clinchedTopSeed',
    'eliminated'}}`.

    The test is "can this club still be caught": a rival's CEILING is its current
    points plus a win in every game it has left, and this club's FLOOR is its
    points now. Anyone whose ceiling cannot reach the floor is out of the race.

    ⚠️ DELIBERATELY CONSERVATIVE, and the direction matters. It ignores head to
    head, division records and every other tiebreaker, and it lets every rival
    win out at once even where they play each other. So a club may be shown as
    clinched a little LATE — never early. A badge that appears and then has to be
    taken away is worse than one that appears a week after the fact.

    ⚠️ It also does NOT reuse `leagueManager.checkPlayoffClinching`, which is dead
    code and unsafe here: that takes the top half BY RECORD as the playoff field,
    which stopped being true when divisions arrived — a division winner is
    guaranteed a top-four seed regardless of record, so the field and the record
    order are different sets. Seeding lives in `seedLeague`, so clinching lives
    beside it and the two cannot contradict each other.
    """
    out: Dict[int, Dict[str, bool]] = {}
    if not teams:
        return out
    spots = playoffSpots(len(teams))
    divisions = divisionsOf(teams)
    divisionOf = {getattr(t, 'id', None): name
                  for name, members in divisions.items() for t in members}

    def ceiling(team) -> float:
        return _points(team) + max(0, totalGames - _played(team))

    for team in teams:
        tid = getattr(team, 'id', None)
        floor = _points(team)
        myCeiling = ceiling(team)
        rivals = [t for t in teams if getattr(t, 'id', None) != tid]

        # Clubs that can still finish above this one. If fewer than the number of
        # berths can pass it, it is in whatever they all do.
        canPassMe = sum(1 for t in rivals if ceiling(t) > floor)
        # Clubs this one can no longer catch. Once that many sit above it, the
        # berths are gone.
        cannotBeCaught = sum(1 for t in rivals if _points(t) > myCeiling)

        myDivision = divisionOf.get(tid)
        divisionRivals = [t for t in divisions.get(myDivision, [])
                          if getattr(t, 'id', None) != tid] if myDivision else []
        divisionClinched = bool(myDivision) and all(
            ceiling(t) <= floor for t in divisionRivals)
        # ⚠️ THE DIVISION IS A SECOND ROAD IN, so it also decides elimination. The
        # title is lost only once a rival is beyond reach; while it is winnable a
        # club is alive no matter how far down the league table it sits.
        divisionLost = bool(myDivision) and any(
            _points(t) > myCeiling for t in divisionRivals)

        out[tid] = {
            # ⚠️ WINNING THE DIVISION IS AN AUTO-CLINCH (owner). A division winner
            # takes a guaranteed top-four seed, so the berth does not depend on
            # the record race at all — a club can win a weak division while more
            # than `spots` league rivals could still finish above it, and it is
            # in regardless. Computing the two independently missed that and held
            # the berth badge back behind a test that no longer applies.
            'clinchedPlayoffs': (canPassMe < spots) or divisionClinched,
            'clinchedDivision': divisionClinched,
            # ⚠️ The top seed needs the DIVISION as well as the record. Division
            # winners take the top four seeds, so a club with the best record in
            # the league is not the 1 seed until its own division is settled —
            # it could still be seeded behind a winner it out-performed.
            'clinchedTopSeed': divisionClinched and canPassMe == 0,
            # ⚠️ ELIMINATED MEANS NO ROAD IN AT ALL, not "too far down the table".
            # Reported from the live board: a club that had WON ITS DIVISION was
            # being greyed out as eliminated, because its record was poor enough
            # that `spots` rivals sat above it — which is exactly the situation a
            # guaranteed division seed exists to protect. A club is out only when
            # the wildcard is gone AND the division is lost; an undivisioned
            # league has only the one road, so the wildcard test stands alone.
            # This is the mirror of the auto-clinch above and was missed with it.
            'eliminated': (cannotBeCaught >= spots
                           and (divisionLost or not myDivision)),
        }
    return out


def gamesBackFrom(cutTeam, team) -> float:
    """Games behind the club holding the LAST playoff spot.

    Signed so the column reads as a race rather than a ranking: negative is ahead of the
    cut, 0 is the club on it, positive is chasing. Half-games are real — one club playing
    a game the other has not shifts the gap by a half.
    """
    if cutTeam is None:
        return 0.0
    cutW, cutL = _record(cutTeam)
    w, l = _record(team)
    return ((cutW - w) + (l - cutL)) / 2.0


def _emptyStats() -> Dict[str, Any]:
    return {
        'wins': 0, 'losses': 0, 'ties': 0,
        'winPerc': 0.0, 'scoreDiff': 0,
        'divWins': 0, 'divLosses': 0, 'divTies': 0,
        'lgWins': 0, 'lgLosses': 0, 'lgTies': 0,
        'Offense': {'pts': 0},
    }


def _applyResult(stats: Dict[str, Any], scored: int, allowed: int,
                 sameDivision: bool, sameLeague: bool) -> None:
    stats['Offense']['pts'] += scored
    stats['scoreDiff'] += (scored - allowed)
    if scored > allowed:
        key, divKey, lgKey = 'wins', 'divWins', 'lgWins'
    elif allowed > scored:
        key, divKey, lgKey = 'losses', 'divLosses', 'lgLosses'
    else:
        key, divKey, lgKey = 'ties', 'divTies', 'lgTies'
    stats[key] += 1
    # A division game is always a league game too — the same rule the live game-end path
    # applies, so a rebuilt week cannot disagree with a played one.
    if sameDivision:
        stats[divKey] += 1
    if sameDivision or sameLeague:
        stats[lgKey] += 1


def _finalise(stats: Dict[str, Any]) -> Dict[str, Any]:
    played = stats['wins'] + stats['losses'] + stats['ties']
    stats['winPerc'] = round((stats['wins'] + 0.5 * stats['ties']) / played, 4) if played else 0.0
    return stats


def buildFormAndMovement(session, season: int,
                         teamsByLeague: Dict[str, List[Any]]) -> Dict[int, Dict[str, Any]]:
    """Per-team `last5`, `streak` and last week's rank, rebuilt from final games.

    One query for the season's finals, then two passes: results in week order for the
    form fields, and everything before the latest played week re-ranked through
    `seeding.orderTeams` for the movement arrow. Returns `{teamId: {...}}`.

    ⚠️ The cutoff is the newest week with a FINAL game, taken from the rows themselves —
    not `seasonManager.currentWeek`. Two reasons. The live standings only reflect finals,
    so cutting at `currentWeek` includes every game the board is already showing and the
    movement column comes back all zeroes (it did). And `currentWeek` is a known-stale
    field; the games table is the thing that actually moved.
    """
    from database.models import Game
    from seeding import REGULAR_SEASON_WEEKS

    divisionOf: Dict[int, Optional[str]] = {}
    leagueOf: Dict[int, str] = {}
    for leagueName, teams in teamsByLeague.items():
        for team in teams:
            divisionOf[team.id] = getattr(team, 'division', None)
            leagueOf[team.id] = leagueName

    rows = (
        session.query(
            Game.week, Game.home_team_id, Game.away_team_id,
            Game.home_score, Game.away_score,
        )
        .filter(
            Game.season == season,
            Game.status == 'final',
            Game.week <= REGULAR_SEASON_WEEKS,
        )
        .order_by(Game.week.asc(), Game.id.asc())
        .all()
    )

    results: Dict[int, List[str]] = {}
    priorStats: Dict[int, Dict[str, Any]] = {}
    # The board is a snapshot of everything final; "last week" is everything final
    # BEFORE the newest week that has produced a result.
    latestWeek = max((r[0] for r in rows), default=0)

    for gameWeek, homeId, awayId, homeScore, awayScore in rows:
        homeScore = homeScore or 0
        awayScore = awayScore or 0
        if homeScore > awayScore:
            homeMark, awayMark = 'W', 'L'
        elif awayScore > homeScore:
            homeMark, awayMark = 'L', 'W'
        else:
            homeMark = awayMark = 'T'
        results.setdefault(homeId, []).append(homeMark)
        results.setdefault(awayId, []).append(awayMark)

        if gameWeek < latestWeek:
            sameDivision = (divisionOf.get(homeId) is not None
                            and divisionOf.get(homeId) == divisionOf.get(awayId))
            sameLeague = leagueOf.get(homeId) == leagueOf.get(awayId)
            for teamId in (homeId, awayId):
                priorStats.setdefault(teamId, _emptyStats())
            _applyResult(priorStats[homeId], homeScore, awayScore, sameDivision, sameLeague)
            _applyResult(priorStats[awayId], awayScore, homeScore, sameDivision, sameLeague)

    # Last week's rank, per league. Week 1 has no prior week, and neither does a season
    # whose games have not been played yet — both leave rankLastWeek null rather than
    # inventing a movement arrow out of an empty table.
    rankLastWeek: Dict[int, int] = {}
    if priorStats:
        for leagueName, teams in teamsByLeague.items():
            shims = [
                _TeamShim(team.id, divisionOf.get(team.id),
                          _finalise(priorStats.get(team.id) or _emptyStats()))
                for team in teams
            ]
            for i, shim in enumerate(orderTeams(shims, [])):
                rankLastWeek[shim.id] = i + 1

    out: Dict[int, Dict[str, Any]] = {}
    for teamId in {t.id for teams in teamsByLeague.values() for t in teams}:
        marks = results.get(teamId, [])
        # Oldest first, newest last — the design reads the bar strip left to right as
        # time, so reversing it here would run the season backwards.
        last5 = marks[-5:]
        streak = ''
        if marks:
            latest = marks[-1]
            run = 0
            for mark in reversed(marks):
                if mark != latest:
                    break
                run += 1
            streak = f"{latest}{run}"
        out[teamId] = {
            'last5': last5,
            'streak': streak,
            'rankLastWeek': rankLastWeek.get(teamId),
        }
    return out
