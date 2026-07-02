# Play-Calling Decision Tree

A complete reference of every play-calling **decision** the sim makes, scenario by scenario.
Source: `floosball_game.py` (line numbers cited throughout; approximate but current as of this doc).

The entry point is **`playCaller()`** (line 2980), called once per offensive snap. It resolves to
exactly one of: **Run**, a pass (`short` / `medium` / `long` / `deep` tier), **FieldGoal**, **Punt**,
**kneel**, **spike**, or a scripted **Hail Mary** heave.

Two sub-callers handle special phases:
- **`_otPlayCaller(scoreDiff)`** (2110) — all of overtime (Q5).
- **`_fourthDownCaller(scoreDiff, coach, isHome)`** (2237) — the full 4th-down FG / punt / go-for-it tree.

Where a branch is fully deterministic it is written `→ <PlayType>`. Where it rolls a die it is
marked **(probabilistic)** with the odds.

---

## 1. Overview — evaluation order inside `playCaller`

Every snap, `playCaller` (2980) records situation/composure insight, then walks these gates **in order**.
The first one that returns wins:

1. **Clock management** — only on non-final downs (`down < downsPerSeries`, i.e. downs 1–3), block at 3008:
   - **Kneel** (3015) — Q4/OT, leading, can drain the clock.
   - **Desperation / setup FG when trailing ≤3, ≤45s** (3046).
   - **Game-winning FG when tied, ≤45s** (3137).
   - **Spike** (3178).
   - **Offensive timeout** (3214) — this one *falls through* (does not return; still needs a play).
2. **Overtime** (3259) — if Q5, delegate to `_otPlayCaller` and return.
3. **End-of-half FG** (Q2, 4th down, 3310).
4. **End-of-game FG** (Q4, 4th down, within 3, 3320).
5. **Charged-kicker last-play FG** (3344).
6. **Hail Mary** (3359).
7. **4th down** (3387) — if `down == downsPerSeries`, delegate to `_fourthDownCaller`, then apply the
   charged-kicker "never punt" override, and return.
8. **Downs 1–3** (3410) — weighted random selection via `_computePlayWeights` + `_executeWeightedPlay`.

Note the structure: sections 3–6 only actually fire on the **last down** of the series (they check
`down == downsPerSeries`) *except* the charged-kicker last-play FG and Hail Mary, which are gated on
`_estimateAvailablePlays()` / time and can trigger on any down. Clock management (section 1) only runs
on downs 1–3. So on downs 1–3 the ladder is: clock-mgmt → (OT) → charged/Hail-Mary edge cases →
weighted selection. On down 4 the ladder is: (OT) → end-of-half/game FG → charged/Hail-Mary →
`_fourthDownCaller`.

---

## 2. Clock management (`playCaller`, checked first, downs 1–3 only)

All of section 2 is gated by `if self.down < self.gameRules.downsPerSeries:` (3009) — it never runs on 4th down.

