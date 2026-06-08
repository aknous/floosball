import enum
from os import stat
import math
from random import randint
from random_batch import batched_randint, batched_random
import copy
from stats_optimization import OptimizedPlayerStats, get_optimized_stats
import numpy as np
import floosball_methods as FloosMethods
from floosball_team import Team
from stat_tracker import StatTracker
from player_development import PlayerDevelopment
from rating_cache import CachedRatingMixin

class Position(enum.Enum):
    QB = 1
    RB = 2
    WR = 3
    TE = 4
    K = 5

class DefensivePosition(enum.Enum):
    S = 'S'     # Safety (QB)
    LB = 'LB'   # Linebacker (RB)
    CB = 'CB'   # Cornerback (WR)
    DE = 'DE'   # Defensive End (TE)

# Offensive → Defensive position mapping
DEFENSIVE_POSITION_MAP = {
    Position.QB: DefensivePosition.S,
    Position.RB: DefensivePosition.LB,
    Position.WR: DefensivePosition.CB,
    Position.TE: DefensivePosition.DE,
    Position.K: None,  # Kickers don't play defense
}

class PlayerTier(enum.Enum):
    TierS = 5
    TierA = 4
    TierB = 3
    TierC = 2
    TierD = 1

class PlayerServiceTime(enum.Enum):
    Rookie = 'Rookie'
    Veteran1 = 'Established'
    Veteran2 = 'Veteran'
    Veteran3 = 'Grizzled Veteran'
    Veteran4 = 'Ancient Veteran'
    Retired = 'Retired'

playerStatsDict =   {   
                        'team': None,
                        'season': 0,
                        'gp': 0,
                        'fantasyPoints': 0,
                        'passing': {
                            'att': 0, 
                            'comp': 0, 
                            'compPerc': 0, 
                            'missedPass': 0,
                            'tds': 0, 
                            'ints': 0, 
                            'yards': 0, 
                            'ypc': 0, 
                            '20+': 0,
                            'longest': 0
                        },
                        'rushing': {
                            'carries': 0,
                            'yards': 0, 
                            'ypc': 0, 
                            'tds': 0, 
                            'fumblesLost': 0, 
                            '20+': 0,
                            'longest': 0
                        },
                        'receiving': {
                            'receptions': 0, 
                            'targets': 0, 
                            'rcvPerc': 0, 
                            'drops': 0,
                            'yards': 0,
                            'yac': 0, 
                            'ypr': 0, 
                            'tds': 0,
                            '20+': 0,
                            'longest': 0
                        },
                        'kicking': {
                            'fgAtt': 0,
                            'fgs': 0,
                            'fgPerc': 0,
                            'fgYards': 0,
                            'fgAvg': 0,
                            'fg45+': 0,
                            'fgUnder20att': 0,
                            'fgUnder20': 0,
                            'fgUnder20perc': 0,
                            'fg20to40att': 0,
                            'fg20to40': 0,
                            'fg20to40perc': 0,
                            'fg40to50att': 0,
                            'fg40to50': 0,
                            'fg40to50perc': 0,
                            'fgOver50att': 0,
                            'fgOver50': 0,
                            'fgOver50perc': 0,
                            'longest': 0
                        },
                        'defense': {
                            'sacks': 0,
                            'ints': 0,
                            'tackles': 0,
                            'tfl': 0,
                            'forcedFumbles': 0,
                            'passBreakups': 0,
                        }
                    }

qbStatsDict = {
                'passAtt': 0, 
                'passComp': 0, 
                'passCompPerc': 0, 
                'passMiss': 0,
                'tds': 0, 
                'ints': 0, 
                'passYards': 0, 
                'ypc': 0, 
                'totalYards': 0,
                'pass20+': 0,
                'longest': 0
            }
rbStatsDict = {
                'carries': 0, 
                'receptions': 0, 
                'passTargets': 0, 
                'rcvPerc': 0, 
                'rcvYards': 0, 
                'runYards': 0, 
                'ypc': 0, 
                'runTds': 0, 
                'rcvTds': 0, 
                'fumblesLost': 0, 
                'ypr': 0, 
                'totalYards': 0,
                'run20+': 0,
                'pass20+': 0,
                'longest': 0
            }
wrStatsDict = {
                'receptions': 0, 
                'passTargets': 0, 
                'drops': 0,
                'rcvPerc': 0, 
                'rcvYards': 0, 
                'ypr': 0, 
                'rcvTds': 0, 
                'totalYards': 0,
                'pass20+': 0,
                'longest': 0
            }
kStatsDict = {
                'fgAtt': 0, 
                'fgs': 0, 
                'fgPerc': 0,
                'fgUnder20att': 0,
                'fgUnder20': 0,
                'fgUnder20perc': 0,
                'fg20to40att': 0,
                'fg20to40': 0,
                'fg20to40perc': 0,
                'fg40to50att': 0,
                'fg40to50': 0,
                'fg40to50perc': 0,
                'fgOver50att': 0,
                'fgOver50': 0,
                'fgOver50perc': 0,
                'longest': 0
            }

