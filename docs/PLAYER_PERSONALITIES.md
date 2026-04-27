# Floosball Player Personality System

Two-layer model. Every player has a **vibe** (their core personality flavor) and *optionally* a **quirk** (a specific tic or trait). The system powers reaction text, sideline observations, and Discord interview/mood commands.

The point of this system is **humor and flavor**, not play-by-play description. Every reaction template should add personality, not paraphrase what just happened.

- **Vibes**: 9 total. Flat list of distinct voices. No drift, no spectrum math.
- **Quirks**: 34 total across 2 tiers (22 Common, 12 Rare). ~50% of players have one. League-wide cap of 1 for Rare quirks. Quirks are **observable tics** (things players do), not personality descriptors — vibes already cover personality. Quirks contribute their own positive/negative reaction lines that get *added* to the vibe's pool, so each vibe+quirk combination produces a distinct mix.

Source of truth: [`managers/personalityData.py`](../managers/personalityData.py) on the `feature/player-reactions` branch.

---

## Vibes — The 9 Flavors

Each vibe is a distinct voice. Reactions key off `(vibe, situation)`. Players don't shift between vibes — what you generate is what you get.

The vibes loosely sit on a **weighed-down → controlled → chaotic** spectrum, with Wholesome and Goofy as warmer / sillier branches off the middle:

```
Melancholy → Stoic → Easy → Wholesome → Cool → Lively → Goofy → Fiery → Unhinged
weighed       flat   chill    sincere   smooth animated  silly  hot     deranged
```

| Vibe          | Voice                                            | Distribution |
|---------------|--------------------------------------------------|--------------|
| **Melancholy**| Brooding, Romantic-poet flowery. Waxes poetic. Heart-on-sleeve. | 4%           |
| **Stoic**     | Silent, controlled. Dry one-liners. Says less than expected.   | 13%          |
| **Easy**      | Relaxed pro. Even-keeled, deflects to team. Surfer-zen detached. | 18%        |
| **Wholesome** | Sincere, warm, team-first. Loves teammates out loud. Effusive but kind. | 12%   |
| **Cool**      | Over-the-top swagger. Vain, sees self as main character.       | 8%           |
| **Lively**    | Animated, expressive. Normal-loud, plays with feeling.         | 15%          |
| **Goofy**     | Silly, slapstick, jokey. Bits and gags. Doesn't take self seriously. | 12%    |
| **Fiery**     | Hot, explosive. Big emotions. Yelling is on the table.         | 15%          |
| **Unhinged**  | Chaotic, internet-poisoned. All-time hot takes. Conspiracy-adjacent. | 3%     |

### Tone guide

Sample reactions to the same situation, by vibe — gives a feel for the voice:

(Sample of voice contrast — full pools live in `data/templates/vibe_reactions.yaml`.)

| Situation             | Melancholy                                | Stoic               | Easy                       | Wholesome                                  | Cool                                            | Lively                   | Goofy                                            | Fiery                      | Unhinged                                       |
|-----------------------|-------------------------------------------|---------------------|----------------------------|--------------------------------------------|-------------------------------------------------|--------------------------|--------------------------------------------------|----------------------------|------------------------------------------------|
| Scored a TD           | "Oh, briefly, beautiful."                 | "Job done."         | "That one felt nice."      | "I love these guys. They earned it."       | "Was that ever in doubt?"                       | "Y'all see that?!"       | "I closed my eyes and tripped into the endzone." | "THERE IT IS!"             | "Mother always said I'd be famous."            |
| Fumbled               | "I had it. And then I didn't."            | "Lost it."          | "Yeah, my bad."            | "I'm so sorry to my line. I'll do better." | "Won't happen again. *brushes shoulder*"        | "C'mon, c'mon!"          | "I think the ball is haunted."                   | "I'M DONE. I'M FINISHED."  | "the ball was greased."                        |
| Made a sack           | "Their hour had come. I was the messenger." | "Got there."      | "They held it. I came home." | "Just doing my job. Defense did the work." | "Tell your kids about me."                    | "GOT THEM! GOT THEM!"    | "{name} mimes putting the QB in a tiny pocket."  | "GET UP! GET UP!"          | "I knew their cadence. I dreamed it."          |

The tone matrix above is the **brief for content writing.** When in doubt about a reaction line, ask: does it sound like the voice in this column?

---

## Quirks — Optional Flavor Tics

