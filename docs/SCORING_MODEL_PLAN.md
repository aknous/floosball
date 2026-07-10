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
- **`spread`** — a leader-centric betting-line readout of the margin: the leading team's cell shows `+N`, the
  trailing team's `-N`, a tie shows `EVEN`. (Where the layout is a single line, `LEADER +N`.) Same two numbers,
  framed as the spread. *(Replaces the earlier `differential` idea.)*
- **`share`** — each team shows its **percentage of total points scored**: `60% / 40%`, a tie (or 0-0) shows
  `50% / 50%`. Still reflects who's ahead, so the board stays consistent with the real winner.

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
- `spread` → the signed margin `teamScore - oppScore` as `+N` / `-N` (leader positive), `EVEN` when tied. Still
  `formatScore`-cleaned so a float margin reads `+6.4`. (The exact one-line vs per-cell treatment is a small
  frontend layout call.)
- `share` → `round(teamScore / (teamScore + oppScore) × 100)%`, `50% / 50%` when tied or scoreless.

Applied everywhere a team score renders: the game-modal scoreboard, the game card, the GameBar, the league-news
feed's final score, and the play-feed running score. (The **quarter-by-quarter table** is a per-quarter breakdown
where cumulative points make sense — recommend it stays `additive` regardless of the model; flag as a small
decision.)

## The rule (toggle + config) — `constants.py` / `game_rules.py`
- `scoringModel` on `GameRules` (`'additive'` default | `'spread'` | `'share'`). Surfaced as the Rulebook popover's
  **"Scoring Model"** row (already teased as "Additive"), which flips to the active model.
- It's an **enum choice among models**, so the vote offers the models as options (a light case of the non-scalar
  vote generalization). During **Criticality**, the model can be randomized (a game shown in spread or share).
- Exposed on `/api/rules` (league-level); per-game override during chaos is a build detail (the model is
  presentation, so showing a chaos game in spread/share doesn't leak point values).

## Deferred — two deeper tiers (designed-for, not built)
The display models above are safe now. Everything below changes what the game *is*, in escalating blast radius.
Structure the `ScoreModel`/`GameFormat` layer so a mode can optionally define a display transform [built now], a
**win-condition / game-over hook** [tier 1 below], and/or a **game-loop override** [tier 2 below].

### Tier 1 — Win-condition models (who wins / when it ends; score stays cumulative)
Touch game-over, the scoring-aware decision tree, and WP.
- **`frames`** *(owner: keep)* — divide the 60 minutes into **more, smaller periods** than the 4 quarters
  (e.g. 6 / 8 / 12 frames, tunable); win the **most frames** (a frame goes to whoever scored more in it; total
  points break ties). A team can out-score and still lose the game. Needs period tracking + a win-by-frames
  resolution + WP that thinks in frames.
- **`countdown`** *(race-to-zero)* — both teams start at N; scoring **subtracts**; first to 0 (or lowest at time)
  wins. **Inverts "higher is better"** → inverts the whole decision tree + WP. Biggest blast radius here.
- **`target`** *(first-to-X)* — game ends when a team reaches X points; adds a "closer" urgency.
- **`mercy`** *(lead cap)* — game ends the instant a team leads by N. Only shortens the game (winner unchanged), so
  it's *almost* display-only — just an early game-over.

### Tier 2 — Game-format models (rewrite the game loop — possession / clock / plays)
The deepest tier: these change how the game is *played*, not just how score is kept. Likely their own spec doc(s).
- **`chessClock`** — each team gets a total **offense-time budget** (e.g. 30 min). Their clock runs only while they
  possess; when it hits 0 they can **no longer be on offense** — the other team keeps the ball to the end.
  Turnovers just restart the offense at their own 20. Rewrites possession assignment + adds per-team offense clocks.
- **`splitHalf`** *(innings)* — each team is on offense for a **full half**: one team has the ball the entire first
  two quarters (score as much as possible), the other the whole second half. No alternating possession within a
  half. Rewrites the possession model.
- **`oldSchool`** *(play-count, no game clock)* — how floosball ORIGINALLY worked: **no game clock**, a fixed number
  of **plays per quarter**; offenses manage the play count (hurry-up near the end of halves, know when the last play
  is). This **revives the deprecated play-count model** (`GAME_MAX_PLAYS` / `PLAYS_TO_*_QUARTER` still exist as
  vestigial constants — see CLAUDE.md "Open Questions"). A neat callback to origins; swaps the clock-driven loop for
  a play-driven one.

> These tier-2 formats are the largest changes in the whole rule-mutation direction — each is effectively an
> alternate game engine mode. Spec + build them individually, well after the display models and the Tier-2
> mechanics (Contested Scoring / Drive Clock / Conversion Ladder / Sideline Goals) land.

## Blast radius (scoped version)
- **Essentially none on the engine** — display-only. All score consumers read the real cumulative values.
- **Frontend:** thread the active model into the score-render sites via `displayScore` (a small, mechanical change
  to the same sites as `formatScore`). Needs the frontend to know the model (from `/api/rules`, like the
  last-down color).
- **Edge cases to settle:** the quarter table (rec: keep additive), and whether the spread board colors the
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
6. **Validation** — with `spread` on: a TD reads `+7 / -7`, a tie reads `EVEN`; with `share`, `60% / 40%`; floats read `+6.4`; and the
   winner/standings/WP are all unchanged (real scores).

### Later (separate efforts, when appetite exists)
7. **Tier 1 — Win-condition models** — extend the model with a game-over/win-condition hook: `frames` (period
   tracking + win-by-frames), `countdown`/`target`/`mercy`. `countdown` needs the decision-tree + WP inversion.
8. **Tier 2 — Game-format models** — the deepest: `chessClock`, `splitHalf`, `oldSchool` (revive the play-count
   loop). Each is effectively an alternate engine mode; likely its own spec + build.

## Open / revisit
- Quarter table under `spread`/`share` — additive (rec) or per-period?
- `+`/`-` coloring on the spread board (rec: minimal — sign only).
- Naming the models for the Rulebook / vote (Additive, Spread, Share now; the deferred tiers later).
- `frames`: how many periods, and how a frame is won on a tie within the period (rec: carry to total-points tiebreak).
