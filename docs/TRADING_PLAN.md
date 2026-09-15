# In-season trading — plan

_Owner-directed, 2026-09-14/15. Feasibility and the full decision trail are in
`docs/TRADING_FEASIBILITY.md` (15 addenda). The prospect draft this depends on is in
`docs/PROSPECT_DRAFT_PLAN.md`._

---

## 1. Why trades happen

### ⚠️ The engine is the re-sign limit, not GM disagreement

The obvious model — two GMs value a player differently, so they swap — is **noise wearing a
strategy's clothes**. With six position-locked slots there are no holes and no surpluses:
every club has exactly one of each. Nothing creates a *need*.

**Contract congestion does.** `RESIGN_LIMIT_PER_OFFSEASON` is 2, and on the live league:

> **89 of 192 players (46%) are on walk years. 18 of 32 clubs have more than two expiring.
> 33 players — 2,420 rating points — walk for ZERO return at season end.**

A club about to lose a player for nothing should sell him for something. Principled,
abundant, and free with a mechanic that already ships.

### Sellers and buyers

⚠️ **Congestion alone does not make a seller.** Pinecones are the most congested club in the
league (5 expiring, 3 forced walks) *and* the best — they **rent** their walk-years for the
playoff run and lose them at season end, exactly as a real contender does. Selling needs
congestion **and** no run to protect.

Against the season-6 forecast, split at the median (14.0 wins):

| | |
|---|---|
| **Sellers** — congested, not contending | **8**: Slippers, Grillmeisters, Bees, Raccoons, Beans, Cranes, Rocks, Phones |
| **Buyers** — contending | **16**, headed by Pinecones, Curd, Residents, Dry Heat |

Thirteen departing players against sixteen clubs with a reason to rent. A functioning market
on day one.

---

## 2. Valuation — one scale for four asset classes

### Surplus over replacement × seasons of control

**Value = how much better than freely-available, multiplied by how long you keep it.**

Replacement is not zero: a club can always sign from the FA pool, currently ~**67**. So an 80
is worth 13 surplus, not 80. Time is the other half, and `termRemaining` already carries it —
a walk-year player traded in week 10 is **0.64 seasons** of control against **2.64** for the
same player with three years left. **A 4x spread on identical talent.**

| asset | value |
|---|---|
| **roster player** | `(rating − 67) × seasonsOfControl(termRemaining, week)` |
| **prospect** | projected mature surplus × seasons × wash-out discount, read through the buyer's own `scoutingVision` |
| **rookie pick** | expected mature surplus at that slot × seasons × risk |
| **Treasury** | face value ÷ a conversion rate — ⚠️ the one number with no anchor yet |

### The pick curve is steep

Expected true skill of the player taken at each slot (order statistics of 32 draws from the
live generation constants, 4,000 classes):

| pick | 1 | 3 | 8 | 12 | 16 | 24 | 32 |
|---|---:|---:|---:|---:|---:|---:|---:|
| true skill | **98.6** | 92.0 | 85.2 | 81.6 | 78.4 | 71.8 | **57.2** |

Pick 1 is a future superstar, pick 16 league-average, pick 32 a token. That steepness is what
makes an early pick a real asset and gives the market denominations to settle a gap with.

⚠️ **Mid-season a pick is a DISTRIBUTION, not a number** — the order is worst-first by *final*
record, so a club trading its own pick is selling something it is still determining by
playing.

### ⚠️ The contention weight is what makes a market exist at all

On the raw scale, **picks dominate rentals ~10x and nothing would ever clear.** The missing
term is that clubs do not share a discount rate:

> A contender prices THIS season high and the future low. A club going nowhere does the
> reverse. **Both are right. They want different currencies, and that gap is the trade.**

`nowWeight = (contention / leagueMean) ** 1.25`. Swept on Bees' WR 80 at week 10 — the
earliest pick each buyer would part with:

