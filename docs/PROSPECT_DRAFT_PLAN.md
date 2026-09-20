# Prospect Draft — restoration plan

_Owner-directed, 2026-09-14. Feasibility, measurements and the decision trail are in
`docs/TRADING_FEASIBILITY.md` (addenda 9–13); this is the build._

## Why

**A bottom-feeder team drafting a huge prospect.** That is the whole pitch, and the machinery
for it is already built and calibrated — `constants.py` states the intent verbatim:

> *"Rookies/prospects DEBUT this many attribute points below their true skill and develop up
> into it over their early seasons. **A future 5-star looks like a solid 3-4-star as a
> rookie.**"*

The three-tier model (`current ≤ trueSkill ≤ potential`) is live, its columns are populated,
and on the current 224 players potential runs **+6.1 above current skill on average, +25 at
the top, with 48 players carrying 10+ points of headroom**. It has had nothing to express it
through since `68e5608` removed the draft.

⚠️ **A free-agent pick cannot substitute.** An FA is a known quantity with a rating on the
card; there is no story in signing a 74. The uncertainty *is* the feature.

## Settled decisions

| # | decision | why |
|---:|---|---|
| 1 | **1 round, 32 prospects**, worst-first | three rounds does not produce a better headliner — see Sizing |
| 2 | **No fan ballots** | the autonomous front office is the decider everywhere else |
| 3 | Class generated at **SEASON START**, visible and scoutable all season | ⚠️ revised 2026-09-14 — see below. Week 22 was wrong: trades close at week 22, so a pick would be traded entirely blind |
| 4 | The draft **replaces** the supply trickle | `ensurePositionSupply` stays the per-position backstop it already is, not a second faucet |
| 5 | **The cull ships with it**, not after | at ~13/season surplus, "after" means the pool grows 13 a season until it arrives |
| 6 | Prospects become a tradeable asset class | alongside FA draft position and Treasury — see the trading plan |

## Sizing — why one round

Over 2,000 simulated classes at the live generation constants
(`GEN_TRUESKILL_MEAN` 78, `GEN_TRUESKILL_STD` 10, `POTENTIAL_HEADROOM` 15,
`PROSPECT_ENTRY_DISCOUNT` 11):

**A class of 32 yields a headliner who debuts at 83, has true skill 94 and potential 99**,
with **2.6 genuine future 5-stars** (trueSkill ≥ 92) in the class. The worst team picks
first, so he is theirs, and the story fires every season.

| class size | best trueSkill | best potential | true 5-stars |
|---:|---:|---:|---:|
| **32** | 98.7 | **99.0** | 2.6 |
| 64 | 101.3 | **99.0** | 5.1 |
| 96 | 103.0 | **99.0** | 7.8 |

⚠️ **Potential is capped at 99 in all three.** Extra rounds buy also-rans, not a better
headline — and those also-rans are the entire inflation cost below.

## ⚠️ Why the cull is not optional

192 roster spots are **fixed**. Growing the candidate population raises the bar with no change
to how players are generated — pure selection pressure. Resampling the current empirical
rating distribution at larger N:

| population | rostered mean | 4★+ share |
|---:|---:|---:|
| 224 (today) | 80.5 | 35% |
| 300 | 83.0 | 48% |
| 400 | 85.0 | **63%** |

Intake 32/season against ~19 replacement need (192 spots ÷ median longevity 10) leaves a
**~13/season surplus**. Unchecked that reaches ~63% four-star by season 20 — *every team ends
up with four-star players*, which is the thing this must not do. **A cull at the surplus rate
holds it flat at 34% indefinitely.**

✅ The timing is favourable: the retirement wave is just starting (players past longevity:
**12 now → 44 by season 8 → 108 by season 10**), so intake ramps up as outflow does. The
risk window is seasons 6–8, which is another reason the opener is one round.

## What already exists

⚠️ **`68e5608` excised the draft but left its entire surrounding scaffolding.** Most of this
feature is already in the codebase:

