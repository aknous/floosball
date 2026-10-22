# Treasury, Payroll and Gate Revenue Plan

> **Status:** Direction agreed with the owner (2026-10-21), not built. Numbers below are proposals to be set by the harness in Phase 0, not decisions. Builds on `docs/MARKETS_FACILITIES_PLAN.md` (the treasury and facilities it describes are live) and the fan-income work (Supporter / Spectator, live).

## 1. The problem

Fans of well-funded teams feel the treasury is pointless. The complaint comes from both sides:

- **Funded teams that lose** see no return on what they put in.
- **Funded teams that win** still say "all that money and for what": the money has nothing visible to buy.

Measured on the season-7 snapshot (`data/floosball.db`, an older prod copy; prod is now on season 11, re-measure before tuning):

- **Rich treasuries sit idle.** Balances run 52,107 (NYS), 51,621 (STL), 46,274 (CHI), 38,325 (LAE) down to under 100 for about ten teams. Maxing all five facilities from zero costs ~43k at the current share unit (~5,300F). NYS could have maxed everything and still holds 52k; its levels are 4/2/5/2/0.
- **Facilities are throttled by the pipeline, not money.** A project only opens through the season-end fan vote, one per team per season, so a team gains at most one level a season. League-wide ~13 builds a season. After seven seasons nobody holds more than one or two level-5 facilities.
- **Facilities are already strong.** A full level-5 set measures ~+6.4 wins a season (CLAUDE.md, Facilities Economy). The live league cannot show it because nobody is near a full set.
- **Money does not reach the roster at all.** Players sign by worst-first draft order, re-signs by GM value, and the Appeal gate (`frontOfficeBrain.appealDemand`) keys on age only, deliberately: its docstring says rating was left out so "the best players [don't] pool at the best-funded clubs and the league [doesn't] stratify by treasury". **This plan reverses that decision on purpose**; update that docstring when payroll lands.

## 2. Design goals

Each is a test the Phase 0 harness must be able to run.

| # | Goal | Proposed measure |
|---|---|---|
| G1 | **Money is an advantage that keeps growing, more slowly at the top.** No on/off line where "funded" teams are all equal. | Wins rise monotonically with funding; the marginal win per 1,000F falls. |
| G2 | **A new fan can lift a fanless team, over several seasons.** The first Floobits do the most. | A fanless team given one engaged fan's income visibly improves (rating and wins) each of its first 3-4 seasons. |
| G3 | **Fantasy is not required.** | G2 holds for a fan earning only non-fantasy income (~5k a season, see §7). A fantasy player's extra income helps their team at most about as much as a second fan joining. |
| G4 | **Fanless teams stay competitive.** The league baseline covers a roster of about today's league average. | Fanless playoff rate not far below its share today (owner to set). |
| G5 | **The effect is bounded.** | Top-quarter-funded teams finish N wins ahead of the bottom quarter, facilities included. **Owner sets N** (proposal: 4-6 of 28). |
| G6 | **No roster slot is ever empty.** | Every team can always afford a minimum-salary player. |

## 3. Phase 1: let the treasury buy facilities as fast as it can pay

Independent of everything else, and the cheapest way to make money turn into wins.

- **Each facility can be upgraded once a season** (owner, 2026-10-22), but different facilities can all upgrade in the same season. A team can gain up to five levels in one season (one per facility) instead of one level total, and a windfall still takes five seasons to max a facility.
- **Fans rank the facilities instead of casting one vote** (owner, 2026-10-22). Today each fan gets one vote per team per season (`FacilityVote`, unique on team + user + season) and the plurality winner opens one project, so a team with one fan only ever has one choice, and re-voting cannot help because money is spent once a season, in one payment run.
  - Each fan orders all five facilities by priority. The ballot **persists across seasons** until the fan changes it, so it takes one visit to keep it current and occasional fans are not left out.
  - The team's combined ranking is a points count: a fan's first choice gets 5 points, second 4, down to 1 for fifth. Ties break toward the facility the team is weakest in. A team with one fan follows that fan's list.
  - With no ballots, the fallback order is weakest facility first.
  - The season-start payment run (§5) walks the combined ranking after payroll and upkeep: fund the top facility's project, and if money is left, open and fund the next one, skipping any facility already upgraded this season or at level 5, until the money runs out or every facility has had its upgrade.
  - Migration: an existing single vote becomes that fan's first choice, with the rest of their list filled in by the fallback order.
  - Replaces `castFacilityVote` / `tallyFacilityVotes` / `resolveFacilityVote` and the frontend vote control with a ranking control.
