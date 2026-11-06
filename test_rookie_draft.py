"""The rookie draft — class generation, the pick, and the flags nobody may be left with.

⚠️ THE WHOLE PITCH IS A BOTTOM-FEEDER DRAFTING A HUGE PROSPECT, and `constants.py`
states the intent verbatim: rookies debut below their true skill and develop up into it,
so "a future 5-star looks like a solid 3-4-star as a rookie". A free-agent signing cannot
substitute — an FA is a known quantity with a rating on the card, and there is no story in
signing a 74. The uncertainty IS the feature.

See docs/PROSPECT_DRAFT_PLAN.md.
"""

from constants import ROOKIE_DRAFT_CLASS_SIZE, PROSPECT_SLOT_CAP_PER_POSITION, ROOKIE_CLASS_PER_TEAM
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
        self.rosterDict = {}

    def assignPlayerNumber(self, player):
        self.numbered.append(player)


class StubBrain:
    """A board built by a rule the test controls, so the ORDER is checkable."""

    def __init__(self, valueFn=None):
        self.valueFn = valueFn or (lambda p, team: float(p.playerRating))

    def decisionValue(self, player, coach=None, rng=None, team=None):
        return self.valueFn(player, team)

    def _ceilingRating(self, player, team=None):
        # The draft board reads the club's belief about a prospect's CEILING.
        return self.valueFn(player, team)


class Harness:
    def __init__(self, rookies):
        self.activePlayers = list(rookies)
        self.freeAgents = []
        self.unusedNames = []
        self.positioned = []
        self.sorted = False

    def addToPositionList(self, player):
        self.positioned.append(player)

    def removeFromPositionList(self, player):
        if player in self.positioned:
            self.positioned.remove(player)

    def sortPlayersByPosition(self):
        self.sorted = True

    # ⚠️ BORROW THE REAL METHODS, DO NOT RE-IMPLEMENT THEM. Every one the generator
    # reaches has to be listed here, and a method added to `PlayerManager` without being
    # added here fails LOUDLY on an AttributeError rather than quietly testing a stub that
    # has drifted from the class under test.
    countTeamProspectsAtPosition = PlayerManager.countTeamProspectsAtPosition
    hasOpenProspectSlot = PlayerManager.hasOpenProspectSlot
    rookieDraftPickGenerator = PlayerManager.rookieDraftPickGenerator
    washOutUndrafted = PlayerManager.washOutUndrafted
    positionSupplyDeficits = PlayerManager.positionSupplyDeficits
    _playersWithARecord = staticmethod(PlayerManager._playersWithARecord)
    _removeUnsignedPlayer = PlayerManager._removeUnsignedPlayer
    findPickBuyer = PlayerManager.findPickBuyer
    handOverNextSeasonPick = PlayerManager.handOverNextSeasonPick
    forfeitPayoutFor = PlayerManager.forfeitPayoutFor
    payForfeitedSlot = PlayerManager.payForfeitedSlot
    rookieCeiling = PlayerManager.rookieCeiling
    blockedByOwnProspect = PlayerManager.blockedByOwnProspect
    committedRookie = PlayerManager.committedRookie
    chooseRookiePick = PlayerManager.chooseRookiePick
    prospectRanking = PlayerManager.prospectRanking
    superstarLockedPositions = PlayerManager.superstarLockedPositions
    keptStarPositions = PlayerManager.keptStarPositions
    preferClearNeed = PlayerManager.preferClearNeed
    rookieBoardValue = PlayerManager.rookieBoardValue
    _rookieNeedBar = PlayerManager._rookieNeedBar
    _planRating = PlayerManager._planRating
    _planMarket = PlayerManager._planMarket
    _planMarketUncached = PlayerManager._planMarketUncached
    _planSlotHolders = staticmethod(PlayerManager._planSlotHolders)
    _planOpenSlots = PlayerManager._planOpenSlots
    _likelyResigned = PlayerManager._likelyResigned
    projectedMarketPool = PlayerManager.projectedMarketPool
    positionOutlook = PlayerManager.positionOutlook
    positionPlan = PlayerManager.positionPlan
    rookiePlanValue = PlayerManager.rookiePlanValue
    rookiePlanMargin = PlayerManager.rookiePlanMargin


