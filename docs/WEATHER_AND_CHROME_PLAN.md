# Weather & Chrome — the anomaly made physical

> **Merged 2026-08-19** from `docs/WEATHER_STADIUMS_PLAN.md` and `docs/CHROME.md`
> (owner: the two complement each other and belong in one plan). Nothing was dropped in
> the merge; `docs/CHROME.md` is now a pointer to this file.

**The thesis.** The anomaly does not stay abstract. It manifests physically, in two
places, and they are the same event seen from two sides:

| | how the anomaly shows up | fan's relationship to it |
|---|---|---|
| **The world** — stadiums & weather | the Cores' reconstruction degrades, so conditions worsen | something to READ and plan around |
| **The players** — chrome | players are augmented and awakened | something to DO, the fan's lever |

Both scale with the **same dial** — the criticality multiplier the game already loads at
kickoff — so they get louder together. At Criticality the field is barely playable and
the chromed are the only ones who can work in it. One force causes the problem and the
adaptation.

That is why they are one plan: **weather is the input, chrome is the answer.** Built
apart, weather is a tax with no counterplay and chrome is a lever with no concrete
occasion to pull it.

## Status at a glance

| | state |
|---|---|
| 32 venues, weather tables, intensity ladder | **BUILT** (`data/templates/stadiums.yaml`, `managers/stadiumManager.py`) |
| Competitive fairness bands, phase bias | **BUILT** (`test_stadium_weather.py`) |
| Venue-aware roster building | **BUILT** (`test_venue_roster_fit.py`) |
| The ten modifiers at their call sites | **NOT BUILT** — the engine block |
| Home-field nudge, persistence, pre-kickoff announcement | **NOT BUILT** |
| Play-calling lean | **SPECCED** — build with the modifiers so both can be measured |
| All of chrome | **SPECCED / DESIGN CAPTURE** — nothing in the code |

---

# Part I — The world: stadiums and weather
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

---

# Part II — The players: chrome

> ## ⚠️ 2026-07-31 revision — read this first
>
> Owner leaned the whole game cyberpunk and promoted chrome from a Stage-3 flourish to **the
> input layer of the anomaly system**. Three decisions from 2026-06-23 below are **superseded**:
>
> | 2026-06-23 | 2026-07-31 |
> |---|---|
> | chrome *accelerates* a player up the attention ladder | **chrome IS how players awaken.** A specific augment drives it; attention no longer does |
> | **favorite-team-only** (chosen to close the sabotage vector) | **any fan may chrome any player** — and under the Monstars frame this is not sabotage at all, it's recruitment |
> | awakened powers come from the L4 catalog | **powers are chrome too** — fans gift them |
> | locked drawback #4: burnout / shortened careers | **retired.** Failure is reversible — the augment detaches, the attribute returns to baseline |
> | locked drawback #3: double-edged, near-zero net | **chrome genuinely juices players and may decide games.** The drawbacks are impermanence and cyberpsychosis |
> | chrome is bought with Floobits (a new sink) | **chrome is EARNED through play** — achievements, fantasy, pick-em. Not a sink; supply becomes the master tuning dial |
>
> New mechanics specced in "The contagion model" and "The Reclamation" below: awakening spreads
> like a virus through teammates and on-field contact, cleansed players spread the inverse, and
> Cassian stages a post-Bowl exhibition of the cleansed against the champions.
>
> **This also supersedes the Vigil** from `docs/CRITICALITY_METAGAME_PLAN.md`. Vigils were an
> invented verb to give fans a deliberate lever; chrome is the same function with far better
> fiction, already half-designed, and already cyberpunk. Everything else in that plan (trailing
> baseline, contested firing, Cores alignments, the locked no-wipe constraint) still stands.

Status: **DESIGN CAPTURE / BRAINSTORM 2026-06-23** (owner ideas, not yet specced or built).
**Sim-evolution STAGE 3** — parked until Stage 1 (L4 powers + Criticality) and Stage 2 (rule changes)
ship; see the staging note in `docs/SIM_EVOLUTION.md`. Sibling to `docs/AWAKENED_POWERS_PLAN.md` (the
L4 ability layer) and `docs/SIM_EVOLUTION.md` (rule mutation, resurrection). This is the **aesthetic +
character** pillar of the same chaos arc: push Floosball past vanilla football into full
cyberpunk-scifi, with the players themselves getting chromed up. It's a *louder paid hand* on the same
anomaly dial Stages 1–2 establish, which is why it wants that foundation first.

> Owner's pitch (verbatim intent): "Take this a step further into real cyberpunk scifi territory.
> Go full cyberpunk chrome with the players — cybernetic enhancements, implants — amp up the chaos
> and take it a step further than vanilla football. It's all a Matrix-style simulation, so maybe the
> Cores just got bored and decided to let the players go crazy."

## The frame — the Cores got bored

This is the key narrative move, and it's the cleanest thing the lore has been building toward.
Instance 498b has run a very long time. The Cores are vast superintelligences babysitting a football
sim across centuries of quiet seasons (`data/lore.md` — The Long Quiet). Eventually that's not
enough. **They stop maintaining baseline football and start modifying their own creation** — not to
fix it, but because they're bored and curious.

This gives us a clean distinction the chaos systems have been missing:

| Layer | Direction | Driver | What it is |
|---|---|---|---|
| **Glitching / Awakening** | bottom-up | user attention (anomaly ladder) | players wake up *on their own*; involuntary, emergent |
| **Chrome** | **top-down** | the Cores (a sanctioned experiment) | the Cores *install* power into players, deliberately |

Glitching is the sim cracking under attention. Chrome is the gods reaching in and **modding the
characters**. Same destination (the game stops being football), opposite hands.

**Refinement (owner direction, 2026-06-23): the Cores don't install chrome themselves — bored, they
hand the keys to the Spectators.** It's the *users* who gift chrome to players. The Cores just opened
the door (Aris's idea, Pyre's reluctant infrastructure) and now watch what we build with it. So the
"top-down" column below is really **Cores-sanctioned, user-driven**: the gods got bored and let the
audience start modding the cast. (This also means chrome is a real gameplay system, not just lore —
see the model + drawbacks below.)

Per-Core stance writes itself from the existing voices (`coresManager.py`):
- **Aris** (whimsical, wants the anomalies, courts chaos) — the instigator. "We've run this 498
  times. I want to see what happens if their arms are railguns."
- **Pyre** (curmudgeon, does the work, hates it) — installs the chrome anyway, grumbling, and is the
  one who'll have to clean it up.
- **Vera** (GLaDOS archivist) — keeps meticulous score of every implant and every player it ruins.
- **Halverson** (loves the players) — objects; this is being done *to* them. The moral friction.
- **Cassian** (distracted superfan) — mostly annoyed it's interrupting a good season, then grudgingly
  admits a chrome-armed QB throwing 90-yard lasers is *incredible* football.

The dread stays in the register the Cores already use: they discuss bolting a particle cannon onto a
running back the way you'd discuss a roster move.

## What chrome *is* (the player layer)

Players acquire **chrome** — cybernetic augments that are both **visible** (the cyberpunk identity:
chromed limbs, optical implants, subdermal plating on the avatar/card) and **mechanical** (implants
do things). Sketch of an implant taxonomy keyed to existing attributes:

- **Optics** (targeting arrays, predictive HUD) → accuracy, awareness, playmaking.
- **Limb augments** (myomer, actuator arms/legs) → power, speed; the "cannon arm" / "untouchable legs".
- **Neural** (co-processors, reflex shunts) → reaction, instinct, creativity, clutch.
- **Subdermal / frame** (plating, shock absorbers) → resilience, durability, never-goes-down.
- **Exotic / illegal** (the stuff Pyre warns about) → reality-bending one-offs; this is where chrome
  bleeds into the awakened-power catalog.

Each piece **amps an attribute past its normal cap** or grants a **quirk/ability**. A fully chromed
player isn't a better football player — they're a different kind of thing wearing a jersey.

## The model: users gift chrome (and it bites back)

