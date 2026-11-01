# Free Agency Market Plan: players choose

> **Status:** Direction from the owner (2026-11-01): replace the FA draft with a signing
> period where **players choose**, each for their own reasons. Not built. Numbers below are
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
payment run), in rounds:

1. **Offers.** Each team's GM offers contracts to the free agents it wants: a salary at or
   above the player's current asking salary, and a term. A team can only offer what its
   budget covers with facility upkeep counted (`payroll.maxAffordable`, unchanged), and its
   offers in a round must fit together. A team with no open slot at the position may name a
   starter it would release if the offer is accepted; never anyone signed or re-signed this
   offseason, filled earlier in the period, or cut-protected (the existing rules).
2. **Players choose.** Every free agent with offers scores each one (section 3) and either
   accepts the best or waits for a better one, depending on his motive and the round.
3. **Prices fall.** A player with no offer in a round lowers his asking salary
   (`FA_ASK_DECAY` a round, never under the minimum), so a star nobody can afford ends up
   with a team that can.
4. **Holes are filled.** After the last round (`FA_MARKET_ROUNDS`), a team with an empty
   slot signs the cheapest remaining player at the position, as the FA draft's last tier
   does now, then the last-resort generation if the pool is empty. No roster is left short.

**Walk-year players enter the market** instead of a re-sign step before it: a team keeps a
player by out-offering everyone else, and a loyal player gives the team that drafted him a
discount (section 3). Whether the old team also gets to **match** the best outside offer is
an open decision (section 7).

Prospects: the team's own prospect-versus-free-agent choice (`prospectTakesSlot`) is made
before the period opens for each open slot; a promoted prospect fills the slot and the team
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

Other motives wait: a player with offers accepts the best only if it clears his asking
salary or the period is in its last rounds; otherwise he holds a round to see if a better
one comes. A player who holds and gets nothing better takes his best standing offer.

Ties go to the worse team (last season's record), which is the one place worst-first order
survives.

## 4. How a GM makes offers

- **Who:** each team ranks the market with its own board (`frontOfficeBrain`, scouting
  vision, position value, standing) and makes offers where a player beats its current
  starter (or fills a hole) by its bar. The value per Floobit rule (`FO_SALARY_PRICE_WEIGHT`)
  carries over.
- **How much:** at least the asking salary. A GM offers more for a player it values well
  above the alternatives, up to what that edge is worth to it and what it can afford, and
  knows the player's motive (it is public: "a hometown player", "wants a winner").
- **How many:** at most one open offer per roster slot it is shopping, so a team cannot tie
  up the market.

## 5. What fans see

The live FA draft becomes a **signing period feed**: offers ("3 teams are after X"),
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

1. **Matching rights:** does a player's old team get to match the best outside offer on its
   walk-year players? Recommendation: no; the hometown discount already favors his drafting
   team, and matching would let rich teams keep everyone.
2. Motive mix and pull sizes (`FA_HOMETOWN_DISCOUNT`, `FA_WINNER_PULL`, `FA_COMFORT_PULL`,
   `FA_OPPORTUNITY_ASK`), rounds and price decay: set by the harness.
3. Whether a player's motive can change over a career (for example, a veteran turning
   winner late).

## 8. Build order

1. `players.fa_motive` (model, inline migration, load/save), rolled at generation, and a
   one-shot backfill for existing players from their personality.
2. The market engine: offers, choices, price decay, the fill step; pure functions with
   tests, the same split as `payroll.py`.
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