| buyer | e=1.0 | **e=1.25** | e=1.5 | e=2.0 |
|---|---:|---:|---:|---:|
| Pinecones (25.6W) | 20 | **17** | 12 | **2** |
| Curd (21.0W) | 24 | **22** | 20 | 15 |
| Waffles (15.8W) | 26 | **26** | 26 | 25 |

**1.25.** At 2.0 the best club pays a top-two pick for a six-week rental, which no real club
does. Linear compresses the market into picks 20-26 — a 6-slot spread with little separating
a 25-win club from a 16-win one. 1.25 gives 9 slots and lands a rental mid-round.

### ⚠️ Contention is UNCERTAIN early, and that produces the deadline for free

A club does not know in week 2 whether it is a contender, so `nowWeight` reads off a **blend
of prior expectation and this season's evidence**.

✅ That blend already exists: `teamManager.applyRegularSeasonPressureBlend`, `progress =
(week − 1) / 14`. Reuse its shape rather than inventing a second ramp.

| week | Pinecones | Bees | gap |
|---:|---:|---:|---:|
| 1 | 1.00 | 1.00 | **1.00** |
| 8 | 1.54 | 0.84 | 1.84 |
| 12 | 1.87 | 0.75 | 2.50 |
| 15+ | 2.12 | 0.68 | **3.12** |

⚠️ **In week 1 every club sits at 1.00, so buyer and seller price the future identically and
there is no gap to trade across. Nothing fires.** The market opens as the table separates —
**a deadline without a deadline rule.**

**Bubble clubs fall out of the same number**: near 1.0 they value now and later almost
equally, so they neither buy nor sell — they stand pat *by arithmetic*. Their next few results
push them one way, and then they act.

⚠️ Certainty arrives at week 15 while the deadline is week 22, leaving a seven-week window
where clubs *know* and must act. If the picture should keep sharpening to the deadline
itself, widen the ramp to 21 — do not add a second term.

### The three modifiers — all a PRICE, never a VETO

The same rule governs all three, matching how `sentimentTilt` is described everywhere else in
the front office: *it tips close calls, it never dictates.*

#### Fan sentiment — it must raise the BAR, not the seller's valuation

⚠️ The obvious wiring **does nothing**. Letting a beloved player's `sentimentTilt` raise his
club's valuation left every buyer's clearing pick **identical** across the full tilt range,
because **the seller's constraint never binds**: Bees' rental is worth 5.7 to them and even
pick 26 is worth 13.5 — every pick already beats a player they were losing for nothing. The
buyer is the only side that can refuse.

So sentiment raises **the surplus the trade must clear**:

| required surplus | +0% | +30% | +100% |
|---|---:|---:|---:|
| Pinecones | 17 | 20 | **24** |
| Waffles | 26 | 27 | **27** |

At +30% a favourite costs a contender ~3 extra picks of value; at +100% he is only movable to
the strongest buyer in the league.

⚠️ **Sentiment is LIVE, and CLAUDE.md says otherwise.** It records *"no production player or
GM has reached even the old floor"* — measured under the old flat league-wide quorum of 3.
Under the per-club rule prod holds **153 ratings across 107 players**, four clearing quorum
today, two at a perfect 5.0.

#### Divisional reluctance — you do not arm a rival

| counterparty | games against per season | premium |
|---|---:|---|
| **division rival** | **4** | large |
| same league, other division | 1 | small |
| other league | 1 | none |

12 division games across 3 rivals is **4 apiece**; the other 12 league games spread over 12
clubs and the 4 interleague over 4. **A division rival is faced four times as often as anybody
else** — the ratio is the premium, derived from the schedule rather than chosen. They are also
the only clubs that can take a **division title**, which at 8 divisions is what most of the
league is playing for.

⚠️ **Scale it by the rival's threat, not flat.** Selling a rental to a 3-9 rival costs
nothing; selling to the club you are chasing is self-harm. Scale by the buyer's `nowWeight`.

