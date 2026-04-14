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
    "goal_line_vulture": "floobits", "connection": "floobits",
    # conditional
    "showoff": "conditional", "bandwagon": "conditional",
    "upset_special": "conditional", "believe": "conditional", "schadenfreude": "conditional",
    "reclamation": "conditional", "pedigree": "conditional",
    "mismatch": "conditional", "team_chemistry": "conditional",
    "comeback_kid": "conditional", "domination": "conditional", "walk_off": "conditional",
    # streak
    "couch_potato": "streak", "on_fire": "streak", "gravy_train": "streak",
    "snowball_fight": "streak", "fairweather_fan": "streak", "bandwagon_express": "streak",
    "touchdown_jackpot": "accumulator", "odometer": "flat_fp", "complacency": "streak",
    "leg_day": "streak", "automatic": "streak", "hot_hand": "accumulator",
    "momentum": "streak",
    # cross-position (declared by _buildCrossPositionParams)
    "game_ball": "conditional", "spectacle": "cross", "indemnity": "cross",
    "full_roster": "cross", "all_in": "cross", "diversified": "cross",
    "gold_rush": "cross", "stacked_deck": "cross", "copycat": "cross",
    "chain_reaction": "cross", "bonus_round": "cross", "double_down": "cross",
    "last_resort": "cross", "high_roller": "cross", "jackpot": "cross",
    "fortitude": "cross", "immaculate": "cross",
    # same-team / game-outcome (map to their builder)
    "hometown_hero": "floobits",
    # escalating / pace effects
    "crescendo": "flat_fp", "eminence": "multiplier", "traverse": "flat_fp",
    # chance synergy
    "advantage": "meta", "catalyst": "floobits",
    # strategy-warping
    "alchemy": "flat_fp", "home_alone": "multiplier", "moral_victory": "flat_fp",
    "closer": "flat_fp", "dark_horse": "multiplier",
    "vagabond": "multiplier", "fat_cat": "flat_fp", "surplus": "floobits",
    "bonsai": "streak",
}

POSITION_LABELS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K"}

# ─── Effect → Edition Tier Mapping ─────────────────────────────────────────
# Each effect belongs to exactly one edition tier. Edition IS the rarity signal —
# a Radiant card is exciting because it has a Radiant-tier effect, not because of
# power scaling. No more multiplied base effects.

EFFECT_EDITION_TIER = {
    # ── BASE (32) — Simple, reliable, always produces value ──
    "freebie": "base", "entourage": "base", "touchdown_pinata": "base",
    "honor_roll": "base", "garbage_time": "base", "windfall": "base",
    "resplendent": "base", "three_pointer": "base", "hot_hand": "base",
    "big_deal": "base", "bandwagon": "base", "rng": "base",
    "allowance": "base", "piggy_bank": "base", "buy_low": "base", "trust_fund": "base",
    "showoff": "base", "schadenfreude": "base",
    "believe": "base", "reclamation": "base",
    "gunslinger": "base", "workhorse": "base", "expedition": "base",
    "possession": "base", "slippery": "base", "safety_blanket": "base",
    "sniper": "base", "industrious": "base", "air_raid": "base",
    "goal_line_vulture": "base",
    "homer": "base",

    # ── HOLOGRAPHIC (26) — Conditional, team-composition, position thresholds ──
    "gone_streaking": "holographic",
    "closer": "holographic", "moral_victory": "holographic", "good_neighbor": "holographic",
    "diversified": "holographic", "bonus_round": "holographic",
    "spotlight_moment": "holographic", "squire": "holographic",
    "mismatch": "holographic", "upset_special": "holographic",
    "pedigree": "holographic", "spectacle": "holographic", "game_ball": "holographic",
    "jailbreak": "holographic",
    "luminary": "holographic", "stampede": "holographic",
    "stack": "holographic", "backfield_buddies": "holographic",
    "cha_ching": "holographic", "feeding_frenzy": "holographic",
    "highlight_reel": "holographic", "connection": "holographic",
    "team_chemistry": "holographic", "hometown_hero": "holographic",
    "loyalty_bonus": "holographic",
    "ace_up_the_sleeve": "holographic", "trebuchet": "holographic",
    "double_trouble": "holographic", "lead_blocker": "holographic",
    "fat_cat": "holographic", "surplus": "holographic", "hedge": "holographic",

    # ── PRISMATIC (40) — Chance-based, streaks, game-outcome, build-around ──
    "alchemy": "prismatic", "home_alone": "prismatic", "dark_horse": "prismatic",
    "providence": "prismatic", "chain_reaction": "prismatic", "copycat": "prismatic",
    "cornucopia": "prismatic", "rising_tide": "prismatic", "juggernaut": "prismatic",
    "scrappy": "prismatic", "babysitter": "prismatic", "martyr": "prismatic", "underdog": "prismatic",
    "consolation_prize": "prismatic", "rock_bottom": "prismatic",
    "indemnity": "prismatic", "crescendo": "prismatic", "traverse": "prismatic",
    "couch_potato": "prismatic", "complacency": "prismatic", "snowball_fight": "prismatic",
    "bandwagon_express": "prismatic", "on_fire": "prismatic", "momentum": "prismatic",
    "gravy_train": "prismatic", "fairweather_fan": "prismatic", "leg_day": "prismatic",
    "automatic": "prismatic", "touchdown_jackpot": "prismatic", "odometer": "prismatic",
    "comeback_kid": "prismatic", "domination": "prismatic", "walk_off": "prismatic",
    "stockpiler": "prismatic", "house_money": "prismatic", "eminence": "prismatic", "vagabond": "prismatic",
    "bonsai": "prismatic",
    "all_in": "prismatic", "gold_rush": "prismatic",
    "last_resort": "prismatic", "avalanche": "prismatic",

    # ── DIAMOND (9) — Strategy-defining cornerstones that shape your entire hand ──
    "catalyst": "diamond", "advantage": "diamond",
    "high_roller": "diamond", "jackpot": "diamond",
    "fortitude": "diamond", "immaculate": "diamond",
    "full_roster": "diamond", "stacked_deck": "diamond",
    "double_down": "diamond",
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
    "windfall": "Windfall",
    "rng": "RNG",
    "avalanche": "Avalanche",
    "hedge": "Hedge",
    "complacency": "Complacency",
    "spotlight_moment": "Spotlight Moment",
    "ace_up_the_sleeve": "Ace Up the Sleeve",
    "lead_blocker": "Lead Blocker",
    # Multiplier (QB) — 10 effects
    "big_deal": "Big Deal",
    "cornucopia": "Cornucopia",
    "luminary": "Luminary",
    "squire": "Hype Man",
    "babysitter": "Babysitter",
    "martyr": "Martyr",
    "juggernaut": "Juggernaut",
    "resplendent": "Resplendent",
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
    "upset_special": "Upset Special",
    "believe": "Believe",
    "schadenfreude": "Schadenfreude",
    "reclamation": "Reclamation",
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
    # ── New Position-Based Effects ──
    "gunslinger": "Gunslinger",
    "air_raid": "Air Raid",
    "workhorse": "Workhorse",
    "expedition": "Expedition",
    "stampede": "Stampede",
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
    "game_ball": "Game Ball",
    "spectacle": "Spectacle",
    "indemnity": "Indemnity",
    # ── Same-Team Stacking Effects ──
    "stack": "Stack",
    "backfield_buddies": "Backfield Buddies",
    "homer": "Homer",
    "gone_streaking": "Gone Streaking",
    "hometown_hero": "Hometown Hero",
    "connection": "Connection",
    "team_chemistry": "Team Chemistry",
    # ── Game-Outcome Effects ──
    "comeback_kid": "Comeback Kid",
    "domination": "Domination",
    "walk_off": "Walk Off",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "Full Roster",
    "all_in": "All In",
    "diversified": "Diversified",
    "gold_rush": "Gold Rush",
    "stacked_deck": "Stacked Deck",
    "copycat": "Copycat",
    "chain_reaction": "Chain Reaction",
    "bonus_round": "Bonus Round",
    "double_down": "Double Down",
    "last_resort": "Last Resort",
    "high_roller": "High Roller",
    "jackpot": "Jackpot",
    "fortitude": "Fortitude",
    "immaculate": "Immaculate",
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
    "moral_victory": "Moral Victory",
    "closer": "Closer",
    "dark_horse": "Dark Horse",
    "vagabond": "Vagabond",
    "fat_cat": "Fat Cat",
    "surplus": "Surplus",
    "bonsai": "Bonsai",
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
    "windfall": "Cashing in on talent",
    "rng": "Feeling lucky?",
    "avalanche": "Each one hits harder",
    "hedge": "Downside protection",
    "complacency": "Stop tinkering",
    "spotlight_moment": "Your {posLabel} delivers",
    "ace_up_the_sleeve": "Your WRs hit the mark",
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
    "cha_ching": "Your {posLabel} scores, you profit",
    "piggy_bank": "Points into coins",
    "good_neighbor": "Silver lining included",
    "consolation_prize": "Better luck next time",
    "rock_bottom": "Silver lining",
    "buy_low": "Buy the dip",
    "trust_fund": "Set it and collect",
    "feeding_frenzy": "TD feast",
    "highlight_reel": "Big play bonus",
    # Conditional (TE)
    "showoff": "Your {posLabel} showed up",
    "bandwagon": "Your team wins, you win",
    "upset_special": "Giant slayer",
    "believe": "Playoff or bust",
    "schadenfreude": "Your {posLabel}'s team lost",
    "reclamation": "Fixer's bonus",
    # ── Strategy-Warping Effects ──
    "alchemy": "Lead into gold",
    "home_alone": "Keep the change, ya filthy animal",
    "moral_victory": "We lost, but we grew as a team",
    "closer": "Finish the job",
    "dark_horse": "Nobody saw them coming",
    "vagabond": "A restless spirit",
    "fat_cat": "Money makes money",
    "surplus": "More where that came from",
    "bonsai": "Snip snip, grow grow",
    "pedigree": "Blue blood benefits",
    # Streak (K)
    "couch_potato": "Don't touch that dial",
    "on_fire": "Keep the flame alive",
    "gravy_train": "All aboard!",
    "snowball_fight": "Getting bigger",
    "fairweather_fan": "Only here for the wins",
    "bandwagon_express": "Choo choo!",
    "touchdown_jackpot": "Weekly TD lottery",
    "odometer": "Every milestone pays",
    "leg_day": "Never skip leg day",
    "automatic": "Perfect kicks only",
    "hot_hand": "Foot on fire",
    "momentum": "Rolling",
    # ── New Position-Based Effects ──
    "gunslinger": "Slinging it",
    "air_raid": "Bombs away",
    "workhorse": "Feed the beast",
    "expedition": "Marching downfield",
    "stampede": "Unstoppable force",
    "goal_line_vulture": "Opportunistic scavenging",
    "possession": "Catch everything",
    "trebuchet": "Going deep",
    "double_trouble": "Both WRs showed up",
    "slippery": "Can't bring me down",
    "jailbreak": "Breaking tackles, breaking records",
    "safety_blanket": "Reliable target",
    "industrious": "Honest work",
    "lead_blocker": "Paving the way",
    "mismatch": "Too big, too fast",
    "sniper": "From downtown",
    "game_ball": "Above and beyond",
    "spectacle": "Career day",
    "indemnity": "Consolation floobits",
    # ── Same-Team Stacking Effects ──
    "stack": "QB-WR stack",
    "backfield_buddies": "Same backfield",
    "homer": "Hometown discount",
    "gone_streaking": "Streaks of all kinds",
    "hometown_hero": "Full stack",
    "connection": "TD connection",
    "team_chemistry": "Chemistry bonus",
    # ── Game-Outcome Effects ──
    "comeback_kid": "Never count them out",
    "domination": "Total destruction",
    "walk_off": "Buzzer beater",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "Five positions, one bonus",
    "all_in": "Go deep on one position",
    "diversified": "Variety pack",
    "gold_rush": "Floobits love company",
    "stacked_deck": "Multipliers on multipliers",
    "copycat": "Imitation is flattery",
    "chain_reaction": "Cards feeding cards",
    "bonus_round": "Everyone showed up",
    "double_down": "High risk, high reward",
    "last_resort": "The ultimate insurance",
    "high_roller": "Degenerate strategy",
    "jackpot": "Stars aligned",
    "fortitude": "Persistence is a virtue",
    "immaculate": "A blemish-free record",
    # ── Escalating / Pace Effects ──
    "crescendo": "Keep missing, it only gets easier",
    "eminence": "Stats don't lie",
    "traverse": "Long road, big payoff",
    # ── Chance Synergy Effects ──
    "advantage": "Double or nothing (minus the nothing)",
    "catalyst": "Points in, luck out",
}