Roughly half of players carry a quirk. Quirks are specific behavioral tags that surface in **sidelines** (between-play flavor) and as **descriptors** (on the player page, in interviews).

- **Common (22 quirks)**: ~45% of all players. No league cap. Reusable across many players.
- **Rare (12 quirks)**: ~5% of all players. **League-wide cap of 1 each** — only one Alien, one Cursed, one Time Traveler at a time.
- Players are assigned quirks **independently** of their vibe. A Stoic player can be a Goofball; a Fiery player can be Wholesome. The contrast often *is* the joke.

### Common quirks

Each one is a specific observable tic — something you'd see them DO, not a way they sound. Vibes cover the voice; quirks add a concrete behavior on top.

| Quirk            | One-line description                                         |
|------------------|--------------------------------------------------------------|
| **Perfectionist**| Stews on imperfect reps. Visible self-disappointment.        |
| **Superstitious**| Same socks, same meal, same ritual. Always.                  |
| **Oblivious**    | Missed the memo. Unbothered by chaos around him.             |
| **Hugger**       | Physically affectionate. Hugs teammates, refs, mascots.      |
| **Vain**         | High-maintenance grooming. Mirror checks, sleeve tugs.       |
| **Bling**        | Visible wealth. Jewelry, loud cars, designer everything.     |
| **Gym Rat**      | Lives in the weight room.                                    |
| **Prankster**    | Whoopee cushions, fake injuries, juvenile bits.              |
| **Snacker**      | Always eating. Sunflower seeds, gum, granola, anything.      |
| **Ear Buds**     | Headphones on sideline, pregame, walkthroughs.               |
| **Ref-Yeller**   | Every call gets a tirade. Even the favorable ones.           |
| **Phone Addict** | On the phone every dead moment. Sideline. Tunnel. Bus.       |
| **Hydrated**     | Evangelical about water. Always has a bottle, preaches it.   |
| **Napper**       | Catches sleep anywhere. Bus, locker, pregame couch.          |
| **Reader**       | Actual books on the bench. Literary tastes.                  |
| **Gamer**        | Console nut. References video games in interviews.           |
| **Whistler**     | Whistles tunes in the huddle, on the bench, down the tunnel. |
| **Sketcher**     | Doodles on his wristband, playbook, any napkin.              |
| **Singer**       | Bursts into song. Locker, huddle, bus, tunnel.               |
| **Stargazer**    | Astronomy references. Telescopes. Talks about the sky.       |
| **Insomniac**    | Texts teammates at 4am about film.                           |
| **Streamer**     | Broadcasts prep, reactions, daily life. Always live.         |

### Rare quirks (league-wide cap of 1 each)

The memorable ones. These should feel like Easter eggs when you encounter them.

| Quirk             | One-line description                                              |
|-------------------|-------------------------------------------------------------------|
| **Alien**         | Rumored to be not of this planet. Eerie talent, no explanation.   |
| **Time Traveler** | Insists they've seen this play before. Sometimes correct.         |
| **Prophet**       | Predicts plays, outcomes, injuries with unsettling accuracy.      |
| **4th Wall**      | Aware they're in a simulation. Speaks directly to camera.         |
| **Cursed**        | Bad luck follows them. Broken mirrors. Bad bounces. Black cats.   |
| **Sleepwalker**   | Plays half-asleep. Weirdly effective.                             |
| **Disinterested** | Bored by the whole thing. Peak talent, zero effort, zero care.    |
| **Silent**        | Has literally never spoken publicly. Communicates by gesture.     |
| **Nameless**      | No one knows their real identity. Media uses a handle.            |
| **Ghost**         | No social media, no quotes, no presence off the field.            |
| **Twin**          | Identical twin somewhere. Fans can't tell which one shows up.     |
| **Fossil**        | Ancient, still playing. Older than anyone thought possible.       |

---

## Data shape

### Player record

```python
class PlayerAttributes:
    vibe: str                  # one of: melancholy, stoic, easy, wholesome, cool, lively, goofy, fiery, unhinged
    quirk: Optional[str]       # one of QUIRK_KEYS, or None (~50% have one)
```

That's it. No archetype, no demeanor index, no drift state.

### Static data (`personalityData.py`)