- **Visibility:** the team page shows what each facility is doing right now, e.g. "roster 2% fatigued, league average 9%" (Recovery), the home-game edge (Stadium), the in-game edge (Locker Room).
- Upkeep (a full level-5 set holds at ~11k a season) becomes the ongoing cost that only well-funded teams sustain. That is G1 for facilities with no new mechanic.

## 4. Phase 2: gate revenue

A second treasury income stream that comes from fans **showing up**, not from fans' wallets.

- **Gate revenue is the main income stream; donations are the top-up** (owner, 2026-10-22). Size it so a few active fans who never play fantasy can afford a competitive roster on gate revenue alone. A fantasy player's bigger donations then speed a team up but are never what makes it competitive (G3).
- Each week, each **active** fan of a team (the Supporter activity window, `SUPPORTER_ACTIVITY_WINDOW_DAYS` 14) earns the team a gate-and-merch payment, paid by the league into the treasury. No user Floobits are spent. "Active" should be easy to reach: any visit counts, not only fantasy.

### Participation boost (owner, 2026-10-22)
A fan who takes part in the site's games that week is worth more at the gate than one who only visits. No single game is required, and nobody has to do everything.

- **Qualifying activities, each worth the same:**
  - **Pick-em:** made picks this week. **Auto-picks don't count** (owner, 2026-10-22).
  - **Fantasy:** fielded a lineup this week (a banked `WeeklyCardBonus` row for the week).
  - **Showcase:** has cards in the Showcase.
  - Candidates to add later: the playoff bracket, award votes, the facility ranking, rallies.
- **The boost tops out early.** Proposal: a fan's weight is 1.0 for being active, about 1.35 with one activity and 1.5 (the maximum) with any two. One activity gets most of the effect and a second reaches the top; a third adds nothing.
- Because the activities are weighted equally and the cap is reached with any two, **pick-em plus the Showcase earns exactly what fantasy plus anything else does.** Fantasy is one way to reach the top, never the only one.
- The boost applies to each fan before the fan-count curve: `gate = base x (sum of fan weights)^p`.
- Shown on the team page as each fan's contribution ("You're adding 1.5x to the gate this week"), with the activities that count listed.

### Gate formula
- **Concave in fan count:** `gate = base x (sum of fan weights)^p` with p around 0.5-0.7, so 17 fans do not earn 17 times what 1 fan earns. A fanless team's first fan is worth the most.
- **The Stadium raises gate revenue** per level. This gives the Stadium a second job and lets a facility pay for part of its own upkeep.
- Share-denominated like everything else, so it tracks the league's economy.
- Not inflationary for users: treasury money only buys facilities and payroll.
- Relationship to `FUNDING_BASELINE_PER_TEAM` (200F): the baseline stays (it is what a fanless team runs on); gate revenue sits on top.

### League matching on donations (owner, 2026-10-22)
- The league matches the first part of what each fan gives their team each season. Proposal: 2:1 on a fan's first 1,000F a season. A casual fan's 500F becomes 1,500F in the treasury; a fantasy player's 10,000F becomes 12,000F.
- Small donors get the biggest boost and nobody's money is turned away. (Rejected: counting each fan's donations at a falling rate, which does the same job but reads as a penalty to the fans who give the most.)
- Counts direct contributions and the passive season-end percentage together, per fan per season.
- Paid by the league, like gate revenue, so it adds no Floobits to users.
- The match rate and the matched amount are set by the harness against G3.

### Alt accounts (known risk, accepted)
Gate revenue and the match both pay per fan, so a second account favoriting the same team earns that team money. An account-age rule was considered and rejected (owner, 2026-10-22): an alt kept around for a few seasons passes it. Accepted as a known risk. What limits it: the gate curve is concave, so each extra fan adds less; the participation boost needs the alt to actually play each week; and the match only applies to Floobits the alt earned itself.

