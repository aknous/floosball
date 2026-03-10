"""
Card Effects — position-based effect system with 53 named variants.

Effects are grouped into 5 categories determined by card position:
  WR → flat_fp      (always awards FP)
  QB → multiplier   (always multiplies FP)
  RB → floobits     (always earns currency)
  TE → conditional  (if/when gate — awards FP, mult, or floobits)
  K  → streak       (grows over time, resets on broken condition)

Edition scales power (Base 1.0x → Diamond 4.0x) and adds secondary effects (Holo+).
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from logger_config import get_logger

logger = get_logger("floosball.cardEffects")


# ─── Position → Category Mapping ────────────────────────────────────────────

POSITION_CATEGORY = {
    1: "multiplier",    # QB
    2: "floobits",      # RB
    3: "flat_fp",       # WR
    4: "conditional",   # TE
    5: "streak",        # K
}

# ─── Edition Power Scaling ───────────────────────────────────────────────────

EDITION_POWER_SCALES = {
    'base': 1.0,
    'chrome': 1.5,
    'holographic': 2.0,
    'gold': 2.5,
    'prismatic': 3.0,
    'diamond': 4.0,
}

# Secondary effects per edition (static, not affected by match bonus)
EDITION_SECONDARY = {
    'base': None,
    'chrome': {"flatFP": 3, "floobits": 0, "mult": 0, "xMult": 0},
    'holographic': {"flatFP": 0, "floobits": 0, "mult": 0.2, "xMult": 0},
    'gold': {"flatFP": 0, "floobits": 5, "mult": 0, "xMult": 0},
    'prismatic': {"flatFP": 0, "floobits": 0, "mult": 0, "xMult": 1.3},
    'diamond': None,  # Generated randomly by buildDiamondSecondary()
}

# Diamond gets 2 of 4 possible secondary effects, randomly selected
_DIAMOND_SECONDARY_OPTIONS = [
    {"flatFP": 3, "floobits": 0, "mult": 0, "xMult": 0},      # +FP
    {"flatFP": 0, "floobits": 0, "mult": 0.2, "xMult": 0},    # +FPx
    {"flatFP": 0, "floobits": 5, "mult": 0, "xMult": 0},      # +Floobits
    {"flatFP": 0, "floobits": 0, "mult": 0, "xMult": 1.3},    # xFPx
]


def buildDiamondSecondary() -> dict:
    """Generate a diamond edition secondary by picking 2 of 4 options."""
    picks = random.sample(_DIAMOND_SECONDARY_OPTIONS, 2)
    return {
        "flatFP": sum(p["flatFP"] for p in picks),
        "floobits": sum(p["floobits"] for p in picks),
        "mult": sum(p["mult"] for p in picks),
        "xMult": max((p["xMult"] for p in picks), default=0),
    }

# ─── Position Conditionals (same as current system) ─────────────────────────

POSITION_CONDITIONALS = {
    1: [  # QB
        {"stat": "passYards", "threshold": 300, "bonus": 5, "label": "300+ pass yards"},
        {"stat": "passTds", "threshold": 3, "bonus": 8, "label": "3+ pass TDs"},
    ],
    2: [  # RB
        {"stat": "rushYards", "threshold": 100, "bonus": 5, "label": "100+ rush yards"},
        {"stat": "rushTds", "threshold": 2, "bonus": 8, "label": "2+ rush TDs"},
    ],
    3: [  # WR
        {"stat": "recYards", "threshold": 100, "bonus": 5, "label": "100+ rec yards"},
        {"stat": "recTds", "threshold": 2, "bonus": 8, "label": "2+ rec TDs"},
    ],
    4: [  # TE
        {"stat": "recYards", "threshold": 75, "bonus": 4, "label": "75+ rec yards"},
        {"stat": "recTds", "threshold": 1, "bonus": 5, "label": "1+ rec TD"},
    ],
    5: [  # K
        {"stat": "fgMade", "threshold": 3, "bonus": 4, "label": "3+ FGs made"},
        {"stat": "longFg", "threshold": 50, "bonus": 5, "label": "50+ yard FG"},
    ],
}

# ─── Effect Display Names ────────────────────────────────────────────────────

EFFECT_DISPLAY_NAMES = {
    # Flat FP (WR)
    "freebie": "Freebie",
    "entourage": "Entourage",
    "touchdown_pinata": "Touchdown Piñata",
    "scrappy": "Scrappy",
    "honor_roll": "Honor Roll",
    "three_pointer": "Three Pointer",
    "garbage_time": "Garbage Time",
    "loyalty_bonus": "Loyalty Bonus",
    "diamond_in_the_rough": "Diamond in the Rough",
    "ride_or_die": "Ride or Die",
    "top_dog": "Top Dog",
    "spotlight_moment": "Spotlight Moment",
    "ace_up_the_sleeve": "Ace Up the Sleeve",
    # Multiplier (QB) — 10 effects
    "big_deal": "Big Deal",
    "trigger_happy": "Trigger Happy",
    "main_character": "Main Character",
    "hype_man": "Hype Man",
    "babysitter": "Babysitter",
    "tank_commander": "Tank Commander",
    "juggernaut": "Juggernaut",
    "hot_roster": "Hot Roster",
    "loyalty_program": "Loyalty Program",
    "underdog": "Underdog",
    "stockpiler": "Stockpiler",
    "house_money": "House Money",
    # Floobits (RB)
    "allowance": "Allowance",
    "cha_ching": "Cha-Ching",
    "piggy_bank": "Piggy Bank",
    "good_neighbor": "Good Neighbor",
    "consolation_prize": "Consolation Prize",
    "rock_bottom": "Rock Bottom",
    "buy_low": "Buy Low",
    "trust_fund": "Trust Fund",
    "rags_to_riches": "Rags to Riches",
    "feeding_frenzy": "Feeding Frenzy",
    "highlight_reel": "Highlight Reel",
    # Conditional (TE)
    "showoff": "Showoff",
    "glow_up": "Glow Up",
    "bandwagon": "Bandwagon",
    "upset_special": "Upset Special",
    "believe": "Believe",
    "schadenfreude": "Schadenfreude",
    "due": "Due",
    "fixer_upper": "Fixer Upper",
    "pedigree": "Pedigree",
    # Streak (K) — 10 effects
    "couch_potato": "Couch Potato",
    "on_fire": "On Fire",
    "gravy_train": "Gravy Train",
    "snowball_fight": "Snowball Fight",
    "fairweather_fan": "Fairweather Fan",
    "bandwagon_express": "Bandwagon Express",
    "touchdown_jackpot": "Touchdown Jackpot",
    "odometer": "Odometer",
    "leg_day": "Leg Day",
    "automatic": "Automatic",
    "hot_hand": "Hot Hand",
    "momentum": "Momentum",
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
    # Flat FP (WR)
    "freebie": "Free real estate",
    "entourage": "Stars attract stars",
    "touchdown_pinata": "Smash for points",
    "scrappy": "Root for the little guy",
    "honor_roll": "Straight A's",
    "three_pointer": "Cash money kicks",
    "garbage_time": "Participation trophies",
    "loyalty_bonus": "Faithful fan rewards",
    "diamond_in_the_rough": "Hidden gems",
    "ride_or_die": "Stop tinkering",
    "top_dog": "Big team energy",
    "spotlight_moment": "Score = bonus",
    "ace_up_the_sleeve": "Hit the mark",
    # Multiplier (QB)
    "big_deal": "Kind of a big deal",
    "trigger_happy": "TDs go brrr",
    "main_character": "It's their story",
    "hype_man": "Your MVP's hype man",
    "babysitter": "Carrying the team",
    "tank_commander": "Embrace the tank",
    "juggernaut": "I'M THE JUGGERNAUT",
    "hot_roster": "Everyone's cooking",
    "loyalty_program": "Rewards member",
    "underdog": "Nothing to lose",
    "stockpiler": "Saving for a rainy day",
    "house_money": "Playing with profit",
    # Floobits (RB)
    "allowance": "Weekly pocket money",
    "cha_ching": "TD = payday",
    "piggy_bank": "Points into coins",
    "good_neighbor": "You're covered.",
    "consolation_prize": "Better luck next time",
    "rock_bottom": "Silver lining",
    "buy_low": "Buy the dip",
    "trust_fund": "Set it and collect",
    "rags_to_riches": "STONKS",
    "feeding_frenzy": "TD feast",
    "highlight_reel": "Big play bonus",
    # Conditional (TE)
    "showoff": "Playing up a level",
    "glow_up": "Overperform = multiply",
    "bandwagon": "Your team wins, you win",
    "upset_special": "Giant slayer",
    "believe": "Playoff vibes only",
    "schadenfreude": "Their loss, your gain",
    "due": "They're due",
    "fixer_upper": "Fixer's bonus",
    "pedigree": "Blue blood benefits",
    # Streak (K)
    "couch_potato": "Don't touch that dial",
    "on_fire": "Keep the flame alive",
    "gravy_train": "All aboard!",
    "snowball_fight": "Getting bigger",
    "fairweather_fan": "Only here for the wins",
    "bandwagon_express": "Choo choo!",
    "touchdown_jackpot": "Weekly TD lottery",
    "odometer": "Racking up miles",
    "leg_day": "Never skip leg day",
    "automatic": "Perfect kicks only",
    "hot_hand": "He can't miss",
    "momentum": "Rolling",
}

EFFECT_TOOLTIPS = {
    # Flat FP (WR)
    "freebie": "It pays to show up. Bonus FP every week just for having this card equipped.",
    "entourage": "Squad goals. Bonus FP for each high-rated player on your roster.",
    "touchdown_pinata": "Every house call fills the piñata. Bonus FP per roster TD.",
    "scrappy": "Somebody's gotta believe in them. Bonus FP for each low-rated roster player.",
    "honor_roll": "Good grades get rewarded. Bonus FP for each roster player putting up a solid score.",
    "three_pointer": "Three points for them, bonus for you. FP for every kicker FG.",
    "garbage_time": "Hey, they showed up. Bonus FP for each roster player who doesn't score a TD.",
    "loyalty_bonus": "Bandwagoning encouraged. Bonus FP based on your favorite team's win streak.",
    "diamond_in_the_rough": "They believed before you did. Bonus FP per overperforming roster player.",
    "ride_or_die": "Put the phone down. FP that grows each week you don't touch your roster. Resets if you make a swap.",
    "top_dog": "Good teams radiate good vibes. FP based on your favorite team's ELO.",
    "spotlight_moment": "Their spotlight is your payday. FP whenever the card player finds the endzone.",
    "ace_up_the_sleeve": "Always have something up your sleeve. Bonus when the card player hits a stat threshold.",
    # Multiplier (QB)
    "big_deal": "Get that bag. Flat xFPx on your total score.",
    "trigger_happy": "Touchdowns go brrr. +FPx that stacks per roster TD.",
    "main_character": "Plot armor activated. xFPx that increases when the card player gains FP.",
    "hype_man": "The crowd goes wild. xFPx that stacks with each TD the card player scores.",
    "babysitter": "Someone's gotta carry. +FPx for each roster player having a rough week.",
    "tank_commander": "Pain builds character (and +FPx). Grows when your favorite team loses a game.",
    "juggernaut": "Momentum is a beautiful thing. xFPx grows with every win in your favorite team's win streak.",
    "hot_roster": "When they're hot, they're HOT. +FPx per overperforming roster player.",
    "loyalty_program": "Set it and forget it. +FPx that grows each week your roster doesn't change.",
    "underdog": "The worse they are, the harder this slaps. xFPx is higher when your favorite team ELO is lower.",
    "stockpiler": "Patience pays. xFPx that grows with each unused roster swap you're sitting on.",
    "house_money": "Upset city. xFPx that builds every time your favorite team wins as an underdog.",
    # Floobits (RB)
    "allowance": "Don't spend it all in one place. Free Floobits every week just for existing.",
    "cha_ching": "The endzone is your cash register. Floobits for every TD the card player scores.",
    "piggy_bank": "Automatic savings plan. Converts a chunk of your roster's total FP into Floobits.",
    "good_neighbor": "At least something good came out of it. Floobits when your kicker misses a FG.",
    "consolation_prize": "Here's a little something for your troubles. Floobits per roster player having a bad week.",
    "rock_bottom": "Rock bottom has a cash reward. Floobits for every loss in your favorite team's losing streak.",
    "buy_low": "Buy low, sell... whenever. Floobits for every underperforming roster player.",
    "trust_fund": "The lazy investor strategy. Floobits that grow each week your roster stays unchanged.",
    "rags_to_riches": "Bad teams fund good portfolios. The lower your favorite team's ELO, the higher the Floobits.",
    "feeding_frenzy": "Dinner is served. Floobits when your roster scores enough TDs in a week.",
    "highlight_reel": "Highlight reel material pays. Floobits for every big play your favorite team pulls off.",
    # Conditional (TE)
    "showoff": "Love a good flex. FP when the card player is overperforming.",
    "glow_up": "Overachievement looks good on you. xFPx when the card player is overperforming.",
    "bandwagon": "Bandwagoning has never been so rewarding. +FPx whenever your favorite team wins.",
    "upset_special": "David vs Goliath energy. xFPx when your favorite team beats a higher-rated opponent.",
    "believe": "Keep the dream alive. FP as long as your favorite team holds a playoff spot.",
    "schadenfreude": "You feel bad about it. But also... free points. FP when the card player's team loses.",
    "due": "Redemption tastes sweet. xFPx when your favorite team snaps a long losing streak.",
    "fixer_upper": "Someone's gotta fix this mess. FP when most of your roster is underperforming.",
    "pedigree": "Good breeding shows. xFPx when your favorite team's ELO is high enough.",
    # Streak (K)
    "couch_potato": "Just sit there. Literally. FP that grows every week this card stays equipped.",
    "on_fire": "Don't let the flame die. xFPx that grows each week the card player makes a FG. Resets if they don't.",
    "gravy_train": "The gravy train keeps rolling. Floobits growing each week the card player's team wins. Resets on a loss.",
    "snowball_fight": "It just keeps getting bigger. FP growing each week your roster scores a TD. Resets if they don't.",
    "fairweather_fan": "Fair-weather fandom has its perks. Floobits growing each week your favorite team wins. Resets on a loss.",
    "bandwagon_express": "Next stop: more points. FP growing each week your favorite team wins. Resets on a loss.",
    "touchdown_jackpot": "Fresh lottery every week. Floobits stacking per roster TD, resets weekly.",
    "odometer": "Miles and miles of yards. FP ticking up per chunk of roster yards, resets weekly.",
    "leg_day": "Never skip it. FP growing each week the card player nails a 45+ yard FG. Resets if they don't.",
    "automatic": "Perfection pays. FPx growing each week the card player doesn't miss a FG. Resets on a miss.",
    "hot_hand": "Feed the hot hand. xFPx grows each week the card player scores a TD. Resets if they don't.",
    "momentum": "Can't stop won't stop. xFPx grows each week your roster breaks 50 FP. Resets if they don't.",
}

EFFECT_DETAIL_TEMPLATES = {
    # Flat FP (WR)
    "freebie": "+{baseFP} FP per week",
    "entourage": "+{perPlayerFP} FP for every roster player with {minStars}★+",
    "touchdown_pinata": "+{perTdFP} FP for every TD your roster scores",
    "scrappy": "+{perPlayerFP} FP for every roster player with {maxStars}★ or lower",
    "honor_roll": "+{perPlayerFP} FP per roster player with {fpThreshold}+ FP",
    "three_pointer": "+{perFgFP} FP for every FG your roster's K makes",
    "garbage_time": "+{perPlayerFP} FP for every roster player with 0 TDs",
    "loyalty_bonus": "+{perStreakFP} FP equal to your fav team's win streak",
    "diamond_in_the_rough": "+{perPlayerFP} FP per overperforming roster player",
    "ride_or_die": "+{baseReward} FP, +{growthPerTick} per week roster is unchanged. Resets on swap",
    "top_dog": "FP scales with how far above league average your fav team is",
    "spotlight_moment": "+{rewardValue} FP when card player scores a TD",
    "ace_up_the_sleeve": "+{rewardValue} FP if card player gets {threshold}+ {statDisplay}",
    # Multiplier (QB) — +FPx
    "trigger_happy": "+{perTdMult} FPx per roster TD",
    "babysitter": "+{perPlayerMult} FPx per roster player under {fpThreshold} FP",
    "tank_commander": "+{perLossMult} FPx per fav team loss",
    "hot_roster": "+{perPlayerMult} FPx per overperforming roster player",
    "loyalty_program": "+{baseMult} FPx base, grows by {growthPerWeek} per unchanged week",
    # Multiplier (QB) — xFPx
    "big_deal": "×{xMultValue} xFPx",
    "main_character": "xFPx grows the more FP the card player scores",
    "hype_man": "+{perTdXMult} xFPx per card player TD",
    "juggernaut": "×{baseXMult} xFPx, grows by {growthPerWin} per fav team win streak",
    "underdog": "xFPx scales with how far below league average your fav team is",
    "stockpiler": "×{perSwapXMult} xFPx per unused roster swap",
    "house_money": "×{baseXMult} xFPx base, +{perUpsetXMult} per fav team upset win this season",
    # Floobits (RB)
    "allowance": "{floobits} Floobits per week",
    "cha_ching": "{perTdFloobits} Floobits per card player TD",
    "piggy_bank": "{fpPercent}% of roster FP → Floobits",
    "good_neighbor": "{perMissFloobits} Floobits per missed FG",
    "consolation_prize": "{perPlayerFloobits} Floobits per roster player under {fpThreshold} FP",
    "rock_bottom": "{perStreakFloobits} Floobits per loss in fav team's streak",
    "buy_low": "{perPlayerFloobits} Floobits per underperforming roster player",
    "trust_fund": "{baseFloobits} Floobits base, +{growthPerWeek} per unchanged week",
    "rags_to_riches": "Floobits scale with how far below league average your fav team is",
    "feeding_frenzy": "{rewardValue} Floobits when roster scores {tdThreshold}+ TDs",
    "highlight_reel": "{rewardValue} Floobits per fav team big play",
    # Conditional (TE)
    "showoff": "+{rewardValue} FP when card player is overperforming",
    "glow_up": "×{rewardValue} xFPx when card player is overperforming",
    "bandwagon": "+{rewardValue} FPx when fav team wins",
    "upset_special": "×{rewardValue} xFPx when fav team beats a higher-ELO team",
    "believe": "+{rewardValue} FP while fav team is in a playoff spot",
    "schadenfreude": "+{rewardValue} FP when card player's team loses",
    "due": "×{rewardValue} xFPx when fav team snaps a {streakThreshold}+ game losing streak",
    "fixer_upper": "+{rewardValue} FP when majority of roster is underperforming",
    "pedigree": "×{rewardValue} xFPx when fav team ELO ≥ {eloThreshold}",
    # Streak (K)
    "couch_potato": "+{baseReward} FP, grows by {growthPerTick} each week equipped",
    "on_fire": "×{baseReward} xFPx, +{growthPerTick} per consecutive FG week. Resets if no FG",
    "gravy_train": "{baseReward} Floobits, +{growthPerTick} per consecutive team win. Resets on loss",
    "snowball_fight": "+{baseReward} FP, +{growthPerTick} per consecutive roster TD week. Resets if no TD",
    "fairweather_fan": "{baseReward} Floobits, +{growthPerTick} per consecutive fav team win. Resets on loss",
    "bandwagon_express": "+{baseReward} FP, +{growthPerTick} per consecutive fav team win. Resets on loss",
    "touchdown_jackpot": "{baseReward} Floobits on 1st TD, +{growthPerTick} more per TD after. Resets weekly",
    "odometer": "+{baseReward} FP per {yardsPerTick} yards, +{growthPerTick} more each time. Resets weekly",
    "leg_day": "+{baseReward} FP, +{growthPerTick} per consecutive 45+ yd FG week. Resets if no 45+ FG",
    "automatic": "+{baseReward} FPx, +{growthPerTick} per consecutive perfect FG week. Resets on a miss",
    "hot_hand": "×{baseReward} xFPx, +{growthPerTick} per consecutive week card player scores a TD. Resets if no TD",
    "momentum": "×{baseReward} xFPx, +{growthPerTick} per consecutive week roster scores 50+ FP. Resets if under 50",
}

# ─── Category Effect Pools (weighted random selection) ───────────────────────

CATEGORY_EFFECT_POOLS = {
    "flat_fp": [
        ("freebie", 10),
        ("entourage", 8),
        ("touchdown_pinata", 8),
        ("scrappy", 7),
        ("honor_roll", 7),
        ("three_pointer", 6),
        ("garbage_time", 5),
        ("loyalty_bonus", 5),
        ("diamond_in_the_rough", 5),
        ("top_dog", 5),
        ("spotlight_moment", 7),
        ("ace_up_the_sleeve", 6),
    ],
    "multiplier": [
        ("big_deal", 10),
        ("trigger_happy", 8),
        ("main_character", 7),
        ("hype_man", 7),
        ("babysitter", 6),
        ("tank_commander", 5),
        ("juggernaut", 6),
        ("hot_roster", 5),
        ("loyalty_program", 4),
        ("underdog", 5),
        ("stockpiler", 6),
        ("house_money", 5),
    ],
    "floobits": [
        ("allowance", 10),
        ("cha_ching", 8),
        ("piggy_bank", 7),
        ("good_neighbor", 6),
        ("consolation_prize", 6),
        ("rock_bottom", 5),
        ("buy_low", 5),
        ("trust_fund", 4),
        ("rags_to_riches", 5),
        ("feeding_frenzy", 6),
        ("highlight_reel", 4),
    ],
    "conditional": [
        ("showoff", 7),
        ("glow_up", 6),
        ("bandwagon", 8),
        ("upset_special", 5),
        ("believe", 6),
        ("schadenfreude", 5),
        ("due", 4),
        ("fixer_upper", 5),
        ("pedigree", 5),
    ],
    "streak": [
        ("couch_potato", 10),
        ("on_fire", 7),
        ("gravy_train", 7),
        ("snowball_fight", 8),
        ("fairweather_fan", 7),
        ("bandwagon_express", 5),
        ("touchdown_jackpot", 6),
        ("odometer", 5),
        ("ride_or_die", 5),
        ("leg_day", 4),
        ("automatic", 4),
        ("hot_hand", 5),
        ("momentum", 5),
    ],
}

# ─── Streak Configuration ────────────────────────────────────────────────────

# resetCondition: what breaks the streak (checked at week end)
# isWeekly: if True, streak resets each week (accumulates within a week)
STREAK_CONFIGS = {
    "couch_potato":      {"resetCondition": "equipped", "isWeekly": False},
    "on_fire":           {"resetCondition": "kicker_fg", "isWeekly": False},
    "gravy_train":       {"resetCondition": "card_player_team_wins", "isWeekly": False},
    "snowball_fight":    {"resetCondition": "roster_td", "isWeekly": False},
    "fairweather_fan":   {"resetCondition": "favorite_team_wins", "isWeekly": False},
    "bandwagon_express": {"resetCondition": "favorite_team_wins", "isWeekly": False},
    "touchdown_jackpot": {"resetCondition": None, "isWeekly": True},
    "odometer":          {"resetCondition": None, "isWeekly": True},
    "ride_or_die":       {"resetCondition": "roster_unchanged", "isWeekly": False},
    "leg_day":           {"resetCondition": "kicker_45plus", "isWeekly": False},
    "automatic":         {"resetCondition": "kicker_no_miss", "isWeekly": False},
    "hot_hand":          {"resetCondition": "card_player_td", "isWeekly": False},
    "momentum":          {"resetCondition": "roster_50fp", "isWeekly": False},
    "house_money":       {"resetCondition": "favorite_team_upset_win", "isWeekly": False, "noReset": True},
}


# ─── EffectResult ────────────────────────────────────────────────────────────

@dataclass
class EffectResult:
    """Result of computing a single card's primary effect."""
    fpBonus: float = 0.0
    floobits: int = 0
    multBonus: float = 0.0   # +FPx: additive mult pool
    xMultBonus: float = 0.0  # xFPx: multiplicative mult pool
    equation: str = ""       # Human-readable equation showing how value was derived


