"""Achievement progress tracking and reward grants.

Flow:
  1. Action happens (e.g. pick-em pick submitted) → handler calls recordProgress(session, userId, key, ...)
  2. recordProgress bumps UserAchievement.progress; if it hits target, sets completed_at and grants rewards
  3. Non-deferred rewards resolve immediately:
       - Floobits: added to UserCurrency via CurrencyRepository
       - Packs/powerups: PendingReward rows the user later claims
  4. Deferred rewards (Veteran) are held until processDeferredRewards() runs on season start
  5. Any PendingReward left unclaimed and unstashed at season start is dropped by sweepExpiredRewards()
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from database.models import (
    Achievement, UserAchievement, PendingReward, UserCard, CardTemplate,
)
from database.repositories.card_repositories import CurrencyRepository
from logger_config import get_logger

logger = get_logger("floosball.achievements")


def getAchievement(session: Session, key: str) -> Optional[Achievement]:
    """Look up an achievement template by its canonical key."""
    return session.query(Achievement).filter(Achievement.key == key).first()


def _resolveSeason(achievement: Achievement, currentSeason: int) -> int:
    """Return the season key to store on UserAchievement: 0 for once, currentSeason for per_season."""
    return currentSeason if achievement.scope == "per_season" else 0


def getOrCreateUserAchievement(session: Session, userId: int, achievement: Achievement,
                               currentSeason: int = 0) -> UserAchievement:
    seasonKey = _resolveSeason(achievement, currentSeason)
    ua = session.query(UserAchievement).filter(
        UserAchievement.user_id == userId,
        UserAchievement.achievement_id == achievement.id,
        UserAchievement.season == seasonKey,
    ).first()
    if ua:
        return ua
    ua = UserAchievement(user_id=userId, achievement_id=achievement.id,
                         season=seasonKey, progress=0)
    session.add(ua)
    session.flush()
    return ua


def recordProgress(session: Session, userId: int, key: str, increment: int = 1,
                   absolute: Optional[int] = None, currentSeason: int = 0) -> Optional[UserAchievement]:
    """Bump progress on an achievement. Returns the UserAchievement row if it
    was newly completed, else None. Safe to call even after completion.

    - increment: how much to add to current progress
    - absolute: if set, replaces progress with this value (used for Curator-style
      "collected 15 unique" checks where caller has authoritative count)
    - currentSeason: required for per_season scoped achievements so re-earns get their own row
    """
    ach = getAchievement(session, key)
    if ach is None:
        return None
    ua = getOrCreateUserAchievement(session, userId, ach, currentSeason)
    if ua.completed_at is not None:
        return None  # already done (for this season, if per_season)

    if absolute is not None:
        ua.progress = max(ua.progress, absolute)
    else:
        ua.progress += increment

    if ua.progress >= ach.target:
        ua.progress = ach.target
        ua.completed_at = datetime.utcnow()
        _grantReward(session, userId, ach, ua)
        logger.info(f"Achievement unlocked: user={userId} key={key} season={ua.season}")
        return ua
    return None


def _grantReward(session: Session, userId: int, achievement: Achievement, ua: UserAchievement) -> None:
    """Grant rewards for a just-completed achievement. Deferred rewards are held.

    Commits the session BEFORE broadcasting the achievement_unlocked event so
    the PendingReward row is durable by the time the user sees the toast. If
    a deploy killed the process between the broadcast and the commit, users
    saw the toast but the claim endpoint returned "Reward not found" because
    the row rolled back on process exit. Committing first makes the row
    durable even if the subsequent broadcast or the caller's later work fails.
    """
    cfg = achievement.reward_config or {}
    deferred = bool(cfg.get("deferred"))

    if not deferred:
        _applyReward(session, userId, cfg, source=f"achievement:{achievement.key}")
        ua.claimed_at = datetime.utcnow()

    # Commit the PendingReward + UserAchievement updates before we tell the
    # user about them. If the commit fails, we never broadcast.
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to commit achievement grant for user={userId} key={achievement.key}: {e}")
        return

    # Push an achievement_unlocked event to the user's live websocket(s).
    # Fires for both immediate and deferred unlocks so the UI gets the notification.
    try:
        from api.event_models import AchievementEvent
        from api.game_broadcaster import broadcaster
        event = AchievementEvent.unlocked(
            key=achievement.key,
            name=achievement.name,
            description=achievement.description,
            rewardConfig=cfg,
            season=ua.season,
        )
        broadcaster.broadcast_to_user_sync(userId, event)
    except Exception as e:
        logger.warning(f"Failed to push achievement_unlocked event: {e}")


# Soft cap on stashed pack rewards. Backend doesn't enforce — packs
# queue freely. The frontend surfaces a Convert-to-Floobits button on
# pending pack rows when the user is over this limit, letting users
# decide whether to open the overflow pack now or trade it for Floobits.
MAX_PENDING_PACK_REWARDS = 1


def _applyReward(session: Session, userId: int, cfg: dict, source: str) -> None:
    """Apply a reward config: floobits credited immediately, packs/powerups queued as PendingReward."""
    floobits = int(cfg.get("floobits") or 0)
    if floobits > 0:
        currencyRepo = CurrencyRepository(session)
        currencyRepo.addFunds(
            userId=userId, amount=floobits,
            transactionType="achievement",
            description=source,
        )

    now = datetime.utcnow()
    packs = cfg.get("packs") or []
    powerups = cfg.get("powerups") or []
    # Diagnostic: trace each PendingReward the reward grant attempts. We had a
    # production case (May 2026) where floobits credited and the user_achievement
    # row got claimed_at set, but no PendingReward row appeared in the DB for
    # tier-IV pack rewards. _applyReward and the surrounding _grantReward have
    # no obvious failure path that would skip the insert while keeping the
    # surrounding commits, so log enough to catch it in the act next time.
    logger.info(
        f"_applyReward user={userId} source={source} "
        f"floobits={floobits} packs={packs} powerups={powerups}"
    )
    addedIds = []
    for packSlug in packs:
        pr = PendingReward(
            user_id=userId, kind="pack", slug=packSlug,
            source=source, available_at=now,
        )
        session.add(pr)
        addedIds.append(("pack", packSlug, pr))
    for powerupSlug in powerups:
        pr = PendingReward(
            user_id=userId, kind="powerup", slug=powerupSlug,
            source=source, available_at=now,
        )
        session.add(pr)
        addedIds.append(("powerup", powerupSlug, pr))
    session.flush()
    if addedIds:
        # After flush, each PendingReward should have its primary key populated.
        idSummary = ", ".join(
            f"{kind}:{slug}#{pr.id}" for kind, slug, pr in addedIds
        )
        logger.info(f"_applyReward user={userId} source={source} flushed: {idSummary}")


def processDeferredRewards(session: Session, userId: Optional[int] = None) -> int:
    """Grant any completed-but-unclaimed deferred achievement rewards.

    Called at season start. Scans UserAchievement rows where completed_at is set
    but claimed_at is null, and the achievement has deferred=true. Grants the
    reward and marks claimed_at. Returns count of rewards processed.
    """
    q = session.query(UserAchievement, Achievement).join(
        Achievement, UserAchievement.achievement_id == Achievement.id,
    ).filter(
        UserAchievement.completed_at.isnot(None),
        UserAchievement.claimed_at.is_(None),
    )
    if userId is not None:
        q = q.filter(UserAchievement.user_id == userId)

    # Collect events during the loop; commit all rows before broadcasting so
    # a crash between flush and broadcast can't produce a toast-without-row.
    pendingEvents = []
    count = 0
    for ua, ach in q.all():
        cfg = ach.reward_config or {}
        if not cfg.get("deferred"):
            continue
        _applyReward(session, ua.user_id, cfg, source=f"achievement:{ach.key}")
        ua.claimed_at = datetime.utcnow()
        count += 1
        pendingEvents.append((ua.user_id, ach, ua.season, cfg))

    if not count:
        return 0

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to commit deferred reward grants: {e}")
        return 0

    logger.info(f"Processed {count} deferred achievement rewards")

    for userId, ach, season, cfg in pendingEvents:
        try:
            from api.event_models import AchievementEvent
            from api.game_broadcaster import broadcaster
            event = AchievementEvent.unlocked(
                key=ach.key, name=ach.name, description=ach.description,
                rewardConfig=cfg, season=season,
            )
            event["deferredRelease"] = True
            broadcaster.broadcast_to_user_sync(userId, event)
        except Exception as e:
            logger.warning(f"Failed to push deferred achievement event: {e}")
    return count


def convertOverCapPackStash(session: Session) -> int:
    """At season start, find any user holding more than MAX_PENDING_PACK_REWARDS
    unclaimed pack rewards and auto-convert the excess to Floobits at each
    pack's shop cost. Keeps the oldest pack (created_at asc); converts the
    rest. Mirrors the per-grant overflow logic in _applyReward — same cap,
    same conversion math — but operates retroactively at season rollover.

    Returns the number of pack rewards converted across all users.
    """
    from sqlalchemy import func as _sqlfunc
    from database.models import PackType

    # Find user_ids with > cap pending packs.
    overCapUserIds = [
        row[0] for row in
        session.query(PendingReward.user_id)
        .filter(PendingReward.kind == "pack",
                PendingReward.claimed_at.is_(None))
        .group_by(PendingReward.user_id)
        .having(_sqlfunc.count(PendingReward.id) > MAX_PENDING_PACK_REWARDS)
        .all()
    ]
    if not overCapUserIds:
        return 0

    currencyRepo = CurrencyRepository(session)
    convertedTotal = 0
    for userId in overCapUserIds:
        rows = (
            session.query(PendingReward)
            .filter(PendingReward.user_id == userId,
                    PendingReward.kind == "pack",
                    PendingReward.claimed_at.is_(None))
            .order_by(PendingReward.created_at.asc())
            .all()
        )
        # Keep the oldest MAX_PENDING_PACK_REWARDS; convert the rest.
        toConvert = rows[MAX_PENDING_PACK_REWARDS:]
        for pr in toConvert:
            packType = session.query(PackType).filter(PackType.name == pr.slug).first()
            value = int(packType.cost) if packType and packType.cost else 0
            if value > 0:
                currencyRepo.addFunds(
                    userId=userId, amount=value,
                    transactionType="achievement",
                    description=f"{pr.source} (season-start stash conversion: {pr.slug}→{value}F)",
                )
            session.delete(pr)
            convertedTotal += 1
        if toConvert:
            logger.info(
                f"convertOverCapPackStash user={userId}: "
                f"converted {len(toConvert)} pack(s) to Floobits"
            )
    if convertedTotal:
        session.flush()
    return convertedTotal


def sweepExpiredRewards(session: Session, currentSeason: int = 0) -> int:
    """Delete pending rewards the user never claimed or stashed-in-time.

    Called at season start. Two categories get swept:
      - Unclaimed rewards with no defer_until_season — abandoned from last
        season's default pool.
      - Unclaimed rewards whose defer_until_season is already past — the
        user stashed them for a target season but didn't open them during
        that season. E.g. a reward deferred to season 14 that wasn't
        claimed by season 14's end gets swept at season 15's start.

    Rewards with defer_until_season == currentSeason are preserved (that's
    the current season they're meant to be claimed in).

    Returns the number of rows deleted.
    """
    from sqlalchemy import or_
    q = session.query(PendingReward).filter(PendingReward.claimed_at.is_(None))
    if currentSeason:
        # Sweep undeferred + past-due deferred
        q = q.filter(or_(
            PendingReward.defer_until_season.is_(None),
            PendingReward.defer_until_season < currentSeason,
        ))
    else:
        # No season context — only sweep undeferred (legacy safety)
        q = q.filter(PendingReward.defer_until_season.is_(None))
    count = q.count()
    if count:
        q.delete(synchronize_session=False)
        session.flush()
        logger.info(f"Swept {count} expired pending reward(s)")
    return count


def backfillOnboardingAchievements(session: Session, userId: int) -> int:
    """Retro-credit onboarding achievements based on existing user state.
    Idempotent — recordProgress() no-ops once an achievement is completed.
    Returns the number of achievements newly unlocked by this call."""
    from database.models import (
        User, PickEmPick, PackOpening, FantasyRoster, FantasyRosterPlayer,
        EquippedCard, CurrencyTransaction,
    )

    unlocks = 0

    # Rookie — favorite team set
    user = session.get(User, userId)
    if user and user.favorite_team_id:
        if recordProgress(session, userId, "rookie", absolute=1):
            unlocks += 1

    # Prognosticator — any pick-em pick
    hasPick = session.query(PickEmPick.id).filter(PickEmPick.user_id == userId).first()
    if hasPick:
        if recordProgress(session, userId, "prognosticator", absolute=1):
            unlocks += 1

    # Pack Popper — any pack opened
    hasPack = session.query(PackOpening.id).filter(PackOpening.user_id == userId).first()
    if hasPack:
        if recordProgress(session, userId, "pack_popper", absolute=1):
            unlocks += 1

    # Field General — any roster with at least one player
    hasRoster = session.query(FantasyRoster.id).join(
        FantasyRosterPlayer, FantasyRosterPlayer.roster_id == FantasyRoster.id,
    ).filter(FantasyRoster.user_id == userId).first()
    if hasRoster:
        if recordProgress(session, userId, "field_general", absolute=1):
            unlocks += 1

    # Deck Builder — any equipped card row
    hasEquipped = session.query(EquippedCard.id).filter(EquippedCard.user_id == userId).first()
    if hasEquipped:
        if recordProgress(session, userId, "deck_builder", absolute=1):
            unlocks += 1

    # Patron — any team_contribution currency transaction
    hasContribution = session.query(CurrencyTransaction.id).filter(
        CurrencyTransaction.user_id == userId,
        CurrencyTransaction.transaction_type == "team_contribution",
    ).first()
    if hasContribution:
        if recordProgress(session, userId, "patron", absolute=1):
            unlocks += 1

    return unlocks


def getUserAchievements(session: Session, userId: int, currentSeason: int = 0) -> List[Dict[str, Any]]:
    """Return all achievements with the user's progress and completion state.
    For per_season achievements, shows progress for the currentSeason."""
    # For per_season we need to match on season=currentSeason; for once we match season=0.
    # Easiest: outer-join with season-aware condition.
    rows = session.query(Achievement, UserAchievement).outerjoin(
        UserAchievement,
        (UserAchievement.achievement_id == Achievement.id)
        & (UserAchievement.user_id == userId)
        & (
            ((Achievement.scope == "once") & (UserAchievement.season == 0))
            | ((Achievement.scope == "per_season") & (UserAchievement.season == currentSeason))
        ),
    ).order_by(Achievement.sort_order.asc()).all()

    out = []
    for ach, ua in rows:
        progress = ua.progress if ua else 0
        completedAt = ua.completed_at.isoformat() + 'Z' if ua and ua.completed_at else None
        claimedAt = ua.claimed_at.isoformat() + 'Z' if ua and ua.claimed_at else None
        # Secret achievements: hide name/description/reward until unlocked.
        # Caller can still see the count so they know secrets exist.
        isSecret = ach.category == "secret"
        isLocked = isSecret and completedAt is None
        out.append({
            "id": ach.id,
            "key": None if isLocked else ach.key,
            "name": "???" if isLocked else ach.name,
            "description": None if isLocked else ach.description,
            "category": ach.category,
            "scope": ach.scope,
            "target": None if isLocked else ach.target,
            "progress": 0 if isLocked else min(progress, ach.target),
            "completedAt": completedAt,
            "claimedAt": claimedAt,
            "rewardConfig": {} if isLocked else (ach.reward_config or {}),
        })
    return out


def getUnclaimedRewardCount(session: Session, userId: int, currentSeason: int = 0) -> int:
    """Count pending rewards the user can actually claim right now.
    Excludes rewards deferred to a future season."""
    q = session.query(PendingReward).filter(
        PendingReward.user_id == userId,
        PendingReward.claimed_at.is_(None),
        PendingReward.available_at <= datetime.utcnow(),
    )
    if currentSeason:
        from sqlalchemy import or_
        q = q.filter(or_(
            PendingReward.defer_until_season.is_(None),
            PendingReward.defer_until_season <= currentSeason,
        ))
    return q.count()


# Regular-season weeks remaining below which the UI may offer "defer to next season"
DEFER_OFFER_WEEKS_REMAINING = 4
REGULAR_SEASON_WEEKS = 28


def getPendingRewards(session: Session, userId: int, currentSeason: int = 0,
                      currentWeek: int = 0, isOffseason: bool = False) -> List[Dict[str, Any]]:
    """List unclaimed rewards for the user, with canDefer flag for late-season packs."""
    rows = session.query(PendingReward).filter(
        PendingReward.user_id == userId,
        PendingReward.claimed_at.is_(None),
    ).order_by(PendingReward.created_at.asc()).all()

    weeksLeft = max(0, REGULAR_SEASON_WEEKS - currentWeek) if currentWeek else REGULAR_SEASON_WEEKS
    lateSeason = weeksLeft <= DEFER_OFFER_WEEKS_REMAINING and currentWeek > 0
    # Offseason is treated as deferral-eligible too — currentWeek resets to 0
    # at offseason start, which would otherwise hide the option during the
    # exact window when a user is most likely to come back and clean up
    # unclaimed pack rewards.
    deferEligible = lateSeason or isOffseason

    out = []
    for r in rows:
        # Defer option shown for any unclaimed reward during the eligible
        # window (late regular season or offseason), as long as it hasn't
        # already been deferred. Applies to packs and powerups.
        canDefer = (
            deferEligible
            and r.defer_until_season is None
            and currentSeason > 0
        )
        out.append({
            "id": r.id,
            "kind": r.kind,
            "slug": r.slug,
            "source": r.source,
            "availableAt": r.available_at.isoformat() + 'Z',
            "createdAt": r.created_at.isoformat() + 'Z',
            "deferUntilSeason": r.defer_until_season,
            "canDefer": canDefer,
        })
    return out


# ── Convenience recorders — one-liners for trigger sites ──────────────────────

def onFavoriteTeamChosen(session: Session, userId: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "rookie")


def onPickEmSubmitted(session: Session, userId: int, isAutoPick: bool) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "prognosticator")


def onPackOpened(session: Session, userId: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "pack_popper")


# Required paid pack names for the Anthology secret. Excludes the free
# starter pack — the achievement is about deliberate purchasing breadth.
# Keep in sync with the PackTypeRepository.seedDefaults() pack list.
ANTHOLOGY_REQUIRED_PACK_NAMES = frozenset({
    'humble', 'grand', 'exquisite',
    'themed_pos_qb', 'themed_pos_rb', 'themed_pos_wr',
    'themed_pos_te', 'themed_pos_k',
    'themed_out_fp', 'themed_out_fpx', 'themed_out_floobits',
    'themed_champion', 'themed_allpro',
})


def checkAnthology(session: Session, userId: int, currentSeason: int) -> Optional[UserAchievement]:
    """Anthology — secret unlocked when a user has purchased every paid
    pack type in a single season. Champion + All-Pro packs require
    season ≥ 2 to even appear in rotation, so this can't fire in season 1.
    Called after each successful pack purchase commit.
    """
    if not currentSeason:
        return None
    from database.models import PackOpening, PackType, Season
    seasonRow = session.query(Season).filter_by(season_number=currentSeason).first()
    if not seasonRow or not seasonRow.start_date:
        return None
    rows = (
        session.query(PackType.name)
        .join(PackOpening, PackOpening.pack_type_id == PackType.id)
        .filter(
            PackOpening.user_id == userId,
            PackOpening.cost > 0,
            PackOpening.opened_at >= seasonRow.start_date,
        )
        .distinct()
        .all()
    )
    purchasedNames = {name for (name,) in rows}
    if ANTHOLOGY_REQUIRED_PACK_NAMES.issubset(purchasedNames):
        return unlockSecret(session, userId, "anthology")
    return None


def onFantasyRosterSet(session: Session, userId: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "field_general")


def onFantasyRosterWeekCompleted(session: Session, userId: int, currentSeason: int) -> Optional[UserAchievement]:
    """Call once per week after the user has a roster set for the just-completed week."""
    return recordProgress(session, userId, "veteran", currentSeason=currentSeason)


def onCardEquipped(session: Session, userId: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "deck_builder")


def onTeamContribution(session: Session, userId: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "patron")


def onClairvoyant(session: Session, userId: int, currentSeason: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "sharp", currentSeason=currentSeason)


def onFloobitsEarned(session: Session, userId: int, currentSeason: int) -> List[UserAchievement]:
    """Tycoon tiers (I-IV) — track floobits earned this season. Queries
    CurrencyTransaction for the season sum. Skips if season is 0
    (e.g. admin grants outside a season)."""
    if not currentSeason:
        return []
    from database.models import CurrencyTransaction
    from sqlalchemy import func
    seasonEarned = session.query(func.coalesce(func.sum(CurrencyTransaction.amount), 0)).filter(
        CurrencyTransaction.user_id == userId,
        CurrencyTransaction.season == currentSeason,
        CurrencyTransaction.amount > 0,
    ).scalar() or 0
    unlocked = []
    for key in ("tycoon_i", "tycoon_ii", "tycoon_iii", "tycoon_iv"):
        u = recordProgress(session, userId, key, absolute=int(seasonEarned), currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def syncCuratorProgress(session: Session, userId: int, currentSeason: int) -> Optional[UserAchievement]:
    """Curator — recompute unique templates the user owns from this season."""
    if not currentSeason:
        return None
    uniqueCount = session.query(UserCard.card_template_id).join(
        CardTemplate, UserCard.card_template_id == CardTemplate.id,
    ).filter(
        UserCard.user_id == userId,
        CardTemplate.season_created == currentSeason,
    ).distinct().count()
    return recordProgress(session, userId, "curator", absolute=uniqueCount, currentSeason=currentSeason)


def syncCollectionAchievements(session: Session, userId: int) -> List[UserAchievement]:
    """Recompute the permanent Vault collection achievements from the user's
    vaulted cards. Called whenever the vault changes (vault / trash). These are
    once-scope, so progress is authoritative (absolute) and never resets.

    - Hometown Hero: vaulted cards of players on the user's favorite team
    - Full Spectrum: all 4 editions of a single player vaulted
    - Ice Cold I/II/III: vaulted Diamond count
    - Archivist I/II/III: distinct players vaulted
    - All-Pro Set: every All-Pro card from a single season vaulted
    """
    from database.models import User
    completed: List[UserAchievement] = []

    vaulted = (
        session.query(UserCard, CardTemplate)
        .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
        .filter(UserCard.user_id == userId, UserCard.vaulted == True)  # noqa: E712
        .all()
    )
    if not vaulted:
        return completed

    user = session.get(User, userId)
    favTeamId = getattr(user, "favorite_team_id", None) if user else None

    homeTeamCount = 0
    diamondCount = 0
    players = set()
    editionsByPlayer: Dict[int, set] = {}
    allProBySeason: Dict[int, set] = {}
    hasMaxTierVaulted = False
    for _uc, tpl in vaulted:
        players.add(tpl.player_id)
        if favTeamId and tpl.team_id == favTeamId:
            homeTeamCount += 1
        if tpl.edition == "diamond":
            diamondCount += 1
        if (getattr(_uc, "tier", 1) or 1) >= 4:
            hasMaxTierVaulted = True
        editionsByPlayer.setdefault(tpl.player_id, set()).add(tpl.edition)
        if tpl.classification and "all_pro" in tpl.classification:
            allProBySeason.setdefault(tpl.season_created, set()).add(tpl.player_id)

    fullSpectrum = 1 if any(len(eds) >= 4 for eds in editionsByPlayer.values()) else 0

    # All-Pro Set: a season where the user has vaulted every All-Pro player's card.
    allProSet = 0
    for season, ownedPlayers in allProBySeason.items():
        totalAllPro = (
            session.query(CardTemplate.player_id)
            .filter(
                CardTemplate.season_created == season,
                CardTemplate.classification.like("%all_pro%"),
            ).distinct().count()
        )
        if totalAllPro > 0 and len(ownedPlayers) >= totalAllPro:
            allProSet = 1
            break

    def _rec(key, value):
        ua = recordProgress(session, userId, key, absolute=value)
        if ua:
            completed.append(ua)

    if favTeamId:
        _rec("hometown_hero", homeTeamCount)
    _rec("full_spectrum", fullSpectrum)
    _rec("all_pro_set", allProSet)
    _rec("ice_cold_i", diamondCount)
    _rec("ice_cold_ii", diamondCount)
    _rec("ice_cold_iii", diamondCount)
    _rec("archivist_i", len(players))
    _rec("archivist_ii", len(players))
    _rec("archivist_iii", len(players))
    # Secret: enshrine a fully upgraded card.
    if hasMaxTierVaulted:
        s = unlockSecret(session, userId, "dynasty")
        if s:
            completed.append(s)
    return completed


def onDiamondOpened(session: Session, userId: int, currentSeason: int) -> Optional[UserAchievement]:
    """Sparkler — fires once per season on first Diamond card opened."""
    return recordProgress(session, userId, "sparkler", currentSeason=currentSeason)


def onWeeklyFantasyPoints(session: Session, userId: int, weeklyFP: int, currentSeason: int) -> List[UserAchievement]:
    """Banner Week tiers (I–IV) — progress is the FP earned that week. A high week
    completes every tier at or below its total."""
    unlocked = []
    for key in ("banner_week_i", "banner_week_ii", "banner_week_iii", "banner_week_iv"):
        u = recordProgress(session, userId, key, absolute=weeklyFP, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onWeeklyCardFloobits(session: Session, userId: int, floobitsFromCards: int, currentSeason: int) -> List[UserAchievement]:
    """Racket tiers (I–IV) — floobits earned from card effects in a single week."""
    unlocked = []
    for key in ("racket_i", "racket_ii", "racket_iii", "racket_iv"):
        u = recordProgress(session, userId, key, absolute=floobitsFromCards, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onPerfectPickEmWeek(session: Session, userId: int, currentSeason: int) -> Optional[UserAchievement]:
    return recordProgress(session, userId, "perfect_week", currentSeason=currentSeason)


def onSeasonFantasyPointsTotal(session: Session, userId: int, totalSeasonFP: int, currentSeason: int) -> List[UserAchievement]:
    """Dynamo tiers (I–IV) — cumulative season fantasy points."""
    unlocked = []
    for key in ("dynamo_i", "dynamo_ii", "dynamo_iii", "dynamo_iv"):
        u = recordProgress(session, userId, key, absolute=totalSeasonFP, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onSeasonPickemPointsTotal(session: Session, userId: int, totalSeasonPoints: int, currentSeason: int) -> List[UserAchievement]:
    """Oracle tiers (I–IV) — cumulative season prognostication points."""
    unlocked = []
    for key in ("oracle_i", "oracle_ii", "oracle_iii", "oracle_iv"):
        u = recordProgress(session, userId, key, absolute=totalSeasonPoints, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onPlayoffBracketScored(session: Session, userId: int, points: int, currentSeason: int) -> List[UserAchievement]:
    """Bracketeer tiers (I–IV) — final playoff bracket points this season."""
    unlocked = []
    for key in ("bracketeer_i", "bracketeer_ii", "bracketeer_iii", "bracketeer_iv"):
        u = recordProgress(session, userId, key, absolute=points, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onSeasonFloobitsSpent(session: Session, userId: int, currentSeason: int) -> List[UserAchievement]:
    """Magnate tiers (I–IV) — cumulative season floobits spent.
    Sums CurrencyTransaction negatives for this user this season."""
    if not currentSeason:
        return []
    from database.models import CurrencyTransaction
    from sqlalchemy import func
    spent = session.query(func.coalesce(func.sum(-CurrencyTransaction.amount), 0)).filter(
        CurrencyTransaction.user_id == userId,
        CurrencyTransaction.season == currentSeason,
        CurrencyTransaction.amount < 0,
    ).scalar() or 0
    unlocked = []
    for key in ("magnate_i", "magnate_ii", "magnate_iii", "magnate_iv"):
        u = recordProgress(session, userId, key, absolute=int(spent), currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onWeeklyFantasyPodium(session: Session, userId: int, currentSeason: int) -> List[UserAchievement]:
    """Podium tiers (I–IV) — fires when user places top 3 on a weekly fantasy leaderboard."""
    unlocked = []
    for key in ("podium_i", "podium_ii", "podium_iii", "podium_iv"):
        u = recordProgress(session, userId, key, increment=1, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onWeeklyPickemPodium(session: Session, userId: int, currentSeason: int) -> List[UserAchievement]:
    """Pundit tiers (I–IV) — fires when user places top 3 on a weekly pick-em leaderboard."""
    unlocked = []
    for key in ("pundit_i", "pundit_ii", "pundit_iii", "pundit_iv"):
        u = recordProgress(session, userId, key, increment=1, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onCardLeveledUp(session: Session, userId: int, toTier: int, currentSeason: int) -> List[UserAchievement]:
    """Card-upgrade hooks (seasonal): Artificer tiers count level-ups; Ascendant
    fires on reaching max tier. Secret Overclocked fires at three max-tier cards
    in one season."""
    from constants import CARD_TIER_MAX
    unlocked = []
    for key in ("artificer_i", "artificer_ii", "artificer_iii"):
        u = recordProgress(session, userId, key, increment=1, currentSeason=currentSeason)
        if u:
            unlocked.append(u)
    if toTier >= CARD_TIER_MAX:
        u = recordProgress(session, userId, "ascendant", absolute=1, currentSeason=currentSeason)
        if u:
            unlocked.append(u)
        # Secret: three max-tier cards minted this season.
        maxCount = (
            session.query(UserCard.id)
            .join(CardTemplate, UserCard.card_template_id == CardTemplate.id)
            .filter(
                UserCard.user_id == userId,
                UserCard.tier >= CARD_TIER_MAX,
                CardTemplate.season_created == currentSeason,
            ).count()
        )
        if maxCount >= 3:
            s = unlockSecret(session, userId, "overclocked")
            if s:
                unlocked.append(s)
    return unlocked


def unlockSecret(session: Session, userId: int, key: str) -> Optional[UserAchievement]:
    """Unlock a one-time secret achievement. No-op if already unlocked."""
    return recordProgress(session, userId, key, absolute=1)


def onWeeklyTotalFpMultiplier(session: Session, userId: int, multProduct: float, currentSeason: int) -> List[UserAchievement]:
    """Compound tiers (I–IV) — single-week total FP multiplier.
    Targets are stored as mult × 100 (so target=120 represents a 1.2x gate)."""
    # Encode the multiplier as int×100 to match the stored targets.
    encoded = int(round(multProduct * 100))
    unlocked = []
    for key in ("compound_i", "compound_ii", "compound_iii", "compound_iv"):
        u = recordProgress(session, userId, key, absolute=encoded, currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked


def onSeasonTeamContributions(session: Session, userId: int, currentSeason: int) -> List[UserAchievement]:
    """Benefactor tiers (I–IV) — cumulative floobits contributed to the user's team this season.
    Sums CurrencyTransaction rows with type='team_contribution'."""
    if not currentSeason:
        return []
    from database.models import CurrencyTransaction
    from sqlalchemy import func
    contributed = session.query(func.coalesce(func.sum(-CurrencyTransaction.amount), 0)).filter(
        CurrencyTransaction.user_id == userId,
        CurrencyTransaction.season == currentSeason,
        CurrencyTransaction.transaction_type == "team_contribution",
    ).scalar() or 0
    unlocked = []
    for key in ("benefactor_i", "benefactor_ii", "benefactor_iii", "benefactor_iv"):
        u = recordProgress(session, userId, key, absolute=int(contributed), currentSeason=currentSeason)
        if u: unlocked.append(u)
    return unlocked