⚠️ The seller is by definition not contending, so "why care who wins the division" is fair.
Two answers hold: they play that rival four more times next season, and their own fans care
now — and this league already models exactly that.

#### Attitude — a toxic player damages the room, and the GM cannot currently see it

`seasonManager._applyLockerRoomDrift` runs **every week**, nudging each starter's confidence
and determination toward the room's average attitude, coach-anchored at 1/3 weight. Its own
docstring: *"a toxic veteran genuinely poisons teammates' confidence."*

⚠️ **`frontOfficeBrain` never reads attitude. Not once.** The sim models the damage and gives
the GM no way to perceive it.

The spread is large: rostered attitude **35-100** (median 72), team rooms span **20 points**
(Exoticos 82.8, Grillmeisters 62.7). Live cases — Chud Bumpington rates **85 on a 45
attitude**.

✅ **It does not become a dumping ground, because the damage travels.** The naive version
(seller discounts, buyer does not) would have GMs palming headcases off on each other. But the
drift lands in whichever room he is in, so both clubs price it and a toxic player is simply
worth less to everybody.

⚠️ **The trade comes from the ROOM, not from blindness.** Drift works off `(avgAttitude × 3 +
coachAttitude) / 4`, so a strong room with a leader coach absorbs one bad apple while an
already-toxic room compounds. **Exoticos can take a headcase Grillmeisters cannot**, and pay
less than his rating suggests. Change of scenery as arithmetic, and it makes a good locker
room a tradeable asset in itself.

Attitude needs **no scouting band** — unlike potential it is not hidden.

⚠️ **It belongs in `decisionValue`, which means it reaches CUTS and RE-SIGNS too** (owner).
That is the one number every front-office decision consumes, so a single term covers
`rankCutCandidates`, `rankResignCandidates`, `buildDraftBoard`, prospect promotion and the
trade market alike. **This is therefore a live front-office change, not a trade-only
feature** — it alters how the current league cuts and re-signs the moment it ships, and wants
measuring on its own.

✅ Not double-counting: `corr(rating, attitude) = +0.293` across 192 rostered players — weakly
positive (85+ attitude averages 84.2 rating against 79.3 for sub-55), nowhere near enough that
rating already carries it.

⚠️ **Soft, for the reason the Appeal gate already taught.** Discount toxic players hard enough
and they pool in free agency, never get signed, and the supply floor generates replacements
around them — the exact failure that made `FLOOS_SOFT_APPEAL_PENALTY` a 0.90 multiplier rather
than a veto. `_attemptRosterFill`'s last tier already drops the board rather than leave a slot
empty, so a difficult player is still signed when nothing else is there.

---

## 3. Mechanics

A **two-sided listing market, resolved as a weekly auction.** Any club may post an asset it
will move together with what it wants back; every other club prices what is posted; the poster
takes the best offer clearing its reserve.

Two-sided rather than sellers-only because it unifies both shapes without special-casing — a
rebuilder posting *"WR 80, want picks"* and a contender posting *"QB 78 with 3 years, want a
rental"* are the same operation, and the second **is** the 1-for-1 QB-for-QB swap.

### 3.1 Deciding to list — four triggers

| trigger | condition | what gets posted |
|---|---|---|
| **expiring surplus** | walk-year, over the re-sign limit, not contending | the player — he leaves for nothing otherwise |
| **horizon mismatch** | contending and holding term it would swap for now, or the reverse | the contract |
| **blocked prospect** | a pipeline prospect the GM rates above the incumbent | the incumbent |
| **locker room** | attitude dragging the room down | the player, contending or not |

⚠️ **The horizon trigger is what makes a 1-for-1 a real trade rather than a coin flip.**
QB-for-QB is a **TIME trade**, not a talent trade — a rebuilder gives up now for term, a
contender term for now, and both are right. Rating barely enters; `seasonsOfControl` does.

⚠️ **The blocked-prospect trigger is one of three independent reasons the draft lands first.**
It cannot fire with an empty pipeline.

