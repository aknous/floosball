# Ceiling / Projection Unification Plan

Builds on the three-tier prospect model (`docs/PARITY_PROSPECT_PLAN.md`): every physical
attribute now carries **current ≤ trueSkill ≤ potential**. New prospects debut *below*
trueSkill and develop up into it; **potential** is the best case, reachable only with good
player development (coach `playerDevelopment`). Mental attributes don't train — they're set
at final value at creation — so every overall projection lifts only the 8 physical attrs.

## Problem

Two "ceiling" numbers exist and disagree, and the profile one leaks scouted info:

1. **Rookie card** shows `blur(potentialSkillRating)` (e.g. "97–100") — a **skill sub-rating**
   at full potential, structurally higher than an overall rating.
2. **Profile dotted line** shows `computeCeilingRating()` — an **overall rating** at full
   potential. Different metric, so it reads far lower and looks like it "sits on current."
3. The profile line is served for **undrafted prospects too**, revealing an exact projection
   that the rookie ballot deliberately blurs — a loophole around scouting fog-of-war.

## Goals

- **One family of overall projections** used everywhere: `Expected` (overall at trueSkill) and
  `Ceiling` (overall at potential). Blurred on the scouting board, exact once revealed.
- **Two markers** on both the rookie card and the profile: Expected + Ceiling.
- **Hide both projections for undrafted prospects**; reveal the moment a team drafts them.
- Rookie card drops the per-attribute potential ranges entirely (headline projections only).

Note: the unified numbers read *lower* than today's "97–100" — intended. The old number
overstated by ignoring the (non-growing) playmaking/xFactor terms.

---

## Backend

### 1. Add `computeExpectedRating()` — `floosball_player.py` (next to `computeCeilingRating`, ~376)

Mirror `computeCeilingRating()` but target the **trueSkill** attrs instead of potential.
Same structure: lift only the 8 physical attrs, recompute the real overall rating, restore.

```python
def computeExpectedRating(self):
    """Projected 'expected' rating: overall rating with every physical attr at its
    trueSkill (the level the player naturally develops into). Returns current rating
    when already developed in (current >= trueSkill) or no trueSkill data exists."""
    attrs = getattr(self, 'attributes', None)
    if attrs is None:
        return int(round(getattr(self, 'playerRating', 0) or 0))
    pairs = [(a, t) for (a, t, _p) in _TRUESKILL_ATTR_TRIPLES]   # (live, trueSkill)
    saved = {}
    try:
        for base, tru in pairs:
            cur = getattr(attrs, base, None)
            truVal = getattr(attrs, tru, None)
            if cur is not None and truVal and truVal > cur:
                saved[base] = cur
                setattr(attrs, base, truVal)
        if not saved:
            return int(round(getattr(self, 'playerRating', 0) or 0))
        self.updateRating()
        return int(round(getattr(self, 'playerRating', 0) or 0))
    finally:
        for base, val in saved.items():
            setattr(attrs, base, val)
        if saved:
            self.updateRating()
```

`computeCeilingRating()` is unchanged (already correct — targets `potential*`). Its
fallback-to-current is *correct* when there's no headroom (frozen legacy pool).

By construction `computeExpectedRating() <= computeCeilingRating()` (trueSkill ≤ potential).

### 2. Suppression gate — one helper

Undrafted future player = `drafting_team_id is None AND (is_upcoming_rookie OR is_prospect)`.
Add a tiny predicate (e.g. in `api/main.py` near the player serializers, or as a Player method):

```python
def _isUndraftedProspect(p) -> bool:
    return (getattr(p, 'drafting_team_id', None) is None
            and (getattr(p, 'is_upcoming_rookie', False) or getattr(p, 'is_prospect', False)))
```

### 3. Player detail endpoint — `api/main.py` (~1030)

```python
if _isUndraftedProspect(player):
    player_dict['expected'] = None
    player_dict['ceiling'] = None
else:
    try:
        player_dict['expected'] = player.computeExpectedRating()
        player_dict['ceiling']  = player.computeCeilingRating()
    except Exception:
        player_dict['expected'] = None
        player_dict['ceiling']  = None
```

### 4. Rating-history endpoint — `api/main.py` (~6935)

