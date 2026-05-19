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

        Standard tiers (themed-pack rework):
          - Humble: cheap entry tier, no rarity guarantee.
          - Grand: guaranteed prismatic in one slot.
          - Exquisite: guaranteed diamond in one slot.
          - Themed: 5 position + 3 output + per-qualifying-team rows seeded
            once. Cost/weights identical across themed rows; theme_type and
            theme_value distinguish them. The shop rotation surfaces 4 of
            them per 7-week cycle (FeaturedPackRotation).
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
                # Tightened (next-season): halved prismatic, removed
                # diamond entirely. Humble is the bulk-grind pack —
                # diamonds should not drop here.
                #   Per draw: ~80% base / ~16% holo / ~3% prismatic / 0% diamond
                rarity_weights={'base': 100, 'holographic': 20, 'prismatic': 4, 'diamond': 0},
                description='Reveal 3 cards, keep 2. Anything is possible.',
            ),
            PackType(
                name='grand',
                display_name='Grand Pack',
                cost=350,
                cards_per_pack=5,
                cards_kept=3,
                guaranteed_rarity='prismatic',
                # Tightened (next-season): non-guaranteed slot prism/diamond
                # rates trimmed sharply so the guaranteed Prismatic is the
                # actual value prop. Diamond can still upgrade the guaranteed
                # slot (16-17% chance) for a lucky pull, but the other 4
                # slots almost never carry diamond.
                #   Per non-guaranteed draw: ~69% base / ~24% holo / ~4% prismatic / ~0.9% diamond
                rarity_weights={'base': 82, 'holographic': 28, 'prismatic': 5, 'diamond': 1},
                description='Reveal 5 cards, keep 3. Guaranteed Prismatic; remaining cards at elevated odds.',
            ),
            PackType(
                name='exquisite',
                display_name='Exquisite Pack',
                cost=750,
                cards_per_pack=5,
                cards_kept=3,
                guaranteed_rarity='diamond',
                # Same tightened non-guaranteed rates as Grand. The
                # Diamond guarantee remains the entire reason to buy this.
                rarity_weights={'base': 82, 'holographic': 28, 'prismatic': 5, 'diamond': 1},
                description='Reveal 5 cards, keep 3. Guaranteed Diamond; remaining cards at elevated odds.',
            ),
        ]

        # ── Themed packs ──────────────────────────────────────────────────
        # Mid-tier price (150F). Tightened (next-season) to match the new
        # Grand/Exquisite non-guaranteed rates — diamonds nearly gone from
        # themed packs, prismatic less than half what it was. Themed value
        # comes from the player / position filter, not from chasing rarity.
        #   Per draw: ~69% base / ~24% holo / ~4% prismatic / ~0.9% diamond
        themedRarityWeights = {'base': 82, 'holographic': 28, 'prismatic': 5, 'diamond': 1}
        themedCost = 150
        themedCardsPerPack = 3
        themedCardsKept = 2

        def makeThemed(name, displayName, themeType, themeValue, desc):
            return PackType(
                name=name,
                display_name=displayName,
                cost=themedCost,
                cards_per_pack=themedCardsPerPack,
                cards_kept=themedCardsKept,
                guaranteed_rarity=None,
                rarity_weights=themedRarityWeights,
                description=desc,
                theme_type=themeType,
                theme_value=themeValue,
            )

        # Position-themed: 5 packs (one per position)
        positionInfo = [
            ('QB', 'Quarterback'),
            ('RB', 'Running Back'),
            ('WR', 'Wide Receiver'),
            ('TE', 'Tight End'),
            ('K',  'Kicker'),
        ]
        for code, label in positionInfo:
            defaults.append(makeThemed(
                name=f'themed_pos_{code.lower()}',
                displayName=f'{label} Pack',
                themeType='position',
                themeValue=code,
                desc=f'Reveal 3, keep 2. {label}s only.',
            ))

        # Output-themed: 3 packs (FP / FPx / Floobits)
        outputInfo = [
            ('fp',       'FP',       'cards that pay raw fantasy points'),
            ('fpx',      'FPx',      'cards that multiply fantasy points'),
            ('floobits', 'Floobits', 'cards that mint floobits'),
        ]
        for code, label, blurb in outputInfo:
            defaults.append(makeThemed(
                name=f'themed_out_{code}',
                displayName=f'{label} Pack',
                themeType='output',
                themeValue=code,
                desc=f'Reveal 3, keep 2. Only {blurb}.',
            ))

        # Prestige themed packs — bigger reveal pool, special player filter.
        # theme_value is resolved at draw time from Season state (last
        # season's champion roster / all-pro selection). Once-per-season
        # availability per user.
        # Guaranteed Holographic+: classifications (champion, all-pro)
        # only stamp onto non-base templates, so a base-only pack would
        # be a wasted "Champion Pack" with no classification. One slot
        # forced to holographic-or-better ensures at least one card carries
        # the classification users opened the pack for.
        defaults.append(PackType(
            name='themed_champion',
            display_name='Champion Pack',
            cost=250,
            cards_per_pack=5,
            cards_kept=3,
            guaranteed_rarity='holographic',
            rarity_weights=themedRarityWeights,
            description='Reveal 5, keep 3. Players from last season\u2019s champion.',
            theme_type='champion',
            theme_value=None,
        ))
        defaults.append(PackType(
            name='themed_allpro',
            display_name='All-Pro Pack',
            cost=250,
            cards_per_pack=5,
            cards_kept=3,
            guaranteed_rarity='holographic',
            rarity_weights=themedRarityWeights,
            description='Reveal 5, keep 3. Last season\u2019s All-Pro selections.',
            theme_type='allpro',
            theme_value=None,
        ))

        # Team-themed packs are seeded lazily once teams exist (see
        # _seedTeamThemedPacks below) — they depend on the teams table
        # being populated and on each team having enough card templates
        # to make for a viable pool.

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
                existing.theme_type = pt.theme_type
                existing.theme_value = pt.theme_value
        self.session.flush()

    def seedTeamThemed(self, minTemplates: int = 10):
        """Seed one themed pack per team that has at least minTemplates
        card templates. Idempotent — skips teams that already have a row."""
        from database.models import Team, CardTemplate
        from sqlalchemy import func

        # Count templates per team
        rows = (
            self.session.query(CardTemplate.team_id, func.count(CardTemplate.id))
            .filter(CardTemplate.team_id.isnot(None))
            .group_by(CardTemplate.team_id)
            .all()
        )
        eligibleTeamIds = {tid for tid, count in rows if count >= minTemplates}
        if not eligibleTeamIds:
            return 0

        themedRarityWeights = {'base': 75, 'holographic': 20, 'prismatic': 4, 'diamond': 1}
        added = 0
        for team in self.session.query(Team).filter(Team.id.in_(eligibleTeamIds)).all():
            name = f'themed_team_{team.id}'
            if self.getByName(name):
                continue
            self.session.add(PackType(
                name=name,
                display_name=f'{team.name} Pack',
                cost=150,
                cards_per_pack=3,
                cards_kept=2,
                guaranteed_rarity=None,
                rarity_weights=themedRarityWeights,
                description=f'Reveal 3, keep 2. {team.name} players only.',
                theme_type='team',
                theme_value=str(team.id),
            ))
            added += 1
        if added:
            self.session.flush()
        return added


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
