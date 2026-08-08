"""The front page's league-news feed: read the persisted stream, pick a lead.

Every item in the feed was published AT THE MOMENT IT HAPPENED by whichever system it
happened in (see `league_news.publish`). This module does not generate news — it reads,
orders and picks.

That is a deliberate change from the first version, which built the feed from CURRENT
state on every request. Generating meant a clinch stopped being news the moment the
standings moved past it, nothing from week 9 was ever visible in week 10, and the whole
feed reset at the week rollover. Stories should fall off the bottom because the reader
asked for a fixed number of them, not because the sim stopped considering them true.

The LEAD is the most interesting recent item that carries a four-number strip. Carrying
`stats` is what makes an item eligible to lead; everything else is a row.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger('floosball.frontPage')

# Ordered by how much a fan cares. Decides which of the eligible items leads, and breaks
# ties between items published in the same tick.
CATEGORY_PRIORITY = [
    'criticality',
    'record',
    'clinched',
    'upset',
    'big_game',
    'rules',
    'anomaly_transition',
    'streak',
    'eliminated',
    'signing',
    'milestone',
    'injury',
    'cores',
]

# How far back the lead may reach. A headline is a "right now" slot — leading with a
# three-week-old clinch because nothing since carried four numbers reads as a stuck page.
LEAD_MAX_AGE_HOURS = 72

# Categories that are voice rather than report. They belong in the feed, but a Core musing
# is not a headline, so they never lead even if they somehow carried stats.
NEVER_LEAD = {'cores'}


def _rowsToItems(rows) -> List[Dict[str, Any]]:
    items = []
    for r in rows:
        stats: List[Dict[str, Any]] = []
        if r.stats_json:
            try:
                stats = json.loads(r.stats_json) or []
            except (ValueError, TypeError):
                stats = []
        text = r.text or ''
        # A Core speaking is attributed inline, the way the highlight feed does it.
        if r.category == 'cores' and r.core_display_name:
            text = f'{r.core_display_name}: {text}'
        items.append({
            'id': r.id,
            'category': (r.category or '').upper().replace('_', ' '),
            'rawCategory': r.category,
            'text': text,
            'week': r.week,
            'season': r.season,
            'teamId': r.team_id,
            'playerId': r.player_id,
            'stats': stats,
            'at': r.created_at.isoformat() + 'Z' if r.created_at else None,
        })
    return items


def _fillTeamFromPlayer(session, items: List[Dict[str, Any]]) -> None:
    """Give player-attributed items their player's team, so the feed can show a crest.

    Records and anomaly transitions know who the player is but not who they play for —
    the publisher is inside the player's own system and has no team to hand. Rather than
    teaching each of those publishers to resolve a team, the gap is closed once here, in
    one bulk query, which also covers any future player-attributed category for free.
    """
    needy = [i for i in items if i.get('playerId') and not i.get('teamId')]
    if not needy:
        return
    try:
        from database.models import Player
        rows = (
            session.query(Player.id, Player.team_id)
            .filter(Player.id.in_({i['playerId'] for i in needy}))
            .all()
        )
        teamByPlayer = {pid: tid for pid, tid in rows}
        for item in needy:
            item['teamId'] = teamByPlayer.get(item['playerId'])
    except Exception as e:
        # A crest is decoration; losing it must not cost the feed.
        logger.debug(f"Could not resolve teams for news items: {e}")


def buildLeagueNews(app, session, limit: int = 8) -> Dict[str, Any]:
    """One lead item plus the rows behind it, newest first.

    Not filtered by week OR by season. The feed is cumulative and fixed-length: it carries
    whatever the most recent `limit` stories are, and a season boundary is a natural
    changeover rather than a reset (the offseason publishes plenty of its own).
    """
    from database.models import LeagueNewsItem
    from datetime import datetime, timedelta

    # Over-fetch so the lead can be chosen from a real window rather than from whatever
    # happened to land in the last `limit` rows.
    rows = (
        session.query(LeagueNewsItem)
        .order_by(LeagueNewsItem.created_at.desc(), LeagueNewsItem.id.desc())
        .limit(max(limit * 4, 40))
        .all()
    )
    items = _rowsToItems(rows)
    if not items:
        return {'lead': None, 'items': []}
    _fillTeamFromPlayer(session, items)

    priority = {c: i for i, c in enumerate(CATEGORY_PRIORITY)}
    cutoff = datetime.utcnow() - timedelta(hours=LEAD_MAX_AGE_HOURS)

    def leadable(item) -> bool:
        if len(item['stats']) != 4 or item['rawCategory'] in NEVER_LEAD:
            return False
        row = next((r for r in rows if r.id == item['id']), None)
        return row is None or row.created_at is None or row.created_at >= cutoff

    candidates = [i for i in items if leadable(i)]
    lead = min(
        candidates,
        key=lambda i: priority.get(i['rawCategory'], len(CATEGORY_PRIORITY)),
        default=None,
    )

    # Rows stay in publication order — the feed reads as a timeline, and reordering it by
    # category would make a quiet week look reshuffled every refresh.
    #
    # But no category may take more than its share. A whole slate of games resolves at
    # once, so without this the newest N rows are simply the last N things that happened,
    # which in practice means the feed is entirely big games and the clinch that landed
    # thirty seconds earlier is already gone. The cap keeps a week's worth of different
    # kinds of news visible.
    # ⚠️ The cap is HARD — there is deliberately no top-up from the overflow. A first pass
    # refilled the remaining slots when the cap left the feed short, which quietly undid
    # the whole thing: with only two categories in play it went straight back to six big
    # games and three upsets. A six-row feed that shows three kinds of news beats a
    # nine-row feed that shows one.
    room = limit - 1 if lead else limit
    cap = max(2, room // 3)
    perCategory: Dict[str, int] = {}
    rowItems: List[Dict[str, Any]] = []
    for item in items:
        if item is lead or len(rowItems) >= room:
            continue
        count = perCategory.get(item['rawCategory'], 0)
        if count >= cap:
            continue
        perCategory[item['rawCategory']] = count + 1
        rowItems.append(item)

    return {'lead': lead, 'items': rowItems}