EFFECT_TOOLTIPS = {
    # Flat FP (WR)
    "freebie": "It pays to show up. Bonus FP every week.",
    "entourage": "Strength in numbers. Bonus FP for each high-rated player on your roster.",
    "touchdown_pinata": "Every house call fills the piñata. Bonus FP per roster TD.",
    "scrappy": "Somebody has to believe in them. Guaranteed FP floor plus a chance at enhanced FP. Odds increase the more low-rated players are on your roster.",
    "honor_roll": "Good grades get rewarded. Bonus FP for each roster player putting up a solid score.",
    "three_pointer": "Three points for them, bonus for you. FP for every kicker FG.",
    "garbage_time": "Hey, they showed up. Bonus FP for each roster player who doesn't score a TD.",
    "loyalty_bonus": "Bandwagoning encouraged. Bonus FP based on your favorite team's win streak.",
    "windfall": "When your players ball out, you get paid. Floobits per overperforming roster player.",
    "rng": "Feeling lucky? Random FP rolled each week — could be a little, could be a lot.",
    "avalanche": "Momentum builds with every score. Each roster TD pays more FP than the last.",
    "hedge": "Insurance policy. Starts with an FP pool. Roster FP subtracts from it, and whatever remains is your payout.",
    "complacency": "Put the phone down. FP that grows each week you don't touch your roster. Resets if you make a swap. Stacking streak cards accelerates growth.",
    "spotlight_moment": "When your {posLabel} finds the endzone, you cash in. FP whenever your {posLabel} slot scores a TD. For WR, either slot counts.",
    "ace_up_the_sleeve": "Your WRs put in the work. Bonus FP when your WR slots hit a combined stat threshold.",
    # Multiplier (QB)
    "big_deal": "Show me the money. Flat FPx on your total score.",
    "cornucopia": "Every touchdown compounds. FPx that stacks per roster TD.",
    "luminary": "Your {posLabel} runs the offense. FPx that increases the more FP your {posLabel} slot earns.",
    "squire": "The crowd goes wild. FP that stacks with each TD your {posLabel} slot scores.",
    "babysitter": "Someone has to do the heavy lifting. Guaranteed FP floor plus a chance at enhanced FP. Odds increase the more roster players underperform.",
    "martyr": "Pain builds character. FP floor plus a chance at enhanced FP. Odds scale with your favorite team's ELO below average.",
    "juggernaut": "Momentum is a beautiful thing. FPx grows with every win in your favorite team's win streak.",
    "resplendent": "When they're hot, they're HOT. FP per overperforming roster player.",
    "underdog": "The worse they are, the better the odds. Guaranteed FP floor plus a chance at enhanced FP. Odds increase with each loss on your favorite team's record.",
    "stockpiler": "Patience pays. FPx that grows with each unused roster swap.",
    "providence": "Fortune favors the prepared. FPx bonus plus chance boost to all chance cards in your hand.",
    "house_money": "Upset city. FP that builds every time your favorite team wins as an underdog.",
    "rising_tide": "A rising tide lifts all boats. FPx that grows with each roster player outperforming their rating.",
    # Floobits (RB)
    "allowance": "Don't spend it all in one place. Free Floobits every week just for existing.",
    "cha_ching": "Your {posLabel}'s endzone is your cash register. Floobits for every TD your {posLabel} slot scores.",
    "piggy_bank": "Automatic savings plan. Converts a chunk of your roster's total FP into Floobits.",
    "good_neighbor": "Every cloud has a silver lining. Guaranteed Floobits plus a bonus for each FG your kicker misses.",
    "consolation_prize": "Here's a little something for your troubles. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the more roster players have a bad week.",
    "rock_bottom": "Rock bottom has a cash reward. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the longer your favorite team's losing streak.",
    "buy_low": "Buy low, sell... whenever. Floobits for every underperforming roster player.",
    "trust_fund": "The lazy investor strategy. Floobits that grow each week your roster stays unchanged.",
    "feeding_frenzy": "Dinner is served. Floobits when your roster scores enough TDs in a week.",
    "highlight_reel": "Highlight reel material pays. Floobits for every big play your favorite team pulls off.",
    # Conditional (TE)
    "showoff": "Your {posLabel} had a career day. FP when your {posLabel} slot overperforms expectations in a single game.",
    "bandwagon": "Bandwagoning has never been so rewarding. FPx whenever your favorite team wins.",
    "upset_special": "Giant killer. FP when your favorite team beats a higher-rated opponent.",
    "believe": "Keep the dream alive. FP as long as your favorite team holds a playoff spot.",
    "schadenfreude": "You feel bad about it. But also... free points. FP when your {posLabel} slot's team loses.",
    "reclamation": "Someone has to fix this mess. FP when most of your roster is underperforming.",
    "pedigree": "Good breeding shows. FP with a bonus when your favorite team's ELO reaches elite status (1600+).",
    # Streak (K) — streak cards boost each other's growth when stacked
    "couch_potato": "Just sit there. Literally. FP that grows every week this card stays equipped. Stacking streak cards accelerates growth.",
    "on_fire": "Don't let the flame die. FPx that grows each week your K slot makes a FG. Resets if they don't. Stacking streak cards accelerates growth.",
    "gravy_train": "The gravy train keeps rolling. Floobits growing each week the card player's team wins. Resets on a loss. Stacking streak cards accelerates growth.",
    "snowball_fight": "It just keeps getting bigger. FP growing each week your roster scores a TD. Resets if they don't. Stacking streak cards accelerates growth.",
    "fairweather_fan": "Fair-weather fandom has its perks. Floobits growing each week your favorite team wins. Resets on a loss. Stacking streak cards accelerates growth.",
    "bandwagon_express": "Next stop: more points. FP growing each week your favorite team wins. Resets on a loss. Stacking streak cards accelerates growth.",
    "touchdown_jackpot": "Fresh lottery every week. Floobits stacking per roster TD, resets weekly.",
    "odometer": "Hit the milestones. Escalating FP at each yardage gate your roster hits. Resets weekly.",
    "leg_day": "Never skip it. FP growing each week your K slot nails a 35+ yard FG. Stacking streak cards accelerates growth.",
    "automatic": "Perfection pays. FP growing each consecutive week your K slot goes perfect on FGs. Resets on a miss. Stacking streak cards accelerates growth.",
    "hot_hand": "Feed the hot hand. FP scales with how many FGs your K slot makes each week.",
    "momentum": "Can't stop won't stop. FPx grows each week your roster breaks 75 FP. Resets if they don't. Stacking streak cards accelerates growth.",
    # ── New Position-Based Effects ──
    "gunslinger": "Let it fly. FP that scales with how many passing yards your QB slot racks up.",
    "air_raid": "Death from above. Floobits for each passing TD your QB slot throws.",
    "workhorse": "Pound the rock. FP scaling with your RB slot's rushing attempts.",
    "expedition": "Yards are yards. FP that scales with how many rushing yards your RB slot gains.",
    "stampede": "Get rolling. Base FPx always, enhanced FPx when your RB slot hits 75+ rushing yards.",
    "goal_line_vulture": "Vulture season. Floobits for every rushing TD your RB slot punches in.",
    "possession": "Chain-mover. FP that scales with how many catches your WR slots haul in combined.",
    "trebuchet": "One big play changes everything. FP if either of your WR slots catches a pass of 25+ yards.",
    "double_trouble": "Two is better than one. FP when either WR scores a TD, with a bonus when both WRs score.",
    "slippery": "Yards after the catch turn into points. FP that scales with your WR slots' combined YAC.",
    "jailbreak": "Big YAC day = big bonus. FP when your WR slots combine for enough yards after catch.",
    "safety_blanket": "Every QB needs one. FP scaling with your TE slot's receptions.",
    "industrious": "Honest work deserves honest pay. Floobits scaling with your TE slot's receptions.",
    "lead_blocker": "Clearing the path. FP per TD by your TE — RB touchdowns on the same team count as TE TDs.",
    "mismatch": "They can't cover this guy. FP when your {posLabel} slot scores 2+ TDs in a week.",
    "sniper": "From long range. FP for each field goal your K slot makes from 40+ yards out.",
    "game_ball": "Game ball material. FP when your {posLabel} slot overperforms expectations in a single game.",
    "spectacle": "Going off. FP that scales with how much your {posLabel} slot overperforms expectations this week.",
    "indemnity": "At least you got floobits. Guaranteed Floobits floor plus a chance at enhanced Floobits. Odds increase the more your {posLabel} slot underperforms.",
    # ── Same-Team Stacking Effects ──
    "stack": "Stack attack. FPx when your QB slot and any WR slot play on the same team.",
    "backfield_buddies": "Same backfield, double the payoff. FPx when your QB slot and RB play on the same team.",
    "homer": "Loyalty has its perks. FP scaling with how many of your roster players play on your favorite team.",
    "gone_streaking": "It doesn't matter if they're winning or losing — the longer the streak, the bigger the payout. Uses your favorite team's longest streak this season.",
    "hometown_hero": "Full stack activated. Floobits when 3 or more of your roster players share the same team.",
    "connection": "Shared teams pay off. Earn Floobits when two or more of your fantasy roster players are on the same team and one scores a TD.",
    "team_chemistry": "Good chemistry lifts all boats. Floobits that grow with the number of same-team pairs on your roster.",
    # ── Game-Outcome Effects ──
    "comeback_kid": "Down but never out. FP when your favorite team overcomes a deficit and wins.",
    "domination": "Run up the score. FP when your favorite team wins, with a bonus for blowout victories.",
    "walk_off": "The best kind of finish. FP when your favorite team wins, with a bonus for walk-off victories.",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "Cover all your bases. FPx when your equipped hand has cards from all 5 positions (QB, RB, WR, TE, K).",
    "all_in": "Bet big on one position. FPx that grows with how many of your equipped cards share the same position.",
    "diversified": "Don't put all your eggs in one basket. FP per unique output type (FP, FPx, Floobits) across your equipped cards.",
    "gold_rush": "Floobits cards amplify each other. Floobits bonus for each other floobits card in your hand.",
    "stacked_deck": "Multipliers boost multipliers. FPx for each FPx card in your hand.",
    "copycat": "Copies the best. FP equal to the highest flat FP bonus from your other cards.",
    "chain_reaction": "Cards feeding cards. FPx that scales with how many of your other 4 cards produced a non-zero bonus.",
    "bonus_round": "Everyone showed up to play. Large FP if 4 or more of your other cards triggered a non-zero bonus this week.",
    "double_down": "Go big or go home. FPx boost, but zeroes your highest card's bonus.",
    "last_resort": "When nothing else works. Guaranteed FP floor plus a chance at enhanced FP. Odds increase the more of your other cards fail to produce a bonus.",
    "high_roller": "Built for the gamble. FPx that scales with how many of your chance cards hit enhanced this week.",
    "jackpot": "The ultimate payoff. FP when every chance card in your hand hits enhanced.",
    "fortitude": "The resolute are rewarded. FPx that scales with how many of your streak cards have active streaks.",
    "immaculate": "Not a single blemish. FP when every streak card in your hand has an active streak.",
    # ── Escalating / Pace Effects ──
    "crescendo": "Miss enough and eventually you can't miss. Each {posLabel} slot TD rolls for a bonus. Miss and the odds go up. For K, triggers on FGs.",
    "eminence": "Good players get paid more. FPx that scales with how far above position average your player performs. Active from week 3.",
    "traverse": "High stakes yardage gamble. FP floor plus a jackpot chance based on your {posLabel} slot's yardage.",
    # ── Chance Synergy Effects ──
    "advantage": "Loaded dice. Every chance card in your hand rolls twice, keeping the better result.",
    "catalyst": "Compound interest. Roster FP boosts odds on all your chance cards. Also pays Floobits.",
    # ── Strategy-Warping Effects ──
    "alchemy": "Transmutation complete. Each FG your K slot makes counts as a TD for fantasy scoring and other card effects.",
    "home_alone": "Embrace the void. FPx that grows with each empty roster slot.",
    "moral_victory": "Not all losses are total losses. Base FP every week, with a bonus when your {posLabel} slot's team loses.",
    "closer": "Fourth quarter closer. Bonus FP from a multiple of your roster's Q4 and OT production.",
    "dark_horse": "The stars shine brightest from below. FPx that scales inversely with your {posLabel} slot's star rating.",
    "vagabond": "Never settle. FPx that grows with each roster swap you've made this season.",
    "fat_cat": "Money talks. FP that scales with your Floobits balance. Excludes current week earnings.",
    "surplus": "Raise the ceiling. Increases the maximum Floobits you can earn per week while equipped.",
    "bonsai": "Patience rewards the diligent. Base FP that can permanently grow each week. Game events boost the growth chance. Resets if unequipped.",
}

