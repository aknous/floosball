# Fan-Voted Awards — MVP & Hall of Fame

Move the two season-end honors from algorithm-decided to **fan-voted**, with the
existing value-metric / HoF-points algorithms demoted to *shortlister* and
*fallback*. The metagame already has a mature voting system (GM / Front Office);
this builds on those patterns.

Status: **designed + decisions locked 2026-06-15**, not built. Backend
`development`. No code written yet.

## Locked decisions
- **MVP**: the value metric nominates (top 3 per position); fans elect a single
  winner (plurality, value-metric rank as tiebreak).
- **HoF**: every retiree is a candidate, but `_computeHofPoints` **pre-filters**
  the ballot to real contenders (no new rostered-seasons tracking). NFL-style
  approval vote, **class capped at 5/season**, rolling ballot.
- **Fallback**: below a turnout quorum (and in all fast/sim modes), the current
  algorithms decide — value-metric MVP, `inductHallOfFame` points induction.
  Awards always resolve.
- **Cost**: voting is **free** for both (civic/engagement, not a Floobit sink).
- **Vote storage**: reuse the GM voting *patterns*, but a **dedicated
  `AwardVote` table** — `GmVote` is team-scoped (`team_id` NOT NULL,
  `models.py:1652`) and these awards are league-wide.

## Why the timing works (the key insight)
**Week 22 (`GM_ACTIVE_WEEK`) is already the moment everything locks**, so both
ballots seed off events that already exist:
- `_evaluateRetirementCandidates` (`seasonManager.py:6018`) rolls retirements and
  sets `willRetire=True`. **This is final** — `willRetire` is never cleared
  anywhere, re-sign votes on a `willRetire` player return outcome `"retiring"`
  (`gmManager.py:351`), and retirement **overrides** re-sign at execution
  (`seasonManager.py:5933`, "Player retires (overrides re-sign)"). So the
  week-22 retiring set **is** the final retiree set — no "confirm at induction"
  guard needed.
- FA retirees are removed at week 22 (`_processFreeAgentRetirements`).
- `front_office_fan_snapshot` (`models.py:812`) freezes the per-team fan count at
  week 22 — the same snapshot the award quorum can key off.

## MVP
- **Eligibility / ballot**: top 3 per position by `mvpScore`
  (`playerManager.py:2535`, already returns candidates sorted by
  `offenseScore + defValue`). ~15 names; the value metric keeps scrubs off the
  ballot. Defensive value is already folded into `mvpScore`, so the ballot spans
  offense + defense without a separate award.
- **Mechanic**: one vote per fan, most votes wins. `mvpScore` breaks ties.
- **Window**: opens at **regular-season end (wk 28)** — the shortlist isn't final
  until week-28 stats land — and closes at the **season-end MVP announcement**
  (currently emitted alongside `_selectSeasonAllPro`, `seasonManager.py:9938`,
  called at `:387`).
