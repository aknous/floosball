"""Keeping or replacing a starter weighs who he is, not just his rating.

owner, 2026-10-10: when a prospect is weighed against a starter, or a walk-year starter
is up for re-sign, the GM considers whether the starter is an aging vet past his peak,
whether he played to his rating, whether the team won with him, the fans, and how
ready the GM is to move on, and each GM weighs those differently.

Reported: Midnights let last-window RB Gibson Gnegy (82) wash out rather than displace
Dingers Culpepper (83, ten seasons in, one year left).

Run: .venv/bin/python -m pytest -q test_starter_standing.py
"""
import types

from managers.frontOfficeBrain import FrontOfficeBrain
from floosball_player import Position
from constants import (FO_MOVE_ON_SHIFT, FO_CUT_UPGRADE_MARGIN, FO_RESULTS_WEIGHT,
                       FO_STANDING_HORIZON_SEASONS, POSITION_VALUE)

SEASON = 9


class Brain(FrontOfficeBrain):
    """The real standing/bar logic over a value that is just the rating."""

    def __init__(self, performanceMap=None):
        super().__init__(playerManager=None, performanceMap=performanceMap or {})
        self.season = SEASON

    def decisionValue(self, player, coach=None, rng=None, team=None, **kw):
        return float(player.playerRating) * POSITION_VALUE[player.position.name]

    def upgradeConfidence(self, *a, **kw):
        return 0.0


def _coach(**attrs):
    base = dict(playerDevelopment=80, adaptability=80, aggressiveness=80, scouting=80,
                fanTrust=80, id=1)
    base.update(attrs)
    return types.SimpleNamespace(**base)


def _team(wins=14, losses=14):
    return types.SimpleNamespace(seasonTeamStats={'wins': wins, 'losses': losses,
                                                  'ties': 0},
                                 facilityEffect=lambda key: 0.0)


def _player(pid, rating, nextSeason=None, position=Position.RB):
    p = types.SimpleNamespace(id=pid, playerRating=rating, position=position,
                              termRemaining=1, term=3)
    if nextSeason is not None:
        p.projectedRatingPastPeak = lambda devBias, n=nextSeason: n
    return p


# ── aging ────────────────────────────────────────────────────────────────────

def test_a_past_peak_starter_loses_standing_over_the_commitment():
    vet = _player(1, 83, nextSeason=81.5)
    prime = _player(2, 83)
    brain = Brain()
    assert brain.starterStanding(prime, _team(), _coach()) == 0.0
    drag = brain.starterStanding(vet, _team(), _coach())
    # 1.5 a season over the rest of the horizon, seen at 0.5 + 0.5 x vision (0.5).
    expected = -1.5 * (FO_STANDING_HORIZON_SEASONS - 1) * 0.75 * POSITION_VALUE['RB']
    assert abs(drag - expected) < 1e-6, drag


def test_a_development_gm_weighs_aging_more():
    vet = _player(1, 83, nextSeason=81.5)
    brain = Brain()
    believer = brain.starterStanding(vet, _team(), _coach(playerDevelopment=100))
    skeptic = brain.starterStanding(vet, _team(), _coach(playerDevelopment=60))
    assert believer < brain.starterStanding(vet, _team(), _coach()) < 0
    assert skeptic == 0.0


def test_a_poor_scout_still_sees_a_veteran_getting_old():
    vet = _player(1, 83, nextSeason=81.5)
    brain = Brain()
    blind = brain.starterStanding(vet, _team(), _coach(scouting=60))
    sharp = brain.starterStanding(vet, _team(), _coach(scouting=100))
    assert sharp < blind < 0
    assert abs(blind / sharp - 0.5) < 1e-6


# ── results ──────────────────────────────────────────────────────────────────

def _perf(pid, rating, perf, season=SEASON):
    return {pid: [(season, rating, perf)]}


def test_results_credit_follows_play_and_team_record():
    up, down = _player(1, 80), _player(2, 80)
    brain = Brain(performanceMap={**_perf(1, 80, 90), **_perf(2, 80, 70)})
    winner, loser = _team(21, 7), _team(7, 21)
    upWin = brain.starterStanding(up, winner, _coach())
    upLose = brain.starterStanding(up, loser, _coach())
    downWin = brain.starterStanding(down, winner, _coach())
    downLose = brain.starterStanding(down, loser, _coach())
    # Played well: more credit when the team won. Played badly: more blame when it lost.
    assert upWin > upLose > 0
    assert downLose < downWin < 0
    assert abs(upWin - FO_RESULTS_WEIGHT * 1.5 * POSITION_VALUE['RB']) < 1e-6


