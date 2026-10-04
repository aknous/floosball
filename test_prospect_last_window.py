"""A prospect's LAST development window — the promotion bar, the cut-to-make-room
fallback, and where the washout release sits in the offseason.

Three separate faults, one story. A bottom-feeder drafts the headline prospect,
develops him for three seasons, and:

  1. loses him for nothing because its slot at his position happened to be filled
     (`_findOpenSlotForPosition` returned None and the loop just `continue`d), or
  2. loses him because the GM compared him to a free agent it could sign — on the
     final window that is the WRONG ALTERNATIVE, because he walks either way, or
  3. gets him back into the pool 53 lines too late to be draftable, so he idles a
     whole extra season while the supply floor generates a replacement he could
     have been.

See docs/TRADING_PLAN.md §4 and docs/PROSPECT_DRAFT_PLAN.md §2b.
"""

import re

from constants import (PROSPECT_DEVELOPMENT_WINDOW, CUT_FEE_RATE,
                       REPLACEMENT_RATING, FO_CUT_UPGRADE_MARGIN)
from managers.frontOfficeBrain import cutFeeFor
from managers.seasonManager import SeasonManager


# --------------------------------------------------- the window predicate

class FakeProspect:
    def __init__(self, seasons):
        self.prospect_seasons = seasons


def test_final_window_is_the_season_before_release():
    """⚠️ THE OFF-BY-ONE IS THE POINT. `_advanceProspectWindow` INCREMENTS first and
    then releases at >= WINDOW, and it runs immediately after the promotions pass.
    So the last chance belongs to a prospect sitting on WINDOW-1; testing >= WINDOW
    would fire only on someone already gone."""
    last = PROSPECT_DEVELOPMENT_WINDOW - 1
    assert SeasonManager._isFinalProspectWindow(FakeProspect(last)) is True
    for earlier in range(0, last):
        assert SeasonManager._isFinalProspectWindow(FakeProspect(earlier)) is False, earlier
    print(f"PASS final window fires at prospect_seasons == {last}, not before")


def test_a_fresh_prospect_is_not_on_his_last_chance():
    """The old bar has to survive every earlier window — there IS a next year then,
    and promoting a project player over a better free agent is the failure the
    FO_PROSPECT_PROMOTE_EDGE bar exists to prevent."""
    assert SeasonManager._isFinalProspectWindow(FakeProspect(0)) is False
    print("PASS a fresh prospect still faces the free-agent bar")


# --------------------------------------------------- the cut fee

class FakePlayer:
    def __init__(self, rating, termRemaining):
        self.playerRating = rating
        self.termRemaining = termRemaining


def test_cut_fee_reproduces_the_priced_table():
    """The three rows the fee was sized against (docs/TRADING_PLAN.md §3.7)."""
    assert cutFeeFor(FakePlayer(72, 1)) == 250
    assert cutFeeFor(FakePlayer(84, 2)) == 1700
    assert cutFeeFor(FakePlayer(96, 3)) == 4350
    print("PASS cut fee: 250F / 1,700F / 4,350F")


def test_cut_fee_is_floored_at_zero_never_a_debt():
    """⚠️ A club that cannot pay cannot cut. If the fee could go NEGATIVE a broke
    club would have unlimited roster churn — the opposite of the intent — and
    cutting would become a way to EARN Treasury."""
    assert cutFeeFor(FakePlayer(REPLACEMENT_RATING, 3)) == 0     # at replacement
    assert cutFeeFor(FakePlayer(40, 3)) == 0                     # far below it
    assert cutFeeFor(FakePlayer(99, 0)) == 0                     # no term left
    assert cutFeeFor(None) == 0
    assert all(cutFeeFor(FakePlayer(r, t)) >= 0
               for r in range(40, 101, 3) for t in range(0, 7))
    print("PASS fee floored at zero for every rating x term")


def test_cut_fee_scales_with_control_not_just_talent():
    """Both terms are load-bearing: the fee prices what is being THROWN AWAY, so
    four years of an elite player costs far more than one year of the same man."""
    oneYear = cutFeeFor(FakePlayer(90, 1))
    fourYear = cutFeeFor(FakePlayer(90, 4))
    assert fourYear == 4 * oneYear
    assert cutFeeFor(FakePlayer(90, 2)) > cutFeeFor(FakePlayer(80, 2))
    print("PASS fee scales with both seasons of control and surplus")


