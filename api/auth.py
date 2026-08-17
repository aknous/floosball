"""Clerk JWT verification for FastAPI."""

import os
import random as _random
import re as _re
from sqlalchemy import func as _func
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


# ─── User-chosen usernames ───────────────────────────────────────────────────
# Until now the only route to a username was picking one of four GENERATED candidates.
# The endpoint always accepted an arbitrary string — it was the frontend that only offered
# the picker — so opening it up is mostly about the rules that were never written.

USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 20
# ⚠️ A name may START with a digit or an underscore (owner, 2026-08-10). The rule used
# to demand a leading LETTER, which refused "_floosfan" and "99Problems" for no reason a
# reader could see. The character SET is unchanged — letters, digits and underscore — so
# nothing new arrives that could be used to build a lookalike out of punctuation.
_USERNAME_RE = _re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_]*$")

# Underscores and digits are stripped before the reserved-name check. Allowing them to
# lead re-opens the very impersonation route that list exists to close: "_admin",
# "admin_" and "_cassian_" all clear a plain membership test while reading in a feed as
# exactly the name they are imitating.
_RESERVED_STRIP_RE = _re.compile(r"[_0-9]+")

# Names nobody may take. Impersonation is the point: a user called "Cassian" posting in a
# feed that also carries real Cores lines is indistinguishable from the Core itself, and
# the same goes for anything that reads as staff.
USERNAME_RESERVED = {
    "admin", "administrator", "moderator", "mod", "staff", "system", "root",
    "floosball", "official", "support", "help", "null", "undefined", "anonymous",
    # The Cores (coresManager) — they speak in the same feeds users do.
    "cassian", "pyre", "aris", "halverson", "vera", "cores", "core",
}

# ─── Profanity ───────────────────────────────────────────────────────────────
# `better_profanity` does the heavy lifting (maintained wordlist, no dependencies), but it
# matches on WORD BOUNDARIES and a username has none. Measured on realistic handles it got
# 0 false positives — it clears every classic trap, Scunthorpe / Cockburn / Assassin /
# Analyst — but missed 4 in 10 abusive names, because `cuntpuncher` and `FUCKER99` are
# single tokens with no word for it to find. So it needs normalization in front of it, and
# a small substring list for the terms that survive being run together.
#
# ⚠️ THE SUBSTRING LIST IS DERIVED, NOT HAND-PICKED, and intuition gets it backwards.
# Checked against /usr/share/dict/words (236k words): `cunt` and `bitch` have ZERO innocent
# uses, while `nigg` has thirty — niggard, niggling, snigger are ordinary English. Using
# truncated roots is the trap; the full form `nigger` is unambiguous where `nigg` is not.
#
# ⚠️ Two rounds of a subtler bug are baked into these lists: THE DICTIONARY CONTAINS SLURS.
# Auto-building an exception list of "innocent words containing this term" hands the
# exception the very words being blocked — `nigger` became an excuse for `nigg`, and once
# that was filtered through better_profanity a second tier surfaced (niggerhead, niggertoe)
# that the library does not flag at all. Anything regenerated here must be eyeballed.

# Zero innocent dictionary words contain these, so a plain substring match is safe.
_PROFANITY_SUBSTRINGS = (
    "fuck", "cunt", "nigger", "faggot", "kike", "tranny", "wetback", "bitch",
    "molester", "pedophile", "dildo", "jizz", "bollock", "hitler",
)

# Substring-matched too, but each has a handful of genuine English words that contain it.
# Block only when none of the exceptions is present.
_PROFANITY_GUARDED = {
    "nigga": ("niggard",),
    "gook": ("gobbledygook",),
    "retarded": ("unretarded",),
    "wanker": ("swanker", "twanker"),
    # All obscure: -shite mineral and tribal names, plus shitepoke (a heron). None is a
    # plausible username, but they cost nothing to exempt and the alternative is a
    # confusing rejection for someone called Cushite.
    "shit": ("brushite", "cushite", "elkoshite", "girgashite", "kaneshite", "koreishite",
             "mackintoshite", "marshite", "bereshith", "shitepoke", "shita"),
}