class Player:
    def __init__(self, seed = None):
        self.position = None
        self.name = ''
        self.id = 0
        self.currentNumber = 0
        self.preferredNumber = randint(0,99)
        self.team: Team = None
        self.previousTeam = None
        self.attributes = PlayerAttributes()
        self.gameAttributes: PlayerAttributes = None
        self.playerTier = PlayerTier.TierC  # Default tier, updated by sortPlayersByPosition
        self.seasonsPlayed = 0
        self.gamesPlayed = 0
        self.term = 0
        self.termRemaining = 0
        self.capHit = 0
        # willRetire: set during the regular season when a retirement-eligible
        # player is determined to be calling it after this season. Surfaces
        # in the UI well before the offseason so users can plan replacements.
        # Players retire ONLY at the end of their contract — flag is set only
        # for those whose contract expires this offseason.
        self.willRetire = False
        self.seasonPerformanceRating = 0
        self.playerRating = 0
        self.offensiveRating = 0
        self.defensiveRating = 0
        self.defensivePosition = None
        self.freeAgentYears = 0
        self.serviceTime = PlayerServiceTime.Rookie
        self.leagueChampionships = []
        self.mvpAwards = []
        self.allProSeasons = []

        # Use optimized stats instead of deep copying
        self.gameStats = get_optimized_stats()
        self.seasonStats = get_optimized_stats()
        self.careerStats = get_optimized_stats()
        
        # Keep legacy dict access for backwards compatibility
        self.gameStatsDict = self.gameStats.to_legacy_dict()
        self.seasonStatsDict = self.seasonStats.to_legacy_dict()
        self.careerStatsDict = self.careerStats.to_legacy_dict()
        self.seasonStatsArchive = []

        # Initialize StatTracker with the stats dictionaries
        self.stat_tracker = StatTracker(
            self.gameStatsDict, 
            self.seasonStatsDict, 
            self.careerStatsDict
        )
    
    def sync_stats_dicts(self):
        """Sync FROM updated legacy dictionaries TO optimized stats objects"""
        # Update optimized stats from the legacy dicts that have been updated by stat_tracker
        self.gameStats = OptimizedPlayerStats.from_legacy_dict(self.gameStatsDict)
        self.seasonStats = OptimizedPlayerStats.from_legacy_dict(self.seasonStatsDict)
        self.careerStats = OptimizedPlayerStats.from_legacy_dict(self.careerStatsDict)
    
    def reset_game_stats(self):
        """Reset game stats for a new game using optimized stats"""
        self.gameStats.reset_for_new_game()
        # Sync the reset stats TO the legacy dict (not FROM it)
        self.gameStatsDict = self.gameStats.to_legacy_dict()
        # Update stat_tracker reference to the new dict
        self.stat_tracker.game_stats_dict = self.gameStatsDict

    def postgameChanges(self):
        self.attributes.confidenceModifier = round((self.attributes.confidenceModifier + self.gameAttributes.confidenceModifier)/2, 3)
        self.attributes.determinationModifier = round((self.attributes.determinationModifier + self.gameAttributes.determinationModifier)/2, 3)
        self.gamesPlayed += 1
        # Sync stat_tracker data to optimized objects, then update gp in both
        self.sync_stats_dicts()
        self.seasonStats.gp = self.gamesPlayed
        self.seasonStatsDict['gp'] = self.gamesPlayed
        self.careerStats.gp += 1
        self.careerStatsDict['gp'] = self.careerStatsDict.get('gp', 0) + 1
        if isinstance(self.team,Team):
            # Per-game streak adjustments. Refactored from an attitude-only
            # cascade to use the same complacency / resolve composites the
            # weekly form-shift mechanic relies on, so streak reactions are
            # consistent with the season-arc trend they feed into.
            #
            # selfBelief governs the magnitude of CONFIDENCE swings only —
            # determination is the drive-to-win axis, not a belief axis, so
            # it's not gated. selfBelief 80 = neutral (no scaling); 100 =
            # half-magnitude swings (steady); 60 = 1.4x swings (volatile).
            sb = getattr(self.attributes, 'selfBelief', 80) or 80
            confStability = max(0.4, min(1.6, 1.0 - (sb - 80) / 50))

            if self.team.winningStreak:
                # Winning streak: confidence boost, but vulnerable players
                # get less of one (their hot-team coasting tendency caps
                # the upside). Bulletproof players get the full +0..25.
                vuln = self.attributes.complacencyVulnerability()
                boostMax = max(8, round(25 * (1 - 0.6 * vuln) * confStability))
                self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (batched_randint(0, boostMax)/100), 3)
            elif self.team.seasonTeamStats['streak'] < -2:
                # Losing streak: response shaped by adversityResolve.
                # High resolve (>=0.7): determination goes UP (counter-puncher).
                # Low resolve: confidence/determination drop, scaling with
                # how short of resolve they are (no resolve → biggest drop).
                # Confidence drop scaled by selfBelief; determination drop is not.
                resolve = self.attributes.adversityResolve()
                if resolve >= 0.7:
                    self.attributes.determinationModifier = round(self.attributes.determinationModifier + (batched_randint(0, 10)/100), 3)
                else:
                    shortfall = 1.0 - resolve  # 0=full resolve, 1=none
                    confPenaltyMax = max(0, round(20 * shortfall * confStability))
                    detPenaltyMax = max(0, round(20 * shortfall))
                    if confPenaltyMax > 0:
                        self.attributes.confidenceModifier = round(self.attributes.confidenceModifier + (batched_randint(-confPenaltyMax, 0)/100), 3)
                    if detPenaltyMax > 0:
                        self.attributes.determinationModifier = round(self.attributes.determinationModifier + (batched_randint(-detPenaltyMax, 0)/100), 3)

            if self.attributes.confidenceModifier > 5:
                self.attributes.confidenceModifier = 5
            if self.attributes.determinationModifier > 5:
                self.attributes.determinationModifier = 5

            if self.attributes.confidenceModifier < -5:
                self.attributes.confidenceModifier = -5
            if self.attributes.determinationModifier < -5:
                self.attributes.determinationModifier = -5

        self.updateRating()

    def updateInGameRating(self):
        pass

    def updateRating(self):
        pass

    def updateInGameDetermination(self, value):
        self.gameAttributes.determinationModifier = round(self.gameAttributes.determinationModifier + value, 3)
        self.updateInGameRating()

    def updateInGameConfidence(self, value):
        self.gameAttributes.confidenceModifier = round(self.gameAttributes.confidenceModifier + value, 3)
        self.updateInGameRating()

    def offseasonTraining(self, coachDevRating: int = 50, fundingDevBonus: int = 0):
        pass


    def addPassTd(self, yards, isRegularSeason):
        self.stat_tracker.add_pass_td(yards, isRegularSeason)

    def addCompletion(self, isRegularSeason):
        self.stat_tracker.add_completion(isRegularSeason)

    def addInterception(self, isRegularSeason):
        self.stat_tracker.add_interception(isRegularSeason)

    def addPassAttempt(self, isRegularSeason):
        self.stat_tracker.add_pass_attempt(isRegularSeason)

    def addPassYards(self, yards, isRegularSeason):
        self.stat_tracker.add_pass_yards(yards, isRegularSeason)

    def addMissedPass(self, isRegularSeason):
        self.stat_tracker.add_missed_pass(isRegularSeason)

    def addRcvPassTarget(self, isRegularSeason):
        self.stat_tracker.add_rcv_pass_target(isRegularSeason)

    def addReception(self, isRegularSeason):
        self.stat_tracker.add_reception(isRegularSeason)

    def addPassDrop(self, isRegularSeason):
        self.stat_tracker.add_pass_drop(isRegularSeason)

    def addReceiveYards(self, yards, isRegularSeason):
        self.stat_tracker.add_receive_yards(yards, isRegularSeason)

    def addYAC(self, yac, isRegularSeason):
        self.stat_tracker.add_yac(yac, isRegularSeason)

    def addReceiveTd(self, yards, isRegularSeason):
        self.stat_tracker.add_receive_td(yards, isRegularSeason)

    def addCarry(self, isRegularSeason):
        self.stat_tracker.add_carry(isRegularSeason)

    def addRushTd(self, yards, isRegularSeason):
        self.stat_tracker.add_rush_td(yards, isRegularSeason)

    def addRushYards(self, yards, isRegularSeason):
        self.stat_tracker.add_rush_yards(yards, isRegularSeason)

    def addFumble(self, isRegularSeason):
        self.stat_tracker.add_fumble(isRegularSeason)

    def addFgAttempt(self, isRegularSeason):
        self.stat_tracker.add_fg_attempt(isRegularSeason)

    def addFg(self, yards, isRegularSeason):
        self.stat_tracker.add_fg(yards, isRegularSeason)
        
        # Handle additional stats not covered by base StatTracker
        if yards >= 40:
            self.gameStatsDict['kicking']['fg40+'] = self.gameStatsDict['kicking'].get('fg40+', 0) + 1
        if yards >= 45:
            self.gameStatsDict['kicking']['fg45+'] += 1
            if isRegularSeason:
                # Use .get() with default for safety when loading old player data
                self.seasonStatsDict['kicking']['fg45+'] = self.seasonStatsDict['kicking'].get('fg45+', 0) + 1
                self.careerStatsDict['kicking']['fg45+'] = self.careerStatsDict['kicking'].get('fg45+', 0) + 1
                
        # Handle distance-specific attempt + make tracking. Both buckets get
        # incremented on a successful kick so we can compute per-range FG%
        # (under 20 / 20-40 / 40-50 / 50+) at save/read time.
        if isRegularSeason:
            if yards < 20:
                attKey, mkKey = 'fgUnder20att', 'fgUnder20'
            elif yards < 40:
                attKey, mkKey = 'fg20to40att', 'fg20to40'
            elif yards < 50:
                attKey, mkKey = 'fg40to50att', 'fg40to50'
            else:
                attKey, mkKey = 'fgOver50att', 'fgOver50'
            self.seasonStatsDict['kicking'][attKey] = self.seasonStatsDict['kicking'].get(attKey, 0) + 1
            self.careerStatsDict['kicking'][attKey] = self.careerStatsDict['kicking'].get(attKey, 0) + 1
            self.seasonStatsDict['kicking'][mkKey] = self.seasonStatsDict['kicking'].get(mkKey, 0) + 1
            self.careerStatsDict['kicking'][mkKey] = self.careerStatsDict['kicking'].get(mkKey, 0) + 1


    def addMissedFg(self, yards, isRegularSeason):
        if yards >= 40 and yards < 50:
            self.stat_tracker.add_fantasy_points(-1)
        elif yards < 40:
            self.stat_tracker.add_fantasy_points(-2)

        if isRegularSeason:
            if yards < 50 and yards > 39:
                self.seasonStatsDict['kicking']['fg40to50att'] = self.seasonStatsDict['kicking'].get('fg40to50att', 0) + 1
                self.careerStatsDict['kicking']['fg40to50att'] = self.careerStatsDict['kicking'].get('fg40to50att', 0) + 1
            elif yards < 40 and yards >= 20:
                self.seasonStatsDict['kicking']['fg20to40att'] = self.seasonStatsDict['kicking'].get('fg20to40att', 0) + 1
                self.careerStatsDict['kicking']['fg20to40att'] = self.careerStatsDict['kicking'].get('fg20to40att', 0) + 1
            elif yards < 20:
                self.seasonStatsDict['kicking']['fgUnder20att'] = self.seasonStatsDict['kicking'].get('fgUnder20att', 0) + 1
                self.careerStatsDict['kicking']['fgUnder20att'] = self.careerStatsDict['kicking'].get('fgUnder20att', 0) + 1
            else:
                self.seasonStatsDict['kicking']['fgOver50att'] = self.seasonStatsDict['kicking'].get('fgOver50att', 0) + 1
                self.careerStatsDict['kicking']['fgOver50att'] = self.careerStatsDict['kicking'].get('fgOver50att', 0) + 1


    def addExtraPoint(self):
        self.stat_tracker.add_fantasy_points(1)

    def addMissedExtraPoint(self):
        self.stat_tracker.add_fantasy_points(-3)


