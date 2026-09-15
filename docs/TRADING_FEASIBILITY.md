# GM Trading — feasibility

_Assessment 2026-09-14, against the code as it stands on `development`. Not a build plan; the open questions at the end need owner calls before one is worth writing._

Owner ask: teams can trade at any point before the last day of the season (Thursday, week 22), plus offseason trades.

## Verdict

**Feasible, and cheaper than it looks — because the expensive half is already built.** The
part that normally sinks a trading feature is the valuation model, and `frontOfficeBrain`
already has one that produces *genuine, principled disagreement between two GMs about the
same player*. That is the engine a trade runs on, and it exists.

What is genuinely missing is not machinery but **consideration**: there is no salary cap and
there are no draft picks, so there is nothing to trade except players, and the roster shape
constrains even that very tightly. The feature that falls out is narrower than "trading"
usually means — and the narrowness is mostly a good thing.

## The deadline lines up exactly

`(week - 1) // 7` is the game-day index, so weeks 22-28 are all **Thursday** and week 22 is
its first week. `GM_ACTIVE_WEEK = 22` is already the moment the Front Office opens — the
retirement roll, the FA window, the HoF ballot seed. So "trades close when the last day
begins" is the same instant as an existing, already load-bearing boundary, and needs no new
constant. The per-week hook block in `seasonManager` (~`:760-800`) is the natural place to
run a weekly trade pass.

## What already exists

| piece | where | why it matters |
|---|---|---|
| `decisionValue(player, coach=, team=)` | `frontOfficeBrain:481` | "What is this player worth **to this club**, through **this GM's** eyes." Four calls price a two-sided swap. |
| `_scoutError` + `_noiseSigma` | `:355`, `:385` | Per-GM error, **cached per brain** so a GM holds a belief rather than re-rolling. Two GMs genuinely disagree. |
| `FO_SCOUT_INCUMBENT_NOISE_SCALE` | `:299` | A club reads its own player precisely and a stranger noisily. That asymmetry **is** the real shape of trading. |
| `venueBiasFor(team)` | `:141` | A run-favoring stadium values an RB more. Disagreement that is *reasoning*, not noise. |
| `positionValue`, `performanceAdjustment`, `sentimentTilt` | `:116`, `:439`, `:418` | Position weight, form, and fan pressure already fold into the number. |
| `_deWinnersCurse` | `:545` | Picking the best of N noisy reads overvalues it. A GM choosing the best of several offers has **exactly** this curse. |
| `releasePlayerToFreeAgency` / `_signPlayer` | `playerManager:4798`, `:4831` | The slot / jersey-number / `player.team` rebinding dance is already written down. |
| `SeasonRecapEvent` | `models:1122` | A durable transaction log, already feeding the Season Recap. |

⚠️ **The incumbent-noise asymmetry is the most valuable thing here and is easy to miss.** It
exists because clubs were releasing their best walk-year player and re-signing two lesser
ones. For trading it does something better than prevent a bug: each side knows its own
player well and the other's badly, so a trade happens when the *misreads point in opposite
directions* — which is why real trades happen. Nothing needs to be added for this.

## The three real problems

### 1. The roster is six position-locked slots with no bench — and that is the binding constraint

`team.rosterDict` is `{qb, rb, wr1, wr2, te, k}` (`floosball_team:166`). There is no bench,
no practice squad, no roster limit to trade against.

⚠️ **So a 1-for-1 trade at DIFFERENT positions is structurally illegal**: it leaves both
clubs holding a duplicate and a hole. Every legal trade is therefore either

- **position-for-position** (my QB for your QB), or
- **balanced multi-player** (my QB + WR for your QB + WR), which is the same thing twice.

WR is the only position with two slots, so it is the only one with any internal flexibility
at all.

This is the single most important finding, and it cuts both ways. It makes the feature much
**smaller and safer** than "trading" normally implies — there is no package-building, no
consolidation, no way to strip a roster. But it also means the trade space is six positions
wide, and a trade can only ever be two GMs disagreeing about two players at one position.

### 2. There is no consideration — no cap, no picks

- **No salary cap.** It was built and then scratched (`c8e1ec7`), so there is no cap space
  to take on and no financial reason to move a player.
- **No tradeable picks.** The draft order is a *derived list of team objects*
  (`currentSeason.freeAgencyOrder`), not persisted pick entities. There is no `DraftPick`
  model. **There is literally nothing to trade but players.**

⚠️ The consequence is that **a rebuilding club cannot sell**. Buyer/seller at a deadline —
the main real-world reason trades exist — is not expressible. Every trade is a pure swap
where both sides believe they improved *right now*.

Making picks tradeable is a genuinely separate and larger project: picks must become
first-class persisted objects, and both draft-order derivations must read them instead of
computing from standings. It should not be smuggled into a first version.

### 3. `player_season_stats` holds one row per player per season, with one `team_id`

Verified on the prod snapshot: **max rows per (player, season) is exactly 1.**

A mid-season trade means that season line was earned at two clubs and the schema can hold
only one. `game_player_stats.team_id` **is** per-game, so the data needed to split it
exists — but season aggregates, team leaders and the record book all read the season row.

This is a decision, not just plumbing: does a traded player's season line follow them, split
at the trade, or stay with the club where it was earned? Offseason-only trading avoids the
question entirely, which is one reason to consider shipping the offseason half first.

## Secondary consequences

- ⚠️ **`card_templates.team_id` is frozen at mint on all 8,251 templates** and drives the
  team-themed pack filter (`cardManager:298`). A traded player stays in the **old** club's
  pack for the rest of the season. The codebase already acknowledges this drift in a comment
  about champion packs ("`team_id` drifts as players join/leave/retire", `:325`) — trading
  just adds a third and more frequent driver. Arguably correct, since the card depicts the
  player as they were, but it is a call.
- ✅ **Card effects are safe.** `ctx.rosterPlayerTeamIds` is built live from the player's
  current team, so any effect reading a team reads the **new** one. No work needed.
- **Fan sentiment** is gated to a club's own fans (`_requireOwnClub`). A traded player
  carries ratings given by the old club's supporters. Follow, reset, or stay?
- ⚠️ **`player.team` is polymorphic** — a Team object, a team-name string, or a `team_id`
  int depending on the path (`playerManager:254`, `:392`, `:657`). A trade must go through
  the established release/sign pattern rather than assigning directly, or it breaks loading.
- ⚠️ **`_recordOffseasonEvent`'s idempotency key is `(season, event_type, player_id|team_id)`**
  — one player, one club. A two-sided trade does not fit that shape and needs a trade id, or
  the resume-safety dedupe will silently drop half of it.
- `_leftThisTeamThisOffseason` blocks a club re-signing a player it released this offseason.
  A trade is not a release, so it should not trip this — but the check is on
  `previousTeam == team.name and freeAgentYears == 0`, and a trade sets `previousTeam`.

## What a first version could be

The narrow version the code already supports, with no schema work beyond a trade log:

1. **Offseason, position-for-position, 1-for-1.** Both GMs price both players with
   `decisionValue`; a trade clears only when each side's own arithmetic says it gained more
   than `TRADE_MIN_SURPLUS`. Run it in the front-office decision block, after re-signs and
   before the FA draft.
2. **De-curse the offers.** A club fielding several offers picks the best-looking, which is
   the exact bias `_deWinnersCurse` already corrects. Reuse it, do not re-derive it.
3. **Cap the volume.** One or two per club per offseason. GM turnover already measures at
   1-4 exits per season against a stated "not a carousel" target; trading should be held to
   the same bar, and the number should be *measured* rather than assumed.
4. **Then in-season**, once the season-stats question is answered.

## Open questions for the owner

1. **Season stats on a mid-season trade** — follow the player, split at the trade, or stay
   with the club where earned? This gates the in-season half.
2. **Should picks become tradeable?** Without them there is no buyer/seller, and trades can
   only be mutual-improvement swaps. It is the difference between a modest feature and a
   large one.
3. **Do fans keep their say?** A traded player's sentiment was given by different supporters.
4. **How visible?** Trading is the most legible thing a GM does. Fan *proposals*, a trade
   block, or purely autonomous with a news item?
5. **Card team drift** — is a traded player staying in the old club's pack for the season
   acceptable, or should the season's templates re-point?

---

# Addendum — prospect draft and Treasury as trade assets

_2026-09-14, following the owner's proposal to bring back the prospect draft for picks, and to use Treasury Floobits as consideration._

Both ideas are sound. The Treasury half is **much** cheaper than the draft half, and — more
importantly — the two do not solve the same problem. One of them changes the conclusion of
the assessment above.

## The crux: cash does not relax the position lock in-season

⚠️ **THERE IS NO MID-SEASON SIGNING PATH AT ALL.** `_attemptRosterFill` is called from
exactly three places, all inside `conductFreeAgencySimulation` (`playerManager:3282`, `:3495`,
`:3531`). Nothing fills an empty roster slot outside the offseason FA draft.

So selling a player for Floobits mid-season leaves a hole that **nothing can fill until the
offseason**. Cash does not buy a replacement, because there is nobody to buy.

That splits the feature in two:

- **Offseason trades** can be player-for-cash, player-for-pick, anything. The FA draft runs
  afterward and fills whatever hole the trade opened. The position lock does not bind.
- **In-season trades** must still be strictly balanced player-for-player at matching
  positions — **cash or no cash, picks or no picks.** Consideration changes nothing here.

**These are two different features, not one feature with two windows.** The offseason half is
where assets matter and is the larger design; the in-season half stays the narrow
position-for-position swap described above and could ship independently of both proposals.

## Treasury Floobits — already built, and the distribution is ideal

`TeamTreasury` (`models:690`) is live on **all 32 clubs**, holding **307,651F**, funded by
carry-forward + baseline + fan contributions and already *spent* by the facilities
season-end waterfall. Nothing needs building to give teams a balance; they have one.

Measured on the prod snapshot against the 25-run forecast:

| | |
|---|---:|
| corr(treasury, forecast wins) | **−0.012** |
| corr(treasury, roster rating) | −0.103 |
| corr(treasury, facility levels) | +0.642 |
| corr(treasury, favoriters) | +0.388 |
| spread | 200F → 45,427F (227x) |

