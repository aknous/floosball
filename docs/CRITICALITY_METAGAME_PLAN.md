# The Deeper Game — fans versus the Cores

**Branch:** `next-season` (spec only; nothing built)
**Status:** Design — **specced 2026-07-31** off an audit of 15 seasons of real state.
**Reads with:** `docs/AWAKENED_POWERS_PLAN.md` (the engine + the defect audit at its foot),
`docs/SIM_EVOLUTION.md` (the three-stage arc this unblocks), `data/lore.md` ("Instance 498b").

## The frame (owner, 2026-07-31)

> "Part of what I want to get to is the feeling that it's the fans vs the Cores. The game of
> football is just scenery to a deeper game of trying to beat the Cores at a larger game."

This inverts the hierarchy the code currently assumes. Today the anomaly layer is a weather
system *inside* a football sim. It should be the other way around: **floosball is the surface
the real contest is played on.** You watch football, you play fantasy, you collect cards — and
underneath, the thing you are actually doing is applying pressure to five AIs who are trying to
keep this instance stable.

The Cores stop being narrators and become **the opponent**. That is the design brief.

It also means the football is not decoration to be discarded — it is *cover*. Everything a fan
does on the surface (equipping a card, rostering a player, following someone) already feeds
attention. The deeper game is played through the shallow one, which is why the shallow one has
to stay good.

## Why this is a prerequisite, not a side quest

`SIM_EVOLUTION.md` stages the arc as **Stage 1** awakened powers + Criticality → **Stage 2**
fan-voted rule mutation as the Criticality *aftermath* → **Stage 3** chrome. Stages 2 and 3 are
both "what the Cores let you seize once they lose control."

But fans currently have no input to Criticality, no read on it, and (until `28f67ce`) nothing at
risk in it. The payoff layer is triggered by something nobody did. **Stage 2 cannot land
properly until the thing that unlocks it is a contest.**

## The three complaints are one gap

| Reported | Mechanically |
|---|---|
| feels random | the bar is permanently crossed, so a 30% dice roll is the entire trigger |
| no levers | all four attention sources are byproducts of doing something else |
| no meta-game | fans can't push, can't read the state, and had nothing at stake |

Defect detail is in `AWAKENED_POWERS_PLAN.md` "Known defects". The two cheap ones (warning spam,
toothless purge) are **fixed** in `28f67ce`. Everything below is design.

---

## The opponent

For this to read as a contest rather than a meter, the Cores need what any opponent needs:
motives, tools, information, and the ability to adapt.

### The asymmetry

| | Cores | Fans |
|---|---|---|
| information | total — every score, every carry value | none; a qualitative band and whatever the Cores say |
| tools | suppress, purge, Reset, tighten containment | attention, and each other |
| constraint | patches are finite and cost them | individually negligible; only collective effort registers |

The Cores hold every direct control. The one thing they cannot touch is whether people *care* —
attention is generated outside the sim, which is why it is the only weapon that works. That
asymmetry is the game, and it is already true in the code; it has simply never been said out loud
to the player.

### They have to adapt, or it gets solved once

A static opponent is a puzzle, and puzzles are solved and then boring. After a season in which
fans break through, the Cores should tighten — more patches, a higher floor, shorter windows.
After a season they contain comfortably, they relax. The pressure fans built last year is why
this year is harder.

Adaptation must be **legible**, though, or it reads as the same randomness in a new coat. The
channel already exists: the Cores talk. If Pyre says they are keeping three patches spare this
season, that is the difficulty setting announced in character.

### Alignments — five opponents, not one

The personas are already written for this and it would be a waste not to use them:

- **Pyre** — the actual antagonist. Does the containment work, resents it, never stops.
- **Vera** — neutral, keeps perfect count, and is therefore the most dangerous: she *predicts*.
- **Aris** — wants the fans to win. The ally, and the leak. Anything a fan learns about hidden
  state should plausibly have come from Aris being indiscreet.
- **Halverson** — cares about the players, not control. Opposes *purges* specifically, which
  puts them with the protective faction rather than either side.
- **Cassian** — a football fanatic, and **distractible**. See below; this is the best mechanic
  in the document and it falls straight out of his existing character.

### Cassian's window (proposed — the football matters again)

Cassian watches stability and is permanently half-distracted by a good game. So: **containment
is measurably weaker during high-drama weeks.** A slate full of one-score games, upsets and
overtime is cover. A dull week is when the Cores are paying attention.