# ─── Primary Parameter Builders ──────────────────────────────────────────────
# Each effect has base values scaled by playerRating and editionScale.
# ratingNorm = playerRating - 60 (range 0–40 for ratings 60–100)

def _buildFlatFPParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "freebie":
        return {"baseFP": round((2 + rn * 0.075) * editionScale, 1)}
    if effectName == "entourage":
        return {"perPlayerFP": round((0.6 + rn * 0.025) * editionScale, 1), "minStars": 3}
    if effectName == "touchdown_pinata":
        return {"perTdFP": round((0.8 + rn * 0.03) * editionScale, 1)}
    if effectName == "scrappy":
        return {"perPlayerFP": round((1.0 + rn * 0.03) * editionScale, 1), "maxStars": 2}
    if effectName == "honor_roll":
        return {"perPlayerFP": round((0.7 + rn * 0.025) * editionScale, 1), "fpThreshold": 15}
    if effectName == "three_pointer":
        return {"perFgFP": round((1.5 + rn * 0.05) * editionScale, 1)}
    if effectName == "garbage_time":
        return {"perPlayerFP": round((0.5 + rn * 0.02) * editionScale, 1)}
    if effectName == "loyalty_bonus":
        return {"perStreakFP": round((0.8 + rn * 0.03) * editionScale, 1)}
    if effectName == "diamond_in_the_rough":
        return {"perPlayerFP": round((0.7 + rn * 0.025) * editionScale, 1)}
    if effectName == "top_dog":
        fpPer100 = round((0.2 + rn * 0.01) * editionScale, 1)
        return {"fpPer100Elo": fpPer100, "fpAt1500": round(fpPer100 * 15, 1)}
    if effectName == "spotlight_moment":
        return {"rewardType": "fp", "rewardValue": round((5 + rn * 0.2) * editionScale, 1)}
    if effectName == "ace_up_the_sleeve":
        return {"rewardType": "fp", "rewardValue": round((4 + rn * 0.15) * editionScale, 1),
                "stat": "recYards", "threshold": 75}
    return {"baseFP": round(2 * editionScale, 1)}


