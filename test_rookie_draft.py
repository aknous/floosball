"""The rookie draft — class generation, the pick, and the flags nobody may be left with.

⚠️ THE WHOLE PITCH IS A BOTTOM-FEEDER DRAFTING A HUGE PROSPECT, and `constants.py`
states the intent verbatim: rookies debut below their true skill and develop up into it,
so "a future 5-star looks like a solid 3-4-star as a rookie". A free-agent signing cannot
substitute — an FA is a known quantity with a rating on the card, and there is no story in
signing a 74. The uncertainty IS the feature.

See docs/PROSPECT_DRAFT_PLAN.md.
"""

from constants import ROOKIE_DRAFT_CLASS_SIZE, PROSPECT_SLOT_CAP_PER_POSITION
from managers.playerManager import PlayerManager
from floosball_player import Position


class FakePlayer:
    def __init__(self, pid, rating, position=Position.QB, name=None):
        self.id = pid
        self.name = name or f"Rookie {pid}"
        self.playerRating = rating
        self.position = position
        self.is_prospect = False
        self.is_upcoming_rookie = True
        self.is_undrafted = False
        self.drafting_team_id = None
        self.prospect_seasons = None
        self.team = 'Upcoming Rookie'
        self.freeAgentYears = None

    @property
    def playerTier(self):
        class T:
            name = 'TierB'
        return T()


class FakeTeam:
    def __init__(self, tid, name):
        self.id = tid
        self.name = name
        self.abbr = name[:3].upper()
        self.prospects = []
        self.coach = None
        self.numbered = []

    def assignPlayerNumber(self, player):
        self.numbered.append(player)


class StubBrain:
    """A board built by a rule the test controls, so the ORDER is checkable."""

    def __init__(self, valueFn=None):
        self.valueFn = valueFn or (lambda p, team: float(p.playerRating))

    def decisionValue(self, player, coach=None, rng=None, team=None):
        return self.valueFn(player, team)


class Harness:
    def __init__(self, rookies):
        self.activePlayers = list(rookies)
        self.freeAgents = []
        self.positioned = []
        self.sorted = False

    def addToPositionList(self, player):
        self.positioned.append(player)

    def sortPlayersByPosition(self):
        self.sorted = True

    # ⚠️ BORROW THE REAL METHODS, DO NOT RE-IMPLEMENT THEM. Every one the generator
    # reaches has to be listed here, and a method added to `PlayerManager` without being
    # added here fails LOUDLY on an AttributeError rather than quietly testing a stub that
    # has drifted from the class under test.
    countTeamProspectsAtPosition = PlayerManager.countTeamProspectsAtPosition
    hasOpenProspectSlot = PlayerManager.hasOpenProspectSlot
    rookieDraftPickGenerator = PlayerManager.rookieDraftPickGenerator
    findPickBuyer = PlayerManager.findPickBuyer
    handOverNextSeasonPick = PlayerManager.handOverNextSeasonPick
    forfeitPayoutFor = PlayerManager.forfeitPayoutFor
    payForfeitedSlot = PlayerManager.payForfeitedSlot


def _run(rookies, teams, brain=None):
    h = Harness(rookies)
    events = list(h.rookieDraftPickGenerator(rookies, teams,
                                             brain=brain or StubBrain()))
    return h, events


def _teams(n):
    return [FakeTeam(i + 1, f"Club{i + 1}") for i in range(n)]


# ----------------------------------------------------------- class size

def test_class_size_is_counted_not_a_constant():
    """⚠️ `ROOKIE_DRAFT_CLASS_SIZE` IS A 24-TEAM-ERA CONSTANT. The league grew to 32 and
    it did not, so a restored draft reading it leaves eight clubs with nothing to pick.
    `computeShareUnit` already paid for this exact lesson — its `numTeams` defaulted to
    24 and made every facility 33% too expensive after the league grew."""
    class TM:
        teams = _teams(32)

    class Container:
        def getService(self, name):
            return TM() if name == 'team_manager' else None

    pm = Harness([])
    pm.serviceContainer = Container()
    assert PlayerManager.rookieClassSize(pm) == 32
    assert ROOKIE_DRAFT_CLASS_SIZE != 32, \
        "the stale constant now matches the league by accident — the test proves nothing"
    print(f"PASS class size is counted (32), not the stale constant ({ROOKIE_DRAFT_CLASS_SIZE})")


def test_class_size_falls_back_when_no_league_is_loaded():
    class Container:
        def getService(self, name):
            return None

    pm = Harness([])
    pm.serviceContainer = Container()
    assert PlayerManager.rookieClassSize(pm) == ROOKIE_DRAFT_CLASS_SIZE
    print("PASS an unloaded league falls back rather than drafting zero")


# --------------------------------------------------------- the picking

def test_every_club_picks_once_worst_first():
    rookies = [FakePlayer(i, 60 + i) for i in range(1, 9)]
    teams = _teams(8)
    _, events = _run(rookies, teams)
    picks = [e for e in events if e['type'] == 'pick']
    assert len(picks) == 8
    assert [p['teamName'] for p in picks] == [t.name for t in teams]
    print("PASS eight clubs, eight picks, in the order given")