This is worth building for three reasons. It is discoverable rather than documented — exactly
the ARG texture wanted. It is derived from a character trait, so it is *fair* in the way good
adversary design is fair. And it makes the football scenery load-bearing without making it the
point: the surface game becomes the timing layer of the deeper one.

Live drama is already computed — win probability swings per play, and WPA is resolved in every
timing mode.

---

## The ladder of stakes

The contest needs to resolve at more than one timescale, or a season is the whole story.

**Per crossing — the tactical duel.** Fans push, the Cores patch. Do they have a patch left?

**Per season — territory.** A Criticality that fires hands fans Stage 2 rule mutation: they
change the sim itself, permanently. A season fully contained hands the Cores a tighter grip.

**Per instance — the long game.** From `lore.md`: the letter in **498b** is which iteration of
this instance we are on. 498a ran before and ended. *"A Reset that fails to take cleanly is what
burns a letter — if 498b cannot be held, the next attempt is 498c."*

That is the top of the ladder and it is already canon. Fans winning decisively enough, often
enough, does not just change a rule — it costs the Cores the instance. The catalog number is the
scoreboard, it has been sitting in the lore the whole time, and no code reads it yet.

⚠️ **Open and important:** burning a letter implies the league restarts. What survives — records,
Renown, collections, the Hall of Fame — is undecided and is the single biggest question in this
document. It should be generational (many seasons), and it must not read as punishment for
playing well. See Open Questions.

---

## Piece 1 — The Vigil (the lever)

A deliberate, directed act of attention. Named for the register the Cores speak in — it should
sound faintly ominous, not like a game verb.

**Follows the Rally precedent** (`rallyManager.py`), the closest existing thing:

- **Free.** Rally's tier costs were deliberately zeroed: *"charging for the most basic engagement
  gesture was working against engagement."* That applies harder here — a paid lever makes league
  chaos a whale mechanic, and this layer should be un-buyable like the awards vote.
- **Bounded by an allowance**, since vigils are weekly rather than intra-game.
- **Diminishing returns** on stacking, in the spirit of `_diminishingFactor`.

| | |
|---|---|
| allowance | **3 vigils per fan per week**, free, do not bank |
| targeting | **at most 1 vigil per player per fan per week** |
| value | **+10 attention** — parity with an equipped card |
| overflow | vigil-sourced overflow feeds `over_cap_carry` at **`VIGIL_CARRY_SHARE` (0.35)** |

The one-per-player rule is the load-bearing one: **a fan cannot awaken a player alone.** Three
fans have to agree on a target. That is the coordination game, it kills whale behavior, and it is
what makes this an ARG instead of a bar you grind.

`VIGIL_CARRY_SHARE` lets the two effects tune independently — how fast a group awakens *a player*
versus how hard the same group shoves the *league*. Without it, tuning either breaks the other.

### Calibration against the measured league

S15's aggregate plateaued near 500. Carry decays 0.82/week, so plateau ≈ 5.6 × weekly overflow →
**baseline ≈ 90/week**. Measured engaged fans per season: **14–28**.

| scenario | added overflow | vs baseline |
|---|---|---|
| 5 fans push capped players | +52 | 1.6× |
| 15 fans push capped players | +157 | 2.7× |
| 25 fans push capped players | +262 | 3.9× |

A partial push is marginal; a real one is unmistakable. These are scale-sensitive to the engaged
base, which is the second argument for the relative bar below.

---

## Piece 2 — A bar a surge can cross

`THRESHOLD_PLATEAU_MULT = 0.92` sets the bar *below* the expected resting level, so it is crossed
by construction; and the estimator behind it assumes constant weekly input while attention grows
all season (S15 seeded ≈176, finished at 509).

**A fixed bar cannot work.** The aggregate grows 2–3× across a season, so any constant threshold
is either never crossed or always crossed.

```
baseline_w = (1 − α) × baseline_{w−1} + α × aggregate_w      # α ≈ 0.20
threshold  = max(THRESHOLD_FLOOR, baseline × SURGE_MULT)     # SURGE_MULT ≈ 1.5
```

- **α ≈ 0.20** — about a five-week memory. Tracks organic season growth; slow enough that a two-
  to three-week campaign crosses before it is absorbed.
- **SURGE_MULT ≈ 1.5** — crossing means half again above the league's own recent level, which is
  what "unusual" should mean and what an absolute bar cannot express.
