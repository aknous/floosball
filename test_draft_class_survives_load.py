"""The rookie class must survive a restart, and the draft must not run twice.

⚠️ THE CLASS-DESTROYING TRAP. `68e5608` removed the draft and, correctly for that world,
made `assignPlayersToTeams` RELEASE every `is_upcoming_rookie` into free agency on load —
the draft was the only thing that ever cleared the flag, so a class left in the database
would have been stranded forever.

With the draft restored that same block is a bug of the opposite sign: the class is
generated at SEASON START and drafted in the OFFSEASON, so a release-on-load empties it
on the very next restart and the draft finds nothing to pick. Between those two moments
sits an entire season, and this project deploys weekly.

The release survives, gated, for the one case that still needs it — a database carrying
a class with the draft switched OFF.

⚠️ AND THE SECOND DOOR IS QUIETER THAN THE FIRST. Even with the release gated, the
free-agent loop below it resolves `player.team` to a club and falls through to the FA
branch for anything it cannot place. `'Upcoming Rookie'` is not a club.
"""

import os
import tempfile

os.environ['DATABASE_DIR'] = tempfile.mkdtemp(prefix='floos_class_')

import inspect                                                   # noqa: E402

import constants                                                 # noqa: E402
from managers.playerManager import PlayerManager                 # noqa: E402


def _source():
    return inspect.getsource(PlayerManager.assignPlayersToTeams)


def test_the_release_is_gated_on_the_draft_being_off():
    src = _source()
    assert 'rookieDraftEnabled()' in src, \
        "the upcoming-rookie release is ungated — a restart empties the class"
    release = src.index('is_upcoming_rookie = False')
    gate = src.index('if not rookieDraftEnabled():')
    assert gate < release, "the release runs before its own gate"
    print("PASS the release only runs when the draft is off")


def test_the_free_agent_loop_skips_upcoming_rookies():
    """⚠️ THE QUIET SECOND DOOR. Gating the release alone is not enough: the loop below
    it marks anything whose `team` does not resolve to a club as a free agent, and
    `'Upcoming Rookie'` never will. Same class destruction, no log line."""
    src = _source()
    faLoop = src.index('faCount = 0')
    tail = src[faLoop:]
    guard = tail.index("is_upcoming_rookie")
    freeAgentBranch = tail.index("player.team = 'Free Agent'")
    assert guard < freeAgentBranch, \
        "the FA loop reaches its free-agent branch before excluding upcoming rookies"
    print("PASS the free-agent loop excludes the draft class")


def test_the_flag_has_readers_now():
    """⚠️ `ROOKIE_DRAFT_ENABLED` HAD ZERO READERS FOR SIX WEEKS. It was declared, its
    comment described the switch in the present tense, and flipping it did nothing at
    all — the same trap class as `AUTONOMOUS_FO_ENABLED`, polarity reversed. The plan's
    instruction was "delete it or wire it, but do not start here believing it is the
    switch." It is wired."""
    import subprocess
    out = subprocess.run(
        ['grep', '-rln', 'rookieDraftEnabled', '--include=*.py', '.'],
        capture_output=True, text=True).stdout.split()
    readers = [f for f in out if 'constants.py' not in f and 'test_' not in f]
    # The claim is ZERO -> some, not a particular count. Both managers read it,
    # each at more than one site (the load path, class generation, the phase).
    assert len(readers) >= 2, readers
    print(f"PASS the switch is read by {len(readers)} modules: "
          f"{sorted(os.path.basename(f) for f in readers)}")


def test_there_is_one_definition_of_whether_the_draft_runs():
    """Two call sites computed `FLAG and not os.environ.get('NO_ROOKIE_DRAFT')`
    independently before. That is how a flag and its override drift apart."""
    assert callable(constants.rookieDraftEnabled)
    original = constants.ROOKIE_DRAFT_ENABLED
    try:
        constants.ROOKIE_DRAFT_ENABLED = False
        assert constants.rookieDraftEnabled() is False
        constants.ROOKIE_DRAFT_ENABLED = True
        assert constants.rookieDraftEnabled() is True
        os.environ['NO_ROOKIE_DRAFT'] = '1'
        assert constants.rookieDraftEnabled() is False, \
            "the sim/harness escape hatch does not work"
    finally:
        constants.ROOKIE_DRAFT_ENABLED = original
        os.environ.pop('NO_ROOKIE_DRAFT', None)
    print("PASS one definition, and the env override still works")


def test_generation_is_idempotent_across_restarts():
    """⚠️ `startNewSeason` IS ALSO THE MID-SEASON RESUME PATH, called on every deploy. A
    non-idempotent generator there mints a fresh class on every restart and the draft
    pool grows without bound."""
    import managers.seasonManager as sm
    src = inspect.getsource(sm.SeasonManager.startNewSeason)
    block = src[src.index('rookieDraftEnabled()'):]
    assert 'existingUpcoming' in block[:600]
    assert 'reusing' in block[:900], "no reuse path — a restart would mint a second class"
    print("PASS an existing class is reused, never topped up")
