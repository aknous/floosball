# Prospect Uncertainty: busts, diamonds, and scouting that sees them

> **Status:** built on `next-season` (2026-10-30). Measured outcome in CLAUDE.md's Prospect Draft section; sizes in `constants.py` (PROSPECT_TALENT_*, DEV_LUCK_*, DEV_CATCHUP_*). Owner direction: prospects should not be "just good players who will inevitably get better". There should be highly touted prospects who bust and real diamonds in the rough that only teams with the best scouts can see, and not every player should reach their ceiling, because development matters.

## 1. The problem, measured

**The yardstick is a redraft** (owner): go back five drafts with what you know now and draft again. Does the order hold? Is there a different clear #1? Did someone from the last five picks get redrafted into the 5-15 range? That re-sorting is what scouting should be able to see coming.

Measured on 32-player classes. NFL: 2000-15 drafts, career value (`w_av`) from nflverse `draft_picks.csv`, with each draft sampled every ~8th pick into 32-player classes so a class spans the whole talent range like Floosball's. Floosball: 40 classes from the real generator, developed five offseasons under an average coach with no Training Facility, ordered by the displayed expected rating and redrafted by best rating reached.

| After 5 seasons (32-player class) | NFL | Floosball now |
|---|---|---|
| The #1 pick is still the redraft #1 | 26% | 85% |
| The #1 pick's median redraft slot | 4th | 1st |
| A class has a last-5 pick who redrafts into 5-15 | 67% | 0% |
| Top-5 picks who redraft below 16th | 8% | 0% |
| Rank correlation, draft order vs outcome | 0.56 | 0.95 |
| Average slots a player moves | 6.4 | 1.7 |

The displayed expected rating predicts a prospect's best rating within ±4 points 90% of the time. In 640 prospects, none ended 6+ below it and none 6+ above. The 2% late bloom is the only exception, about 0.6 players a season league-wide.

