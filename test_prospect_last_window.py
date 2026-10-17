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
from managers.frontOfficeBrain import cutFeeFor, FrontOfficeBrain
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
    FA-draft rule (`prospectTakesSlot`) exists to prevent."""
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
        return float(getattr(player, 'value', player.playerRating))

    def bestReplacementValue(self, player, coach=None, pool=None, rng=None,
                             pickDepth=0, team=None):
        return self.replacement

    def faPickDepth(self, team, faOrder=None):
        return 0

    # Who is better this season: a knob per player (`seasonNext`), else today's rating.
    def seasonRating(self, player, coach=None, team=None):
        return float(getattr(player, 'seasonNext', player.playerRating))

    # The free agent the team can expect at its pick (step 3.78's washout check): a knob.
    expectedFa = None

    def expectedFreeAgent(self, position, team=None, coach=None, pickDepth=0, pool=None):
        return self.expectedFa

    prospectTakesSlot = FrontOfficeBrain.prospectTakesSlot

    # The standing/bar layer at neutral: no standing, the bar is its base. The
    # real weighing is covered in test_starter_standing.py.
    def starterStanding(self, starter, team=None, coach=None):
        return 0.0

    # The today-gates at their simplest: no aging, so the starter is measured as he is
    # today (the declining-starter reading is covered in test_starter_standing.py).
    def roughlyMatches(self, prospect, starter, coach=None):
        from constants import FO_PROSPECT_LAST_WINDOW_TODAY_GAP
        return prospect.playerRating >= starter.playerRating - FO_PROSPECT_LAST_WINDOW_TODAY_GAP

    def ratedAtLeast(self, prospect, starter, coach=None, strictly=False):
        if strictly:
            return prospect.playerRating > starter.playerRating
        return prospect.playerRating >= starter.playerRating

    def moveOnBar(self, coach, base, floor=None):
        return max(base, floor) if floor is not None else base

    def prospectEdgeOver(self, prospect, starter, team=None, coach=None):
        return (self.decisionValue(prospect, coach, team=team)
                - self.decisionValue(starter, coach, team=team))


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
    _prospectContractYields = SeasonManager._prospectContractYields

    def _recordOffseasonEvent(self, *a, **kw):
        pass

    def _chargeCutFee(self, team, fee):
        if fee > self.treasury:
            return False
        self.treasury -= fee
        self.charged.append(fee)
        return True


LAST = PROSPECT_DEVELOPMENT_WINDOW - 1


def test_the_kickoff_leaves_open_slots_to_the_fa_draft():
    """owner, 2026-10-17: "teams should be able to hold off on promoting until the free
    agent draft". An open slot is filled there, where the prospect is weighed against
    the free agents the team can sign (test_fa_draft_prospect_choice.py), at every window."""
    for seasons in (0, LAST):
        prospect = FakeBrainPlayer('Headliner', 74)
        prospect.prospect_seasons = seasons
        team = StubTeam({'qb': None, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1}, [prospect])
        sm = StubSM(StubBrain(replacement=0.0), StubPlayerManager())
        assert sm._promoteProspectsAutonomously(team) == []
        assert team.rosterDict['qb'] is None and prospect.is_prospect is True
    print("PASS the kickoff leaves open slots to the FA draft")


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
    """Losing a prospect is bad; cutting a BETTER player to keep him is worse."""
    prospect = FakeBrainPlayer('Marginal', 74)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Starter', 76, termRemaining=3)
    team = StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(team) == []
    assert pm.released == []
    print("PASS a last-window prospect does not displace a better incumbent")


def test_a_last_window_prospect_only_has_to_roughly_match():
    """owner, 2026-10-10: on his last window the alternative is losing him for
    nothing, so matching the starter is enough (FO_PROSPECT_LAST_WINDOW_BAR)."""
    prospect = FakeBrainPlayer('Match', 74)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Starter', 74, termRemaining=2)
    incumbent.term = 3
    team = StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert [p['name'] for p in sm._promoteProspectsAutonomously(team)] == ['Match']
    assert pm.released == [incumbent]
    print("PASS a last-window prospect who matches the starter is promoted")


def test_a_last_window_prospect_can_displace_a_starter_in_his_final_year():
    """⚠️ "He leaves on his own" means AFTER the coming season, and a final-window
    prospect is released moments after this pass, so he cannot wait for that slot.
    Prod season 9: Midnights' Gibson Gnegy was never weighed against Dingers Culpepper
    (one year left), washed out, and the club drafted a weaker RB for the hole."""
    prospect = FakeBrainPlayer('Headliner', 88)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('FinalYear', 72, termRemaining=1)
    incumbent.term = 3
    team = _filledQb(incumbent, prospect)
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    promotions = sm._promoteProspectsAutonomously(team)
    assert [p['name'] for p in promotions] == ['Headliner']
    assert team.rosterDict['qb'] is prospect
    assert pm.released == [incumbent]
    print("PASS a last-window prospect can displace a starter in his final year")


def test_an_earlier_prospect_waits_for_a_starter_in_his_final_year():
    """An earlier-window prospect is still a prospect next offseason, when the
    final-year starter's slot opens, so nobody is paid to leave early."""
    prospect = FakeBrainPlayer('Rising', 88)
    prospect.prospect_seasons = 0
    incumbent = FakeBrainPlayer('FinalYear', 72, termRemaining=1)
    incumbent.term = 3
    team = _filledQb(incumbent, prospect)
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(team) == []
    assert sm.charged == []
    print("PASS an earlier-window prospect waits for the final-year starter")


