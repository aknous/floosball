from random import randint
import statistics
import copy
import floosball_methods as FloosMethods
import floosball_player as FloosPlayer



teamStatsDict = {'wins': 0, 'losses': 0, 'winPerc': 0, 'streak': 0, 'divWins': 0, 'divLosses': 0, 'divWinPerc': 0, 'Offense': {'tds': 0, 'passYards': 0, 'runYards': 0, 'totalYards': 0}, 'Defense': {'sacks': 0, 'ints': 0, 'fumRec': 0, 'passYardsAlwd': 0, 'runYardsAlwd': 0, 'totalYardsAlwd': 0, 'runTdsAlwd': 0, 'passTdsAlwd': 0, 'tdsAlwd': 0}}
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
        self.overallRating = 0
        self.leagueChampionships = 0
        self.playoffAppearances = 0
        self.defenseSeasonPerformanceRating = 0
        self.schedule = []

        self.gameDefenseStats = copy.deepcopy(teamStatsDict['Defense'])
        self.seasonTeamStats = copy.deepcopy(teamStatsDict)
        self.allTimeTeamStats = copy.deepcopy(teamStatsDict)
        self.rosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr': None, 'te': None, 'k': None}
        self.reserveRosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr': None, 'te': None, 'k': None}
        self.rosterHistoryList = []

    def setupTeam(self):
        if self.overallRating == 0:
            self.offenseRating = round(((self.rosterDict['qb'].attributes.overallRating*1.2)+(self.rosterDict['rb'].attributes.overallRating*1.1)+(self.rosterDict['wr'].attributes.overallRating*1)+(self.rosterDict['te'].attributes.overallRating*.9)+(self.rosterDict['k'].attributes.overallRating*.8))/5)
            x = randint(1, 100)
            if x >= 99:
                self.runDefenseRating = randint(90, 100)
                self.passDefenseRating = randint(90, 100)
            elif x >= 85 and x < 98:
                self.runDefenseRating = randint(86, 95)
                self.passDefenseRating = randint(86, 95)
            elif x >= 60 and x < 85:
                self.runDefenseRating = randint(80, 89)
                self.passDefenseRating = randint(80, 89)
            else:
                self.runDefenseRating = randint(70, 95)
                self.passDefenseRating = randint(70, 95)
                
            self.defenseRating = round(((self.runDefenseRating*1.8)+(self.passDefenseRating*2.2))/4)
            self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))

    def setRoster(self):
        if self.reserveRosterDict['qb'] is not None:
            if self.reserveRosterDict['qb'].attributes.overallRating > self.rosterDict['qb'].attributes.overallRating:
                replacedPlayer = self.rosterDict['qb']
                self.rosterDict['qb'] = self.reserveRosterDict['qb']
                self.reserveRosterDict['qb'] = replacedPlayer
        if self.reserveRosterDict['rb'] is not None:
            if self.reserveRosterDict['rb'].attributes.overallRating > self.rosterDict['rb'].attributes.overallRating:
                replacedPlayer = self.rosterDict['rb']
                self.rosterDict['rb'] = self.reserveRosterDict['rb']
                self.reserveRosterDict['rb'] = replacedPlayer
        if self.reserveRosterDict['wr'] is not None:
            if self.reserveRosterDict['wr'].attributes.overallRating > self.rosterDict['wr'].attributes.overallRating:
                replacedPlayer = self.rosterDict['wr']
                self.rosterDict['wr'] = self.reserveRosterDict['wr']
                self.reserveRosterDict['wr'] = replacedPlayer
        if self.reserveRosterDict['te'] is not None:
            if self.reserveRosterDict['te'].attributes.overallRating > self.rosterDict['te'].attributes.overallRating:
                replacedPlayer = self.rosterDict['te']
                self.rosterDict['te'] = self.reserveRosterDict['te']
                self.reserveRosterDict['te'] = replacedPlayer
        if self.reserveRosterDict['k'] is not None:
            if self.reserveRosterDict['k'].attributes.overallRating > self.rosterDict['k'].attributes.overallRating:
                replacedPlayer = self.rosterDict['k']
                self.rosterDict['k'] = self.reserveRosterDict['k']
                self.reserveRosterDict['k'] = replacedPlayer

        self.updateRating()


    def updateRating(self):
        self.defenseRating = round(((self.runDefenseRating*1.8)+(self.passDefenseRating*2.2))/4)
        self.offenseRating = round(((self.rosterDict['qb'].attributes.overallRating*1.2)+(self.rosterDict['rb'].attributes.overallRating*1.1)+(self.rosterDict['wr'].attributes.overallRating*1)+(self.rosterDict['te'].attributes.overallRating*.9)+(self.rosterDict['k'].attributes.overallRating*.8))/5)
        self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))
        self.gameDefenseRating = round(((self.gameRunDefenseRating*1.5)+(self.gamePassDefenseRating*1.7)+(self.defenseDiscipline*1)+(self.defenseLuck*.8))/5)

    def updateInGameDefenseRating(self):
        rating = round(((self.gameRunDefenseRating*1.5)+(self.gamePassDefenseRating*1.7)+(self.defenseDiscipline*1)+(self.defenseLuck*.8))/5)
        self.gameDefenseRating = round(((((rating - 60) * self._gameDefenseEnergy)/100)+60)*((self._gameDefenseConfidence+self._gameDefenseDetermination)/2))
        if self.gameDefenseRating > 100:
            self.gameDefenseRating = 100

    def updateDefense(self):
        if self.defenseDiscipline >= 95:
            self.defenseDiscipline += randint(-15, -5)
        elif self.defenseDiscipline <= 75:
            self.defenseDiscipline += randint(5, 15)
        else:
            self.defenseDiscipline += randint(-10, 10)

        if self.passDefenseRating >= 95:
            self.passDefenseRating += randint(-10, -5)
        elif self.passDefenseRating <= 75:
            self.passDefenseRating += randint(5, 15)
        else:
            self.passDefenseRating += randint(-10, 10)
        if self.runDefenseRating >= 95:
            self.runDefenseRating += randint(-10, -5)
        elif self.runDefenseRating <= 75:
            self.runDefenseRating += randint(5, 15)
        else:
            self.runDefenseRating += randint(-10, 10)
        
        if self.passDefenseRating > 100:
            self.passDefenseRating = 100
        elif self.passDefenseRating < 70:
            self.passDefenseRating = 70
        if self.runDefenseRating > 100:
            self.runDefenseRating = 100
        elif self.runDefenseRating < 70:
            self.runDefenseRating = 70

        self.updateRating()

    def saveRoster(self):
        seasonRosterDict = {}
        for k,v in self.rosterDict.items():
            seasonRosterDict[k] = {'name': v.name, 'rating': v.attributes.overallRating, 'tier': v.playerTier.name, 'term': v.term, 'seasonStats': v.seasonStatsDict}
        seasonRosterDict['runDefense'] = self.runDefenseRating
        seasonRosterDict['passDefense'] = self.passDefenseRating
        self.rosterHistoryList.append(seasonRosterDict)

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