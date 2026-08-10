# Recovered from the reverted progression commit

These were deleted by `54a6275`, the revert of `2a37f2f` ("Progression: per-activity ranks
+ permanent overall level + profile API"). The revert was for **timing, not design** — the
work was built and shipped-ready, then pulled from the release.

`docs/NEXT_SEASON.md` and the Renown plan both reference `docs/PICKEM_DEPTH_PLAN.md` as if
it exists. It did not: the revert took it with the code, and nothing noticed because a
missing markdown file breaks no build. Restored here rather than at the original paths so
it is unambiguous that this is **history, not current design**.

| file | what it is |
|---|---|
| `PICKEM_DEPTH_PLAN.md` | pick-em depth + Survivor. The reference that next-season item 9 (prognostication) has been pointing at. |
| `PROGRESSION_PLAN.md` | the achievement-derived progression model. **Superseded by Renown** (owner, 2026-07-31) — kept for the parts worth salvaging, not as a live spec. |
| `progressionManager.py.txt` | the 172-line implementation, plus `GET /api/profile/{userId?}`. No schema changes, so it is cherry-pickable. Relevant to items 3 and 4. |

⚠️ Read against the code before trusting any of it. It predates the fantasy/cards fusion,
the autonomous front office and the 24 → 32 expansion.

To restore the code rather than read it: `git show 2a37f2f -- managers/progressionManager.py api/main.py`