# Leetspeak, so f4gg0t and n1gg3r normalize onto the lists above.
_LEET = str.maketrans({"1": "i", "0": "o", "3": "e", "4": "a", "5": "s",
                       "7": "t", "@": "a", "$": "s", "!": "i", "|": "i"})

# Proper nouns are absent from the dictionary, so the canonical traps are named directly.
# These are whole-name exemptions, not substrings.
_NAME_ALLOWLIST = {
    "scunthorpe", "penistone", "clitheroe", "lightwater", "cockburn", "hancock",
    "dickens", "cumberland", "bastardi", "spicer", "wangchuk", "assange",
}


def _normalizeForProfanity(name: str) -> str:
    """Lowercase, de-leet and strip everything that is not a letter.

    Separators are what defeat a wordlist on usernames: f_u_c_k and F.U.C.K are the same
    word with punctuation between the letters.
    """
    return _re.sub(r"[^a-z]", "", (name or "").lower().translate(_LEET))


def _segmentForProfanity(name: str) -> str:
    """Break a handle into something word-shaped so the library has boundaries to match.

    Splits camelCase and separators, so `TwatWaffle` reaches better_profanity as two words
    rather than one token it has never seen.
    """
    spaced = _re.sub(r"([a-z])([A-Z])", r"\1 \2", name or "")
    return " ".join(w for w in _re.split(r"[^A-Za-z]+", spaced) if w)


def containsProfanity(name: str) -> bool:
    """True when a username should be refused on language grounds."""
    normalized = _normalizeForProfanity(name)
    if not normalized or normalized in _NAME_ALLOWLIST:
        return False
    if any(term in normalized for term in _PROFANITY_SUBSTRINGS):
        return True
    for term, exceptions in _PROFANITY_GUARDED.items():
        if term in normalized and not any(ex in normalized for ex in exceptions):
            return True
    try:
        from better_profanity import profanity
        return bool(profanity.contains_profanity(_segmentForProfanity(name))
                    or profanity.contains_profanity(normalized))
    except Exception:
        # The substring tiers above already cover the worst of it; a missing or broken
        # dependency must not take the whole signup flow down with it.
        return False


# Fast membership for the generated-name check below. Built once — `_USERNAME_LASTS` is
# 260 entries and the check runs on every username submission.
_USERNAME_LASTS_SET = set(_USERNAME_LASTS)
# What the generator emits: a first, a last, and randint(1, 99) — so no leading zero.
_GENERATED_NAME_RE = _re.compile(r"^([A-Za-z]+)([1-9][0-9]?)$")


def isGeneratedUsername(name: str) -> bool:
    """True when `name` is one this server could have produced itself.

    Verified against the generator's OWN vocabulary rather than taken on trust from the
    client, so it cannot be used to smuggle an over-long custom name past the limit.

    Worst case is one pass over the 255 firsts, and only for names that already look like
    `WordWord42`.
    """
    match = _GENERATED_NAME_RE.match((name or "").strip())
    if not match:
        return False
    stem = match.group(1)
    for first in _USERNAME_FIRSTS:
        if stem.startswith(first) and stem[len(first):] in _USERNAME_LASTS_SET:
            return True
    return False


def validateUsername(name: str) -> tuple:
    """(cleanedName, errorMessage). errorMessage is None when the name is acceptable.

    Rules are deliberately narrow — letters, digits and underscores, starting with a
    letter. Anything wider (spaces, punctuation, unicode lookalikes) invites impersonation
    of other users and renders unpredictably in the places a name appears.
    """
    name = (name or "").strip()
    if not name:
        return None, "Username is required"
    if len(name) < USERNAME_MIN_LEN:
        return None, f"Username must be at least {USERNAME_MIN_LEN} characters"
    # ⚠️ THIS EXEMPTION IS GRANDFATHERING, NOT A LICENCE. The generator used to produce
    # names past the cap — 14,786 of its 66,300 pairings do — and auto-provisioning
    # handed them out at signup, so 36 of production's 157 named users (23%) carry one
    # they never chose. Rejecting those names now would lock a fifth of the user base out
    # of their own identity, so a name this server could have produced stays valid.
    #
    # It is NOT the fix for the generator. `_usernameSuggestionRejected` now screens
    # length at the source, so nothing new arrives over the cap; the exemption only ever
    # covers what was already handed out. It also never worked as a fix, because the
    # onboarding client applies the plain rule to a clicked suggestion and the request
    # never reached this function.
    if len(name) > USERNAME_MAX_LEN and not isGeneratedUsername(name):
        return None, f"Username must be {USERNAME_MAX_LEN} characters or fewer"
    if not _USERNAME_RE.match(name):
        return None, "Use letters, numbers and underscores"
    lowered = name.lower()
    if lowered in USERNAME_RESERVED or _RESERVED_STRIP_RE.sub("", lowered) in USERNAME_RESERVED:
        return None, "That name is reserved"
    if containsProfanity(name):
        return None, "That name is not available"
    return name, None


