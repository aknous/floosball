"""Front-page league news — templated clauses over fields the sim already stores.

This is generated rather than logged, and that is the design constraint, not a shortcut.
An earlier draft of the front page gave the lead item an authored headline and two
sentences of editorial prose. It was rejected because nothing in the system publishes copy
at that level and an automated version would never reach it. So the rule here is:

  * every headline is a TEMPLATE — one clause, one verb, no analysis
  * the lead item's supporting content is FOUR NUMBERS, not prose
  * no line may need a fact the sim does not already store as a field

Each generator returns items of one category and is independent of the others, so adding a
category later is a new function rather than a rework. A category with no qualifying items
simply contributes nothing; the feed does not pad.

The alternative — persisting every announcement at its call site — was considered and
rejected for now: `leagueHighlights.insert` has 89 call sites and the overwhelming
majority are play highlights, not news.
"""

from typing import Any, Dict, List, Optional

# Ordered by how much a fan cares, which is also lead-item priority. The colours live in
# the frontend; this side only names the category.
CATEGORY_PRIORITY = [
    'CLINCHED',
    'RECORD',
    'MILESTONE',
    'ERRATIC',
    'STREAK',
    'RULE CHANGE',
    'SIGNING',
    'INJURY',
]

STREAK_MIN = 4

# Most rows any one category may contribute before the feed moves on.
CATEGORY_ROW_CAP = 3


def _item(category: str, text: str, *, week: int, teamId=None, playerId=None,
          stats: Optional[List[Dict[str, Any]]] = None, at: Optional[str] = None,
          league: Optional[str] = None) -> Dict[str, Any]:
    return {
        'category': category,
        'text': text,
        'week': week,
        'teamId': teamId,
        'playerId': playerId,
        # Only the lead item renders these, but any item may carry them — which of them
        # leads is decided at serve time, not at generation time.
        'stats': stats or [],
        'at': at,
        'league': league,
    }


def _clinchedItems(leagues, week: int) -> List[Dict[str, Any]]:
    """Playoff berths, top seeds and division titles.

    The four supporting numbers are record, streak, seed and point differential — the
    same four for every clinch, so the strip never has to be reasoned about per item.
    """
    items = []
    for league in leagues:
        for team in league.teamList:
            if not getattr(team, 'clinchedPlayoffs', False):
                continue
            stats = getattr(team, 'seasonTeamStats', {}) or {}
            wins = stats.get('wins', 0) or 0
            losses = stats.get('losses', 0) or 0
            streak = stats.get('streak', 0) or 0
            diff = round(stats.get('scoreDiff', 0) or 0)
            verb = ('clinch the top seed' if getattr(team, 'clinchedTopSeed', False)
                    else 'clinch a playoff berth')
            items.append(_item(
                'CLINCHED',
                f'{team.city} {team.name} {verb}',
                week=week,
                teamId=team.id,
                league=league.name,
                stats=[
                    {'label': 'RECORD', 'value': f'{wins}-{losses}'},
                    {'label': 'STREAK', 'value': (f'W{streak}' if streak > 0
                                                  else f'L{abs(streak)}' if streak < 0 else '—'),
                     'positive': streak > 0},
                    {'label': f'{league.name.split()[0].upper()} SEED',
                     'value': _ordinal(_seedOf(team, league))},
                    {'label': 'POINT DIFF', 'value': f'+{diff}' if diff > 0 else str(diff),
                     'positive': diff > 0},
                ],
            ))
    return items


def _seedOf(team, league) -> Optional[int]:
    try:
        from standings_view import seedLeague
        seeded = seedLeague(list(league.teamList), [])
        seed = seeded['seeds'].get(team.id)
        return seed[0] if seed else None
    except Exception:
        return None


