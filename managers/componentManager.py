"""The component ledger — grant, count, spend.

⚠️ ONE FAMILY, TWO MEMBERS, AND THEY DIVERGE ON ACQUISITION. Synth Components are
shop-bought (a small daily allowance) plus achievement grants; **Chrome Components are
earned only, never purchased** — a locked owner ruling, and not a flavor difference. The
whole "supply is the master dial" argument for chrome rests on it: an earned-only faucet
makes R0, the one load-bearing number in the contagion design, a schedule we set rather
than a figure emergent from Floobit income x price x spending appetite.

A shared noun makes "unify the acquisition too" sound tidy later. It would quietly undo
the hardest calibration in that plan. Everything here is deliberately acquisition-blind:
`grant` takes a source and does not care where it came from, and nothing in this module
knows what a shop is.

⚠️ A BALANCE IS A COUNT OF UNCONSUMED ROWS, never a stored integer. A stored balance can
disagree with its own history; a count cannot. It also means every component carries its
own provenance, which is what lets the per-season achievement cap be enforced without a
second counter.
"""
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

SYNTH = 'synth'
CHROME = 'chrome'


def balance(session, userId: int, season: int, componentType: str = SYNTH) -> int:
    """How many unspent components of this type the user holds THIS season."""
    from database.models import UserComponent
    return (session.query(UserComponent)
            .filter(UserComponent.user_id == userId,
                    UserComponent.component_type == componentType,
                    UserComponent.season == season,
                    UserComponent.consumed_at.is_(None))
            .count())


def grantedFrom(session, userId: int, season: int, source: str,
                componentType: str = SYNTH) -> int:
    """How many components of this type came from `source` this season — spent or not.

    ⚠️ COUNTS GRANTS, NOT HOLDINGS, and that is what makes the achievement cap real. A cap
    read off the current balance would refill every time the user spent one, so a player
    could take four, build four cards, and take four more.
    """
    from database.models import UserComponent
    return (session.query(UserComponent)
            .filter(UserComponent.user_id == userId,
                    UserComponent.component_type == componentType,
                    UserComponent.season == season,
                    UserComponent.source == source)
            .count())


def grant(session, userId: int, season: int, count: int = 1,
          source: str = 'grant', componentType: str = SYNTH,
          cap: Optional[int] = None) -> int:
    """Add `count` components. Returns how many were actually granted.

    `cap` bounds the TOTAL ever granted from this source this season (see `grantedFrom`).
    Returns fewer than asked — or zero — when the cap bites, rather than raising: a
    capped grant is a normal outcome of an achievement completing, not an error.
    """
    from database.models import UserComponent
    if count <= 0:
        return 0
    if cap is not None:
        room = max(0, int(cap) - grantedFrom(session, userId, season, source, componentType))
        count = min(count, room)
        if count <= 0:
            return 0
    for _ in range(int(count)):
        session.add(UserComponent(
            user_id=userId, component_type=componentType, source=source,
            season=season, granted_at=datetime.utcnow(),
        ))
    session.flush()
    return int(count)


def consume(session, userId: int, season: int, count: int = 1,
            componentType: str = SYNTH, consumedFor: str = None) -> bool:
    """Spend `count` components. True if they were available and marked spent.

    ⚠️ ALL-OR-NOTHING, and it checks before it writes: a partial spend would take
    components for a build that then fails its own validation and hand back nothing.

    ⚠️ OLDEST FIRST. Components are season-scoped and identical in effect, so the order
    is invisible to a user — but spending the oldest keeps the ledger readable and makes
    a capped source's rows retire in the order they were earned.
    """
    from database.models import UserComponent
    if count <= 0:
        return True
    rows = (session.query(UserComponent)
            .filter(UserComponent.user_id == userId,
                    UserComponent.component_type == componentType,
                    UserComponent.season == season,
                    UserComponent.consumed_at.is_(None))
            .order_by(UserComponent.granted_at.asc(), UserComponent.id.asc())
            .limit(int(count)).all())
    if len(rows) < count:
        return False
    now = datetime.utcnow()
    for r in rows:
        r.consumed_at = now
        if consumedFor:
            r.consumed_for = consumedFor[:80]
    session.flush()
    return True