| piece | where |
|---|---|
| prospect columns (`is_prospect`, `prospect_seasons`, `drafting_team_id`) | `models.py` |
| `team.prospects` load path | `playerManager` pass 1 |
| autonomous promotion, **already ballot-free** | `seasonManager._promoteProspectsAutonomously` |
| development wiring: coach `playerDevelopment` + Training Facility `dev_bonus` → climb toward `trueSkill` | `seasonManager` step 7 → `PlayerDevelopment.apply_offseason_training` |
| washout release after `PROSPECT_DEVELOPMENT_WINDOW` | `playerManager._advanceProspectWindow` |
| `GET /api/players?status=prospects` | `api/main.py` |
| stats prospects facet + filter | `_PLAYER_STATUSES` |
| `GET /api/teams/{id}/prospects` — incl. a **batched `ratingHistory` series** for a sparkline | `api/main.py:8243` |
| scouting accuracy → `FO_SCOUT_FACILITY_ENABLED`, `facilityEffect('scouting_bonus')` | `frontOfficeBrain.scoutingVision` |

**Development magnitudes** (verified live): Training Facility `dev_bonus` `[0, 0.4, 0.8, 1.2,
1.6, 2.0]`; coach `(playerDevelopment − 60)/10` → 60→0, 80→+2, 100→+4. Combined devBias
spans **0 to +6**, and the docstring says it *"skews prospect booms"*.

## What to build

### 1. Class generation — AT SEASON START, not week 22

⚠️ **Revised.** The plan first put generation at week 22, reasoning that the class is sized
against the holes retirement is about to open. **That dependency does not exist**: at one
round the class size is fixed by the team count, not by how many players retire. And week 22
is where in-season trades *close*, so a pick would have been traded blind for the entire
window — which is exactly the owner's objection.

✅ **The original design already did this**, and `constants.py` still says so verbatim:

> *"Rookie class is generated at season start; fans can scout + vote on prospects all
> season. Scouting accuracy = coach.scouting + funding tier bonus, and determines how wide
> the potential-attribute range is in the scouted view."*

Generating at season start gives the class a whole season of visibility, which is what makes
a pick a tradeable asset with a known shape — *"this year has a 99-potential quarterback at
the top, so pick 1 is precious"* — and it runs the bottom-feeder story all year rather than
for one afternoon.

Restore `_generateRookieClass` from `68e5608`, called from `startNewSeason` (alongside
`_generateCardTemplates`, which already mints there).

⚠️ **`ROOKIE_DRAFT_CLASS_SIZE = 24` is stale** — a 24-team-era constant. Derive it from the
live team count rather than hardcoding 32; `computeShareUnit` already paid for that lesson
(its `numTeams` defaulted to 24 and made every facility 33% too expensive after the league
grew).

### 1b. The scouted view — REBUILD

A prospect must not show his true numbers. The uncertainty is the feature: it is what makes a
pick worth arguing about, what gives the Scouting Department a job, and what makes trading a
pick a real decision rather than an arithmetic one.

**What is known vs scouted.** Current rating is a FACT — he exists and plays at that level.
**Potential is the scouted quantity**, shown as a band.

| scouting accuracy | potential shown as |
|---|---|
| ≥ 95 | the exact value |
| 80–94 | ± 5 |
| 65–79 | ± 10 |
| < 65 | ± 15 |

`SCOUTING_BANDS` still holds that table. ⚠️ **It has ZERO readers** — `scoutRookie` was
removed by `68e5608` — so unlike the columns and the API surfaces, this half is a genuine
rebuild rather than a restore.

#### ⚠️ Accuracy comes from `scoutingVision`, not the stale constant

The comment above `SCOUTING_BANDS` says accuracy is *"coach.scouting + funding tier bonus"*,
and `FUNDING_SCOUTING_BONUS` is the **old market-tier system**, superseded by
`facilityEffect('scouting_bonus')` (levels `[0, 1, 2, 3, 5, 7]`).

Wire the band to **`frontOfficeBrain.scoutingVision(coach, team)`**, which already blends the
GM's own `scouting` with the Scouting Department behind `FO_SCOUT_FACILITY_ENABLED`. One
definition, already used for every other front-office judgement.