EFFECT_DETAIL_TEMPLATES = {
    # Flat FP (WR)
    "freebie": "+{baseFP} FP per week",
    "entourage": "+{perPlayerFP} FP for every roster player with {minStars}★+",
    "touchdown_pinata": "+{perTdFP} FP for every TD your roster scores",
    "scrappy": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 25% with 1 low-rated player ({maxStars}★ or below), up to 75%",
    "honor_roll": "+{perPlayerFP} FP per roster player with {fpThreshold}+ FP",
    "three_pointer": "+{perFgFP} FP for every FG your K slot makes",
    "garbage_time": "+{perPlayerFP} FP for every roster player with 0 TDs",
    "loyalty_bonus": "+{perStreakFP} FP per win in your favorite team's streak",
    "windfall": "+{perPlayerFloobits}F per overperforming roster player",
    "rng": "Random +{minFP}–{maxFP} FP each week",
    "avalanche": "Roster TDs pay escalating FP: 1st={td1}, 2nd={td2}, 3rd={td3}, 4th+={td4}",
    "hedge": "Starts with a {floorFP} FP pool. FP earned by your roster is subtracted from the pool. Pays out whatever remains",
    "complacency": "+{baseReward} FP, +{growthPerTick} per week roster is unchanged. Resets on swap",
    "spotlight_moment": "+{rewardValue} FP when your {posLabel} slot scores a TD. WR counts both slots combined",
    "ace_up_the_sleeve": "+{rewardValue} FP if your WR slots combine for {threshold}+ {statDisplay}",
    # Multiplier (QB) — FPx
    "cornucopia": "+{perTdMult} FPx per roster TD",
    "babysitter": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 20% with 1 underperformer (under {fpThreshold} FP), up to 70%",
    "martyr": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 10% at 1 loss, grows with your favorite team's season losses, up to 60%",
    "resplendent": "+{perPlayerFP} FP per overperforming roster player",
    "big_deal": "{xMultValue}x FPx",
    "luminary": "FPx that grows the more FP your {posLabel} slot earns compared to teammates",
    "squire": "+{perTdFP} FP per {posLabel} slot TD",
    "juggernaut": "{baseXMult} FPx, grows by {growthPerWin} per your favorite team's win streak",
    "underdog": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. Chance grows the worse your favorite team's rating is, up to 75%",
    "stockpiler": "{perSwapXMult} FPx per unused roster swap",
    "providence": "{baseMult}x FPx + boosts all chance card odds by {chanceBonus}",
    "house_money": "+{baseFP} FP base, +{perUpsetFP} per your favorite team's upset wins this season",
    "rising_tide": "+{perPlayerMult} FPx per overperforming roster player (max {maxMult}x)",
    # Floobits (RB)
    "allowance": "{floobits} Floobits per week",
    "cha_ching": "{perTdFloobits} Floobits per {posLabel} slot TD",
    "piggy_bank": "{fpPercent}% of roster FP → Floobits",
    "good_neighbor": "+{baseFloobits}F base + {perMissFloobits}F per missed FG this week",
    "consolation_prize": "+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. 20% with 1 underperformer (under {fpThreshold} FP), up to 70%",
    "rock_bottom": "+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. 20% at 1-game losing streak, up to 65%",
    "buy_low": "{perPlayerFloobits} Floobits per underperforming roster player",
    "trust_fund": "{baseFloobits} Floobits base, +{growthPerWeek} per unchanged week",
    "feeding_frenzy": "{rewardValue} Floobits when roster scores {tdThreshold}+ TDs",
    "highlight_reel": "{rewardValue} Floobits per your favorite team's big plays",
    # Conditional (TE)
    "showoff": "+{rewardValue} FP when your {posLabel} slot has a strong game",
    "bandwagon": "+{rewardValue} FPx when your favorite team wins",
    "upset_special": "+{rewardValue} FP when your favorite team beats a higher-ELO team",
    "believe": "+{rewardValue} FP while your favorite team is in a playoff spot",
    "schadenfreude": "+{rewardValue} FP when your {posLabel} slot's team loses",
    "reclamation": "+{rewardValue} FP when majority of roster is underperforming",
    "pedigree": "+{baseFP} FP base, +{rewardValue} FP when your favorite team's ELO ≥ {eloThreshold}",
    # Streak (K)
    # Synergy: each other streak card in hand adds +1 to effective streak count (+growthPerTick per peer)
    "couch_potato": "+{baseReward} FP, +{growthPerTick} per week equipped. Each other streak card adds +1 bonus tick",
    "on_fire": "{baseReward} FPx, +{growthPerTick} per consecutive FG week. Resets if no FG. Each other streak card adds +1 bonus tick",
    "gravy_train": "{baseReward} Floobits, +{growthPerTick} per consecutive card player's team win. Resets on loss. Each other streak card adds +1 bonus tick",
    "snowball_fight": "+{baseReward} FP, +{growthPerTick} per consecutive roster TD week. Resets if no TD. Each other streak card adds +1 bonus tick",
    "fairweather_fan": "{baseReward} Floobits, +{growthPerTick} per consecutive your favorite team's wins. Resets on loss. Each other streak card adds +1 bonus tick",
    "bandwagon_express": "+{baseReward} FP, +{growthPerTick} per consecutive your favorite team's wins. Resets on loss. Each other streak card adds +1 bonus tick",
    "touchdown_jackpot": "{baseReward} Floobits on 1st TD, +{growthPerTick} more per TD after. Resets weekly",
    "odometer": "Escalating FP at 200, 400, 600, and 800+ total roster yards. Resets weekly",
    "leg_day": "+{baseReward} FP, +{growthPerTick} per consecutive 35+ yd FG week. Each other streak card adds +1 bonus tick",
    "automatic": "+{baseReward} FP, +{growthPerTick} per consecutive perfect FG week. Resets on a miss. Each other streak card adds +1 bonus tick",
    "hot_hand": "+{perFGFP} FP per FG made by your K slot this week",
    "momentum": "{baseReward} FPx, +{growthPerTick} per consecutive week roster scores 75+ FP. Resets if under 75. Each other streak card adds +1 bonus tick",
    # ── New Position-Based Effects ──
    "gunslinger": "+{perHundredYardsFP} FP per 100 passing yards by your QB slot",
    "air_raid": "{perTdFloobits} Floobits per passing TD by your QB slot",
    "workhorse": "+{perAttemptFP} FP per rushing attempt by your RB slot",
    "expedition": "+{perFiftyYardsFP} FP per 50 rushing yards by your RB slot",
    "stampede": "{baseMult}x FPx normally, {enhancedMult}x FPx when your RB hits {yardThreshold}+ rush yards",
    "goal_line_vulture": "{perTdFloobits} Floobits per rushing TD by your RB slot",
    "possession": "+{perReceptionFP} FP per reception by your WR slots (combined)",
    "trebuchet": "+{rewardValue} FP if a WR slot catches a 25+ yard pass",
    "double_trouble": "+{singleWrFP} FP when a WR scores, +{rewardValue} bonus FP when both WRs score",
    "slippery": "+{perYacFP} FP per 10 YAC by your WR slots",
    "jailbreak": "+{rewardValue} FP if your WR slots combine for {threshold}+ YAC",
    "safety_blanket": "+{perReceptionFP} FP per reception by your TE slot",
    "industrious": "{perReceptionFloobits} Floobits per reception by your TE slot",
    "lead_blocker": "+{perTdFP} FP per TE TD (same-team RB TDs count as TE TDs)",
    "mismatch": "+{rewardValue} FP when your {posLabel} slot scores 2+ TDs",
    "sniper": "+{perFgFP} FP per 40+ yard FG by your K slot",
    "game_ball": "+{rewardValue} FP when your {posLabel} slot overperforms",
    "spectacle": "+{perPointFP} FP per point your {posLabel} slot overperforms by",
    "indemnity": "+{baseFloobits}F guaranteed, chance at {enhancedFloobits}F. Chance grows with {posLabel} underperformance, up to 70%",
    # ── Same-Team Stacking Effects ──
    "stack": "{rewardValue} FPx when QB slot and WR share a team",
    "backfield_buddies": "+{rewardValue} FPx when QB slot and RB share a team",
    "homer": "+{perPlayerFP} FP per roster player on your favorite team",
    "gone_streaking": "+{baseFP} FP base, +{perStreakFP} per game in longest streak",
    "hometown_hero": "+{rewardFloobits} Floobits when 3+ roster players share a team",
    "connection": "{perTdFloobits} Floobits per TD when the scorer shares a team with another roster player",
    "team_chemistry": "+{perGroupFloobits} Floobits per same-team pair on your roster",
    # ── Game-Outcome Effects ──
    "comeback_kid": "+{perPointFP} FP per point of deficit overcome when your favorite team wins",
    "domination": "+{baseFP} FP on your favorite team win, +{rewardValue} FP on blowout ({marginThreshold}+ pt margin)",
    "walk_off": "+{baseFP} FP on your favorite team win, +{rewardValue} FP on walk-off victory",
    # ── Card-to-Card Interaction Effects ──
    "full_roster": "{rewardValue} FPx when hand has all 5 positions",
    "all_in": "{baseXMult} FPx + {perDuplicateXMult} per duplicate position card",
    "diversified": "+{perTypeFP} FP per unique output type in your hand",
    "gold_rush": "{perCardFloobits} Floobits per other floobits card in your hand",
    "stacked_deck": "+{perCardMult} FPx per multiplier card in your hand",
    "copycat": "+FP equal to highest flat FP bonus from your other cards",
    "chain_reaction": "{perCardXMult} FPx per other card that produced a bonus",
    "bonus_round": "+{rewardValue} FP when 4+ of your other cards triggered",
    "double_down": "{rewardValue} FPx, but zeroes your highest card's bonus",
    "last_resort": "+{baseFP} FP guaranteed, chance at {enhancedFP} FP. 15% per card that didn't trigger, up to 70%",
    "high_roller": "{perCardMult} FPx per chance card that hits",
    "jackpot": "+{rewardValue} FP when all chance cards in hand hit enhanced",
    "fortitude": "{perCardMult} FPx per active streak card in your hand",
    "immaculate": "+{rewardValue} FP when all season streak cards have active streaks",
    # ── Escalating / Pace Effects ──
    "crescendo": "+{baseFP} FP guaranteed, chance at {bonusFP} FP. {baseChance}% to start, +{chanceStep}% each time you miss",
    "eminence": "+{bonusPerFP} FPx per FP/game above position average (max {maxMult}x)",
    "traverse": "+{baseFP} FP floor + {bonusFP} FP jackpot. Jackpot chance starts at {baseChance}%, +{chancePerStep}% per {yardStep} {yardType} yards",
    # ── Chance Synergy Effects ──
    "advantage": "All chance cards roll twice, keep the better result",
    "catalyst": "+1% chance boost per {fpPer1Pct} roster FP above {baseline}. Max +{maxBoostDisplay}%. Also pays {baseFloobits} Floobits",
    # ── Strategy-Warping Effects ──
    "alchemy": "+{perFgBonusFP} bonus FP per FG by your K slot. FGs count as TDs for other effects",
    "home_alone": "+{perSlotMult} FPx per empty roster slot",
    "moral_victory": "+{baseFP} FP base, +{lossBonusFP} FP when your {posLabel} slot's team loses",
    "closer": "+{q4MultFactor}x bonus on all Q4/OT FP earned by your roster",
    "dark_horse": "+{perStarMult} FPx per star under 5 of your rostered {posLabel}",
    "vagabond": "+{perSwapXMult} FPx per roster swap used this season",
    "fat_cat": "+1 FP per {floobitsPerFP} Floobits in your balance (max {maxFP} FP)",
    "surplus": "Weekly Floobits cap raised by +{ceilingBonus} while equipped",
    "bonsai": "+{baseFP} FP base. {baseChance}% chance to permanently grow by {growthFP} FP each week. {triggerLabel} boost the growth chance",
}

# ─── Shared + Position-Exclusive Effect Pools ────────────────────────────────
# All positions draw from the shared pool. Position-exclusive pools add effects
# that reference position-specific stats (passing, rushing, receiving, kicking).

SHARED_EFFECT_POOL = [
    # flat_fp effects
    "freebie", "entourage", "touchdown_pinata", "scrappy",
    "honor_roll", "garbage_time", "loyalty_bonus",
    "windfall", "homer", "gone_streaking", "rng", "avalanche", "hedge",
    # multiplier effects
    "big_deal", "cornucopia", "babysitter",
    "martyr", "juggernaut", "resplendent",
    "underdog", "stockpiler",
    "providence", "house_money", "rising_tide",
    # floobits effects
    "allowance", "cha_ching", "piggy_bank",
    "good_neighbor", "consolation_prize", "rock_bottom",
    "buy_low", "trust_fund",
    "feeding_frenzy", "highlight_reel",
    # conditional effects
    "showoff", "bandwagon", "upset_special",
    "believe", "schadenfreude", "reclamation",
    "pedigree", "mismatch",
    # streak effects
    "couch_potato", "gravy_train", "snowball_fight",
    "fairweather_fan", "bandwagon_express", "touchdown_jackpot",
    "odometer", "complacency", "momentum",
    # position-keyed (generic concept, adapts to card position)
    "luminary", "squire", "spotlight_moment",
    # cross-position
    "game_ball", "spectacle", "indemnity",
    # same-team / game-outcome
    "hometown_hero", "connection", "team_chemistry",
    "comeback_kid", "domination", "walk_off",
    # card-to-card
    "full_roster", "all_in", "diversified", "gold_rush",
    "stacked_deck", "copycat", "chain_reaction",
    "bonus_round", "double_down",
    "last_resort", "high_roller", "jackpot",
    "fortitude", "immaculate",
    # escalating / pace
    "eminence",
    # chance synergy
    "advantage", "catalyst",
    # strategy-warping
    "home_alone", "moral_victory", "closer", "dark_horse",
    "vagabond", "fat_cat", "surplus", "bonsai",
]

POSITION_EXCLUSIVE_POOLS = {
    1: ["gunslinger", "air_raid", "stack", "backfield_buddies",
        "crescendo", "traverse"],
    2: ["workhorse", "expedition", "stampede", "goal_line_vulture",
        "crescendo", "traverse"],
    3: ["possession", "trebuchet", "double_trouble",
        "slippery", "jailbreak",
        "ace_up_the_sleeve", "crescendo", "traverse"],
    4: ["safety_blanket", "industrious", "lead_blocker",
        "traverse"],
    5: ["three_pointer", "sniper", "leg_day",
        "automatic", "on_fire", "hot_hand",
        "crescendo", "alchemy"],
}

# Effects excluded from certain positions (dead cards)
# TD-dependent effects are dead on K (kickers never score TDs)
POSITION_EXCLUDED_EFFECTS = {
    4: {"crescendo"},  # TE: too few TDs for escalating mechanic
    5: {"spotlight_moment", "squire", "cha_ching", "mismatch", "double_trouble",
        "traverse", "closer"},  # K: no meaningful yardage or Q4 stats
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
    "complacency":       {"resetCondition": "roster_unchanged", "isWeekly": False},
    "leg_day":           {"resetCondition": "kicker_35plus", "isWeekly": False},
    "automatic":         {"resetCondition": "kicker_no_miss", "isWeekly": False},
    "momentum":          {"resetCondition": "roster_75fp", "isWeekly": False},
    "house_money":       {"resetCondition": "favorite_team_upset_win", "isWeekly": False, "noReset": True},
    "bonsai":       {"resetCondition": "equipped", "isWeekly": False, "noReset": True},
}

# ─── Cultivation Trigger Pool ────────────────────────────────────────────────
# Each trigger is a countable, repeatable game event. Pass TDs count for both
# QBs (as passer) and WR/TEs (as receiver) so stacking same-team players
# doubles trigger frequency.
CULTIVATION_TRIGGER_POOL = [
    # statPaths: list of (category, key) tuples — all are summed across roster players.
    # pass_td counts for both QBs (passer) and WR/TEs (receiver) for double events.
    {"event": "pass_td",      "label": "passing/receiving TDs",   "statPaths": [("passing_stats", "tds"), ("receiving_stats", "rcvTds")]},
    {"event": "rush_td",      "label": "rushing TDs",             "statPaths": [("rushing_stats", "runTds")]},
    {"event": "reception",    "label": "receptions",              "statPaths": [("receiving_stats", "receptions")]},
    {"event": "fg_made",      "label": "field goals made",        "statPaths": [("kicking_stats", "fgs")]},
    {"event": "carry",        "label": "rushing attempts",        "statPaths": [("rushing_stats", "carries")]},
    {"event": "yac",          "label": "yards after catch",       "statPaths": [("receiving_stats", "yac")]},
]


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


# ─── Primary Parameter Builders ──────────────────────────────────────────────
# Each effect has base values scaled by playerRating and editionScale.
# ratingNorm = playerRating - 60 (range 0–40 for ratings 60–100)

def _buildCrossPositionParams(effectName, playerRating, editionScale):
    """Build params for effects that can appear in any category pool."""
    rn = playerRating - 60
    if effectName == "spectacle":
        return {"rewardType": "fp", "perPointFP": round((0.3 + rn * 0.015) * editionScale, 2)}
    if effectName == "indemnity":
        return {"rewardType": "floobits", "baseFloobits": int(round(8 * editionScale)),
                "enhancedFloobits": int(round((30 + rn * 0.4) * editionScale)),
                "isChanceEffect": True}
    # ── Hand Composition Effects ──
    if effectName == "full_roster":
        return {"rewardType": "mult", "rewardValue": round(1 + (0.40 + rn * 0.005) * editionScale, 2)}
    if effectName == "all_in":
        return {"rewardType": "mult", "baseXMult": round(1 + (0.05 + rn * 0.003) * editionScale, 2),
                "perDuplicateXMult": round((0.08 + rn * 0.004) * editionScale, 2)}
    if effectName == "diversified":
        return {"rewardType": "fp", "perTypeFP": round((5.0 + rn * 0.12) * editionScale, 1)}
    if effectName == "gold_rush":
        return {"rewardType": "floobits", "perCardFloobits": int(round((6 + rn * 0.3) * editionScale))}
    if effectName == "stacked_deck":
        return {"perCardMult": round((0.08 + rn * 0.003) * editionScale, 2)}
    # ── Trigger-Chain Effects (second pass) ──
    if effectName == "copycat":
        return {"rewardType": "fp", "_noParams": True}  # No params needed — copies highest flat FP from other cards
    if effectName == "chain_reaction":
        return {"rewardType": "mult", "perCardXMult": round((0.08 + rn * 0.004) * editionScale, 2)}
    if effectName == "bonus_round":
        return {"rewardType": "fp", "rewardValue": round((12 + rn * 0.5) * editionScale, 1)}
    # ── Chance Synergy Effects (second pass) ──
    if effectName == "high_roller":
        return {"rewardType": "mult", "perCardMult": round((0.15 + rn * 0.005) * editionScale, 2)}
    if effectName == "jackpot":
        return {"rewardType": "fp", "rewardValue": round((30 + rn * 0.8) * editionScale, 1)}
    # ── Streak Synergy Effects (second pass) ──
    if effectName == "fortitude":
        return {"rewardType": "mult", "perCardMult": round((0.15 + rn * 0.005) * editionScale, 2)}
    if effectName == "immaculate":
        return {"rewardType": "fp", "rewardValue": round((30 + rn * 0.8) * editionScale, 1)}
    # ── Tradeoff Effects (second pass) ──
    if effectName == "double_down":
        return {"rewardType": "mult", "rewardValue": min(3.0, round(1 + (0.60 + rn * 0.02) * editionScale, 2))}
    if effectName == "last_resort":
        return {"rewardType": "fp", "baseFP": round(5.0 * editionScale, 1),
                "enhancedFP": round((20 + rn * 0.4) * editionScale, 1),
                "isChanceEffect": True}
    return None