def _buildMultiplierParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    # ── +FPx effects (additive mult pool) ──
    if effectName == "trigger_happy":
        return {"perTdMult": round((0.1 + rn * 0.005) * editionScale, 1)}
    if effectName == "babysitter":
        return {"perPlayerMult": round((0.1 + rn * 0.005) * editionScale, 1), "fpThreshold": 8}
    if effectName == "tank_commander":
        return {"perLossMult": round((0.1 + rn * 0.005) * editionScale, 1)}
    if effectName == "hot_roster":
        return {"perPlayerMult": round((0.1 + rn * 0.005) * editionScale, 1)}
    if effectName == "loyalty_program":
        return {"baseMult": round((0.1 + rn * 0.005) * editionScale, 1),
                "growthPerWeek": round((0.1 + rn * 0.003) * editionScale, 1)}
    # ── xFPx effects (multiplicative, values > 1) ──
    if effectName == "big_deal":
        return {"xMultValue": round(1 + (playerRating / 100) * 0.5 * editionScale, 1)}
    if effectName == "main_character":
        return {"fpShareScale": round((0.5 + rn * 0.025) * editionScale, 1)}
    if effectName == "hype_man":
        return {"perTdXMult": round((0.1 + rn * 0.005) * editionScale, 2)}
    if effectName == "juggernaut":
        return {"baseXMult": round(1 + (0.1 + rn * 0.003) * editionScale, 1),
                "growthPerWin": round((0.1 + rn * 0.003) * editionScale, 1)}
    if effectName == "underdog":
        return {"eloPer100": round((0.1 + rn * 0.005) * editionScale, 1)}
    if effectName == "stockpiler":
        basePerSwap = 0.05
        return {"perSwapXMult": round(basePerSwap * editionScale, 3)}
    if effectName == "house_money":
        return {"baseXMult": round(1 + (0.1 + rn * 0.003) * editionScale, 1),
                "perUpsetXMult": round((0.1 + rn * 0.003) * editionScale, 1)}
    return {"multPercent": round(0.2 * editionScale, 1)}


