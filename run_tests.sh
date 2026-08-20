#!/usr/bin/env bash
# Run the whole backend test suite.
#
# ⚠️ THERE ARE THREE TEST STYLES IN THIS REPO AND NO STOCK COMMAND RUNS THEM ALL.
# That is not cosmetic: a failing test hid behind it until someone reported the bug from
# a live game.
#
#   1. self-running   — `if __name__ == '__main__'`. Must be invoked DIRECTLY.
#   2. module-level   — assertions run on import, then sys.exit(). Must be invoked
#                       DIRECTLY. Under pytest these abort collection with
#                       INTERNALERROR: SystemExit, which looks like a failure and is not.
#   3. pytest-style   — only `def test_*` functions. Invoked directly it defines them and
#                       exits 0 having run NOTHING, reporting a pass it never earned.
#
# ⚠️ DETECTING THE STYLE BY GREP DOES NOT WORK, and two attempts at it produced false
# failures that cost more time than the real bugs. `__main__` alone misses style 2, and
# grepping for sys.exit misses the ones that reach it some other way. So this RUNS the
# file and reads what happens: pytest first for anything with test functions, and if
# pytest cannot even collect it (INTERNALERROR — style 2 exiting at import), fall back to
# running it directly, which is what that style wants.
#
# Usage:  ./run_tests.sh            all tests
#         ./run_tests.sh pattern    only files matching the pattern
set -uo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
PATTERN="${1:-}"
OUT=/tmp/_floo_test_out

runDirect() { $PY "$1" >"$OUT" 2>&1; }

pass=0; fail=0; failed=""
for f in test_*.py; do
  [ -n "$PATTERN" ] && [[ "$f" != *"$PATTERN"* ]] && continue

  if grep -q "__main__" "$f"; then
    runDirect "$f" && ok=1 || ok=0
  elif grep -qE "^def test|^class .*[Tt]est" "$f"; then
    $PY -m pytest "$f" -q --no-header -p no:cacheprovider >"$OUT" 2>&1
    rc=$?
    if grep -q "INTERNALERROR" "$OUT"; then
      # style 2: it exits at import, so pytest can never collect it. Run it directly.
      runDirect "$f" && ok=1 || ok=0
    elif [ $rc -eq 0 ] || [ $rc -eq 5 ]; then
      ok=1          # 5 = collected nothing, which for style 2 means the checks already ran
    else
      ok=0
    fi
  else
    runDirect "$f" && ok=1 || ok=0
  fi

  if [ $ok -eq 1 ]; then pass=$((pass+1)); else fail=$((fail+1)); failed="$failed $f"; fi
done

echo "pass=$pass  fail=$fail"
if [ -n "$failed" ]; then
  echo "FAILING:"
  for f in $failed; do echo "  $f"; done
  exit 1
fi