def _buildFlatFPParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "freebie":
        return {"baseFP": round((7 + rn * 0.15) * editionScale, 1)}
    if effectName == "entourage":
        return {"perPlayerFP": round((1.2 + rn * 0.04) * editionScale, 1), "minStars": 3}
    if effectName == "touchdown_pinata":
        return {"perTdFP": round((1.0 + rn * 0.03) * editionScale, 1)}
    if effectName == "scrappy":
        return {"baseFP": round(4.0 * editionScale, 1), "enhancedFP": round((18 + rn * 0.3) * editionScale, 1),
                "maxStars": 2, "isChanceEffect": True}
    if effectName == "rng":
        return {"minFP": round((3 + rn * 0.06) * editionScale, 1),
                "maxFP": round((14 + rn * 0.25) * editionScale, 1)}
    if effectName == "avalanche":
        return {"td1": round((2.0 + rn * 0.08) * editionScale, 1),
                "td2": round((4.0 + rn * 0.16) * editionScale, 1),
                "td3": round((7.0 + rn * 0.28) * editionScale, 1),
                "td4": round((11.0 + rn * 0.44) * editionScale, 1)}
    if effectName == "hedge":
        return {"floorFP": 75}
    if effectName == "honor_roll":
        return {"perPlayerFP": round((2.0 + rn * 0.06) * editionScale, 1), "fpThreshold": 15}
    if effectName == "three_pointer":
        return {"perFgFP": round((2.5 + rn * 0.08) * editionScale, 1)}
    if effectName == "garbage_time":
        return {"perPlayerFP": round((2.0 + rn * 0.08) * editionScale, 1)}
    if effectName == "loyalty_bonus":
        return {"perStreakFP": round((3.0 + rn * 0.12) * editionScale, 1)}
    if effectName == "windfall":
        return {"perPlayerFloobits": round((5 + rn * 0.20) * editionScale)}
    if effectName == "spotlight_moment":
        return {"rewardType": "fp", "rewardValue": round((8 + rn * 0.3) * editionScale, 1)}
    if effectName == "ace_up_the_sleeve":
        return {"rewardType": "fp", "rewardValue": round((7 + rn * 0.25) * editionScale, 1),
                "stat": "recYards", "threshold": 125}
    if effectName == "possession":
        return {"perReceptionFP": round((0.8 + rn * 0.04) * editionScale, 1)}
    if effectName == "slippery":
        return {"perYacFP": round((0.15 + rn * 0.008) * editionScale, 2)}
    if effectName == "jailbreak":
        return {"rewardType": "fp", "rewardValue": round((8 + rn * 0.3) * editionScale, 1), "threshold": 30}
    if effectName == "expedition":
        return {"perFiftyYardsFP": round((2.5 + rn * 0.12) * editionScale, 1)}
    if effectName == "homer":
        return {"perPlayerFP": round((3.0 + rn * 0.10) * editionScale, 1)}
    if effectName == "gone_streaking":
        return {"baseFP": round((2.0 + rn * 0.08) * editionScale, 1), "perStreakFP": round((0.8 + rn * 0.04) * editionScale, 1)}
    if effectName == "safety_blanket":
        return {"rewardType": "fp", "perReceptionFP": round((1.0 + rn * 0.04) * editionScale, 1)}
    if effectName == "lead_blocker":
        return {"rewardType": "fp", "perTdFP": round((4.0 + rn * 0.2) * editionScale, 1)}
    if effectName == "sniper":
        return {"perFgFP": round((3.0 + rn * 0.10) * editionScale, 1)}
    if effectName == "squire":
        return {"perTdFP": round((4 + rn * 0.15) * editionScale, 1)}
    # ── Escalating chance: Crescendo (TD/FG triggers, escalating per miss)
    if effectName == "crescendo":
        # Position-specific tuning set at compute time; params store rarity-scaled values
        return {"baseFP": round((1.0 + rn * 0.04) * editionScale, 1),
                "bonusFP": round((8.0 + rn * 0.3) * editionScale, 1),
                "baseChance": 15, "chanceStep": 12,  # QB defaults; compute overrides per position
                "isChanceEffect": True}
    # ── Yardage chance: Traverse (end-of-game roll scaled by yards)
    if effectName == "traverse":
        return {"baseFP": round((0.5 + rn * 0.03) * editionScale, 1),
                "bonusFP": round((15.0 + rn * 0.5) * editionScale, 1),
                "baseChance": 2, "chancePerStep": 5, "yardStep": 50, "yardType": "passing",
                "isChanceEffect": True}
    # ── Meta: Advantage (no direct payout, enables roll-twice on all chance cards)
    if effectName == "advantage":
        return {"isAdvantage": True}
    # ── Strategy-Warping: Opulence (FP per Floobits balance)
    if effectName == "fat_cat":
        # 1 FP per X Floobits, capped
        floobitsPerFP = max(1, int(round((3 - rn * 0.02) / editionScale)))
        maxFP = int(round((15 + rn * 0.5) * editionScale))
        return {"floobitsPerFP": floobitsPerFP, "maxFP": maxFP}
    # ── Strategy-Warping: Alchemy (FG → TD upgrade)
    if effectName == "alchemy":
        # Bonus FP per FG = TD FP value (6) minus FG FP value (~3) = ~3 base
        return {"perFgBonusFP": round((3.0 + rn * 0.12) * editionScale, 1)}
    # ── Strategy-Warping: Consolation (base FP + loss bonus)
    if effectName == "moral_victory":
        return {"baseFP": round((3.0 + rn * 0.10) * editionScale, 1),
                "lossBonusFP": round((10.0 + rn * 0.35) * editionScale, 1)}
    # ── Strategy-Warping: Overtime (Q4 FP multiplier)
    if effectName == "closer":
        return {"q4MultFactor": round((1.5 + rn * 0.03) * editionScale, 1)}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"baseFP": round(2 * editionScale, 1)}


def _buildMultiplierParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    # ── FPx effects (delta-based, wrapped as 1+val in compute) ──
    if effectName == "cornucopia":
        return {"perTdMult": round((0.05 + rn * 0.003) * editionScale, 2)}
    if effectName == "babysitter":
        return {"baseFP": round(5.0 * editionScale, 1), "enhancedFP": round((18 + rn * 0.3) * editionScale, 1),
                "fpThreshold": 8, "isChanceEffect": True}
    if effectName == "martyr":
        return {"baseFP": round(5.0 * editionScale, 1), "enhancedFP": round((18 + rn * 0.3) * editionScale, 1),
                "isChanceEffect": True}
    if effectName == "resplendent":
        return {"perPlayerFP": round((1.5 + rn * 0.05) * editionScale, 1)}
    # ── FPx effects (factor-based, values > 1) ──
    if effectName == "big_deal":
        return {"xMultValue": round(1 + (playerRating / 100) * 0.12 * editionScale, 2)}
    if effectName == "luminary":
        return {"fpShareScale": round((0.25 + rn * 0.012) * editionScale, 2)}
    if effectName == "juggernaut":
        return {"baseXMult": round(1 + (0.05 + rn * 0.002) * editionScale, 2),
                "growthPerWin": round((0.05 + rn * 0.002) * editionScale, 2)}
    if effectName == "underdog":
        return {"baseFP": round(5.0 * editionScale, 1), "enhancedFP": round((18 + rn * 0.3) * editionScale, 1),
                "isChanceEffect": True}
    if effectName == "stockpiler":
        return {"perSwapXMult": round((0.04 + rn * 0.002) * editionScale, 2)}
    if effectName == "hometown_hero":
        return {"rewardFloobits": int(round((15 + rn * 0.6) * editionScale))}
    if effectName == "providence":
        return {"baseMult": round(1 + 0.05 * editionScale, 2),
                "chanceBonus": round(0.12 * editionScale, 2),
                "isChanceAmplifier": True}
    if effectName == "house_money":
        return {"baseFP": round((3 + rn * 0.12) * editionScale, 1),
                "perUpsetFP": round((3 + rn * 0.12) * editionScale, 1)}
    if effectName == "rising_tide":
        return {"perPlayerMult": round((0.04 + rn * 0.002) * editionScale, 2),
                "maxMult": round(1 + (0.20 + rn * 0.008) * editionScale, 2)}
    if effectName == "trebuchet":
        return {"rewardType": "fp", "rewardValue": round((12 + rn * 0.5) * editionScale, 1)}
    if effectName == "double_trouble":
        return {"rewardType": "fp",
                "singleWrFP": round((6 + rn * 0.25) * editionScale, 1),
                "rewardValue": round((14 + rn * 0.55) * editionScale, 1)}
    if effectName == "gunslinger":
        return {"rewardType": "fp", "perHundredYardsFP": round((2.0 + rn * 0.06) * editionScale, 1)}
    if effectName == "air_raid":
        return {"rewardType": "floobits", "perTdFloobits": int(round((6 + rn * 0.3) * editionScale))}
    if effectName == "stampede":
        return {"baseMult": round(1 + (0.06 + rn * 0.003) * editionScale, 2),
                "enhancedMult": round(1 + (0.18 + rn * 0.008) * editionScale, 2),
                "yardThreshold": 75}
    if effectName == "stack":
        return {"rewardValue": round(1 + (0.15 + rn * 0.008) * editionScale, 2)}
    if effectName == "backfield_buddies":
        return {"rewardValue": round((0.15 + rn * 0.008) * editionScale, 2)}
    # ── Pace multiplier: Eminence (FPx from season pace above position avg)
    if effectName == "eminence":
        return {"rewardType": "mult",
                "bonusPerFP": round((0.015 + rn * 0.0008) * editionScale, 2),
                "maxMult": min(1.50, round(1 + (0.12 + rn * 0.004) * editionScale, 2))}
    # ── Strategy-Warping: Austerity (FPx per empty roster slot)
    if effectName == "home_alone":
        return {"perSlotMult": round((0.12 + rn * 0.004) * editionScale, 2)}
    # ── Strategy-Warping: Humility (FPx per star under 5 of rostered player)
    if effectName == "dark_horse":
        return {"perStarMult": round((0.08 + rn * 0.003) * editionScale, 2)}
    # ── Strategy-Warping: Vagabond (FPx per swap used, inverse Stockpiler)
    if effectName == "vagabond":
        return {"perSwapXMult": round((0.03 + rn * 0.001) * editionScale, 2)}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"multPercent": round(0.2 * editionScale, 1)}


def _buildFloobitsParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "allowance":
        return {"floobits": int(round((10 + rn * 0.5) * editionScale))}
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
        return {"rewardType": "floobits", "rewardValue": int(round((15 + rn * 0.5) * editionScale)),
                "tdThreshold": 3}
    if effectName == "highlight_reel":
        return {"rewardType": "floobits", "rewardValue": int(round((6 + rn * 0.3) * editionScale)),
                "wpaThreshold": 10.0}
    if effectName == "workhorse":
        return {"rewardType": "fp", "perAttemptFP": round((0.2 + rn * 0.01) * editionScale, 1)}
    if effectName == "goal_line_vulture":
        return {"perTdFloobits": int(round((8 + rn * 0.4) * editionScale))}
    if effectName == "connection":
        return {"perTdFloobits": int(round((6 + rn * 0.3) * editionScale))}
    if effectName == "industrious":
        return {"perReceptionFloobits": int(round((1.5 + rn * 0.06) * editionScale))}
    # ── Strategy-Warping: Prosperity (Floobits payout ceiling raiser)
    if effectName == "surplus":
        ceilingBonus = int(round((10 + rn * 0.4) * editionScale))
        return {"ceilingBonus": ceilingBonus}
    # ── Catalyst: dynamic chance boost from roster FP + small floobits base
    if effectName == "catalyst":
        # Lower FP threshold + higher max = easier to activate, higher ceiling
        fpPer1Pct = 7
        baseline = 30
        maxBoostPct = 20
        baseFloobits = int(round((3 + rn * 0.15) * editionScale))
        return {"fpPer1Pct": fpPer1Pct, "baseline": baseline,
                "maxBoost": maxBoostPct / 100, "maxBoostDisplay": maxBoostPct,
                "baseFloobits": baseFloobits,
                "isChanceAmplifier": True}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"floobits": int(round(5 * editionScale))}


def _buildConditionalParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "showoff":
        return {"rewardType": "fp", "rewardValue": round((8 + rn * 0.3) * editionScale, 1)}
    if effectName == "game_ball":
        return {"rewardType": "fp", "rewardValue": round((7 + rn * 0.25) * editionScale, 1)}
    if effectName == "bandwagon":
        return {"rewardType": "mult", "rewardValue": round(1 + (0.08 + rn * 0.004) * editionScale, 2)}
    if effectName == "upset_special":
        return {"rewardType": "fp", "rewardValue": round((12 + rn * 0.5) * editionScale, 1)}
    if effectName == "believe":
        return {"rewardType": "fp", "rewardValue": round((6 + rn * 0.25) * editionScale, 1)}
    if effectName == "schadenfreude":
        return {"rewardType": "fp", "rewardValue": round((6 + rn * 0.25) * editionScale, 1)}
    if effectName == "reclamation":
        return {"rewardType": "fp", "rewardValue": round((8 + rn * 0.3) * editionScale, 1)}
    if effectName == "pedigree":
        return {"rewardType": "fp",
                "baseFP": round((4 + rn * 0.15) * editionScale, 1),
                "rewardValue": round((12 + rn * 0.5) * editionScale, 1),
                "eloThreshold": 1600}
    if effectName == "mismatch":
        return {"rewardType": "fp", "rewardValue": round((15 + rn * 0.6) * editionScale, 1)}
    if effectName == "team_chemistry":
        return {"rewardType": "floobits", "perGroupFloobits": int(round((8 + rn * 0.3) * editionScale))}
    if effectName == "comeback_kid":
        return {"rewardType": "fp", "perPointFP": round((1.0 + rn * 0.04) * editionScale, 1)}
    if effectName == "domination":
        return {"rewardType": "fp",
                "baseFP": round((5 + rn * 0.2) * editionScale, 1),
                "rewardValue": round((18 + rn * 0.7) * editionScale, 1),
                "marginThreshold": 21}
    if effectName == "walk_off":
        return {"rewardType": "fp",
                "baseFP": round((4 + rn * 0.15) * editionScale, 1),
                "rewardValue": round((20 + rn * 0.8) * editionScale, 1)}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"rewardType": "fp", "rewardValue": round(3 * editionScale, 1)}