✅ This is what finally makes the Scouting Department honest — its UI copy promises *"clearer
read on draft prospects"* and it currently only sharpens free-agent valuations.

#### ⚠️ The view must be REPRODUCIBLE, not cached

`_scoutError` is the right model and gets two things right that this needs:

- **Drawn once and held.** A GM who overrates a player must overrate him consistently — on
  the board, at the pick, and in a trade.
- **Stored as a STANDARD normal**, so the same opinion *rescales* when vision changes. A club
  that upgrades its Scouting Department mid-season sees its view **tighten around the opinion
  it already held** rather than jump to a different one. That is exactly the behaviour a fan
  should see after a facility upgrade.

⚠️ **But its storage will not do here.** `_scoutBeliefs` is an in-memory dict on a brain that
lives **one offseason** (`_foBrainForOffseason`). A scouted view is fan-facing, season-long,
and must survive every restart and deploy — a supporter checking the class on Monday and
again on Thursday cannot be shown different numbers.

So derive it deterministically instead of storing it:

```
seed  = (gmId or teamId, prospectId, seasonNumber)
draw  = Random(hash(seed)).gauss(0, 1)      # the club's standing opinion, forever
shown = truePotential + draw * bandWidth(scoutingVision)
```

No table, no cache, no migration, and identical before and after a deploy. ⚠️ The season is
**in the seed on purpose**: a club's read should reset for next year's class, not inherit
last year's luck.

#### Per club, which means the UI has a viewpoint

The band is per `(club, prospect)`, so **there is no single "the class" view** — a team page
shows that club's read, and the league-wide prospect list shows the viewing user's favourite
club's read (falling back to a neutral/median band for a user with no favourite).

⚠️ That is a real UI decision, not an implementation detail: two fans of different clubs
looking at the same prospect should see different ranges, and that is the feature working.

#### Belief and range are two different things

⚠️ Worth stating plainly, because conflating them leads to the wrong implementation:

| | what it is | who uses it |
|---|---|---|
| **belief** | a single number — `truePotential + draw × band` | the GM: draft board, trade valuation, promotion |
| **range** | `belief ± band`, clamped to the rating scale | a human — it is how the uncertainty is shown |

The GM never acts on a range. It acts on its belief, which may be wrong, and the range is the
honest statement of how wrong it could be. Two clubs with identical scouting and opposite
opinions of a true-88 prospect believe **94** and **81** and pay accordingly — same player,
and each range still contains the truth.

#### The band narrows as the season runs

Band width scales with **both** scouting accuracy and how long the club has been watching:

```
progress = (week - 1) / (REGULAR_SEASON_WEEKS - 1)          # 0.0 at week 1, 1.0 at week 28
scale    = SCOUT_BAND_EARLY - (SCOUT_BAND_EARLY - SCOUT_BAND_LATE) * progress
band     = bandFor(scoutingVision) * scale                   # SCOUTING_BANDS gives bandFor
belief   = truePotential + draw * band                       # draw is the fixed (club, prospect, season) normal
shown    = clamp(belief - band), clamp(belief + band)
```

With `SCOUT_BAND_EARLY` 1.4 and `SCOUT_BAND_LATE` 0.4, a club on the ±10 accuracy tier sees:

| week | band | believes | shows |
|---:|---:|---:|---|
| 1 | ±14 | 96 | 82–100 |
| 8 | ±10 | 94 | 84–100 |
| 15 | ±7 | 92 | 85–99 |
| 22 | ±4 | **90** | **86–94** |

