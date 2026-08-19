# Weather & Stadiums

**Status: SPECCED, BUILD IN PROGRESS** (2026-08-19). Owner direction in this document's
"Premise" is settled; everything under "Open decisions" is not.

Prior work: `feature/stadium-quirks` (4 commits, last touched 2026-06-08, 1,100
commits behind development). Data and loader only — its own scaffold commit says
"game wiring and frontend surfacing come in follow-up commits", and there are none.

---

## Premise (owner, 2026-08-19)

Every stadium is a **fantastical setting**. The Jetskis play on a field literally
floating on the ocean; the Rocks play in a cavern; the Midnights play under a
perpetual full moon; the Trains play inside a moving train.

**Weather is whatever is realistic FOR THAT SETTING**, which is deliberately not
limited to rain/wind/snow. A cavern has no rain — it has dripping, dust, echo and
darkness. A moving train has crosswinds, tunnels and speed. Open water has swell,
spray and fog.

Weather has **levels of intensity, and intensity scales with the current anomaly
level, peaking during Criticality.** Whatever the weather is, the game must
describe it accurately.

This already has a home in the lore. The stadiums are the **Cores' reconstructions**
of old floosball venues, assembled from fragmentary broadcast transmissions — that
framing was established on the old branch and is why a team called Rocks ends up in
a mine. Weather degrading as the anomaly aggregate climbs is therefore not a
metaphor bolted on: it is the reconstruction losing coherence, in public, where
everyone can see it.

## Why the anomaly hook is the centerpiece

Every public anomaly surface today is deliberately **number-free** — `getCriticalityStatus`
returns qualitative bands, and the Cores' data-aware beats are confined to an
ephemeral endpoint precisely so the buildup reads as a mood rather than a progress bar.

That design has always been missing a way for a normal user to FEEL the buildup
without being told about it. Weather is that: nobody has to explain that the storms
are getting worse. It is the same information the hidden aggregate carries, delivered
as scenery, and it costs no new number on screen.

⚠️ **The intensity input already exists and is already safe.** Every game loads
`self._criticalityMultiplier` at kickoff (`floosball_game.py:~13756`), inside a
try/except that falls back to 1.0 on any failure. Its range:

| dial | meaning |
|---|---|
| **0.45** | a suppression window — the Cores just patched a near-miss, pointedly quiet |
| **1.0** | quiet league (baseline) |
| **1.0 → 2.6** | the instability ramp, climbing as the aggregate approaches its hidden threshold |
| **5.0** | an actually-fired Criticality (`CRITICALITY_MULTIPLIER`; 8.0 in FAST) |

So weather intensity is a **pure function of a number the game already holds**. No
new DB read per game, no new failure mode, and it inherits the existing fallback:
if the anomaly system is unavailable the league plays in settled weather.

The 0.45 suppression rung is a free storytelling beat worth keeping: after the Cores
catch a crossing, the weather goes **unnaturally still** rather than merely normal.

## Architecture

### 1. The venue owns its weather table

Weather is **drawn from the venue's own table**, not a global weather system that
stadiums then modify. A global model cannot express "the cavern's bad day", and every
venue would need an exclusion list for the conditions that make no sense in it.

```yaml
Jetskis:
  name: "Marina Bay"
  setting: open water            # the fantastical premise, one line
  weather:
    - key: glass
      label: "Glassy"            # the calm state; every venue needs one
      effects: {}
    - key: swell
      label: "Heavy Swell"
      effects: {fumbleRate: 1.18, passAccuracy: 0.94, fgAccuracy: 0.90}
    - key: spray
      label: "Salt Spray"
      effects: {passAccuracy: 0.92, puntDistance: 0.94}
    - key: fog
      label: "Sea Fog"
      effects: {deepPassChance: 0.80, passAccuracy: 0.95}
    - key: squall
      label: "Squall"
      unrealOnly: true           # Criticality tier only
      effects: {fumbleRate: 1.5, deepPassChance: 0.5, fgAccuracy: 0.7}
```

Each venue authors its states at **full ("Rough") strength**; intensity scales the
deviation from neutral, so there is one authored number per effect rather than one
per effect per level:

```
applied = 1 + (authored - 1) * intensityScale
```

### 2. The intensity ladder