def test_a_one_year_deal_signed_this_offseason_is_still_protected():
    """A final-window prospect does not lift the signed-this-offseason rule:
    a one-year deal reads termRemaining == term == 1."""
    prospect = FakeBrainPlayer('Headliner', 88)
    prospect.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('JustSigned', 72, termRemaining=1)
    incumbent.term = 1
    team = _filledQb(incumbent, prospect)
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(team) == []
    assert pm.released == []
    print("PASS a one-year deal signed this offseason is not cut")


def _filledQb(incumbent, prospect):
    return StubTeam({'qb': incumbent, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': 1},
                    [prospect])


# ── A prospect who is better TODAY (owner, 2026-10-03) ──────────────────────


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


# ------------------------------------- step 3.78: the last look before the release
#
# owner, 2026-10-17. Prod season 10: the Raccoons let Crunchtime McCown (79) walk at
# step 3, then step 3.78 released Dearie Lizardo (TE, 86) with their TE slot empty,
# because the only promotion pass after step 3 was the FA kickoff, after the release.


def test_washout_pass_promotes_a_prospect_about_to_be_released():
    washout = FakeBrainPlayer('Lizardo', 86, position=Position.TE)
    washout.prospect_seasons = LAST
    team = StubTeam({'qb': 1, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': None, 'k': 1}, [washout])
    brain = StubBrain()
    brain.expectedFa = FakeBrainPlayer('Dunebuggy', 77, position=Position.TE)
    sm = StubSM(brain, StubPlayerManager())
    promotions = sm._promoteProspectsAutonomously(team, washoutOnly=True)
    assert [p['name'] for p in promotions] == ['Lizardo']
    assert team.rosterDict['te'] is washout and washout.is_prospect is False
    print("PASS a washing-out prospect goes into the open slot before the release")


def test_washout_pass_lets_him_go_when_the_market_has_better():
    """He is released before the FA draft, so his open-slot decision is made here,
    against the free agent this team can expect at its pick (owner, 2026-10-17)."""
    washout = FakeBrainPlayer('Bodie', 64, position=Position.WR)
    washout.prospect_seasons = LAST
    team = StubTeam({'qb': 1, 'rb': 1, 'wr1': 1, 'wr2': None, 'te': 1, 'k': 1}, [washout])
    brain = StubBrain()
    brain.expectedFa = FakeBrainPlayer('Veteran', 74, position=Position.WR)
    sm = StubSM(brain, StubPlayerManager())
    assert sm._promoteProspectsAutonomously(team, washoutOnly=True) == []
    assert team.rosterDict['wr2'] is None and washout.is_prospect is True
    # ...but one projecting to be as good this season still takes it.
    washout.seasonNext = 75
    assert [p['name'] for p in sm._promoteProspectsAutonomously(team, washoutOnly=True)] \
        == ['Bodie']
    print("PASS the washout pass weighs the free agent the team can expect")


def test_washout_pass_leaves_prospects_with_time_left_for_the_kickoff():
    """Only the prospects this release would take: anyone else keeps the FA bar and
    the kickoff pass, so an open slot is not handed to a project player early."""
    kid = FakeBrainPlayer('Kid', 90, position=Position.TE)
    kid.prospect_seasons = LAST - 1
    team = StubTeam({'qb': 1, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': None, 'k': 1}, [kid])
    sm = StubSM(StubBrain(replacement=0.0), StubPlayerManager())
    assert sm._promoteProspectsAutonomously(team, washoutOnly=True) == []
    assert team.rosterDict['te'] is None
    print("PASS the washout pass ignores prospects with a window left")


def test_washout_pass_can_cut_a_roster_player_for_him():
    washout = FakeBrainPlayer('Headliner', 88)
    washout.prospect_seasons = LAST
    incumbent = FakeBrainPlayer('Journeyman', 72, termRemaining=2)
    incumbent.term = 3
    team = _filledQb(incumbent, washout)
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert [p['name'] for p in sm._promoteProspectsAutonomously(team, washoutOnly=True)] \
        == ['Headliner']
    assert pm.released == [incumbent]
    print("PASS the washout pass cuts a weaker starter to keep him")


def test_washout_pass_runs_inside_the_gate_before_the_release():
    src = _seasonManagerSource()
    gate = src.index("if not self._isOffseasonStepComplete('prospect_window'):")
    look = src.index('await self._promoteWashoutProspects()')
    release = src.index('self.playerManager._advanceProspectWindow()')
    assert gate < look < release
    print("PASS gate -> last look -> release")


def test_resign_check_weighs_a_washing_out_prospect():
    """The step-3 re-sign decision must see a WINDOW-1 prospect as a last-chance
    alternative: if he roughly matches the expiring starter the starter walks and the
    3.78 pass promotes the prospect into the open slot. Leaving him out kept the
    starter (or let him walk to the market) and lost the prospect either way."""
    src = _seasonManagerSource()
    block = src[src.index('internal, lastChance = [], set()'):]
    block = block[:block.index('chooseResigns(')]
    assert 'continue' not in block.split('internal.append(pr)')[1]
    assert 'served >= PROSPECT_DEVELOPMENT_WINDOW - 2' in block
    assert 'if served >= PROSPECT_DEVELOPMENT_WINDOW - 1:\n                    continue' \
        not in block
    print("PASS washing-out prospects are last-chance alternatives at re-sign")


# ------------------------------- two prospects, one slot: the better player wins
#
# owner, 2026-10-17: "the better player should always win ... if a team has two
# prospects at the same position, there needs to be a point where the team chooses one
# or the other". Prod-snapshot sim, season 11: WAS promoted a 68 K rookie (whose
# projected ceiling gave him the higher decisionValue) over Blorbos Phil (75, last
# chance); Blorbos then washed out behind the rookie's protected prospect contract.

def _k(name, rating, seasons, seasonNext=None, value=None):
    p = FakeBrainPlayer(name, rating, position=Position.K)
    p.prospect_seasons = seasons
    if seasonNext is not None:
        p.seasonNext = seasonNext
    if value is not None:
        p.value = value
    return p


def _openK(prospects):
    return StubTeam({'qb': 1, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': None}, prospects)


# The choice between two prospects for an OPEN slot is the FA draft's now:
# test_fa_draft_prospect_choice.py::test_the_better_of_two_prospects_this_season_is_the_one_weighed


def _prospectContractK(name, rating, seasonNext=None, pid=900):
    p = FakeBrainPlayer(name, rating, position=Position.K, termRemaining=2)
    p.term = 3
    p.onProspectContract = True
    p.is_prospect = False
    p.id = pid
    if seasonNext is not None:
        p.seasonNext = seasonNext
    return p


def _filledK(incumbent, prospects):
    return StubTeam({'qb': 1, 'rb': 1, 'wr1': 1, 'wr2': 1, 'te': 1, 'k': incumbent}, prospects)


def test_a_prospect_contract_yields_to_a_better_prospect():
    starter = _prospectContractK('Willia', 68, seasonNext=69)
    challenger = _k('Blorbos', 76, LAST, seasonNext=77)
    team = _filledK(starter, [challenger])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert [p['name'] for p in sm._promoteProspectsAutonomously(team)] == ['Blorbos']
    assert pm.released == [starter] and team.rosterDict['k'] is challenger
    print("PASS a prospect contract gives way to a better prospect")


def test_an_early_window_prospect_also_wins_when_better_this_season():
    starter = _prospectContractK('Willia', 68, seasonNext=69)
    challenger = _k('Kid', 74, 0, seasonNext=75)
    team = _filledK(starter, [challenger])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert [p['name'] for p in sm._promoteProspectsAutonomously(team)] == ['Kid']
    assert pm.released == [starter]
    print("PASS an early-window prospect who is better this season takes the slot")


def test_a_prospect_contract_holds_against_a_worse_prospect():
    starter = _prospectContractK('Willia', 76, seasonNext=78)
    challenger = _k('Blorbos', 75, LAST, seasonNext=76)
    team = _filledK(starter, [challenger])
    pm = StubPlayerManager()
    sm = StubSM(StubBrain(replacement=0.0), pm)
    assert sm._promoteProspectsAutonomously(team) == []
    assert pm.released == []
    print("PASS a prospect contract holds against a prospect who is not better")


def test_the_exception_does_not_reach_this_offseasons_promotion_or_a_fan_favorite():
    from managers.playerManager import stampPromotion, setFanSentiment
    from constants import FAN_VERDICT_KEEP_SENTIMENT
    # Promoted earlier in this same offseason.
    starter = _prospectContractK('Fresh', 68, seasonNext=69)
    stampPromotion(starter, 0)              # StubSM's season number is 0
    team = _filledK(starter, [_k('Blorbos', 76, LAST, seasonNext=77)])
    pm = StubPlayerManager()
    assert StubSM(StubBrain(replacement=0.0), pm)._promoteProspectsAutonomously(team) == []
    # A player his fans clearly want.
    favorite = _prospectContractK('Favorite', 68, seasonNext=69, pid=901)
    setFanSentiment({901: FAN_VERDICT_KEEP_SENTIMENT})
    try:
        team = _filledK(favorite, [_k('Blorbos', 76, LAST, seasonNext=77)])
        pm = StubPlayerManager()
        assert StubSM(StubBrain(replacement=0.0), pm)._promoteProspectsAutonomously(team) == []
        assert pm.released == []
    finally:
        setFanSentiment({})
    print("PASS same-offseason promotions and fan favorites stay protected")


def test_the_exception_is_only_for_the_prospect_choice():
    """Every other cut path still reads the full protection."""
    from managers.playerManager import isCutProtected
    starter = _prospectContractK('Willia', 68)
    assert isCutProtected(starter, 0) is True
    assert isCutProtected(starter, 0, ignoreProspectContract=True) is False
    print("PASS the prospect contract still protects everywhere else")
