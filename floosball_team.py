from os import stat
from random import randint
import statistics
import copy
import floosball_methods as FloosMethods
import floosball_player as FloosPlayer



teamStatsDict = {   
                    'season': 0,
                    'elo': 0,
                    'overallRating': 0,
                    'madePlayoffs': False,
                    'leagueChamp': False,
                    'floosbowlChamp': False,
                    'topSeed': False,
                    'wins': 0,
                    'losses': 0,
                    'winPerc': 0,
                    'streak': 0,
                    'peakStreak': 0,
                    'scoreDiff': 0,
                    # Cumulative big plays in games this team played this
                    # season (either side of the ball). Used for the
                    # Highlight Reel card projection — per-game avg =
                    # bigPlays / (wins + losses).
                    'bigPlays': 0,
                    'Offense': {
                        'runTds': 0,
                        'passTds': 0,
                        'tds': 0, 
                        'fgs': 0,
                        'pts': 0,
                        'passYards': 0, 
                        'runYards': 0, 
                        'totalYards': 0,
                        'avgRunYards': 0,
                        'avgPassYards': 0,
                        'avgYards': 0,
                        'avgTds': 0,
                        'avgFgs': 0,
                        'avgPts': 0
                    }, 
                    'Defense': {
                        'sacks': 0, 
                        'ints': 0, 
                        'fumRec': 0, 
                        'safeties': 0, 
                        'passYardsAlwd': 0, 
                        'runYardsAlwd': 0, 
                        'totalYardsAlwd': 0, 
                        'runTdsAlwd': 0, 
                        'passTdsAlwd': 0, 
                        'tdsAlwd': 0, 
                        'ptsAlwd': 0,
                        'avgSacks': 0,
                        'avgInts': 0,
                        'avgFumRec': 0,
                        'avgPassYardsAlwd': 0,
                        'avgRunYardsAlwd': 0,
                        'avgYardsAlwd': 0,
                        'avgPassTdsAlwd': 0,
                        'avgRunTdsAlwd': 0,
                        'avgTdsAlwd': 0,
                        'avgPtsAlwd': 0,
                        'fantasyPoints': 0
                    }
                }
