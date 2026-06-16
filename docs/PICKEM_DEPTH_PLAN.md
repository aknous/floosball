# Pick-em depth — design exploration

**Status:** exploring 2026-06-16. Goal: make prognostications deeper than "pick the
winner, get a modest payout" **without** drifting into betting (no confidence-wagering,
parlays, over/under, spreads, margin lines — owner ruled these out). Depth comes from
**skill, progression, and story**, not staking. Everything must stay compatible with the
"set your whole day at once" model (a once-a-day user can do it all and walk away).

## What exists today (baseline)
Per-game winner pick, editable until that game hits Final. Score per correct pick:
`points = PICKEM_BASE_POINTS(10) × timingMult × underdogMult`.
- **timingMult** — full value pre-game, decays by quarter (`PICKEM_QUARTER_MULTIPLIERS`),
  softened in close games (`PICKEM_MIN_DECAY_FRACTION`).
- **underdogMult** — ELO-based, up to `PICKEM_UNDERDOG_MAX 3.0×` for live dogs, floored at
  `PICKEM_FAVORITE_MIN 0.4×` for chalk, `PICKEM_UNDERDOG_EXPONENT 1.2` gives dogs an EV edge.
- 1 pt = `PICKEM_POINTS_TO_FLOOBITS 0.65` F. Weekly/season leaderboards + prizes;
  `Clairvoyant` bonus at ≥80 pts/week. Whole-day picks (`/api/pickem/day`, bulk `picks`).
- Auto-pick modes (favorites/underdogs/random).

**Key insight:** real strategy already exists (back live dogs early for big EV) but is
**invisible** — a casual user just sees "pick winner → points." Some of the "shallow"
feeling is legibility, not a missing mechanic.

---

## Idea 1 — Surface the existing skill (legibility)  · lowest lift
Make the timing + underdog-EV strategy visible so the depth is *felt*, no new mechanic.
- On each game in the pick UI, show the **live point value** of each side: "Otters
  (underdog) — 24 pts now" vs "Foxes — 4 pts," and that it **locks at full value
  pre-game, decays each quarter**. A one-word tag: "Live dog — high EV."
- Slate-level "points on the table" total; a gentle teach ("pick early, back underdogs").
- Post-week recap: where your points came from ("3 underdog calls paid 2.4×").
- **Build:** mostly UI + exposing the already-computed `underdogMultiplier`/timing in the
  day/week payloads (partly there). No scoring change. Could be "enough" on its own.

## Idea 2 — Prognosticator progression (identity)  · medium lift
Give prediction skill a persistent arc beyond the weekly Floobit payout.
- **Season + all-time accuracy %** (correct / total), shown on a prognosticator profile.
- **Climbing rank/title** from accuracy × volume: e.g. Rookie Analyst → Beat Writer →
  Forecaster → **Oracle**. Surfaced on profile + a dedicated pick-em leaderboard column.
- **Streaks:** current and longest correct-pick streak (season + all-time); a "form"
  strip (last 10).
- **Badges** (via the existing achievement system): Perfect Day, Perfect Week, Upset
  Caller (N correct underdogs), Hot Hand (X-streak), Sharpshooter (season acc ≥ X%).
- **Build:** track accuracy/streaks off the picks already stored; add achievement
  templates + a rank function; a profile/stats panel. Set-and-forget (passive tracking).
- Pairs naturally with Idea 1 (the surfaced stats *are* the progression).

## Idea 3 — Survivor contest  · medium-high lift (new subsystem)
A free, season-long elimination contest — a *contest*, not a wager (nothing staked),
the regular-season analog to the existing playoff bracket.
- Each game-day, pick **one** team you think wins. **Can't reuse a team** all season
  (forces planning — don't burn your best team on week 1).
- Wrong pick → eliminated. Soften with a **lives variant** (2–3 lives) so a casual user
  isn't out in week 1 and gone for the season.
- Survivors at season end share a prize + a title ("Last Analyst Standing").
- Strategy: read the schedule, save strong teams for thin slates.
- **Build:** new survivor model (entry, per-day pick, used-teams set, lives/alive state),
  day-end resolution, a survivor view, season prize. Coexists with regular pick-em.
- **Watch-out:** elimination can sideline users early — the lives variant or weekly
  re-entry keeps everyone playing.

## Idea 4 — Story-driven calls  · medium lift
Extra predictions tied to the sim's narrative, framed as analyst/knowledge calls, not
lines. A few optional picks when you set your day.
- **Upset of the Day** — name the one underdog you think springs the biggest upset →
  recognition + modest bonus when right (and a "called it!" beat in the news feed).
- **Team on the Rise / Standout** — pick a team you expect to win big, or a player you
  expect to go off (ties to the sim's stars + the Cores/news flavor).
- Earn **recognition** (badge, feed callout) + a small bonus — NOT a points-wager.
- **Build:** define the call types + day-end resolution, a small UI for the extra calls,
  the recognition hooks. Ties into league news / achievements.
- **Keep clean:** stay narrative ("upset", "standout") — avoid totals/margins/closest-game
  framing, which slides back toward props/betting.

---

## DECISION (2026-06-16): pursue Ideas 1, 2, 3. Idea 4 (story calls) PARKED.

## Build #2 as a GENERAL progression layer, not a pick-em silo
Owner wants a site-wide **user progression / rank / level system based on engagement
across the whole site** (cards, fantasy, GM, supporting a team, pick-em, …), with a
**profile page** to show off achievements + awards. Pick-em progression is the **first
input** to that system, not a standalone feature. So build the progression layer generic
from day one to avoid a later refactor:
- A central **engagement/XP + rank model** (e.g. `UserProgression`: xp, level/rank, per-
  source breakdown) that ACCEPTS contributions from any activity via a single hook
  (`awardProgress(userId, source, amount)`); pick-em is just `source='pickem'` to start.
- Ranks/titles defined centrally and shown anywhere (leaderboards, profile, nav).
- The **profile page** is the natural home (level, rank, accuracy, streaks, badges,
  awards, trophy case). Build the profile shell now or design it to slot in.
- Existing pieces to reuse/extend, NOT duplicate: the **achievement system**
  (badges/awards already live there), HoF/All-Pro/MVP accolades, leaderboards.
- Keep pick-em-specific stats (accuracy %, streaks, Oracle title) as a pick-em VIEW of the
  general model, so other activities can later add their own views + feed the same level.

## Suggested sequence
1. **Idea 1 (surface)** — foundation, lowest lift, makes the existing depth legible. Mostly
   frontend (`underdogMultiplier` is already in the API payloads); surface live point value
   + timing decay. Do first.
2. **Idea 2 (progression)** — build the GENERAL engagement/XP + rank model above, with
   pick-em as the first source (accuracy/streaks/Oracle title + badges via achievements).
   This is the seed of the site-wide system; design the profile page home here.
3. **Idea 3 (survivor)** — the biggest standalone subsystem; a season-long elimination
   contest, ships independently whenever.

All non-betting, all set-and-forget compatible. Open questions: rank tiers / badge
thresholds / survivor lives count — tune against the existing pick-em economy (a correct
pick ≈ 6.5 F today). The XP→level curve + cross-activity weighting is the big design call
in #2; settle it before wiring many sources so levels stay meaningful.

> **Bigger picture (owner, 2026-06-16):** #2 is the on-ramp to a site-wide player
> level/rank system fed by engagement everywhere + a profile page showing achievements &
> awards. Design #2's model to generalize.