# Mood tier names (1-5). Used by getMood() to return a coarse-grained tier
# label alongside the personality-flavored mood name.
MOOD_TIER_NAMES = {5: 'electric', 4: 'confident', 3: 'steady', 2: 'frustrated', 1: 'miserable'}


class PlayerAttributes:
    def __init__(self):
        self.overallRating = 0

        #physical attributes
        self.speed = 0
        self.hands = 0
        self.reach = 0
        self.agility = 0
        self.power = 0
        self.armStrength = 0
        self.accuracy = 0
        self.legStrength = 0
        self.skillRating = 0

        self.potentialSpeed = 0
        self.potentialHands = 0
        self.potentialReach = 0
        self.potentialAgility = 0
        self.potentialPower = 0
        self.potentialArmStrength = 0
        self.potentialAccuracy = 0
        self.potentialLegStrength = 0
        self.potentialSkillRating = 0

        #physical skills
        self.routeRunning = 0
        self.vision = 0
        self.blocking = 0
        self.blockingModifier = 0
        
        #dynamic personality attributes
        self.discipline = 0
        self.attitude = 0

        #static personality intangibles
        self.focus = 0
        self.instinct = 0
        self.creativity = 0
        self.resilience = 0
        # selfBelief (60-100): how stable this player's confidence is.
        # High = quiet, steady belief — small swings from results.
        # Low = volatile — confidence soars and crashes with recent results.
        self.selfBelief = 80
        # clutchFactor: deprecated. Was meant to amplify pressure-induced
        # variance but never got populated (always 0). Kept on the class so
        # DB sync code that reads/writes the existing clutch_factor column
        # doesn't crash; not used by any game-sim logic.
        self.clutchFactor = 0
        self.pressureHandling = randint(-10, 10)  # -10 (chokes) to +10 (thrives under pressure)

        self.longevity = randint(4,10)
        self.playMakingAbility = 0
        self.xFactor = 0

        #modifiers
        self.confidenceModifier = randint(-2, 2)
        self.determinationModifier = randint(-2, 2)
        self.luckModifier = randint(-5, 5)

        # Defensive talent: persistent modifier that shifts defensive rating
        # Creates real spread between offensive and defensive ability
        # Range: -15 to +10 (skewed negative — most players are better on offense)
        self.defensiveTalent = randint(-15, 10)

        # Fatigue (0.0 = fresh, accumulates over the season)
        self.fatigue = 0.0

        # Personality (single layer + mood, plus optional quirk)
        # Personality is one of 28 personalities (9 base vibes + 19 variants).
        # Quirk is optional sideline-flavor trait. Mood is 1-5, recomputed
        # from confidence + determination, surfaced on UI as a personality-
        # flavored label via PersonalityReactionEngine.getMoodName().
        self.personality = None
        self.quirk = None
        self.mood = 3  # neutral start

        # Flavor (hometown, favorite, motto) — rolled once at creation,
        # never changes. Pure character flavor for the player detail page.
        self.hometown = None
        self.favorite_category = None
        self.favorite_item = None
        self.motto = None

    # ── Mental composites for season-form trends ──
    # Two distinct composites: one captures how vulnerable a player is to
    # coasting / cracking under expectations when their team is winning;
    # the other captures how hard they fight back when the team is losing.
    # Both used by the weekly form-shift mechanic in seasonManager and by
    # the per-game streak adjustment in _updatePostGameModifiers.

    def complacencyVulnerability(self) -> float:
        """0 = bulletproof, 1 = fully vulnerable. Hot-team direction.
          discipline       40%   professional habits, doesn't slack
          pressureHandling 25%   season-level expectations weight (-10 to +10
                                 normalized to 60-100 scale)
          focus            20%   mental sharpness vs going through the motions
          attitude         15%   ego resistance / leader-vs-toxic axis
        Composite weighted to a 60–100 scale; 80+ → 0, ≤60 → 1.
        """
        ph = getattr(self, 'pressureHandling', 0) or 0
        ph_norm = 80 + ph * 2  # -10→60, 0→80, +10→100
        weighted = (
            (getattr(self, 'discipline', 80) or 80) * 0.40
            + ph_norm * 0.25
            + (getattr(self, 'focus', 80) or 80) * 0.20
            + (getattr(self, 'attitude', 80) or 80) * 0.15
        )
        return max(0.0, min(1.0, (80 - weighted) / 20))

    def adversityResolve(self) -> float:
        """0 = checked out, 1 = full Cinderella. Cold-team direction.
          resilience  40%   bouncing back from setbacks
          attitude    25%   morale floor — the leader-vs-toxic axis
          discipline  20%   keeps doing the right things
          creativity  15%   finds new ways to win
        Composite weighted to a 60–100 scale; ≤70 → 0, 100 → 1.
        """
        weighted = (
            (getattr(self, 'resilience', 80) or 80) * 0.40
            + (getattr(self, 'attitude', 80) or 80) * 0.25
            + (getattr(self, 'discipline', 80) or 80) * 0.20
            + (getattr(self, 'creativity', 80) or 80) * 0.15
        )
        return max(0.0, min(1.0, (weighted - 70) / 30))

    def computeMoodTier(self):
        """Compute the 1-5 mood tier as a catchall mental-state signal.

        Blends three inputs:
          - confidenceModifier (volatile, -5..+5) — current week-to-week vibe
          - determinationModifier (volatile, -5..+5) — drive level
          - attitude (slow, 30-100) — locker-room identity (toxic ↔ leader)

        Attitude shifts the floor/ceiling so a toxic player can never feel
        electric for long and a leader has a higher resting state. This is
        what lets one pill represent the player's full mental state instead
        of needing separate Mood + Attitude readouts.
        """
        attitude = getattr(self, 'attitude', 80) or 80
        # 30 → −10 (deep toxic drag), 80 → 0 (neutral), 100 → +4 (leader lift).
        # Asymmetric: toxic players pull mood down harder than leaders push it up,
        # which matches how locker-room dysfunction tends to swamp performance.
        attBias = (attitude - 80) / 5
        combined = self.confidenceModifier + self.determinationModifier + attBias
        if combined >= 6:
            return 5
        elif combined >= 3:
            return 4
        elif combined >= -2:
            return 3
        elif combined >= -5:
            return 2
        else:
            return 1

    def getMood(self):
        """Return (mood label, tier name) using personality + computed tier."""
        tier = self.computeMoodTier()
        tierName = MOOD_TIER_NAMES[tier]
        # Mood label is personality-flavored; engine looks it up.
        try:
            from managers.personalityReactionEngine import getEngine
            label = getEngine().getMoodName(self.personality, tier) if self.personality else None
        except Exception:
            label = None
        return (label or 'Measured', tierName)

    def calculateIntangibles(self):
        self.playMakingAbility = round((self.instinct+self.creativity)/2)
        self.xFactor = round((((self.focus*1.8) + (self.discipline*1.2))/3) + ((self.confidenceModifier*2.2)+(self.determinationModifier*1.2)/3) + (self.luckModifier))
        if self.xFactor > 100:
            self.xFactor = 100

    def calculateSkills(self):
        self.routeRunning = round(((self.speed*1.2) + (self.agility*1) + (self.xFactor*.8) + (self.playMakingAbility))/4)
        self.vision = round((self.discipline + self.instinct + self.focus)/3)
        self.blocking = round(((self.power*1.2) + (self.xFactor*.8))/2)
        self.blockingModifier = math.floor((self.blocking - 60)/6)
    
    def getPressureModifier(self, gamePressure: int) -> float:
        """Calculate performance modifier based on game pressure and player's pressure handling.
        
        Three possible outcomes: overperform, no effect, or underperform.
        Higher pressureHandling = more likely to overperform AND more likely to have no effect than underperform.
        Lower pressureHandling = more likely to underperform AND more likely to have no effect than overperform.
        
        Args:
            gamePressure: Current game pressure (0-100)
            
        Returns:
            Modifier that affects player performance (positive, zero, or negative)
        """
        # Normalize game pressure to 0-1 scale
        normalizedPressure = min(100, max(0, gamePressure)) / 100.0
        
        # In low pressure situations, minimal impact
        if normalizedPressure < 0.3:
            return 0
        
        # Calculate the magnitude of potential variance based on pressure and pressureHandling
        maxVariance = abs(self.pressureHandling) * normalizedPressure

        # Roll for outcome (1-100)
        roll = batched_randint(1, 100)

        # Map pressureHandling to probability zones
        # pressureHandling +10: overperform 60%, no effect 30%, underperform 10%
        # pressureHandling 0: overperform 15%, no effect 70%, underperform 15%
        # pressureHandling -10: overperform 10%, no effect 30%, underperform 60%

        # Calculate probability zones based on pressureHandling
        if self.pressureHandling >= 0:
            # Positive pressure handling: more overperform, less underperform
            overPerformChance = 15 + (self.pressureHandling * 4.5)  # 15 to 60
            noEffectChance = 70 - (self.pressureHandling * 4)       # 70 to 30
            # underperform is the remainder (15 to 10)
        else:
            # Negative pressure handling: less overperform, more underperform
            overPerformChance = 15 + (self.pressureHandling * 0.5)  # 15 to 10
            noEffectChance = 70 + (self.pressureHandling * 4)       # 70 to 30
            # underperform is the remainder (15 to 60)

        # High pressure compresses the no-effect zone — players are more
        # likely to either rise or crumble in big moments
        if normalizedPressure >= 0.7:
            compressionFactor = (normalizedPressure - 0.7) / 0.3  # 0→1 as pressure goes 70→100
            noEffectReduction = noEffectChance * 0.5 * compressionFactor
            noEffectChance -= noEffectReduction
            overPerformChance += noEffectReduction * 0.5
            # underperform (remainder) gets the other half
        
        if roll <= overPerformChance:
            # Overperform
            return batched_random() * maxVariance
        elif roll <= overPerformChance + noEffectChance:
            # No effect
            return 0
        else:
            # Underperform — use a variance floor so even neutral players can
            # produce choke-level modifiers under high pressure.  The floor only
            # kicks in when pressure is significant (≥0.5 normalised).
            chokeVariance = maxVariance
            if normalizedPressure >= 0.5:
                chokeVariance = max(2.0, maxVariance)
            return -(batched_random() * chokeVariance)


    def getPlayerAttributes(self, position, physicalSeed = None, mentalSeed = None):
        # Generate seeds if not provided. Switched from uniform randint
        # to a Gaussian centered at 78 so the seed distribution itself
        # is bell-shaped — players with no seed passed in (legacy paths,
        # one-off creations) now match the league-balanced curve.
        if physicalSeed is None:
            physicalSeed = int(np.clip(np.random.normal(78, 7), 60, 100))
        if mentalSeed is None:
            mentalSeed = int(np.clip(np.random.normal(78, 7), 60, 100))

        # Physical skills: tight variance around the seed. stdDev was 5
        # → 3, narrowing the spread of attribute values around the
        # player's overall talent level. Reduces the per-player gap
        # between, say, a player's best and worst attribute.
        stdDev = 3
        numSkills = 3
        skillValList = np.random.normal(physicalSeed, stdDev, numSkills)
        skillValList = np.clip(skillValList, 60, 100)
        skillValList: list = skillValList.tolist()


        if position is Position.QB:
            self.armStrength = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.accuracy = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
        elif position is Position.RB:
            self.power = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.speed = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.hands = np.random.normal(physicalSeed, stdDev)
            self.hands = int(np.clip(self.hands, 60, 100))
            self.reach = np.random.normal(physicalSeed, stdDev)
            self.reach = int(np.clip(self.reach, 60, 100))
        elif position is Position.WR:
            self.hands = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.speed = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.reach = np.random.normal(physicalSeed, stdDev)
            self.reach = int(np.clip(self.reach, 60, 100))
        elif position is Position.TE:
            self.hands = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.power = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.reach = np.random.normal(physicalSeed, stdDev)
            self.reach = int(np.clip(self.reach, 60, 100))
        elif position is Position.K:
            self.legStrength = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.accuracy = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))
        else:
            self.power = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.speed = int(skillValList.pop(randint(0, len(skillValList)) - 1))
            self.agility = int(skillValList.pop(randint(0, len(skillValList)) - 1))

        # Intangibles: split into two pools.
        #
        # Pool A — game-formula attrs (60-100, stdDev 7): focus, instinct,
        # creativity, discipline. These are baked into linear weights across
        # ~14 game-sim formulas (xFactor, vision, fumble resist, route
        # variance, drop chance, defensive coverage, etc). Keeping them in
        # the original "pro minimum" range avoids cascading balance issues —
        # a 30-discipline player would fumble dramatically more often, etc.
        #
        # Pool B — locker-room/state attrs (30-100, mentalSeed offset down
        # to 50, stdDev 12): attitude, resilience, selfBelief. These feed
        # composites and modulators (contagion, fatigue, confidence
        # volatility) — wider range produces real toxic teammates, fragile
        # players, and confidence-volatile players without breaking the
        # game-formula balance.
        # gameStdDev tightened from 7 → 5 to match the narrower physical
        # spread above. Keeps game-formula attrs (focus, instinct,
        # creativity, discipline) closer to the player's seed.
        gameStdDev = 5
        gamePool = np.random.normal(mentalSeed, gameStdDev, 4)
        gamePool = np.clip(gamePool, 60, 100).tolist()

        # Locker-room pool centers slightly lower with bigger variance so the
        # tails actually get used. mentalSeed-7 keeps most players near-pro
        # (median ~73) while letting a meaningful minority fall into real
        # trouble (10-15% below 60, 3-5% below 50). Clipped to 30 for the
        # extreme tail — actual head cases exist but stay rare.
        lrCenter = max(55, mentalSeed - 7)
        lrStdDev = 10
        lrPool = np.random.normal(lrCenter, lrStdDev, 3)
        lrPool = np.clip(lrPool, 30, 100).tolist()

        self.instinct    = int(gamePool.pop(randint(0, len(gamePool)) - 1))
        self.focus       = int(gamePool.pop(randint(0, len(gamePool)) - 1))
        self.creativity  = int(gamePool.pop(randint(0, len(gamePool)) - 1))
        self.discipline  = int(gamePool.pop(randint(0, len(gamePool)) - 1))
        self.attitude    = int(lrPool.pop(randint(0, len(lrPool)) - 1))
        self.resilience  = int(lrPool.pop(randint(0, len(lrPool)) - 1))
        # selfBelief: governs how volatile this player's confidence is in
        # response to performance and team form. High = stable; low = volatile.
        self.selfBelief  = int(lrPool.pop(randint(0, len(lrPool)) - 1))

        # Generate any missing core physical attributes (needed for defensive ratings)
        # Core 5: speed, power, agility, hands, reach — every player needs these
        coreAttrs = {'speed': self.speed, 'power': self.power, 'agility': self.agility,
                     'hands': self.hands, 'reach': self.reach}
        for attr, val in coreAttrs.items():
            if val == 0:
                generated = int(np.clip(np.random.normal(physicalSeed, stdDev), 60, 100))
                setattr(self, attr, generated)

        # Personality (personality + quirk + mood) is assigned by personalityManager
        # via playerManager after this method returns, since OVR-tiered variant
        # gating depends on the final overall rating.

    # ── Defensive attribute calculations ─────────────────────────────────
    # Derived from the same base athletics using different formulas per
    # defensive position, shifted by the player's defensiveTalent modifier
    # to create real spread between offensive and defensive ability.

    def calculateDefensiveRating(self, position):
        """Calculate defensive skill rating based on offensive position → defensive position."""
        defPos = DEFENSIVE_POSITION_MAP.get(position)
        if defPos is None:
            return 0  # Kickers don't play defense

        if defPos == DefensivePosition.CB:
            base = self._calculateCBRating()
        elif defPos == DefensivePosition.S:
            base = self._calculateSafetyRating()
        elif defPos == DefensivePosition.LB:
            base = self._calculateLBRating()
        elif defPos == DefensivePosition.DE:
            base = self._calculateDERating()
        else:
            return 0

        talent = getattr(self, 'defensiveTalent', 0)
        return max(60, min(100, base + talent))

    def _calculateCBRating(self):
        """Cornerback: coverage + tackling."""
        coverage = round(0.4 * self.speed + 0.3 * self.agility + 0.2 * self.instinct + 0.1 * self.discipline)
        tackling = round(0.5 * self.power + 0.3 * self.speed + 0.2 * self.discipline)
        return round((coverage * 1.5 + tackling * 0.5) / 2)

    def _calculateSafetyRating(self):
        """Safety: coverage + play reading + tackling."""
        coverage = round(0.3 * self.vision + 0.3 * self.instinct + 0.2 * self.agility + 0.2 * self.focus)
        playReading = round(0.4 * self.vision + 0.3 * self.instinct + 0.3 * self.focus)
        tackling = round(0.4 * self.power + 0.3 * self.discipline + 0.3 * self.agility)
        return round((coverage + playReading + tackling) / 3)

    def _calculateLBRating(self):
        """Linebacker: tackling + run defense + blitzing."""
        tackling = round(0.4 * self.power + 0.3 * self.speed + 0.2 * self.agility + 0.1 * self.discipline)
        runDefense = round(0.4 * self.power + 0.3 * self.instinct + 0.2 * self.discipline + 0.1 * self.speed)
        blitzing = round(0.4 * self.speed + 0.3 * self.power + 0.2 * self.agility + 0.1 * self.instinct)
        return round((tackling + runDefense + blitzing) / 3)

    def _calculateDERating(self):
        """Defensive End: pass rush + run defense."""
        passRush = round(0.4 * self.power + 0.3 * self.speed + 0.2 * self.agility + 0.1 * self.instinct)
        runDefense = round(0.5 * self.power + 0.3 * self.discipline + 0.2 * self.instinct)
        return round((passRush * 1.3 + runDefense * 0.7) / 2)

    def getDefensiveAttributes(self, position):
        """Return individual defensive attributes for the player's defensive position.
        Each attribute is shifted by the player's defensiveTalent modifier."""
        defPos = DEFENSIVE_POSITION_MAP.get(position)
        if defPos is None:
            return {}

        talent = getattr(self, 'defensiveTalent', 0)
        clamp = lambda v: max(60, min(100, v + talent))

        if defPos == DefensivePosition.CB:
            return {
                'coverage': clamp(round(0.4 * self.speed + 0.3 * self.agility + 0.2 * self.instinct + 0.1 * self.discipline)),
                'tackling': clamp(round(0.5 * self.power + 0.3 * self.speed + 0.2 * self.discipline)),
            }
        elif defPos == DefensivePosition.S:
            return {
                'coverage': clamp(round(0.3 * self.vision + 0.3 * self.instinct + 0.2 * self.agility + 0.2 * self.focus)),
                'playReading': clamp(round(0.4 * self.vision + 0.3 * self.instinct + 0.3 * self.focus)),
                'tackling': clamp(round(0.4 * self.power + 0.3 * self.discipline + 0.3 * self.agility)),
            }
        elif defPos == DefensivePosition.LB:
            return {
                'tackling': clamp(round(0.4 * self.power + 0.3 * self.speed + 0.2 * self.agility + 0.1 * self.discipline)),
                'runDefense': clamp(round(0.4 * self.power + 0.3 * self.instinct + 0.2 * self.discipline + 0.1 * self.speed)),
                'blitzing': clamp(round(0.4 * self.speed + 0.3 * self.power + 0.2 * self.agility + 0.1 * self.instinct)),
            }
        elif defPos == DefensivePosition.DE:
            return {
                'passRush': clamp(round(0.4 * self.power + 0.3 * self.speed + 0.2 * self.agility + 0.1 * self.instinct)),
                'runDefense': clamp(round(0.5 * self.power + 0.3 * self.discipline + 0.2 * self.instinct)),
            }
        return {}

    def changeStat(self, value):
        if value >= 95:
            value += randint(-10, 0)
        elif value <= 75:
            value += randint(0, 10)
        else:
            value += randint(5, 5)


