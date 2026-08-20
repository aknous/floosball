#!/usr/bin/env bash
# Run the whole backend test suite.
#
# ⚠️ THERE ARE THREE TEST STYLES IN THIS REPO AND NO SINGLE COMMAND RUNS THEM ALL.
# That is not cosmetic: a failing test hid behind it for as long as it took someone to
# report the bug from a live game.
#
#   1. self-running   — has `if __name__ == '__main__'`, must be invoked DIRECTLY.
#                       Calls sys.exit() at module level, which ABORTS pytest collection
#                       for the entire run, so these can never be in a pytest invocation.
#   2. module-level   — assertions run on import. Works invoked directly. Under pytest it
#                       reports "no tests ran" even though the checks did run.
#   3. pytest-style   — only `def test_*` functions. Invoked directly it defines them and
#                       exits 0 having run NOTHING, reporting a pass it never earned.
#
# Style 3 is the dangerous one: `python test_punt_play_text.py` exited 0 with nine tests
# unrun, one of which was failing and encoded a real play-by-play bug.
#
# Usage:  ./run_tests.sh            all tests
#         ./run_tests.sh pattern    only files matching the pattern
set -uo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
PATTERN="${1:-}"

pass=0; fail=0; failed=""
for f in test_*.py; do
  [ -n "$PATTERN" ] && [[ "$f" != *"$PATTERN"* ]] && continue
  # ⚠️ `__main__` ALONE IS THE WRONG SIGNAL. Style 2 files run their assertions at
  # module level and call sys.exit() there WITHOUT a __main__ guard — handing one of
  # those to pytest aborts collection with INTERNALERROR: SystemExit, which reads as a
  # failure and is really the runner's mistake. Anything that exits at import time must
  # be run directly.
  if grep -qE "__main__|^[[:space:]]*sys\.exit\(" "$f"; then
    # styles 1 and 2 — direct
    if $PY "$f" >/tmp/_floo_test_out 2>&1; then pass=$((pass+1)); else fail=$((fail+1)); failed="$failed $f"; fi
  else
    # style 3 — pytest. A file whose checks are module-level reports "no tests ran"
    # while having already run them on import; exit 5 means collected-nothing, not failure.
    $PY -m pytest "$f" -q --no-header -p no:cacheprovider >/tmp/_floo_test_out 2>&1
    rc=$?
    if [ $rc -eq 0 ] || [ $rc -eq 5 ]; then pass=$((pass+1)); else fail=$((fail+1)); failed="$failed $f"; fi
  fi
done

echo "pass=$pass  fail=$fail"
if [ -n "$failed" ]; then
  echo "FAILING:"
  for f in $failed; do echo "  $f"; done
  exit 1
fi
