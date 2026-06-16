# Collectible Cards — build spec

**Status:** designed 2026-06-16, not built. Branch: `next-season`.

## Motivation
The Showcase rewards quality (fresh, high-edition, decorated cards), and S tier now
demands multiple fresh decorated **diamonds** (see `docs/SHOWCASE_TUNING` notes /
`showcaseManager.py`). But the fantasy economy is intentionally scarce — 5 packs per
shop cycle, no guaranteed prismatic/diamond, ~1.3% diamond pulls — so reaching S by
pulling fantasy diamonds is nearly impossible, and bumping fantasy pull odds would
inflate fantasy power.

**Solution: a collectible-only card class.** Cards that can be vaulted/showcased but
**never equipped in fantasy**. Because they can't be played, their edition and
classification are pure collection cosmetics with **zero fantasy-balance impact** — so
we can sell decorated diamonds (legends, HOF, past MVPs) freely. This gives collectors a
satisfying, balance-safe path to S and a recurring **Floobit sink**, and gives retired /
HOF / past-season players a card presence.

## Locked decisions
- **Sale model: BOTH** — collector packs (random chase) AND a direct store (buy a
  specific card toward a set).
- **Pool: ALL players** — current, past-season stars, retired, and HOF.
- **Auto-vault on acquisition** — collectible cards go straight into the permanent Vault
  (no reveal/keep, no equipped-pool step). Inherently blocks equip/sell/Combine.
- **Mint-season recency** — a collectible's `season_created` = the season it is
  bought/minted, NOT the player's era. So a "Diamond HOF [legend]" bought this season is
  fresh (recency ×1.0) and decays normally. Reuses the existing recency engine; keeps the
  "keep buying new ones" pressure; no special-casing in the showcase.
- **Separate from the fantasy pack cap** — collector packs do NOT count toward
  `MAX_PACKS_PER_SHOP_CYCLE` (that cap exists to protect fantasy/Combine supply).

## Data model
- **`CardTemplate.collectible_only`** — Boolean, default False, NOT NULL. Inline migration
  (`ADD COLUMN ... DEFAULT 0`). The single source of truth for "not fantasy-eligible."
  (Positive flag matches the codebase's `is_*`/`*_only` style.)
- No new column on `UserCard` — collectibles reuse `vaulted=True` + `acquired_via`
  (`collector_pack_*` / `collector_store`).
- Collectible templates carry: `player_id/player_name/team_id/position/player_rating`
  (snapshot), `edition`, `classification`, `season_created = mint season`,
  `collectible_only=True`, `effect_config = None` (no fantasy effect), `output_type = None`,
  `is_rookie=False`. They are minted on demand at purchase, not seeded per season.

## Player pool sourcing (`collectibleCandidates(season)`)
Build the buyable pool from the Player table. **Every player is eligible** (undecorated
included), but each is **tiered by their real record**, which gates the max edition and the
classification — you can only buy a "diamond legend" for an actual legend, and you can only
buy an "MVP" card for an actual MVP. (Prod counts ~season 10 in parens.)

| Tier | Who | Count | Max edition | Classification |
|------|-----|-------|-------------|----------------|
| Immortal  | `is_hof` OR all-three accolades | 3  | diamond   | real compound (MVP+AllPro+Champ) |
| Elite     | 2+ accolade types               | 18 | diamond   | their real compound tags |
| Decorated | exactly 1 accolade type         | 38 | prismatic | MVP / AllPro / Champ |
| Journeyman| undecorated (current + retired) | ~370 | holographic | none |

**Retired-player eligibility filter** — a perennial free agent isn't a collectible legend.
A retired player is included only if **decorated OR rostered for the majority of their
career** (`seasons_played >= 2 × free_agent_years`). Decorated players are always kept (they
earned their card). Prunes ~70 of 135 retired journeymen. `free_agent_years` is cumulative;
rostered seasons ≈ `seasons_played − free_agent_years`. (Current/active players are rostered
by definition, so the filter only applies to the retired/Legends pool.)

**Accolade sources** (Player table): `is_hof`; `mvp_awards` (→ mvp), `all_pro_seasons`
(→ all_pro), `league_championships` (→ champion) — JSON lists, non-empty = holds that tag.
Classification = the compound of all tags a player actually holds. **Max edition is gated by
tier** (above): undecorated cap at holo, single-accolade at prismatic, 2+/HOF at diamond. So
a fresh decorated **diamond** can only exist for an Elite/Immortal player — keeping S scarce.

- **Direct store**: lists each eligible (player × allowed-edition) at a price scaling with
  edition × classification; the buyer picks the exact card. Edition choices are clamped to
  the player's tier cap.
- **Packs**: draw a player from the pack's pool, then an edition from the pack's rarity
  weights **clamped to that player's tier cap** (so a Journeyman pulled from a pack maxes at
  holo even if the pack rolls "diamond"). Classification always = the player's real tags.

