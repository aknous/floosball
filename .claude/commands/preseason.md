---
description: Forecast the upcoming season by simulating it many times from a prod snapshot (title odds + average wins per team)
argument-hint: [optional — season number and run count, e.g. "season 4, 25 runs"; defaults to the season prod is about to start]
---

Forecast the season prod is about to play. Focus: $ARGUMENTS

Run the upcoming season many times from a copy of the live database and report who
wins the Floos Bowl and how many games each team averages. Every run starts from the
identical schedule and rosters, so the spread is the sim's own variance.

Do this **between the offseason finishing and the first kickoff**. That window is the
only time the starting line is fair (see the timing trap below).

## 1. Pull a snapshot

Prod's SQLite is at `/data/floosball.db` (~180MB). Copy it down; never simulate
against prod itself.

```bash
mkdir -p /tmp/floo_preseason
fly ssh sftp get /data/floosball.db /tmp/floo_preseason/prod.db
```

Confirm the state before spending time on runs. There is **no sqlite3 binary on prod**,
so if you want to check remotely first, wrap it in a `python3` heredoc (`/dbquery`).

## 2. Run the suite

```bash
.venv/bin/python tools_preseason.py \
  --db /tmp/floo_preseason/prod.db --season 4 --runs 25 --parallel 5
```

- `--runs 25` is a good default. Title odds are the noisy number and want the volume;
  average wins settle much earlier.
- `--parallel 5` on a 10-core machine. Each sim pins roughly one core, so leave the
  owner headroom — they are usually running their own dev server.
- A run takes about 90 seconds solo, longer in a parallel batch. 25 runs is ~8 minutes.
- `--json out.json` keeps the raw per-run results if you want to slice them further.

The tool refuses a snapshot that is not a fair starting line and says why
(`--allow-any-state` overrides). Launch it with `run_in_background: true` and wait on
the process rather than polling the results directory.

## 3. Report

Give the user, in this order:

1. **The Floos Bowl for every run** — they asked for each one, not just the tally.
2. **Title odds** — how often each team won, as a count and a percentage.
3. **Average wins for all teams**, with the spread (SD, min, max). The min and max
   matter more than the average here: a team averaging 14 with a 9 to 19 range is a
   different story from one that lands on 14 every time.

Sanity checks worth stating: the league mean must come out at exactly half the games
per team (every game has one winner, so this is fixed by the schedule, not a result),
and every team must have played the full slate.

If one team dominates, check whether that is roster strength before calling it a bug:

```bash
SELECT t.name, ROUND(AVG(p.player_rating),1) FROM players p
JOIN teams t ON t.id = p.team_id WHERE p.team_id IS NOT NULL
GROUP BY t.name ORDER BY 2 DESC
```

## Traps

**The sim does not stop at a season boundary.** `run_api.py` plays the offseason and
rolls into the next season, and the one after. The tool kills each run when its Floos
Bowl goes final. A hand-rolled harness that forgets this reached season 6.

**Do not detect completion with a game count.** A season-N game count stops changing
when season N ends *and* when the sim has moved on to N+1. The two look identical, so
a count-based poll reports a finished season while the process runs on for another ten
minutes, burning a core. Gate on the Floos Bowl row.

**Snapshot timing decides whether the question is even answerable.** Take it once prod
is at week 0 with the schedule generated. Taken during the offseason, each run holds
its own draft and free agency, so the rosters differ before week 1 and the runs are no
longer forecasting the same season. Prod sits in the right state for roughly the gap
between the offseason completing and the opening kickoff.

**Only the `--timing=fast` mode is safe here**, and only against a copy. Never point a
run at `data/` or at port 8000, which is the owner's dev server.

**Clean up.** Kill every sim you started (`ps aux | grep '[r]un_api.py'`, kill by PID;
the season loop survives some signals, which is why the tool kills the process group)
and remove the work directory. Each run copies the whole database, so 25 runs is
several GB.

**Never let a `rm -rf` glob reach the harness.** `rm -rf /tmp/.../run*` once deleted
the runner script itself, and the driver then invoked a missing file twenty times
while reporting each batch as done. That is why the tool keeps run directories under
a work dir it owns.