```python
VIBES = {
    # Ordered along the weighed-down → controlled → chaotic spectrum
    'melancholy': {'label': 'Melancholy', 'weight': 4},
    'stoic':      {'label': 'Stoic',      'weight': 13},
    'chill':      {'label': 'Chill',      'weight': 18},
    'wholesome':  {'label': 'Wholesome',  'weight': 12},
    'cool':       {'label': 'Cool',       'weight': 8},
    'lively':     {'label': 'Lively',     'weight': 15},
    'goofy':      {'label': 'Goofy',      'weight': 12},
    'fiery':      {'label': 'Fiery',      'weight': 15},
    'unhinged':   {'label': 'Unhinged',   'weight': 3},
}

QUIRKS = {
    'wholesome':    {'label': 'Wholesome',    'tier': 'common'},
    'hothead':      {'label': 'Hothead',      'tier': 'common'},
    # ... ~24 common total
    'alien':        {'label': 'Alien',        'tier': 'rare'},
    'time_traveler':{'label': 'Time Traveler','tier': 'rare'},
    # ... ~12 rare total
}

QUIRK_ASSIGNMENT_RATE = 0.50    # 50% of players get a quirk
RARE_QUIRK_ROLL_RATE  = 0.10    # of those quirked, 10% roll a rare
```

No compatibility tables. No demeanor ranges. No archetype allowlists. No drift tracking.

### Reaction templates

YAML keyed by `(vibe, key)`. Each vibe has 12 keys: 2 generic pools + 10 specific event keys.

**The lookup combines both pools.** When a specific event fires, the system pulls from BOTH the generic pool (positive or negative) AND the specific event key — then picks one at random from the combined list. This means specific keys only need a few event-flavored lines (those that explicitly reference the play); the bulk of variety comes from the generic pool.

```
data/templates/
  vibe_reactions.yaml       # keyed by vibe + reaction key
  quirk_sidelines.yaml      # observational flavor lines per quirk
  crowd_atmosphere.yaml     # general atmosphere lines (not personality-keyed)
```

#### Reaction key map

| Reaction key       | Pool used                                  | Used for                                          |
|--------------------|--------------------------------------------|---------------------------------------------------|
| `positive_generic` | Pool itself (~12-15 lines)                 | `clutch_play`, `made_big_play`, any positive fallback |
| `negative_generic` | Pool itself (~12-15 lines)                 | `choke_play`, any negative fallback               |
| `scored_td`        | `positive_generic` + `scored_td` combined  | The runner or receiver who scored                 |
| `threw_td`         | `positive_generic` + `threw_td` combined   | The QB on a passing TD                            |
| `made_fg`          | `positive_generic` + `made_fg` combined    | The kicker                                        |
| `missed_fg`        | `negative_generic` + `missed_fg` combined  | The kicker                                        |
| `got_sacked`       | `negative_generic` + `got_sacked` combined | The QB                                            |
| `made_sack`        | `positive_generic` + `made_sack` combined  | The defender who got the sack                     |
| `threw_int`        | `negative_generic` + `threw_int` combined  | The QB who threw it                               |
| `made_int`         | `positive_generic` + `made_int` combined   | The defender who picked it                        |
| `fumbled`          | `negative_generic` + `fumbled` combined    | The player who fumbled                            |
| `recovered_fumble` | `positive_generic` + `recovered_fumble` combined | The defender who recovered                  |

Specific keys hold only **2-3 event-flavored lines** that explicitly reference the play (e.g. `"I crossed the line. The line is everything."` for `scored_td`). Generic-feeling lines belong in the pool.

#### Line formats

A reaction line can be one of three formats. Writers pick whichever sells the vibe best:

| Format             | Example                                           | When to use                          |
|--------------------|---------------------------------------------------|--------------------------------------|
| Pure quote         | `"For one moment, the universe held."`            | When the player has something to say |
| Pure description   | `{name} stares at the sky for a long moment.`     | When silence/action says it          |
| Quote + stage dir  | `"That's me." *adjusts his headband*`             | Quote that lands harder with action  |

**`{name}`** is substituted with the reactor's full name at render time. Use it freely in descriptions; quotes don't need it (the UI attributes the speaker automatically).

Stoic and Melancholy vibes especially benefit from descriptions — these voices say less, so *showing* what the player does often lands harder than a quote.

#### Example — same generic pool across vibes

