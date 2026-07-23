# Chance Synergy Audit — is a viable build assemblable?

**Branch:** `feature/fantasy-cards-fusion`
**Context (owner, 2026-07-23):** chance cards are a SYNERGY archetype — weak alone, strong
when you commit (multiple chance cards, amplifiers, the powerup). The power-bar redesign
folds the depicted player's FP in as one more odds source (the "middle option": the luck
bar aggregates FP + trigger + synergy + amplifiers + powerup). This audits whether a
viable build can actually be put together.

## The odds machinery (how a chance card's hit % is built)

`ctx.chanceBonus` is added to every chance card's own trigger chance. Sources:
- **Innate synergy** — `+0.04 (4%) per ADDITIONAL chance card` equipped (`cardEffectCalculator.py:902`).
  6 chance cards → +20% to all of them.
- **Providence** (holographic amplifier) — `+0.12 (12%)`, tier-scaled.
- **Catalyst** (diamond amplifier) — up to `+0.10 (10%)`, scaled by roster FP.
- **Patronage** powerup (`fortunes_favor`) — `+10%` for 3 weeks (125F, 2/season).
- **Advantage** (diamond) — rolls N times (tier I=2 … IV=5), keeps the best.
- **Per-card trigger** — each card's own condition (Rock Bottom's losing streak, Underdog's
  ELO gap, Scrappy's low-rated players, Sleeper's low-rated count, …).
- **NEW (power-bar middle option)** — the depicted player's FP fills the base of the luck bar.

A full prismatic build reaches roughly: card trigger (~15-30%) + innate (+20%) + Patronage
(+10%) ≈ **45-60%** hit on the enhanced payout, higher with an amplifier slotted in. The
math is sound — the synergy genuinely stacks to worthwhile odds.

## The problem: no low/mid-rarity on-ramp

Chance cards by edition: **9 prismatic, 3 base, 0 holographic, 0 diamond.**

1. **The archetype is gated behind prismatic.** 9 of 12 chance cards are prismatic, so a
   real chance build needs prismatic cards. A base/holo-rarity player can't assemble one.
2. **All 3 base chance cards are FLOOBITS-output** (`indemnity`, `rock_bottom`,
   `consolation_prize`). So a base chance build produces NO fantasy points — a non-starter
   for a fantasy lineup whose job is FP.
3. **Zero holographic chance cards** — a gap in the rarity ladder; a holo chance build is
   impossible.
4. **Amplifier support is thin and high-rarity** — only 2 amplifiers (Providence holo,
   Catalyst diamond). No base/holo-accessible amplifier, so the "amplifier leg" of the
   synergy is also locked behind rarity.

Net: the synergy WORKS, but only a player who already has prismatic cards can build it, and
even they get no FP from the base entries. For "possible to make a viable build" to be true
for regular players, the archetype needs a rarity on-ramp.

Position availability is NOT a problem: 10 of 12 chance cards are all-position, so filling
fusion's 6 position-locked slots with chance cards is fine.

## Recommendations

1. **Seed chance cards across the rarity ladder** — add holographic chance cards (currently
   0) and at least one FP-output base chance card (currently all 3 base are floobits), so a
   low/mid-rarity chance build is possible and produces FP.
2. **Add an accessible amplifier** at base or holo, so the amplifier leg isn't diamond/holo-
   only. (Or make innate synergy stronger so amplifiers are optional, not required.)
3. **Confirm the power-bar (middle option) numbers**: FP should be a SMALL base contributor
   to the luck bar so the synergy stack stays the main driver — a lone chance card on a
   good player should still be weak (the archetype's premise). Tune the FP share low.
4. Ensure each position has at least one accessible chance card so a position-locked lineup
   can be all-chance at low rarity.
