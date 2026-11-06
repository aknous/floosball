"""The team plan drives the rookie draft (docs/TEAM_PLAN.md).

Owner, 2026-11-06: "teams need to know their whole situation. who their prospects are at
each position, which roster players they want to resign, when they plan to promote their
prospects, what the free agent market looks like." And: "teams need to be looking at both
ratings, not just the overall. and coaches should have a preference."

Run: .venv/bin/python -m pytest -q test_team_plan.py
"""
from floosball_player import Position
from managers.frontOfficeBrain import FrontOfficeBrain
from test_rookie_draft import FakePlayer, FakeTeam, Harness


class PlanBrain:
    """Projections from a per-name map (flat across seasons unless a list is given), a
    board that is plain rating, a league of `teams`, and a fixed side tilt."""

    def __init__(self, ratings, tilt=0.0, teams=None, arcs=None):
        self.ratings = ratings
        self.tilt = tilt
        self.teams = teams or []
        self.arcs = arcs or {}

    def _ceilingRating(self, player, team=None):
        r = self.ratings.get(player.name, player.playerRating)
        return float(r[-1] if isinstance(r, list) else r)

    def projectedRating(self, player, seasonsAhead, coach=None, team=None):
        r = self.ratings.get(player.name, player.playerRating)
        if isinstance(r, list):
            return float(r[min(len(r), seasonsAhead) - 1])
        return float(r)

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating)

    def willSignWith(self, fa, team):
        return True

    def _leagueTeams(self):
        return self.teams

    def classifyArc(self, player):
        return self.arcs.get(player.name, 'prime')

    def sideTilt(self, team, coach=None):
        return self.tilt

    sideRating = FrontOfficeBrain.sideRating


def _starter(rating, position=Position.QB, name='Starter', term=3, pid=900):
    p = FakePlayer(pid, rating, position, name)
    p.termRemaining = term
    p.willRetire = False
    return p


def _freeAgent(pid, rating, position, name):
    fa = FakePlayer(pid, rating, position, name)
    fa.team = 'Free Agent'
    fa.willRetire = False
    return fa


def _pick(team, rookies, brain, intent=None, slot=5, pool=None):
    h = Harness(rookies)
    h.freeAgents = list(pool or [])
    return h.chooseRookiePick(brain, team, rookies, slot, intent=intent).name


def test_a_prospect_due_to_take_over_covers_the_position():
    """The Melons' case: a walk-year QB the GM will not re-sign covers next season only,
    and a prospect projected to 86 takes over after him, so a QB rookie adds almost
    nothing and the pick goes to the position with a hole."""
    team = FakeTeam(1, 'Melons')
    team.rosterDict = {'qb': _starter(86, term=1, name='Moonshine'),
                       'rb': _starter(70, Position.RB, name='Weak RB', pid=901)}
    prospect = FakePlayer(950, 79, Position.QB, 'Connery'); prospect.prospect_seasons = 1
    team.prospects = [prospect]
    rookies = [FakePlayer(1, 80, Position.QB, 'QB Rookie'), FakePlayer(2, 75, Position.RB, 'RB Rookie')]
    brain = PlanBrain({'Connery': [82, 85, 86], 'QB Rookie': [82, 85, 87], 'RB Rookie': [78, 82, 84]})
    assert _pick(team, rookies, brain, intent={}) == 'RB Rookie'
    # With no prospect behind him the QB slot opens after next season, and the QB is the pick.
    team.prospects = []
    assert _pick(team, rookies, brain, intent={}) == 'QB Rookie'
    print("PASS a prospect due to take over covers the position")


def test_a_kept_walk_year_starter_covers_the_whole_horizon():
    team = FakeTeam(1, 'Club')
    star = _starter(90, term=1, name='Walk Year QB')
    team.rosterDict = {'qb': star, 'rb': _starter(72, Position.RB, name='RB', pid=901)}
    rookies = [FakePlayer(1, 80, Position.QB, 'QB Rookie'), FakePlayer(2, 75, Position.RB, 'RB Rookie')]
    brain = PlanBrain({'QB Rookie': [84, 88, 92], 'RB Rookie': [76, 80, 84]})
    assert _pick(team, rookies, brain, intent={star.id: True}) == 'RB Rookie'
    assert _pick(team, rookies, brain, intent={star.id: False}) == 'QB Rookie'
    print("PASS a starter the GM will re-sign covers the horizon")


def test_a_deep_free_agent_market_lowers_the_need():
    """Two open slots. At RB the team can expect an 86 free agent, so an 84-ceiling RB
    rookie adds nothing there; nobody is coming at TE."""
    team = FakeTeam(1, 'Club')
    team.rosterDict = {}
    rookies = [FakePlayer(1, 76, Position.RB, 'RB Rookie'), FakePlayer(2, 70, Position.TE, 'TE Rookie')]
    brain = PlanBrain({'RB Rookie': 84, 'TE Rookie': 80}, teams=[team])
    pool = [_freeAgent(800, 86, Position.RB, 'Market RB')]
    assert _pick(team, rookies, brain, pool=pool) == 'TE Rookie'
    assert _pick(team, rookies, brain) == 'RB Rookie'
    print("PASS a deep market at a position lowers the need there")