### Presentation
Lead with **showing up**, not paying up: the team page's biggest number is active fans and the gate they bring in; donations and the match show as a bonus on top.

A team then has two income streams: **fans showing up** (gate, the same for every fan, plus the participation boost) and **fans giving** (donations and the season-end percentage, where fantasy players can give more, with the league match favoring small donors and diminishing returns via §5).

## 5. Phase 3: payroll

### Salary
- Each contract carries a **salary**, set at signing or re-sign, paid every season from the treasury for the contract's term.
- **The salary locks when the contract is signed** (owner, 2026-10-22). It is stored in Floobits on the contract and does not change for its term: not with the player's rating, not with the league's income. A player's price only moves when they sign their next contract. This also makes affordability answerable at signing (see Budget).
- **Convex in rating:** a 95 costs far more than twice a 78. This is the main source of diminishing returns: each extra point of roster quality costs more than the last, and with six roster slots a team that can afford six stars gains nothing from more money. Size the curve so only the very top team approaches that.
- **The asking salary is share-denominated at signing**, so new contracts track the league's income. Only the price of a new contract moves; existing contracts keep their locked salary.
- **Rollout: existing contracts are grandfathered** (owner, 2026-10-22). Contracts signed before payroll ships carry no salary for the rest of their term; only contracts signed or re-signed after it come with one. Payroll phases in over a few seasons as contracts expire, so no team faces a shortfall or forced cuts the moment it lands. The harness should start from a grandfathered league, not a fully salaried one.
- **Rookie and promoted-prospect contracts are cheap.** The draft stays the poor team's route to talent; money is the rich team's route. Both stay open.
- A **minimum salary** that the league baseline always covers (G6). The FA draft's last-resort generated player is minimum salary.

### When money moves (owner, 2026-10-22)
Players get first claim on the money and facilities get what is left, and teams start each season with both settled.

1. **Season end: income only.** The season-end contribution comes in and the season's gate revenue is already in hand. Nothing is spent, except forced cuts (below).
2. **Offseason: players.** Re-signs and the FA draft check affordability against the full balance.
3. **Season start: the payment run.** Pay payroll, then facility upkeep, then new projects in the fans' ranked order (§3). Facilities built here are active from week 1, the same as a level built in the offseason today.

This replaces a separate payroll reserve: because signings happen before any project is funded, nothing has to be set aside for them.

⚠️ The payment run lives on the `startNewSeason` path, which is also the mid-season resume path on every deploy, so it must be gated by a once-per-season marker or a restart pays twice.

### Budget
- Payroll is a flow: a team can afford what its balance plus expected income (gate + recent donations) covers. Saved-up treasury is a war chest a team can spend down to win now.
- **Affordability is checked at signing.** A team signs or re-signs a player only if its balance plus a cautious income estimate covers all its committed salaries for the rest of every contract **and the upkeep of its current facility levels**. Counting upkeep stops a signing from knocking facilities down by accident. A shortfall can then only come from income really dropping (fans leaving, gate revenue falling), not from overspending.
- **A GM can sacrifice a facility level to sign a big player** (owner, 2026-10-22). When a signing doesn't fit, the GM may count a facility's upkeep as available, accepting that the facility drops a level at season start. The money freed is the upkeep saved by holding that facility one level lower for the contract's term. The GM does it only when the player is worth more than the level: it compares the player's value with the wins that level is worth, priced off the measured facility effects (Facilities Economy in CLAUDE.md). It sacrifices the level that costs the least value for the money it needs, ties going to the facility the fans ranked lowest. Fans see it: a news item ("The Waffles let the Stadium slip to sign X") and a line on the team page.
- **No debt.** The balance never goes negative.

### When a team can't make payroll (owner, 2026-10-22)
The check runs at **season end**, before the offseason, so the FA draft can fill any slot it opens. Payment happens at season start, but by then the FA draft is over, and a cut made there would leave a slot empty.