### 3.2 Choosing who to approach — public information only

Rank counterparties on what is observable: **standings** (contention), **roster**, **contract
state**, **Treasury**.

⚠️ What a lister **cannot** see is the other GM's `_scoutError` and fan `sentimentTilt` — which
is precisely why an offer can be declined. Remove that and every trade is pre-agreed and the
market is theatre.

Approach the top `TRADE_CANDIDATES_PER_LISTING` (3-5), not all 31, so a weekly pass stays
legible in the news feed.

### 3.3 Pricing — ask, floor, and the price actually paid

Three distinct numbers. ⚠️ **Conflating them is the mistake:**

| | what it is |
|---|---|
| **ask (reserve)** | what the seller currently demands. Opens at full value, decays toward the floor |
| **floor** | the walk-away. Below it, keeping him beats trading him. Set by the **backfill** |
| **price paid** | the **highest bid** clearing the ask — set by the market, never by the floor |

**The floor is the cost of the downgrade**, and the model already knows it:

```
ask   = (player − REPLACEMENT) × seasonsLeft × nowWeight
floor = (player − backfill)    × seasonsLeft × nowWeight
```

Same shape; the floor simply measures against **who actually replaces him**. Bees' WR 80
backfilled by a 70:

| week | ask | floor |
|---:|---:|---:|
| 5 | 7.3 | 5.6 |
| 10 | 5.7 | 4.4 |
| 20 | 2.5 | 1.9 |
| 22 | 1.9 | 1.5 |

✅ Both ends decay together, so a late seller is never squeezed into a giveaway.

⚠️ **A ready prospect makes a club WILLING, not CHEAP.** A low floor buys **room to hold out
later**, not a discount now — and because settlement is an auction, a seller with three
interested contenders gets the best of the three whatever its floor is. The club should be
converting a departing player into **future value, typically picks**.

**The floor moves with the backfill**, at week 10:

| backfill | floor | vs the 5.7 ask |
|---:|---:|---|
| 62 | **7.9** | above the ask — **will not sell** |
| 70 | 4.4 | can discount |
| 79 | **0.4** | can go very low if it must |

⚠️ `floor < ask` requires `backfill > REPLACEMENT`. **A pipeline is literally what makes a club
a seller** — the third independent argument for the draft landing first.

**Each approached club bids** its private de-cursed value. ⚠️ `_deWinnersCurse` is not
optional: a buyer choosing the best-looking of several listings preferentially finds the one it
overrates, the exact bias that function exists for. A bid is a **bundle** — picks, prospects,
Floobits or a player — the cheapest combination clearing the reserve, capped at
`TRADE_MAX_PIECES` (2-3) so a trade reads as a sentence.

### 3.4 Settling — the best bid wins

The lister takes the **highest bid above its reserve**; the rest lapse. An auction rather than
first-come because sixteen contenders will want the same rental, and the auction turns
competition into a price instead of a race.

⚠️ **No second round within a week, and no rule is needed to prevent it.** A sealed round where
each buyer bids its private value is already optimal discovery. An *ascending* second round is
**worse for the seller**: the winner only has to top the runner-up, so the seller captures the
second-best valuation instead of the best. "Let me shop this around" feels like leverage and is
a discount.

### 3.5 Listings persist, re-priced weekly

An unsold listing **stays on the block** and is re-evaluated every week, because three inputs
have moved: the **ask** has decayed, the lister's **contention** has sharpened, and every
bidder's has too.

✅ **Deadline pressure falls out of the value model with no new term:**

| week | 1 | 10 | 15 | 20 | 22 |
|---|---:|---:|---:|---:|---:|
| reserve vs week 1 | 100% | 67% | 48% | **30%** | **22%** |

Hold out early, take what you can get late — exactly how a real deadline behaves.

