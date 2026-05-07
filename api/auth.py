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
_optionalBearerScheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Random username generation
# ---------------------------------------------------------------------------

_USERNAME_FIRSTS = [
    # Original
    "Bootleg", "Moist", "Cornbread", "Squids", "Gootsy",
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
    # Expanded II
    "Counterfeit", "Derelict", "Makeshift", "Undercover", "Stranded",
    "Smoked", "Grizzled", "Smuggled", "Mothballed", "Prototype",
    "Generic", "Irregular", "Drafted", "Rebooted", "Cardboard",
    "Corduroy", "Thermos", "Turnip", "Custard", "Sourdough",
    "Burlap", "Disputed", "Dormant", "Stealthy", "Pilfered",
    "Fossilized", "Misplaced", "Nomadic", "Freelance", "Ransacked",
    "Fugitive", "Sketchy", "Crooked", "Placebo", "Decaf",
    "Standby", "Borrowed", "Stray", "Rented", "Botched",
    "Crunchy", "Soggy", "Tepid", "Stuffy", "Musty",
    "Gnarled", "Wobbly", "Janky", "Clunky", "Grimy",
    # Expanded III
    "Refurbished", "Artisanal", "Disgruntled", "Provisional", "Condemned",
    "Impounded", "Overclocked", "Undercooked", "Petrified", "Quarantined",
    "Geriatric", "Prehistoric", "Dubious", "Infamous", "Wayward",
    "Delinquent", "Ornamental", "Remedial", "Curbside", "Fermented",
    "Broiled", "Charred", "Peppered", "Archaic", "Peculiar",
    "Reckless", "Vagrant", "Honorary", "Interim", "Auxiliary",
    "Forfeited", "Embargoed", "Suspended", "Expired", "Sanctioned",
    "Defective", "Unverified", "Classified", "Redacted", "Restricted",
    "Armored", "Confiscated", "Repossessed", "Unclaimed",
    # Expanded IV — config-name style: object/material as descriptor,
    # mythological singletons, archaic titles, place-as-name, edible adj.
    "Plywood", "Linoleum", "Stucco", "Vellum", "Velour", "Pleather",
    "Chamois", "Parchment", "Lacquer", "Enamel", "Brocade", "Toadstool",
    "Frosted", "Buttered", "Glazed", "Salted", "Steamed", "Pungent",
    "Crusty", "Velvety", "Greasy", "Crinkly", "Smudgy", "Tangled",
    "Lopsided", "Wonky", "Threadbare", "Mottled", "Speckled", "Blotchy",
    "Spongy", "Rubbery", "Squidgy", "Mushy", "Brackish", "Dingy",
    "Sergeant", "Captain", "Magistrate", "Cardinal", "Duchess", "Baron",
    "Viscount", "Bishop", "Constable", "Pharaoh", "Czar", "Brother",
    "Sister", "Grandmaster", "Grand", "Admiral", "Idaho", "Tulsa",
    "Hoboken", "Nantucket", "Sacramento", "Bavaria", "Saskatchewan",
    "Toledo", "Topeka", "Fresno", "Fondue", "Schnitzel", "Frittata",
    "Pierogi", "Goulash", "Tamale", "Empanada", "Knish", "Latke",
    "Rigatoni", "Anubis", "Beowulf", "Crassus", "Jezebel", "Spacepope",
    "Hercules", "Atlas", "Hermes", "Persephone", "Werewolf", "Penguin",
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
    # Expanded II
    "Crankshaw", "Mudflap", "Thudsworth", "Bonkerton", "Plunkett",
    "Grumbleton", "Stumpton", "Crumbles", "Clodhopper", "Turnbuckle",
    "Hogwash", "Codswallop", "Balderdash", "Poppycock", "Flimflam",
    "Riffraff", "Skullduggery", "Chicanery", "Treachery", "Quibble",
    "Shambles", "Bungle", "Fumbles", "Bloopers", "Guffaw",
    "Snafu", "Hootenanny", "Ruckus", "Fracas", "Hubbub",
    "Mudslinger", "Dropkick", "Brickhouse", "Sledgehammer", "Anvil",
    "Crowbar", "Pickaxe", "Sandbag", "Haymaker", "Uppercut",
    "Corkscrew", "Wrenchford", "Crankshaft", "Sprocket", "Gasket",
    "Gearbox", "Camshaft", "Flywheel", "Axlegrease", "Dipstick",
    # Expanded III
    "Thunderclap", "Dustpan", "Breadstick", "Doorknob", "Chowderhead",
    "Drawbridge", "Catapult", "Windmill", "Scaffolding", "Cannonball",
    "Wheelbarrow", "Filibuster", "Bureaucrat", "Armistice", "Turnstile",
    "Fishstick", "Meatloaf", "Tenderfoot", "Doohickey", "Thingamajig",
    "Contraption", "Whirligig", "Buckshot", "Portcullis", "Cobblestone",
    "Dumbwaiter", "Clothesline", "Cheapshot", "Trainwreck", "Carbuncle",
    "Blunderbuss", "Curveball", "Piledriver", "Steamroller", "Wrecking",
    "Jackhammer", "Crowsnest", "Tumblebum", "Hornblower", "Frogmouth",
    "Jetsam", "Nightcap", "Gutterball", "Pratfall", "Sideburns",
    "Potluck", "Corkboard", "Thumbtack", "Paperweight", "Sockpuppet",
    # Expanded IV — config-name style: Wodehousian surnames, Italianate
    # romance, mock-bureaucratic, weather/edible mashups, kerfuffle-class.
    "Throckmorton", "Pemberton", "Snickerton", "Pottersworth", "Wickerby",
    "Hardcastle", "Snufflesworth", "Cresswell", "Pondworth", "Snufflebee",
    "Wadsworth", "Mulligrub", "Pumblechook", "Hardacre", "Hocknell",
    "Throgshire", "Twaddle", "Lordling", "Snortlebottom", "Mortimer",
    "Mortadella", "Provolone", "Bruschetta", "Caponata", "Limoncello",
    "Bolognese", "Carbonara", "Risotto", "Gnocchi", "Ravioli",
    "Calzone", "Cannoli", "Tortellini", "Espresso", "Mascarpone",
    "Doorbell", "Mailbox", "Streetlamp", "Manhole", "Saltshaker",
    "Pepperpot", "Coatrack", "Doormat", "Floorboard", "Doorhinge",
    "Thunderhead", "Snowdrift", "Slushpile", "Cloudburst", "Heatwave",
    "Bratwurst", "Sauerkraut", "Cheesecurd", "Marshmallow", "Custardpie",
    "Conundrum", "Quandary", "Skirmish", "Pandemonium", "Calamity",
    "Kerplunk", "Ballyhoo", "Befuddlement", "Bafflement", "Dispute",
    "Stipulation", "Memorandum", "Affidavit", "Loophole", "Indictment",
    "Suplex", "Powerbomb", "Bodyslam", "Headlock", "Pinkerton",
    "Spectacles", "Hollyhock", "Pickleweed", "Bumblefiddle", "Periwinkle",
]


