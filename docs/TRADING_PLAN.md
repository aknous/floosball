# In-season trading — design sketch

_Owner-directed, 2026-09-14. Feasibility and the decision trail are in
`docs/TRADING_FEASIBILITY.md` (15 addenda); the prospect draft it depends on is in
`docs/PROSPECT_DRAFT_PLAN.md`. This is how a trade actually works._

## ⚠️ The engine is the re-sign limit, not GM disagreement

The obvious model — two GMs value a player differently, so they swap — is **noise wearing a
strategy's clothes**. With six position-locked slots there are no holes and no surpluses:
every club has exactly one of each. Nothing creates a *need*.

What creates a need is **contract congestion**. `RESIGN_LIMIT_PER_OFFSEASON` is 2, and on the
live league:

> **89 of 192 players (46%) are on walk years. 18 of 32 clubs have more than two expiring.
> 33 players — 2,420 rating points — walk for ZERO return at season end.**

A club about to lose a player for nothing should sell him for something. That is a real,
principled, non-noise reason to trade, it is abundant, and it arrives free with a mechanic
that already ships.

## Sellers and buyers

⚠️ **Congestion alone does not make a seller.** Pinecones are the most congested club in the
league (5 expiring, 3 forced walks) and are also the best — they *rent* their walk-years for
the playoff run and lose them at season end, exactly as a real contender does. Selling
requires congestion **and** no run to protect.

Against the season-6 forecast, splitting at the median (14.0 wins):

| | |
|---|---|
| **Sellers** — congested, not contending | **8 clubs**: Slippers, Grillmeisters, Bees, Raccoons, Beans, Cranes, Rocks, Phones |
| **Buyers** — contending | **16 clubs**, headed by Pinecones, Curd, Residents, Dry Heat |

That is a functioning market on day one: eight sellers holding thirteen players who are
leaving anyway, and sixteen clubs with a reason to rent.

## The loop

1. **A seller identifies a walk-year player it cannot keep.** Deterministic — it knows its
   expiring count and its re-sign limit.
2. **It requires a backfill before it may sell.** A trade is legal only if both rosters are
   complete when it settles, and there is **no mid-season signing path**
   (`_attemptRosterFill` is called only inside the FA draft). So the seller must have a
   **prospect at that position** to promote into the hole.
   ⚠️ *This is why the prospect draft is a dependency of trading rather than a companion to
   it.* Without a pipeline, selling is illegal.
3. **A buyer pays in future value** — a rookie pick, an FA-draft position, or Treasury
   Floobits. The seller wants next season; the buyer wants the next six weeks.
4. **The seller promotes the prospect**, who gets the rest of the season developing — which
   is what a rebuilding club wanted anyway.

Every piece exists or is planned: congestion (live), the contention split (standings),
`_promoteProspectsAutonomously` (live, already ballot-free), picks and Treasury (planned).

## How the sim finds a trade

Weekly, in the existing per-week hook block (`seasonManager` ~`:760-800`), closing at
**week 22** — the first week of the final game day, already `GM_ACTIVE_WEEK`.

For each seller × each surplus walk-year player × each buyer:

- **Seller's price** = `decisionValue(player, team=seller)` discounted for the fact that he
  walks anyway — a player the club cannot keep is worth only what he adds between now and
  the end of the season, not his standing value.
- **Buyer's bid** = `decisionValue(player, team=buyer)` **de-cursed**. ⚠️ A buyer picking the
  best-looking of many available players preferentially finds the one it overrates, which is
  exactly what `_deWinnersCurse` exists for; reuse it rather than rediscovering it.
- **Clears** when the bid exceeds the price by `TRADE_MIN_SURPLUS`, paid in the sweetener
  that closes the gap.

⚠️ **`FO_SCOUT_INCUMBENT_NOISE_SCALE` is doing real work here and should not be flattened.**
Each club reads its own player precisely and a stranger noisily, which is the actual
asymmetry of trading — a trade happens when the two misreads point in opposite directions.

## Legality

| rule | why |
|---|---|
| Both rosters complete at settlement | an empty slot rates **50**; never rely on the engine tolerating `None` |
| In-season trades are **position-for-position**, or player-for-assets **with a prospect backfill** | six locked slots, no bench |
| Closes at week 22 | owner; coincides with `GM_ACTIVE_WEEK` |
| A club may not trade a player it acquired this season | stops churn and pass-the-parcel |
| Volume capped per club per season | GM turnover measures 1-4 exits a season against a stated "not a carousel" bar; hold trading to the same and **measure it** |

## Visibility

- **League news** on every trade — `league_news.publish()`. ⚠️ keyword-only and camelCase; a
  snake_case typo has caused two incidents including a production outage.
- **A central transactions page**, new. `SeasonRecapEvent` is the durable log and `trade`
  joins its existing kinds. ⚠️ Its idempotency key is `(season, event_type,
  player_id|team_id)` — one player, one club — which a two-sided trade does not fit; it needs
  a trade id or the resume dedupe silently drops half a swap.

## Settled rulings carried in

- Season stats **stay with the player** — already the behaviour (`team_id` is overwritten with
  the current club on every save).
- Fan sentiment **does not follow** — and since the own-club gate is on *writing* only, that
  means clearing the rows on the trade.
- A traded player gets a **new card minted** with the new club; cards already held of him at
  his old club are untouched. ⚠️ Templates mint once per season and return early, so this
  needs its own path — and it creates two scoreable cards of one player in a season.
- **Rookie picks are tradeable.**
- **No competitive-balance tax** for now.

## Open

1. **Pick horizon** — how many seasons out? Two bounds the mortgage.
2. **Does a contender ever sell?** The model says no, which is realistic but means the eight
   sellers are the whole supply. If that proves thin, the lever is letting a club sell a
   walk-year player it has *already decided* not to re-sign, contending or not.
3. **Rental pricing** — a six-week rental of an 80 is worth what, in picks or Floobits?
   Nothing in the economy prices a partial season yet.
4. **Volume cap** per club per season.
5. **Does the buyer's own congestion matter?** A contender at its re-sign limit is renting
   too, and should know it — otherwise it overpays for a player it also cannot keep.