⚠️ **A club may also WITHDRAW.** A bubble team that wins six straight becomes a buyer and
should pull its own player off the block. Same check as the listing trigger, re-run — it needs
no separate rule, only that triggers are evaluated **every week** rather than latched at
listing time.

### 3.6 Settlement, in order

1. verify both rosters will be complete (a prospect to promote, or player-for-player)
2. move the assets; stamp `previousTeam`
3. **promote the backfill prospect** — `_promoteProspectsAutonomously` already does this,
   ⚠️ but its bar compares against a free agent the club could sign, and mid-season there is
   **no signing path at all**. The real alternative is an empty slot rating **50**, so the bar
   must drop to near zero in-season
4. clear the traded player's fan sentiment rows
5. mint his new card at the new club; leave existing cards alone
6. publish to `league_news`; write the `SeasonRecapEvent` with a **trade id**

### 3.7 Cadence and rate limits

Runs **weekly** in the existing per-week hook block, closing at **week 22** — the first week of
the final game day, already `GM_ACTIVE_WEEK`.

| limit | value | why |
|---|---|---|
| listings per club at once | 1 | else every congested club posts three players in week 1 |
| bids per club per week | 1 | stops a contender hoovering the block in one pass |
| trades per club per season | 2-3 | GM turnover runs 1-4 exits a season against a "not a carousel" bar |

⚠️ **The volume caps are the part most likely to be wrong on the first try, and the only way to
know is to run a season and count.** Eight sellers and sixteen buyers is a lot of willing
counterparties; without limits week 1 would move a third of the league.

---

## 4. Legality

| rule | why |
|---|---|
| both rosters complete at settlement | an empty slot rates **50**; never rely on the engine tolerating `None` |
| position-for-position, or player-for-assets **with a prospect backfill** | six locked slots, no bench |
| closes at week 22 | owner; coincides with `GM_ACTIVE_WEEK` |
| a club may not trade a player it acquired this season | stops pass-the-parcel |
| volume capped per club per season | see above — and **measure it** |

## 5. Visibility

- **League news** on every trade via `league_news.publish()`. ⚠️ keyword-only and camelCase; a
  snake_case typo has caused two incidents, one a production outage. `test_publish_kwargs.py`
  sweeps call sites statically.
- **A central transactions page**, new. `SeasonRecapEvent` is the durable log and `trade` joins
  its existing kinds. ⚠️ Its idempotency key is `(season, event_type, player_id|team_id)` —
  one player, one club — which a two-sided trade does not fit; it needs a **trade id** or the
  resume dedupe silently drops half a swap.
- **The trade block itself is a surface.** Listings persist with visible interest, which is the
  live half of the transactions page and costs nothing extra.

## 6. Settled rulings

| | |
|---|---|
| season stats | **stay with the player** — already the behaviour (`team_id` overwritten with the current club on every save) |
| fan sentiment | **does not follow** — and since the own-club gate is on *writing* only, that means **clearing the rows** on the trade |
| cards | a traded player gets a **new card minted** at his new club; cards already held of him at his old club are untouched. ⚠️ Templates mint once per season and return early, so this needs its own path — and it creates two scoreable cards of one player in a season |
| rookie picks | **tradeable** |
| competitive-balance tax | **not built** — measured at ~one season of earlier correction on one club |
| attitude | enters `decisionValue`, so it reaches cuts and re-signs as well as trades |

## 7. Open

1. **Treasury → value conversion rate.** The only asset class with no anchor.
2. **Pick horizon** — how many seasons out? Two bounds the mortgage.
3. **Volume caps** — sized by running a season and counting, not by choosing.
4. **Does a contender ever sell?** The model says no, which is realistic but makes those eight
   clubs the whole supply. Lever if thin: let a club sell a walk-year player it has *already
   decided* not to re-sign, contending or not.
5. **Transactions page scope** — trades only, or the full `SeasonRecapEvent` log with trades as
   one kind?
6. **Attitude term magnitude** — a live front-office change; wants measuring on its own before
   it rides in with trading.