class Team:
    def __init__(self, name):
        self.name = name
        self.id = 0
        self.city = None
        self.abbr = None
        self.color = None
        self.secondaryColor = None
        self.tertiaryColor = None
        self.league = None
        self.offenseRating = 0
        self.defenseRunCoverageRating = 0
        self.defensePassCoverageRating = 0
        self.defensePassRushRating = 0
        self.defensePassRating = 0
        self.coach = None  # Coach object assigned by TeamManager
        self.elo = 1500
        self._gameDefenseConfidence = randint(-2,2)
        self._gameDefenseDetermination = randint(-2,2)
        # self.defenseLuck = FloosMethods.getStat(1,100,1)
        # self.defenseDiscipline = FloosMethods.getStat(1,100,1)
        # self._gameDefenseEnergy = 100
        self.defenseRating = 0
        self.defenseOverallRating = 0
        self.defenseOverallTier = 0
        self.defensePassTier = 0
        self.defenseRunTier = 0
        self.overallRating = 0
        self.pressureModifier = 1.0
        # Prior-season expectations baseline: set once at season start from
        # last year's playoff finish / win pct. Wanes across the regular
        # season as inSeasonPressure (driven by current standings and
        # elimination state) takes over. pressureModifier itself is the
        # blended live value used at game time.
        self.priorSeasonPressure = 1.0
        self.inSeasonPressure = 1.0
        # Streak pressure: builds with consecutive wins (regular season +
        # playoffs), resets on any loss. Adds to the live pressureModifier
        # at game-time scaling. See constants.STREAK_PRESSURE_*.
        self.currentWinStreak = 0
        self.streakPressure = 0.0
        self.leagueChampionships = []
        self.floosbowlChampionships = []
        self.topSeeds = []
        self.playoffAppearances = 0
        self.defenseRunCoverageSeasonPerformanceRating = 0
        self.defensePassCoverageSeasonPerformanceRating = 0
        self.defenseSeasonPerformanceRating = 0
        self.playerCap = 0
        self.gmScore = 0
        self.fundingTier = 'MID_MARKET'
        self.fundingTierRank = 3
        # Markets→Facilities: facility_key -> level. Loaded from team_facilities.
        # Drives the dev/morale/fatigue/scouting effects via facilityEffect()
        # (replaces the old fundingTier perk lookups). Empty = treat as Lv0.
        self.facilities = {}
        self.cutsAvailable = 0
        self.eliminated = False
        self.faComplete = False
        self.schedule = []
        self.rosterHistory = []
        self.statArchive = []
        self.clinchedPlayoffs = False
        self.clinchedTopSeed = False
        self.leagueChampion = False
        self.floosbowlChampion = False
        self.winningStreak = False

        self.playerNumbersList = []

        self.gameDefenseStats = copy.deepcopy(teamStatsDict['Defense'])
        self.seasonTeamStats = copy.deepcopy(teamStatsDict)
        self.allTimeTeamStats = copy.deepcopy(teamStatsDict)
        self.rosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None, 'te': None, 'k': None}
        # Prospects: drafted rookies + undrafted signings, capped per-position by
        # constants.PROSPECT_SLOT_CAP_PER_POSITION, auto-released after
        # constants.PROSPECT_DEVELOPMENT_WINDOW offseasons. Not roster-eligible.
        self.prospects: list = []

    def setupTeam(self):
        if self.overallRating == 0:
            # Calculate offense rating with defensive checks for None positions
            qb_rating = self.rosterDict.get('qb').attributes.overallRating if self.rosterDict.get('qb') else 50
            rb_rating = self.rosterDict.get('rb').attributes.overallRating if self.rosterDict.get('rb') else 50
            wr1_rating = self.rosterDict.get('wr1').attributes.overallRating if self.rosterDict.get('wr1') else 50
            wr2_rating = self.rosterDict.get('wr2').attributes.overallRating if self.rosterDict.get('wr2') else 50
            te_rating = self.rosterDict.get('te').attributes.overallRating if self.rosterDict.get('te') else 50
            k_rating = self.rosterDict.get('k').attributes.overallRating if self.rosterDict.get('k') else 50

            self.offenseRating = round(((qb_rating*1.2)+(rb_rating*1.1)+(wr1_rating*.5)+(wr2_rating*.5)+(te_rating*.9)+(k_rating*.8))/5)
            self.deriveDefenseFromRoster()
            if self.defenseSeasonPerformanceRating > 0:
                self.defenseOverallRating = round(((self.defenseRating*1.2)+(self.defenseSeasonPerformanceRating*.8))/2)
            else:
                self.defenseOverallRating = self.defenseRating

    def updateInGameDefenseRating(self):
        self.defenseRating = round((((self.defenseRunCoverageRating*.8)+(self.defensePassCoverageRating*1.2)+(self.defensePassRushRating*1))/3) + ((self._gameDefenseConfidence + self._gameDefenseDetermination)/2))

    def deriveDefenseFromRoster(self):
        """Derive team defense ratings from player defensive attributes.

        Replaces old random 70-90 generation and weekly drift.
        Called whenever roster changes (trades, free agency, setup).
        """
        # Get defensive attributes for each roster position
        qb = self.rosterDict.get('qb')
        rb = self.rosterDict.get('rb')
        wr1 = self.rosterDict.get('wr1')
        wr2 = self.rosterDict.get('wr2')
        te = self.rosterDict.get('te')

        # Safety (QB) attributes
        sAttrs = qb.attributes.getDefensiveAttributes(qb.position) if qb else {}
        # Linebacker (RB) attributes
        lbAttrs = rb.attributes.getDefensiveAttributes(rb.position) if rb else {}
        # Cornerback (WR1) attributes
        cb1Attrs = wr1.attributes.getDefensiveAttributes(wr1.position) if wr1 else {}
        # Cornerback (WR2) attributes
        cb2Attrs = wr2.attributes.getDefensiveAttributes(wr2.position) if wr2 else {}
        # Defensive End (TE) attributes
        deAttrs = te.attributes.getDefensiveAttributes(te.position) if te else {}

        # Pass coverage: CB1 35% + CB2 35% + S 30%
        cb1Cov = cb1Attrs.get('coverage', 70)
        cb2Cov = cb2Attrs.get('coverage', 70)
        sCov = sAttrs.get('coverage', 70)
        self.defensePassCoverageRating = round(0.35 * cb1Cov + 0.35 * cb2Cov + 0.30 * sCov)

        # Pass rush: DE 60% passRush + LB 25% blitzing + DE 15% runDefense
        dePassRush = deAttrs.get('passRush', 70)
        lbBlitz = lbAttrs.get('blitzing', 70)
        deRunDef = deAttrs.get('runDefense', 70)
        self.defensePassRushRating = round(0.60 * dePassRush + 0.25 * lbBlitz + 0.15 * deRunDef)

        # Run coverage: LB 40% runDefense + DE 30% runDefense + LB 20% tackling + S 10% tackling
        lbRunDef = lbAttrs.get('runDefense', 70)
        lbTackle = lbAttrs.get('tackling', 70)
        sTackle = sAttrs.get('tackling', 70)
        self.defenseRunCoverageRating = round(0.40 * lbRunDef + 0.30 * deRunDef + 0.20 * lbTackle + 0.10 * sTackle)

        # Derived composite ratings
        self.defensePassRating = round(((self.defensePassCoverageRating * 1.2) + (self.defensePassRushRating * 0.8)) / 2)
        self.defenseRating = round((((self.defenseRunCoverageRating * 0.8) + (self.defensePassCoverageRating * 1.2) + (self.defensePassRushRating * 1)) / 3) + ((self._gameDefenseConfidence + self._gameDefenseDetermination) / 2))
        self.overallRating = round(statistics.mean([self.offenseRating, self.defenseRunCoverageRating, self.defensePassCoverageRating]))

    def updateRating(self):
        # Calculate offense rating with defensive checks for None positions
        qb_rating = self.rosterDict.get('qb').attributes.overallRating if self.rosterDict.get('qb') else 50
        rb_rating = self.rosterDict.get('rb').attributes.overallRating if self.rosterDict.get('rb') else 50
        wr1_rating = self.rosterDict.get('wr1').attributes.overallRating if self.rosterDict.get('wr1') else 50
        wr2_rating = self.rosterDict.get('wr2').attributes.overallRating if self.rosterDict.get('wr2') else 50
        te_rating = self.rosterDict.get('te').attributes.overallRating if self.rosterDict.get('te') else 50
        k_rating = self.rosterDict.get('k').attributes.overallRating if self.rosterDict.get('k') else 50

        self.offenseRating = round(((qb_rating*1.2)+(rb_rating*1.1)+(wr1_rating*.5)+(wr2_rating*.5)+(te_rating*.9)+(k_rating*.8))/5)
        self.deriveDefenseFromRoster()
        if self.defenseSeasonPerformanceRating < 0:
            self.defenseOverallRating = self.defenseRating

    def updateDefense(self):
        """Recalculate defense from roster. No more random drift."""
        self.deriveDefenseFromRoster()

    def getAverages(self, season=None):
        """Compute season averages from the database Game table.

        Queries completed games for this team and aggregates offensive/defensive
        stats.  This avoids holding Game objects in memory after week completion.

        Args:
            season: Season number to query. If None, queries all seasons.
        """
        try:
            from database.connection import get_session
            from database.repositories.game_repository import GameRepository
        except ImportError:
            return  # DB not available

        session = get_session()
        try:
            rows = GameRepository(session).get_team_games(self.id, season=season)
            offRushYards, offPassYards, offTotalYards = [], [], []
            offRushTds, offPassTds, offTds, offFgs, offPts = [], [], [], [], []
            defSacks, defInts, defFumRec = [], [], []
            defPassYardsAlwd, defRunYardsAlwd, defTotalYardsAlwd = [], [], []
            defRunTdsAlwd, defPassTdsAlwd, defTotalTdsAlwd, defPtsAlwd = [], [], [], []

            for g in rows:
                if g.status != 'final':
                    continue
                # Determine home/away perspective
                isHome = (g.home_team_id == self.id)
                # Offense columns
                rushYds = (g.home_rush_yards if isHome else g.away_rush_yards) or 0
                passYds = (g.home_pass_yards if isHome else g.away_pass_yards) or 0
                rushTds = (g.home_rush_tds if isHome else g.away_rush_tds) or 0
                passTds = (g.home_pass_tds if isHome else g.away_pass_tds) or 0
                fgs     = (g.home_fgs if isHome else g.away_fgs) or 0
                pts     = (g.home_score if isHome else g.away_score) or 0
                offRushYards.append(rushYds)
                offPassYards.append(passYds)
                offTotalYards.append(rushYds + passYds)
                offRushTds.append(rushTds)
                offPassTds.append(passTds)
                offTds.append(rushTds + passTds)
                offFgs.append(fgs)
                offPts.append(pts)
                # Defense columns (opponent's offense = our defense allowed)
                dRushYds = (g.away_rush_yards if isHome else g.home_rush_yards) or 0
                dPassYds = (g.away_pass_yards if isHome else g.home_pass_yards) or 0
                dRushTds = (g.away_rush_tds if isHome else g.home_rush_tds) or 0
                dPassTds = (g.away_pass_tds if isHome else g.home_pass_tds) or 0
                dSacks   = (g.home_sacks if isHome else g.away_sacks) or 0
                dInts    = (g.home_ints if isHome else g.away_ints) or 0
                dFumRec  = (g.home_fum_rec if isHome else g.away_fum_rec) or 0
                dPts     = (g.away_score if isHome else g.home_score) or 0
                defSacks.append(dSacks)
                defInts.append(dInts)
                defFumRec.append(dFumRec)
                defPassYardsAlwd.append(dPassYds)
                defRunYardsAlwd.append(dRushYds)
                defTotalYardsAlwd.append(dRushYds + dPassYds)
                defRunTdsAlwd.append(dRushTds)
                defPassTdsAlwd.append(dPassTds)
                defTotalTdsAlwd.append(dRushTds + dPassTds)
                defPtsAlwd.append(dPts)

            # Helper for safe mean
            def _avg(lst):
                return round(statistics.mean(lst), 2) if lst else 0

            self.seasonTeamStats['Offense']['avgRunYards']  = _avg(offRushYards)
            self.seasonTeamStats['Offense']['avgPassYards'] = _avg(offPassYards)
            self.seasonTeamStats['Offense']['avgYards']     = _avg(offTotalYards)
            self.seasonTeamStats['Offense']['avgRunTds']    = _avg(offRushTds)
            self.seasonTeamStats['Offense']['avgPassTds']   = _avg(offPassTds)
            self.seasonTeamStats['Offense']['avgTds']       = _avg(offTds)
            self.seasonTeamStats['Offense']['avgFgs']       = _avg(offFgs)
            self.seasonTeamStats['Offense']['avgPts']       = _avg(offPts)

            self.seasonTeamStats['Defense']['avgSacks']       = _avg(defSacks)
            self.seasonTeamStats['Defense']['avgInts']        = _avg(defInts)
            self.seasonTeamStats['Defense']['avgFumRec']      = _avg(defFumRec)
            self.seasonTeamStats['Defense']['avgPassYardsAlwd'] = _avg(defPassYardsAlwd)
            self.seasonTeamStats['Defense']['avgRunYardsAlwd']  = _avg(defRunYardsAlwd)
            self.seasonTeamStats['Defense']['avgYardsAlwd']     = _avg(defTotalYardsAlwd)
            self.seasonTeamStats['Defense']['avgPassTdsAlwd']   = _avg(defPassTdsAlwd)
            self.seasonTeamStats['Defense']['avgRunTdsAlwd']    = _avg(defRunTdsAlwd)
            self.seasonTeamStats['Defense']['avgTdsAlwd']       = _avg(defTotalTdsAlwd)
            self.seasonTeamStats['Defense']['avgPtsAlwd']       = _avg(defPtsAlwd)
        finally:
            session.close()

    def assignPlayerNumber(self, player):
        numberToAssign = player.preferredNumber
        while True:
            if numberToAssign in self.playerNumbersList:
                numberToAssign = randint(0,99)
                continue
            else:
                player.currentNumber = numberToAssign
                self.playerNumbersList.append(player.currentNumber) 
                break   


    def saveRoster(self):
        seasonRosterDict = {}
        for k,v in self.rosterDict.items():
            seasonRosterDict[k] = {'name': v.name, 'rating': v.attributes.overallRating, 'tier': v.playerTier.name, 'term': v.term, 'number': v.currentNumber, 'seasonStats': v.seasonStatsDict}
        seasonRosterDict['runDefense'] = self.defenseRunCoverageRating
        seasonRosterDict['passDefense'] = self.defensePassCoverageRating

    def updateInGameConfidence(self, value):
        self._gameDefenseConfidence = round(self._gameDefenseConfidence + value, 2)

    def updateInGameDetermination(self, value):
        self._gameDefenseDetermination = round(self._gameDefenseDetermination + value, 2)

    def inGamePush(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(.01)
        self.updateInGameDetermination(.01)

    def facilityLevel(self, facilityKey):
        """Current level of a facility (0 if unbuilt / not loaded)."""
        return (self.facilities or {}).get(facilityKey, 0)

    def facilityEffect(self, effectType):
        """Effect value this team gets for a given effect ('dev_bonus',
        'morale', 'fatigue_reduction', 'scouting_bonus', 'home_morale') from
        the facility that drives it, at the team's current level. Replaces the
        old FUNDING_* market-tier lookups. Returns 0 when unbuilt/unknown."""
        from constants import FACILITY_CATALOG, FACILITY_MAX_LEVEL
        for key, cfg in FACILITY_CATALOG.items():
            if cfg.get('effect') == effectType:
                level = max(0, min(FACILITY_MAX_LEVEL, (self.facilities or {}).get(key, 0)))
                levels = cfg.get('levels') or []
                return levels[level] if level < len(levels) else (levels[-1] if levels else 0)
        return 0

    def teamUnderPerform(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(-.01)
            player.updateInGameConfidence(-.01)
        self.updateInGameDetermination(-.01)
        self.updateInGameConfidence(-.01)

    def teamOverPerform(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(.01)
            player.updateInGameConfidence(.01)
        self.updateInGameDetermination(.01)
        self.updateInGameConfidence(.01)


    def resetGameEnergy(self):
        for player in self.rosterDict.values():
            player: FloosPlayer.Player
            player.energy = 100