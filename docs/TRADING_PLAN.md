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

## 2. Valuation — one scale for three asset classes

### Surplus over replacement × seasons of control

**Value = how much better than freely-available, multiplied by how long you keep it.**

Replacement is not zero: a club can always sign from the FA pool, currently ~**67**. So an 80
is worth 13 surplus, not 80. Time is the other half, and `termRemaining` already carries it —
a walk-year player traded in week 10 is **0.64 seasons** of control against **2.64** for the
same player with three years left. **A 4x spread on identical talent.**

| asset | value |
|---|---|
| **roster player** | `(rating − 67) × seasonsOfControl(termRemaining, week)` |
| **prospect** | projected mature surplus × post-promotion term × **p(promoted before the window closes)**, read through the buyer's own `scoutingVision`. ⚠️ The pipeline window is a deadline, not a term — see §5b |
| **rookie pick** | expected mature surplus at that slot × seasons × risk |


#### ✅ Prospects are priced on their FUTURE, and the two clubs disagree by construction

Yes — both sides value a prospect's projection rather than his current rating, and the
machinery is already there. A prospect debuts `PROSPECT_ENTRY_DISCOUNT` (**11**) below his
true skill, so pricing him at today's number would undervalue every prospect in the league by
about that much.

`trueForwardRating` handles it. For a **developing** player:

```
forward = current + (ceiling − current) × FO_CEILING_CREDIT × devLean
seen    = current + (forward − current) × scoutingVision          # perceivedValue
```

⚠️ **Three multiplicative terms sit on the ceiling gap** — the credit (0.45), the GM's
`playerDevelopment` lean, and scouting vision — so a club prices only the part of the upside
it can *see* and expects to *realise*. A real headline prospect (debuts 83, true skill 94,
potential 99):

| GM | devLean | vision | forward | **seen** | vs his 83 |
|---|---:|---:|---:|---:|---:|
| poor developer, poor scout | 0.00 | 0.00 | 83.0 | **83.0** | +0.0 |
| average / average | 0.50 | 0.50 | 86.6 | **84.8** | +1.8 |
| elite developer, average scout | 1.00 | 0.50 | 90.2 | **86.6** | +3.6 |
| elite / elite | 1.00 | 1.00 | 90.2 | **90.2** | **+7.2** |

✅ **That spread is the trade.** A weak front office sees a prospect as exactly what he is
today; an elite one sees seven points of upside on the same player. Two clubs valuing the same
prospect differently is not noise here — it is a real difference in what each can *do* with
him, and the code comment says so: *"a strong developer rationally values raw talent higher
than a weak one does — sharp scout + good developer takes on the project player."*

⚠️ **The asymmetry is the right way round.** A club with a good Scouting Department and a
developer coach will pay more for prospects and should — it will actually realise more of the
ceiling. A club with neither should be buying proven players instead, and prices accordingly
without being told to.

⚠️ **One consequence for the scouted view**: the GM's `ceiling` here is ground truth, while a
*fan* sees the scouted band. Those must not diverge in the UI — the number a club is shown to
have paid should be explicable from the band the fan can see, or trades will look irrational
from the outside.

#### ⚠️ Treasury is NOT a trade asset (owner, 2026-09-15)

Dropped for now. The measurement is why it is no loss: Treasury spans **200F to 45,427F — a
227x spread** across the league, and at *every* conversion rate swept (50 / 200 / 400 F per
value unit) the richest club could fund the entire market. It would have needed a cap on the
Floobit share of a trade to be safe at all, and a capped sweetener is a lot of machinery for a
small effect.

✅ **Dropping it also removes the only asset class with no natural anchor**, so every remaining
asset — player, prospect, pick — prices on the same surplus-times-time scale with nothing to
convert between. Trades are talent for talent, and future value for present.

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

#### ⚠️ A NEXT-SEASON pick is worth slightly less — but the top 5 are premium regardless

A pick for a future draft carries two layers of uncertainty rather than one: you know neither
your slot **nor the class**. It should therefore be discounted — but **not uniformly**, and
the measurement says why. Variance by slot, over 6,000 simulated classes:

| pick | mean | sd | sd ÷ surplus |
|---:|---:|---:|---:|
| 1 | 98.7 | 4.88 | **0.15** |
| 3 | 92.1 | 3.21 | **0.13** |
| 5 | 88.8 | 2.73 | **0.13** |
| 16 | 78.4 | 2.22 | 0.19 |
| 24 | 71.8 | 2.38 | **0.49** |
| 32 | 57.2 | 5.03 | **50.3** |