⚠️ **Treasury is essentially UNCORRELATED with on-field strength, and that is exactly what
makes it a good currency.** The two best teams in the league are at the floor — Pinecones
(25.6 forecast wins) hold **200F**, Curd (21.0) hold **212F** — while mid-table Waffles and
Strangers sit on 45k. Money and talent run on different axes, so cash creates a
**buyer/seller dynamic with no salary cap needed**. That is the gap the assessment above
identified as the feature's biggest hole, and the Treasury closes it without a cap.

Two things follow that are worth deciding deliberately rather than discovering:

- **Spending on trades competes with facilities** (+0.64 correlation, and the waterfall
  already spends this balance). That is a genuine opportunity cost and good design — money
  has an alternative use — but it means trade prices and facility costs are one economy and
  have to be tuned together. `FACILITY_UPGRADE_COST_SHARES` is share-denominated; a trade
  price probably should be too.
- ⚠️ **Some of this is fan money** (+0.39 with favoriters). A GM trading Treasury is
  spending what supporters contributed to their club. That is a politics call, not a
  technical one, and it is the sort of thing fans notice.

## The prospect draft — removed, not switched off

⚠️ **`ROOKIE_DRAFT_ENABLED = False` HAS ZERO READERS.** It is declared at `constants.py:2068`
and read nowhere in any Python file. Flipping it to True does nothing at all. The comment
above it describes the switch in the present tense and the switch does not exist.

This is the same trap class as `AUTONOMOUS_FO_ENABLED`, documented **directly beneath it in
the same file** — that one was described as vestigial and was live; this one is described as
live and is vestigial. Anyone starting this work by flipping the flag will conclude the
draft is broken.

What actually happened: **`68e5608` "Part F wave 1: remove the rookie draft"** excised the
draft itself — **669 lines deleted across `api/main.py`, `playerManager.py` and
`seasonManager.py`**: the `rookie_draft` offseason phase, `rookieDraftPickGenerator`,
`_generateRookieClass`, the fan rookie ballot and tally, `GET /api/rookies/upcoming`, and
`scoutRookie`. `seasonManager:6839` now carries a comment where the call used to be.

Confirmed on prod: **0 prospects, 0 `drafting_team_id`, and not one `rookie_pick` event in
any of the five seasons played.** All acquisition is `fa_pick`.

The good news is that the removal was disciplined. **The prospect columns and the promotion
machinery deliberately stayed** (the commit says so), so `team.prospects`, promotion step
5.75, `PROSPECT_SLOT_CAP_PER_POSITION`, `PROSPECT_DEVELOPMENT_WINDOW` and the FO's
`FO_PROSPECT_PROMOTE_EDGE` are all still in place. Bringing the draft back is a revert of a
known commit plus re-pointing it at the current offseason flow — real work, but bounded, and
the code is recoverable rather than lost.

## ⚠️ But a rookie class is not a tradeable pick

This is the part most likely to be underestimated. Reverting `68e5608` gives back a **rookie
class and a draft that consumes it**. It does **not** give picks as assets.

The draft order was — and the FA order still is — a **derived list of team objects**
(`currentSeason.freeAgencyOrder`, rebuilt from standings each season). There is no
`DraftPick` model and never was. To trade a pick, three things have to become true:

1. Picks become **first-class persisted entities** — season, round, slot, *original* team,
   *current owner*. The original team must survive the trade, or the pick loses the identity
   that makes "their first-rounder" mean anything.
2. The draft **consumes owned picks** instead of walking a derived order. That is the actual
   invasive change, and it applies to the FA draft too if picks are ever to be traded there.
3. Future-season picks need a horizon rule. Trading next season's first is the whole point
   of picks as assets, but it means the draft must resolve ownership for a season whose
   order does not exist yet.

So the honest sequencing is that **picks are a third project**, not a rider on the revert:
draft revert → picks as entities → picks as trade assets.

## Revised recommendation

Given the above, the cheapest path to a trading feature that is actually *interesting*
skips the draft entirely at first:

1. **Offseason player-for-Treasury trades.** Everything needed exists — `decisionValue` to
   price the player, `TeamTreasury` to pay, the FA draft afterward to fill the hole. The
   money/talent anti-correlation means a poor strong club can sell a star to a rich weak one
   on the first day it ships, which is the buyer/seller dynamic the whole feature wants.
2. **In-season position-for-position swaps**, closing at week 22. Independent of 1, no
   assets involved, no schema work beyond the trade log and the season-stats decision.
3. **Then** the draft revert, if a rookie class is wanted for its own sake.
4. **Then** picks as entities, if picks-as-assets are wanted.

Steps 1 and 2 together are a real trading feature and need no new economy. Steps 3 and 4 are
each larger than either of them.

## Additional open questions

6. **Is Treasury spendable on trades at all**, given it is partly fan-contributed and its
   alternative use is facilities? A cap on how much of it a GM may trade per season is the
   obvious lever if the answer is "yes, but".
7. **Is a trade price share-denominated** (like facility costs) or absolute? Share-denominated
   keeps it stable as the economy grows.
8. **Do picks need to exist for the feature to be good**, or is Treasury enough consideration?
   The measured anti-correlation suggests Treasury alone may carry it.

---

# Addendum 2 — in-season trades, and why the draft should probably stay dead

_2026-09-14. Owner: in-season trades are the part of interest; restore the prospect/rookie
draft without fan ballots, so teams can trade picks, trade prospects, and backfill a traded
roster player with a prospect. Owner's reason for killing the draft originally: it blows up
the FA list with players who never see a roster, and inflates league-wide skill._

## The backfill idea is right, and half of it is already written

`seasonManager._promoteProspectsAutonomously` (`:7690`) already does exactly the described
backfill, and is **already ballot-free** — it was written *because* the ballot was removed.
It values the prospect with `decisionValue`, finds an open slot via
`_findOpenSlotForPosition`, clears `is_prospect` / `drafting_team_id`, assigns the roster
slot and issues a contract term. The only thing tying it to the offseason is its call site.

⚠️ **But its promotion BAR is wrong for mid-season.** It promotes only when the prospect
beats `bestReplacementValue(..., pickDepth=)` — the free agent this club could realistically
land at its own slot in the FA order. **Mid-season there is no free agent to land** (see
below), so the real alternative to promoting is an empty slot. The bar has to be near zero
in-season, or the promotion is refused and the hole stays.

**An empty slot rates 50** (`floosball_team:175`) against a league of 73-85. That is
crippling, and it is a useful natural brake — you cannot strip a roster and stay
competitive. It also argues for the trade rule being **"a trade is legal only if both
rosters are complete when it settles"** rather than relying on the engine. The engine does
guard `None` starters in many places, but trusting that for a novel state is how you find
the one place it does not, mid-game, in production.

## ⚠️ The owner's objection is correct, and the mechanism is structural

The bloat was not a tuning miss. It is a direct consequence of how the supply floor counts,
and `playerManager.ensurePositionSupply` says so in its own comment:

> "*prospects / the upcoming rookie class (`is_prospect`) — each is LOCKED to its drafting
> team ... Counting them overstated availability ... Excluding them makes the floor generate
> enough genuine free agents (**over-generating slightly when prospects do get promoted,
> which is harmless — the extra FAs just sit in the pool**)*"

"The extra FAs just sit in the pool" **is** the complaint, written down as an acceptable
cost. And it is not slight at depth:

**Every prospect parked in a pipeline causes the supply floor to generate one extra free
agent. When that prospect is later promoted, both remain in the league. Pipeline depth × 32
teams is permanent population inflation, and the excess lands in the FA pool where it never
sees a roster.**

The skill inflation follows from the same thing: a deeper pool means every club selects the
best of more candidates, so rosters rise league-wide.

The current numbers show how tight the closed loop is by comparison — **224 players have
ever existed**: 192 rostered, 26 free agents, 6 retired. `ensurePositionSupply` generates
only the per-position deficit, so it produces nothing while the pool is above target.

And the licensed pipeline depth is not modest:

| | |
|---|---:|
| `PROSPECT_SLOT_CAP_PER_POSITION` 2 × 5 positions × 32 teams | **320 prospect slots** |
| roster spots in the whole league | 192 |
| current FA pool | 26 |
| ⇒ off-roster players licensed, as a share of a full league | **167%** |

So restoring the pipeline at its configured cap licenses more players held off-roster than
the league has roster spots. That is the blow-up, and it is arithmetic rather than balance.

## The move: picks are free, prospects are not

The three things the owner wants from the pipeline separate cleanly, and only one of them
actually needs prospects:

| want | cheapest source | population cost |
|---|---|---:|
| something to trade | **draft picks** | **zero** |
| backfill a traded player | **mid-season FA signing** | **zero** |
| owned future value | prospects | one body each, permanently |

⚠️ **A pick is a claim with no body attached, so picks cause no population inflation at
all.** They are the trade asset the owner is asking for, and they are free in exactly the
dimension that killed the draft.

⚠️ **And backfill does not need a pipeline — it needs a function.** There are 26 unowned
free agents sitting in the pool right now. The only reason a club cannot sign one mid-season
is that `_attemptRosterFill` is called from nowhere but the FA draft. Adding a mid-season
signing path gives backfill with **zero new players**, which is strictly better than a
pipeline for that purpose, and it is a much smaller change than reverting the draft.

That leaves prospects providing only *owned, tradeable future value* — real, but the one
thing on the list that costs a permanent body per unit.

## Revised recommendation for the in-season feature

1. **Picks as first-class tradeable entities, over the FA draft order that already exists.**
   `currentSeason.freeAgencyOrder` is already computed worst-first each season; the change is
   to persist its positions as ownable objects (season, round, *original* team, current
   owner) and have the draft consume owned picks instead of walking a derived list. **No
   rookie class, no prospect pipeline, no new players.**
   ⚠️ Note the horizon lands immediately rather than later: an in-season trade of "this
   season's pick" refers to an order derived from *final standings that do not exist yet*.
   That is a feature — the pick's value is genuinely uncertain while the season runs, which
   is what makes trading it interesting — but it means a pick must be identified by
   `(season, round, original team)` and resolved to a slot only when the order is computed.
