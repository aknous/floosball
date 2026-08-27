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


def _projected(team, winsOut: bool, totalGames: int) -> '_TeamShim':
    """This club's record if it wins (or loses) every game it has left."""
    stats = dict(getattr(team, 'seasonTeamStats', {}) or {})
    remaining = max(0, totalGames - _played(team))
    wins = (stats.get('wins', 0) or 0) + (remaining if winsOut else 0)
    losses = (stats.get('losses', 0) or 0) + (0 if winsOut else remaining)
    ties = stats.get('ties', 0) or 0
    played = wins + losses + ties
    stats['wins'], stats['losses'] = wins, losses
    stats['winPerc'] = ((wins + 0.5 * ties) / played) if played else 0.0
    return _TeamShim(getattr(team, 'id', None), getattr(team, 'division', None), stats)


def regularSeasonWeeks(schedule) -> int:
    """How many REGULAR-SEASON weeks a season's schedule holds — i.e. how many games
    each club plays, which is what clinching is measured against.

    ⚠️ `seasonManager._simulatePlayoffRounds` APPENDS each playoff round to the very
    same `currentSeason.schedule` list, so a plain `len(schedule)` climbs 28 -> 29 ->
    30 -> 31 -> 32 across the postseason. Every one of those phantom weeks reads to
    `clinchStatus` as a game still in hand, and its whole method is "can anyone still
    catch me" — so the badges dissolve exactly when the season is most settled.
    Measured on a played-out 16-club league: at 32 the clinched count fell 8 -> 4,
    eliminated 8 -> 4, division winners 4 -> 2 and the top seed 1 -> 0, which is the
    board showing no eliminations, no division trophies, and seeds still reading as
    projections after the Floos Bowl.

    A week counts when it holds a regular-season game. Playoff games are stamped
    `isRegularSeasonGame = False` at creation, so this reads the flag rather than
    assuming a week count — the season length has already moved once (24 clubs / 14
    weeks -> 32 / 28) and a hardcoded 28 would rot the same way.

    Returns 0 for an empty or unusable schedule; callers treat that as "unknown" and
    skip clinching rather than badging off a guess.
    """
    if not schedule:
        return 0
    weeks = 0
    for entry in schedule:
        try:
            games = entry.get('games') or [] if hasattr(entry, 'get') else []
        except Exception:
            continue
        if any(getattr(g, 'isRegularSeasonGame', False) for g in games):
            weeks += 1
    return weeks


def _divisionRate(wins: float, losses: float, ties: float) -> float:
    """Win rate inside the division. Mirrors `seeding._divisionWinPerc`, which is what
    actually breaks a division tie, so the two cannot disagree."""
    played = wins + losses + ties
    if not played:
        return 0.0
    return round((wins + 0.5 * ties) / played, 4)


def _divisionTiebreakSecured(team, rival, totalGames: int) -> bool:
    """Would `team` beat `rival` on DIVISION RECORD no matter how the rest plays out?

    The first tiebreaker after win% when both clubs share a division, and the only rung
    of the chain that can be bounded at all — so it is the only rung a clinch can be
    proved on. Below it sits SCORE DIFFERENTIAL, which has no ceiling (a club can win by
    one or by forty), and nothing after that is projectable either. A club that cannot
    settle it here is genuinely undecided, not merely unproven.

    ⚠️ The bound is TOTAL remaining games, not remaining DIVISION games. Fewer of a
    club's remaining fixtures are divisional than that, so this over-states how far the
    rival can climb and how far this club can fall — deliberately, because it needs no
    schedule lookup and no assumption about the season's shape. The 28-week format is
    12 division games out of 28 today, and that split has already moved once (it was
    14/8/6 at 24 clubs); a clinch rule must not quietly depend on it.
    """
    myStats = getattr(team, 'seasonTeamStats', {}) or {}
    rivalStats = getattr(rival, 'seasonTeamStats', {}) or {}

    myLeft = max(0, totalGames - _played(team))
    rivalLeft = max(0, totalGames - _played(rival))


    # This club's floor: every remaining game a divisional LOSS.
    mine = _divisionRate(
        (myStats.get('divWins', 0) or 0),
        (myStats.get('divLosses', 0) or 0) + myLeft,
        (myStats.get('divTies', 0) or 0))
    # The rival's ceiling: every remaining game a divisional WIN.
    theirs = _divisionRate(
        (rivalStats.get('divWins', 0) or 0) + rivalLeft,
        (rivalStats.get('divLosses', 0) or 0),
        (rivalStats.get('divTies', 0) or 0))
    return mine > theirs


