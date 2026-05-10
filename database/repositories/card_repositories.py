"""Repository classes for trading card system database access."""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from database.models import (
    CardTemplate,
    UserCard,
    EquippedCard,
    UserCurrency,
    CurrencyTransaction,
    PackType,
    PackOpening,
)


# Transaction types that fire a per-user `floobits_received` toast event.
# Add types here when introducing a new passive earning source.
_PASSIVE_GRANT_TYPES = frozenset({
    'weekly_fp_bonus',
    'leaderboard_season',
    'leaderboard_weekly',
    'pickem_correct',
    'pickem_leaderboard_season',
    'pickem_leaderboard_weekly',
    'card_effect',
    'admin_grant',
})


class CardTemplateRepository:
    """Repository for card template operations."""

    def __init__(self, session: Session):
        self.session = session

    def getById(self, templateId: int) -> Optional[CardTemplate]:
        return self.session.query(CardTemplate).filter_by(id=templateId).first()

    def getBySeason(self, season: int, includeUpgraded: bool = False) -> List[CardTemplate]:
        query = self.session.query(CardTemplate).filter_by(season_created=season)
        if not includeUpgraded:
            query = query.filter(CardTemplate.is_upgraded == False)
        return query.all()

    def getBySeasonAndEdition(self, season: int, edition: str, includeUpgraded: bool = False) -> List[CardTemplate]:
        query = (
            self.session.query(CardTemplate)
            .filter_by(season_created=season, edition=edition)
        )
        if not includeUpgraded:
            query = query.filter(CardTemplate.is_upgraded == False)
        return query.all()

    def getByPlayer(self, playerId: int, season: Optional[int] = None) -> List[CardTemplate]:
        query = self.session.query(CardTemplate).filter_by(player_id=playerId)
        if season is not None:
            query = query.filter_by(season_created=season)
        return query.all()

    def save(self, template: CardTemplate) -> CardTemplate:
        self.session.add(template)
        self.session.flush()
        return template

    def saveBatch(self, templates: List[CardTemplate]):
        self.session.add_all(templates)
        self.session.flush()

    def countBySeason(self, season: int) -> int:
        return self.session.query(func.count(CardTemplate.id)).filter_by(season_created=season).scalar()


class UserCardRepository:
    """Repository for user card collection operations."""

    def __init__(self, session: Session):
        self.session = session

    def getById(self, cardId: int) -> Optional[UserCard]:
        return self.session.query(UserCard).filter_by(id=cardId).first()

    def getByUser(self, userId: int) -> List[UserCard]:
        return (
            self.session.query(UserCard)
            .filter_by(user_id=userId)
            .options(joinedload(UserCard.card_template))
            .all()
        )

    def getByUserAndSeason(self, userId: int, season: int) -> List[UserCard]:
        """Get user's active cards for a season (cards minted that season)."""
        return (
            self.session.query(UserCard)
            .join(CardTemplate)
            .filter(UserCard.user_id == userId, CardTemplate.season_created == season)
            .options(joinedload(UserCard.card_template))
            .all()
        )

    def getByIds(self, cardIds: List[int], userId: int) -> List[UserCard]:
        """Get multiple cards by ID, scoped to a user."""
        return (
            self.session.query(UserCard)
            .filter(UserCard.id.in_(cardIds), UserCard.user_id == userId)
            .options(joinedload(UserCard.card_template))
            .all()
        )

    def save(self, card: UserCard) -> UserCard:
        self.session.add(card)
        self.session.flush()
        return card

    def saveBatch(self, cards: List[UserCard]):
        self.session.add_all(cards)
        self.session.flush()

    def delete(self, card: UserCard):
        self.session.delete(card)
        self.session.flush()

    def deleteBatch(self, cards: List[UserCard]):
        for card in cards:
            self.session.delete(card)
        self.session.flush()

    def countByUser(self, userId: int) -> int:
        return self.session.query(func.count(UserCard.id)).filter_by(user_id=userId).scalar()