**The ratio is the point.** A top-5 pick's class-to-class variation is a small fraction of what
it delivers — the worst class in 6,000 still gave pick 1 an **86**. A late pick's variation is
comparable to its entire value, and by pick 32 the surplus over replacement is ~0 and the
noise swamps it completely.

So **not knowing the class costs a late pick most and a top pick least**, which is the owner's
rule arrived at from the data rather than asserted. Implement as a discount that **scales with
slot** — near-nil in the top 5, steep in the back half — rather than a flat haircut on every
future pick.

⚠️ And the discount is for **time and risk, not expectation**: every class is drawn from the
same distribution, so a future pick's *expected* class is identical to this year's. What is
worse is that it pays later and it pays less predictably.

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

### The four modifiers — all a PRICE, never a VETO

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

#### ✅ Season performance — already wired, already working

Yes: `frontOfficeBrain.performanceAdjustment` prices *production disagreeing with the sheet*,
and unlike attitude it is **fully wired** — `seasonManager._buildPerformanceMap` feeds it in
production and it flows through `perceivedValue` into every front-office decision.

It is a **deadband, not a weight** (`FO_PERF_DEADBAND` 10.0): a 90 playing like an 85 tells
you nothing and returns exactly 0.0, so ordinary variation cannot move a decision. Only the
part past the band counts, at `FO_PERF_WEIGHT` 0.5, capped at `±FO_PERF_MAX_ADJUST` (8.0).
One divergent season is discounted by `FO_PERF_SINGLE_SEASON_TRUST` (0.5) — *one season is an
outlier, two is a pattern* — and seasons that disagree cancel.

⚠️ And it measures against **the rating the player carried THAT season**, from
`player_rating_history`, not today's number. Judging a developed player's rookie production
against his current sheet scores every improver as a chronic underachiever and every declining
veteran as an overachiever.

Measured on prod (208 players with usable history, `FO_PERF_HISTORY_SEASONS` 3):

| | |
|---|---:|
| players the deadband actually moves | **30 of 208 (14%)** |
| adjustment range | −1.7 to **+4.5** |
| players at the ±8 cap | **0** |

**So it is live and it is conservative** — it moves one player in seven, never by more than
about 4 points, and nobody is anywhere near the cap. That is the deadband doing its job:
evidence only, not noise.

⚠️ **It needs nothing for trading.** It already rides in `decisionValue`, so a player having a
genuinely divergent season is already priced differently by every club — which is exactly the
"he's been playing out of his mind this year" trade, for free.

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

**Magnitude: start at 0.20 per attitude point below 80.** Anchored on a decision that should
flip — Chud Bumpington (TE, rating 85, attitude 45) on a Melons roster whose room averages
62.8:

| penalty / pt below 80 | effective | rank on his own roster |
|---:|---:|---:|
| 0 | 85.0 | 2 of 6 |
| 0.10 | 81.5 | 2 of 6 |
| **0.20** | **78.0** | **3 of 6** |
| 0.30 | 74.5 | 4 of 6 |

0.20 is where a 45-attitude 85 first falls below a clean 79 — the point the decision actually
changes. Below it he is untouched; at 0.30 he drops under a 78, which overstates it.

⚠️ **Soft, for the reason the Appeal gate already taught.** Discount toxic players hard enough
and they pool in free agency, never get signed, and the supply floor generates replacements
around them — the exact failure that made `FLOOS_SOFT_APPEAL_PENALTY` a 0.90 multiplier rather
than a veto. `_attemptRosterFill`'s last tier already drops the board rather than leave a slot
empty, so a difficult player is still signed when nothing else is there.

---

## 3. Mechanics — the in-season market

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

✅ **Only the first trigger is contention-gated, so a contender already sells** — for a
locker-room problem or a blocked prospect, whether it is buying or not. Measured: **7
contending clubs hold a sub-55 attitude player right now**, including Pinecones, Dry Heat and
Sand Dollars. No extra rule is needed to let a contender into the selling side.

### 3.2 Choosing who to approach — public information only

Rank counterparties on what is observable: **standings** (contention), **roster**, **contract
state**, and **pipeline depth** (can they backfill, and do they have a prospect blocked?).

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

⚠️ `floor < ask` requires `backfill > REPLACEMENT`, so **the quality of the backfill is what
makes a club a seller.** With mid-season signing (below) the backfill is
`max(readyProspect, bestAvailableFreeAgent)`, so every club can sell — but a club with a good
prospect still sells far more readily than one drawing on the pool.