class PlayerQB(Player, CachedRatingMixin):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.QB
        self.defensivePosition = DefensivePosition.S
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()

        self.attributes.potentialArmStrength = self.attributes.armStrength + randint(0,30)
        self.attributes.potentialAccuracy = self.attributes.accuracy + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialArmStrength > 100:
            self.attributes.potentialArmStrength = 100
        if self.attributes.potentialAccuracy > 100:
            self.attributes.potentialAccuracy = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialArmStrength*1.2) + (self.attributes.potentialAccuracy*1.3) + (self.attributes.potentialAgility*.5))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.armStrength*1.2) + (self.gameAttributes.accuracy*1.3) + (self.gameAttributes.agility*.5))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*3) + (self.gameAttributes.playMakingAbility) + (self.gameAttributes.xFactor))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def _calculate_skill_rating(self) -> float:
        """Calculate QB-specific skill rating"""
        return round(((self.attributes.armStrength*1.2) + (self.attributes.accuracy*1.3) + (self.attributes.agility*.5))/3)

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()

        # Use cached calculations
        self.attributes.skillRating = self.get_cached_skill_rating()
        self.attributes.overallRating = self.get_cached_overall_rating()
        self.offensiveRating = self.attributes.overallRating
        self.defensiveRating = self.attributes.calculateDefensiveRating(self.position)
        self.playerRating = round((self.offensiveRating + self.defensiveRating) / 2)

    def updateInGameRating(self):
        # Invalidate cache when game attributes change
        self.invalidate_rating_cache()
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()

        # For game ratings, we still calculate directly since they change frequently
        self.gameAttributes.skillRating = round(((self.gameAttributes.armStrength*1.2) + (self.gameAttributes.accuracy*1.3) + (self.gameAttributes.agility*.5))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*3) + (self.gameAttributes.playMakingAbility) + (self.gameAttributes.xFactor))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100


    def offseasonTraining(self, coachDevRating: int = 50, fundingDevBonus: int = 0):
        PlayerDevelopment.apply_offseason_training(self, "QB", coachDevRating=coachDevRating, fundingDevBonus=fundingDevBonus)
        self.updateRating()