class EquippedCardRepository:
    """Repository for equipped card operations."""

    def __init__(self, session: Session):
        self.session = session

    def getByUserWeek(self, userId: int, season: int, week: int) -> List[EquippedCard]:
        return (
            self.session.query(EquippedCard)
            .filter_by(user_id=userId, season=season, week=week)
            .options(joinedload(EquippedCard.user_card).joinedload(UserCard.card_template))
            .order_by(EquippedCard.slot_number)
            .all()
        )

    def getAllForWeek(self, season: int, week: int) -> List[EquippedCard]:
        """Get all equipped cards for a given week (all users)."""
        return (
            self.session.query(EquippedCard)
            .filter_by(season=season, week=week)
            .options(joinedload(EquippedCard.user_card).joinedload(UserCard.card_template))
            .all()
        )

    def getEquippedCardIds(self, userId: int, season: int = 0, week: int = 0) -> set:
        """Get the set of user_card_ids equipped for a specific season/week."""
        return {
            r[0] for r in self.session.query(EquippedCard.user_card_id)
            .filter_by(user_id=userId, season=season, week=week)
            .all()
        }

    def save(self, equipped: EquippedCard) -> EquippedCard:
        self.session.add(equipped)
        self.session.flush()
        return equipped

    def deleteByUserWeek(self, userId: int, season: int, week: int):
        """Remove all equipped cards for a user's week (for re-equipping)."""
        self.session.query(EquippedCard).filter_by(
            user_id=userId, season=season, week=week
        ).delete()
        self.session.flush()

    def lockWeek(self, season: int, week: int):
        """Lock equipped cards for users who have all slots filled.

        Base is 5 slots; users with an MVP-classified card or active
        temp_card_slot power-up get 6.
        """
        from sqlalchemy import func
        from database.models import ShopPurchase

        # Find each user's card count for this week
        userCounts = (
            self.session.query(
                EquippedCard.user_id,
                func.count(EquippedCard.id).label("cnt"),
            )
            .filter_by(season=season, week=week)
            .group_by(EquippedCard.user_id)
            .having(func.count(EquippedCard.id) >= 5)
            .all()
        )

        if not userCounts:
            self.session.flush()
            return

        candidateIds = {row[0] for row in userCounts}

        # Check which of these users have an MVP card equipped this week
        mvpRows = (
            self.session.query(EquippedCard.user_id)
            .join(UserCard, EquippedCard.user_card_id == UserCard.id)
            .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
            .filter(
                EquippedCard.season == season,
                EquippedCard.week == week,
                EquippedCard.user_id.in_(candidateIds),
                CardTemplate.classification.isnot(None),
                CardTemplate.classification.contains("mvp"),
            )
            .distinct()
            .all()
        )
        mvpUserIds = {row[0] for row in mvpRows}

        # Check which users have an active temp_card_slot power-up
        cardSlotRows = (
            self.session.query(ShopPurchase.user_id)
            .filter(
                ShopPurchase.user_id.in_(candidateIds),
                ShopPurchase.season == season,
                ShopPurchase.item_slug == "temp_card_slot",
                ShopPurchase.expires_at_week >= week,
            )
            .distinct()
            .all()
        )
        cardSlotUserIds = {row[0] for row in cardSlotRows}

        sixSlotUserIds = mvpUserIds | cardSlotUserIds

        fullUserIds = set()
        for userId, cnt in userCounts:
            requiredSlots = 6 if userId in sixSlotUserIds else 5
            if cnt >= requiredSlots:
                fullUserIds.add(userId)

        if fullUserIds:
            self.session.query(EquippedCard).filter(
                EquippedCard.season == season,
                EquippedCard.week == week,
                EquippedCard.locked == False,
                EquippedCard.user_id.in_(fullUserIds),
            ).update({"locked": True}, synchronize_session='fetch')
        self.session.flush()

    def lockAllForWeek(self, season: int, week: int):
        """Lock ALL equipped cards for a week when games start (auto-lock)."""
        self.session.query(EquippedCard).filter(
            EquippedCard.season == season,
            EquippedCard.week == week,
            EquippedCard.locked == False,
        ).update({"locked": True}, synchronize_session='fetch')
        self.session.flush()

    def unlockWeek(self, season: int, week: int):
        """Unlock all equipped cards after a week completes."""
        self.session.query(EquippedCard).filter_by(
            season=season, week=week, locked=True
        ).update({"locked": False})
        self.session.flush()


