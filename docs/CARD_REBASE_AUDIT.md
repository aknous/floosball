# Card Effect Re-base Audit — which effects can key off the CARD PLAYER

**Branch:** `feature/fantasy-cards-fusion`
**Goal (owner, 2026-07-22):** audit every effect and find ones that can change to be based
on the depicted card player, so more effects are card-player-based.

## Framing — the gate already ties every card to its player

The card gate (`docs/CARD_ONCARD_REBASE_PLAN.md`, shipped `4fb57f2`) already makes EVERY
gated card scale with its depicted player's week (the ramp). So "tied to the card player"
is done. This audit is about a DEEPER layer: which effects' CORE LOGIC reads better as a
card-player effect ("+FP when THIS player scores") than as a roster aggregate ("+FP per
roster TD"). Re-basing the logic is about legibility and flavour, not about whether the
card responds to the player — the gate handles that.

**Watch for double-tying:** if an effect is re-based to the card player's stat AND gated
on that same player's stat, the two overlap. Prefer re-basing effects whose payoff stat
DIFFERS from a plausible gate stat, or accept the gate as the player-tie and leave the
logic roster-scoped.

Counts: 21 already on-card (Stage 1). Of the remaining, 64 read roster data. Verdicts:

## A. CLEAN RE-BASE — reads better on-card, no re-tune needed  [~14]

Over/under their OWN rating — becomes a crisp binary on the card player:
- `rising_tide` (`_computeRisingTide`) — FPx per roster player beating their rating →
  "+FPx if THIS player beats their rating".
- `buy_low` (`_computeBuyLow`) — floobits per underperformer → "floobits if THIS player
  underperforms".
- `reclamation` (`_computeFixerUpper`), `resplendent` (`_computeHotRoster`),
  `windfall` (`_computeDiamondInTheRough`) — same over/under family.

Own single-player stat sums — collapse the roster loop to the card player:
- `closer` (`_computeCloser`) — Q4 FP × mult → this player's Q4 FP.
- `walk_off` (`_computeWalkOff`) — Q4 scoring plays → this player's.
- `odometer` (`_computeOdometer`) — total roster yards → this player's yards.
- `honor_roll` (`_computeHonorRoll`) — FPx per roster player with 15+ FP → "+FPx if THIS
  player clears 15 FP" (binary). (Or keep as a roster COUNT — borderline; see C.)

Total roster FP → own FP:
- `piggy_bank` (`_computePiggyBank`) — % of roster FP as floobits → % of this player's FP.
- `catalyst` (`_computeCatalyst`) — chance boost per roster FP → per this player's FP.
- `hedge` (`_computeHedge`) — insurance vs a low roster week → insurance vs this player's
  bad game (premise shifts but reads fine).

Chance cards keyed on roster stats — re-point the trigger to the card player:
- `babysitter`, `bonsai`, `consolation_prize`, `snake_eyes` — their trigger stat becomes
  the card player's.

## B. RE-BASE BUT RE-TUNE — TD-scale mismatch  [~6]

These multiply by `rosterTotalTds` (0–8 across a roster). One player scores 0–2, so a
straight re-base makes them weak and their escalating gates unreachable. Re-base AND bump
the per-TD value / lower the gates.
- `touchdown_pinata`, `avalanche`, `cornucopia`, `feeding_frenzy`, `touchdown_jackpot`.

⚠️ **Doubler interaction:** `doubler` doubles `rosterTotalTds` "for other cards". If the
pinata family reads the card player's TDs instead, `doubler`'s mechanic no longer feeds
them — decide whether doubler doubles the card player's TDs, or these leave the doubler web.

## C. KEEP ROSTER — the deckbuilding layer (owner: preserve it)  [~15]

Composition premises that only mean something across a lineup; re-basing deletes them:
- `vanguard` (5+ veterans), `rookie_hype` (rookies), `home_alone` (empty slots),
  `loyalty` (original lineup kept), `eminence` (top-10 at position),
  `cornerstone` (#1 at position), `dark_horse`, `entourage`/`showoff` (star counts),
  `trust_fund` (weeks unchanged), `patient`, `sleeper`, `scrappy`.

## D. CAN'T RE-BASE — inherently multi-player  [~10]

Same-team / cross-team relationships need at least two roster players:
- `stack`, `backfield_buddies`, `synergy`, `castaway`, `comeback_kid`, `domination`,
  `homer`, `hometown_hero`, `wanderer`, `lead_blocker`.

## E. STREAK / ESCALATING keyed on roster TDs — re-base optional  [~11]

Read `rosterTotalTds` as a per-week streak TRIGGER, not a payout: `automatic`,
`bandwagon_express`, `complacency`, `drought`, `momentum`, `nose_picker`, `on_fire`,
`quiet_storm`, `sandbagger`, `snowball_fight`, `leg_day`. Could key the streak off the card
player's TDs, but that changes streak semantics AND hits the same TD-scale problem. Lower
priority — leave unless we want streaks to be player-specific.

## Recommended order

1. **Group A** — the clean wins, ~14 effects, no re-tune, immediately more legible on-card.
2. **Group B** — re-base + re-tune, after deciding the doubler question.
3. Leave C (deckbuilding), D (multi-player), E (streaks) as roster-scoped; the gate already
   ties them to their player.