def _buildStreakParams(effectName, playerRating, editionScale):
    rn = playerRating - 60

    if effectName == "couch_potato":
        return {"rewardType": "fp",
                "baseReward": round((2.0 + rn * 0.08) * editionScale, 1),
                "growthPerTick": round((1.0 + rn * 0.04) * editionScale, 1)}
    if effectName == "complacency":
        return {"rewardType": "fp",
                "baseReward": round((1.5 + rn * 0.06) * editionScale, 1),
                "growthPerTick": round((0.8 + rn * 0.03) * editionScale, 1)}
    if effectName == "on_fire":
        return {"rewardType": "mult",
                "baseReward": round(1 + (0.05 + rn * 0.003) * editionScale, 2),
                "growthPerTick": round((0.05 + rn * 0.002) * editionScale, 2)}
    if effectName == "gravy_train":
        return {"rewardType": "floobits",
                "baseReward": int(round((6 + rn * 0.3) * editionScale)),
                "growthPerTick": int(round((2 + rn * 0.1) * editionScale))}
    if effectName == "snowball_fight":
        return {"rewardType": "fp",
                "baseReward": round((2.0 + rn * 0.08) * editionScale, 1),
                "growthPerTick": round((1.0 + rn * 0.04) * editionScale, 1)}
    if effectName == "fairweather_fan":
        return {"rewardType": "floobits",
                "baseReward": int(round((4 + rn * 0.2) * editionScale)),
                "growthPerTick": int(round((2 + rn * 0.08) * editionScale))}
    if effectName == "bandwagon_express":
        return {"rewardType": "fp",
                "baseReward": round((3.0 + rn * 0.12) * editionScale, 1),
                "growthPerTick": round((1.0 + rn * 0.04) * editionScale, 1)}
    if effectName == "touchdown_jackpot":
        return {"rewardType": "floobits",
                "baseReward": int(round((4 + rn * 0.2) * editionScale)),
                "growthPerTick": int(round((2 + rn * 0.1) * editionScale))}
    if effectName == "odometer":
        return {"rewardType": "fp",
                "gates": [
                    {"yards": 200, "fp": round((5.0 + rn * 0.08) * editionScale, 1)},
                    {"yards": 400, "fp": round((10.0 + rn * 0.15) * editionScale, 1)},
                    {"yards": 600, "fp": round((16.0 + rn * 0.25) * editionScale, 1)},
                    {"yards": 800, "fp": round((20.0 + rn * 0.3) * editionScale, 1)},
                ]}
    if effectName == "leg_day":
        return {"rewardType": "fp",
                "baseReward": round((3.0 + rn * 0.12) * editionScale, 1),
                "growthPerTick": round((1.2 + rn * 0.05) * editionScale, 1)}
    if effectName == "automatic":
        return {"rewardType": "fp",
                "baseReward": round((3.0 + rn * 0.12) * editionScale, 1),
                "growthPerTick": round((1.5 + rn * 0.06) * editionScale, 1)}
    if effectName == "hot_hand":
        return {"rewardType": "fp", "perFGFP": round((2.0 + rn * 0.06) * editionScale, 1)}
    if effectName == "momentum":
        return {"rewardType": "mult",
                "baseReward": round(1 + (0.05 + rn * 0.003) * editionScale, 2),
                "growthPerTick": round((0.05 + rn * 0.002) * editionScale, 2)}
    # ── Strategy-Warping: Cultivation (growing chance — streak + chance hybrid)
    if effectName == "bonsai":
        trigger = random.choice(CULTIVATION_TRIGGER_POOL)
        return {"rewardType": "fp",
                "baseFP": round((4.0 + rn * 0.15) * editionScale, 1),
                "growthFP": round((2.0 + rn * 0.08) * editionScale, 1),
                "baseChance": 20, "chancePerTrigger": 5,
                "triggerEvent": trigger["event"],
                "triggerLabel": trigger["label"],
                "isChanceEffect": True}
    return _buildCrossPositionParams(effectName, playerRating, editionScale) or {"rewardType": "fp", "baseReward": round(1.0 * editionScale, 1), "growthPerTick": round(0.5 * editionScale, 1)}


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


# ─── Config Builder ──────────────────────────────────────────────────────────

def buildEffectConfig(edition: str, playerRating: int, position: int, teamId=None,
                      forceEffect: str = None, forceCategory: str = None) -> dict:
    """Build the effect_config JSON for a new card template.

    Effects are drawn from a shared pool (all positions) plus position-exclusive
    pools, filtered to only effects belonging to the requested edition tier,
    minus excluded effects. Category is derived from the effect's natural type,
    not the card's position.
    forceEffect/forceCategory allow admin overrides.
    """
    # Pool selection: shared + position exclusive, minus excluded, filtered by edition tier
    excluded = POSITION_EXCLUDED_EFFECTS.get(position, set())
    pool = [n for n in SHARED_EFFECT_POOL if n not in excluded]
    pool += POSITION_EXCLUSIVE_POOLS.get(position, [])

    # Filter to only effects that belong to this edition tier
    pool = [n for n in pool if EFFECT_EDITION_TIER.get(n) == edition]

    if forceEffect:
        effectName = forceEffect
    elif not pool:
        logger.warning(f"No effects available for edition={edition}, position={position} — falling back to freebie")
        effectName = "freebie"
    else:
        effectName = random.choice(pool)

    # Category from effect's natural type (not position)
    category = forceCategory or EFFECT_CATEGORY.get(effectName, "flat_fp")

    editionScale = 1.0  # Edition no longer scales effect params — tier determines effect

    # Dampen player rating scaling for rarer tiers — higher tiers have narrow
    # rating bands already, and the tier itself IS the power signal.
    _RATING_DAMPENING = {"base": 1.0, "holographic": 0.5, "prismatic": 0.25, "diamond": 0.0}
    dampening = _RATING_DAMPENING.get(edition, 1.0)
    dampenedRating = 60 + (playerRating - 60) * dampening

    # Builder: check per-effect overrides first, then category dispatch
    if category == "cross":
        builder = _buildCrossPositionParams
    elif effectName in _EFFECT_BUILDER_OVERRIDES:
        builder = _EFFECT_BUILDER_OVERRIDES[effectName]
    else:
        builder = _PARAM_BUILDERS.get(category, _buildFlatFPParams)
    primary = builder(effectName, dampenedRating, editionScale)
    # _buildCrossPositionParams returns None for unknown effects — fallback
    if primary is None:
        primary = {"baseFP": round(2 * editionScale, 1)}
    primary["posLabel"] = POSITION_LABELS.get(position, "??")

    # Position-specific param overrides for effects with per-position tuning
    if effectName == "crescendo" and position in _CRESCENDO_POSITION_TUNING:
        baseChance, chanceStep = _CRESCENDO_POSITION_TUNING[position]
        primary["baseChance"] = baseChance
        primary["chanceStep"] = chanceStep
    if effectName == "traverse" and position in _TRAVERSE_POSITION_TUNING:
        yardStep, chancePerStep, yardType = _TRAVERSE_POSITION_TUNING[position]
        primary["yardStep"] = yardStep
        primary["chancePerStep"] = chancePerStep
        primary["yardType"] = yardType

    conditionals = POSITION_CONDITIONALS.get(position, [])
    conditional = conditionals[0] if conditionals else None

    # StreakConfig: check by effect name (not gated on category)
    streakConfig = STREAK_CONFIGS.get(effectName)

    tagline = EFFECT_TAGLINES.get(effectName, "")
    tooltip = EFFECT_TOOLTIPS.get(effectName, "")

    # Fill in primary params across detail, tooltip, and tagline
    detail = EFFECT_DETAIL_TEMPLATES.get(effectName, "")
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


def _computeAvalanche(primary, ctx, cardPlayerId, eqId):
    """Escalating FP per roster TD within a week. Each TD pays more than the last."""
    gates = [primary.get("td1", 2), primary.get("td2", 4), primary.get("td3", 7), primary.get("td4", 11)]
    tds = ctx.rosterTotalTds
    if tds == 0:
        return EffectResult(equation="No roster TDs this week")
    totalFP = 0
    details = []
    for i in range(tds):
        gateFP = gates[min(i, len(gates) - 1)]
        totalFP += gateFP
        label = f"TD{i + 1}=+{gateFP}"
        details.append(label)
    totalFP = round(totalFP, 1)
    eq = f"{tds} roster TD{'s' if tds != 1 else ''}: {', '.join(details)} = +{totalFP} FP"
    return EffectResult(fpBonus=totalFP, equation=eq)


def _computeHedge(primary, ctx, cardPlayerId, eqId):
    """FP floor: guarantees a minimum roster output. Pays the difference between floor and actual."""
    floorFP = primary.get("floorFP", 50)
    rosterFP = round(ctx.weekRawFP, 1)
    bonus = round(max(0, floorFP - rosterFP), 1)
    if bonus > 0:
        eq = f"{floorFP} floor − {rosterFP} roster FP = +{bonus} FP"
        return EffectResult(fpBonus=bonus, equation=eq)
    eq = f"Roster scored {rosterFP} FP (above {floorFP} floor — no hedge needed)"
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
    count = sum(1 for pid in ctx.rosterPlayerIds
                if _playerStars(ctx.rosterPlayerRatings.get(pid, 60)) <= maxStars)
    if count <= 0:
        eq = f"+{baseFP} FP. No {maxStars}★ or lower players"
        return EffectResult(fpBonus=baseFP, equation=eq)
    baseChance = min(0.75, count * 0.125 + 0.125)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFP} FP", f"{count} low-rated", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


def _computeHonorRoll(primary, ctx, cardPlayerId, eqId):
    threshold = primary.get("fpThreshold", 15)
    perPlayer = primary.get("perPlayerFP", 0)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) >= threshold)
    eq = f"{perPlayer}/player × {count} ({threshold}+ FP)"
    return EffectResult(fpBonus=perPlayer * count, equation=eq)


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
    perTd = primary.get("perTdMult", 0)
    tds = ctx.rosterTotalTds
    bonus = perTd * tds
    eq = f"1 + ({perTd}/TD × {tds} roster TDs) = {1 + bonus:.2f}x"
    return EffectResult(multBonus=1 + bonus, equation=eq)


def _computeMainCharacter(primary, ctx, cardPlayerId, eqId):
    # Roster player's FP share (keyed off card position)
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 1)
    rosterFP = rosterStats.get("fantasyPoints", 0)
    fpShare = rosterFP / max(ctx.weekRawFP, 1)
    scale = primary.get("fpShareScale", 0)
    eq = f"1 + ({scale} × {round(fpShare * 100)}% {posLabel} slot FP share)"
    return EffectResult(multBonus=1 + scale * fpShare, equation=eq)


def _computeHypeMan(primary, ctx, cardPlayerId, eqId):
    # Roster player's TDs (keyed off card position)
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 1)
    rosterTds = _countPlayerTds(rosterStats)
    # Normalize legacy cards: perTdXMult/xMultValue → perTdFP
    perTdFP = primary.get("perTdFP") or primary.get("perTdXMult") or primary.get("xMultValue") or 0
    if rosterTds > 0:
        bonus = round(perTdFP * rosterTds, 1)
        eq = f"{perTdFP}/TD × {rosterTds} {posLabel} slot TD{'s' if rosterTds != 1 else ''}"
        return EffectResult(fpBonus=bonus, equation=eq)
    return EffectResult(equation=f"{perTdFP} FP/TD × 0 {posLabel} slot TDs")


def _computeBabysitter(primary, ctx, cardPlayerId, eqId):
    """Chance card: base FP always + chance of enhanced FP based on underperformers."""
    from managers.cardEffectCalculator import _chanceRoll
    baseFP = primary.get("baseFP", 5)
    enhancedFP = primary.get("enhancedFP", 18)
    threshold = primary.get("fpThreshold", 8)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
    if count <= 0:
        eq = f"+{baseFP} FP. No players under {threshold} FP"
        return EffectResult(fpBonus=baseFP, equation=eq)
    baseChance = min(0.70, count * 0.125 + 0.075)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFP} FP", f"{count} under {threshold} FP", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


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
    # Gate: team must have lost this week
    if not ctx.favoriteTeamGameFinal or ctx.favoriteTeamWonThisWeek:
        eq = f"+{baseFP} FP. Team won or game not final"
        return EffectResult(fpBonus=baseFP, equation=eq)
    losses = ctx.favoriteTeamSeasonLosses
    baseChance = min(0.60, losses * 0.06 + 0.08) if losses >= 2 else (0.10 if losses == 1 else 0)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFP} FP", f"team lost, {losses} season losses", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


def _computeJuggernaut(primary, ctx, cardPlayerId, eqId):
    streak = max(0, ctx.favoriteTeamStreak)
    baseX = primary.get("baseXMult", 1.1)
    growth = primary.get("growthPerWin", 0.1)
    # Only pay out once the team wins this week, extending their streak
    if not ctx.favoriteTeamWonThisWeek or streak <= 0:
        return EffectResult(multBonus=1.0, equation="Waiting for win to extend streak")
    eq = f"{baseX}x base + ({growth}x × {streak} win streak)"
    return EffectResult(multBonus=baseX + growth * streak, equation=eq)


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
    eq = f"1 + ({perPlayer}/player × {count} overperforming) = {1 + bonus:.2f}x"
    return EffectResult(multBonus=1 + bonus, equation=eq)


def _computeRisingTide(primary, ctx, cardPlayerId, eqId):
    perPlayer = primary.get("perPlayerMult", 0)
    maxMult = primary.get("maxMult", 1.5)
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.playerPerformanceRatings.get(pid, 0) - ctx.rosterPlayerRatings.get(pid, 60) >= 5)
    rawMult = 1 + perPlayer * count
    mult = min(rawMult, maxMult)
    eq = f"1 + ({perPlayer}/player × {count} overperforming) = {mult:.2f}x (max {maxMult}x)"
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
    baseChance = min(0.75, eloBelowAvg / 400)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
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
    eq = f"1 + ({perSwap}x × {unusedSwaps} unused swaps)"
    return EffectResult(multBonus=1 + unusedSwaps * perSwap, equation=eq)


def _computeProvidence(primary, ctx, cardPlayerId, eqId):
    """Small FPx bonus + aura that boosts all chance card trigger rates."""
    baseMult = primary.get("baseMult", 1.05)
    chanceBonus = primary.get("chanceBonus", 0.12)
    eq = f"{baseMult}x + {chanceBonus:.0%} chance boost"
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
    eq = f"{baseXMult} base + ({perUpset}x × {upsetWins} upset wins)"
    return EffectResult(multBonus=xMult, equation=eq)


# ── Floobits (RB) ────────────────────────────────────────────────────────────

def _computeAllowance(primary, ctx, cardPlayerId, eqId):
    val = primary.get("floobits", 0)
    return EffectResult(floobits=val)


def _computeChaChing(primary, ctx, cardPlayerId, eqId):
    # Roster player's TDs (keyed off card position)
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 2)
    rosterTds = _countPlayerTds(rosterStats)
    perTd = primary.get("perTdFloobits", 0)
    eq = f"{perTd}F/TD × {rosterTds} {posLabel} slot TDs"
    return EffectResult(floobits=perTd * rosterTds, equation=eq)


def _computePiggyBank(primary, ctx, cardPlayerId, eqId):
    pct = primary.get("fpPercent", 0)
    eq = f"{pct}% × {round(ctx.weekRawFP, 1)} roster FP"
    return EffectResult(floobits=int(ctx.weekRawFP * pct / 100), equation=eq)


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
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.weekPlayerStats.get(pid, {}).get("fantasyPoints", 0) < threshold)
    if count <= 0:
        eq = f"+{baseFloobits}F. No players under {threshold} FP"
        return EffectResult(floobits=baseFloobits, equation=eq)
    baseChance = min(0.70, count * 0.125 + 0.075)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    floobitsVal = enhancedFloobits if triggered else baseFloobits
    context = f"{count} under {threshold} FP"
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFloobits}F", context, ctx=ctx, base=f"+{baseFloobits}F")
    return EffectResult(floobits=floobitsVal, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


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
    baseChance = min(0.65, lossStreak * 0.10 + 0.10)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
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
    # +FP if WR slots hit combined stat threshold (keyed off card position)
    stat = primary.get("stat", "recYards")
    threshold = primary.get("threshold", 75)
    rewardFP = primary.get("rewardValue", 0)
    rosterStats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 3)
    actualValue = _getStatValue(rosterStats, stat)
    if actualValue >= threshold:
        return EffectResult(fpBonus=rewardFP, equation=f"WR slots {stat}: {round(actualValue)} >= {threshold}")
    return EffectResult(equation=f"WR slots {stat}: {round(actualValue)} / {threshold}")


