"""Contract length by tier — `playerManager._getPlayerTerm`.

⚠️ THE STAR DEALS WERE ORPHANED. They were shortened to 2-3 seasons to feed a
retention ratchet (first the salary cap, scratched; then the re-sign-once limit,
disabled 2026-08-13). Both are gone and the deals were not revisited — measured
on production, no player in the league held a contract longer than 3 seasons and
a 96-rated star was on a 2-year deal.

Term is also what carries `seasonsOfControl` in the trade valuation, so a league
where every star is permanently near his walk year is a league where the best
players are permanently the cheapest. See docs/TRADING_PLAN.md §8.
"""

import random

from managers.playerManager import PlayerManager
import floosball_player as FloosPlayer


class FakeAttrs:
    def __init__(self, longevity):
        self.longevity = longevity


class FakePlayer:
    """Exactly what _getPlayerTerm reads: tier, seasons played, longevity."""

    def __init__(self, tier, seasonsPlayed=4, longevity=14):
        self.playerTier = tier
        self.seasonsPlayed = seasonsPlayed
        self.attributes = FakeAttrs(longevity)


def _term(tier, seasonsPlayed=4, longevity=14):
    # _getPlayerTerm touches no instance state, so it runs unbound.
    return PlayerManager._getPlayerTerm(None, FakePlayer(tier, seasonsPlayed, longevity))


def _spread(tier, n=400, **kw):
    random.seed(11)
    return sorted({_term(tier, **kw) for _ in range(n)})


# ------------------------------------------------------- veteran deals

def test_star_veterans_get_long_deals():
    """S is 4-6 and A is 3-4 — the values the comment says were there before."""
    assert _spread(FloosPlayer.PlayerTier.TierS) == [4, 5, 6]
    assert _spread(FloosPlayer.PlayerTier.TierA) == [3, 4]
    print("PASS veteran star deals: S 4-6, A 3-4")


def test_lower_tiers_untouched():
    """Only S and A moved. B/C roll 1-3 and D is a one-year deal, as before —
    ⚠️ this is what keeps the walk-year market alive: most contract congestion
    is B/C tier and this change must not touch it."""
    assert _spread(FloosPlayer.PlayerTier.TierB) == [1, 2, 3]
    assert _spread(FloosPlayer.PlayerTier.TierC) == [1, 2, 3]
    assert _spread(FloosPlayer.PlayerTier.TierD) == [1]
    print("PASS B/C still 1-3, D still 1")


def test_a_star_can_exceed_three_seasons():
    """The headline symptom: prod's longest contract in the league was 3."""
    assert max(_spread(FloosPlayer.PlayerTier.TierS)) > 3
    assert max(_spread(FloosPlayer.PlayerTier.TierA)) > 3
    print("PASS a star can be signed past 3 seasons")


# ------------------------------------------------------- the clamps

def test_runway_clamp_still_bites():
    """A deal never runs well past expected retirement. An aged star with two
    seasons of runway left gets the floor, not a six-year deal."""
    aged = _spread(FloosPlayer.PlayerTier.TierS, seasonsPlayed=13, longevity=14)
    assert aged == [3], aged            # floor 3, runway would have given 2
    agedB = _spread(FloosPlayer.PlayerTier.TierB, seasonsPlayed=13, longevity=14)
    assert agedB == [1, 2], agedB
    print("PASS runway clamp survives the longer rolls")


def test_tier_s_floor_is_three():
    """⚠️ The floor moved with the roll and they have to move together: a
    2-season floor under a 4-6 roll would let an aged hall-of-famer sign for
    less than a B-tier journeyman's best year."""
    onlyOneYearLeft = _term(FloosPlayer.PlayerTier.TierS, seasonsPlayed=20, longevity=14)
    assert onlyOneYearLeft == 3
    print("PASS TierS floor restored to 3")


# ------------------------------------------------------- rookie deals

def test_rookie_deal_is_unchanged():
    """⚠️ DELIBERATELY NOT RESTORED. The first-contract branch is a prove-it
    deal regardless of tier — it predates the shortening and exists so a
    diamond prospect does not get six years before playing a snap."""
    assert _spread(FloosPlayer.PlayerTier.TierS, seasonsPlayed=0) == [3]
    assert _spread(FloosPlayer.PlayerTier.TierA, seasonsPlayed=0) == [3]
    assert _spread(FloosPlayer.PlayerTier.TierB, seasonsPlayed=0) == [2]
    assert _spread(FloosPlayer.PlayerTier.TierD, seasonsPlayed=0) == [1]
    print("PASS rookie prove-it deals unchanged")