**Each approached club bids** its private de-cursed value. ⚠️ `_deWinnersCurse` is not
optional: a buyer choosing the best-looking of several listings preferentially finds the one it
overrates, the exact bias that function exists for. A bid is a **bundle** — picks, prospects,
or a player — the cheapest combination clearing the reserve, capped at
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

### 3.6 Mid-season free-agent signing (owner, 2026-09-15)

A club may **sign a free agent to fill an empty slot mid-season**, so a trade no longer
requires a prospect to be legal. This is the piece that makes player-for-picks available to
everybody rather than only to clubs with a pipeline.

**Scope: filling a hole, not upgrading.** A signing is available when a roster slot is
**empty** — after a trade, and nowhere else. Letting clubs sign over a filled slot would be a
different feature entirely (a second, continuous free-agency market) and would undo the
position-lock logic the rest of this plan rests on.

#### What it changes in the valuation

The backfill in the floor becomes `max(readyProspect, bestAvailableFreeAgent)`, and the pool
is **thin and uneven**, so what a trade costs a club now depends sharply on position:

| position | best available | rating shed for the rest of the season, trading an 80 |
|---|---:|---:|
| QB | 68 | **−12** |
| RB | 68 | −12 |
| WR | 70 | −10 |
| TE | 74 | −6 |
| K | 77 | **−3** |

✅ **That is a good property, not a problem.** A kicker is nearly free to trade because the
pool replaces him; a quarterback is expensive because it cannot. The market will move kickers
and hoard quarterbacks without a rule saying so.

#### ⚠️ It softens the draft dependency from THREE reasons to ONE

This is an honest downgrade of an argument made three times above:

| reason the draft had to land first | still true? |
|---|---|
| the blocked-prospect trigger cannot fire with an empty pipeline | ✅ yes |
| a seller needs a prospect or the trade is illegal | ❌ **no — a signing fills the hole** |
| `floor < ask` requires `backfill > REPLACEMENT` | ⚠️ **weakened** — the pool clears that bar at TE and K but barely at QB |

So the draft is no longer a hard prerequisite for trading. It remains the thing that makes
clubs *willing* sellers rather than reluctant ones, and it is still item 0 — but trading could
now ship without it if that ordering ever becomes inconvenient.

#### ⚠️ The pool is sized for ONE annual draw, not continuous withdrawal

26 free agents across five positions, and **TE has three**. Two mid-season signings would
leave a single tight end for an offseason FA draft that 32 clubs pick through.

The fix is already built: **`ensurePositionSupply` is the per-position backstop** and it
generates only the deficit, producing nothing while a position is above target. Run it on the
same weekly cadence as the trade pass rather than only in the offseason, and the pool refills
exactly as much as it is drained.

⚠️ **Do not instead cap mid-season signings.** A cap would leave a club unable to fill a hole
it created legally, and an empty slot rates **50** — the failure this whole section exists to
prevent.

⚠️ And a mid-season signee needs a **contract term**. `_getPlayerTerm` is the existing rule;
whether a week-15 signing should get a full-length deal or a prorated one is an open question —
a full deal makes a desperate club's hole-filling a cheap way to acquire term.

### 3.7 The roster window, cutting, and the cut fee (owner, 2026-09-15)

**Cut, sign and trade are all live until week 22. After that rosters FREEZE until the
offseason.** One window, one deadline, three verbs — a club can reshape its roster right up to
the final game day and then must play what it has through the run-in and the playoffs.

✅ That the deadline is `GM_ACTIVE_WEEK` is convenient rather than coincidental: the Front
Office block already opens there, so the freeze and the offseason machinery share a boundary.

#### A mid-season signing runs to the end of THIS season, or one more

Not a full `_getPlayerTerm` deal. Two options, and the GM picks: **remainder of this season**,
or **remainder plus one**. ⚠️ Anything longer makes hole-filling a cheap way to acquire term —
a club could trade a player away in week 15 and sign a three-year replacement, converting a
roster hole into an asset.

⚠️ **And the thin pool is the real deterrent, by design.** Best available today is 68 at QB
and 70 at WR against a league median of 79. Signing is the path a club takes when it has no
prospect and no better option — not a strategy.

#### Cutting to make room for an incoming player

A club may **cut a player to open a slot for one arriving in a trade.** Without it, a club
whose every slot is filled cannot buy at all, which would shut the contenders — the entire
demand side — out of the market.

#### ⚠️ Cutting a player with term left costs Treasury

This is where Treasury earns a place in trading after all, and it is the **safe** use: a
**cost**, not a purchase.

```
cutFee = remainingSeasons × (rating − REPLACEMENT) × CUT_FEE_RATE   Floobits
```

At a rate of **50 F per surplus-season**:

