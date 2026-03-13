"""Repository for shop power-up purchases."""

from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import ShopPurchase, UserModifierOverride


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

    def getPurchasesToday(self, userId: int, itemSlug: str) -> int:
        """Count purchases of a specific item made today (for daily limit in production)."""
        today = date.today()
        todayStart = datetime(today.year, today.month, today.day)
        return self.session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.created_at >= todayStart,
        ).scalar() or 0

    def getPurchasesForCycle(self, userId: int, season: int, itemSlug: str, cycleStartWeek: int, cycleEndWeek: int) -> int:
        """Count purchases within a swap cycle (for testing-mode daily limit)."""
        return self.session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.season == season,
            ShopPurchase.week >= cycleStartWeek,
            ShopPurchase.week <= cycleEndWeek,
        ).scalar() or 0

    def getSeasonPurchaseCount(self, userId: int, season: int, itemSlug: str) -> int:
        return self.session.query(func.count(ShopPurchase.id)).filter_by(
            user_id=userId, season=season, item_slug=itemSlug,
        ).scalar() or 0

    def getActiveTempFlex(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "temp_flex",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActiveFortunesFavor(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "fortunes_favor",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActiveTempCardSlot(self, userId: int, season: int, currentWeek: int) -> Optional[ShopPurchase]:
        return self.session.query(ShopPurchase).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.season == season,
            ShopPurchase.item_slug == "temp_card_slot",
            ShopPurchase.expires_at_week >= currentWeek,
        ).first()

    def getActivePowerups(self, userId: int, season: int, currentWeek: int) -> List[ShopPurchase]:
        """Get all active power-ups (either current week or with unexpired duration)."""
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
        todayStart = datetime(today.year, today.month, today.day)
        return session.query(func.count(ShopPurchase.id)).filter(
            ShopPurchase.user_id == userId,
            ShopPurchase.item_slug == itemSlug,
            ShopPurchase.created_at >= todayStart,
        ).scalar() or 0
