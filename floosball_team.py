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
                    'divPlace': 0,
                    'divisionChamp': False,
                    'leagueChamp': False,
                    'topSeed': False,
                    'wins': 0, 
                    'losses': 0, 
                    'winPerc': 0, 
                    'streak': 0, 
                    'divWins': 0, 
                    'divLosses': 0, 
                    'divWinPerc': 0, 
                    'scoreDiff': 0,
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
        self.division = None
        self.offenseRating = 0
        self.runDefenseRating = 0
        self.passDefenseRating = 0
        self.gameRunDefenseRating = 0
        self.gamePassDefenseRating = 0
        self.gameDefenseRating = 0
        self.elo = 1500
        # self._gameDefenseConfidence = 1
        # self._gameDefenseDetermination = 1
        # self.defenseLuck = FloosMethods.getStat(1,100,1)
        # self.defenseDiscipline = FloosMethods.getStat(1,100,1)
        # self._gameDefenseEnergy = 100
        self.defenseRating = 0
        self.defenseOverallRating = 0
        self.defenseTier = 0
        self.overallRating = 0
        self.divisionChampionships = []
        self.leagueChampionships = []
        self.regularSeasonChampions = []
        self.playoffAppearances = 0
        self.defenseSeasonPerformanceRating = 0
        self.playerCap = 0
        self.gmScore = 0
        self.cutsAvailable = 0
        self.eliminated = False
        self.faComplete = False
        self.schedule = []
        self.rosterHistory = []
        self.statArchive = []
        self.clinchedPlayoffs = False
        self.clinchedDivision = False
        self.clinchedTopSeed = False
        self.leagueChampion = False
        self.winningStreak = False

        self.gameDefenseStats = copy.deepcopy(teamStatsDict['Defense'])
        self.seasonTeamStats = copy.deepcopy(teamStatsDict)
        self.allTimeTeamStats = copy.deepcopy(teamStatsDict)
        self.rosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr1': None, 'wr2': None, 'te': None, 'k': None, 'db1': None, 'db2': None, 'lb': None, 'de': None, 'dl': None}

    def setupTeam(self):
        if self.overallRating == 0:
            self.offenseRating = round(((self.rosterDict['qb'].attributes.overallRating*1.2)+(self.rosterDict['rb'].attributes.overallRating*1.1)+(self.rosterDict['wr1'].attributes.overallRating*.5)+(self.rosterDict['wr2'].attributes.overallRating*.5)+(self.rosterDict['te'].attributes.overallRating*.9)+(self.rosterDict['k'].attributes.overallRating*.8))/5)
            self.passDefenseRating = round(((self.rosterDict['db1'].attributes.overallRating*1.2)+(self.rosterDict['db2'].attributes.overallRating*1.2)+(self.rosterDict['lb'].attributes.overallRating*.8)+(self.rosterDict['dl'].attributes.overallRating*.8)+(self.rosterDict['de'].attributes.overallRating*1))/5)
            self.runDefenseRating = round(((self.rosterDict['db1'].attributes.overallRating*.5)+(self.rosterDict['db2'].attributes.overallRating*.5)+(self.rosterDict['lb'].attributes.overallRating*1.3)+(self.rosterDict['dl'].attributes.overallRating*1.5)+(self.rosterDict['de'].attributes.overallRating*1.2))/5)
                   
            self.defenseRating = round(((self.runDefenseRating*1.8)+(self.passDefenseRating*2.2))/4)
            self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))
            if self.defenseSeasonPerformanceRating > 0:
                self.defenseOverallRating = round(((self.defenseRating*1.2)+(self.defenseSeasonPerformanceRating*.8))/2)
            else:
                self.defenseOverallRating = self.defenseRating


    def updateRating(self):
        self.passDefenseRating = round(((self.rosterDict['db1'].attributes.overallRating*1.2)+(self.rosterDict['db2'].attributes.overallRating*1.2)+(self.rosterDict['lb'].attributes.overallRating*.8)+(self.rosterDict['dl'].attributes.overallRating*.8)+(self.rosterDict['de'].attributes.overallRating*1))/5)
        self.runDefenseRating = round(((self.rosterDict['db1'].attributes.overallRating*.5)+(self.rosterDict['db2'].attributes.overallRating*.5)+(self.rosterDict['lb'].attributes.overallRating*1.3)+(self.rosterDict['dl'].attributes.overallRating*1.5)+(self.rosterDict['de'].attributes.overallRating*1.2))/5)
        self.defenseRating = round(((self.runDefenseRating*1.8)+(self.passDefenseRating*2.2))/4)
        self.offenseRating = round(((self.rosterDict['qb'].attributes.overallRating*1.2)+(self.rosterDict['rb'].attributes.overallRating*1.1)+(self.rosterDict['wr1'].attributes.overallRating*.5)+(self.rosterDict['wr2'].attributes.overallRating*.5)+(self.rosterDict['te'].attributes.overallRating*.9)+(self.rosterDict['k'].attributes.overallRating*.8))/5)
        self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))
        self.gamePassDefenseRating = round(((self.rosterDict['db1'].attributes.overallRating*1.2)+(self.rosterDict['db2'].attributes.overallRating*1.2)+(self.rosterDict['lb'].attributes.overallRating*.8)+(self.rosterDict['dl'].attributes.overallRating*.8)+(self.rosterDict['de'].attributes.overallRating*1))/5)
        self.gameRunDefenseRating = round(((self.rosterDict['db1'].attributes.overallRating*.5)+(self.rosterDict['db2'].attributes.overallRating*.5)+(self.rosterDict['lb'].attributes.overallRating*1.3)+(self.rosterDict['dl'].attributes.overallRating*1.5)+(self.rosterDict['de'].attributes.overallRating*1.2))/5)
        self.gameDefenseRating = round(((self.gameRunDefenseRating*1.5)+(self.gamePassDefenseRating*1.7))/3)
        if self.defenseSeasonPerformanceRating > 0:
            self.defenseOverallRating = round(((self.defenseRating*.8)+(self.defenseSeasonPerformanceRating*1.2))/2)
        else:
            self.defenseOverallRating = self.defenseRating

    def updateDefense(self):

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
        self.seasonTeamStats['Offense']['avgRunTds'] = round(statistics.mean(offenseRunTdsList),2)
        self.seasonTeamStats['Offense']['avgPassTds'] = round(statistics.mean(offensePassTdsList),2)
        self.seasonTeamStats['Offense']['avgTds'] = round(statistics.mean(offenseTdsList),2)
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

    def updateGameDetermination(self, value):
        self._gameDefenseDetermination = round(self._gameDefenseDetermination + value, 2)

    def inGamePush(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(.01)
        self.updateGameDetermination(.01)

    def teamUnderPerform(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(-.01)
            player.updateInGameConfidence(-.01)
        self.updateGameDetermination(-.01)
        self.updateGameConfidence(-.01)

    def teamOverPerform(self):
        for player in self.rosterDict.values():
            player.updateInGameDetermination(.01)
            player.updateInGameConfidence(.01)
        self.updateGameDetermination(.01)
        self.updateGameConfidence(.01)

    def resetConfidence(self):
        for player in self.rosterDict.values():
            player.gameAttributes.confidence = 1
            player.updateInGameRating
        #self._gameDefenseConfidence = 1

    def resetDetermination(self):
        for player in self.rosterDict.values():
            player.gameAttributes.determination = 1
            player.updateInGameRating
        #self._gameDefenseDetermination = 1

    def resetGameEnergy(self):
        for player in self.rosterDict.values():
            player: FloosPlayer.Player
            player.energy = 100