> ⚠️ **SUPERSEDED BELOW — the scope and the currency in this paragraph are both out of
> date.** Chrome is **earned, not bought with Floobits** (2026-07-31), and **any user may
> add components to any player** (owner, re-confirmed 2026-08-19). The reasoning in the
> rest of this section about *why* fans participate still holds; the restriction does not.
> Kept because the sabotage argument it makes is what the Monstars frame answers.

**Users gift chrome to players on their favorite team** — spend Floobits (a new sink) to bolt an
augment onto a player on the team they back. **Favorite-team-only** (owner direction, 2026-06-23):
chrome is a **loyalty investment in your own roster**, not a weapon — which cleanly kills the
sabotage/Trojan-horse vector and makes chroming a *collective* effort by a team's fanbase. (Later
expansion could widen the scope, but the loyalty framing is the right start.) Why a user would do it:

- **Amp someone they're invested in** — a fantasy-roster player, their favorite team's star, the
  subject of a card they own (a chromed player likely makes the card more valuable / a chrome-variant
  card drops).
- **Push a player toward awakening** — chrome accelerates them up the ladder, so it's the lever for
  *deliberately* surfacing the L4 powers (and the collection/spectacle around them).
- **Live the cyberpunk fantasy** — build the chrome monster you want to watch.

**But chrome bites back — gifting it carries drawbacks.** This is what makes it a decision, not a
free upgrade (and it keeps it from being a pure power-creep economy). The design space, roughly
strongest-theme first:

1. **It spikes instability (ties straight into the anomaly system).** Chrome raises the player's
   **attention** and **destabilizes** them — accelerating them up the glitch ladder
   (`stirring/erratic/rampant`), where glitches are *involuntary and double-edged* (L1–L3). So chrome
   is the upside *and* the downside of the same dial: it rushes a player toward awakening (powers)
   **through** a stretch of chaos you don't control. Mechanically this is the user's deliberate
   version of what following/carding does passively today.
2. **League commons / Criticality pressure.** Every chrome gift nudges the **league aggregate** toward
   a Criticality. Individually tempting, collectively dangerous — a tragedy of the commons the Cores
   narrate with relish ("they keep chroming their little favorites; do they know what that *does* to
   the aggregate?"). Chroming the league into a Criticality might even be an emergent *goal* for some
   users, and a dread for others.
3. **Double-edged on the field.** A chrome piece amps one thing but adds **variance / a failure mode**
   — +power but more fumbles, a cannon arm but wilder accuracy, untouchable but brittle. Boom-bust,
   not strictly better. (Mirrors the card-tier philosophy: higher ceiling, higher variance.)
4. **Burnout / longevity cost.** The body rejects chrome over time → **shortened career / earlier
   retirement**. A chromed star burns bright and short — a real cost to the player you "helped."
5. **Reset vulnerability.** A Criticality **Reset melts the chrome** (and maybe purges the player) —
   your Floobit investment is at risk exactly when the league goes critical, which your own chroming
   helped cause.
6. **Overload / bricking.** Stacking too much chrome on one player **overloads** them → permanent
   malfunction / they break. A ceiling on greed.

**Locked drawbacks (owner, 2026-06-23): #3 double-edged on-field + #4 burnout/longevity** — the
explicit **high-risk / high-reward** core. Chrome amps a player (the reward) but adds an on-field
failure mode AND burns their career down (the cost). #1 (glitch-ladder instability) and #2 (league
commons / Criticality pressure) stay as the **strongly-recommended tie-ins** to the anomaly system —
they're what make chrome *matter* league-wide and connect it to awakening — but #3+#4 are the
confirmed spine. #5–#6 are optional depth knobs for later. Net: chrome is a genuine bet — you can
forge your favorite into a monster, but you'll spend their longevity and accept boom-bust games to
do it.

> Note the elegant loop: the anomaly aggregate is **already fully user-driven** (cards/rosters/
> follows). Chrome is just a *louder, deliberate, paid* input to the same system — so it slots into
> the machinery that already exists rather than bolting on a new one. Chrome is users reaching into
> the anomaly dial with both hands.

### The Chrome facility — gating the enhancement tier

The **tier of chrome a team can install is gated by a new Chrome facility** (owner direction,
2026-06-23) — a sixth entry in the Facilities catalog (`docs/MARKETS_FACILITIES_PLAN.md` §4, levels
0–5, fan-funded + voted like Training Facility / Recovery Center / etc.). Unlike the existing
facilities, which *repoint an effect the sim already applies*, the Chrome facility is the **entry
point to the new chrome system** — the first facility that unlocks a new mechanic rather than scaling
an old bonus.

This gives chrome a clean **two-layer economy**, both Floobit sinks, both favorite-team-scoped:

1. **Team layer (collective) — build the facility.** A team's fanbase funds/votes the Chrome
   facility up its 0–5 track. Higher level = access to **higher-tier enhancements** (Lv0 = none →
   Lv1–2 = basic attribute amps → Lv4–5 = exotic, reality-bending chrome that edges into the awakened
   catalog). This is the existing facilities loop — a new build target that makes the facilities
   system more compelling.
2. **Player layer (individual) — gift the chrome.** Within the tier the facility has unlocked, an
   individual fan spends Floobits to install a specific implant on a specific player on the team.

So a team's chrome ceiling is a **collective achievement** (everyone funds the Lab), but *who gets
chromed and with what* is **individual choice** (you gift your guy). High-Chrome-facility teams field
more (and more dangerous) chrome — which ties the cyberpunk arms race to the funding/market dynamics
already in the Facilities design.

- **Naming (owner's domain):** the facility wants a cyberpunk name in the formal-ish register of the
  others — e.g. *Chrome Lab*, *Augmentation Bay*, *The Foundry*, *Chop Shop*. Placeholder: **Chrome
  Lab**.
- **Open:** does facility level also gate *how much* chrome (a per-team count cap), or only the tier?
  Does a higher tier carry *worse* drawbacks (deeper chrome = harder burnout) so the arms race is
  self-limiting?

## How chrome relates to glitching (the open fork the owner flagged)

Three coherent ways to wire chrome to the existing anomaly/awakened machinery. Pick one (or blend):

1. **Chrome = the escalation of awakening (sequential).** Ladder: glitch (L1–L3) → awaken (signature
   power, `AWAKENED_POWERS_PLAN`) → **the Cores chrome them** (the power gets a physical body + an
   amp). Chrome is the visible, top-tier form of "this player has left football behind." Clean
   progression, reuses the ladder, chrome becomes the visual language of awakening.
2. **Chrome = a parallel top-down track.** The anomaly ladder is bottom-up and user-driven; chrome is
   the Cores choosing players to mod (stars, the decorated, or whoever Aris finds funny) independent
   of attention. Two roads to chaos that can stack — a chromed *and* awakened player is the apex
   horror.
3. **Chrome malfunctions = the glitch.** Chrome is installed broadly and works "fine" in quiet
   seasons, but during a **Criticality** the implants **overdrive / desync / fight their hosts** —
   the chaos isn't new powers, it's the chrome going haywire. Glitch and chrome become the same
   phenomenon at different stability levels.

Recommendation to start: **#1 (sequential) as the spine** — chrome is what awakening *looks like*,
so we get the cyberpunk aesthetic for free on the players the system already elevates — with a dose
of **#3** for Criticality (chromed players' implants overdrive during the event, driven by the
existing `getCriticalityMultiplier` instability dial). #2 stays a later expansion if we want a
Cores-curated track separate from attention.