def _run(rookies, teams, brain=None, resignIntent=None):
    h = Harness(rookies)
    events = list(h.rookieDraftPickGenerator(rookies, teams,
                                             brain=brain or StubBrain(),
                                             resignIntent=resignIntent))
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
    # 1.5 prospects per team since 2026-10-30 (ROOKIE_CLASS_PER_TEAM): more than the draft.
    assert PlayerManager.rookieClassSize(pm) == round(32 * ROOKIE_CLASS_PER_TEAM)
    assert ROOKIE_DRAFT_CLASS_SIZE != 32, \
        "the stale constant now matches the league by accident — the test proves nothing"
    print(f"PASS class size is counted (32), not the stale constant ({ROOKIE_DRAFT_CLASS_SIZE})")


def test_class_size_falls_back_when_no_league_is_loaded():
    class Container:
        def getService(self, name):
            return None

    pm = Harness([])
    pm.serviceContainer = Container()
    assert PlayerManager.rookieClassSize(pm) == round(ROOKIE_DRAFT_CLASS_SIZE * ROOKIE_CLASS_PER_TEAM)
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


def test_with_every_position_open_the_pick_is_the_ceiling_above_replacement():
    """With nothing at any position, need is each rookie's ceiling above replacement times
    his position's weight. A QB barely above replacement goes last (production's season-7
    #2 was a 75-ceiling QB while a 99-ceiling QB and a 100 TE were still on the board),
    and position weight now counts at the top too: a 96 WR (0.72) beats a 100 TE (0.60).
    Until 2026-11-06 the top two picks ranked by raw ceiling and took the TE."""
    rookies = [FakePlayer(1, 72, Position.QB, 'Low Ceiling QB'),
               FakePlayer(2, 82, Position.TE, 'Hundred TE'),
               FakePlayer(3, 70, Position.WR, 'Ninety Six WR')]
    ceilings = {'Low Ceiling QB': 75, 'Hundred TE': 100, 'Ninety Six WR': 96}
    _, events = _run(rookies, _teams(3), StubBrain(lambda p, team: ceilings[p.name]))
    picks = [e['playerName'] for e in events if e['type'] == 'pick']
    assert picks == ['Ninety Six WR', 'Hundred TE', 'Low Ceiling QB'], picks
    print("PASS an open roster takes the ceiling above replacement, position weighted")


def test_a_top_pick_passes_on_a_kicker():
    rookies = [FakePlayer(1, 80, Position.K, 'Hundred K'), FakePlayer(2, 70, Position.RB, 'Eighty RB')]
    ceilings = {'Hundred K': 100, 'Eighty RB': 80}
    _, events = _run(rookies, _teams(1), StubBrain(lambda p, team: ceilings[p.name]))
    first = next(e for e in events if e['type'] == 'pick')
    assert first['playerName'] == 'Eighty RB', first
    print("PASS a top-3 pick skips the kicker")


def _fillersThenChoice(choices, chooserRoster=None, teams=7):
    """Five high-ceiling fillers taken by picks 1-5, then the remaining clubs choose
    among `choices` {name: (position, rating, ceiling)}. The fillers are 99-95 ceiling
    QBs so they go first under the best-available board AND under need (picks 3-5 weigh
    need since the best-available slots dropped to 2): no empty roster can prefer
    anything else."""
    filler = [FakePlayer(10 + i, 60, Position.QB, f'Filler {i}') for i in range(5)]
    picks = [FakePlayer(20 + i, rating, pos, name)
             for i, (name, (pos, rating, _)) in enumerate(choices.items())]
    ceilings = {name: c for name, (_, _, c) in choices.items()}
    ceilings.update({f'Filler {i}': 99 - i for i in range(5)})
    clubs = _teams(teams)
    if chooserRoster is not None:
        clubs[5].rosterDict = chooserRoster
    _, events = _run(filler + picks, clubs, StubBrain(lambda p, team: ceilings[p.name]))
    return [e for e in events if e['type'] == 'pick']


def test_after_the_top_five_the_board_prices_the_ceiling_above_replacement():
    """Past the best-available picks the board is `prospectValue`: ceiling ABOVE
    REPLACEMENT x position weight. A QB barely above replacement is worth less than a
    90-ceiling TE even at TE's lower weight, where the old board (today's rating x
    position) took the QB."""
    picks = _fillersThenChoice({'Barely QB': (Position.QB, 74, 75),
                                'Ninety TE': (Position.TE, 70, 90)})
    assert picks[5]['playerName'] == 'Ninety TE', picks[5]
    print("PASS pick 6 values a 90-ceiling TE over a 75-ceiling QB")


