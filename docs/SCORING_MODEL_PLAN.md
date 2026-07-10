# Scoring Model — Design Plan

> A mutable rule (dormant → switched on by a Cores vote, or during Criticality). Owner-specced 2026-07-09.
> Changes **how the score is PRESENTED**, not the points earned. The underlying cumulative points are untouched
> (a TD is still 6/7, etc.); only the *display* transforms. Part of the rule-mutation direction (Tier 3, but
> scoped down). Tracker: `docs/NEXT_SEASON.md` / memory `rule-changes-feature`.
>
> **Scoped for now: DISPLAY ONLY.** Models that change *when a game ends* or the *win condition* (race-to-zero,
> first-to-X) are **deferred** — designed-for but not built. The abstraction below leaves room for them.

## The idea
The score MODEL is how the running tally is shown. The real engine still tracks cumulative points and decides the
winner by them — the model is a lens over those two numbers.

- **`additive`** (default) — today's behavior. Each team shows its cumulative points (`21`, `14`).
- **`differential`** — each team shows its **margin**: the leader is `+N`, the trailer is `-N`, a tie is `0-0`.
  When a team scores a TD, the board reads `+7` / `-7`. Purely a presentation of the same two numbers
  (`home = homeScore - awayScore`, `away = awayScore - homeScore`).

## What does NOT change (the whole point of scoping it here)
Everything reads the **real cumulative scores** exactly as today, so there is **no engine/decision/fairness ripple**:
- Winner determination + game-over, ELO margin-of-victory, standings + tiebreakers, win probability, MVP/WPA,
  pick-em, and the play-caller's scoring-aware decision logic all use `homeScore`/`awayScore` unchanged.
- The model is applied ONLY at the **score-display sites** (the same set the `formatScore` work touched).

This is why it's safe to ship the display models now and defer the win-condition ones — those are the pieces with
the real blast radius.

## The display transform
A single helper: `displayScore(teamScore, oppScore, model)`:
- `additive` → `teamScore` (formatted via `formatScore`).
- `differential` → the signed margin: `teamScore - oppScore`, shown as `+N` / `-N`, `0` when tied. (Still
  `formatScore`-cleaned so float margins read `+6.4` etc.)

Applied everywhere a team score renders: the game-modal scoreboard, the game card, the GameBar, the league-news
feed's final score, and the play-feed running score. (The **quarter-by-quarter table** is a per-quarter breakdown
where cumulative points make sense — recommend it stays `additive` regardless of the model; flag as a small
decision.)

## The rule (toggle + config) — `constants.py` / `game_rules.py`
- `scoringModel` on `GameRules` (`'additive'` default | `'differential'`). Surfaced as the Rulebook popover's
  **"Scoring Model"** row (already teased as "Additive"), which flips to the active model.
- It's an **enum choice among models**, so the vote offers the models as options (a light case of the non-scalar
  vote generalization). During **Criticality**, the model can be randomized (a game shown in differential).
- Exposed on `/api/rules` (league-level); per-game override during chaos is a build detail (the model is
  presentation, so showing a chaos game in differential doesn't leak point values).

## Deferred (designed-for, not built)
Future models that DO change the game — kept out of scope now but the abstraction should accommodate them:
- **race-to-zero / countdown-from-N** — both teams start at N, scoring *subtracts*, first to 0 (or lowest) wins.
  This **inverts "higher is better"** → it would invert the scoring-aware decision tree + WP. Big blast radius.
- **first-to-X / capped** — game ends when a team reaches X points.
- Structure the `ScoreModel` so it can optionally define (a) a display transform [built now] AND (b) a
  win-condition / game-over hook [deferred]. For now every model is display-only and the win condition stays
  cumulative-highest-wins.

## Blast radius (scoped version)
- **Essentially none on the engine** — display-only. All score consumers read the real cumulative values.
- **Frontend:** thread the active model into the score-render sites via `displayScore` (a small, mechanical change
  to the same sites as `formatScore`). Needs the frontend to know the model (from `/api/rules`, like the
  last-down color).
- **Edge cases to settle:** the quarter table (rec: keep additive), and whether the differential board colors the
  `+`/`-` (rec: sign is enough; optional leader-green / trailer-muted).

## Build phases
1. **Rule** — `scoringModel` on `GameRules` + `/api/rules` exposure + wire the "Scoring Model" Rulebook row to the
   live value; the enum choice in the vote layer.
2. **Display helper** — `displayScore(teamScore, oppScore, model)` (frontend), building on `formatScore`.
3. **Apply at render sites** — game card, modal scoreboard + running score, GameBar, league-news final score;
   decide the quarter table (rec: leave additive).
4. **Model source** — fetch the active model (`/api/rules`, mirroring the last-down color fetch); per-game chaos
   override if the game data carries it.
5. **Criticality** — randomize the model during a Criticality.
6. **Validation** — with `differential` on: a TD reads `+7 / -7`, a tie reads `0 / 0`, floats read `+6.4`, and the
   winner/standings/WP are all unchanged (real scores).

### Later (separate effort, when appetite exists)
7. **Win-condition models** — extend `ScoreModel` with a game-over/win-condition hook, implement race-to-zero /
   first-to-X, and do the decision-tree + WP inversion work those require. This is the original Tier-3 flagship
   blast radius; keep it its own project.

## Open / revisit
- Quarter table under `differential` — additive (rec) or per-quarter differential?
- `+`/`-` coloring on the differential board (rec: minimal — sign only).
- Naming the models for the Rulebook / vote (Additive, Differential, and later the deferred ones).