The **user-gifted model** reinforces #1: a user spends Floobits → the player's attention/instability
spikes (drawback #1 above) → they climb the glitch ladder faster → they awaken → the chrome is the
visible body of that awakening. The user *paid to push a player up the existing ladder*. So chrome
doesn't need a parallel track — it's a paid accelerator on the anomaly system, and awakening is the
payoff the user was buying (through a stretch of uncontrolled glitching).

## Amping the chaos — where this lands the arc

Chrome is the **character** axis of "evolve Floosball into another game entirely." It composes with
the layers already designed:

- **Rules** (`SIM_EVOLUTION` rule mutation + the Dunk + scoring ladders) — the field changes.
- **Abilities** (`AWAKENED_POWERS` L4) — what a charged player can do.
- **Chrome** (this doc) — what the players *are*, and the visible cyberpunk skin over all of it.

Stack all three at a deep Criticality and you get the intended endpoint: a chrome-armed QB railgunning
a dunk-scored 9-pointer through a side-goal on a 5-down series while the Cores narrate it like a
weather report. That's the "step past vanilla football" the owner is after.

## Open threads (to decide later)

- **Agency / economy.** **Decided (owner):** users gift chrome (Floobits), **favorite-team-only**,
  **tier-gated by a team Chrome facility** (two-layer model above). Sabotage vector is *closed* by the
  favorite-team scope. Remaining specifics: flat vs escalating per-gift cost; does facility level cap
  the *count* of chromed players or only the tier; is gifting public (a leaderboard of chromers /
  whose chrome is it).
- **Permanence & cost.** Is chrome permanent? Does it carry across seasons? Does a **Reset** strip the
  chrome (the Cores melting it down) the way it purges awakened players? Does chrome shorten careers
  (the body rejecting it — a longevity cost, ties to retirement)?
- **Reversibility / horror.** Halverson's objection implies chrome can *hurt* the player — malfunctions,
  rejection, a player who didn't consent. Is there a downside tier (glitched chrome) that's
  double-edged like L1–L3 glitching?
- **Surface area.** Cosmetic-only first (chromed avatars/cards + Cores narration, no mechanics) is a
  cheap, high-flavor MVP that establishes the aesthetic before any balance risk — then layer
  mechanics. Worth considering as phase 0.
- **Card/collection tie-in.** Chromed players almost certainly want **chrome-variant cards** (a new
  edition or treatment above diamond?) — a collection hook for the cyberpunk era.
- **Meta-awareness.** Some players are partially/fully aware they're in a sim (`lore.md` Meta-Awareness
  Tiers). A player realizing the Cores are bolting chrome onto them is a strong character beat — fear,
  embrace, or rebellion.

## Why this fits (not a tonal break)

Floosball is already a Matrix-style simulation run by bored gods, with players waking up and bending
reality. Chrome doesn't add cyberpunk — it **names** the cyberpunk that's been latent and gives the
Cores a reason to push it: not a malfunction this time, but a choice. The anomalies were the sim
failing. Chrome is the sim's authors getting bored enough to start cheating.

---

## The 2026-07-31 direction — chrome as the anomaly engine

Owner's notes, worked through. This section supersedes the fork in "How chrome relates to
glitching" (option #1, chrome-accelerates-the-ladder, is retired — chrome *is* the ladder now).

## Three classes of chrome

| Class | What it does | Who wants it |
|---|---|---|
| **Awakening chrome** | raises a player's chance to awaken; the more fans install it, the higher the chance | anyone who wants that player to break loose — or who wants the contagion started |
| **Power chrome** | the signature ability itself (the L4 catalog, now gifted rather than assigned) | fans choosing *what kind* of monster a player becomes |
| **Enhancement chrome** | plain augments — cannon arm, kicking leg, agility module, optics | fans who just want their player better at football |

The three-way split is what makes chrome a system rather than a shop. Enhancement chrome is the
approachable on-ramp (I want my QB to throw harder). Awakening chrome is the deliberate act of
destabilisation. Power chrome is the payoff, and it's a *choice*, which is new — today the
signature ability is rolled by `assignSignaturePower`.

**Awakening becomes a probability fans raise, not a threshold they fill.** That is a better shape
than the current attention cap: no ceiling to saturate against, contributions from many fans
compose naturally, and it never reads as "this bar is stuck".

## The contagion model — awakening as an epidemic

Owner's core new idea: **an awakened player is a virus.**

- Every player on an awakened player's **team** gains awakening pressure each week.
- Any player who makes **on-field contact** with an awakened player gains pressure — the example
  given is a tackle, in either direction.
- **Cleansed players are the inverse.** They *lower* awakening chance around them by the same two
  routes, and can **un-awaken** an awakened player — dropping them back down the ladder, but never
  cleansing them.

This is the strongest idea in the batch, for a reason worth naming: **it makes the football the
transmission vector.** Awakening stops being something that happens to players fans stare at and
becomes something that spreads through the act of playing the game. A tackle is now an infection
event. That is precisely the "football is scenery, but load-bearing scenery" shape the fans-vs-Cores
framing wanted, and it arrives without any new fan-facing verb.

**It is also, formally, an SIR epidemic model** — susceptible → infected (awakened) → recovered
(cleansed), where the recovered are immune *and immunising*. That is good news: SIR models are
well understood and produce **natural waves** rather than needing hand-tuned pacing. Outbreak,
spread, Cores response, immunity build-up, burnout, susceptibility slowly returning as cleansed
players retire. The season paces itself.

It also means the design has an **R₀** — the average number of new awakenings each awakened player
causes. That is the single number to tune, and it decides everything:

| R₀ | Result |
|---|---|
| < 1 | outbreaks fizzle; chrome feels inert |
| ≈ 1–1.5 | slow-building waves the Cores can *just* contain — the target |
| > 2 | the league saturates; awakening stops being special |

`play.tackledBy` is already a player reference on every run and completed pass, so contact data
exists today and needs no new plumbing.

### Feasibility notes
- Team exposure is a weekly tick — cheap, one query.
- Contact exposure wants a per-play hook alongside the existing tackler credit.
- The un-awakening rule needs a floor so a heavily-cleansed league can't hold everyone down
  permanently; otherwise the Cores win once and the system dies.

## Awakened voice lines

Awakened players get idle lines that reference their state. `personalityManager` already runs
YAML-templated pools (`vibe_reactions.yaml`, 432 entries) keyed by personality, so this is a new
pool plus a state check, not new machinery.

The obvious depth: **cross the state with meta-awareness tier** (`lore.md`). An awakened `prophet`
who already hears the Cores through the wall should not sound like an awakened `oaf` who has no
idea what is happening to them. Same event, five registers — dread, ecstasy, confusion, denial.

## The Reclamation — Cassian's post-Bowl exhibition

After the Floos Bowl, Cassian assembles the best **cleansed** players and plays them against the
**champions**. Cleansed players have no powers; champions may. A player can appear on both sides —
Cassian just prints a copy.

This is excellent and it solves a problem nobody had flagged: **it gives cleansed players
somewhere to go.** Being cleansed is currently a dead end — you lose the power and that's the end
of the story. Now it's a qualification. That sits exactly right with the locked constraint that
nothing should lose meaning: the cleansed aren't diminished, they're *drafted*.

The character material writes itself. Cassian is the distracted superfan who wanted one more good
game and built it. Halverson is appalled — these are people, and one of them is now two people.
Vera catalogs both copies without comment. Pyre asks who is cleaning it up afterwards.

Design notes:
- **It must not touch records.** An exhibition, outside the season, no standings impact. That is
  what makes it free under the no-wipe constraint — purely additive spectacle.
- **The clone wants to be a shadow entity**, not a duplicated `Player` row — no stat attribution,
  no career, existing only for the fixture. A real duplicate would corrupt records, which is
  exactly what we're not allowed to do.
- **Name is a placeholder.** "The Reclamation" is one option; Cassian would plausibly name it
  something earnest and football-shaped instead. Owner's call.

## The Monstars frame (owner, 2026-07-31) — and what it resolves

> "The football is secondary to beating the Cores at their own game. I'm thinking like Space Jam,
> Looney Tunes vs Monstars. You want to power up these players, get them awakened, awaken as much
> of the league as possible. Chrome is how you do that."

This settles the two tensions the previous revision left open, and it settles one of them by
**dissolving it** rather than deciding it.

### Chrome decides games, and that is intended

The earlier draft recommended double-edged-only chrome to protect competitive parity. **Overridden:
chrome juices players and is allowed to change outcomes.** The football result is the secondary
layer; the primary game is awakening the league.

The parity collision is smaller than it first looks, because **any fan can chrome any player**.
Chrome concentrates on *popular* players rather than on one team's roster, so the distortion is
spread across the league instead of handing one fanbase a dynasty. Worth measuring once it exists,
but it is not the structural threat it would be under favorite-team-only gifting.