def clinchStatus(teams: List[Any], totalGames: int) -> Dict[int, Dict[str, bool]]:
    """Who is mathematically IN, who has won their division, who owns the top seed.

    `{teamId: {'clinchedPlayoffs', 'clinchedDivision', 'clinchedTopSeed',
    'eliminated'}}`.

    ⚠️ THE TEST RUNS THE REAL SEEDING, not a count of who is above you. It used to
    ask "can fewer than `spots` clubs finish ahead of me on record", which is wrong
    the moment divisions exist: a DIVISION WINNER takes a guaranteed top-four seed
    with any record at all, so it occupies a berth without ever appearing above you
    in the table. Measured on the live board — BOS, DET and PHI all finished 14-14
    with only seven clubs holding more points, so all three read as CLINCHED while
    actually missing the field, because 13-15 MIN had won its division and taken
    seed 4.

    So each club is seeded twice through `seedLeague`, the same chain the playoffs
    run on:
      * WORST case (this club loses out, every rival wins out) — still seeded means
        nothing can take the berth away, so it is CLINCHED.
      * BEST case (this club wins out, every rival loses out) — not seeded even
        then means there is no road left, so it is ELIMINATED.

    That gets the division rule, the seeding order and the tiebreakers for free, and
    it cannot contradict the seeds the board is showing beside it.

    ⚠️ Still CONSERVATIVE by construction: every rival winning out at once is not
    actually possible where they play each other, so a badge can appear a week LATE
    and never early. A badge that has to be taken away reads as the table lying.
    """
    out: Dict[int, Dict[str, bool]] = {}
    if not teams:
        return out
    divisions = divisionsOf(teams)
    divisionOf = {getattr(t, 'id', None): name
                  for name, members in divisions.items() for t in members}

    def ceiling(team) -> float:
        return _points(team) + max(0, totalGames - _played(team))

    for team in teams:
        tid = getattr(team, 'id', None)
        floor = _points(team)
        myCeiling = ceiling(team)

        # Everyone else at their best, this club at its worst.
        worstShims = [_projected(t, t is not team, totalGames) for t in teams]
        worstSeeds = seedLeague(worstShims)['seeds']
        # This club at its best, everyone else at their worst.
        bestShims = [_projected(t, t is team, totalGames) for t in teams]
        bestSeeds = seedLeague(bestShims)['seeds']

        # ⚠️ A PROJECTED TIE PROVES NOTHING, and this is what put a wildcard badge on a
        # club that then missed the playoffs. `_projected` advances wins and losses only:
        # `divWins` / `lgWins` ride through UNCHANGED, so when the worst case lands on a
        # TIE, `orderTeams` breaks it on TODAY's division and league records rather than
        # the ones the finished season will hold. The club won the projected tiebreak,
        # was shown as clinched, lost in week 28 and lost the real tiebreak with it.
        #
        # Reported exactly there: the Broads shown as having clinched a wildcard after
        # week 27 and out of the field after week 28. A badge that has to be taken away
        # is the one failure this whole function exists to avoid.
        #
        # So a berth has to survive every tie going AGAINST this club: seeded in the
        # worst case, and nobody left outside the field level with it on points.
        # ⚠️ ONCE THE SEASON IS OVER THE TIE GUARDS BELOW ARE WRONG. They exist because a
        # PROJECTED tie is unresolved — `_projected` cannot move div/league records, so a
        # tie broken on today's numbers is not the tie the finished season will hold. With
        # every game played there is no projection: the worst case IS the result, the
        # tiebreakers have run on final numbers, and the field is settled.
        #
        # Reported from a finished board — the 7 and 8 seeds shown as NOT having clinched,
        # tied on record and on league record with the club in 9th. They were in; the
        # guard was still asking whether a tie could take it away when there was nothing
        # left to play.
        #
        # This is the same correction the division badge already got a commit earlier. It
        # needed making twice because the berth and the title are computed separately.
        seasonComplete = bool(teams) and all(_played(t) >= totalGames for t in teams)

        myWorst = next((sh for sh in worstShims if sh.id == tid), None)
        tiedFromOutside = (not seasonComplete) and myWorst is not None and any(
            sh.id != tid and worstSeeds.get(sh.id) is None
            and _points(sh) >= _points(myWorst) for sh in worstShims)

        # The mirror, so elimination is not claimed on a tie either: a club level with
        # someone inside the field at ITS best could still win that tiebreak.
        #
        # ⚠️ IT HAS TO BE A REAL TIE, AGAINST A SEED THIS CLUB CAN ACTUALLY CONTEST, and
        # this read `<=` over EVERY seeded club. Two separate faults, and together they
        # made elimination nearly unreachable in a league with one weak division.
        #
        #   `<=` rather than `==`: the comment says "level with", and level is the only
        #   thing that proves anything. Being AHEAD of a club inside the field while
        #   still outside it yourself is not a tiebreak you might win — it is evidence
        #   that their berth does not come from their record.
        #
        #   ...which is the second fault: a DIVISION WINNER holds a top-four seed at ANY
        #   record, so a bad one sits inside the field on far fewer points than a healthy
        #   club sitting outside it. You cannot take that berth by out-pointing them; it
        #   is their division's, and you are not in it.
        #
        # Reported from the live board: the Oysters **3 games back of the wildcard and 4
        # back in their own division with 2 to play** — no path by either route — shown
        # as alive, and the Monuments likewise. Reproduced exactly: with one weak
        # division whose winner sat on 8 points, a club whose ABSOLUTE ceiling was 13
        # cleared `8 <= 13` and was spared, and **1 club of 16 was eliminated where 5
        # had no road left**.
        #
        # So the tie must be genuine, and the seed contestable: a WILDCARD berth is open
        # to anyone, a DIVISION berth only to that division's own members.
        myBest = next((sh for sh in bestShims if sh.id == tid), None)
        myDivision = divisionOf.get(tid)

        def _contestable(otherId) -> bool:
            seed = bestSeeds.get(otherId)
            if seed is None:
                return False
            kind = seed[1] if isinstance(seed, (tuple, list)) and len(seed) > 1 else None
            if kind != 'division':
                return True                      # a wildcard is open to the whole league
            return divisionOf.get(otherId) == myDivision and myDivision is not None

        tiedFromInside = (not seasonComplete) and myBest is not None and any(
            sh.id != tid and _contestable(sh.id)
            and _points(sh) == _points(myBest) for sh in bestShims)

        divisionRivals = [t for t in divisions.get(myDivision, [])
                          if getattr(t, 'id', None) != tid] if myDivision else []
        # A title is won when no rival can reach this club, and lost once one is
        # beyond reach. Both are within-division questions, so they stay a points
        # comparison rather than a re-seed.
        #
        # ⚠️ STRICTLY LESS THAN. `<=` says a rival who can draw LEVEL cannot take the
        # title, and that is false: a level finish goes to the tiebreaker chain, which
        # the leader can lose. Reported from a live board at week 27 — the Sand Dollars
        # were shown as division champions one game up on the club they still had to
        # PLAY in week 28, where a loss ties them and hands the title to a tiebreak.
        #
        # ⚠️ It also produced a self-contradicting row. `clinchedPlayoffs` runs the real
        # worst-case seeding, which honours the division rule; a genuine division winner
        # is therefore always seeded and always reads as clinched too. This test was the
        # only one using a different, looser rule, so it was the only way the board could
        # claim a division title and no playoff berth at the same time.
        #
        # ⚠️ IT DOES NOT RE-SEED TO BREAK THE TIE, and that is deliberate. Running the
        # worst case through `seedLeague` and asking whether this club still leads its
        # division looks like the obvious upgrade and is wrong: `_projected` advances wins
        # and losses only, so `divWins` / `divLosses` ride through UNCHANGED and a
        # projected tie would be settled on TODAY's division record while the games that
        # decide it are unplayed. That is exactly the reported case — the Rocks shown as
        # champions when a week-28 loss ties them and the Strangers take it on division
        # record.
        #
        # `_divisionTiebreakSecured` answers the same question honestly instead: it moves
        # the division record to this club's FLOOR and the rival's CEILING, so a clinch is
        # claimed only where the tie is already decided whatever happens. That is strictly
        # harsher than what `seedLeague` would do with today's numbers, which is what
        # keeps `clinchedDivision` from ever outrunning `clinchedPlayoffs`.
        # A rival who cannot even reach this club's points is beaten outright. One who
        # can draw LEVEL is only beaten if the tie itself is already decided — see
        # `_divisionTiebreakSecured`.
        def rivalBeaten(t) -> bool:
            rivalCeiling = ceiling(t)
            if rivalCeiling < floor:
                return True
            if rivalCeiling > floor:
                return False
            return _divisionTiebreakSecured(team, t, totalGames)

        # ⚠️ A FINISHED DIVISION IS DECIDED BY ITS ACTUAL ORDER, not by projection.
        # With every game played there is no floor and no ceiling, just a result, and the
        # rungs below division record settle it — score differential, then head-to-head
        # point diff, then points for and against. None of those can be bounded, which is
        # why the projection stops at division record; at season end it does not have to.
        #
        # ⚠️ It must be ONE ordering of the whole division, never a pairwise test. Two
        # clubs tied all the way down the chain each win their own pairwise comparison,
        # because the sort is stable and each sees itself first — so BOTH were crowned.
        # Ordering the division once gives exactly one leader by construction.
        #
        # Without any of this, two clubs finishing level on record and division record
        # left the division with NO champion on the board while the seeding beneath had
        # already picked one and shown that club a berth.
        divisionMembers = divisions.get(myDivision, []) if myDivision else []
        seasonOver = bool(divisionMembers) and all(
            _played(t) >= totalGames for t in divisionMembers)
        if seasonOver:
            try:
                from seeding import orderTeams
                divisionClinched = orderTeams(list(divisionMembers))[0] is team
            except Exception:
                divisionClinched = all(rivalBeaten(t) for t in divisionRivals)
        else:
            divisionClinched = bool(myDivision) and all(rivalBeaten(t) for t in divisionRivals)

        seededAtWorst = worstSeeds.get(tid)
        seededAtBest = bestSeeds.get(tid)

        # ⚠️ A SECURED DIVISION TITLE IS A BERTH WHATEVER THE POINTS DO — the seed is
        # guaranteed, so it does not depend on winning a tie for a wildcard place and the
        # tie test above must not withhold it. `divisionClinched` has already proved the
        # title survives every tie, so leaning on it here is not circular.
        safeOnPoints = seededAtWorst is not None and not tiedFromOutside

        out[tid] = {
            'clinchedPlayoffs': bool(divisionClinched or safeOnPoints),
            'clinchedDivision': divisionClinched,
            # The top seed has to survive the worst case as seed 1 specifically, and a
            # tie for it is no more decided than a tie for the last berth.
            'clinchedTopSeed': (seededAtWorst is not None and seededAtWorst[0] == 1
                                and not tiedFromOutside),
            'eliminated': seededAtBest is None and not tiedFromInside,
        }
    return out


