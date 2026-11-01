# Free Agency Market Plan: players choose

> **Status:** Direction from the owner (2026-11-01): replace the FA draft with a signing
> period where **players choose**, each for their own reasons. **Built** on `next-season`
> (`managers/faMarket.py`), live once salaries charge: the re-sign head start, held offers with
> match-or-beat, motives, cut fees on releases and comparable-contract pricing; the frontend
> feed is not built. Numbers below are
> proposals for the synthetic-fan harness to set, not decisions. Needed before salaries
> first charge (the end of the first funded season, `payroll.salariesActive`); the
> facilities and prospect changes do not wait on it.

## 1. Why the FA draft has to go

The worst-first FA draft was built for a league without money: one player per turn, only
into an open slot, the worst team first. With payroll it breaks in three places, measured
on prod-snapshot runs with synthetic fans (2026-11-01, seasons 11-16):

- **Re-signs come before the market.** A team decides whether to keep its walk-year starter
  before it knows who will be available, against a model that assumes the teams ahead will
  take the best free agents. With payroll most of them cannot afford a star, so the star
  survives and the team has already committed to a worse player. On teams with 20,000F+,
  26 of 42 starters had been signed or re-signed that offseason; the Midnights re-signed
  receivers rated 79 and 82, STL a 76 QB and the Sea Otters a 76 TE while 86-88-rated
  players at those positions went unsigned.
- **Money cannot say how much a team wants someone.** The worst team gets first claim on
  every free agent even when it cannot pay him. A rich team with a full roster could only
  reach a free agent through the upgrade cut, which the no-sign-then-cut rule (owner,
  2026-10-03) blocks for everyone it just re-signed: 4-8 upgrade cuts in five offseasons.
- **Nothing moves a price.** A star nobody can afford sits unsigned at his asking salary;
  86-92-rated free agents were still unsigned at season 16, some for a whole season.

## 2. The signing period

Runs where the FA draft runs (after the rookie draft and the supply floor, before the
payment run).

### Nothing is final until the market closes (owner, 2026-11-01)

One-shot rounds would make losing a bid cost a team its whole backup plan: it would shop
again in the next round after the good alternatives had signed elsewhere. So offers are
**held, not signed**, until no team has a move left (deferred acceptance, with bidding):

1. **Lists.** Each team's GM ranks the free agents it wants for each open slot (or each slot
   it would upgrade), with the most it would pay each one (section 4), and offers its top
   choice his asking salary. A team with no open slot at the position may name a starter it
   would release if the offer is accepted: never anyone signed or re-signed this offseason,
   filled earlier in the period, or cut-protected (the existing rules). The release only
   happens if the offer is accepted.