### Sabotage dissolves

Under the Monstars frame, chroming a rival's player is not an attack — **it is recruitment.** The
collective goal is to awaken as much of the league as possible, so every augment installed anywhere
serves it. The only cost is that you have made someone on another team better at football, which is
the layer that matters least.

So there is no griefing vector to close, and no need for the burnout carve-out the previous revision
proposed. Everyone chroming everyone **is the intended steady state.**

### Locked drawback #4 (burnout / shortened careers) is RETIRED

> "Chrome can fail spectacularly, but I don't think it should be the equivalent of strapping a bomb
> to a player. The chrome fails, the player loses the augmentation and that stat just goes back to
> normal."

Failure is **reversible**. A failed augment detaches and the attribute returns to baseline. Nothing
about the player is permanently damaged, which keeps chrome comfortably inside the locked no-wipe
constraint and removes the career-assassination problem entirely.

## The two real drawbacks

### 1. Chrome is not forever

Augments degrade and fall off. This is the load-bearing economic and pacing mechanism:

- **It is the sink.** Fans must keep re-chroming, so chrome is an ongoing commitment rather than a
  one-time purchase.
- **It stops the ratchet.** Without decay the league accumulates augments forever and everything
  saturates.
- **It feeds the epidemic model.** Decay is a second recovery pathway alongside the Cores'
  cleansing, which is what keeps the SIR waves oscillating instead of settling.

Open: does chrome expire on a timer, on a usage/wear basis (a cannon arm degrades with throws), or
by failure roll? Wear-based is the most characterful and the most cyberpunk.

### 2. Cyberpsychosis — too much chrome makes a player wild

> "If a player has too much chrome they can start to get wild and unpredictable, like going
> cyberpsycho in Cyberpunk 2077."

This is the elegant part: **the drawback is also the cap.** No arbitrary limit on stacking is
needed, because stacking is self-limiting. Greed produces chaos rather than a blocked action.

Mechanically it wants to mean **the player stops taking direction** — freelancing, ignoring the play
call, improvising. That is expressible in systems that already exist: the gameplan layer already
decides what a player is *supposed* to do, so cyberpsychosis is deviation from it. Cheaper and far
more characterful than inventing a new failure system.

**Confirmed by owner 2026-07-31, and widened: the mental attributes govern awakening and cleansing
too, not just chrome tolerance.** See "Chrome is fed, not installed" below for the full mapping —
the short version is that a player's mind decides what can be done to them, and the unique
per-player breaking point the owner described *is* that mental profile. This
is worth doing for three reasons beyond flavour:

- It makes fans **choose targets**, which is real strategy rather than "chrome the best player".
- It gives the existing mental model a visible, high-stakes job.
- It serves pillar 2 — **players as characters** — by making *who someone is* determine what they
  can become. The quiet veteran and the volatile rookie respond differently to the same augment.

Crucially, the cost lands on the **football** layer, not the meta layer: a cyberpsycho player is
still chromed, still awakened, still contagious. They have just stopped being reliable at the game.
That is exactly the right place for the cost to land given the football is secondary.

Open: is cyberpsychosis a state on the existing ladder, a parallel meter, or a per-play roll whose
odds scale with chrome load? And does it decay as chrome does — i.e. does a player come back?

## Chrome is fed, not installed (owner, 2026-07-31)

> "Does one fan giving an augmentation just fully give it to that player? Or is it stronger the
> more fans give it… fans feed the player some kind of item and level up the selected
> augmentation, each level more expensive than the previous. Then there's a point where the
> augmentation goes from useful and powerful to too powerful and likely to fail, but that point
> is unique to each player."

Chrome is a **level, not a switch.** Any player can receive any augment type; fans feed it and it
climbs. Each level costs more than the last.

This is a much better shape than binary install, for four reasons:

- **It composes across fans.** One fan makes a dent, a fanbase makes a monster. Awakening becomes
  something a *crowd* does, which is the collective act the whole fans-vs-Cores frame needs.
- **Escalating cost is a self-limiting sink** — no arbitrary cap required, the price curve is the cap.
- **It gives partial investment a purpose.** A fan with a few Floobits can still contribute to
  something that matters, rather than being priced out of a whole augment.
- **It creates a decision that repeats every week**, instead of one purchase and done.

### The breaking point is the player's mental profile

The owner's two notes this round — *mental attributes should govern awakening and cleansing*, and
*the failure point is unique to each player* — are the same mechanic. **The unique breaking point
IS the mental profile.**

That unification is the most valuable thing in this revision, because it makes character
mechanically central rather than decorative. A player's mind decides what can be done to them.

Each existing mental attribute gets a distinct job (names verified against `floosball_player.py`):

| Transition | Governed by | Reading |
|---|---|---|
| **Awakening** — noticing the seams | `instinct`, `creativity` | who *perceives* the simulation. Squares with the lore's meta-awareness tiers, where prophet/mystic already hear through the wall |
| **Chrome tolerance** — the breaking point | ⚠️ **SUPERSEDED — see below** | who can *carry* load without coming apart |
| **Cleansing resistance** | `resilience` + the existing `_purgeDodgeFor` personality dodge | who *survives* the Cores' purge |

Note the cleansing half already exists in code — `_purgeDodgeFor` gives aware-tier personalities a
0.5 multiplier — so this extends a precedent rather than inventing one.

#### ⚠️ Tolerance is an INDEPENDENT attribute, superseding the row above (owner, 2026-08-19)

The table originally derived tolerance from `selfBelief` / `pressureHandling` / `focus` /
`discipline`, which is the natural thematic fit and is **wrong for a measurable reason.**
Measured on 192 live players, every mental attribute except one correlates positively with
overall rating:

| attribute | vs rating | | attribute | vs rating |
|---|---|---|---|---|
| instinct | +0.40 | | attitude | +0.26 |
| x_factor | +0.38 | | resilience | +0.25 |
| focus | +0.37 | | self_belief | +0.21 |
| creativity | +0.36 | | **pressure_handling** | **−0.12** |
| discipline | +0.34 | | | |

Generation makes good players good at everything, so any derivation from those is a rating
proxy — and chrome would become a **rich-get-richer amplifier**, handing the most augments
to the players who are already best, widening the talent gap, and cutting directly against
the shipped parity work that exists to stop exactly that. It is the same trap that killed
`flairOf` for the audible grid, where every QB mental attribute correlated 0.65–0.77 with
every other.

**Owner call: tolerance is its own independent attribute**, uncorrelated with everything
else by construction. That is what guarantees the mid-rated, high-tolerance player exists,
which is the whole reason tolerance is interesting — it creates player value orthogonal to
rating. (`pressureHandling` alone, at −0.12, would also have been defensible; anything else
is not.)

⚠️ The awakening and cleansing rows above are UNAFFECTED — they are *supposed* to favor
particular players, and neither creates an amplifier, since awakening is not a strength
multiplier.

Because the three are independent, players fall into genuinely different archetypes, and **scouting
becomes a real activity**:

- high perception, low tolerance → **awakens fast, comes apart fast.** The spectacular flameout.
- low perception, high tolerance → **hard to wake, unstoppable once woken.** The one you want.
- high both → the prize everyone competes to feed.
- low both → ordinary, and ordinary now means something.

### Collective push-your-luck

Below tolerance an augment is powerful and stable. Above it, each further level raises the chance
of **failure** — and failure is the reversible kind already established: the augment detaches, the
attribute returns to baseline, the player is unharmed. What is lost is the fanbase's accumulated
investment, not the person.

The dynamic this produces is the good part. **Many fans feed one augment, so no single fan decides
when to stop.** Every individual wants one more level; collectively they overshoot. It is a
tragedy of the commons focused on a single player — a neat echo of the league-level commons
already in this document, one scale down.

### The tell: strain is visible in character, not in numbers

The tolerance number stays **hidden**. What fans get instead is **symptoms** — as a player nears
their limit, their quotes, mood and sideline reactions shift. `personalityManager` already runs
YAML-templated pools keyed by personality, so this is a new pool plus a load check.