| level | dial | scale | reads as |
|---|---|---|---|
| **Still** | ≤ 0.45 | 0.0 | unnaturally calm; suppression window |
| **Settled** | ≤ 1.0 | 0.25 | the venue on a normal day |
| **Unsettled** | ≤ 1.6 | 0.6 | noticeable, not decisive |
| **Rough** | ≤ 2.2 | 1.0 | authored strength |
| **Severe** | < 5.0 | 1.4 | the top of the pre-Criticality ramp |
| **Unreal** | ≥ 5.0 | 2.0 | Criticality only; `unrealOnly` states unlock |

`unrealOnly` states are the payoff: a condition that cannot occur at all until the
league goes critical, so Criticality has a face at every venue rather than only in
the Cores' feed.

### 3. One modifier vocabulary, every key with a real call site

⚠️ The old branch's `EFFECT_KEYS` is a **proposed vocabulary, not an interface** —
not one of its ten keys is read by anything, and three (`clutchVariance`,
`roadDiscipline`, `homeBoost`) do not map onto anything that exists in the sim
today. Ship only keys with a verified call site:

| key | applied at |
|---|---|
| `passAccuracy` | completion roll in `passPlay` |
| `deepPassChance` | pass-tier weighting (`_applyGameplanMods`) |
| `footing` | the **shared carrier tail** — rushes *and* yards after catch |
| `fgAccuracy` | `fgMakeProbability` — the single source of truth, so the coach's attempt decision moves with it automatically |
| `sackRate` | `calculateSackProbability` |
| `fumbleRate` | the fumble check in the shared carrier tail |
| `puntDistance` | `resolvePunt` |
| `returnYards` | `_resolvePuntReturn` |
| `paceMod` | pre-snap time |
| `visibility` | **two-sided, see below** |

### The surface is not a run-only effect, and symmetry is not the goal

⚠️ **`footing` was called `runYardage`, and that was wrong once you look at where it
wires.** The sim resolves `_runnerMove` and `_stretchForFirst` in a carrier tail
**shared by runs and receptions**, so ground that runs fast helps a receiver who has
caught it exactly as much as it helps a back. Yards after catch are **~31% of passing
yards** in this sim, so a surface effect lands on all of the run game and roughly a
third of the pass game.

This corrected a real error downstream: `phaseBias` counted the surface as purely
run-side, which **overstated how run-favoring every firm-ground venue is by the whole
YAC share** — and that error would have flowed straight into what the front office
drafts.

⚠️ **Perfect symmetry between the phases is not achievable and is not the goal**
(owner, 2026-08-19). Weather acts on two things and they do not partition evenly:

- the **air** — ball flight, so passing and kicking;
- the **surface** — the carrier, so running *plus a third of passing*.

Passing simply has more distinct failure modes (the throw, the catch, the protection,
the sight of it) than running has. The honest response is to **measure the asymmetry and
account for it**, not to flatten the model until every key is even. What must hold is
that the *league* does not lean systematically one way, which the centered bias handles
and the test pins.

### Sight is its own dimension, and it cuts both ways

⚠️ Darkness was first modeled as `passAccuracy`, which quietly asserts that **poor sight
only costs the offense**. It does not: a carrier nobody can see is a carrier nobody can
tackle. Measured on the draft, **34 of the league's conditions** had collapsed into a
flat tax on throwing because of it — which is also most of why the file came out 92%
penalties.

`visibility` (1.0 normal, below = obscured, above = unnaturally clear) drives four
things, and all four call sites were verified to exist before the key was added:

| | |
|---|---|
| `passAccuracy` | `× visibility ** VISIBILITY_PASS_EXP` (0.5, mild) |
| `deepPassChance` | `× visibility ** VISIBILITY_DEEP_EXP` (1.5, steep — a deep ball needs sight most) |
| punt muff + fair catch | raised as sight falls (`PUNT_MUFF_*`, `PUNT_FAIRCATCH_*`) |
| **the tackler in `_runnerMove`** | **resistance LOWERED as sight falls**, so a dark field hands yards to the carrier |

⚠️ **The fourth row is the whole point and is the one most likely to be quietly dropped
during wiring.** Without it this is a renamed passing penalty. `test_stadium_weather.py`
pins the exponents' relationship so it cannot silently become one-sided.