def _computeShowoff(primary, ctx, cardPlayerId, eqId):
    # +FP if player at card's position overperformed (after all games complete)
    if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    pids = _getRosterPlayersByPosition(ctx, ctx.cardPosition or 4)
    if not pids:
        return EffectResult(equation="no roster player at position")
    for pid in pids:
        gamePerfRating = ctx.gamePerformanceRatings.get(pid, 0)
        baseRating = ctx.rosterPlayerRatings.get(pid, 60)
        if gamePerfRating > baseRating and gamePerfRating > 0:
            playerName = ctx.rosterPlayerNames.get(pid, "?")
            result = _conditionalReward(primary)
            result.equation = f"{playerName} overperformed"
            return result
    names = [ctx.rosterPlayerNames.get(pid, "?") for pid in pids]
    return EffectResult(equation=f"{' + '.join(names)}: did not overperform")


def _computeBandwagon(primary, ctx, cardPlayerId, eqId):
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="waiting for game to end")
    if ctx.favoriteTeamWonThisWeek:
        result = _conditionalReward(primary)
        result.equation = "team won this week"
        return result
    return EffectResult(equation="waiting for team win")


def _computeUpsetSpecial(primary, ctx, cardPlayerId, eqId):
    oppName = ctx.favoriteTeamOpponentName
    isUnderdog = ctx.favoriteTeamOpponentElo > ctx.favoriteTeamElo
    matchupTag = f"vs {oppName} — {'underdog' if isUnderdog else 'favored'}" if oppName else ""
    if not ctx.favoriteTeamGameFinal:
        if matchupTag:
            return EffectResult(equation=f"waiting for game to end ({matchupTag})")
        return EffectResult(equation="waiting for game to end")
    if ctx.favoriteTeamWonThisWeek and isUnderdog:
        result = _conditionalReward(primary)
        result.equation = f"upset win {matchupTag}"
        return result
    if matchupTag:
        return EffectResult(equation=f"no upset win ({matchupTag})")
    return EffectResult(equation="no upset win")


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
    # +FP if player at card's position scores a TD
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rosterStats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 3)
    rosterTds = _countPlayerTds(rosterStats)
    rewardFP = primary.get("rewardValue", 0)
    if rosterTds > 0:
        return EffectResult(fpBonus=rewardFP, equation=f"{posLabel} slot scored {rosterTds} TD{'s' if rosterTds != 1 else ''}")
    return EffectResult(equation=f"waiting for {posLabel} slot TD")


def _computeHighlightReel(primary, ctx, cardPlayerId, eqId):
    if ctx.favoriteTeamBigPlays > 0:
        perPlay = primary.get("rewardValue", 0)
        plays = ctx.favoriteTeamBigPlays
        rewardValue = perPlay * plays
        return EffectResult(floobits=int(rewardValue), equation=f"{perPlay}F/play × {plays} big plays")
    return EffectResult(equation="waiting for big plays")


def _computeSchadenfreude(primary, ctx, cardPlayerId, eqId):
    # Any roster player's team at card position must have lost
    pids = _getRosterPlayersByPosition(ctx, ctx.cardPosition or 4)
    if not pids:
        return EffectResult(equation="no roster player at position")
    anyLost = False
    allResolved = True
    for pid in pids:
        rosterStats = ctx.weekPlayerStats.get(pid, {})
        teamId = rosterStats.get("teamId") or ctx.rosterPlayerTeamIds.get(pid)
        if not teamId or teamId not in ctx.teamResults:
            allResolved = False
            continue
        if not ctx.teamResults[teamId]:
            anyLost = True
            break
    if anyLost:
        result = _conditionalReward(primary)
        result.equation = "roster player's team lost"
        return result
    if not allResolved:
        return EffectResult(equation="waiting for game to end")
    return EffectResult(equation="roster player's team won")



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
            return EffectResult(multBonus=mult, equation=f"{mult}x (legacy, ELO {teamElo})")
        return EffectResult(multBonus=baseMult, equation=f"{baseMult}x (legacy, ELO {teamElo})")
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
        eq = f"{baseReward} base + ({growthPerTick}/TD × {ticks} TDs)"
    else:
        # Season streaks: live-aware computation
        # streakCounts already includes +1 increment if condition was met live
        streakCount = ctx.streakCounts.get(eqId, 1)
        conditionMet = ctx.liveStreakConditionsMet.get(eqId, True)

        if not conditionMet:
            # Condition not yet met → show base only (no growth)
            result = _streakReward(primary, baseReward)
            result.equation = f"{baseReward} base"
            return result

        peerBonus = max(0, getattr(ctx, 'streakCardCount', 1) - 1)
        effectiveCount = streakCount + peerBonus
        growthTicks = max(0, effectiveCount - 1)
        totalReward = baseReward + growthPerTick * growthTicks
        if peerBonus > 0:
            eq = f"{baseReward} base + ({growthPerTick}/streak × {growthTicks} [{max(0, streakCount - 1)} wk + {peerBonus} synergy])"
        else:
            eq = f"{baseReward} base + ({growthPerTick}/streak × {max(0, streakCount - 1)})"

    result = _streakReward(primary, totalReward)
    result.equation = eq
    return result


def _countWeeklyTicks(effectName, primary, ctx):
    """Count ticks for weekly-reset streaks."""
    if effectName == "touchdown_jackpot":
        return ctx.rosterTotalTds
    return 0


def _computeOdometer(primary, ctx, cardPlayerId, eqId):
    """Yard gates with escalating payouts. Each gate crossed adds its FP bonus."""
    totalYards = _getRosterTotalYards(ctx)
    gates = primary.get("gates", [])
    # Legacy cards stored accumulator params (baseReward/growthPerTick/yardsPerTick)
    # instead of gates — use current gate thresholds with legacy FP values
    if not gates and "yardsPerTick" in primary:
        baseReward = primary.get("baseReward", 5.0)
        growth = primary.get("growthPerTick", 6.0)
        gates = [
            {"yards": 200, "fp": round(baseReward, 1)},
            {"yards": 400, "fp": round(baseReward + growth, 1)},
            {"yards": 600, "fp": round(baseReward + growth * 2, 1)},
            {"yards": 800, "fp": round(baseReward + growth * 3, 1)},
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
        eq = f"{totalYards} roster yds — next gate at {nextGate['yards']}"
        return EffectResult(equation=eq)
    nextIdx = gatesHit
    if nextIdx < len(gates):
        nextLabel = f" — next gate at {gates[nextIdx]['yards']}yd"
    else:
        nextLabel = " — all gates cleared!"
    totalFP = round(totalFP, 1)
    eq = f"{totalYards} roster yds: {', '.join(gateDetails)} = +{totalFP} FP{nextLabel}"
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
    """FP scaling with QB slot's pass yards."""
    perHundredFP = primary.get("perHundredYardsFP", 6.0)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 1)
    passYards = stats.get("passing_stats", {}).get("passYards", 0) if isinstance(stats.get("passing_stats"), dict) else 0
    chunks = passYards / 100.0
    fp = round(perHundredFP * chunks, 1)
    eq = f"{perHundredFP} FP/100yds × {passYards} pass yds = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeAirRaid(primary, ctx, cardPlayerId, eqId):
    """Floobits per QB slot passing TD."""
    perTdF = primary.get("perTdFloobits", 12)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 1)
    tds = stats.get("passing_stats", {}).get("tds", 0) if isinstance(stats.get("passing_stats"), dict) else 0
    floobits = int(perTdF * tds)
    eq = f"{perTdF}F/TD × {tds} QB pass TD{'s' if tds != 1 else ''}"
    return EffectResult(floobits=floobits, equation=eq)


def _computeWorkhorse(primary, ctx, cardPlayerId, eqId):
    """FP scaling with RB slot's rushing attempts."""
    perAttFP = primary.get("perAttemptFP", 0.8)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 2)
    attempts = stats.get("rushing_stats", {}).get("carries", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    fp = round(perAttFP * attempts, 1)
    eq = f"{perAttFP} FP/att × {attempts} rush attempts = +{fp} FP"
    return EffectResult(fpBonus=fp, equation=eq)


def _computeExpedition(primary, ctx, cardPlayerId, eqId):
    """FP scaling with RB slot's rushing yards."""
    perFiftyFP = primary.get("perFiftyYardsFP", 2.5)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 2)
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
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 2)
    rushYards = stats.get("rushing_stats", {}).get("runYards", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    if rushYards >= threshold:
        eq = f"{enhancedMult:.2f}x FPx ({rushYards} rush yds >= {threshold})"
        return EffectResult(multBonus=enhancedMult, equation=eq)
    eq = f"{baseMult:.2f}x FPx (base — {rushYards} rush yds < {threshold})"
    return EffectResult(multBonus=baseMult, equation=eq)


def _computeGoalLineVulture(primary, ctx, cardPlayerId, eqId):
    """Floobits per RB slot rushing TD."""
    perTd = primary.get("perTdFloobits", 4)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 2)
    tds = stats.get("rushing_stats", {}).get("runTds", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    floobits = int(perTd * tds)
    eq = f"{perTd}/TD × {tds} RB rush TDs"
    return EffectResult(floobits=floobits, equation=eq)


def _computePossession(primary, ctx, cardPlayerId, eqId):
    """FP scaling with WR slots' combined receptions."""
    perRec = primary.get("perReceptionFP", 0.5)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 3)
    recs = stats.get("receiving_stats", {}).get("receptions", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    bonus = round(perRec * recs, 1)
    eq = f"{perRec}/rec × {recs} WR receptions"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeDeepThreat(primary, ctx, cardPlayerId, eqId):
    """FP if either WR slot catches a 25+ yard pass."""
    rewardValue = primary.get("rewardValue", 12)
    pids = _getRosterPlayersByPosition(ctx, ctx.cardPosition or 3)
    hasDeepCatch = False
    for pid in pids:
        stats = ctx.weekPlayerStats.get(pid, {})
        rcvStats = stats.get("receiving_stats", {})
        if isinstance(rcvStats, dict):
            longest = rcvStats.get("longest", 0) or rcvStats.get("longestRec", 0)
            if longest >= 25:
                hasDeepCatch = True
                break
    if hasDeepCatch:
        eq = f"+{rewardValue} FP (WR 25+ yd reception)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = "No 25+ yd WR reception"
    return EffectResult(equation=eq)


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
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 3)
    yac = stats.get("receiving_stats", {}).get("yac", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    bonus = round(perYac * (yac / 10), 1)
    eq = f"{perYac}/10yac × {yac} YAC"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeYacAttack(primary, ctx, cardPlayerId, eqId):
    """Flat FP if WR slots combine for threshold+ YAC."""
    rewardValue = primary.get("rewardValue", 6)
    threshold = primary.get("threshold", 30)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 3)
    yac = stats.get("receiving_stats", {}).get("yac", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    if yac >= threshold:
        eq = f"+{rewardValue} FP ({yac} YAC >= {threshold})"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"{yac}/{threshold} YAC needed"
    return EffectResult(equation=eq)



def _computeSafetyBlanket(primary, ctx, cardPlayerId, eqId):
    """FP scaling with TE slot's receptions."""
    perRec = primary.get("perReceptionFP", 0.6)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 4)
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
    """FP when player at card's position scores 2+ TDs."""
    posLabel = POSITION_LABELS.get(ctx.cardPosition, "??")
    rewardValue = primary.get("rewardValue", 15)
    stats = _getRosterStatsAtPosition(ctx, ctx.cardPosition or 4)
    tds = _countPlayerTds(stats)
    if tds >= 2:
        eq = f"+{rewardValue} FP ({tds} {posLabel} TDs)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"{tds}/2 {posLabel} TDs needed"
    return EffectResult(equation=eq)


def _computeSniper(primary, ctx, cardPlayerId, eqId):
    """FP per 40+ yard FG by K slot."""
    perFg = primary.get("perFgFP", 2)
    _, _, _, fg40plus = _getKickerFgStats(ctx)
    bonus = round(perFg * fg40plus, 1)
    eq = f"{perFg}/FG × {fg40plus} FGs 40+ yds"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeHotHand(primary, ctx, cardPlayerId, eqId):
    """FP scaling with FGs made by K slot this week."""
    fgMade, _, _, _ = _getKickerFgStats(ctx)
    if fgMade == 0:
        return EffectResult(equation="No FGs made")
    # New FP path
    perFGFP = primary.get("perFGFP", 0)
    if perFGFP:
        bonus = round(perFGFP * fgMade, 1)
        eq = f"{perFGFP}/FG × {fgMade} FGs = +{bonus} FP"
        return EffectResult(fpBonus=bonus, equation=eq)
    # Legacy FPx path
    perFGMult = primary.get("perFGMult", 0.1)
    bonus = round(perFGMult * fgMade, 2)
    eq = f"1 + ({perFGMult}/FG × {fgMade} FGs) = {1 + bonus:.2f}x"
    return EffectResult(multBonus=1 + bonus, equation=eq)


def _computeGameBall(primary, ctx, cardPlayerId, eqId):
    """FP when roster player at card position overperforms their base rating."""
    if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    pos = ctx.cardPosition or 1
    pids = _getRosterPlayersByPosition(ctx, pos)
    if not pids:
        return EffectResult(equation="no roster player at position")
    for pid in pids:
        gamePerfRating = ctx.gamePerformanceRatings.get(pid, 0)
        baseRating = ctx.rosterPlayerRatings.get(pid, 60)
        if gamePerfRating > baseRating and gamePerfRating > 0:
            playerName = ctx.rosterPlayerNames.get(pid, "?")
            result = _conditionalReward(primary)
            result.equation = f"{playerName} overperformed"
            return result
    names = [ctx.rosterPlayerNames.get(pid, "?") for pid in pids]
    return EffectResult(equation=f"{' + '.join(names)}: did not overperform")