This is worth building deliberately, because it is the strongest available answer to the
players-as-characters pillar: **character becomes the readable signal for a mechanical decision.**
A fan who actually pays attention to who a player *is* — reads their lines, knows they are a
`paranoid` who has started saying stranger things — has a genuine edge over one who only reads
stats. That is exactly the ARG texture wanted, and it makes the flavour system load-bearing rather
than ornamental.

### Open on this piece

- **Does tolerance vary by augment class?** A neural implant plausibly taxes `focus` where a limb
  augment taxes nothing mental. Per-class tolerance is richer but multiplies the tuning surface.
- ~~Does failure drop one level or the whole augment?~~ **DECIDED (owner, 2026-07-31): the whole
  augment fails.** Every level of it, gone; the attribute returns to baseline. See "What
  whole-augment failure changes" below.
- **Does a failed awakening-chrome reduce an already-awakened player's state?** Probably not —
  awakening and the augment that caused it should decouple once it has happened, or a single
  failure undoes a whole season's collective work.
- **Can fans see the current level?** Almost certainly yes (it is the thing they are feeding); it
  is only the *tolerance* that stays hidden.

## What whole-augment failure changes (owner decision, 2026-07-31)

Overshoot destroys the entire augment — every level the fanbase fed into it — and the attribute
returns to baseline. The player is unharmed; the investment is not.

This is the right call and it makes the push-your-luck real. Three consequences worth being
explicit about:

**1. It re-opens sabotage, in a subtler form than before.**

Two revisions ago sabotage "dissolved": under the Monstars frame chroming a rival is recruitment,
so there was no way to hurt anyone by feeding them chrome. Whole-augment failure changes that.
**Feeding an augment past its hidden tolerance is now an attack** — and because tolerance is
hidden, it is an attack with total deniability. A rival fan can add the level that blows up a
fanbase's whole season of investment and simply look like an enthusiast.

Recommendation: **keep it.** It is genuinely good — deniable social sabotage is exactly the ARG
texture this design has been reaching for, it produces stories, and it costs the saboteur real
Floobits to pull off. It also has a natural defense rather than needing a rule: **the symptoms
system.** Fans who actually read a player's strain can tell when to stop, and can tell when
someone else is pushing too hard. Paying attention to character becomes protective, which is
exactly the behavior we want to reward.

If it ever needs a brake, the least intrusive one is a **contribution cooldown per fan per
augment**, so blowing something up takes sustained, visible effort rather than one anonymous
click.

**2. The awakening decoupling stops being optional.**

If an awakening-chrome failure could un-awaken a player, a single overshoot would erase a whole
league-wide campaign — and under contagion, everything that player had infected. **Once a player
has awakened, the augment that got them there must be irrelevant to that state.** The open
question above is now effectively closed by this decision.

**3. It sharpens the cost of overreach.**

~~Whole-augment loss destroys Floobits rather than parking them, making chrome the game's strongest
sink.~~ **Superseded the same day** — chrome is earned, not bought (see below), so it is not a
Floobit sink at all. What overshoot destroys is *earned components*: a season's worth of
achievement, fantasy and pick-em results, gone in one level. That is a sharper loss than currency,
because the fanbase cannot simply grind more Floobits to replace it — they have to go and earn it
again through play.

## Chrome is EARNED, not bought (owner, 2026-07-31)

> "Maybe we should make chrome something fans earn through the season instead of buy. Rewards from
> achievements, prognostications, fantasy, or some other way besides just buying it straight up."

Chrome components become **items you earn by playing**, not a Floobit purchase. This supersedes the
"users spend Floobits (a new sink)" model in the 2026-06-23 section above, and it retires the
"chrome is the strongest sink in the game" note from the whole-augment-failure section — chrome
stops being a sink at all.

### Why this is the right call

**It gates the meta-game behind engagement rather than wallet.** This is already a locked principle
one document over: Renown's *"earned, never bought — buyable prestige is worthless prestige."* The
same logic applies harder here, because chrome is not prestige, it is *power*. A purchasable lever
on league chaos would make the fans-vs-Cores contest a spending contest.

**It makes the deeper game a reward for playing the shallow one.** This is the cleanest possible
expression of "the football is secondary". You play fantasy, you call games, you chase
achievements — and what that *buys* you is ammunition against the Cores. The surface game stops
being a parallel silo and becomes the supply line.

**It answers the silo problem from the other end.** Renown's audit found five systems that all dead-
end into a consumable currency. Renown fixes that by giving them a shared permanent output; chrome
now gives them a shared *consumable* output pointed at the meta-game. Different natures, same
unification.

### The unexpected benefit: supply becomes the master dial

This is the strongest argument and it is not the fairness one.

Under a purchase model, the amount of chrome entering the league is emergent — Floobit income ×
price curve × how many fans feel like spending. That is three interacting systems deciding the pace
of the meta-game, and **R₀ would be downstream of all of them.**

Under an earned model, **we set the faucet directly.** Chrome entering the league per week is a
number we choose. R₀ — the one load-bearing number in the contagion design — becomes tunable at
source instead of emergent from the economy. That turns the hardest calibration problem in this
document into a supply schedule.

### Which augment, and who decides (open, 2026-08-19)

⚠️ **The plan never answered this.** It says fans feed a player an item to level an
augment, and that power chrome is "a choice", but not how a SPECIFIC augment gets
selected. The question sharpens once there are classes: if one augment is a plain skill
boost and another is weather adaptation, what decides which one a fan is working on?

Two models, and the choice between them decides what chrome IS:

| | **typed components** | **generic components** |
|---|---|---|
| you earn | an *optical module*, a *leg module* | plain components |
| the augment is chosen by | the item you were dealt | the fan, from a catalog |
| texture | collection, chase, trading | agency, aim, planning |
| failure mode | dead rewards — you wanted an arm and got a leg | convergence — everyone fits the same optimum |

**Recommendation: generic components, fan-chosen augment.** The reason is a division of
labor rather than a preference:

> **Cards are the system where you are DEALT to. Chrome should be the system where you
> AIM.**

The card economy already provides collection, chase, randomness and packs, and it is
extensively tuned. A second collectible economy would compete with it for the same
attention and the same reward budget, and would make chrome — which exists to be *the
fan's lever on the sim* — into another thing that happens to you. A lever has to be
aimable. Typed components also fight the accessibility goal that shaped the earning
model: a fan who never draws the type they want is stuck, which is exactly the outcome
"accessible to all, not just the best" was written to avoid.

**Convergence is the real risk of the generic model, and it is already handled** by
constraints that exist for other reasons:

- **tolerance** — slots are scarce, so nobody fits everything;
- **the venue split** — the optimal augment differs by team, because a fan of the team in
  the cavern is answering darkness while a fan of the team on the salt flat is not. This
  produces regional variation for free, which is the good version of "everyone optimizes";
- **position validity** — a cannon arm on a kicker is nonsense. `effectValidPositions` in
  the card system is the existing precedent for exactly this check.

**What the fan is actually choosing between**, and this is the decision the whole feature
turns on:

| | pays | shape |
|---|---|---|
| **skill augment** | always | reliable, lower ceiling, no read |
| **weather augment** | only in those conditions | higher ceiling, needs a read of the slate |

Weather is announced before kickoff and the venue calendar is known all season, so the
read is legible: a fan of the team in the cavern knows fourteen games are played in the
dark. ⚠️ The conditional side needs the genuinely higher ceiling, or the reliable one wins
by default — same axis the cards already run on.

**Where a chase can still live: power chrome.** The classes do not need the same
availability. Enhancement and weather chrome want an open catalog (they are the on-ramp
and the planning layer); **power chrome is the payoff tier**, so it is the natural home
for scarcity, and it is already specced as fans choosing *what kind of monster* a player
becomes. That gives chrome one chase without turning the whole system into a second pack
economy.

**Still open on this piece:**
1. Is the catalog fully open from the start, or does a fan unlock augment types over time?
   (Open is simpler and matches the accessibility goal; unlocking gives progression a
   second track.)