_(true potential 88, one club's fixed opinion)_

✅ **The belief converges on the truth as well as the range**, because the error scales with
the band and the club's `draw` is fixed. Early it is confidently wrong-ish and openly unsure;
late it is close and knows it. Nothing jumps — the same opinion simply sharpens.

✅ **A perfect scout is unaffected.** `SCOUTING_BANDS` gives ±0 at accuracy ≥95, and zero
times any scale is still zero — so an elite scouting operation sees the exact number in
week 1 and has nothing to gain from waiting. That is the Scouting Department's ceiling being
worth something.

**Why it is worth building.** It gives the trade deadline a shape: a pick traded in week 3 is
speculation on a blurry class, and the same pick at week 22 is a priced asset both clubs can
see. Without it a pick is exactly as knowable in week 3 as in week 22, and there is no reason
to trade at one moment rather than another.

#### ⚠️ Clamp at the rating ceiling — and the clamp is informative

Ratings cap at **100** (`floosball_player`: `min(100, ...)`; prod's highest potential is
exactly 100). A band must be clamped, or the UI prints impossible numbers.

But the clamp is not only a correctness fix. Near the top of the scale the range goes
**asymmetric**, and that asymmetry is real information — "could be maxed" is exactly the
signal a scout would have. A true-97 prospect seen by a ±10 club:

| week | believes | shows |
|---:|---:|---|
| 1 | 100 | **91–100** |
| 22 | 99 | **95–100** |

So an elite prospect still *looks* elite through a wide band, which is what makes the
top of a class legible to a fan in week 1 — and it is why the clamp must sit on the displayed
range rather than on the underlying draw.

#### Surfaces

- `GET /api/teams/{id}/prospects` **already exists** and already batches a rating history —
  it gains the scouted band for that club.
- The league-wide prospect list rides `GET /api/players?status=prospects`, also already live.
- ⚠️ Both currently return raw values; the band has to be applied **server-side**. Sending
  true potential to the client and hiding it in the UI leaks it to anyone who opens the
  network tab.

### 2. The draft itself
Restore `rookieDraftPickGenerator` and the `rookie_draft` offseason phase, worst-first, one
pick per club. **Leave the fan ballot and its tally out** — `_promoteProspectsAutonomously`
is the pattern for replacing a ballot-driven decision with a brain-driven one.

### 2b. ⚠️ Move `_advanceProspectWindow` before the FA draft

Currently `_processFreeAgency()` runs at `seasonManager:6941` and
`_advanceProspectWindow()` at `:6994`, so a prospect who washes out is released into the pool
**after that offseason's FA draft has already run** — he is unsignable until the *next*
offseason and sits idle for a full extra season.

⚠️ **It costs twice**: `ensurePositionSupply` runs before the draft and excludes prospects, so
it generates a fresh free agent for a hole the washing-out prospect could have filled.

Move it to just after the promotions pass:

```
front office → promotions (last chance) → advanceProspectWindow → rookie draft →
supply floor → FA draft
```

✅ The released prospect is then in the pool for the draft about to happen (owner), the supply
floor counts him instead of replacing him, and this season's new draftees — not yet in
`team.prospects` — correctly start at `prospect_seasons = 0` instead of being incremented in
the offseason they arrived.

⚠️ **And the last window needs a real last chance.** `_promoteProspectsAutonomously` only
promotes into an **open slot** and only when the prospect beats `bestReplacementValue ×
FO_PROSPECT_PROMOTE_EDGE`. On the final window both tests are wrong: a club whose slot is
filled loses a 99-potential player at any quality, and the comparison is against a free agent
when the real alternative is **nothing**. See `docs/TRADING_PLAN.md` §5b for the three-option
fix (promote regardless of the bar / cut to make room, paying the cut fee / trade him).

### 3. The cull
New. Removes players who **never reached a roster** and have sat unsigned past a grace
window.

- Predicate: `seasonsPlayed == 0` **and** pool tenure ≥ 2 seasons **and** rating below a bar
  set *relative to the league's own mean*, not an absolute number (the same self-normalising
  argument as the anomaly threshold).
- ⚠️ **MUST exclude `is_prospect` and `drafting_team_id`** — prospects carry
  `seasonsPlayed == 0` by definition, so a naive rule deletes the class it just drafted.