| what is being cut | fee | clubs that could pay |
|---|---:|---:|
| a filler, 1 year left | 250F | 25 / 32 |
| a good starter, 2 years left | 1,700F | 16 / 32 |
| an elite player, 3 years left | **4,350F** | 15 / 32 |

The median club (1,896F) can afford roughly **one** cut of a good starter per season.

✅ **As a cost rather than a purchase, the wealth spread finally works the right way round.**
Treasury was rejected as a trade *asset* because a 227x spread let the richest club buy the
market. As a *fee* the same spread constrains the poor instead of empowering the rich — a club
cannot buy a player with Treasury, only **roster space**, and the club that hoards talent pays
to keep churning it.

⚠️ It also reconnects the two economies deliberately: Treasury's other claim is facility
upkeep, and `resolveSeasonEnd` spends it at season end. **A club that cuts freely in-season
loses a facility level in the offseason** — the trade-off is real and needs no extra rule.

⚠️ And it wants a **floor of zero, not a debt**: a club that cannot pay simply cannot cut.
Letting the fee go negative would hand a broke club unlimited roster churn, which is the
opposite of the intent.

### 3.8 Settlement, in order

1. verify both rosters **can** be complete — a prospect to promote, a signable free agent at
   that position, or player-for-player
2. move the assets; stamp `previousTeam`
3. **backfill** — promote the prospect if one is ready, else sign the best available free
   agent. `_promoteProspectsAutonomously` already does the promotion half,
   ⚠️ but its bar compares against a free agent the club could sign, and mid-season there is
   **no signing path at all**. The real alternative is an empty slot rating **50**, so the bar
   must drop to near zero in-season
4. clear the traded player's fan sentiment rows
5. mint his new card at the new club; leave existing cards alone
6. publish to `league_news`; write the `SeasonRecapEvent` with a **trade id**

### 3.9 Cadence and rate limits

Runs **weekly** in the existing per-week hook block, closing at **week 22** — the first week of
the final game day, already `GM_ACTIVE_WEEK`.

| limit | value | why |
|---|---|---|
| listings per club at once | 1 | else every congested club posts three players in week 1 |
| bids per club per week | 1 | stops a contender hoovering the block in one pass |
| trades per club per season | 2-3 | GM turnover runs 1-4 exits a season against a "not a carousel" bar |

⚠️ **But the market is SUPPLY-constrained, so the caps are a safety rail rather than a balance
lever.** Counted on the live league, the four triggers produce roughly:

| trigger | listings today |
|---|---:|
| expiring surplus | **14** across 8 non-contending clubs |
| locker room (attitude < 55) | **18** across 15 clubs |
| blocked prospect | 0 (empty pipeline) → ~1 per club once the draft lands |
| horizon mismatch | not countable from a snapshot |

16 buyers chase ~32 listings and **each listing sells once**. The ceiling is departing
players, not appetite.

**So ship with the weekly limits and NO per-season cap**, then count. A per-season cap
constrains something that is not currently the binding constraint, and guessing its value
before a season has run is how it ends up wrong.

---

## 4. The offseason trade window

### The offseason is ~2 days of real time, and it already has the right shape

Measured against the live schedule (playoffs Friday, next season anchored Sunday 19:00 ET):

| moment | when | state after it |
|---|---|---|
| Floos Bowl ends | **Fri ~16:00 ET** | season over |
| `post_bowl` wait (1h) → **front office resolves** | **Fri ~17:00 ET** | contracts decremented, retirements done, re-signs and cuts settled, FA pool filled |
| ⟶ *gap of ~19 hours* | | |
| `_runPreDraftPass` → **rookie draft** | **Sat noon ET** | this year's picks are spent |
| **FA draft** | Sat, next top of the hour | rosters full |
| **new season** | **Sun 19:00 ET** | frozen until week 22 |

✅ **The gap between the front office and the draft is the window**, and it is ~19 hours of
wall clock. By then every club knows three things it does not know at any other moment: **who
it kept, what the pool holds, and where it picks.**

### Two passes, not one

| pass | when | what it is for |
|---|---|---|
| **A — pre-rookie-draft** | after the front office, before `_runPreDraftPass` | the main window. Roster settled, pick known, needs visible. **This is where pick trading lives** |
| **B — pre-FA-draft** | after the rookie draft, before free agency | smaller. A club that just drafted a QB may now have a surplus one, and the pool it is about to fish is known |

⚠️ **Pass A is where picks are tradeable and pass B is not** — this year's picks are spent the
moment the draft runs, so only *future* picks remain. That asymmetry is worth honouring rather
than smoothing: the pre-draft window is the valuable one precisely because the picks are live
in it.