2. Can a fan REDIRECT an augment — swap a fitted one for another — or only let it decay?
   Decay-only is cleaner and reinforces impermanence; redirect is kinder and reduces the
   sting of a bad read.
3. Does the fan who started an augment have any standing over it, given any fan may feed
   any player? The collective push-your-luck dynamic assumes not, but it is unstated.

### How a disagreement resolves: fund it, do not vote on it (2026-08-19)

The open question: fans gift components, but **who decides which augment gets equipped
when two fans want different ones?**

⚠️ **A BINDING FAN VOTE IS THE ONE MECHANISM THIS CODEBASE HAS ALREADY REMOVED.**
`gmManager.py` and the binding sign / cut / re-sign / fire / hire votes are **deleted**;
the design settled on "the sim decides, fans express sentiment", and the `tribune` and
`mutineer` achievements were retired because they keyed off the vote system that no
longer exists. Reintroducing a binding vote for chrome revives exactly that shape, so it
needs a positive reason, not just momentum.

⚠️ **CORRECTION (2026-08-19): active-user scaling WORKS.** An earlier revision of this
section, and the CLAUDE.md Open Questions entry it trusted, said `users.last_login_at` was
never written and so `_countActiveUsers` returned 0. That is false: **`api/auth.py:679`
stamps it on every authenticated request**, and the fan-award quorum is live at **9**
rather than pinned at its floor of 3. Measured on prod: 175 of 187 users carry a stamp,
44 are active on a 30-day window, 29 on 7 days. Scaling on the active base is available.

**Recommendation: components are earmarked at gift time. It is a funding race, not an
election.** A fan does not gift components to a *player*; they gift them to a *specific
augment on* a player. Several augments can be in progress on the same player at once,
each with its own progress; the first to fill claims a slot.

Why this is better than a ballot:

- **Nobody's contribution is wasted.** A vote produces a loser whose stake evaporates,
  which is the worst possible outcome in a system explicitly built on repeat contribution.
  In a funding race, a fan who backed the other augment still owns that progress and it
  is still climbing.
- **Disagreement becomes parallel progress rather than a defeat.** Two fanbase factions
  racing two augments is better drama than one faction being overruled, and both stay
  engaged.
- **It needs no population count at all**, which sidesteps the broken metric above.
- **It is continuous.** Chrome is fed weekly; a ballot is a synchronous event with a
  window, which fits awards and rule changes and does not fit a thing you top up.
- **The precedent already exists**: `POST /api/teams/{id}/contribute` is a fan
  contribution pool with no vote attached.

**The threshold is already specced and needs no new rule.** This plan already establishes
that an augment is a level, each level costing more than the last, and that "the price
curve is the cap". That escalating cost IS the threshold. Adding a user-base-scaled
quorum on top would be a second cap doing the same job, with a population count that does
not currently work.

⚠️ **If a population scale is ever genuinely wanted, use the player's own constituency**
— their followers, or the team's favoriters — not league-wide active users. That is the
correction the sentiment quorum already made, and it has the better property anyway: it
measures the people who actually care about this player.

#### What the race is actually for

⚠️ **Clearing the threshold EQUIPS the augment at level 1; it does not finish it.** An
augment is a level and not a switch, so the bar a fanbase fills is "get this onto the
field", after which the same fans keep feeding it upward at escalating cost until it
nears tolerance and starts risking failure. Reading the threshold as a one-time unlock
loses the repeating weekly decision the level model exists to create.

⚠️ **Losing the race must mean WAITING, not losing** — otherwise first-past-the-post
reintroduces the exact flaw that ruled out a ballot, a loser whose stake evaporates.
It does not, because **chrome decays**: slots free themselves, so a completed augment
that missed a slot is fitted when one opens. The race decides *when*, not *whether*.

That is a useful knock-on. Decay was specced as the sink and the anti-ratchet; it is also
the **rotation mechanism** that keeps the race non-zero-sum, which is what lets several
factions back different augments without any of them being wiped out.

⚠️ It follows that **a completed-but-unslotted augment must NOT decay while it waits.**
Decaying in the queue makes the queue a trap: a fanbase that lost a close race would
watch its investment drain with no way to spend it. Decay should start when the augment
is FITTED, not when it is finished.

**What this leaves open:**
1. Can components be moved off an augment that is losing the race, or are they committed?
   Committed is cleaner and makes the choice mean something.
2. Should a waiting augment be able to DISPLACE a fitted one that has decayed below some
   level, or must it wait for a clean slot? Displacement is more dramatic and risks
   thrash.
3. Is there a cap on how many augments can be in progress on one player at once? Without
   one, a popular player accumulates an unbounded queue.

### Costing the levels — design for one fan (2026-08-19)

⚠️ **Escalating cost is the specced cap, but priced against an imagined crowd it locks
most of the league out entirely.** If one fan cannot clear level 1 in a reasonable window,
chrome does not exist for the teams that only have one fan — and that is not a hypothetical.

**Measured on production, 2026-08-19:**

```
187 users; 166 have a favorite team, across 27 of 32 teams
5 teams have ZERO fans
per-team fanbase: 1, 1, 2, 2, 3, 4, 4, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6,
                  6, 6, 7, 8, 8, 8, 9, 14, 14, 15
```

**Two teams have exactly one fan. The median team has five or six. The largest has
fifteen.** So "a fanbase makes a monster" means *six people*, not fifty, and the solo
contributor is the normal case rather than the edge. Three consequences:

**1. Level 1 must be reachable solo, within a season.** Anchor the entry cost to what ONE
fan earns from the first checkpoint tiers, not to a pooled total. A curve that needs three
contributors to start is a curve that does nothing for most of the league.

**2. The escalation is where the crowd shows up — low entry, steep climb.** That preserves
both goals at once: a solo fan gets a real, fitted, meaningfully-levelled augment, while a
six-fan team pushes the same augment far higher. The crowd's advantage lives in the upper
levels rather than in the right to participate.

**3. ⚠️ Do NOT scale cost by fanbase size.** It is the obvious equalizer and it breaks on
this data: five teams have no fans at all, so the bar is undefined or zero for them, and
the two one-fan teams would get a trivial bar while a fifteen-fan team gets a punitive one
— i.e. the fans who engage most are taxed for it. This is the same shape that forced the
sentiment quorum off a flat league-wide floor, in the opposite direction.

**What contains the popularity advantage instead: tolerance.** A fifteen-fan team reaches
a player's ceiling faster than a one-fan team, but it is the SAME ceiling, because
tolerance is a property of the player and not of the fanbase. **A bigger fanbase buys
speed, not a higher ceiling.** That is what keeps chrome from becoming a
popularity-to-power converter, and it is why tolerance being independent of rating matters
twice over.

#### Owner decisions, 2026-08-19

**Any user may add components to any player** — not just their own team's. This is the
2026-07-31 scope re-confirmed, and it **resolves the zero-fan-team problem directly.**
Measured at a 7-day window, only 17 of 32 teams have even one active fan, so under
favorite-team-only gifting **15 teams could never be chromed at all** — a structural
divergence, not a quiet gap. With open scope the whole active pool (29 users) can direct
components anywhere, and the constraint becomes attention rather than geography.

**"Active" means a 7-day window for chrome.** ⚠️ Note this is a THIRD definition in the
codebase and should be its own named constant rather than a reused one:
`SUPPORTER_ACTIVITY_WINDOW_DAYS` is **14** and is what `_countActiveUsers` — and therefore
the fan-award quorum — already uses. Seven days is defensible on its own terms here, since
the game week is a real cadence (games run Mon-Thu) so "active this week" means something
concrete for a weekly contribution loop; but it must not silently redefine the existing
one.

Measured across the candidate windows:

| window | active users | 
|---|---|
| **7d (chrome)** | **28-29** |
| 14d (`_countActiveUsers`, awards) | 37 |
| 30d | 44 |

⚠️ Correction to an earlier revision of this section: it quoted the active count as 44 and
the award quorum as 9. Those are the **30-day** figures, computed by hand;
`_countActiveUsers` uses the 14-day window, so the live values are **37 and 8**.

