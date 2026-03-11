"""Clerk JWT verification for FastAPI."""

import os
import random as _random
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt
from jwt import PyJWKClient

from database.connection import get_session
from database.models import User, UserCurrency, UserCard, CardTemplate, CurrencyTransaction, BetaAllowlist
from database.repositories.card_repositories import CurrencyRepository
from logger_config import get_logger

logger = get_logger("floosball.auth")

_bearerScheme = HTTPBearer()

# ---------------------------------------------------------------------------
# Random username generation
# ---------------------------------------------------------------------------

_USERNAME_FIRSTS = [
    # Original
    "Bootleg", "Moist", "Cornbread", "Squids", "Gootsy", "Frunk", "Chud",
    "Schmorby", "Quasi", "Stove", "Flakey", "Ovaltine", "Pickled", "Socks",
    "Reverend", "Professor", "Laserdisc", "Powershell", "Discount", "Turbo",
    "Wombat", "Pretzel", "Biscuit", "Waffle", "Pudding", "Gravy", "Noodle",
    "Spork", "Tugboat", "Gazebo", "Dumpster", "Forklift", "Trebuchet",
    "Pamphlet", "Kazoo", "Sweatpants", "Toaster", "Blunderbuss", "Firmware",
    "Lowercase", "Crispy", "Lukewarm", "Adequate", "Suspicious", "Bogus",
    "Rogue", "Sentient", "Forbidden", "Haunted", "Certified",
    # Expanded
    "Unlicensed", "Feral", "Tandem", "Benched", "Surplus", "Vintage",
    "Bargain", "Wholesale", "Squishy", "Marinated", "Unsanctioned",
    "Contraband", "Backup", "Defrosted", "Inflatable", "Offbrand",
    "Leftover", "Recalled", "Overtime", "Scrambled", "Knockoff",
    "Secondhand", "Unhinged", "Bedazzled", "Municipal", "Decoy",
    "Tactical", "Offshore", "Bootcamp", "Clearance",
]

_USERNAME_LASTS = [
    # Original
    "Gutpunch", "Flashmob", "Dreamcast", "Wigglesworth", "Dribbleston",
    "Bumpington", "Lagume", "Nightshift", "Perkinshire", "Pumpernick",
    "McElroy", "Trolleyproblem", "Vinaigrette", "Mouthfeel", "Supertoe",
    "Porkins", "Brutale", "Buckets", "Dangerfield", "Thunderpants",
    "Waffleton", "Crumpet", "Jalopy", "Kazooie", "Shenanigans",
    "Hooligan", "Rascal", "Fiasco", "Debacle", "Kerfuffle",
    "Brouhaha", "Bamboozle", "Hullabaloo", "Rigmarole", "Cahoots",
    "Tomfoolery", "Sheepdog", "Crabcakes", "Megabyte", "Malarkey",
    # Expanded
    "Humperdink", "Flapjacks", "Thundersocks", "Wigglebottom",
    "Bananahands", "Cheddarworth", "Dingleberry", "Fiddlesticks",
    "Goosebumps", "Hornswoggle", "Jibberjabber", "Lampshade",
    "Mumblecrust", "Nincompoop", "Pantaloons", "Quagmire",
    "Rumpelstilt", "Sassafras", "Tumbleweed", "Underbelly",
    "Whippersnap", "Clutterbuck", "Doodlebug", "Flotsam",
    "Gobsmacker", "Hoodwink", "Jellyroll", "Kettledrum",
    "Lollygag", "Monkeyshine", "Noodleberg", "Fumblerooski",
    "Puddinpop", "Scuttlebutt", "Slapstick", "Butterfumble",
    "Trampoline", "Collywobble", "Boondoggle", "Whodunnit",
]


def _generateRandomUsername(session) -> str:
    """Generate a unique random username like 'ThunderFalcon42'."""
    for _ in range(50):
        name = (
            _random.choice(_USERNAME_FIRSTS)
            + _random.choice(_USERNAME_LASTS)
            + str(_random.randint(1, 99))
        )
        existing = session.query(User).filter(User.username == name).first()
        if not existing:
            return name
    # Extremely unlikely fallback
    return "Player" + str(_random.randint(10000, 99999))


STARTER_FLOOBITS = 100
STARTER_CARD_COUNT = 5