class CurrencyRepository:
    """Repository for user currency and transaction operations."""

    def __init__(self, session: Session):
        self.session = session

    def getByUser(self, userId: int) -> Optional[UserCurrency]:
        return self.session.query(UserCurrency).filter_by(user_id=userId).first()

    def getOrCreate(self, userId: int, initialBalance: int = 0) -> UserCurrency:
        """Get user currency or create with initial balance."""
        currency = self.getByUser(userId)
        if not currency:
            currency = UserCurrency(
                user_id=userId,
                balance=initialBalance,
                lifetime_earned=initialBalance,
                lifetime_spent=0,
            )
            self.session.add(currency)
            self.session.flush()
        return currency

    def addFunds(self, userId: int, amount: int, transactionType: str,
                 description: str = None, season: int = None, week: int = None) -> UserCurrency:
        """Add Floobits to a user's balance and log the transaction."""
        currency = self.getOrCreate(userId)
        currency.balance += amount
        currency.lifetime_earned += amount

        tx = CurrencyTransaction(
            user_id=userId,
            amount=amount,
            balance_after=currency.balance,
            transaction_type=transactionType,
            description=description,
            season=season,
            week=week,
        )
        self.session.add(tx)
        self.session.flush()

        # Achievement hook — Tycoon (per-season floobits). Requires season context;
        # skip for achievement grants (avoids recursion) and for grants without a season.
        if transactionType != "achievement" and season:
            try:
                from managers import achievementManager as _am
                _am.onFloobitsEarned(self.session, userId, season)
            except Exception:
                pass  # never break a grant over an achievement hook

        # Toast hook — fire a per-user `floobits_received` WS event for passive
        # grants. Achievements have their own toast; user-initiated grants
        # (refunds, etc.) carry no surprise so they're skipped.
        if amount > 0 and transactionType in _PASSIVE_GRANT_TYPES:
            try:
                from api.event_models import CurrencyEvent
                from api.game_broadcaster import broadcaster
                event = CurrencyEvent.received(
                    amount=amount,
                    transactionType=transactionType,
                    description=description,
                    balanceAfter=int(currency.balance),
                    season=season,
                    week=week,
                )
                broadcaster.broadcast_to_user_sync(userId, event)
            except Exception:
                pass  # never break a grant over a toast broadcast

        return currency

    def spendFunds(self, userId: int, amount: int, transactionType: str,
                   description: str = None, season: int = None, week: int = None) -> Optional[UserCurrency]:
        """Spend Floobits. Returns None if insufficient balance."""
        currency = self.getOrCreate(userId)
        if currency.balance < amount:
            return None
        currency.balance -= amount
        currency.lifetime_spent += amount

        tx = CurrencyTransaction(
            user_id=userId,
            amount=-amount,
            balance_after=currency.balance,
            transaction_type=transactionType,
            description=description,
            season=season,
            week=week,
        )
        self.session.add(tx)
        self.session.flush()

        # Achievement hook — Magnate (per-season floobits spent). Requires season context.
        if season:
            try:
                from managers import achievementManager as _am
                _am.onSeasonFloobitsSpent(self.session, userId, season)
            except Exception:
                pass  # never break a spend over an achievement hook

        return currency

    def getTransactions(self, userId: int, limit: int = 20, offset: int = 0) -> List[CurrencyTransaction]:
        return (
            self.session.query(CurrencyTransaction)
            .filter_by(user_id=userId)
            .order_by(CurrencyTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )


class PackTypeRepository:
    """Repository for pack type operations."""

    def __init__(self, session: Session):
        self.session = session

    def getAll(self) -> List[PackType]:
        return self.session.query(PackType).all()

    def getByName(self, name: str) -> Optional[PackType]:
        return self.session.query(PackType).filter_by(name=name).first()

    def getById(self, packTypeId: int) -> Optional[PackType]:
        return self.session.query(PackType).filter_by(id=packTypeId).first()

    def save(self, packType: PackType) -> PackType:
        self.session.add(packType)
        self.session.flush()
        return packType

    def seedDefaults(self):
        """Seed default pack types if they don't exist.

        Pack revamp (feature/pack-revamp):
          - Starter: free, once per season, 5 base cards (no selection).
          - Daily packs: reveal/keep mechanic. Humble/Grand/Exquisite stay;
            Proper deprecated (left in DB to preserve PackOpening history).
          - guaranteed_rarity dropped — rates are bumped on higher tiers
            so Exquisite still feels Exquisite without a hard guarantee.
        """
        defaults = [
            PackType(
                name='starter',
                display_name='Starter Pack',
                cost=0,
                cards_per_pack=5,
                cards_kept=5,
                guaranteed_rarity=None,
                rarity_weights={'base': 100, 'holographic': 0, 'prismatic': 0, 'diamond': 0},
                description='Free starter. 5 base cards to fill your hand. Once per season.',
            ),
            PackType(
                name='humble',
                display_name='Humble Pack',
                cost=50,
                cards_per_pack=3,
                cards_kept=2,
                guaranteed_rarity=None,
                rarity_weights={'base': 100, 'holographic': 20, 'prismatic': 8, 'diamond': 1},
                description='Reveal 3 cards, keep 2. Anything is possible.',
            ),
            PackType(
                name='grand',
                display_name='Grand Pack',
                cost=350,
                cards_per_pack=5,
                cards_kept=3,
                guaranteed_rarity=None,
                rarity_weights={'base': 30, 'holographic': 50, 'prismatic': 35, 'diamond': 5},
                description='Reveal 5 cards, keep 3. Modestly increased drop rates.',
            ),
            PackType(
                name='exquisite',
                display_name='Exquisite Pack',
                cost=750,
                cards_per_pack=5,
                cards_kept=4,
                guaranteed_rarity=None,
                rarity_weights={'base': 15, 'holographic': 35, 'prismatic': 45, 'diamond': 12},
                description='Reveal 5 cards, keep 4. Greatly increased drop rates.',
            ),
        ]
        for pt in defaults:
            existing = self.getByName(pt.name)
            if not existing:
                self.session.add(pt)
            else:
                existing.cost = pt.cost
                existing.display_name = pt.display_name
                existing.description = pt.description
                existing.rarity_weights = pt.rarity_weights
                existing.guaranteed_rarity = pt.guaranteed_rarity
                existing.cards_per_pack = pt.cards_per_pack
                existing.cards_kept = pt.cards_kept
        self.session.flush()


class PackOpeningRepository:
    """Repository for pack opening history."""

    def __init__(self, session: Session):
        self.session = session

    def save(self, opening: PackOpening) -> PackOpening:
        self.session.add(opening)
        self.session.flush()
        return opening

    def getByUser(self, userId: int, limit: int = 20) -> List[PackOpening]:
        return (
            self.session.query(PackOpening)
            .filter_by(user_id=userId)
            .order_by(PackOpening.opened_at.desc())
            .limit(limit)
            .all()
        )