class PlayerRB(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.RB
        self.defensivePosition = DefensivePosition.LB
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()

        self.attributes.potentialSpeed = self.attributes.speed + randint(0,30)
        self.attributes.potentialPower = self.attributes.power + randint(0,30)
        self.attributes.potentialReach = self.attributes.reach + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialSpeed > 100:
            self.attributes.potentialSpeed = 100
        if self.attributes.potentialPower > 100:
            self.attributes.potentialPower = 100
        if self.attributes.potentialReach > 100:
            self.attributes.potentialReach = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialPower*1.2) + (self.attributes.potentialSpeed*1.3) + (self.attributes.potentialAgility*.5))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.power*1.3) + (self.gameAttributes.agility*1))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*3) + (self.gameAttributes.playMakingAbility) + (self.gameAttributes.xFactor))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.power*1.3) + (self.attributes.agility*1))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*3) + (self.attributes.playMakingAbility) + (self.attributes.xFactor))/5)
        self.offensiveRating = self.attributes.overallRating
        self.defensiveRating = self.attributes.calculateDefensiveRating(self.position)
        self.playerRating = round((self.offensiveRating + self.defensiveRating) / 2)


    def offseasonTraining(self, coachDevRating: int = 50, fundingDevBonus: int = 0):
        PlayerDevelopment.apply_offseason_training(self, "RB", coachDevRating=coachDevRating, fundingDevBonus=fundingDevBonus)
        self.updateRating()