**S-supply reality:** only ~18 players can be a compound-class diamond and only 3 the
all-three; an 8-slot compound-diamond S showcase means owning 8 of ~18 — a finite chase that
grows a few players/season. Good: S stays a genuine multi-season goal.

**Pool → pack mapping:** Legends Pack = retired (135; 13 decorated); Throwback Pack =
decorated past-season stars (56); Current = active league (144). **HOF Pack is only 3
players today** — fold HOF into a broader premium "Immortals/Legends" pool until HOF grows.

## Collector packs (Phase 2)
New `PackType` rows (seeded in `seedDefaults`), marked collectible (reuse a naming prefix
`collector_*` and/or a `theme_type='collectible'` discriminator the draw path keys off):
- **Legends Pack** — retired-player pool.
- **Hall of Fame Pack** — HOF pool (premium; weights skew prismatic/diamond).
- **Throwback Pack** — past-season stars (optionally theme_value = a season).
- (Current-player collectibles can ride the general pool too.)
Pack open: draw from collectible templates (mint on demand), create UserCards with
`vaulted=True`. NOT counted toward `MAX_PACKS_PER_SHOP_CYCLE`. Own cap TBD (likely
Floobit-gated only, or a generous collector cap).

## Direct store (Phase 3)
- `GET /api/collectibles/store` — list buyable collectible cards (player × edition ×
  classification) with prices. Paginated/filterable by pool (legends/hof/stars/current),
  position, edition.
- `POST /api/collectibles/buy` — spend Floobits, mint the chosen collectible template,
  create the UserCard `vaulted=True`. Pricing by edition × classification (the key balance
  lever — see below).

## Fantasy-gate exclusions (Phase 1, belt-and-suspenders)
`vaulted=True` already blocks equip/sell/Combine, but also guard on `collectible_only`:
- **Equip** (`api/main.py` `setEquippedCards`, ~8932): reject `collectible_only`.
- **Combine / Level-Up** (`cardManager.blendCards`, `levelUpCard`): reject `collectible_only`
  as offering or target.
- **Fantasy pack pool** (`cardManager._drawPackCards` / theme filter): exclude
  `collectible_only` templates so they never appear in fantasy packs. Conversely collector
  packs draw ONLY `collectible_only` templates.
- **Roster match** (`cardEffectCalculator`): no change needed (only equipped cards reach it).

## Showcase interaction (no code change, but a balance note)
Collectibles flow through `UserCard → card_template`, so `showcaseManager` scores them with
no change. They count toward set bonuses (incl. **Diamond Vault** / **Hall of Fame** /
**All-Pro Line**) and S. This is intended: collectibles ARE the path to S.
**Balance lever = direct-store / pack pricing.** A full fresh-diamond showcase (S) should be
a serious multi-season Floobit investment, not a cheap buy. Tune prices so:
- one decorated collectible diamond ≈ a meaningful fraction of a season's Floobit income;
- assembling 6–8 fresh decorated diamonds (S) costs roughly a season-plus of dedicated
  saving. Validate against the Floobit income curve + `tune_showcase.py`.

## Build phases
1. **Schema + gates**: `collectible_only` column + migration; `mintCollectibleTemplate()`
   helper; exclude from fantasy pack pool; equip/Combine/Level-Up guards. (No user-visible
   change yet.)
2. **Collector packs**: PackType seed + collectible draw path + auto-vault open; exclude
   from fantasy cap.
3. **Direct store**: list + buy endpoints; pricing table.
4. **Frontend**: Collector shop (packs + store tabs), "Collectible — not playable" card
   badge, collectibles surfaced in Vault/Showcase pickers.
5. **Balance pass**: price/rarity tuning vs. Floobit income + showcase S-reachability (sim).

## Open questions
- Collector-pack cap (uncapped + Floobit-gated, or its own per-cycle cap)?
- Should the direct store stock ALL editions for every eligible player, or only editions
  justified by accolades (e.g. only HOF players sell as diamond)? Leaning accolade-gated so
  a diamond collectible means something.
- Do collectibles get distinct visual chrome vs fantasy cards (recommended — a clear
  "collectible" frame so users don't confuse them with playable cards)?