```yaml
# vibe_reactions.yaml
melancholy:
  positive_generic:
    - "Briefly, beautiful."
    - "I felt the universe align. It will not last."
    - "{name} looks up at the lights for a long moment."
    - "Maybe I'm allowed this one."
  negative_generic:
    - "Yes. As I expected."
    - "{name} just stares at the turf."
    - "We were always going to be here."
  scored_td:
    - "For one moment, the universe held."
    - "I crossed the line. The line is everything."
  fumbled:
    - "I had it. And then I didn't. As all things go."
    - "The ball does not love us back."
  got_sacked:
    - "I was reaching for something. It wasn't there."
    - "The pocket collapsed. As pockets do."

stoic:
  positive_generic:
    - "Job."
    - "That'll do."
    - "{name} hands the ball to the ref and walks off."
  negative_generic:
    - "{name} jogs back to the huddle without expression."
    - "Move on."

cool:
  positive_generic:
    - "Was that ever in doubt?"
    - "Watch the tape. I'll wait."
    - "{name} smooths his jersey."
    - "You're welcome, by the way."
  negative_generic:
    - "I'll allow it. Once."
    - "{name} adjusts his sleeves and gets back to it."
```

### Quirk reactions (additive layer)

Every quirk has its own short pool of positive and negative reaction lines (typically 2-3 each). When a player has a quirk, those lines get **added to the candidate pool** for the matching event sentiment. This means a Stoic Snacker pulls from:
- Stoic's `positive_generic` pool
- Stoic's specific event key (e.g. `scored_td`)
- Snacker's `positive` pool

…all combined into one candidate list. The lookup picks one line at random.

Quirks only contribute generic positive/negative lines — never event-specific lines. Specific event flavor (e.g. "I crossed the line" for a TD) stays in the vibe data.

The full quirk reaction file lives in `data/templates/quirk_reactions.yaml`. Each quirk has the shape:

```yaml
snacker:
  positive:
    - "{name} cracks a fresh seed bag on the bench."
    - "*chews triumphantly*"
  negative:
    - "{name} reaches for the seeds before sitting down."
    - "*chews thoughtfully* Hmm."
```

#### Lookup logic

```
on event:
  reactor    = pickReactor(event)              # per the Reaction Architecture table
  vibe       = reactor.attributes.vibe
  quirk      = reactor.attributes.quirk        # may be None
  sentiment  = "positive" or "negative" based on event
  poolKey    = sentiment + "_generic"          # e.g. "positive_generic"
  specKey    = specific key for the event (e.g. "scored_td"), or None

  candidates  = vibeReactions[vibe][poolKey]
  candidates += vibeReactions[vibe][specKey] if specKey else []
  candidates += quirkReactions[quirk][sentiment] if quirk else []

  line       = random.choice(candidates)
  emit       = substitute(line, name=reactor.name)
```

For events without a specific key (clutch / choke / made_big_play), the lookup just uses the generic pool plus optional quirk lines.

---

## Reaction Architecture

Two distinct surfaces driven by the two layers:

- **Vibes drive in-game reactions** to high-energy moments (scores, turnovers, big swings).
- **Quirks drive ambient flavor** during low-energy stoppages (between possessions, quarter changes, halftime).

### When vibe reactions fire

**Always fire** (regardless of WPA):
- Touchdowns
- Field goals (made or missed)
- Interceptions
- Fumbles lost

**Conditional fire** (only when the play has notable WPA impact, typically `isBigPlay` >= ~10% swing):
- Sacks
- Long-yardage plays not otherwise tagged
- Plays flagged `isClutchPlay` or `isChokePlay`

### Who reacts (single reactor per event)

One reactor per event keeps the feed from getting noisy. Each event has a defined reactor pool — when more than one player is eligible, pick at random so receivers, defenders, etc. all get screen time.

| Event              | Reactor pool                              | Pick rule         | Pool used (specific + generic combined)      |
|--------------------|-------------------------------------------|-------------------|----------------------------------------------|
| Rushing TD         | the runner                                | always            | `scored_td` + `positive_generic`             |
| Passing TD         | passing QB OR scoring receiver            | random 50/50      | (QB) `threw_td` + `positive_generic` / (receiver) `scored_td` + `positive_generic` |
| FG made            | the kicker                                | always            | `made_fg` + `positive_generic`               |
| FG missed          | the kicker                                | always            | `missed_fg` + `negative_generic`             |
| Sack               | sacked QB OR defender who sacked          | random 50/50      | (QB) `got_sacked` + `negative_generic` / (defender) `made_sack` + `positive_generic` |
| INT thrown / caught| QB who threw OR defender who caught       | random 50/50      | (QB) `threw_int` + `negative_generic` / (defender) `made_int` + `positive_generic` |
| Fumble             | player who fumbled OR defender who recovered | random 50/50  | (fumbler) `fumbled` + `negative_generic` / (defender) `recovered_fumble` + `positive_generic` |
| Clutch play        | the flagged player                        | always            | `positive_generic` only                      |
| Choke play         | the flagged player                        | always            | `negative_generic` only                      |
| Big play (untagged)| central player (runner/receiver/tackler)  | always            | `positive_generic` only                      |

