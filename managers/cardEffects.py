"""
Card Effects — shared-pool effect system with 100+ named variants.

Effects are drawn from a shared pool available to all positions, plus small
position-exclusive pools for effects that reference position-specific stats
(passing yards, rushing attempts, receiving YAC, kicker FGs, etc.).

Each effect retains its natural category (flat_fp, multiplier, floobits,
conditional, streak, cross) for param building and output-type derivation.

Edition IS the effect tier — each effect belongs to exactly one edition
(base, holographic, prismatic, diamond). No power scaling or secondary bonuses.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from logger_config import get_logger

logger = get_logger("floosball.cardEffects")


# ─── Effect → Category Mapping ──────────────────────────────────────────────
# Maps every effect name to its natural category (reward/behavior type).
# Used for param builder dispatch and output-type derivation.

EFFECT_CATEGORY = {
    # flat_fp
    "freebie": "flat_fp", "entourage": "flat_fp", "touchdown_pinata": "flat_fp",
    "scrappy": "flat_fp", "honor_roll": "flat_fp", "garbage_time": "flat_fp",
    "loyalty_bonus": "flat_fp", "windfall": "floobits",
    "spotlight_moment": "flat_fp", "possession": "flat_fp", "ace_up_the_sleeve": "flat_fp",
    "slippery": "flat_fp", "jailbreak": "flat_fp", "homer": "flat_fp", "gone_streaking": "flat_fp", "rng": "flat_fp", "avalanche": "flat_fp", "hedge": "flat_fp",
    "three_pointer": "flat_fp", "safety_blanket": "flat_fp",
    "industrious": "floobits", "sniper": "flat_fp", "lead_blocker": "flat_fp",
    # multiplier
    "big_deal": "multiplier", "cornucopia": "multiplier", "luminary": "multiplier",
    "snake_eyes": "multiplier",
    "squire": "flat_fp", "babysitter": "flat_fp", "martyr": "flat_fp",
    "juggernaut": "multiplier", "resplendent": "flat_fp",
    "underdog": "flat_fp", "stockpiler": "multiplier", "providence": "multiplier",
    "house_money": "flat_fp", "gunslinger": "flat_fp",
    "air_raid": "floobits", "trebuchet": "flat_fp", "double_trouble": "flat_fp",
    "stampede": "multiplier",
    "stack": "multiplier", "backfield_buddies": "multiplier", "rising_tide": "multiplier",
    # floobits
    "allowance": "floobits", "cha_ching": "floobits", "piggy_bank": "floobits",
    "good_neighbor": "floobits", "consolation_prize": "floobits", "rock_bottom": "floobits",
    "buy_low": "floobits", "trust_fund": "floobits",
    "feeding_frenzy": "floobits", "highlight_reel": "floobits", "workhorse": "flat_fp",
    "expedition": "flat_fp",
    "goal_line_vulture": "floobits",
    # conditional
    "showoff": "conditional", "bandwagon": "conditional",
    "believe": "conditional",
    "reclamation": "conditional", "pedigree": "conditional",
    "mismatch": "conditional",
    "comeback_kid": "conditional", "domination": "conditional", "walk_off": "conditional",
    # streak
    "on_fire": "streak",
    "snowball_fight": "streak", "fairweather_fan": "streak", "bandwagon_express": "streak",
    "touchdown_jackpot": "accumulator", "odometer": "flat_fp", "complacency": "streak",
    "leg_day": "streak", "automatic": "streak",
    "momentum": "streak",
    # cross-position (declared by _buildCrossPositionParams)
    "spectacle": "cross", "indemnity": "cross",
    "full_roster": "cross", "all_in": "cross", "diversified": "cross",
    "gold_rush": "cross", "stacked_deck": "cross", "copycat": "cross",
    "chain_reaction": "cross", "bonus_round": "cross", "double_down": "cross",
    "last_resort": "cross", "high_roller": "cross",
    "fortitude": "cross",
    # same-team / game-outcome (map to their builder)
    "hometown_hero": "floobits",
    # escalating / pace effects
    "crescendo": "flat_fp", "eminence": "multiplier", "traverse": "flat_fp",
    # chance synergy
    "advantage": "meta", "catalyst": "floobits",
    # fusion additions (2026-07): replace the retired anti-synergy effects
    "winners_circle": "floobits", "no_passengers": "multiplier", "franchise": "multiplier",
    "metronome": "streak",
    # strategy-warping
    "alchemy": "flat_fp", "home_alone": "multiplier",
    "closer": "flat_fp", "dark_horse": "multiplier",
    "vagabond": "multiplier", "fat_cat": "flat_fp", "surplus": "floobits",
    "bonsai": "streak",
    # ── New cards (FP/FPx rebalance, see card_balance_fp_vs_fpx memory) ──
    # Hand-composition synergy
    "anthem": "cross",          # threshold based on flat_fp card count in hand
    "conductor": "cross",       # diamond amplifier, no own output
    "captain": "cross",         # diamond overshoot amplifier, no own output
    # Roster-trait flat_fp
    "castaway": "flat_fp",      # roster has player from sub-.500 team
    "sleeper": "flat_fp",       # chance card, odds scale with low-rated roster players
    "patient": "flat_fp",       # per-week reward for keeping a low-rated slot
    "rookie_hype": "flat_fp",   # per rookie on roster
    "wanderer": "flat_fp",      # per unique team represented across roster
    # Inverse streak (peak-decay shared with existing streaks)
    "sandbagger": "streak",     # streak grows when a slot scores ≤5 FP
    "quiet_storm": "streak",    # streak grows when no roster player ≥15 FP
    "drought": "streak",        # streak grows when roster total <50 FP
    # Prognostication-driven
    "nose_picker": "streak",     # streak grows when user manually submits picks (no auto-pick)
    "medium": "conditional",     # weekly accuracy bonus (counts auto-picks)
    "parlay": "multiplier",    # FPx — log-taper on weekly pick-em point total
    # Roster-construction-driven (next-season additions)
    "synergy": "multiplier",     # FPx per pair of roster players from same team
    "vanguard": "multiplier",    # FPx per veteran (5+ seasons) on roster
    "range": "flat_fp",          # FP per FG yard kicked by roster K this week
    "loyalty": "flat_fp",        # FP per first-save roster player still on roster
    "charmed": "cross",          # second-pass FP per chance trigger this week
    "cornerstone": "multiplier", # FPx per roster player who is #1 at their position
    # Stat ladder families — the compute functions read the card player directly, so
    # category only drives param-builder dispatch and output typing.
    "frontier": "flat_fp", "territory": "multiplier", "dominion": "streak",
    "slipstream": "multiplier", "updraft": "flat_fp", "stratosphere": "streak",
    "marksman": "multiplier", "dead_eye": "streak",
    "cadence": "flat_fp", "rhythm": "multiplier", "clockwork": "streak",
    "beast_of_burden": "multiplier", "iron_man": "streak",
    "odyssey": "streak", "battering_ram": "multiplier",
    "custody": "multiplier", "tenure": "streak", "getaway": "streak",
    "runback": "flat_fp", "house_call": "flat_fp",
    "attention": "multiplier", "altitude": "flat_fp", "haymaker": "flat_fp",
    "highpoint": "flat_fp", "breakaway": "flat_fp",
    "houdini": "flat_fp", "custodian": "flat_fp",
    "freight": "flat_fp", "grinder": "multiplier", "landslide": "streak",
    "pinpoint": "flat_fp", "coffin_corner": "multiplier", "undertaker": "streak",
    "paydirt": "multiplier", "end_zone": "flat_fp", "promised_land": "flat_fp",
    "bombardier": "multiplier", "salvo": "flat_fp", "barrage": "flat_fp",
    # Diamond stat amplifiers — no own output, pre-pass mutates ctx stats
    "doubler": "cross",          # roster TDs counted 2x for other card effects
    "surveyor": "cross",         # roster yards counted 1.5x for other card effects
    "sharpshooter": "cross",     # roster FGs counted 2x for other card effects
}

POSITION_LABELS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K"}


# ─── Effect → Concrete Output Type ─────────────────────────────────────────
# Used by themed packs. Effects that produce more than one currency type, or
# whose output kind is context-dependent (e.g. Copycat copies whatever it
# reads), are intentionally absent — themed packs filter them OUT so the
# "FP pack" really only contains FP-output cards. Anything not listed here
# resolves to NULL (mixed) at template-generation time.
EFFECT_OUTPUT_TYPE = {
    # ── Concrete FP output ──
    # Stat ladder families
    "frontier": "fp", "territory": "fpx", "dominion": "fpx",
    "slipstream": "fpx", "updraft": "fp", "stratosphere": "fpx",
    "marksman": "fpx", "dead_eye": "fpx",
    "cadence": "fp", "rhythm": "fpx", "clockwork": "fpx",
    "beast_of_burden": "fpx", "iron_man": "fpx",
    "odyssey": "fpx", "battering_ram": "fpx",
    "custody": "fpx", "tenure": "fpx", "getaway": "fpx",
    "runback": "fp", "house_call": "fp",
    "attention": "fpx", "altitude": "fp", "haymaker": "fp",
    "highpoint": "fp", "breakaway": "fp", "houdini": "fp", "custodian": "fp",
    "freight": "fp", "grinder": "fpx", "landslide": "fpx",
    "pinpoint": "fp", "coffin_corner": "fpx", "undertaker": "fpx",
    "paydirt": "fpx", "end_zone": "fp", "promised_land": "fp",
    "bombardier": "fpx", "salvo": "fp", "barrage": "fp",
    "freebie": "fp", "entourage": "fp", "touchdown_pinata": "fp", "scrappy": "fp",
    "honor_roll": "fpx", "three_pointer": "fp", "garbage_time": "fp",
    "loyalty_bonus": "fp", "spotlight_moment": "fp", "ace_up_the_sleeve": "fp",
    "possession": "fp", "slippery": "fp", "jailbreak": "fp", "expedition": "fp",
    "homer": "fpx", "gone_streaking": "fp", "safety_blanket": "fp",
    "synergy": "fpx", "vanguard": "fpx", "range": "fp", "loyalty": "fp",
    "charmed": "fp", "cornerstone": "fpx",
    "lead_blocker": "fp", "sniper": "fp", "squire": "fp", "crescendo": "fp",
    "traverse": "fp", "alchemy": "fp", "castaway": "fp", "sleeper": "fp",
    "patient": "fp", "rookie_hype": "fp", "wanderer": "fp", "hedge": "fp",
    "avalanche": "fp", "rng": "fp", "fat_cat": "fp", "workhorse": "fp",
    "babysitter": "fp", "martyr": "fp", "resplendent": "fp", "underdog": "fp",
    "house_money": "fp", "trebuchet": "fp", "double_trouble": "fp",
    "gunslinger": "fp", "odometer": "fp", "complacency": "fp",
    "snowball_fight": "fp", "bandwagon_express": "fp", "leg_day": "fp",
    "automatic": "fp", "sandbagger": "fp", "quiet_storm": "fp", "drought": "fp",
    "winners_circle": "floobits", "no_passengers": "fpx", "franchise": "fpx", "metronome": "fp",
    "nose_picker": "fp", "bonsai": "fp", "showoff": "fp",
    "believe": "fp", "reclamation": "fp", "pedigree": "fp", "mismatch": "fp",
    "comeback_kid": "fp", "domination": "fp", "walk_off": "fp", "medium": "fp",
    "diversified": "fp", "bonus_round": "fp", "last_resort": "fp",
    "anthem": "fp", "spectacle": "fp",
    # ── Concrete FPx (multiplier) output ──
    "big_deal": "fpx", "cornucopia": "fpx", "snake_eyes": "fpx",
    "luminary": "fpx", "juggernaut": "fpx", "stockpiler": "fpx",
    "providence": "fpx", "stampede": "fpx", "stack": "fpx",
    "backfield_buddies": "fpx", "rising_tide": "fpx", "eminence": "fpx",
    "home_alone": "fpx", "dark_horse": "fpx", "vagabond": "fpx", "parlay": "fpx",
    "on_fire": "fpx", "momentum": "fpx", "full_roster": "fpx", "all_in": "fpx",
    "stacked_deck": "fpx", "chain_reaction": "fpx", "high_roller": "fpx",
    "fortitude": "fpx", "double_down": "fpx", "bandwagon": "fpx",
    "closer": "fpx",  # Q4 FP multiplier — user-facing presentation is FPx
    # ── Concrete Floobits output ──
    "windfall": "floobits", "industrious": "floobits", "air_raid": "floobits",
    "allowance": "floobits", "cha_ching": "floobits", "piggy_bank": "floobits",
    "good_neighbor": "floobits", "consolation_prize": "floobits",
    "rock_bottom": "floobits", "buy_low": "floobits", "trust_fund": "floobits",
    "feeding_frenzy": "floobits", "highlight_reel": "floobits",
    "goal_line_vulture": "floobits", "hometown_hero": "floobits",
    "surplus": "floobits", "fairweather_fan": "floobits",
    "touchdown_jackpot": "floobits", "indemnity": "floobits",
    "gold_rush": "floobits",
    # Intentionally NOT listed (resolve to NULL → excluded from themed packs):
    #   advantage   — meta amplifier, no direct payout
    #   conductor   — structural amplifier, multiplies other cards
    #   copycat     — copies another card's output (any type)
    #   catalyst    — chance amplifier + small Floobits base (mixed primary)
}


def getEffectOutputType(effectName: str):
    """Return the concrete output type for themed-pack filtering, or None
    if the effect's primary output is mixed/contextual."""
    return EFFECT_OUTPUT_TYPE.get(effectName)


def tierScaledStrength(effectName: str, primary: dict, tierMult: float) -> dict:
    """Tier-scaled STRENGTH params for amplifier/meta cards whose power lives in
    a param that isn't editionScale-driven (so the normal tier scaling misses it).
    Returns {paramKey: scaledValue} to override; used by both the calc (so the
    effect actually strengthens) and serializeCard (so the description matches).
      - conductor: boost % scales directly
      - doubler/surveyor/sharpshooter: the count multiplier scales its DELTA
      - catalyst: chance ramp gets steeper (fewer FP per 1%) with a higher cap
    """
    if not tierMult or tierMult == 1.0:
        return {}
    p = primary or {}
    if effectName == "conductor":
        return {"boostPct": int(round(p.get("boostPct", 20) * tierMult))}
    if effectName == "captain" and "perOvershootPct" in p:
        scaled = round(p["perOvershootPct"] * tierMult, 4)
        return {"perOvershootPct": scaled, "perOvershootShown": round(scaled * 100, 1)}
    if effectName == "doubler" and "tdMult" in p:
        return {"tdMult": round(1 + (p["tdMult"] - 1) * tierMult, 2)}
    if effectName == "surveyor" and "yardMult" in p:
        return {"yardMult": round(1 + (p["yardMult"] - 1) * tierMult, 2)}
    if effectName == "sharpshooter" and "fgMult" in p:
        return {"fgMult": round(1 + (p["fgMult"] - 1) * tierMult, 2)}
    if effectName == "catalyst":
        out = {}
        for _k in ("fpPer1PctSolo", "fpPer1Pct"):   # Solo is current; the other is legacy
            if _k in p:
                out[_k] = max(1, int(round(p[_k] / tierMult)))
        if "maxBoost" in p:
            out["maxBoost"] = round(p["maxBoost"] * tierMult, 2)
            out["maxBoostDisplay"] = int(round(out["maxBoost"] * 100))
        return out
    return {}

# ─── Effect → Edition Tier Mapping ─────────────────────────────────────────
# Each effect belongs to exactly one edition tier. Edition IS the rarity signal —
# a Radiant card is exciting because it has a Radiant-tier effect, not because of
# power scaling. No more multiplied base effects.

EFFECT_EDITION_TIER = {
    # ── BASE (29) — Simple, reliable, always produces value ──
    "freebie": "metallic", "entourage": "metallic", "touchdown_pinata": "metallic",
    "honor_roll": "metallic", "garbage_time": "metallic", "windfall": "metallic",
    "resplendent": "metallic", "three_pointer": "metallic",
    "big_deal": "metallic", "bandwagon": "metallic", "rng": "metallic",
    "allowance": "metallic", "piggy_bank": "metallic", "buy_low": "metallic", "trust_fund": "metallic",
    "showoff": "metallic",
    "believe": "metallic", "reclamation": "metallic",
    "gunslinger": "metallic", "workhorse": "metallic", "expedition": "metallic",
    "possession": "metallic", "slippery": "metallic", "safety_blanket": "metallic",
    "sniper": "metallic", "industrious": "metallic", "air_raid": "metallic",
    "goal_line_vulture": "metallic",
    "homer": "metallic",
    # Floobits utility demotions — modest payouts, no build-around character.
    # Belong with the rest of the base floobits utilities.
    "consolation_prize": "metallic", "rock_bottom": "metallic",
    "indemnity": "metallic", "gold_rush": "metallic",

    # ── HOLOGRAPHIC (26) — Conditional, team-composition, position thresholds ──
    "gone_streaking": "holographic",
    "closer": "holographic", "good_neighbor": "holographic",
    "diversified": "holographic", "bonus_round": "holographic",
    "spotlight_moment": "holographic", "squire": "holographic",
    "mismatch": "holographic",
    "pedigree": "holographic", "spectacle": "holographic",
    "jailbreak": "holographic",
    "luminary": "holographic", "stampede": "holographic",
    "stack": "holographic", "backfield_buddies": "holographic",
    "cha_ching": "holographic", "feeding_frenzy": "holographic",
    "highlight_reel": "holographic",
    "hometown_hero": "holographic",
    "loyalty_bonus": "holographic",
    "ace_up_the_sleeve": "holographic", "trebuchet": "holographic",
    "double_trouble": "holographic", "lead_blocker": "holographic",
    "fat_cat": "holographic", "surplus": "holographic", "hedge": "holographic",

    # fusion additions (2026-07): base=Winner's Circle, holo=No Passengers, prismatic=Franchise/Metronome
    "winners_circle": "metallic", "no_passengers": "holographic", "franchise": "prismatic",
    "metronome": "prismatic",
    # ── PRISMATIC — Chance-based, streaks, game-outcome, build-around ──
    "home_alone": "prismatic", "dark_horse": "prismatic",
    "chain_reaction": "prismatic", "copycat": "prismatic",
    "cornucopia": "prismatic", "juggernaut": "prismatic",
    "scrappy": "prismatic", "babysitter": "prismatic", "martyr": "prismatic", "underdog": "prismatic",
    "crescendo": "prismatic", "traverse": "prismatic",
    "complacency": "prismatic", "snowball_fight": "prismatic",
    "bandwagon_express": "prismatic", "on_fire": "prismatic", "momentum": "prismatic",
    "fairweather_fan": "prismatic", "leg_day": "prismatic",
    "automatic": "prismatic", "touchdown_jackpot": "prismatic", "odometer": "prismatic",
    # Reworked fav-team-event cards: demoted to holo since the rebuild now
    # pays from roster traits + a small floobits cherry on the fav-team event.
    "comeback_kid": "holographic", "domination": "holographic", "walk_off": "holographic",
    # FPx demotions: useful build-arounds that don't need Prismatic rarity
    # to express identity. Frees Prismatic for the true meta build-arounds.
    "providence": "holographic", "rising_tide": "holographic",
    "eminence": "holographic", "vagabond": "holographic",
    "stockpiler": "prismatic", "house_money": "prismatic",
    "bonsai": "prismatic",
    "all_in": "prismatic",
    "last_resort": "prismatic", "avalanche": "prismatic",

    # ── DIAMOND — Game-changing, rule-bending cornerstones ──
    "alchemy": "diamond", "snake_eyes": "diamond",
    "catalyst": "diamond", "advantage": "diamond",
    "high_roller": "diamond",
    "fortitude": "diamond",
    "full_roster": "diamond", "stacked_deck": "diamond",
    "double_down": "diamond",

    # ── New cards (FP/FPx rebalance) ──
    "patient": "holographic", "rookie_hype": "holographic",
    "castaway": "holographic", "wanderer": "holographic",
    "anthem": "prismatic", "sleeper": "prismatic",
    "sandbagger": "prismatic", "quiet_storm": "prismatic", "drought": "prismatic",
    "conductor": "diamond",
    "captain": "diamond",

    # ── Prognostication cards ──
    "nose_picker": "holographic", "medium": "holographic", "parlay": "holographic",
    # ── Roster-construction-driven (next-season additions) ──
    "synergy": "holographic", "vanguard": "holographic", "range": "holographic",
    "loyalty": "holographic",
    # Chance-trigger synergy (second-pass)
    "charmed": "prismatic",
    "cornerstone": "prismatic",
    # Diamond stat amplifiers
    "doubler": "diamond", "surveyor": "diamond", "sharpshooter": "diamond",

    # ── Stat ladder families (docs/CARD_STAT_LADDER.md) ──
    # One stat, three rungs, each containing the one below: metallic pays a flat rate,
    # holographic adds a conditional bonus, prismatic adds a streak or chance.
    "frontier": "metallic", "territory": "holographic", "dominion": "prismatic",
    "slipstream": "metallic", "updraft": "holographic", "stratosphere": "prismatic",
    "marksman": "holographic", "dead_eye": "prismatic",
    "cadence": "metallic", "rhythm": "holographic", "clockwork": "prismatic",
    "beast_of_burden": "holographic", "iron_man": "prismatic",
    "odyssey": "prismatic", "battering_ram": "metallic",
    "custody": "holographic", "tenure": "prismatic", "getaway": "prismatic",
    "runback": "metallic", "house_call": "prismatic",
    "attention": "metallic", "altitude": "holographic", "haymaker": "holographic",
    "highpoint": "holographic", "breakaway": "holographic",
    "houdini": "prismatic", "custodian": "prismatic",
    "freight": "metallic", "grinder": "holographic", "landslide": "prismatic",
    "pinpoint": "metallic", "coffin_corner": "holographic", "undertaker": "prismatic",
    "paydirt": "metallic", "end_zone": "holographic", "promised_land": "prismatic",
    "bombardier": "metallic", "salvo": "holographic", "barrage": "prismatic",
}


# Display names + flavor for new roster-driven cards (helper block)

# ─── Balatro-pass dial ───────────────────────────────────────────────────────
# Multipliers applied on top of the prior Balatro 3× bump. 1.0 = full Balatro
# values shipped on next-season; 0.5 = half-strength pullback (target FP land
# at ~3.4× the original baselines instead of 6.75×; FPx deltas at ~1.05×
# original instead of 2.1×). Dial down/up here to retune without rewriting
# every constant.
_BAL_FP_MULT  = 0.5    # scales FP outputs (chips) added by the Balatro pass
_BAL_FPX_MULT = 0.5    # scales FPx deltas (multiplier portions) added by the Balatro pass

# Per-edition power dial (Phase 9 fusion retune). Fusion fields a full 6-7 card
# lineup instead of ~5, so aggregate card bonus per user is structurally higher —
# measured post-gate on real lineups at base ~89% / holo ~107% / prismatic ~143%
# of the lineup's own player FP (target: ~100% MEAN for every edition; rarity buys
# ceiling/variance, not a higher mean). This scales an edition's minted FP + FPx +
# floobits params (via `editionScale`, which every param builder already threads).
# Frozen at mint, so a change re-values every scoreable card cleanly at the next
# season boundary. Tune here; re-measure with simcheck_edition_power.py.
# Tuned 2026-07-23 to ~100% mean per edition (simcheck_edition_power.py, N=100 real
# lineups): base 103% / holo 99% / prismatic 99% / diamond 109%, with variance rising
# into diamond (p90 220%, median 80%). Baseline before the retune was 84/161/218/89%.
EDITION_POWER_SCALE = {
    'base': 1.0,          # no-effect floor card — no params, scale is moot
    'metallic': 1.10,     # 84% -> 103%: nudge the flat/reliable floor to parity
    # Retuned 2026-08-06 against simcheck_pool_power.py, which measures whole six-card
    # lineups on the LIVE path. The previous values (holo 0.47, prismatic 0.30) were
    # calibrated in PROJECTION mode on a prod snapshot and against a pool with no ladder
    # cards in it. Two things had since made them wrong: the live on/off FP gate pays less
    # than projection's EV-scaled version, and the ~27 stat-ladder cards bypass this dial
    # entirely (they are anchored per rung by construction), so it now moves only the
    # older half of each pool. Measured before: metallic 91% / holo 36% / prismatic 50%.
    # After: 91 / 87 / 92.
    'holographic': 1.70,
    'prismatic': 0.70,
    'diamond': 1.0,       # see below — the dial is NOT the lever here
}

# Rookie Hype pays flat FP per rookie in the fantasy lineup, uncapped by roster
# size. It is intentionally left uncapped: rookies are usually weak, low-FP
# players, so a rare rookie-stacked lineup that pushes past the holo-tier ceiling
# is compensating for the meager base production those players contribute. The
# per-rookie value (~8.0, see _buildCrossPositionParams) is intentionally strong
# for the tier so that rostering usually-weak rookies is worthwhile.


# ─── Position Conditionals (same as current system) ─────────────────────────

# Stat-threshold flat-FP bonuses added when a card's player hits a milestone.
# Bonus values shown here are post-Balatro (3×); `_BAL_FP_MULT` halves them at
# read time via `_positionConditionalBonus`.
POSITION_CONDITIONALS = {
    1: [  # QB
        {"stat": "passYards", "threshold": 300, "bonus": 15, "label": "300+ pass yards"},
        {"stat": "passTds", "threshold": 3, "bonus": 24, "label": "3+ pass TDs"},
    ],
    2: [  # RB
        {"stat": "rushYards", "threshold": 100, "bonus": 15, "label": "100+ rush yards"},
        {"stat": "rushTds", "threshold": 2, "bonus": 24, "label": "2+ rush TDs"},
    ],
    3: [  # WR
        {"stat": "recYards", "threshold": 100, "bonus": 15, "label": "100+ rec yards"},
        {"stat": "recTds", "threshold": 2, "bonus": 24, "label": "2+ rec TDs"},
    ],
    4: [  # TE
        {"stat": "recYards", "threshold": 75, "bonus": 12, "label": "75+ rec yards"},
        {"stat": "recTds", "threshold": 1, "bonus": 15, "label": "1+ rec TD"},
    ],
    5: [  # K
        {"stat": "fgMade", "threshold": 3, "bonus": 12, "label": "3+ FGs made"},
        {"stat": "longFg", "threshold": 50, "bonus": 15, "label": "50+ yard FG"},
    ],
}


def _positionConditionalBonus(raw: int) -> int:
    """Apply the Balatro FP dial to a POSITION_CONDITIONALS bonus value."""
    return int(round(raw * _BAL_FP_MULT))

# ─── Effect Display Names ────────────────────────────────────────────────────

EFFECT_DISPLAY_NAMES = {
    # Stat ladder families
    "frontier": "Frontier", "territory": "Territory", "dominion": "Dominion",
    "slipstream": "Slipstream", "updraft": "Updraft", "stratosphere": "Stratosphere",
    "marksman": "Marksman", "dead_eye": "Dead Eye",
    "cadence": "Cadence", "rhythm": "Rhythm", "clockwork": "Clockwork",
    "beast_of_burden": "Beast of Burden", "iron_man": "Iron Man",
    "odyssey": "Odyssey", "battering_ram": "Battering Ram",
    "custody": "Custody", "tenure": "Tenure", "getaway": "Getaway",
    "runback": "Runback", "house_call": "House Call",
    "attention": "Attention", "altitude": "Altitude", "haymaker": "Haymaker",
    "highpoint": "Highpoint", "breakaway": "Breakaway",
    "houdini": "Houdini", "custodian": "Custodian",
    # Stampede renamed to join the rush-yards journey motif (Expedition -> Odyssey).
    "stampede": "Trailblazer",
    "freight": "Freight", "grinder": "Grinder", "landslide": "Landslide",
    "pinpoint": "Pinpoint", "coffin_corner": "Coffin Corner", "undertaker": "Undertaker",
    "paydirt": "Paydirt", "end_zone": "End Zone", "promised_land": "Promised Land",
    "bombardier": "Bombardier", "salvo": "Salvo", "barrage": "Barrage",
    # Flat FP (WR)
    "freebie": "Freebie",
    "entourage": "Entourage",
    "touchdown_pinata": "Touchdown Piñata",
    "scrappy": "Scrappy",
    "honor_roll": "Honor Roll",
    "three_pointer": "Three Pointer",
    "garbage_time": "Garbage Time",
    "loyalty_bonus": "Loyalty Bonus",
    "windfall": "Windfall",
    "rng": "RNG",
    "snake_eyes": "Bizarro",
    "avalanche": "Avalanche",
    "hedge": "Hedge",
    "complacency": "Complacency",
    "spotlight_moment": "Spotlight Moment",
    "ace_up_the_sleeve": "Pocket Aces",
    "lead_blocker": "Lead Blocker",
    # Multiplier (QB) — 10 effects
    "big_deal": "Big Deal",
    "cornucopia": "Cornucopia",
    "luminary": "Luminary",
    "squire": "Hype Man",
    "babysitter": "Babysitter",
    "martyr": "Martyr",
    "juggernaut": "Juggernaut",
    "resplendent": "Hot Stove",
    "underdog": "Underdog",
    "stockpiler": "Stockpiler",
    "providence": "Providence",
    "house_money": "House Money",
    "rising_tide": "Rising Tide",
    # Floobits (RB)
    "allowance": "Allowance",
    "cha_ching": "Cha-Ching",
    "piggy_bank": "Piggy Bank",
    "good_neighbor": "Good Neighbor",
    "consolation_prize": "Consolation Prize",
    "rock_bottom": "Rock Bottom",
    "buy_low": "Buy Low",
    "trust_fund": "Trust Fund",
    "feeding_frenzy": "Feeding Frenzy",
    "highlight_reel": "Highlight Reel",
    # Conditional (TE)
    "showoff": "Showoff",
    "bandwagon": "Bandwagon",
    "believe": "Believe",
    "reclamation": "Reclamation",
    "pedigree": "Blue Ribbon",
    # Streak (K) — 10 effects
    "on_fire": "On Fire",
    "snowball_fight": "Snowball Fight",
    "fairweather_fan": "Fairweather Fan",
    "bandwagon_express": "Bandwagon Express",
    "touchdown_jackpot": "Touchdown Jackpot",
    "odometer": "Odometer",
    "leg_day": "Leg Day",
    "automatic": "Automatic",
    "momentum": "Momentum",
    # ── New Position-Based Effects ──
    "gunslinger": "Gunslinger",
    "air_raid": "Air Raid",
    "workhorse": "Workhorse",
    "expedition": "Expedition",
    "goal_line_vulture": "Goal Line Vulture",
    "possession": "Possession",
    "trebuchet": "Trebuchet",
    "double_trouble": "Double Trouble",
    "slippery": "Slippery",
    "jailbreak": "Jailbreak",
    "safety_blanket": "Safety Blanket",
    "industrious": "Industrious",
    "mismatch": "Mismatch",
    "sniper": "Sniper",
    "spectacle": "Spectacle",
    "indemnity": "Indemnity",
    # ── Same-Team Stacking Effects ──
    "stack": "Stack",
    "backfield_buddies": "Backfield Buddies",
    "homer": "Homer",
    "gone_streaking": "Gone Streaking",
    "hometown_hero": "Clique",
    # ── Game-Outcome Effects ──
    "comeback_kid": "Comeback Kid",
    "domination": "Domination",
    "walk_off": "Walk Off",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "Full House",
    "all_in": "All In",
    "diversified": "Diversified",
    "gold_rush": "Gold Rush",
    "stacked_deck": "Stacked Deck",
    "copycat": "Copycat",
    "chain_reaction": "Chain Reaction",
    "bonus_round": "Group Project",
    "winners_circle": "Winner's Circle",
    "no_passengers": "No Passengers",
    "franchise": "Franchise",
    "metronome": "Metronome",
    "double_down": "Lemons",
    "last_resort": "Last Resort",
    "high_roller": "High Roller",
    "fortitude": "Heat Check",
    # ── Escalating / Pace Effects ──
    "crescendo": "Crescendo",
    "eminence": "Eminence",
    "traverse": "Traverse",
    # ── Chance Synergy Effects ──
    "advantage": "Advantage",
    "catalyst": "Catalyst",
    # ── Strategy-Warping Effects ──
    "alchemy": "Alchemy",
    "home_alone": "Home Alone",
    "closer": "Closers",
    "dark_horse": "Dark Horse",
    "vagabond": "Vagabond",
    "fat_cat": "Fat Cat",
    "surplus": "Surplus",
    "bonsai": "Bonsai",
    # ── New cards (FP/FPx rebalance) ──
    "anthem": "Anthem",
    "conductor": "Conductor",
    "captain": "Captain",
    "castaway": "Castaway",
    "sleeper": "Sleeper",
    "patient": "Patient",
    "rookie_hype": "Rookie Hype",
    "wanderer": "Wanderer",
    "sandbagger": "Sandbagger",
    "quiet_storm": "Quiet Storm",
    "drought": "Drought",
    # ── Prognostication cards ──
    "nose_picker": "Nose Picker",
    "medium": "Medium",
    "parlay": "Parlay",
    # ── Roster-construction-driven ──
    "synergy": "Synergy",
    "vanguard": "Vanguard",
    "range": "Range",
    "loyalty": "Loyalty",
    "charmed": "Charmed",
    "cornerstone": "Cornerstone",
    # ── Diamond stat amplifiers ──
    "doubler": "Doubler",
    "surveyor": "Surveyor",
    "sharpshooter": "Sharpshooter",
}

# ─── Three-Tier Description System ───────────────────────────────────────────
# Tagline: short punchy text for card front (under effect name)
# Tooltip: generic explanation shown on hover over effect name
# Detail: specific template with {param} placeholders, shown on card back

STAT_DISPLAY_NAMES = {
    "passYards": "passing yards",
    "passTds": "passing TDs",
    "rushYards": "rushing yards",
    "rushTds": "rushing TDs",
    "recYards": "receiving yards",
    "recTds": "receiving TDs",
    "fgMade": "FGs made",
    "longFg": "longest FG yards",
}

EFFECT_TAGLINES = {
    # Stat ladder families
    "cadence": "Keep the chains moving",
    "rhythm": "Finding a groove",
    "clockwork": "Never misses a beat",
    "beast_of_burden": "Carrying the load",
    "iron_man": "Never comes off the field",
    "odyssey": "The long road",
    "battering_ram": "Straight through",
    "custody": "Safe hands",
    "tenure": "Long service",
    "getaway": "Gone",
    "runback": "Bring it out",
    "house_call": "All the way",
    "attention": "Feed the target",
    "altitude": "Throwing it deep",
    "haymaker": "Swinging big",
    "highpoint": "Above the crowd",
    "breakaway": "Gone in a blink",
    "houdini": "Impossible to corner",
    "custodian": "Cleaning up",
    "slipstream": "Riding the air",
    "updraft": "Catching a lift",
    "stratosphere": "Thin air up here",
    "marksman": "Nothing wasted",
    "dead_eye": "Never off target",
    "frontier": "Always pushing out",
    "territory": "Claiming ground",
    "dominion": "The whole field",
    "freight": "Hard to stop",
    "grinder": "Earning every inch",
    "landslide": "Gathering weight",
    "pinpoint": "Drop it on a dime",
    "coffin_corner": "Nowhere to go",
    "undertaker": "Bury them",
    "paydirt": "Cash in",
    "end_zone": "Where it counts",
    "promised_land": "Getting there",
    "bombardier": "Target acquired",
    "salvo": "All at once",
    "barrage": "Keep firing",
    # Flat FP (WR)
    "freebie": "Free real estate",
    "entourage": "Seeing stars",
    "touchdown_pinata": "Smash for points",
    "scrappy": "Root for the little guy",
    "honor_roll": "Straight A's",
    "three_pointer": "Count it",
    "garbage_time": "Participation trophies",
    "loyalty_bonus": "Faithful fan rewards",
    "windfall": "Cashing in",
    "rng": "Feeling lucky?",
    "snake_eyes": "Down is up",
    "avalanche": "Bury them",
    "hedge": "Downside protection",
    "complacency": "Stop tinkering",
    "spotlight_moment": "Lights please",
    "ace_up_the_sleeve": "AA",
    # Multiplier (QB)
    "big_deal": "Kind of a big deal",
    "cornucopia": "Every touchdown compounds",
    "luminary": "Your {posLabel} runs the show",
    "squire": "Your {posLabel}'s biggest fan",
    "babysitter": "Carrying the team",
    "martyr": "Embrace the tank",
    "juggernaut": "I'M THE JUGGERNAUT",
    "resplendent": "Everyone's cooking",
    "underdog": "Nothing to lose",
    "stockpiler": "Saving for a rainy day",
    "providence": "A little something extra",
    "house_money": "Playing with profit",
    "rising_tide": "Lifts all boats",
    # Floobits (RB)
    "allowance": "Weekly pocket money",
    "cha_ching": "Cash out",
    "piggy_bank": "Points into coins",
    "good_neighbor": "You're covered",
    "consolation_prize": "Better luck next time",
    "rock_bottom": "Silver lining",
    "buy_low": "Buy the dip",
    "trust_fund": "Set it and collect",
    "feeding_frenzy": "Eat up",
    "highlight_reel": "Did you see that?",
    # Conditional (TE)
    "showoff": "Star power",
    "bandwagon": "Get in, loser",
    "believe": "Reward the faithful",
    "reclamation": "Fixer's bonus",
    # ── Strategy-Warping Effects ──
    "alchemy": "Lead into gold",
    "home_alone": "Keep the change, ya filthy animal",
    "closer": "See this watch?",
    "dark_horse": "Nobody saw them coming",
    "vagabond": "A restless spirit",
    "fat_cat": "Rolling in it",
    "surplus": "Steady stipend",
    "bonsai": "Snip snip",
    "pedigree": "Pedigree",
    # Streak (K)
    "on_fire": "Keep the flame alive",
    "snowball_fight": "Getting bigger",
    "fairweather_fan": "Only here for the wins",
    "bandwagon_express": "Choo choo!",
    "touchdown_jackpot": "Weekly TD lottery",
    "odometer": "Every milestone pays",
    "leg_day": "Never skip leg day",
    "automatic": "Perfect kicks only",
    "momentum": "Rolling",
    # ── New Position-Based Effects ──
    "gunslinger": "Slinging it",
    "air_raid": "Bombs away",
    "workhorse": "Feed the beast",
    "expedition": "Marching downfield",
    "stampede": "Unstoppable force",
    "goal_line_vulture": "Opportunistic scavenging",
    "possession": "Catch everything",
    "trebuchet": "Siege engine",
    "double_trouble": "Both WRs deliver",
    "slippery": "Can't bring me down",
    "jailbreak": "Breaking out",
    "safety_blanket": "Reliable target",
    "industrious": "Honest work",
    "lead_blocker": "Paving the way",
    "mismatch": "Too big, too fast",
    "sniper": "From downtown",
    "spectacle": "Career day",
    "indemnity": "Consolation floobits",
    # ── Same-Team Stacking Effects ──
    "stack": "QB-WR stack",
    "backfield_buddies": "Same backfield",
    "homer": "Hometown discount",
    "gone_streaking": "CENSORED",
    "hometown_hero": "BFFs",
    # ── Game-Outcome Effects ──
    "comeback_kid": "Bet on the bounce-back",
    "domination": "Ride the contenders",
    "walk_off": "Show up when it counts",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "Whole squad shows up",
    "all_in": "Eggs + basket",
    "diversified": "Variety pack",
    "gold_rush": "Floobits love company",
    "stacked_deck": "Let's get exponential",
    "copycat": "Imitation is flattery",
    "chain_reaction": "Cards feeding cards",
    "bonus_round": "Everyone showed up",
    "winners_circle": "Ride the winners",
    "no_passengers": "No free rides",
    "franchise": "The centerpiece",
    "metronome": "Never misses a beat",
    "double_down": "Burn the house down",
    "last_resort": "The ultimate insurance",
    "high_roller": "Degenerate strategy",
    "fortitude": "Staying hot",
    # ── Escalating / Pace Effects ──
    "crescendo": "Keep missing, it only gets easier",
    "eminence": "Stack the leaderboard",
    "traverse": "Take the long way",
    # ── Chance Synergy Effects ──
    "advantage": "Double or nothing (minus the nothing)",
    "catalyst": "Points in, luck out",
    # ── New cards (FP/FPx rebalance) ──
    "anthem": "All together now",
    "conductor": "Wave the baton",
    "captain": "Set the tone",
    "castaway": "Diamond in the basement",
    "sleeper": "Rest easy",
    "patient": "Time on the pine",
    "rookie_hype": "Trust the kids",
    "wanderer": "Spread thin",
    "sandbagger": "Save it for later",
    "quiet_storm": "Calm before the chaos",
    "drought": "Dried up",
    # ── Prognostication cards ──
    "nose_picker": "Pick it yourself",
    "medium": "Crystal clear",
    "parlay": "Let it ride",
    # ── Roster-construction-driven ──
    "synergy": "Stack the depth chart",
    "vanguard": "Old guard",
    "range": "Boot it through",
    "loyalty": "Stick with your guys",
    "charmed": "The dice love you",
    "cornerstone": "Build around the best",
    # ── Diamond stat amplifiers ──
    "doubler": "Twice the score",
    "surveyor": "Every yard counts more",
    "sharpshooter": "Boots that pay double",
}

EFFECT_TOOLTIPS = {
    # Stat ladder families
    "cadence": "Tick, tick, tick. FP for every completion this player makes.",
    "rhythm": "Once the rhythm arrives, everything comes easier. FPx on every completion, and more once past a big week.",
    "clockwork": "Same time every week. FPx on completions, plus a streak for every week the count holds up.",
    "beast_of_burden": "FPx on every carry, and more once the workload runs long.",
    "iron_man": "FPx on carries, plus a streak for every week the load holds up.",
    "odyssey": "FPx on rushing yards, plus a streak for every hundred-yard week.",
    "battering_ram": "No finesse required. FPx for every rushing touchdown.",
    "custody": "FPx on every catch, and more once the count runs high.",
    "tenure": "FPx on catches, plus a streak for every week the count holds up.",
    "getaway": "FPx on yards after the catch, plus a streak for every big week.",
    "runback": "The play starts on the catch. FP for every punt return yard.",
    "house_call": "FP on every return yard, and sometimes nobody gets a hand on it at all.",
    "attention": "The ball is coming down there, caught or not. FPx for every target.",
    "altitude": "Nothing underneath. FP that grows the further downfield the ball goes.",
    "haymaker": "Twenty yards at a time. FP for passing yards, and a bonus on every throw that goes deep.",
    "highpoint": "Two defenders on the ball and it still comes down. FP per catch, and a bonus for the ones taken in traffic.",
    "breakaway": "One crease is all it takes. FP for rushing yards, and a bonus every time one breaks loose.",
    "houdini": "FP on every rushing yard, and a shot at more every time a tackle gets broken.",
    "custodian": "The throw was bad. The catch was made anyway. FP per catch, and a bonus for rescuing a bad ball.",
    "slipstream": "The ball hangs and the yards pile up. FPx scaling with passing yards.",
    "updraft": "Some days the ball just carries. FP on every passing yard, with more at 300, 400 and 500.",
    "stratosphere": "Territory most passers never see. FPx on passing yards, plus a streak for every big week.",
    "marksman": "FPx on every well-placed ball, and more for a week without a single bad throw.",
    "dead_eye": "FPx on well-placed balls, plus a streak for every week with nothing off target.",
    "frontier": "Every yard is new ground. FP for every receiving yard.",
    "territory": "FPx on every receiving yard, with more at 75, 125 and 175.",
    "dominion": "FPx on receiving yards, plus a streak for every hundred-yard week.",
    "freight": "The first hit never finishes the job. FP for every yard gained after contact.",
    "grinder": "FPx on every yard after contact, and more when those yards clear half the total.",
    "landslide": "FPx on yards after contact, plus a streak for every hundred-yard week.",
    "pinpoint": "Placement over power. FP for every punt downed inside the 20.",
    "coffin_corner": "FPx on every punt downed inside the 20, and more for the ones inside the 10.",
    "undertaker": "FPx on punts downed inside the 20, plus a streak for every multi-pin week.",
    "paydirt": "Cross the line, collect. FPx for every receiving touchdown.",
    "end_zone": "One is good. Two is somebody else's problem. FP on every receiving TD, with a bonus at two.",
    "promised_land": "FP on every receiving TD, and each one raises the odds the next pays out.",
    "bombardier": "Precision from altitude. FPx for every passing touchdown.",
    "salvo": "One is a shot. Three is a salvo. FP on every passing TD, with a bonus at three.",
    "barrage": "FP on every passing TD, and each one raises the odds the next pays out.",
    # Flat FP (WR)
    "freebie": "It's free. Bonus FP every week.",
    "entourage": "Seeing stars. Bonus FP for each high-rated player on your roster.",
    "touchdown_pinata": "Every house call fills the piñata. Bonus FP per roster TD.",
    "scrappy": "Somebody has to believe in them. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each low-rated player on your roster.",
    "honor_roll": "Make the grade. FPx that grows with every point past the bar, reaching full at double it. A bare pass is worth almost nothing.",
    "three_pointer": "Three points for them, bonus for you. FP for every kicker FG.",
    "garbage_time": "Hey, they showed up. Bonus FP for each roster player who doesn't score a TD.",
    "loyalty_bonus": "Bandwagoning encouraged. Bonus FP based on your favorite team's win streak.",
    "windfall": "When your players ball out, you get paid. Floobits per overperforming roster player.",
    "rng": "Feeling lucky? Random FP rolled each week.",
    "snake_eyes": "Bad is good. The worse this player's week, the bigger the FPx on your total.",
    "avalanche": "Momentum builds with every score. Each roster TD pays more FP than the last.",
    "hedge": "Insurance policy. Tops this player up to an FP floor on a quiet week.",
    "complacency": "Put the phone down. FP that grows each week you don't touch your roster. Stacking streak cards accelerates growth.",
    "spotlight_moment": "Lights, camera, action. FP whenever this player scores a TD. For WR, either counts.",
    "ace_up_the_sleeve": "Pocket Rockets. Base FP every week, plus bonus FP when this player hits a combined stat threshold.",
    # Multiplier (QB)
    "big_deal": "Don't you know who I am? Flat FPx on your total score.",
    "cornucopia": "Every touchdown compounds, but each one matters a little less. FPx that stacks per roster TD with diminishing returns.",
    "luminary": "Your {posLabel} runs the offense. FPx that increases the more FP this player earns.",
    "squire": "The crowd goes wild. FP that stacks with each TD this player scores.",
    "babysitter": "Someone has to do the heavy lifting. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each roster player who underperforms.",
    "martyr": "Pain builds character. FP floor plus a chance at enhanced FP. Odds scale with your favorite team's season losses.",
    "juggernaut": "Momentum is a beautiful thing. FPx grows with every win in your favorite team's streak, with diminishing returns past long runs.",
    "resplendent": "When they're hot, they're HOT. FP per overperforming roster player.",
    "underdog": "The worse they are, the better the odds. Guaranteed FP floor plus a chance at enhanced FP. Odds increase with each loss on your favorite team's record.",
    "stockpiler": "Patience pays. FPx that grows with each unused roster swap.",
    "providence": "Fortune favors the prepared. FPx bonus plus chance boost to all chance cards in your hand.",
    "house_money": "Upset city. FP that builds every time your favorite team wins as an underdog.",
    "rising_tide": "A rising tide lifts all boats. FPx that grows with each roster player outperforming their rating.",
    # Floobits (RB)
    "allowance": "Don't spend it all in one place. Free Floobits every week just for existing.",
    "cha_ching": "The endzone is your cash register. Floobits for every TD this player scores.",
    "piggy_bank": "Automatic savings plan. Converts a chunk of this player's total FP into Floobits.",
    "good_neighbor": "Worry free. Guaranteed Floobits plus a bonus for each FG your kicker misses.",
    "consolation_prize": "Here's a little something for your troubles. Guaranteed Floobits floor plus a chance at enhanced Floobits. The trigger bar fills from this player's own FP and from each roster player who has a bad week.",
    "rock_bottom": "Rock bottom has a cash reward. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the longer your favorite team's losing streak.",
    "buy_low": "Buy low, sell... whenever. Floobits for every underperforming roster player.",
    "trust_fund": "The lazy investor strategy. Floobits that grow each week your roster stays unchanged.",
    "feeding_frenzy": "Dinner is served. Floobits per roster TD, plus a jackpot bonus when your roster hits the TD threshold.",
    "highlight_reel": "Highlight reel material. Floobits for every big play your favorite team pulls off.",
    # Conditional (TE)
    "showoff": "Stack the studs. FP per 5-star player on your roster.",
    "bandwagon": "Hop on the bandwagon. FPx whenever your favorite team wins.",
    "believe": "Your faith rewarded. FP scaling with your favorite team's season wins. Bonus floobits when they win this week.",
    "reclamation": "Someone has to fix this mess. FP when most of your roster is underperforming.",
    "pedigree": "Prize winner. FP with a bonus when your favorite team's ELO reaches elite status (1600+).",
    # Streak (K) — streak cards boost each other's growth when stacked
    "on_fire": "Don't let the flame die. FPx that grows each week this player makes a FG. Stacking streak cards accelerates growth.",
    "snowball_fight": "It just keeps getting bigger. FP growing each week your roster scores a TD. Stacking streak cards accelerates growth.",
    "fairweather_fan": "Fair-weather fandom has its perks. Floobits growing each week your favorite team wins. Stacking streak cards accelerates growth.",
    "bandwagon_express": "Next stop: more points. FP growing each week your favorite team wins. Stacking streak cards accelerates growth.",
    "touchdown_jackpot": "Fresh lottery every week. Floobits stacking per roster TD, resets weekly.",
    "odometer": "Hit the milestones. Escalating FP at each yardage gate this player hits. Resets weekly.",
    "leg_day": "Never skip it. FP growing each week this player nails a 35+ yard FG. Stacking streak cards accelerates growth.",
    "automatic": "Perfection pays. FP growing each consecutive week this player goes perfect on FGs. Stacking streak cards accelerates growth.",
    "momentum": "Can't stop won't stop. FPx grows each week your roster breaks 100 FP. Stacking streak cards accelerates growth.",
    # ── New Position-Based Effects ──
    "gunslinger": "Let it fly. FP for every well-placed ball this player throws.",
    "air_raid": "Death from above. Floobits for each passing TD this player throws.",
    "workhorse": "Pound the rock. FP scaling with rushing attempts by this player.",
    "expedition": "Yards are yards. FP that scales with how many rushing yards this player gains.",
    "stampede": "Get rolling. Base FPx, enhanced FPx when this player hits 75+ rushing yards.",
    "goal_line_vulture": "Vulture season. Floobits for every rushing TD this player punches in.",
    "possession": "Chain-mover. FP that scales with how many catches this player hauls in.",
    "trebuchet": "Send it deep. Base FP every week, plus bonus FP when this player catches a pass of 25+ yards.",
    "double_trouble": "Two is better than one. FP when either WR scores a TD, bonus when both WRs score.",
    "slippery": "Yards after the catch turn into points. FP that scales with this player's YAC.",
    "jailbreak": "Can't catch them. Base FP every week, plus bonus FP when this player racks up enough yards after catch.",
    "safety_blanket": "Every QB needs one. FP scaling with receptions by this player.",
    "industrious": "Honest work deserves honest pay. Floobits scaling with receptions by this player.",
    "lead_blocker": "Clearing the path. FP per TD by your TE. RB TDs count as TE TDs if they are on the same team.",
    "mismatch": "They can't cover this guy. FP per TD by this player, plus a bonus when they score multiple TDs.",
    "sniper": "From long range. FP for each field goal this player makes from 40+ yards out.",
    "spectacle": "Going off. FP that scales with how much this player overperforms expectations this week.",
    "indemnity": "At least you got floobits. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the more this player underperforms.",
    # ── Same-Team Stacking Effects ──
    "stack": "Stack attack. FPx when this player and any rostered WR play on the same team.",
    "backfield_buddies": "Same backfield, double the payoff. FPx when this player and your rostered RB play on the same team.",
    "homer": "The home crowd lifts everyone. FPx per roster player on your favorite team.",
    "gone_streaking": "Don't look away. FP based on your favorite team's longest streak (wins or losses).",
    "hometown_hero": "Always together. Floobits when 3 or more of your roster players share the same team.",
    # ── Game-Outcome Effects ──
    "comeback_kid": "Find the rising teams. FP per roster player whose team missed playoffs last season. Bonus floobits if your favorite team pulls off a comeback win.",
    "domination": "Ride with the leaders. FP per roster player whose team is currently top-6 in their league. Bonus floobits if your favorite team wins by 21+.",
    "walk_off": "Built for the late game. FP per Q4 or OT TD or field goal scored by this player. Bonus floobits if your favorite team wins on a walk-off.",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "Cover all your bases. Big FPx, but only in a week where every performing card in your lineup clears its FP power bar. One cold player and it pays nothing.",
    "all_in": "Adds FPx for each fantasy point this player scores past a high FP line, up to a cap. No bonus below the line.",
    "diversified": "Don't put all your eggs in one basket. FP per unique output type (FP, FPx, Floobits) across your equipped cards.",
    "gold_rush": "Floobits cards amplify each other. Floobits bonus for each other floobits card in your hand.",
    "stacked_deck": "Multiply the multipliers. FPx for every other FPx card in your hand.",
    "copycat": "Copies the best. FP equal to the highest flat FP bonus from your other cards.",
    "chain_reaction": "Cards feeding cards. FPx that scales with how many of your other 4 cards produced a non-zero bonus.",
    "bonus_round": "Everyone chipped in. FP if 4 or more of your other cards triggered a non-zero bonus this week.",
    "winners_circle": "Back the winners. Floobits whenever this player's real team wins their game this week.",
    "no_passengers": "Depth pays. FPx that scales with your lowest-scoring roster player, so a lineup with no weak link earns more.",
    "franchise": "Build around your guy. FPx when this player is your single highest scorer this week.",
    "metronome": "FP that grows each week this player clears their power bar. A cold week holds the streak rather than resetting it.",
    "double_down": "With the lemons. Multiplies your lowest-earning card's FP this week.",
    "last_resort": "When nothing else works. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each of your other cards that fails to produce a bonus.",
    "high_roller": "Built for the gamble. FPx that scales with how many of your chance cards hit enhanced this week.",
    "fortitude": "Are you feeling the heat? FPx that scales with how many of your streak cards have active streaks.",
    # ── Escalating / Pace Effects ──
    "crescendo": "Miss enough and eventually you can't miss. Each TD by this player rolls for a bonus. Miss and the odds go up. For K, triggers on FGs.",
    "eminence": "Top of the heap. FPx per roster player ranked top-10 at their position by season FP/game.",
    "traverse": "High stakes yardage gamble. FP floor plus a jackpot chance based on yardage by this player.",
    # ── Chance Synergy Effects ──
    "advantage": "Loaded dice. Every chance card in your hand rolls twice, keeping the better result.",
    "catalyst": "Compound interest. This player's FP boosts the odds on all your chance cards. Also pays Floobits.",
    # ── Strategy-Warping Effects ──
    "alchemy": "Transmutation complete. Every field goal your kicker makes counts as a TD for fantasy scoring and other card effects.",
    "home_alone": "Embrace the void. FPx that grows with each empty roster slot.",
    "closer": "Always be closing. Bonus FP from this player's Q4 and OT production.",
    "dark_horse": "The stars shine brightest from below. FPx that scales inversely with the star rating of your roster's {posLabel}.",
    "vagabond": "Never settle. FPx that grows with each roster swap you've made this season.",
    "fat_cat": "Money talks. FP that scales with your Floobits balance. Excludes current week earnings.",
    "surplus": "A reliable kickback. Adds a flat Floobits bonus to your weekly earnings while equipped.",
    "bonsai": "Grown, not gifted. This player's own performance earns permanent FP growth each week. Higher levels demand bigger weeks. Resets if unequipped.",
    # ── New cards (FP/FPx rebalance) ──
    "anthem": "Power in numbers. Flat FP that fires when your hand is heavy on flat-FP cards. 3 or more pays a bonus, 4 raises it, 5 maxes it out.",
    "conductor": "Orchestrates the rest of your hand. Every other flat-FP card you have equipped outputs more. Produces nothing on its own.",
    "captain": "Leads by example. Every other card is amplified by how far its player blows past their power bar this week (up to 2x). Produces nothing on its own.",
    "castaway": "Find the gem on a bad team and they pay you. Bonus FP when your roster includes any player whose team is below .500.",
    "sleeper": "Diamond in the rough territory. Guaranteed FP floor plus a chance at enhanced FP. The trigger bar fills from this player's own FP and from each low-rated player you keep on your roster.",
    "patient": "Stick with the bench. Earns FP each week you keep a sub-3-star roster slot intact, with the bonus growing the longer you hold.",
    "rookie_hype": "Believe in the new class. Bonus FP per rookie on your roster.",
    "wanderer": "A bit of everywhere. Output scales with how many different teams your roster players come from. Max payout when no two share a team.",
    "sandbagger": "Hold the line on a weak slot. Streak grows each week one of your roster slots scores 5 FP or less. Requires a full 6-player roster.",
    "quiet_storm": "Spread the love. Streak grows each week no roster player scores 15 or more FP. Requires a full 6-player roster.",
    "drought": "Cold rosters get hot rewards. Streak grows each week your roster scores under 35 FP total. Requires a full 6-player roster.",
    # ── Prognostication cards ──
    "nose_picker": "Streak grows each week you submit picks yourself instead of letting auto-pick fill them in.",
    "medium": "Bonus FP when your weekly Prognostication accuracy is high.",
    "parlay": "FPx that grows with your weekly Prognostication points.",
    # ── Roster-construction-driven ──
    "synergy": "Two heads, one team. FPx per pair of roster players on the same actual team.",
    "vanguard": "The old guard endures. FPx per roster player with 5 or more seasons played.",
    "range": "Distance is the reward. FP scaling with the total FG yardage this player kicked this week.",
    "loyalty": "Keep the band together. FP per player still equipped from your first lineup this season.",
    "charmed": "Pays out every time luck breaks your way. FP per chance card that triggered this week.",
    "cornerstone": "Roster the position leaders. FPx per roster player ranked #1 at their position by season FP.",
    # ── Diamond stat amplifiers ──
    "doubler": "Doubles down on the scoreboard. Roster TDs count 2x for every other card. Produces nothing on its own.",
    "surveyor": "Measures every yard twice. Roster yards count 1.5x for every other card. Produces nothing on its own.",
    "sharpshooter": "Kicks land harder. Roster FGs count 2x for every other card. Produces nothing on its own.",
}

EFFECT_DETAIL_TEMPLATES = {
    # Stat ladder families
    "cadence": "+{perCompletionFP} FP for every completion by this player",
    "rhythm": "+{per25Mult} FPx per 25 completions, +{bonusMult} more past {threshold}",
    "clockwork": "+{per25Mult} FPx per 25 completions, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "beast_of_burden": "+{per25Mult} FPx per 25 carries, +{bonusMult} more past {threshold}",
    "iron_man": "+{per25Mult} FPx per 25 carries, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "odyssey": "+{per50Mult} FPx per 50 rushing yards, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "battering_ram": "+{perTdMult} FPx for every rushing TD by this player",
    "custody": "+{per5Mult} FPx per 5 receptions, +{bonusMult} more past {threshold}",
    "tenure": "+{per5Mult} FPx per 5 receptions, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "getaway": "+{per10Mult} FPx per 10 YAC, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "runback": "+{perYardFP} FP per punt return yard by this player",
    "house_call": "+{perYardFP} FP per return yard, plus a chance at {bonusFP} FP on a return TD",
    "attention": "+{per5Mult} FPx per 5 targets by this player",
    "altitude": "+{perYardFP} FP per yard of average target depth above {threshold}",
    "haymaker": "+{perYardFP} FP per passing yard, +{bonusFP} for every 20+ yard completion",
    "highpoint": "+{perReceptionFP} FP per reception, +{bonusFP} per contested catch",
    "breakaway": "+{perYardFP} FP per rushing yard, +{bonusFP} for every 20+ yard run",
    "houdini": "+{perYardFP} FP per rushing yard, plus a chance at {bonusFP} FP filling from broken tackles",
    "custodian": "+{perReceptionFP} FP per reception, +{bonusFP} per bailout",
    "slipstream": "+{per100Mult} FPx per 100 passing yards by this player",
    "updraft": "+{perYardFP} FP per passing yard, +{gateFP} bonus at each of {gates}",
    "stratosphere": "+{per100Mult} FPx per 100 passing yards, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "marksman": "+{per5Mult} FPx per 5 well-placed throws, +{cleanSheetMult} more on 0 bad throws",
    "dead_eye": "+{per5Mult} FPx per 5 well-placed throws, plus a streak growing {growthPerTick} FPx per clean sheet",
    "frontier": "+{perYardFP} FP per receiving yard by this player",
    "territory": "+{per50Mult} FPx per 50 receiving yards, +{gateMult} more at 75, 125 and 175",
    "dominion": "+{per50Mult} FPx per 50 receiving yards, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "freight": "+{perYardFP} FP per yard after contact by this player",
    "grinder": "+{per50Mult} FPx per 50 yards after contact, +{ratioMult} more when they exceed half the total",
    "landslide": "+{per50Mult} FPx per 50 yards after contact, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "pinpoint": "+{perPuntFP} FP per punt downed inside the 20",
    "coffin_corner": "+{perPuntMult} FPx per punt inside the 20, +{bonusMult} more for inside the 10",
    "undertaker": "+{perPuntMult} FPx per punt inside the 20, plus a streak growing {growthPerTick} FPx per week past {threshold}",
    "paydirt": "+{perTdMult} FPx for every receiving TD by this player",
    "end_zone": "+{perTdFP} FP per receiving TD, +{bonusFP} bonus at {threshold}+",
    "promised_land": "+{perTdFP} FP per receiving TD, plus escalating odds at {bonusFP} FP on each one",
    "bombardier": "+{perTdMult} FPx for every passing TD by this player",
    "salvo": "+{perTdFP} FP per passing TD, +{bonusFP} bonus at {threshold}+",
    "barrage": "+{perTdFP} FP per passing TD, plus escalating odds at {bonusFP} FP on each one",
    # Flat FP (WR)
    "freebie": "+{baseFP} FP per week",
    "entourage": "+{perPlayerFP} FP for every roster player with {minStars}★+",
    "touchdown_pinata": "+{perTdFP} FP for every TD your roster scores",
    "scrappy": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each {maxStars}★-or-lower roster player.",
    "honor_roll": "+{baseDelta} FPx once this player reaches {fpThreshold} FP, and grows if they score more, up to +{maxDelta} FPx.",
    "three_pointer": "+{perFgFP} FP for every FG this player makes",
    "garbage_time": "+{perPlayerFP} FP for every roster player with 0 TDs",
    "loyalty_bonus": "+{perStreakFP} FP per win in your favorite team's win streak",
    "windfall": "+{perPlayerFloobits}F per overperforming roster player",
    "rng": "Random +{minFP}–{maxFP} FP each week",
    "snake_eyes": "FPx that grows the WORSE this player's game is. A blank stat line pays the most.",
    "avalanche": "Roster TDs pay escalating FP: 1st={td1}, 2nd={td2}, 3rd={td3}, 4th={td4} then diminishing",
    "hedge": "Tops this player up to a {floorSoloFP} FP floor if they have a quiet week.",
    "complacency": "+{baseReward} FP, +{growthPerTick} per week roster is unchanged.",
    "spotlight_moment": "+{rewardValue} FP when this player scores a TD. WR counts either WR scoring a TD.",
    "ace_up_the_sleeve": "+{baseFP} FP base, +{rewardValue} bonus if this player combines for {threshold}+ {statDisplay}",
    # Multiplier (QB) — FPx
    "cornucopia": "FPx that grows as your roster scores TDs.",
    "babysitter": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each roster player under {fpThreshold} FP.",
    "martyr": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 10% at 1 loss, grows with your favorite team's season losses, up to 60%",
    "resplendent": "+{perPlayerFP} FP per overperforming roster player",
    "big_deal": "+{xMultDelta} FPx",
    "luminary": "FPx that grows the more FP this player earns compared to teammates",
    "squire": "+{perTdFP} FP per TD by this player",
    "juggernaut": "+{baseXDelta} FPx base, grows with your favorite team's win streak.",
    "underdog": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Chance grows the lower your favorite team's ELO rating is, up to 75%",
    "stockpiler": "+{perSwapXMult} FPx per unused roster swap",
    "providence": "+{baseDelta} FPx, plus +{chanceBonusPct}% trigger odds to every chance card in your hand",
    "house_money": "+{baseFP} FP base, +{perUpsetFP} per your favorite team's upset wins this season",
    "rising_tide": "+{perPlayerMult} FPx per overperforming roster player (max +{maxDelta})",
    # Floobits (RB)
    "allowance": "{floobits} Floobits per week",
    "cha_ching": "{perTdFloobits} Floobits per TD by this player",
    "piggy_bank": "{fpPercent}% of this player's FP → Floobits",
    "good_neighbor": "+{baseFloobits}F base + {perMissFloobits}F per missed FG this week",
    "consolation_prize": "+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. Trigger odds fill from this player's FP plus each roster player under {fpThreshold} FP.",
    "rock_bottom": "+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. 20% at 1-game losing streak, up to 65%",
    "buy_low": "{perPlayerFloobits} Floobits per underperforming roster player",
    "trust_fund": "{baseFloobits} Floobits base, +{growthPerWeek} per week your roster stays unchanged",
    "feeding_frenzy": "{perTdFloobits}F per roster TD, +{bonusFloobits}F jackpot at {tdThreshold}+ roster TDs",
    "highlight_reel": "{rewardValue} Floobits per your favorite team's big plays",
    # Conditional (TE)
    "showoff": "+{perStarFP} FP per 5-star roster player",
    "bandwagon": "+{rewardDelta} FPx when your favorite team wins",
    "believe": "+{perWinFP} FP per favorite-team season win, +{floobitsOnTrigger}F when they win this week",
    "reclamation": "+{rewardValue} FP when majority of roster is underperforming",
    "pedigree": "+{baseFP} FP base, +{rewardValue} FP when your favorite team's ELO ≥ {eloThreshold}",
    # Streak (K)
    # Synergy: each other streak card in hand adds +1 to effective streak count (+growthPerTick per peer)
    "on_fire": "+{baseRewardDelta} FPx base, +{growthPerTick} per consecutive week with a FG made by your K.",
    "snowball_fight": "+{baseReward} FP base, +{growthPerTick} per consecutive week at least one player on your roster scores a TD.",
    "fairweather_fan": "{baseReward} Floobits base, +{growthPerTick} per consecutive favorite-team win.",
    "bandwagon_express": "+{baseReward} FP base, +{growthPerTick} per consecutive favorite-team win.",
    "touchdown_jackpot": "{baseReward} Floobits on 1st roster TD, +{growthPerTick} for every subsequent roster TD. Resets weekly.",
    "odometer": "Escalating FP as this player piles up yards this week (40 / 80 / 120 / 160+).",
    "leg_day": "+{baseReward} FP base, +{growthPerTick} per consecutive game with a 35+ yd FG by your K. A week with no FG attempts will not break the streak.",
    "automatic": "+{baseReward} FP base, +{growthPerTick} per consecutive week your K makes all FG attempts. A week with no FG attempts will not break the streak.",
    "momentum": "+{baseRewardDelta} FPx base, +{growthPerTick} per consecutive week your roster scores 100+ FP.",
    # ── New Position-Based Effects ──
    "gunslinger": "+{perGoodThrowFP} FP for every well-placed ball by this player",
    "air_raid": "{perTdFloobits} Floobits for every passing TD in one game by this player",
    "workhorse": "+{perAttemptFP} FP for every rushing attempt in one game by this player",
    "expedition": "+{perFiftyYardsFP} FP for every 50 rushing yards in one game by this player",
    "stampede": "+{baseDelta} FPx base, +{enhancedDelta} FPx when this player hits {yardThreshold}+ rush yards in a game",
    "goal_line_vulture": "{perTdFloobits} Floobits for every rushing TD by this player in a game",
    "possession": "+{perReceptionFP} FP for every reception by this player in a game",
    "trebuchet": "+{baseFP} FP base, +{rewardValue} bonus if this player catches a {threshold}+ yard pass",
    "double_trouble": "+{singleWrFP} FP when a WR scores, +{rewardValue} bonus FP when both WRs score",
    "slippery": "+{perYacFP} FP per 10 yards after catch by this player in a game",
    "jailbreak": "+{baseFP} FP base, +{rewardValue} bonus if this player racks up {threshold}+ yards after catch in a game",
    "safety_blanket": "+{perReceptionFP} FP per reception by this player in a game",
    "industrious": "{perReceptionFloobits} Floobits per reception by this player in a game",
    "lead_blocker": "+{perTdFP} FP per TE TD in a game. Rushing touchdowns by the TE team's RB count as TE TDs",
    "mismatch": "+{perTdFP} FP per TD by this player, +{bonusFP} bonus at {tdThreshold}+ TDs",
    "sniper": "+{perFgFP} FP per 40+ yard FG by this player in a game",
    "spectacle": "+{perPointFP} FP per point this player overperforms by",
    "indemnity": "+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. Chance grows with {posLabel} underperformance, up to 70%",
    # ── Same-Team Stacking Effects ──
    "stack": "+{rewardDelta} FPx when this player and a rostered WR share a team",
    "backfield_buddies": "+{rewardValue} FPx when this player and your rostered RB share a team",
    "homer": "+{perPlayerMult} FPx per roster player on your favorite team. Max +{maxDelta} FPx.",
    "gone_streaking": "+{baseFP} FP base, +{perStreakFP} per game in longest streak (winning or losing) by your favorite team this season. Streak does not need to be active.",
    "hometown_hero": "+{rewardFloobits} Floobits when 3+ roster players share a team",
    # ── Game-Outcome Effects ──
    "comeback_kid": "+{perPlayerFP} FP per roster player whose team missed playoffs last season, +{floobitsOnTrigger}F if your favorite team wins a comeback this week",
    "domination": "+{perPlayerFP} FP per roster player whose team is top-6 in their league, +{floobitsOnTrigger}F if your favorite team wins by {marginThreshold}+ this week",
    "walk_off": "+{perScoreFP} FP per Q4/OT TD or FG by this player, +{floobitsOnTrigger}F when your favorite team wins with a walk-off",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "+{rewardDelta} FPx when every card in your lineup clears its power bar",
    "all_in": "+{perFPxShown} FPx for every fantasy point this player scores past {studLine} FP.",
    "diversified": "+{perTypeFP} FP per unique output type in your hand (FP, FPx, Floobits)",
    "gold_rush": "{perCardFloobits} Floobits per other Floobits card in your hand",
    "stacked_deck": "+{perCardMult} FPx for each other FPx card in your hand",
    "copycat": "+FP equal to highest flat FP bonus from your other cards",
    "chain_reaction": "+{perCardXMult} FPx for every card in your hand that produced a non-zero bonus this week",
    "bonus_round": "+{rewardValue} FP when 4 or more of your other cards produced a non-zero bonus this week",
    "winners_circle": "{winFloobits} Floobits when this player's team wins this week",
    "no_passengers": "+{perFloorFP} FPx per FP scored by your lowest roster player (max +{maxDelta})",
    "franchise": "+{topScorerDelta} FPx when this player is your top scorer this week",
    "metronome": "+{baseReward} FP, +{growthPerTick} per consecutive week this player clears their power bar. Streak does not reset on cold weeks.",
    "double_down": "Multiplies your lowest-earning card's FP by {rewardValue} this week",
    "last_resort": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each of your other cards that produced no bonus.",
    "high_roller": "+{perCardMult} FPx per chance card that triggered enhanced bonuses this week",
    "fortitude": "+{perCardMult} FPx per active streak card in your hand",
    # ── Escalating / Pace Effects ──
    "crescendo": "+{baseFP} FP guaranteed. {baseChance}% chance at {bonusFP} FP on this player's first {scoreNoun}, chance increases by +{chanceStep}% if bonus doesn't trigger.",
    "eminence": "+{perPlayerMult} FPx per roster player ranked top-10 at their position. Max +{maxDelta} FPx. Active from week 3.",
    "traverse": "+{baseFP} FP floor + {bonusFP} FP jackpot. Jackpot chance starts at {baseChance}%, +{chancePerStep}% per {yardStep} {yardType} yards",
    # ── Chance Synergy Effects ──
    "advantage": "All chance cards roll {rollCount}x for their bonus, keeping the best result",
    "catalyst": "+1% chance boost per {fpPer1PctSolo} of this player's FP above {baselineSolo}. Max +{maxBoostDisplay}%. Also pays {baseFloobits} Floobits",
    # ── Strategy-Warping Effects ──
    "alchemy": "+{perFgBonusFP} bonus FP per FG by your kicker. Those FGs also count as TDs for other cards in your hand.",
    "home_alone": "+{perSlotMult} FPx per empty roster slot",
    "closer": "This player's Q4/OT fantasy points are multiplied by {q4MultFactor}x",
    "dark_horse": "+{perStarMult} FPx per star under 5 of your rostered {posLabel}",
    "vagabond": "+{perSwapXMult} FPx per roster swap used this season",
    "fat_cat": "+1 FP per {floobitsPerFP} Floobits in your balance (max {maxFP} FP)",
    "surplus": "+{flatBonus}F added to weekly earnings while equipped",
    "bonsai": "+{baseFP} FP guaranteed. This player's {triggerLabel} scale the chance to grow the base by +{growthFP} FP at week's end. Every grow slows the next.",
    # ── New cards (FP/FPx rebalance) ──
    "anthem": "+{tier3FP} FP with 3 flat-FP cards equipped, +{tier4FP} with 4, +{tier5FP} with 5",
    "conductor": "Boosts each other flat-FP card's output by +{boostPct}%",
    "captain": "+{perOvershootShown}% output to each other card per FP its player scores over their power bar (max +100%)",
    "castaway": "+{rewardFP} FP when at least one roster player is on a sub-.500 team",
    "sleeper": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Trigger odds fill from this player's FP plus each roster player under 3 stars.",
    "patient": "+{baseFP} FP per week a sub-3-star roster slot stays unchanged",
    "rookie_hype": "+{perRookieFP} FP per rookie on your roster",
    "wanderer": "+{perTeamFP} FP per unique team represented across your roster",
    "sandbagger": "+{baseReward} FP, +{growthPerTick} per consecutive week any roster slot scored 5 FP or less. Needs a full 6-player roster.",
    "quiet_storm": "+{baseReward} FP, +{growthPerTick} per consecutive week no roster player scored 15 or more FP. Needs a full 6-player roster.",
    "drought": "+{baseReward} FP, +{growthPerTick} per consecutive week your roster scored under 35 FP. Needs a full 6-player roster.",
    # ── Prognostication cards ──
    "nose_picker": "+{baseReward} FP base. Grows every week you submit manual picks. Growth starts at +{firstWeekGrowth} FP and tapers off as the streak continues.",
    "medium": "+{lowFP} FP at 50%+ Prognostication accuracy, +{midFP} FP at 65%+, +{highFP} FP at 85%+. Counts auto-picks",
    "parlay": "FPx that grows with your weekly Prognostication points. Counts auto-picks",
    # ── Roster-construction-driven ──
    "synergy": "+{perPairMult} FPx per pair of roster players on the same actual team. Max +{maxDelta} FPx.",
    "vanguard": "+{perVetMult} FPx per roster player with 5+ seasons played. Max +{maxDelta} FPx.",
    "range": "+{perYardFP} FP per yard of FG kicked by this player this week.",
    "loyalty": "+{perPlayerFP} FP per player still equipped from your first lineup this season.",
    "charmed": "+{perTriggerFP} FP per chance card that triggered this week.",
    "cornerstone": "+{perPlayerMult} FPx per roster player ranked #1 at their position. Max +{maxDelta} FPx. Active from week 3.",
    "doubler": "Roster TDs count {tdMult}x for every other card's effect this week.",
    "surveyor": "Roster yards count {yardMult}x for every other card's effect this week.",
    "sharpshooter": "Roster FGs count {fgMult}x for every other card's effect this week.",
}

# ─── Shared + Position-Exclusive Effect Pools ────────────────────────────────
# All positions draw from the shared pool. Position-exclusive pools add effects
# that reference position-specific stats (passing, rushing, receiving, kicking).

SHARED_EFFECT_POOL = [
    # flat_fp effects
    "freebie", "entourage", "touchdown_pinata",
    # NOTE: the LOW-RATED-PLAYER set — "scrappy", "sleeper", "patient", "dark_horse" —
    # retired together (owner call 2026-08-06). Each paid for FIELDING WEAK PLAYERS:
    # scrappy and sleeper filled their chance bar from 2-star-or-lower roster players,
    # patient paid per week a sub-3-star slot went untouched, dark_horse scaled FPx
    # INVERSELY to the card player's stars. Under fusion an equipped card IS a rostered
    # player, so almost nobody fields a weak lineup on purpose and these sat dead in hand.
    # Their high-rated counterparts (Entourage 3-star-plus, Showoff 5-star) are KEPT — the
    # objection is to rewarding weakness, not to reading a rating. Dropped from the minting
    # pool; compute/templates stay dormant so owned copies still score.
    "honor_roll", "garbage_time", "loyalty_bonus",
    "homer", "gone_streaking", "rng", "snake_eyes", "avalanche", "hedge",
    # NOTE: the OVER/UNDERPERFORMANCE set — "resplendent" (Hot Stove), "windfall",
    # "buy_low", "reclamation", "rising_tide", "spectacle" — retired together (owner call
    # 2026-08-06). All six keyed off `playerPerformanceRatings`, a percentile-of-production
    # score computed weekly in memory and surfaced nowhere a user can see, so "is my roster
    # overperforming?" was unanswerable while setting a lineup. It is also a LAUNDERED stat:
    # derived from real production but stripped of the texture that made it readable. The
    # replacement direction is stat-native cards (see the stat ladder). Removed from the
    # minting pool; compute/templates stay dormant so any card already carrying them scores.
    # multiplier effects
    "big_deal", "cornucopia",
    # NOTE: "babysitter" and "consolation_prize" retired (owner call 2026-08-06) — the last
    # two of the "worse is better" class the fusion rework began cutting (martyr, underdog,
    # rock_bottom, indemnity). Both filled their chance bar from roster players under an FP
    # threshold, so they paid for a COLD roster. Unlike the low-rated set they were not
    # structurally dead (a well-rated player still has quiet weeks), but they pull against
    # the direction of every stat-native card. Dropped from the minting pool;
    # compute/templates stay dormant so owned copies still score.
    "juggernaut",
    # NOTE: "martyr" and "underdog" retired in the fusion chance rework (owner call 2026-07-26).
    # Both are "worse = better odds" losers keyed off the favorite team's record — the exact
    # inverse of the new "fill the bar to raise your odds" chance model, so they can't be
    # rerouted without flipping their meaning. Removed from the minting pool; compute/templates
    # stay dormant so any card already carrying them still scores.
    # NOTE: "stockpiler" retired in the fantasy/cards fusion — it scaled FPx with
    # UNUSED roster swaps, and swaps are gone. Removed from the minting pool so no
    # new copies are created; the handler + display + payout reader are kept so any
    # existing owned copies still render (they compute 0 with no swaps).
    "providence",
    # NOTE: "house_money" retired in the fusion chance/favorite-team cleanup (owner call
    # 2026-07-26) — it accumulated FP only on the favorite team's UPSET wins, which are rare,
    # so it barely grew past its base. Same favorite-team-parasite class as underdog/martyr/
    # rock_bottom. Removed from the minting pool; compute/templates/streak-config stay dormant
    # so any card already carrying it still scores.
    # floobits effects
    "allowance", "cha_ching", "piggy_bank",
    # NOTE: "good_neighbor" moved to the K-exclusive pool (owner call 2026-08-06). It minted
    # on ANY position while paying off the ROSTER kicker's missed FGs, so on a QB card the
    # depicted player was decorative. Rule: a card must never sit on one position and read
    # another's stats. Audited the whole pool for this — lead_blocker, stack and
    # backfield_buddies also touch a second position but use the CARD's player as a real
    # participant (lead_blocker pays the TE's own TDs with same-team RB TDs added; stack and
    # backfield_buddies make the card player half of a same-team pair), so they stay.
    # NOTE: "rock_bottom" retired alongside martyr/underdog (owner call 2026-07-26) — its odds
    # ride the favorite team's LOSING streak, another "worse = better" loser incompatible with
    # the fill-the-bar chance model. Dormant compute/templates kept for owned copies.
    "trust_fund",
    "feeding_frenzy", "highlight_reel",
    # conditional effects
    "showoff", "bandwagon",
    "believe",
    "pedigree", "mismatch",
    # streak effects
    "snowball_fight",
    "fairweather_fan", "bandwagon_express", "touchdown_jackpot",
    "odometer", "complacency", "momentum",
    # position-keyed (generic concept, adapts to card position)
    "luminary", "squire", "spotlight_moment",
    # cross-position
    # NOTE: "indemnity" retired in the fusion chance rework (owner call 2026-07-26) — its odds
    # grew as THIS player underperformed, the direct inverse of "clear your bar to raise your
    # odds." Dormant compute/templates kept for owned copies.
    # same-team / game-outcome
    "hometown_hero",
    "walk_off",
    # NOTE: the STANDINGS-LOOKUP set — "comeback_kid", "domination", "castaway" — retired
    # together (owner call 2026-08-06). Each paid off a fact about a roster player's TEAM
    # rather than anything the player did: castaway wanted someone on a sub-.500 club,
    # domination someone on a top-6 club, comeback_kid someone whose club missed the
    # playoffs LAST season. Playing them well meant leaving the fantasy page to read the
    # standings (or worse, last season's final table) for a modest per-player bonus, and
    # the answer changed under you as the season moved. Dropped from the minting pool;
    # compute/templates stay dormant so owned copies still score. "walk_off" is KEPT — it
    # pays on this player's own Q4/OT scores.
    # card-to-card
    "full_roster", "all_in", "diversified", "gold_rush",
    "stacked_deck", "copycat", "chain_reaction",
    "bonus_round", "double_down",
    "last_resort", "high_roller",
    "fortitude",
    # escalating / pace
    "eminence",
    # chance synergy
    "advantage", "catalyst",
    # strategy-warping
    "closer",
    # NOTE: "home_alone" retired from circulation (owner call 2026-07-25) — its "empty
    # roster slot" reward doesn't fit the position-locked fusion lineup, where a full
    # lineup is always the goal. Removed from the minting pool; its compute/templates
    # stay dormant so any card already carrying it still scores.
    # NOTE: "surplus" retired from circulation — it was built to raise the old
    # weekly Floobit income cap, which no longer exists. Removed from the minting
    # pool so no new copies are created; the effect handler + display + payout
    # reader are kept so the existing owned copies still render and pay out.
    # NOTE: "vagabond" retired in the fantasy/cards fusion — it scaled FPx with
    # roster swaps USED this season, and swaps are gone. Removed from the minting
    # pool (handler + display + payout reader kept for existing owned copies).
    "fat_cat", "bonsai",
    # New cards (FP/FPx rebalance)
    "anthem", "conductor", "captain",
    "rookie_hype", "wanderer",
    # fusion additions (2026-07) — replace the retired anti-synergy effects
    "winners_circle", "no_passengers", "franchise", "metronome",
    # NOTE: "sandbagger", "quiet_storm", "drought" retired from circulation (owner call
    # 2026-07-26). All three reward a COLD roster (a slot ≤5 FP / no player ≥15 FP /
    # roster total <35), but in fusion your fantasy score IS your roster's FP — so they
    # only pay if you deliberately tank your own lineup, which never nets out. Removed
    # from the minting pool; compute/templates/streak-configs stay dormant so any card
    # already carrying them still scores.
    # Prognostication cards
    "nose_picker", "medium", "parlay",
    # Roster-construction-driven (next-season additions)
    "synergy", "vanguard", "loyalty",
    # Chance-trigger synergy (second-pass)
    "charmed",
    # Per-position leaders
    "cornerstone",
    # Diamond stat amplifiers
    "doubler", "surveyor", "sharpshooter",
]

POSITION_EXCLUSIVE_POOLS = {
    1: ["gunslinger", "air_raid", "stack", "backfield_buddies",
        "slipstream", "updraft", "stratosphere", "marksman", "dead_eye",
        "cadence", "rhythm", "clockwork", "altitude", "haymaker",
        "bombardier", "salvo", "barrage",
        "crescendo", "traverse"],
    2: ["workhorse", "expedition", "stampede", "goal_line_vulture",
        "freight", "grinder", "landslide",
        "beast_of_burden", "iron_man", "odyssey", "battering_ram",
        "breakaway", "houdini", "runback", "house_call",
        "crescendo", "traverse"],
    3: ["possession", "trebuchet", "double_trouble",
        "frontier", "territory", "dominion", "paydirt", "end_zone", "promised_land",
        "custody", "tenure", "getaway", "attention", "highpoint", "custodian",
        "runback", "house_call",
        "slippery", "jailbreak",
        "ace_up_the_sleeve", "crescendo", "traverse"],
    4: ["safety_blanket", "industrious", "lead_blocker",
        "frontier", "territory", "dominion", "paydirt", "end_zone", "promised_land",
        "custody", "tenure", "getaway", "attention", "highpoint", "custodian",
        "traverse"],
    5: ["three_pointer", "sniper", "leg_day", "good_neighbor",
        "pinpoint", "coffin_corner", "undertaker",
        "automatic", "on_fire",
        "crescendo", "alchemy",
        "range"],
}

# Effects excluded from certain positions (dead cards)
# TD-dependent effects are dead on K (kickers never score TDs)
POSITION_EXCLUDED_EFFECTS = {
    4: {"crescendo"},  # TE: too few TDs for escalating mechanic
    5: {"spotlight_moment", "squire", "cha_ching", "mismatch", "double_trouble",
        "traverse", "closer"},  # K: no meaningful yardage or Q4 stats
}


def effectValidPositions(effectName: str) -> set:
    """Positions (1-5) where this effect can validly exist — mirrors how buildEffectConfig
    builds its pool: a SHARED effect is valid for every position it isn't excluded from; a
    position-EXCLUSIVE effect only for the position(s) that list it (some, like crescendo /
    traverse, span several). Drives the transplant's position rule: a shared effect can move
    onto any same-edition card, a position-specific one only onto its valid position(s)."""
    if not effectName or effectName in ('none', ''):
        return set()
    valid = set()
    for pos in range(1, 6):
        excluded = POSITION_EXCLUDED_EFFECTS.get(pos, set())
        if (effectName in SHARED_EFFECT_POOL and effectName not in excluded) \
           or effectName in POSITION_EXCLUSIVE_POOLS.get(pos, []):
            valid.add(pos)
    return valid

# ─── Streak Configuration ────────────────────────────────────────────────────

# resetCondition: what breaks the streak (checked at week end)
# isWeekly: if True, streak resets each week (accumulates within a week)
STREAK_CONFIGS = {
    "on_fire":           {"resetCondition": "kicker_fg", "isWeekly": False},
    "snowball_fight":    {"resetCondition": "roster_td", "isWeekly": False},
    "fairweather_fan":   {"resetCondition": "favorite_team_wins", "isWeekly": False},
    "bandwagon_express": {"resetCondition": "favorite_team_wins", "isWeekly": False},
    "touchdown_jackpot": {"resetCondition": None, "isWeekly": True},
    "complacency":       {"resetCondition": "roster_unchanged", "isWeekly": False},
    "leg_day":           {"resetCondition": "kicker_35plus", "isWeekly": False},
    "automatic":         {"resetCondition": "kicker_no_miss", "isWeekly": False},
    "momentum":          {"resetCondition": "roster_75fp", "isWeekly": False},
    # Fusion (2026-07): grows each week the depicted player clears their FP bar; a cold
    # week FREEZES it (noReset) rather than resetting — hence a deliberately modest step.
    "metronome":         {"resetCondition": "player_cleared_bar", "isWeekly": False, "noReset": True},
    # Inverse streaks — grow when the roster underperforms; break when
    # production picks up. Get peak-decay carryover the same as forward
    # streaks so a built-up underperformance bonus doesn't vanish on the
    # first hot week.
    "sandbagger":        {"resetCondition": "roster_slot_low_5fp", "isWeekly": False},
    "quiet_storm":       {"resetCondition": "no_player_15fp", "isWeekly": False},
    "drought":           {"resetCondition": "roster_under_50fp", "isWeekly": False},
    # Prognostication
    "nose_picker":        {"resetCondition": "pickem_manual_submit", "isWeekly": False},
    "house_money":       {"resetCondition": "favorite_team_upset_win", "isWeekly": False, "noReset": True},
    "bonsai":       {"resetCondition": "equipped", "isWeekly": False, "noReset": True},
    # Stat ladder prismatic rungs — the streak rides on top of a base rate that pays
    # every week, so a cold week costs the growth but never the whole card.
    "dominion":     {"resetCondition": "card_player_100_rec_yards", "isWeekly": False},
    "landslide":    {"resetCondition": "card_player_100_contact_yards", "isWeekly": False},
    "undertaker":   {"resetCondition": "card_player_multi_pin", "isWeekly": False},
    "stratosphere": {"resetCondition": "card_player_big_passing_week", "isWeekly": False},
    "dead_eye":     {"resetCondition": "card_player_clean_sheet", "isWeekly": False},
    "clockwork":    {"resetCondition": "card_player_completion_bar", "isWeekly": False},
    "iron_man":     {"resetCondition": "card_player_carry_bar", "isWeekly": False},
    "odyssey":      {"resetCondition": "card_player_100_rush_yards", "isWeekly": False},
    "tenure":       {"resetCondition": "card_player_reception_bar", "isWeekly": False},
    "getaway":      {"resetCondition": "card_player_big_yac", "isWeekly": False},
}

# ─── Cultivation Trigger Pool ────────────────────────────────────────────────
# Each trigger is a countable, repeatable game event. Pass TDs count for both
# QBs (as passer) and WR/TEs (as receiver) so stacking same-team players
# doubles trigger frequency.
CULTIVATION_TRIGGER_POOL = [
    # statPaths: list of (category, key) tuples — all are summed across roster players.
    # stepSize: triggers required at level 0 for a guaranteed grow; scales with level.
    # pass_td counts for both QBs (passer) and WR/TEs (receiver) for double events.
    {"event": "pass_td",      "label": "passing/receiving TDs",   "stepSize": 3,  "statPaths": [("passing_stats", "tds"), ("receiving_stats", "rcvTds")]},
    {"event": "rush_td",      "label": "rushing TDs",             "stepSize": 3,  "statPaths": [("rushing_stats", "runTds")]},
    {"event": "reception",    "label": "receptions",              "stepSize": 12, "statPaths": [("receiving_stats", "receptions")]},
    {"event": "fg_made",      "label": "field goals made",        "stepSize": 3,  "statPaths": [("kicking_stats", "fgs")]},
    {"event": "carry",        "label": "rushing attempts",        "stepSize": 15, "statPaths": [("rushing_stats", "carries")]},
    {"event": "yac",          "label": "yards after catch",       "stepSize": 60, "statPaths": [("receiving_stats", "yac")]},
]

# Bonsai counts the ON-CARD player's own trigger events, so the trigger must be a stat that
# player actually posts. Restrict the mint-time pick to each position's real stats (1-based
# QB..K) — otherwise e.g. a WR could roll the "rushing attempts" trigger and never grow.
_CULTIVATION_TRIGGERS_BY_POSITION = {
    1: {"pass_td"},                          # QB: passing TDs
    2: {"carry", "rush_td", "reception"},    # RB: carries, rushing TDs, checkdown catches
    3: {"reception", "yac", "pass_td"},      # WR: catches, YAC, receiving TDs
    4: {"reception", "yac", "pass_td"},      # TE: catches, YAC, receiving TDs
    5: {"fg_made"},                          # K: field goals
}


# ─── EffectResult ────────────────────────────────────────────────────────────

@dataclass
class EffectResult:
    """Result of computing a single card's primary effect."""
    fpBonus: float = 0.0
    floobits: int = 0
    multBonus: float = 0.0   # FPx: multiplicative factor (e.g. 1.3 means ×1.3)
    equation: str = ""       # Human-readable equation showing how value was derived
    # Chance card metadata
    chanceRoll: float = 0.0
    chanceThreshold: float = 0.0
    chanceTriggered: bool = False
    # Cultivation (Bonsai): the odds gate FUTURE growth, and fpBonus is the guaranteed
    # base — so the projection EV pass must NOT scale the payout down by chanceThreshold.
    chanceMetaGrowth: bool = False


def _chanceEq(baseChance, chanceBonus, totalChance, triggered, reward, context, ctx=None, base=None):
    """Build a standardized chance card equation string.

    base  – e.g. "+4.0 FP" or "+8F", shown as guaranteed floor
    reward – e.g. "+18 FP" or "+30F", shown as enhanced payout
    context – e.g. "2 low-rated" or "56 ELO below avg"
    """
    bonusStr = f"+{chanceBonus:.0%}" if chanceBonus > 0 else ""
    pctStr = f"({baseChance:.0%}{bonusStr})" if bonusStr else f"{totalChance:.0%}"
    basePrefix = f"{base}. " if base else ""
    if ctx and getattr(ctx, 'gamesActive', False):
        return f"{basePrefix}{pctStr} chance ({context}) to win {reward}"
    if triggered:
        return f"{reward}. {pctStr} chance ({context}) triggered"
    return f"{basePrefix}{pctStr} chance ({context}) missed"


def _chanceFpFill(ctx, cardPlayerId) -> float:
    """0-1 fill from the on-card player's weekly FP toward their position bar."""
    from constants import CARD_GATE_FP_THRESHOLDS
    pos = (getattr(ctx, 'rosterPlayerPositions', None) or {}).get(cardPlayerId, 0)
    thr = CARD_GATE_FP_THRESHOLDS.get(pos, 0) or 0
    if thr <= 0:
        return 0.0
    fp = ((getattr(ctx, 'weekPlayerStats', None) or {}).get(cardPlayerId, {}) or {}).get("fantasyPoints", 0) or 0
    return max(0.0, min(1.0, fp / thr))


def _chanceOdds(ctx, cardPlayerId, conditionFill: float, useFP: bool = True) -> float:
    """Additive trigger probability for a chance card's enhanced payout.

    Group A (useFP=True): the depicted player's FP fills up to CARD_CHANCE_FP_WEIGHT of the
    bar and the card's own condition fills up to CARD_CHANCE_CONDITION_WEIGHT; the two sum.
    Group C (useFP=False): the condition owns the whole bar. Any hand synergy (ctx.chanceBonus
    from Providence/Catalyst/innate) adds on top. Capped just under 1.0."""
    from constants import CARD_CHANCE_FP_WEIGHT, CARD_CHANCE_CONDITION_WEIGHT
    conditionFill = max(0.0, min(1.0, conditionFill))
    if useFP:
        fpPart = CARD_CHANCE_FP_WEIGHT * _chanceFpFill(ctx, cardPlayerId)
        condPart = CARD_CHANCE_CONDITION_WEIGHT * conditionFill
    else:
        fpPart = 0.0
        condPart = conditionFill
    return max(0.0, min(0.99, fpPart + condPart + getattr(ctx, 'chanceBonus', 0.0)))


def _chanceBarEq(ctx, odds, conditionFill, useFP, triggered, reward, context, base):
    """Chance-bar equation string: the additive odds shown as the trigger %, with a note on
    what filled the bar (the on-card player's FP + the condition, or the condition alone)."""
    pctStr = f"{odds:.0%}"
    fill = "player FP + " if useFP else ""
    basePrefix = f"{base}. " if base else ""
    if ctx and getattr(ctx, 'gamesActive', False):
        return f"{basePrefix}{pctStr} to win {reward} ({fill}{context})"
    if triggered:
        return f"{reward}. {pctStr} ({fill}{context}) triggered"
    return f"{basePrefix}{pctStr} ({fill}{context}) missed"


# ─── Primary Parameter Builders ──────────────────────────────────────────────
# Each effect has base values scaled by playerRating and editionScale.
# ratingNorm = playerRating - 60 (range 0–40 for ratings 60–100)

def _buildCrossPositionParams(effectName, playerRating, editionScale, position=None):
    """Cross-category effects (hand composition, trigger-chain, etc.).

    Numeric constants represent the post-Balatro (3×) values; `_BAL_FP_MULT`
    / `_BAL_FPX_MULT` at the top of the file dial them back at build time.
    Conductor's structural 20% amp is left undialed — it scales with the
    cards it amplifies.
    """
    rn = playerRating - 60
    if effectName == "spectacle":
        return {"rewardType": "fp", "perPointFP": round((2.04 + rn * 0.102) * editionScale * _BAL_FP_MULT, 2)}
    if effectName == "indemnity":
        # Floobits output — leave untouched
        return {"rewardType": "floobits", "baseFloobits": int(round(8 * editionScale)),
                "enhancedFloobits": int(round((30 + rn * 0.4) * editionScale)),
                "isChanceEffect": True}
    # ── Hand Composition Effects ──
    if effectName == "full_roster":
        return {"rewardType": "mult", "rewardValue": round(1 + (1.575 + rn * 0.033) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "all_in":
        # Bet Big: FPx scales with FP over the (position-aware) stud line, set in
        # buildEffectConfig. perFPx = FPx delta per FP past the line; capped so a freak
        # week can't run away. studLine itself is injected per-position at mint.
        _perFPx = round((0.05 + rn * 0.0015) * editionScale * _BAL_FPX_MULT, 3)
        return {"rewardType": "mult",
                "perFPx": _perFPx,               # full precision for scoring math
                "perFPxShown": round(_perFPx, 2),  # display copy (2-decimal cap)
                "maxXBonus": round((1.4 + rn * 0.02) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "diversified":
        return {"rewardType": "fp", "perTypeFP": round((63.0 + rn * 1.5) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "gold_rush":
        # Floobits output — leave untouched
        return {"rewardType": "floobits", "perCardFloobits": int(round((6 + rn * 0.3) * editionScale))}
    if effectName == "stacked_deck":
        # Exponential by design ("multiply the multipliers"), but the old
        # perCardMult (~0.24 @ r75) gave +136% on a full 4-FPx hand, which made
        # "stack every multiplier" the dominant meta. Pulled down to ~0.17 so a
        # 4-FPx hand lands ~+85% — still a strong diamond, no longer auto-win.
        return {"perCardMult": round((0.225 + rn * 0.0075) * editionScale * _BAL_FPX_MULT, 2)}
    # ── Trigger-Chain Effects (second pass) ──
    if effectName == "copycat":
        return {"rewardType": "fp", "_noParams": True}
    if effectName == "chain_reaction":
        return {"rewardType": "mult", "perCardXMult": round((0.168 + rn * 0.0084) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "bonus_round":
        return {"rewardType": "fp", "rewardValue": round((81 + rn * 3.39) * editionScale * _BAL_FP_MULT, 1)}
    # ── Chance Synergy Effects (second pass) ──
    if effectName == "high_roller":
        return {"rewardType": "mult", "perCardMult": round((0.63 + rn * 0.021) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "charmed":
        # FP per chance card that triggered this week.
        return {"rewardType": "fp", "perTriggerFP": round((33.0 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1)}
    # ── Diamond stat amplifiers — no own output, applied via pre-pass ──
    if effectName == "doubler":
        return {"isAmplifier": True, "tdMult": 2.0}
    if effectName == "surveyor":
        return {"isAmplifier": True, "yardMult": 1.5}
    if effectName == "sharpshooter":
        return {"isAmplifier": True, "fgMult": 2.0}
    # ── Streak Synergy Effects (second pass) ──
    if effectName == "fortitude":
        return {"rewardType": "mult", "perCardMult": round((0.63 + rn * 0.021) * editionScale * _BAL_FPX_MULT, 2)}
    # ── Tradeoff Effects (second pass) ──
    if effectName == "double_down":
        # Lemons — multiplies the lowest FP card. Structural amp, not dialed.
        return {"rewardType": "mult", "rewardValue": min(4.0, round(2.0 + (0.50 + rn * 0.02) * editionScale, 2))}
    if effectName == "last_resort":
        return {"rewardType": "fp", "baseFP": round(105.0 * editionScale * _BAL_FP_MULT, 1),
                "enhancedFP": round((135 + rn * 2.70) * editionScale * _BAL_FP_MULT, 1),
                "isChanceEffect": True}
    # ── New cards (FP/FPx rebalance) ──
    if effectName == "anthem":
        # Builder values halved again (next-season tightening): Anthem's
        # raw outputs after the Balatro 0.5 pullback still produced 90+ FP
        # at tier 3, which dwarfed peer holos (Loyalty caps ~72 FP,
        # Showoff ~75). Prismatic rarity warrants a premium but not 2-3×
        # the holo ceiling.
        return {"rewardType": "fp",
                "tier3FP": round((75 + rn * 2.00) * editionScale * _BAL_FP_MULT, 1),
                "tier4FP": round((108 + rn * 2.70) * editionScale * _BAL_FP_MULT, 1),
                "tier5FP": round((162 + rn * 3.40) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "conductor":
        # Structural amplifier — left at 20% (multiplies already-rebalanced
        # FP outputs, so its absolute contribution scales with them).
        return {"rewardType": "mult",
                "boostPct": int(round(20 + rn * 0.2)),
                "isAmplifier": True}
    if effectName == "captain":
        # Diamond overshoot amplifier (2026-07): boosts each other card's output by
        # perOvershootPct per FP its player scores OVER their power bar, capped at +100%
        # (2x) in _applyCaptainBoost. Balance value is a starting point — simcheck.
        pct = round((0.02 + rn * 0.0004) * editionScale, 4)
        return {"rewardType": "mult", "perOvershootPct": pct,
                "perOvershootShown": round(pct * 100, 1),
                "isAmplifier": True, "isCaptain": True}
    return None


# ─── Stat Ladder: measured per-game volumes ─────────────────────────────────
# The denominator every ladder rate is sized against. Measured per position on a fresh
# sim (see docs/CARD_STAT_LADDER.md). Position-keyed because the SAME mechanic on two
# positions needs two rates — a TE catches 8.2 balls a game to a WR's 9.4, which is
# exactly the drift that left Safety Blanket paying 5.3/reception and Possession 2.7.
_LADDER_VOLUMES = {
    "recYards":  {3: 83.5, 4: 59.0},
    "puntsIn20": {5: 2.03},
    "recTds":    {3: 0.40, 4: 0.26},
    "receptions": {3: 9.35, 4: 8.22},
    "fgMade":    {5: 1.98},
    "goodThrows": {1: 13.4},   # GOOD_THROW_THRESHOLD 76 -> 35% of throws
    "passYards": {1: 229.9},
    "completions": {1: 27.7},
    "carries":   {2: 25.9},
    "rushYards": {2: 110.5},
    "rushTds":   {2: 0.69},
    "yac":       {3: 23.0, 4: 17.6},
    "yac2":      {2: 87.5},   # yards after contact (RB), distinct from receiving YAC
    # QBs throw ~1 TD a game, so unlike receiving TDs this is not a rare event: 43% of
    # QB games are scoreless but 29% are multi-TD. Measured over 736 QB games.
    "passTds":   {1: 1.02},
    # ⚠️ RE-MEASURED after the target-counting fix (12.3 WR / 11.0 TE over 24 games,
    # was 9.9 / 8.7). A target used to be booked only on a catch or a drop, so an
    # incompletion never reached the receiver's line and this table — which sizes
    # Attention's rate — was reading about 24% light. Left alone, the card would have
    # quietly paid a quarter more than its rung.
    "targets":   {3: 12.3, 4: 11.0},
    # Return yards go to whichever skill player returns; ~2.5 returns a game at ~9 yards.
    "returnYards": {2: 23.0, 3: 23.0},
    # Rare one-off events, used as the BONUS half of a base+bonus card.
    "bigRuns":   {2: 0.88},
    "bigThrows": {1: 1.75},
    "contested": {3: 1.02, 4: 0.98},
    "bailouts":  {3: 0.31, 4: 0.25},
    "brokenTackles": {2: 0.64},
}
# A metallic flat card should mean this much FP in a typical week (Freebie measures 26.0).
_LADDER_FP_ANCHOR = 26.0
# An FPx card should deliver about this much on a typical week. Cannot go far below it:
# multFactors are appended as round(mult, 2), so the delta is quantised to 0.01 and a
# card under ~+0.05 has too few steps left to tune with.
_LADDER_FPX_TARGET = 0.10


# A streak bar means "showed up", NOT "had a good week". Set above the mean it gives a
# hold rate near 30% and an average run under one week, so the streak never builds and the
# card loses to its own metallic sibling over a season (measured 0.17-0.49x before this).
# At 0.75x the mean the hold rate lands near 75%, which is an average run of ~3 weeks.
_STREAK_BAR_RATIO = 0.75

# Per-stat override. A single ratio does not work because the stats differ in SPREAD, not
# just level: at 0.75x the mean, carries held 80% of weeks and YAC only 56%, and season
# value tracks hold rate almost exactly (corr 0.87 across the ten cards). A spiky stat
# needs a lower bar to reach the same hold rate. Tuned against simcheck_streak_replay.py
# toward ~1.10x the metallic sibling's season total.
_STREAK_BAR_OVERRIDES = {
    "carries": 0.92,       # 80% hold -> too generous
    "completions": 0.90,   # 78%
    "passYards": 0.90,     # 74%
    "recYards": 0.56,      # tuned to ~1.1x
    "receptions": 0.66,    # 70% but a low per-unit rate
    "rushYards": 0.70,     # 62%
    "yac2": 0.70,          # 61%
    "yac": 0.40,           # the spikiest of the set, so the lowest bar
        # Only ~2 pins a game, and the bar is an INTEGER, so the sole options are 1 or 2.
    # 0.45 and 0.70 both round to 1 and held 84%; 0.85 rounds to 2.
    "puntsIn20": 0.85,
}


def _streakBar(stat, position, fallback):
    """The bar a streak card's condition checks, derived from the position's own volume."""
    vol = (_LADDER_VOLUMES.get(stat) or {}).get(position or 0, fallback)
    ratio = _STREAK_BAR_OVERRIDES.get(stat, _STREAK_BAR_RATIO)
    return max(1, int(round(vol * ratio)))


def _ladderVolume(stat, position, fallback):
    """Per-game volume for a stat at a position, for rate sizing at mint."""
    return (_LADDER_VOLUMES.get(stat) or {}).get(position or 0, fallback)


def _ladderFpRate(stat, position, fallback, ratingScale=0.0, rn=0.0):
    """Flat FP per unit, sized so a typical week lands on the anchor.

    Precision scales with MAGNITUDE. A rate is user-facing text, and "13.935 FP per punt
    downed inside the 20" reads as a bug even though it is arithmetically fine — three
    decimals is noise on a big per-unit number. A per-yard rate genuinely needs them,
    because 0.34 and 0.339 are meaningfully different across 100 yards.
    """
    vol = _ladderVolume(stat, position, fallback)
    val = (_LADDER_FP_ANCHOR / vol) * (1 + ratingScale * rn)
    if val >= 10:
        return round(val, 1)
    if val >= 1:
        return round(val, 2)
    return round(val, 3)


def _ladderFpxRate(stat, position, fallback, unit=1):
    """FPx per `unit` of a stat, sized so a typical week lands on the FPx target.

    Rounded to 2dp because that is the resolution the calculator stores and aggregates
    at; `unit` exists so the stored value does not round to 0.00 on a high-volume stat.
    """
    vol = _ladderVolume(stat, position, fallback)
    return round(_LADDER_FPX_TARGET / vol * unit, 2)


def _buildFlatFPParams(effectName, playerRating, editionScale, position=None):
    """Flat-FP card parameter builder.

    Numeric constants represent the post-Balatro (3×) values; `_BAL_FP_MULT`
    at the top of the file dials them back at build time.
    """
    rn = playerRating - 60

    # ── Stat ladder: metallic flat rungs ──
    if effectName == "cadence":
        return {"perCompletionFP": _ladderFpRate("completions", position, 27.7, 0.004, rn)}
    if effectName == "runback":
        return {"perYardFP": _ladderFpRate("returnYards", position, 23.0, 0.004, rn)}
    if effectName == "house_call":
        # Return TDs run ~3 per 100 games, so the jackpot contributes almost nothing in
        # EV and the base has to carry the card. The TD is the drama, not the value.
        return {"perYardFP": round(_ladderFpRate("returnYards", position, 23.0) * 0.85, 3),
                "bonusFP": round(_LADDER_FP_ANCHOR * 2.2, 1), "isChanceEffect": True}
    if effectName == "altitude":
        # League aDOT is ~6.8. A bar AT the mean pays nothing on a typical week and only
        # ~12 FP at p90, so it sits below it and the rate carries the anchor: a typical
        # passer clears it by ~1.3 yards, a deep thrower by ~2.7.
        bar = 5.5
        return {"perYardFP": round(_LADDER_FP_ANCHOR / (6.79 - bar), 1), "threshold": bar}
    # ── base + bonus one-offs: a floor on the parent stat, the rare event as the kicker ──
    if effectName == "haymaker":
        return {"perYardFP": round(_LADDER_FP_ANCHOR * 0.60 / _ladderVolume("passYards", position, 229.9), 3),
                "bonusFP": round(_LADDER_FP_ANCHOR * 0.40 / _ladderVolume("bigThrows", position, 1.75), 1)}
    if effectName == "breakaway":
        return {"perYardFP": round(_LADDER_FP_ANCHOR * 0.60 / _ladderVolume("rushYards", position, 110.5), 3),
                "bonusFP": round(_LADDER_FP_ANCHOR * 0.40 / _ladderVolume("bigRuns", position, 0.88), 1)}
    if effectName == "highpoint":
        return {"perReceptionFP": round(_LADDER_FP_ANCHOR * 0.60 / _ladderVolume("receptions", position, 9.35), 2),
                "bonusFP": round(_LADDER_FP_ANCHOR * 0.40 / _ladderVolume("contested", position, 1.02), 1)}
    if effectName == "custodian":
        return {"perReceptionFP": round(_LADDER_FP_ANCHOR * 0.60 / _ladderVolume("receptions", position, 9.35), 2),
                "bonusFP": round(_LADDER_FP_ANCHOR * 0.40 / _ladderVolume("bailouts", position, 0.31), 1)}
    if effectName == "houdini":
        # Same problem as promised_land: 0.47x alone, 0.79x fully built.
        return {"perYardFP": round(_LADDER_FP_ANCHOR * 0.70 / _ladderVolume("rushYards", position, 110.5), 3),
                "bonusFP": round(_LADDER_FP_ANCHOR * 2.2, 1), "isChanceEffect": True}
    if effectName == "updraft":
        vol = _ladderVolume("passYards", position, 229.9)
        return {"perYardFP": round(_LADDER_FP_ANCHOR / vol, 3),
                "gateFP": round(_LADDER_FP_ANCHOR * 0.35, 1),
                "gates": [int(round(vol * m)) for m in (1.3, 1.7, 2.1)]}
    if effectName == "frontier":
        return {"perYardFP": _ladderFpRate("recYards", position, 83.5, 0.004, rn)}
    if effectName == "freight":
        return {"perYardFP": _ladderFpRate("yac2", position, 87.5, 0.004, rn)}
    if effectName == "pinpoint":
        return {"perPuntFP": _ladderFpRate("puntsIn20", position, 2.03, 0.004, rn)}
    # ── Stat ladder: holographic / prismatic FP rungs ──
    if effectName == "end_zone":
        # Pays the metallic rate on every TD, with a bonus once a second one lands.
        vol = _ladderVolume("recTds", position, 0.40)
        return {"perTdFP": round(_LADDER_FP_ANCHOR / vol * 0.62, 1),
                "bonusFP": round(_LADDER_FP_ANCHOR * 0.55, 1), "threshold": 2}
    if effectName == "promised_land":
        # Measured at 0.47x its metallic sibling alone and 0.60x at full hand synergy —
        # a build-around that loses even when you build around it. Base and jackpot both
        # raised, and the opening odds lowered so the HAND has more room to move them.
        vol = _ladderVolume("recTds", position, 0.40)
        return {"perTdFP": round(_LADDER_FP_ANCHOR / vol * 0.70, 1),
                "bonusFP": round(_LADDER_FP_ANCHOR * 2.4, 1),
                "baseChance": 14, "chanceStep": 12, "isChanceEffect": True}
    if effectName == "salvo":
        # Measured 15.7 FP/week against End Zone's 15.0 — the 0.55 coefficient is lower
        # than End Zone's 0.62 precisely because pass TDs are ~3x more common.
        vol = _ladderVolume("passTds", position, 1.02)
        return {"perTdFP": round(_LADDER_FP_ANCHOR / vol * 0.55, 1),
                "bonusFP": round(_LADDER_FP_ANCHOR * 0.55, 1), "threshold": 3}
    if effectName == "barrage":
        # 19.5 FP/week against Promised Land's 19.4, but with 40% of the payout in the
        # jackpot rather than 18% — more rolls at longer odds, which is the shape a
        # prismatic chance card should have.
        vol = _ladderVolume("passTds", position, 1.02)
        return {"perTdFP": round(_LADDER_FP_ANCHOR / vol * 0.45, 1),
                "bonusFP": round(_LADDER_FP_ANCHOR * 2.75, 1),
                "baseChance": 8, "chanceStep": 6, "isChanceEffect": True}
    if effectName == "freebie":
        return {"baseFP": round((48 + rn * 1.02) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "entourage":
        return {"perPlayerFP": round((8.1 + rn * 0.27) * editionScale * _BAL_FP_MULT, 1), "minStars": 3}
    if effectName == "touchdown_pinata":
        return {"perTdFP": round((6.75 + rn * 0.21) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "scrappy":
        return {"baseFP": round(105.0 * editionScale * _BAL_FP_MULT, 1),
                "enhancedFP": round((120 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1),
                "maxStars": 2, "isChanceEffect": True}
    if effectName == "rng":
        return {"minFP": round((21 + rn * 0.42) * editionScale * _BAL_FP_MULT, 1),
                "maxFP": round((93 + rn * 1.68) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "avalanche":
        return {"td1": round((4.7 + rn * 0.19) * editionScale * _BAL_FP_MULT, 1),
                "td2": round((9.5 + rn * 0.38) * editionScale * _BAL_FP_MULT, 1),
                "td3": round((16.8 + rn * 0.66) * editionScale * _BAL_FP_MULT, 1),
                "td4": round((26.0 + rn * 1.05) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "hedge":
        # Single-player FP floor (fusion rebase): tops the depicted player's weekly FP
        # up to this floor on a quiet game, pays nothing when they clear it. Rating-scaled
        # (a better player floors a touch higher); key must be floorSoloFP to match both
        # the detail template and _computeHedge.
        return {"floorSoloFP": round(11 + rn * 0.14, 1)}
    if effectName == "honor_roll":
        # FPx when THIS player clears the bar, growing from there to double it.
        #
        # ⚠️ `baseMult` IS THE PAYOUT AT THE BAR, and it exists because the ramp used to
        # start at zero: a card could read ACTIVE, with a full green bar, and pay
        # +0.00 FPx at the exact point it switched on. Clearing the bar now earns
        # HONOR_ROLL_BASE_SHARE of the maximum, and beating it earns the rest.
        #
        # `perPlayerMult` was dropped with the rebase: it paid per qualifying ROSTER
        # player and _computeHonorRoll has not read it since. Cards minted before that
        # keep the dead key, which is harmless since no detail template referenced it.
        _maxDelta = (0.42 + rn * 0.014) * editionScale * _BAL_FPX_MULT
        return {"rewardType": "mult",
                "baseMult": round(1 + _maxDelta * HONOR_ROLL_BASE_SHARE, 2),
                "maxMult": round(1 + _maxDelta, 2),
                "fpThreshold": 15}
    if effectName == "three_pointer":
        # Measured 39.0 FP/week, second highest at metallic, off only 1.98 FGs a game.
        # Sized from the volume table like the rest of the flat rungs.
        return {"perFgFP": _ladderFpRate("fgMade", position, 1.98, 0.004, rn)}
    if effectName == "garbage_time":
        return {"perPlayerFP": round((13.5 + rn * 0.54) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "loyalty_bonus":
        # NOTE: read ~6 only because the projection ctx's favoriteTeamStreak was
        # low/negative; with a representative 4-win streak it already pays ~70
        # (holo band). The low number was a measurement blind spot, not weakness.
        return {"perStreakFP": round((20.4 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "windfall":
        # Windfall outputs floobits, not FP — leave untouched.
        return {"perPlayerFloobits": round((5 + rn * 0.20) * editionScale)}
    if effectName == "spotlight_moment":
        return {"rewardType": "fp", "rewardValue": round((54 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "ace_up_the_sleeve":
        return {"rewardType": "fp",
                "baseFP": round((21 + rn * 0.69) * editionScale * _BAL_FP_MULT, 1),
                "rewardValue": round((42 + rn * 1.50) * editionScale * _BAL_FP_MULT, 1),
                "stat": "recYards", "threshold": 125}
    if effectName == "possession":
        # Sized from the volume table, same as safety_blanket. These two are the SAME
        # mechanic on two positions and drifted to 2.47 and 5.5 FP per reception against
        # volumes of 9.35 and 8.22 a game — the TE card paid 96% more per catch for 12%
        # less volume and measured 47.0 FP/week, the highest of any metallic card.
        return {"perReceptionFP": _ladderFpRate("receptions", position, 9.35, 0.004, rn)}
    if effectName == "slippery":
        # perYacFP is per TEN yards (see _computeSlippery), so 1.21 paid 2.8 FP against
        # the 26 anchor — the most under-tuned card in the tier.
        return {"perYacFP": round(_ladderFpRate("yac", position, 23.0, 0.004, rn) * 10, 2)}
    if effectName == "__retired_slippery":
        return {"perYacFP": round((1.02 + rn * 0.054) * editionScale * _BAL_FP_MULT, 2)}
    if effectName == "jailbreak":
        return {"rewardType": "fp",
                "baseFP": round((15 + rn * 0.5) * editionScale * _BAL_FP_MULT, 1),
                "rewardValue": round((35 + rn * 1.2) * editionScale * _BAL_FP_MULT, 1),
                "threshold": 30}
    if effectName == "expedition":
        # Paid 7.5 per 50 yards against a 110.5-yard mean, i.e. 16.6 FP against the 26
        # anchor. Routed through the volume table like the rest.
        return {"perFiftyYardsFP": round(_ladderFpRate("rushYards", position, 110.5, 0.004, rn) * 50, 2)}
    if effectName == "__retired_expedition":
        return {"perFiftyYardsFP": round((6.6 + rn * 0.32) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "homer":
        # FPx delta per fav-team player on roster.
        return {"rewardType": "mult",
                "perPlayerMult": round((0.105 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (0.42 + rn * 0.014) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "gone_streaking":
        return {"baseFP": round((13.5 + rn * 0.54) * editionScale * _BAL_FP_MULT, 1),
                "perStreakFP": round((5.4 + rn * 0.27) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "safety_blanket":
        # See possession — one rate source for both, so the TE and WR prints stay in step.
        return {"rewardType": "fp",
                "perReceptionFP": _ladderFpRate("receptions", position, 8.22, 0.004, rn)}
    if effectName == "lead_blocker":
        return {"rewardType": "fp", "perTdFP": round((43.0 + rn * 2.16) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "sniper":
        return {"perFgFP": round((20.4 + rn * 0.69) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "range":
        # FP per yard of FG kicked by the roster K this week.
        return {"perYardFP": round((0.27 + rn * 0.012) * editionScale * _BAL_FP_MULT, 2)}
    if effectName == "loyalty":
        # FP per first-save roster player still on roster.
        return {"perPlayerFP": round((15.0 + rn * 0.42) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "squire":
        return {"perTdFP": round((27 + rn * 1.02) * editionScale * _BAL_FP_MULT, 1)}
    # ── Escalating chance: Crescendo (TD/FG triggers, escalating per miss)
    if effectName == "crescendo":
        # Measured at a 1.04x build gain — it barely responded to hand synergy despite
        # being a chance card, because a 12.5 guaranteed floor dwarfed a 15.5 jackpot.
        # Doubling the trigger rate moved the season 4%. It also ran ~0.50x a metallic
        # sibling, so it needed BOTH more total value and more of that value in the
        # jackpot. Split solved against the measured trigger rates (22% alone, 31% mid,
        # 38% fully built) for a ~1.5x build gain at the prismatic band.
        return {"baseFP": round(_LADDER_FP_ANCHOR * 0.32, 1),
                "bonusFP": round(_LADDER_FP_ANCHOR * 3.1, 1),
                "baseChance": 15, "chanceStep": 12,
                "isChanceEffect": True}
    # ── Yardage chance: Traverse (end-of-game roll scaled by yards)
    if effectName == "traverse":
        return {"baseFP": round((27.0 + rn * 0.42) * editionScale * _BAL_FP_MULT, 1),
                "bonusFP": round((102.0 + rn * 3.39) * editionScale * _BAL_FP_MULT, 1),
                "baseChance": 2, "chancePerStep": 5, "yardStep": 50, "yardType": "passing",
                "isChanceEffect": True}
    # ── Meta: Advantage (no direct payout)
    if effectName == "advantage":
        return {"isAdvantage": True, "rollCount": 2}
    # ── Strategy-Warping: Opulence (FP per Floobits balance)
    if effectName == "fat_cat":
        floobitsPerFP = max(1, int(round((3 - rn * 0.02) / editionScale)))
        maxFP = int(round((61 + rn * 2.0) * editionScale * _BAL_FP_MULT))
        return {"floobitsPerFP": floobitsPerFP, "maxFP": maxFP}
    if effectName == "alchemy":
        return {"perFgBonusFP": round((40.5 + rn * 1.35) * editionScale * _BAL_FP_MULT, 1)}
    # ── FPx card — closer (Q4 multiplier). Stored as full mult; only the
    # delta portion (over 1.0) is scaled by the Balatro dial.
    if effectName == "closer":
        return {"q4MultFactor": round(1 + (1.05 + rn * 0.063) * editionScale * _BAL_FPX_MULT, 2)}
    # ── Roster-trait flat FP cards
    if effectName == "castaway":
        return {"rewardFP": round((66.0 + rn * 1.9) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "sleeper":
        return {"baseFP": round((105.0 + rn * 2.0) * editionScale * _BAL_FP_MULT, 1),
                "enhancedFP": round((150.0 + rn * 2.40) * editionScale * _BAL_FP_MULT, 1),
                "baseChance": 15, "chancePerLow": 12,
                "isChanceEffect": True}
    if effectName == "patient":
        return {"baseFP": round((10.2 + rn * 0.27) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "rookie_hype":
        # Per-rookie flat FP. Calibrated (against the dampened rating rn) to ~8.0
        # at a mid holo rating, ranging ~7.9-8.1. Deliberately generous for the
        # tier — rookies are usually weak, low-FP players, so a strong per-rookie
        # payout is what makes rostering them worthwhile. Old constant (75 + rn*2)
        # produced a broken ~40-57/rookie. Uncapped by design (a rare rookie stack
        # overshooting the holo ceiling makes up for weak base production).
        return {"perRookieFP": round((13.7 + rn * 0.27) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "wanderer":
        return {"perTeamFP": round((12.9 + rn * 0.34) * editionScale * _BAL_FP_MULT, 1)}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"baseFP": round(13.5 * editionScale * _BAL_FP_MULT, 1)}


def _buildMultiplierParams(effectName, playerRating, editionScale, position=None):
    """FPx param builder. See `_buildFlatFPParams` for the Balatro dial note."""
    rn = playerRating - 60
    # ── Stat ladder: FPx rungs ──
    if effectName == "rhythm":
        vol = _ladderVolume("completions", position, 27.7)
        return {"rewardType": "mult",
                "per25Mult": _ladderFpxRate("completions", position, 27.7, 25),
                "bonusMult": round(_LADDER_FPX_TARGET * 0.55, 2),
                "threshold": int(round(vol * 1.3))}
    if effectName == "clockwork":
        vol = _ladderVolume("completions", position, 27.7)
        return {"rewardType": "mult",
                "per25Mult": round(_ladderFpxRate("completions", position, 27.7, 25) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": int(round(vol * 1.15)), "isStreak": True}
    if effectName == "beast_of_burden":
        vol = _ladderVolume("carries", position, 25.9)
        return {"rewardType": "mult",
                "per25Mult": _ladderFpxRate("carries", position, 25.9, 25),
                "bonusMult": round(_LADDER_FPX_TARGET * 0.55, 2),
                "threshold": int(round(vol * 1.3))}
    if effectName == "iron_man":
        vol = _ladderVolume("carries", position, 25.9)
        return {"rewardType": "mult",
                "per25Mult": round(_ladderFpxRate("carries", position, 25.9, 25) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": int(round(vol * 1.15)), "isStreak": True}
    if effectName == "odyssey":
        return {"rewardType": "mult",
                "per50Mult": round(_ladderFpxRate("rushYards", position, 110.5, 50) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": 100, "isStreak": True}
    if effectName == "battering_ram":
        # See paydirt — same per-event sizing, and a cap so a three-TD game cannot run away.
        return {"rewardType": "mult",
                "perTdMult": _LADDER_FPX_TARGET * 1.2,
                "maxMult": round(_LADDER_FPX_TARGET * 3.0, 2)}
    if effectName == "custody":
        vol = _ladderVolume("receptions", position, 9.35)
        return {"rewardType": "mult",
                "per5Mult": _ladderFpxRate("receptions", position, 9.35, 5),
                "bonusMult": round(_LADDER_FPX_TARGET * 0.55, 2),
                "threshold": int(round(vol * 1.4))}
    if effectName == "tenure":
        vol = _ladderVolume("receptions", position, 9.35)
        return {"rewardType": "mult",
                "per5Mult": round(_ladderFpxRate("receptions", position, 9.35, 5) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": int(round(vol * 1.15)), "isStreak": True}
    if effectName == "getaway":
        vol = _ladderVolume("yac", position, 23.0)
        return {"rewardType": "mult",
                "per10Mult": round(_ladderFpxRate("yac", position, 23.0, 10) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": int(round(vol * 1.7)), "isStreak": True}
    if effectName == "attention":
        return {"rewardType": "mult",
                "per5Mult": _ladderFpxRate("targets", position, 9.9, 5)}
    if effectName == "slipstream":
        return {"rewardType": "mult",
                "per100Mult": _ladderFpxRate("passYards", position, 229.9, 100)}
    if effectName == "stratosphere":
        vol = _ladderVolume("passYards", position, 229.9)
        return {"rewardType": "mult",
                "per100Mult": round(_ladderFpxRate("passYards", position, 229.9, 100) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": int(round(vol * 1.3)), "isStreak": True}
    if effectName == "marksman":
        return {"rewardType": "mult",
                "per5Mult": _ladderFpxRate("goodThrows", position, 13.4, 5),
                "cleanSheetMult": round(_LADDER_FPX_TARGET * 0.65, 2)}
    if effectName == "dead_eye":
        return {"rewardType": "mult",
                "per5Mult": round(_ladderFpxRate("goodThrows", position, 13.4, 5) * 0.85, 2),
                "growthPerTick": 0.03, "isStreak": True}
    if effectName == "territory":
        # Gates must sit ABOVE a typical week or the bonus is not conditional at all.
        # Derived from this position's own mean: 1.2x / 1.7x / 2.3x.
        vol = _ladderVolume("recYards", position, 83.5)
        return {"rewardType": "mult",
                "per50Mult": _ladderFpxRate("recYards", position, 83.5, 50),
                "gateMult": round(_LADDER_FPX_TARGET * 0.55, 2),
                "gates": [int(round(vol * m)) for m in (1.2, 1.7, 2.3)]}
    if effectName == "dominion":
        return {"rewardType": "mult",
                "per50Mult": round(_ladderFpxRate("recYards", position, 83.5, 50) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": 100, "isStreak": True}
    if effectName == "grinder":
        # Contact yards are ~80% of rush yards league-wide, so "over half" is the norm,
        # not an achievement. The bar sits above it.
        return {"rewardType": "mult",
                "per50Mult": _ladderFpxRate("yac2", position, 87.5, 50),
                "ratioMult": round(_LADDER_FPX_TARGET * 0.60, 2),
                "ratioBar": 0.88}
    if effectName == "landslide":
        return {"rewardType": "mult",
                "per50Mult": round(_ladderFpxRate("yac2", position, 87.5, 50) * 0.85, 2),
                "growthPerTick": 0.03, "threshold": 100, "isStreak": True}
    if effectName == "coffin_corner":
        # ~1 punt a week is downed inside the 10, so paying per inside-10 punt fires every
        # week. The bonus needs MORE than one.
        return {"rewardType": "mult",
                "perPuntMult": _ladderFpxRate("puntsIn20", position, 2.03),
                "bonusMult": round(_LADDER_FPX_TARGET * 0.70, 2), "deepBar": 2}
    if effectName == "undertaker":
        # The streak bar is an integer on a ~2-per-game stat, so it can only be 1 or 2:
        # at 1 the card ran 1.50x its sibling over a season, at 2 it ran 0.88x, with
        # nothing in between. With the bar quantised, the RATE is the only continuous
        # lever, so the growth carries the difference.
        return {"rewardType": "mult",
                "perPuntMult": round(_ladderFpxRate("puntsIn20", position, 2.03) * 0.85, 2),
                "growthPerTick": 0.05,
                "threshold": _streakBar("puntsIn20", position, 2.03), "isStreak": True}
    if effectName == "bombardier":
        # Unlike Paydirt this CAN be sized off the target, because ~1 TD a game is a
        # number QBs actually post. Rate x volume lands the mean on the FPx target and the
        # cap bites at three TDs, which happens in 10.5% of QB games.
        return {"rewardType": "mult",
                "perTdMult": _LADDER_FPX_TARGET,
                "maxMult": round(_LADDER_FPX_TARGET * 3.0, 2)}
    if effectName == "paydirt":
        # ⚠️ Size per SCORING EVENT, not per mean. Sizing an FPx rate off a 0.26 TD/game
        # average produced 0.38 per TD, because the maths assumes you can receive 0.26 of a
        # touchdown. You cannot — you get 0, 1 or 2, so the card paid nothing most weeks and
        # +0.76 FPx on a 2-TD week, which is ~190 FP on a normal lineup against a 26 FP
        # anchor. Lumpy stats take FPx to smooth their DEAD weeks (rule 2); that does not
        # license pricing the live ones off an average nobody ever posts.
        return {"rewardType": "mult",
                "perTdMult": _LADDER_FPX_TARGET * 1.2,
                "maxMult": round(_LADDER_FPX_TARGET * 3.0, 2)}
    """FPx (multiplier) card parameter builder.

    Numeric constants represent the post-Balatro (3×) deltas; `_BAL_FPX_MULT`
    (and `_BAL_FP_MULT` for the FP-output cards routed here) at the top of
    the file dials them back at build time.
    """
    rn = playerRating - 60

    # ── FPx effects (delta-based, wrapped as 1+val in compute) ──
    if effectName == "cornucopia":
        return {"perTdMult": round((0.84 + rn * 0.012) * editionScale * _BAL_FPX_MULT, 2)}
    # ── FP-output cards from inside this builder ──
    if effectName == "babysitter":
        return {"baseFP": round(120.0 * editionScale * _BAL_FP_MULT, 1),
                "enhancedFP": round((120 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1),
                "fpThreshold": 8, "isChanceEffect": True}
    if effectName == "martyr":
        return {"baseFP": round(33.0 * editionScale * _BAL_FP_MULT, 1),
                "enhancedFP": round((120 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1),
                "isChanceEffect": True}
    if effectName == "resplendent":
        return {"perPlayerFP": round((10.2 + rn * 0.33) * editionScale * _BAL_FP_MULT, 1)}
    # ── FPx effects (factor-based, values > 1) ──
    if effectName == "big_deal":
        return {"xMultValue": round(1 + (playerRating / 100) * 0.252 * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "snake_eyes":
        # Tiered FPx. Stored as full multipliers; only the delta (over 1.0)
        # is scaled by the Balatro dial.
        _se = lambda m: round(1 + (m - 1.0) * _BAL_FPX_MULT, 2)
        return {"tiers": [(0, _se(2.50)), (4, _se(2.05)), (9, _se(1.70)), (14, _se(1.40)), (19, _se(1.15))],
                "minMult": 1.0}
    if effectName == "luminary":
        return {"fpShareScale": round((0.54 + rn * 0.024) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "juggernaut":
        return {"baseXMult": round(1 + (0.105 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2),
                "growthPerWin": round((0.54 + rn * 0.012) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "underdog":
        return {"baseFP": round(90.0 * editionScale * _BAL_FP_MULT, 1),
                "enhancedFP": round((120 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1),
                "isChanceEffect": True}
    if effectName == "stockpiler":
        # NOTE: looked weak (~29) only because the projection ctx left unusedSwaps
        # unread; with condition active it already pays ~70 (prismatic band) at 4
        # hoarded swaps. Left at original value.
        return {"perSwapXMult": round((0.084 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "hometown_hero":
        # Floobits output — left alone
        return {"rewardFloobits": int(round((15 + rn * 0.6) * editionScale))}
    if effectName == "providence":
        # chanceBonus is a probability bump — not scaled by FP/FPx dials.
        # Buff pass: base mult was only +5%, leaving it weak in any hand without
        # several chance cards. Raised to +15% so it carries its own weight.
        return {"baseMult": round(1 + 0.30 * editionScale * _BAL_FPX_MULT, 2),
                "chanceBonus": round(0.12 * editionScale, 2),
                "chanceBonusPct": int(round(0.12 * editionScale * 100)),
                "isChanceAmplifier": True}
    if effectName == "house_money":
        return {"baseFP": round((21 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1),
                "perUpsetFP": round((21 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "rising_tide":
        return {"perPlayerMult": round((0.084 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (0.84 + rn * 0.021) * editionScale * _BAL_FPX_MULT, 2)}
    # ── Fusion additions (2026-07). Balance values are starting points — simcheck before locking. ──
    if effectName == "no_passengers":
        # Holo: FPx that scales with the roster's LOWEST weekly FP (reward depth), capped.
        return {"rewardType": "mult",
                "perFloorFP": round((0.055 + rn * 0.0018) * editionScale * _BAL_FPX_MULT, 3),
                "maxDelta": round((0.6 + rn * 0.02) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "franchise":
        # Prismatic: conditional boom FPx when the depicted player is the roster's top scorer.
        return {"rewardType": "mult",
                "topScorerDelta": round((0.9 + rn * 0.03) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "trebuchet":
        return {"rewardType": "fp",
                "baseFP": round((21 + rn * 0.69) * editionScale * _BAL_FP_MULT, 1),
                "rewardValue": round((54 + rn * 2.34) * editionScale * _BAL_FP_MULT, 1),
                "threshold": 25}
    if effectName == "double_trouble":
        return {"rewardType": "fp",
                "singleWrFP": round((15.0 + rn * 0.62) * editionScale * _BAL_FP_MULT, 1),
                "rewardValue": round((35.0 + rn * 1.38) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "gunslinger":
        # RE-POINTED from pass yards to throw quality (docs/CARD_STAT_LADDER.md). The name
        # read as marksmanship while the card measured yardage; it now sits on the stat it
        # describes. Pass yards moved to Slipstream. Needs GOOD_THROW_THRESHOLD's counter.
        return {"rewardType": "fp",
                "perGoodThrowFP": _ladderFpRate("goodThrows", position, 13.4, 0.004, rn)}
    if effectName == "air_raid":
        # Floobits output — left alone
        return {"rewardType": "floobits", "perTdFloobits": int(round((6 + rn * 0.3) * editionScale))}
    if effectName == "stampede":
        return {"baseMult": round(1 + (0.126 + rn * 0.0063) * editionScale * _BAL_FPX_MULT, 2),
                "enhancedMult": round(1 + (0.378 + rn * 0.0168) * editionScale * _BAL_FPX_MULT, 2),
                "yardThreshold": 75}
    if effectName == "stack":
        return {"rewardValue": round(1 + (0.315 + rn * 0.0168) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "backfield_buddies":
        # NOTE: read ~16 only because the projection ctx left roster team IDs
        # empty (QB+RB same-team never detected). With the condition active it
        # pays ~73 (matching Stack), so it was never weak. Left at original value.
        return {"rewardValue": round((0.315 + rn * 0.0168) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "eminence":
        # FPx delta per roster player ranked top-10 at their position (by
        # season FP/game). Whole-roster scope.
        return {"rewardType": "mult",
                "perPlayerMult": round((0.105 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (0.42 + rn * 0.014) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "home_alone":
        return {"perSlotMult": round((0.252 + rn * 0.0084) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "dark_horse":
        return {"perStarMult": round((0.168 + rn * 0.0063) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "vagabond":
        # Was uncapped (mult = 1 + perSwap × swapsUsed), giving a runaway ~4.6x
        # ceiling for heavy swappers — every comparable FPx card has a maxMult.
        # Added a ~+62% cap so swapping is rewarded without a holo out-scaling
        # prismatic FPx at the tail.
        return {"perSwapXMult": round((0.038 + rn * 0.0013) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (1.0 + rn * 0.0167) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "synergy":
        # FPx delta per pair of roster players from the same team.
        return {"rewardType": "mult",
                "perPairMult": round((0.105 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (0.42 + rn * 0.014) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "vanguard":
        # FPx delta per veteran (5+ seasons played) on roster.
        return {"rewardType": "mult",
                "perVetMult": round((0.105 + rn * 0.0042) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (0.42 + rn * 0.014) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "cornerstone":
        # FPx delta per roster player ranked #1 at their position by season FP/game.
        # Scarcer than Eminence (top-1 vs top-10) so per-player delta is bigger.
        return {"rewardType": "mult",
                "perPlayerMult": round((0.21 + rn * 0.0084) * editionScale * _BAL_FPX_MULT, 2),
                "maxMult": round(1 + (0.84 + rn * 0.028) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "parlay":
        return {"rewardType": "mult",
                "baseXMult": 1.0,
                "coef": round((0.50 + rn * 0.019) * editionScale * _BAL_FPX_MULT, 3),
                "kPoints": 80}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"multPercent": round(0.42 * editionScale * _BAL_FPX_MULT, 1)}


def _buildFloobitsParams(effectName, playerRating, editionScale, position=None):
    rn = playerRating - 60

    if effectName == "allowance":
        return {"floobits": int(round((10 + rn * 0.5) * editionScale))}
    if effectName == "winners_circle":
        # Fusion (2026-07): flat Floobits when the depicted player's real team wins
        # (~50% of weeks). Balance value is a starting point — simcheck before locking.
        return {"rewardType": "floobits", "winFloobits": int(round((12 + rn * 0.5) * editionScale))}
    if effectName == "cha_ching":
        return {"perTdFloobits": int(round((6 + rn * 0.3) * editionScale))}
    if effectName == "piggy_bank":
        return {"fpPercent": int(round((14 + rn * 0.3) * editionScale))}
    if effectName == "good_neighbor":
        return {"baseFloobits": int(round((4 + rn * 0.15) * editionScale)),
                "perMissFloobits": int(round((8 + rn * 0.3) * editionScale))}
    if effectName == "consolation_prize":
        return {"baseFloobits": int(round(8 * editionScale)), "enhancedFloobits": int(round((30 + rn * 0.4) * editionScale)),
                "fpThreshold": 5, "isChanceEffect": True}
    if effectName == "rock_bottom":
        return {"baseFloobits": int(round(8 * editionScale)), "enhancedFloobits": int(round((30 + rn * 0.4) * editionScale)),
                "isChanceEffect": True}
    if effectName == "windfall":
        return {"perPlayerFloobits": int(round((5 + rn * 0.20) * editionScale))}
    if effectName == "buy_low":
        return {"perPlayerFloobits": int(round((4 + rn * 0.2) * editionScale))}
    if effectName == "trust_fund":
        return {"baseFloobits": int(round((4 + rn * 0.2) * editionScale)),
                "growthPerWeek": int(round((2 + rn * 0.1) * editionScale))}
    if effectName == "feeding_frenzy":
        return {"rewardType": "floobits",
                "perTdFloobits": int(round((3 + rn * 0.10) * editionScale)),
                "bonusFloobits": int(round((8 + rn * 0.3) * editionScale)),
                "tdThreshold": 3}
    if effectName == "highlight_reel":
        return {"rewardType": "floobits", "rewardValue": int(round((6 + rn * 0.3) * editionScale)),
                "wpaThreshold": 7.0}
    if effectName == "workhorse":
        return {"rewardType": "fp",
                "perAttemptFP": _ladderFpRate("carries", position, 25.9, 0.004, rn)}
    if effectName == "__retired_workhorse":
        return {"rewardType": "fp", "perAttemptFP": round((0.6 + rn * 0.03) * editionScale, 2)}
    if effectName == "goal_line_vulture":
        return {"perTdFloobits": int(round((8 + rn * 0.4) * editionScale))}
    if effectName == "industrious":
        return {"perReceptionFloobits": int(round((1.5 + rn * 0.06) * editionScale))}
    # ── Strategy-Warping: Prosperity (Floobits payout ceiling raiser)
    if effectName == "surplus":
        flatBonus = int(round((6 + rn * 0.18) * editionScale))
        return {"flatBonus": flatBonus}
    # ── Catalyst: dynamic chance boost from roster FP + small floobits base
    if effectName == "catalyst":
        # Diamond tier — big chance boost + meaningful Floobits output.
        # SOLO keys: the compute and the detail template were both rebased onto the card's
        # own player, but this builder still emitted the roster-era `fpPer1Pct`/`baseline`.
        # The effect of that split: the detail rendered raw {fpPer1PctSolo} placeholders,
        # _computeCatalyst silently fell through to its hardcoded defaults, and the
        # calculator pre-scan (the path that actually feeds ctx.chanceBonus) measured
        # ROSTER FP against a single-player baseline of 25 and sat near its cap every week.
        fpPer1PctSolo = 5
        baselineSolo = 12
        maxBoostPct = 35
        baseFloobits = int(round((10 + rn * 0.40) * editionScale))
        return {"fpPer1PctSolo": fpPer1PctSolo, "baselineSolo": baselineSolo,
                "maxBoost": maxBoostPct / 100, "maxBoostDisplay": maxBoostPct,
                "baseFloobits": baseFloobits,
                "isChanceAmplifier": True}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"floobits": int(round(5 * editionScale))}


def _buildConditionalParams(effectName, playerRating, editionScale, position=None):
    """Conditional card parameter builder.

    Numeric constants represent the post-Balatro (3×) values; `_BAL_FP_MULT`
    / `_BAL_FPX_MULT` dials them back at build time.
    """
    rn = playerRating - 60

    if effectName == "showoff":
        # FP per 5-star roster player (92+ rating). Was wildly over-tuned
        # (perStarFP ~82 → ~157 FP/wk avg, ~17x a normal base card); dialed into
        # the base band while still rewarding 5-star stacking.
        return {"rewardType": "fp",
                "perStarFP": round((12 + rn * 0.24) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "bandwagon":
        return {"rewardType": "mult", "rewardValue": round(1 + (0.168 + rn * 0.0084) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "believe":
        # FP per fav-team season win + small floobits when they win this week.
        return {"rewardType": "fp",
                "perWinFP": round((4.5 + rn * 0.10) * editionScale * _BAL_FP_MULT, 1),
                "floobitsOnTrigger": int(round((10 + rn * 0.3) * editionScale))}
    if effectName == "reclamation":
        return {"rewardType": "fp", "rewardValue": round((54 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "pedigree":
        return {"rewardType": "fp",
                "baseFP": round((27 + rn * 1.02) * editionScale * _BAL_FP_MULT, 1),
                "rewardValue": round((81 + rn * 3.39) * editionScale * _BAL_FP_MULT, 1),
                "eloThreshold": 1600}
    if effectName == "mismatch":
        return {"rewardType": "fp",
                "perTdFP": round((33 + rn * 1.35) * editionScale * _BAL_FP_MULT, 1),
                "bonusFP": round((54 + rn * 2.04) * editionScale * _BAL_FP_MULT, 1),
                "tdThreshold": 2}
    if effectName == "comeback_kid":
        # Per-roster-player FP if their team missed playoffs last season +
        # floobits if fav team pulls off a comeback win this week.
        return {"rewardType": "fp",
                "perPlayerFP": round((30 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1),
                "floobitsOnTrigger": int(round((30 + rn * 0.6) * editionScale))}
    if effectName == "domination":
        # Per-roster-player FP if their team is currently top-6 in the league +
        # floobits if fav team wins by 21+ this week. Was over-tuned like Showoff
        # (~191 FP/wk avg); dialed toward the strong-prismatic band.
        return {"rewardType": "fp",
                "perPlayerFP": round((13 + rn * 0.31) * editionScale * _BAL_FP_MULT, 1),
                "floobitsOnTrigger": int(round((30 + rn * 0.6) * editionScale)),
                "marginThreshold": 21}
    if effectName == "walk_off":
        # Per Q4/OT scoring play (TD or FG) by a roster player + floobits
        # if fav team has a walk-off win.
        return {"rewardType": "fp",
                "perScoreFP": round((40 + rn * 1.05) * editionScale * _BAL_FP_MULT, 1),
                "floobitsOnTrigger": int(round((30 + rn * 0.6) * editionScale))}
    if effectName == "medium":
        return {"rewardType": "fp",
                "lowFP": round((19.5 + rn * 0.60) * editionScale * _BAL_FP_MULT, 1),
                "midFP": round((56.0 + rn * 1.20) * editionScale * _BAL_FP_MULT, 1),
                "highFP": round((103.0 + rn * 2.00) * editionScale * _BAL_FP_MULT, 1)}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"rewardType": "fp", "rewardValue": round(20.4 * editionScale * _BAL_FP_MULT, 1)}


def _buildStreakParams(effectName, playerRating, editionScale, position=None):
    """Streak card parameter builder.

    Numeric constants represent the post-Balatro (3×) values; `_BAL_FP_MULT`
    / `_BAL_FPX_MULT` dials them back at build time.
    """
    rn = playerRating - 60

    if effectName == "complacency":
        return {"rewardType": "fp",
                "baseReward": round((20.4 + rn * 0.69) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((10.2 + rn * 0.42) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "metronome":
        # Fusion (2026-07): FREEZE streak (noReset) — never resets, so the per-week step
        # is deliberately modest (~0.8 FP/tick, capping ~35 FP at a full-season streak)
        # to keep it in check. Balance is a starting point — simcheck before locking.
        return {"rewardType": "fp",
                "baseReward": round((110 + rn * 1.4) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((6.0 + rn * 0.09) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "on_fire":
        return {"rewardType": "mult",
                "baseReward": round(1 + (0.105 + rn * 0.0063) * editionScale * _BAL_FPX_MULT, 2),
                "growthPerTick": round((0.052 + rn * 0.0021) * editionScale * _BAL_FPX_MULT, 2)}
    if effectName == "snowball_fight":
        # Band pass (v2): the hot streak was paying ~27 FP at a 3-week streak —
        # 5-6x weaker than the cold-streak cards, which is backwards (winning
        # should reward more than losing). Lifted to ~60 FP @ streak 3.
        return {"rewardType": "fp",
                "baseReward": round((45.0 + rn * 1.0) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((15.0 + rn * 0.34) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "fairweather_fan":
        # Floobits output — leave untouched
        return {"rewardType": "floobits",
                "baseReward": int(round((4 + rn * 0.2) * editionScale)),
                "growthPerTick": int(round((2 + rn * 0.08) * editionScale))}
    if effectName == "bandwagon_express":
        return {"rewardType": "fp",
                "baseReward": round((20.4 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((6.75 + rn * 0.27) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "touchdown_jackpot":
        # Floobits output — leave untouched
        return {"rewardType": "floobits",
                "baseReward": int(round((4 + rn * 0.2) * editionScale)),
                "growthPerTick": int(round((2 + rn * 0.1) * editionScale))}
    if effectName == "odometer":
        return {"rewardType": "fp",
                "gates": [
                    {"yards": 200, "fp": round((10.0 + rn * 0.16) * editionScale * _BAL_FP_MULT, 1)},
                    {"yards": 400, "fp": round((20.0 + rn * 0.34) * editionScale * _BAL_FP_MULT, 1)},
                    {"yards": 600, "fp": round((28.0 + rn * 0.44) * editionScale * _BAL_FP_MULT, 1)},
                    {"yards": 800, "fp": round((38.0 + rn * 0.56) * editionScale * _BAL_FP_MULT, 1)},
                ]}
    if effectName == "leg_day":
        return {"rewardType": "fp",
                "baseReward": round((20.4 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((8.1 + rn * 0.33) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "automatic":
        return {"rewardType": "fp",
                "baseReward": round((20.4 + rn * 0.81) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((10.2 + rn * 0.42) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "momentum":
        return {"rewardType": "mult",
                "baseReward": round(1 + (0.105 + rn * 0.0063) * editionScale * _BAL_FPX_MULT, 2),
                "growthPerTick": round((0.052 + rn * 0.0021) * editionScale * _BAL_FPX_MULT, 2)}
    # ── Inverse streaks — grow when roster underperforms ──
    if effectName == "sandbagger":
        return {"rewardType": "fp",
                "baseReward": round((40.5 + rn * 1.02) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((27.0 + rn * 0.69) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "quiet_storm":
        # Band pass (v2): was ~153 FP at a 3-week streak, >2x the prismatic band.
        # Lifted floor lowered so cold streaks land ~85 @ streak 3, ~120 @ 6 —
        # still a premium over the hot streak for the risk of a cold roster.
        return {"rewardType": "fp",
                "baseReward": round((75.0 + rn * 1.65) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((17.5 + rn * 0.39) * editionScale * _BAL_FP_MULT, 1)}
    if effectName == "drought":
        # Band pass (v2): was ~133 FP at a 3-week streak. Brought into line with
        # quiet_storm — lands ~85 @ streak 3, ~120 @ 6. (Prior tightening still
        # left it ~2x the prismatic band; this is the band-coherent value.)
        return {"rewardType": "fp",
                "baseReward": round((75.0 + rn * 1.65) * editionScale * _BAL_FP_MULT, 1),
                "growthPerTick": round((17.5 + rn * 0.39) * editionScale * _BAL_FP_MULT, 1)}
    # ── Prognostication cards ─────────────────────────────────────────
    if effectName == "nose_picker":
        # Log-tapered streak — pays for showing up to Prognostications each
        # week. Trigger is fully under user control (no luck/skill).
        import math as _math
        coef = round((48.0 + rn * 1.5) * editionScale * _BAL_FP_MULT, 2)
        kStreak = 4
        return {"rewardType": "fp",
                "baseReward": round((30.0 + rn * 0.72) * editionScale * _BAL_FP_MULT, 1),
                "coef": coef,
                "kStreak": kStreak,
                # First held week's growth over base (the steepest step); each
                # later week adds less. Display-only, for the detail template.
                "firstWeekGrowth": round(coef * _math.log(1 + 1 / kStreak), 1),
                # growthPerTick kept for legacy callers / detail template
                "growthPerTick": 0}
    # ── Strategy-Warping: Cultivation (performance-driven growth)
    if effectName == "bonsai":
        trigger = random.choice(CULTIVATION_TRIGGER_POOL)
        return {"rewardType": "fp",
                "baseFP": round((60.0 + rn * 1.8) * editionScale * _BAL_FP_MULT, 1),
                "growthFP": round((12.0 + rn * 0.5) * editionScale * _BAL_FP_MULT, 1),
                "triggerEvent": trigger["event"],
                "triggerLabel": trigger["label"],
                "isChanceEffect": True}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"rewardType": "fp", "baseReward": round(3.0 * editionScale * _BAL_FP_MULT, 1), "growthPerTick": round(1.5 * editionScale * _BAL_FP_MULT, 1)}


_PARAM_BUILDERS = {
    "flat_fp": _buildFlatFPParams,
    "multiplier": _buildMultiplierParams,
    "floobits": _buildFloobitsParams,
    "conditional": _buildConditionalParams,
    "streak": _buildStreakParams,
    "accumulator": _buildStreakParams,
}

# Effects whose handler lives in a different builder than their EFFECT_CATEGORY
# would dispatch to. Overrides category-based dispatch for param building only.
_EFFECT_BUILDER_OVERRIDES = {
    # Stat-ladder prismatic rungs. Their CATEGORY is 'streak' so the UI labels them as
    # streak cards and the breakdown fills streakActive/streakCount, but their params are
    # FPx-shaped, so dispatch goes to the multiplier builder.
    "dominion": _buildMultiplierParams, "landslide": _buildMultiplierParams,
    "undertaker": _buildMultiplierParams, "stratosphere": _buildMultiplierParams,
    "dead_eye": _buildMultiplierParams, "clockwork": _buildMultiplierParams,
    "iron_man": _buildMultiplierParams, "odyssey": _buildMultiplierParams,
    "tenure": _buildMultiplierParams, "getaway": _buildMultiplierParams,
    # flat_fp effects with handlers in _buildMultiplierParams
    "babysitter": _buildMultiplierParams,
    "martyr": _buildMultiplierParams,
    "resplendent": _buildMultiplierParams,
    "rising_tide": _buildMultiplierParams,
    "underdog": _buildMultiplierParams,
    "house_money": _buildMultiplierParams,
    "odometer": _buildStreakParams,
    "trebuchet": _buildMultiplierParams,
    "double_trouble": _buildMultiplierParams,
    "gunslinger": _buildMultiplierParams,
    # floobits effects with handlers in _buildMultiplierParams
    "hometown_hero": _buildMultiplierParams,
    "air_raid": _buildMultiplierParams,
    # flat_fp effect with handler in _buildFloobitsParams
    "workhorse": _buildFloobitsParams,
}


# ─── Output Type Derivation ──────────────────────────────────────────────────

# Effects that return multBonus (FPx factors)
_MULT_EFFECTS = frozenset({
    "no_passengers", "franchise",
    "big_deal", "luminary", "juggernaut", "stockpiler",
    "stampede", "stack", "backfield_buddies",
    "cornucopia", "providence",
    "full_roster", "all_in", "chain_reaction",
    "double_down", "high_roller", "fortitude",
    "stacked_deck", "eminence",
    "home_alone", "dark_horse", "vagabond",
})

def _deriveOutputType(category: str, effectName: str, primary: dict) -> str:
    """Derive the output type of a card effect for frontend coloring.

    Returns one of: "fp", "mult", "floobits".
    Priority: explicit rewardType in params > mult set > category default.
    """
    # Cross-category effects declare their output type explicitly
    explicitType = primary.get("rewardType")
    if explicitType:
        return explicitType
    # Accumulators/streaks may have stale stored primary — check current builder
    if category in ("accumulator", "streak") and effectName in STREAK_CONFIGS:
        currentParams = _buildStreakParams(effectName, primary.get("playerRating", 70), 1.0)
        if currentParams.get("rewardType"):
            return currentParams["rewardType"]
    if effectName in _MULT_EFFECTS:
        return "mult"
    if category == "flat_fp":
        return "fp"
    if category == "floobits":
        return "floobits"
    if category == "multiplier":
        return "mult"
    return "fp"


def rebuildPrimaryParams(effectName: str, playerRating: int, editionScale: float) -> dict:
    """Rebuild primary params from the current builder for a given effect.

    Used by serializeCard to fix stale stored params that don't match
    the current template placeholders.
    """
    category = EFFECT_CATEGORY.get(effectName, "flat_fp")
    if category == "cross":
        builder = _buildCrossPositionParams
    elif effectName in _EFFECT_BUILDER_OVERRIDES:
        builder = _EFFECT_BUILDER_OVERRIDES[effectName]
    else:
        builder = _PARAM_BUILDERS.get(category, _buildFlatFPParams)
    result = builder(effectName, playerRating, editionScale)
    return result if result else {"baseFP": round(2 * editionScale, 1)}


# ─── Position-Specific Tuning (used by both buildEffectConfig and compute) ───

# Crescendo: (baseChance%, chanceStep%) per position
_CRESCENDO_POSITION_TUNING = {
    1: (15, 12),   # QB: 2-4 TDs/game, lower start
    2: (30, 20),   # RB: 0-2 TDs/game, needs higher start
    3: (30, 20),   # WR: 0-2 TDs/game, same as RB
    5: (25, 20),   # K:  2-3 FGs/game, middle ground
}

# Traverse: (yardStep, chancePerStep%, yardType) per position
_TRAVERSE_POSITION_TUNING = {
    1: (50, 8, "passing"),    # QB: 200-350 pass yds/game
    2: (15, 8, "rushing"),    # RB: 40-100 rush yds/game
    3: (15, 8, "receiving"),  # WR: 40-100 rec yds/game
    4: (15, 8, "receiving"),  # TE: 30-70 rec yds/game
}

# All In / "Bet Big" (all_in) — the per-position STUD LINE. Well above the FP power-bar
# gate (QB 8 / RB 9 / WR 8 / TE 4 / K 6, a "showed up" bar): a genuinely big individual
# week. all_in pays nothing until the depicted player's week FP clears this line, then
# scales the FPx above it. Frozen into the config at mint (position-aware). Magnitudes
# are Phase-9-tunable. Position encoding is 1-based (QB1/RB2/WR3/TE4/K5).
_ALL_IN_STUD_LINE = {1: 22, 2: 22, 3: 20, 4: 14, 5: 15}


# ─── Config Builder ──────────────────────────────────────────────────────────

def effectPoolFor(edition: str, position: int) -> list:
    """Every effect mintable at this edition for this position.

    The ONE definition of the mint pool. buildEffectConfig draws from it, and
    cardManager's season dealer deals from it — if those two ever disagreed, the dealer
    would hand out effects the roller would never pick, which is the drift that makes a
    card exist in the registry and never in the game.
    """
    excluded = POSITION_EXCLUDED_EFFECTS.get(position, set())
    pool = [n for n in SHARED_EFFECT_POOL if n not in excluded]
    pool += POSITION_EXCLUSIVE_POOLS.get(position, [])
    return [n for n in pool if EFFECT_EDITION_TIER.get(n) == edition]


def buildEffectConfig(edition: str, playerRating: int, position: int, teamId=None,
                      forceEffect: str = None, forceCategory: str = None,
                      classification: str = None) -> dict:
    """Build the effect_config JSON for a new card template.

    Effects are drawn from a shared pool (all positions) plus position-exclusive
    pools, filtered to only effects belonging to the requested edition tier,
    minus excluded effects. Category is derived from the effect's natural type,
    not the card's position.
    forceEffect/forceCategory allow admin overrides.

    The 'base' edition (fusion) is the NO-EFFECT floor print: it carries
    no effect at all, so a card equipped from it just fields the player for their FP.
    """
    if edition == 'base' and not forceEffect:
        return {
            "effectName": "none", "displayName": "", "tagline": "", "tooltip": "",
            "detail": "", "category": "none", "outputType": "",
            "editionScale": 1.0, "primary": {},
            "posLabel": POSITION_LABELS.get(position, "??"),
        }

    # Pool selection: shared + position exclusive, minus excluded, filtered by edition tier
    pool = effectPoolFor(edition, position)

    if forceEffect:
        effectName = forceEffect
    elif not pool:
        logger.warning(f"No effects available for edition={edition}, position={position} — falling back to freebie")
        effectName = "freebie"
    else:
        effectName = random.choice(pool)

    # Category from effect's natural type (not position)
    category = forceCategory or EFFECT_CATEGORY.get(effectName, "flat_fp")

    # Per-edition power dial (Phase 9 fusion retune). Repurposes the long-dormant
    # `editionScale` hook every param builder already multiplies through — so one
    # number per edition scales that edition's FP/FPx/floobits magnitudes at mint.
    editionScale = EDITION_POWER_SCALE.get(edition, 1.0)

    # Dampen player rating scaling for rarer tiers — higher tiers have narrow
    # rating bands already, and the tier itself IS the power signal.
    _RATING_DAMPENING = {"metallic": 1.0, "holographic": 0.5, "prismatic": 0.25, "diamond": 0.0}
    dampening = _RATING_DAMPENING.get(edition, 1.0)
    dampenedRating = 60 + (playerRating - 60) * dampening

    # Builder: check per-effect overrides first, then category dispatch
    if category == "cross":
        builder = _buildCrossPositionParams
    elif effectName in _EFFECT_BUILDER_OVERRIDES:
        builder = _EFFECT_BUILDER_OVERRIDES[effectName]
    else:
        builder = _PARAM_BUILDERS.get(category, _buildFlatFPParams)
    # Position is threaded to every builder so a rate can be sized against the volume
    # THAT position actually produces. Its absence is what let Safety Blanket (TE) and
    # Possession (WR) drift to 5.3 and 2.7 FP per reception for the same mechanic, on
    # positions that catch 8.2 and 9.4 balls a game.
    primary = builder(effectName, dampenedRating, editionScale, position)
    # _buildCrossPositionParams returns None for unknown effects — fallback
    if primary is None:
        primary = {"baseFP": round(2 * editionScale, 1)}
    primary["posLabel"] = POSITION_LABELS.get(position, "??")

    # Position-specific param overrides for effects with per-position tuning
    if effectName == "crescendo":
        if position in _CRESCENDO_POSITION_TUNING:
            baseChance, chanceStep = _CRESCENDO_POSITION_TUNING[position]
            primary["baseChance"] = baseChance
            primary["chanceStep"] = chanceStep
        # Kickers escalate on FIELD GOALS, not TDs (the compute path already does; the detail
        # text must say so too, or a K-Crescendo card reads "first TD" and never fires on it).
        primary["scoreNoun"] = "FG" if position == 5 else "TD"
    if effectName == "traverse" and position in _TRAVERSE_POSITION_TUNING:
        yardStep, chancePerStep, yardType = _TRAVERSE_POSITION_TUNING[position]
        primary["yardStep"] = yardStep
        primary["chancePerStep"] = chancePerStep
        primary["yardType"] = yardType
    if effectName == "all_in":
        # Bet Big: freeze the position-aware stud line the payout scales above.
        primary["studLine"] = _ALL_IN_STUD_LINE.get(position, 20)
    if effectName == "bonsai":
        # The builder picks the growth trigger position-blind; re-pick it from ONLY the stats
        # the card player's position produces (a WR keys off receptions/YAC, a RB off carries,
        # a K off FGs) so the card can actually grow. Frozen into the config at mint.
        eligible = [t for t in CULTIVATION_TRIGGER_POOL
                    if t["event"] in _CULTIVATION_TRIGGERS_BY_POSITION.get(position, set())]
        if eligible:
            t = random.choice(eligible)
            primary["triggerEvent"] = t["event"]
            primary["triggerLabel"] = t["label"]

    conditionals = POSITION_CONDITIONALS.get(position, [])
    # Copy and apply the Balatro FP dial so the stored config carries the
    # final bonus value (cardEffectCalculator reads it as-is at compute time).
    if conditionals:
        c = dict(conditionals[0])
        c["bonus"] = _positionConditionalBonus(c.get("bonus", 0))
        conditional = c
    else:
        conditional = None

    # StreakConfig: check by effect name (not gated on category)
    streakConfig = STREAK_CONFIGS.get(effectName)

    # ⚠️ HONOR ROLL'S RAMP STARTS WHERE ITS BAR FILLS (owner, 2026-08-10), and this has
    # to happen BEFORE the detail is formatted or the card advertises one threshold and
    # scores against another. It used a hardcoded fpThreshold of 15 while the bar
    # unlocked at the gate's own position- and edition-scaled figure, 9 FP for a
    # metallic QB, so the card sat full and green reading ACTIVE while paying +0.00 FPx
    # across a six-point dead band. Syncing them also makes the figure scale by position
    # and rarity like every other bar, rather than asking a kicker and a quarterback for
    # the same 15 FP.
    if effectName == "honor_roll":
        _hrGate = buildGateSpec(effectName, position, classification, edition)
        if _hrGate and _hrGate.get("threshold"):
            primary["fpThreshold"] = _hrGate["threshold"]

    tagline = EFFECT_TAGLINES.get(effectName, "")
    tooltip = EFFECT_TOOLTIPS.get(effectName, "")

    # Fill in primary params across detail, tooltip, and tagline
    detail = EFFECT_DETAIL_TEMPLATES.get(effectName, "")
    # Auto-derive *Delta variants for known full-multiplier fields so
    # description templates can use delta notation ("+0.30 FPx") instead
    # of full-mult notation ("1.30x FPx"). Keeps user-facing numbers
    # consistent with the per-card chip and equation result (both show
    # deltas) while the underlying runtime math stays mult-based.
    _FULL_MULT_FIELDS = {
        'xMultValue':    'xMultDelta',
        'baseXMult':     'baseXDelta',
        'baseMult':      'baseDelta',
        'enhancedMult':  'enhancedDelta',
        'maxMult':       'maxDelta',
        'q4MultFactor':  'q4MultDelta',
    }
    for fullKey, deltaKey in _FULL_MULT_FIELDS.items():
        if fullKey in primary and isinstance(primary[fullKey], (int, float)):
            primary[deltaKey] = round(primary[fullKey] - 1, 2)
    # rewardValue can be either a flat FP value OR a full-mult value
    # depending on the effect. For the handful of FPx-output effects that
    # store rewardValue as 1+delta, compute a rewardDelta variant too.
    # NOTE: backfield_buddies stores rewardValue as a bare delta (compute does
    # 1 + rewardValue), so it is NOT in this set — its template uses {rewardValue}.
    _REWARDVALUE_IS_MULT_EFFECTS = {'bandwagon', 'stack', 'full_roster'}
    if effectName in _REWARDVALUE_IS_MULT_EFFECTS and 'rewardValue' in primary:
        rv = primary['rewardValue']
        if isinstance(rv, (int, float)) and rv >= 1.0:
            primary['rewardDelta'] = round(rv - 1, 2)
    # FPx streak effects (on_fire, momentum) store baseReward as a full
    # multiplier. Derive a delta variant for description templates.
    if primary.get('rewardType') == 'mult' and 'baseReward' in primary:
        br = primary['baseReward']
        if isinstance(br, (int, float)) and br >= 1.0:
            primary['baseRewardDelta'] = round(br - 1, 2)

    for key, val in primary.items():
        placeholder = "{" + key + "}"
        strVal = str(val)
        detail = detail.replace(placeholder, strVal)
        tooltip = tooltip.replace(placeholder, strVal)
        tagline = tagline.replace(placeholder, strVal)
    # Handle {statDisplay} for ace_up_the_sleeve and similar
    statKey = primary.get("stat", "")
    if statKey:
        detail = detail.replace("{statDisplay}", STAT_DISPLAY_NAMES.get(statKey, statKey))

    # Strip any unresolved placeholders
    import re as _re
    detail = _re.sub(r'\{[a-zA-Z_]+\}', '?', detail)
    tooltip = _re.sub(r'\{[a-zA-Z_]+\}', '?', tooltip)
    tagline = _re.sub(r'\{[a-zA-Z_]+\}', '?', tagline)

    # Determine output type for frontend coloring
    outputType = _deriveOutputType(category, effectName, primary)

    config = {
        "effectName": effectName,
        "displayName": EFFECT_DISPLAY_NAMES.get(effectName, effectName),
        "category": category,
        "outputType": outputType,
        "primary": primary,
        "editionScale": editionScale,
        "tagline": tagline,
        "tooltip": tooltip,
        "detail": detail,
        "streakConfig": streakConfig,
        "conditional": conditional,
    }
    # Propagate chance/amplifier flags to top-level for easy pre-scan
    if primary.get("isChanceEffect"):
        config["isChanceEffect"] = True
    if primary.get("isChanceAmplifier"):
        config["isChanceAmplifier"] = True
    # Card gate: freeze the depicted-player performance gate into the config so live
    # scoring and projection read the same spec (docs/CARD_ONCARD_REBASE_PLAN.md).
    gate = buildGateSpec(effectName, position, classification, edition)
    if gate:
        config["gate"] = gate
        # Surface the gate as its OWN field (frontend renders it on its own line, a
        # distinct requirement from the effect detail). Not appended to the detail
        # string. Fall back to it as the detail only if there's no effect detail.
        config["gateText"] = gate["text"]
        if not config.get("detail"):
            config["detail"] = gate["text"]
    return config


# ─── Effect Compute Functions ────────────────────────────────────────────────
# Each function receives (primary: dict, ctx: CardCalcContext, cardPlayerId: int,
#   equippedCardId: int) and returns an EffectResult.
# CardCalcContext is imported at function call time to avoid circular imports.

def _playerStars(rating: int) -> int:
    """Convert a player rating to 1-5 stars. Bands: 1★60-67, 2★68-75, 3★76-83, 4★84-91, 5★92+."""
    return min(5, max(1, (rating - 60) // 8 + 1))


def _getRosterPlayersByPosition(ctx, position: int) -> list:
    """Get roster player IDs at a given position. For WR (3), returns both WR1+WR2."""
    return [
        pid for pid, pos in ctx.rosterPlayerPositions.items()
        if pos == position and pid in ctx.rosterPlayerIds
    ]


def _getRosterStatsAtPosition(ctx, position: int) -> dict:
    """Get combined stats for all roster players at a position.

    For WR (position 3), combines WR1+WR2 stats.
    Returns a merged weekPlayerStats-format dict.
    """
    pids = _getRosterPlayersByPosition(ctx, position)
    if not pids:
        return {}
    if len(pids) == 1:
        return ctx.weekPlayerStats.get(pids[0], {})

    # Combine stats across multiple players
    combined = {
        "fantasyPoints": 0,
        "passing_stats": {},
        "rushing_stats": {},
        "receiving_stats": {},
        "kicking_stats": {},
    }
    for pid in pids:
        stats = ctx.weekPlayerStats.get(pid, {})
        combined["fantasyPoints"] += stats.get("fantasyPoints", 0)
        for group in ("passing_stats", "rushing_stats", "receiving_stats", "kicking_stats"):
            src = stats.get(group, {})
            if isinstance(src, dict):
                for k, v in src.items():
                    if isinstance(v, (int, float)):
                        combined[group][k] = combined[group].get(k, 0) + v
    return combined


def _getCardPlayerStats(ctx, cardPlayerId: int) -> dict:
    """Weekly stats for the player depicted ON THIS CARD.

    Fusion re-base: an equipped card IS its depicted player's lineup slot, so a
    position-specific effect (RB carries, QB completions, receiver yards) scores
    off that player directly. Replaces `_getRosterStatsAtPosition(ctx,
    ctx.cardPosition)`, which resolved to "whoever occupies this position" — and
    for WR (position 3, two slots) SUMMED WR1+WR2, so both receiver cards scored
    off the pair's combined output and paid roughly double.

    Cross-position effects that genuinely read another slot (Lead Blocker, Stack,
    Backfield Buddies) still use the position lookups — they're roster-scoped by
    design and are handled in Stage 2 of docs/CARD_ONCARD_REBASE_PLAN.md.
    """
    return ctx.weekPlayerStats.get(cardPlayerId, {}) or {}


def _countPlayerTds(playerStats: dict) -> int:
    """Count total TDs from a player's weekly game stats."""
    tds = 0
    for statGroup in ("passing_stats", "rushing_stats", "receiving_stats"):
        group = playerStats.get(statGroup)
        if isinstance(group, dict):
            tdKey = "tds" if statGroup == "passing_stats" else ("runTds" if statGroup == "rushing_stats" else "rcvTds")
            tds += group.get(tdKey, 0)
    return tds


def _getKickerStats(ctx) -> dict:
    """Find kicker stats from roster players."""
    for pid in ctx.rosterPlayerIds:
        pos = ctx.rosterPlayerPositions.get(pid)
        if pos == 5:  # K
            return ctx.weekPlayerStats.get(pid, {})
    return {}


def _getKickerFgStats(ctx) -> tuple:
    """Return (fgMade, fgAtt, longest, fg40plus) for the roster's kicker."""
    kickerStats = _getKickerStats(ctx)
    ks = kickerStats.get("kicking_stats", {})
    if not isinstance(ks, dict):
        return (0, 0, 0, 0)
    return (ks.get("fgs", 0), ks.get("fgAtt", 0), ks.get("longest", 0), ks.get("fg40plus", 0))


# ── Flat FP (WR) ─────────────────────────────────────────────────────────────

def _computeRng(primary, ctx, cardPlayerId, eqId):
    """Random FP between min and max, seeded by week + equipped card ID for consistency."""
    import random as _rand
    minFP = primary.get("minFP", 5)
    maxFP = primary.get("maxFP", 20)
    seed = hash((eqId, ctx.season, ctx.weekNumber))
    rng = _rand.Random(seed)
    rolledFP = round(rng.uniform(minFP, maxFP), 1)
    eq = f"Rolled +{rolledFP} FP (range {minFP}–{maxFP})"
    return EffectResult(fpBonus=rolledFP, equation=eq)


def _computeSnakeEyes(primary, ctx, cardPlayerId, eqId):
    """Weekly FPx that inversely scales with THIS player's FP (re-based off the roster).
    The worse their week, the higher the multiplier. Snake eyes (0 FP) pays out the most."""
    if not ctx.weekPlayerStats or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    tiers = primary.get("tiers", [(0, 3.0), (4, 2.5), (9, 2.0), (14, 1.5), (19, 1.2)])
    minMult = float(primary.get("minMult", 1.0))
    # Re-based off the roster's lowest scorer: inverse to THIS player's own FP \u2014
    # the worse their game, the bigger the multiplier (a true Bizarro card).
    stats = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}) or {}
    playerFP = round(float(stats.get("fantasyPoints", 0) or 0), 1)
    name = ctx.rosterPlayerNames.get(cardPlayerId, "?")

    mult = minMult
    for maxFP, tierMult in tiers:
        if playerFP <= maxFP:
            mult = tierMult
            break

    if mult <= 1.0:
        eq = f"{name} had {playerFP} FP \u2192 no bonus (scored well)"
        return EffectResult(equation=eq)
    # Use delta notation (+X FPx) to match the result chip — keeps the
    # input and output numbers directly comparable. Match-bonus multiplies
    # the delta cleanly: +1.5 × 1.5x match = +2.25 FPx, same units throughout.
    eq = f"{name} had {playerFP} FP \u2192 +{(mult - 1):.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeAvalanche(primary, ctx, cardPlayerId, eqId):
    """Escalating FP per roster TD within a week. First 3 TDs use fixed gates,
    then TD4+ uses sqrt decay: td4 / sqrt(n-3) where n is the TD number."""
    import math
    gates = [primary.get("td1", 2), primary.get("td2", 4), primary.get("td3", 7)]
    peakFP = primary.get("td4", 11)
    # Projection contexts may carry per-game averages which make roster
    # TDs a float. Cast to int so range() is safe regardless of caller.
    try:
        tds = int(round(float(ctx.rosterTotalTds or 0)))
    except Exception:
        tds = 0
    if tds == 0:
        return EffectResult(equation="No roster TDs this week")
    totalFP = 0
    details = []
    for i in range(tds):
        if i < len(gates):
            gateFP = gates[i]
        else:
            gateFP = round(peakFP / math.sqrt(i - 2), 1)
        totalFP += gateFP
        label = f"TD{i + 1}=+{gateFP}"
        details.append(label)
    totalFP = round(totalFP, 1)
    eq = f"{tds} roster TD{'s' if tds != 1 else ''}: {', '.join(details)} = +{totalFP} FP"
    return EffectResult(fpBonus=totalFP, equation=eq)


def _computeHedge(primary, ctx, cardPlayerId, eqId):
    """FP floor for THIS player: tops their output up to a floor if they had a bad
    game (re-based off the whole roster to the depicted player)."""
    floorFP = primary.get("floorSoloFP", 12)
    playerFP = round((ctx.weekPlayerStats or {}).get(cardPlayerId, {}).get("fantasyPoints", 0) or 0, 1)
    bonus = round(max(0, floorFP - playerFP), 1)
    if bonus > 0:
        eq = f"{floorFP} floor − {playerFP} FP = +{bonus} FP"
        return EffectResult(fpBonus=bonus, equation=eq)
    eq = f"Scored {playerFP} FP (above the {floorFP} floor — no hedge needed)"
    return EffectResult(equation=eq)


def _computeFreebie(primary, ctx, cardPlayerId, eqId):
    val = primary.get("baseFP", 0)
    return EffectResult(fpBonus=val)


def _computeEntourage(primary, ctx, cardPlayerId, eqId):
    minStars = primary.get("minStars", 3)
    perPlayer = primary.get("perPlayerFP", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) >= minStars)
    eq = f"{perPlayer}/player × {count} ({minStars}★+)"
    return EffectResult(fpBonus=perPlayer * count, equation=eq)


def _computeTouchdownPinata(primary, ctx, cardPlayerId, eqId):
    perTd = primary.get("perTdFP", 0)
    tds = ctx.rosterTotalTds
    eq = f"{perTd}/TD × {tds} roster TDs"
    return EffectResult(fpBonus=perTd * tds, equation=eq)


def _computeScrappy(primary, ctx, cardPlayerId, eqId):
    """Chance card: base FP always + chance of enhanced FP based on low-rated player count."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", primary.get("perPlayerFP", 1.0))
    enhancedFP = primary.get("enhancedFP", 5.0)
    maxStars = primary.get("maxStars", 2)
    # Legacy fallback — old param shape without baseFP/enhancedFP
    if "baseFP" not in primary and "perPlayerFP" in primary:
        perPlayer = primary["perPlayerFP"]
        count = sum(1 for pid in ctx.rosterPlayerIds
                    if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) <= maxStars)
        eq = f"{perPlayer}/player × {count} ({maxStars}★ or lower)"
        return EffectResult(fpBonus=perPlayer * count, equation=eq)
    from constants import CARD_CHANCE_CONDITION_FULL_COUNT
    count = sum(1 for pid in ctx.rosterPlayerIds
                if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) <= maxStars)
    conditionFill = count / CARD_CHANCE_CONDITION_FULL_COUNT
    odds = _chanceOdds(ctx, cardPlayerId, conditionFill, useFP=True)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= odds and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceBarEq(ctx, odds, conditionFill, True, triggered,
                      f"+{enhancedFP} FP", f"{count} low-rated", f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(odds, 4), chanceTriggered=triggered)


def _computeHonorRoll(primary, ctx, cardPlayerId, eqId):
    """FPx bonus when THIS player clears the FP threshold (re-based off the roster).

    The mult RAMPS from zero at the threshold to maxMult at double it, so the payout
    scales with how big the game was rather than switching on flat. `fpThreshold` is the
    card's own power-bar threshold (synced in buildEffectConfig), so the ramp begins at
    exactly the point the bar fills — a card that reads ACTIVE is always earning.
    """
    threshold = primary.get("fpThreshold", 15)
    maxMult = primary.get("maxMult", 1.30)
    # Older cards were minted without a base and started their ramp at zero.
    baseMult = primary.get("baseMult") or 1.0
    playerFP = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}).get("fantasyPoints", 0) or 0
    if playerFP < threshold:
        return EffectResult(equation=f"{round(playerFP, 1)} FP, needs {threshold}+ this week")
    # Clearing the bar pays the base; beating it ramps to the max at double the bar.
    over = min(1.0, (playerFP - threshold) / max(threshold, 1))
    mult = round(baseMult + (maxMult - baseMult) * over, 2)
    delta = round(mult - 1.0, 2)
    eq = f"+{delta} FPx from {round(playerFP, 1)} FP (bar is {threshold})"
    return EffectResult(multBonus=mult, equation=eq)


def _computeThreePointer(primary, ctx, cardPlayerId, eqId):
    fgMade, _, _, _ = _getKickerFgStats(ctx)
    perFg = primary.get("perFgFP", 0)
    eq = f"{perFg}/FG × {fgMade} FGs made"
    return EffectResult(fpBonus=perFg * fgMade, equation=eq)


def _computeGarbageTime(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerFP", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.rosterPlayerPositions.get(pid) != 5  # Exclude K
                and _countPlayerTds(ctx.weekPlayerStats.get(pid, {})) == 0)
    eq = f"{perPlayer}/player × {count} (0 TD players)"
    return EffectResult(fpBonus=perPlayer * count, equation=eq)


def _computeLoyaltyBonus(primary, ctx, cardPlayerId, eqId):
    streak = max(0, ctx.favoriteTeamStreak)  # Only positive (win streak)
    perStreak = primary.get("perStreakFP", 0)
    eq = f"{perStreak}/win × {streak} win streak"
    return EffectResult(fpBonus=perStreak * streak, equation=eq)


def _computeDiamondInTheRough(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerFloobits", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) - ctx.rosterPlayerRatings.get(pid, 60) >= 5)
    bonus = perPlayer * count
    eq = f"{perPlayer}F/player × {count} overperforming = +{bonus}F"
    return EffectResult(floobits=bonus, equation=eq)




# ── Multiplier (QB) ──────────────────────────────────────────────────────────

def _computeBigDeal(primary, ctx, cardPlayerId, eqId):
    val = primary.get("xMultValue", 1.0)
    return EffectResult(multBonus=val)


def _computeTriggerHappy(primary, ctx, cardPlayerId, eqId):
    """Cornucopia FPx scales with roster TDs using a log taper. Linear
    growth let strong-offense rosters with 10+ TDs run away (2.0x and up);
    log curve rewards 3-5 TD weeks similarly to before but plateaus around
    1.7x on monster TD weeks. `perTdMult` is now the log-curve coefficient.
    """
    import math
    perTd = primary.get("perTdMult", 0)
    tds = ctx.rosterTotalTds or 0
    if tds <= 0:
        return EffectResult(multBonus=1.0, equation="No roster TDs this week")
    bonus = perTd * math.log(1 + tds / 3.0)
    mult = round(1 + bonus, 3)
    delta = round(mult - 1.0, 2)
    eq = f"{tds} roster TDs = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeMainCharacter(primary, ctx, cardPlayerId, eqId):
    # Roster player's FP share (keyed off card position)
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getCardPlayerStats(ctx, cardPlayerId)
    rosterFP = rosterStats.get("fantasyPoints", 0)
    fpShare = rosterFP / max(ctx.weekRawFP, 1)
    scale = primary.get("fpShareScale", 0)
    delta = round(scale * fpShare, 2)
    eq = f"{scale} × {round(fpShare * 100)}% {posLabel} FP share = +{delta:.2f} FPx"
    return EffectResult(multBonus=1 + scale * fpShare, equation=eq)


def _computeHypeMan(primary, ctx, cardPlayerId, eqId):
    # Roster player's TDs (keyed off card position)
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getCardPlayerStats(ctx, cardPlayerId)
    rosterTds = _countPlayerTds(rosterStats)
    # Normalize legacy cards: perTdXMult/xMultValue → perTdFP
    perTdFP = primary.get("perTdFP") or primary.get("perTdXMult") or primary.get("xMultValue") or 0
    if rosterTds > 0:
        bonus = round(perTdFP * rosterTds, 1)
        eq = f"{perTdFP}/TD × {rosterTds} {posLabel} TD{'s' if rosterTds != 1 else ''}"
        return EffectResult(fpBonus=bonus, equation=eq)
    return EffectResult(equation=f"{perTdFP} FP/TD × 0 {posLabel} TDs")


def _computeBabysitter(primary, ctx, cardPlayerId, eqId):
    """Chance card: base FP always + chance of enhanced FP based on underperformers."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 5)
    enhancedFP = primary.get("enhancedFP", 18)
    threshold = primary.get("fpThreshold", 8)
    from constants import CARD_CHANCE_CONDITION_FULL_COUNT
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
    conditionFill = count / CARD_CHANCE_CONDITION_FULL_COUNT
    odds = _chanceOdds(ctx, cardPlayerId, conditionFill, useFP=True)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= odds and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceBarEq(ctx, odds, conditionFill, True, triggered,
                      f"+{enhancedFP} FP", f"{count} under {threshold} FP", f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(odds, 4), chanceTriggered=triggered)


def _computeTankCommander(primary, ctx, cardPlayerId, eqId):
    """Chance card: base FP always + chance of enhanced FP when team loses (scales with season losses)."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 5)
    enhancedFP = primary.get("enhancedFP", 18)
    # Legacy fallback
    if "baseFP" not in primary and "perLossMult" in primary:
        perLoss = primary["perLossMult"]
        losses = ctx.favoriteTeamSeasonLosses
        bonus = perLoss * losses
        eq = f"1 + ({perLoss}/loss × {losses} team losses) = {1 + bonus:.2f}x"
        return EffectResult(multBonus=1 + bonus, equation=eq)
    if "baseFP" not in primary and "baseMult" in primary:
        baseMult = primary["baseMult"]
        enhancedMult = primary.get("enhancedMult", 1.3)
        if not ctx.favoriteTeamGameFinal or ctx.favoriteTeamWonThisWeek:
            return EffectResult(multBonus=baseMult, equation=f"{baseMult:.2f}x FPx (legacy base)")
        return EffectResult(multBonus=enhancedMult, equation=f"{enhancedMult:.2f}x FPx (legacy enhanced)")
    if not ctx.favoriteTeamGameFinal:
        eq = f"+{baseFP} FP. Game not final"
        return EffectResult(fpBonus=baseFP, equation=eq)
    losses = ctx.favoriteTeamSeasonLosses
    baseChance = min(0.85, losses * 0.085 + 0.10) if losses >= 2 else (0.12 if losses == 1 else 0)
    totalChance = min(0.97, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFP} FP", f"{losses} season losses", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


def _computeJuggernaut(primary, ctx, cardPlayerId, eqId):
    """Juggernaut FPx scales with the favorite team's win streak using a log
    taper: early wins are very rewarding, gains plateau as the streak grows.
    Replaces the prior linear baseX + growth × streak which made 10+ win
    runs explosive (e.g. a 15-win streak produced ~2.3x). New shape peaks
    around 1.7x on long streaks. Coefficient `growth` now scales the log
    curve rather than the per-win delta.
    """
    import math
    streak = max(0, ctx.favoriteTeamStreak)
    baseX = primary.get("baseXMult", 1.08)
    growth = primary.get("growthPerWin", 0.30)  # repurposed: log-curve scale
    # Only pay out once the team wins this week, extending their streak
    if not ctx.favoriteTeamWonThisWeek or streak <= 0:
        return EffectResult(multBonus=1.0, equation="Waiting for win to extend streak")
    bonus = growth * math.log(1 + streak / 3.0)
    mult = round(baseX + bonus, 3)
    baseDelta = round(baseX - 1.0, 2)
    delta = round(mult - 1.0, 2)
    eq = f"+{baseDelta:.2f} base + {streak} win streak = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeHotRoster(primary, ctx, cardPlayerId, eqId):
    # Match the +5 threshold used by the player hover tooltip
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) - ctx.rosterPlayerRatings.get(pid, 60) >= 5)
    # New FP path
    perPlayerFP = primary.get("perPlayerFP", 0)
    if perPlayerFP:
        bonus = round(perPlayerFP * count, 1)
        eq = f"{perPlayerFP}/player × {count} overperforming"
        return EffectResult(fpBonus=bonus, equation=eq)
    # Legacy FPx path
    perPlayer = primary.get("perPlayerMult", 0)
    bonus = perPlayer * count
    mult = 1 + bonus
    delta = round(mult - 1.0, 2)
    eq = f"+{perPlayer}/player × {count} overperforming = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeRisingTide(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerMult", 0)
    maxMult = primary.get("maxMult", 1.5)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) - ctx.rosterPlayerRatings.get(pid, 60) >= 5)
    rawMult = 1 + perPlayer * count
    mult = min(rawMult, maxMult)
    delta = round(mult - 1.0, 2)
    maxDelta = round(maxMult - 1.0, 2)
    eq = f"+{perPlayer}/player × {count} overperforming = +{delta:.2f} FPx (max +{maxDelta:.2f})"
    return EffectResult(multBonus=mult, equation=eq)



def _computeUnderdog(primary, ctx, cardPlayerId, eqId):
    """Chance card: base FP always + chance of enhanced FP (scales with ELO gap)."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 5)
    enhancedFP = primary.get("enhancedFP", 18)
    # Legacy fallback
    if "baseFP" not in primary and "eloPer100" in primary:
        eloPer100 = primary["eloPer100"]
        eloBelowAvg = max(0, (ctx.leagueAverageElo - ctx.favoriteTeamElo) / 100)
        eloDiff = round(ctx.leagueAverageElo - ctx.favoriteTeamElo)
        if eloBelowAvg == 0:
            return EffectResult(equation="team not below avg ELO")
        eq = f"1 + ({eloPer100}x × {eloDiff} ELO below avg)"
        return EffectResult(multBonus=1 + eloPer100 * eloBelowAvg, equation=eq)
    if "baseFP" not in primary and "baseMult" in primary:
        baseMult = primary["baseMult"]
        return EffectResult(multBonus=baseMult, equation=f"{baseMult:.2f}x FPx (legacy)")
    eloBelowAvg = max(0, ctx.leagueAverageElo - ctx.favoriteTeamElo)
    if eloBelowAvg <= 0:
        eq = f"+{baseFP} FP. Team not below avg ELO"
        return EffectResult(fpBonus=baseFP, equation=eq)
    baseChance = min(0.85, eloBelowAvg / 320)
    totalChance = min(0.97, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    eloDiff = round(eloBelowAvg)
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFP} FP", f"{eloDiff} ELO below avg", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


def _computeStockpiler(primary, ctx, cardPlayerId, eqId):
    perSwap = primary.get("perSwapXMult", 0.05)
    unusedSwaps = ctx.unusedSwaps
    if unusedSwaps <= 0:
        return EffectResult(equation="no unused swaps")
    delta = round(unusedSwaps * perSwap, 2)
    eq = f"+{perSwap}/swap × {unusedSwaps} unused swaps = +{delta:.2f} FPx"
    return EffectResult(multBonus=1 + unusedSwaps * perSwap, equation=eq)


def _computeProvidence(primary, ctx, cardPlayerId, eqId):
    """Small FPx bonus + aura that boosts all chance card trigger rates."""
    baseMult = primary.get("baseMult", 1.05)
    chanceBonus = primary.get("chanceBonus", 0.12)
    baseDelta = round(baseMult - 1.0, 2)
    eq = f"+{baseDelta:.2f} FPx + {chanceBonus:.0%} chance boost"
    return EffectResult(multBonus=baseMult, equation=eq)


def _computeHouseMoney(primary, ctx, cardPlayerId, eqId):
    upsetWins = max(0, ctx.streakCounts.get(eqId, 1) - 1)  # streak_count starts at 1
    # New FP path
    baseFP = primary.get("baseFP", 0)
    perUpsetFP = primary.get("perUpsetFP", 0)
    if baseFP or perUpsetFP:
        bonus = round(baseFP + perUpsetFP * upsetWins, 1)
        eq = f"{baseFP} base + {perUpsetFP}/upset × {upsetWins} upset wins = +{bonus} FP"
        return EffectResult(fpBonus=bonus, equation=eq)
    # Legacy FPx path
    baseXMult = primary.get("baseXMult", 1.0)
    perUpset = primary.get("perUpsetXMult", 0)
    xMult = baseXMult + perUpset * upsetWins
    baseDelta = round(baseXMult - 1.0, 2)
    delta = round(xMult - 1.0, 2)
    eq = f"+{baseDelta:.2f} base + ({perUpset}/upset × {upsetWins} upset wins) = +{delta:.2f} FPx"
    return EffectResult(multBonus=xMult, equation=eq)


# ── Floobits (RB) ────────────────────────────────────────────────────────────

def _computeAllowance(primary, ctx, cardPlayerId, eqId):
    val = primary.get("floobits", 0)
    return EffectResult(floobits=val)


def _computeChaChing(primary, ctx, cardPlayerId, eqId):
    # Roster player's TDs (keyed off card position)
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getCardPlayerStats(ctx, cardPlayerId)
    rosterTds = _countPlayerTds(rosterStats)
    perTd = primary.get("perTdFloobits", 0)
    eq = f"{perTd}F/TD × {rosterTds} {posLabel} TDs"
    return EffectResult(floobits=perTd * rosterTds, equation=eq)


def _computePiggyBank(primary, ctx, cardPlayerId, eqId):
    pct = primary.get("fpPercent", 0)
    # Re-based off the roster: a cut of THIS player's own FP.
    playerFP = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}).get("fantasyPoints", 0) or 0
    eq = f"{pct}% × {round(playerFP, 1)} FP"
    return EffectResult(floobits=int(playerFP * pct / 100), equation=eq)


def _computegood_neighbor(primary, ctx, cardPlayerId, eqId):
    """Base Floobits every week + windfall per missed FG this week."""
    baseFloobits = primary.get("baseFloobits", 4)
    perMissFloobits = primary.get("perMissFloobits", 8)
    fgMade, fgAtt, _, _ = _getKickerFgStats(ctx)
    weekMisses = max(0, fgAtt - fgMade)
    missBonus = perMissFloobits * weekMisses
    total = baseFloobits + missBonus
    if weekMisses > 0:
        eq = f"+{baseFloobits}F base + {perMissFloobits}F × {weekMisses} missed FG{'s' if weekMisses > 1 else ''} = +{total}F"
    else:
        eq = f"+{baseFloobits}F base (no missed FGs this week)"
    return EffectResult(floobits=total, equation=eq)


def _computeConsolationPrize(primary, ctx, cardPlayerId, eqId):
    """Chance card: base Floobits always + chance of enhanced (scales with bad-week players)."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFloobits = primary.get("baseFloobits", 2)
    enhancedFloobits = primary.get("enhancedFloobits", 10)
    threshold = primary.get("fpThreshold", 5)
    # Legacy fallback
    if "baseFloobits" not in primary and "perPlayerFloobits" in primary:
        perPlayer = primary["perPlayerFloobits"]
        count = sum(1 for pid in ctx.rosterPlayerIds
                    if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
        eq = f"{perPlayer}F/player × {count} (under {threshold} FP)"
        return EffectResult(floobits=perPlayer * count, equation=eq)
    from constants import CARD_CHANCE_CONDITION_FULL_COUNT
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
    conditionFill = count / CARD_CHANCE_CONDITION_FULL_COUNT
    odds = _chanceOdds(ctx, cardPlayerId, conditionFill, useFP=True)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= odds and not getattr(ctx, 'gamesActive', False)
    floobitsVal = enhancedFloobits if triggered else baseFloobits
    eq = _chanceBarEq(ctx, odds, conditionFill, True, triggered,
                      f"+{enhancedFloobits}F", f"{count} under {threshold} FP", f"+{baseFloobits}F")
    return EffectResult(floobits=floobitsVal, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(odds, 4), chanceTriggered=triggered)


def _computeRockBottom(primary, ctx, cardPlayerId, eqId):
    """Chance card: base Floobits always + chance of enhanced (scales with losing streak)."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFloobits = primary.get("baseFloobits", 2)
    enhancedFloobits = primary.get("enhancedFloobits", 10)
    # Legacy fallback
    if "baseFloobits" not in primary and "perStreakFloobits" in primary:
        lossStreak = max(0, -ctx.favoriteTeamStreak)
        perStreak = primary["perStreakFloobits"]
        eq = f"{perStreak}F/loss × {lossStreak} loss streak"
        return EffectResult(floobits=perStreak * lossStreak, equation=eq)
    lossStreak = max(0, -ctx.favoriteTeamStreak)
    if lossStreak <= 0:
        eq = f"+{baseFloobits}F. No losing streak"
        return EffectResult(floobits=baseFloobits, equation=eq)
    baseChance = min(0.85, lossStreak * 0.135 + 0.10)
    totalChance = min(0.97, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    floobitsVal = enhancedFloobits if triggered else baseFloobits
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFloobits}F", f"{lossStreak} loss streak", ctx=ctx, base=f"+{baseFloobits}F")
    return EffectResult(floobits=floobitsVal, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


def _computeBuyLow(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerFloobits", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.rosterPlayerRatings.get(pid, 60) - ctx.playerPerformanceRatings.get(pid, 0) >= 5
                and ctx.playerPerformanceRatings.get(pid, 0) > 0)
    eq = f"{perPlayer}F/player × {count} underperforming"
    return EffectResult(floobits=perPlayer * count, equation=eq)


def _computeTrustFund(primary, ctx, cardPlayerId, eqId):
    baseFloobits = primary.get("baseFloobits", 0)
    growth = primary.get("growthPerWeek", 0)
    weeks = max(0, ctx.rosterUnchangedWeeks)
    eq = f"{baseFloobits}F base + ({growth}F × {weeks} wks unchanged)"
    return EffectResult(floobits=baseFloobits + growth * weeks, equation=eq)



# ── Conditional (TE) ─────────────────────────────────────────────────────────

def _computeAceUpTheSleeve(primary, ctx, cardPlayerId, eqId):
    # Flat base FP + bonus when WR slots hit combined stat threshold
    stat = primary.get("stat", "recYards")
    threshold = primary.get("threshold", 125)
    baseFP = primary.get("baseFP", 3.0)
    bonusFP = primary.get("rewardValue", 0)
    rosterStats = _getCardPlayerStats(ctx, cardPlayerId)
    actualValue = _getStatValue(rosterStats, stat)
    if actualValue >= threshold:
        total = round(baseFP + bonusFP, 1)
        eq = f"{baseFP} base + {bonusFP} bonus (WR {stat}: {round(actualValue)} >= {threshold})"
        return EffectResult(fpBonus=total, equation=eq)
    eq = f"{baseFP} base (WR {stat}: {round(actualValue)} / {threshold})"
    return EffectResult(fpBonus=baseFP, equation=eq)


def _computeShowoff(primary, ctx, cardPlayerId, eqId):
    """FP per 5-star roster player. The 'star turn' card — rewards rostering
    elite-tier players. Predictable: visible at lock time.
    """
    perStarFP = primary.get("perStarFP", 25)
    count = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if _playerStars((ctx.rosterPlayerRatings or {}).get(pid, 60)) >= 5
    )
    fp = round(perStarFP * count, 1)
    eq = f"{perStarFP}/star × {count} (5★ roster players) = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeBandwagon(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    if ctx.favoriteTeamWonThisWeek:
        result = _conditionalReward(primary)
        result.equation = "team won this week"
        return result
    return EffectResult(equation="waiting for team win")


def _computeBelieve(primary, ctx, cardPlayerId, eqId):
    """FP scaling with favorite team's season wins — your faith pays off
    more the better they do. Floobits bonus on a fav-team win this week.
    """
    perWinFP = primary.get("perWinFP", 4.5)
    floobitsBonus = primary.get("floobitsOnTrigger", 10)
    wins = int(getattr(ctx, 'favoriteTeamSeasonWins', 0) or 0)
    fp = round(perWinFP * wins, 1)
    fbBonus = 0
    eqParts = [f"{perWinFP}/win × {wins} fav-team wins = +{fp} FP"]
    if ctx.favoriteTeamGameFinal and ctx.favoriteTeamWonThisWeek:
        fbBonus = floobitsBonus
        eqParts.append(f"+{fbBonus}F (fav team won this week)")
    return EffectResult(fpBonus=fp, floobits=fbBonus, equation=" | ".join(eqParts))


def _computeFeedingFrenzy(primary, ctx, cardPlayerId, eqId):
    # Floobits per roster TD, plus a bonus when roster hits the threshold.
    perTd = int(primary.get("perTdFloobits", 3))
    bonus = int(primary.get("bonusFloobits", 8))
    tdThreshold = primary.get("tdThreshold", 3)
    try:
        tds = int(round(float(ctx.rosterTotalTds or 0)))
    except Exception:
        tds = 0
    perTdPayout = perTd * tds
    if tds >= tdThreshold:
        total = perTdPayout + bonus
        eq = f"{perTd}F × {tds} TDs + {bonus}F bonus = {total}F"
        return EffectResult(floobits=total, equation=eq)
    if tds > 0:
        eq = f"{perTd}F × {tds} TDs = {perTdPayout}F ({tdThreshold - tds} more for +{bonus}F bonus)"
        return EffectResult(floobits=perTdPayout, equation=eq)
    return EffectResult(equation=f"no roster TDs yet ({tdThreshold} for bonus)")


def _computeSpotlightMoment(primary, ctx, cardPlayerId, eqId):
    # +FP if player at card's position scores a TD
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getCardPlayerStats(ctx, cardPlayerId)
    rosterTds = _countPlayerTds(rosterStats)
    rewardFP = primary.get("rewardValue", 0)
    if rosterTds > 0:
        return EffectResult(fpBonus=rewardFP, equation=f"{posLabel} scored {rosterTds} TD{'s' if rosterTds != 1 else ''}")
    return EffectResult(equation=f"waiting for {posLabel} TD")


def _computeHighlightReel(primary, ctx, cardPlayerId, eqId):
    if ctx.favoriteTeamBigPlays > 0:
        perPlay = primary.get("rewardValue", 0)
        plays = ctx.favoriteTeamBigPlays
        rewardValue = perPlay * plays
        return EffectResult(floobits=int(rewardValue), equation=f"{perPlay}F/play × {plays} big plays")
    return EffectResult(equation="waiting for big plays")


def _computeFixerUpper(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    underperforming = sum(1 for pid in ctx.rosterPlayerIds
                         if ctx.rosterPlayerRatings.get(pid, 60) - ctx.playerPerformanceRatings.get(pid, 0) >= 5
                         and ctx.playerPerformanceRatings.get(pid, 0) > 0)
    total = len(ctx.rosterPlayerIds)
    needed = total // 2 + 1
    if underperforming > total / 2:
        result = _conditionalReward(primary)
        result.equation = f"{underperforming}/{total} underperforming"
        return result
    return EffectResult(equation=f"{underperforming} / {needed} needed underperforming")


def _computePedigree(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    baseFP = primary.get("baseFP", 4)
    rewardValue = primary.get("rewardValue", 12)
    eloThreshold = primary.get("eloThreshold", 1600)
    teamElo = round(ctx.favoriteTeamElo)
    # Legacy fallback
    if "baseFP" not in primary and "baseMult" in primary:
        baseMult = primary["baseMult"]
        mult = primary.get("rewardValue", 1.3)
        if ctx.favoriteTeamElo >= eloThreshold:
            return EffectResult(multBonus=mult, equation=f"+{mult - 1.0:.2f} FPx (legacy, ELO {teamElo})")
        return EffectResult(multBonus=baseMult, equation=f"+{baseMult - 1.0:.2f} FPx (legacy, ELO {teamElo})")
    if ctx.favoriteTeamElo >= eloThreshold:
        eq = f"+{rewardValue} FP (team ELO {teamElo} >= {eloThreshold})"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"+{baseFP} FP (team ELO {teamElo}, need {eloThreshold} for full bonus)"
    return EffectResult(fpBonus=baseFP, equation=eq)


def _conditionalReward(primary) -> EffectResult:
    """Convert a conditional's reward into an EffectResult.
    Mult rewardValue is stored as a factor >1 (e.g. 1.3 = ×1.3)."""
    rewardType = primary.get("rewardType", "fp")
    rewardValue = primary.get("rewardValue", 0)
    if rewardType == "fp":
        return EffectResult(fpBonus=rewardValue)
    elif rewardType == "mult":
        return EffectResult(multBonus=rewardValue)
    elif rewardType == "floobits":
        return EffectResult(floobits=int(rewardValue))
    return EffectResult()


# ── New cards (FP/FPx rebalance) ─────────────────────────────────────────────

def _computeAnthem(primary, ctx, cardPlayerId, eqId):
    """Threshold-based flat FP. Pops when the hand carries 3+ flat-FP cards;
    larger pop at 4, biggest at 5. Counts only OTHER flat-FP cards in the
    hand, plus this card itself, against the thresholds.
    """
    flatFPCount = sum(
        1 for outType in (ctx.equippedCardOutputTypes or [])
        if outType == "fp"
    )
    tier3 = primary.get("tier3FP", 25)
    tier4 = primary.get("tier4FP", 35)
    tier5 = primary.get("tier5FP", 50)
    if flatFPCount >= 5:
        eq = f"+{tier5} FP (5 flat-FP cards equipped)"
        return EffectResult(fpBonus=tier5, equation=eq)
    if flatFPCount >= 4:
        eq = f"+{tier4} FP (4 flat-FP cards equipped)"
        return EffectResult(fpBonus=tier4, equation=eq)
    if flatFPCount >= 3:
        eq = f"+{tier3} FP (3 flat-FP cards equipped)"
        return EffectResult(fpBonus=tier3, equation=eq)
    return EffectResult(equation=f"{flatFPCount}/3 flat-FP cards (need 3+)")


def _computeConductor(primary, ctx, cardPlayerId, eqId):
    """Pure amplifier. Produces no own output. The actual boost is applied
    by the calculator's tradeoff phase (_applyConductorBoost), which
    multiplies every other flat-FP card's output by (1 + boostPct/100).
    Returning an empty EffectResult here marks the card as "present"
    so the amplifier-status pill can read its config.
    """
    return EffectResult()


def _computeCastaway(primary, ctx, cardPlayerId, eqId):
    """Flat FP bonus when at least one roster player is on a sub-.500 team.
    Reads team records via ctx.teamResults if available; falls back to a
    'no signal' state during projection if records aren't loaded yet.
    """
    rewardFP = primary.get("rewardFP", 14)
    rosterTeamIds = ctx.rosterPlayerTeamIds or {}
    teamRecords = getattr(ctx, '_teamRecords', None) or {}
    # ctx may carry team records directly via teamResults (boolean wins
    # this week) — for season win pct we look at teamRecords mapping.
    found = False
    for pid, teamId in rosterTeamIds.items():
        if pid not in (ctx.rosterPlayerIds or set()):
            continue
        rec = teamRecords.get(teamId)
        if rec is not None and rec < 0.5:
            found = True
            break
    if found:
        return EffectResult(fpBonus=rewardFP, equation=f"+{rewardFP} FP (sub-.500 player on roster)")
    return EffectResult(equation="No sub-.500 player on roster")


def _computeSleeper(primary, ctx, cardPlayerId, eqId):
    """Chance card. Enhanced-roll odds scale per <3★ player on roster.
    Floor pays a guaranteed baseFP; enhanced FP fires more often the more
    sub-3★ players are committed to the roster.
    """
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 5)
    enhancedFP = primary.get("enhancedFP", 22)
    from constants import CARD_CHANCE_CONDITION_FULL_COUNT
    lowStarCount = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if (ctx.rosterPlayerRatings or {}).get(pid, 80) < 76
    )
    conditionFill = lowStarCount / CARD_CHANCE_CONDITION_FULL_COUNT
    odds = _chanceOdds(ctx, cardPlayerId, conditionFill, useFP=True)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= odds and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceBarEq(ctx, odds, conditionFill, True, triggered,
                      f"+{enhancedFP} FP", f"{lowStarCount} low-rated players", f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4),
                        chanceThreshold=round(odds, 4),
                        chanceTriggered=triggered)


def _computePatient(primary, ctx, cardPlayerId, eqId):
    """Per-week reward for keeping a sub-3★ roster slot intact. Reads how
    many weeks the user has gone without swapping out a low-rated slot;
    pays baseFP * weeks_held until they swap or the player rises to 3★+.
    Uses ctx.rosterUnchangedWeeks as a proxy when slot-level history isn't
    available.
    """
    baseFP = primary.get("baseFP", 1.5)
    lowStarCount = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if (ctx.rosterPlayerRatings or {}).get(pid, 80) < 76
    )
    if lowStarCount == 0:
        return EffectResult(equation="No sub-3★ roster slot to reward")
    weeksHeld = max(1, getattr(ctx, 'rosterUnchangedWeeks', 1))
    fp = round(baseFP * weeksHeld, 1)
    eq = f"+{baseFP}/wk × {weeksHeld} weeks unchanged = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeRookieHype(primary, ctx, cardPlayerId, eqId):
    """Per-rookie FP. Uses _isRookie attached on player or rosterPlayerNames
    plus a fallback to ctx-stored rookie set if available.
    """
    perRookieFP = primary.get("perRookieFP", 4.5)
    rookieFlags = getattr(ctx, '_rosterRookieFlags', None) or {}
    count = sum(1 for pid in (ctx.rosterPlayerIds or set())
                if rookieFlags.get(pid))
    if count == 0:
        return EffectResult(equation="No rookies on roster")
    fp = round(perRookieFP * count, 1)
    eq = f"+{perRookieFP}/rookie × {count} = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeWanderer(primary, ctx, cardPlayerId, eqId):
    """Per unique team represented across the roster. Counts distinct
    team_ids from rosterPlayerTeamIds; max payout when no two roster
    players share a team.
    """
    perTeamFP = primary.get("perTeamFP", 3)
    teamIds = set(
        teamId for pid, teamId in (ctx.rosterPlayerTeamIds or {}).items()
        if pid in (ctx.rosterPlayerIds or set()) and teamId is not None
    )
    if not teamIds:
        return EffectResult(equation="No team affiliation data on roster")
    fp = round(perTeamFP * len(teamIds), 1)
    eq = f"+{perTeamFP}/team × {len(teamIds)} unique teams = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeSynergy(primary, ctx, cardPlayerId, eqId):
    """FPx delta per same-team pair (sets of 2) on roster. With n players
    on the same actual team, that's n // 2 pairs. Max 3 pairs (all 6 roster
    slots from the same team). Rewards real-team stacking."""
    perPairMult = primary.get("perPairMult", 0.05)
    maxMult = primary.get("maxMult", 1.30)
    teamCounts: Dict[int, int] = {}
    for pid in (ctx.rosterPlayerIds or set()):
        tid = (ctx.rosterPlayerTeamIds or {}).get(pid)
        if tid is None:
            continue
        teamCounts[tid] = teamCounts.get(tid, 0) + 1
    pairs = sum(n // 2 for n in teamCounts.values())
    if pairs == 0:
        return EffectResult(multBonus=1.0, equation="No same-team pairs on roster")
    mult = min(maxMult, round(1.0 + perPairMult * pairs, 2))
    delta = round(mult - 1.0, 2)
    eq = f"+{delta} FPx — {pairs} same-team pair{'s' if pairs != 1 else ''}"
    return EffectResult(multBonus=mult, equation=eq)


def _computeVanguard(primary, ctx, cardPlayerId, eqId):
    """FPx delta per veteran (5+ seasons played) on roster."""
    perVetMult = primary.get("perVetMult", 0.05)
    maxMult = primary.get("maxMult", 1.30)
    sp = getattr(ctx, '_rosterSeasonsPlayed', None) or {}
    count = sum(1 for pid in (ctx.rosterPlayerIds or set())
                if sp.get(pid, 0) >= 5)
    if count == 0:
        return EffectResult(multBonus=1.0, equation="No 5+ season veterans on roster")
    mult = min(maxMult, round(1.0 + perVetMult * count, 2))
    delta = round(mult - 1.0, 2)
    eq = f"+{delta} FPx — {count} veteran{'s' if count != 1 else ''} (5+ seasons)"
    return EffectResult(multBonus=mult, equation=eq)


def _computeRange(primary, ctx, cardPlayerId, eqId):
    """FP scaling with total FG yardage from roster K this week."""
    perYardFP = primary.get("perYardFP", 0.3)
    kickerPids = [pid for pid in (ctx.rosterPlayerIds or set())
                  if (ctx.rosterPlayerPositions or {}).get(pid) == 5]
    totalYards = 0
    for pid in kickerPids:
        ps = (ctx.weekPlayerStats or {}).get(pid, {})
        kStats = ps.get("kicking_stats", {}) if isinstance(ps.get("kicking_stats"), dict) else {}
        totalYards += int(kStats.get("fgYards", 0) or 0)
    fp = round(perYardFP * totalYards, 1)
    eq = f"{perYardFP}/yd × {totalYards} K FG yards = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeCornerstone(primary, ctx, cardPlayerId, eqId):
    """FPx delta per roster player ranked #1 at their position by season
    FP/game. Up to 5 max (QB/RB/WR/TE/K — one #1 per position). Active
    from week 3 once enough season data exists."""
    perPlayerMult = primary.get("perPlayerMult", 0.10)
    maxMult = primary.get("maxMult", 1.50)
    weekNum = getattr(ctx, 'weekNumber', 0)
    if weekNum < 3:
        return EffectResult(multBonus=1.0, equation="Inactive until week 3 (need season data)")
    top1 = getattr(ctx, 'top1PerPosition', {}) or {}
    if not top1:
        return EffectResult(multBonus=1.0, equation="Leaderboard not yet populated")
    positions = ctx.rosterPlayerPositions or {}
    count = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if positions.get(pid) and pid in top1.get(positions[pid], set())
    )
    if count == 0:
        return EffectResult(multBonus=1.0, equation="No roster player ranks #1 at their position")
    mult = min(maxMult, round(1.0 + perPlayerMult * count, 2))
    delta = round(mult - 1.0, 2)
    eq = f"+{delta:.2f} FPx — {count} position leader{'s' if count != 1 else ''}"
    return EffectResult(multBonus=mult, equation=eq)


def _computeLoyalty(primary, ctx, cardPlayerId, eqId):
    """FP per player still fielded from the user's INITIAL equipped set this
    season (fusion: the roster IS the equipped cards). Rewards keeping the
    originals equipped through the season."""
    perPlayerFP = primary.get("perPlayerFP", 12)
    initial = getattr(ctx, 'initialRosterPlayerIds', None) or set()
    if not initial:
        return EffectResult(equation="Initial roster snapshot not set yet")
    current = ctx.rosterPlayerIds or set()
    loyal = current & initial
    count = len(loyal)
    fp = round(perPlayerFP * count, 1)
    eq = f"{perPlayerFP}/player × {count} originals still rostered = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


# ── Prognostication cards ──────────────────────────────────────────────────

def _computeMedium(primary, ctx, cardPlayerId, eqId):
    """Weekly Prognostication accuracy bonus.

    Thresholds tuned for a 70% season-long user accuracy average — the
    65-84% band catches the typical "good week," ~55% of weeks land there.
      - 50% to 64%: lowFP (below-average week)
      - 65% to 84%: midFP (typical hit zone)
      - 85%+: highFP (chase tier, ~15% of weeks)
    Counts auto-picks. Returns no output if the user submitted nothing.
    """
    correct = int(getattr(ctx, 'userWeeklyPickemCorrect', 0) or 0)
    total = int(getattr(ctx, 'userWeeklyPickemTotal', 0) or 0)
    if total <= 0:
        if getattr(ctx, 'gamesActive', False):
            return EffectResult(equation="Waiting for game results")
        return EffectResult(equation="No Prognostications submitted this week")
    accuracy = correct / total
    lowFP = primary.get("lowFP", 4.0)
    midFP = primary.get("midFP", 10.0)
    highFP = primary.get("highFP", 20.0)
    if accuracy >= 0.85:
        fp = highFP
        tier = "85%+"
    elif accuracy >= 0.65:
        fp = midFP
        tier = "65%+"
    elif accuracy >= 0.50:
        fp = lowFP
        tier = "50%+"
    else:
        return EffectResult(equation=f"{correct}/{total} picks ({accuracy:.0%}) — below 50% threshold")
    eq = f"{correct}/{total} picks ({accuracy:.0%}) — {tier} = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeParlay(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with weekly Prognostication points via log-taper.

    Same shape as Cornucopia: mult = baseXMult + coef × ln(1 + pts/kPoints).
    Counts auto-picks. Returns 1.0x when the user submitted no picks.
    """
    import math
    points = int(getattr(ctx, 'userWeeklyPickemPoints', 0) or 0)
    baseXMult = primary.get("baseXMult", 1.0)
    coef = primary.get("coef", 0.10)
    k = primary.get("kPoints", 40)
    if points <= 0:
        if getattr(ctx, 'gamesActive', False):
            return EffectResult(multBonus=baseXMult, equation="Waiting for game results")
        return EffectResult(multBonus=baseXMult, equation="No Prognostication points this week")
    mult = baseXMult + coef * math.log(1 + points / k)
    mult = round(mult, 2)
    delta = round(mult - 1.0, 2)
    eq = f"{coef:.2f} × ln(1 + {points}/{k}) = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


# ── Streak (K) ───────────────────────────────────────────────────────────────

def _computeStreakEffect(primary, ctx, cardPlayerId, eqId):
    """Generic streak computation with locked-base carryover.

    Carried base (peak_output) semantics:
    - First-ever streak: peak_output is None → carriedBase = baseReward.
    - During an active streak: peak_output is LOCKED at the value held
      when the streak began. It does not change while the streak runs.
    - When a streak breaks: the post-calc step writes peak_output =
      carriedBase + growth × (priorCount - 1), the peak the streak
      actually achieved. The break-week output also pays that peak.
    - During continuing cold weeks: peak_output decays one step per
      week (post-calc, multiplicative). Compute pays current peak_output.
    - When a new streak begins: peak_output stays locked at its current
      (decayed) value for the duration of the new streak.

    Decay: 0.85 for FPx cards (narrow range), 0.7 for flat-FP/floobits.
    Floor: peak_output is cleared to None when it falls to ≤ baseReward.
    """
    streakConfig = STREAK_CONFIGS.get(ctx._currentEffectName, {})
    isWeekly = streakConfig.get("isWeekly", False)

    # Inverse-streak cards (Drought / Sandbagger / Quiet Storm) need a
    # near-full roster — they're meant for "field a team of bad players"
    # not "gut your roster to easily clear the under-50 / under-5 / no-15
    # bars." Empty payout when below the filled-slot threshold.
    if ctx._currentEffectName in _FULL_ROSTER_INTENT_EFFECTS and not _meetsFullRosterRequirement(ctx):
        return EffectResult(
            equation=f"Requires {_FULL_ROSTER_MIN_FILLED}+ rostered players"
        )

    baseReward = primary.get("baseReward", 0)
    growthPerTick = primary.get("growthPerTick", 0)

    if isWeekly:
        # Weekly streaks: count ticks from this week's data
        ticks = _countWeeklyTicks(ctx._currentEffectName, primary, ctx)
        totalReward = sum(baseReward + growthPerTick * i for i in range(ticks))
        eq = f"{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)"
        result = _streakReward(primary, totalReward)
        result.equation = eq
        return result

    # Season streaks: live-aware computation
    streakCount = ctx.streakCounts.get(eqId, 1)
    conditionMet = ctx.liveStreakConditionsMet.get(eqId, True)

    storedBase = ctx.streakPeakOutputs.get(eqId)
    if storedBase is not None and storedBase > baseReward:
        carriedBase = storedBase
    else:
        carriedBase = baseReward

    if not conditionMet:
        if streakCount > 0:
            # Streak just broke this week. Pay the peak the streak achieved:
            # carriedBase (the locked base) + growth × (priorCount - 1).
            peakOutput = carriedBase + growthPerTick * (streakCount - 1)
            result = _streakReward(primary, peakOutput)
            result.equation = f"{round(peakOutput, 2)} (streak broke, paying peak)"
            return result
        # Continuing cold week — pay current carried base (already decayed
        # one step per prior cold week via post-calc).
        result = _streakReward(primary, carriedBase)
        if carriedBase > baseReward:
            result.equation = f"{round(carriedBase, 2)} (carried base, decaying)"
        else:
            result.equation = f"{baseReward} base"
        return result

    # Active streak — carriedBase is locked.
    peerBonus = max(0, getattr(ctx, 'streakCardCount', 1) - 1)
    effectiveCount = streakCount + peerBonus

    # Log-tapered streaks (Conviction): set when `coef` is in primary.
    # output = carriedBase + coef × ln(1 + effectiveCount / kStreak)
    # Naturally plateaus on long streaks rather than scaling linearly.
    if "coef" in primary:
        import math
        coef = primary.get("coef", 0.0)
        kStreak = primary.get("kStreak", 4)
        totalReward = carriedBase + coef * math.log(1 + effectiveCount / kStreak)
        if peerBonus > 0:
            eq = f"{round(carriedBase, 2)} + {coef} × ln(1 + {effectiveCount}/{kStreak}) [{streakCount} wk + {peerBonus} synergy]"
        else:
            eq = f"{round(carriedBase, 2)} + {coef} × ln(1 + {streakCount}/{kStreak})"
        result = _streakReward(primary, totalReward)
        result.equation = eq
        return result

    growthTicks = max(0, effectiveCount - 1)
    totalReward = carriedBase + growthPerTick * growthTicks
    baseLabel = "base" if carriedBase == baseReward else "carried base"
    if peerBonus > 0:
        eq = f"{round(carriedBase, 2)} {baseLabel} + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])"
    else:
        eq = f"{round(carriedBase, 2)} {baseLabel} + ({growthPerTick}/streak × {max(0, streakCount - 1)})"
    result = _streakReward(primary, totalReward)
    result.equation = eq
    return result


def _countWeeklyTicks(effectName, primary, ctx):
    """Count ticks for weekly-reset streaks. Always returns int —
    projection contexts can carry float per-game averages for TD counts."""
    if effectName == "touchdown_jackpot":
        try:
            return int(round(float(ctx.rosterTotalTds or 0)))
        except Exception:
            return 0
    return 0


def _computeOdometer(primary, ctx, cardPlayerId, eqId):
    """Yard gates with escalating payouts, re-based off the whole roster to THIS
    player's own yards — so the gates are single-player scale (a good game clears a
    few), not roster scale."""
    stats = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}) or {}
    totalYards = (
        (stats.get("passing_stats", {}) or {}).get("passYards", 0)
        + (stats.get("rushing_stats", {}) or {}).get("runYards", 0)
        + (stats.get("receiving_stats", {}) or {}).get("rcvYards", 0)
    )
    # Single-player gates (roster gates were 200/400/600/800); re-tuned so a strong
    # individual game clears the lower ones and a monster game clears them all.
    gates = primary.get("gatesSolo") or []
    if not gates:
        baseReward = primary.get("baseReward", 5.0)
        growth = primary.get("growthPerTick", 6.0)
        gates = [
            {"yards": 40, "fp": round(baseReward, 1)},
            {"yards": 80, "fp": round(baseReward + growth, 1)},
            {"yards": 120, "fp": round(baseReward + growth * 2, 1)},
            {"yards": 160, "fp": round(baseReward + growth * 3, 1)},
        ]
    totalFP = 0
    gatesHit = 0
    gateDetails = []
    for gate in gates:
        yardThreshold = gate.get("yards", 100)
        gateFP = gate.get("fp", 2.0)
        if totalYards >= yardThreshold:
            totalFP += gateFP
            gatesHit += 1
            gateDetails.append(f"{yardThreshold}yd=+{gateFP}")
    if gatesHit == 0:
        nextGate = gates[0] if gates else {"yards": 50}
        eq = f"{totalYards} yds — next gate at {nextGate['yards']}"
        return EffectResult(equation=eq)
    nextIdx = gatesHit
    if nextIdx < len(gates):
        nextLabel = f" — next gate at {gates[nextIdx]['yards']}yd"
    else:
        nextLabel = " — all gates cleared!"
    totalFP = round(totalFP, 1)
    eq = f"{totalYards} yds: {', '.join(gateDetails)} = +{totalFP} FP{nextLabel}"
    return EffectResult(fpBonus=totalFP, equation=eq)


def _getRosterTotalYards(ctx):
    """Sum all yards (passing + rushing + receiving) from roster players."""
    totalYards = 0
    for pid in ctx.rosterPlayerIds:
        stats = ctx.weekPlayerStats.get(pid, {})
        passing = stats.get("passing_stats", {})
        rushing = stats.get("rushing_stats", {})
        receiving = stats.get("receiving_stats", {})
        if isinstance(passing, dict):
            totalYards += passing.get("passYards", 0)
        if isinstance(rushing, dict):
            totalYards += rushing.get("runYards", 0)
        if isinstance(receiving, dict):
            totalYards += receiving.get("rcvYards", 0)
    return totalYards


def _streakReward(primary, totalReward) -> EffectResult:
    """Convert streak reward to EffectResult based on rewardType.
    Mult totalReward is a factor >1 (e.g. 1.3 = ×1.3)."""
    rewardType = primary.get("rewardType", "fp")
    if rewardType == "fp":
        return EffectResult(fpBonus=totalReward)
    elif rewardType == "mult":
        return EffectResult(multBonus=totalReward)
    elif rewardType == "floobits":
        return EffectResult(floobits=int(totalReward))
    return EffectResult()


# ── Stat Lookup Helper ───────────────────────────────────────────────────────

CONDITIONAL_STAT_MAP = {
    "passYards": ("passing_stats", "passYards"),
    "passTds":   ("passing_stats", "tds"),
    "rushYards": ("rushing_stats", "runYards"),
    "rushTds":   ("rushing_stats", "runTds"),
    "recYards":  ("receiving_stats", "rcvYards"),
    "recTds":    ("receiving_stats", "rcvTds"),
    "fgMade":    ("kicking_stats", "fgs"),
    "longFg":    ("kicking_stats", "longest"),
}


def _getStatValue(playerStats: dict, statKey: str) -> float:
    """Look up a stat value from a player's weekly stats."""
    mapping = CONDITIONAL_STAT_MAP.get(statKey)
    if not mapping:
        return 0
    column, subKey = mapping
    statsJson = playerStats.get(column)
    if not statsJson or not isinstance(statsJson, dict):
        return 0
    return statsJson.get(subKey, 0)


# ── New Position-Based Effects ────────────────────────────────────────────────

def _computeGunslinger(primary, ctx, cardPlayerId, eqId):
    """FP per well-placed ball by this player.

    Was pass yards; re-pointed onto the goodThrows counter so the marksmanship name
    matches the stat. Falls back to the old param so any card minted before the change
    still scores its original effect rather than silently reading zero.
    """
    per = primary.get("perGoodThrowFP")
    if per is None:
        legacy = primary.get("perHundredYardsFP", 6.0)
        yards = _ladderStat(ctx, cardPlayerId, "passing_stats", "passYards")
        fp = round(legacy * yards / 100.0, 1)
        return EffectResult(fpBonus=fp, equation=f"{legacy} FP/100yds x {yards} pass yds")
    good = _ladderStat(ctx, cardPlayerId, "passing_stats", "goodThrows")
    return EffectResult(fpBonus=round(per * good, 1),
                        equation=f"{per}/throw x {good} well-placed")


def _computeAirRaid(primary, ctx, cardPlayerId, eqId):
    """Floobits per QB slot passing TD."""
    perTdF = primary.get("perTdFloobits", 12)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    tds = stats.get("passing_stats", {}).get("tds", 0) if isinstance(stats.get("passing_stats"), dict) else 0
    floobits = int(perTdF * tds)
    eq = f"{perTdF}F/TD × {tds} QB pass TD{'s' if tds != 1 else ''}"
    return EffectResult(floobits=floobits, equation=eq)


def _computeWorkhorse(primary, ctx, cardPlayerId, eqId):
    """FP scaling with RB slot's rushing attempts."""
    perAttFP = primary.get("perAttemptFP", 0.8)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    attempts = stats.get("rushing_stats", {}).get("carries", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    fp = round(perAttFP * attempts, 1)
    eq = f"{perAttFP} FP/att × {attempts} rush attempts = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeExpedition(primary, ctx, cardPlayerId, eqId):
    """FP scaling with RB slot's rushing yards."""
    perFiftyFP = primary.get("perFiftyYardsFP", 2.5)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    rushYards = stats.get("rushing_stats", {}).get("runYards", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    chunks = rushYards / 50.0
    fp = round(perFiftyFP * chunks, 1)
    eq = f"{perFiftyFP} FP/50yds × {rushYards} rush yds = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeStampede(primary, ctx, cardPlayerId, eqId):
    """Base FPx always, enhanced FPx when RB slot hits rushing yard threshold."""
    baseMult = primary.get("baseMult", 1.08)
    enhancedMult = primary.get("enhancedMult", 1.25)
    threshold = primary.get("yardThreshold", 75)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    rushYards = stats.get("rushing_stats", {}).get("runYards", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    if rushYards >= threshold:
        eq = f"+{enhancedMult - 1.0:.2f} FPx ({rushYards} rush yds >= {threshold})"
        return EffectResult(multBonus=enhancedMult, equation=eq)
    eq = f"+{baseMult - 1.0:.2f} FPx (base — {rushYards} rush yds < {threshold})"
    return EffectResult(multBonus=baseMult, equation=eq)


def _computeGoalLineVulture(primary, ctx, cardPlayerId, eqId):
    """Floobits per RB slot rushing TD."""
    perTd = primary.get("perTdFloobits", 4)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    tds = stats.get("rushing_stats", {}).get("runTds", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    floobits = int(perTd * tds)
    eq = f"{perTd}/TD × {tds} RB rush TDs"
    return EffectResult(floobits=floobits, equation=eq)


def _computePossession(primary, ctx, cardPlayerId, eqId):
    """FP scaling with WR slots' combined receptions."""
    perRec = primary.get("perReceptionFP", 0.5)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    recs = stats.get("receiving_stats", {}).get("receptions", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    bonus = round(perRec * recs, 1)
    eq = f"{perRec}/rec × {recs} receptions"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeDeepThreat(primary, ctx, cardPlayerId, eqId):
    """Base FP always, bonus FP if either WR slot catches a 25+ yard pass."""
    baseFP = primary.get("baseFP", 3.0)
    bonusFP = primary.get("rewardValue", 8)
    threshold = primary.get("threshold", 25)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    bestCatch = 0
    rcvStats = stats.get("receiving_stats", {})
    if isinstance(rcvStats, dict):
        bestCatch = rcvStats.get("longest", 0) or rcvStats.get("longestRec", 0)
    if bestCatch >= threshold:
        total = round(baseFP + bonusFP, 1)
        eq = f"{baseFP} base + {bonusFP} bonus (longest catch: {bestCatch} yd)"
        return EffectResult(fpBonus=total, equation=eq)
    eq = f"{baseFP} base (longest catch: {bestCatch}/{threshold} yd)"
    return EffectResult(fpBonus=baseFP, equation=eq)


def _computeDoubleTrouble(primary, ctx, cardPlayerId, eqId):
    """Tiered WR TD bonus: moderate FP for one WR scoring, big bonus when both score."""
    singleFP = primary.get("singleWrFP", 6)
    bothFP = primary.get("rewardValue", 14)
    pids = _getRosterPlayersByPosition(ctx, ctx.cardPosition or 3)
    wrWithTd = 0
    for pid in pids:
        stats = ctx.weekPlayerStats.get(pid, {})
        if _countPlayerTds(stats) > 0:
            wrWithTd += 1
    if wrWithTd >= 2:
        total = singleFP + bothFP
        eq = f"+{singleFP} FP (1st WR TD) + {bothFP} FP (2nd WR TD) = +{total} FP"
        return EffectResult(fpBonus=total, equation=eq)
    if wrWithTd == 1:
        eq = f"+{singleFP} FP (1 WR scored — need both for +{bothFP} bonus)"
        return EffectResult(fpBonus=singleFP, equation=eq)
    eq = "No WR TDs this week"
    return EffectResult(equation=eq)


def _computeSlippery(primary, ctx, cardPlayerId, eqId):
    """FP scaling with WR slots' combined YAC."""
    perYac = primary.get("perYacFP", 0.3)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    yac = stats.get("receiving_stats", {}).get("yac", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    bonus = round(perYac * (yac / 10), 1)
    eq = f"{perYac}/10yac × {yac} YAC"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeYacAttack(primary, ctx, cardPlayerId, eqId):
    """Base FP always, bonus FP when WR slots combine for threshold+ YAC."""
    baseFP = primary.get("baseFP", 3.0)
    bonusFP = primary.get("rewardValue", 7)
    threshold = primary.get("threshold", 30)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    yac = stats.get("receiving_stats", {}).get("yac", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    if yac >= threshold:
        total = round(baseFP + bonusFP, 1)
        eq = f"{baseFP} base + {bonusFP} bonus ({yac} YAC >= {threshold})"
        return EffectResult(fpBonus=total, equation=eq)
    eq = f"{baseFP} base ({yac}/{threshold} YAC)"
    return EffectResult(fpBonus=baseFP, equation=eq)



def _computeSafetyBlanket(primary, ctx, cardPlayerId, eqId):
    """FP scaling with TE slot's receptions."""
    perRec = primary.get("perReceptionFP", 0.6)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    recs = stats.get("receiving_stats", {}).get("receptions", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    bonus = round(perRec * recs, 1)
    eq = f"{perRec}/rec × {recs} TE receptions"
    return EffectResult(fpBonus=bonus, equation=eq)



def _computeLeadBlocker(primary, ctx, cardPlayerId, eqId):
    """FP per TE TD, where same-team RB rushing TDs count as TE TDs."""
    perTd = primary.get("perTdFP", 4.0)
    tePids = _getRosterPlayersByPosition(ctx, 4)  # TE slot
    rbPids = _getRosterPlayersByPosition(ctx, 2)  # RB slot
    # Count TE's own TDs
    teTds = 0
    for tePid in tePids:
        teTds += _countPlayerTds(ctx.weekPlayerStats.get(tePid, {}))
    # Count same-team RB rushing TDs that credit to the TE
    rbTds = 0
    for tePid in tePids:
        teTeam = ctx.rosterPlayerTeamIds.get(tePid, 0)
        if not teTeam:
            continue
        for rbPid in rbPids:
            if ctx.rosterPlayerTeamIds.get(rbPid, 0) == teTeam:
                rbStats = ctx.weekPlayerStats.get(rbPid, {})
                rushGroup = rbStats.get("rushing_stats")
                if isinstance(rushGroup, dict):
                    rbTds += rushGroup.get("runTds", 0)
    totalTds = teTds + rbTds
    if totalTds > 0:
        bonus = round(perTd * totalTds, 1)
        parts = []
        if teTds:
            parts.append(f"{teTds} TE")
        if rbTds:
            parts.append(f"{rbTds} RB")
        eq = f"{perTd}/TD × {totalTds} TDs ({' + '.join(parts)})"
        return EffectResult(fpBonus=bonus, equation=eq)
    return EffectResult(equation="No TDs by TE or same-team RBs")


def _computeChainMover(primary, ctx, cardPlayerId, eqId):
    """Floobits scaling with TE slot's receptions."""
    perRec = primary.get("perReceptionFloobits", 3)
    stats = _getRosterStatsAtPosition(ctx, 4)
    recs = stats.get("receiving_stats", {}).get("receptions", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    bonus = int(perRec * recs)
    eq = f"{perRec}F/rec × {recs} TE receptions"
    return EffectResult(floobits=bonus, equation=eq)


def _computeMismatch(primary, ctx, cardPlayerId, eqId):
    """FP per roster TD at card position, plus a bonus when threshold met."""
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    perTdFP = primary.get("perTdFP", 5)
    bonusFP = primary.get("bonusFP", 8)
    tdThreshold = primary.get("tdThreshold", 2)
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    tds = _countPlayerTds(stats)
    perTdPayout = round(perTdFP * tds, 1)
    if tds >= tdThreshold:
        total = round(perTdPayout + bonusFP, 1)
        eq = f"{perTdFP}/TD × {tds} {posLabel} TDs + {bonusFP} bonus = +{total} FP"
        return EffectResult(fpBonus=total, equation=eq)
    if tds > 0:
        eq = f"{perTdFP}/TD × {tds} {posLabel} TDs = +{perTdPayout} FP ({tdThreshold - tds} more for +{bonusFP} bonus)"
        return EffectResult(fpBonus=perTdPayout, equation=eq)
    return EffectResult(equation=f"no {posLabel} TDs ({tdThreshold} for bonus)")


def _computeSniper(primary, ctx, cardPlayerId, eqId):
    """FP per 40+ yard FG by K slot."""
    perFg = primary.get("perFgFP", 2)
    _, _, _, fg40plus = _getKickerFgStats(ctx)
    bonus = round(perFg * fg40plus, 1)
    eq = f"{perFg}/FG × {fg40plus} FGs 40+ yds"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeBoomWeek(primary, ctx, cardPlayerId, eqId):
    """FP scaling with how much THIS CARD'S player overperformed this week."""
    if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    bestOver = (ctx.gamePerformanceRatings.get(cardPlayerId, 0)
                - ctx.rosterPlayerRatings.get(cardPlayerId, 60))
    if bestOver <= 0:
        return EffectResult(equation="Did not overperform")
    # New FP path
    perPointFP = primary.get("perPointFP", 0)
    if perPointFP:
        bonus = round(perPointFP * bestOver, 1)
        return EffectResult(fpBonus=bonus, equation=f"Overperformed — +{bonus} FP")
    # Legacy FPx path
    perPoint = primary.get("perPointOver", 0.02)
    bonus = round(1 + perPoint * bestOver, 2)
    return EffectResult(multBonus=bonus, equation=f"Overperformed — +{bonus - 1.0:.2f} FPx")


def _computeDudInsurance(primary, ctx, cardPlayerId, eqId):
    """Chance card: base Floobits always + chance of enhanced (scales with underperformance)."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFloobits = primary.get("baseFloobits", 2)
    enhancedFloobits = primary.get("enhancedFloobits", 10)
    # Legacy fallback
    if "baseFloobits" not in primary and "perPointUnder" in primary:
        if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
            return EffectResult(equation="Waiting for games to complete")
        perPoint = primary["perPointUnder"]
        worstUnder = (ctx.rosterPlayerRatings.get(cardPlayerId, 60)
                      - ctx.gamePerformanceRatings.get(cardPlayerId, 0))
        if worstUnder > 0:
            floobits = int(perPoint * worstUnder)
            return EffectResult(floobits=floobits, equation=f"Underperformed — +{floobits} Floobits")
        return EffectResult(equation="Did not underperform")
    if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    worstUnder = (ctx.rosterPlayerRatings.get(cardPlayerId, 60)
                  - ctx.gamePerformanceRatings.get(cardPlayerId, 0))
    if worstUnder <= 0:
        return EffectResult(floobits=baseFloobits, equation=f"+{baseFloobits}F. Did not underperform")
    baseChance = min(0.85, worstUnder * 0.030 + 0.100)
    totalChance = min(0.97, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    floobitsVal = enhancedFloobits if triggered else baseFloobits
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFloobits}F", "underperformed", ctx=ctx, base=f"+{baseFloobits}F")
    return EffectResult(floobits=floobitsVal, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


# ── Escalating / Pace Effects ────────────────────────────────────────────────

def _getPositionTds(ctx, position: int, cardPlayerId: int = 0) -> int:
    """Get TDs relevant to position for the CARD'S OWN player. Always returns int
    so callers that iterate range(tds) don't choke on the float per-game
    averages the projection context feeds in (e.g., 0.7 TDs/game).

    Position selects WHICH stat counts (passing / rushing / receiving / FGs);
    cardPlayerId selects WHOSE. Falls back to the position lookup when no card
    player is supplied, for any legacy caller."""
    stats = (_getCardPlayerStats(ctx, cardPlayerId) if cardPlayerId
             else _getRosterStatsAtPosition(ctx, position))
    raw = 0
    if position == 1:  # QB — passing TDs
        raw = stats.get("passing_stats", {}).get("tds", 0) if isinstance(stats.get("passing_stats"), dict) else 0
    elif position == 2:  # RB — rushing TDs
        raw = stats.get("rushing_stats", {}).get("runTds", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    elif position == 3:  # WR — receiving TDs
        raw = stats.get("receiving_stats", {}).get("rcvTds", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    elif position == 5:  # K — FGs made
        if cardPlayerId:
            ks = stats.get("kicking_stats", {})
            raw = ks.get("fgs", 0) if isinstance(ks, dict) else 0
        else:
            fgMade, _, _, _ = _getKickerFgStats(ctx)
            raw = fgMade
    try:
        return int(round(float(raw)))
    except Exception:
        return 0


def _getPositionYards(ctx, position: int, cardPlayerId: int = 0) -> int:
    """Get yards relevant to position for the CARD'S OWN player.

    Position selects WHICH yardage counts; cardPlayerId selects WHOSE."""
    stats = (_getCardPlayerStats(ctx, cardPlayerId) if cardPlayerId
             else _getRosterStatsAtPosition(ctx, position))
    if position == 1:  # QB — passing yards
        return stats.get("passing_stats", {}).get("passYards", 0) if isinstance(stats.get("passing_stats"), dict) else 0
    if position == 2:  # RB — rushing yards
        return stats.get("rushing_stats", {}).get("runYards", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    if position in (3, 4):  # WR/TE — receiving yards
        return stats.get("receiving_stats", {}).get("rcvYards", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    return 0


def _computeCrescendo(primary, ctx, cardPlayerId, eqId):
    """Escalating chance per TD/FG, one-time bonus per week.

    Each TD (or FG for K) rolls with increasing odds. First miss bumps the
    chance for the next trigger. Resets after hitting once.
    """
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 1.0)
    bonusFP = primary.get("bonusFP", 8.0)
    pos = ctx.cardPosition or 1
    baseChance, chanceStep = _CRESCENDO_POSITION_TUNING.get(pos, (20, 15))

    triggerLabel = "FGs" if pos == 5 else "TDs"
    triggers = _getPositionTds(ctx, pos, cardPlayerId)

    if triggers <= 0:
        eq = f"+{baseFP} FP. 0 {triggerLabel}"
        return EffectResult(fpBonus=baseFP, equation=eq)

    # During live games, show current escalated chance without rolling
    if getattr(ctx, 'gamesActive', False):
        currentBase = (baseChance + (triggers - 1) * chanceStep) / 100.0
        totalWithBonus = min(0.97, currentBase + ctx.chanceBonus)
        eq = _chanceEq(currentBase, ctx.chanceBonus, totalWithBonus, False,
                       f"+{bonusFP} FP", f"{triggers} {triggerLabel}", ctx=ctx, base=f"+{baseFP} FP")
        return EffectResult(fpBonus=baseFP, equation=eq)

    # At week end: simulate sequential rolls per trigger
    rng = _chanceRoll(ctx, eqId)
    hit = False
    hitOnTrigger = 0
    for i in range(triggers):
        chance = min(0.97, (baseChance + i * chanceStep) / 100.0 + ctx.chanceBonus)
        roll = rng.random()
        if roll <= chance:
            hit = True
            hitOnTrigger = i + 1
            break

    fp = bonusFP if hit else baseFP
    finalBase = (baseChance + (hitOnTrigger - 1 if hit else triggers - 1) * chanceStep) / 100.0
    finalChance = min(0.97, finalBase + ctx.chanceBonus)
    bonusStr = f"+{ctx.chanceBonus:.0%}" if ctx.chanceBonus > 0 else ""
    pctStr = f"({finalBase:.0%}{bonusStr})" if bonusStr else f"{finalChance:.0%}"
    if hit:
        eq = f"+{bonusFP} FP. Hit on {triggerLabel[:-1]} #{hitOnTrigger} of {triggers} ({pctStr})"
    else:
        eq = f"+{baseFP} FP. {triggers} {triggerLabel}, maxed at {pctStr}, missed"
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(rng.random(), 4), chanceThreshold=round(finalChance, 4), chanceTriggered=hit)


def _computeEminence(primary, ctx, cardPlayerId, eqId):
    """FPx delta per roster player ranked in the top 10 at their position
    (by season FP/game). Whole-roster scope — leaderboard rank is directly
    visible to the user. Active from week 3 once enough season data exists.
    """
    perPlayerMult = primary.get("perPlayerMult", 0.05)
    maxMult = primary.get("maxMult", 1.25)
    weekNum = getattr(ctx, 'weekNumber', 0)

    if weekNum < 3:
        return EffectResult(multBonus=1.0, equation="Inactive until week 3 (need season data)")

    top10 = getattr(ctx, 'top10PerPosition', {}) or {}
    if not top10:
        return EffectResult(multBonus=1.0, equation="Leaderboard not yet populated")

    positions = ctx.rosterPlayerPositions or {}
    count = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if positions.get(pid) and pid in top10.get(positions[pid], set())
    )
    if count == 0:
        return EffectResult(multBonus=1.0, equation="No roster player ranks top-10 at their position")

    mult = min(maxMult, round(1.0 + perPlayerMult * count, 2))
    delta = round(mult - 1.0, 2)
    eq = f"+{delta:.2f} FPx — {count} top-10 roster player{'s' if count != 1 else ''}"
    return EffectResult(multBonus=mult, equation=eq)


def _computeTraverse(primary, ctx, cardPlayerId, eqId):
    """End-of-game chance roll where odds scale with player yardage.

    Formula: baseChance + (yards / yardStep) * chancePerStep, capped at 95%.
    Single roll at game end.
    """
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 0.5)
    bonusFP = primary.get("bonusFP", 7.0)
    pos = ctx.cardPosition or 1
    yardStep, chancePerStep, yardType = _TRAVERSE_POSITION_TUNING.get(pos, (50, 8, "passing"))

    yards = _getPositionYards(ctx, pos, cardPlayerId)
    steps = int(yards // yardStep)
    baseChance = (primary.get("baseChance", 5) + steps * chancePerStep) / 100.0
    totalChance = min(0.97, baseChance + ctx.chanceBonus)

    if getattr(ctx, 'gamesActive', False):
        eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, False,
                       f"+{bonusFP} FP", f"{yards} {yardType} yds", ctx=ctx, base=f"+{baseFP} FP")
        return EffectResult(fpBonus=baseFP, equation=eq)

    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance
    fp = bonusFP if triggered else baseFP

    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{bonusFP} FP", f"{yards} {yardType} yds", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


# ── Chance Synergy Effects ───────────────────────────────────────────────────

def _computeAdvantage(primary, ctx, cardPlayerId, eqId):
    """Pure meta effect — no direct payout.

    The actual mechanic (roll-twice) is handled in _chanceRoll via ctx.hasAdvantage,
    set during the pre-scan in calculateWeekCardBonuses. This compute function
    just reports the status.
    """
    chanceCount = ctx.chanceCardCount
    if chanceCount > 0:
        eq = f"Active · {chanceCount} chance card{'s' if chanceCount != 1 else ''} rolling with advantage"
    else:
        eq = "No chance cards equipped — dormant"
    return EffectResult(equation=eq)


def _computeCatalyst(primary, ctx, cardPlayerId, eqId):
    """Dynamic chance boost from THIS player's FP (re-based off the roster) + small floobits base.

    Boost = (rosterFP - baseline) / fpPer1Pct / 100, capped at maxBoost.
    Also pays a flat floobits dividend.
    """
    # Re-based off roster FP to THIS player's FP, so the scale (baseline / per-1%)
    # drops from roster-wide to single-player.
    fpPer1Pct = primary.get("fpPer1PctSolo", 3)
    baseline = primary.get("baselineSolo", 12)
    maxBoost = primary.get("maxBoost", 0.10)
    baseFloobits = primary.get("baseFloobits", 3)
    playerFP = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}).get("fantasyPoints", 0) or 0

    if playerFP > baseline:
        boost = min(maxBoost, (playerFP - baseline) / fpPer1Pct / 100)
    else:
        boost = 0.0

    eq = f"{playerFP:.1f} FP · +{boost:.1%} chance boost · {baseFloobits}F"
    return EffectResult(floobits=baseFloobits, equation=eq)


# ── Same-Team Stacking Effects ───────────────────────────────────────────────

def _getSameTeamGroups(ctx) -> Dict[int, List[int]]:
    """Group roster players by their team. Returns {teamId: [pid, ...]}."""
    groups: Dict[int, List[int]] = {}
    for pid in ctx.rosterPlayerIds:
        teamId = ctx.rosterPlayerTeamIds.get(pid, 0)
        if teamId:
            groups.setdefault(teamId, []).append(pid)
    return groups


def _computeStack(primary, ctx, cardPlayerId, eqId):
    """FPx if QB slot and any WR slot share a team."""
    rewardValue = primary.get("rewardValue", 1.3)
    qbPids = _getRosterPlayersByPosition(ctx, 1)
    wrPids = _getRosterPlayersByPosition(ctx, 3)
    for qbPid in qbPids:
        qbTeam = ctx.rosterPlayerTeamIds.get(qbPid, 0)
        if qbTeam:
            for wrPid in wrPids:
                if ctx.rosterPlayerTeamIds.get(wrPid, 0) == qbTeam:
                    eq = f"+{(rewardValue - 1):.2f} FPx (QB + WR on same team)"
                    return EffectResult(multBonus=rewardValue, equation=eq)
    eq = "QB and WR not on same team"
    return EffectResult(equation=eq)


def _computeBackfieldBuddies(primary, ctx, cardPlayerId, eqId):
    """FPx if QB slot and RB share a team."""
    rewardValue = primary.get("rewardValue", 0.3)
    qbPids = _getRosterPlayersByPosition(ctx, 1)
    rbPids = _getRosterPlayersByPosition(ctx, 2)
    for qbPid in qbPids:
        qbTeam = ctx.rosterPlayerTeamIds.get(qbPid, 0)
        if qbTeam:
            for rbPid in rbPids:
                if ctx.rosterPlayerTeamIds.get(rbPid, 0) == qbTeam:
                    eq = f"+{rewardValue:.2f} FPx (QB + RB on same team)"
                    return EffectResult(multBonus=1 + rewardValue, equation=eq)
    eq = "QB and RB not on same team"
    return EffectResult(equation=eq)


def _computeHomer(primary, ctx, cardPlayerId, eqId):
    """FPx delta per roster player on the user's favorite team."""
    perPlayerMult = primary.get("perPlayerMult", 0.05)
    maxMult = primary.get("maxMult", 1.30)
    favTeamId = ctx.userFavoriteTeamId
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.rosterPlayerTeamIds.get(pid, 0) == favTeamId) if favTeamId else 0
    mult = min(maxMult, round(1.0 + perPlayerMult * count, 2))
    delta = round(mult - 1.0, 2)
    eq = f"+{delta} FPx — {count} roster players on your favorite team"
    return EffectResult(multBonus=mult, equation=eq)


def _computeGoneStreaking(primary, ctx, cardPlayerId, eqId):
    """FP based on favorite team's longest win or loss streak this season."""
    baseFP = primary.get("baseFP", 2.0)
    perStreakFP = primary.get("perStreakFP", 0.8)
    peakStreak = getattr(ctx, 'favoriteTeamPeakStreak', 0)
    total = round(baseFP + perStreakFP * peakStreak, 1)
    eq = f"{baseFP} base + ({perStreakFP} × {peakStreak} peak streak)"
    return EffectResult(fpBonus=total, equation=eq)


def _computeHometownHero(primary, ctx, cardPlayerId, eqId):
    """Floobits if 3+ roster players share the same team."""
    rewardFloobits = primary.get("rewardFloobits", 15)
    groups = _getSameTeamGroups(ctx)
    for _, pids in groups.items():
        if len(pids) >= 3:
            eq = f"+{rewardFloobits}F ({len(pids)} players on same team)"
            return EffectResult(floobits=rewardFloobits, equation=eq)
    # Legacy FPx fallback
    if "rewardValue" in primary and "rewardFloobits" not in primary:
        rewardValue = primary["rewardValue"]
        for _, pids in groups.items():
            if len(pids) >= 3:
                return EffectResult(multBonus=rewardValue, equation=f"{rewardValue}x (legacy)")
    maxGroup = max((len(pids) for pids in groups.values()), default=0)
    eq = f"Max {maxGroup} on same team (need 3+)"
    return EffectResult(equation=eq)


# ── Card-to-Card Interaction Effects ─────────────────────────────────────────

# -- Hand Composition (first pass) --

def _computeFullRoster(primary, ctx, cardPlayerId, eqId):
    """Full House (Diamond): a big FPx, but only in a week where EVERY performing card
    in the lineup cleared its FP power bar. One cold player and it pays nothing.

    Under fusion the old "hand has all 5 positions" premise fired free (the position-locked
    base slots always span all 5). This re-bases it onto the power-bar gate: it fires only
    when all of the lineup's gated (effect-bearing) cards are ON this week. Runs second-pass
    (see _SECOND_PASS_EFFECTS) so every first-pass card's gate is already resolved; the
    calculator snapshots that outcome into ctx._firstPassGatedCount / _firstPassGatedOn
    before any second-pass card computes, so this reads a clean, order-independent tally of
    the first-pass value cards only (no-effect floor cards carry no gate and second-pass
    cross cards aren't counted). Full House's own gate (on its depicted player) is applied
    centrally afterward, so its own player must show up too.

    Scales its reward by the PRODUCT of the first-pass gate ratios. Live those ratios are
    1.0/0.0, so the product is exactly 1.0 (all cleared → full reward) or 0.0 (any cold →
    nothing). In the expected projection the ratios are fractional clear probabilities, so
    the product is the joint chance all of them clear and the reward becomes the true EV
    (instead of the old all-or-nothing on the season averages)."""
    rewardValue = primary.get("rewardValue", 2.5)
    gatedCount = int(getattr(ctx, "_firstPassGatedCount", 0) or 0)
    if gatedCount < _FULL_HOUSE_MIN_CARDS:
        eq = f"Need {_FULL_HOUSE_MIN_CARDS}+ performing cards in the lineup ({gatedCount})"
        return EffectResult(equation=eq)
    product = float(getattr(ctx, "_firstPassGateProduct", 0.0) or 0.0)
    if product <= 0.0:
        onCount = int(getattr(ctx, "_firstPassGatedOn", 0) or 0)
        cold = gatedCount - onCount
        eq = f"{onCount}/{gatedCount} cards cleared their bar ({cold} cold) — no bonus"
        return EffectResult(equation=eq)
    mult = round(1.0 + (rewardValue - 1.0) * product, 2)
    if product >= 0.999:
        eq = f"{rewardValue} (all {gatedCount} cards cleared their power bar)"
    else:
        eq = f"~{mult} expected ({round(product * 100)}% chance all {gatedCount} clear)"
    return EffectResult(multBonus=mult, equation=eq)


def _computeAllIn(primary, ctx, cardPlayerId, eqId):
    """All In / "Bet Big" (Prismatic): a one-player gamble.

    Under fusion the old "stack duplicate positions" premise fired free (WR1+WR2 are both
    WR, so every lineup showed a duplicate). Re-based onto the depicted player: the card's
    normal FP power-bar gate handles on/off, and THIS adds a higher STUD LINE that scales
    the payout — nothing until the player clears a genuinely big week, then FPx grows with
    every FP past the line (capped). An average starter pays nothing; a monster individual
    game pays big. Reads only the on-card player, so it stays a first-pass effect."""
    studLine = primary.get("studLine", 20)
    perFPx = primary.get("perFPx", 0.05)
    maxBonus = primary.get("maxXBonus", 1.4)
    stats = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}) or {}
    fp = float(stats.get("fantasyPoints", 0) or 0)
    over = fp - studLine
    if over <= 0:
        eq = f"{fp:.0f} FP, under {studLine} FP, no payout"
        return EffectResult(equation=eq)
    bonus = min(maxBonus, round(perFPx * over, 2))
    mult = round(1.0 + bonus, 2)
    eq = f"+{bonus:.2f} FPx ({fp:.0f} FP, +{over:.0f} over {studLine})"
    return EffectResult(multBonus=mult, equation=eq)


def _computeDiversified(primary, ctx, cardPlayerId, eqId):
    """+FP per unique output type in hand."""
    perType = primary.get("perTypeFP", 1.5)
    types = set(ctx.equippedCardOutputTypes)
    count = len(types)
    bonus = round(perType * count, 1)
    eq = f"{perType}/type × {count} unique output types"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeGoldRush(primary, ctx, cardPlayerId, eqId):
    """Floobits per other floobits card in hand."""
    perCard = primary.get("perCardFloobits", 3)
    floobitsCount = sum(1 for t in ctx.equippedCardOutputTypes if t == "floobits")
    # Subtract 1 for this card itself (if it's a floobits card)
    otherFloobits = max(0, floobitsCount - 1)
    floobits = int(perCard * otherFloobits)
    eq = f"{perCard}/card × {otherFloobits} other floobits cards"
    return EffectResult(floobits=floobits, equation=eq)


def _computeStackedDeck(primary, ctx, cardPlayerId, eqId):
    """Compounding FPx — each FPx card in hand multiplies the bonus.
    True 'multipliers on multipliers': (1 + perCardMult)^otherMults."""
    perCard = primary.get("perCardMult", 0.1)
    multCount = sum(1 for t in ctx.equippedCardOutputTypes if t == "mult")
    # Subtract 1 for this card itself
    otherMults = max(0, multCount - 1)
    mult = round((1 + perCard) ** otherMults, 2)
    delta = round(mult - 1.0, 2)
    if otherMults == 0:
        return EffectResult(multBonus=mult, equation="No other FPx cards in your hand")
    eq = (f"{otherMults} other FPx card{'s' if otherMults != 1 else ''} "
          f"compounding at +{perCard} = +{delta:.2f} FPx")
    return EffectResult(multBonus=mult, equation=eq)


# -- Trigger-Chain (second pass) --

def _computeCopycat(primary, ctx, cardPlayerId, eqId):
    """+FP equal to the highest flat FP bonus among other cards.

    Skips other Copycat cards in the read pool — otherwise two equipped
    Copycats cascade through the convergence pass, each copying the
    other's already-match-multiplied total and compounding the bonus.
    """
    breakdowns = list(ctx._firstPassBreakdowns or [])
    spBreakdowns = getattr(ctx, '_secondPassBreakdowns', None) or []
    spEqIds = getattr(ctx, '_secondPassEqIds', None) or []
    for spIdx, spEqId in enumerate(spEqIds):
        if spEqId != eqId and spIdx < len(spBreakdowns):
            breakdowns.append(spBreakdowns[spIdx])
    bestFP = 0
    for b in breakdowns:
        if b.effectName == "copycat":
            continue
        if b.totalFP > bestFP:
            bestFP = b.totalFP
    if bestFP > 0:
        eq = f"+{bestFP:.1f} FP (copied from best card)"
        return EffectResult(fpBonus=bestFP, equation=eq)
    eq = "No other cards produced FP"
    return EffectResult(equation=eq)


def _computeChainReaction(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with how many other cards produced a non-zero bonus."""
    perCard = primary.get("perCardXMult", 0.15)
    breakdowns = ctx._firstPassBreakdowns or []
    triggeredCount = sum(1 for b in breakdowns
                         if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
    preTriggers = getattr(ctx, '_secondPassPreTriggers', None) or {}
    triggeredCount += sum(1 for otherId, t in preTriggers.items() if otherId != eqId and t)
    if triggeredCount > 0:
        bonus = round(1 + perCard * triggeredCount, 2)
        delta = round(bonus - 1.0, 2)
        eq = f"+{perCard}/card × {triggeredCount} triggered cards = +{delta:.2f} FPx"
        return EffectResult(multBonus=bonus, equation=eq)
    eq = "No other cards triggered"
    return EffectResult(equation=eq)


_BONUS_ROUND_THRESHOLD = 6  # Fusion: raised 4->6. With a 6-7 card lineup, 4+ cards
                            # triggering was ~guaranteed; 6 means nearly the whole hand
                            # must pop, keeping it a real "everything fires" payoff.

_FULL_HOUSE_MIN_CARDS = 5   # Full House (full_roster) needs at least this many first-pass
                            # gated (effect) cards present AND all ON to fire. A full 6-slot
                            # effect lineup that includes Full House itself (second-pass, so
                            # not counted) leaves exactly 5 first-pass value cards, so this
                            # means "your other five slots all showed up." Fewer performing
                            # cards than this and it can't fire (you haven't fielded a full
                            # squad). See _computeFullRoster.


def _computeBonusRound(primary, ctx, cardPlayerId, eqId):
    """Large FP if 6+ other cards triggered a non-zero bonus."""
    rewardValue = primary.get("rewardValue", 8)
    threshold = _BONUS_ROUND_THRESHOLD
    breakdowns = ctx._firstPassBreakdowns or []
    triggeredCount = sum(1 for b in breakdowns
                         if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
    preTriggers = getattr(ctx, '_secondPassPreTriggers', None) or {}
    triggeredCount += sum(1 for otherId, t in preTriggers.items() if otherId != eqId and t)
    if triggeredCount >= threshold:
        eq = f"+{rewardValue} FP ({triggeredCount}/{threshold}+ cards triggered)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"{triggeredCount}/{threshold} cards triggered (need {threshold}+)"
    return EffectResult(equation=eq)


# -- Chance Synergy (second pass) --

def _computeHighRoller(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with how many chance cards triggered their enhanced payout."""
    perCardMult = primary.get("perCardMult", 0.10)
    breakdowns = list(ctx._firstPassBreakdowns or [])
    spBreakdowns = getattr(ctx, '_secondPassBreakdowns', None) or []
    spEqIds = getattr(ctx, '_secondPassEqIds', None) or []
    for spIdx, spEqId in enumerate(spEqIds):
        if spEqId != eqId and spIdx < len(spBreakdowns):
            breakdowns.append(spBreakdowns[spIdx])
    chanceTriggered = sum(1 for b in breakdowns if b.chanceTriggered)
    if chanceTriggered > 0:
        bonus = round(1 + perCardMult * chanceTriggered, 2)
        delta = round(bonus - 1.0, 2)
        eq = f"+{perCardMult}/hit × {chanceTriggered} chance hit{'s' if chanceTriggered != 1 else ''} = +{delta:.2f} FPx"
        return EffectResult(multBonus=bonus, equation=eq)
    eq = "No chance cards hit"
    return EffectResult(equation=eq)


def _computeDoubler(primary, ctx, cardPlayerId, eqId):
    """Pure amplifier — roster TD count is doubled in the pre-pass before any
    card computes. This stub marks the card present so the breakdown row
    renders with the amplifier-status pill."""
    return EffectResult(equation="TDs counted 2x for other card effects")


def _computeSurveyor(primary, ctx, cardPlayerId, eqId):
    """Pure amplifier — roster yards are scaled 1.5x in the pre-pass."""
    return EffectResult(equation="Yards counted 1.5x for other card effects")


def _computeSharpshooter(primary, ctx, cardPlayerId, eqId):
    """Pure amplifier — roster FGs are doubled in the pre-pass."""
    return EffectResult(equation="FGs counted 2x for other card effects")


def _computeCharmed(primary, ctx, cardPlayerId, eqId):
    """FP per chance card that triggered this week. The flat-FP twin of
    High Roller (which scales FPx). Second-pass — reads first-pass results."""
    perTriggerFP = primary.get("perTriggerFP", 15.0)
    breakdowns = list(ctx._firstPassBreakdowns or [])
    spBreakdowns = getattr(ctx, '_secondPassBreakdowns', None) or []
    spEqIds = getattr(ctx, '_secondPassEqIds', None) or []
    for spIdx, spEqId in enumerate(spEqIds):
        if spEqId != eqId and spIdx < len(spBreakdowns):
            breakdowns.append(spBreakdowns[spIdx])
    chanceTriggered = sum(1 for b in breakdowns if b.chanceTriggered)
    if chanceTriggered == 0:
        return EffectResult(equation="No chance cards hit this week")
    fp = round(perTriggerFP * chanceTriggered, 1)
    eq = f"{perTriggerFP}/hit × {chanceTriggered} chance hit{'s' if chanceTriggered != 1 else ''} = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


# -- Streak Synergy (second pass) --

def _computeIronWill(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with how many streak cards have active streaks."""
    perCardMult = primary.get("perCardMult", 0.10)
    activeStreaks = getattr(ctx, 'activeStreakCount', 0)
    if activeStreaks > 0:
        bonus = round(1 + perCardMult * activeStreaks, 2)
        delta = round(bonus - 1.0, 2)
        eq = f"+{perCardMult}/streak × {activeStreaks} active streaks = +{delta:.2f} FPx"
        return EffectResult(multBonus=bonus, equation=eq)
    eq = "No active streak cards"
    return EffectResult(equation=eq)


# -- Tradeoff/Sacrifice (second pass) --
# Note: Lemons and Feast or Famine are handled by _applyTradeoffEffects
# in cardEffectCalculator.py. Their compute functions just return their FPx
# value as a marker — the actual tradeoff logic modifies other breakdowns.

def _computeLemons(primary, ctx, cardPlayerId, eqId):
    """Multiplies the lowest non-zero card's FP. Amplification applied post-calculation."""
    rewardValue = primary.get("rewardValue", 2.5)
    breakdowns = ctx._firstPassBreakdowns or []
    nonZeroFP = [b for b in breakdowns if b.totalFP > 0 and b.effectName != "double_down"]
    if nonZeroFP:
        # Use the same "× N" notation as the affected card's tag in
        # _applyTradeoffEffects (cardEffectCalculator.py). Avoids the
        # earlier mismatch where this row said "+1.50 FPx" while the
        # impacted card showed "× 2.5" — same operation, two formats.
        eq = f"× {rewardValue} on your lowest-earning card"
        return EffectResult(multBonus=rewardValue, equation=eq)
    eq = "No FP-earning cards to amplify"
    return EffectResult(equation=eq)


def _computeLastResort(primary, ctx, cardPlayerId, eqId):
    """Chance card: base FP always + chance of enhanced FP (scales with failed card count)."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 5)
    enhancedFP = primary.get("enhancedFP", 20)
    # Legacy fallback
    if "baseFP" not in primary and "rewardValue" in primary:
        rewardValue = primary["rewardValue"]
        breakdowns = ctx._firstPassBreakdowns or []
        anyTriggered = any(b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0 for b in breakdowns)
        if not anyTriggered:
            eq = f"+{rewardValue - 1.0:.2f} FPx (no other cards produced a bonus)"
            return EffectResult(multBonus=rewardValue, equation=eq)
        triggeredCount = sum(1 for b in breakdowns if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
        eq = f"{triggeredCount} other card(s) produced a bonus"
        return EffectResult(equation=eq)
    if "baseFP" not in primary and "baseMult" in primary:
        baseMult = primary["baseMult"]
        return EffectResult(multBonus=baseMult, equation=f"+{baseMult - 1.0:.2f} FPx (legacy)")
    breakdowns = ctx._firstPassBreakdowns or []
    failedCount = sum(1 for b in breakdowns if b.totalFP <= 0 and b.floobitsEarned <= 0 and b.primaryMult <= 0)
    preTriggers = getattr(ctx, '_secondPassPreTriggers', None) or {}
    failedCount += sum(1 for otherId, t in preTriggers.items() if otherId != eqId and not t)
    from constants import CARD_CHANCE_CONDITION_FULL_COUNT
    conditionFill = failedCount / CARD_CHANCE_CONDITION_FULL_COUNT
    odds = _chanceOdds(ctx, cardPlayerId, conditionFill, useFP=True)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= odds and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceBarEq(ctx, odds, conditionFill, True, triggered,
                      f"+{enhancedFP} FP", f"{failedCount} cards failed", f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(odds, 4), chanceTriggered=triggered)


# ── Game-Outcome Effects ─────────────────────────────────────────────────────

def _computeComebackKid(primary, ctx, cardPlayerId, eqId):
    """FP per roster player on a team that missed playoffs LAST season — bet
    on the rebuilding teams before the league prices them in. Floobits bonus
    if your favorite team actually pulls off a comeback win this week.
    """
    perPlayerFP = primary.get("perPlayerFP", 15)
    floobitsBonus = primary.get("floobitsOnTrigger", 30)
    missedSet = ctx.priorSeasonMissedPlayoffTeamIds or set()
    if not missedSet:
        # Season 1 or lookup failed — pay base on rostered players regardless,
        # so the card isn't dead in season 1.
        count = 0
        eq = "No prior-season standings available"
        return EffectResult(equation=eq)
    count = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if (ctx.rosterPlayerTeamIds or {}).get(pid) in missedSet
    )
    fp = round(perPlayerFP * count, 1)
    fbBonus = 0
    eqParts = [f"{perPlayerFP}/player × {count} (missed playoffs last season) = +{fp} FP"]
    if ctx.favoriteTeamGameFinal and ctx.favoriteTeamComebackWin:
        fbBonus = floobitsBonus
        eqParts.append(f"+{fbBonus}F (comeback win!)")
    return EffectResult(fpBonus=fp, floobits=fbBonus, equation=" | ".join(eqParts))


def _computeDomination(primary, ctx, cardPlayerId, eqId):
    """FP per roster player whose team is currently top-6 in the league. Bet
    on contenders' players. Floobits bonus if your favorite team wins by 21+
    this week.
    """
    perPlayerFP = primary.get("perPlayerFP", 18)
    floobitsBonus = primary.get("floobitsOnTrigger", 30)
    margin = ctx.favoriteTeamScoreMargin
    threshold = primary.get("marginThreshold", 21)
    top6 = ctx.currentTop6TeamIds or set()
    count = sum(
        1 for pid in (ctx.rosterPlayerIds or set())
        if (ctx.rosterPlayerTeamIds or {}).get(pid) in top6
    )
    fp = round(perPlayerFP * count, 1)
    fbBonus = 0
    eqParts = [f"{perPlayerFP}/player × {count} (top-6 team) = +{fp} FP"]
    if ctx.favoriteTeamGameFinal and ctx.favoriteTeamWonThisWeek and margin >= threshold:
        fbBonus = floobitsBonus
        eqParts.append(f"+{fbBonus}F (fav team blowout, won by {margin})")
    return EffectResult(fpBonus=fp, floobits=fbBonus, equation=" | ".join(eqParts))


def _computeWalkOff(primary, ctx, cardPlayerId, eqId):
    """FP per Q4/OT scoring play (TD or FG) by THIS player (re-based off the roster). Counts each
    scoring event individually — two Q4 TDs from one rostered player = 2.
    A Q4 TD pass between two rostered players (QB and WR) = 2. Floobits
    bonus on actual fav-team walk-off win.
    """
    perScoreFP = primary.get("perScoreFP", 22)
    floobitsBonus = primary.get("floobitsOnTrigger", 30)
    weekStats = ctx.weekPlayerStats or {}
    # Re-based off the roster: THIS player's Q4/OT scoring plays.
    totalScores = int((weekStats.get(cardPlayerId, {}) or {}).get("q4ScoringPlays", 0))
    fp = round(perScoreFP * totalScores, 1)
    fbBonus = 0
    eqParts = [f"{perScoreFP}/score × {totalScores} Q4/OT TDs+FGs = +{fp} FP"]
    if ctx.favoriteTeamGameFinal and ctx.favoriteTeamWalkOffWin:
        fbBonus = floobitsBonus
        eqParts.append(f"+{fbBonus}F (walk-off win!)")
    return EffectResult(fpBonus=fp, floobits=fbBonus, equation=" | ".join(eqParts))


# ─── Strategy-Warping Effect Compute Functions ──────────────────────────────

BASE_ROSTER_SLOTS = 6  # QB, RB, WR1, WR2, TE, K (FLEX adds +1 when active)

# Effects that mean "field a full roster of underperformers, not an
# empty one." Their condition is easy to trigger with a gutted roster
# (fewer slots = fewer ways to score 15+, fewer paths to break the
# under-50 line, etc.), so we gate them on a near-full roster. Home
# Alone is intentionally excluded — empty slots ARE its mechanic.
_FULL_ROSTER_INTENT_EFFECTS = frozenset({"drought", "sandbagger", "quiet_storm", "hedge"})
# Need at least this many filled roster slots for the gated effects to
# pay out. 6 = all base roster slots filled — blocks the gut-the-roster
# strategy that trivially triggers Drought / Quiet Storm.
_FULL_ROSTER_MIN_FILLED = 6


def _meetsFullRosterRequirement(ctx) -> bool:
    """True when the user has enough filled slots for the full-roster-intent
    effects to fire. Used by Drought / Sandbagger / Quiet Storm / Hedge to
    deny payouts on gutted rosters. A filled FLEX counts toward the total —
    six rostered players is six rostered players."""
    return len(ctx.rosterPlayerIds or set()) >= _FULL_ROSTER_MIN_FILLED


def _computeAlchemy(primary, ctx, cardPlayerId, eqId):
    """FGs count as TDs for other cards (Cornucopia, Touchdown Piñata, etc.)
    plus a bonus FP per FG. The rosterTotalTds bump happens in the
    calculator's pre-pass — see calculateWeekCardBonuses — so this
    function only needs to compute its own FP payout.

    ⚠️ STILL ROSTER-SCOPED: it sums every FG by a KICKER on the roster, not by the
    depicted player, so the on-card rebase never reached it. Both texts used to say
    "by this player" and now say "your kicker", which is what the code does. In
    practice the two almost always coincide — alchemy is K-exclusive and a roster has
    one K slot — and they part only when a FLEX slot holds a second kicker. Rebasing
    the maths onto `cardPlayerId` is a scoring change rather than a wording one, and
    is moot while the effect is unmintable (diamond needs a 90 rating and no K has
    ever passed 88 — see CLAUDE.md).
    """
    if not ctx.gamesActive and not ctx.teamResults:
        return EffectResult(equation="Waiting for games")
    perFgBonusFP = primary.get("perFgBonusFP", 3.0)
    fgsMade = 0
    for pid in ctx.rosterPlayerIds:
        if ctx.rosterPlayerPositions.get(pid) == 5:
            kickStats = ctx.weekPlayerStats.get(pid, {}).get("kicking_stats", {})
            fgsMade += kickStats.get("fgs", 0)
    if fgsMade == 0:
        return EffectResult(equation="No FGs made by roster K")
    bonus = round(perFgBonusFP * fgsMade, 1)
    eq = f"{perFgBonusFP}/FG × {fgsMade} FGs (counted as TDs)"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeAusterity(primary, ctx, cardPlayerId, eqId):
    """FPx per empty roster slot. Fewer players = bigger multiplier."""
    perSlotMult = primary.get("perSlotMult", 0.15)
    totalSlots = BASE_ROSTER_SLOTS + (1 if ctx.hasFlexSlot else 0)
    filledSlots = len(ctx.rosterPlayerIds)
    emptySlots = max(0, totalSlots - filledSlots)
    if emptySlots == 0:
        return EffectResult(multBonus=1.0, equation="No empty roster slots")
    mult = round(1.0 + perSlotMult * emptySlots, 3)
    delta = round(mult - 1.0, 2)
    eq = f"+{perSlotMult:.2f}/slot × {emptySlots} empty = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeCloser(primary, ctx, cardPlayerId, eqId):
    """Bonus FP from THIS player's Q4/OT fantasy points (re-based off the roster)."""
    if ctx.gamesActive:
        return EffectResult(equation="Waiting for games to complete")
    q4MultFactor = primary.get("q4MultFactor", 2.0)
    ps = (ctx.weekPlayerStats or {}).get(cardPlayerId, {}) or {}
    playerQ4 = ps.get("q4FantasyPoints", 0) or 0
    if playerQ4 <= 0:
        return EffectResult(equation="No Q4/OT fantasy points")
    bonus = round(q4MultFactor * playerQ4, 1)
    eq = f"{q4MultFactor}x × {round(playerQ4, 1)} Q4/OT FP = +{bonus}"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeHumility(primary, ctx, cardPlayerId, eqId):
    """FPx inverse to star rating of rostered player at card's position."""
    perStarMult = primary.get("perStarMult", 0.1)
    cardPos = ctx.cardPosition
    # Find rostered players at this card's position
    matchingPids = [pid for pid, pos in ctx.rosterPlayerPositions.items() if pos == cardPos]
    if not matchingPids:
        return EffectResult(multBonus=1.0, equation="No rostered player at position")
    # Average stars-under-5 across matching players (handles WR1+WR2)
    totalStarsUnder = 0
    for pid in matchingPids:
        rating = ctx.rosterPlayerRatings.get(pid, 60)
        stars = min(5, max(1, (rating - 60) // 8 + 1))
        totalStarsUnder += max(0, 5 - stars)
    avgStarsUnder = totalStarsUnder / len(matchingPids)
    if avgStarsUnder <= 0:
        return EffectResult(multBonus=1.0, equation="Rostered player is 5★ (no bonus)")
    mult = round(1.0 + perStarMult * avgStarsUnder, 2)
    delta = round(mult - 1.0, 2)
    posLabel = POSITION_LABELS.get(cardPos, "player")
    eq = f"+{perStarMult}/star × {avgStarsUnder:.1f} stars under 5 ({posLabel}) = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeVagabond(primary, ctx, cardPlayerId, eqId):
    """FPx per roster swap used this season — inverse of Stockpiler."""
    perSwap = primary.get("perSwapXMult", 0.03)
    maxMult = primary.get("maxMult", 1.6)
    swapsUsed = ctx.seasonSwapsUsed
    if swapsUsed <= 0:
        return EffectResult(multBonus=1.0, equation="No swaps used this season")
    mult = round(min(1.0 + perSwap * swapsUsed, maxMult), 3)
    delta = round(mult - 1.0, 2)
    eq = f"+{perSwap}/swap × {swapsUsed} swaps used = +{delta:.2f} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeOpulence(primary, ctx, cardPlayerId, eqId):
    """FP scaling with Floobits balance."""
    floobitsPerFP = primary.get("floobitsPerFP", 3)
    maxFP = primary.get("maxFP", 15)
    balance = ctx.userFloobitsBalance
    if balance <= 0:
        return EffectResult(equation="No Floobits in balance")
    rawFP = balance / max(1, floobitsPerFP)
    bonus = round(min(rawFP, maxFP), 1)
    eq = f"{balance}F ÷ {floobitsPerFP} = {rawFP:.1f} FP (cap {maxFP}) = +{bonus}"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeProsperity(primary, ctx, cardPlayerId, eqId):
    """Adds a flat F bonus to weekly earnings. Output is informational only —
    the actual bonus is applied in seasonManager._awardWeeklyFpFloobits()."""
    flatBonus = primary.get("flatBonus", primary.get("ceilingBonus", 6))
    return EffectResult(floobits=0, equation=f"+{flatBonus}F flat weekly bonus")


def _getCultivationStepSize(triggerEvent):
    """Look up the per-level trigger step size from the trigger pool.
    High-volume stats (carries, receptions, YAC) use bigger step sizes so
    grows still require a real outlier week."""
    for t in CULTIVATION_TRIGGER_POOL:
        if t["event"] == triggerEvent:
            return t.get("stepSize", 3)
    return 3


# Bonsai grow-requirement ramp per level. GENTLER than linear (was stepSize*(level+1), which
# made a high-stepSize trigger like YAC (60) unreachable past level ~2 — a great week still
# gave a poor grow-chance, and the card stalled far below its edition FP ceiling). At 0.4 the
# requirement grows ~40% of a full step per level, so strong weeks keep advancing the card
# while higher levels still demand more. Computed live (not frozen at mint), so it re-values
# all Bonsai cards immediately.
CULTIVATION_LEVEL_RAMP = 0.4


def _cultivationRequired(triggerEvent, growthLevel):
    """Trigger events needed for a near-certain grow at `growthLevel`. Shared by the chance
    calc, the display note, and the week-end roll so all three agree."""
    stepSize = _getCultivationStepSize(triggerEvent)
    return max(1, int(round(stepSize * (1 + growthLevel * CULTIVATION_LEVEL_RAMP))))


def cultivationGrowthChance(primary, triggerCount, growthLevel, chanceBonus=0.0):
    """Bonsai's grow odds (0-100), SHARED by the live display (_computeCultivation) and the
    week-end roll (_rollCultivationGrowth) so the power-bar meter, the effect detail, and the
    actual result always agree. The requirement scales with the current level (gentle ramp) —
    a higher level needs a bigger week to keep pushing the base upward. A dead week floors 2%.

    `chanceBonus` (0-1) is the same hand-synergy / powerup / weekly-modifier trigger lift
    every other chance card gets (Fortunate modifier, Fortune's Favor, Providence, Catalyst,
    innate chance synergy — summed onto ctx.chanceBonus). Bonsai is a chance card too, so the
    boost raises its grow odds; without this it silently ignored those amplifiers."""
    triggerEvent = primary.get("triggerEvent", "pass_td")
    stepSize = _getCultivationStepSize(triggerEvent)
    required = _cultivationRequired(triggerEvent, growthLevel)
    if required <= 0:
        base = 2
    elif triggerCount >= required:
        excess = triggerCount - required
        base = min(100, 90 + int((excess / stepSize) * 10))
    else:
        base = max(2, int((triggerCount / required) * 90))
    if chanceBonus:
        base = min(100, base + int(round(chanceBonus * 100)))
    return base


def _computeCultivation(primary, ctx, cardPlayerId, eqId):
    """Performance-driven growth — growth chance is earned by hitting trigger
    events, and the threshold scales with current growth level. Higher levels
    require bigger weeks from THIS player to keep pushing the base upward."""
    baseFP = primary.get("baseFP", 4.0)
    growthFP = primary.get("growthFP", 2.0)
    # streak_count tracks number of successful growths (starts at 1 = no growth)
    growthLevel = max(0, ctx.streakCounts.get(eqId, 1) - 1)
    currentFP = round(baseFP + growthFP * growthLevel, 1)
    triggerEvent = primary.get("triggerEvent", "pass_td")
    triggerLabel = primary.get("triggerLabel", "events")
    triggerCount = _countCultivationTriggers(triggerEvent, ctx, cardPlayerId)
    # Triggers needed to earn a grow at this level (gentle per-level ramp). Shared with the
    # chance calc and the week-end roll so the meter, the detail note, and the result agree.
    required = _cultivationRequired(triggerEvent, growthLevel)
    # Chance-card amplifiers (Fortunate modifier, Fortune's Favor, Providence, Catalyst,
    # innate synergy) lift Bonsai's grow odds just like any other chance card.
    growthChance = cultivationGrowthChance(primary, triggerCount, growthLevel,
                                           getattr(ctx, 'chanceBonus', 0.0))
    nextFP = round(currentFP + growthFP, 1)
    triggerNote = f" ({triggerCount}/{required} {triggerLabel})"
    eq = f"+{currentFP} FP. {growthChance}% chance{triggerNote} to grow to +{nextFP} FP"
    # The power-bar meter for a chance card reads chanceThreshold as its fill, so expose the
    # grow-odds there to make the meter match the detail. chanceMetaGrowth flags that fpBonus
    # is the GUARANTEED base (the odds gate FUTURE growth, not this week's payout) so the
    # projection EV pass doesn't scale the floor down by the odds. chanceTriggered stays False
    # here — the grow is resolved at week end by _rollCultivationGrowth, which patches the
    # meter state (threshold + triggered) into the stored breakdown.
    return EffectResult(fpBonus=currentFP, equation=eq,
                        chanceThreshold=round(growthChance / 100.0, 4),
                        chanceMetaGrowth=True)


def _countCultivationTriggers(triggerEvent, ctx, cardPlayerId=0):
    """Count trigger events for Cultivation (Bonsai). Re-based off the roster to THIS
    player when cardPlayerId is given; falls back to the roster sum for any legacy
    caller without one."""
    total = 0
    triggerDef = None
    for t in CULTIVATION_TRIGGER_POOL:
        if t["event"] == triggerEvent:
            triggerDef = t
            break
    if not triggerDef:
        return 0
    pids = [cardPlayerId] if cardPlayerId else list(ctx.rosterPlayerIds)
    for pid in pids:
        ps = ctx.weekPlayerStats.get(pid, {})
        for catKey, statKey in triggerDef["statPaths"]:
            total += ps.get(catKey, {}).get(statKey, 0)
    return total


# ─── Fusion additions (2026-07) ──────────────────────────────────────────────

def _computeWinnersCircle(primary, ctx, cardPlayerId, eqId):
    """Flat Floobits when the depicted player's real team won its game this week."""
    teamId = ctx.rosterPlayerTeamIds.get(cardPlayerId)
    won = ctx.teamResults.get(teamId)  # True / False / None (not final)
    val = int(primary.get("winFloobits", 0))
    if won:
        return EffectResult(floobits=val, equation=f"+{val}F (team won)")
    if won is None:
        return EffectResult(equation="waiting for game to end")
    return EffectResult(equation="team didn't win this week")


def _rosterWeekFPs(ctx):
    return [round((ctx.weekPlayerStats.get(pid, {}) or {}).get("fantasyPoints", 0) or 0, 1)
            for pid in ctx.rosterPlayerIds]


def _computeNoPassengers(primary, ctx, cardPlayerId, eqId):
    """FPx that scales with the roster's LOWEST weekly FP — reward a deep lineup."""
    fps = _rosterWeekFPs(ctx)
    if not fps:
        return EffectResult(equation="no roster")
    floorFP = min(fps)
    perFP = primary.get("perFloorFP", 0.0)
    maxDelta = primary.get("maxDelta", 0.5)
    delta = min(max(0.0, floorFP * perFP), maxDelta)
    if delta <= 0:
        return EffectResult(equation=f"lowest roster player scored {floorFP} FP")
    mult = round(1.0 + delta, 3)
    eq = f"lowest {floorFP} FP × {perFP}/FP = +{round(delta, 2)} FPx"
    return EffectResult(multBonus=mult, equation=eq)


def _computeCaptain(primary, ctx, cardPlayerId, eqId):
    """Pure overshoot amplifier (Diamond). Produces no own output — the actual boost is
    applied by the calculator's tradeoff phase (_applyCaptainBoost), which lifts every
    other card's output by how far its player overshot its power bar. Returning an empty
    EffectResult marks the card as present so the amplifier pill can read its config."""
    return EffectResult()


def _computeFranchise(primary, ctx, cardPlayerId, eqId):
    """Conditional boom FPx when the depicted player is the roster's single top scorer."""
    fps = _rosterWeekFPs(ctx)
    myFP = round((ctx.weekPlayerStats.get(cardPlayerId, {}) or {}).get("fantasyPoints", 0) or 0, 1)
    topFP = max(fps) if fps else 0
    delta = primary.get("topScorerDelta", 0.0)
    if myFP > 0 and myFP >= topFP and delta > 0:
        mult = round(1.0 + delta, 3)
        return EffectResult(multBonus=mult, equation=f"top scorer ({myFP} FP) → +{round(delta, 2)} FPx")
    return EffectResult(equation="not your top scorer this week")


# ─── Stat Ladder Families ────────────────────────────────────────────────────
# One stat, three rungs, each containing the one below. Every function reads the
# CARD's own player via _getCardPlayerStats. See docs/CARD_STAT_LADDER.md.

def _ladderStat(ctx, cardPlayerId, group, key):
    """A single stat off the card's own player, defaulting to 0."""
    stats = _getCardPlayerStats(ctx, cardPlayerId)
    sub = stats.get(group)
    return (sub or {}).get(key, 0) if isinstance(sub, dict) else 0


def _ladderStreakDelta(primary, ctx, eqId):
    """The streak half of a prismatic rung: growth per week the bar has been cleared.

    Kept separate from the base rate so the prismatic rung literally contains the
    metallic one — the base pays every week and this rides on top.
    """
    growth = primary.get("growthPerTick", 0.0) or 0.0
    count = max(0, (ctx.streakCounts.get(eqId, 1) or 1) - 1)
    return round(growth * count, 3), count


# ── Receiving yards: Frontier -> Territory -> Dominion ──
def _computeFrontier(primary, ctx, cardPlayerId, eqId):
    """FP per receiving yard by this player."""
    per = primary.get("perYardFP", 0.3)
    yards = _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvYards")
    return EffectResult(fpBonus=round(per * yards, 1),
                        equation=f"{per}/yd x {yards} rec yds")


def _computeTerritory(primary, ctx, cardPlayerId, eqId):
    """FPx per 50 receiving yards, plus a step at each yardage gate."""
    per50 = primary.get("per50Mult", 0.06)
    gateMult = primary.get("gateMult", 0.05)
    gates = primary.get("gates", [75, 125, 175])
    yards = _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvYards")
    cleared = sum(1 for g in gates if yards >= g)
    delta = per50 * (yards / 50.0) + gateMult * cleared
    if delta <= 0:
        return EffectResult(equation="no receiving yards")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({yards} yds, {cleared}/{len(gates)} gates)")


def _computeDominion(primary, ctx, cardPlayerId, eqId):
    """FPx per 50 receiving yards, plus a streak of hundred-yard weeks."""
    per50 = primary.get("per50Mult", 0.03)
    yards = _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvYards")
    streak, count = _ladderStreakDelta(primary, ctx, eqId)
    delta = per50 * (yards / 50.0) + streak
    if delta <= 0:
        return EffectResult(equation="no receiving yards")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({yards} yds + {count} wk streak)")


# ── Yards after contact: Freight -> Grinder -> Landslide ──
def _computeFreight(primary, ctx, cardPlayerId, eqId):
    """FP per yard gained after contact by this player."""
    per = primary.get("perYardFP", 0.3)
    yac = _ladderStat(ctx, cardPlayerId, "rushing_stats", "yardsAfterContact")
    return EffectResult(fpBonus=round(per * yac, 1),
                        equation=f"{per}/yd x {yac} yds after contact")


def _computeGrinder(primary, ctx, cardPlayerId, eqId):
    """FPx per 50 contact yards, more when they are most of the total."""
    per50 = primary.get("per50Mult", 0.06)
    ratioMult = primary.get("ratioMult", 0.06)
    bar = primary.get("ratioBar", 0.88)
    yac = _ladderStat(ctx, cardPlayerId, "rushing_stats", "yardsAfterContact")
    total = _ladderStat(ctx, cardPlayerId, "rushing_stats", "runYards")
    delta = per50 * (yac / 50.0)
    earned = total > 0 and yac >= total * bar
    if earned:
        delta += ratioMult
    if delta <= 0:
        return EffectResult(equation="no yards after contact")
    tail = f" ({yac / total:.0%} after contact)" if earned else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({yac}/{total} yds{tail})")


def _computeLandslide(primary, ctx, cardPlayerId, eqId):
    """FPx per 50 contact yards, plus a streak of hundred-yard weeks."""
    per50 = primary.get("per50Mult", 0.03)
    yac = _ladderStat(ctx, cardPlayerId, "rushing_stats", "yardsAfterContact")
    streak, count = _ladderStreakDelta(primary, ctx, eqId)
    delta = per50 * (yac / 50.0) + streak
    if delta <= 0:
        return EffectResult(equation="no yards after contact")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({yac} yds + {count} wk streak)")


# ── Punt placement: Pinpoint -> Coffin Corner -> Undertaker ──
def _computePinpoint(primary, ctx, cardPlayerId, eqId):
    """FP per punt this player downed inside the 20."""
    per = primary.get("perPuntFP", 13.0)
    pins = _ladderStat(ctx, cardPlayerId, "kicking_stats", "puntsInside20")
    return EffectResult(fpBonus=round(per * pins, 1),
                        equation=f"{per}/punt x {pins} inside the 20")


def _computeCoffinCorner(primary, ctx, cardPlayerId, eqId):
    """FPx per pin, with more for the ones downed inside the 10."""
    perPunt = primary.get("perPuntMult", 0.05)
    bonus = primary.get("bonusMult", 0.07)
    deepBar = primary.get("deepBar", 2)
    pins = _ladderStat(ctx, cardPlayerId, "kicking_stats", "puntsInside20")
    deep = _ladderStat(ctx, cardPlayerId, "kicking_stats", "puntsInside10")
    delta = perPunt * pins + (bonus * deep if deep >= deepBar else 0)
    if delta <= 0:
        return EffectResult(equation="no punts inside the 20")
    tail = f", {deep} inside 10" if deep >= deepBar else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({pins} inside 20{tail})")


def _computeUndertaker(primary, ctx, cardPlayerId, eqId):
    """FPx per pin, plus a streak of multi-pin weeks."""
    perPunt = primary.get("perPuntMult", 0.03)
    pins = _ladderStat(ctx, cardPlayerId, "kicking_stats", "puntsInside20")
    streak, count = _ladderStreakDelta(primary, ctx, eqId)
    delta = perPunt * pins + streak
    if delta <= 0:
        return EffectResult(equation="no punts inside the 20")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({pins} pinned + {count} wk streak)")


# ── Receiving TDs: Paydirt -> End Zone -> Promised Land ──
def _computePaydirt(primary, ctx, cardPlayerId, eqId):
    """FPx for every receiving TD by this player, capped."""
    per = primary.get("perTdMult", 0.12)
    cap = primary.get("maxMult", 0.30)
    tds = _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvTds")
    if tds <= 0:
        return EffectResult(equation="no receiving TDs")
    delta = min(cap, per * tds)
    capped = " (max)" if per * tds > cap else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({tds} rec TD){capped}")


def _computeEndZone(primary, ctx, cardPlayerId, eqId):
    """FP per receiving TD, with a bonus once a second one lands."""
    per = primary.get("perTdFP", 40.0)
    bonus = primary.get("bonusFP", 14.0)
    threshold = primary.get("threshold", 2)
    tds = _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvTds")
    total = per * tds + (bonus if tds >= threshold else 0)
    tail = f", +{bonus} at {threshold}+" if tds >= threshold else ""
    return EffectResult(fpBonus=round(total, 1),
                        equation=f"{per}/TD x {tds}{tail}")


def _computePromisedLand(primary, ctx, cardPlayerId, eqId):
    """FP per receiving TD, each one raising the odds of a jackpot.

    Mirrors Crescendo's escalating-odds shape: every score rolls, and a miss lifts
    the chance on the next one. Pays out once.
    """
    from managers.cardEffectCalculator import _chanceRoll
    per = primary.get("perTdFP", 26.0)
    bonus = primary.get("bonusFP", 32.0)
    baseChance = primary.get("baseChance", 22)
    step = primary.get("chanceStep", 14)
    rawTds = _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvTds")
    base = round(per * rawTds, 1)
    if rawTds <= 0:
        return EffectResult(equation="no receiving TDs")
    # The projection path feeds PER-GAME AVERAGES, so this arrives fractional there.
    # Round up to one roll so a projected part-TD still shows its chance.
    tds = max(1, int(round(rawTds)))
    if getattr(ctx, "gamesActive", False):
        live = min(0.97, (baseChance + max(0, tds - 1) * step) / 100.0
                   + getattr(ctx, "chanceBonus", 0.0))
        return EffectResult(fpBonus=base, chanceThreshold=live,
                            equation=_chanceEq(live, 0, live, False, f"+{bonus} FP",
                                               f"{tds} rec TD", ctx, f"+{base} FP"))
    rng = _chanceRoll(ctx, eqId)
    for i in range(tds):
        odds = min(0.97, (baseChance + i * step) / 100.0
                   + getattr(ctx, "chanceBonus", 0.0))
        if rng.random() < odds:
            return EffectResult(fpBonus=round(base + bonus, 1), chanceTriggered=True,
                                chanceThreshold=odds,
                                equation=f"+{base} FP. {odds:.0%} on TD {i + 1} hit, +{bonus} FP")
    return EffectResult(fpBonus=base,
                        equation=f"+{base} FP. {tds} TD rolled, none hit")


# ── Pass TDs: Bombardier -> Salvo -> Barrage ──
# Structurally the receiving-TD family pointed at the QB, but sized quite differently: a QB
# throws ~1.02 TDs a game against a WR's 0.35, so this is a REGULAR stat wearing a lumpy
# stat's shape. Paydirt has to price per scoring event because 0.35 is an average nobody
# posts; Bombardier can be sized against the ordinary FPx target and still spike.


def _computeBombardier(primary, ctx, cardPlayerId, eqId):
    """FPx for every passing TD by this player, capped."""
    per = primary.get("perTdMult", 0.10)
    cap = primary.get("maxMult", 0.30)
    tds = _ladderStat(ctx, cardPlayerId, "passing_stats", "tds")
    if tds <= 0:
        return EffectResult(equation="no passing TDs")
    delta = min(cap, per * tds)
    capped = " (max)" if per * tds > cap else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({tds} pass TD){capped}")


def _computeSalvo(primary, ctx, cardPlayerId, eqId):
    """FP per passing TD, with a bonus once a third one lands.

    The bar is 3 rather than End Zone's 2 because two passing TDs is an ordinary QB day
    (29% of games) while two receiving TDs is not (6%). Matching the NUMBER would have
    made the bonus routine; matching the RARITY is what keeps it a bonus.
    """
    per = primary.get("perTdFP", 14.0)
    bonus = primary.get("bonusFP", 14.3)
    threshold = primary.get("threshold", 3)
    tds = _ladderStat(ctx, cardPlayerId, "passing_stats", "tds")
    total = per * tds + (bonus if tds >= threshold else 0)
    tail = f", +{bonus} at {threshold}+" if tds >= threshold else ""
    return EffectResult(fpBonus=round(total, 1),
                        equation=f"{per}/TD x {tds}{tail}")


def _computeBarrage(primary, ctx, cardPlayerId, eqId):
    """FP per passing TD, each one raising the odds of a jackpot.

    Same escalating shape as Promised Land, but the opening odds and step are LOWER
    because a QB gets more rolls: at Promised Land's 14/+12 the extra volume compounds to
    a 52% richer card. Lowering the odds instead of the jackpot keeps the payout worth
    chasing, which is the whole point of a chance card.
    """
    from managers.cardEffectCalculator import _chanceRoll
    per = primary.get("perTdFP", 11.5)
    bonus = primary.get("bonusFP", 71.5)
    baseChance = primary.get("baseChance", 8)
    step = primary.get("chanceStep", 6)
    rawTds = _ladderStat(ctx, cardPlayerId, "passing_stats", "tds")
    base = round(per * rawTds, 1)
    if rawTds <= 0:
        return EffectResult(equation="no passing TDs")
    # The projection path feeds PER-GAME AVERAGES, so this arrives fractional there.
    tds = max(1, int(round(rawTds)))
    if getattr(ctx, "gamesActive", False):
        live = min(0.97, (baseChance + max(0, tds - 1) * step) / 100.0
                   + getattr(ctx, "chanceBonus", 0.0))
        return EffectResult(fpBonus=base, chanceThreshold=live,
                            equation=_chanceEq(live, 0, live, False, f"+{bonus} FP",
                                               f"{tds} pass TD", ctx, f"+{base} FP"))
    rng = _chanceRoll(ctx, eqId)
    for i in range(tds):
        odds = min(0.97, (baseChance + i * step) / 100.0
                   + getattr(ctx, "chanceBonus", 0.0))
        if rng.random() < odds:
            return EffectResult(fpBonus=round(base + bonus, 1), chanceTriggered=True,
                                chanceThreshold=odds,
                                equation=f"+{base} FP. {odds:.0%} on TD {i + 1} hit, +{bonus} FP")
    return EffectResult(fpBonus=base,
                        equation=f"+{base} FP. {tds} TD rolled, none hit")


# ── Pass yards: Slipstream -> Updraft -> Stratosphere ──
def _computeSlipstream(primary, ctx, cardPlayerId, eqId):
    """FPx per 100 passing yards by this player."""
    per100 = primary.get("per100Mult", 0.04)
    yards = _ladderStat(ctx, cardPlayerId, "passing_stats", "passYards")
    delta = per100 * (yards / 100.0)
    if delta <= 0:
        return EffectResult(equation="no passing yards")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({yards} pass yds)")


def _computeUpdraft(primary, ctx, cardPlayerId, eqId):
    """FP per passing yard, with a step at each yardage gate."""
    per = primary.get("perYardFP", 0.11)
    gateFP = primary.get("gateFP", 9.0)
    gates = primary.get("gates", [300, 390, 480])
    yards = _ladderStat(ctx, cardPlayerId, "passing_stats", "passYards")
    cleared = sum(1 for g in gates if yards >= g)
    total = per * yards + gateFP * cleared
    return EffectResult(fpBonus=round(total, 1),
                        equation=f"{per}/yd x {yards} yds, {cleared}/{len(gates)} gates")


def _computeStratosphere(primary, ctx, cardPlayerId, eqId):
    """FPx per 100 passing yards, plus a streak of big weeks."""
    per100 = primary.get("per100Mult", 0.02)
    yards = _ladderStat(ctx, cardPlayerId, "passing_stats", "passYards")
    streak, count = _ladderStreakDelta(primary, ctx, eqId)
    delta = per100 * (yards / 100.0) + streak
    if delta <= 0:
        return EffectResult(equation="no passing yards")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({yards} yds + {count} wk streak)")


# ── Throw quality: Gunslinger -> Marksman -> Dead Eye ──
def _computeMarksman(primary, ctx, cardPlayerId, eqId):
    """FPx per well-placed ball, with more for a week without a bad throw."""
    per5 = primary.get("per5Mult", 0.04)
    clean = primary.get("cleanSheetMult", 0.07)
    good = _ladderStat(ctx, cardPlayerId, "passing_stats", "goodThrows")
    bad = _ladderStat(ctx, cardPlayerId, "passing_stats", "badThrows")
    threw = _ladderStat(ctx, cardPlayerId, "passing_stats", "throws")
    delta = per5 * (good / 5.0)
    # A clean sheet only counts if they actually threw; 0 attempts is not accuracy.
    sheet = threw > 0 and bad == 0
    if sheet:
        delta += clean
    if delta <= 0:
        return EffectResult(equation="no well-placed throws")
    tail = ", no bad throws" if sheet else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({good} well-placed{tail})")


def _computeDeadEye(primary, ctx, cardPlayerId, eqId):
    """FPx per well-placed ball, plus a streak of clean sheets."""
    per5 = primary.get("per5Mult", 0.02)
    good = _ladderStat(ctx, cardPlayerId, "passing_stats", "goodThrows")
    streak, count = _ladderStreakDelta(primary, ctx, eqId)
    delta = per5 * (good / 5.0) + streak
    if delta <= 0:
        return EffectResult(equation="no well-placed throws")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({good} well-placed + {count} wk streak)")


# ── Completions: Cadence -> Rhythm -> Clockwork ──
def _computeCadence(primary, ctx, cardPlayerId, eqId):
    """FP for every completion by this player."""
    per = primary.get("perCompletionFP", 0.9)
    comp = _ladderStat(ctx, cardPlayerId, "passing_stats", "comp")
    return EffectResult(fpBonus=round(per * comp, 1),
                        equation=f"{per}/comp x {comp} completions")


def _ladderRateBonus(primary, ctx, cardPlayerId, group, key, rateKey, unit, label):
    """Shared holo shape: a rate on the stat, plus a step once it clears a bar."""
    rate = primary.get(rateKey, 0.05)
    bonus = primary.get("bonusMult", 0.05)
    threshold = primary.get("threshold", 0)
    val = _ladderStat(ctx, cardPlayerId, group, key)
    delta = rate * (val / float(unit))
    earned = threshold and val >= threshold
    if earned:
        delta += bonus
    if delta <= 0:
        return EffectResult(equation=f"no {label}")
    tail = f", past {threshold}" if earned else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({val} {label}{tail})")


def _ladderRateStreak(primary, ctx, cardPlayerId, eqId, group, key, rateKey, unit, label):
    """Shared prismatic shape: a rate on the stat, plus the streak riding on top."""
    rate = primary.get(rateKey, 0.03)
    val = _ladderStat(ctx, cardPlayerId, group, key)
    streak, count = _ladderStreakDelta(primary, ctx, eqId)
    delta = rate * (val / float(unit)) + streak
    if delta <= 0:
        return EffectResult(equation=f"no {label}")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({val} {label} + {count} wk streak)")


def _computeRhythm(primary, ctx, cardPlayerId, eqId):
    return _ladderRateBonus(primary, ctx, cardPlayerId, "passing_stats", "comp",
                            "per25Mult", 25, "completions")


def _computeClockwork(primary, ctx, cardPlayerId, eqId):
    return _ladderRateStreak(primary, ctx, cardPlayerId, eqId, "passing_stats", "comp",
                             "per25Mult", 25, "completions")


# ── Carries: Workhorse -> Beast of Burden -> Iron Man ──
def _computeBeastOfBurden(primary, ctx, cardPlayerId, eqId):
    return _ladderRateBonus(primary, ctx, cardPlayerId, "rushing_stats", "carries",
                            "per25Mult", 25, "carries")


def _computeIronMan(primary, ctx, cardPlayerId, eqId):
    return _ladderRateStreak(primary, ctx, cardPlayerId, eqId, "rushing_stats", "carries",
                             "per25Mult", 25, "carries")


# ── Rush yards: Expedition -> Trailblazer -> Odyssey ──
def _computeOdyssey(primary, ctx, cardPlayerId, eqId):
    return _ladderRateStreak(primary, ctx, cardPlayerId, eqId, "rushing_stats", "runYards",
                             "per50Mult", 50, "rush yds")


# ── Rush TDs ──
def _computeBatteringRam(primary, ctx, cardPlayerId, eqId):
    per = primary.get("perTdMult", 0.12)
    cap = primary.get("maxMult", 0.30)
    tds = _ladderStat(ctx, cardPlayerId, "rushing_stats", "runTds")
    if tds <= 0:
        return EffectResult(equation="no rushing TDs")
    delta = min(cap, per * tds)
    capped = " (max)" if per * tds > cap else ""
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({tds} rush TD){capped}")


# ── Receptions: Possession / Safety Blanket -> Custody -> Tenure ──
def _computeCustody(primary, ctx, cardPlayerId, eqId):
    return _ladderRateBonus(primary, ctx, cardPlayerId, "receiving_stats", "receptions",
                            "per5Mult", 5, "catches")


def _computeTenure(primary, ctx, cardPlayerId, eqId):
    return _ladderRateStreak(primary, ctx, cardPlayerId, eqId, "receiving_stats",
                             "receptions", "per5Mult", 5, "catches")


# ── YAC: Slippery -> Jailbreak -> Getaway ──
def _computeGetaway(primary, ctx, cardPlayerId, eqId):
    return _ladderRateStreak(primary, ctx, cardPlayerId, eqId, "receiving_stats", "yac",
                             "per10Mult", 10, "YAC")


# ── Targets ──
def _computeAttention(primary, ctx, cardPlayerId, eqId):
    per5 = primary.get("per5Mult", 0.05)
    targets = _ladderStat(ctx, cardPlayerId, "receiving_stats", "targets")
    delta = per5 * (targets / 5.0)
    if delta <= 0:
        return EffectResult(equation="no targets")
    return EffectResult(multBonus=round(1.0 + delta, 3),
                        equation=f"+{delta:.2f} FPx ({targets} targets)")


# ── Punt returns: Runback -> House Call ──
def _computeRunback(primary, ctx, cardPlayerId, eqId):
    per = primary.get("perYardFP", 1.1)
    yards = _ladderStat(ctx, cardPlayerId, "returning_stats", "puntReturnYards")
    return EffectResult(fpBonus=round(per * yards, 1),
                        equation=f"{per}/yd x {yards} return yds")


def _computeHouseCall(primary, ctx, cardPlayerId, eqId):
    """FP per return yard, with a jackpot on a return touchdown."""
    per = primary.get("perYardFP", 0.45)
    bonus = primary.get("bonusFP", 36.0)
    yards = _ladderStat(ctx, cardPlayerId, "returning_stats", "puntReturnYards")
    tds = _ladderStat(ctx, cardPlayerId, "returning_stats", "puntReturnTds")
    base = round(per * yards, 1)
    if tds > 0:
        return EffectResult(fpBonus=round(base + bonus, 1), chanceTriggered=True,
                            equation=f"+{base} FP + {bonus} (return TD)")
    return EffectResult(fpBonus=base, equation=f"{per}/yd x {yards} return yds")


# ── Deep passing ──
def _computeAltitude(primary, ctx, cardPlayerId, eqId):
    """FP scaling with how far downfield this player throws.

    Average depth of target, not raw air yards: a checkdown machine with volume should
    not out-earn someone genuinely pushing the ball downfield.
    """
    per = primary.get("perYardFP", 8.7)
    bar = primary.get("threshold", 6.8)
    air = _ladderStat(ctx, cardPlayerId, "passing_stats", "airYardsSum")
    throws = _ladderStat(ctx, cardPlayerId, "passing_stats", "throws")
    if throws <= 0:
        return EffectResult(equation="no throws")
    adot = air / float(throws)
    over = max(0.0, adot - bar)
    return EffectResult(fpBonus=round(per * over, 1),
                        equation=f"{adot:.1f} aDOT, {over:.1f} over {bar}")


# ── base + bonus one-offs ────────────────────────────────────────────────────
def _ladderBaseBonus(primary, ctx, cardPlayerId, baseGroup, baseKey, baseRateKey,
                     bonusGroup, bonusKey, baseLabel, bonusLabel):
    """A floor on the parent stat plus a kicker on a rare event.

    Rare stats cannot carry a card alone — at under two a game the per-unit value needed
    to reach the anchor makes a typical week pay nothing. The base is what stops that.
    """
    rate = primary.get(baseRateKey, 0.1)
    bonus = primary.get("bonusFP", 10.0)
    base = _ladderStat(ctx, cardPlayerId, baseGroup, baseKey)
    events = _ladderStat(ctx, cardPlayerId, bonusGroup, bonusKey)
    total = rate * base + bonus * events
    tail = f", {events} {bonusLabel}" if events else ""
    return EffectResult(fpBonus=round(total, 1),
                        equation=f"{rate}/{baseLabel} x {base}{tail}")


def _computeHaymaker(primary, ctx, cardPlayerId, eqId):
    return _ladderBaseBonus(primary, ctx, cardPlayerId, "passing_stats", "passYards",
                            "perYardFP", "passing_stats", "twentyPlus", "yd", "20+ throws")


def _computeBreakaway(primary, ctx, cardPlayerId, eqId):
    return _ladderBaseBonus(primary, ctx, cardPlayerId, "rushing_stats", "runYards",
                            "perYardFP", "rushing_stats", "twentyPlus", "yd", "20+ runs")


def _computeHighpoint(primary, ctx, cardPlayerId, eqId):
    return _ladderBaseBonus(primary, ctx, cardPlayerId, "receiving_stats", "receptions",
                            "perReceptionFP", "receiving_stats", "contestedCatches",
                            "rec", "contested")


def _computeCustodian(primary, ctx, cardPlayerId, eqId):
    return _ladderBaseBonus(primary, ctx, cardPlayerId, "receiving_stats", "receptions",
                            "perReceptionFP", "receiving_stats", "bailouts",
                            "rec", "bailouts")


def _computeHoudini(primary, ctx, cardPlayerId, eqId):
    """FP per rushing yard, with odds of a jackpot filling from broken tackles."""
    from managers.cardEffectCalculator import _chanceRoll
    per = primary.get("perYardFP", 0.1)
    bonus = primary.get("bonusFP", 34.0)
    yards = _ladderStat(ctx, cardPlayerId, "rushing_stats", "runYards")
    breaks = _ladderStat(ctx, cardPlayerId, "rushing_stats", "brokenTackles")
    base = round(per * yards, 1)
    conditionFill = min(1.0, breaks / 3.0)
    odds = _chanceOdds(ctx, cardPlayerId, conditionFill, useFP=True)
    if getattr(ctx, "gamesActive", False):
        return EffectResult(fpBonus=base, chanceThreshold=odds,
                            equation=_chanceBarEq(ctx, odds, conditionFill, True, False,
                                                  f"+{bonus} FP", f"{breaks} broken",
                                                  f"+{base} FP"))
    rng = _chanceRoll(ctx, eqId)
    if rng.random() < odds:
        return EffectResult(fpBonus=round(base + bonus, 1), chanceTriggered=True,
                            chanceThreshold=odds,
                            equation=f"+{base} FP. {odds:.0%} ({breaks} broken) hit, +{bonus} FP")
    return EffectResult(fpBonus=base, chanceThreshold=odds,
                        equation=f"+{base} FP. {odds:.0%} ({breaks} broken) missed")



# ─── Stat Ladder: what each card READS ───────────────────────────────────────
# (statGroup, key, label). Drives the breakdown's stat line so a card that pays on YAC
# shows YAC rather than a generic receptions/yards/TD summary — otherwise the number
# driving the payout is the one number not on screen, which makes a correct card look
# broken. Keep in step with the compute functions; they are the source of truth.
LADDER_STAT_READS = {
    "frontier":      ("receiving_stats", "rcvYards", "rec yds"),
    "territory":     ("receiving_stats", "rcvYards", "rec yds"),
    "dominion":      ("receiving_stats", "rcvYards", "rec yds"),
    "paydirt":       ("receiving_stats", "rcvTds", "rec TD"),
    "end_zone":      ("receiving_stats", "rcvTds", "rec TD"),
    "promised_land": ("receiving_stats", "rcvTds", "rec TD"),
    "bombardier":    ("passing_stats", "tds", "pass TD"),
    "salvo":         ("passing_stats", "tds", "pass TD"),
    "barrage":       ("passing_stats", "tds", "pass TD"),
    "possession":    ("receiving_stats", "receptions", "rec"),
    "safety_blanket": ("receiving_stats", "receptions", "rec"),
    "custody":       ("receiving_stats", "receptions", "rec"),
    "tenure":        ("receiving_stats", "receptions", "rec"),
    "highpoint":     ("receiving_stats", "contestedCatches", "contested"),
    "custodian":     ("receiving_stats", "bailouts", "bailouts"),
    "attention":     ("receiving_stats", "targets", "targets"),
    "slippery":      ("receiving_stats", "yac", "YAC"),
    "jailbreak":     ("receiving_stats", "yac", "YAC"),
    "getaway":       ("receiving_stats", "yac", "YAC"),
    "freight":       ("rushing_stats", "yardsAfterContact", "yds after contact"),
    "grinder":       ("rushing_stats", "yardsAfterContact", "yds after contact"),
    "landslide":     ("rushing_stats", "yardsAfterContact", "yds after contact"),
    "workhorse":     ("rushing_stats", "carries", "carries"),
    "beast_of_burden": ("rushing_stats", "carries", "carries"),
    "iron_man":      ("rushing_stats", "carries", "carries"),
    "expedition":    ("rushing_stats", "runYards", "rush yds"),
    "stampede":      ("rushing_stats", "runYards", "rush yds"),
    "odyssey":       ("rushing_stats", "runYards", "rush yds"),
    "battering_ram": ("rushing_stats", "runTds", "rush TD"),
    "breakaway":     ("rushing_stats", "twentyPlus", "20+ runs"),
    "houdini":       ("rushing_stats", "brokenTackles", "broken tackles"),
    "slipstream":    ("passing_stats", "passYards", "pass yds"),
    "updraft":       ("passing_stats", "passYards", "pass yds"),
    "stratosphere":  ("passing_stats", "passYards", "pass yds"),
    "gunslinger":    ("passing_stats", "goodThrows", "well-placed"),
    "marksman":      ("passing_stats", "goodThrows", "well-placed"),
    "dead_eye":      ("passing_stats", "goodThrows", "well-placed"),
    "cadence":       ("passing_stats", "comp", "completions"),
    "rhythm":        ("passing_stats", "comp", "completions"),
    "clockwork":     ("passing_stats", "comp", "completions"),
    "haymaker":      ("passing_stats", "twentyPlus", "20+ throws"),
    # Derived: aDOT is airYardsSum/throws, so it is computed in ladderStatLine rather
    # than read straight off a key.
    "altitude":      ("passing_stats", "__adot__", "aDOT"),
    "pinpoint":      ("kicking_stats", "puntsInside20", "inside the 20"),
    "coffin_corner": ("kicking_stats", "puntsInside20", "inside the 20"),
    "undertaker":    ("kicking_stats", "puntsInside20", "inside the 20"),
    "runback":       ("returning_stats", "puntReturnYards", "return yds"),
    "house_call":    ("returning_stats", "puntReturnYards", "return yds"),
}


def ladderStatLine(effectName: str, playerStats: dict) -> str:
    """"<value> <label>" for a ladder card, or "" when it is not one.

    Returns a line even at zero — "0 YAC" is the answer to "why did this pay nothing",
    and hiding it is what makes a quiet week look like a bug.
    """
    read = LADDER_STAT_READS.get(effectName)
    if not read or not isinstance(playerStats, dict):
        return ""
    group, key, label = read
    sub = playerStats.get(group)
    if not isinstance(sub, dict):
        return f"0 {label}"
    if key == "__adot__":
        throws = sub.get("throws", 0) or 0
        val = round((sub.get("airYardsSum", 0) or 0) / throws, 1) if throws else 0
    else:
        val = sub.get(key, 0)
    if isinstance(val, float):
        val = round(val, 1)
    return f"{val} {label}"

# ─── Effect Registry ─────────────────────────────────────────────────────────

EFFECT_REGISTRY = {
    # Stat ladder families
    "cadence": _computeCadence, "rhythm": _computeRhythm, "clockwork": _computeClockwork,
    "beast_of_burden": _computeBeastOfBurden, "iron_man": _computeIronMan,
    "odyssey": _computeOdyssey, "battering_ram": _computeBatteringRam,
    "custody": _computeCustody, "tenure": _computeTenure, "getaway": _computeGetaway,
    "runback": _computeRunback, "house_call": _computeHouseCall,
    "attention": _computeAttention, "altitude": _computeAltitude,
    "haymaker": _computeHaymaker, "breakaway": _computeBreakaway,
    "highpoint": _computeHighpoint, "custodian": _computeCustodian,
    "houdini": _computeHoudini,
    "slipstream": _computeSlipstream, "updraft": _computeUpdraft,
    "stratosphere": _computeStratosphere,
    "marksman": _computeMarksman, "dead_eye": _computeDeadEye,
    "frontier": _computeFrontier, "territory": _computeTerritory,
    "dominion": _computeDominion,
    "freight": _computeFreight, "grinder": _computeGrinder,
    "landslide": _computeLandslide,
    "pinpoint": _computePinpoint, "coffin_corner": _computeCoffinCorner,
    "undertaker": _computeUndertaker,
    "paydirt": _computePaydirt, "end_zone": _computeEndZone,
    "promised_land": _computePromisedLand,
    "bombardier": _computeBombardier, "salvo": _computeSalvo, "barrage": _computeBarrage,
    # Flat FP (WR)
    "freebie": _computeFreebie,
    "entourage": _computeEntourage,
    "touchdown_pinata": _computeTouchdownPinata,
    "scrappy": _computeScrappy,
    "honor_roll": _computeHonorRoll,
    "three_pointer": _computeThreePointer,
    "garbage_time": _computeGarbageTime,
    "loyalty_bonus": _computeLoyaltyBonus,
    "windfall": _computeDiamondInTheRough,
    "rng": _computeRng,
    "snake_eyes": _computeSnakeEyes,
    "avalanche": _computeAvalanche,
    "hedge": _computeHedge,
    # Multiplier (QB)
    "big_deal": _computeBigDeal,
    "cornucopia": _computeTriggerHappy,
    "luminary": _computeMainCharacter,
    "squire": _computeHypeMan,
    "babysitter": _computeBabysitter,
    "martyr": _computeTankCommander,
    "juggernaut": _computeJuggernaut,
    "resplendent": _computeHotRoster,
    "rising_tide": _computeRisingTide,
    "underdog": _computeUnderdog,
    "stockpiler": _computeStockpiler,
    "providence": _computeProvidence,
    # Floobits (RB)
    "allowance": _computeAllowance,
    "cha_ching": _computeChaChing,
    "piggy_bank": _computePiggyBank,
    "good_neighbor": _computegood_neighbor,
    "consolation_prize": _computeConsolationPrize,
    "rock_bottom": _computeRockBottom,
    "buy_low": _computeBuyLow,
    "trust_fund": _computeTrustFund,
    # Conditional (TE)
    "ace_up_the_sleeve": _computeAceUpTheSleeve,
    "showoff": _computeShowoff,
    "bandwagon": _computeBandwagon,
    "believe": _computeBelieve,
    "feeding_frenzy": _computeFeedingFrenzy,
    "spotlight_moment": _computeSpotlightMoment,
    "highlight_reel": _computeHighlightReel,
    "reclamation": _computeFixerUpper,
    "pedigree": _computePedigree,
    # Streak (K) — all use the generic streak handler
    "complacency": _computeStreakEffect,
    "on_fire": _computeStreakEffect,
    "snowball_fight": _computeStreakEffect,
    "fairweather_fan": _computeStreakEffect,
    "bandwagon_express": _computeStreakEffect,
    "touchdown_jackpot": _computeStreakEffect,
    "odometer": _computeOdometer,
    "leg_day": _computeStreakEffect,
    "automatic": _computeStreakEffect,
    "momentum": _computeStreakEffect,
    "house_money": _computeHouseMoney,
    # ── New Position-Based Effects ──
    "gunslinger": _computeGunslinger,
    "air_raid": _computeAirRaid,
    "workhorse": _computeWorkhorse,
    "expedition": _computeExpedition,
    "stampede": _computeStampede,
    "goal_line_vulture": _computeGoalLineVulture,
    "possession": _computePossession,
    "trebuchet": _computeDeepThreat,
    "double_trouble": _computeDoubleTrouble,
    "slippery": _computeSlippery,
    "jailbreak": _computeYacAttack,
    "safety_blanket": _computeSafetyBlanket,
    "lead_blocker": _computeLeadBlocker,
    "industrious": _computeChainMover,
    "mismatch": _computeMismatch,
    "sniper": _computeSniper,
    "spectacle": _computeBoomWeek,
    "indemnity": _computeDudInsurance,
    # ── Escalating / Pace Effects ──
    "crescendo": _computeCrescendo,
    "eminence": _computeEminence,
    "traverse": _computeTraverse,
    # ── Chance Synergy Effects ──
    "advantage": _computeAdvantage,
    "catalyst": _computeCatalyst,
    # ── Same-Team Stacking Effects ──
    "stack": _computeStack,
    "backfield_buddies": _computeBackfieldBuddies,
    "homer": _computeHomer,
    "gone_streaking": _computeGoneStreaking,
    "hometown_hero": _computeHometownHero,
    # ── Game-Outcome Effects ──
    "comeback_kid": _computeComebackKid,
    "domination": _computeDomination,
    "walk_off": _computeWalkOff,
    # ── Card-to-Card Interaction Effects ──
    "full_roster": _computeFullRoster,
    "all_in": _computeAllIn,
    "diversified": _computeDiversified,
    "gold_rush": _computeGoldRush,
    "stacked_deck": _computeStackedDeck,
    "copycat": _computeCopycat,
    "chain_reaction": _computeChainReaction,
    "bonus_round": _computeBonusRound,
    "winners_circle": _computeWinnersCircle,
    "no_passengers": _computeNoPassengers,
    "franchise": _computeFranchise,
    "captain": _computeCaptain,
    "metronome": _computeStreakEffect,
    "double_down": _computeLemons,
    "last_resort": _computeLastResort,
    "high_roller": _computeHighRoller,
    "fortitude": _computeIronWill,
    # ── Strategy-Warping Effects ──
    "alchemy": _computeAlchemy,
    "home_alone": _computeAusterity,
    "closer": _computeCloser,
    "dark_horse": _computeHumility,
    "vagabond": _computeVagabond,
    "fat_cat": _computeOpulence,
    "surplus": _computeProsperity,
    "bonsai": _computeCultivation,
    # ── New cards (FP/FPx rebalance) ──
    "anthem": _computeAnthem,
    "conductor": _computeConductor,
    "castaway": _computeCastaway,
    "sleeper": _computeSleeper,
    "patient": _computePatient,
    "rookie_hype": _computeRookieHype,
    "wanderer": _computeWanderer,
    # ── Roster-construction-driven (next-season additions) ──
    "synergy": _computeSynergy,
    "vanguard": _computeVanguard,
    "range": _computeRange,
    "loyalty": _computeLoyalty,
    "charmed": _computeCharmed,
    "cornerstone": _computeCornerstone,
    # ── Diamond stat amplifiers (pre-pass mutates ctx, no own output) ──
    "doubler": _computeDoubler,
    "surveyor": _computeSurveyor,
    "sharpshooter": _computeSharpshooter,
    "sandbagger": _computeStreakEffect,
    "quiet_storm": _computeStreakEffect,
    "drought": _computeStreakEffect,
    # ── Prognostication cards ──
    "nose_picker": _computeStreakEffect,
    "medium": _computeMedium,
    "parlay": _computeParlay,
}


_LOGGED_UNKNOWN_EFFECTS: set = set()

# INVERSE / underdog effects — they reward a BAD game, so a normal "unlock on a good game"
# bar would kill them exactly when they should fire. Their bar runs in reverse: full at 0 FP,
# depleting as the player scores, disabled once the player clears the threshold.
# Effects with NO power bar at all: their trigger IS low scoring — the depicted player's
# own quiet game, a cold roster total, or roster underperformance — so gating them on the
# player showing up would fight the effect. Ungated like the no-effect floor card (owner
# call 2026-07-25).
_UNGATED_EFFECTS = frozenset({
    'hedge', 'snake_eyes', 'drought',        # own / roster-total low FP
    'buy_low', 'reclamation',                # reward roster underperformance
})

# CHANCE cards: their power bar is NOT an on/off gate — its FILL is the trigger probability
# for the enhanced payout (see CARD_CHANCE_* in constants.py). So they're exempt from the
# normal FP on/off gate; the odds are computed inside each compute fn and surfaced as the
# breakdown's chanceThreshold, which the UI renders as the bar.
#   * FP-contributing (Group A): the depicted player's FP fills half the bar, the card's own
#     condition (struggling roster / failed cards) fills the other half, additively.
#   * condition-only (Group C): crescendo/traverse/bonsai already key the odds off the on-card
#     player's own TDs/yardage/growth triggers, so the condition fills the whole bar.
_CHANCE_FP_EFFECTS = frozenset({
    'scrappy', 'sleeper', 'babysitter', 'consolation_prize', 'last_resort',
})
_CHANCE_CONDITION_ONLY_EFFECTS = frozenset({'crescendo', 'traverse', 'bonsai'})
_CHANCE_EFFECTS = _CHANCE_FP_EFFECTS | _CHANCE_CONDITION_ONLY_EFFECTS

# Inverse gate RETIRED. No effect runs the bar in reverse now; the inverse code path is kept
# dormant for possible future use. (The old "underdog"-flavored losers — underdog, martyr,
# rock_bottom, indemnity — were retired in the fusion chance rework, 2026-07-26.)
_INVERSE_GATE_EFFECTS = frozenset()


# What Honor Roll pays the moment its bar fills, as a share of its maximum. The rest is
# earned by beating the bar, up to double it. Above zero on purpose: a card that reads
# ACTIVE has to be worth something, or the bar is lying about what it means.
HONOR_ROLL_BASE_SHARE = 0.35


def buildGateSpec(effectName: str, position: int, classification: str = None,
                  edition: str = None) -> Optional[dict]:
    """The FP power-bar gate frozen into a card's effect_config at mint, or None.

    Every effect-bearing card is gated on the depicted player's weekly FP against a
    position threshold — one stat, one rule, pure on/off. Normal cards unlock once the bar
    fills; INVERSE cards (`_INVERSE_GATE_EFFECTS`) run it in reverse and switch OFF once it
    fills. No per-effect exemptions beyond that; only the no-effect floor card ('none') is
    ungated (owner call 2026-07-23).

    An **All-Pro**-classified card (prior-season All-Pro) lowers ITS OWN threshold by
    `CARD_GATE_ALLPRO_MULT` — an individual accolade buys individual reliability ("the best
    players deliver"). On-card only: baked into this card's frozen gate.threshold, never
    touches any other card. (Champion is a TEAM accolade → it amplifies a team STACK instead;
    see calculateWeekCardBonuses.)"""
    from constants import (CARD_GATE_ENABLED, CARD_GATE_FP_THRESHOLDS,
                           CARD_GATE_FP_THRESHOLDS_BY_EDITION, CARD_GATE_ALLPRO_MULT)
    if not CARD_GATE_ENABLED:
        return None
    # No on/off bar for: the no-effect floor card; effects whose trigger IS low scoring
    # (gating them on the player showing up would fight the effect — see _UNGATED_EFFECTS);
    # or CHANCE cards, whose bar is a probability meter, not an on/off gate (_CHANCE_EFFECTS).
    if (not effectName or effectName in ('none', '')
            or effectName in _UNGATED_EFFECTS or effectName in _CHANCE_EFFECTS):
        return None
    # Edition-scaled: higher rarity depicts a better player + has a higher ceiling, so it
    # needs a higher bar. Fall back to the metallic base row for an unknown/missing edition.
    threshold = (CARD_GATE_FP_THRESHOLDS_BY_EDITION.get(edition, {}).get(position)
                 or CARD_GATE_FP_THRESHOLDS.get(position))
    if not threshold:
        return None
    allPro = bool(classification) and 'all_pro' in classification
    if allPro:
        threshold = max(1, round(threshold * CARD_GATE_ALLPRO_MULT))
    inverse = effectName in _INVERSE_GATE_EFFECTS
    apNote = " (All-Pro)" if allPro else ""
    if inverse:
        text = f"Active while this player stays under {threshold} FP{apNote}"
    else:
        text = f"Unlocks once this player reaches {threshold} FP{apNote}"
    return {'threshold': threshold, 'inverse': inverse, 'text': text, 'allPro': allPro}


def gateRatio(gate: dict, ctx, cardPlayerId: int) -> float:
    """The card's power-bar switch from the depicted player's weekly FP.

    LIVE (and the optimistic-ceiling projection): pure on/off — 1.0 / 0.0. Normal cards are
    on once FP clears the threshold (a bench-warmer never fills the bar); inverse cards are
    on WHILE FP stays under it. Missing FP reads as 0.

    EXPECTED PROJECTION: returns the empirical PROBABILITY the player clears the bar this
    week (fraction of their weekly games meeting the condition, Laplace-smoothed so it's
    never a hard 0/1), so a card near its threshold projects as its expected value instead
    of an all-or-nothing read on the season average. `_applyGateRatio` scales the card's
    output by this fraction, mirroring how chance cards are EV-scaled in projection."""
    threshold = gate.get('threshold', 0) or 0
    if threshold <= 0:
        return 1.0
    inverse = bool(gate.get('inverse'))
    if (getattr(ctx, 'isProjection', False)
            and getattr(ctx, 'projectionVariant', 'expected') == 'expected'):
        weekly = (getattr(ctx, 'playerWeeklyFP', None) or {}).get(cardPlayerId)
        if weekly:
            n = len(weekly)
            clears = sum(1 for fp in weekly if (fp < threshold if inverse else fp >= threshold))
            p = (clears + 1) / (n + 2)  # Laplace-smoothed empirical clear rate
            return max(0.02, min(0.98, p))
        return 0.5  # no weekly history — unknown, not a false certainty
    stats = (getattr(ctx, 'weekPlayerStats', None) or {}).get(cardPlayerId) or {}
    fp = float(stats.get('fantasyPoints', 0) or 0)
    if inverse:
        return 1.0 if fp < threshold else 0.0
    return 1.0 if fp >= threshold else 0.0


def _applyGateRatio(result: 'EffectResult', ratio: float) -> 'EffectResult':
    """Apply the power-bar switch. `ratio` >= 1.0 leaves the effect; 0.0 zeros it. A
    FRACTIONAL ratio (only produced by the expected-value projection) SCALES the output by
    the player's clear probability — live scoring never sees a fraction (gateRatio is pure
    on/off there), so this is a projection-only path."""
    if result is None or ratio >= 1.0:
        return result
    if ratio <= 0.0:
        result.fpBonus = 0.0
        result.floobits = 0
        if result.multBonus and result.multBonus > 1.0:
            result.multBonus = 1.0
        return result
    result.fpBonus = round(result.fpBonus * ratio, 2)
    result.floobits = int(round(result.floobits * ratio))
    if result.multBonus and result.multBonus > 1.0:
        result.multBonus = round(1.0 + (result.multBonus - 1.0) * ratio, 3)
    return result


def computeEffect(effectConfig: dict, ctx, cardPlayerId: int, equippedCardId: int,
                   firstPassBreakdowns=None) -> EffectResult:
    """Dispatch to the named effect's compute function.

    For second-pass effects, firstPassBreakdowns provides the results of all
    first-pass cards so they can react to other cards' outputs.
    """
    effectName = effectConfig.get("effectName", "")
    # No-effect floor cards ('base') carry effectName 'none' (or blank) —
    # they produce nothing on purpose, so return an empty result WITHOUT the
    # unknown-effect warning below.
    if effectName in ("", "none"):
        return EffectResult()
    handler = EFFECT_REGISTRY.get(effectName)
    if not handler:
        # Prior-season templates may reference effects that were removed or
        # renamed in later releases. Log once per unknown name to flag the
        # legacy reference without flooding logs each time a user's
        # collection is projected.
        if effectName not in _LOGGED_UNKNOWN_EFFECTS:
            _LOGGED_UNKNOWN_EFFECTS.add(effectName)
            logger.warning(f"Unknown effect (legacy or removed): {effectName}")
        return EffectResult()

    primary = effectConfig.get("primary", {})

    # For streak effects, stash the effect name on ctx temporarily
    # so the generic streak handler knows which config to look up
    ctx._currentEffectName = effectName

    # Stash first-pass breakdowns on ctx for second-pass effects
    ctx._firstPassBreakdowns = firstPassBreakdowns

    result = handler(primary, ctx, cardPlayerId, equippedCardId)

    # Card gate: scale the card's output by how well its depicted player performed
    # this week (docs/CARD_ONCARD_REBASE_PLAN.md). Applied centrally so every effect
    # obeys it — value effects ramp, cross/hand-modifier effects hard-gate. The ratio
    # is stashed on ctx for the breakdown so the UI can show "142/200 yds → 71%".
    gate = effectConfig.get("gate")
    if gate:
        ratio = gateRatio(gate, ctx, cardPlayerId)
        if getattr(ctx, '_gateRatios', None) is None:
            ctx._gateRatios = {}
        ctx._gateRatios[equippedCardId] = ratio
        result = _applyGateRatio(result, ratio)
    return result


# ─── Streak Condition Checking (for week-end reset logic) ────────────────────

def checkStreakCondition(effectName: str, ctx, cardPlayerId: int) -> bool:
    """Check if a streak card's condition was met this week.

    Called at week end to determine if streak_count should reset.
    Returns True if condition met (streak continues), False if broken.
    """
    config = STREAK_CONFIGS.get(effectName)
    if not config:
        return True

    if config.get("isWeekly"):
        return True  # Weekly streaks always reset, no carry-forward condition

    condition = config.get("resetCondition", "equipped")

    if condition == "equipped":
        return True  # Always met as long as card is equipped

    if condition == "player_cleared_bar":
        # Metronome: the streak grows when the depicted player clears their position
        # FP bar (the same threshold that gates the effect).
        from constants import CARD_GATE_FP_THRESHOLDS
        pos = ctx.rosterPlayerPositions.get(cardPlayerId, 0)
        thr = CARD_GATE_FP_THRESHOLDS.get(pos, 0)
        fp = (ctx.weekPlayerStats.get(cardPlayerId, {}) or {}).get("fantasyPoints", 0) or 0
        return fp >= thr

    # Kicker conditions all share a "no attempt = streak holds" rule:
    # if the offense never reached FG range, the kicker had no chance to
    # fail, so the streak shouldn't reset through no fault of their own.
    if condition == "kicker_fg":
        fgMade, fgAtt, _, _ = _getKickerFgStats(ctx)
        return fgAtt == 0 or fgMade > 0

    if condition == "kicker_2fg":
        fgMade, fgAtt, _, _ = _getKickerFgStats(ctx)
        return fgAtt == 0 or fgMade >= 2

    if condition == "roster_td":
        return ctx.rosterTotalTds > 0

    if condition == "favorite_team_wins":
        return ctx.favoriteTeamWonThisWeek

    if condition == "kicker_45plus":
        _, fgAtt, longest, _ = _getKickerFgStats(ctx)
        return fgAtt == 0 or longest >= 45

    if condition == "kicker_35plus":
        fgMade, fgAtt, longest, _ = _getKickerFgStats(ctx)
        return fgAtt == 0 or longest >= 35  # No attempt = streak maintained

    if condition == "kicker_no_miss":
        fgMade, fgAtt, _, _ = _getKickerFgStats(ctx)
        return fgAtt == 0 or fgMade == fgAtt  # No attempts or perfect

    if condition == "roster_unchanged":
        return ctx.rosterUnchangedWeeks > 0

    if condition == "card_player_td":
        cardPlayerTds = _countPlayerTds(ctx.weekPlayerStats.get(cardPlayerId, {}))
        return cardPlayerTds > 0

    if condition == "roster_75fp":
        # Threshold is 100 despite the condition name — kept the key for
        # backwards-compat with stored STREAK_CONFIGS so no DB migration.
        return ctx.weekRawFP >= 100

    if condition == "favorite_team_upset_win":
        return ctx.favoriteTeamWonThisWeek and ctx.favoriteTeamOpponentElo > ctx.favoriteTeamElo

    # ── Inverse-streak triggers (FP/FPx rebalance) ──
    # All three return True when the roster is UNDERPERFORMING; the streak
    # grows on bad weeks, breaks on good ones (peak-decay handles the tail).
    # Each also requires a near-full roster — these effects are designed
    # for a hand of bad players, not a gutted roster that trivially clears
    # the under-50 / under-5 / no-15 bars.
    if condition == "roster_slot_low_5fp":
        if not _meetsFullRosterRequirement(ctx):
            return False
        # Streak grows if any roster slot scored ≤5 FP this week.
        for pid in (ctx.rosterPlayerIds or set()):
            stats = (ctx.weekPlayerStats or {}).get(pid, {}) or {}
            if float(stats.get("fantasyPoints", 0) or 0) <= 5:
                return True
        return False

    if condition == "no_player_15fp":
        if not _meetsFullRosterRequirement(ctx):
            return False
        # Streak grows if NO roster player scored 15+ FP this week.
        for pid in (ctx.rosterPlayerIds or set()):
            stats = (ctx.weekPlayerStats or {}).get(pid, {}) or {}
            if float(stats.get("fantasyPoints", 0) or 0) >= 15:
                return False
        return True

    if condition == "roster_under_50fp":
        if not _meetsFullRosterRequirement(ctx):
            return False
        # Streak grows if total roster FP this week was under 35.
        # Threshold lowered from 50 — typical rosters score 60+ so 50 was
        # too easy to slip under during a mediocre week, letting Drought
        # streaks chain naturally instead of requiring genuine cold spells.
        # Key name kept as "roster_under_50fp" for backwards-compat with
        # stored STREAK_CONFIGS — no DB migration needed.
        return (ctx.weekRawFP or 0) < 35

    if condition == "card_player_completion_bar":
        return _ladderStat(ctx, cardPlayerId, "passing_stats", "comp") >= _streakBar("completions", 1, 27.7)

    if condition == "card_player_carry_bar":
        return _ladderStat(ctx, cardPlayerId, "rushing_stats", "carries") >= _streakBar("carries", 2, 25.9)

    if condition == "card_player_100_rush_yards":
        return _ladderStat(ctx, cardPlayerId, "rushing_stats", "runYards") >= _streakBar("rushYards", 2, 110.5)

    if condition == "card_player_reception_bar":
        return _ladderStat(ctx, cardPlayerId, "receiving_stats", "receptions") >= _streakBar("receptions", 3, 9.35)

    if condition == "card_player_big_yac":
        return _ladderStat(ctx, cardPlayerId, "receiving_stats", "yac") >= _streakBar("yac", 3, 23.0)

    if condition == "card_player_big_passing_week":
        return _ladderStat(ctx, cardPlayerId, "passing_stats", "passYards") >= _streakBar("passYards", 1, 229.9)

    if condition == "card_player_clean_sheet":
        # Zero bad throws, but only if they actually threw the ball.
        # One errant ball is not a bad week. Demanding a perfect sheet held only 49% of
        # weeks, which is too brittle for a streak to survive on.
        return (_ladderStat(ctx, cardPlayerId, "passing_stats", "throws") > 0
                and _ladderStat(ctx, cardPlayerId, "passing_stats", "badThrows") <= 1)

    if condition == "card_player_100_rec_yards":
        return _ladderStat(ctx, cardPlayerId, "receiving_stats", "rcvYards") >= _streakBar("recYards", 3, 83.5)

    if condition == "card_player_100_contact_yards":
        return _ladderStat(ctx, cardPlayerId, "rushing_stats", "yardsAfterContact") >= _streakBar("yac2", 2, 87.5)

    if condition == "card_player_multi_pin":
        return _ladderStat(ctx, cardPlayerId, "kicking_stats", "puntsInside20") >= _streakBar("puntsIn20", 5, 2.03)

    if condition == "pickem_manual_submit":
        # Streak grows when the user submitted Prognostications manually
        # this week (any auto-pick fill-in breaks the streak).
        return bool(getattr(ctx, 'userManualPickSubmittedThisWeek', False))

    return True