def _generateUsernameCandidate(session) -> str:
    """Generate a single unique random username like 'CrispyKerfuffle42'."""
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


def generateUsernameCandidates(session, count: int = 4) -> list[str]:
    """Generate multiple unique username candidates, each verified against the DB."""
    candidates = []
    seen = set()
    for _ in range(count * 10):  # generous retry budget
        name = (
            _random.choice(_USERNAME_FIRSTS)
            + _random.choice(_USERNAME_LASTS)
            + str(_random.randint(1, 99))
        )
        if name in seen:
            continue
        seen.add(name)
        existing = session.query(User).filter(User.username == name).first()
        if not existing:
            candidates.append(name)
            if len(candidates) >= count:
                break
    return candidates


STARTER_FLOOBITS = 100
STARTER_CARD_COUNT = 5


def _provisionStarterPack(session, user, currentSeason: Optional[int] = None):
    """Give a new user starter Floobits and 5 random base cards.

    Also marks `starter_pack_claimed_season` to the current season so the
    in-shop "Claim Free Pack" offer is hidden — they've already been given
    the equivalent at signup. The shop offer naturally re-enables next
    season when the season number advances.

    currentSeason can be passed explicitly when the caller knows it
    (e.g. seasonManager during fresh-start reprovision); otherwise we
    fall back to reading floosball_app.seasonManager.  This matters at
    boot because seasonManager runs reprovision BEFORE the api.main
    floosball_app reference is set.
    """
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

        # Mark this season as already-claimed so the in-shop starter offer
        # doesn't show for the rest of season N.
        if currentSeason is None:
            try:
                from api import main as _apiMain
                sm = getattr(getattr(_apiMain, 'floosball_app', None), 'seasonManager', None)
                currentSeason = sm.currentSeason.seasonNumber if sm and sm.currentSeason else None
            except Exception:
                currentSeason = None
        if currentSeason is not None:
            user.starter_pack_claimed_season = currentSeason

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
            # Extract email from JWT claims
            email = payload.get("email", "")
            if not email:
                emailAddresses = payload.get("email_addresses", [])
                if emailAddresses and isinstance(emailAddresses, list):
                    email = emailAddresses[0].get("email_address", "")
            if not email:
                email = f"{clerkUserId}@clerk.user"
            else:
                email = email.lower().strip()

            # Check if existing user with this email (Clerk instance migration)
            from sqlalchemy import func
            existingByEmail = session.query(User).filter(
                func.lower(User.email) == email.lower()
            ).first()

            if existingByEmail:
                # Migrating from dev→prod Clerk: update clerk_id
                oldClerkId = existingByEmail.clerk_id
                existingByEmail.clerk_id = clerkUserId
                session.commit()
                session.refresh(existingByEmail)
                logger.info(f"Migrated Clerk ID for user {existingByEmail.id}: {oldClerkId} -> {clerkUserId}")
                user = existingByEmail
            else:
                # Truly new user — auto-provision. First-login browsers fire several
                # /api/* calls in parallel, so two threads can both miss the existing-
                # user lookup above and both try to INSERT. Handle the race by catching
                # the unique-constraint violation and re-reading the row the other
                # thread just wrote.
                from sqlalchemy.exc import IntegrityError
                try:
                    user = User(
                        clerk_id=clerkUserId,
                        email=email,
                        username=None,
                        hashed_password="",
                    )
                    session.add(user)
                    session.flush()

                    _provisionStarterPack(session, user)

                    session.commit()
                    session.refresh(user)
                    logger.info(f"Auto-provisioned user: clerk_id={clerkUserId}, email={email} (username pending)")
                except IntegrityError:
                    session.rollback()
                    user = session.query(User).filter(User.clerk_id == clerkUserId).first()
                    if user is None:
                        # Not a clerk_id conflict — surface the original error
                        raise
                    logger.info(f"Lost provisioning race for clerk_id={clerkUserId} — using existing row id={user.id}")
        else:
            # Existing user — update email if JWT now provides a real one
            jwtEmail = payload.get("email", "")
            if not jwtEmail:
                emailAddresses = payload.get("email_addresses", [])
                if emailAddresses and isinstance(emailAddresses, list):
                    jwtEmail = emailAddresses[0].get("email_address", "")
            needsCommit = False
            if jwtEmail:
                jwtEmail = jwtEmail.lower().strip()
                if user.email != jwtEmail:
                    logger.info(f"Updating user email: {user.email} -> {jwtEmail}")
                    user.email = jwtEmail
                    needsCommit = True
            # Stamp last login + record today's DAU bucket. UserLoginDay
            # has a unique (user_id, login_date) constraint so re-logins
            # within the same day collapse into one row, but each new
            # calendar day gets its own row — that's what makes the
            # admin DAU chart historically stable.
            from datetime import datetime as _dt
            now = _dt.utcnow()
            user.last_login_at = now
            needsCommit = True
            try:
                from database.models import UserLoginDay
                from sqlalchemy.dialects.sqlite import insert as _sqlite_insert
                stmt = _sqlite_insert(UserLoginDay).values(
                    user_id=user.id,
                    login_date=now.date(),
                ).on_conflict_do_nothing(
                    index_elements=['user_id', 'login_date']
                )
                session.execute(stmt)
            except Exception as e:
                logger.warning(f"Failed to record UserLoginDay for {user.id}: {e}")
            if needsCommit:
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


def getOptionalUser(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optionalBearerScheme),
) -> Optional[User]:
    """Return the authenticated User if a valid token is present, else None."""
    if creds is None:
        return None
    try:
        return getCurrentUser(creds)
    except Exception:
        return None


def getAdminUser(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_optionalBearerScheme),
) -> Optional[User]:
    """Return the authenticated User only if they have is_admin=True, else None.

    Does NOT raise — allows downstream code to fall back to password auth.
    """
    if creds is None:
        logger.debug("getAdminUser: no credentials provided")
        return None
    try:
        user = getCurrentUser(creds)
        if user and getattr(user, 'is_admin', False):
            logger.debug(f"getAdminUser: admin user authenticated: {user.id} ({user.email})")
            return user
        if user:
            logger.warning(f"getAdminUser: user {user.id} ({user.email}) is not admin (is_admin={user.is_admin})")
        return None
    except Exception as e:
        logger.warning(f"getAdminUser: auth failed: {e}")
        return None