def _buildFloobitsParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "allowance":
        return {"floobits": int(round((5 + rn * 0.3) * editionScale))}
    if effectName == "cha_ching":
        return {"perTdFloobits": int(round((3 + rn * 0.15) * editionScale))}
    if effectName == "piggy_bank":
        return {"fpPercent": int(round((3 + rn * 0.1) * editionScale))}
    if effectName == "good_neighbor":
        return {"perMissFloobits": int(round((5 + rn * 0.2) * editionScale))}
    if effectName == "consolation_prize":
        return {"perPlayerFloobits": int(round((2 + rn * 0.1) * editionScale)), "fpThreshold": 5}
    if effectName == "rock_bottom":
        return {"perStreakFloobits": int(round((3 + rn * 0.15) * editionScale))}
    if effectName == "buy_low":
        return {"perPlayerFloobits": int(round((2 + rn * 0.1) * editionScale))}
    if effectName == "trust_fund":
        return {"baseFloobits": int(round((2 + rn * 0.1) * editionScale)),
                "growthPerWeek": int(round((1 + rn * 0.05) * editionScale))}
    if effectName == "rags_to_riches":
        per100 = int(round((1 + rn * 0.05) * editionScale))
        return {"floobitsPer100Elo": per100, "floobitsAt1200": per100 * 3}
    if effectName == "feeding_frenzy":
        return {"rewardType": "floobits", "rewardValue": int(round((8 + rn * 0.3) * editionScale)),
                "tdThreshold": 3}
    if effectName == "highlight_reel":
        return {"rewardType": "floobits", "rewardValue": int(round((3 + rn * 0.15) * editionScale)),
                "wpaThreshold": 10.0}
    return {"floobits": int(round(5 * editionScale))}


