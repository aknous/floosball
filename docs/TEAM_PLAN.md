# Team Plan

Owner direction, 2026-11-06: "teams need to know their whole situation. who their
prospects are at each position, which roster players they want to resign, when they plan
to promote their prospects, what the free agent market looks like. all of these play into
who they need to draft." And: "there should be an offense vs defense consideration. teams
need to be looking at both ratings, not just the overall. and coaches should have a
preference."

## Why

The offseason has four deciders that each judge a roster with their own rule: the re-sign
step, the promotion pass, the FA draft and the rookie draft. Nothing carries a plan from
one to the next. On the season-13 prod snapshot, in 2 of 4 runs the Melons let TeeTee
Moonshine (86 QB) walk because their last-chance prospect Comicbook Connery would replace
him, then signed Catface Martins (84) over Connery in the FA draft. Moonshine left for
nothing and Connery sat a third season.

## The plan

One outlook per team and position, for the next `FO_STANDING_HORIZON_SEASONS` (3) seasons.
Each season's level is the sum of the slot holders' projected ratings (WR has two slots),
taken from:

- **Starters** under contract that season, or beyond it when the GM intends to re-sign
  them (`walkYearResignIntent`). A retiring starter is gone.
- **Prospects** at the position, while their window lasts. A prospect who makes the top of
  the position within his window is promoted and stays; one who does not washes out.
- **The free agent market**, only for a slot no starter holds: who will be left at this
  team's pick. This offseason, today's pool after the teams ahead fill their open slots;
  later, what this FA draft leaves plus other teams' expiring players their GMs will not
  keep (stars in their prime are assumed kept beyond next offseason). A signing this
  offseason stays. When a later pool runs dry, a free agent of this year's quality at the
  pick stands in.

Ratings are projected per season (`FrontOfficeBrain.projectedRating`): growth toward this
team's read of the ceiling for a developing player, the sim's aging rules for one past his
peak, flat otherwise.

**Offense and defense.** Every rating in the plan is read through the team's side tilt
(`FrontOfficeBrain.sideTilt`): rating + tilt x (defense - offense) / 2. The tilt is the
team's need (its offense and defense against the league's, the trade market's `needTilt`,
now one shared function) plus the coach's lean (defensiveMind against offensiveMind). A
balanced team with a balanced coach reads plain overall ratings.

## Stages

1. **Rookie draft** (built first). A rookie is worth what he adds to the position's
   outlook: the sum over the horizon of the level with him minus the level without him,
   times position weight. Covered positions (a kept starter plus a prospect due to take
   over) show little need; an opening hole shows a lot; a deep market at the position
   lowers it.
2. **Re-sign step** reads the same outlook (is the starter needed once the prospects and
   market are counted).
3. **Promotion pass and FA draft** follow the plan's promotion seasons, so the FA draft
   cannot sign over a prospect the plan has taking over unless the plan changes.

Each stage is measured on a prod snapshot before the next.

## Stage 1 results (season-13 snapshot)

- Every pick adds something to the drafting team's plan; no pick sits behind a kept
  starter already as good as the rookie can become, or behind its own better prospect.
- The plan's expected free agent lands within 3 points of who a team actually signs 56
  times in 103 (43 before the market model), median error 0.
- The class's outcome two seasons on (rookies on a roster by season 16) was unchanged
  against the need-only draft, within noise: drafting for seasons two and three only pays
  once the FA draft and promotions follow the plan (stage 3).
- The draft-time re-sign read now uses next offseason's market (two passes); see CLAUDE.md.
