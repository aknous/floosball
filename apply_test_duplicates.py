"""Dev helper: grant a user duplicate cards of every effect so the card
upgrade/Level-Up flow can be tested (leveling needs same-effect duplicates).

For each effect that has a current-season template, ensures the user owns at
least --count cards of that effect (default 4 = a target + 3 duplicates to max
I->IV). Idempotent: re-running only tops up effects that are short.

DRY-RUN by default — pass --apply to write. Targets the local dev DB.

  .venv/bin/python apply_test_duplicates.py                       # dry-run
  .venv/bin/python apply_test_duplicates.py --apply               # grant 4/effect
  .venv/bin/python apply_test_duplicates.py --count 4 --floobits 1000000 --apply
"""
import argparse
import json
import sys
from collections import defaultdict

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from database.models import User, UserCard, CardTemplate, UserCurrency


def effectName(tpl):
    ec = tpl.effect_config or {}
    if isinstance(ec, str):
        try:
            ec = json.loads(ec)
        except Exception:
            ec = {}
    return ec.get("effectName")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/floosball.db", help="dev DB path")
    ap.add_argument("--user", default=None, help="username (default: the only user)")
    ap.add_argument("--count", type=int, default=4,
                    help="ensure at least N cards per effect (default 4 = target + 3 dupes)")
    ap.add_argument("--season", type=int, default=None,
                    help="season for template selection (default: max season_created)")
    ap.add_argument("--floobits", type=int, default=None,
                    help="set the user's balance to this (for paying upgrades)")
    ap.add_argument("--no-mint", action="store_true",
                    help="don't mint templates for registry effects missing from this DB")
    ap.add_argument("--only", default=None,
                    help="comma-list of effects to keep/grant; PRUNES the user's cards "
                         "for every other effect (use to scope to a re-test set)")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    engine = create_engine(f"sqlite:///{args.db}")
    session = sessionmaker(bind=engine)()

    # Resolve user
    if args.user:
        user = session.query(User).filter(func.lower(User.username) == args.user.lower()).first()
        if not user:
            print(f"User '{args.user}' not found."); sys.exit(1)
    else:
        users = session.query(User).all()
        if len(users) != 1:
            print(f"{len(users)} users — pass --user <username>: "
                  f"{', '.join(u.username for u in users)}"); sys.exit(1)
        user = users[0]

    season = args.season or session.query(func.max(CardTemplate.season_created)).scalar()

    # Restrict to a specific effect list (--only) and prune the rest.
    onlySet = None
    if args.only:
        onlySet = {e.strip() for e in args.only.split(",") if e.strip()}

    # One representative template per effect, for the chosen season.
    repByEffect = {}
    for tpl in session.query(CardTemplate).filter_by(season_created=season).all():
        en = effectName(tpl)
        if en and en not in repByEffect:
            repByEffect[en] = tpl

    # Mint templates for effects that exist in the registry but were never seeded
    # in this dev DB (so they're testable), unless --no-mint. With --only, only
    # mint the listed effects.
    from managers.cardEffects import (
        EFFECT_REGISTRY, EFFECT_EDITION_TIER, buildEffectConfig, getEffectOutputType,
    )
    from managers.cardManager import computeRarityWeight, getSellValue
    wanted = onlySet if onlySet is not None else set(EFFECT_REGISTRY)
    missing = sorted((wanted & set(EFFECT_REGISTRY)) - set(repByEffect))
    donors = [t for t in session.query(CardTemplate).all() if (t.player_rating or 0) >= 75] \
        or session.query(CardTemplate).all()

    def mintTemplate(effect, donor):
        edition = EFFECT_EDITION_TIER.get(effect, "base")
        rating = donor.player_rating or 80
        cfg, usedPos = None, donor.position
        for pos in [donor.position, 1, 2, 3, 4, 5]:
            c = buildEffectConfig(edition, rating, pos, donor.team_id, forceEffect=effect)
            if (c or {}).get("effectName") == effect:
                cfg, usedPos = c, pos
                break
        if cfg is None:
            return None
        t = CardTemplate(
            player_id=donor.player_id, edition=edition, season_created=season,
            is_rookie=False, classification=donor.classification,
            player_name=donor.player_name, team_id=donor.team_id,
            player_rating=rating, position=usedPos, effect_config=cfg,
            rarity_weight=computeRarityWeight(edition, rating),
            sell_value=getSellValue(edition, isActive=True),
            is_upgraded=True, output_type=getEffectOutputType(effect),
        )
        session.add(t)
        session.flush()
        return t

    minted = []
    if args.apply and not args.no_mint and missing:
        for i, eff in enumerate(missing):
            t = mintTemplate(eff, donors[i % len(donors)])
            if t:
                repByEffect[eff] = t
                minted.append(eff)

    # With --only, restrict grants to the listed effects.
    if onlySet is not None:
        repByEffect = {e: t for e, t in repByEffect.items() if e in onlySet}

    # Count the user's existing cards per effect.
    haveByEffect = defaultdict(int)
    for uc in session.query(UserCard).filter_by(user_id=user.id).all():
        en = effectName(uc.card_template)
        if en:
            haveByEffect[en] += 1

    # With --only, prune the user's cards for every other effect (skip equipped).
    pruneIds = []
    if onlySet is not None:
        from database.models import EquippedCard
        equippedUcIds = {r[0] for r in session.query(EquippedCard.user_card_id)
                         .filter_by(user_id=user.id).all()}
        for uc in session.query(UserCard).filter_by(user_id=user.id).all():
            if uc.id not in equippedUcIds and effectName(uc.card_template) not in onlySet:
                pruneIds.append(uc.id)

    # Plan grants.
    grants = []  # (effectName, templateId, n)
    for en, tpl in sorted(repByEffect.items()):
        need = max(0, args.count - haveByEffect.get(en, 0))
        if need:
            grants.append((en, tpl.id, need))
    totalCards = sum(n for _, _, n in grants)

    print(f"DB: {args.db}  |  user: {user.username} (id {user.id})  |  season {season}")
    print(f"effects with templates: {len(repByEffect)}  |  target {args.count}/effect")
    if missing and not args.no_mint:
        if args.apply:
            print(f"minted {len(minted)} missing-effect template(s): {', '.join(minted)}")
        else:
            print(f"would mint {len(missing)} missing-effect template(s): {', '.join(missing)}")
    if onlySet is not None:
        print(f"--only: {len(onlySet)} effect(s); will prune {len(pruneIds)} card(s) for other effects")
    print(f"plan: grant {totalCards} cards across {len(grants)} effect(s) short of target")
    if grants:
        sample = ", ".join(f"{en}+{n}" for en, _, n in grants[:8])
        print(f"  e.g. {sample}{' ...' if len(grants) > 8 else ''}")
    if args.floobits is not None:
        cur = session.query(UserCurrency).filter_by(user_id=user.id).first()
        print(f"floobits: {cur.balance if cur else 0} -> {args.floobits}")

    if not args.apply:
        print("\nDRY RUN — re-run with --apply to write.")
        session.close()
        return

    # Apply
    if pruneIds:
        session.query(UserCard).filter(UserCard.id.in_(pruneIds)).delete(synchronize_session=False)
    for en, tplId, n in grants:
        for _ in range(n):
            session.add(UserCard(user_id=user.id, card_template_id=tplId,
                                 acquired_via="test_grant"))
    if args.floobits is not None:
        cur = session.query(UserCurrency).filter_by(user_id=user.id).first()
        if cur:
            cur.balance = args.floobits
        else:
            session.add(UserCurrency(user_id=user.id, balance=args.floobits))
    session.commit()
    print(f"\nAPPLIED: pruned {len(pruneIds)} card(s), granted {totalCards} card(s)"
          + (f", set balance to {args.floobits}" if args.floobits is not None else ""))
    session.close()


if __name__ == "__main__":
    main()