⚠️ Use `visibility` **instead of** a raw passing penalty where the cause is sight —
carrying both charges for the same darkness twice, which the test also refuses.

⚠️ It is weighted **×2** in the fairness severity metric (`SEVERITY_WEIGHTS`): one term
replaces two authored keys and adds two more consequences, so counting it once would
make a dark venue measure as half the venue it is.

⚠️ `fgAccuracy` reaching `fgMakeProbability` is the reason that function was
consolidated: the attempt decision, the kick, the PAT estimate and the OT model all
read it, so weather correctly makes a coach decline a kick he would take on a calm
day. Do not apply weather at the kick site only.

### 4. Description is a requirement, not a garnish

⚠️ **Every effect the description names must be a real modifier, and every
significant modifier must be named.** The owner's standing complaint about contested
scoring — that it "just seems like flavor on top of the score instead of another gate"
— is exactly the failure mode available here, and weather is the single easiest place
in this codebase to ship something that looks like a system and is a sticker.

Surfaces:
- **Pre-game**: venue + condition + intensity, on the game card.
- **Play feed**: an opening line, and a line when the condition SHIFTS (see below).
  At most one line per state change, never a line per play — the Bleachers already
  taught that lesson.
- **`game_state`**: a `weather` block on the broadcast, so the live board can render it.
- **Persisted** on the games row (`games.weather`, JSON), following the
  `chaos_rules` / `format_state` precedent, so a finished game still describes the
  conditions it was played in. Not derivable after the fact — like `format_state`,
  it exists only in the live stream unless written down.

### 5. Weather can shift mid-game (phase 2)

Real weather turns. At `Rough` and above, allow one shift per game at a quarter
boundary, drawn from the same venue table. This is where the play-feed line earns
its place. Deliberately phase 2: land a static condition first so the effects can be
measured against a fixed baseline.

## State of the prior work

| | |
|---|---|
| `data/templates/stadium_quirks.yaml` | 443 lines, 24 venues, named and written with flavor pools. **Only 18 are current teams.** |
| `managers/stadiumQuirkManager.py` | 153 lines, read-only singleton loader keyed by team name. Structurally fine; the effect vocabulary needs replacing. |

⚠️ **14 of 32 teams have no stadium**: Monuments, Pops, Tuesdays, Waffles, Midnights,
Bees, Extras, Raccoons, Curd, Trains, Grillmeisters, Exoticos, Buffalo, Sodas — which
includes **Midnights and Trains, two of the four venues named in the premise above.**

⚠️ **6 venues belong to teams that no longer exist**: Drivers, Moonlight, Lattes,
Bachelorettes, Babies, Blouses. At least one is a straight salvage — *Moonlight
Towers, "Moonlit Field"* is the Midnights' perpetual-full-moon venue under an older
team name.

⚠️ The file is keyed by **team name**, which is mutable (six keys already went stale
this way). Key by team id, or the file rots again at the next rename.

## Build order

1. Port the branch onto `next-season`; re-key by team id; drop the dead effect keys.
2. Write the 14 missing venues, salvaging the 6 orphans where they fit.
3. Weather tables per venue + the intensity ladder off `_criticalityMultiplier`.
4. Wire the 9 modifiers at their call sites, behind `WEATHER_ENABLED`.
5. Description: pre-game, `game_state`, persistence, play feed.
6. Measure (below), then tune.
7. Phase 2: mid-game shifts; frontend venue art.

## Measurement

⚠️ Weather is a **pre-game rating-adjacent layer**, and this codebase has a measured
rule for those: **rating-multiplier → win-probability transfer is 1.619**, i.e. a ±10%
roster-wide multiplier is worth ±4.5 wins a season. A weather layer that looks small
can be decisive. Measure with a forced-intensity arm (the `FLOOS_POS_FORCE` pattern)
before tuning, and check:
- scoring at each intensity level vs. the ~36 pts/game target
- whether home teams gain (see Open decisions)
- FP distribution, since weather moves fantasy scoring and therefore the economy

## Settled decisions (owner, 2026-08-19)

1. **Weather effects are SYMMETRIC.** A wet ball is wet for everyone. No weather key
   is ever applied to one side only.