### ⚠️ The offseason changes the valuation, in the club's favour

Two of the in-season terms behave differently and both should be read deliberately:

- **`seasonsOfControl` jumps.** In-season a walk-year player is a fraction of a season; in the
  offseason the walk-years are already gone (the front office resolved them) and everyone
  remaining has **whole seasons** of term. So offseason trades are about *assets*, not
  rentals — the rental market does not exist here at all.
- **`nowWeight` resets.** Contention is unknown for a season that has not been played, so
  every club is back at ~1.00 — the same state that makes the in-season market quiet in week
  1. ⚠️ **That removes the buyer/seller asymmetry entirely**, so the offseason market cannot
  run on contention. It runs on the other three triggers: **blocked prospect** (loudest here,
  right after promotions), **locker room**, and **horizon mismatch** — which in the offseason
  is a club with a 2-year veteran wanting a 5-year one, or the reverse.

✅ That is a genuinely different market rather than the same one at a different date, which is
the argument for having both.

### ⚠️ A prospect's "seasons of control" is a DEADLINE, not a term

`seasonsOfControl` as written measures *seasons of contribution* off `termRemaining`. **A
prospect has neither.** He contributes nothing while in the pipeline, and
`PROSPECT_DEVELOPMENT_WINDOW` (3) is the number of offseasons his club has to **promote him or
lose him** — `_advanceProspectWindow` releases him to free agency for nothing once
`prospect_seasons >= 3`.

So a prospect's value has two parts, and only the second is a term:

| | |
|---|---|
| **window remaining** | offseasons left to find him a slot. A **risk**, not a contribution |
| **contract term** | seasons of actual output — and it only starts once he is promoted |

Modelled with a ~0.45 chance a slot opens at his position in a given offseason:

| `prospect_seasons` | window left | p(promoted) | value | |
|---:|---:|---:|---:|---|
| 0 | 3 | 0.83 | **52.5** | fresh, full runway |
| 1 | 2 | 0.70 | 43.9 | mid-window |
| 2 | 1 | 0.45 | **28.3** | ⚠️ **distressed** |

⚠️ **A prospect at 2/3 is a distressed asset.** His holder must find him a slot this offseason
or lose him for nothing — which is the walk-year squeeze again, one level down, and it is
another trigger with urgency built into it rather than bolted on.

✅ **And the deadline TRAVELS.** `prospect_seasons` moves with the player, so a buyer inherits
the same clock. That makes a distressed prospect worth buying **only if you have the slot the
seller does not** — which is exactly the trade that should happen, and it cannot be gamed by
passing him around, because each pass burns the same window.

⚠️ Two implementation notes: the prospect's **post-promotion term is not yet known** (it comes
from `_getPlayerTerm` at promotion), so the value model must assume a tier-typical term rather
than read one; and `PROSPECT_SLOT_CAP_PER_POSITION` (2) means a buyer can be **blocked from
taking him at all**, which is a legality check, not a pricing one.

### ⚠️ The last window needs a last chance — and today it does not get one

`_runPreDraftPass` (promotions) runs at `seasonManager:6839` and `_advanceProspectWindow`
(the expiry) at `:6994`, so a club **does** get a promotion attempt every offseason, including
the final one. But that attempt is narrower than it looks, and on the last window both
constraints are wrong:

```python
slot = self.playerManager._findOpenSlotForPosition(team, prospect.position.value)
if not slot:
    continue        # no hole at his position — nothing to win
...
if value < replacement * FO_PROSPECT_PROMOTE_EDGE:
    continue        # free agency offers better — leave him down
```

1. ⚠️ **No open slot means no promotion, at any quality.** A club whose QB slot happens to be
   filled loses a 99-potential quarterback for nothing.
2. ⚠️ **The bar compares him against a free agent** (`FO_PROSPECT_PROMOTE_EDGE` 0.88 of
   `bestReplacementValue`). On the final window that is the **wrong alternative**: the club is
   not choosing between the prospect and a free agent, it is choosing between the prospect and
   **nothing**, because he walks either way.

**This is the third instance of the same structural error in this plan** — the reserve floor,
the mid-season promotion bar, and now this: *the alternative changed and the comparison did
not.* It is worth naming as a pattern, because it will recur wherever a decision written for
one context gets reused in another.

⚠️ **And the consequence lands squarely on the feature's own story.** A bottom-feeder drafts
the headline prospect, develops him for three seasons, and loses him for free because their
slot at his position happened to be occupied. That is the exact outcome the draft exists to
create and this would quietly undo it.

