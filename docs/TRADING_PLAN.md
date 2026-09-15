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

## Quantifying value — one scale for four asset classes

The owner's expansion (1-for-1 same-position swaps; returns of a player **plus** a prospect,
or a prospect **plus** a pick) means every asset has to price on a common scale. It is
buildable, and the shape falls out of two ideas.

### Surplus over replacement, times seasons of control

**Value = how much better than freely-available, multiplied by how long you keep it.**

Replacement is not zero — a club can always sign from the FA pool, whose current level is
~**67**. So an 80 is worth 13 surplus, not 80. And time is the other half: a walk-year player
traded in week 10 is **0.64 seasons** of control; the same player with three years left is
**2.64**. That is a **4x** spread on identical talent, and `termRemaining` already carries it.

| asset | value |
|---|---|
| **roster player** | `(rating − 67) × seasonsOfControl(termRemaining, week)` |
| **prospect** | projected mature surplus × seasons of control × a wash-out discount — ⚠️ read through the buyer's own `scoutingVision`, so trading prospects carries genuine uncertainty about what you got |
| **rookie pick** | expected mature surplus at that slot × seasons × risk |
| **Treasury** | face value ÷ a conversion rate (the one number with no anchor yet) |

### The pick curve is steep, and that matters

Expected true skill of the player taken at each slot (order statistics of 32 draws from the
live generation constants, 4,000 classes):

| pick | 1 | 3 | 8 | 12 | 16 | 24 | 32 |
|---|---:|---:|---:|---:|---:|---:|---:|
| true skill | **98.6** | 92.0 | 85.2 | 81.6 | 78.4 | 71.8 | **57.2** |

Pick 1 is a future superstar; pick 16 is a league-average player; pick 32 is nearly a token.
**That steepness is what makes an early pick a real asset** and gives the market a wide range
of denominations to settle a gap with.

⚠️ **Mid-season a pick is a DISTRIBUTION, not a number** — the order is worst-first by *final*
record, which is not known while the season runs. A club trading its own pick in week 10 is
selling something whose value it is still determining by playing.

### ⚠️ The contention weight is what makes a market exist

On the raw scale above, **picks dominate rentals by roughly 10x and nothing would ever
clear**. The missing term is that clubs do not share a discount rate:

> A contender prices THIS season high and the future low. A club going nowhere prices the
> future high and this season at almost nothing. **Both are right. They simply want
> different currencies — and that gap is the trade.**

Modelled as `nowWeight = (forecastWins / leagueMean) ** 2`, and tested on Bees' WR 80 at
week 10 (a club whose own weight is **0.54**):

| buyer | forecast W | nowWeight | clears at |
|---|---:|---:|---|
| Pinecones | 25.6 | 3.33 | **pick 2** and later |
| Curd | 21.0 | 2.26 | pick 15 |
| Residents | 20.2 | 2.08 | pick 17 |
| Dry Heat | 18.2 | 1.68 | pick 22 |
| Waffles | 15.8 | 1.27 | pick 25 |

Every slot clears for the *seller* — a pick always beats a rental they were losing for
nothing — so **the buyer's contention sets the price**, and price discovery falls out of the
standings rather than being scripted.

**Swept** on Bees' WR 80 at week 10 — the earliest pick each buyer would part with:

| buyer | e=1.0 | **e=1.25** | e=1.5 | e=2.0 |
|---|---:|---:|---:|---:|
| Pinecones (25.6W) | 20 | **17** | 12 | **2** |
| Curd (21.0W) | 24 | **22** | 20 | 15 |
| Dry Heat (18.2W) | 25 | **24** | 24 | 22 |
| Waffles (15.8W) | 26 | **26** | 26 | 25 |

**e=1.25 is the pick.** At 2.0 the best club pays a top-two pick for a six-week rental, which
no real club does. Linear compresses the whole market into picks 20-26 — a 6-slot spread with
little to distinguish a 25-win club from a 16-win one. **1.25 gives a 9-slot spread and lands
a rental at the middle of the round**, which is where a rental belongs.

## ⚠️ Fan sentiment: it must raise the BAR, not the seller's valuation

Owner: clubs should try not to trade fan favourites. `sentimentTilt` already feeds
`decisionValue`, so the obvious wiring is to let a beloved player's tilt raise his club's
valuation — **and that does exactly nothing.** Measured across the full tilt range (+0 to +5,
the cap), every buyer's clearing pick was **identical**:

| tilt | +0 | +1 | +2 | +3 | +5 |
|---|---|---|---|---|---|
| Pinecones | pick 17 | pick 17 | pick 17 | pick 17 | pick 17 |