2. **Weather is announced BEFORE kickoff**, with the slate at the week rollover. This
   makes it real input for pick-em and for card lineups, so weather is a strategy
   surface rather than scenery — and it means the announcement path is part of the
   feature, not a follow-up.
3. **Criticality hits hard.** `Unreal` is meant to be disruptive, not a few percent.
   The old file's "character, not balance disruption" note governs the settled league
   and explicitly does NOT govern the top rung.
4. **Home-field advantage exists as a small, separate nudge** — separate from weather,
   which stays symmetric per (1).

### Competitive fairness: equal magnitude, different shape

⚠️ **A team plays 14 games a season at its own venue** (owner, 2026-08-19), so a venue
that is harsher than the rest is a season-long tax on whoever lives there. Weather is
symmetric inside a game, so this is not about one side gaining — it is about repeated
exposure, and it lands on the home team specifically.

The mechanism is skill compression rather than a flat penalty: adverse conditions add
variance and mute the better team's edge, so a harsh venue quietly costs a GOOD home
team wins and hands a BAD one a few. Either way it is uncompensated, because the
autonomous front office does not consider the venue when building a roster.

**Measured before it was enforced**: always-on severity (log-space distance from
neutral) ran **0.070 to 0.263, a 3.8x spread** — St. Louis carried nearly four times
Minnesota's permanent load. Now 1.04x.

⚠️ **The ALWAYS-ON layer is the dangerous one, and the two layers get different bands.**
Always-on is paid at full strength in all 14 home games; weather is scaled to a quarter
in a settled league and varies game to game, so it averages out over a season. Targets:
always-on **0.130** (tight), weather **0.210** per condition (looser), Criticality
conditions at 3.4x the ordinary target since they are meant to be extreme.

⚠️ Equalizing scales every deviation in a venue by **one factor**, which preserves the
proportions between its keys exactly — the venue still feels like itself and only its
weight changes. **Do NOT equalize the shape**: 25 distinct key combinations across 32
venues is what makes these different places rather than one weather system wearing 32
names.

**Residual, accepted for now**: a pass/run tilt of −0.20 to +0.26 remains (fog suppresses
passing more than running, and it should). At a settled league's quarter strength that
is small, and it cuts both ways depending on the home roster's style. ⚠️ Re-measure it
as a **win-rate** effect once the modifiers are wired — everything above is an
analytic proxy, since nothing reaches a game yet.

### Paired venues

⚠️ **Minnesota Pops and Salt Lake City Sodas are a MATCHED PAIR** (owner, 2026-08-19).
Both teams are named for the same dispute — what the drink is called — and both are
rivals who think they do it better. Their venues therefore have to be written together
or the rivalry stops reading: Minnesota argues the word is the SOUND and bottles it
(`The Bottling Floor`, "That Is the Sound It Makes"); Salt Lake argues the word belongs
to the drink and mixes it to order (`The Fountain`, "Mixed, Not Sealed"). Bottle against
fountain, sealed against mixed. Each YAML entry carries a pointer to the other.

⚠️ A weather **key is scoped to its venue, not global** — 7 keys are reused across the
league by design (4 venues have a `glare`). Anything persisting a condition must store
the venue alongside it, or a bare key does not identify what was played in.

### Home-field advantage

⚠️ **There is no home-field advantage in the sim today, at all.** Nothing reads a
home/away flag for anything but scoreboard labeling; `calculateWinProbability` treats
the two ELOs identically. Measured on prod over **687 finals: 50.7% home wins, with
the home team scoring 0.12 BELOW the away team** — a coin flip inside noise. Real
football runs ~54-57%.

Sizing it off the measured transfer rather than guessing: the
**rating-multiplier → win-probability transfer is 1.619** (a +10% roster-wide
multiplier is worth +16.1pp of win rate). So a target of **~55% home wins** is
**+2.6% on the home team's `gameAttributes`**, applied pre-game alongside the other
multiplier layers.

⚠️ It does **not distort the standings**, because every team plays 14 home and 14
away — it makes home games matter without making any team better. Verify that in the
measurement rather than assuming it.

⚠️ Deliberately a flat league-wide nudge, NOT a per-venue one. A venue-scaled home
advantage is the `homeBoost` key from the old branch, and it means "some teams are
simply better", which is a competitive-balance change wearing a stadium costume. Venue
character belongs in the weather, which is symmetric.