def test_the_worst_club_gets_the_headliner():
    """The entire pitch of the feature, as one assertion."""
    rookies = [FakePlayer(i, 60 + i) for i in range(1, 9)]
    teams = _teams(8)
    _, events = _run(rookies, teams)
    first = next(e for e in events if e['type'] == 'pick')
    assert first['teamName'] == 'Club1'
    assert first['rating'] == max(r.playerRating for r in rookies)
    print(f"PASS the first pick takes the best available ({first['playerName']})")


def test_each_club_drafts_off_ITS_OWN_board():
    """⚠️ THE OLD SCORER WAS RAW `playerRating`, so every club ranked the class
    identically and the draft was a QUEUE. A prospect's value is his PROJECTION, and a
    weak front office sees him as exactly what he is today while an elite one sees seven
    points of upside on the same player — a real difference in what each can DO with him,
    not noise."""
    rookies = [FakePlayer(1, 70, Position.QB, 'Project'),
               FakePlayer(2, 72, Position.RB, 'Safe')]
    # Club1 rates the project highest; a rating-only board would take 'Safe'.
    brain = StubBrain(lambda p, team: 99.0 if (team.id == 1 and p.name == 'Project')
                      else float(p.playerRating))
    _, events = _run(rookies, _teams(2), brain)
    picks = [e for e in events if e['type'] == 'pick']
    assert picks[0]['playerName'] == 'Project', picks
    assert picks[0]['rating'] < picks[1]['rating'], \
        "the club took the higher-rated player, so the board was never consulted"
    print("PASS a club can take the lower-rated player its own board prefers")


def test_a_tie_goes_to_the_thinner_position():
    """A pipeline should not stack three quarterbacks because they happened to score
    alike."""
    rookies = [FakePlayer(1, 70, Position.QB), FakePlayer(2, 70, Position.RB)]
    teams = _teams(1)
    teams[0].prospects.append(FakePlayer(99, 70, Position.QB))
    _, events = _run(rookies, teams, StubBrain(lambda p, team: 50.0))
    pick = next(e for e in events if e['type'] == 'pick')
    assert pick['position'] == 'RB', pick
    print("PASS a tie breaks toward the position the club is thin at")


# ------------------------------------------------ flags and the aftermath

def test_a_drafted_rookie_becomes_a_prospect_with_a_full_window():
    rookies = [FakePlayer(1, 70)]
    teams = _teams(1)
    h, _ = _run(rookies, teams)
    pick = rookies[0]
    assert pick.is_prospect is True
    assert pick.is_upcoming_rookie is False
    assert pick.drafting_team_id == 1
    assert pick.prospect_seasons == 0, "a draftee must start his window at zero"
    assert pick in teams[0].prospects
    assert pick in teams[0].numbered, "a promoted prospect would show #0"
    print("PASS a draftee is a prospect at window 0, numbered, in the pipeline")


def test_nobody_is_left_holding_the_upcoming_rookie_flag():
    """⚠️ THE DRAFT IS THE ONE THING THAT CLEARS `is_upcoming_rookie`. A rookie left
    holding it is stranded FOREVER — never rostered, never signable, invisible to the
    sim but still taking up space in the pool. That is exactly what happened to a whole
    class when the draft was removed."""
    rookies = [FakePlayer(i, 60 + i) for i in range(1, 13)]
    h, events = _run(rookies, _teams(4))
    assert sum(1 for r in rookies if r.is_upcoming_rookie) == 0
    undrafted = [r for r in rookies if r.is_undrafted]
    assert len(undrafted) == 8
    assert all(r in h.freeAgents for r in undrafted)
    assert all(r.team == 'Free Agent' and r.freeAgentYears == 0 for r in undrafted)
    complete = next(e for e in events if e['type'] == 'complete')
    assert len(complete['undrafted']) == 8
    print("PASS the 8 undrafted go to free agency, none keep the flag")


def test_a_full_pipeline_forfeits_the_pick_rather_than_breaking():
    teams = _teams(1)
    for i in range(PROSPECT_SLOT_CAP_PER_POSITION):
        teams[0].prospects.append(FakePlayer(90 + i, 70, Position.QB))
    rookies = [FakePlayer(1, 70, Position.QB)]
    _, events = _run(rookies, teams)
    skip = next(e for e in events if e['type'] == 'skip')
    assert skip['reason'] == 'no_eligible_rookies'
    assert rookies[0].is_undrafted is True
    print("PASS a club with no open slot at that position passes, and he goes to FA")


def test_an_exhausted_class_ends_the_draft_cleanly():
    rookies = [FakePlayer(1, 70)]
    _, events = _run(rookies, _teams(8))
    picks = [e for e in events if e['type'] == 'pick']
    assert len(picks) == 1
    assert events[-1]['type'] == 'complete'
    print("PASS a short class ends the draft without stranding anyone")