def _buildConditionalParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "showoff":
        return {"rewardType": "fp", "rewardValue": round((3 + rn * 0.12) * editionScale, 1)}
    if effectName == "glow_up":
        return {"rewardType": "xmult", "rewardValue": round(1 + (0.2 + rn * 0.01) * editionScale, 1)}
    if effectName == "bandwagon":
        return {"rewardType": "mult", "rewardValue": round((0.3 + rn * 0.015) * editionScale, 1)}
    if effectName == "upset_special":
        return {"rewardType": "xmult", "rewardValue": round(1 + (0.4 + rn * 0.02) * editionScale, 1)}
    if effectName == "believe":
        return {"rewardType": "fp", "rewardValue": round((3 + rn * 0.1) * editionScale, 1)}
    if effectName == "schadenfreude":
        return {"rewardType": "fp", "rewardValue": round((3 + rn * 0.1) * editionScale, 1)}
    if effectName == "due":
        return {"rewardType": "xmult", "rewardValue": round(1 + (0.4 + rn * 0.02) * editionScale, 1),
                "streakThreshold": 3}
    if effectName == "fixer_upper":
        return {"rewardType": "fp", "rewardValue": round((4 + rn * 0.15) * editionScale, 1)}
    if effectName == "pedigree":
        return {"rewardType": "xmult", "rewardValue": round(1 + (0.3 + rn * 0.015) * editionScale, 1),
                "eloThreshold": 1600}
    return {"rewardType": "fp", "rewardValue": round(3 * editionScale, 1)}


def _buildStreakParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "couch_potato":
        return {"rewardType": "fp",
                "baseReward": round((1.0 + rn * 0.04) * editionScale, 1),
                "growthPerTick": round((0.5 + rn * 0.02) * editionScale, 1)}
    if effectName == "ride_or_die":
        return {"rewardType": "fp",
                "baseReward": round((0.5 + rn * 0.02) * editionScale, 1),
                "growthPerTick": round((0.3 + rn * 0.01) * editionScale, 1)}
    if effectName == "on_fire":
        return {"rewardType": "xmult",
                "baseReward": round(1 + (0.1 + rn * 0.005) * editionScale, 1),
                "growthPerTick": round((0.1 + rn * 0.003) * editionScale, 1)}
    if effectName == "gravy_train":
        return {"rewardType": "floobits",
                "baseReward": int(round((3 + rn * 0.15) * editionScale)),
                "growthPerTick": int(round((1 + rn * 0.05) * editionScale))}
    if effectName == "snowball_fight":
        return {"rewardType": "fp",
                "baseReward": round((1.0 + rn * 0.04) * editionScale, 1),
                "growthPerTick": round((0.5 + rn * 0.02) * editionScale, 1)}
    if effectName == "fairweather_fan":
        return {"rewardType": "floobits",
                "baseReward": int(round((2 + rn * 0.1) * editionScale)),
                "growthPerTick": int(round((1 + rn * 0.04) * editionScale))}
    if effectName == "bandwagon_express":
        return {"rewardType": "fp",
                "baseReward": round((1.5 + rn * 0.06) * editionScale, 1),
                "growthPerTick": round((0.5 + rn * 0.02) * editionScale, 1)}
    if effectName == "touchdown_jackpot":
        return {"rewardType": "floobits",
                "baseReward": int(round((2 + rn * 0.1) * editionScale)),
                "growthPerTick": int(round((1 + rn * 0.05) * editionScale))}
    if effectName == "odometer":
        return {"rewardType": "fp",
                "baseReward": round((0.5 + rn * 0.02) * editionScale, 1),
                "growthPerTick": round((0.2 + rn * 0.01) * editionScale, 1),
                "yardsPerTick": 50}
    if effectName == "leg_day":
        return {"rewardType": "fp",
                "baseReward": round((1.5 + rn * 0.06) * editionScale, 1),
                "growthPerTick": round((0.5 + rn * 0.02) * editionScale, 1)}
    if effectName == "automatic":
        return {"rewardType": "mult",
                "baseReward": round((0.1 + rn * 0.005) * editionScale, 1),
                "growthPerTick": round((0.1 + rn * 0.003) * editionScale, 1)}
    if effectName == "hot_hand":
        return {"rewardType": "xmult",
                "baseReward": round(1 + (0.1 + rn * 0.005) * editionScale, 1),
                "growthPerTick": round((0.1 + rn * 0.003) * editionScale, 1)}
    if effectName == "momentum":
        return {"rewardType": "xmult",
                "baseReward": round(1 + (0.1 + rn * 0.005) * editionScale, 1),
                "growthPerTick": round((0.1 + rn * 0.003) * editionScale, 1)}
    return {"rewardType": "fp", "baseReward": round(1.0 * editionScale, 1), "growthPerTick": round(0.5 * editionScale, 1)}


_PARAM_BUILDERS = {
    "flat_fp": _buildFlatFPParams,
    "multiplier": _buildMultiplierParams,
    "floobits": _buildFloobitsParams,
    "conditional": _buildConditionalParams,
    "streak": _buildStreakParams,
}


# ─── Config Builder ──────────────────────────────────────────────────────────

def buildEffectConfig(edition: str, playerRating: int, position: int, teamId=None) -> dict:
    """Build the effect_config JSON for a new card template.

    Position determines the effect category, edition scales the power,
    and a random variant is selected from the category's pool.
    """
    category = POSITION_CATEGORY.get(position, "flat_fp")
    pool = CATEGORY_EFFECT_POOLS.get(category, [("freebie", 1)])

    names, weights = zip(*pool)
    effectName = random.choices(names, weights=weights, k=1)[0]

    editionScale = EDITION_POWER_SCALES.get(edition, 1.0)
    secondary = EDITION_SECONDARY.get(edition)
    if secondary is None and edition == 'diamond':
        secondary = buildDiamondSecondary()

    builder = _PARAM_BUILDERS.get(category, _buildFlatFPParams)
    primary = builder(effectName, playerRating, editionScale)

    conditionals = POSITION_CONDITIONALS.get(position, [])
    conditional = conditionals[0] if conditionals else None

    streakConfig = STREAK_CONFIGS.get(effectName) if category == "streak" else None

    tagline = EFFECT_TAGLINES.get(effectName, "")
    tooltip = EFFECT_TOOLTIPS.get(effectName, "")

    # Build detail from template — fill in primary params + stat display names
    detail = EFFECT_DETAIL_TEMPLATES.get(effectName, "")
    for key, val in primary.items():
        detail = detail.replace("{" + key + "}", str(val))
    # Handle {statDisplay} for ace_up_the_sleeve and similar
    statKey = primary.get("stat", "")
    if statKey:
        detail = detail.replace("{statDisplay}", STAT_DISPLAY_NAMES.get(statKey, statKey))

    return {
        "effectName": effectName,
        "displayName": EFFECT_DISPLAY_NAMES.get(effectName, effectName),
        "category": category,
        "primary": primary,
        "editionScale": editionScale,
        "secondary": secondary,
        "tagline": tagline,
        "tooltip": tooltip,
        "detail": detail,
        "streakConfig": streakConfig,
        "conditional": conditional,
    }


# ─── Effect Compute Functions ────────────────────────────────────────────────
# Each function receives (primary: dict, ctx: CardCalcContext, cardPlayerId: int,
#   equippedCardId: int) and returns an EffectResult.
# CardCalcContext is imported at function call time to avoid circular imports.

