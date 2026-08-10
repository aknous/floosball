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
    'announcement',
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
    'schedule',
    'cores',
]

# How far back the lead may reach. A headline is a "right now" slot — leading with a
# three-week-old clinch because nothing since carried four numbers reads as a stuck page.
LEAD_MAX_AGE_HOURS = 72

# Items published within this window of each other count as "the same moment" for the
# purpose of choosing a lead, so importance ranks them rather than millisecond arrival.
LEAD_RECENCY_BUCKET_SECONDS = 600
# A record leads on three numbers; everything else carries four.
LEAD_MIN_STATS = 3

# Categories that are context rather than report. They belong in the feed, but a Core
# musing and "week 4 begins" are not headlines, so they never lead even if they somehow
# carried stats.
NEVER_LEAD = {'cores', 'schedule'}

# Categories allowed to take the headline with NO number strip (owner, 2026-08-08). A rule
# changing, or the instability crossing a threshold, is the most important thing that can
# happen in this league, and neither is a thing you put four numbers under.
#
# ⚠️ For criticality a strip would be actively wrong, not merely absent: every public
# surface for the anomaly is deliberately number-free, so that it reads as a mood rather
# than a progress bar. The raw aggregate and threshold live only in the debug endpoint and
# the ephemeral control room.
LEAD_WITHOUT_STATS = {'rules', 'criticality', 'announcement'}

# An announcement is written by a person who chose to write it, so it is RESERVED ahead of
# everything else — a cap that can drop it defeats the point of having posted it. Taken in
# its own pass before meta and league rows, and deliberately uncapped: an admin posting
# nine announcements has made the feed nine announcements, which is their call to make.
ANNOUNCEMENT_CATEGORIES = {'announcement'}

# How many pinned items may be held above the feed at once. A ceiling rather than a
# policy: pinning everything is the same as pinning nothing, and an admin who wants a
# tenth notice up there almost certainly meant to unpin one first.
PINNED_MAX = 5

# The feed is Cores/meta-simulation centric (owner, 2026-08-08), so these categories get a
# bigger share of the visible rows than the league's own results do.
#
# The size is not arbitrary: a Cores exchange is 2-4 turns and each turn is its own row, so
# a cap of three routinely cut a conversation off mid-argument. This is the smallest cap
# that lets a whole exchange land.
META_CATEGORIES = {'cores', 'criticality', 'rules', 'anomaly_transition'}

# How many meta rows to pull from outside the newest-N window. Generous enough that a
# week of awakenings all reach the feed, bounded so a quiet league does not serve a
# month of old Cores chatter.
META_FETCH_MAX = 40

# The opposite end: a routine notice that is worth ONE row and no more. "Week 12 begins,
# 16 games scheduled" is a marker, not a story, and three of them stacked is the same
# filler the big-game items used to be — with those gone, these expanded to fill the gap.
NOTICE_CATEGORIES = {'schedule'}
NOTICE_CAP = 1


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
            # Which Core spoke, so the feed can show their icon rather than a generic
            # dot. The display name is already folded into `text`; this is the key.
            'core': r.core,
            'coreDisplayName': r.core_display_name,
            # Threading. A Cores exchange is persisted one row per turn; these are what
            # let the reader put the conversation back together.
            'exchangeId': r.exchange_id,
            'turnIndex': r.turn_index,
            'rawText': r.text or '',
            'text': text,
            'pinned': bool(getattr(r, 'pinned', False)),
            # Prose beneath the headline. Hand-written items only — NULL everywhere else,
            # and the reader renders nothing rather than an empty paragraph.
            'body': getattr(r, 'body', None) or None,
            'week': r.week,
            'season': r.season,
            'teamId': r.team_id,
            'playerId': r.player_id,
            'stats': stats,
            'at': r.created_at.isoformat() + 'Z' if r.created_at else None,
        })
    return items


