---
description: Locate and safely adjust a balance / economy constant, with the right validation loop and the guardrails that keep a tweak from quietly breaking design intent
argument-hint: [what to tune, e.g. "raise weekly fantasy income ~15%" or "make underdog pick-em picks worth more" or "buff base-edition card floor"]
---

Tune a balance/economy value: $ARGUMENTS

Almost everything tunable lives in **`constants.py`** (a few card dials live with the card code). Change the value there, then validate with `/simcheck`. If the request is directional ("buff X", "make Y rarer") without a target, propose a specific number + the reasoning before editing — and say what it does to adjacent systems.

## Where things live (`constants.py` unless noted)

| Domain | Constants | Consumer / formula |
|--------|-----------|--------------------|
| **Game balance** | `LEAGUE_COMPRESSION_MEAN/FACTOR`, `MENTAL_FLOOR_RATIO`, `MOMENTUM_*` (decay rates, event deltas, cascade), `RECEIVER_MATCHUP_SCALE`, `COACH_ATTR_NEUTRAL/RANGE`, `ELO_DIVISOR`, pressure/clutch thresholds | `floosball_game.py` (`playGame` pre-game mods, play-calling, momentum, WP). Clock/FG rules are in `game_rules.py` (`QUARTER_SECONDS`, `FG_SNAP_DISTANCE`, `FG_MIN_ATTEMPT_PROB`). |
| **Weekly income (FP→Floobits)** | `WEEKLY_FP_FLOOBIT_SCALE/EXPONENT` (standard), `WEEKLY_FP_FLOOBIT_BOOSTED_SCALE/EXPONENT` (Endowment) | `seasonManager._awardWeeklyFpFloobits`. Curve: `round(SCALE × FP^EXPONENT)`, no cap. Raise SCALE to lift floor+ceiling together; raise EXPONENT toward 1.0 to taper less. Keep Endowment flatter (lower scale, higher exponent) so it stays a high-roller bet. |
| **Other earning** | `CLINCH_PLAYOFF_REWARD`, `CLINCH_TOPSEED_REWARD`, `FLOOSBOWL_WIN_REWARD` | currency grants in `seasonManager`. |
| **Fantasy** | `ROSTER_SWAP_COST` / `_INCREMENT` (cost = `15 + 15×prior_swaps_in_slot`), `ROSTER_MIN_PLAYERS`, `WEEKLY_LEADERBOARD_PRIZES` / `_TOP_PCT[_PRIZE]`, `SEASON_LEADERBOARD_PRIZES` / `_TOP_PCT[_PRIZE]` | `fantasyTracker.py` (swaps), `seasonManager` (prize payouts). |
| **Pick-Em** | `PICKEM_BASE_POINTS`, `PICKEM_QUARTER_MULTIPLIERS` + `PICKEM_MIN_DECAY_FRACTION`, `PICKEM_UNDERDOG_MAX` / `PICKEM_FAVORITE_MIN` / `PICKEM_UNDERDOG_EXPONENT`, `PICKEM_CLAIRVOYANT_THRESHOLD` / `_BONUS`, `PICKEM_POINTS_TO_FLOOBITS`, `PICKEM_WEEKLY/SEASON_PRIZES` | `pickem_repository.resolvePicks` + `calculateUnderdogMultiplier`. points = `base × timing × underdog` (correct picks). |
| **GM / Front Office** | `GM_VOTE_COST` (per type), `GM_ACTIVE_WEEK` (=22), `GM_TRIBUNE_VOTE_THRESHOLD`, `GM_FA_BALLOT_COST` / `_MAX_RANKINGS`, `GM_ROOKIE_BALLOT_COST` / `GM_ROOKIE_DRAFT_MAX_RANKINGS` | `gmManager.py`. Pass threshold is `max(1, teamFanCount)` (computed, not a constant). |
| **Team funding** | `FUNDING_BASELINE_PER_TEAM`, `FUNDING_DECAY_RATE`, `DEFAULT_FUNDING_PCT`, tier ratio thresholds, `FUNDING_DEV_BONUS` / `FUNDING_MORALE_MODIFIER` / `FUNDING_FATIGUE_REDUCTION` (per tier) | `seasonManager` funding recompute + `floosball_game._applyFundingMorale`. |
| **Powerups** | `POWERUP_CATALOG` (price/duration/limit per slug) | shop + effect sites. To add one, use `/powerup`. |
| **Shop / packs** | `SHOP_REROLL_BASE_COST` / `_INCREMENT`, `THEMED_PACK_REROLL_BASE_COST` / `_INCREMENT`, `FEATURED_CARD_COUNT`, `THEMED_PACK_SLOT_COUNT` (in `cardManager.py`); pack prices/weights in `card_repositories.py::seedDefaults` | `cardManager.py`. |
| **Cards** | Edition rating-gates + sell values + rarity weights in `cardManager.py`; the Balatro-pass dials `_BAL_FP_MULT` / `_BAL_FPX_MULT` (currently 0.5, halving effect outputs) in `cardEffects.py`; per-effect numbers in each compute fn (`cardEffects.py`) | use `/effect` for new effects, `card-effect-investigator` for payout bugs. |

## Guardrails (don't break these)
- **Card tier philosophy**: base = simple/reliable/unconditional (steady floor); holographic→diamond = increasingly conditional/synergy-dependent with higher ceiling + variance, not higher average. A Diamond can be useless if mis-deployed — that's by design. Don't flatten that curve when tuning.
- **Legacy/dead — do NOT tune these thinking they do something**: `GAME_MAX_PLAYS`, `PLAYS_TO_*_QUARTER`, `FOURTH_QUARTER_START` (play-count model is deprecated; game is clock-driven); `GM_VOTES_PER_SEASON` / `GM_VOTES_PER_TYPE` / `GM_VOTES_PER_TARGET` (old GM caps, unused under single-vote — `GM_TRIBUNE_VOTE_THRESHOLD` is the only live one).
- **Pack prices** are seeded in `card_repositories.py::seedDefaults`, not `constants.py`, and re-seed on every boot.
- **User-facing copy** that mentions a tuned value (tooltips, changelog) follows the voice rule: no em-dashes, punchy declarative.

## Validate
Run `/simcheck` after any change — confirm no errors and that the affected system still produces sane numbers (e.g. income lands on the new curve, rosters stay full, scores ~realistic). For a card-number change, spot-check one hand via `card-effect-investigator`; for economy, query a few `currency_transactions` in the throwaway DB. Report the before→after value, the formula it feeds, and what you observed in validation. If the change is meant to ship a tuning the user will notice, remind them it also needs a `[Tag]` changelog line in the frontend.