**Why:** each trained attribute has a `trueSkill` cap that every prospect climbs to (`PlayerDevelopment._settle`), and "expected" is that cap, read exactly. Development only changes how fast he gets there. The cap is shown to fans and, within a few points by draft day, to every GM (`prospect_scouting` narrows every team's band to 40% by week 22).

⚠️ NFL career value is confounded by opportunity (a high pick gets more snaps), which flatters the draft order, so the real NFL draft is if anything less predictive than the 0.56 above. The table is a reference for the size of the effect, not a number to fit.

## 2. Goals

- **G1. The public board is NFL-like** (owner: "NFL like"). Redrafting a class by the public consensus projection should look roughly like the NFL column above: the #1 holds about a quarter of the time, most classes have a late riser, and roughly one top-5 pick in twelve falls into the bottom half.
- **G2. Most of that re-sorting is visible to good scouts in advance.** An elite scouting operation's board redrafts far better than the consensus. A poor one does no better than the consensus, and can do worse.
- **G3. Some of it is nobody's to see.** Development is not certain: a prospect can fall short of his ceiling or run past his projection for reasons that happen after the draft.
- **G4. Development environment changes the outcome** (owner). A good development coach and Training Facility raise a prospect's odds of reaching his upside and soften a bust; a poor one can waste a diamond.
- **G5. It plays out gradually** (owner). A bust's projection slides season by season and a diamond's climbs; no single reveal moment.
- **G6. Fans see the public consensus** (owner), the same number on every page, updating as each player develops.
- **G7. The league's talent level does not drift.** Busts and diamonds even out on average for an average environment, so the share of 4-5 star players stays where the parity work put it.

## 3. The model

A prospect's future has three parts, each with a different audience.

### 3.1 Hidden talent: what the consensus gets wrong (scouts can see it)

At class generation each prospect gets a **talent shift** `h`, in attribute points, applied equally to every trained attribute's `trueSkill` and `potential`, like today's late bloom (a shared shift is what moves the composite; per-attribute draws average away, see `LATE_BLOOM_*`).

- **The consensus does not know `h`.** The public projection is computed as if `h` were 0, so a prospect with `h = -12` looks like an ordinary first-rounder and is the touted bust, and one with `h = +15` looks like a late pick and is the diamond.
- **Two-sided and fat-tailed.** Most prospects near 0, a minority far out on either side. A mixture (a narrow core plus wide tails) gets the "most picks are roughly right, a few are badly wrong" shape the NFL table shows; a single normal wide enough to produce the tails would scramble every pick.
- **Mean zero** (G7).
- **It folds in the late bloom.** The bloom is the upper tail of `h` and is retired as a separate mechanic. It was a sudden jump, and the owner chose gradual.

### 3.2 Development luck: what nobody can see (G3, G4)

The `trueSkill` cap stops being fixed. Each development season, while a player is still rising, his cap takes a step:

- a random part, so two identical prospects can diverge;
- an environment drift, positive with a good development coach and Training Facility and negative with a poor one, zero for an average environment (G7).

This is what makes "not every player reaches their ceiling" true. The ceiling (`potential`) is still the most a player can become; how much of the gap to it he closes now depends on luck and on where he develops. It also gives the Training Facility a second job beside its current growth-speed bonus.

The step is visible to everyone once it happens (it changes the player's real numbers, and so his projection), which gives G5's season-by-season slide for free.

### 3.3 The public consensus: what fans see (G6)

Fans, and every fan-facing payload (`api.main._prospectProjection`: profile, rating-history chart, team pipeline, draft class), see:

```
consensus expected = expected(current true numbers) - h x (1 - revealed)
consensus ceiling  = ceiling(current true numbers)  - h x (1 - revealed)
```

`revealed` rises with seasons of development watched (0 at the draft, approaching 1 after about three seasons), so a hidden shift comes out gradually as the player plays and develops. Before the draft, the consensus is also what the whole league's media would say.

⚠️ This reverses the 2026-09-27 rule that fans see the TRUE expected and ceiling. It keeps that rule's real point, one number on every page: `test_prospect_read_consistency.py` is kept and repointed at the consensus.

### 3.4 Team reads: what scouting buys (G2)

A team's belief about a prospect becomes:

```
belief = consensus + vision x h x (1 - revealed) + noise x (1 - vision)
```

- **Facilities carry more than the coach, in both halves** (owner, 2026-10-30: fans control the facilities and have no say over the coach, so the facilities must feel important; "a good coach with top tier facilities makes the team truly elite in development and scouting, but the weakest coach in both areas still makes a top tier facility team dangerous"). A 40/60 coach/facility blend, in place of today's additive points where the coach spans the whole range on his own:
  - **Seeing** (`scoutingVision`): `0.25 floor + 0.75 x (0.4 x coach scouting lean + 0.6 x Scouting Department level / 5)`. Best coach + level 5 = 1.0 (elite); worst coach + level 5 = 0.70 (dangerous); best coach with no department = 0.55; worst + none = 0.25. The floor (owner, 2026-10-31) softens the league-wide drop: vision feeds every GM read, free agents and re-signs included, and without it the league average fell from about 0.78 to 0.49 at season-11 levels; with it about 0.62.
  - **Developing** (dev bias, today coach 0-4 + Training 0-2): coach `0-2.4`, Training Facility `0-3.6` (0.72 a level). Same maximum (6) as today and, at today's coach and facility levels, the same league average (~3.4), so players league-wide do not grow slower or faster on average. Worst coach + level 5 = 3.6, above the best coach with no facility (2.4).
  - So a coach change still moves a team, but a fanbase that builds both facilities has an elite pipeline whoever the coach is.
- `vision` is `frontOfficeBrain.scoutingVision` (the GM's scouting plus the Scouting Department), **continuous**: every level moves it, replacing the four-tier `SCOUTING_BANDS` step where most levels did nothing.
- An elite scout sees nearly all of `h`, so he passes on the touted bust and takes the diamond in the middle of the draft. A poor scout sees none of it and drafts off the consensus, plus his own noise.
- The belief still narrows through the season (`SCOUT_BAND_*`), but toward the scout's own limit, not toward the truth: a poor scout on draft day still knows only what the consensus knows.
- Development luck (3.2) is not in anyone's belief until it happens.

Every GM decision that reads a prospect already goes through the team's belief (`frontOfficeBrain._ceilingRating` → `prospect_scouting.believedPotential`): the rookie board, BPA picks, promotions and the washout last look, re-sign checks against the pipeline, trade valuation. So the scouting advantage reaches all of them through one function.

### 3.5 A bigger class, and the undrafted wash out (owner, 2026-10-30)

The class is one player per team today, so the draft's last few picks take whatever is left. Generate **more prospects than there are picks** (1.5 per team, 48 at 32 teams; owner, 2026-10-30), so every pick is a real choice, and **wash out everyone undrafted**: removed, with each name going straight back into the name pool as its base form.

- **This is what gives hidden talent somewhere to hide.** With 48 prospects and 32 picks, a diamond the consensus ranks 40th is someone only a good scout drafts. Everyone else lets him wash out.
- **Talent coming into the league is unchanged:** still 32 players a season, the same as today. That matters, because a growing player population raises the star share by selection alone (`cullUnsignedPool`'s docstring: a 400-player pool puts 63% of rosters at four stars).
- **Removal is safe for the same reason the pool cull's is.** An undrafted rookie never played, so he has no game or season rows, and he has no cards (`generateRookieTemplates` mints only for rostered players). His name returns as the base form, not a Junior, as in the cull (`_recyclePlayerName` would invent a father nobody saw). Follows on him need clearing too.
- **Side effect:** the "unusable slot" path (`findPickBuyer` / forfeits) mostly disappears, since a team's board no longer empties at its open positions late in the draft.
- **Today the undrafted go to free agency** (`playerManager` draft tail, `is_undrafted`). Today's 32-for-32 class leaves almost nobody undrafted, so this changes free agent supply only marginally. Watch the position-supply floor anyway: anything it generates to cover a shortfall is a fresh player with a fresh name.
- ⚠️ **KICKERS (owner, 2026-10-30): a bigger class can starve a position.** Kickers carry the lowest position value (0.35 of a QB) and are excluded from the best-available picks, so with 16 extra prospects most undrafted players at any one draft are likely to be kickers. Washing them all out would shrink the kicker pool until the position-supply floor starts generating fresh kickers, each with a new name, which is the opposite of what the wash-out is for. **Rule: wash out only the surplus.** Before removing anyone, keep (as free agents, best by consensus first) as many undrafted players at each position as that position needs to stay at the supply floor (`ensurePositionSupply`'s per-position target, counting rostered players, free agents and the drafted class). Only the rest wash out. The floor then never generates a player that an undrafted rookie could have been. The class keeps today's position mix (QB 1 / RB 1 / WR 2 / TE 1 / K 1 per six), so the extras are spread like the roster.
- The Draft Class page shows the whole class all season and marks the undrafted after the draft until they wash out.

## 4. Measurement

A committed harness (built from the throwaway one used for §1) that generates classes with the real generator, develops them five offseasons, and reports the §1 redraft table for:

0. **by position**: drafted, kept as free agents, washed out, and anything the supply floor generated, per season (kickers especially);
1. the **consensus board** (target: G1, near the NFL column), redrafting the 32 drafted players, plus how often a washed-out player would have redrafted into the top 32 (the diamond nobody took);
2. an **elite scout's board** (vision 1.0) and a **poor scout's board** (vision 0) (G2: elite clearly better than the consensus, poor no better);
3. the **same classes developed under the best and worst environments** (G4: how far apart the same prospect ends up);
4. the league-wide **4-5 star share** before and after, over a multi-season sim (G7).

Then a fresh-league simcheck and a multi-season run on a prod snapshot for the knock-on effects: draft order behavior, washouts, promotions, rosters staying full.

## 5. Decisions for the owner

1. ~~**How much of the re-sorting scouts can see.**~~ Settled 2026-10-30 (owner): **three quarters hidden talent (3.1), one quarter development luck (3.2).** With the public board at NFL level (rank correlation ~0.56 against the redraft), a simple variance split puts an elite scout's board near **0.91**: the best scouts usually avoid the bust and find the gem, and still get surprised now and then. A poor scout reads at the public level. The harness measures the real numbers; the split is what it is sized to.
2. **Who is affected.** Proposed: new draft classes only, from the next season start. Prospects already in pipelines keep `h = 0` (their numbers are already public) but get development luck. Founding and free-agent-generated veterans are untouched. **Accepted (owner, 2026-10-30).**
3. **Whether hidden talent applies to free agents too.** With the undrafted washing out (3.5), this is only released prospects (window washouts). Proposed: they keep their unrevealed `h`, so the FA draft also rewards scouting, since a released bust or an overlooked late developer is the same player. **Accepted (owner, 2026-10-30).**
4. **Whether to show fans anything team-specific.** The owner chose public consensus only. A team's own read could later appear on its own page (the old per-team band), but that is out of scope here. **Accepted (owner, 2026-10-30).**
5. ~~**Class size** (3.5).~~ Settled 2026-10-30: 1.5 per team (48), with the undrafted surplus washed out and enough undrafted kept per position to hold the supply floor.

## 6. Where it lands

On `next-season`: classes generate at season start, so it takes effect cleanly at the boundary. Touches `playerManager.generateRookieClass` and `rookieClassSize`, the draft's undrafted tail (wash out, names back to the pool, follows cleared), `player_development.py` (`_settle`, the cap step), `prospect_scouting.py` (continuous band, consensus vs belief), `frontOfficeBrain._ceilingRating`, `api.main._prospectProjection`, `players` (a talent-shift column, inline migration + load/save), `constants.py` (the `h` mixture, the cap-step sizes, `revealed`), and retires `LATE_BLOOM_*`.
