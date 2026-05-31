---
description: Run an isolated fresh fast simulation and sanity-check league/economy/offseason health (for validating engine, season, card, or balance changes)
argument-hint: [optional — what to focus on, e.g. "offseason FA draft" or "card payouts" or just leave blank for a full health pass]
---

Validate the sim by running a fresh fast season in isolation and inspecting outcomes. Focus: $ARGUMENTS

This is the project's standard way to confirm a backend change didn't break the sim. For verifying a *specific user-facing behavior* in the running app, the generic `/verify` or `/run` skills may fit better — this one is about holistic sim health.

## Run in isolation (never clobber the dev DB on :8000)
Point the run at a throwaway DB dir and a non-default port, in the background:

```bash
DATABASE_DIR=/tmp/floo_simcheck PORT=8099 .venv/bin/python run_api.py --fresh --timing=fast
```

- `DATABASE_DIR` (default `data`) redirects the SQLite file + flag files; `PORT` (default 8000) avoids colliding with the user's dev server.
- `--fresh --timing=fast` = clean DB, no delays (a full season + playoffs + offseason runs in seconds to a minute).
- Run it backgrounded and poll/stream the log rather than blocking. `rm -rf /tmp/floo_simcheck` when done.

## Health checks (read the logs + the throwaway DB)
Confirm, at minimum:
1. **No tracebacks / ERROR lines** in stdout or `logs/floosball.log`. A silent rollback (e.g. "GM ... resolution error", "database is locked") is the usual failure mode — grep for `Error|Traceback|locked|rollback`.
2. **A full season completes**: 28 regular-season weeks → playoffs (`Playoffs Round 1/2`, `League Championship`, `Floos Bowl`) → offseason → next `season_start`. The offseason must pass every gate (`frontoffice_decisions`, `rookie_draft`, `fa_draft`, `training_and_finalize`).
3. **Scores are realistic**: roughly ~20 ppg, no rashes of 0-0 or 80-point games. Query `games` in the throwaway DB or scan the play-by-play logs.
4. **Rosters stay full**: after the FA draft, every team has all 6 slots (`qb/rb/wr1/wr2/te/k`) filled. Empty slots after the draft = a bug (e.g. an over-aggressive FA exclusion).
5. **Economy sane**: weekly FP→Floobit payouts land on the expected curve (`round(0.43 × FP^0.78)`), no negative balances.

For a focused change, add the relevant check:
- **Card/effect change** → inspect `weekly_card_bonuses.breakdowns_json` for a user, or use the `card-effect-investigator` agent against the throwaway DB.
- **GM/offseason change** → confirm `gm_vote_results` outcomes and that fired/cut/unre-signed players left rosters and weren't re-signed by the same team.
- **Balance change** → pull season aggregates (avg ppg, ypp) from the `games` / `team_season_stats` tables.

## Report
State plainly what ran, what you observed (with the actual numbers / log lines), and whether each health check passed. If something failed, quote the error and point at the likely code path — don't just say "looks fine." Tear down `/tmp/floo_simcheck` afterward.