# ------------------------------------------- the offseason ordering

def _seasonManagerSource():
    import managers.seasonManager as sm
    return open(sm.__file__).read()


def test_washout_release_runs_before_the_fa_draft():
    """⚠️ THE ORDERING IS THE FIX, so it is asserted positionally on the source.

    A washout released AFTER `_processFreeAgency` is unsignable until the NEXT
    offseason. Worse, `ensurePositionSupply` runs before the draft and excludes
    prospects, so it generates a fresh free agent for the very hole he could have
    filled: the league gains a body it did not need and he goes unused."""
    src = _seasonManagerSource()
    release = src.index('self.playerManager._advanceProspectWindow()')
    faDraft = src.index('await self._processFreeAgency()')
    supply = src.index("_ensurePositionSupply(reason='pre-FA-draft guarantee'")
    predraft = src.index('await self._runPreDraftPass(faOrderForPredraft, gmResults)')

    assert release < faDraft, "washout release still runs after the FA draft"
    assert release < supply, "supply floor still tops up before the release"
    assert predraft < release, "release must follow the promotions pass — the last " \
                               "chance has to happen before he is let go"
    print("PASS ordering: promotions -> release -> supply floor -> FA draft")


def test_only_one_call_site_moved_not_copied():
    """A second surviving call would age every prospect twice."""
    src = _seasonManagerSource()
    assert src.count('self.playerManager._advanceProspectWindow()') == 1
    print("PASS exactly one _advanceProspectWindow call site")


def test_the_release_is_step_gated():
    """⚠️ NON-NEGOTIABLE. Where it used to sit it was covered by
    `training_and_finalize`; here it is not, and it INCREMENTS. An unguarded re-run
    on a restart ages every prospect twice and washes out a class a season early —
    and the offseason is exactly where this project's restarts land."""
    src = _seasonManagerSource()
    block = src[src.index('# STEP 3.78'):src.index('self.playerManager._advanceProspectWindow()')]
    assert "_isOffseasonStepComplete('prospect_window')" in block
    tail = src[src.index('self.playerManager._advanceProspectWindow()'):]
    assert "_markOffseasonStepComplete('prospect_window')" in tail[:2000]
    print("PASS release is gated on the prospect_window step marker")


# ------------------------------------- the promotion loop, behaviourally
#
# ⚠️ The predicate tests above prove the RULE; these prove the LOOP CONSULTS IT.
# A correct `_isFinalProspectWindow` wired to nothing passes everything above.

from floosball_player import Position


class FakeBrainPlayer:
    def __init__(self, name, rating, position=Position.QB, termRemaining=3):
        self.name = name
        self.playerRating = rating
        self.position = position
        self.termRemaining = termRemaining
        self.willRetire = False
        self.prospect_seasons = 0
        self.is_prospect = True
        self.drafting_team_id = 7
        self.team = 'Prospect'

    @property
    def playerTier(self):
        class T:
            name = 'TierB'
        return T()

    def computeExpectedRating(self):
        return self.playerRating

    def computeCeilingRating(self):
        return self.playerRating


class StubBrain:
    """decisionValue is the player's rating; the replacement bar is a knob."""

    def __init__(self, replacement=0.0):
        self.replacement = replacement

    def decisionValue(self, player, coach=None, rng=None, team=None):
        return float(player.playerRating)

    def bestReplacementValue(self, player, coach=None, pool=None, rng=None,
                             pickDepth=0, team=None):
        return self.replacement

    def faPickDepth(self, team, faOrder=None):
        return 0


class StubTeam:
    def __init__(self, roster, prospects, name='Slippers'):
        self.name = name
        self.id = 7
        self.rosterDict = roster
        self.prospects = prospects
        self.coach = None

    def assignPlayerNumber(self, player):
        pass


class StubPlayerManager:
    def __init__(self):
        self.freeAgents = []
        self.released = []

    def _findOpenSlotForPosition(self, team, positionValue):
        posSlots = {1: ['qb'], 2: ['rb'], 3: ['wr1', 'wr2'], 4: ['te'], 5: ['k']}
        for slot in posSlots.get(positionValue, []):
            if team.rosterDict.get(slot) is None:
                return slot
        return None

    def _getPlayerTerm(self, player):
        return 3

    def releasePlayerToFreeAgency(self, player, team, freeAgentLists):
        for slot, rostered in list(team.rosterDict.items()):
            if rostered is player:
                team.rosterDict[slot] = None
        self.released.append(player)


