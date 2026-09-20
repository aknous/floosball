"""The roster dict contract: six keys, always present, `None` when vacant.

⚠️ THE ENGINE INDEXES THIS DIRECTLY. `Play.passPlay` does
`self.offense.rosterDict['qb']`, so a MISSING key is a KeyError mid-game — and
`_simulateGame` swallows it, so the league plays on around the wreckage with no
visible failure beyond a log line.
"""
import sys, types


class FakePos:
    def __init__(self, v): self.value = v


class FakePlayer:
    def __init__(self, pid, posValue):
        self.id, self.position = pid, FakePos(posValue)
        self.capHit, self.currentNumber, self.team = 0, 7, None
        self.name = f'P{pid}'


class FakeTeam:
    def __init__(self, tid):
        self.id, self.name = tid, f'T{tid}'
        self.rosterDict = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None, 'te': None, 'k': None}
        self.playerCap, self.playerNumbersList = 0, []

    def assignPlayerNumber(self, p): p.currentNumber = 1


SLOTS = ('qb', 'rb', 'wr1', 'wr2', 'te', 'k')


def _rebuild(team, players):
    """The rebuild from teamManager, reduced to the part under test."""
    team.rosterDict = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None, 'te': None, 'k': None}
    wrCount = 0
    posMap = {1: 'qb', 2: 'rb', 3: 'wr', 4: 'te', 5: 'k'}
    for player in players:
        posKey = posMap.get(player.position.value)
        if posKey is None:
            continue
        if posKey == 'wr':
            wrCount += 1
            if wrCount > 2:
                continue
            key = f'wr{wrCount}'
        else:
            if team.rosterDict.get(posKey) is not None:
                continue
            key = posKey
        team.rosterDict[key] = player
    return team.rosterDict


def test_aVacantSlotIsNoneAndNotAMissingKey():
    """⚠️ Rebuilding from `{}` left a vacancy with NO KEY, and the engine indexes the
    dict directly — measured on a real development database mid-offseason, that was
    **92 failed games in the first two seconds of a boot**, each one a swallowed
    `KeyError: 'qb'`.

    Bite check: rebuild from `{}` and the assertion below raises KeyError, which is
    exactly what production did.
    """
    team = FakeTeam(1)
    # A team with no quarterback and no kicker — the shape an offseason leaves behind
    # before the free-agent draft fills the holes.
    roster = _rebuild(team, [FakePlayer(2, 2), FakePlayer(3, 3), FakePlayer(4, 3), FakePlayer(5, 4)])
    for slot in SLOTS:
        assert slot in roster, f'{slot} key vanished; the engine indexes this directly'
    assert roster['qb'] is None and roster['k'] is None, 'a vacancy is None'
    assert roster['rb'] is not None and roster['wr1'] is not None and roster['wr2'] is not None


def test_theSingleSlotGuardStillFillsTheSlot():
    """⚠️ THE TWO CHANGES HAVE TO LAND TOGETHER. The dedupe guard was `if pos_key in
    rosterDict: continue`, which with pre-seeded keys is true BEFORE anyone is assigned —
    so seeding the slots without fixing the guard leaves every single-slot position empty
    and is worse than the bug it fixes.

    Bite check: restore the `in` test and qb/rb/te/k all come back None.
    """
    team = FakeTeam(2)
    roster = _rebuild(team, [FakePlayer(1, 1), FakePlayer(2, 2), FakePlayer(6, 4), FakePlayer(7, 5)])
    assert roster['qb'].id == 1, 'the single-slot guard blocked the first assignment'
    assert roster['rb'].id == 2 and roster['te'].id == 6 and roster['k'].id == 7


def test_theSecondPlayerAtASingleSlotIsIgnored():
    team = FakeTeam(3)
    roster = _rebuild(team, [FakePlayer(1, 1), FakePlayer(9, 1)])
    assert roster['qb'].id == 1, 'the first player at a single slot keeps it'


def test_aThirdReceiverIsIgnoredRatherThanOverwritingWr2():
    team = FakeTeam(4)
    roster = _rebuild(team, [FakePlayer(1, 3), FakePlayer(2, 3), FakePlayer(3, 3)])
    assert roster['wr1'].id == 1 and roster['wr2'].id == 2
