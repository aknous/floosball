"""Repository for shop power-up purchases."""

from datetime import datetime, date, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import ShopPurchase, UserModifierOverride
from constants import CROSS_DAY_ROLLOVER_LEAD_MINUTES


def _rolloverMomentUtc(gameDate: date) -> datetime:
    """The instant the shop rolls over INTO the game day `gameDate`.

    The same expression the sim's own week rollover uses: the day's first kickoff is 12:00
    ET, and the rollover leads it by `CROSS_DAY_ROLLOVER_LEAD_MINUTES`. At the shipped lead
    of 1020 (17h) that lands at 19:00 ET the evening BEFORE, so the moment returned here
    sits on the previous calendar day. ET is converted by hand, exactly as
    `seasonManager.getWeekStartTime` and `cardManager._shopCycleStartDate` do.
    """
    from managers.timingManager import _isEdtDate
    utcOffset = 4 if _isEdtDate(gameDate) else 5
    kickoffUtc = datetime(gameDate.year, gameDate.month, gameDate.day, 12 + utcOffset)
    return kickoffUtc - timedelta(minutes=CROSS_DAY_ROLLOVER_LEAD_MINUTES)


def _dailyResetBoundary() -> datetime:
    """The start of the current SHOP DAY — when daily allowances (rerolls, per-day buy
    limits) reset.

    ⚠️ THIS USED TO BE A FIXED UTC HOUR (`DAILY_RESET_HOUR_UTC`) AND DRIFTED OFF THE PACK
    ROTATION. The rotation follows the week rollover, which is ET-anchored at
    `12:00 ET - CROSS_DAY_ROLLOVER_LEAD_MINUTES` = 19:00 ET; a fixed 00:00 UTC is 20:00 EDT.
    So through the summer there was a ONE-HOUR WINDOW, 19:00-20:00 ET every game day, in
    which the new day's packs were already on sale and the reroll costs had not reset.
    Reported exactly that way: "day 2 packs are purchaseable, the week rolled over, but the
    card and pack reroll costs haven't reset yet".

    ⚠️ IT WAS INVISIBLE IN WINTER, which is why a fixed hour looked correct when it was
    chosen. Under EST the rollover is 12:00 + 5 - 17h = 00:00 UTC — exactly midnight, the
    old constant's value — so the two agreed perfectly and diverged by an hour only once
    the clocks changed. A fixed UTC hour cannot track an ET-anchored schedule; that was
    already written down as the reason the hour needed slack, and the conclusion should
    have been to stop using one.

    Deriving both boundaries from the same expression is what actually keeps them in step:
    move the lead and the shop's two halves still refresh together.
    """
    now = datetime.utcnow()
    # A rollover moment for game day D lands about a day before D, so the candidate game
    # days worth testing straddle today. Take the most recent that has already passed.
    candidates = [_rolloverMomentUtc(now.date() + timedelta(days=offset))
                  for offset in (2, 1, 0, -1)]
    passed = [moment for moment in candidates if moment <= now]
    # `passed` cannot be empty — the offset -1 candidate is over a day behind `now` — but
    # falling back to a day ago is cheaper than an IndexError on a shop request.
    return max(passed) if passed else now - timedelta(days=1)