def _ordinal(n: Optional[int]) -> str:
    if not n:
        return '—'
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def _streakItems(leagues, week: int) -> List[Dict[str, Any]]:
    """Runs of four or more, either direction. Below four is not news.

    Streaks carry the same four-number strip a clinch does, which matters more than it
    looks: for most of the season NOTHING has clinched, and a news module whose lead item
    only ever exists in the last few weeks spends the rest of the year as a list of rows
    with a hole where the headline goes. The longest streak in the league is a real story
    in week 9 and it is fully derivable, so it can lead.
    """
    items = []
    for league in leagues:
        for team in league.teamList:
            stats = getattr(team, 'seasonTeamStats', {}) or {}
            streak = stats.get('streak', 0) or 0
            if abs(streak) < STREAK_MIN:
                continue
            wins = stats.get('wins', 0) or 0
            losses = stats.get('losses', 0) or 0
            diff = round(stats.get('scoreDiff', 0) or 0)
            if streak > 0:
                text = f'{team.city} {team.name} have taken {streak} straight'
            else:
                text = f'{team.city} {team.name} have lost {abs(streak)} in a row'
            items.append(_item(
                'STREAK', text, week=week, teamId=team.id, league=league.name,
                stats=[
                    {'label': 'RECORD', 'value': f'{wins}-{losses}'},
                    {'label': 'RUN', 'value': (f'W{streak}' if streak > 0 else f'L{abs(streak)}'),
                     'positive': streak > 0},
                    {'label': f'{league.name.split()[0].upper()} SEED',
                     'value': _ordinal(_seedOf(team, league))},
                    {'label': 'POINT DIFF', 'value': f'+{diff}' if diff > 0 else str(diff),
                     'positive': diff > 0},
                ],
            ))
    # Winning runs first, longest first inside each direction. A nine-game LOSING streak is
    # the longest run in the league most weeks, and leading the front page with it is the
    # wrong emphasis — it also produces a stat strip of a losing record, no seed and a
    # negative differential, which is four numbers that say nothing.
    items.sort(key=lambda i: (not _runIsWinning(i['stats']), -_runLength(i['stats'])))
    return items


def _run(stats: List[Dict[str, Any]]) -> str:
    return next((str(s['value']) for s in stats if s['label'] == 'RUN'), '')


def _runIsWinning(stats: List[Dict[str, Any]]) -> bool:
    return _run(stats).startswith('W')


def _runLength(stats: List[Dict[str, Any]]) -> int:
    run = _run(stats)
    try:
        return int(run[1:])
    except (ValueError, IndexError):
        return 0