def test_the_first_pick_drafts_by_need_too():
    """Owner, 2026-11-06: "teams just need to be picking by need at all picks". The #1
    pick, with a 90 QB under contract and no RB, takes the 85-ceiling RB over a
    92-ceiling QB who would sit behind its starter. It used to take the QB (the best
    prospect available, need ignored)."""
    starter = FakePlayer(99, 90, Position.QB, 'Starter QB')
    starter.termRemaining = 3
    rookies = [FakePlayer(1, 80, Position.QB, 'Better QB'),
               FakePlayer(2, 75, Position.RB, 'Needed RB')]
    ceilings = {'Better QB': 92, 'Needed RB': 85}
    clubs = _teams(1)
    clubs[0].rosterDict = {'qb': starter}
    _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Needed RB'
    print("PASS the #1 pick takes the RB the club is missing")


def test_a_late_pick_fills_a_hole_over_a_better_asset():
    """Owner, 2026-10-01: "the further back the draft goes, the more teams draft by
    need". A club with a 90-rated QB under contract and no RB takes the 85-ceiling RB
    with its last pick over a 92-ceiling QB who would sit behind its starter. The
    asset board alone takes the QB (25 points above replacement at 1.00, against 18 at
    0.78)."""
    starter = FakePlayer(99, 90, Position.QB, 'Starter QB')
    starter.termRemaining = 3
    picks = _fillersThenChoice({'Better QB': (Position.QB, 80, 92),
                                'Needed RB': (Position.RB, 75, 85)},
                               chooserRoster={'qb': starter}, teams=6)
    assert picks[5]['playerName'] == 'Needed RB', picks[5]
    print("PASS the last pick takes the RB the club is missing")


def test_a_walk_year_starter_is_a_hole_coming():
    """A starter on his last year counts as nobody: that slot is about to open."""
    starter = FakePlayer(99, 90, Position.QB, 'Walk Year QB')
    starter.termRemaining = 1
    picks = _fillersThenChoice({'Better QB': (Position.QB, 80, 92),
                                'Needed RB': (Position.RB, 75, 85)},
                               chooserRoster={'qb': starter}, teams=6)
    assert picks[5]['playerName'] == 'Better QB', picks[5]
    print("PASS a walk-year starter does not block the QB")


def test_a_walk_year_starter_the_team_will_re_sign_still_blocks_the_position():
    """Fixed 2026-11-06: the need bar counted every walk-year starter as gone, so a team
    drafted behind one it planned to keep (prod snapshot, season 13: the Exoticos took a
    79-ceiling QB while planning to re-sign their 82). With the GM's re-sign intent he
    counts at his rating; without it (or intending to let him go) the slot is a hole."""
    for keep, expected in ((True, 'Needed RB'), (False, 'Better QB')):
        starter = FakePlayer(99, 90, Position.QB, 'Walk Year QB')
        starter.termRemaining = 1
        filler = [FakePlayer(10 + i, 60, Position.QB, f'Filler {i}') for i in range(5)]
        rookies = filler + [FakePlayer(20, 80, Position.QB, 'Better QB'),
                            FakePlayer(21, 75, Position.RB, 'Needed RB')]
        ceilings = {'Better QB': 92, 'Needed RB': 85}
        ceilings.update({f'Filler {i}': 99 - i for i in range(5)})
        clubs = _teams(6)
        clubs[5].rosterDict = {'qb': starter}
        _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]),
                         resignIntent={starter.id: keep})
        picks = [e for e in events if e['type'] == 'pick']
        assert picks[5]['playerName'] == expected, (keep, picks[5])
    print("PASS a walk-year starter the GM is keeping blocks the position")