def _provisionStarterPack(session, user):
    """Give a new user starter Floobits and 5 random base cards."""
    try:
        # Create currency record
        currency = UserCurrency(
            user_id=user.id,
            balance=STARTER_FLOOBITS,
            lifetime_earned=STARTER_FLOOBITS,
            lifetime_spent=0,
        )
        session.add(currency)

        # Log the starter bonus transaction
        tx = CurrencyTransaction(
            user_id=user.id,
            amount=STARTER_FLOOBITS,
            balance_after=STARTER_FLOOBITS,
            transaction_type='starter_bonus',
            description='Welcome bonus',
        )
        session.add(tx)

        # Give 5 base cards — one random card per position (QB, RB, WR, TE, K)
        baseTemplates = (
            session.query(CardTemplate)
            .filter_by(edition='base')
            .order_by(CardTemplate.season_created.desc())
            .all()
        )
        if baseTemplates:
            # Filter to only the latest season
            latestSeason = baseTemplates[0].season_created
            latestTemplates = [t for t in baseTemplates if t.season_created == latestSeason]

            # Group by position and pick one random card from each
            byPosition: dict[int, list] = {}
            for t in latestTemplates:
                byPosition.setdefault(t.position, []).append(t)

            picked = []
            for pos in range(1, 6):  # QB=1, RB=2, WR=3, TE=4, K=5
                candidates = byPosition.get(pos, [])
                if candidates:
                    picked.append(_random.choice(candidates))

            for template in picked:
                card = UserCard(
                    user_id=user.id,
                    card_template_id=template.id,
                    acquired_via='starter',
                )
                session.add(card)

        session.flush()
        logger.info(f"Provisioned starter pack for user {user.id}: {STARTER_FLOOBITS} Floobits + cards")
    except Exception as e:
        logger.warning(f"Failed to provision starter pack for user {user.id}: {e}")
        # Don't fail user creation if starter pack fails


# ---------------------------------------------------------------------------
# JWKS client (caches Clerk's public keys)
# ---------------------------------------------------------------------------

_jwksClient: Optional[PyJWKClient] = None


def _getJwksClient() -> PyJWKClient:
    global _jwksClient
    if _jwksClient is None:
        try:
            from config_manager import get_config
            jwksUrl = get_config().get('clerkJwksUrl', '')
        except Exception:
            jwksUrl = ''
        if not jwksUrl:
            jwksUrl = os.environ.get('CLERK_JWKS_URL', '')
        if not jwksUrl:
            raise RuntimeError("clerkJwksUrl not configured in config.json or CLERK_JWKS_URL env var")
        _jwksClient = PyJWKClient(jwksUrl)
    return _jwksClient


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def getCurrentUser(creds: HTTPAuthorizationCredentials = Depends(_bearerScheme)) -> User:
    """Verify Clerk JWT and return (or auto-create) the local User record."""
    credentialsException = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        signingKey = _getJwksClient().get_signing_key_from_jwt(creds.credentials)
        payload = pyjwt.decode(
            creds.credentials,
            signingKey.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        clerkUserId = payload.get("sub")
        if not clerkUserId:
            raise credentialsException
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"JWT verification failed: {e}")
        raise credentialsException

    # Look up or auto-provision local user
    session = get_session()
    try:
        user = session.query(User).filter(User.clerk_id == clerkUserId).first()
        if user is None:
            # Auto-provision: create local user record on first API call
            # Try to extract email from Clerk JWT claims
            email = payload.get("email", "")
            if not email:
                # Clerk sometimes nests email in different claim structures
                emailAddresses = payload.get("email_addresses", [])
                if emailAddresses and isinstance(emailAddresses, list):
                    email = emailAddresses[0].get("email_address", "")
            if not email:
                email = f"{clerkUserId}@clerk.user"
            else:
                email = email.lower().strip()

            username = _generateRandomUsername(session)
            user = User(
                clerk_id=clerkUserId,
                email=email,
                username=username,
                hashed_password="",
            )
            session.add(user)
            session.flush()  # Get user.id without committing yet

            # Provision starter currency (100 Floobits)
            _provisionStarterPack(session, user)

            session.commit()
            session.refresh(user)
            logger.info(f"Auto-provisioned user: clerk_id={clerkUserId}, email={email}, username={username}")
        else:
            # Existing user — update email if JWT now provides a real one
            jwtEmail = payload.get("email", "")
            if not jwtEmail:
                emailAddresses = payload.get("email_addresses", [])
                if emailAddresses and isinstance(emailAddresses, list):
                    jwtEmail = emailAddresses[0].get("email_address", "")
            if jwtEmail:
                jwtEmail = jwtEmail.lower().strip()
                if user.email != jwtEmail:
                    logger.info(f"Updating user email: {user.email} -> {jwtEmail}")
                    user.email = jwtEmail
                    session.commit()

        # Beta gate: if enabled, verify user's email is on the allowlist
        try:
            from config_manager import get_config
            betaEnabled = get_config().get("betaEnabled", False)
        except Exception:
            betaEnabled = False
        if betaEnabled:
            from sqlalchemy import func
            userEmail = user.email.lower().strip() if user.email else ""
            allowed = session.query(BetaAllowlist).filter(
                func.lower(BetaAllowlist.email) == userEmail
            ).first()
            if not allowed:
                logger.warning(f"Beta gate blocked user: email={user.email}, clerk_id={user.clerk_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Floosball is in closed beta. Your email is not on the allowlist.",
                )

        return user
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"User lookup/creation failed: {e}")
        raise credentialsException
    finally:
        session.close()