## Weather does not have to suppress (owner, 2026-08-19)

⚠️ **Measured on the first complete draft: 92% of every effect in the file was a
penalty.** In the weather layer `passAccuracy` was lowered in **40 of 40** conditions
and `deepPassChance` in **32 of 32**. Not one condition in the league helped anything —
inherited without noticing from real weather, which almost only ever subtracts.

Three consequences, all bad:
- weather can only **subtract** offense, and subtracts more as the anomaly climbs, so
  **Criticality becomes a scoring drought instead of a spectacle**;
- a "pass-favoring venue" is a lie — it only hurts running *more*, so a GM building a
  passing team for one is building for somewhere merely less bad;
- 32 places collapse into 32 amounts of difficulty.

Two ways out, both now in use.

**PHYSICAL.** Thin air at altitude carries the ball (Colorado's mountain basin, Mexico
City at 7,300ft), heat thins it the same way (Arizona), a sealed room has no wind at all
(Las Vegas, San Francisco), a tower has a standing updraft (Seattle), and ground that
freezes or bakes hard runs fast (Buffalo, Georgia, Philadelphia).

⚠️ **Note the split, because it explains why the boosts skewed to passing:** weather acts
on the **air**, so it boosts **ball flight** — passing and kicking. The run game is
helped by **surface**, and surface is mostly the venue's permanent character rather than
its weather. The only way weather touches surface positively is by drying or freezing it.

**SUBVERSION.** These are not real places and their weather need not obey. A cavern has
no wind at all, so the best throwing conditions in the league are underground. A Tuesday
on a loop has been *rehearsed*, so nobody is surprised by anything. A hive is the most
coordinated thing alive. Boston's Criticality **snaps to spec** instead of degrading —
every reading exactly nominal, which has never once happened — and that is far more
unsettling than another penalty.

⚠️ A subversion must be **earned by the setting**, not handed out, or the rule stops
meaning anything and every venue drifts toward being pleasant.

Landed: **83% penalties** (from 92%), **14 of 32 venues have a genuinely good
condition**, 11 conditions lift the passing game, and one Criticality condition improves
things. Severity bands and the centered phase bias both held. Pinned by
`test_stadium_weather.py`, which now fails if the league goes back to all-penalty.

## Venue-aware teams (owner, 2026-08-19)

A GM knows their own stadium. Where the venue suppresses the passing game they should
value the run — backs, and tight ends for their blocking — over quarterbacks and
receivers, and lean that way in play-calling too. The inverse where passing is favored.

This is also what turns the residual pass/run tilt from an uncompensated penalty into a
team's identity: the tilt only hurt because nothing adapted to it.

**`stadiumManager.phaseBias(teamId)`** → −1 (favors the pass) .. +1 (favors the run).

⚠️ **MEASURED AGAINST THE LEAGUE, NOT AGAINST NEUTRAL, and this is the load-bearing
detail.** Real weather suppresses throwing far more often than running — fog, wind,
rain, glare and dark all land on the passing game — so the raw reading came out **20 of
32 venues run-favoring against 1 pass-favoring**. Fed to the front office that is not 32
identities, it is a league-wide instruction to stop drafting quarterbacks, and it would
devalue the position the sim measures as the most impactful (+2.52 wins). Centering
turns "everywhere is hard to throw in" into "this place is harder to throw in than most",
which is the only version a GM can act on. After centering: **11 run-lean, 11 pass-lean,
10 neutral, summing to zero.**

**BUILT — roster valuation.** `positionValue(player, venueBias)` scales RB/TE against
QB/WR by `VENUE_POSITION_WEIGHT` (0.10), reached through `perceivedValue`, so every
fill, upgrade, re-sign and draft-board call inherits it. ⚠️ Deliberately modest: a team
plays 14 home and 14 away, so a roster fitted hard to one venue is paid for in the other
half of the season. At full bias a quarterback still outranks a back — the weight tips
close calls and never inverts the hierarchy, the same bar the sentiment tilt is held to.
Regression: `test_venue_roster_fit.py`.