class StubSeason:
    freeAgencyOrder = []
    leagueHighlights = []


class StubSM:
    """Just enough SeasonManager to run the promotion loop."""

    def __init__(self, brain, playerManager, treasury=1_000_000):
        self._brain = brain
        self.playerManager = playerManager
        self.currentSeason = StubSeason()
        self.treasury = treasury
        self.charged = []

    def _foBrainForOffseason(self):
        return self._brain

    # ⚠️ re-wrapped: reading a staticmethod off the class yields a plain
    # function, which a class body would rebind as an instance method.
    _isFinalProspectWindow = staticmethod(SeasonManager._isFinalProspectWindow)
    _cutToMakeRoomForProspect = SeasonManager._cutToMakeRoomForProspect
    _cutPlanForProspect = SeasonManager._cutPlanForProspect
    _executeProspectCut = SeasonManager._executeProspectCut
    _promoteProspectsAutonomously = SeasonManager._promoteProspectsAutonomously

    def _recordOffseasonEvent(self, *a, **kw):
        pass

    def _chargeCutFee(self, team, fee):
        if fee > self.treasury:
            return False
        self.treasury -= fee
        self.charged.append(fee)
        return True


LAST = PROSPECT_DEVELOPMENT_WINDOW - 1


def test_last_window_promotes_past_the_free_agent_bar():
    """⚠️ THE BAR IS THE WRONG COMPARISON ON THE FINAL WINDOW. He walks either way,
    so the club is choosing between him and an EMPTY SLOT (which rates 50), not
    between him and a free agent it could sign."""
    prospect = FakeBrainPlayer('Headliner', 74)
    prospect.prospect_seasons = LAST
    team = StubTeam({'qb': None, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1}, [prospect])
    # A far better free agent is available — under the old rule he stays down.
    sm = StubSM(StubBrain(replacement=200.0), StubPlayerManager())
    promotions = sm._promoteProspectsAutonomously(team)
    assert [p['name'] for p in promotions] == ['Headliner']
    assert team.rosterDict['qb'] is prospect
    assert prospect.is_prospect is False
    print("PASS last window promotes into an open slot regardless of the bar")


def test_earlier_window_still_respects_the_bar():
    """⚠️ THE OVER-REACH GUARD. Skipping the bar in EVERY window would promote every
    project player over every free agent and make the edge constant dead."""
    prospect = FakeBrainPlayer('Kid', 74)
    prospect.prospect_seasons = 0
    team = StubTeam({'qb': None, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1}, [prospect])
    sm = StubSM(StubBrain(replacement=200.0), StubPlayerManager())
    assert sm._promoteProspectsAutonomously(team) == []
    assert team.rosterDict['qb'] is None
    print("PASS an early-window prospect still loses to a better free agent")


def test_last_window_cuts_to_make_room_when_the_slot_is_filled():
    """The headline failure: a 99-potential quarterback lost for nothing because
    the QB slot happened to be occupied."""
    prospect = FakeBrainPlayer('Headliner', 88)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Journeyman', 72, termRemaining=3)
    team = StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    promotions = sm._promoteProspectsAutonomously(team)
    assert [p['name'] for p in promotions] == ['Headliner']
    assert team.rosterDict['qb'] is prospect
    assert pm.released == [incumbent]
    assert sm.charged == [cutFeeFor(incumbent)]
    print(f"PASS cut to make room, charged {sm.charged[0]}F")


def test_a_club_that_cannot_pay_the_fee_cannot_cut():
    """⚠️ The fee is a real constraint, not decoration. A broke club loses him —
    which is exactly the priced decision the last chance is supposed to be."""
    prospect = FakeBrainPlayer('Headliner', 88)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Journeyman', 72, termRemaining=3)
    team = StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm, treasury=10)
    assert sm._promoteProspectsAutonomously(team) == []
    assert team.rosterDict['qb'] is incumbent
    assert pm.released == []
    print("PASS an unaffordable fee blocks the cut and he walks")