def _computeBoomWeek(primary, ctx, cardPlayerId, eqId):
    """FP scaling with how much roster player overperformed this week."""
    if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    pos = ctx.cardPosition or 1
    pids = _getRosterPlayersByPosition(ctx, pos)
    bestOver = 0
    for pid in pids:
        gameRating = ctx.gamePerformanceRatings.get(pid, 0)
        baseRating = ctx.rosterPlayerRatings.get(pid, 60)
        over = gameRating - baseRating
        if over > bestOver:
            bestOver = over
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
    return EffectResult(multBonus=bonus, equation=f"Overperformed — {bonus}x FP")


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
        pos = ctx.cardPosition or 1
        pids = _getRosterPlayersByPosition(ctx, pos)
        worstUnder = 0
        for pid in pids:
            gameRating = ctx.gamePerformanceRatings.get(pid, 0)
            baseRating = ctx.rosterPlayerRatings.get(pid, 60)
            under = baseRating - gameRating
            if under > worstUnder:
                worstUnder = under
        if worstUnder > 0:
            floobits = int(perPoint * worstUnder)
            return EffectResult(floobits=floobits, equation=f"Underperformed — +{floobits} Floobits")
        return EffectResult(equation="Did not underperform")
    if not ctx.gamePerformanceRatings or getattr(ctx, 'gamesActive', False):
        return EffectResult(equation="Waiting for games to complete")
    pos = ctx.cardPosition or 1
    pids = _getRosterPlayersByPosition(ctx, pos)
    worstUnder = 0
    for pid in pids:
        gameRating = ctx.gamePerformanceRatings.get(pid, 0)
        baseRating = ctx.rosterPlayerRatings.get(pid, 60)
        under = baseRating - gameRating
        if under > worstUnder:
            worstUnder = under
    if worstUnder <= 0:
        return EffectResult(floobits=baseFloobits, equation=f"+{baseFloobits}F. Did not underperform")
    baseChance = min(0.70, worstUnder * 0.025 + 0.075)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    floobitsVal = enhancedFloobits if triggered else baseFloobits
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFloobits}F", "underperformed", ctx=ctx, base=f"+{baseFloobits}F")
    return EffectResult(floobits=floobitsVal, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


# ── Escalating / Pace Effects ────────────────────────────────────────────────

def _getPositionTds(ctx, position: int) -> int:
    """Get TDs relevant to position from roster stats."""
    stats = _getRosterStatsAtPosition(ctx, position)
    if position == 1:  # QB — passing TDs
        return stats.get("passing_stats", {}).get("tds", 0) if isinstance(stats.get("passing_stats"), dict) else 0
    if position == 2:  # RB — rushing TDs
        return stats.get("rushing_stats", {}).get("runTds", 0) if isinstance(stats.get("rushing_stats"), dict) else 0
    if position == 3:  # WR — receiving TDs
        return stats.get("receiving_stats", {}).get("rcvTds", 0) if isinstance(stats.get("receiving_stats"), dict) else 0
    if position == 5:  # K — FGs made
        fgMade, _, _, _ = _getKickerFgStats(ctx)
        return fgMade
    return 0


def _getPositionYards(ctx, position: int) -> int:
    """Get yards relevant to position from roster stats."""
    stats = _getRosterStatsAtPosition(ctx, position)
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
    triggers = _getPositionTds(ctx, pos)

    if triggers <= 0:
        eq = f"+{baseFP} FP. 0 {triggerLabel}"
        return EffectResult(fpBonus=baseFP, equation=eq)

    # During live games, show current escalated chance without rolling
    if getattr(ctx, 'gamesActive', False):
        currentBase = (baseChance + (triggers - 1) * chanceStep) / 100.0
        totalWithBonus = min(0.95, currentBase + ctx.chanceBonus)
        eq = _chanceEq(currentBase, ctx.chanceBonus, totalWithBonus, False,
                       f"+{bonusFP} FP", f"{triggers} {triggerLabel}", ctx=ctx, base=f"+{baseFP} FP")
        return EffectResult(fpBonus=baseFP, equation=eq)

    # At week end: simulate sequential rolls per trigger
    rng = _chanceRoll(ctx, eqId)
    hit = False
    hitOnTrigger = 0
    for i in range(triggers):
        chance = min(0.95, (baseChance + i * chanceStep) / 100.0 + ctx.chanceBonus)
        roll = rng.random()
        if roll <= chance:
            hit = True
            hitOnTrigger = i + 1
            break

    fp = bonusFP if hit else baseFP
    finalBase = (baseChance + (hitOnTrigger - 1 if hit else triggers - 1) * chanceStep) / 100.0
    finalChance = min(0.95, finalBase + ctx.chanceBonus)
    bonusStr = f"+{ctx.chanceBonus:.0%}" if ctx.chanceBonus > 0 else ""
    pctStr = f"({finalBase:.0%}{bonusStr})" if bonusStr else f"{finalChance:.0%}"
    if hit:
        eq = f"+{bonusFP} FP. Hit on {triggerLabel[:-1]} #{hitOnTrigger} of {triggers} ({pctStr})"
    else:
        eq = f"+{baseFP} FP. {triggers} {triggerLabel}, maxed at {pctStr}, missed"
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(rng.random(), 4), chanceThreshold=round(finalChance, 4), chanceTriggered=hit)


def _computeEminence(primary, ctx, cardPlayerId, eqId):
    """FPx multiplier based on player's FP/game pace vs position average.

    Active from week 3 onward. Below pace = 1.0x (no penalty).
    Uses positionAvgFPs and playerSeasonFPPerGame from context.
    """
    bonusPerFP = primary.get("bonusPerFP", 0.02)
    maxMult = primary.get("maxMult", 1.18)
    weekNum = getattr(ctx, 'weekNumber', 0)

    if weekNum < 3:
        return EffectResult(multBonus=1.0, equation="1.00x FPx — inactive until week 3")

    pos = ctx.cardPosition or 1
    posAvg = getattr(ctx, 'positionAvgFPs', {}).get(pos, 0.0)
    # Find the roster player at this position to look up their FP/game
    pids = _getRosterPlayersByPosition(ctx, pos)
    playerAvg = 0.0
    if pids:
        fpMap = getattr(ctx, 'playerSeasonFPPerGame', {})
        playerAvg = max(fpMap.get(pid, 0.0) for pid in pids)

    if posAvg <= 0:
        return EffectResult(multBonus=1.0, equation="1.00x FPx — no position data yet")

    abovePace = playerAvg - posAvg
    if abovePace <= 0:
        eq = f"1.00x FPx — {abovePace:+.1f} below pace ({playerAvg:.1f} vs {posAvg:.1f} avg)"
        return EffectResult(multBonus=1.0, equation=eq)

    mult = min(maxMult, round(1.0 + abovePace * bonusPerFP, 2))
    eq = f"{mult:.2f}x FPx — {abovePace:+.1f} above pace ({playerAvg:.1f} vs {posAvg:.1f} avg)"
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

    yards = _getPositionYards(ctx, pos)
    steps = int(yards // yardStep)
    baseChance = (primary.get("baseChance", 5) + steps * chancePerStep) / 100.0
    totalChance = min(0.95, baseChance + ctx.chanceBonus)

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
    """Dynamic chance boost from roster FP + small floobits base.

    Boost = (rosterFP - baseline) / fpPer1Pct / 100, capped at maxBoost.
    Also pays a flat floobits dividend.
    """
    fpPer1Pct = primary.get("fpPer1Pct", 12)
    baseline = primary.get("baseline", 55)
    maxBoost = primary.get("maxBoost", 0.10)
    baseFloobits = primary.get("baseFloobits", 3)
    rosterFP = ctx.weekRawFP

    if rosterFP > baseline:
        boost = min(maxBoost, (rosterFP - baseline) / fpPer1Pct / 100)
    else:
        boost = 0.0

    eq = f"{rosterFP:.1f} roster FP · +{boost:.1%} chance boost · {baseFloobits}F"
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
                    eq = f"{rewardValue} (QB + WR on same team)"
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
                    eq = f"{1 + rewardValue:.2f}x FPx (QB + RB on same team)"
                    return EffectResult(multBonus=1 + rewardValue, equation=eq)
    eq = "QB and RB not on same team"
    return EffectResult(equation=eq)


def _computeHomer(primary, ctx, cardPlayerId, eqId):
    """+FP scaling with how many roster players are on favorite team."""
    perPlayer = primary.get("perPlayerFP", 1.5)
    favTeamId = ctx.userFavoriteTeamId
    count = sum(1 for pid in ctx.rosterPlayerIds
                if ctx.rosterPlayerTeamIds.get(pid, 0) == favTeamId) if favTeamId else 0
    bonus = round(perPlayer * count, 1)
    eq = f"{perPlayer}/player × {count} on your favorite team"
    return EffectResult(fpBonus=bonus, equation=eq)


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


def _computeConnection(primary, ctx, cardPlayerId, eqId):
    """Floobits per TD scored by a roster player who shares a team with another."""
    perTd = primary.get("perTdFloobits", 3)
    groups = _getSameTeamGroups(ctx)
    # Find players who share a team with at least one other roster player
    connectedPids = set()
    for _, pids in groups.items():
        if len(pids) >= 2:
            connectedPids.update(pids)
    # Count TDs by connected players
    tds = 0
    for pid in connectedPids:
        tds += _countPlayerTds(ctx.weekPlayerStats.get(pid, {}))
    floobits = int(perTd * tds)
    eq = f"{perTd}/TD × {tds} TDs by connected players"
    return EffectResult(floobits=floobits, equation=eq)


def _computeTeamChemistry(primary, ctx, cardPlayerId, eqId):
    """Floobits scaling with number of same-team groups."""
    groups = _getSameTeamGroups(ctx)
    numGroups = sum(1 for pids in groups.values() if len(pids) >= 2)
    # New Floobits path
    perGroupFloobits = primary.get("perGroupFloobits", 0)
    if perGroupFloobits:
        bonus = int(perGroupFloobits * numGroups)
        eq = f"{perGroupFloobits}F/group × {numGroups} same-team pairs"
        return EffectResult(floobits=bonus, equation=eq)
    # Legacy FPx path
    perGroup = primary.get("perGroupMult", 0.15)
    bonus = round(perGroup * numGroups, 2)
    eq = f"1 + ({perGroup}/group × {numGroups} same-team pairs) = {1 + bonus:.2f}x"
    return EffectResult(multBonus=1 + bonus, equation=eq)


# ── Card-to-Card Interaction Effects ─────────────────────────────────────────

# -- Hand Composition (first pass) --

def _computeFullRoster(primary, ctx, cardPlayerId, eqId):
    """FPx when equipped hand has all 5 positions."""
    rewardValue = primary.get("rewardValue", 1.4)
    positions = set(ctx.equippedCardPositions)
    if len(positions) >= 5:
        eq = f"{rewardValue} (all 5 positions in hand)"
        return EffectResult(multBonus=rewardValue, equation=eq)
    missing = 5 - len(positions)
    eq = f"{len(positions)}/5 positions ({missing} missing)"
    return EffectResult(equation=eq)


def _computeAllIn(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with duplicate position cards."""
    baseXMult = primary.get("baseXMult", 1.1)
    perDupe = primary.get("perDuplicateXMult", 0.15)
    positions = ctx.equippedCardPositions
    if not positions:
        return EffectResult(equation="No cards equipped")
    # Count max duplicates for any single position
    from collections import Counter
    posCounts = Counter(positions)
    maxCount = max(posCounts.values())
    if maxCount <= 1:
        eq = "No duplicate positions"
        return EffectResult(equation=eq)
    dupes = maxCount - 1
    bonus = round(baseXMult + perDupe * dupes, 2)
    eq = f"{baseXMult} base + ({perDupe} × {dupes} dupes) = {bonus}"
    return EffectResult(multBonus=bonus, equation=eq)


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
    """FPx per multiplier card in hand."""
    perCard = primary.get("perCardMult", 0.1)
    multCount = sum(1 for t in ctx.equippedCardOutputTypes if t == "mult")
    # Subtract 1 for this card itself
    otherMults = max(0, multCount - 1)
    bonus = round(perCard * otherMults, 2)
    eq = f"1 + ({perCard}/card × {otherMults} other FPx cards) = {1 + bonus:.2f}x"
    return EffectResult(multBonus=1 + bonus, equation=eq)


# -- Trigger-Chain (second pass) --

def _computeCopycat(primary, ctx, cardPlayerId, eqId):
    """+FP equal to the highest flat FP bonus among other cards."""
    breakdowns = ctx._firstPassBreakdowns or []
    bestFP = 0
    for b in breakdowns:
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
    if triggeredCount > 0:
        bonus = round(1 + perCard * triggeredCount, 2)
        eq = f"1 + ({perCard} × {triggeredCount} triggered cards) = {bonus}"
        return EffectResult(multBonus=bonus, equation=eq)
    eq = "No other cards triggered"
    return EffectResult(equation=eq)


def _computeBonusRound(primary, ctx, cardPlayerId, eqId):
    """Large FP if 4+ other cards triggered a non-zero bonus."""
    rewardValue = primary.get("rewardValue", 8)
    breakdowns = ctx._firstPassBreakdowns or []
    triggeredCount = sum(1 for b in breakdowns
                         if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
    if triggeredCount >= 4:
        eq = f"+{rewardValue} FP ({triggeredCount}/4+ cards triggered)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"{triggeredCount}/4 cards triggered (need 4+)"
    return EffectResult(equation=eq)


# -- Chance Synergy (second pass) --

def _computeHighRoller(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with how many chance cards triggered their enhanced payout."""
    perCardMult = primary.get("perCardMult", 0.10)
    breakdowns = ctx._firstPassBreakdowns or []
    chanceTriggered = sum(1 for b in breakdowns if b.chanceTriggered)
    if chanceTriggered > 0:
        bonus = round(1 + perCardMult * chanceTriggered, 2)
        eq = f"1 + ({perCardMult} x {chanceTriggered} chance hit{'s' if chanceTriggered != 1 else ''}) = {bonus}x"
        return EffectResult(multBonus=bonus, equation=eq)
    eq = "No chance cards hit"
    return EffectResult(equation=eq)


def _computeJackpot(primary, ctx, cardPlayerId, eqId):
    """Massive FP bonus when every chance card in hand triggered enhanced."""
    rewardValue = primary.get("rewardValue", 20)
    breakdowns = ctx._firstPassBreakdowns or []
    chanceCards = [b for b in breakdowns if b.isChanceEffect]
    if len(chanceCards) == 0:
        eq = "No chance cards in hand"
        return EffectResult(equation=eq)
    chanceTriggered = sum(1 for b in chanceCards if b.chanceTriggered)
    if chanceTriggered == len(chanceCards):
        eq = f"+{rewardValue} FP ({chanceTriggered}/{chanceTriggered} chance cards hit)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"{chanceTriggered}/{len(chanceCards)} chance cards hit (need all)"
    return EffectResult(equation=eq)


# -- Streak Synergy (second pass) --

def _computeIronWill(primary, ctx, cardPlayerId, eqId):
    """FPx scaling with how many streak cards have active streaks."""
    perCardMult = primary.get("perCardMult", 0.10)
    activeStreaks = getattr(ctx, 'activeStreakCount', 0)
    if activeStreaks > 0:
        bonus = round(1 + perCardMult * activeStreaks, 2)
        eq = f"1 + ({perCardMult} × {activeStreaks} active streaks) = {bonus}x"
        return EffectResult(multBonus=bonus, equation=eq)
    eq = "No active streak cards"
    return EffectResult(equation=eq)


def _computeUnbreakable(primary, ctx, cardPlayerId, eqId):
    """Massive FP bonus when every season streak card has an active streak."""
    rewardValue = primary.get("rewardValue", 20)
    streakTotal = getattr(ctx, 'streakCardCount', 0)
    activeStreaks = getattr(ctx, 'activeStreakCount', 0)
    if streakTotal == 0:
        eq = "No streak cards in hand"
        return EffectResult(equation=eq)
    if activeStreaks == streakTotal:
        eq = f"+{rewardValue} FP ({activeStreaks}/{streakTotal} streaks active)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    eq = f"{activeStreaks}/{streakTotal} streaks active (need all)"
    return EffectResult(equation=eq)


# -- Tradeoff/Sacrifice (second pass) --
# Note: Double Down and Feast or Famine are handled by _applyTradeoffEffects
# in cardEffectCalculator.py. Their compute functions just return their FPx
# value as a marker — the actual tradeoff logic modifies other breakdowns.

def _computeDoubleDown(primary, ctx, cardPlayerId, eqId):
    """Large FPx — tradeoff applied post-calculation."""
    rewardValue = primary.get("rewardValue", 2.0)
    breakdowns = ctx._firstPassBreakdowns or []
    nonZero = [b for b in breakdowns if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0]
    if len(nonZero) >= 2:
        eq = f"{rewardValue} to lowest bonus, zeroes highest"
        return EffectResult(multBonus=rewardValue, equation=eq)
    eq = f"Need 2+ non-zero cards ({len(nonZero)} found)"
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
            eq = f"{rewardValue} (no other cards produced a bonus)"
            return EffectResult(multBonus=rewardValue, equation=eq)
        triggeredCount = sum(1 for b in breakdowns if b.totalFP > 0 or b.floobitsEarned > 0 or b.primaryMult > 0)
        eq = f"{triggeredCount} other card(s) produced a bonus"
        return EffectResult(equation=eq)
    if "baseFP" not in primary and "baseMult" in primary:
        baseMult = primary["baseMult"]
        return EffectResult(multBonus=baseMult, equation=f"{baseMult}x FPx (legacy)")
    breakdowns = ctx._firstPassBreakdowns or []
    failedCount = sum(1 for b in breakdowns if b.totalFP <= 0 and b.floobitsEarned <= 0 and b.primaryMult <= 0)
    if failedCount <= 0:
        eq = f"+{baseFP} FP. All cards triggered"
        return EffectResult(fpBonus=baseFP, equation=eq)
    baseChance = min(0.70, failedCount * 0.14 + 0.01)
    totalChance = min(0.95, baseChance + ctx.chanceBonus)
    rng = _chanceRoll(ctx, eqId)
    roll = rng.random()
    triggered = roll <= totalChance and not getattr(ctx, 'gamesActive', False)
    fp = enhancedFP if triggered else baseFP
    eq = _chanceEq(baseChance, ctx.chanceBonus, totalChance, triggered,
                   f"+{enhancedFP} FP", f"{failedCount} cards failed", ctx=ctx, base=f"+{baseFP} FP")
    return EffectResult(fpBonus=fp, equation=eq,
                        chanceRoll=round(roll, 4), chanceThreshold=round(totalChance, 4), chanceTriggered=triggered)


# ── Game-Outcome Effects ─────────────────────────────────────────────────────

def _computeComebackKid(primary, ctx, cardPlayerId, eqId):
    """FP scaling with deficit overcome when favorite team wins."""
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="Waiting for games to complete")
    perPoint = primary.get("perPointFP", 0.5)
    if ctx.favoriteTeamComebackWin and ctx.favoriteTeamLargestDeficit > 0:
        deficit = ctx.favoriteTeamLargestDeficit
        bonus = round(perPoint * deficit, 1)
        eq = f"{perPoint}/pt × {deficit} pt deficit overcome"
        return EffectResult(fpBonus=bonus, equation=eq)
    if ctx.favoriteTeamComebackWin:
        eq = "Comeback win but no measurable deficit"
    else:
        eq = "No comeback win"
    return EffectResult(equation=eq)


def _computeDomination(primary, ctx, cardPlayerId, eqId):
    """Base FP on your favorite team win, big FP bonus on blowout win."""
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="Waiting for games to complete")
    baseFP = primary.get("baseFP", 5)
    rewardValue = primary.get("rewardValue", 18)
    threshold = primary.get("marginThreshold", 21)
    margin = ctx.favoriteTeamScoreMargin
    # Legacy fallback
    if "baseFP" not in primary and "baseMult" in primary:
        baseMult = primary["baseMult"]
        mult = primary.get("rewardValue", 1.5)
        if ctx.favoriteTeamWonThisWeek and margin >= threshold:
            return EffectResult(multBonus=mult, equation=f"{mult}x (legacy blowout)")
        if ctx.favoriteTeamWonThisWeek:
            return EffectResult(multBonus=baseMult, equation=f"{baseMult}x (legacy win)")
        return EffectResult(equation="Your favorite team didn't win")
    if ctx.favoriteTeamWonThisWeek and margin >= threshold:
        eq = f"+{rewardValue} FP (your favorite team won by {margin}, blowout!)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    if ctx.favoriteTeamWonThisWeek:
        eq = f"+{baseFP} FP (your favorite team won by {margin})"
        return EffectResult(fpBonus=baseFP, equation=eq)
    eq = "Your favorite team didn't win"
    return EffectResult(equation=eq)