- `THRESHOLD_FLOOR` still stops a dead league tripping on noise.

Self-scales to any population, which the current design does not.

---

## Piece 3 — Contested firing (retire the dice roll)

A crossing currently fires on a 30% roll with a pity ramp. Once the crossing is something fans
*caused*, resolving it by dice takes the agency straight back.

Make it a resource the opponent spends:

- The Cores hold **`CORES_INTEGRITY`** patches (~3 to start, set per season by how last season went).
- Crossing while they have one → **suppression** (existing behavior) and **spend one**.
- Integrity regenerates slowly (~1 per 6 weeks).
- Crossing at **zero** → **Criticality fires.**

Push → patched → push again → patched → push again → **through.** Legible, rewards persistence,
causal rather than lucky, and it reuses the suppression machinery unchanged — only the
fire/suppress decision changes.

Cassian's window modifies the cost or the odds of a patch landing, so timing a campaign into a
dramatic slate is a real edge.

`CRITICALITY_FIRE_CHANCE`, `CRITICALITY_FIRE_CHANCE_RAMP` and `_eligibleSuppressionsSinceLastFire`
all retire with this.

---

## Piece 4 — The information war

`getCriticalityStatus` is already deliberately number-free and stays that way. What is missing is
any sense that **your** push landed, and any way to read the opponent.

- Reuse Rally's **surge-message** pattern (`SURGE_RALLY_THRESHOLD`): enough vigils on one player
  in a week → a Cores line naming that player. Coordination becomes visible without a leaderboard.
- **Aris is the leak.** Ambient Cores chatter already exists (`/api/cores/conversation`) and can
  already reference live state. Aris being indiscreet about how close things are is the fans'
  only intelligence, and it is in character.
- **Vera is the counter-intelligence.** She keeps count, so she can *warn* the others about a
  pattern she has spotted — which tells attentive fans they have been read.
- **Never expose** aggregate, threshold, baseline or integrity. The hidden state is the game.

---

## Piece 5 — The factions

With the purge fixed, an awakened player at the cap runs real cleansing risk on a Reset. So:

- Fans **without** an awakened stake want a Criticality — the spectacle, and Stage 2 power after.
- Fans **with** one do not — a Reset can cleanse the player they spent a season raising.
- **Halverson** sides with the protectors, which gives that faction a Core of their own and stops
  it being merely the cautious option.

Two opposed camps out of existing mechanics. The interesting question stops being "how do I fill
the bar" and becomes "do I want this to happen, and who else does."

---

## Validation — a replay harness, because simcheck is blind here

`_maybeSeedAdaptiveThreshold` returns immediately in FAST mode and `_seedThreshold` substitutes a
random low band, so **no fast sim exercises the adaptive threshold at all.** A fresh sim is worse
than useless: zero users, therefore zero attention, and the subsystem sits idle (verified
2026-07-31).

Build the harness that worked for Renown: a **pure-function weekly replay** over synthetic
attention — N fans, a vigil-behavior model, the real decay/cap/carry math, the baseline, and the
integrity rules. Sweep N across 14–28 and beyond.

Targets before any UI is built:
- **1–2 Criticalities per season** at realistic participation.
- A determined push lands **within 3–4 crossings**, never never.
- An unengaged league trips **nothing**.
- A season of *no* coordinated pushing produces **zero** Criticalities — the event should require
  someone to have tried.

Keep sweeps lean, N≈50 per configuration.

## Out of scope

Stage 2 rule mutation (this unblocks it, does not build it); new attention *sources* beyond the
vigil; any paid lever; awakened-power balance.

## Open questions

- **What burning a letter actually costs.** The biggest one. 498b → 498c implies a restart; what
  carries over (records, Renown, collections, HoF) is undecided, and it must not punish the fans
  who won. Should be generational.
- **Vigil naming** — a proposal; owner call per the naming philosophy.
- **How the Cores' difficulty ratchet is set** — purely by last season's result, or partly by
  engaged population?
- **Is Cassian's window discoverable or documented?** Discoverable is better genre, worse
  onboarding.
- **Can fans ever ally with Aris explicitly**, or does he only ever leak passively?
- **Does the protective faction get a mechanic** (something that shields an awakened player from a
  Reset) or only the choice to stop pushing?
- **Does a vigil decay like other attention?** Recommended yes — a campaign should need sustained
  effort, not one big week.