def test_an_adaptable_gm_reacts_to_results_and_a_rigid_one_does_not():
    up = _player(1, 80)
    brain = Brain(performanceMap=_perf(1, 80, 90))
    assert brain.starterStanding(up, _team(), _coach(adaptability=60)) == 0.0
    assert (brain.starterStanding(up, _team(), _coach(adaptability=100))
            > brain.starterStanding(up, _team(), _coach()) > 0)


def test_a_stale_season_says_nothing_about_how_last_season_went():
    up = _player(1, 80)
    brain = Brain(performanceMap=_perf(1, 80, 90, season=SEASON - 1))
    assert brain.starterStanding(up, _team(), _coach()) == 0.0


# ── the bar ──────────────────────────────────────────────────────────────────

def test_aggressiveness_moves_the_bar_both_ways():
    brain = Brain()
    assert brain.moveOnBar(_coach(), 1.0) == 1.0
    assert brain.moveOnBar(_coach(aggressiveness=100), 1.0) == 1.0 - FO_MOVE_ON_SHIFT
    assert brain.moveOnBar(_coach(aggressiveness=60), 1.0) == 1.0 + FO_MOVE_ON_SHIFT
    assert brain.moveOnBar(_coach(aggressiveness=100), 0.5, floor=0.0) == 0.0


def test_a_last_window_prospect_roughly_matching_replaces_a_fading_starter():
    """The Midnights case in miniature: an 82 prospect on his last window against an
    83 ten-year back who is past his peak."""
    brain = Brain()
    gnegy = _player(10, 82)
    dingers = _player(11, 83, nextSeason=81.5)
    team = _team()
    assert brain.prospectReplacesStarter(gnegy, dingers, team, _coach(), finalWindow=True)
    # Not on an earlier window, where the ordinary cut margin applies.
    assert not brain.prospectReplacesStarter(gnegy, dingers, team, _coach(),
                                             finalWindow=False)


def test_a_conservative_gm_keeps_the_known_starter_on_a_close_call():
    brain = Brain()
    prospect, starter = _player(10, 82), _player(11, 82)
    assert brain.prospectReplacesStarter(prospect, starter, _team(),
                                         _coach(aggressiveness=100), finalWindow=True)
    assert not brain.prospectReplacesStarter(prospect, starter, _team(),
                                             _coach(aggressiveness=60), finalWindow=True)


def test_a_starter_who_won_playing_past_his_rating_holds_off_the_prospect():
    prospect, starter = _player(10, 82), _player(11, 80)
    hot = Brain(performanceMap=_perf(11, 80, 92))
    assert not hot.prospectReplacesStarter(prospect, starter, _team(21, 7), _coach(),
                                           finalWindow=True)
    assert Brain().prospectReplacesStarter(prospect, starter, _team(21, 7), _coach(),
                                           finalWindow=True)


# ── re-sign with no prospect involved ────────────────────────────────────────

def test_re_sign_priority_carries_the_starter_standing():
    """With the market unable to replace anyone, priority is the incumbent's value, so
    a fading vet ranks below a same-rated starter who won playing past his rating."""
    fading = _player(1, 82, nextSeason=80.0)
    hot = _player(2, 82)
    brain = Brain(performanceMap=_perf(2, 82, 92))
    brain.worthResigningOnStars = lambda player, coach=None, team=None: True
    ranked = brain.rankResignCandidates([fading, hot], coach=_coach(), team=_team(20, 8))
    assert [p for p, _ in ranked] == [hot, fading]
    assert ranked[0][1] > ranked[1][1]


def test_a_last_window_prospect_must_roughly_match_a_prime_starter_today():
    """Measured on a prod copy before this guard: Anaheim cut a 90 TE with three years
    left for an 82 prospect, because aging and projected growth evened the values. A
    starter who is NOT declining is still measured as he is today."""
    brain = Brain()
    prospect = _player(10, 82, position=Position.TE)
    star = _player(11, 90, position=Position.TE)
    assert not brain.prospectReplacesStarter(prospect, star, _team(), _coach(aggressiveness=100),
                                             finalWindow=True)
    close = _player(12, 86, nextSeason=83.0, position=Position.TE)
    assert brain.prospectReplacesStarter(prospect, close, _team(), _coach(), finalWindow=True)