#### ⚠️ And the release currently lands AFTER the draft he should be in

Owner: at the end of his last window the club either signs him, **or he becomes available in
the upcoming FA draft.** Today he does neither in time.

| step | line | |
|---|---:|---|
| supply floor tops up the pool | — | excludes prospects, so it generates a replacement |
| `_processFreeAgency()` — **the FA draft** | `:6941` | |
| `_advanceProspectWindow()` — **release** | `:6994` | ⚠️ **53 lines too late** |

So a prospect washing out in offseason N is released into the pool **after** offseason N's
draft has already run, and is not signable until offseason **N+1**. He sits idle for an entire
extra season.

⚠️ **And it costs twice.** `ensurePositionSupply` runs before the FA draft and **excludes
prospects by design**, so it generates a fresh free agent for a hole the washing-out prospect
could have filled — the league gains a body it did not need *and* the prospect goes unused.

**Fix: move `_advanceProspectWindow` to just after the promotions pass**, before the rookie
draft and the supply floor:

```
front office → promotions (last chance) → advanceProspectWindow (release) →
rookie draft → supply floor → FA draft
```

✅ Two things fall out for free. The released prospect is in the pool **for the draft that is
about to happen**, which is what the owner asked for. And the supply floor now **counts him**,
so it stops generating a replacement he can be — which is the same over-generation documented
in `ensurePositionSupply`'s own comment (*"the extra FAs just sit in the pool"*).

⚠️ Moving it earlier also fixes the increment: run before the rookie draft, this season's
new draftees are not yet in `team.prospects`, so they correctly start at `prospect_seasons = 0`
rather than being incremented in the offseason they arrived.

#### The last chance, in order of preference

On his final offseason, at the promotions pass, the club should get to act rather than watch:

1. **Promote into an open slot regardless of the bar** — better than nothing beats better than
   a free agent, and the free agent is not the alternative any more.
2. **Cut a worse rostered player to make room**, paying the cut fee. ✅ This is where the cut
   fee earns its second job: a club facing the loss of a good prospect has a real, priced
   decision — pay to keep him, or let him walk. Nothing extra needs designing; both halves
   already exist.
3. **Trade him** — already covered, and this is exactly the distressed asset above. A club
   without a slot sells to one that has it, which is the trade that *should* happen.

⚠️ Option 2 must compare the **prospect's projected value against the incumbent's**, not
against a free agent, and must respect the cut fee's zero-floor: a club that cannot afford the
fee cannot take that route and falls back to 1 or 3.

### What to reuse

`_runPreDraftPass` already walks teams **worst→best** before the draft, broadcasting
`offseason_team_setup` per club, and already runs prospect promotions there *"so the prospect
slot opens up before the rookie draft fills it."* A trade pass immediately before it inherits
the ordering, the broadcast rhythm and the UI's existing on-the-clock highlight.

### Deliberately NOT doing: live draft-day trades

Trading *between picks* — the trade-up-to-take-him story — is the most dramatic version and
the most complex: it interleaves trade evaluation with pick selection and every trade
re-orders the board mid-draft. **Two discrete passes first**, and revisit once the market has
run a season and the volume is known.

## 5. Legality

| rule | why |
|---|---|
| both rosters complete at settlement | an empty slot rates **50**; never rely on the engine tolerating `None` |
| position-for-position, or player-for-assets **with a backfill** (prospect or free agent) | six locked slots, no bench |
| closes at week 22 | owner; coincides with `GM_ACTIVE_WEEK` |
| a club may not trade a player it acquired this season | stops pass-the-parcel |
| volume capped per club per season | see above — and **measure it** |

## 6. Visibility

- **League news** on every trade via `league_news.publish()`. ⚠️ keyword-only and camelCase; a
  snake_case typo has caused two incidents, one a production outage. `test_publish_kwargs.py`
  sweeps call sites statically.
### The transactions page

New, and **not a trade log** — it is the league's front-office desk, useful year-round. Seven
sections (owner):

| section | source | notes |
|---|---|---|
| **upcoming draft order** | `freeAgencyOrder` / standings, **live** | ⚠️ must re-render when a pick is traded — the order is *who picks*, not *whose pick it is* |
| **upcoming draft class** | the class generated at season start | shown through the **viewing club's own scouted band**, so two fans see different ranges |
| **potential free agents** | walk-year players (`termRemaining <= 1`) | ⚠️ flag who the club **cannot keep** — 18 of 32 are over the re-sign limit, and that is the story |
| **players on the block** | live listings | the analyst layer: who is available, and what it would take |
| **trades** | `SeasonRecapEvent` | as they happen |
| **signings and cuts** | `SeasonRecapEvent` (`fa_pick`, `cut`, `resign`, `walked`) | already written every offseason |
| **prospect promotions** | `SeasonRecapEvent` (`promotion`) | already written |