**NOT BUILT — play-calling.** The lever is `runPassRatio`, consumed in
`_applyGameplanMods`. Add the venue lean as its own multiplicative term there so it
composes with the existing mid-game adaptation and can be flagged off independently.
⚠️ Apply it to **BOTH teams**, not just the home side: the conditions are symmetric and
any coach can read them. The home team's edge should come from having the right
PERSONNEL for the place, which the roster half above already provides — giving them the
play-calling read as well would double-count it into a second, unmeasured home
advantage. Build it with the modifier wiring so the two can be measured together.

## Chrome answers the weather — as ONE family (owner, 2026-08-19)

⚠️ **Chrome is not only weather counters.** Its backbone is **straight skill boosts** —
fit an augment, the player is better, full stop — and that is what a fan reaches for by
default. Everything below is a SECOND family alongside that one. Weather does not
redefine chrome and is not its reason for existing; it gives one family of augments a
concrete, repeating trigger. ⚠️ The conditional family also needs a genuinely higher
ceiling than the straight one, or nobody takes it: an augment carrying variance and
requiring a read loses to a reliable one at equal expectation. Same axis the cards
already run on.

⚠️ **As built, weather is pure input with no counterplay** — it happens to you and you
take it. Chrome (`docs/CHROME.md`, doc-only, staged behind Stages 1-2) is the answer,
and the two dovetail better than either was designed for.

**Why it fits.** Chrome is the fan's lever on the sim, and weather is **announced before
kickoff** — so a fan can read the slate, see their team is at Bedrock Cavern in the
dark, and chrome their receiver with low-light optics. That is a decision with a visible
input and a visible outcome, which is what a metagame lever needs and what chrome
otherwise lacks a concrete trigger for.

**The fiction is already correct.** The same anomaly that degrades the Cores'
reconstruction — which is *why* the weather worsens as the aggregate climbs — is the one
handing players the means to operate in it. One force causes the problem and the
adaptation, and both get louder together. At Criticality the field is barely playable
and the chromed are the only ones who can work in it.

**The mapping is one-to-one**, because cybernetic augmentation is sensory and physical
adaptation and these keys are sensory and physical conditions:

| condition | the chrome that answers it |
|---|---|
| `visibility` | optical implants — low-light, thermal. The most obvious augment in the game |
| `footing` | grip actuators, gyroscopic balance |
| `fumbleRate` | tactile feedback, grip |
| `passAccuracy` | targeting assist, a stabilized arm |
| `deepPassChance` | arm augment |
| `sackRate` | threat detection, reaction |
| `fgAccuracy` / `puntDistance` | gyroscopic leg |
| `paceMod` | lungs, for thin air and heat |

⚠️ **Weather chrome must be CONDITIONAL — it pays only in the conditions it is for.**
That is what makes it a read rather than a flat upgrade, and it is the same shape the
card system already uses for its higher-ceiling effects. A fan who chromes optics for a
dark venue and then watches their team play three clear weeks has made a bad read, and
that is the point.

⚠️ **It must not fully negate the weather, or the two features cancel and both stop
mattering.** Proposal: ordinary chrome restores *toward* baseline and is capped there —
a player with optics is as good in the dark as they would be in daylight, never better.
**Owner call needed**: whether awakened / Criticality-tier chrome may EXCEED baseline,
i.e. a player who is genuinely better in the dark than in the light. That is the Monstars
fantasy and the strongest version of the spectacle, but it is also the one thing that
can undo the fairness work above, so it should be deliberate.

**It composes with the roster fit already built.** The GM builds for the venue
(`phaseBias` → positions), the fans chrome for the venue (conditions → augments). Two
layers reading the same input from opposite ends, which is exactly the fans-versus-Cores
frame the metagame plan is built on. It also gives each team a visible chrome identity
over time — the team in the cavern all run optics — which is character emerging from
mechanics rather than being authored.

## Remaining open decisions

1. **Alternate formats.** Frames, darts and chess clock each change what a modifier
   means (`puntDistance` matters less in darts, where hoops decide it). Darts is
   already excluded from Criticality chaos; decide whether weather follows it.
2. **Cards.** Weather-keyed effects are an obvious future card family ("scores in
   Severe weather or worse"). Out of scope here, but the persisted `games.weather`
   row is what would make it possible later, so persist it in the shape a card
   calculator could read.
