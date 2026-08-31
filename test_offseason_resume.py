"""Restarting during the offseason must not skip, delay or re-run the draft.

⚠️ REPORTED AS A LONG-STANDING HAZARD (owner, 2026-08-28): "this has always been a bad
time to restart because it sometimes skips the draft or just runs it immediately."

Three separate defects, all with ONE root cause: `_setOffseasonFlow` persists
`offseason_phase_target` at every phase change — and **no wait ever read it back**. Each
gate invented its own timing instead.

    gate                    what it did                     on restart
    waitPostChampionship    flat asyncio.sleep(3600)        re-waits the FULL hour
    waitUntilNoonEt         polls to a RECOMPUTED noon      +24h if the target just passed
    in_offseason write      after runSeasonSimulation ret.  offseason skipped entirely

⚠️ THE THIRD IS THE ONE THAT SKIPS THE DRAFT. The phase is stamped `post_bowl` INSIDE
`_completeSeasonSimulation`, but `in_offseason` was written only by the application loop
after `runSeasonSimulation` RETURNS. In that window the database says
`offseason_phase='post_bowl'` and `in_offseason=False`, so a restart matches neither the
offseason branch nor the playoff branch, falls through to "start new season", and the
offseason never runs.

⚠️ THE SECOND IS THE MOST DECEPTIVE. It polled honestly — but always to
`_nextNoonEasternUtc()`, recomputed at call time. A restart a minute BEFORE the target
resumes correctly; a minute AFTER it, that noon is gone, the next one is computed, and the
draft moves a full day. A 24-hour miss decided by deploy timing.

⚠️ Sections 1-3 are BEHAVIORAL — they call the real waits and time them. Sections 4-5 are
structural source assertions, because the write they guard happens inside a database
session on the season manager and there is no cheap seam to drive it. Stated rather than
blurred: a source-text assertion fails on an innocent rename and passes on a regression
that keeps the same words.

⚠️ Verified against the LIVE offseason this was reported from (`phase='frontoffice'`,
`target='2026-08-29 16:00:00'`): the frontoffice phase's target is set by
`_computeDraftDayTarget()`, which in SCHEDULED returns the same next-noon-ET that
`waitUntilNoonEt` computed for itself. So the two agree at SET time and this changes
RESUME behavior only — never the happy path.

Run: .venv/bin/python test_offseason_resume.py
"""
import asyncio
import datetime
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.CRITICAL)

from managers.timingManager import TimingManager, TimingMode

HERE = os.path.dirname(os.path.abspath(__file__))
SEASON_SRC = io.open(os.path.join(HERE, 'managers', 'seasonManager.py'),
                     encoding='utf-8').read()

failures = []
def expect(desc, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {desc}")
    if not cond: failures.append(desc)


def _tm():
    tm = TimingManager(TimingMode.SCHEDULED)
    # Poll fast so the test does not actually wait; the target logic is what matters.
    tm.delays = dict(tm.delays)
    tm.delays['daily_check'] = 0.01
    tm.delays['post_championship'] = 3600.0
    return tm


print("1. A target already in the past means the wait is OVER")
# ⚠️ Proceeding is the correct reading of "the hour has elapsed" — not a skip. This is
# what makes a restart after the moment resume instead of re-waiting.
past = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
t0 = datetime.datetime.utcnow()
asyncio.run(_tm().waitPostChampionship(past))
expect(f"post-championship with a past target returns at once "
       f"({(datetime.datetime.utcnow()-t0).total_seconds():.2f}s)",
       (datetime.datetime.utcnow() - t0).total_seconds() < 1.0)

t0 = datetime.datetime.utcnow()
asyncio.run(_tm().waitUntilNoonEt(past))
expect(f"draft day with a past target returns at once — never +24h "
       f"({(datetime.datetime.utcnow()-t0).total_seconds():.2f}s)",
       (datetime.datetime.utcnow() - t0).total_seconds() < 1.0)


print("\n2. A target still ahead is honored, not restarted")
soon = datetime.datetime.utcnow() + datetime.timedelta(seconds=0.25)
t0 = datetime.datetime.utcnow()
asyncio.run(_tm().waitPostChampionship(soon))
waited = (datetime.datetime.utcnow() - t0).total_seconds()
# ⚠️ The point: it waits the REMAINING quarter-second, not a fresh `post_championship`
# hour. Before the fix this call slept 3600s regardless of the target.
expect(f"it waits the remaining time, not the full delay again ({waited:.2f}s)",
       0.1 < waited < 3.0)


print("\n3. With no target it still behaves as before")
# Fast modes and any caller that has nothing persisted must be unaffected.
fast = TimingManager(TimingMode.FAST)
t0 = datetime.datetime.utcnow()
asyncio.run(fast.waitPostChampionship())
asyncio.run(fast.waitUntilNoonEt())
expect("fast mode flows straight through with no target",
       (datetime.datetime.utcnow() - t0).total_seconds() < 1.0)


print("\n4. The flag and the phase cannot disagree")
# ⚠️ THE ONE THAT SKIPPED THE DRAFT. `in_offseason` must be written the moment a phase
# exists, not after the season simulation returns.
expect("_persistOffseasonFlow sets in_offseason when a phase is set",
       'row.in_offseason = True' in SEASON_SRC)
expect("...guarded on a non-null phase, so the end-of-offseason clear is not undone",
       'if self._offseasonFlowPhase:\n                    row.in_offseason = True' in SEASON_SRC)

print("\n5. The persisted target actually reaches the waits")
expect("post-championship is given the stored target",
       'waitPostChampionship(self._offseasonFlowTarget)' in SEASON_SRC)
expect("draft day is given the stored target",
       'waitUntilNoonEt(self._offseasonFlowTarget)' in SEASON_SRC)
# ⚠️ The comment that sent me looking: it claimed the post-championship wait polled to a
# target when it slept a flat hour. A false claim about idempotency is worse than none.
expect("the comment no longer claims the wait is idempotent on its own",
       'waitPostChampionship clock check is itself idempotent' not in SEASON_SRC)

print()
if failures:
    print(f"{len(failures)} FAILED"); sys.exit(1)
print("PASS — a restart resumes the offseason where it stood.")