def test_a_rookie_his_teams_own_prospect_matches_is_not_drafted():
    """Owner, 2026-11-06: a team does not draft a rookie at a position where it already
    has a prospect projected as good or better, while anyone else is on the board. Here
    neither rookie fills a need (the QB is under the 90-ceiling prospect, the RB under an
    85 starter), and the tie-break alone would take the QB, who comes closer to what he
    must beat (-2 against -5)."""
    starter = FakePlayer(98, 85, Position.RB, 'Starter RB'); starter.termRemaining = 3
    prospect = FakePlayer(97, 75, Position.QB, 'Prospect QB')
    rookies = [FakePlayer(1, 80, Position.QB, 'Matched QB'),
               FakePlayer(2, 70, Position.RB, 'Blocked RB')]
    ceilings = {'Matched QB': 88, 'Blocked RB': 80, 'Prospect QB': 90}
    clubs = _teams(1)
    clubs[0].rosterDict = {'rb': starter}
    clubs[0].prospects.append(prospect)
    _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Blocked RB'
    # ...but with nobody else left he is still drafted rather than the pick wasted.
    clubs = _teams(1)
    clubs[0].prospects.append(prospect)
    _, events = _run([FakePlayer(1, 80, Position.QB, 'Matched QB')], clubs,
                     StubBrain(lambda p, team: ceilings[p.name]))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Matched QB'
    print("PASS a rookie his own prospect matches is passed over while others remain")


def _star(rating=94, term=3, position=Position.QB, name='Star'):
    p = FakePlayer(900 + rating, rating, position, name)
    p.termRemaining = term
    p.willRetire = False
    return p


def test_a_top_pick_skips_a_position_a_superstar_holds():
    """Owner, 2026-11-04: a top pick does not draft behind a 5-star prime starter with
    years left. He would wash out unless traded, and a trade may never come. Before this
    the #1 pick took the 99-ceiling QB behind a 94 QB."""
    rookies = [FakePlayer(1, 80, Position.QB, 'Ninety Nine QB'),
               FakePlayer(2, 75, Position.WR, 'Ninety WR')]
    ceilings = {'Ninety Nine QB': 99, 'Ninety WR': 90}
    clubs = _teams(1)
    clubs[0].rosterDict = {'qb': _star()}
    _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]))
    first = next(e for e in events if e['type'] == 'pick')
    assert first['playerName'] == 'Ninety WR', first
    print("PASS the #1 pick passes on the QB behind its 94 QB")


def test_a_star_who_is_leaving_or_fading_does_not_lock_the_position():
    """A walk-year star, a retiring one, one past his longevity, or a 4-star leaves the
    position unlocked. Whether the team then drafts there is need's call: a walk-year or
    retiring star is a hole coming, so the 99 QB is the pick; an aging or 4-star starter
    under contract still has to be beaten, so need takes the open-position WR."""
    class ArcBrain(StubBrain):
        def classifyArc(self, player):
            return 'regressing' if getattr(player, 'name', '') == 'Old Star' else 'prime'
    retiring = _star(name='Retiring Star'); retiring.willRetire = True
    for starter, expected in ((_star(term=1, name='Walk Year Star'), 'Ninety Nine QB'),
                              (retiring, 'Ninety Nine QB'),
                              (_star(name='Old Star'), 'Ninety WR'),
                              (_star(rating=88, name='Four Star'), 'Ninety WR')):
        rookies = [FakePlayer(1, 80, Position.QB, 'Ninety Nine QB'),
                   FakePlayer(2, 75, Position.WR, 'Ninety WR')]
        ceilings = {'Ninety Nine QB': 99, 'Ninety WR': 90}
        clubs = _teams(1)
        clubs[0].rosterDict = {'qb': starter}
        brain = ArcBrain(lambda p, team: ceilings[p.name])
        h, events = _run(rookies, clubs, brain)
        assert not h.superstarLockedPositions(brain, clubs[0], {}), starter.name
        first = next(e for e in events if e['type'] == 'pick')
        assert first['playerName'] == expected, (starter.name, first)
    print("PASS a leaving, fading or 4-star starter leaves the position unlocked")


def test_a_walk_year_star_the_team_will_re_sign_still_locks_the_position():
    """Owner, 2026-11-04: a star with one season left locks the position when the team
    intends to re-sign him next offseason (the re-sign limit decides that until
    salaries start, the budget after), and leaves it open when it does not."""
    for keep, expected in ((True, 'Ninety WR'), (False, 'Ninety Nine QB')):
        star = _star(term=1, name='Walk Year Star')
        rookies = [FakePlayer(1, 80, Position.QB, 'Ninety Nine QB'),
                   FakePlayer(2, 75, Position.WR, 'Ninety WR')]
        ceilings = {'Ninety Nine QB': 99, 'Ninety WR': 90}
        clubs = _teams(1)
        clubs[0].rosterDict = {'qb': star}
        h = Harness(rookies)
        events = list(h.rookieDraftPickGenerator(
            rookies, clubs, brain=StubBrain(lambda p, team: ceilings[p.name]),
            resignIntent={star.id: keep}))
        first = next(e for e in events if e['type'] == 'pick')
        assert first['playerName'] == expected, (keep, first)
    print("PASS a walk-year star locks the position only if he will be re-signed")


