---
description: Add a new card effect end-to-end (compute handler + edition tier + display/tooltip/detail text + output-type classification + second-pass wiring if cross-card)
argument-hint: [effect name + what it does, e.g. "Underdog: +8 FP if all rostered players are 3 stars or lower"]
---

Add a new card effect: $ARGUMENTS

All card-effect data lives in `managers/cardEffects.py` (keyed by a snake_case `effectName`) and is computed by `managers/cardEffectCalculator.py`. If the request is vague about edition/tier, output type (FP vs FPx vs Floobits), or trigger condition, ask before writing — those determine which path the effect follows and they're hard to change after cards are minted. Honor the naming philosophy (timeless, punchy, no trendy slang) and the no-em-dash voice rule for tooltip/detail copy.

## Steps (in `managers/cardEffects.py` unless noted)

### 1. Compute handler + registry
Write a compute function for the effect and register it in **`EFFECT_REGISTRY`** (the `effectName → handler` dict that `computeEffect()` dispatches through). Mirror an existing handler of the same shape — find a sibling effect of the intended output type and copy its signature/return. Handlers read from the `CardCalcContext` (`ctx`) and return a `CardBreakdown` (see its fields: `preMatchFP`, `primaryFP`, `totalFP`, `primaryMult`, `matchMultiplied`, etc.). If the effect needs computed params, add a branch to the param-builder dispatch (the `if effectName == "..."` chain).

### 2. Edition tier
Add the effect to **`EFFECT_EDITION_TIER`** with its edition: `base` / `holographic` / `prismatic` / `diamond`. This is the single source of truth for which edition the effect belongs to — base = simple/reliable/unconditional; higher = more conditional, higher ceiling/variance. Pick the edition to match the effect's conditionality, not just its raw power.

### 3. Output-type classification
Make sure **`getEffectOutputType(effectName)`** returns the right type (`fp` / `fpx` / `floobits`) — this drives themed-pack filtering and the `card_templates.output_type` stamp. If the classifier is heuristic and misclassifies your effect, add it explicitly.

### 4. Display text
Add entries to **`EFFECT_DISPLAY_NAMES`** (the card's shown name), **`EFFECT_TOOLTIPS`** (one-line hover), and **`EFFECT_DETAIL_TEMPLATES`** (longer description; supports `{statDisplay}` etc. templating resolved against `STAT_DISPLAY_NAMES`). Copy must be punchy and declarative, no em-dashes. The frontend pulls all of this from `GET /api/cards/effects`, so no frontend text changes are needed for the words themselves.

### 5. Second-pass effects ONLY (cross-card)
If the effect reads OTHER cards' breakdowns (copies/chains/scales off them), it must run in the second pass:
- Add the `effectName` to **`_SECOND_PASS_EFFECTS`** in `cardEffectCalculator.py`.
- Implement its second-pass branch there (the `if effectName == "..."` blocks around the second-pass section that read `ctx._firstPassBreakdowns`).
- If it should also see other second-pass cards, it participates in the convergence loop — verify it doesn't read its own `effectName` (the two-Copycat cascade bug).
Skip this entire step for normal (first-pass) effects.

### 6. Frontend behavior tag (optional)
If the effect is chance-based, conditional, or a streak, `Components/Cards/TradingCard.tsx` shows a behavior tag (Chance / Conditional / Streak). These are derived from the effect config; confirm the new effect surfaces the right tag, and add a mapping if it doesn't.

### 7. Verify
- `python -c "import ast; ast.parse(open('managers/cardEffects.py').read()); ast.parse(open('managers/cardEffectCalculator.py').read()); print('OK')"`
- Confirm the effect appears in all four dicts (`EFFECT_REGISTRY`, `EFFECT_EDITION_TIER`, `EFFECT_DISPLAY_NAMES`, `EFFECT_TOOLTIPS`) — a missing tier or registry entry is the usual silent failure.
- Spot-check the math by hand for one roster scenario; if it reads/writes streak state (`equipped_cards.peak_output`/`streak_count`) or match state, walk that path explicitly.

Report which dicts you touched and whether it's a first- or second-pass effect, so a reviewer can confirm step 5 wasn't missed. To validate live math against a real hand, use the `card-effect-investigator` agent or `/simcheck`.