class PlayerWR(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.WR
        self.defensivePosition = DefensivePosition.CB
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()

        self.attributes.potentialSpeed = self.attributes.speed + randint(0,30)
        self.attributes.potentialHands = self.attributes.hands + randint(0,30)
        self.attributes.potentialReach = self.attributes.reach + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialSpeed > 100:
            self.attributes.potentialSpeed = 100
        if self.attributes.potentialHands > 100:
            self.attributes.potentialHands = 100
        if self.attributes.potentialReach > 100:
            self.attributes.potentialReach = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialHands*1.2) + (self.attributes.potentialSpeed*1.3) + (self.attributes.potentialAgility*.5))/3)

    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.speed*.7) + (self.gameAttributes.hands*1.5) + (self.gameAttributes.agility*.8))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*3) + (self.gameAttributes.playMakingAbility) + (self.gameAttributes.xFactor))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.speed*.7) + (self.attributes.hands*1.5) + (self.attributes.agility*.8))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*3) + (self.attributes.playMakingAbility) + (self.attributes.xFactor))/5)
        self.offensiveRating = self.attributes.overallRating
        self.defensiveRating = self.attributes.calculateDefensiveRating(self.position)
        self.playerRating = round((self.offensiveRating + self.defensiveRating) / 2)


    def offseasonTraining(self, coachDevRating: int = 50, fundingDevBonus: int = 0):
        PlayerDevelopment.apply_offseason_training(self, "WR", coachDevRating=coachDevRating, fundingDevBonus=fundingDevBonus)
        self.updateRating()

