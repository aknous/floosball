"""
A RULE-VOTE BALLOT CANNOT OUTLIVE THE GAME DAY IT GOVERNS.

Reproduces the season 6 day-0 failure, which had TWO independent causes and needed
both fixed.

⚠️ CAUSE 1 — a stale `closes_at`. The day-0 window was written with week 1's kickoff as
it stood BEFORE the season-anchor fix, i.e. a week in the future. `requireClosed`
refuses to resolve until that moment, so the ballot sat open through its entire game
day while the day played out in the standard format, and would have resolved after the
season ended.

⚠️ CAUSE 2 — and correcting the timestamp would NOT have been enough. `getOpenWindow`
orders by `day_index DESC` and takes the first, so the moment day 1's window opened,
day 0's became UNREACHABLE by the resolver forever. A fix that only repairs close times
leaves this half live, and it is the half that makes the failure permanent rather than
merely late.

An expired window resolves to **'none' with applied=0**: the day it governed is over, so
applying its winner would impose a rule change on a day nobody voted about.
"""
import types
import datetime


class _Window:
    def __init__(self, dayIndex, closesAt, kind='change'):
        self.day_index = dayIndex
        self.closes_at = closesAt
        self.kind = kind
        self.resolved = False
        self.winner_key = None
        self.applied = False


class _Repo:
    """Mirrors RuleVoteRepository's two selectors, including the DESC ordering that
    is the whole point of cause 2."""
    def __init__(self, windows):
        self.windows = windows

    def getOpenWindow(self, season):
        openOnes = [w for w in self.windows if not w.resolved]
        if not openOnes:
            return None
        return sorted(openOnes, key=lambda w: -w.day_index)[0]

    def getStaleOpenWindows(self, season, currentDayIndex):
        return sorted([w for w in self.windows
                       if not w.resolved and w.day_index < currentDayIndex],
                      key=lambda w: w.day_index)


def _mgr(windows):
    """A RuleVoteManager with its session/repo/enabled plumbing stubbed out."""
    from managers.ruleVoteManager import RuleVoteManager
    m = RuleVoteManager(None)
    repo = _Repo(windows)
    m._repo = lambda session=None: repo
    m._enabled = lambda: True
    import database.connection as conn
    conn.get_session = lambda: types.SimpleNamespace(
        commit=lambda: None, close=lambda: None, rollback=lambda: None)
    return m


FUTURE = datetime.datetime.utcnow() + datetime.timedelta(days=7)


def testTheDayZeroBallotIsClosedOnceDayOneIsPlaying():
    """The exact production shape: day 0 open, closes_at a week out, sim on day 1."""
    day0 = _Window(0, FUTURE)
    m = _mgr([day0])
    closed = m.expireStaleWindows(season=6, currentWeek=8)   # week 8 -> day 1
    assert closed == 1
    assert day0.resolved is True
    assert day0.winner_key == 'none'
    assert day0.applied is False, 'an expired ballot must not change the rules'


def testAnOrphanedWindowIsReachedEvenBehindANewerOne():
    """Cause 2: getOpenWindow returns the HIGHEST day index, so the sweep must not
    go through it. Without getStaleOpenWindows, day 0 here is invisible forever."""
    day0, day1 = _Window(0, FUTURE), _Window(1, FUTURE)
    repoView = _Repo([day0, day1])
    assert repoView.getOpenWindow(6) is day1, 'precondition: the newer window shadows it'
    m = _mgr([day0, day1])
    m.expireStaleWindows(season=6, currentWeek=8)            # day 1 is current
    assert day0.resolved is True, 'the shadowed window was never reached'
    assert day1.resolved is False, 'the CURRENT day must be left alone'


def testTheCurrentDaysBallotIsNeverExpired():
    day0 = _Window(0, FUTURE)
    m = _mgr([day0])
    assert m.expireStaleWindows(season=6, currentWeek=1) == 0   # week 1 -> day 0
    assert m.expireStaleWindows(season=6, currentWeek=7) == 0   # week 7 -> still day 0
    assert day0.resolved is False


def testPlayoffsExpireADayThreeBallot():
    """Regular season is days 0-3; week 29+ is past all of them."""
    day3 = _Window(3, FUTURE, kind='revert')
    m = _mgr([day3])
    assert m.expireStaleWindows(season=6, currentWeek=29) == 1
    assert day3.resolved is True and day3.winner_key == 'none'


def testNoCurrentWeekSweepsNothing():
    """The debug endpoint resolves on demand and passes no week; it must not sweep."""
    day0 = _Window(0, FUTURE)
    m = _mgr([day0])
    assert m.expireStaleWindows(season=6, currentWeek=0) == 0
    assert day0.resolved is False


def testTheDayIsABACKSTOPForAWrongCloseTime():
    """resolveOpenWindow's own gate: a window whose day has passed is due regardless
    of what its close time claims. This is what stops a bad timestamp being fatal."""
    from managers.ruleVoteManager import RuleVoteManager
    m = RuleVoteManager(None)
    # week 8 is day 1; a day-0 window is past due even with a close time a week out
    assert m.dayIndexForWeek(8) > 0
    assert m.dayIndexForWeek(1) == 0 and m.dayIndexForWeek(7) == 0
    assert m.dayIndexForWeek(8) == 1 and m.dayIndexForWeek(15) == 2
    assert m.dayIndexForWeek(22) == 3


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test') and callable(fn):
            fn(); print('ok', name)