def test_a_declining_starter_is_gated_on_next_season_then_value_decides():
    """owner, 2026-10-17: a starter past his peak is measured at next season's
    projection, so an 82 prospect is within reach of a 90 falling to 86. The gate no
    longer vetoes; the value comparison (aging over the horizon, the GM's bar) decides."""
    brain = Brain()
    prospect = _player(10, 82, position=Position.TE)
    fading = _player(11, 90, nextSeason=86.0, position=Position.TE)
    assert brain.roughlyMatches(prospect, fading, _coach())
    assert not brain.roughlyMatches(prospect, _player(12, 90, position=Position.TE), _coach())
    # Neutral GM: 82 against 90 less 6 of aging is still short of the bar.
    assert not brain.prospectReplacesStarter(prospect, fading, _team(), _coach(),
                                             finalWindow=True)
    # An aggressive GM bets on the prospect on that close call.
    assert brain.prospectReplacesStarter(prospect, fading, _team(),
                                         _coach(aggressiveness=100), finalWindow=True)


def _rising(pid, rating, ceiling, position=Position.TE):
    p = _player(pid, rating, position=position)
    p.computeCeilingRating = lambda c=ceiling: c
    return p


def test_a_prospect_grows_over_the_same_horizon_the_starter_declines_over():
    """Next season's value credits a share f of the gap to the ceiling; each later
    season realises f of what is left, over FO_STANDING_HORIZON_SEASONS."""
    from constants import FO_CEILING_CREDIT
    brain = Brain()
    coach = _coach()
    prospect = _rising(10, 78, 92)
    f = FO_CEILING_CREDIT * brain._attrLean(coach, 'playerDevelopment')
    H = FO_STANDING_HORIZON_SEASONS
    expected = (14 * ((1 - f) - (1 - f) ** H) * brain.scoutingVision(coach, _team())
                * POSITION_VALUE['TE'])
    got = brain._growthBeyondNextSeason(prospect, _team(), coach)
    assert abs(got - expected) < 1e-6, (got, expected)
    # Never past the ceiling, even for the best developer.
    best = _coach(playerDevelopment=100, scouting=100)
    assert brain._growthBeyondNextSeason(prospect, _team(), best) < 14 * POSITION_VALUE['TE']
    # Nothing for a player with no headroom or past his peak.
    assert brain._growthBeyondNextSeason(_player(11, 78), _team(), coach) == 0.0
    aging = _rising(12, 78, 92)
    aging.projectedRatingPastPeak = lambda devBias: 77.0
    assert brain._growthBeyondNextSeason(aging, _team(), coach) == 0.0


def test_growth_counts_on_both_sides_of_the_comparison():
    """A developing starter's growth is extended too, so two equal young players with
    equal headroom compare as equal: the horizon does not favour the prospect."""
    brain = Brain()
    a, b = _rising(10, 80, 90), _rising(11, 80, 90)
    assert abs(brain.prospectEdgeOver(a, b, _team(), _coach())) < 1e-9


def test_an_aging_starter_rated_higher_can_lose_to_a_rising_prospect():
    """The owner's question: the starter is rated higher today but aging out. Against
    the same prospect, the fading starter is replaced and a prime one is not."""
    brain = Brain()
    prospect = _rising(10, 82, 94)
    fading = _player(11, 85, nextSeason=83.5, position=Position.TE)
    prime = _player(12, 85, position=Position.TE)
    assert brain.prospectReplacesStarter(prospect, fading, _team(), _coach(), finalWindow=True)
    assert not brain.prospectReplacesStarter(prospect, prime, _team(), _coach(),
                                             finalWindow=True)


def test_earlier_window_and_resign_gates_read_a_declining_starter_forward():
    brain = Brain()
    prospect = _player(10, 84)
    fading = _player(11, 86, nextSeason=83.0)
    assert brain.ratedAtLeast(prospect, fading, _coach(), strictly=True)
    assert not brain.ratedAtLeast(prospect, _player(12, 86), _coach())


def test_nobody_signed_this_offseason_is_cut_anywhere():
    """No signing then cutting in the same offseason (owner, 2026-10-03), on every cut
    path, not only the prospect one."""
    from managers.playerManager import signedThisOffseason
    assert signedThisOffseason(types.SimpleNamespace(term=2, termRemaining=2))
    assert not signedThisOffseason(types.SimpleNamespace(term=3, termRemaining=2))
    assert not signedThisOffseason(types.SimpleNamespace(term=None, termRemaining=1))
    import inspect
    from managers import playerManager, seasonManager
    sources = {
        'FA draft upgrade cut': inspect.getsource(playerManager.PlayerManager),
        'GM cut sweep': inspect.getsource(FrontOfficeBrain.rankCutCandidates),
        'prospect cut': inspect.getsource(seasonManager.SeasonManager._cutPlanForProspect),
    }
    for name, src in sources.items():
        assert 'signedThisOffseason(' in src, name