class ShopPurchaseRepository:
    """Repository for shop power-up purchase operations."""

    def __init__(self, session: Session):
        self.session = session

    def getPurchasesForWeek(self, userId: int, season: int, week: int, itemSlug: Optional[str] = None) -> List[ShopPurchase]:
        query = self.session.query(ShopPurchase).filter_by(
            user_id=userId, season=season, week=week,
        )
        if itemSlug:
            query = query.filter_by(item_slug=itemSlug)
        return query.all()

    def getPurchasesToday(self, userId: int, itemSlug: str,
                          includeFree: bool = False) -> int:
        """Count purchases since the last daily reset boundary.

        By default only PAID ones. Free grants (achievement-reward claims that insert
        ShopPurchase with price_paid=0) are excluded so they don't consume the user's
        daily buy limit — a user who claims an extra_swap reward should still be able
        to buy one in the shop that day.

        ⚠️ `includeFree=True` IS REQUIRED BY ANY LADDER WHOSE FIRST STEP IS FREE, and the
        shop reroll became one. Its price is `f(count of rerolls used today)`, so a free
        reroll that is not counted leaves the count at 0 forever: every subsequent reroll
        re-prices as the first, charges nothing and never escalates. Shipped and reported
        from production. The default stays False because for a POWERUP the two meanings
        genuinely differ — a free one should not spend your allowance — but for a reroll
        the free one IS the first use of the allowance.
        """
        q = self.session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.created_at >= _dailyResetBoundary(),
        )
        if not includeFree:
            q = q.filter(ShopPurchase.price_paid > 0)
        return q.scalar() or 0

    def getPurchasesForCycle(self, userId: int, season: int, itemSlug: str,
                             cycleStartWeek: int, cycleEndWeek: int,
                             includeFree: bool = False) -> int:
        """Count purchases within a swap cycle. Free grants excluded by default
        (see getPurchasesToday, including why a free-first ladder must pass
        includeFree=True)."""
        q = self.session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.season == season,
            ShopPurchase.week >= cycleStartWeek,
            ShopPurchase.week <= cycleEndWeek,
        )
        if not includeFree:
            q = q.filter(ShopPurchase.price_paid > 0)
        return q.scalar() or 0

    def getSeasonPurchaseCount(self, userId: int, season: int, itemSlug: str) -> int:
        """Count PAID purchases this season. Used for per-season buy
        limits; free grants from rewards don't burn the budget."""
        return self.session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.price_paid > 0,
        ).scalar() or 0

    def getActiveTempFlex(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        # Also returns rows purchased this week during active games (`week` set
        # to currentWeek + 1 as the effective start). Visible immediately so
        # users see the slot after purchase, even though the duration doesn't
        # start counting until next week.
        if currentWeek < 1:
            return None  # offseason — see _OFFSEASON note below
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "temp_flex",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActiveFortunesFavor(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        if currentWeek < 1:
            return None
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "fortunes_favor",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActiveTempCardSlot(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        if currentWeek < 1:
            return None
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "temp_card_slot",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActiveIncomeBoost(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        if currentWeek < 1:
            return None
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "income_boost",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActivePowerups(self, userId: int, season: int, currentWeek: int) -> List[ShopPurchase]:
        """Get all active power-ups (either current week or with unexpired duration).

        _OFFSEASON: between the Floos Bowl and the next season, the league sets the current week to 0.
        With `expires_at_week >= 0` always true, every still-on-the-books powerup (e.g. an Endowment
        bought late) would read as active through the whole offseason and keep boosting offseason
        income. No powerup is active once the season's games are over, so currentWeek < 1 -> nothing
        active. (Cross-season is already safe: next season's rows carry a new `season`.)"""
        if currentWeek < 1:
            return []
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
        ).filter(
            # Either instant (current week) or has active expiry
            (ShopPurchase.week == currentWeek) | (ShopPurchase.expires_at_week >= currentWeek)
        ).all()

    def createPurchase(self, userId: int, itemSlug: str, season: int, week: int, pricePaid: int,
                       expiresAtWeek: Optional[int] = None) -> ShopPurchase:
        purchase = ShopPurchase(
            user_id=userId,
            item_slug=itemSlug,
            season=season,
            week=week,
            price_paid=pricePaid,
            expires_at_week=expiresAtWeek,
        )
        self.session.add(purchase)
        self.session.flush()
        return purchase


class ModifierOverrideRepository:
    """Repository for user modifier override operations."""

    def __init__(self, session: Session):
        self.session = session

    def getOverride(self, userId: int, season: int, week: int) -> Optional[UserModifierOverride]:
        return self.session.query(UserModifierOverride).filter_by(
            user_id=userId, season=season, week=week,
        ).first()

    def createOverride(self, userId: int, season: int, week: int, modifier: str = "steady") -> UserModifierOverride:
        override = UserModifierOverride(
            user_id=userId,
            season=season,
            week=week,
            override_modifier=modifier,
        )
        self.session.add(override)
        self.session.flush()
        return override

    def getRerollCountForCycle(self, session: Session, userId: int, itemSlug: str,
                                generatedAt: Optional[datetime], today: date) -> int:
        """Check if user already rerolled in current refresh cycle."""
        if generatedAt is None:
            return 0
        boundary = _dailyResetBoundary()
        return session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.created_at >= boundary,
        ).scalar() or 0
