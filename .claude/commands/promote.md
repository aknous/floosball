---
description: Merge development → main and push (after explicit user confirmation), then return to development
---

Promote development to main for deploy. This is a prod-impacting operation — confirm with the user before running it if they haven't already authorized it in this turn.

## Pre-flight checks

Run in parallel:
1. `git status` on the current repo — confirm clean working tree (no uncommitted changes)
2. `git log origin/main..origin/development --oneline` — show what's about to land on main; if empty, abort with "nothing to promote"
3. `git branch --show-current` — confirm we're on a branch that's safe to leave (typically `development`)

Report the list of incoming commits to the user before proceeding. If anything looks unexpected (e.g. unfamiliar commits, a hotfix the user didn't write, force-pushes evident in history), stop and ask.

## Promotion

Once authorized:

```bash
git checkout main
git pull origin main
git merge development --no-ff -m "Merge development: <one-line summary of the incoming commits>"
git push origin main
git checkout development
```

Use `--no-ff` always — the merge commit is the audit trail. The commit message should be one short line summarizing the incoming work, not a bullet list.

## Post-promotion

After pushing, remind the user that `fly deploy` is the next step — but **do not** run `fly deploy` yourself unless explicitly asked. Mention that the inline migrations (if any new ones landed) will run on next boot.

If this was a frontend repo promotion, the next step is the deploy pipeline on that side instead.

## Safety

- Never `git push --force` to main.
- If pre-flight reveals merge conflicts, stop and report them — don't try to resolve heuristically.
- If the user hasn't tested the development changes in this session and nothing in conversation indicates they've tested separately, ask before promoting.