- **Resolution**: tally votes → winner. If total votes < quorum → the current
  top-`mvpScore` candidate (today's behavior). Emit `mvp_announcement` either
  way; stamp the winner's `mvp_seasons` accolade (existing path).

## Hall of Fame
- **Ballot seeding (wk 22)**: take the just-locked `willRetire` set, run each
  through `_computeHofPoints` (`playerManager.py:1995`), and put the real
  contenders on the ballot. Pre-filter bar is a knob (see below) — looser than
  the auto-induct `HOF_INDUCT_THRESHOLD=22` so borderline cases get a fan vote.
- **Rolling ballot** — new table `HofBallotEntry`:
  - `player_id`, `first_eligible_season`, `seasons_remaining`, `status`
    (`on_ballot` / `inducted` / `dropped`).
  - Each offseason: add the new qualifying retirees; run the vote; induct the
    winners; decrement `seasons_remaining` on the rest; drop entries that hit 0.
  - **Tenure**: retirement season + 4 more = **5 seasons** on the ballot.
- **Mechanic**: approval vote (fans vote "yes" on whoever they want in).
  **Induct the top vote-getters that also clear a minimum approval floor, capped
  at 5/season.** The floor prevents a weak class from forcing 5 in just to fill
  the cap; the cap makes carryover snubs meaningful.
- **Window**: opens at **wk 22** (longest possible window — runs across the
  farewell games, playoffs, and all drafts) and closes at the start of the final
  offseason phase, **`training`** (`OFFSEASON_PARTIAL_PHASES`, `constants.py:894`),
  where induction already runs (`inductHallOfFame`, `playerManager.py:2024`).
- **Accolades recompute at close**: a balloted player can earn a ring / All-Pro
  during their farewell playoff run (wks 29–32) *after* the ballot opened, so the
  displayed HoF case (`_computeHofPoints` breakdown) should refresh at close, not
  freeze at week 22. (Feature: fans react to the farewell run.)
- **Resolution / fallback**: tally → induct top ≤5 above the floor via the
  existing `inductHallOfFame` stamping (`hof_season`, `is_hof`, plaque gallery).
  Below quorum / fast-sim → fall back to the points-threshold induction (today's
  behavior). Either path feeds the same `/api/hall-of-fame` + `HallOfFame.tsx`.

## Data model
- **`AwardVote`** (new) — league-wide, mirrors `GmVote`'s shape minus `team_id`:
  `user_id`, `season`, `award_type` (`mvp` | `hof`), `target_player_id`,
  `direction` (`yea` for both; approval = a `yea` per player for HoF), `created_at`.
  Single net vote per (user, award_type, target) — withdraw to change, exactly
  like the GM single-vote model.
- **`HofBallotEntry`** (new) — rolling ballot state (fields above).
- No change to `Player` (uses existing `is_hof`, `hof_season`, `all_pro_seasons`,
  `league_championships`, `mvp_seasons`).
- Inline migration (`connection.py::_runPendingMigrations`) — both are new
  `CREATE TABLE IF NOT EXISTS`, the prod-safe path.

## Reuse from GM voting (patterns, not the table)
- `gmManager` resolution structure (tally, `calculateProbability`, `_lowQuorum`
  quorum fallback, IRV at `gmManager.py:554` if ranked is ever wanted).
- `front_office_fan_snapshot` for the quorum denominator.
- `CurrencyRepository` is **not** needed (votes are free) — skip the cost/refund
  plumbing.

## API (new endpoints, mirror the GM group)
- `GET /api/awards/mvp/ballot` — candidates + the user's current vote + tally
  (number-free until close, like the recap).
- `POST /api/awards/mvp/vote` — `{playerId}` (replaces prior vote).
- `GET /api/awards/hof/ballot` — current ballot with each player's case,
  seasons_remaining, the user's approvals, live tally.
- `POST /api/awards/hof/vote` — `{playerId, direction}` (approve / withdraw).
- Window state (`open` / `closed`) gates the POSTs, same as per-game pick locks.

## Frontend surfaces
- MVP ballot: Season Recap / a season-end voting card (the MVP panel already
  exists, `MvpRankings.tsx`).
- HoF ballot: a voting view alongside the plaque gallery (`HallOfFame.tsx`),
  showing each candidate's case + seasons left on the ballot.
- Both: WS nudges (`league_news`) when a window opens / is closing.

## Build phases
- **P1 — data + backend voting**: `AwardVote` + `HofBallotEntry` models, inline
  migrations, repositories, vote cast/withdraw, tally.
- **P2 — windows + lifecycle**: open MVP at wk 28 / HoF at wk 22; close + resolve
  MVP at season-end announcement, HoF at the `training` phase; rolling-ballot
  carryover + drop. Wire the algorithm fallbacks.
- **P3 — API**: the four endpoints + window-state gating.
- **P4 — frontend**: MVP + HoF ballot UIs, WS open/closing nudges.
- **P5 — validation**: fast-sim falls back cleanly (no empty awards); a manual
  voting pass resolves; rolling ballot carries snubs across seasons; cap-5 binds
  on a stacked class; CLAUDE.md updated (awards are fan-voted, algorithms are
  shortlist + fallback).

## Open knobs (defaults proposed, confirm at build)
- **MVP quorum**: min total votes before fan result stands (else algorithm).
- **HoF pre-filter bar**: `_computeHofPoints` cutoff for *ballot* entry (looser
  than the 22-point auto-induct).
- **HoF approval floor**: min approval (fan-count or %) to be induct-eligible
  under the cap.
- **HoF class cap**: **5** (locked).
- **HoF ballot tenure**: **5 seasons** (locked).

## Sequencing note
Both windows live in the season-transition flow that the deferred **FO
vote-resolution-timing** change also touches (see memory
`front_office_voting_resolution_timing`). Design the transition windows once,
together, to avoid reworking it twice.

## Deploy-timing constraint
For this to fire **this** season (prod is mid-season 10), MVP voting must ship
before week 28 and HoF before the offseason `training` step. Real clock.