def _computeWalkOff(primary, ctx, cardPlayerId, eqId):
    """Base FP on your favorite team win, big FP bonus on walk-off win."""
    if not ctx.favoriteTeamGameFinal:
        return EffectResult(equation="Waiting for games to complete")
    baseFP = primary.get("baseFP", 4)
    rewardValue = primary.get("rewardValue", 20)
    if ctx.favoriteTeamWalkOffWin:
        eq = f"+{rewardValue} FP (walk-off win!)"
        return EffectResult(fpBonus=rewardValue, equation=eq)
    if ctx.favoriteTeamWonThisWeek:
        eq = f"+{baseFP} FP (your favorite team won, no walk-off)"
        return EffectResult(fpBonus=baseFP, equation=eq)
    eq = "Your favorite team didn't win"
    return EffectResult(equation=eq)


# ─── Strategy-Warping Effect Compute Functions ──────────────────────────────

MAX_ROSTER_SLOTS = 6  # QB, RB, WR1, WR2, TE, K


def _computeAlchemy(primary, ctx, cardPlayerId, eqId):
    """FGs count as TDs: bonus FP per FG, and bump rosterTotalTds for synergy."""
    if not ctx.gamesActive and not ctx.teamResults:
        return EffectResult(equation="Waiting for games")
    perFgBonusFP = primary.get("perFgBonusFP", 3.0)
    # Find kicker FGs from roster (K position = 5)
    fgsMade = 0
    for pid in ctx.rosterPlayerIds:
        if ctx.rosterPlayerPositions.get(pid) == 5:
            kickStats = ctx.weekPlayerStats.get(pid, {}).get("kicking_stats", {})
            fgsMade += kickStats.get("fgs", 0)
    if fgsMade == 0:
        return EffectResult(equation="No FGs made by K slot")
    bonus = round(perFgBonusFP * fgsMade, 1)
    # Bump rosterTotalTds so TD-counting effects (Cornucopia, Touchdown Piñata, etc.) synergize
    ctx.rosterTotalTds += fgsMade
    eq = f"{perFgBonusFP}/FG × {fgsMade} FGs (counted as TDs)"
    return EffectResult(fpBonus=bonus, equation=eq)


def _computeAusterity(primary, ctx, cardPlayerId, eqId):
    """FPx per empty roster slot. Fewer players = bigger multiplier."""
    perSlotMult = primary.get("perSlotMult", 0.15)
    filledSlots = len(ctx.rosterPlayerIds)
    emptySlots = max(0, MAX_ROSTER_SLOTS - filledSlots)
    if emptySlots == 0:
        return EffectResult(multBonus=1.0, equation="No empty roster slots")
    mult = round(1.0 + perSlotMult * emptySlots, 3)
    eq = f"1.0 + {perSlotMult}/slot × {emptySlots} empty = {mult}x"
    return EffectResult(multBonus=mult, equation=eq)


def _computeConsolation(primary, ctx, cardPlayerId, eqId):
    """Base FP always, bonus FP when the card's position slot player's team loses."""
    if not ctx.teamResults:
        return EffectResult(equation="Waiting for games to complete")
    baseFP = primary.get("baseFP", 3.0)
    lossBonusFP = primary.get("lossBonusFP", 10.0)
    # Check roster players at this card's position slot (WR returns both)
    slotPids = _getRosterPlayersByPosition(ctx, ctx.cardPosition or 3)
    if not slotPids:
        return EffectResult(fpBonus=baseFP, equation=f"{baseFP} base (no player in slot)")
    # Bonus triggers if any slot player's team lost
    anyLost = False
    for pid in slotPids:
        teamId = ctx.rosterPlayerTeamIds.get(pid)
        if teamId and ctx.teamResults.get(teamId) is False:
            anyLost = True
            break
    if anyLost:
        total = round(baseFP + lossBonusFP, 1)
        eq = f"{baseFP} base + {lossBonusFP} loss bonus = {total}"
        return EffectResult(fpBonus=total, equation=eq)
    return EffectResult(fpBonus=baseFP, equation=f"{baseFP} base (slot player's team won)")


def _computeCloser(primary, ctx, cardPlayerId, eqId):
    """Bonus FP based on Q4/OT fantasy points earned by roster players."""
    if ctx.gamesActive:
        return EffectResult(equation="Waiting for games to complete")
    q4MultFactor = primary.get("q4MultFactor", 2.0)
    # Sum Q4 FP across all rostered players
    totalQ4FP = 0
    for pid in ctx.rosterPlayerIds:
        ps = ctx.weekPlayerStats.get(pid, {})
        totalQ4FP += ps.get("q4FantasyPoints", 0)
    if totalQ4FP <= 0:
        return EffectResult(equation="No Q4/OT fantasy points")
    bonus = round(q4MultFactor * totalQ4FP, 1)
    eq = f"{q4MultFactor}x × {round(totalQ4FP, 1)} Q4/OT FP = +{bonus}"
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
    posLabel = POSITION_LABELS.get(cardPos, "player")
    eq = f"1.0 + {perStarMult}/star × {avgStarsUnder:.1f} stars under 5 ({posLabel}) = {mult}x"
    return EffectResult(multBonus=mult, equation=eq)


def _computeVagabond(primary, ctx, cardPlayerId, eqId):
    """FPx per roster swap used this season — inverse of Stockpiler."""
    perSwap = primary.get("perSwapXMult", 0.03)
    swapsUsed = ctx.seasonSwapsUsed
    if swapsUsed <= 0:
        return EffectResult(multBonus=1.0, equation="No swaps used this season")
    mult = round(1.0 + perSwap * swapsUsed, 3)
    eq = f"1.0 + {perSwap}/swap × {swapsUsed} swaps used = {mult}x"
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
    """Raises the weekly Floobits payout cap. Output is informational only —
    the actual cap raise is applied in seasonManager._awardWeeklyFpFloobits()."""
    ceilingBonus = primary.get("ceilingBonus", 10)
    from constants import WEEKLY_FP_FLOOBIT_CAP
    newCap = WEEKLY_FP_FLOOBIT_CAP + ceilingBonus
    return EffectResult(floobits=0, equation=f"+{ceilingBonus} cap raise (effective cap: {newCap}F)")


def _computeCultivation(primary, ctx, cardPlayerId, eqId):
    """Growing chance — base FP that can permanently increase each week.
    streak_count tracks how many times the base has grown."""
    baseFP = primary.get("baseFP", 4.0)
    growthFP = primary.get("growthFP", 2.0)
    # streak_count tracks number of successful growths (starts at 1 = no growth)
    growthLevel = max(0, ctx.streakCounts.get(eqId, 1) - 1)
    currentFP = round(baseFP + growthFP * growthLevel, 1)
    # Count trigger events across all rostered players
    triggerEvent = primary.get("triggerEvent", "pass_td")
    triggerLabel = primary.get("triggerLabel", "events")
    triggerCount = _countCultivationTriggers(triggerEvent, ctx)
    # Calculate growth chance
    baseChance = primary.get("baseChance", 20)
    chancePerTrigger = primary.get("chancePerTrigger", 5)
    growthChance = min(90, baseChance + chancePerTrigger * triggerCount)
    nextFP = round(currentFP + growthFP, 1)
    triggerNote = f" ({triggerCount} {triggerLabel})" if triggerCount > 0 else ""
    eq = f"+{currentFP} FP. {growthChance}% chance{triggerNote} to increase to +{nextFP} FP"
    return EffectResult(fpBonus=currentFP, equation=eq)


def _countCultivationTriggers(triggerEvent, ctx):
    """Sum trigger events across all rostered players for Cultivation."""
    total = 0
    triggerDef = None
    for t in CULTIVATION_TRIGGER_POOL:
        if t["event"] == triggerEvent:
            triggerDef = t
            break
    if not triggerDef:
        return 0
    for pid in ctx.rosterPlayerIds:
        ps = ctx.weekPlayerStats.get(pid, {})
        for catKey, statKey in triggerDef["statPaths"]:
            total += ps.get(catKey, {}).get(statKey, 0)
    return total


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
    "windfall": _computeDiamondInTheRough,
    "rng": _computeRng,
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
    "upset_special": _computeUpsetSpecial,
    "believe": _computeBelieve,
    "feeding_frenzy": _computeFeedingFrenzy,
    "spotlight_moment": _computeSpotlightMoment,
    "highlight_reel": _computeHighlightReel,
    "schadenfreude": _computeSchadenfreude,
    "reclamation": _computeFixerUpper,
    "pedigree": _computePedigree,
    # Streak (K) — all use the generic streak handler
    "couch_potato": _computeStreakEffect,
    "complacency": _computeStreakEffect,
    "on_fire": _computeStreakEffect,
    "gravy_train": _computeStreakEffect,
    "snowball_fight": _computeStreakEffect,
    "fairweather_fan": _computeStreakEffect,
    "bandwagon_express": _computeStreakEffect,
    "touchdown_jackpot": _computeStreakEffect,
    "odometer": _computeOdometer,
    "leg_day": _computeStreakEffect,
    "automatic": _computeStreakEffect,
    "hot_hand": _computeHotHand,
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
    "game_ball": _computeGameBall,
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
    "connection": _computeConnection,
    "team_chemistry": _computeTeamChemistry,
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
    "double_down": _computeDoubleDown,
    "last_resort": _computeLastResort,
    "high_roller": _computeHighRoller,
    "jackpot": _computeJackpot,
    "fortitude": _computeIronWill,
    "immaculate": _computeUnbreakable,
    # ── Strategy-Warping Effects ──
    "alchemy": _computeAlchemy,
    "home_alone": _computeAusterity,
    "moral_victory": _computeConsolation,
    "closer": _computeCloser,
    "dark_horse": _computeHumility,
    "vagabond": _computeVagabond,
    "fat_cat": _computeOpulence,
    "surplus": _computeProsperity,
    "bonsai": _computeCultivation,
}


def computeEffect(effectConfig: dict, ctx, cardPlayerId: int, equippedCardId: int,
                   firstPassBreakdowns=None) -> EffectResult:
    """Dispatch to the named effect's compute function.

    For second-pass effects, firstPassBreakdowns provides the results of all
    first-pass cards so they can react to other cards' outputs.
    """
    effectName = effectConfig.get("effectName", "")
    handler = EFFECT_REGISTRY.get(effectName)
    if not handler:
        logger.warning(f"Unknown effect: {effectName}")
        return EffectResult()

    primary = effectConfig.get("primary", {})

    # For streak effects, stash the effect name on ctx temporarily
    # so the generic streak handler knows which config to look up
    ctx._currentEffectName = effectName

    # Stash first-pass breakdowns on ctx for second-pass effects
    ctx._firstPassBreakdowns = firstPassBreakdowns

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
        fgMade, _, _, _ = _getKickerFgStats(ctx)
        return fgMade > 0

    if condition == "kicker_2fg":
        fgMade, _, _, _ = _getKickerFgStats(ctx)
        return fgMade >= 2

    if condition == "card_player_team_wins":
        cardPlayerStats = ctx.weekPlayerStats.get(cardPlayerId, {})
        teamId = cardPlayerStats.get("teamId")
        return ctx.teamResults.get(teamId, False) if teamId else False

    if condition == "roster_td":
        return ctx.rosterTotalTds > 0

    if condition == "favorite_team_wins":
        return ctx.favoriteTeamWonThisWeek

    if condition == "kicker_45plus":
        _, _, longest, _ = _getKickerFgStats(ctx)
        return longest >= 45

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
        return ctx.weekRawFP >= 75

    if condition == "favorite_team_upset_win":
        return ctx.favoriteTeamWonThisWeek and ctx.favoriteTeamOpponentElo > ctx.favoriteTeamElo

    return True