### Quirk surfaces (ambient)

Quirk flavor is sprinkled during slow moments — never tied to a specific play outcome. Each surface picks ONE rostered player at random across both teams; if that player has a quirk, emit a flavor line; otherwise, do nothing.

Surfaces:
- Between possessions (after kickoff, after punt, after turnover)
- Quarter transitions
- Halftime
- Two-minute warning
- Timeouts

Sample rate per surface: ~30-40% (so it feels organic, not constant).

### Other usage surfaces

- **Discord `/interview <player>`**: vibe-driven press-conference quote, optional quirk twist.
- **Discord `/mood <player>`**: vibe + quirk display.
- **Player page**: vibe shown as a single tag; quirk shown as a second tag if present.

---

## What this replaces

The previous design used three layers (archetype + demeanor + quirk) with compatibility tables, weekly drift, and quirk-swap logic. The new design collapses archetype + demeanor into a single static `vibe` and drops all drift/swap machinery.

**Removed entirely:**

- `ARCHETYPES` (12-entry alignment grid, `selfAxis` / `disciplineAxis`)
- Archetype-keyed reaction templates
- Demeanor drift logic and `checkWeeklyDrift`
- Quirk-swap logic when demeanor drifts out of range
- Quirk demeanor-range and archetype allowlist constraints
- 4-tier quirk rarity (Common / Uncommon / Rare / Unique)
- Tier bucket types (`universal` / `constrained` / `exclusive`)
- `personality_drift_log` table (if it existed)

**Migrated:**

- `archetype` column → dropped
- `demeanor` column → renamed to `vibe`, value migrated (Stoic → stoic, Cool → cool, Intense → lively, Fiery → fiery, Melancholy → melancholy, Dramatic → unhinged)
- `quirk` column → kept; values normalized (some legacy quirks dropped or merged into the trimmed list)

---

## Writing tone — quick reference

**Universal rule:** all reaction lines should be **timeless**. No current internet slang. Phrases like *"let's go,"* *"we cooked,"* *"I am literally him,"* *"based,"* *"slay,"* *"no cap,"* etc. will read as dated within a year. Period-neutral exclamations (*"There it is!"*, *"What a game!"*, *"We're back!"*) age better. The only exception is the **Unhinged** vibe, where conspiracy/internet-brain phrasing is *the* joke — and even there, lean toward conspiracy-noir tropes (*"the refs were paid by..."*, *"the simulation is buggy"*) over TikTok phrasing.

| Vibe        | Do                                                  | Don't                                       |
|-------------|-----------------------------------------------------|---------------------------------------------|
| Melancholy  | Romantic-poet flowery. Heart imagery, "Oh." Nature/dusk metaphors. | Modern slang. Cliches. Hot energy. |
| Stoic       | Few words. Dry. Sometimes silent. Bureaucratic deadpan. | Long sentences. Emotional flourishes.   |
| Easy        | Surfer-zen pro talk. Shrugs. Deflects to team.      | Hot takes. Sad poetry. Self-mythologizing.  |
| Wholesome   | Sincere. Effusive about teammates. "These guys, man." Hugs and helps. | Cynical. Detached. Self-praise. |
| Cool        | Swagger. Third-person refs to self. Action-hero one-liners. Vain gestures. | Self-deprecation. Humility. |
| Lively      | Energy. Exclamations. Calls out teammates. Whoo!    | Monotone. Brooding.                         |
| Goofy       | Bits, gags, slapstick. Mimes things. Doesn't take self seriously. | Sincere earnest delivery. Anger. |
| Fiery       | Yelling. Anger. Big swings. Property damage.        | Calm acceptance. Chill detachment.          |
| Unhinged    | Conspiracy. Internet brain. Wrong confidently. Cult energy. | Reasonable. Self-aware.             |