The reason is structural: **the seller's constraint never binds.** Bees' rental is worth
**5.7** to them and even pick 26 is worth **13.5** — every pick in the round already beats a
player they were losing for nothing. The buyer is the only side that can refuse, so a premium
on the seller's private valuation is not the binding term and is swallowed whole.

For sentiment to bite it has to raise **the surplus the trade must clear**:

| required surplus | +0% | +15% | +30% | +50% | +100% |
|---|---:|---:|---:|---:|---:|
| Pinecones | 17 | 18 | 20 | 21 | **24** |
| Curd | 22 | 23 | 24 | 25 | **26** |
| Waffles | 26 | 26 | 27 | 27 | **27** |

At **+30%** a fan favourite costs a contender roughly three extra picks of value, and at
**+100%** he is effectively only movable to the strongest buyer in the league. That is "try
not to trade fan favourites" landing as **a price rather than a veto** — which matches how
sentiment is described everywhere else in the front office: *it tips close calls, it never
dictates.*

⚠️ **Sentiment is LIVE now, and CLAUDE.md says otherwise.** It records *"no production player
or GM has reached even the old floor"* — that was measured under a flat league-wide quorum of
3. The per-club rule (`max(1, ceil(teamFavoriters × 0.34))`) changed it: prod holds **153
ratings across 107 players**, and at least four clear their club's quorum today, including two
at a perfect 5.0. The term has data to work with.

### Bundles and 1-for-1

Once assets price on one scale, both of the owner's shapes are the same operation:

- **1-for-1 same position** clears when each side's valuation of the incoming player exceeds
  its own outgoing one. ⚠️ Note this already produces a real trade with no sweetener: a
  walk-year 84 is worth *less* than a controlled 78 on the scale, so the club holding the
  rental is the one that pays — unless it is contending, where `nowWeight` flips it.
- **Bundles** are a subset-sum against the gap: find the cheapest combination of pick,
  prospect and Floobits that closes the difference, capped at some number of pieces so a
  trade stays legible in the news feed.

## Mechanics — how a trade actually happens

A **two-sided listing market, resolved as a weekly auction.** Any club may post an asset it
is willing to move together with what it wants back; every other club prices what is posted;
the poster takes the best offer clearing its reserve.

Two-sided rather than sellers-only because it unifies both of the owner's shapes without
special-casing either — a rebuilder posting *"WR 80, want picks"* and a contender posting
*"QB 78 with 3 years, want a rental"* are the same operation, and the second is exactly the
1-for-1 QB-for-QB swap.

### 1. Deciding to list — three triggers

A club posts an asset when one of these is true. All three are read off state that already
exists; none needs a new signal.

| trigger | condition | what gets posted |
|---|---|---|
| **expiring surplus** | walk-year player, club is over `RESIGN_LIMIT_PER_OFFSEASON`, and not contending | the player — he leaves for nothing otherwise |
| **horizon mismatch** | contending, and holding a long contract it would swap for immediate help (or the reverse) | the contract, wanting a rental back |
| **blocked prospect** | a pipeline prospect the GM rates above the incumbent at his position | the incumbent |

⚠️ **The horizon trigger is what makes a 1-for-1 a real trade rather than a coin flip.** A
QB-for-QB swap is not a talent trade, it is a **TIME trade**: a rebuilder gives up now for
term, a contender gives up term for now, and both are right. Rating barely enters it —
`seasonsOfControl` does.

⚠️ **The blocked-prospect trigger is why the draft has to land first.** It cannot fire with
an empty pipeline, and it is the trigger that gives a rebuilding club something to do beyond
selling.

### 2. Choosing who to approach — public information only

A lister ranks counterparties on what it can actually observe: **standings** (contention),
**roster** (who they field at each position), **contract state**, and **Treasury**. All of
that is public.

⚠️ **What it cannot see is the other GM's private read** — their `_scoutError` on the player
and their fan `sentimentTilt`. So a lister's estimate of who will bite is *approximately*
right and sometimes wrong, which is why an offer can be declined at all. Remove that and
every trade is pre-agreed and the market is theatre.

Approach the top `TRADE_CANDIDATES_PER_LISTING` (3-5) rather than all 31, so a weekly pass
stays legible in the news feed.

### 3. Pricing — a reserve and a bid

**The lister sets a reserve**, not an asking price: the minimum it will accept, computed on
its own scale (surplus over replacement × seasons of control × its own `nowWeight`), raised
by the fan-favourite premium.