def test_need_takes_the_clear_need_over_a_qb_behind_a_kept_star():
    """Owner, 2026-11-04 (the clear-need rule): behind a kept 4-star QB with a 2-star RB,
    the RB is the pick. Need alone now gets there at every gap the rule used to cover and
    beyond (a 95-ceiling QB over an 88 starter is a 7-point upgrade; an 88 RB over a 70
    one is 18)."""
    for needCeiling in (92, 88):
        rookies = [FakePlayer(1, 80, Position.QB, 'Best QB'),
                   FakePlayer(2, 75, Position.RB, 'Need RB')]
        ceilings = {'Best QB': 95, 'Need RB': needCeiling}
        clubs = _teams(1)
        clubs[0].rosterDict = {'qb': _star(rating=88),
                               'rb': _star(rating=70, position=Position.RB, name='Weak RB')}
        _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]))
        assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Need RB'
    print("PASS need takes the clear need behind a kept star")


def test_the_clear_need_rule_still_moves_a_need_pick_off_a_kept_star():
    """When need itself lands behind a kept 4-star and a clear-need rookie of comparable
    ceiling exists, `preferClearNeed` takes him. Under need-based picks that happens
    only across position weights: a 99-ceiling QB over an 85 starter (14 points at 1.00)
    outscores a 96 TE over a 74 (22 points at 0.60)."""
    h = Harness([])
    clubs = _teams(1)
    clubs[0].rosterDict = {'qb': _star(rating=85),
                           'te': _star(rating=74, position=Position.TE, name='Weak TE')}
    ceilings = {'Best QB': 99, 'Need TE': 96}
    brain = StubBrain(lambda p, team: ceilings[p.name])
    qb, rb = FakePlayer(1, 80, Position.QB, 'Best QB'), FakePlayer(2, 75, Position.TE, 'Need TE')
    plain = h.chooseRookiePick(brain, clubs[0], [qb, rb], 5, preferNeed=False)
    assert plain is qb, "need alone should take the QB here, or this tests nothing"
    assert h.chooseRookiePick(brain, clubs[0], [qb, rb], 5) is rb
    print("PASS the clear-need rule moves a need pick off a kept 4-star")


def test_one_superstar_receiver_does_not_lock_the_position():
    """WR has two slots: a rookie can still take the weaker one."""
    rookies = [FakePlayer(1, 80, Position.WR, 'Ninety Nine WR'),
               FakePlayer(2, 75, Position.TE, 'Ninety TE')]
    ceilings = {'Ninety Nine WR': 99, 'Ninety TE': 90}
    clubs = _teams(1)
    clubs[0].rosterDict = {'wr1': _star(position=Position.WR), 'wr2': None}
    _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Ninety Nine WR'
    clubs = _teams(1)
    clubs[0].rosterDict = {'wr1': _star(position=Position.WR, name='A'),
                           'wr2': _star(rating=93, position=Position.WR, name='B')}
    rookies = [FakePlayer(1, 80, Position.WR, 'Ninety Nine WR'),
               FakePlayer(2, 75, Position.TE, 'Ninety TE')]
    _, events = _run(rookies, clubs, StubBrain(lambda p, team: ceilings[p.name]))
    assert next(e for e in events if e['type'] == 'pick')['playerName'] == 'Ninety TE'
    print("PASS WR locks only when both starters are superstars")


def test_a_later_pick_skips_a_superstar_position_too():
    """The rule is not only for the top picks: the need picks skip it as well."""
    picks = _fillersThenChoice({'Better QB': (Position.QB, 80, 99),
                                'Needed RB': (Position.RB, 75, 70)},
                               chooserRoster={'qb': _star()}, teams=6)
    assert picks[5]['playerName'] == 'Needed RB', picks[5]
    print("PASS a later pick skips a superstar position")