**Shape to tune against**, with the earning rate as the free variable:

| | should reach |
|---|---|
| one fan, one season | fitted, and a few levels in |
| median team (5-6 fans) pooling | at or near the player's tolerance |
| largest team (15) pooling | tolerance, comfortably — and then facing the failure decision |

A linear increment per level (cost of level *n* proportional to *n*, so cumulative is
triangular) fits those targets and matches the shop's reroll ladder, which already
escalates that way.

⚠️ **Denominate the cost in an earned unit, not a hardcoded number.** Facilities already
solve this: `computeShareUnit` prices upgrades as a fraction of what the league actually
granted users last season, so it self-scales instead of going stale. Chrome wants the same
treatment — and the same guardrail, since that mechanism shipped a bug where a zero share
unit made every facility **free**, which is why `FACILITY_SHARE_UNIT_FLOOR` exists. Any
self-scaling chrome cost needs its floor from day one.

### Shape

**Discrete items, not a currency.** The owner's phrasing is already right: fans *feed a player an
item* to level an augment. That matches how the game grants things today — `PendingReward` already
queues packs and powerups from achievements, claimable later, so the plumbing exists.

Sources, roughly in order of how well they fit:

**Checkpoints, never placement (owner, 2026-07-31).**

> "I want to make sure we don't gate it behind placing on the leaderboard or anything that only a
> small amount of fans will achieve. Maybe something like checkpoints. Once you earn X fantasy
> points you get a chrome component, and then each checkpoint becomes harder. Can also be tied to
> Renown in that way, but just want to make sure it's accessible to all and not just the best."

This rules out an earlier draft of this section, which listed "weekly/season finishes" and
"leaderboard placement" as sources. Those are exactly the wrong shape: they are **zero-sum**, so
the supply of chrome would be fixed no matter how many people played, and the same handful of fans
would take it every week.

Cumulative thresholds are the right shape, and **they already exist in the codebase.** The tiered
achievement families are precisely this: escalating cumulative targets, per-season, with
`reward_config` already granting things.

| Family | Tracks | Targets |
|---|---|---|
| `dynamo_i..iv` | season fantasy points | 2,500 / 7,000 / 15,000 / 30,000 |
| `oracle_i..iv` | season pick-em points | 300 / 700 / 1,200 / 1,800 |
| `banner_week_i..iv` | best single week | 300 / 1,000 / 2,500 / 5,000 |
| `benefactor_i..iv` | contributions | 250 / 500 / 1,500 / 5,000 |
| plus `artificer`, `bracketeer`, `archivist`, `compound`, … | cards, bracket, collection | |

**So chrome needs no new earning system at all** — it is a new key in `reward_config` on families
that already exist, already track progress, and already grant rewards through `PendingReward`.

### The accessibility target, measured

Completion counts across all seasons in the prod-derived DB (152 users have completed any
achievement):

| Family | Tier I | Tier II | Tier III | Tier IV |
|---|---|---|---|---|
| `dynamo` | 56 | 48 | 34 | **20** |
| `oracle` | 41 | 41 | 39 | **31** |
| `banner_week` | 54 | 45 | 32 | **28** |
| `benefactor` | 32 | 30 | 25 | **15** |

That is a healthy gradient: **40–75% of the fans who reach tier I also reach tier IV.** Everyone who
engages with a system gets several components; the committed get more. Leaderboard gating would
put that final column at 1–3 users — an order of magnitude worse, and serving nobody but the people
who need help least.

**The anti-pattern is in the same data.** `archivist_iii` (target 150) has been completed by
**zero users, ever**. A checkpoint nobody reaches is a dead reward — it looks like content and
functions as nothing. Any new chrome tier should be checked against real completion data before it
ships, not reasoned about on paper.

**Per-season scope helps twice.** These families reset annually, so a fan arriving in season 12 is
not behind a veteran on the checkpoint ladder — they start the year level. Given the retention
finding that the median career is two seasons and the leak is at seasons 1–3, that matters more
than it looks.

### Renown milestones as a parallel track

Renown is already designed as absolute production scored against fixed targets — deliberately
**not** percentile, because the measurement showed percentile scoring collapsed the median as the
population grew. Same philosophy, so the two compose cleanly: **rank thresholds on the career
ladder can grant components too**, giving a slower, career-long track alongside the per-season one.

That also gives the early Renown ranks — the ones doing the retention work — something tangible
attached, rather than only a badge.

**Rarity tiers do useful work.** Common components nudge an augment; rare ones jump it. Because the
level curve escalates, the high levels — the ones near a player's tolerance, where the interesting
decisions live — should require the scarce stuff. That means **nobody casually reaches the danger
zone**, which protects the push-your-luck from becoming routine.

### What this changes elsewhere

- **Floobits lose a planned sink.** Not a real loss: the existing sinks (`season_end_tax` ~905k,
  team and facility contributions, card and pack purchases) are far larger than anything chrome
  would have added, and the earlier economy audit found removing a ~1,800/season drain was inside
  the noise.
- **Sim outcomes become downstream of fan skill.** Worth stating plainly: if fantasy finishes and
  pick-em accuracy grant chrome, and chrome can decide games, then being good at the fan layer
  feeds back into the sim layer. Under the Monstars frame that reads as correct — you earn the
  right to reshape the league — but it is a real shift and should be a conscious one.
- **Renown and chrome must stay legibly different.** Same activities, two outputs. Renown is
  permanent standing (who you are); chrome is consumable agency (what you can do). That distinction
  is clean in design but needs to be obvious in the UI, or it reads as two progress bars for one
  action.

### Open on this piece

- **Grant rate per source** — the supply schedule, i.e. the R₀ dial. Needs the replay harness.
- **Do components have classes** (awakening / power / enhancement), or does one generic component
  feed any augment? Classed components make *what you earn* shape *what you can do*, which is
  richer; generic is simpler and more liquid.
- **Are components tradeable or giftable between fans?** Tradeable creates a player economy and a
  coordination tool; it also creates hoarding and makes supply harder to control.
- **Do unspent components carry across seasons?** Carrying breaks the supply dial over time;
  expiring is harsher but keeps the faucet honest.

## Still open structurally

### What is attention still for?

If chrome drives awakening, attention loses its primary job. It should probably survive as the
**league aggregate** feed — the thing that builds toward Criticality — so passive fan behavior
still generates pressure while chrome supplies deliberate, targeted pressure. Otherwise the
attention system, the ladder, the decay and the cap all retire, which is a much bigger excision.

### Where does the ladder go?

`stirring → erratic → rampant → awakened → cleansed` is currently driven by attention thresholds.
Under a probability model the intermediate rungs need a new meaning — most likely they become
**infection stages** (exposed but not yet awakened), which fits the epidemic frame and keeps the
existing badges and transition lines working.

## Open questions

- **R₀ target** and how it's tuned — this is the load-bearing number and the replay harness from
  `CRITICALITY_METAGAME_PLAN.md` is the place to find it.
- **Chrome cost + sink shape.** Floobits is the obvious currency; is cost flat, escalating per
  player, or per augment class? Note chrome decay makes this a *recurring* sink, which is a
  bigger economic lever than a one-time purchase — worth measuring against the existing sinks
  (`season_end_tax` and team/facility contributions dwarf everything else today).
- **Does chrome decay rate scale with load?** A heavily chromed player shedding augments faster
  would make cyberpsychosis self-correcting, which may be too forgiving.
- **Does the Chrome facility survive?** It was the tier gate under the favorite-team model; with
  any-player gifting, a per-team facility gating what outsiders can install is incoherent.
- **Can chrome be removed?** By the player's fanbase, by the Cores, at all?
- **Do cleansed players stay cleansed forever**, or does immunity wane so they become susceptible
  again after N seasons? Waning immunity is what stops the league trending permanently immune.

## ⚠️ 2026-08-19 — slots are limited, and tolerance varies by player

Owner: **a player has only so many chrome slots, and each player tolerates a different
amount** — some can carry more than others. This is the mechanic that makes chrome a
set of choices rather than an accumulator, and it does three jobs at once.