**Each approached club bids** its private value for the asset, de-cursed. ⚠️ `_deWinnersCurse`
is not optional here: a buyer choosing the best-looking of several listings preferentially
finds the one it overrates, which is the exact bias that function exists for and the reason
free agency needed it.

A bid is a **bundle** — picks, prospects, Floobits, or a player — assembled as the cheapest
combination clearing the reserve, capped at `TRADE_MAX_PIECES` (2-3) so a trade stays
readable as a sentence.

### 4. Settling — the best bid wins

The lister takes the **highest bid above its reserve**; everything else lapses. An auction
rather than first-come because sixteen contenders will want the same rental, and the auction
is what turns that competition into a price instead of a race.

Unsold listings **persist** to the next week rather than being re-posted, so a player sits on
the block with visible interest — which is the drama, and it is free.

### 5. Settlement, in order

1. verify both rosters will be complete (the seller has a prospect to promote, or the trade
   is player-for-player)
2. move the assets; stamp `previousTeam`
3. **promote the backfill prospect** — `_promoteProspectsAutonomously` already does this,
   ⚠️ but its bar compares against a free agent the club could sign, and mid-season there is
   no signing path at all. In-season the alternative is an empty slot rating **50**, so the
   bar must drop to near zero
4. clear the traded player's fan sentiment rows
5. mint his new card at the new club; leave existing cards alone
6. publish to `league_news`, and write the `SeasonRecapEvent` with a **trade id**

### ⚠️ Divisional reluctance — you do not arm a rival

A club charges a **premium to trade inside its own division**, and the weight is derived from
the schedule rather than chosen:

| counterparty | games against them per season | premium |
|---|---:|---|
| **division rival** | **4** | large |
| same league, other division | 1 | small |
| other league | 1 | none |

12 division games across 3 rivals is **4 apiece**; the other 12 league games are spread over
12 clubs and the 4 interleague games over 4, so **a division rival is faced four times as
often as anybody else.** That ratio is the premium.

And they are the only clubs that can take a **division title** from you — which at 8
divisions is what most of the league is actually playing for, since 24 of 32 will never win
a league championship.

⚠️ **A price, not a veto**, matching the fan-favourite rule and `sentimentTilt`'s stated
behaviour everywhere else in the front office: *it tips close calls, it never dictates.* A
division rival can still get the player — it just has to pay over the odds, which is exactly
what a fan would expect to see.

⚠️ **The premium should scale with the rival's threat, not be flat.** Selling a rental to a
3-9 division rival costs nothing; selling to the club you are chasing is self-harm. Scale it
by the buyer's own `nowWeight` so an irrelevant rival is nearly free and a contending one is
expensive.

⚠️ **And note the seller is by definition NOT contending**, so "why do they care who wins the
division" is a fair question. Two reasons that both hold: they meet that rival four times
again next season, and their own fans care now. The second is the real one — a club arming
its rival is the sort of thing supporters remember, and this league has a sentiment system
that already models exactly that.

### Shopping an offer — the second round is NEXT WEEK

Can a seller take a good offer back to the other bidders and ask for better? **Deliberately
no, within a week** — and it needs no rule to prevent, because the structure already answers
it better.

A single **sealed round** where each buyer bids its private value, and the seller takes the
best, is already optimal price discovery for that moment. Running a second, *ascending* round
makes it worse for the seller, not better: in an ascending auction the winner only has to top
the second-best bid, so the seller captures the runner-up's valuation instead of the
winner's. "Let me shop this around" feels like leverage and is actually a discount.

**The real second round is the following week.** A listing that does not clear its reserve
**persists**, so a seller holding out for more simply does not sell and the block is offered
again — to a league whose standings have moved, which means the bids have moved too.

✅ **And the deadline pressure falls out of the value model with no new term.** A walk-year
player's reserve decays on its own as `seasonsOfControl` shrinks:

| week | seasons of control | reserve vs week 1 |
|---:|---:|---:|
| 1 | 0.96 | 100% |
| 10 | 0.64 | 67% |
| 15 | 0.46 | 48% |
| 20 | 0.29 | **30%** |
| 22 | 0.21 | **22%** |

So a seller that holds out in week 5 is asking three times what it will accept in week 20 —
**hold out early, take what you can get late**, which is exactly how a real deadline behaves.
Nothing had to be written to produce it.

### The reserve floor is the cost of the downgrade

The floor is not a constant to pick — the value model already knows it. Ask what the club
actually loses by trading, versus not:

> **Not trading:** keep him for the rest of the season, then lose him for nothing.
> **Trading:** lose him now, promote the backfill, bank the return.

