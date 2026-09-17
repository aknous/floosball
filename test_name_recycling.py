"""Every retirement returns its name to the pool, not just rostered ones.

⚠️ THE FAILURE IS SILENT AND ARRIVES LATE. A drained pool makes `createPlayer` return
None, `ensurePositionSupply` used to swallow that, and the first visible symptom is a
team with an empty roster slot whose games cannot be simulated — seasons after the leak
started.
"""
import os, tempfile
os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_names_')


class FakePM:
    """The two methods under test, lifted onto a stub so this needs no app boot."""
    def __init__(self):
        self.pending = []
        self.unusedNames = []

    def addPendingName(self, name, availableSeason):
        self.pending.append((name, availableSeason))

    recycleRetiredName = None   # bound below from the real implementation


def _realRecycle():
    from managers.playerManager import PlayerManager
    return PlayerManager.recycleRetiredName


def test_theLadderClimbsOneRungPerRetirement():
    pm = FakePM()
    recycle = _realRecycle()
    assert recycle(pm, 'Bizzy Bone', 1) == 'Bizzy Bone Jr.'
    assert recycle(pm, 'Bizzy Bone Jr.', 1) == 'Bizzy Bone III'
    assert recycle(pm, 'Bizzy Bone III', 1) == 'Bizzy Bone IV'
    assert recycle(pm, 'Bizzy Bone IV', 1) == 'Bizzy Bone V'
    assert recycle(pm, 'Bizzy Bone V', 1) == 'Bizzy Bone VI'


def test_everyRecycledNameIsHeldForReuseRatherThanLost():
    pm = FakePM()
    recycle = _realRecycle()
    for n in ('A One', 'B Two', 'C Three'):
        recycle(pm, n, 5)
    assert len(pm.pending) == 3, 'a recycled name must be queued, not dropped'
    from constants import NAME_REUSE_DELAY_SEASONS
    assert all(season == 5 + NAME_REUSE_DELAY_SEASONS for _, season in pm.pending)


def test_theFreeAgentRetirementPathRecyclesTheName():
    """⚠️ THE LEAK. `_processFreeAgentRetirements` calls `retirePlayer`, which does NOT
    recycle — so on a mature league, where free agents are the bulk of retirements, the
    pool only ever drains. Measured over 49 simulated seasons: **1,014 free-agent
    retirements burned a name against 676 released back**, ~7 lost a season.

    Bite check: drop the `recycleRetiredName` call from that path and this fails.
    """
    import inspect
    from managers.playerManager import PlayerManager
    src = inspect.getsource(PlayerManager._processFreeAgentRetirements)
    # ⚠️ THE CALL, NOT A MENTION. Asserting the bare name passed vacuously: the comment
    # explaining the fix sits directly above the call and contains the word, so deleting
    # the call left the assertion satisfied. Same trap as asserting a helper is "present"
    # in a function that merely names it in prose.
    assert 'self.recycleRetiredName(' in src, \
        'the free-agent retirement path does not return the name to the pool'


def test_theSupplyFloorDoesNotSwallowAFailedCreate():
    """⚠️ A supply floor that cannot meet its floor must not report success. It logged
    what it MANAGED to make and never what it FAILED to: `generated {'TE': 1}` against a
    deficit of 11 TE and 5 K, on a database where six teams then had no tight end.

    Bite check: restore the bare `continue` and this fails.
    """
    import inspect
    from managers.playerManager import PlayerManager
    src = inspect.getsource(PlayerManager.ensurePositionSupply)
    assert 'COULD NOT BE MET' in src, 'the floor still fails quietly'
    assert 'logger.error' in src, 'an unfillable roster slot is an error, not a warning'


def test_seasonManagerDelegatesRatherThanKeepingASecondLadder():
    """Two copies is how a rung gets added to one and not the other."""
    import inspect
    from managers.seasonManager import SeasonManager
    src = inspect.getsource(SeasonManager._recyclePlayerName)
    assert 'recycleRetiredName' in src, 'seasonManager must delegate to the one ladder'
    assert "endswith('Jr.')" not in src, 'a second copy of the ladder has reappeared'


def test_aFreeAgentWhoNeverPlayedReturnsHisBASEName():
    """⚠️ THE LADDER SAYS A FOOTBALLER CAME BEFORE. A free agent who sat in the pool until
    he retired had no career for a son to follow, so minting "X Jr." invents a father
    nobody saw — the same reasoning `_removeFromPool` already applies to a culled player.
    His base name goes straight back, immediately available, with no hold.

    Bite check: recycle every retiree through the ladder and this fails.
    """
    import inspect
    from managers.playerManager import PlayerManager
    src = inspect.getsource(PlayerManager._processFreeAgentRetirements)
    assert '_playersWithARecord' in src, \
        'the path does not distinguish a player who actually played'
    assert 'self.unusedNames.append(name)' in src, \
        'a never-rostered retiree must go back as the BASE name, not up the ladder'


def test_havingPlayedIsNotAskedViaSeasonsPlayed():
    """⚠️ `seasonsPlayed` IS INCREMENTED FOR AN UNSIGNED FREE AGENT TOO, so it reads as a
    career for a man who never took a snap — the exact trap that made the cull's first
    predicate remove nobody. The question is asked through `_playersWithARecord`."""
    import inspect
    from managers.playerManager import PlayerManager
    src = inspect.getsource(PlayerManager._processFreeAgentRetirements)
    nameReturn = src.split('Free-agent names returned')[0].split('retirements:')[-1]
    assert 'seasonsPlayed' not in nameReturn, \
        'the name-return decision must not key off seasonsPlayed'