2. **A mid-season signing path** off the existing FA pool, for backfill. This is also what
   makes player-for-picks trades legal in-season at all, since the seller must end the trade
   with a complete roster.
3. **In-season trades** closing at week 22: player-for-player at matching positions,
   player-for-picks, or picks-for-picks. Priced with `decisionValue` on both sides.
4. **Prospects only if wanted for their own sake** — and then with a hard cap on the TOTAL
   per team (1, maybe 2), not the per-position cap of 2 that licenses ten. At one per team
   the inflation is 32 bodies, about 14%, bounded and legible. At the configured cap it is
   the thing that was removed.

If the pipeline does come back, `PROSPECT_DEVELOPMENT_WINDOW` (3 offseasons then forced
release) is the pressure valve that makes prospects trade rather than accumulate — a
use-him-or-lose-him asset is one a GM will move.

## Revised open questions

9. **Do picks alone satisfy the "assets to trade" goal?** They cost nothing in the dimension
   that killed the draft, and the Treasury (addendum 1) is a second free asset already live.
   Between them there may be no need for prospects at all.
10. **If prospects return, what is the total per-team cap** — and is the supply floor
    adjusted to count them, so the league population stays fixed rather than growing by the
    pipeline's depth?
11. ⚠️ **A prospect promoted mid-season has no card.** Templates exclude `is_prospect` /
    `drafting_team_id` and mint once per season, so a player promoted in week 10 cannot be
    collected, equipped or scored until the next season's mint. A fan watching their club
    trade for a player and then being unable to field him is the most visible fantasy-side
    consequence of in-season roster movement. (A traded *rostered* player is fine — he
    already has a card; it just carries the old club's `team_id`.)

---

# Addendum 3 — the competitive-balance tax

_2026-09-14. Owner: to get around inflation, either a salary cap or a tax where a team
exceeding a limit on player skill pays from its Treasury, as MLB does._

## ⚠️ First, a correction: there are TWO inflations and a tax fixes only one

The word is doing double duty in this thread and the two problems have different fixes.

**Population inflation** — the FA list filling with players who never see a roster. This is
caused by `ensurePositionSupply` excluding prospects from its supply count (they are locked
to their drafting team), so every prospect held makes the floor generate one extra free
agent. **Money is not in that loop anywhere.** The floor compares roster demand against
draftable supply; a team's wealth or payroll is not a term in it. **A tax cannot touch this,
and neither could a salary cap.** The only fixes are to not restore the pipeline, or to make
the floor count prospects so the league population stays fixed.

**Skill concentration** — one club accumulating the league's talent. **A tax fixes this
well**, and it is the problem the season 6 forecast actually shows.

So the tax is a good idea for its own reason, not as a solution to the FA-pool bloat. If the
pipeline comes back, the bloat comes back with it, taxed or not.

## A tax is structurally safer than a cap here, and that is not a close call

Rosters are exactly **six position-locked slots**. A cap constrains *how much a team may
have* — but with a fixed roster size a team cannot have *more* players, only better ones. So
a cap has nowhere to bite except by **blocking a signing**, and blocking a signing collides
head-on with the rule that a roster must never carry an empty slot: **an empty slot rates 50**
against a league of 73-85.

A tax never blocks anything and never leaves a hole. It charges for the roster a club has
already built. With a fixed roster size that is strictly safer.

This is very likely why the cap did not survive the first time. `c8e1ec7` removed it in
favour of **retention limits** (re-sign-once + count-limit) as the parity model — and the
cap's own machinery included *"the `_attemptRosterFill` budget gate"*, i.e. exactly the
signing-blocker described above.

⚠️ **And the chosen replacement is now half-disabled**: `RESIGN_ONCE_ENABLED` is **False**
(owner, 2026-08-13 — at a limit of 1 a career-long one-club player was impossible). So the
model that displaced the cap has had its main limb turned off, and there is currently **no
roster-economic parity mechanism at all**. Parity today rests on `LEAGUE_COMPRESSION_FACTOR`
and the defense modifiers. A tax would be filling a real hole rather than adding a third
overlapping system.

## The tax base: `cap_hit` is free but too coarse

`players.cap_hit` is already populated on **all 224 players** — the star tier frozen at
signing, S=5 down to D=1 — and it survived the cap removal as a vestigial column. Summing
the six starters gives a payroll for nothing.

⚠️ **But it has almost no room to set a threshold.** Measured on prod:

| base | range | usable thresholds |
|---|---|---|
| payroll (Σ `cap_hit`) | **13–20** (on a theoretical 6–30) | 18 or 19, and that is all |
| rating sum (Σ `player_rating`) | **439–510**, sd 15.0 | anywhere |

At a payroll threshold of 18, eleven teams are over; at 20, zero are. Seven points of spread
across a 32-club league is a step function, not a dial — the tiers are five coarse buckets
and every club has exactly six players, so there is no roster-size lever to create spread.

The rating sum gives **71 points** of spread and scales smoothly with excess. The owner said
"a limit on player **skill**", which is rating rather than tier — that instinct is right, and
`cap_hit` is the wrong base despite being free.

Correlations on the payroll base, for reference: `rating` **+0.879**, `wins` **+0.724**,
`treasury` **−0.183**.

## Measured: the tax lands on exactly the right team, and it cannot pay

At a rating-sum threshold of **495**:

| team | Σ rating | excess | treasury | forecast wins | title odds |
|---|---:|---:|---:|---:|---:|
| Pinecones | 510 | 15 | **200F** | 25.6 | **48%** |
| Residents | 502 | 7 | 2,732F | 20.2 | 20% |
| Broads | 500 | 5 | 8,739F | 14.3 | 0% |

✅ **The runaway favorite is taxed hardest and holds the league minimum.** Pinecones carry
48% title odds across 25 runs and have **200 Floobits**. Under a tax they must shed talent,
which manufactures precisely the seller that in-season trading needs — and it is aimed at
the one problem the forecast actually identified. That is the MLB dynamic working.

The Treasury being anti-correlated with talent (−0.18 against payroll, −0.10 against rating)
is what gives the tax its bite: the clubs that owe are the clubs without money.

## ⚠️ Two problems to settle before building it

**1. What happens when a club cannot pay?** MLB's answer is "you just pay" — that is not
available here, because the best team has 200F. This is the central design question and it
must be decided rather than discovered. Options: a forced sale (the sim trades someone),
Treasury debt carried against next season's income, or a rating/development penalty. A tax
whose penalty is unpayable and has no fallback is a dead end that will surface in the first
season it fires.

**2. The base produces false positives.** Broads sit third in rating sum (500) and forecast
**14.3 wins with zero titles in 25 runs**. Rating sum correlates +0.72 with winning — strong,
but loose enough to tax a club that is not dominating anything. Either accept that (a tax on
payroll, not on success, is defensible and is what MLB does) or move the base closer to
outcome, at the cost of taxing last season rather than this roster.

## Where this leaves the whole proposal

- **Picks** as trade assets: free, no population cost, no tax needed. ✅
- **Treasury** as consideration: already live, anti-correlated with strength. ✅
- **A rating-sum tax** paid from Treasury: a real parity lever aimed at a measured problem,
  and it makes the Treasury *matter* — a club near the line must weigh a trade against the
  bill. It also gives the strong-but-broke clubs a reason to sell, which is the missing half
  of a trade market. ✅
- **The prospect pipeline**: still the only piece that inflates the player population, and a
  tax does not change that. ⚠️

## Revised open questions

12. **Unpayable tax** — forced sale, carried debt, or a non-Floobit penalty?
13. **Threshold and rate** — a flat percentage of excess, or MLB's escalating repeat-offender
    rate? The escalator is what actually breaks dynasties and is barely more work.
14. **Is the threshold fixed or league-relative?** A fixed number drifts as
    `LEAGUE_COMPRESSION_MEAN` or the rating curve moves; a percentile of the league's own
    rating sum self-normalizes, the way the anomaly threshold already does.
15. **Does the tax alone remove the need for the pipeline?** If the goal of prospects was
    trade assets, picks plus Treasury plus a tax may cover it with no population cost.

---

# Addendum 4 — tax penalty, tax-aware GMs, and culling the pool

_2026-09-14. Owner: an unpayable tax forces a trade or drops a facility a level; GMs must
weigh the threshold when signing; and the FA pool should be fixed by removing low-rated
players who have never been rostered or have been off one for multiple seasons, returning
the name to the pool without the Jr._

## The unpayable-tax penalty already exists as built, tested machinery

`facilitiesManager.resolveSeasonEnd` already runs an **upkeep waterfall out of the
Treasury**: each facility's shortfall is covered from the pot, and a facility whose upkeep
goes unmet decays a level. `test_facility_immediate_build.py` pins exactly that — *"empty
treasury -> any upkeep charge forces decay"*.

So **"can't pay → a facility drops a level" needs no new penalty code.** Charge the tax into
the same waterfall and a club that cannot cover it loses a level precisely as it would from
unpaid upkeep. It also inherits an ordering that is already thought through: the waterfall
sorts `key=lambda x: -x['level']`, protecting the **highest**-level facilities first, so
decay lands on the cheapest one rather than the crown jewel.

✅ And there is a second-order effect that falls out for free and points the right way:
**facilities drive Appeal, and Appeal gates free-agent destination preference**
(`willSignWith` / `appealDemand`). A taxed club that loses a facility becomes *less
attractive to free agents* — the penalty compounds exactly as it should, with nothing coded
for it.

## ⚠️ Tax-aware GMs must DISCOUNT a signing, never REFUSE one

This is the single most important implementation note in this document, because it is the
mistake the codebase has already made once.

`c8e1ec7` removed, among other things, *"the `_attemptRosterFill` **budget gate**"* — the
salary cap's mechanism for keeping a club under the line. **A gate refuses a signing. A
refused signing leaves an empty slot. An empty slot rates 50.** That is why a cap was unsafe
on a six-slot roster and it is the same trap here.

The right shape already exists in the same function. `decisionValue` ends with:

```python
if self.teamAppeal(team) < self.appealDemand(player):
    value *= _SOFT_APPEAL_PENALTY
```

That soft penalty was **deliberately chosen over a hard gate** for this exact reason — the
comment says so: *"Below the player's Appeal demand this club is a worse fit, so it ranks
them lower — it does NOT lose the right to sign them."* The tax term belongs in the same
place, in the same shape: multiply `decisionValue` by a penalty that scales with how far the
signing pushes the club past the threshold. A club over the line then *prefers* cheaper
talent and *sells* willingly, which is the trade pressure wanted — and it can still fill a
hole when the alternative is a rating-50 slot.

## ⚠️ The FA pool is currently healthy, and there is nothing to cull

Measured on the prod snapshot:

| | |
|---|---:|
| free agents | **26** |
| of those, players with **0** pro seasons | **0** |
| players anywhere in the DB with `seasonsPlayed = 0` | **0** |
| every free agent's `seasonsPlayed` | **6** — all of them |

Every player in the pool is a six-season veteran who was cut or walked. **The "never been on
a roster" limb of the rule catches nobody today**, because the bloat being remembered was
the draft era and the deficit-fill model already fixed it — 224 players have ever existed,
192 rostered, 26 free, 6 retired.

So the cull is a **good prophylactic if the pipeline ever returns**, and has no work to do
now. (A related worry checked and dismissed: `_generateReplacementPlayers` generates
`max(numRetired, 3)` a season regardless of need — a genuine second faucet — but the live
path passes `skipRetirements=True` and `conductFreeAgencySimulation` has no callers at all,
so it is dormant.)

## ⚠️ And hard removal is unsafe for everyone currently in the pool

Those 26 free agents are not orphans. They hold:

| | |
|---|---:|
| `game_player_stats` rows | **2,782** |
| `player_season_stats` rows | 130 |
| `player_career_stats` rows | 26 |
| `card_templates` | 378 |
| **cards owned by real users right now** | **253** |

Deleting one blanks a card in somebody's collection and removes history from the record
book. That collides head-on with the locked design pillar — *never wipe games, seasons or
players; the currency is control and anomaly, never records*.

**So the rule needs scoping to `seasonsPlayed == 0`: a player who never took a snap.** That
population genuinely is orphan-free — no game rows, no season rows, and `generateSeasonTemplates`
requires a real `teamId`, so a never-rostered player mints **no cards at all** (confirmed:
zero season-6 templates exist for any current free agent). It is also exactly the population
a restored pipeline would create, so the rule is aimed correctly — just narrower than "low
rated and off a roster for two seasons".

**Never played → remove. Played → retire.** Retirement already exists and is the right exit
for a washed-up veteran; it keeps the record and the cards.

## The existing cull is loose in exactly the ways described

`_processFreeAgentRetirements` (`playerManager:3593`):

- fires only at **`freeAgentYears >= 3`** — three full seasons unrostered before anything
  can happen;
- is a **roll, not a rule**: TierD 65% + 15%/year, so a bottom-tier player has a 35% chance
  of surviving year three and can linger for years;
- keys off **tier**, an absolute five-bucket measure, not the league's own average.

The owner's *"rating well below the average team roster skill"* is the better test precisely
because it **self-normalizes** as `LEAGUE_COMPRESSION_MEAN` and the rating curve move — the
same argument that made the anomaly threshold adaptive instead of a fixed constant.

## ✅ The name handling is right, and it prevents a documented bug class

`_recyclePlayerName` (`seasonManager:8412`) **always advances the ladder**: Base → Jr. → III
→ IV → … There is no path through it that returns a base name.

Returning the base *unchanged* for a culled player is not a convenience, it is correctness. A
rung is earned **because the holder is gone** — a Junior commemorates a predecessor who
actually played. A player who never took a snap established no lineage, so minting a "Jr."
for him invents a father nobody ever saw **and puts a second form of that lineage into
circulation**. That is precisely the fault that left the season-1 production database with
**39 orphaned variants**, 8 live players collapsed back and 3 reassigned.

One further detail: a culled name should probably go **straight to `unused_names`**, not
through `addPendingName`'s `NAME_REUSE_DELAY_SEASONS` hold. That hold exists so a *familiar*
name does not reappear the next season — and nobody is familiar with a player who never
played.

## Revised open questions

16. **Does the tax charge into the upkeep waterfall, or before it?** Charging first means the
    tax can cost a facility while upkeep was affordable; charging last means upkeep is
    protected and the tax is what goes unpaid. Both are defensible; it decides whether the
    tax or the buildings have priority on a thin Treasury.
17. **Forced trade vs facility decay — who chooses?** If the GM may pick, a club with cheap
    facilities will always take the decay and never trade, which removes the trade pressure
    the tax exists to create. Facility decay may need to be the *fallback* rather than the
    option.
18. **Is the cull scoped to `seasonsPlayed == 0`** (safe, orphan-free) with retirement
    handling everyone else? Anything broader deletes owned cards and record-book history.

---

# Addendum 5 — intake arithmetic and the decay ladder

_2026-09-14. Owner: culling starts only once the rookie draft is back, since every season
then adds 32 players — and the first season may want 3 rounds (96) so teams have prospect
stock. On the tax penalty: facilities decay until they cannot any more and then a trade is
forced, or a cap on consecutive decay seasons before a trade is forced._

## ⚠️ First, a correction to addendum 2

Addendum 2 said *"every prospect parked in a pipeline causes the supply floor to generate one
extra free agent."* **That is wrong, and it overstates the effect.** The mechanism is real
but second-order.

`ensurePositionSupply` generates when `supply < demand`, where supply excludes prospects and
demand is fixed at `32 × slots + buffer`. A rookie class generated straight into pipelines
adds **no** supply and changes **no** demand, so it triggers no extra generation at all.

The over-generation happens later, and the code comment describes it exactly: the floor tops
the pool up *as though prospects could not fill vacancies*, and then some vacancies **are**
filled by promotion. The surplus therefore equals **the number of vacancies filled by
promotion each season**, not the number of prospects held. Smaller, and differently shaped —
it scales with promotion rate, not pipeline depth.

The conclusion survives (prospects do inflate the pool, and a tax cannot fix it), but the
sizing in addendum 2 should not be used.

## The intake arithmetic

**Replacement demand.** 192 roster spots, median longevity **10** seasons ⇒ roughly
**19 players per season** to hold the league full.

**Draft intake.** 32 per season ⇒ a **surplus of about 13 per season**. That is the number
the cull has to remove for the population to be stable, and it is a clean target to build and
measure against.

**The first-season shock.** 96 against a universe of 224 players is **+43% in one
offseason**. Three per club sits comfortably inside `PROSPECT_SLOT_CAP_PER_POSITION` (which
licenses up to ten), so the stock argument holds — but the pool will feel it, and the cull
should ship **with** the draft rather than after it.

## ✅ The timing is better than it looks: the retirement wave is about to start

This league has only ever retired **6 players in 5 completed seasons**, which reads as a
broken retirement system and is not. It is a *young* league: every rostered player has 6
seasons or fewer, and median longevity is 10, so almost nobody has reached the bands yet.

Projected count of rostered players past longevity, holding the current roster:

| season | past longevity |
|---:|---:|
| 6 (now) | 12 |
| 7 | 23 |
| 8 | 44 |
| 9 | 71 |
| 10 | 108 |
| 12 | 178 of 192 |

**So the draft would return at almost exactly the moment outflow ramps up.** Intake of 32
looks reckless against today's ~1 retirement a season and much more reasonable against
season 9-10. The dangerous window is **seasons 6-8**, where 32 (or 96) arrive against 12-44
merely *eligible* players, only a fraction of whom actually retire — "past longevity" is a
probability band, not an exit, and the contract gate holds most of them to their walk year.

That argues for the 3-round opener being the thing to reconsider rather than the 32/season
steady rate: the steady rate meets a rising wave, the opener does not.

## The decay ladder is far too long, and it is regressive

Every club has exactly **5 facilities**; levels sum to between **4 and 13** (median 8.5). So
"decay until it cannot any more" buys:

| club (over a 495 threshold) | Σ rating | facility levels | treasury | seasons of dodging |
|---|---:|---:|---:|---:|
| Pinecones | 510 | 7 | **200F** | **7** |
| Residents | 502 | 8 | 2,732F | 8 |
| Broads | 500 | 12 | 8,739F | 12 |

⚠️ **Pinecones could dodge the tax for seven seasons — longer than this league has
existed.** Decay alone is not a penalty, it is a payment plan with no maturity date.

⚠️ **And it is regressive.** `corr(facility levels, treasury) = +0.642` — the clubs with the
deepest decay cushion are the richest ones, who were least likely to be taxed in the first
place. Broads, the borderline club forecast at 14.3 wins, gets **12** seasons of protection;
Pinecones, the 48%-title-odds problem the tax exists for, gets **7**.

## Why the consecutive-season cap is the right answer

The sharper reason is not the length, it is what decay *does*:

**Decay is interest. A trade is principal.** A club that decays keeps its over-threshold
roster, so it is taxed again next season, and again. Nothing about decaying reduces Σ rating
— only moving a player does. So decay can service the debt indefinitely while never
addressing what created it, which is precisely the failure mode of "decay until it cannot".

A cap on consecutive decay seasons says: *you may service this for a while, then you pay it
down.* On the measured numbers, **2 consecutive seasons** puts Pinecones into a forced trade
in season 8 — inside the window where the forecast says they are a problem. At 3 it is
season 9. Beyond that the tax stops being a parity lever within any horizon a fan cares
about.

A useful refinement, since decay is not free: facilities drive **Appeal**, and Appeal gates
free-agent destination preference. A club that decays twice is *already* getting worse at
signing anyone, so the two penalties compound in the right direction without being stacked
deliberately.

## Revised open questions

19. **Should the first draft really be 3 rounds?** The steady 32/season meets a rising
    retirement wave; the 96-player opener does not, landing in the one window (seasons 6-8)
    where outflow is still small. A 2-round opener, or 3 rounds with the cull running
    immediately, both close that gap.
20. **Consecutive-decay cap: 2 or 3?** Measured, 2 forces Pinecones to trade in season 8 and
    3 in season 9. Anything higher lets the deepest-facility clubs — who are also the richest
    — sit out the tax entirely.
21. **Should the decay counter reset on a trade, or on getting back under the threshold?**
    Resetting on a *trade* rewards the gesture; resetting on being *under the line* rewards
    the outcome, and is harder to game with a token swap.
22. **Does the cull ship with the draft or after it?** At a ~13/season surplus, "after"
    means the pool grows by 13 a season until it arrives.

---

# Addendum 6 — decay counter reset (settled)

_2026-09-14. **Owner ruling: the consecutive-decay counter resets on getting back UNDER the
threshold, not on making a trade.**_

The reason to prefer it is that a token swap cannot buy a reset — only the outcome counts.
Three things follow.

## 1. The forced trade must CLEAR the threshold, not merely happen

If a token trade cannot reset the counter, a token trade cannot satisfy the forced move
either — otherwise the rule bans gaming at one end and permits it at the other. So when the
cap is hit, the trade the sim makes has to put the club back under the line.

## ✅ 2. That is always possible, and it is surgical

The worry with "must clear" is that it could be a dead end, or a fire sale. Measured against
the live league at a 495 threshold, it is neither:

| club | Σ rating | must shed | legal clearing swaps | smallest swap | overshoot |
|---|---:|---:|---:|---|---:|
| Residents | 502 | 7 | **52** | WR 73 → Midnights for WR 66 | **0** |
| Pinecones | 510 | 15 | **26** | TE 87 → Raccoons for TE 72 | **0** |
| Broads | 500 | 5 | **51** | WR 78 → Beans for WR 73 | **0** |

**Zero overshoot in every case.** The rating curve is fine-grained enough that a club can
shed exactly what it owes — Pinecones give up 15 points of talent to clear 15 points of
excess. The forced trade is proportionate, not a punishment dressed as a trade. (The filter
also requires the *partner* not to cross the threshold themselves, so these are legal on both
sides.)

## ✅ 3. It composes with Treasury-as-consideration, in the right direction

Every partner in that table can pay: Raccoons **11,997F**, Midnights **21,250F**, Beans
**38,742F**. So a forced trade is naturally *player-for-player-plus-Floobits* — the partner
buys the upgrade.

That closes the loop the whole design has been circling. The taxed club is over the
threshold **and broke** (Pinecones: Σ510, 200F). The forced trade sheds exactly the rating
they owe **and** hands them the Treasury they lack, from a club that is rich and weak. Money
flows rich-weak → poor-strong, which is precisely the anti-correlation measured in
addendum 1 (`corr(treasury, wins) = −0.012`).

## ⚠️ Two things to name now rather than discover

**The measurement moment must be single and shared with the tax.** Σ rating moves all
offseason — retirements, walks, re-signs, the FA draft, promotions each change it. Assess
the tax and read the counter at **the same instant**, and the natural one is season end,
where `resolveSeasonEnd` already runs the waterfall the tax is charged into. One moment, one
number, both rules reading it.

**A club can fall under the threshold passively.** A player declining with age, or a
retirement, drops Σ rating with no decision taken — and the counter resets for free. That is
consistent with the ruling (the threshold measures the roster, not the effort), and it is
correct, but it should be a known property rather than a surprise. The same applies more
strongly if the threshold is made league-relative: another club improving could drop you
under it.

---

# Addendum 7 — sizing the tax against the real economy

_2026-09-14. Picking the threshold and rate now that the Treasury's other claim is measured._

## The share unit is ~5,485, not the 300 floor

`computeShareUnit` = last season's capped faucet ÷ 32. Measured: season 4 → **6,299**,
season 5 → **5,485**. So a season of upkeep by facility level is **[0, 27, 82, 247, 631,
2194]**, and a club's whole-roster upkeep runs **164 to 2,632** (median 369).

That matters because an earlier read of this at the 300 floor made the facility economy look
trivial next to Treasury balances. It is not. At the real unit it binds.

## ⚠️ Three clubs are ALREADY insolvent on upkeep alone, before any tax exists

| club | treasury | season upkeep | short by |
|---|---:|---:|---:|
| **Pinecones** | 200F | 383F | **−183F** |
| Jetskis | 200F | 273F | −73F |
| Phones | 295F | 328F | −33F |

**The league's best team is broke.** Pinecones carry 48% title odds and 25.6 forecast wins,
and they cannot cover their own buildings this offseason. They will lose a facility level
whether or not a competitive-balance tax is ever built.

## Which means the tax's PAYMENT limb is inert for its own target

Modelled at threshold 495 across four rates:

| rate (shares/excess pt) | Pinecones owes | Residents owes | Broads owes |
|---|---:|---:|---:|
| 0.002 | 165F | 77F | 55F |
| 0.005 | 411F | 192F | 137F |
| 0.01 | 823F | 384F | 274F |
| 0.02 | 1,646F | 768F | 548F |

_(spare after upkeep: Pinecones **−183F**, Residents 2,404F, Broads 7,532F)_

⚠️ **Pinecones cannot pay 165F any more than they can pay 1,646F.** The rate is irrelevant to
the club the tax exists for. Every rate produces the same outcome for them: decay, then —
once the consecutive cap bites — a forced trade.

**So the tax does not collect money from the clubs it targets. It converts financial
pressure into ROSTER pressure.** That is the whole point and it is worth stating plainly,
because the facility economy was already going to take Pinecones' buildings; what it could
never do is make them give up the 96-rated receiver. Only the tax reaches the roster.

## The THRESHOLD is the real dial; the rate only reaches solvent clubs

At rate 0.01:

| threshold | clubs over | can pay | must decay | who cannot pay |
|---:|---:|---:|---:|---|
| 485 | 12 | 8 | **4** | Curd, Exoticos, Phones, Pinecones |
| 490 | 7 | 6 | 1 | Pinecones |
| **495** | **3** | **2** | **1** | Pinecones |
| 500 | 2 | 1 | 1 | Pinecones |

⚠️ **485 is a league-wide shock** — a third of the league over the line and four clubs pushed
into decay at once, including Curd (2nd-best team, 48F spare) and Phones (already insolvent).
495 isolates the one club that is actually running away with the league.

## Recommended values

**Threshold: league-relative at `mean + 1 standard deviation`.** Measured, Σ rating has
mean **480** and sd **15.0**, so mean + 1sd = **495** — the column that behaves best above,
arrived at by a rule rather than by picking a number. This also settles open question 14: a
fixed 495 drifts the moment `LEAGUE_COMPRESSION_MEAN`, the rating curve, or the returning
draft moves the distribution, and all three are live. A relative threshold self-normalizes,
exactly as the anomaly threshold already does.

**Rate: 0.01 shares per excess rating point.** At that rate a *solvent* club over the line
pays 274–384F — about one level-3 facility's annual upkeep. Noticeable, not ruinous, and it
gives the payment limb real work to do in the middle of the table where clubs can actually
pay. Below 0.005 it is not worth collecting; above 0.02 it starts pushing solvent clubs into
decay, which is the 485 failure in a different costume.

## ⚠️ Two consequences to decide

**Facility decay is self-limiting, and that is mostly good.** Losing a level lowers next
season's upkeep, so a club shrinks until its buildings fit its income. That makes the ladder
shorter in practice than the raw level counts suggested — but it also means a club could
shrink to a minimal footprint and then pay the tax forever from a tiny base. The consecutive
cap is what stops that, which is a second reason to keep it low (2).

**Three clubs being already insolvent is a finding about the ECONOMY, not the tax**, and it
lands this offseason either way. Worth deciding on its own merits: is a club with 9
favourites and the league's best roster supposed to be unable to afford a level-3 locker
room? The Treasury correlates +0.39 with favourites and −0.01 with winning, so on the
current design a great team with a small fanbase simply goes broke. That is defensible
(fan-funded clubs), but it is not a rule anybody chose.

## Revised open questions

23. **Is the threshold `mean + 1sd`, or a fixed number reviewed each season?** Relative
    self-normalizes against three live sources of drift; fixed is legible to fans.
24. **Should the tax be charged BEFORE or AFTER upkeep in the waterfall?** (Open question 16,
    now sharper: at these numbers the order decides whether Pinecones lose a facility to the
    tax or to the buildings, and the decay counter only advances for one of those.)
25. **Is the already-insolvent trio a bug or the design?** It fires this offseason regardless.

---

# Addendum 8 — the tax, settled

_2026-09-14. **Owner rulings: drop the rate escalator; the consecutive counter drives the
forced trade.** Consolidates every settled decision, since the seven addenda above are
conversation order rather than design order._

## ⚠️ The ruling fixes a hole, it does not just simplify

The counter now tracks **consecutive seasons OVER THE THRESHOLD**, not consecutive seasons
of facility decay. That distinction is load-bearing:

**Under a decay counter, the one club the tax exists for could never be reached.** Broads
sit at Σ500 with 7,532F of spare and **1 expiring player, 0 forced walks** — they pay the
274F every season without blinking and never decay, so a decay counter never advances and no
forced trade ever fires. Counting seasons *over the line* reaches the solvent club and the
insolvent one alike.

## The mechanism

At season end, in the facilities waterfall:

1. **Over the line?** `excess = Σ rating − threshold`, charged at
   `excess × RATE × shareUnit`. Marginal only — the roster up to the threshold is free.
2. **Can pay** → paid from the Treasury, roster untouched.
3. **Cannot pay** → a facility decays a level (the existing upkeep-shortfall path, no new
   penalty code).
4. **Counter** increments for being over, *whether or not it paid*.
5. **Counter reaches the cap** → a **forced trade that must clear the threshold**.
6. **Counter resets** on being back under the line — never on making a trade, so a token
   swap buys nothing.

| parameter | value | basis |
|---|---|---|
| threshold | league **mean + 1 sd** | measured mean 480, sd 15.0 → 495; self-normalizes against compression, rating-curve and draft drift |
| rate | **0.01** shares / excess point | a solvent club pays ~one level-3 facility's upkeep |
| counter cap | **2** | at 3 the forced trade slips past the window the forecast cares about |

## How it plays, on the two real cases

**Broads** — long contracts, so the re-sign limit cannot touch them. This is the tax's actual target.

| season | Σ | over | owed | counter | outcome |
|---:|---:|---:|---:|---:|---|
| 6 | 500 | 5 | 274F | 1 | pays, roster intact |
| 7 | 500 | 5 | 274F | 2 | ⚠️ forced trade: WR 78 → Beans for WR 73 |
| 8+ | 495 | — | 0 | 0 | under the line |

**548F total over five seasons, and one trade that actually moved a roster.** The money was
never the point.

**Pinecones** — the re-sign limit reaches them first and far harder.

| season | Σ | over | owed | counter | outcome |
|---:|---:|---:|---:|---|---|
| 6 | 510 | 15 | 823F | 1 | cannot pay (−183F spare) → facility decays |
| 7 | **452** | — | 0 | 0 | under the line, counter resets |

⚠️ **Five of their six players are on walk years and the limit is 2 re-signs**, so they are
forced to lose three, and they pick last in a thin FA pool (backfilling at 63 / 61 / 62).
**Σ 510 → 452**, which is 43 under the threshold and below the league mean of 480. The tax
fires exactly once, for money they do not have, and never again.

## ⚠️ The re-sign limit is already the primary soft cap

Measured league-wide: **89 of 192 players (46%) are on walk years**, median 3 expiring per
club, and **18 of 32 clubs must let someone walk**. That is a heavy annual erosion which
nobody has been counting as a balance mechanism, and it is doing most of the work.

So the tax's honest job is **narrow and specific: the club that escaped the re-sign limit by
signing its stars long.** It is not a general parity lever — the re-sign limit already is
one. Sizing it as though it were the main dial is how it ends up at a threshold like 485,
which pushes a third of the league into decay at once.

## Everything settled so far

| # | decision |
|---:|---|
| 1 | In-season trades are the priority; offseason trades are a separate, larger feature |
| 2 | Trades close at week 22 — the first week of the final game day, already `GM_ACTIVE_WEEK` |
| 3 | In-season trades are position-for-position (six locked slots, no bench) |
| 4 | A trade is legal only if both rosters are complete when it settles |
| 5 | Prospect/rookie draft returns, **without fan ballots**; 32/season, first season possibly 3 rounds |
| 6 | Trade assets: picks, prospects, Treasury Floobits |
| 7 | Culling starts only once the draft is back; hard removal scoped to `seasonsPlayed == 0`; a culled name returns as the **base**, no Jr. |
| 8 | Tax base is **Σ player rating**, not `cap_hit` (13-20 is too coarse a range) |
| 9 | Tax is **marginal** — only the excess over the threshold |
| 10 | **Flat rate, no escalator** (owner, this addendum) |
| 11 | Unpayable → facility decay, reusing the existing upkeep-shortfall path |
| 12 | Counter on **consecutive seasons over the line** drives the forced trade (owner, this addendum) |
| 13 | Counter resets on getting back **under the threshold**, never on trading |
| 14 | A forced trade must **clear** the threshold; measured, always possible with zero overshoot |
| 15 | GMs **discount** a signing near the line, never refuse one (`_SOFT_APPEAL_PENALTY`'s shape, not the removed cap's budget gate) |

## Still open

26. **Counter cap of 2 — confirm?** It is the only parameter with no measurement behind it,
    only the observation that 3 pushes the forced trade past the window that matters.
27. **Tax charged before or after upkeep** in the waterfall — decides whether an insolvent
    club loses a facility to the tax or to its buildings.
28. **Three clubs are already insolvent on upkeep alone** (Pinecones, Jetskis, Phones), with
    no tax in existence. That fires this offseason and wants deciding on its own merits.
29. **The 3-round opener** still lands in the one window (seasons 6-8) where retirement
    outflow is still small.

---

# Addendum 9 — the owner is right about the draft, and it changes what the tax is for

_2026-09-14. Owner: "it's not rising substantially now, but it will when we re-introduce the
prospect draft." Tested; confirmed; and it invalidates the threshold recommendation in
addendum 7._

## Today the league is NOT inflating

`player_rating_history` holds the real series. Rostered players only:

| season | mean | 4★+ (≥84) | 5★ (≥92) |
|---:|---:|---:|---:|
| 1 | 78.9 | 25% | 4% |
| 2 | 79.5 | 32% | 5% |
| 3 | 79.9 | 34% | 5% |
| 4 | 80.3 | 34% | 5% |
| 5 | 80.4 | 36% | 6% |
| 6 | 80.0 | 34% | 5% |

It rose while the league was young and has been **flat for three seasons** at ~34% 4★+. The
FA pool sits at 66.8 against a rostered 80.0, so the system is *sorting*, not inflating.

## ⚠️ But the draft breaks that, and the mechanism is selection pressure

192 roster spots are fixed. Grow the candidate population and the best 192 are simply better
— nothing about generation has to change. Modelled by resampling the SAME empirical rating
distribution at larger N, which isolates selection pressure from every other effect:

| population | rostered mean | 4★+ | 5★ | cut line |
|---:|---:|---:|---:|---:|
| 224 (today) | 80.5 | 35% | 5% | 69 |
| 300 | 83.0 | 48% | 7% | 76 |
| 400 | 85.0 | **63%** | 10% | 78 |
| 500 | 86.5 | **78%** | 12% | 81 |

At 32 intake a season against ~19 replacement need, the surplus is ~13/season:

| season | no cull | 4★+ | cull 13/yr | 4★+ | 3-round opener, no cull | 4★+ |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 218 | 34% | 218 | 35% | 314 | **50%** |
| 10 | 270 | 43% | 218 | 34% | 366 | 58% |
| 14 | 322 | 50% | 218 | 34% | 418 | 66% |
| 20 | 400 | **63%** | 218 | **34%** | 496 | **78%** |

⚠️ **The 3-round opener alone takes the league from 34% to ~50% four-star in a single
offseason.** It is the riskiest decision in this plan, and it is riskiest immediately.

✅ **And a cull at the surplus rate holds the league exactly flat at 34% indefinitely.** The
cull is not hygiene. It is the entire defense against the thing the owner is worried about,
and it has to ship WITH the draft, not after it.

## ⚠️ This invalidates the relative threshold, and the tax's purpose

Addendum 7 recommended a threshold at league **mean + 1 sd**. Against this concern that is
exactly wrong.

**A relative threshold is a RANK rule.** It catches the top ~3 clubs whatever the league's
level — if every roster drifts to Σ520 the threshold drifts with it and nobody is ever over
it. It cannot, by construction, prevent everyone ending up with four-star players.

So the two concerns need different tools, and they were being conflated:

| concern | the right lever | what the tax does |
|---|---|---|
| **level** — everyone ends up with stars | the **cull** (and a FIXED threshold, if a tax is used at all) | nothing, if relative |
| **rank** — one club stockpiles for years | the **re-sign limit**, mostly | reaches the club that signed long |

## And on the rank concern, the tax buys about one season

Persistence is real — wins correlate **+0.818** S4→S5, the top-4 repeat count has gone 0, 1,
1, **3**, and Pinecones have been top-4 in three of five seasons with two titles. So the
re-sign limit is not a complete answer.

But modelled forward, it catches even the long-contract club **on a lag**:

| | Broads |
|---|---|
| end S6 | 1 expiring → re-sign, Σ500, still over |
| end S7 | **4 expiring**, keep 2, lose 78 and 75 → **Σ477, under the line** |

⚠️ So against Broads — the single club the tax uniquely reaches — the forced trade would fire
at the end of S7 and the re-sign limit would have corrected them at the end of S7 anyway.
**The tax buys one season, on one club, worth 5 rating points.** That is a lot of machinery
(threshold, rate, waterfall ordering, decay ladder, counter, forced-trade engine) for that
return.

## Recommendation

**Build the cull; treat the tax as optional and decide it later.** The cull is load-bearing
against the owner's actual concern and nothing else addresses it. The tax addresses a
narrower problem that the re-sign limit already handles within a season, and its relative
threshold addresses the main concern not at all.

If a tax is built anyway, it should use a **fixed** threshold so that it bites more clubs as
the league rises — that is the only form that does anything about the level.

## Revised open questions

30. **Does the tax survive at all**, given it buys ~one season on one club and the cull does
    the heavy lifting?
31. **If yes: fixed threshold, not relative.** What number, and reviewed how often?
32. **Is the 3-round opener worth 50% four-star in one offseason?** A 1-round opener with the
    cull running from day one keeps the league flat.

---

# Addendum 10 — trading does not need the draft

_2026-09-14. Owner: the 3-round opener was only ever a means — the point is to give teams a
stock of assets so TRADING can exist. Reconsidered on that basis._

## The opener is a very expensive way to buy assets

96 players lands the league at **~50% four-star in one offseason** (addendum 9). That is a
permanent change to what a star means, bought to enable a feature that does not actually
require it.

## ⚠️ The FA draft order is ALREADY a scarce, per-team, tradeable asset

With the rookie draft off, **the FA pool is the draft** — `ensurePositionSupply` is the only
intake, so every new player in the league appears there. And it is genuinely scarce:

> **26 players. 32 teams. Worst-first.**
>
> An early pick takes a 77. A late pick takes a 61 — or nothing at all, and the draft falls
> through to `generateLastResortFreeAgent`.

Six teams get no one. That is not a token asset; it is the difference between filling a hole
with a 74 TE and filling it with a generated replacement.

So the asset stock the owner wants **already exists**, unowned and untradeable, in
`currentSeason.freeAgencyOrder`. Making those order positions first-class and tradeable
costs **zero new players, zero prospects, no rookie draft, and no cull**.

## ✅ And an in-season FA pick has exactly the right uncertainty

The order is worst-first **by final record**, which is not known until the season ends. So
mid-season:

- a contender's own pick is late and cheap — it should be selling it,
- a struggling club's is early and dear — it should be holding it,
- and both are *guessing*, because the order firms up as the table does.

That is a real trade market falling out of existing machinery, and it is the buyer/seller
dynamic this whole document has been looking for. Nothing had to be built to create it.

## Revised sequencing

**1. Ship trading now, with no draft at all.** Assets: players (position-for-position),
**FA draft position**, and **Treasury Floobits**. Population unchanged, no cull required, no
inflation risk, nothing to tune.

**2. Add the rookie draft later if it is wanted for its own sake** — at **1 round (32)**, with
the cull shipping alongside it, adding prospects as a second asset class.

**3. Leave the tax out for now.** Addendum 9 measured it at roughly one season of earlier
correction on one club; with no draft there is no inflation for it to fight either.

## What is given up

Prospects as tradeable bodies — "I traded for their prospect" has a flavour that a pick does
not. That is a real want, but it is the one version that costs population, and it can be
added in step 2 without redoing step 1.

⚠️ And one caveat on the FA pick as an asset: **it is only as valuable as the pool is deep.**
26 players across 32 teams makes an early pick precious; a pool of 60 would make it routine.
So pick value and pool size are the same dial, which is a reason to keep the supply trickle
tight rather than generous — and a second, independent reason not to open the faucet.

## Revised open questions

33. **Does trading ship on FA picks + Treasury alone**, deferring the draft entirely?
34. **If the draft does return, is 1 round enough** to add prospects without the inflation?
35. **How many seasons out can a pick be traded?** Two is enough to matter and bounds how far
    a club can mortgage itself.

---

# Addendum 11 — the prospect draft, at one round

_2026-09-14. Owner: the draft comes back regardless of the trading case — a bottom-feeder
landing a huge prospect is a dimension fans get excited about. Agreed, and the payload is
already built. The only question left is the round count._

## ✅ The "huge prospect" is a designed, calibrated feature with no draft to express it

`constants.py` states the intent verbatim:

> *"Rookies/prospects DEBUT this many attribute points below their true skill and develop up
> into it over their early seasons. **A future 5-star looks like a solid 3-4-star as a
> rookie.**"*

The three-tier model is live and the columns are populated: `GEN_TRUESKILL_MEAN` 78,
`GEN_TRUESKILL_STD` 10, `POTENTIAL_HEADROOM` 15, `PROSPECT_ENTRY_DISCOUNT` 11. Measured on
the current 224 players, potential sits **+6.1 above current skill on average, +25 at the
top, with 48 players carrying 10 or more points of headroom.**

So this is not a feature to design. It is a feature that has been sitting unused since
`68e5608` removed the only thing that could show it to anyone. An FA pick cannot do it: a
free agent is a known quantity with a rating on the card, and there is no story in signing a
74.

## What a single round actually delivers (2,000 simulated classes)

The class's best prospect:

| | |
|---|---|
| debuts at | **83** — a 3-4 star on the day he is drafted |
| true skill | **94** |
| potential | **99** |
| classes containing a true 5-star (trueSkill ≥ 92) | **2.6 per class** |

And the **worst team picks first**, so he is theirs. The story fires every season, and the
scarcity is right — two or three genuine future stars in a class of 32, not a handful.

## ⚠️ Three rounds does NOT produce a bigger headliner

This is the argument for one round, and it is not a compromise:

| class size | best trueSkill | best potential | true 5-stars in class |
|---:|---:|---:|---:|
| **32** | 98.7 | **99.0** | 2.6 |
| 64 | 101.3 | **99.0** | 5.1 |
| 96 | 103.0 | **99.0** | 7.8 |

**Potential is capped at 99 in all three**, and true skill above 99 is unreachable anyway. A
single round already produces the maximum headliner in essentially every class.

So three rounds buys **64 additional also-rans and no extra story** — and those 64 are the
entire inflation cost (addendum 9: ~50% four-star in one offseason). The thing the opener was
for is delivered in full by round one.

## The shape

- **1 round, 32 prospects, worst-first.** Every club gets a pick; the bottom feeder gets the
  headliner.
- **The cull ships alongside**, removing the ~13/season who never reach a roster — which
  holds the population flat and the four-star share at 34% indefinitely.
- **No fan ballots** (owner, settled earlier).
- Prospects become the second tradeable asset class, alongside FA picks and Treasury.

⚠️ Two implementation notes carried forward: the cull must exclude `is_prospect` /
`drafting_team_id` or it deletes the class it just drafted, and the draft should **replace**
the supply trickle rather than run alongside it — `ensurePositionSupply` stays as the
per-position backstop it already is, not as a second faucet.

## Revised open questions

36. **Does the draft replace `ensurePositionSupply` entirely, or does the floor stay as a
    backstop?** Both running is ~51 intake a season against ~19 replacement need.
37. **Rookie-pick trading**: are the picks in this draft tradeable from day one, or only the
    prospects once drafted? Picks are free; prospects cost a body.

---

# Addendum 12 — draft intake, prospect visibility, development wiring

_2026-09-14. Owner: the draft replaces the trickle; prospects generate at week 22 and appear
in the player tables behind a prospect filter; and confirm facility level + coach player-dev
are still wired into prospect growth._

## 1. The draft replaces the supply trickle — settled

`ensurePositionSupply` stays as the **per-position backstop it already is** (it only fires
when a position is genuinely short), not as a second faucet. Intake is the draft: 32/season
against ~19 replacement need, with the cull removing the ~13 surplus.

## 2. Week 22 is a good home for class generation

`GM_ACTIVE_WEEK` (22) already hosts the Front Office open block — the retirement roll, FA
retirements, the supply top-up, the HoF ballot seed — and that block is **already
once-per-season idempotent**, gated `>= week` plus the persisted
`front_office_open_season` marker so a restart or deploy at or after week 22 cannot re-run
it. Class generation drops into an existing restart-safe slot rather than needing its own.

⚠️ It must sit **after** the retirement roll in that block, for the same reason the HoF
ballot does: the class is sized against the holes retirement is about to open.

## 3. ✅ The backend prospect filter ALREADY EXISTS

`GET /api/players?status=prospects` is live (`api/main.py`, alongside `fa` / `retired` /
`hof` / `followed`) and filters on `is_prospect`. Like the prospect columns and the promotion
machinery, it survived `68e5608` — the draft was removed, its scaffolding was not.

⚠️ **The frontend is the gap.** `/players` redirects to `/stats`, and the Stats page is
position-keyed tables with no status filter, so there is no existing status-filtered player
list to hang a Prospects tab on. That is real frontend work — and it is the only piece of
this request that is not already built.

## 4. ✅ Development wiring is intact, verified link by link

| link | where | state |
|---|---|---|
| coach dev read | `seasonManager` step 7: `team.coach.playerDevelopment` | ✓ |
| facility dev read | `team.facilityEffect('dev_bonus')` | ✓ **new facilities system**, not the old market tier |
| prospects included | explicit second loop over `team.prospects` | ✓ |
| consumed | `PlayerDevelopment.apply_offseason_training(coachDevRating, fundingDevBonus)` | ✓ |
| combined | `devBias = (coachDevRating − 60)/10 + facilityBonus` | ✓ |
| ceiling | `developAttribute(current, trueSkill, potential, ctx)` climbs toward **trueSkill** | ✓ |
| washout | `_advanceProspectWindow()` releases past `PROSPECT_DEVELOPMENT_WINDOW` | ✓ |

The development docstring states the prospect case outright: devBias *"accelerates a RISING
player's climb (and **skews prospect booms**) but does NOT slow the aging decline."*

**Magnitudes.** Training Facility `dev_bonus` by level is `[0, 0.4, 0.8, 1.2, 1.6, 2.0]`;
coach contributes `(playerDevelopment − 60)/10`, so 60→0, 80→+2, 100→+4. Combined devBias
spans **0 to +6** — a real spread between a max-facility club with an elite developer and a
neglected one, and it lands hardest on exactly the population that is still rising.

⚠️ One property worth knowing: the fractional facility bonus is **resolved to an integer
probabilistically** each offseason, so a level-1 Training Facility gives +1 devBias 40% of
the time rather than a guaranteed fraction. That keeps devBias integral but makes a single
prospect's growth noisy season to season; it is the AVERAGE over a pipeline that reflects the
facility.

## Build list for the draft, as it now stands

| item | state |
|---|---|
| prospect columns, `team.prospects` load path | ✓ exists |
| autonomous promotion (`_promoteProspectsAutonomously`) | ✓ exists, already ballot-free |
| development wiring (coach + facility → trueSkill climb) | ✓ exists, verified |
| washout window | ✓ exists |
| `GET /api/players?status=prospects` | ✓ exists |
| class generation at week 22 | build (revert of `68e5608`, minus the ballot) |
| the draft itself, worst-first, 1 round | build (same revert) |
| the cull (~13/season, `seasonsPlayed == 0`, excludes prospects) | build |
| Prospects view in the frontend | build — no status-filtered player list exists to extend |

---

# Addendum 13 — prospect surfaces (correcting addendum 12)

_2026-09-14. Owner: team pages need a spot showing that team's prospects._

## ⚠️ Correction to addendum 12

Addendum 12 said *"there is no existing status-filtered player list to hang a Prospects tab
on. That is real frontend work."* **That is wrong.** The Stats page has exactly such a list,
and the prospects facet is already typed into its response.

## Both backends are complete, and richer than needed

**`GET /api/players?status=prospects`** — live.

**The Stats players endpoint** — `_PLAYER_STATUSES` already contains `'prospects'`, the facet
counter already counts it, and the status filter already maps it. Nothing to add.

**`GET /api/teams/{team_id}/prospects`** — live, and built for exactly this UI. Per prospect
it returns `name`, `position`, `rating`, `tier`, `prospectSeasons`, `seasonsRemaining`,
`draftSeason`, `isUndrafted`, and a **`ratingHistory` series batched in one query so the UI
can draw a development sparkline without N fetches**. Plus `slotCapPerPosition`,
`developmentWindow` and `promotionThreshold` on the envelope.

All three survived `68e5608` along with the columns, the promotion logic and the development
wiring. The draft was excised; its surfaces were not.

## What is actually left to build

| surface | work |
|---|---|
| **Stats page prospects filter** | **one line** — add `{ key: 'prospects', label: 'Prospects' }` to `STATUSES` in `StatsPage.tsx`. The chip renders its count from `facets.prospects`, which is already in `StatsPlayersResponse`. |
| **Team page prospects block** | a `SectionHead label="Prospects"` block under **Squad**, after the existing Roster block (`TeamPage.tsx:1375`), consuming `/api/teams/{id}/prospects`. Optionally a `railSections` entry beside Overview / Squad / Record / Front office. |

Neither needs a backend change. The team-page block is the only piece with any real design in
it, and the payload was shaped for it — rating, tier, seasons remaining in the window, and the
sparkline series.

⚠️ Both surfaces render **empty until the draft ships**, since prospects are the only thing
that populates them and there are currently zero. Worth building them WITH the draft rather
than before it, or they ship as blank panels.

## Updated build list

| item | state |
|---|---|
| prospect columns, `team.prospects` load path | ✓ exists |
| autonomous promotion, ballot-free | ✓ exists |
| development wiring (coach + facility → trueSkill) | ✓ exists, verified |
| washout window | ✓ exists |
| `GET /api/players?status=prospects` | ✓ exists |
| stats endpoint prospects facet + filter | ✓ exists |
| `GET /api/teams/{id}/prospects` (with sparkline series) | ✓ exists |
| class generation at week 22 | build |
| the draft itself, worst-first, 1 round | build |
| the cull | build |
| Stats page prospects chip | build — one line |
| Team page prospects block | build — frontend only |

---

# Addendum 14 — owner rulings, 2026-09-14

## ✅ Season stats stay with the player — already the behaviour

`playerManager` line ~1952 does `db_season_stats.team_id = playerTeamId` on **every save**,
and saves run at every week and season boundary. So a season line already follows the player
to whatever club he is on now. **No work.**

For the record, since the alternatives were unclear: the schema holds **one row per player
per season with one `team_id`**, so the only real question was which club a split season is
attributed to — the one he ends with (this, the status quo), the one he started with, or two
rows (a schema change). The single visible consequence is `/api/stats/leaders`, which prints
the club beside a leaderboard row, so after a trade it shows the new club next to stats
partly earned elsewhere.

⚠️ That is already the established convention: `/api/history/records` reports a **career**
record against the player's CURRENT club, and CLAUDE.md states it is *"deliberately NOT a
claim about where the record was set"*. Same rule, same reasoning.

## ✅ Fan sentiment does NOT follow a traded player

Ratings are gated to a club's own fans (`_requireOwnClub`), so a traded player would
otherwise arrive carrying ratings from supporters who are no longer his.

⚠️ Note the gate is on **writing** only — `sentimentTilt` aggregates every rating a player
holds — so "does not follow" means the rows are **cleared on the trade**, not merely ignored.
Live impact today is nil (no player has reached even the old quorum), but the rule should
ship with the trade rather than be retrofitted.

## ✅ Trades are visible: league news + a new transactions page

Two surfaces, and the machinery for both partly exists.

**League news** — `league_news.publish()` is the one publisher, and a trade is exactly the
shape it takes. ⚠️ It is **keyword-only and camelCase**, and a snake_case typo has already
caused two incidents, one of them a production outage; `test_publish_kwargs.py` sweeps call
sites statically, so a new publisher is covered the moment it is written.

**A central transactions page** — new. `SeasonRecapEvent` is already the durable
per-season transaction log (`rookie_pick | fa_pick | cut | resign | promotion | retirement |
hof_induction | coach_fire | coach_hire`) and a `trade` type joins it naturally. ⚠️ **Its
idempotency key is `(season, event_type, player_id|team_id)` — one player, one club — which a
two-sided trade does not fit.** It needs a trade id, or the resume-safety dedupe silently
drops half of a swap.

## ✅ Rookie picks are tradeable

Horizon still open. Two seasons out is enough to matter and bounds the mortgage.

## ✅ No tax, for now

Dropped on the measurements in addendum 9 — roughly one season of earlier correction on one
club, and a relative threshold that does nothing about league-wide level. The re-sign limit
(89 of 192 players on walk years, 18 of 32 clubs forced to let someone walk) is the primary
soft cap, and the cull is what holds the level.

## ⚠️ Cards: a mid-season trade mints a NEW card; the old one is untouched

Owner: *new cards can be minted when a player is traded mid-season, but a card someone holds
of that player from his previous team does not change.*

This is compatible with the start-of-season rule settled a moment earlier — that rule governs
**who** gets cards (rostered players), and a trade does not change whether he is rostered,
only where. But it is a real build, with consequences worth naming up front:

- ⚠️ **Templates mint once per season and never re-mint** — `generateSeasonTemplates` returns
  early on `countBySeason > 0`. A mid-season mint needs its own path; it cannot ride the
  season-start one.
- ✅ **It fixes the themed-pack drift.** `card_templates.team_id` is frozen at mint, so today
  a traded player would linger in his old club's team pack all season. A new card carrying
  the new `team_id` puts him in the right pack, and the old card keeps the old one — which is
  correct, because that card depicts him as he was.
- ⚠️ **Two scoreable cards of one player then exist in a season.** They are position-locked to
  the same slot, so a holder of both can field at most two of him (slot + FLEX), and only if
  the two carry **different** effects — the no-duplicate rule is per `effectName`. Bounded,
  but it is a genuinely new state and should be a deliberate choice rather than a discovery.
- ⚠️ **`_assignEffects` plans effects per bucket**, dealing least-used first so every effect is
  covered. A mid-season mint arrives outside that plan and needs to either slot into it or
  draw fresh, or it quietly skews the season's effect coverage.

## Updated open questions

1. **Pick horizon** — how many seasons out can a rookie pick be traded?
2. **Cull bar fraction** — what fraction of the league mean, chosen on judgement then measured.
3. **Mid-season mint effects** — does the new card draw from the bucket plan or fresh?
4. **Transactions page scope** — trades only, or the full `SeasonRecapEvent` log (cuts,
   re-signs, promotions, retirements, coach moves) with trades as one kind?
5. ⚠️ **Three clubs are insolvent on upkeep alone** (Pinecones 200F vs 383F, Jetskis, Phones)
   with no tax in existence. Independent of all of the above, and it fires **this offseason**.

---

# Addendum 15 — insolvency is fine; the waterfall's spending is not

_2026-09-14. Owner: the insolvent clubs are fine, they just decay their facilities. Agreed on
the principle. But modelling what actually happens surfaced a defect worth deciding on before
it fires for the first time this offseason._

## Modelled against the real rows

Running `resolveSeasonEnd` with each club's live facilities, treasury and the real share unit:

| club | treasury | owed | levels lost |
|---|---:|---:|---:|
| **Pinecones** | 200F | 383F | **4** |
| Jetskis | 200F | 273F | 2 |
| Phones | 295F | 328F | 1 |

⚠️ **Pinecones lose four levels in one offseason, and their 200F saves nothing.**

## Why: the waterfall pays into a facility it cannot save

`resolveSeasonEnd` sorts `key=lambda x: -x['level']` — *"Highest-level facilities are
protected first (most investment at stake)"* — and pays each facility's full shortfall from
the pot in turn. With 200F against Pinecones' bill:

| facility | needs | paid | outcome |
|---|---:|---:|---|
| locker_room lv3 | 247 | **200** | short → **decays anyway** |
| training lv2 | 82 | 0 | decays |
| recovery lv1 | 27 | 0 | decays |
| scouting lv1 | 27 | 0 | decays |

The whole pot goes into a bill it cannot complete, the facility decays regardless, and the
three cheaper ones — **136F for all of them, comfortably affordable** — get nothing.

⚠️ **And the partial payment is not banked.** `prepareSeasonStart` resets every facility's
`upkeep_funded` to 0 at season start, so the 200F is simply gone. It did not protect the
level-3 facility, and it did not carry forward.

Spending the same 200F cheapest-first instead:

| | levels lost | spent | facilities kept |
|---|---:|---:|---:|
| current (highest-level first) | **4** | 200F | 0 |
| skip what you cannot finish | **1** | 136F | 3 |

## The implementation defeats its own stated intent

The rule exists to *protect* investment. Paying 200 of a 247 bill protects nothing — it is
strictly worse than every alternative, including doing nothing at all. The ordering is
defensible (a level-3 facility cost more to build, so trying to save it first is reasonable);
what is not defensible is **spending into a shortfall it cannot close.**

The minimal fix keeps the ordering and adds one test: pay a facility only if the pot can
cover its shortfall **in full**; otherwise skip it and move down the list. Highest-level
facilities are still tried first, so the stated intent survives — a club that can afford its
crown jewel still saves it, and one that cannot stops burning the treasury on it.

⚠️ This is live for three clubs **this offseason** and will recur for any club whose Treasury
falls short, which the facilities economy guarantees will happen — upkeep at level 5 is
2,194F a season against a league median Treasury of 1,896F.

## Open

6. ~~Change the waterfall to skip what it cannot finish?~~ — **SETTLED and BUILT** (owner,
   2026-09-14: *"that's too hard, lets make that change. ideally it should calculate the most
   efficient use of funds if there's a shortfall"*).

   Implemented as an **exact subset choice**, not a skip-and-continue: value = the cost to
   rebuild the level at risk (`upgradeCostFloobits(level - 1)`), so a level-3 building
   outranks a level-1 in real Floobits rather than by counting levels. ⚠️ **Greedy by value
   density is not optimal on a knapsack** — but a club holds ~5 facilities, so all `2**n`
   subsets are enumerable and the answer is exact. Level order survives as the tie-break, so
   "most investment protected first" still decides between sets of equal value.

   Measured against the live rows: **Pinecones 4 levels → 1** (136F spent, 64F left, where
   before 200F bought nothing), Jetskis 2 → 1, Phones 1 → 1 but now paying efficiently.

   Regression: `test_facility_shortfall.py` (7 tests), verified by restoring the sequential
   waterfall and watching 2 fail. The load-bearing assertion is that **no partial payment is
   ever made at any pot size** — part of a bill is worth exactly zero, because
   `prepareSeasonStart` resets `upkeep_funded` each season.