The only real difference is **the on-field cost of the downgrade for the weeks remaining.**
So:

```
floor = (player - backfill) x seasonsLeft x nowWeight
ask   = (player - REPLACEMENT) x seasonsLeft x nowWeight      # the opening reserve
```

Same shape, same terms; the floor simply measures against **who actually replaces him**
rather than against a generic free agent. Bees' WR 80 backfilled by a 70:

| week | opening ask | floor | room to fall |
|---:|---:|---:|---:|
| 5 | 7.3 | 5.6 | 1.7 |
| 10 | 5.7 | 4.4 | 1.3 |
| 15 | 4.1 | 3.2 | 0.9 |
| 20 | 2.5 | 1.9 | 0.6 |
| 22 | 1.9 | 1.5 | 0.4 |

✅ **Both ends decay together**, so a late-season seller is not squeezed into a giveaway — the
gap narrows but never inverts, and the club always holds a real walk-away.

### ⚠️ And the floor moves with the backfill, which is the good part

At week 10, the same player, same club:

| backfill | floor | vs the 5.7 ask |
|---:|---:|---|
| 62 | **7.9** | above the ask — **will not sell** |
| 70 | 4.4 | sells at a discount |
| 76 | 1.7 | sells cheap |
| 79 | **0.4** | nearly free |

**A club with a good prospect ready loses little by selling, so it sells cheaply. A club with
nothing behind him will not sell at any price.** That is the blocked-prospect trigger and the
reserve floor turning out to be the same idea from two directions, and neither needed a rule
written for it.

⚠️ `floor < ask` requires `backfill > REPLACEMENT`. A club whose only backfill is a generic
free agent has a floor at or above its ask and effectively refuses every offer — correct,
because moving him gains it nothing. **A pipeline is what makes a club a seller**, which is
the third independent argument that the draft has to land before trading does.

### ⚠️ Correction: a ready prospect makes a club WILLING, not CHEAP

The floor derivation above is right and the framing around it was wrong. **The floor is the
walk-away, not the ask.** A club with a good prospect behind him does not sell cheaply — it
sells *willingly*, and still for the best price it can get.

Three distinct numbers, and conflating them is the mistake:

| | what it is |
|---|---|
| **ask (reserve)** | what the seller currently demands. Opens at full value and decays toward the floor as the deadline nears |
| **floor** | the walk-away. Below it, keeping him beats trading him. Set by the backfill |
| **price paid** | the **highest bid** clearing the ask — set by the market, never by the floor |

So a low floor buys **room to hold out later**, not a discount now. And because settlement is
an auction, a seller with three interested contenders gets the best of the three whatever its
floor is. A club should be trying to convert a departing player into **future value —
typically picks** — not to clear him off the books.

⚠️ The floor only ever binds when **nothing clears the ask**, and then the question is hold or
drop. A club with no backfill cannot drop at all; a club with a ready prospect can, which is
why the pipeline decides *whether* a club is a seller rather than *how much* it accepts.

### ⚠️ Contention is uncertain early, and that produces the deadline for free

A club does not know in week 2 whether it is a contender. `nowWeight` must therefore be read
off a **blend of prior expectation and this season's evidence**, not off a final forecast.

✅ **That blend already exists**: `teamManager.applyRegularSeasonPressureBlend` runs at every
week start with `progress = (week - 1) / 14` — 100% prior at week 1, 100% in-season by week
15. Reuse its shape rather than inventing a second ramp.

The consequence is the important part:

| week | Pinecones `nowWeight` | Bees `nowWeight` | gap |
|---:|---:|---:|---:|
| 1 | 1.00 | 1.00 | **1.00** |
| 4 | 1.23 | 0.93 | 1.32 |
| 8 | 1.54 | 0.84 | 1.84 |
| 12 | 1.87 | 0.75 | 2.50 |
| 15+ | 2.12 | 0.68 | **3.12** |

⚠️ **In week 1 every club sits at 1.00, so a buyer and a seller price the future identically
and there is no gap to trade across. Nothing fires.** The market opens as the table
separates — which produces a deadline **without a deadline rule**. The rush toward week 22 is
not scripted; it is what happens when clubs stop guessing.

⚠️ Certainty arrives at **week 15** on that ramp while the deadline is **week 22**, which
leaves a seven-week window where clubs *know* and must act. That is the right shape — but if
the picture should keep sharpening to the deadline itself, widen the ramp to 21 rather than
adding a second term.