def gamesBackFrom(refTeam, team) -> float:
    """Games behind a reference club. Half-games are real — one club having played a game
    the other has not shifts the gap by a half.

    Used against TWO references, and the sign means different things in each:

      - the club ON the playoff cut (`gamesBack`): negative is ahead of the cut, 0 is the
        club holding the last spot, positive is chasing;
      - the DIVISION LEADER (`divisionGamesBack`): 0 is the leader and nothing is
        negative, which is the ordinary standings-table reading.
    """
    if refTeam is None:
        return 0.0
    refW, refL = _record(refTeam)
    w, l = _record(team)
    return ((refW - w) + (l - refL)) / 2.0


def divisionGamesBack(divisions: Dict[str, List[int]], teams: List[Any]) -> Dict[int, float]:
    """{teamId: games behind ITS OWN division leader}.

    The league column answers "am I making the playoffs"; this one answers "am I winning
    my division", which at four clubs per division is what most of the league is actually
    racing for — 24 of 32 will never win a league title.

    ⚠️ The leader is `divisions[name][0]`, which `seedLeague` has already ordered through
    the full tiebreaker chain (`orderTeams`). Do not re-derive it by max(winPct): that
    skips the contextual tiebreaker and would disagree with the division-winner rule the
    same payload reports.
    """
    byId = {t.id: t for t in teams}
    out: Dict[int, float] = {}
    for memberIds in (divisions or {}).values():
        if not memberIds:
            continue
        leader = byId.get(memberIds[0])
        if leader is None:
            continue
        for tid in memberIds:
            team = byId.get(tid)
            if team is not None:
                out[tid] = gamesBackFrom(leader, team)
    return out


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
            Game.home_score, Game.away_score, Game.winner_team_id,
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

    for gameWeek, homeId, awayId, homeScore, awayScore, winnerId in rows:
        homeScore = homeScore or 0
        awayScore = awayScore or 0
        # ⚠️ THE STORED WINNER FIRST, AND THE SCORES ONLY AS A FALLBACK. In frames the
        # match is decided by frames won and points only break a level match, so comparing
        # scores here marked the wrong side — a frames win showed as a red 'L' in Last 5
        # while the club's record counted it as a win. The fallback covers rows finished
        # before the column existed and not yet backfilled; for every points-decided format
        # it gives the same answer.
        if winnerId is not None:
            homeMark, awayMark = ('W', 'L') if winnerId == homeId else ('L', 'W')
        elif homeScore > awayScore:
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