def test_the_market_is_what_is_left_at_this_teams_pick():
    """Owner, 2026-11-06: teams should "know where they will pick in the FA draft and know
    what quality players will be available then". Two teams ahead with an open RB slot
    take the 90 and the 88, so the third team plans on the 75; the first team in the
    order gets the 90."""
    first, second, me = (FakeTeam(i, f'Team{i}') for i in (1, 2, 3))
    for t in (first, second, me):
        t.rosterDict = {}
    brain = PlanBrain({}, teams=[first, second, me])
    h = Harness([])
    h.freeAgents = [_freeAgent(800 + i, r, Position.RB, f'FA {r}') for i, r in enumerate((90, 88, 75))]
    order = [first, second, me]
    assert h.positionPlan(brain, me, Position.RB, faOrder=order)[0][0]['player'].name == 'FA 75'
    assert h.positionPlan(brain, first, Position.RB, faOrder=order)[0][0]['player'].name == 'FA 90'
    print("PASS the market is what the teams ahead leave")


def test_two_open_slots_plan_on_two_different_free_agents():
    """The Melons' plan had one free agent in both WR slots."""
    me = FakeTeam(1, 'Club'); me.rosterDict = {}
    h = Harness([])
    h.freeAgents = [_freeAgent(800, 80, Position.WR, 'FA A'), _freeAgent(801, 74, Position.WR, 'FA B')]
    season1 = h.positionPlan(PlanBrain({}, teams=[me]), me, Position.WR, faOrder=[me])[0]
    assert sorted(x['player'].name for x in season1) == ['FA A', 'FA B']
    print("PASS two open slots plan on two different free agents")


def test_a_defense_minded_team_takes_the_defender():
    """Two RB rookies of equal overall, one the better defender. A balanced team takes
    the first on the tie-break; a team that weighs defense takes the defender."""
    team = FakeTeam(1, 'Club')
    team.rosterDict = {}
    a = FakePlayer(1, 80, Position.RB, 'Runner'); a.offensiveRating, a.defensiveRating = 88, 72
    b = FakePlayer(2, 80, Position.RB, 'Two Way'); b.offensiveRating, b.defensiveRating = 72, 88
    ratings = {'Runner': 80, 'Two Way': 80}
    assert _pick(team, [a, b], PlanBrain(ratings, tilt=0.8)) == 'Two Way'
    assert _pick(team, [a, b], PlanBrain(ratings, tilt=-0.8)) == 'Runner'
    print("PASS the side tilt picks the defender for a defense-minded team")


def test_the_side_tilt_reads_the_coach_and_the_team():
    """`sideTilt`: the coach's lean (defensiveMind over offensiveMind) plus the team's
    league-relative need; a balanced team with a balanced coach reads 0."""
    class Coach:
        def __init__(self, off, dfn):
            self.offensiveMind, self.defensiveMind = off, dfn

    class T:
        def __init__(self, off, dfn, coach):
            self.offenseRating, self.defenseRating, self.coach = off, dfn, coach

    brain = FrontOfficeBrain.__new__(FrontOfficeBrain)
    league = [T(80, 80, None) for _ in range(5)]
    brain.leagueTeams = league
    teams = [T(80, 80, Coach(80, 80)), T(80, 80, Coach(60, 100)),
             T(80, 80, Coach(100, 60)), T(80, 70, Coach(80, 80))]
    balanced, defensive, offensive, weakDefense = (brain.sideTilt(t) for t in teams)
    assert balanced == 0.0
    assert defensive > 0, "a defensive coach weighs defense"
    assert offensive < 0, "an offensive coach weighs offense"
    assert weakDefense > 0, "a weak defense needs defense"
    print("PASS the side tilt reads the coach and the team")


def test_a_later_season_reads_the_market_after_this_fa_draft():
    """Owner, 2026-11-06: teams were "assuming they will all actually make it to FA even
    though most of them will probably get signed". With two other teams missing an RB,
    the two best free-agent RBs are gone by next offseason; what is left for later
    seasons is the third, plus other teams' expiring players their GMs will not keep."""
    other1, other2, me = FakeTeam(1, 'Other1'), FakeTeam(2, 'Other2'), FakeTeam(3, 'Club')
    other1.rosterDict, other2.rosterDict = {}, {}
    # The team's own RB covers next season and walks after it, so it shops a season later.
    me.rosterDict = {'rb': _starter(80, Position.RB, name='Leaving RB', term=1, pid=905)}
    brain = PlanBrain({}, teams=[other1, other2, me])
    h = Harness([])
    h.freeAgents = [_freeAgent(800 + i, r, Position.RB, f'FA {r}') for i, r in enumerate((90, 88, 75))]
    order = [me, other1, other2]
    levels = h.positionOutlook(brain, me, Position.RB, faOrder=order, intent={})
    assert levels == [80.0, 75.0, 75.0], levels
    # A free agent it signs this offseason stays: with no RB at all it takes the 90 (first
    # in the order) and keeps him.
    me.rosterDict = {}
    assert h.positionOutlook(brain, me, Position.RB, faOrder=order) == [90.0, 90.0, 90.0]
    print("PASS later seasons read the market after this FA draft")