Compute both, gated by `not _isUndraftedProspect(player)`. Keep the existing
`ceiling = max(ceiling, maxHist)` floor for **ceiling only** (a past-peak vet may have topped
their current potential). **Do not floor `expected`** — a declining vet legitimately sits
below past peak; render it only when it's meaningfully above current (see frontend). Return
both `expected` and `ceiling` in the payload.

### 5. `scoutRookie()` — `managers/playerManager.py` (~4215)

Replace the per-attribute `potentials` payload with two blurred overall projections:

```python
exp = ceil = None
try:
    exp  = rookie.computeExpectedRating()
    ceil = rookie.computeCeilingRating()
except Exception:
    pass
return {
    ...,                                        # playerId/name/position/rating/tier/longevity
    "projectedExpected": blur(exp, 'overallExpected') if exp else None,
    "projectedCeiling":  blur(ceil, 'overallCeiling') if ceil else None,
    "scoutingAccuracy": effectiveScouting,
    "scoutingRange": rangeSize,
}
```

`blur()` is unchanged — it already clamps to `[60,100]` (fine for overall ratings) and seeds
deterministically per `(player, attrName)` so users can't average out the noise by polling.
Drop the old `potentials` map and the per-attribute loop (card no longer shows them).

---

## Frontend (`../floosball-react`)

### 6. `RookiesSection.tsx`
- `ScoutedRookie` type: remove `potentials`; add `projectedExpected?: PotentialRange` and
  `projectedCeiling?: PotentialRange`.
- Replace the single "Skill Ceiling" column + `PotentialCell` per-attribute usage with two
  headline cells: **Expected** (`projectedExpected.low–high`) and **Ceiling**
  (`projectedCeiling.low–high`). Delete the per-attribute rows/`PotentialCell` for potentials.

### 7. `PlayerPage.tsx` — `RatingHistoryChart` (~1296, 1358)
- Add an `expected?: number | null` prop alongside `ceiling`.
- Draw a **second dotted line** for expected in a distinct color (ceiling stays amber
  `#facc15`; expected in a cooler tone, e.g. `#38bdf8`), guarded `expected != null &&
  expected > 0 && expected > currentRating` so it only shows when it's a real upward target.
  Label "Expected NN" mirroring the "Ceiling NN" pill; nudge labels apart if the two lines
  are within a few px.
- Wire `expected={ratingExpected}` from a new state set off `historyRes.data?.expected`.

### 8. `PlayerHoverCard.tsx` (~209)
- Add a second tick for `data.expected` (guarded `expected > playerRating`), styled to match
  the chart's expected color. Add `expected?: number | null` to the props type.

Both the chart and hover already no-op when the value is `null`, so undrafted prospects
render neither marker with zero extra guarding.

---

## Edge cases
- **Legacy frozen pool** (parity remap set trueSkill=potential=current): both projections
  return current → both markers hidden (nothing above current). Correct — no growth left.
- **Drafted-but-not-promoted prospect** (`drafting_team_id` set, `is_prospect=True`): gate
  passes → exact Expected + Ceiling shown (per "reveal once drafted").
- **Overlapping blurred ranges**: Expected and Ceiling bands may overlap after blur; that's
  acceptable fog. Exact centers stay ordered (trueSkill ≤ potential).
- **Other leak sites**: audit `api/main.py:1976, 4979, 4983` and any serializer that could
  emit `computeCeilingRating()` / raw `potential*` for an undrafted prospect. Only
  `scoutRookie()` (blurred) should expose a prospect's projection.

## Validation
1. Fresh fast sim to a live rookie class (`/simcheck` or `--fresh --timing=fast`).
2. `/api/players/upcoming-rookies` → both blurred ranges present, `projectedExpected` ≤
   `projectedCeiling` centers; no per-attribute `potentials`.
3. Undrafted prospect `/api/players/{id}` + `/rating-history` → `expected: null, ceiling: null`.
4. After the rookie draft, a drafted prospect → exact `expected`/`ceiling` present.
5. A rostered developing player → chart shows both dotted lines, ceiling ≥ expected ≥ current.
6. UI: rookie card shows two ranges, no per-attribute rows; prospect profile shows no lines;
   drafted/rostered profile shows both.

## Branch
Depends on the next-season three-tier prospect model → build on **`next-season`** (kept off
latest `main`), not `development`. Gated on the season flip, consistent with the parity package.