def test_a_last_chance_prospect_is_weighed_at_re_sign_as_his_promotion_will_be():
    """Measured on a prod copy: Pittsburgh re-signed a 74, ten-season RB over a 70 prospect
    on his last chance, under the strict at-least-as-good-today rule, deciding the
    promotion before it could happen."""
    vet = _player(1, 74, nextSeason=71.0)
    prospect = _player(2, 70)
    brain = Brain()
    brain.worthResigningOnStars = lambda player, coach=None, team=None: True
    keptStrict = brain.chooseResigns([vet], 2, coach=_coach(), team=_team(),
                                     internal=[prospect])
    keptLast = brain.chooseResigns([vet], 2, coach=_coach(), team=_team(),
                                   internal=[prospect], lastChance={id(prospect)})
    assert keptStrict == [vet]
    assert keptLast == []


def test_a_prospect_about_to_wash_out_is_a_last_chance_alternative():
    """The re-sign runs before the prospect window advances. A prospect about to wash
    out was once left out of the alternatives, on the reasoning that he was about to
    leave; that kept the starter by default and lost the prospect (Raccoons, season 10:
    Lizardo released with the TE slot empty). Step 3.78 now promotes him into a slot
    this decision leaves open, so he is weighed on the last-chance rules instead
    (owner, 2026-10-17; behaviour in test_prospect_last_window.py)."""
    import inspect
    from managers import seasonManager
    src = inspect.getsource(seasonManager.SeasonManager)
    assert 'if served >= PROSPECT_DEVELOPMENT_WINDOW - 2:' in src
    assert 'lastChance=lastChance' in src


# ── cutting a starter for a better free agent ────────────────────────────────

def _underContract(p):
    p.term, p.termRemaining = 3, 2
    p.willRetire = False
    return p


def test_the_cut_sweep_weighs_the_starter_standing():
    """Same rating, same free agent on the board: the fading vet is cut, the starter
    who won playing past his rating is kept."""
    fading = _underContract(_player(1, 80, nextSeason=77.0))
    hot = _underContract(_player(2, 80))
    brain = Brain(performanceMap=_perf(2, 80, 92))
    brain.upgradeConfidence = lambda *a, **kw: 1.0
    replacement = 80 * POSITION_VALUE['RB'] + FO_CUT_UPGRADE_MARGIN - 0.5
    brain.bestReplacementValue = lambda *a, **kw: replacement
    for starter, cut in ((fading, True), (hot, False)):
        team = _team(20, 8)
        team.rosterDict = {'rb': starter}
        ranked = brain.rankCutCandidates(team, coach=_coach())
        assert bool(ranked) is cut, (starter.id, ranked)


def test_the_fa_draft_board_carries_the_incumbents_standing():
    """The draft's cut-for-upgrade reads incumbents off the board, so their standing
    has to be on it, and only theirs."""
    fading = _player(1, 80, nextSeason=77.0)
    brain = Brain()
    team = _team()
    board = brain.buildDraftBoard(team, [], coach=_coach(), incumbents=[fading],
                                  alsoValue=[_player(3, 80, nextSeason=77.0)])
    standing = brain.starterStanding(fading, team, _coach())
    assert standing < 0
    assert abs(board[1] - (80 * POSITION_VALUE['RB'] + standing)) < 1e-6
    assert board[3] == 80 * POSITION_VALUE['RB']     # a prospect gets no standing


def test_season_rating_reads_growth_and_aging_through_scouting():
    """Who is better THIS season (owner, 2026-10-17): today's rating moved toward next
    season's projection by the GM's scouting vision."""
    brain = Brain()
    coach = _coach()
    vision = brain.scoutingVision(coach, _team())
    aging = _player(1, 85, nextSeason=83.0)
    assert abs(brain.seasonRating(aging, coach, _team()) - (85 - 2.0 * vision)) < 1e-9
    assert brain.seasonRating(_player(2, 80), coach, _team()) == 80.0
    rising = _rising(3, 78, 92)
    assert 78 < brain.seasonRating(rising, coach, _team()) < 92