1. **Facilities give way first.** At season start, payroll is paid before upkeep, so a team short of money pays its players and lets facilities go unpaid: each unpaid facility drops a level under the existing rule. Losing a level raises no money; it is the cost of skipping upkeep.
2. **If the season-end balance cannot cover next season's committed payroll**, even with nothing spent on upkeep, the team **cuts players at season end** to close the gap.
   - **The GM chooses who goes:** the fewest players, with the least value lost, whose salaries close the gap. Usually one expensive player, sometimes two cheaper ones if that costs less. Not "always the highest salary", which could cost a team its best player when a cheaper cut would do.
   - **No cut fee** on a forced cut.
   - A cut player's contract and salary end; they enter this offseason's free agency.
   - The FA draft fills the slot as usual. The league baseline always covers a minimum-salary player (G6), so no slot stays empty.
   - **Protected players (owner, 2026-10-22)** are not considered for a forced cut:
     - **Fan favorites**: a keep verdict from the team's own fans (`playerManager.fanVerdict`, average 4+ with quorum).
     - **The team's best players**: its top two by the GM's value, the same core the trade market protects (`_coreOf`, `TRADE_CORE_SIZE` 2).
     - **Prospects the GM projects as stars**: a player on a prospect contract whom the GM reads as reaching 4 stars or better (`TRADE_RISING_STAR_RATING` 84, the trade market's rising-star read). A prospect contract the GM doesn't project that high is cuttable like anyone else.
   - **Last resort, protected players (owner, 2026-10-22):** when cutting every unprotected player still can't close the gap, protected players are cut **from least to most valuable** (the GM's value) until it closes. Protection sets the order; it can't leave the balance negative. Not necessarily rare: the top two are usually the two highest salaries, so a big gap may be more than the four unprotected players earn together. The harness should count how often it fires.
     - **No unneeded cuts:** once the gap is closed, any protected player already marked for cutting whose salary is no longer needed (the gap stays closed without cutting them) is kept, checked from most to least valuable. Without this, a cheap star-track prospect would be cut first for a few Floobits and a top player cut anyway.
   - Fans see a news item for it ("Unpaid, X leaves the Waffles") and a recap row.
3. **Warn fans during the season.** When the balance is on course to fall short of next season's payroll, the team page says so, e.g. "Payroll short by 1,200F. Fund the team or lose a player at season end."

Rejected: league bailouts (removes the reason to care about the treasury), a negative balance (debt can trap a team for seasons and makes the readout confusing), and paying a star less in exchange for worse play (a hidden penalty fans can't see).

### The re-sign limit goes (owner, 2026-10-22)
`RESIGN_LIMIT_PER_OFFSEASON` (2) is removed **in the same release as salaries, not before.** Today it is the only thing stopping every team from keeping every player; with salaries, the treasury limits retention instead: a rich team keeps its stars and pays for them, a poor team keeps who it can afford. The GM's other re-sign rules stay (the 3-star floor, replaceability, the team's own prospects and top picks as replacements, fan verdicts).

Watch in the harness: **free agent pool quality.** If funded teams keep nearly every good player, the FA draft fills with leftovers and worst-first order stops helping poor teams. The fix then is a steeper salary curve for top players at signing, not bringing the limit back.

Touches `seasonManager._resignDecision` / `_applyRetentionLimits` and the Front Office desk projection (`projectedResigns`, which shares that decision).

### Where it acts (reuses existing flow, no auction)
- **Re-signs** (`rankResignCandidates` / `chooseResigns`): a team keeps a player only if it can pay their asking salary. Funded teams hold their stars; unfunded teams lose theirs to free agency. This happens every offseason and fans will see it.
- **FA draft, still worst-first** (`_attemptRosterFill`, the draft boards): a team on the clock can only take players it can afford. A funded team that has been losing picks early **and** can pay, so it gets the best free agents. A poor team picking early takes the best it can afford and the star drops to the next team that can pay.
- **The GM values players per Floobit**, not only per rating point: a cheap 84 can beat an expensive 88 for a tight budget.
- Cuts already cost treasury (`frontOfficeBrain.cutFeeFor`); with salaries, a cut also frees payroll. Revisit the fee so it is not charged twice.
- Trading is off; when it returns, salaries must travel with players.