def test_a_slot_with_only_superstar_positions_left_is_not_spent_on_them():
    """If every rookie left plays a locked position the team does not draft him: the
    slot goes the way of a slot nobody can use."""
    rookies = [FakePlayer(1, 80, Position.QB, 'Only QB')]
    clubs = _teams(1)
    clubs[0].rosterDict = {'qb': _star()}
    _, events = _run(rookies, clubs, StubBrain(lambda p, team: 90))
    assert not [e for e in events if e['type'] == 'pick'], events
    assert any(e['type'] == 'skip' for e in events), events
    print("PASS the slot is skipped rather than spent behind the star")


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


def test_with_no_need_left_the_pick_is_the_least_blocked_rookie():
    """owner, 2026-10-17: drafting on need. When nobody left on the board fills a hole,
    every need value is 0 and the pick used to fall to the highest ceiling at ANY
    position, i.e. a QB behind a 90 QB. Now it is the rookie who comes closest to the
    player he would have to beat."""
    starterQb = FakePlayer(98, 95, Position.QB, 'Starter QB'); starterQb.termRemaining = 3
    starterRb = FakePlayer(99, 82, Position.RB, 'Starter RB'); starterRb.termRemaining = 3
    # Six clubs: the chooser holds the last pick, which is pure need. Neither rookie beats
    # its starter (QB 88 under 95, RB 80 under 82), so both need values are 0.
    picks = _fillersThenChoice({'Blocked QB': (Position.QB, 70, 88),
                                'Close RB': (Position.RB, 70, 80)},
                               chooserRoster={'qb': starterQb, 'rb': starterRb}, teams=6)
    assert picks[5]['playerName'] == 'Close RB', picks[5]
    print("PASS a pure-need pick with no need left takes the least-blocked rookie")


def test_re_sign_intent_follows_the_limit_then_the_budget():
    """The intent is next offseason's step-3 decision: the per-offseason limit applies
    until salaries start, then it is lifted (the budget filter inside `_resignDecision`
    decides). It never counts this draft's rookies as the replacement."""
    from managers.seasonManager import SeasonManager
    from constants import RESIGN_LIMIT_PER_OFFSEASON
    calls = []

    class P:
        def __init__(self, pid):
            self.id = pid

    kept, walked = P(1), P(2)

    def fakeDecision(self, team, brain, faOrder, slotOwners, limit, afford=True, pool=None):
        calls.append((slotOwners, limit))
        return [kept, walked], [], [kept], 0, 0

    sm = object.__new__(SeasonManager)
    orig = (SeasonManager._resignDecision, SeasonManager._resignLimitOn)
    try:
        SeasonManager._resignDecision = fakeDecision
        for limitOn, expectedLimit in ((True, RESIGN_LIMIT_PER_OFFSEASON), (False, 99)):
            SeasonManager._resignLimitOn = staticmethod(lambda on=limitOn: on)
            calls.clear()
            out = sm.walkYearResignIntent(None, [object()], [])
            assert out == {1: True, 2: False}, out
            assert calls == [([], expectedLimit)], calls
    finally:
        SeasonManager._resignDecision, SeasonManager._resignLimitOn = orig[0], staticmethod(orig[1])
    print("PASS the re-sign intent uses the limit, then the budget, and no draftees")


def test_the_prospect_ranking_is_the_public_read_and_kickers_fall():
    """Owner, 2026-11-04: the class is shown as a prospect ranking, by the public read of
    what each prospect is worth. A team's scouting (here rating the second QB far higher)
    is never used, and a kicker with the best public read still ranks below a QB: a kicker
    is worth less."""
    a = FakePlayer(1, 85, Position.QB, 'Public Favorite')
    b = FakePlayer(2, 70, Position.QB, 'Scouts Secret')
    k = FakePlayer(3, 95, Position.K, 'Big Leg')
    scouted = {'Public Favorite': 80, 'Scouts Secret': 99, 'Big Leg': 95}
    h = Harness([a, b, k])
    ranked = [r.name for r in h.prospectRanking(StubBrain(lambda p, team: scouted[p.name]))]
    assert ranked[0] == 'Public Favorite', ranked
    assert ranked.index('Big Leg') > ranked.index('Public Favorite'), ranked
    assert all(r.is_upcoming_rookie for r in (a, b, k)), "the ranking changed the class"
    print("PASS the ranking reads the public consensus, and kickers fall")