def test_it_will_not_cut_a_better_player_to_keep_a_prospect():
    """Losing a prospect is bad; cutting a BETTER player to keep him is worse.
    The upgrade must clear the same margin a cut-for-upgrade needs anywhere else."""
    prospect = FakeBrainPlayer('Marginal', 74)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Starter', 74 - FO_CUT_UPGRADE_MARGIN + 0.5,
                                termRemaining=3)
    team = StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(team) == []
    assert pm.released == []
    print("PASS a marginal prospect does not displace a comparable incumbent")


def test_a_walk_year_incumbent_is_never_paid_for():
    """He vacates on his own at season end, so paying to cut him is pure waste —
    and the fee would be charged for nothing."""
    prospect = FakeBrainPlayer('Headliner', 88)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Leaving', 72, termRemaining=1)
    team = StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(team) == []
    assert sm.charged == []
    print("PASS a walk-year incumbent is left alone")


# ── A prospect who is better TODAY (owner, 2026-10-03) ──────────────────────

def _filledQb(incumbent, prospect):
    return StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])


def test_an_early_prospect_who_is_better_today_is_promoted_over_the_starter():
    """The rule that was missing: before, an early-window prospect could only take an
    OPEN slot, so a team with a clearly better prospect kept starting the weaker man."""
    prospect = FakeBrainPlayer('Kid', 84)
    prospect.prospect_seasons = 0
    incumbent = FakeBrainPlayer('Journeyman', 72, termRemaining=2)
    incumbent.term = 3
    team = _filledQb(incumbent, prospect)
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert [p['name'] for p in sm._promoteProspectsAutonomously(team)] == ['Kid']
    assert team.rosterDict['qb'] is prospect
    assert pm.released == [incumbent]
    assert sm.charged == [cutFeeFor(incumbent)]


def test_an_early_prospect_must_be_better_now_not_just_projected():
    """Projected better is not enough before his final window: he must rate above
    the starter today, or the team waits."""
    prospect = FakeBrainPlayer('Kid', 70)
    prospect.prospect_seasons = 0
    incumbent = FakeBrainPlayer('Journeyman', 72, termRemaining=2)
    incumbent.term = 3

    class ProjectingBrain(StubBrain):
        def decisionValue(self, player, coach=None, rng=None, team=None):
            return 95.0 if player is prospect else float(player.playerRating)
    pm = StubPlayerManager()
    sm = StubSM(ProjectingBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(_filledQb(incumbent, prospect)) == []
    assert pm.released == []


def test_nobody_signed_this_offseason_is_cut_for_a_prospect():
    """Owner: "I generally dont want teams signing players and then cutting them in
    the offseason." A contract that has not started counting down is off limits."""
    prospect = FakeBrainPlayer('Kid', 88)
    prospect.prospect_seasons = 0
    incumbent = FakeBrainPlayer('JustSigned', 72, termRemaining=3)
    incumbent.term = 3
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(_filledQb(incumbent, prospect)) == []
    assert pm.released == []


def test_a_fan_favorite_is_not_cut_for_a_prospect():
    from managers import playerManager as pmod
    prospect = FakeBrainPlayer('Kid', 88)
    prospect.prospect_seasons = 0
    incumbent = FakeBrainPlayer('Favorite', 72, termRemaining=2)
    incumbent.term = 3
    incumbent.id = 4242
    pmod.setFanSentiment({4242: 0.9})
    try:
        pm = StubPlayerManager()
        sm = StubSM(StubBrain(replacement=0.0), pm)
        assert sm._promoteProspectsAutonomously(_filledQb(incumbent, prospect)) == []
        assert pm.released == []
    finally:
        pmod.setFanSentiment({})


def test_nobody_is_cut_for_a_prospect_who_is_not_finally_promoted():
    """The cut is DECIDED per candidate and EXECUTED only for the one promoted, so a
    losing candidate never costs anyone his job."""
    better = FakeBrainPlayer('Better', 90, position=Position.QB)
    better.prospect_seasons = 0
    worse = FakeBrainPlayer('Worse', 80, position=Position.RB)
    worse.prospect_seasons = 0
    qb = FakeBrainPlayer('QB', 70, termRemaining=2); qb.term = 3
    rb = FakeBrainPlayer('RB', 78, termRemaining=2, position=Position.RB); rb.term = 3
    team = StubTeam({'qb': qb, 'rb': rb, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [better, worse])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    names = [p['name'] for p in sm._promoteProspectsAutonomously(team)]
    assert names == ['Better']          # Worse only clears 78 by 2, under the margin
    assert pm.released == [qb]
