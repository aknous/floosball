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
        """Seed default pack types if they don't exist."""
        defaults = [
            PackType(
                name='humble',
                display_name='Humble Pack',
                cost=100,
                cards_per_pack=3,
                guaranteed_rarity=None,
                rarity_weights={'base': 100, 'chrome': 30, 'holographic': 20, 'gold': 15, 'prismatic': 5, 'diamond': 1},
                description='3 random cards. Anything is possible!',
            ),
            PackType(
                name='proper',
                display_name='Proper Pack',
                cost=250,
                cards_per_pack=5,
                guaranteed_rarity='chrome',
                rarity_weights={'base': 80, 'chrome': 40, 'holographic': 30, 'gold': 20, 'prismatic': 8, 'diamond': 2},
                description='5 cards with at least one Chrome or better.',
            ),
            PackType(
                name='grand',
                display_name='Grand Pack',
                cost=600,
                cards_per_pack=5,
                guaranteed_rarity='holographic',
                rarity_weights={'base': 60, 'chrome': 35, 'holographic': 30, 'gold': 25, 'prismatic': 15, 'diamond': 5},
                description='5 cards with two guaranteed Holographic or better.',
            ),
            PackType(
                name='exquisite',
                display_name='Exquisite Pack',
                cost=1500,
                cards_per_pack=5,
                guaranteed_rarity='prismatic',
                rarity_weights={'base': 20, 'chrome': 20, 'holographic': 25, 'gold': 30, 'prismatic': 30, 'diamond': 25},
                description='5 cards with a guaranteed Prismatic or better. Diamond drop rate massively boosted.',
            ),
        ]
        for pt in defaults:
            existing = self.getByName(pt.name)
            if not existing:
                self.session.add(pt)
            else:
                # Update existing pack type prices
                existing.cost = pt.cost
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