**Bubble clubs are the interesting case and they fall out of the same number.** A club sitting
near `nowWeight` 1.0 in week 12 values now and later almost equally, so it neither buys nor
sells — it stands pat by arithmetic, not by a rule. Its next few results push it one way or
the other, and *then* it acts.

### Do listings persist? Yes — and they are re-priced weekly

A listing that does not clear **stays on the block** and is re-evaluated every week, because
three of its inputs have moved:

- the **ask** has decayed (`seasonsOfControl` shrinks),
- the lister's **contention** has sharpened (the blend above),
- every bidder's contention has too, so the bids differ.

⚠️ **And a club may WITHDRAW.** A bubble team that wins six straight becomes a buyer — it
should pull its own player off the block rather than sell into a run it is now part of. The
withdrawal is the same check as the listing trigger, re-run; it needs no separate rule, only
that the trigger is evaluated every week rather than latched at listing time.

### ⚠️ Attitude — a toxic player damages the room and the GM cannot currently see it

`seasonManager._applyLockerRoomDrift` runs **every week** and nudges each starter's
confidence and determination toward the team's average attitude, anchored by the coach at 1/3
weight. Its own docstring is explicit:

> *"This is what makes attitude a load-bearing attribute ... a toxic veteran genuinely
> poisons teammates' confidence; a strong leader genuinely lifts them."*

⚠️ **And `frontOfficeBrain` never reads attitude. Not once.** A player is valued on rating ×
position, plus form and fan sentiment. So the sim models a locker-room problem doing real
damage and gives the GM no way to perceive it — which is exactly the owner's question, and
the answer today is no.

The spread is large enough to matter. Rostered attitude runs **35 to 100** (median 72), and
team locker rooms span **20 points**, from Exoticos at 82.8 to Grillmeisters at 62.7. Real
cases exist right now:

| player | club | rating | attitude |
|---|---|---:|---:|
| Chud Bumpington (TE) | Melons | **85** | **45** |
| Prima Cutie (WR) | Waffles | 80 | 45 |
| Rusty Mateo (WR) | Bees | 80 | 46 |
| Orville Duckey (K) | Grillmeisters | 78 | **35** |

A talented player actively dragging a weak room down is a trade waiting to happen, and it is
a **fourth listing trigger** independent of contention: a club wants him gone whether it is
buying or selling.

#### ✅ And it does NOT become a dumping ground, because the damage travels

The naive version — the seller discounts for attitude, the buyer does not — would have GMs
systematically palming headcases off on each other. That is not the right model and it is not
what the sim does: **the damage lands in whichever room he is in.** So both clubs price it,
the seller gains by removal and the buyer loses by addition, and a toxic player is simply
worth less to everybody.

⚠️ **The trade comes from the room, not from blindness.** `_applyLockerRoomDrift` works off
`effectiveAvg = (avgAttitude × 3 + coachAttitude) / 4`, so the marginal damage of adding one
player depends on the room receiving him:

- a **high-attitude room with a leader coach** absorbs one bad apple — the average barely
  moves and the coach anchors it,
- an **already-toxic room** compounds.

So Exoticos (82.8, strong coach) can take on a talented headcase that Grillmeisters (62.7)
cannot, and pay less for him than his rating suggests. **That is "change of scenery" as
arithmetic rather than as flavour**, and it gives a good locker room a genuine, tradeable
asset: the capacity to absorb someone.

#### How it enters

Attitude is **not hidden** — unlike potential, it needs no scouting band. Both clubs see it.
What differs is the marginal effect on each room, which each club computes about **itself**.

Add it as a term on `decisionValue` — the value of a player to *this* club is reduced by the
drift he would cause in *this* room. That single term produces all of it: the seller's urge to
move him, the buyer's discount, and the strong room's ability to pay more than a weak one.

⚠️ It should be a **value term, not a veto** — the same rule as fan sentiment and divisional
reluctance. A club can always decide the talent is worth the trouble, and that decision going
wrong is a story.

### Cadence and rate limits

Runs **weekly**, in the existing per-week hook block, closing at week 22.

| limit | value | why |
|---|---|---|
| listings per club at once | 1 | otherwise every congested club posts three players in week 1 |
| bids per club per week | 1 | stops a contender hoovering the whole block in one pass |
| trades per club per season | 2-3 | GM turnover runs 1-4 exits a season against a stated "not a carousel" bar; hold trading to the same and **measure it** |

⚠️ **The volume caps are the part most likely to be wrong on the first try, and the only way
to know is to run a season and count.** Eight sellers and sixteen buyers is a lot of willing
counterparties; without limits the first week of the season would move a third of the league.

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