✅ **Five of the seven already have their data.** `SeasonRecapEvent` holds
`rookie_pick | fa_pick | cut | resign | walked | promotion | retirement | hof_induction |
coach_fire | coach_hire`, and prod has 5 seasons of it. The draft order and the walk-year list
are both derivable today. Only **trades** and **the block** are new.

⚠️ `SeasonRecapEvent`'s idempotency key is `(season, event_type, player_id|team_id)` — one
player, one club — which a two-sided trade does not fit. It needs a **trade id**, or the
resume dedupe silently drops half a swap.

⚠️ **The block and the draft class are the sections with editorial weight**, and the ones that
make the page worth visiting outside the trade window. A walk-year list that says *"these 33
players are leaving for nothing unless someone moves"* is a story every week of the season.

## 7. Settled

| | |
|---|---|
| **contention exponent** | **1.25** — 2.0 has the best club paying a top-two pick for a six-week rental; linear compresses the market into 6 slots |
| **Treasury** | **not a trade asset** — a 227x wealth spread made it unsafe without a cap, and dropping it removes the only asset with no natural anchor |
| **rookie picks** | tradeable, **two seasons** out, with a **slot-scaled** discount on future picks (near-nil in the top 5, steep in the back half) |
| **reserve floor** | `(player − backfill) × seasonsLeft × nowWeight` — set by the backfill, not a constant |
| **fan sentiment** | raises **the surplus the trade must clear**, not the seller's valuation — the obvious wiring measurably does nothing |
| **divisional premium** | derived from the schedule (**4x** the games), scaled by the rival's threat |
| **season performance** | already wired and live — a deadband moving 14% of players, max +4.5, none at the cap. Needs nothing |
| **attitude** | enters `decisionValue`, so it reaches **cuts and re-signs** as well as trades |
| **does a contender sell** | **yes, already** — the locker-room and blocked-prospect triggers are not contention-gated |
| **season stats on a trade** | **stay with the player** — already the behaviour |
| **fan sentiment on a trade** | **does not follow** — clear the rows, since the own-club gate is on *writing* only |
| **cards** | a **new card minted** at the new club; existing cards untouched. ⚠️ Templates mint once per season and return early, so this needs its own path |
| **competitive-balance tax** | **not built** — measured at ~one season of earlier correction on one club |
| **transactions page** | the full front-office desk, seven sections; five already have their data |
| **prospect control** | a **deadline, not a term** — `PROSPECT_DEVELOPMENT_WINDOW` is time to find him a slot, and one at 2/3 is a distressed asset whose clock **travels with him** |
| **a prospect's last window** | the club acts rather than watches: promote regardless of the bar, **cut to make room** (paying the cut fee), or trade him |
| **washout release** | ⚠️ **move `_advanceProspectWindow` before the FA draft** — today it runs 53 lines after it, so a washout waits a whole extra season and the supply floor generates a replacement he could have been |
| **elite contract lengths** | ⚠️ **orphaned bug** — restore S 4-6 / A 3-4; the re-sign-once limit they were shortened for is disabled |
| **mid-season FA signing** | allowed, **to fill an empty slot only**, for this season or one more — with `ensurePositionSupply` running weekly so the pool is not drained |
| **roster window** | cut / sign / trade all live to **week 22**, then **frozen** until the offseason |
| **offseason window** | **two passes — pre-rookie-draft (the main one; picks are live) and pre-FA-draft**. Runs on the blocked-prospect / locker-room / horizon triggers, since `nowWeight` resets and there is no contention asymmetry |
| **cutting** | allowed, including to make room for an incoming trade — but **cutting a player with term left costs Treasury** (`remainingSeasons × surplus × rate`), which is the safe use of a currency with a 227x spread: a cost constrains the poor rather than empowering the rich |

## 8. ⚠️ A live bug found on the way: elite contracts are orphaned

Reported by the owner: *"teams don't seem to be signing elite players to long contracts
anymore — the Pops signed 5-star Frig Lagotis to only 2 seasons."* Confirmed, and the cause is
a rule that outlived its reason.

**Measured on prod: no player in the league has a contract longer than 3 seasons.**

| tier | n | mean term | max | distribution |
|---|---:|---:|---:|---|
| **S** (92+) | 10 | **2.7** | **3** | 2:3, 3:7 |
| A (84+) | 56 | 2.6 | 3 | 2:25, 3:31 |
| B | 75 | 2.1 | 3 | 1:17, 2:30, 3:28 |

