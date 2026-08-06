# Glitch Cards — wild magic from a Criticality

**Branch:** `next-season`
**Status:** DESIGN — settled in conversation 2026-08-06. Nothing built.
**Reads with:** `docs/CRITICALITY_METAGAME_PLAN.md` (the fans-vs-Cores frame and the locked
no-wipe constraint), `docs/AWAKENED_POWERS_PLAN.md` (the ladder and the awakened rule),
`docs/CHROME.md` (chrome supersedes the Vigil as the fan lever), `docs/CARD_STAT_LADDER.md`
(the card pool this attaches to).

## What it is

A **glitch card is a real card that caught something during a Criticality.** Not a new tier,
not a new effect pool — an existing card in someone's collection, marked, that now carries an
extra unpredictable payout on top of what it already did.

The reference is wild magic: you keep everything the card was, and some weeks it also does
something else entirely.

## The rule that shapes everything (owner, 2026-08-06)

> **A glitch never takes anything away.**

An earlier draft had the glitch corrupting the card's printed effect — misreads, damping,
nulls. That was wrong, and for a reason worth writing down: **people cultivate cards and
lineups.** Degrading what someone built reads as a punishment for having built it. A card that
sometimes pays less than it says is a worse card wearing a costume.

So the surge is strictly **additive and non-negative**. The card always does its job. The
glitch rides on top, and the inconsistency lives in the UPSIDE — a quiet week means no bonus,
never a penalty.

This also keeps it inside the locked constraint in `CRITICALITY_METAGAME_PLAN.md:107`:

> The currency of the contest is CONTROL and ANOMALY. It is never RECORDS.

Collections are named explicitly in the *never at risk* column. A glitch card can be
unpredictable in what it ADDS. It can never be confiscated, degraded, or lost.

## Where it lives

**On `UserCard`, not `CardTemplate`.** `UserCard` already carries per-instance state (`tier`,
`vaulted`), and the same template must be able to exist clean in one collection and glitched in
another. The glitch happened to *your copy*, in a specific week, at a specific event.

## The surge table

The multiplier applies to the **card's own output**, so a surge scales with whatever it is
attached to instead of being a flat FP number that trivialises metallic and vanishes on diamond.

| outcome | x base | weight | on a 28.3 FP card | card pays |
|---|---|---|---|---|
| **quiet** | 0.00 | 34% | 0.0 | 28.3 |
| **flicker** | 0.35 | 26% | 9.9 | 38.2 |
| **surge** | 1.00 | 22% | 28.3 | 56.6 |
| **cascade** | 2.50 | 13% | 70.8 | 99.0 |
| **runaway** | 5.00 | 5% | 141.5 | **169.8** |

EV is +0.89x base, so a glitched card averages **1.89x a clean one**, doubles or better 40% of
weeks, and does nothing extra a third of the time. One week in twenty it goes off for six times
a normal card.

Names are placeholder and want an owner pass. The set escalates cleanly and is one-word,
timeless, no slang.

## Who gets glitched

**Everyone with cards equipped, at identical per-card odds.** This is not a lottery among
users — a Criticality hits the whole league, and exposure is the only qualification.

⚠️ **Per-CARD odds, not one-card-per-user.** An earlier version glitched exactly one random
equipped card per user, which is trivially gameable: strip your lineup to a single card for
that week and the glitch is guaranteed to land on it. Rolling each equipped card independently
removes the incentive completely — per-card odds are identical at every lineup size, and
equipping fewer cards simply means fewer chances.

## The odds come from the player on the card

The card is the player under fusion, so the card's instability should be the player's. A card's
glitch chance is read off **its own player's position on the attention ladder**:

| player state | attention | glitch odds | what the card does |
|---|---|---|---|
| stable | 0-10 | 4% | rarely catches anything |
| stirring | 10-30 | 12% | starts flickering |
| erratic | 30-60 | 22% | genuinely unstable |
| rampant | 60-90 | 35% | most likely to glitch |
| **awakened** | 90+ | **0%** | **stops glitching — see below** |
| cleansed | purged | 0% | goes quiet |

A full lineup of stable players expects **0.24** glitches per Criticality. A lineup pushed up
the ladder expects **~1.3**. Cultivating attention on your own card players is the lever, and
that is exactly the deeper game — the thing that earns you glitch cards is the thing that
causes Criticalities.

### Awakened is the arc, not an exception

`AWAKENED_POWERS_PLAN.md:30` is explicit: on reaching awakened a player **stops glitching
entirely** and gains permanent signature abilities instead, and glitch rolls must skip them.

The card should do the same thing. That gives the whole system an arc rather than a slot
machine:

    stable -> stirring -> erratic -> rampant        the card gets wilder and wilder
    -> awakened                                     it stops rolling and settles into
                                                    something permanent and consistent
    -> cleansed                                     it goes quiet; the card is still yours

A cleansed player keeps their career, stats and records and loses only the power. The card
mirrors that: still owned, still playing its printed effect, no longer wild.

**Open:** what an awakened card converts INTO. "Permanent and consistent" is the shape; the
content is undesigned. It should probably relate to the player's signature ability.

## League instability scales the table

`getCriticalityMultiplier` already ramps as the aggregate approaches a crossing and floors
during a suppression window. The surge table should breathe with it — quiet leagues weight
toward `quiet`/`flicker`, and as pressure builds the tail opens up. During a Criticality
`runaway` is genuinely likely.

That gives people a reason to watch the Cores' status page, which is what the metagame plan
wants, and it never requires a negative outcome to create tension.

## Open questions

1. **Does a glitch survive the season boundary?** Only current-season templates score, so a
   glitched card from season 3 goes inert in season 4 whatever its mark. Either the glitch
   transfers to a card at the cutover, or a glitch card is explicitly a ONE-SEASON artifact —
   defensible at 2-3 Criticalities a year, but it makes them ephemeral rather than trophies.
2. **FPx surges need their own damping.** Multiplying a `+0.10 FPx` card by 5 is ~150 FP across
   a full lineup, versus ~140 for the equivalent FP card, and FPx compounds against everything
   else held. The table has to be output-aware or FPx needs a gentler multiplier column.
3. **Is the roll visible before the week scores, or only after?** Revealing it early makes it
   plannable, which cuts against wild magic. Revealing it after makes checking your card the
   payoff.
4. **What does an awakened card become?** See above.
5. **Names** for the five surge outcomes.

## What is NOT in scope

- **No confiscation.** Locked constraint; collections are never at risk.
- **No degradation of the printed effect.** Owner call, 2026-08-06.
- **Not a new edition.** It marks existing cards; it does not add a tier above diamond.
