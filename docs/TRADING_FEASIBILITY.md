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