def usernameTaken(session, name: str, excludeUserId: int = None) -> bool:
    """Case-INSENSITIVE uniqueness.

    The column's unique constraint is case-sensitive, so without this "Andrew" and
    "andrew" are two different accounts — which is an impersonation route, not a
    convenience. Checked in Python rather than with a functional index so it behaves the
    same on the SQLite prod DB as it does locally.
    """
    lowered = (name or "").lower()
    q = session.query(User).filter(_func.lower(User.username) == lowered)
    if excludeUserId is not None:
        q = q.filter(User.id != excludeUserId)
    return q.first() is not None


def _usernameSuggestionRejected(name: str) -> bool:
    """Would we refuse a name we just offered? Then do not offer it.

    ⚠️ ONE FUNCTION, DELIBERATELY. The two generators below used to carry their own
    copies of this screening, and that is exactly how the length rule went missing:
    profanity was added to both, length to neither, so 22% of suggestions were names
    the app proposed and the app then rejected.

    * PROFANITY — two of the 66,300 pairings trip the filter (SaskatchewanKerfuffle
      spans "wanker" across the join), so rare rather than theoretical.
    * LENGTH — 14,786 of the 66,300 pairings run past USERNAME_MAX_LEN. The server
      grandfathers those (see `validateUsername`), but the ONBOARDING CLIENT applies
      the plain rule to every path including a clicked suggestion, so an over-long
      offer showed "20 characters or fewer" and the pick never left the browser. The
      server exemption could not help: nothing was ever sent.
    """
    return len(name) > USERNAME_MAX_LEN or containsProfanity(name)


def _rollUsername() -> str:
    """One raw pairing from the vocabulary. Not screened, not checked for uniqueness."""
    return (
        _random.choice(_USERNAME_FIRSTS)
        + _random.choice(_USERNAME_LASTS)
        + str(_random.randint(1, 99))
    )


def generateUsernameCandidates(session, count: int = 4) -> list[str]:
    """Unique username candidates like 'CrispyKerfuffle42', each verified against the DB.

    THE single implementation — `_generateUsernameCandidate` delegates here rather than
    keeping a second copy of the rules. Roughly a fifth of pairings are screened out, so
    the retry budget is generous rather than tight.
    """
    candidates = []
    seen = set()
    for _ in range(count * 20):
        name = _rollUsername()
        if name in seen:
            continue
        seen.add(name)
        if _usernameSuggestionRejected(name):
            continue
        if session.query(User).filter(User.username == name).first():
            continue
        candidates.append(name)
        if len(candidates) >= count:
            break
    return candidates


