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
| `runYardage` | the run gate model (`_resolveRunGates`) |
| `fgAccuracy` | `fgMakeProbability` — the single source of truth, so the coach's attempt decision moves with it automatically |
| `sackRate` | `calculateSackProbability` |
| `fumbleRate` | the fumble check in the shared carrier tail |
| `puntDistance` | `resolvePunt` |
| `returnYards` | `_resolvePuntReturn` |
| `paceMod` | pre-snap time |

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

## Remaining open decisions

1. **Alternate formats.** Frames, darts and chess clock each change what a modifier
   means (`puntDistance` matters less in darts, where hoops decide it). Darts is
   already excluded from Criticality chaos; decide whether weather follows it.
2. **Cards.** Weather-keyed effects are an obvious future card family ("scores in
   Severe weather or worse"). Out of scope here, but the persisted `games.weather`
   row is what would make it possible later, so persist it in the shape a card
   calculator could read.