Frig Lagotis, rating **96**, term **2**. Jomes Roberston, **97**, term 3.

`playerManager._getPlayerTerm` says why, in its own comment:

> *"Star (S/A) deals are SHORT (2-3, **was 4-6 / 3-4**) so a player cycles through their ~2
> contracts (**re-sign-once retention limit**) in ~4-5 years rather than a decade."*

⚠️ **`RESIGN_ONCE_ENABLED` is `False`** — disabled 2026-08-13, because at a limit of 1 a
career-long one-club player was impossible. **The mechanism these short deals exist to feed
was switched off a month ago and the deals were never revisited.** Same class as
`ROOKIE_DRAFT_ENABLED` and the snapshot prune: a rule surviving the system it served.

### It is not trade-neutral, and the effect runs the right way

| | walk-years per season |
|---|---:|
| today (S/A mean 2.6) | **99 of 192 (52%)** |
| with S 4-6 / A 3-4 restored | **91 of 192 (47%)** |

The market loses ~9 walk-years a season and the seller side survives comfortably, because
**most congestion is B/C tier and is untouched.**

✅ And it makes elite players dramatically better trade assets, since value scales with
seasons of control: a 96 is worth **29** units with one season left, **58** with two, and
**116** with four. Under the current rule the league's best players are permanently near their
walk year and therefore permanently cheap — which is the opposite of what a star should be.

⚠️ **Fix it independently of trading**, like the attitude term. It changes how the current
league re-signs the moment it ships.

## 9. What to build, in order

⚠️ **The prospect draft was a hard prerequisite and mid-season signing softened it to one
reason.** It stays item 0 because it is what makes clubs *willing* sellers, but trading could
ship without it:

1. the **blocked-prospect trigger** cannot fire with an empty pipeline — ✅ still binding,
2. ~~a seller needs a backfill or the trade is illegal~~ — a signing fills the hole,
3. ~~`floor < ask` requires a pipeline~~ — the pool clears that bar at TE and K, barely at QB.

| # | item | state |
|---:|---|---|
| **0a** | **Restore elite contract lengths** — S 4-6, A 3-4. One constant block; see 6b |
| **0b** | **Prospect draft** — see `docs/PROSPECT_DRAFT_PLAN.md` | mostly exists; class generation, the draft loop, the cull and the scouted view are new |
| **0c** | **Move `_advanceProspectWindow` before the FA draft**, and give the final window a real last chance | ⚠️ an ordering move plus a changed bar; both are bugs in their own right and neither needs trading |
| **1** | **Attitude term in `decisionValue`** | ⚠️ **independent of trading, and a live front-office change.** Ship and measure it on its own — cuts, re-signs, FA pool depth — before trading rides in on it |
| **2** | **Point sentiment at the surplus bar** | small; the term exists and is live, it is aimed at the wrong quantity |
| **3** | **Listing model** — triggers, reserve, floor, persistence, withdrawal | new |
| **4** | **Auction** — approach, de-cursed bids, bundles, settle | new; reuses `decisionValue` and `_deWinnersCurse` wholesale |
| **5** | **Settlement** — asset move, backfill promotion, sentiment clear, card mint, news, `SeasonRecapEvent` with a trade id | ⚠️ the promotion bar must drop to near zero in-season |
| **6** | **Transactions page** | five of seven sections already have their data |

### ⚠️ One error recurs three times — watch for a fourth

The reserve floor, the mid-season promotion bar and the final-window promotion bar are all the
same mistake: **a decision written for one context, reused in another where the alternative
changed and the comparison did not.**

| decision | compares against | but the real alternative is |
|---|---|---|
| reserve floor | a generic replacement | **who actually backfills him** |
| mid-season promotion | a free agent the club could sign | an **empty slot rating 50** — there is no signing path |
| final-window promotion | a free agent (`FO_PROSPECT_PROMOTE_EDGE`) | **nothing** — he walks either way |

Whenever a front-office rule is reused in a new window, ask what the club is actually choosing
between there.

### Measure before tuning

Three numbers are guesses until a season has run, and all three are cheap to read off one:

- **trade volume** — ~32 listings against 16 buyers today, but the horizon trigger is not
  countable from a snapshot,
- **the attitude term** at 0.20 — watch cuts, re-signs, and whether the FA pool fills with
  the unsignable,
- **where trades cluster** — the contention ramp should push them past week 12, and if they
  fire in week 3 the ramp is too fast.