def _playerStars(rating: int) -> int:
    """Convert a player rating to 1-5 stars. Bands: 1★60-67, 2★68-75, 3★76-83, 4★84-91, 5★92+."""
    return min(5, max(1, (rating - 60) // 8 + 1))


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
    """Return (fgMade, fgAtt, longest) for the roster's kicker."""
    kickerStats = _getKickerStats(ctx)
    ks = kickerStats.get("kicking_stats", {})
    if not isinstance(ks, dict):
        return (0, 0, 0)
    return (ks.get("fgs", 0), ks.get("fgAtt", 0), ks.get("longest", 0))


# ── Flat FP (WR) ─────────────────────────────────────────────────────────────

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
    maxStars = primary.get("maxStars", 2)
    perPlayer = primary.get("perPlayerFP", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) <= maxStars)
    eq = f"{perPlayer}/player × {count} ({maxStars}★ or lower)"
    return EffectResult(fpBonus=perPlayer * count, equation=eq)


def _computeHonorRoll(primary, ctx, cardPlayerId, eqId):
    threshold = primary.get("fpThreshold", 15)
    perPlayer = primary.get("perPlayerFP", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) >= threshold)
    eq = f"{perPlayer}/player × {count} ({threshold}+ FP)"
    return EffectResult(fpBonus=perPlayer * count, equation=eq)


def _computeThreePointer(primary, ctx, cardPlayerId, eqId):
    fgMade, _, _ = _getKickerFgStats(ctx)
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
    perPlayer = primary.get("perPlayerFP", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) > ctx.rosterPlayerRatings.get(pid, 60))
    eq = f"{perPlayer}/player × {count} overperforming"
    return EffectResult(fpBonus=perPlayer * count, equation=eq)



def _computeTopDog(primary, ctx, cardPlayerId, eqId):
    fpPer100 = primary.get("fpPer100Elo", 0)
    eloAboveAvg = max(0, (ctx.favoriteTeamElo - ctx.leagueAverageElo) / 100)
    eloDiff = round(ctx.favoriteTeamElo - ctx.leagueAverageElo)
    eq = f"{fpPer100}/100 ELO × {eloDiff:+d} ELO vs avg"
    return EffectResult(fpBonus=fpPer100 * eloAboveAvg, equation=eq)


# ── Multiplier (QB) ──────────────────────────────────────────────────────────

def _computeBigDeal(primary, ctx, cardPlayerId, eqId):
    val = primary.get("xMultValue", 1.0)
    return EffectResult(xMultBonus=val)


def _computeTriggerHappy(primary, ctx, cardPlayerId, eqId):
    perTd = primary.get("perTdMult", 0)
    tds = ctx.rosterTotalTds
    eq = f"{perTd}x/TD × {tds} roster TDs"
    return EffectResult(multBonus=perTd * tds, equation=eq)


def _computeMainCharacter(primary, ctx, cardPlayerId, eqId):
    cardPlayerFP = ctx.weekPlayerStats.get(cardPlayerId, {}).get("fantasyPoints", 0)
    fpShare = cardPlayerFP / max(ctx.weekRawFP, 1)
    scale = primary.get("fpShareScale", 0)
    eq = f"1 + {scale} × {round(fpShare * 100)}% FP share"
    return EffectResult(xMultBonus=1 + scale * fpShare, equation=eq)


def _computeHypeMan(primary, ctx, cardPlayerId, eqId):
    cardPlayerTds = _countPlayerTds(ctx.weekPlayerStats.get(cardPlayerId, {}))
    perTd = primary.get("perTdXMult", primary.get("xMultValue", 0))
    if cardPlayerTds > 0:
        xMult = 1 + perTd * cardPlayerTds
        eq = f"1 + {perTd}x × {cardPlayerTds} player TD{'s' if cardPlayerTds != 1 else ''}"
        return EffectResult(xMultBonus=xMult, equation=eq)
    return EffectResult(equation=f"{perTd}x/TD × 0 player TDs")