class PlayerTE(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.TE
        self.defensivePosition = DefensivePosition.DE
        self.isOpen = False
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()

        self.attributes.potentialHands = self.attributes.hands + randint(0,30)
        self.attributes.potentialReach = self.attributes.reach + randint(0,30)
        self.attributes.potentialPower = self.attributes.power + randint(0,30)
        self.attributes.potentialAgility = self.attributes.agility + randint(0,30)
        if self.attributes.potentialHands > 100:
            self.attributes.potentialHands = 100
        if self.attributes.potentialReach > 100:
            self.attributes.potentialReach = 100
        if self.attributes.potentialPower > 100:
            self.attributes.potentialPower = 100
        if self.attributes.potentialAgility > 100:
            self.attributes.potentialAgility = 100
        self.attributes.potentialSkillRating = round(((self.attributes.potentialPower*1.2) + (self.attributes.potentialHands*1.3) + (self.attributes.potentialAgility*.5))/3)
    
    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round(((self.gameAttributes.power*1.3) + (self.gameAttributes.hands*1) + (self.gameAttributes.agility*.7))/3)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*3) + (self.gameAttributes.playMakingAbility) + (self.gameAttributes.xFactor))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round(((self.attributes.power*1.3) + (self.attributes.hands*1) + (self.attributes.agility*.7))/3)
        self.attributes.overallRating = round(((self.attributes.skillRating*3) + (self.attributes.playMakingAbility) + (self.attributes.xFactor))/5)
        self.offensiveRating = self.attributes.overallRating
        self.defensiveRating = self.attributes.calculateDefensiveRating(self.position)
        self.playerRating = round((self.offensiveRating + self.defensiveRating) / 2)


    def offseasonTraining(self, coachDevRating: int = 50, fundingDevBonus: int = 0):
        PlayerDevelopment.apply_offseason_training(self, "TE", coachDevRating=coachDevRating, fundingDevBonus=fundingDevBonus)
        self.updateRating()

