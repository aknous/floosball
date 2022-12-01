from os import stat
from random import randint
import statistics
import copy
import floosball_methods as FloosMethods
import floosball_player as FloosPlayer



teamStatsDict = {   
                    'wins': 0, 
                    'losses': 0, 
                    'winPerc': 0, 
                    'streak': 0, 
                    'divWins': 0, 
                    'divLosses': 0, 
                    'divWinPerc': 0, 
                    'scoreDiff': 0,
                    'Offense': {
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
                        'avgPtsAlwd': 0
                    }
                }
class Team:
    def __init__(self, name):
        self.name = name
        self.id = 0
        self.city = None
        self.abbr = None
        self.color = None
        self.division = None
        self.offenseRating = 0
        self.runDefenseRating = 0
        self.passDefenseRating = 0
        self.gameRunDefenseRating = 0
        self.gamePassDefenseRating = 0
        self.gameDefenseRating = 0
        self._gameDefenseConfidence = 1
        self._gameDefenseDetermination = 1
        self.defenseLuck = FloosMethods.getStat(1,100,1)
        self.defenseDiscipline = FloosMethods.getStat(1,100,1)
        self._gameDefenseEnergy = 100
        self.defenseRating = 0
        self.defenseOverallRating = 0
        self.defenseTier = 0
        self.overallRating = 0
        self.leagueChampionships = []
        self.playoffAppearances = 0
        self.defenseSeasonPerformanceRating = 0
        self.gmScore = randint(0,20)
        self.eliminated = False
        self.schedule = []
        self.draftHistory = []
        self.freeAgentHistory = []
        self.rosterHistory = []

        self.gameDefenseStats = copy.deepcopy(teamStatsDict['Defense'])
        self.seasonTeamStats = copy.deepcopy(teamStatsDict)
        self.allTimeTeamStats = copy.deepcopy(teamStatsDict)
        self.rosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None, 'te': None, 'k': None}
        self.reserveRosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None, 'te': None, 'k': None}

    def setupTeam(self):
        if self.overallRating == 0:
            self.offenseRating = round(((self.rosterDict['qb'].attributes.overallRating*1.2)+(self.rosterDict['rb'].attributes.overallRating*1.1)+(self.rosterDict['wr1'].attributes.overallRating*.5)+(self.rosterDict['wr2'].attributes.overallRating*.5)+(self.rosterDict['te'].attributes.overallRating*.9)+(self.rosterDict['k'].attributes.overallRating*.8))/5)
            x = randint(1, 100)
            if x >= 99:
                self.runDefenseRating = randint(85, 100)
                self.passDefenseRating = randint(85, 100)
            elif x >= 85 and x < 98:
                self.runDefenseRating = randint(80, 95)
                self.passDefenseRating = randint(80, 95)
            elif x >= 60 and x < 85:
                self.runDefenseRating = randint(70, 89)
                self.passDefenseRating = randint(70, 89)
            else:
                self.runDefenseRating = randint(60, 95)
                self.passDefenseRating = randint(60, 95)
                
            self.defenseRating = round(((self.runDefenseRating*1.8)+(self.passDefenseRating*2.2))/4)
            self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))
            if self.defenseSeasonPerformanceRating > 0:
                self.defenseOverallRating = round(((self.defenseRating*1.2)+(self.defenseSeasonPerformanceRating*.8))/2)
            else:
                self.defenseOverallRating = self.defenseRating

    def setRoster(self):
        if self.reserveRosterDict['qb'] is not None:
            if self.reserveRosterDict['qb'].playerRating> self.rosterDict['qb'].playerRating:
                replacedPlayer = self.rosterDict['qb']
                self.rosterDict['qb'] = self.reserveRosterDict['qb']
                self.reserveRosterDict['qb'] = replacedPlayer
        if self.reserveRosterDict['rb'] is not None:
            if self.reserveRosterDict['rb'].playerRating > self.rosterDict['rb'].playerRating:
                replacedPlayer = self.rosterDict['rb']
                self.rosterDict['rb'] = self.reserveRosterDict['rb']
                self.reserveRosterDict['rb'] = replacedPlayer
        if self.reserveRosterDict['wr1'] is not None:
            if self.reserveRosterDict['wr1'].playerRating > self.rosterDict['wr1'].playerRating:
                replacedPlayer = self.rosterDict['wr1']
                self.rosterDict['wr1'] = self.reserveRosterDict['wr1']
                self.reserveRosterDict['wr1'] = replacedPlayer
            elif self.reserveRosterDict['wr1'].playerRating > self.rosterDict['wr2'].playerRating:
                replacedPlayer = self.rosterDict['wr2']
                self.rosterDict['wr2'] = self.reserveRosterDict['wr1']
                self.reserveRosterDict['wr1'] = replacedPlayer
        if self.reserveRosterDict['wr2'] is not None:
            if self.reserveRosterDict['wr2'].playerRating > self.rosterDict['wr2'].playerRating:
                replacedPlayer = self.rosterDict['wr2']
                self.rosterDict['wr2'] = self.reserveRosterDict['wr2']
                self.reserveRosterDict['wr2'] = replacedPlayer
            elif self.reserveRosterDict['wr2'].playerRating > self.rosterDict['wr1'].playerRating:
                replacedPlayer = self.rosterDict['wr1']
                self.rosterDict['wr1'] = self.reserveRosterDict['wr2']
                self.reserveRosterDict['wr2'] = replacedPlayer
        if self.reserveRosterDict['te'] is not None:
            if self.reserveRosterDict['te'].playerRating > self.rosterDict['te'].playerRating:
                replacedPlayer = self.rosterDict['te']
                self.rosterDict['te'] = self.reserveRosterDict['te']
                self.reserveRosterDict['te'] = replacedPlayer
        if self.reserveRosterDict['k'] is not None:
            if self.reserveRosterDict['k'].playerRating > self.rosterDict['k'].playerRating:
                replacedPlayer = self.rosterDict['k']
                self.rosterDict['k'] = self.reserveRosterDict['k']
                self.reserveRosterDict['k'] = replacedPlayer

        self.updateRating()


    def updateRating(self):
        self.defenseRating = round(((self.runDefenseRating*1.8)+(self.passDefenseRating*2.2))/4)
        self.offenseRating = round(((self.rosterDict['qb'].attributes.overallRating*1.2)+(self.rosterDict['rb'].attributes.overallRating*1.1)+(self.rosterDict['wr1'].attributes.overallRating*.5)+(self.rosterDict['wr2'].attributes.overallRating*.5)+(self.rosterDict['te'].attributes.overallRating*.9)+(self.rosterDict['k'].attributes.overallRating*.8))/5)
        self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))
        self.gameDefenseRating = round(((self.gameRunDefenseRating*1.5)+(self.gamePassDefenseRating*1.7)+(self.defenseDiscipline*1)+(self.defenseLuck*.8))/5)
        if self.defenseSeasonPerformanceRating > 0:
            self.defenseOverallRating = round(((self.defenseRating*.8)+(self.defenseSeasonPerformanceRating*1.2))/2)
        else:
            self.defenseOverallRating = self.defenseRating

    def updateInGameDefenseRating(self):
        rating = round(((self.gameRunDefenseRating*1.5)+(self.gamePassDefenseRating*1.7)+(self.defenseDiscipline*1)+(self.defenseLuck*.8))/5)
        self.gameDefenseRating = round(((((rating - 60) * self._gameDefenseEnergy)/100)+60)*((self._gameDefenseConfidence+self._gameDefenseDetermination)/2))
        if self.gameDefenseRating > 100:
            self.gameDefenseRating = 100

    def updateDefense(self):
        x = randint(1,10)
        if x < 3:
            x = randint(1, 100)
            if x >= 99:
                self.runDefenseRating = randint(85, 100)
                self.passDefenseRating = randint(85, 100)
            elif x >= 85 and x < 98:
                self.runDefenseRating = randint(80, 95)
                self.passDefenseRating = randint(80, 95)
            elif x >= 60 and x < 85:
                self.runDefenseRating = randint(70, 89)
                self.passDefenseRating = randint(70, 89)
            else:
                self.runDefenseRating = randint(60, 95)
                self.passDefenseRating = randint(60, 95)   
        else:
            if self.defenseDiscipline >= 95:
                self.defenseDiscipline += randint(-15, -5)
            elif self.defenseDiscipline <= 70:
                self.defenseDiscipline += randint(5, 15)
            else:
                self.defenseDiscipline += randint(-10, 10)

            if self.passDefenseRating >= 95:
                self.passDefenseRating += randint(-10, -5)
            elif self.passDefenseRating <= 70:
                self.passDefenseRating += randint(5, 15)
            else:
                self.passDefenseRating += randint(-10, 10)
            if self.runDefenseRating >= 95:
                self.runDefenseRating += randint(-10, -5)
            elif self.runDefenseRating <= 70:
                self.runDefenseRating += randint(5, 15)
            else:
                self.runDefenseRating += randint(-10, 10)

            if self.passDefenseRating > 100:
                self.passDefenseRating = 100
            elif self.passDefenseRating < 60:
                self.passDefenseRating = 60
            if self.runDefenseRating > 100:
                self.runDefenseRating = 100
            elif self.runDefenseRating < 60:
                self.runDefenseRating = 60

        self.updateRating()

    def getAverages(self):
        from floosball_game import Game, GameStatus
        offenseRunTdsList = []
        offensePassTdsList = []
        offenseTdsList = []
        offenseFgsList = []
        offensePtsList = []
        offensePassYardsList = []
        offenseRunYardsList = []
        offenseTotalYardsList = []
        defenseSacksList = []
        defenseIntsList = []
        defenseFumRecList = []
        defensePassYardsAlwdList = []
        defenseRunYardsAlwdList = []
        defenseTotalYardsAlwdList = []
        defenseRunTdsAlwdList = []
        defensePassTdsAlwdList = []
        defenseTotalTdsAlwdList = []
        defensePtsAlwdList = []

        for game in self.schedule:
            game: Game
            if game.status is GameStatus.Final:
                if game.homeTeam.name == self.name:
                    offenseStatsDict = game.gameDict['gameStats']['homeTeam']['offense']
                    defenseStatsDict = game.gameDict['gameStats']['homeTeam']['defense']
                else:
                    offenseStatsDict = game.gameDict['gameStats']['awayTeam']['offense']
                    defenseStatsDict = game.gameDict['gameStats']['awayTeam']['defense']
                offenseRunTdsList.append(offenseStatsDict['runTds'])
                offensePassTdsList.append(offenseStatsDict['passTds'])
                offenseTdsList.append(offenseStatsDict['tds'])
                offenseRunYardsList.append(offenseStatsDict['rushYards'])
                offensePassYardsList.append(offenseStatsDict['passYards'])
                offenseTotalYardsList.append(offenseStatsDict['totalYards'])
                offenseFgsList.append(offenseStatsDict['fgs'])
                offensePtsList.append(offenseStatsDict['score'])

                defenseSacksList.append(defenseStatsDict['sacks'])
                defenseIntsList.append(defenseStatsDict['ints'])
                defenseFumRecList.append(defenseStatsDict['fumRec'])
                defensePassYardsAlwdList.append(defenseStatsDict['passYardsAlwd'])
                defenseRunYardsAlwdList.append(defenseStatsDict['runYardsAlwd'])
                defenseTotalYardsAlwdList.append(defenseStatsDict['totalYardsAlwd'])
                defenseRunTdsAlwdList.append(defenseStatsDict['runTdsAlwd'])
                defensePassTdsAlwdList.append(defenseStatsDict['passTdsAlwd'])
                defenseTotalTdsAlwdList.append(defenseStatsDict['tdsAlwd'])
                defensePtsAlwdList.append(defenseStatsDict['ptsAlwd'])
            elif game.status is GameStatus.Scheduled:
                break

        self.seasonTeamStats['Offense']['avgRunYards'] = round(statistics.mean(offenseRunYardsList),2)
        self.seasonTeamStats['Offense']['avgPassYards'] = round(statistics.mean(offensePassYardsList),2)
        self.seasonTeamStats['Offense']['avgYards'] = round(statistics.mean(offenseTotalYardsList),2)
        self.seasonTeamStats['Offense']['avgTds'] = round(statistics.mean(offenseTdsList),2)
        self.seasonTeamStats['Offense']['avgFgs'] = round(statistics.mean(offenseFgsList),2)
        self.seasonTeamStats['Offense']['avgPts'] = round(statistics.mean(offensePtsList),2)

        self.seasonTeamStats['Defense']['avgSacks'] = round(statistics.mean(defenseSacksList),2)
        self.seasonTeamStats['Defense']['avgInts'] = round(statistics.mean(defenseIntsList),2)
        self.seasonTeamStats['Defense']['avgFumRec'] = round(statistics.mean(defenseFumRecList),2)
        self.seasonTeamStats['Defense']['avgPassYardsAlwd'] = round(statistics.mean(defensePassYardsAlwdList),2)
        self.seasonTeamStats['Defense']['avgRunYardsAlwd'] = round(statistics.mean(defenseRunYardsAlwdList),2)
        self.seasonTeamStats['Defense']['avgYardsAlwd'] = round(statistics.mean(defenseTotalYardsAlwdList),2)
        self.seasonTeamStats['Defense']['avgPassTdsAlwd'] = round(statistics.mean(defensePassTdsAlwdList),2)
        self.seasonTeamStats['Defense']['avgRunTdsAlwd'] = round(statistics.mean(defenseRunTdsAlwdList),2)
        self.seasonTeamStats['Defense']['avgTdsAlwd'] = round(statistics.mean(defenseTotalTdsAlwdList),2)
        self.seasonTeamStats['Defense']['avgPtsAlwd'] = round(statistics.mean(defensePtsAlwdList),2)


    def saveRoster(self):
        seasonRosterDict = {}
        for k,v in self.rosterDict.items():
            seasonRosterDict[k] = {'name': v.name, 'rating': v.attributes.overallRating, 'tier': v.playerTier.name, 'term': v.term, 'seasonStats': v.seasonStatsDict}
        seasonRosterDict['runDefense'] = self.runDefenseRating
        seasonRosterDict['passDefense'] = self.passDefenseRating

    def updateGameConfidence(self, value):
        self._gameDefenseConfidence = round(self._gameDefenseConfidence + value, 2)
        self.updateInGameDefenseRating()

    def updateGameDetermination(self, value):
        self._gameDefenseDetermination = round(self._gameDefenseDetermination + value, 2)
        self.updateInGameDefenseRating()

    def updateGameEnergy(self, value):
        self._gameDefenseEnergy = round(self._gameDefenseEnergy + value, 2)
        if self._gameDefenseEnergy > 100:
            self._gameDefenseEnergy = 100
        self.updateInGameDefenseRating()

    def inGamePush(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(.02)
        self.updateGameDetermination(.02)

    def teamUnderPerform(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(-.02)
            player.updateInGameConfidence(-.02)
        self.updateGameDetermination(-.02)
        self.updateGameConfidence(-.02)

    def teamOverPerform(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(.02)
            player.updateInGameConfidence(.02)
        self.updateGameDetermination(.02)
        self.updateGameConfidence(.02)

    def resetConfidence(self):
        for player in self.rosterDict.values():
            player.gameAttributes.confidence = 1
            player.updateInGameRating
        self._gameDefenseConfidence = 1

    def resetDetermination(self):
        for player in self.rosterDict.values():
            player.gameAttributes.determination = 1
            player.updateInGameRating
        self._gameDefenseDetermination = 1

    def resetGameEnergy(self):
        self._gameDefenseEnergy = 100
        self.updateInGameDefenseRating()