2. **Players hold their best offer.** Each player keeps the offer that scores highest for him
   (salary plus his motive's pull, section 3) and signs nothing yet.
3. **An outbid team can match or beat** (owner, 2026-11-01: "teams that had offers surpass
   theirs should be able to match or beat it"). When a player drops a team for a better
   offer, that team either raises (by at least `FA_MIN_RAISE` of his asking salary, up to
   the most it would pay) or moves on to the next player on its list. Every team in the war
   keeps responding until nobody will go higher. Matching is on the player's SCORE, so his
   drafting team needs a lower salary to match an outsider for a hometown player. An exact
   tie goes to the team his motive favors, then to the worse team (last season's record).
4. **Waiting never costs a backup.** A team that loses its star and moves on can still win
   its second choice even if he is holding someone else's offer, by out-scoring it; that
   team can then respond in turn. Nothing locks until the end.
5. **The market closes** when no team will raise or has anyone left to try. Every held offer
   becomes a signing; conditional releases happen.
6. **Prices fall for the leftovers.** A player still unsigned lowers his asking salary
   (`FA_ASK_DECAY`, never under the minimum) and the market reopens only for teams that
   still want someone at his position, a few times (`FA_MARKET_ROUNDS`). Nothing already
   signed is reopened.
7. **Holes are filled.** A team still short signs the cheapest remaining player at the
   position (the FA draft's last tier now), then the last-resort generation if the pool is
   empty. No roster is left short. In the synthetic-fan runs 25-45 slots opened each
   offseason against a pool of 50-90, and the supply floor covers every position.

Budget: every offer a team is holding out counts against its budget at once, and a raise
must still fit (`payroll.maxAffordable`, upkeep counted).

**Walk-year players enter the market** instead of a re-sign step before it. A team keeps one
by winning him like anyone else: it can respond to outside offers the same way every outbid
team can, with no special right, and a hometown player's discount favors his drafting team.

Prospects: the team's own prospect-versus-free-agent choice (`prospectTakesSlot`) is made
before the market opens for each open slot; a promoted prospect fills the slot and the team
shops elsewhere. Window-length deals for a free agent who beats a prospect stay.

## 3. Why a player signs somewhere: motives

Every player values money. On top of that each player has one **motive**, persisted on the
player (new column `players.fa_motive`), rolled at generation and weighted by personality so
a player's reasons fit who they already are:

| Motive | What he wants | Data it reads | Personalities it leans toward |
|---|---|---|---|
| **Hometown** | The team that drafted him; takes a discount to go back | the drafting team (`rookie_pick` recap rows since season 6; for older players, the team he first played for) | wholesome, knight, stoic, melancholy |
| **Winner** | A team with a history of success | championships and playoff runs over the last `FA_HISTORY_SEASONS`, plus last season's record | fiery, perfectionist, trash talker, dramatic |
| **Comfort** | The best facilities | team Appeal (`computeAppeal`) | vain, cool, prankster, fossil |
| **Opportunity** | Anywhere that wants him | nothing about the team; signs early and for less | chill, goofy, oblivious, cursed |

Rare personalities (alien, ghost, mystic...) roll from the whole table.

An offer's score for a player:

```
score = salary + motivePull(team)
```

with `motivePull` in Floobits, so a motive is literally the discount a player gives:

- **Hometown:** `FA_HOMETOWN_DISCOUNT` (proposal 20%) of his asking salary for his drafting
  team, nothing for anyone else.
- **Winner:** up to `FA_WINNER_PULL` of his asking salary, scaled by the team's recent
  success relative to the league.
- **Comfort:** up to `FA_COMFORT_PULL` of his asking salary, scaled by Appeal relative to
  the league. This replaces the hard Appeal gate (`willSignWith`): facilities still matter,
  most to the players who care about them, and no player refuses a team outright.
- **Opportunity:** no team pull. Instead he accepts the first offer at or above
  `FA_OPPORTUNITY_ASK` (proposal 85%) of his asking salary rather than waiting for better.

- **Opportunity** players also **sign at once**: the first offer clearing
  `FA_OPPORTUNITY_ASK` is final, with no bidding war. They are the dependable backups a
  cautious team can lock in early, and the reason a poorer team can count on someone.
- **Hometown** players wait for their drafting team's offer while one is still possible;
  once that team has filled the position or dropped him from its list, they choose like
  everyone else.

Exact ties go to the team the motive favors, then the worse team (last season's record),
the one place worst-first order survives.

## 4. How a GM makes offers

- **Who:** each team ranks the market with its own board (`frontOfficeBrain`, scouting
  vision, position value, standing) and makes offers where a player beats its current
  starter (or fills a hole) by its bar. The value per Floobit rule (`FO_SALARY_PRICE_WEIGHT`)
  carries over.
- **How much:** the opening offer is the asking salary. The most it would pay (its walk-away
  price in a bidding war) is the asking salary scaled up by how much better the player is
  than its next option (`FA_MAX_BID_EDGE`), capped by what its budget covers for the whole
  term. It knows the player's motive (it is public: "a hometown player", "wants a winner"),
  so it knows how much a pull is worth against it.
- **How many:** at most one held offer per roster slot it is shopping, so a team cannot tie
  up the market.

## 5. What fans see

The live FA draft becomes a **signing period feed**. The market resolves instantly, but the
feed replays it as a few signing days: opening offers ("3 teams are after X"), bidding wars
("the Midnights raise to 2,400F for X; the Waffles match"), players turning teams down,
signings with the reason ("X signs with the Waffles, his hometown team, for 1,200F a
season"; "X takes the Midnights' offer to chase a title"), players lowering their price, and
walks. Each player's motive shows on his profile and in the free agent list, so a fan can
see why he went where he went. Signings land in news and the recap like FA picks do now.

## 6. Parity

Without a worst-first FA draft, a rich team will usually win the stars it wants. The
checks:

- the **rookie draft** stays worst-first with cheap prospect contracts: the poor team's
  route to talent, as the treasury plan always intended;
- the **convex salary curve**: a sixth star costs far more than the first;
- **motives**: a hometown or opportunity player is cheaper for the team he likes or for
  anyone, and comfort and winner pulls favor different teams;
- **falling prices** hand leftovers to poorer teams cheaply;
- ties go to the worse team.

Harness targets: free agents rated 84+ still unsigned after the period (target: about none),
stars per team by Treasury quarter, the win gap by fan quarter (G5), and re-sign volume by
team wealth.

## 7. Open decisions (owner)

1. ~~Matching rights for the old team.~~ Settled 2026-11-01: every outbid team can match or
   beat, the old team included, with no special right.
2. Motive mix and pull sizes (`FA_HOMETOWN_DISCOUNT`, `FA_WINNER_PULL`, `FA_COMFORT_PULL`,
   `FA_OPPORTUNITY_ASK`), the bidding sizes (`FA_MIN_RAISE`, `FA_MAX_BID_EDGE`), rounds and
   price decay: set by the harness. Watch whether rich teams win every war; the walk-away
   price is the lever.
3. Whether a player's motive can change over a career (for example, a veteran turning
   winner late).

## 7b. Comparable contracts (owner, 2026-11-01)

"contracts are based on what a comparable player recently received. this should be an
incentive to not overspend because that will make players more expensive." Every contract
is recorded against the curve price at signing; a player's asking salary is the curve price
times the weighted ratio of recent comparables (same position, rating within 5, last
offseason at half weight), shrunk toward 1.0 by three curve-price contracts and capped at
0.7-1.6 (`payroll.marketRate`). It re-prices between market passes, so a bidding war in the
first pass raises the next pass's asks, and it carries into next offseason's re-sign offers.
Discounts and late signings at a reduced price pull it back down.

## 8. Build order

1. `players.fa_motive` (model, inline migration, load/save), rolled at generation, and a
   one-shot backfill for existing players from their personality.
2. The market engine: lists, held offers, bidding wars, price decay, the fill step; pure
   functions with tests, the same split as `payroll.py`. It must always terminate (every
   raise is at least `FA_MIN_RAISE` and capped by a finite walk-away price).
3. Wire it in place of `freeAgencyPickGenerator` / `conductFreeAgencySimulation`, with the
   walk-year players moved into the market from the re-sign step, behind a switch so the FA
   draft can stay live until it is tuned.
4. Synthetic-fan harness runs; tune.
5. Frontend: the signing period feed, motives on profiles and the free agent list.

## Files this will touch

`managers/playerManager.py` (the FA draft paths), `managers/seasonManager.py` (re-sign step,
offseason flow), `managers/frontOfficeBrain.py` (offers), `managers/payroll.py` (budget),
`database/models.py` and `connection.py` (`fa_motive`), `api/main.py` (offseason feed,
player payloads), and the frontend offseason board and player page.