def _groupExchanges(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fold a multi-turn Cores exchange into ONE entry, its turns in spoken order.

    ⚠️ Without this the feed reads a conversation BACKWARDS. Rows come newest-first, and
    each turn of an exchange is its own row published milliseconds apart — so the reply
    lands above the line it is replying to, and a four-turn argument runs in reverse.

    The grouped entry sits where its NEWEST turn sat, so the conversation still lands in
    the right place on the timeline, and it counts as a SINGLE row against the caps
    downstream — otherwise one exchange eats the whole meta allowance.

    An exchange split across the fetch window keeps whatever turns it has; sorting by
    `turnIndex` means a partial conversation still reads forwards.
    """
    grouped: List[Dict[str, Any]] = []
    byExchange: Dict[str, Dict[str, Any]] = {}
    for item in items:
        exchangeId = item.get('exchangeId')
        if not exchangeId:
            grouped.append(item)
            continue
        entry = byExchange.get(exchangeId)
        if entry is None:
            entry = dict(item)
            entry['_turnRows'] = [item]
            byExchange[exchangeId] = entry
            grouped.append(entry)
        else:
            entry['_turnRows'].append(item)

    for entry in grouped:
        rows = entry.pop('_turnRows', None)
        if not rows:
            continue
        rows.sort(key=lambda t: t.get('turnIndex') if t.get('turnIndex') is not None else 0)
        entry['turns'] = [{
            'core': t.get('core'),
            'coreDisplayName': t.get('coreDisplayName'),
            'text': t.get('rawText') or t.get('text') or '',
        } for t in rows]
        # `text` stays populated with the opening line so anything reading the flat field
        # still gets something sensible rather than an empty row.
        entry['text'] = rows[0].get('text') or entry.get('text') or ''
        entry['core'] = rows[0].get('core')
        entry['coreDisplayName'] = rows[0].get('coreDisplayName')
    return grouped


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

    # ⚠️ PINNED rows are fetched SEPARATELY, outside that window. That is the entire
    # point of pinning: the window above is the newest ~40 items, and a busy slate
    # publishes enough clinches, records and Cores lines to push a notice out of it
    # within a day. Merged by id so a pinned row that IS still in the window is not
    # duplicated.
    try:
        pinnedRows = (
            session.query(LeagueNewsItem)
            .filter(LeagueNewsItem.pinned.is_(True))
            .order_by(LeagueNewsItem.created_at.desc(), LeagueNewsItem.id.desc())
            .limit(PINNED_MAX)
            .all()
        )
        seen = {r.id for r in rows}
        rows = [r for r in pinnedRows if r.id not in seen] + rows
    except Exception as e:
        # A DB that predates the column must still serve the feed.
        logger.debug(f"Pinned news lookup skipped: {e}")

    # ⚠️ META rows are fetched OUTSIDE the window too, for the same reason pinned ones
    # are. The reservation further down cannot save a category that never reached it:
    # the window above is a flat newest-N, so a category that publishes in bulk starves
    # the others BEFORE any cap or reserve runs.
    #
    # Measured on the season-1 production database: `record` was 93 of 131 rows (71%),
    # the newest 40 came back 34 record and 6 cores, and all NINE anomaly-transition
    # rows sat outside at ranks 43, 44, 48, 81, 82, 86, 122, 123, 124. Ten players had
    # awakened and not one awakening was reachable in the feed.
    #
    # This is the same failure `BIG_GAME_NEWS_ENABLED` was switched off for — that
    # category was 48% of all rows and the visible feed became entirely box score.
    # Records took its place. Turning a category off is a blunt fix; guaranteeing the
    # quiet ones a route into the window is the general one.
    try:
        metaRows = (
            session.query(LeagueNewsItem)
            .filter(LeagueNewsItem.category.in_(tuple(META_CATEGORIES)))
            .order_by(LeagueNewsItem.created_at.desc(), LeagueNewsItem.id.desc())
            .limit(META_FETCH_MAX)
            .all()
        )
        seen = {r.id for r in rows}
        # Appended, not prepended: they take their real place in publication order once
        # the rows are sorted. Reaching the window is the point, not jumping the queue.
        rows = rows + [r for r in metaRows if r.id not in seen]
    except Exception as e:
        logger.debug(f"Meta news lookup skipped: {e}")

    items = _groupExchanges(_rowsToItems(rows))
    if not items:
        return {'lead': None, 'items': []}
    _fillTeamFromPlayer(session, items)

    priority = {c: i for i, c in enumerate(CATEGORY_PRIORITY)}
    cutoff = datetime.utcnow() - timedelta(hours=LEAD_MAX_AGE_HOURS)

    def leadable(item) -> bool:
        # Three cells, not four. A record's whole story is old mark / new mark / gap, and
        # the lead strip flexes to whatever it is handed. Requiring exactly four locked
        # every one of them out of the headline.
        # ⚠️ PINNED is checked FIRST, ahead of NEVER_LEAD and the age cutoff. Those
        # rules exist to stop the sim promoting the wrong thing automatically; an admin
        # pinning a row is a person saying "this, at the top", and a Cores line normally
        # being voice-not-report is not a reason to overrule them. Nothing pins itself.
        if item.get('pinned'):
            return True
        if item['rawCategory'] in NEVER_LEAD:
            return False
        if (item['rawCategory'] not in LEAD_WITHOUT_STATS
                and len(item['stats']) < LEAD_MIN_STATS):
            return False
        row = next((r for r in rows if r.id == item['id']), None)
        return row is None or row.created_at is None or row.created_at >= cutoff

    # ⚠️ The lead is the biggest story of the most recent MOMENT.
    #
    # Two things decide it, in order: when it happened, then how big it was. Category is
    # only the last resort, and that ordering is load-bearing — MEASURED over 546 real
    # feed rows, ranking by a static category ladder inside the moment gave `upset` 87%
    # of all reader views while it was 24% of the eligible items, and buried `big_game`
    # at 8% while it was 76% of them. A whole slate resolves in one instant, so a fixed
    # ladder is not a tiebreak at all: it is the sort, and it picks the same winner every
    # week.
    #
    # `leadWeight` is what replaces it — each publisher records how far past its OWN
    # threshold the event landed, which is what makes the number comparable between a
    # receiving day and an Elo gap. See `LeagueNewsItem.lead_weight`.
    #
    # Recency is BUCKETED before weight is applied, because raw timestamps are
    # microsecond-precise and a straight sort would hand the page to whichever game
    # happened to finish a few milliseconds later. The bucket is wide enough to hold a
    # whole slate (games in a round finish minutes apart in real time, all at once in the
    # fast modes) so the biggest story of the round wins rather than the last one filed.
    weightById = {r.id: getattr(r, 'lead_weight', None) for r in rows}
    createdById = {r.id: r.created_at for r in rows}

    def leadKey(item):
        at = createdById.get(item['id'])
        bucket = int(at.timestamp() // LEAD_RECENCY_BUCKET_SECONDS) if at else 0
        # Rows written before lead_weight existed have none. Treat them as exactly at
        # their threshold rather than as zero, so an old item still ranks sanely against
        # a new one instead of being permanently unleadable.
        weight = weightById.get(item['id'])
        weight = 1.0 if weight is None else weight
        # Pinned first, ahead of recency — that is what "pinned" means. Among several
        # pinned items the newest leads, which the bucket below already handles.
        return (0 if item.get('pinned') else 1,
                -bucket, -weight, priority.get(item['rawCategory'], len(CATEGORY_PRIORITY)))

    candidates = [i for i in items if leadable(i)]
    lead = min(candidates, key=leadKey, default=None)

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
    # One Cores exchange is now ONE row but several lines tall, so the allowance is
    # smaller than it was when each turn cost a row of its own.
    metaCap = max(2, room // 4)

    # ⚠️ Meta rows are RESERVED, not merely capped. A cap is only a ceiling, and the feed
    # is read newest-first — so a burst of same-moment events (a playoff week fires a
    # dozen clinches and eliminations at once) fills the room before the Cores are
    # reached, and the meta share collapses to whatever the burst left over. Observed
    # exactly that: two Cores rows out of nine on a clinch week.
    #
    # Two passes, then back into publication order for display. Taking meta first is what
    # makes the share a floor; re-sorting afterwards is what keeps the feed reading as a
    # timeline rather than as two stacked blocks.
    def take(pool, allowance):
        picked: List[Dict[str, Any]] = []
        perCategory: Dict[str, int] = {}
        for item in pool:
            if len(picked) >= allowance:
                break
            if item is lead:
                continue
            if item.get('pinned') or item['rawCategory'] in ANNOUNCEMENT_CATEGORIES:
                allowed = allowance
            elif item['rawCategory'] in META_CATEGORIES:
                allowed = metaCap
            elif item['rawCategory'] in NOTICE_CATEGORIES:
                allowed = NOTICE_CAP
            else:
                allowed = cap
            count = perCategory.get(item['rawCategory'], 0)
            if count >= allowed:
                continue
            perCategory[item['rawCategory']] = count + 1
            picked.append(item)
        return picked

    order = {id(item): i for i, item in enumerate(items)}
    # Announcements first and uncapped — see ANNOUNCEMENT_CATEGORIES.
    # Pinned rows and announcements share the reserved pass. A pinned CORES post is
    # still a hand-placed item, so capping it under metaCap alongside the sim's own
    # chatter would quietly undo the pin.
    reserved = lambda i: i.get('pinned') or i['rawCategory'] in ANNOUNCEMENT_CATEGORIES
    announcementRows = take(
        sorted([i for i in items if reserved(i)], key=lambda i: 0 if i.get('pinned') else 1),
        room)
    remaining = room - len(announcementRows)
    metaRows = take([i for i in items
                     if i['rawCategory'] in META_CATEGORIES and not reserved(i)],
                    min(metaCap, remaining))
    leagueRows = take([i for i in items
                       if i['rawCategory'] not in META_CATEGORIES and not reserved(i)],
                      remaining - len(metaRows))
    rowItems = sorted(announcementRows + metaRows + leagueRows, key=lambda i: order[id(i)])

    return {'lead': lead, 'items': rowItems}