class PlayerK(Player):
    def __init__(self, physicalSeed = None, mentalSeed = None):
        super().__init__()
        self.position = Position.K
        self.defensivePosition = None
        self.maxFgDistance = 0
        self.attributes.getPlayerAttributes(self.position, physicalSeed, mentalSeed)
        self.updateRating()

        self.attributes.potentialLegStrength = self.attributes.legStrength + randint(0,30)
        self.attributes.potentialAccuracy = self.attributes.accuracy + randint(0,30)
        if self.attributes.potentialLegStrength > 100:
            self.attributes.potentialLegStrength = 100
        if self.attributes.potentialAccuracy > 100:
            self.attributes.potentialAccuracy = 100
        self.attributes.potentialSkillRating = round((self.attributes.potentialLegStrength + self.attributes.potentialAccuracy)/2)
    
    def updateInGameRating(self):
        self.gameAttributes.calculateIntangibles()
        self.gameAttributes.calculateSkills()
        self.gameAttributes.skillRating = round((self.gameAttributes.legStrength + self.gameAttributes.accuracy)/2)
        self.gameAttributes.overallRating = round(((self.gameAttributes.skillRating*3) + (self.gameAttributes.playMakingAbility) + (self.gameAttributes.xFactor))/5)
        if self.gameAttributes.overallRating > 100:
            self.gameAttributes.overallRating = 100

    def updateRating(self):
        self.attributes.calculateIntangibles()
        self.attributes.calculateSkills()
        self.attributes.skillRating = round((self.attributes.legStrength + self.attributes.accuracy)/2)
        self.attributes.overallRating = round(((self.attributes.skillRating*3) + (self.attributes.playMakingAbility) + (self.attributes.xFactor))/5)
        self.offensiveRating = self.attributes.overallRating
        self.defensiveRating = self.offensiveRating  # Kickers: no defensive role, rating = offensive
        self.playerRating = self.attributes.overallRating
        self.maxFgDistance = round(70*(self.attributes.legStrength/100))


    def offseasonTraining(self, coachDevRating: int = 50, fundingDevBonus: int = 0):
        PlayerDevelopment.apply_offseason_training(self, "K", coachDevRating=coachDevRating, fundingDevBonus=fundingDevBonus)
        self.updateRating()