- ⚠️ **Removal, not retirement**, and only for this population: a never-rostered player has no
  game rows, no season rows, and **no cards** (`generateSeasonTemplates` requires a real
  `teamId`). Anyone who has played keeps their record — today's 26 free agents hold 2,782
  game-stat rows and **253 user-owned cards** between them. *Never played → remove. Played →
  retire.*
- ⚠️ **The name returns as the BASE**, no Jr. `_recyclePlayerName` always advances the ladder,
  and a rung is earned *because the holder is gone* — minting a Junior for someone who never
  played invents a father nobody saw, which is the fault that left 39 orphaned variants on
  the season-1 production database. Return it **straight to `unused_names`**, skipping the
  `NAME_REUSE_DELAY_SEASONS` hold: that hold exists so a *familiar* name does not reappear,
  and nobody is familiar with a player who never played.

### 4. Surfaces (frontend only — both backends exist)
- **Stats page**: add `{ key: 'prospects', label: 'Prospects' }` to `STATUSES` in
  `StatsPage.tsx`. **One line** — the chip already reads `facets.prospects`, which is already
  in `StatsPlayersResponse`.
- **Team page**: a `SectionHead label="Prospects"` block under **Squad**, after the Roster
  block (`TeamPage.tsx:1375`), consuming `/api/teams/{id}/prospects`; optionally a
  `railSections` entry. The payload was shaped for this — rating, tier, seasons left in the
  window, and the sparkline series.

⚠️ Both surfaces render **empty until the draft ships**. Build them with it, not before.

## Traps

- ⚠️ **`ROOKIE_DRAFT_ENABLED = False` has ZERO readers.** Declared at `constants.py:2068` and
  read nowhere; flipping it does nothing, and its comment describes the switch in the present
  tense. Same trap class as `AUTONOMOUS_FO_ENABLED` documented directly beneath it, polarity
  reversed. Delete it or wire it, but do not start here believing it is the switch.
- ⚠️ **A promoted prospect has no card.** Templates exclude prospects and mint **once per
  season**, so a prospect promoted mid-season cannot be collected, equipped or scored until
  the next mint. That is the most visible fantasy-side consequence and it needs an owner call.
- ⚠️ **`_promoteProspectsAutonomously`'s bar is offseason-shaped.** It promotes only when the
  prospect beats `bestReplacementValue(…, pickDepth=)` — the free agent the club could sign.
  Mid-season there is no signing path at all, so the real alternative is an empty slot (which
  rates **50**). If promotion is ever wanted in-season, that bar must drop to near zero.
- `PROSPECT_SLOT_CAP_PER_POSITION` is 2 (ten per club). At one round a season against a
  three-season window a club holds at most three, so the cap is not binding and needs no
  change — but it *would* bind immediately at three rounds.
- ✅ Restoring the draft also makes the **Scouting Department** honest again: its UI copy says
  *"clearer read on draft prospects"* and it currently only sharpens free-agent reads.

## Open questions

1. ~~Does the class replace the trickle entirely~~ — **SETTLED** (owner, 2026-09-14):
   **`ensurePositionSupply` stays as a safety net.** The draft is the intake; the floor
   remains the per-position emergency it already is, firing only on a genuinely thin
   position, so it cannot double the faucet in normal operation.
2. ~~Where is the cull's rating bar~~ — **SETTLED**: **relative to the league mean**, not an
   absolute number. ⚠️ It cannot be calibrated against current data — none of today's 26 free
   agents have `seasonsPlayed == 0` — so the fraction has to be chosen on judgement and then
   measured once a class has actually cycled through.
3. ~~Can rookie picks be traded~~ — **SETTLED**: **yes.** Horizon (how many seasons out) is
   still open; two is enough to matter and bounds how far a club can mortgage itself.
4. ~~What happens to a mid-season promoted prospect's card~~ — **SETTLED** (owner,
   2026-09-14): *cards are only minted for players on rosters at the start of the season.*
   That is already the behaviour — `startNewSeason` calls `_generateCardTemplates` →
   `generateSeasonTemplates`, which requires a real `teamId` — so a prospect promoted in
   week 10 simply has no card until the next season's mint. **No work.**
