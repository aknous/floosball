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