### 2a. Kneel (3015)
**Triggers when ALL hold:**
- Quarter 4 or OT (`>= 5`).
- `scoreDiff > 0` (leading).
- `yardsToSafety > 2` (not backed up to own goal — a kneel loses 1 yard and could self-safety).
- The remaining downs' worth of kneels can drain the whole clock: `drainableSeconds >= gameClockSeconds` (3026).
  - Each free kneel drains `kneelDrainSeconds` (**40s**); a kneel the opponent can timeout only drains **4s**.
  - Opponent timeouts only count when the game is close: comeback cap is **8 pts** under 60s, **16 pts** otherwise (3020). Beyond that, opponent TOs are ignored (they won't burn them).

→ **kneel** (deterministic once the drain math clears).

If the drain math fails, falls through (a leading team backed up on own goal or with too much clock left just runs normal offense).

### 2b. Desperation / setup FG — trailing by ≤3, ≤45s (3046)
**Entry filter:** Q2/Q4/OT, `-3 <= scoreDiff < 0`, `gameClockSeconds <= 45`, and the spot is inside
kicker range (`yardsToEndzone <= kickerMax`). The ≤45s is coarse; the **real** gate is
`_estimateAvailablePlays()` (the "last play" signal, reserves ~7s for the kick).

Sub-decisions:
- **Last play** (`down == 4` OR `playsAvailable <= 1`, 3060) → **FieldGoal**. Kick even a long shot — it's the only chance. (trailing 1–2 wins, trailing 3 ties.)
- **2+ plays, long shot** (`fgProb < threshold` and `>8s`, 3073) → *fall through* to the weighted caller (advance to get closer).
- **2+ plays, WINNING FG in hand** (trailing 1–2, down < 4, 3075) → mostly **drain & kick on last play** (fall through to a play this snap), but **(probabilistic)** gamble for the TD with chance `clamp(0.22 + 0.35·aggrNorm − 0.30·gameIQ, 0.05, 0.50)`. Either way, falls through to a play now (the kick comes later).
- **2+ plays, TYING FG** (trailing 3, down < 4, 3105) → **(probabilistic)** defer to try for the winning TD with chance `clamp(0.94 + playsBonus + 0.03·aggrNorm + 0.02·gameIQ, 0.85, 0.99)` (fall through). Otherwise → **FieldGoal** now (rare; a coach settling for the tie).

### 2c. Game-winning FG — tied, ≤45s (3137)
**Entry:** Q4/OT, `scoreDiff == 0`, `gameClockSeconds <= 45`, not garbage time, in kicker range, and `fgProb >= 0.75` (chip-shot-ish).
- **Last play** (`down == 4` OR `playsAvailable <= 1`, 3151) → **FieldGoal** (kick to win).
- **Plays remain** (3161) → mostly **setup**: run to drain clock and kick later (→ **runPlay**, 3175). **(probabilistic)** aggressive push-for-TD instead with chance `clamp(0.10 + 0.25·aggrNorm − 0.15·gameIQ, 0.05, 0.40)` (fall through to normal caller).

### 2d. Spike (3178)
**Triggers when ALL hold** (3194):
- Q2/Q4/OT, `clockRunning`, `secs <= spikeClockThreshold` (**120s**).
- `timeoutsLeft == 0` and `scoreDiff <= 0` (trailing or tied, out of timeouts).
- Not garbage time.
- **Down gate** (`spikeDownOK`, 3193): spike allowed on 1st/2nd down (`down <= downsPerSeries-2`), OR the 3rd-down **FG exception** — 3rd down, within 3, in kicker range, `secs <= 20` (spike to stop clock, kick on 4th).

**(probabilistic)** spike chance:
- `secs <= 30`: `0.7 + 0.3·gameIQ`.
- else: `(0.3 + 0.4·gameIQ) · (1 − secs/150)`.

→ **spike** on success.

### 2e. Offensive timeout (3214) — falls through, does not return
**Triggers when ALL hold** (3232): Q2/Q4/OT, `scoreDiff <= 0`, `clockRunning`, `timeoutsLeft > 0`,
not garbage time, no imminent free two-minute-warning stop, and `secs <= toWindow`.
- `toWindow` = **180s** if Q4+ and (down ≥9 `multiScore` OR `fgStopPriority`), else `timeoutClockThreshold` (**120s**).
- `fgStopPriority` = trailing/tied and within ~8 yards of kicker range (must bank clock for a tying/winning FG).

**(probabilistic)** timeout chance:
- Inside 2:00 (`secs <= 120`): `0.5 + 0.5·gameIQ`; if `fgStopPriority`, floored to **0.9**.
- 2:00–3:00: `base · urgency`, where `urgency = (180−secs)/60` and `base` = `0.5 + 0.4·gameIQ` (fgStopPriority) or `0.2 + 0.45·gameIQ`.

On success it calls `_callTimeout` (stops clock, spends a TO) then **falls through** — a play is still called this snap.

---

## 3. End-of-half / end-of-game FG & Hail Mary (`playCaller`)

Computed once: `kickerCharged = _awakenedReadyFor(kicker, 'kick')`; `kickerMaxFg = 999` if charged
(makes it from anywhere) else `kicker.maxFgDistance − fgSnapDistance` (3303).

### 3a. End-of-half FG (3310)
**Q2, `gameClockSeconds < 120`, 4th down**, spot in range, and (`kickerCharged` OR `fgProb >= threshold`) → **FieldGoal**.

### 3b. End-of-game FG (3320)
**Q4, `gameClockSeconds < 120`, 4th down**, `-3 <= scoreDiff <= 3`, in range, and (charged OR `fgProb >= threshold`):
- **(probabilistic) go-for-it instead** when: `canAdvance` (`secs >= 30`), **not** charged, `fgProb < 0.55`, and `yardsToFirstDown <= 5`. Chance `0.45 + aggrNorm·0.30`. If it fires: `ytg<=2` → **runPlay**, else → **short pass**.
- Otherwise → **FieldGoal**.

### 3c. Charged-kicker last-play FG (3344)
**Charged kicker**, Q2/Q4, and `_estimateAvailablePlays() == 0` (guaranteed last play).
`fgWorthwhile` = Q2 (free 3 before the break) OR `-3 <= scoreDiff <= 0` (ties/wins). → **FieldGoal** (any distance, any down). Beats a Hail Mary.

### 3d. Hail Mary (3359)
**Q4, `scoreDiff < 0`, `yardsToEndzone >= 30`, not garbage time.** Only when a FG *can't* help
(`fgCanHelp` = trailing ≤3 AND in range — if true, skip, the FG paths handle it) AND
`gameClockSeconds <= 12` (the heave itself runs the clock out). → scripted deep pass **`Play9`**, sideline off.

---

## 4. Fourth down (`_fourthDownCaller`, 2237)

The biggest tree. First it sets sideline targeting (2240) and computes range/strategy flags:

- `kickerMaxDistance = kicker.maxFgDistance − fgSnapDistance` (2248).
- `kickerCharged = _awakenedReadyFor(kicker, 'kick')` (2255).
- **`fgHelps`** (2256) = `scoreDiff >= -3` **OR NOT** (Q4+ and `gameClockSeconds <= 300`). I.e. a FG is
  useless only when trailing by more than a field goal, late (Q4, ≤5 min). This gate is what stops a
  charged kicker or an inside-the-40 auto-kick from settling for 3 when a TD is required.
- **`inFieldGoalRange`** (2257) = `(kickerCharged AND fgHelps)` OR `(spot in range AND fgProb >= threshold)`.
  Note the charged kicker is only "in range" when the FG actually helps.
- **`leadingLate`** (2259) = `scoreDiff > 0` AND Q4+ AND `gameClockSeconds <= 120`.
- `goForItThreshold` (2293) = `clamp(round(4 + aggrNorm·3), 1, 9)` — a 1–10 die threshold scaled by coach aggressiveness.

### 4a. Deep own territory — `yardsToSafety <= 35` (2264)
- **Charged kicker + fgHelps + not leadingLate** (2269) → **FieldGoal** (take the free 3 from own territory).
- Else compute `isLateGameDesperation` (2272): Q4 & trailing & `<150s`, OR Q2 & `scoreDiff<=0` & `<60s` & past midfield.
  - **Not desperation** → **Punt** (2278).
  - **Desperation:**
    - **Q4 trailing under 2:00** (`gameClockSeconds < 120`, 2282) → **NEVER punt** — falls through to the go-for-it logic below (there's no way to punt and still get it back).
    - **2:00–2:30 window** → **(probabilistic)** only a poor clock-manager punts: punt if `random() >= 0.85 + 0.15·gameIQ` (2287). An average-or-better coach goes for it (falls through).

### 4b. Q2 end-of-half shot — `yardsToSafety > 35` (2310)
If `gameClockSeconds <= shotTimeThreshold` (`max(15, round(25 + aggrNorm·10))`, 2311):
- In range → **FieldGoal**.
- Else → shot at the endzone: **long pass** if `yardsToEndzone <= 60`, else **medium pass**.

### 4c. Never punt inside the opponent's 40

**Charged-kicker free-3** (2329): charged AND fgHelps AND not leadingLate AND `ytg > 2` AND `yardsToEndzone > 8` → **FieldGoal** (short-yardage/goal-line still defers to go-for-it below).

**Inside the 40** (`yardsToEndzone <= 40` and not leadingLate, 2333):
- `goForIt` defaults to `not inFieldGoalRange` (no makeable FG → must go).
- **`if not fgHelps: goForIt = True`** (2338) — a useless FG (trailing by >3, late) is never the auto-choice; go for the TD.
- **4th-and-short** (in range, `ytg <= 2`, 2340): **(probabilistic)** `goForIt = True` if `randint(1,10) <= goForItThreshold`.
- Resolve:
  - `goForIt` and `ytg <= 3` → **runPlay**; `goForIt` and `ytg > 3` → **medium pass** (`ytg<=12`) or **long pass**.
  - else → **FieldGoal**.

### 4d. Leading — `scoreDiff > 0` (2354)

**Q4 with < 5:00 (`gameClockSeconds < 300`)** (2355) — burn clock, protect the lead:
- **Kneel** (2364) if `gameClockSeconds <= kneelDrainSeconds` AND `yardsToSafety > 2` AND opponent has **0 timeouts** (only safe when it ends the game).
- In range and `yardsToEndzone <= 40` → **FieldGoal**.
- `ytg <= 1` and `yardsToSafety > 50` → **(probabilistic)** **runPlay** if `randint(1,10) <= goForItThreshold`.
- else → **Punt**.

**Q4 with ≥ 5:00, or Q1–3, leading** (2379):
- In range and `yardsToEndzone <= 35` → **FieldGoal**.
- `yardsToEndzone <= 40` and `ytg <= 3` (2383) → **(probabilistic)** go for it, threshold `clamp(round(6 + aggrNorm·3),1,9)` on a d10: `ytg<=1` → **runPlay**, else → **short pass**.
- else if `ytg <= 1` and `yardsToSafety > 45` (2393) → **(probabilistic)** **runPlay** if `d10 <= clamp(round(3 + aggrNorm·3),1,9)`.
- else → **Punt**.

### 4e. Trailing AND in FG range — `scoreDiff < 0 and inFieldGoalRange` (2401)

**Late Q4 (`gameClockSeconds < timeoutClockThreshold` = <120s)** (2404):
- **Deficit ≤ 3** (FG ties/wins, 2406):
  - `yardsToEndzone <= 10` → **FieldGoal** (chip shot, always).
  - else → **(probabilistic)** **FieldGoal** if `random() < 0.9 + 0.1·gameIQ`. Bad-coach blunder otherwise: `ytg<=5` → short pass, else medium pass.
- **Deficit 4–8** (FG doesn't tie, 2421):
  - If `secs >= 45`: **(probabilistic)** settle for FG with chance `timeFactor · max(0, 0.35 − 0.3·gameIQ)` (bad coaches settle). Below 45s no one kicks.
  - Else go for TD: short (`ytg<=5`) / medium (`ytg<=10`) / long pass.
- **Deficit 9+** (FG nearly meaningless, 2441):
  - Only a very conservative coach kicks: **FieldGoal** if `aggrNorm < -0.5`.
  - else go for TD: medium (`ytg<=5`) / long pass.

**Outside late Q4 — standard FG logic** (2452):
- `yardsToEndzone <= 25` → **FieldGoal**.
- Q3+ (2456): **(probabilistic)** **FieldGoal** if `d10 <= clamp(round(9 − aggrNorm·2),5,10)`, else medium pass.
- Q1–2 (2464): **(probabilistic)** **FieldGoal** if `d10 <= clamp(round(7 − aggrNorm·2),4,9)`, else medium pass.

### 4f. Trailing, NOT in FG range — `scoreDiff < 0` (2473)

**Q4** (2476), `aggrMod = aggrNorm·0.15`:
- **Under 2:30 (`secs < 150`)** → always go for it (2481): short (`ytg<=3`) / medium (`ytg<=10`) / long pass.
- **2:30–5:00 (`secs <= 300`)** (2492):
  - Deficit ≤ 8: `ytg<=3` → short; `ytg<=8` → medium; else **(probabilistic)** long pass if `random() < 0.3 + 0.5·gameIQ + aggrMod` (else falls through to Punt).
  - Deficit 9–16: `ytg<=3` → short; `ytg<=5` → **(probabilistic)** medium if `< 0.7 + 0.2·gameIQ + aggrMod`; else → **(probabilistic)** long if `< 0.55 + 0.3·gameIQ + aggrMod`.
  - Deficit 17+ → always **long pass**.
- **5:00+** (2523): deficit ≤8 & `ytg<=2` → short pass; deficit ≤8 & `ytg<=5` → **(probabilistic)** short pass if `random() < max(0, 0.1 + aggrMod)`; else falls through to **Punt** (2546).

**Q2 two-minute drill** (2534): Q2, `secs < 60`, past midfield (`yardsToSafety > 50`) → go for it: short (`ytg<=3`) / medium (`ytg<=10`) / long pass.

**Q3, deficit ≤8, `ytg<=2`** (2543) → **short pass**.

Everything else in this branch → **Punt** (2546).

### 4g. Tied (`scoreDiff == 0`) and the general FG-range tail (2554+)

Reached when not leading, not trailing (tied) — or trailing-in-range cases already returned above.

**Tied, Q4, advance-for-better-FG gamble** (2554): Q4 & tied & inFieldGoalRange & `secs >= 30` & `ytg <= 5` & `yardsToEndzone > 15` & `fgProb < 0.92` → **(probabilistic)** go for it (advance to a shorter FG / winning TD). `goBias = max(0, aggrNorm)`; chance `0.10 + goBias·0.40` (`ytg<=2`) or `0.05 + goBias·0.20`. If it fires: `ytg<=2` → runPlay, else short pass.

**Field-position FG/go-for-it tail** (in FG range):
- `yardsToEndzone <= 5` (2575) → **(probabilistic)** **FieldGoal** if `d10 < 7`; else a sub-roll: runPlay / short / medium.
- `yardsToEndzone <= 20` (2592): if `ytg <= 1` → **(probabilistic)** go for it (`d10 >= 7`: runPlay or short pass); otherwise → **FieldGoal**.
- `yardsToEndzone <= 35` (2606): if `ytg <= 2` → **(probabilistic)** **FieldGoal** if `d10 <= 7`, else runPlay/short; else → **(probabilistic)** **FieldGoal** if `d100 <= 85`, else medium pass.
- else in range (2629) → **(probabilistic)** **FieldGoal** if `d10 <= 7`, else **Punt**.

**Out of FG range tail** (2638) — tied/trailing, no FG option:
- `ytg == 1` (2640): go-for-it only if `yardsToSafety >= 50` OR (`scoreDiff < -14` and Q3+); then **(probabilistic)** **runPlay** if `d10 <= clamp(goForItThreshold-1, 1, 7)`. Else → **Punt**.
- `ytg == 2` (2648): go-for-it only if (`yardsToSafety >= 50` and `goForItThreshold >= 5`) OR (`scoreDiff < -21` & Q4 & `<600s`); then **(probabilistic)** **short pass** if `d10 <= clamp(goForItThreshold-3, 1, 5)`. Else → **Punt**.
- `ytg >= 3` (2656): go-for-it only if (`yardsToSafety >= 55` & `ytg <= goForItThreshold` & `goForItThreshold >= 6`) OR (`scoreDiff < -17` & Q4 & `<300s`); then **(probabilistic)** **medium pass** if `d10 <= clamp(goForItThreshold-4, 1, 4)`. Else → **Punt**.

### 4h. Charged-kicker "never punt" post-override (`playCaller`, 3394)
After `_fourthDownCaller` returns, if the decision was **Punt** and the kicker is **charged** and
`fgHelps`, the punt is rewritten to → **FieldGoal** (a charged kicker makes it from any field position).

---

## 5. Overtime (`_otPlayCaller`, 2110)

Q5 only. `kickerCharged` → treat whole field as in range (`kickerMaxFg = 999`).
`isFirstPoss` (2122) = the first OT possession (a FG here doesn't win — the other team still gets a guaranteed answer).

### 5a. Early-down FG to win (downs 1–3, 2135)
When `down < 4`, `scoreDiff >= -3`, **not** first possession, **not** `fgOnlyTies` (`scoreDiff == -3`),
and in range: kick only on a near-automatic FG. `earlyDownFgThreshold = 0.92 − aggrNorm·0.04` (aggr 60→0.96, 100→0.88).
→ **FieldGoal** if `kickerCharged OR fgProb >= earlyDownFgThreshold`. Otherwise play on.

### 5b. Final down (`down == 4`, 2144)
- **Ties/wins & in range** (`scoreDiff >= -3`, charged OR `fgProb >= threshold`, 2150):
  - **Long-shot go-for-it** (`fgProb < 0.55` and `ytg <= 5`): **(probabilistic)** convert with chance `0.45 + aggrNorm·0.30` — `ytg<=2` → runPlay, else short pass.
  - Otherwise → **FieldGoal**.
- **Tied** (`homeScore == awayScore`, 2164): `ytg<=3` → **(probabilistic)** 50/50 runPlay vs short pass; `ytg<=7` → medium pass; `ytg<=15` → long pass; else → **Punt** if `yardsToSafety < 15`, else long pass.
- **Leading** (`scoreDiff > 0`, 2186): `ytg<=2` → short pass; `ytg<=8` → medium pass; else → long pass.
- **Trailing** (else, 2196): `ytg<=10` → medium pass; else long pass.

### 5c. Downs 1–3 in OT (2204)
- `targetSideline = _shouldTargetSideline(...)`.
- **Tied and in FG range** (2211):
  - **First possession** (2212) → weighted play for a TD (protect the ball): weights `{run 40, short 30, medium 25, long 5}`.
  - **Later possession** (2218): **(probabilistic)** kick now with `fgChance = fgEase · (downBase + clockIQ·0.25)`, where `downBase = {1:0.05, 2:0.15, 3:0.40}` and `fgEase = (fgProb − threshold)/(0.96 − threshold)`. On hit → **FieldGoal**; else conservative weights `{run 55, short 30, medium 15, long 0}`.
- **Otherwise** → `_computePlayWeights(scoreDiff, coach)` and weighted selection (same engine as regulation downs 1–3).

---

## 6. Downs 1–3 — weighted random selection

On downs 1–3 (regulation), the call is a **weighted random draw**, not a deterministic pick.
`_computePlayWeights` (2702) builds a `{run, short, medium, long, deep}` weight dict, and
`_executeWeightedPlay` (2964) samples it with `random.choices`. So the *same* situation can produce
different calls run-to-run; the layers below shift the **odds**, not the outcome.

### Layer 0 — base table (`_getBasePlayWeights`, 2665)
Raw weights keyed on **down × yards-to-go**, tuned to ~60/40 pass/run across a drive. Examples:
- 1st down: `{run 50, short 22, medium 18, long 8, deep 2}` (balanced; the biggest lever).
- 2nd & short (≤4): run-heavy `{run 58, ...}`; 2nd & long (>9): pass-heavy `{run 22, ..., long 26}`.
- 3rd & short (≤3): `{run 60, short 32, ...}`; 3rd & extra-long (>12): `{run 6, ..., long 61, deep 8}`.

### Layer 1 — situational (`_applySituationalMods`, 2720)
Game-state multipliers, **scaled by coach clock IQ** (`sit = 0.4 + 0.6·clockIQ` — a bad coach applies
only ~40% of the ideal shift). Applies via `_mul` (coach-scaled) or `_flat` (full strength):
- **Q4 last 2 min trailing** (2754): universal desperation — crush run (×0.1), boost medium/long/deep. No coach modulation.
- **Trailing by >7, Q3 / Q4 w/ time** (2766): coach-identity split. Disciplined (high adapt, low aggr) → sustainable short/medium. Panic (high aggr, low adapt) → extra deep/long (drives die faster). Scaled by deficit tier.
- **Leading by >7, Q3/Q4** (2800): archetype split — killer (press), clock-killer (run + kill deep), reckless (keep chucking), cruise (no change).
- **Protecting a 1–7 lead late Q4/OT** (2840): ramp run/short up, long/deep down as clock winds (coach-scaled).
- **Q2 two-minute drill** (2859): regardless of score, pass-first hurry-up; deeper if trailing.
- **Field position** (2867): red zone (`yardsToEndzone <= 15`) boosts run, kills long/deep; backed up (`yardsToSafety <= 5`) boosts run, trims short/long/deep.

### Layer 2 — matchup (`_applyMatchupMods`, 2878)
Adjusts run vs pass by the **defense's** run-coverage and pass ratings, scaled by coach **adaptability**
(one-directional: `max(0, adaptNorm)` — below-neutral adaptability has no matchup effect). Weak run D →
boost run; strong run D → trim run; weak pass D → boost all pass tiers.

### Layer 3 — coach personality (`_applyCoachMods`, 2897)
Multiplies by coach **aggressiveness** and **offensiveMind**:
- Deep scales hardest with aggressiveness (`×(1 + 1.8·aggrNorm)`), then long, medium; run/short are nerfed but **floored** (run ≥0.65×, short ≥0.65×) so the run stays viable even for max-aggressive coaches.
- offensiveMind boosts medium/long/deep, trims short.

### Layer 4 — FG drain mode (`_computePlayWeights`, 2712)
If `_isFgDrainMode()` (late Q2/Q4, within 3, chip-shot range): bias hard toward in-bounds runs (run ×3),
suppress downfield passes (medium ×0.3, long ×0.15, deep ×0.05) so the clock keeps running toward the FG snap.

### Pass-tier play selection (`_selectPassPlay`, 2924)
Once a pass tier is chosen, the specific play is drawn from that tier's pool, weighted by each targeted
receiver's `routeRunning` vs the defense's pass-coverage rating, scaled by coach offensiveMind
(60→uniform, 100→fully exploit the best matchup).

---

## 7. Key terms / helpers

- **`scoreDiff`** — offense's score minus defense's (negative = trailing).
- **`yardsToEndzone`** — distance to the opponent's goal (FG distance = `yardsToEndzone + fgSnapDistance`, snap = **17**).
- **`yardsToSafety`** — distance to the offense's OWN goal (`fieldLength − yardsToEndzone`); low = backed up / deep own territory.
- **`fgHelps`** (2256) — a FG is worth kicking: `scoreDiff >= -3` OR not (Q4+ and ≤5:00). False = need a TD, don't settle for 3.
- **`inFieldGoalRange`** (2257) — makeable FG that helps: charged+fgHelps, or (spot in kicker range AND `fgProb >= coachThreshold`).
- **`kickerCharged`** (`_awakenedReadyFor(kicker, 'kick')`) — an awakened/powered-up kicker; makes it **from anywhere**. Never punts (when fgHelps); kicks the last play of a half from any distance.
- **`leadingLate`** (2259) — `scoreDiff > 0` AND Q4+ AND ≤2:00; the one case that may still punt from inside the opponent's 40 (coffin-corner pin).
- **`_coachClockIQ(coach)`** (1449) — normalizes `clockManagement` 60–100 → 0.0–1.0 (0.5 neutral). Gates the quality of nearly every situational/clock decision.
- **`_estimateAvailablePlays()`** (1846) — the **"last play" signal**. Conservative count of productive snaps left, **reserving ~7s for a closing FG**. `0` = only time to snap the FG itself; `1` = one more snap then kick. Accounts for timeouts (~3s stop), spikes (~5s, 1st/2nd down only), and sideline/incomplete (~18s).
- **`_isFgDrainMode()`** (1458) — late Q2/Q4, within 3 (trailing/tied), chip-shot range (`fgProb >= 0.75`). Suppresses sideline passing and bumps runs to bleed clock toward the FG snap.
- **`_shouldTargetSideline(scoreDiff, coach)`** (1912) — **(probabilistic)** whether a pass targets the sideline to stop the clock. Only when trailing/tied in Q2/Q4; scales with time urgency, timeout scarcity, coach clock IQ.
- **`_estimateFgProbability()`** (2059) — logistic make-probability from FG distance + kicker rating (short kicks get a +0.10 bump).
- **`_coachFgThreshold(coach)`** (2072) — minimum make-prob a coach requires. Base **0.20** (`fgMinAttemptProb`), shifted by aggressiveness (±0.08) and the kicker's in-game make/miss record; clamped **0.10–0.35**.
- **`maxFgDistance` / `kickerMaxDistance`** — kicker's max FG distance (reads the in-game, possibly boosted leg via `updateInGameRating`); minus `fgSnapDistance` gives the max `yardsToEndzone` that's in range.
- **`goForItThreshold`** (2293) — `clamp(round(4 + aggrNorm·3), 1, 9)`, used as a d10 cutoff for 4th-down go-for-it rolls (aggressive coaches go more often).
- **Rules constants** (`game_rules.py`): `downsPerSeries` **4**, `firstDownDistance` **10**, `timeoutClockThreshold` / `spikeClockThreshold` **120s**, `kneelDrainSeconds` **40s**, `fgSnapDistance` **17**, `fgMinAttemptProb` **0.20**, quarter **900s**, OT **600s**.

---

## Notes, ambiguities & dead/legacy branches observed

- **Section-order subtlety**: sections 3a–3d in `playCaller` mostly guard on `down == downsPerSeries`, so on downs 1–3 they no-op and control reaches the weighted caller (except the charged/Hail-Mary edge cases which are down-agnostic). The 4th-down block (section 7 of the overview) is where the real 4th-down tree lives.
- **`_fourthDownCaller` FG-range tail (4g) reachability**: the `scoreDiff == 0` (tied) path and the general FG/punt tail at 2554–2663 are reached when neither the leading (2354) nor trailing-in-range (2401) nor trailing-out-of-range (2473) branches returned. In practice this is the **tied** case plus any leading/trailing fall-through; the code comments describe it as "tied or trailing (outside Q4 urgency)". Worth noting the tail re-derives field-position FG logic that partly overlaps the inside-the-40 block (4c) — not a bug, but two places encode near-goal FG preference.
- **Deep-own-territory desperation punt window (4a)**: the 2:00–2:30 punt is the only place an average coach can still punt when trailing late; under 2:00 punting is hard-disabled. This matches the CLAUDE.md note about the "under 2 minutes never-punt window".
- **`fgOnlyTies` in OT (5a)** correctly forces play-for-TD when down exactly 3 on early downs, but the *final-down* OT block (5b) still lets a down-3 team kick the tying FG — intended (tie keeps OT alive) but asymmetric with the early-down suppression.
- **`randint` vs `batched_randint`**: the tree mixes `batched_randint(1,10)` with plain `randint(1,3)` in a couple of sub-rolls (2596, 2613). Functionally equivalent for the decision; just an inconsistency.
- **`_estimateAvailablePlays` spike budget** assumes a spike is only available on 1st/2nd down; consistent with the spike down-gate in `playCaller`. No dead code found, but the reserved-7s coupling between `_estimateAvailablePlays` and the FG paths is subtle — changing the FG snap reserve would shift every "last play" decision.
- **No per-game play cap**: consistent with CLAUDE.md, nothing here keys off a play count; all timing gates read `gameClockSeconds`.