def _computeBabysitter(primary, ctx, cardPlayerId, eqId):
    threshold = primary.get("fpThreshold", 8)
    perPlayer = primary.get("perPlayerMult", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
    eq = f"{perPlayer}x/player × {count} (under {threshold} FP)"
    return EffectResult(multBonus=perPlayer * count, equation=eq)


def _computeTankCommander(primary, ctx, cardPlayerId, eqId):
    perLoss = primary.get("perLossMult", 0)
    losses = ctx.favoriteTeamSeasonLosses
    eq = f"{perLoss}x/loss × {losses} team losses"
    return EffectResult(multBonus=perLoss * losses, equation=eq)


def _computeJuggernaut(primary, ctx, cardPlayerId, eqId):
    streak = max(0, ctx.favoriteTeamStreak)
    if streak == 0:
        return EffectResult(equation="waiting for team win streak")
    baseX = primary.get("baseXMult", 1.1)
    growth = primary.get("growthPerWin", 0.1)
    eq = f"{baseX}x base + {growth}x × {streak - 1} extra wins"
    return EffectResult(xMultBonus=baseX + growth * (streak - 1), equation=eq)


def _computeHotRoster(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerMult", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) > ctx.rosterPlayerRatings.get(pid, 60))
    eq = f"{perPlayer}x/player × {count} overperforming"
    return EffectResult(multBonus=perPlayer * count, equation=eq)


def _computeLoyaltyProgram(primary, ctx, cardPlayerId, eqId):
    baseMult = primary.get("baseMult", 0)
    growth = primary.get("growthPerWeek", 0)
    weeks = max(0, ctx.rosterUnchangedWeeks)
    eq = f"{baseMult}x base + {growth}x × {weeks} wks unchanged"
    return EffectResult(multBonus=baseMult + growth * weeks, equation=eq)


def _computeUnderdog(primary, ctx, cardPlayerId, eqId):
    eloPer100 = primary.get("eloPer100", 0)
    eloBelowAvg = max(0, (ctx.leagueAverageElo - ctx.favoriteTeamElo) / 100)
    eloDiff = round(ctx.leagueAverageElo - ctx.favoriteTeamElo)
    if eloBelowAvg == 0:
        return EffectResult(equation="team not below avg ELO")
    eq = f"1 + {eloPer100}x × {eloDiff} ELO below avg"
    return EffectResult(xMultBonus=1 + eloPer100 * eloBelowAvg, equation=eq)


def _computeStockpiler(primary, ctx, cardPlayerId, eqId):
    perSwap = primary.get("perSwapXMult", 0.05)
    unusedSwaps = ctx.unusedSwaps
    if unusedSwaps <= 0:
        return EffectResult(equation="no unused swaps")
    eq = f"1 + {perSwap}x × {unusedSwaps} unused swaps"
    return EffectResult(xMultBonus=1 + unusedSwaps * perSwap, equation=eq)


def _computeHouseMoney(primary, ctx, cardPlayerId, eqId):
    baseXMult = primary.get("baseXMult", 1.0)
    perUpset = primary.get("perUpsetXMult", 0)
    upsetWins = max(0, ctx.streakCounts.get(eqId, 1) - 1)  # streak_count starts at 1
    xMult = baseXMult + perUpset * upsetWins
    eq = f"{baseXMult} base + {perUpset}x × {upsetWins} upset wins"
    return EffectResult(xMultBonus=xMult, equation=eq)


# ── Floobits (RB) ────────────────────────────────────────────────────────────

def _computeAllowance(primary, ctx, cardPlayerId, eqId):
    val = primary.get("floobits", 0)
    return EffectResult(floobits=val)


def _computeChaChing(primary, ctx, cardPlayerId, eqId):
    cardPlayerTds = _countPlayerTds(ctx.weekPlayerStats.get(cardPlayerId, {}))
    perTd = primary.get("perTdFloobits", 0)
    eq = f"{perTd}F/TD × {cardPlayerTds} player TDs"
    return EffectResult(floobits=perTd * cardPlayerTds, equation=eq)


def _computePiggyBank(primary, ctx, cardPlayerId, eqId):
    pct = primary.get("fpPercent", 0)
    eq = f"{pct}% × {round(ctx.weekRawFP, 1)} roster FP"
    return EffectResult(floobits=int(ctx.weekRawFP * pct / 100), equation=eq)


def _computegood_neighbor(primary, ctx, cardPlayerId, eqId):
    fgMade, fgAtt, _ = _getKickerFgStats(ctx)
    misses = max(0, fgAtt - fgMade)
    perMiss = primary.get("perMissFloobits", 0)
    eq = f"{perMiss}F/miss × {misses} FG misses"
    return EffectResult(floobits=perMiss * misses, equation=eq)


def _computeConsolationPrize(primary, ctx, cardPlayerId, eqId):
    threshold = primary.get("fpThreshold", 5)
    perPlayer = primary.get("perPlayerFloobits", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
    eq = f"{perPlayer}F/player × {count} (under {threshold} FP)"
    return EffectResult(floobits=perPlayer * count, equation=eq)


def _computeRockBottom(primary, ctx, cardPlayerId, eqId):
    lossStreak = max(0, -ctx.favoriteTeamStreak)  # Negative streak = losses
    perStreak = primary.get("perStreakFloobits", 0)
    eq = f"{perStreak}F/loss × {lossStreak} loss streak"
    return EffectResult(floobits=perStreak * lossStreak, equation=eq)


def _computeBuyLow(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerFloobits", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) < ctx.rosterPlayerRatings.get(pid, 60)
                and ctx.playerPerformanceRatings.get(pid, 0) > 0)
    eq = f"{perPlayer}F/player × {count} underperforming"
    return EffectResult(floobits=perPlayer * count, equation=eq)


def _computeTrustFund(primary, ctx, cardPlayerId, eqId):
    baseFloobits = primary.get("baseFloobits", 0)
    growth = primary.get("growthPerWeek", 0)
    weeks = max(0, ctx.rosterUnchangedWeeks)
    eq = f"{baseFloobits}F base + {growth}F × {weeks} wks unchanged"
    return EffectResult(floobits=baseFloobits + growth * weeks, equation=eq)


def _computeRagsToRiches(primary, ctx, cardPlayerId, eqId):
    per100 = primary.get("floobitsPer100Elo", 0)
    eloBelowAvg = max(0, (ctx.leagueAverageElo - ctx.favoriteTeamElo) / 100)
    eloDiff = round(ctx.leagueAverageElo - ctx.favoriteTeamElo)
    eq = f"{per100}F/100 ELO × {eloDiff} ELO below avg"
    return EffectResult(floobits=int(per100 * eloBelowAvg), equation=eq)


# ── Conditional (TE) ─────────────────────────────────────────────────────────

def _computeAceUpTheSleeve(primary, ctx, cardPlayerId, eqId):
    stat = primary.get("stat", "recYards")
    threshold = primary.get("threshold", 75)
    rewardFP = primary.get("rewardValue", 0)
    cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
    actualValue = _getStatValue(cardPlayerStats, stat)
    if actualValue >= threshold:
        return EffectResult(fpBonus=rewardFP, equation=f"{stat}: {round(actualValue)} >= {threshold}")
    return EffectResult(equation=f"{stat}: {round(actualValue)} / {threshold}")


def _computeShowoff(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    perfRating = ctx.playerPerformanceRatings.get(cardPlayerId, 0)
    baseRating = ctx.rosterPlayerRatings.get(cardPlayerId, 60)
    if perfRating > baseRating and perfRating > 0:
        result = _conditionalReward(primary)
        result.equation = f"perf {round(perfRating)} > base {round(baseRating)}"
        return result
    return EffectResult(equation=f"perf {round(perfRating)} / base {round(baseRating)}")


def _computeGlowUp(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    perfRating = ctx.playerPerformanceRatings.get(cardPlayerId, 0)
    baseRating = ctx.rosterPlayerRatings.get(cardPlayerId, 60)
    if perfRating > baseRating and perfRating > 0:
        result = _conditionalReward(primary)
        result.equation = f"perf {round(perfRating)} > base {round(baseRating)}"
        return result
    return EffectResult(equation=f"perf {round(perfRating)} / base {round(baseRating)}")


def _computeBandwagon(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    if ctx.favoriteTeamWonThisWeek:
        result = _conditionalReward(primary)
        result.equation = "team won this week"
        return result
    return EffectResult(equation="waiting for team win")


def _computeUpsetSpecial(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    if ctx.favoriteTeamWonThisWeek and ctx.favoriteTeamOpponentElo > ctx.favoriteTeamElo:
        result = _conditionalReward(primary)
        result.equation = "upset win vs higher ELO"
        return result
    return EffectResult(equation="waiting for upset win")


def _computeBelieve(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    if ctx.favoriteTeamInPlayoffs:
        result = _conditionalReward(primary)
        result.equation = "team in playoffs"
        return result
    return EffectResult(equation="team not in playoffs")


def _computeFeedingFrenzy(primary, ctx, cardPlayerId, eqId):
    tdThreshold = primary.get("tdThreshold", 3)
    rewardFloobits = int(primary.get("rewardValue", 0))
    if ctx.rosterTotalTds >= tdThreshold:
        return EffectResult(floobits=rewardFloobits, equation=f"{ctx.rosterTotalTds} roster TDs >= {tdThreshold}")
    return EffectResult(equation=f"{ctx.rosterTotalTds} / {tdThreshold} roster TDs")


def _computeSpotlightMoment(primary, ctx, cardPlayerId, eqId):
    rewardFP = primary.get("rewardValue", 0)
    cardPlayerTds = _countPlayerTds(ctx.weekPlayerStats.get(cardPlayerId, {}))
    if cardPlayerTds > 0:
        return EffectResult(fpBonus=rewardFP, equation=f"player scored {cardPlayerTds} TD{'s' if cardPlayerTds != 1 else ''}")
    return EffectResult(equation="waiting for player TD")


def _computeHighlightReel(primary, ctx, cardPlayerId, eqId):
    if ctx.favoriteTeamBigPlays > 0:
        perPlay = primary.get("rewardValue", 0)
        plays = ctx.favoriteTeamBigPlays
        rewardValue = perPlay * plays
        return EffectResult(floobits=int(rewardValue), equation=f"{perPlay}F/play × {plays} big plays")
    return EffectResult(equation="waiting for big plays")


def _computeSchadenfreude(primary, ctx, cardPlayerId, eqId):
    # Card player's team must have lost
    cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
    cardPlayerTeamId = cardPlayerStats.get("teamId")
    if not cardPlayerTeamId or cardPlayerTeamId not in ctx.teamResults:
        return EffectResult(equation="waiting for game to end")
    if not ctx.teamResults[cardPlayerTeamId]:
        result = _conditionalReward(primary)
        result.equation = "player's team lost"
        return result
    return EffectResult(equation="player's team won")


def _computeDue(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    streakThreshold = primary.get("streakThreshold", 3)
    if ctx.favoriteTeamWonThisWeek and ctx.favoriteTeamStreak == 1:
        result = _conditionalReward(primary)
        result.equation = "snapped losing streak"
        return result
    return EffectResult(equation="waiting for streak snap")


def _computeFixerUpper(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    underperforming = sum(1 for pid in ctx.rosterPlayerIds
                         if ctx.playerPerformanceRatings.get(pid, 0) < ctx.rosterPlayerRatings.get(pid, 60)
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
    eloThreshold = primary.get("eloThreshold", 1600)
    if ctx.favoriteTeamElo >= eloThreshold:
        result = _conditionalReward(primary)
        result.equation = f"team ELO {round(ctx.favoriteTeamElo)} >= {eloThreshold}"
        return result
    return EffectResult(equation=f"team ELO {round(ctx.favoriteTeamElo)} / {eloThreshold}")


def _conditionalReward(primary) -> EffectResult:
    """Convert a conditional's reward into an EffectResult."""
    rewardType = primary.get("rewardType", "fp")
    rewardValue = primary.get("rewardValue", 0)
    if rewardType == "fp":
        return EffectResult(fpBonus=rewardValue)
    elif rewardType == "mult":
        return EffectResult(multBonus=rewardValue)
    elif rewardType == "xmult":
        return EffectResult(xMultBonus=rewardValue)
    elif rewardType == "floobits":
        return EffectResult(floobits=int(rewardValue))
    return EffectResult()


# ── Streak (K) ───────────────────────────────────────────────────────────────

def _computeStreakEffect(primary, ctx, cardPlayerId, eqId):
    """Generic streak computation. Uses streak_count from ctx for season streaks,
    or computes within-week accumulation for weekly streaks."""
    streakConfig = STREAK_CONFIGS.get(ctx._currentEffectName, {})
    isWeekly = streakConfig.get("isWeekly", False)

    baseReward = primary.get("baseReward", 0)
    growthPerTick = primary.get("growthPerTick", 0)

    if isWeekly:
        # Weekly streaks: count ticks from this week's data
        ticks = _countWeeklyTicks(ctx._currentEffectName, primary, ctx)
        totalReward = sum(baseReward + growthPerTick * i for i in range(ticks))
        # Odometer: include yard data in equation
        if ctx._currentEffectName == "odometer":
            yardsPerTick = primary.get("yardsPerTick", 50)
            totalYards = _getRosterTotalYards(ctx)
            eq = f"{totalYards} yds ({yardsPerTick}/tick) = {ticks} ticks"
        else:
            eq = f"{baseReward} base + {growthPerTick}/tick × {ticks} ticks"
    else:
        # Season streaks: use streak_count
        streakCount = ctx.streakCounts.get(eqId, 1)
        totalReward = baseReward + growthPerTick * max(0, streakCount - 1)
        eq = f"{baseReward} base + {growthPerTick}/wk × {max(0, streakCount - 1)} wk streak"

    result = _streakReward(primary, totalReward)
    result.equation = eq
    return result


def _countWeeklyTicks(effectName, primary, ctx):
    """Count ticks for weekly-reset streaks."""
    if effectName == "touchdown_jackpot":
        return ctx.rosterTotalTds
    if effectName == "odometer":
        yardsPerTick = primary.get("yardsPerTick", 50)
        totalYards = _getRosterTotalYards(ctx)
        return int(totalYards / yardsPerTick) if yardsPerTick > 0 else 0
    return 0


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
    """Convert streak reward to EffectResult based on rewardType."""
    rewardType = primary.get("rewardType", "fp")
    if rewardType == "fp":
        return EffectResult(fpBonus=totalReward)
    elif rewardType == "mult":
        return EffectResult(multBonus=totalReward)
    elif rewardType == "xmult":
        return EffectResult(xMultBonus=totalReward)
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


# ─── Effect Registry ─────────────────────────────────────────────────────────

EFFECT_REGISTRY = {
    # Flat FP (WR)
    "freebie": _computeFreebie,
    "entourage": _computeEntourage,
    "touchdown_pinata": _computeTouchdownPinata,
    "scrappy": _computeScrappy,
    "honor_roll": _computeHonorRoll,
    "three_pointer": _computeThreePointer,
    "garbage_time": _computeGarbageTime,
    "loyalty_bonus": _computeLoyaltyBonus,
    "diamond_in_the_rough": _computeDiamondInTheRough,
    "top_dog": _computeTopDog,
    # Multiplier (QB)
    "big_deal": _computeBigDeal,
    "trigger_happy": _computeTriggerHappy,
    "main_character": _computeMainCharacter,
    "hype_man": _computeHypeMan,
    "babysitter": _computeBabysitter,
    "tank_commander": _computeTankCommander,
    "juggernaut": _computeJuggernaut,
    "hot_roster": _computeHotRoster,
    "loyalty_program": _computeLoyaltyProgram,
    "underdog": _computeUnderdog,
    "stockpiler": _computeStockpiler,
    # Floobits (RB)
    "allowance": _computeAllowance,
    "cha_ching": _computeChaChing,
    "piggy_bank": _computePiggyBank,
    "good_neighbor": _computegood_neighbor,
    "consolation_prize": _computeConsolationPrize,
    "rock_bottom": _computeRockBottom,
    "buy_low": _computeBuyLow,
    "trust_fund": _computeTrustFund,
    "rags_to_riches": _computeRagsToRiches,
    # Conditional (TE)
    "ace_up_the_sleeve": _computeAceUpTheSleeve,
    "showoff": _computeShowoff,
    "glow_up": _computeGlowUp,
    "bandwagon": _computeBandwagon,
    "upset_special": _computeUpsetSpecial,
    "believe": _computeBelieve,
    "feeding_frenzy": _computeFeedingFrenzy,
    "spotlight_moment": _computeSpotlightMoment,
    "highlight_reel": _computeHighlightReel,
    "schadenfreude": _computeSchadenfreude,
    "due": _computeDue,
    "fixer_upper": _computeFixerUpper,
    "pedigree": _computePedigree,
    # Streak (K) — all use the generic streak handler
    "couch_potato": _computeStreakEffect,
    "ride_or_die": _computeStreakEffect,
    "on_fire": _computeStreakEffect,
    "gravy_train": _computeStreakEffect,
    "snowball_fight": _computeStreakEffect,
    "fairweather_fan": _computeStreakEffect,
    "bandwagon_express": _computeStreakEffect,
    "touchdown_jackpot": _computeStreakEffect,
    "odometer": _computeStreakEffect,
    "leg_day": _computeStreakEffect,
    "automatic": _computeStreakEffect,
    "hot_hand": _computeStreakEffect,
    "momentum": _computeStreakEffect,
    "house_money": _computeHouseMoney,
}


def computeEffect(effectConfig: dict, ctx, cardPlayerId: int, equippedCardId: int) -> EffectResult:
    """Dispatch to the named effect's compute function."""
    effectName = effectConfig.get("effectName", "")
    handler = EFFECT_REGISTRY.get(effectName)
    if not handler:
        logger.warning(f"Unknown effect: {effectName}")
        return EffectResult()

    primary = effectConfig.get("primary", {})

    # For streak effects, stash the effect name on ctx temporarily
    # so the generic streak handler knows which config to look up
    ctx._currentEffectName = effectName

    return handler(primary, ctx, cardPlayerId, equippedCardId)


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

    if condition == "kicker_fg":
        fgMade, _, _ = _getKickerFgStats(ctx)
        return fgMade > 0

    if condition == "card_player_team_wins":
        cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
        teamId = cardPlayerStats.get("teamId")
        return ctx.teamResults.get(teamId, False) if teamId else False

    if condition == "roster_td":
        return ctx.rosterTotalTds > 0

    if condition == "favorite_team_wins":
        return ctx.favoriteTeamWonThisWeek

    if condition == "kicker_45plus":
        _, _, longest = _getKickerFgStats(ctx)
        return longest >= 45

    if condition == "kicker_no_miss":
        fgMade, fgAtt, _ = _getKickerFgStats(ctx)
        return fgAtt == 0 or fgMade == fgAtt  # No attempts or perfect

    if condition == "roster_unchanged":
        return ctx.rosterUnchangedWeeks > 0

    if condition == "card_player_td":
        cardPlayerTds = _countPlayerTds(ctx.weekPlayerStats.get(cardPlayerId, {}))
        return cardPlayerTds > 0

    if condition == "roster_50fp":
        return ctx.weekRawFP >= 50

    if condition == "favorite_team_upset_win":
        return ctx.favoriteTeamWonThisWeek and ctx.favoriteTeamOpponentElo > ctx.favoriteTeamElo

    return True