def _anomalyItems(session, season: int, week: int, limit: int) -> List[Dict[str, Any]]:
    """Players who crossed an anomaly threshold. Already persisted, already one clause."""
    from database.models import LeagueNewsItem
    rows = (
        session.query(LeagueNewsItem)
        .filter(LeagueNewsItem.season == season,
                LeagueNewsItem.category == 'anomaly_transition')
        .order_by(LeagueNewsItem.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        _item(
            'ERRATIC',
            r.text,
            week=r.week,
            playerId=r.player_id,
            at=r.created_at.isoformat() + 'Z' if r.created_at else None,
        )
        for r in rows
    ]


def _coresItems(session, season: int, limit: int) -> List[Dict[str, Any]]:
    """Cores dialogue. Its own category so the feed can colour it apart from league news."""
    from database.models import LeagueNewsItem
    rows = (
        session.query(LeagueNewsItem)
        .filter(LeagueNewsItem.season == season, LeagueNewsItem.category == 'cores')
        .order_by(LeagueNewsItem.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        _item(
            'CORES',
            f'{r.core_display_name}: {r.text}' if r.core_display_name else r.text,
            week=r.week,
            at=r.created_at.isoformat() + 'Z' if r.created_at else None,
        )
        for r in rows
    ]


def _recordItems(session, season: int, week: int, limit: int) -> List[Dict[str, Any]]:
    """Records set THIS season. A record from a prior season is history, not news."""
    from database.models import Record, Player
    rows = (
        session.query(Record)
        .filter(Record.season == season, Record.player_id.isnot(None))
        .order_by(Record.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return []
    names = dict(
        session.query(Player.id, Player.name)
        .filter(Player.id.in_([r.player_id for r in rows]))
        .all()
    )
    items = []
    for r in rows:
        name = names.get(r.player_id)
        if not name:
            continue
        value = int(r.value) if float(r.value).is_integer() else round(r.value, 1)
        scope = 'season' if r.scope == 'season' else 'all-time' if r.scope == 'career' else r.scope
        items.append(_item(
            'RECORD',
            f'{name} holds the {scope} {r.stat_name} record at {value}',
            week=week,
            playerId=r.player_id,
        ))
    return items


def _signingItems(session, season: int, week: int, limit: int) -> List[Dict[str, Any]]:
    """Roster movement from the durable recap log. One templated clause per event type."""
    from database.models import SeasonRecapEvent
    templates = {
        'fa_pick': '{team} sign {player}',
        'rookie_pick': '{team} draft {player}',
        'resign': '{team} re-sign {player}',
        'cut': '{team} release {player}',
        'promotion': '{team} promote {player}',
        'retirement': '{player} retires',
        'coach_hire': '{team} hire {player} as coach',
        'coach_fire': '{team} part ways with {player}',
    }
    rows = (
        session.query(SeasonRecapEvent)
        .filter(SeasonRecapEvent.season == season,
                SeasonRecapEvent.event_type.in_(list(templates)))
        .order_by(SeasonRecapEvent.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for r in rows:
        template = templates.get(r.event_type)
        if not template or not r.player_name:
            continue
        text = template.format(team=r.team_name or 'A club', player=r.player_name)
        items.append(_item('SIGNING', text, week=week, teamId=r.team_id, playerId=r.player_id))
    return items


def buildLeagueNews(app, session, limit: int = 8) -> Dict[str, Any]:
    """The front page's news module: one lead item plus the rows behind it.

    The LEAD is whichever item has a full four-number strip and the highest-priority
    category — a lead with nothing behind it would be a headline with an empty stat strip,
    which is exactly the shape the design rejected. When nothing qualifies there is no
    lead and the module renders as rows only.
    """
    seasonMgr = getattr(app, 'seasonManager', None)
    currentSeason = getattr(seasonMgr, 'currentSeason', None) if seasonMgr else None
    season = getattr(currentSeason, 'seasonNumber', 0) or 0
    week = getattr(currentSeason, 'currentWeek', 0) or 0
    leagues = getattr(getattr(app, 'leagueManager', None), 'leagues', []) or []

    items: List[Dict[str, Any]] = []
    items += _clinchedItems(leagues, week)
    items += _streakItems(leagues, week)
    for generator in (
        lambda: _recordItems(session, season, week, limit),
        lambda: _anomalyItems(session, season, week, limit),
        lambda: _signingItems(session, season, week, limit),
        lambda: _coresItems(session, season, limit),
    ):
        try:
            items += generator()
        except Exception:
            # One category failing (a missing table on an older DB, say) must not take the
            # whole feed down with it.
            continue

    priority = {c: i for i, c in enumerate(CATEGORY_PRIORITY)}
    items.sort(key=lambda i: (priority.get(i['category'], len(CATEGORY_PRIORITY)),
                              -(i['week'] or 0)))

    lead = next((i for i in items if len(i['stats']) == 4), None)

    # Cap per category so one prolific generator cannot fill the feed. Without this a
    # mid-season week — when nothing has clinched, no records have fallen and there have
    # been no signings — comes back as eight consecutive STREAK rows, which reads as a
    # broken feed rather than a quiet week.
    perCategory: Dict[str, int] = {}
    rows: List[Dict[str, Any]] = []
    for item in items:
        if item is lead:
            continue
        count = perCategory.get(item['category'], 0)
        if count >= CATEGORY_ROW_CAP:
            continue
        perCategory[item['category']] = count + 1
        rows.append(item)

    # No topping back up past the cap. Early in a season the sim genuinely has less news —
    # nothing has clinched, no records have fallen, no one has signed anywhere — and a
    # short, varied feed is a truer report than eight rows padded out with more streaks.
    room = limit - 1 if lead else limit
    return {'lead': lead, 'items': rows[:room]}