## 6. Phase 4: make it visible

"All that money and for what" is answered as much by seeing where money went as by wins.

- Salaries on player pages; payroll, payroll room and treasury on the team page.
- A team-page goal, e.g. "1,200F more and you can afford a 4-star free agent this offseason".
- Season-over-season line: payroll, facility levels, roster rating.
- News items for signings ("NYS signs X for 1,200F a season") and for losing a player the team couldn't afford.

## 7. Fan income today (season 6 of the snapshot)

| | Earned in season 6 |
|---|---|
| The 12 users who played fantasy | 6k-20k each, median ~12.6k |
| Same 12, non-fantasy income only (pick-em, achievements, Supporter, etc.) | 4k-9k, median ~5.5k |
| The 14 users with no fantasy income | 25-4.2k, median ~500 (many barely active) |

Season-6 fan contributions by team: top 9,174F; 8 teams above 1,500F; median ~150F; 5 teams 0. Toronto, with 2 fans, gave 3,473F (6th). Treasury income is very concentrated, which is why the curve's shape matters more than its prices.

G3 therefore means: the bulk of payroll's advantage must be reachable on ~3-5k a season of donations plus gate revenue.

## 8. Phase 0: the harness (build first)

Replays seasons on a fresh prod snapshot under these rules and reports wins by funding level. Must cover:
- the funding-quartile win gap (G5) and the marginal win per 1,000F (G1);
- a fanless team given one fan's income, fantasy and non-fantasy (G2, G3), tracked for five seasons;
- **the G3 comparison:** a team with one fantasy fan, one with one non-fantasy fan, and one with two non-fantasy fans. If the fantasy fan's team pulls clearly ahead of the two-fan team, raise gate revenue or the match until it doesn't;
- fanless teams' playoff rate (G4) and empty slots (G6);
- free agent pool quality with the re-sign limit removed, and how often forced payroll cuts fire.

Use the `FLOOS_FACILITY_FORCE` lesson: compare arms on the same league; never infer facility or payroll value from a cross-team regression.

## 9. Open decisions (owner)

1. G5's N: how many wins the top-funded quarter should gain over the bottom.
2. ~~Facilities: unlimited levels per offseason, or a per-facility cap.~~ Settled 2026-10-22: one upgrade per facility per season, funded in the order of the fans' ranked ballots (§3).
3. ~~No debt, forced release, or league cover when funding stops.~~ Settled 2026-10-22: facilities absorb unpaid upkeep at season start, and a payroll shortfall found at season end forces cuts then (§5). Protected: fan favorites, the team's top two, prospects the GM projects as stars. As a last resort, protected players are cut from least to most valuable.
4. ~~Whether fans vote on the split between upkeep and new projects.~~ Settled 2026-10-22: players are signed first in the offseason, the season-start run pays payroll, upkeep, then projects in the fans' ranked order, and a GM may sacrifice a facility level for a big signing (§5). The harness sets how the GM prices a level against a player.
5. Gate revenue exponent and Stadium multiplier (set by the harness against G2/G3).
6. Participation boost sizes (proposal 1.35x for one activity, 1.5x for two). League match rate and amount (proposal 2:1 on the first 1,000F) set by the harness.

## 10. Later: the merch shop

An in-game shop (Floobits, not real money) selling team-themed cosmetics for fan profiles, with proceeds going to the team's treasury. A third treasury stream that also gives non-fantasy fans something to spend on. Not specced; revisit after payroll and gate revenue land.

## Files this will touch

`managers/facilitiesManager.py` (waterfall, projects, gate revenue), `managers/seasonManager.py` (`_runFacilitySeasonEnd` moves to season start, the season-end payroll check, `_applySeasonEndTax`, weekly gate accrual), `managers/playerManager.py` (FA draft, re-sign execution, contracts), `managers/frontOfficeBrain.py` (re-sign / board valuation, `appealDemand` docstring), `database/models.py` + `connection.py` (salary column, inline migrations), `constants.py`, the team / player API payloads, and the frontend team and player pages.