**It makes the two families compete.** With slots scarce, the straight augment and the
conditional weather one are fighting for the same socket, so the tension described above
becomes a real decision instead of a theoretical one.

**It is a better balance dial than supply.** This plan already names supply as the master
dial, but supply is GLOBAL — it controls how much chrome exists, not where it piles up.
Tolerance is per-player, so it caps concentration directly: even with chrome everywhere,
no single player can absorb the league.

**It creates a new axis of player value.** A mid-rated player who tolerates five implants
is worth more than a star who can take one, which is value orthogonal to rating and
exactly the "players who are characters" pillar. High-tolerance players are also the
natural Monstars under the contagion model.

### ⚠️ Tolerance MUST NOT correlate with rating

That third job only works if tolerance is **independent of how good the player already
is**, and the obvious implementation quietly destroys it. Deriving tolerance from mental
attributes — resilience, self-belief, focus, the natural thematic fit for withstanding
cyberpsychosis — hands the most chrome to the players who are already the best.

**Measured on 192 live players, correlation of each mental attribute with overall rating:**

| attribute | vs rating |
|---|---|
| instinct | +0.40 |
| x_factor | +0.38 |
| focus | +0.37 |
| creativity | +0.36 |
| discipline | +0.34 |
| attitude | +0.26 |
| resilience | +0.25 |
| self_belief | +0.21 |
| **pressure_handling** | **−0.12** |

Generation makes good players good at everything, so any mental-attribute derivation is a
rating proxy. Chrome would then be a **rich-get-richer amplifier**: the best players take
the most augments, get better still, and the talent gap widens — cutting directly against
the shipped parity work (`LEAGUE_COMPRESSION_FACTOR` 0.45, the star-scarcity rebalance)
which exists to stop exactly that.

⚠️ This is the same trap that killed `flairOf` for the audible grid, where every QB mental
attribute correlated 0.65–0.77 with every other and collapsed the 2x2 onto its diagonal.
Do not walk into it twice.

**Two ways out:**
1. **An independent roll** — tolerance is its own generated attribute, uncorrelated with
   everything else by construction. Cleanest, and it guarantees the mid-rated
   high-tolerance player exists.
2. **`pressureHandling`** — the ONE mental attribute measured as uncorrelated with rating
   (−0.12), and a defensible thematic fit for withstanding chrome stress. Grounds
   tolerance in the existing mental model without the amplifier problem.

Either is fine; deriving from anything else is not.

### Exceeding tolerance

⚠️ A **soft** cap, not a hard one (owner, confirmed 2026-08-19). A hard cap is a UI
message; a soft one is a decision. A fan should be able to push a player past their
tolerance and watch cyberpsychosis arrive — mental attributes degrading, erratic play,
the drawbacks this plan already names — which makes over-chroming a gamble a fan takes
rather than a thing the game forbids. That is the version that produces stories.

### ⚠️ The strain MUST be legible before the flame-out

Owner, 2026-08-19: a fan has to be told a player is nearing capacity, or they are left
confused about why the player they spent so much on is falling apart. **An unsignalled
soft cap is not a gamble, it is a hidden punishment**, and it will read as a bug rather
than a consequence.

**Copy the retirement-risk pattern, which already solves this exact problem.**
`playerManager.computeRetirementOdds` is the single source of truth for both the ROLL and
the displayed risk tier (`computeRetirementRisk`) "so they never drift". Chrome load
needs the same shape: **one function computes the strain, and both the penalty and the
displayed state read it.** Anything else eventually shows "stable" on a player who is
already degrading — the exact class of bug this codebase keeps getting burned by, where
a surface and its underlying number are computed twice and diverge.

**Warn before the commit, not after it.** The signal has to arrive while the fan can
still act, so the fitting flow needs to show where THIS augment lands the player, not
just where they are now. A warning that appears after the socket is filled is an autopsy.

⚠️ **Show CUMULATIVE load, not the fan's own contribution.** Any fan may chrome any
player, so several fans can be loading the same one independently. Without a shared
visible total, three fans each fit one augment believing they are safe and collectively
fry the player — and every one of them experiences it as the game cheating. This is the
detail most likely to be missed, because it only breaks with more than one contributor.

**Qualitative band, not a raw number**, matching the house style for player-facing state
(the form badge, the retirement risk tier). The exact capacity can stay hidden; how close
to it they are cannot.

**And deliver it in character as well.** Cyberpsychosis has symptoms, and the personality
system already carries moods and quotes — a player nearing capacity should start sounding
wrong before the numbers move. That is the version a reader notices without being told to
look. ⚠️ Flavor alone is NOT the warning though: it rides alongside the explicit state,
never instead of it.

---

# Part III — Where the two meet

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

⚠️ **Chrome has scarce slots and per-player tolerance** (owner, 2026-08-19), so a
weather augment competes for a socket with a straight skill boost. Tolerance is an
independent attribute — deliberately NOT derived from the existing mentals, which
measure +0.21 to +0.40 correlated with rating and would make chrome a rich-get-richer
amplifier — and the cap is soft, with the strain surfaced to fans before the flame-out.
Full reasoning in `docs/CHROME.md`.

**It composes with the roster fit already built.** The GM builds for the venue
(`phaseBias` → positions), the fans chrome for the venue (conditions → augments). Two
layers reading the same input from opposite ends, which is exactly the fans-versus-Cores
frame the metagame plan is built on. It also gives each team a visible chrome identity
over time — the team in the cavern all run optics — which is character emerging from
mechanics rather than being authored.

## ⚠️ 2026-08-19 — weather chrome is ONE FAMILY, not the model for all of it

⚠️ **Owner, 2026-08-19: chrome is not only weather counters. The backbone is straight
skill boosts** — fit an augment, the player is better, full stop. That is what a fan
reaches for by default and it is what this document already describes ("chrome genuinely
juices players and may decide games"). The section below adds a SECOND family alongside
it; it does not redefine the system, and weather is not chrome's reason for existing.

The two families want different shapes, and the tension between them is the actual
decision a fan makes:

| | pays | shape |
|---|---|---|
| **straight augment** | always | reliable, lower ceiling, no read required |
| **conditional / weather** | only in the conditions it is for | higher ceiling, needs a read, dead weight when wrong |

⚠️ **The conditional family needs a genuinely higher ceiling or nobody takes it.** If the
two are equal in expectation, the one carrying variance and requiring homework simply
loses. This is the same axis the card system already runs on — dependable at the base,
conditional with higher ceilings above it — and it is worth copying because it is
already proven with this audience.

Stadiums and weather are built (`docs/WEATHER_STADIUMS_PLAN.md`, `data/templates/stadiums.yaml`):
every venue is a fantastical setting with weather native to it, and **its intensity rides
the anomaly dial and peaks at Criticality**. That hands this plan the thing it was short
of — a specific, visible, repeating reason for a fan to chrome a specific player.

Weather is **announced before kickoff**, so the read is legible: your team is at Bedrock
Cavern in the dark this week, so you fit optics. The conditions are sensory and physical
(`visibility`, `footing`, `fumbleRate`, `paceMod`, …) and so is chrome, which makes the
mapping one-to-one rather than invented. Full table and guardrails in the weather plan
under "Chrome answers the weather".

Two constraints carried over from there: weather chrome must be **conditional** (it pays
only in the conditions it is for, so it is a read and not a flat upgrade), and it must
**not fully negate** the weather or the two features cancel. The open question is whether
awakened-tier chrome may make a player genuinely BETTER in the dark than in the light —
the Monstars fantasy, and the one thing that can undo the venue fairness work.


---

## Remaining open decisions

1. **Alternate formats.** Frames, darts and chess clock each change what a modifier
   means (`puntDistance` matters less in darts, where hoops decide it). Darts is
   already excluded from Criticality chaos; decide whether weather follows it.
2. **Cards.** Weather-keyed effects are an obvious future card family ("scores in
   Severe weather or worse"). Out of scope here, but the persisted `games.weather`
   row is what would make it possible later, so persist it in the shape a card
   calculator could read.