def test_a_star_his_team_will_keep_is_not_on_the_later_market():
    """Owner, 2026-11-06: teams "cant assume players above a certain rating and age to
    still actually be available because their team is likely to resign them". Another
    team's RBs both have one season left: an 88 in his prime (assumed re-signed) and an 80.
    Two seasons out the market holds the 80, not the 88; with the other team's own
    re-sign read saying the 88 walks, he is there."""
    other, me = FakeTeam(1, 'Other'), FakeTeam(2, 'Club')
    star = _starter(88, Position.RB, name='Prime Star', term=2, pid=901)
    me.rosterDict = {}
    other.rosterDict = {'rb': star}
    brain = PlanBrain({}, teams=[other, me])
    h = Harness([])
    plan = h.positionPlan(brain, me, Position.RB, faOrder=[me, other])
    assert plan[2][0]['player'] is None and plan[2][0]['source'] != 'starter', plan[2]
    plain = _starter(80, Position.RB, name='Plain RB', term=2, pid=902)
    other.rosterDict = {'rb': plain}
    plan = h.positionPlan(PlanBrain({}, teams=[other, me]), me, Position.RB, faOrder=[me, other])
    assert plan[2][0]['player'] is plain, plan[2]
    # Ending after next season, the GM's own read decides.
    other.rosterDict = {'rb': _starter(88, Position.RB, name='Walking Star', term=1, pid=903)}
    plan = h.positionPlan(PlanBrain({}, teams=[other, me]), me, Position.RB, faOrder=[me, other],
                          intent={903: False})
    assert plan[1][0]['player'].name == 'Walking Star', plan[1]
    print("PASS a star his team will keep is not on the later market")


def test_a_dry_later_market_assumes_this_years_quality():
    """A later season whose projected pool has run dry assumes a free agent of the
    quality this offseason offers at the team's pick, not replacement level: that pool
    cannot see deals ending beyond the horizon, cuts or new players."""
    o1, me, o2 = FakeTeam(1, 'Other1'), FakeTeam(2, 'Club'), FakeTeam(3, 'Other2')
    o1.rosterDict, o2.rosterDict = {}, {}
    me.rosterDict = {'rb': _starter(80, Position.RB, name='Leaving RB', term=1, pid=905)}
    brain = PlanBrain({}, teams=[o1, me, o2])
    h = Harness([])
    h.freeAgents = [_freeAgent(800, 78, Position.RB, 'FA 78'), _freeAgent(801, 74, Position.RB, 'FA 74')]
    plan = h.positionPlan(brain, me, Position.RB, faOrder=[o1, me, o2], intent={})
    # Season 1: the starter. This offseason the two other teams take both free agents, so
    # season 2's pool is empty; at this team's pick this year the 74 was there.
    assert plan[0][0]['source'] == 'starter'
    assert plan[1][0]['source'] == 'typical' and plan[1][0]['rating'] == 74.0, plan[1]
    print("PASS a dry later market assumes this year's quality")


def test_next_offseasons_market_is_what_this_one_leaves_plus_likely_walkers():
    """The draft-time re-sign read measures a walk-year player against next offseason's
    market: this offseason's free agents after the league fills its open slots, plus
    other teams' players whose deals end after next season and who are not stars in
    their prime (owner, 2026-11-06)."""
    a, b = FakeTeam(1, 'A'), FakeTeam(2, 'B')
    a.rosterDict = {}                                   # one open RB slot this offseason
    plain = _starter(80, Position.RB, name='Plain Walker', term=1, pid=910)
    star = _starter(88, Position.WR, name='Prime Star', term=1, pid=911)
    b.rosterDict = {'rb': plain, 'wr1': star}
    h = Harness([])
    best, rest = _freeAgent(800, 85, Position.RB, 'Best FA'), _freeAgent(801, 70, Position.RB, 'Rest FA')
    h.freeAgents = [best, rest]
    pool = h.projectedMarketPool(PlanBrain({}, teams=[a, b]), [a, b])
    names = {p.name for p in pool}
    assert 'Best FA' not in names and 'Rest FA' in names, names   # A signs the 85 now
    assert 'Plain Walker' in names and 'Prime Star' not in names, names
    print("PASS next offseason's market: what this one leaves plus likely walkers")