def _generateUsernameCandidate(session) -> str:
    """A single unique username, for auto-provisioning and the admin re-roll."""
    candidates = generateUsernameCandidates(session, count=1)
    if candidates:
        return candidates[0]
    # Extremely unlikely fallback
    return "Player" + str(_random.randint(10000, 99999))


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

        # Log the starter bonus transaction.
        # ⚠️ Stamp the season. This row is built directly rather than through
        # `CurrencyRepository.addFunds`, so it does not get that method's season
        # default — and 185 of these landed on production with `season = NULL`,
        # 18,400F that counted toward no season's faucet and so quietly discounted
        # every team's facilities. See addFunds for the wider undercount.
        from database.repositories.card_repositories import CurrencyRepository
        tx = CurrencyTransaction(
            user_id=user.id,
            amount=STARTER_FLOOBITS,
            balance_after=STARTER_FLOOBITS,
            transaction_type='starter_bonus',
            description='Welcome bonus',
            season=CurrencyRepository(session)._currentSeasonNumber(),
        )
        session.add(tx)

        # Fusion: the starter gives the no-effect FLOOR lineup — one 'base' card
        # per lineup slot (QB/RB/WR/WR/TE/K — two WR cards for WR1 + WR2) — so every
        # user can field a legal lineup on day one and earns effect cards from
        # packs/play. Fall back to metallic only if no floor templates exist yet
        # (partially-migrated DB).
        baseTemplates = (
            session.query(CardTemplate)
            .filter_by(edition='base')
            .order_by(CardTemplate.season_created.desc())
            .all()
        )
        if not baseTemplates:
            baseTemplates = (
                session.query(CardTemplate)
                .filter_by(edition='metallic')
                .order_by(CardTemplate.season_created.desc())
                .all()
            )
        if baseTemplates:
            # Filter to only the latest season
            latestSeason = baseTemplates[0].season_created
            latestTemplates = [t for t in baseTemplates if t.season_created == latestSeason]

            # Group by position and pick one card per lineup slot — guaranteeing the
            # starter covers all six base slots (two WR for WR1 + WR2) with no
            # duplicate player and no duplicate effect (so the whole set is equippable
            # at once). Distinct players is enforced via usedPlayers; effect-dedup
            # only matters on the base fallback (standard cards are all effect 'none',
            # which is exempt from the no-duplicate-effect rule anyway).
            from managers.cardManager import _STARTER_SLOT_COUNTS
            byPosition: dict[int, list] = {}
            for t in latestTemplates:
                byPosition.setdefault(t.position, []).append(t)

            def _effName(t):
                e = (t.effect_config or {}).get('effectName') or ''
                return e if e and e != 'none' else None

            picked = []
            usedPlayers: set = set()
            usedEffects: set = set()
            for pos, count in _STARTER_SLOT_COUNTS:  # (position, how many cards)
                candidates = list(byPosition.get(pos, []))
                _random.shuffle(candidates)
                if not candidates:
                    logger.warning(f"Starter pack: no card available for position {pos}")
                    continue
                for _ in range(count):
                    chosen = next(
                        (t for t in candidates
                         if t.player_id not in usedPlayers
                         and (_effName(t) is None or _effName(t) not in usedEffects)),
                        None,
                    )
                    # Fall back to any not-yet-picked candidate if every one collided.
                    if chosen is None:
                        chosen = next((t for t in candidates if t.player_id not in usedPlayers),
                                      candidates[0])
                    picked.append(chosen)
                    usedPlayers.add(chosen.player_id)
                    if _effName(chosen):
                        usedEffects.add(_effName(chosen))

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
                    # ⚠️ A username is GENERATED here, not left null.
                    #
                    # It used to be None, and the only thing that ever filled it was the
                    # onboarding modal's first step. With that modal gone (the closed beta
                    # is over and the forced flow with it), a null would have followed the
                    # user forever — every leaderboard row and feed post reading "someone".
                    #
                    # They can still choose their own: `POST /api/users/me/username` takes
                    # a rename once per season, and the first pick does not count as one.
                    user = User(
                        clerk_id=clerkUserId,
                        email=email,
                        username=_generateUsernameCandidate(session),
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

        # ⚠️ HAND BACK A USABLE OBJECT.
        #
        # `session.commit()` above EXPIRES every attribute on the instance (SQLAlchemy's
        # `expire_on_commit` defaults to True), and the `finally` below CLOSES the
        # session. The User returned was therefore detached AND expired, so the first
        # `user.id` in any endpoint tried to lazy-load from a dead session and raised
        # DetachedInstanceError.
        #
        # It went unnoticed because the beta gate read `user.email` a few lines up, INSIDE
        # the still-open session — that access quietly reloaded the expired row and left
        # the instance populated. Turning the gate off (the closed beta is over) removed
        # the accidental refresh and the latent bug surfaced immediately, on
        # GET /api/games/{id}/rally.
        #
        # refresh() repopulates, expunge() detaches deliberately with the values intact.
        try:
            session.refresh(user)
            session.expunge(user)
        except Exception:
            # A user we cannot refresh is still better returned than not — the endpoints
            # that only read already-loaded fields will work.
            pass
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
