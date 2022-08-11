import json
import os
from random import randint, seed, shuffle
import copy
import asyncio
from secrets import choice
from unicodedata import name
import numpy as np
from scipy import stats
import statistics
import floosball_game as FloosGame
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_methods as FloosMethods
 

__version__ = '0.1.2_alpha'

config = None
totalSeasons = 0
seasonsPlayed = 0
activePlayerList = []
unusedNamesList = []
freeAgentList = []
rookieDraftList = []
retiredPlayersList = []

activeQbList = []
activeRbList = []
activeWrList = []
activeTeList = []
activeKList = []
playerLists = [activeQbList, activeRbList, activeWrList, activeTeList, activeKList]

rookieDraftHistoryDict = {}
rookieDraftOrder = []
freeAgencyHistoryDict = {}
teamList = []
divisionList = []   
scheduleList = []
seasonList = []
activeSeason = None
scheduleScheme = [
    ('1112','1314','2122','2324','3132','3334','4142','4344'),
    ('1311','1412','2321','2422','3331','3432','4341','4442'),
    ('1114','1213','2124','2223','3134','3233','4144','4243'),

    ('1121','1222','1323','1424','3141','3242','3343','3444'),
    ('2112','2211','2314','2413','4132','4231','4334','4433'),
    ('1123','1224','1321','1422','3143','3244','3341','3442'),
    ('2114','2213','2312','2411','4134','4233','4332','4431'),

    ('1131','1232','1333','1434','2141','2242','2343','2444'),
    ('3112','3211','3314','3413','4122','4221','4324','4423'),
    ('1133','1234','1331','1432','2143','2244','2341','2442'),
    ('3114','3213','3312','3411','4124','4223','4322','4421'),

    ('1141','1242','1343','1444','2131','2232','2333','2434'),
    ('4112','4211','4314','4413','3122','3221','3324','3423'),
    ('1143','1244','1341','1442','2133','2234','2331','2432'),
    ('4114','4213','4312','4411','3124','3223','3322','3421'),

    ('1211','1413','2221','2423','3231','3433','4241','4443'),
    ('1113','1214','2123','2224','3133','3234','4143','4244'),
    ('1411','1312','2421','2322','3431','3332','4441','4342')]
    

class Division:
    def __init__(self, name):
        self.name = name
        self.teamList = []

class Season:
    def __init__(self):
        self.currentSeason = seasonsPlayed + 1
        self.activeGames = None
        self.currentWeek = None

    def createSchedule(self):
        numOfWeeks = len(scheduleScheme)
        scheduleList.clear()
        for week in range(0, numOfWeeks):
            gameList = []
            numOfGames = int(len(teamList)/2)
            # print("\n-------------------------------------------------\n")
            # print("Week {0}".format(week + 1))
            for x in range(0, numOfGames):
                game = scheduleScheme[week][x]
                homeTeam = divisionList[int(game[0]) - 1].teamList[int(game[1]) - 1]
                awayTeam = divisionList[int(game[2]) - 1].teamList[int(game[3]) - 1]
                newGame = FloosGame.Game(homeTeam,awayTeam)
                newGame.id = 's{0}w{1}g{2}'.format(self.currentSeason, week+1, x+1)
                newGame.status = FloosGame.GameStatus.Scheduled
                gameList.append(newGame)
                # print("{0} v. {1}".format(awayTeam.name, homeTeam.name))
            scheduleList.append(gameList)

    def getSeasonStats(self):
        dict = {}
        y = 0
        jsonFile = open("data/teamData.json", "w+")
        for team in teamList:
            team: FloosTeam.Team
            for player in team.rosterDict.values():
                player: FloosPlayer.Player
                player.seasonsPlayed += 1
                if 'passComp' in player.seasonStatsDict and player.seasonStatsDict['passYards'] > 0:
                    player.careerStatsDict['passAtt'] += player.seasonStatsDict['passAtt']
                    player.careerStatsDict['passComp'] += player.seasonStatsDict['passComp']
                    player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                    player.careerStatsDict['ints'] += player.seasonStatsDict['ints']
                    player.careerStatsDict['passYards'] += player.seasonStatsDict['passYards']
                    player.careerStatsDict['totalYards'] += player.seasonStatsDict['passYards']
                    player.careerStatsDict['ypc'] = round(player.careerStatsDict['passYards']/player.careerStatsDict['passComp'])
                    player.careerStatsDict['passCompPerc'] = round((player.careerStatsDict['passComp']/player.careerStatsDict['passAtt'])*100)
                    team.seasonTeamStats['Offense']['passYards'] += player.seasonStatsDict['passYards']
                if 'receptions' in player.seasonStatsDict and player.seasonStatsDict['rcvYards'] > 0:
                    player.careerStatsDict['receptions'] += player.seasonStatsDict['receptions']
                    player.careerStatsDict['passTargets'] += player.seasonStatsDict['passTargets']
                    player.careerStatsDict['rcvYards'] += player.seasonStatsDict['rcvYards']
                    player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                    player.careerStatsDict['totalYards'] += player.seasonStatsDict['rcvYards']
                    if player.careerStatsDict['receptions'] > 0:
                        player.careerStatsDict['ypr'] = round(player.careerStatsDict['rcvYards']/player.careerStatsDict['receptions'])
                        player.careerStatsDict['rcvPerc'] = round((player.careerStatsDict['receptions']/player.careerStatsDict['passTargets'])*100)
                if 'carries' in player.seasonStatsDict and player.seasonStatsDict['runYards'] > 0:
                    player.careerStatsDict['carries'] += player.seasonStatsDict['carries']
                    player.careerStatsDict['runYards'] += player.seasonStatsDict['runYards']
                    player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                    player.careerStatsDict['fumblesLost'] += player.seasonStatsDict['fumblesLost']
                    player.careerStatsDict['totalYards'] += player.seasonStatsDict['runYards']
                    player.careerStatsDict['ypc'] = round(player.careerStatsDict['runYards']/player.careerStatsDict['carries'])
                    team.seasonTeamStats['Offense']['runYards'] += player.seasonStatsDict['runYards']
                if 'fgs' in player.seasonStatsDict:
                    if player.seasonStatsDict['fgs'] > 0:
                        player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                    else:
                        player.seasonStatsDict['fgPerc'] = 0

                    player.careerStatsDict['fgAtt'] += player.seasonStatsDict['fgAtt']
                    player.careerStatsDict['fgs'] += player.seasonStatsDict['fgs']
                    if player.careerStatsDict['fgs'] > 0:
                        player.careerStatsDict['fgPerc'] = round((player.careerStatsDict['fgs']/player.careerStatsDict['fgAtt'])*100)
                    else:
                        player.careerStatsDict['fgPerc'] = 0
                if 'tds' in player.seasonStatsDict:
                    team.seasonTeamStats['Offense']['tds'] += player.seasonStatsDict['tds']

            for player in team.reserveRosterDict.values():
                player: FloosPlayer.Player
                if player is not None and player.gamesPlayed > 0:
                    player.seasonsPlayed += 1
                    if 'passComp' in player.seasonStatsDict and player.seasonStatsDict['passYards'] > 0:
                        player.careerStatsDict['passAtt'] += player.seasonStatsDict['passAtt']
                        player.careerStatsDict['passComp'] += player.seasonStatsDict['passComp']
                        player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                        player.careerStatsDict['ints'] += player.seasonStatsDict['ints']
                        player.careerStatsDict['passYards'] += player.seasonStatsDict['passYards']
                        player.careerStatsDict['totalYards'] += player.seasonStatsDict['passYards']
                        player.careerStatsDict['ypc'] = round(player.careerStatsDict['passYards']/player.careerStatsDict['passComp'])
                        player.careerStatsDict['passCompPerc'] = round((player.careerStatsDict['passComp']/player.careerStatsDict['passAtt'])*100)
                        team.seasonTeamStats['Offense']['passYards'] += player.seasonStatsDict['passYards']
                    if 'receptions' in player.seasonStatsDict and player.seasonStatsDict['rcvYards'] > 0:
                        player.careerStatsDict['receptions'] += player.seasonStatsDict['receptions']
                        player.careerStatsDict['passTargets'] += player.seasonStatsDict['passTargets']
                        player.careerStatsDict['rcvYards'] += player.seasonStatsDict['rcvYards']
                        player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                        player.careerStatsDict['totalYards'] += player.seasonStatsDict['rcvYards']
                        if player.careerStatsDict['receptions'] > 0:
                            player.careerStatsDict['ypr'] = round(player.careerStatsDict['rcvYards']/player.careerStatsDict['receptions'])
                            player.careerStatsDict['rcvPerc'] = round((player.careerStatsDict['receptions']/player.careerStatsDict['passTargets'])*100)
                    if 'carries' in player.seasonStatsDict and player.seasonStatsDict['runYards'] > 0:
                        player.careerStatsDict['carries'] += player.seasonStatsDict['carries']
                        player.careerStatsDict['runYards'] += player.seasonStatsDict['runYards']
                        player.careerStatsDict['tds'] += player.seasonStatsDict['tds']
                        player.careerStatsDict['fumblesLost'] += player.seasonStatsDict['fumblesLost']
                        player.careerStatsDict['totalYards'] += player.seasonStatsDict['runYards']
                        player.careerStatsDict['ypc'] = round(player.careerStatsDict['runYards']/player.careerStatsDict['carries'])
                        team.seasonTeamStats['Offense']['runYards'] += player.seasonStatsDict['runYards']
                    if 'fgs' in player.seasonStatsDict:
                        if player.seasonStatsDict['fgs'] > 0:
                            player.seasonStatsDict['fgPerc'] = round((player.seasonStatsDict['fgs']/player.seasonStatsDict['fgAtt'])*100)
                        else:
                            player.seasonStatsDict['fgPerc'] = 0

                        player.careerStatsDict['fgAtt'] += player.seasonStatsDict['fgAtt']
                        player.careerStatsDict['fgs'] += player.seasonStatsDict['fgs']
                        if player.careerStatsDict['fgs'] > 0:
                            player.careerStatsDict['fgPerc'] = round((player.careerStatsDict['fgs']/player.careerStatsDict['fgAtt'])*100)
                        else:
                            player.careerStatsDict['fgPerc'] = 0
                    if 'tds' in player.seasonStatsDict:
                        team.seasonTeamStats['Offense']['tds'] += player.seasonStatsDict['tds']



            team.seasonTeamStats['Offense']['totalYards'] = team.seasonTeamStats['Offense']['passYards'] + team.seasonTeamStats['Offense']['runYards']
            team.seasonTeamStats['winPerc'] = round(team.seasonTeamStats['wins']/(team.seasonTeamStats['wins']+team.seasonTeamStats['losses']),3)
            team.allTimeTeamStats['wins'] += team.seasonTeamStats['wins']
            team.allTimeTeamStats['losses'] += team.seasonTeamStats['losses']
            team.allTimeTeamStats['Offense']['tds'] += team.seasonTeamStats['Offense']['tds']
            team.allTimeTeamStats['Offense']['passYards'] += team.seasonTeamStats['Offense']['passYards']
            team.allTimeTeamStats['Offense']['runYards'] += team.seasonTeamStats['Offense']['runYards']
            team.allTimeTeamStats['Offense']['totalYards'] += team.seasonTeamStats['Offense']['totalYards']
            team.allTimeTeamStats['Defense']['sacks'] += team.seasonTeamStats['Defense']['sacks']
            team.allTimeTeamStats['Defense']['ints'] += team.seasonTeamStats['Defense']['ints']
            team.allTimeTeamStats['Defense']['fumRec'] += team.seasonTeamStats['Defense']['fumRec']
            team.allTimeTeamStats['winPerc'] = round(team.allTimeTeamStats['wins']/(team.allTimeTeamStats['wins']+team.allTimeTeamStats['losses']),3)


            y += 1
            dict[y] = FloosMethods._prepare_for_serialization(team)

        jsonFile.write(json.dumps(dict, indent=4))
        jsonFile.close()

        savePlayerData()

    def clearSeasonStats(self):
        for team in teamList:
            team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)

            team.rosterDict['qb'].seasonStatsDict = copy.deepcopy(FloosPlayer.qbStatsDict)
            team.rosterDict['rb'].seasonStatsDict = copy.deepcopy(FloosPlayer.rbStatsDict)
            team.rosterDict['wr'].seasonStatsDict = copy.deepcopy(FloosPlayer.wrStatsDict)
            team.rosterDict['te'].seasonStatsDict = copy.deepcopy(FloosPlayer.wrStatsDict)
            team.rosterDict['k'].seasonStatsDict = copy.deepcopy(FloosPlayer.kStatsDict)
            team.rosterDict['qb'].gamesPlayed = 0
            team.rosterDict['rb'].gamesPlayed = 0
            team.rosterDict['wr'].gamesPlayed = 0
            team.rosterDict['te'].gamesPlayed = 0
            team.rosterDict['k'].gamesPlayed = 0

            if team.reserveRosterDict['qb'] is not None:
                team.reserveRosterDict['qb'].seasonStatsDict = copy.deepcopy(FloosPlayer.qbStatsDict)
                team.reserveRosterDict['qb'].gamesPlayed = 0
            if team.reserveRosterDict['rb'] is not None:
                team.reserveRosterDict['rb'].seasonStatsDict = copy.deepcopy(FloosPlayer.rbStatsDict)
                team.reserveRosterDict['rb'].gamesPlayed = 0
            if team.reserveRosterDict['wr'] is not None:
                team.reserveRosterDict['wr'].seasonStatsDict = copy.deepcopy(FloosPlayer.wrStatsDict)
                team.reserveRosterDict['wr'].gamesPlayed = 0
            if team.reserveRosterDict['te'] is not None:
                team.reserveRosterDict['te'].seasonStatsDict = copy.deepcopy(FloosPlayer.wrStatsDict)
                team.reserveRosterDict['te'].gamesPlayed = 0
            if team.reserveRosterDict['k'] is not None:
                team.reserveRosterDict['k'].seasonStatsDict = copy.deepcopy(FloosPlayer.kStatsDict)
                team.reserveRosterDict['k'].gamesPlayed = 0
 

    async def startSeason(self):
        global rookieDraftOrder
        weekDict = {}
        seasonDict = {}
        gameDictTemp = {}
        rookieDraftOrder = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)

        weekFilePath = '{}/games'.format(strCurrentSeason)
        if os.path.isdir(weekFilePath):
            for f in os.listdir(weekFilePath):
                os.remove(os.path.join(weekFilePath, f))
        else:
            if not os.path.isdir(strCurrentSeason):
                os.mkdir(strCurrentSeason)
                os.mkdir('{}/games'.format(strCurrentSeason))
            else:
                os.mkdir('{}/games'.format(strCurrentSeason))

        for week in scheduleList:
            #print("\n-------------------------------------------------\n")
            #print("Week {0}".format(scheduleList.index(week)+1))
            self.currentWeek = scheduleList.index(week)+1
            currentWeekText = 'Week {}'.format(self.currentWeek)
            self.activeGames = week
            gameDict = gameDictTemp.copy()

            gamesList = [week[game].playGame() for game in range(0,len(week))]
            await asyncio.wait(gamesList)

            for game in range(0,len(week)):
                strGame = 'Game {}'.format(game + 1)
                week[game].postgame()
                gameResults = week[game].gameDict
                gameDict[strGame] = gameResults
            weekDict = FloosMethods._prepare_for_serialization(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()
            
            for division in divisionList:
                list.sort(division.teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
            getPerformanceRating()
            sortPlayers()
            await asyncio.sleep(30)

        #seasonDict['games'] = weekDict
        leagueChampion = await self.playPlayoffs()

        self.getSeasonStats()

        standingsDict = {}
        divStandingsTempDict = {}
        jsonFile = open("data/divisionData.json", "w+")
        for division in divisionList:
            list.sort(division.teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
            divStandingsDict = divStandingsTempDict.copy()
            #print("\n{0} Division".format(division.name))
            for team in division.teamList:
                divStandingsDict[team.name] = '{0} - {1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            standingsDict[division.name] = divStandingsDict

        jsonFile.write(json.dumps(standingsDict, indent=4))
        jsonFile.close()

        seasonDict['standings'] = standingsDict
        seasonDict['champion'] = leagueChampion.name

        _serialzedDict = FloosMethods._prepare_for_serialization(seasonDict)

        if os.path.isdir(strCurrentSeason):
            for f in os.listdir(strCurrentSeason):
                if os.path.isfile(os.path.join(strCurrentSeason, f)):
                    os.remove(os.path.join(strCurrentSeason, f))
        else:
            os.mkdir(strCurrentSeason)
        jsonFile = open(os.path.join(strCurrentSeason, 'seasonData.json'), "w+")
        jsonFile.write(json.dumps(_serialzedDict, indent=4))
        jsonFile.close()

        teamDict = {}
        for team in teamList:
            team: FloosTeam.Team
            dict = {}
            team.saveRoster()
            dict['id'] = team.id
            dict['rating'] = team.overallRating
            dict['offenseRating'] = team.offenseRating
            dict['defenseRating'] = team.defenseRating
            dict['runDefenseRating'] = team.runDefenseRating
            dict['passDefenseRating'] = team.passDefenseRating
            dict['leagueChampionships'] = team.leagueChampionships
            dict['playoffAppearances'] = team.playoffAppearances
            dict['seasonTeamStats'] = team.seasonTeamStats
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                player: FloosPlayer.Player
                playerDict = {}
                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['tier'] = player.playerTier.name
                playerDict['overallRating'] = player.attributes.overallRating
                playerDict['seasonsPlayed'] = player.seasonsPlayed
                playerDict['term'] = player.term
                playerDict['seasonPerformanceRating'] = player.seasonPerformanceRating
                playerDict['seasonStatsDict'] = player.seasonStatsDict
                rosterDict[pos] = playerDict
            dict['roster'] = rosterDict
            teamDict[team.name] = dict
        jsonFile = open(os.path.join(strCurrentSeason, 'teamData.json'), "w+")
        jsonFile.write(json.dumps(teamDict, indent=4))
        jsonFile.close()
        list.sort(teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=False)
        self.clearSeasonStats()

    async def playPlayoffs(self):
        #print("\nFLOOSBALL DIVISIONAL ROUND")
        champ = None
        playoffDict = {}
        playoffTeamsList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)
        x = 0
        for division in divisionList:
            list.sort(division.teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
            division.teamList[0].playoffAppearances += 1
            division.teamList[1].playoffAppearances += 1
            playoffTeamsList.append(division.teamList[0])
            playoffTeamsList.append(division.teamList[1])
            rookieDraftOrder.append(division.teamList[2])
            rookieDraftOrder.append(division.teamList[3])

        list.sort(rookieDraftOrder, key=lambda team: team.seasonTeamStats['winPerc'], reverse=False)

        numOfRounds = FloosMethods.getPower(2, len(playoffTeamsList))

        for x in range(numOfRounds):

            playoffGamesList = []
            playoffGamesTaskList = []
            currentRound = x + 1
            hiSeed = 0
            lowSeed = len(playoffTeamsList) - 1
            gameNumber = 1

            if x == 0:
                for division in divisionList:
                    division: Division
                    newGame = FloosGame.Game(division.teamList[0], division.teamList[1])
                    newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
                    newGame.status = FloosGame.GameStatus.Scheduled
                    playoffGamesList.append(newGame)
                    playoffGamesTaskList.append(newGame.playGame())
                    gameNumber += 1
            else:
                list.sort(playoffTeamsList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
                while lowSeed > hiSeed:
                    newGame = FloosGame.Game(playoffTeamsList[hiSeed], playoffTeamsList[lowSeed])
                    newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
                    newGame.status = FloosGame.GameStatus.Scheduled
                    playoffGamesList.append(newGame)
                    playoffGamesTaskList.append(newGame.playGame())
                    hiSeed += 1
                    lowSeed -= 1
                    gameNumber += 1
            
            scheduleList.append(playoffGamesList)

            self.activeGames = playoffGamesList
            if x < numOfRounds - 1:
                self.currentWeek = 'Playoffs Round {}'.format(x+1)
            else:
                self.currentWeek = 'Championship'
            await asyncio.wait(playoffGamesTaskList)

            for game in playoffGamesList:
                game: FloosGame.Game
                game.postgame()
                gameResults = game.gameDict
                if len(playoffGamesList) == 1:
                    playoffTeamsList.clear()
                    game.winningTeam.leagueChampionships += 1
                    champ = game.winningTeam
                    playoffDict['Championship'] = gameResults
                    rookieDraftOrder.append(game.losingTeam)
                    rookieDraftOrder.append(champ)
                else:
                    playoffDict[game.id] = gameResults
                    for team in playoffTeamsList:
                        if team.name == gameResults['losingTeam']:
                            rookieDraftOrder.append(team)
                            playoffTeamsList.remove(team)
                            break

            jsonFile = open(os.path.join('{}/games'.format(strCurrentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()
            if x < numOfRounds - 1:
                sortPlayers()
                await asyncio.sleep(30)

        return champ

def getPlayerTerm(tier: FloosPlayer.PlayerTier):
        if tier is FloosPlayer.PlayerTier.SuperStar:
            return randint(4,6)
        elif tier is FloosPlayer.PlayerTier.Elite:
            return randint(3,5)
        elif tier is FloosPlayer.PlayerTier.AboveAverage:
            return randint(2,4)
        elif tier is FloosPlayer.PlayerTier.Average:
            return randint(1,3)
        else:
            return 1

def playerDraft():
    draftOrderList = []
    draftQueueList = teamList.copy()
    playerDraftList = activePlayerList.copy()
    rounds = 5

    draftQbList : list[FloosPlayer.Player] = []
    draftRbList : list[FloosPlayer.Player] = []
    draftWrList : list[FloosPlayer.Player] = []
    draftTeList : list[FloosPlayer.Player] = []
    draftKList : list[FloosPlayer.Player] = []

    for player in activePlayerList:
        if player.position.value == 1:
            draftQbList.append(player)
        elif player.position.value == 2:
            draftRbList.append(player)
        elif player.position.value == 3:
            draftWrList.append(player)
        elif player.position.value == 4:
            draftTeList.append(player)
        elif player.position.value == 5:
            draftKList.append(player)
    
    list.sort(draftQbList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(draftRbList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(draftWrList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(draftTeList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(draftKList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(playerDraftList, key=lambda player: player.attributes.overallRating, reverse=True)


    for x in range(len(teamList)):
        rand = randint(0,len(draftQueueList) - 1)
        draftOrderList.insert(x, draftQueueList[rand])
        draftQueueList.pop(rand)

    for x in range(1, int(rounds+1)):
        #print('\nRound {0}'.format(x))
        for team in draftOrderList:
            openPosList = []
            selectedPlayer = None
            bestAvailablePlayer: FloosPlayer.Player = playerDraftList[0]
            if x == 1:
                if bestAvailablePlayer.position.value == 1:
                    selectedPlayer = draftQbList.pop(0)
                    team.rosterDict['qb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 2:
                    selectedPlayer = draftRbList.pop(0)
                    team.rosterDict['rb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 3:
                    selectedPlayer = draftWrList.pop(0)
                    team.rosterDict['wr'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 4:
                    selectedPlayer = draftTeList.pop(0)
                    team.rosterDict['te'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 5:
                    selectedPlayer = draftKList.pop(0)
                    team.rosterDict['k'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
            else:
                if team.rosterDict['qb'] is None:
                    openPosList.append(FloosPlayer.Position.QB.value)
                if team.rosterDict['rb'] is None:
                    openPosList.append(FloosPlayer.Position.RB.value)
                if team.rosterDict['wr'] is None:
                    openPosList.append(FloosPlayer.Position.WR.value)
                if team.rosterDict['te'] is None:
                    openPosList.append(FloosPlayer.Position.TE.value)
                if team.rosterDict['k'] is None:
                    openPosList.append(FloosPlayer.Position.K.value)
                z = choice(openPosList)
                if z == FloosPlayer.Position.QB.value:
                    selectedPlayer = draftQbList.pop(0)
                    team.rosterDict['qb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.RB.value:
                    selectedPlayer = draftRbList.pop(0)
                    team.rosterDict['rb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.WR.value:
                    selectedPlayer = draftWrList.pop(0)
                    team.rosterDict['wr'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.TE.value:
                    selectedPlayer = draftTeList.pop(0)
                    team.rosterDict['te'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.K.value:
                    selectedPlayer = draftKList.pop(0)
                    team.rosterDict['k'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)

            selectedPlayer.team = team
            selectedPlayer.term = getPlayerTerm(selectedPlayer.playerTier)
                
    for player in draftQbList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftRbList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftWrList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftTeList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftKList:
        player.team = 'Free Agent'
        freeAgentList.append(player)


def savePlayerData():
    playerDict = {}
    tempPlayerDict = {}
    for x in range(len(activePlayerList)):
        key = 'Player {}'.format(x + 1)
        newDict = tempPlayerDict.copy()
        newDict['name'] = activePlayerList[x].name
        newDict['id'] = activePlayerList[x].id
        newDict['tier'] = activePlayerList[x].playerTier.name
        newDict['team'] = activePlayerList[x].team
        newDict['position'] = activePlayerList[x].position
        newDict['seasonsPlayed'] = activePlayerList[x].seasonsPlayed
        newDict['term'] = activePlayerList[x].term
        newDict['attributes'] = activePlayerList[x].attributes
        newDict['careerStats'] = activePlayerList[x].careerStatsDict
        playerDict[key] = newDict

    dict = FloosMethods._prepare_for_serialization(playerDict)
    jsonFile = open("data/playerData.json", "w+") 
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()

    
def getPlayers(_config):

    if os.path.exists("data/playerData.json"):
        with open('data/playerData.json') as jsonFile:
            playerData = json.load(jsonFile)
            for x in playerData:
                player = playerData[x]
                if player['position'] == 'QB':
                    newPlayer = FloosPlayer.PlayerQB()
                    activeQbList.append(newPlayer)
                elif player['position'] == 'RB':
                    newPlayer = FloosPlayer.PlayerRB()
                    activeRbList.append(newPlayer)
                elif player['position'] == 'WR':
                    newPlayer = FloosPlayer.PlayerWR()
                    activeWrList.append(newPlayer)
                elif player['position'] == 'TE':
                    newPlayer = FloosPlayer.PlayerTE()
                    activeTeList.append(newPlayer)
                elif player['position'] == 'K':
                    newPlayer = FloosPlayer.PlayerK()
                    activeKList.append(newPlayer)
                    newPlayer.attributes.skillRating = player['attributes']['skillRating']
                    newPlayer.attributes.legStrength = player['attributes']['legStrength']
                    newPlayer.attributes.accuracy = player['attributes']['accuracy']

                newPlayer.name = player['name']
                newPlayer.id = player['id']
                newPlayer.team = player['team']
                newPlayer.seasonsPlayed = player['seasonsPlayed']
                newPlayer.term = player['term']
                newPlayer.attributes.overallRating = player['attributes']['overallRating']
                newPlayer.attributes.skillRating = player['attributes']['skillRating']
                newPlayer.attributes.speed = player['attributes']['speed']
                newPlayer.attributes.hands = player['attributes']['hands']
                newPlayer.attributes.agility = player['attributes']['agility']
                newPlayer.attributes.power = player['attributes']['power']
                newPlayer.attributes.armStrength = player['attributes']['armStrength']
                newPlayer.attributes.accuracy = player['attributes']['accuracy']
                newPlayer.attributes.legStrength = player['attributes']['legStrength']

                newPlayer.attributes.confidence = player['attributes']['confidence']
                newPlayer.attributes.determination = player['attributes']['determination']
                newPlayer.attributes.discipline = player['attributes']['discipline']
                newPlayer.attributes.focus = player['attributes']['focus']
                newPlayer.attributes.instinct = player['attributes']['instinct']
                newPlayer.attributes.creativity = player['attributes']['creativity']
                newPlayer.attributes.luck = player['attributes']['luck']
                newPlayer.attributes.attitude = player['attributes']['attitude']
                newPlayer.attributes.playMakingAbility = player['attributes']['playMakingAbility']

                newPlayer.careerStatsDict = player['careerStats']

                newPlayer.careerStatsDict = player['careerStats']
                activePlayerList.append(newPlayer)

        jsonFile.close()

    else:
        numOfPlayers = 100
        id = 1
        for x in _config['players']:
            unusedNamesList.append(x)
        for x in range(numOfPlayers):
            player = None
            y = x%5
            if y == 0:
                player = FloosPlayer.PlayerQB()
                activeQbList.append(player)
            elif y == 1:
                player = FloosPlayer.PlayerRB()
                activeRbList.append(player)
            elif y == 2:
                player = FloosPlayer.PlayerWR()
                activeWrList.append(player)
            elif y == 3:
                player = FloosPlayer.PlayerTE()
                activeTeList.append(player)
            elif y == 4:
                player = FloosPlayer.PlayerK()
                activeKList.append(player)
            player.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
            player.id = id
            activePlayerList.append(player)
            id += 1
    
    sortPlayers()


def getTeams(_config):

    if os.path.exists("data/teamData.json"):
        with open('data/teamData.json') as jsonFile:
            teamData = json.load(jsonFile)
            for x in teamData:
                team = teamData[x]
                newTeam = FloosTeam.Team(team['name'])
                newTeam.id = team['id']
                newTeam.offenseRating = team['offenseRating']
                newTeam.runDefenseRating = team['runDefenseRating']
                newTeam.passDefenseRating = team['passDefenseRating']
                newTeam.defenseRating = team['defenseRating']
                newTeam.defenseLuck = team['defenseLuck']
                newTeam.defenseDiscipline = team['defenseDiscipline']
                newTeam.overallRating = team['overallRating']
                newTeam.allTimeTeamStats = team['allTimeTeamStats']
                newTeam.leagueChampionships = team['leagueChampionships']
                newTeam.playoffAppearances = team['playoffAppearances']


                teamRoster = team['rosterDict']
                for pos, player in teamRoster.items():
                    for z in activePlayerList:
                        z:FloosPlayer.Player
                        if z.name == player['name']:
                            newTeam.rosterDict[pos] = z
                            break

                teamReserveRoster = team['reserveRosterDict']
                for pos, player in teamReserveRoster.items():
                    for z in activePlayerList:
                        z:FloosPlayer.Player
                        if z.name == player['name']:
                            newTeam.reserveRosterDict[pos] = z
                            break

                teamList.append(newTeam)

    else:
        id = 1
        for x in _config['teams']:
            team = FloosTeam.Team(x)
            team.id = id
            teamList.append(team)
            id += 1

def getDivisons(_config):

    if os.path.exists("data/divisionData.json"):
        with open('data/divisionData.json') as jsonFile:
            divisionData = json.load(jsonFile)
            for x in divisionData:
                division = Division(x)
                jteamList = divisionData[x]
                for team in jteamList:
                    for y in teamList:
                        if y.name == team:
                            division.teamList.append(y)
                            break
                divisionList.append(division)


    else:
        for x in _config['divisions']:
            division = Division(x)
            divisionList.append(division)

def initTeams():
    dict = {}
    y = 0
    jsonFile = open("data/teamData.json", "w+")
    for team in teamList:
        team: FloosTeam.Team
        team.setupTeam()
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['id'] = team.id
        teamDict['offenseRating'] = team.offenseRating
        teamDict['runDefenseRating'] = team.runDefenseRating
        teamDict['passDefenseRating'] = team.passDefenseRating
        teamDict['defenseRating'] = team.defenseRating
        teamDict['defenseLuck'] = team.defenseLuck
        teamDict['defenseDiscipline'] = team.defenseDiscipline
        teamDict['overallRating'] = team.overallRating
        teamDict['allTimeTeamStats'] = team.allTimeTeamStats
        teamDict['leagueChampionships'] = team.leagueChampionships
        teamDict['playoffAppearances'] = team.playoffAppearances

        rosterDict = {}
        
        for pos, player in team.rosterDict.items():
            player:FloosPlayer.Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['tier'] = player.playerTier.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['term'] = player.term
            playerDict['seasonsPlayed'] = player.seasonsPlayed
            playerDict['careerStatsDict'] = player.careerStatsDict
            rosterDict[pos] = playerDict

        reserveRosterDict = {}
        
        for pos, player in team.reserveRosterDict.items():
            if player is not None:
                player:FloosPlayer.Player
                playerDict = {}
                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['tier'] = player.playerTier.name
                playerDict['overallRating'] = player.attributes.overallRating
                playerDict['term'] = player.term
                playerDict['seasonsPlayed'] = player.seasonsPlayed
                playerDict['careerStatsDict'] = player.careerStatsDict
                reserveRosterDict[pos] = playerDict
        teamDict['rosterDict'] = rosterDict
        teamDict['reserveRosterDict'] = reserveRosterDict

        y += 1
        dict[y] = teamDict

    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()


def initPlayers():
    pass

def sortPlayers():
    for playerList in playerLists:
        ratingList = []
        for player in playerList:
            ratingList.append(player.attributes.overallRating)

        starPerc = np.percentile(ratingList, 98)
        elitePerc = np.percentile(ratingList, 90)
        aboveAvgPerc = np.percentile(ratingList, 70)
        avgPerc = np.percentile(ratingList, 40)

        for player in playerList:
            if player.attributes.overallRating >= starPerc:
                player.playerTier = FloosPlayer.PlayerTier.SuperStar
            elif player.attributes.overallRating >= elitePerc:
                player.playerTier = FloosPlayer.PlayerTier.Elite
            elif player.attributes.overallRating >= aboveAvgPerc:
                player.playerTier = FloosPlayer.PlayerTier.AboveAverage
            elif player.attributes.overallRating >= avgPerc:
                player.playerTier = FloosPlayer.PlayerTier.Average
            else:
                player.playerTier = FloosPlayer.PlayerTier.BelowAverage

        
def initDivisions():
    tempTeamList = teamList.copy()
    numOfDivisions = len(divisionList)
    y = 0
    while len(tempTeamList) > 0:
        x = randint(0,len(tempTeamList)-1)
        # if len(tempTeamList) % 2 == 0:
        #     divisionList[0].teamList.append(tempTeamList[x])
        # else:
        #     divisionList[1].teamList.append(tempTeamList[x])
        divisionList[y].teamList.append(tempTeamList[x])
        y += 1
        if y == numOfDivisions:
            y = 0
        tempTeamList.remove(tempTeamList[x])
    for division in divisionList:
        for team in division.teamList:
            team.division = division.name

def offseason():
    freeAgencyDict = {}
    for player in freeAgentList:
        player: FloosPlayer.Player
        player.freeAgentYears += 1

        if player.freeAgentYears > 5:
            x = randint(1,10)
            if x > 6:
                player.team = 'Retired'
                retiredPlayersList.append(player)
                freeAgentList.remove(player)
                activePlayerList.remove(player)
                if player.position is FloosPlayer.Position.QB:
                    activeQbList.remove(player)
                elif player.position is FloosPlayer.Position.RB:
                    activeRbList.remove(player)
                elif player.position is FloosPlayer.Position.WR:
                    activeWrList.remove(player)
                elif player.position is FloosPlayer.Position.TE:
                    activeTeList.remove(player)
                elif player.position is FloosPlayer.Position.K:
                    activeKList.remove(player)

                name = player.name
                if name.endswith('IV'):
                    name = name.replace('IV', 'V')
                elif name.endswith('VIII'):
                    name = name.replace('VIII', 'IX')
                elif name.endswith('IX'):
                    name = name.replace('IX', 'X')
                elif name.endswith('III'):
                    name = name.replace('III', 'IV')
                elif name.endswith('V') or name.endswith('II') or name.endswith('X'):
                    name += 'I'
                else:
                    name += ' II'
                unusedNamesList.append(name)


    for team in teamList:

        for k,v in team.rosterDict.items():
            v: FloosPlayer.Player
            v.term -= 1
            if v.term == 0:
                retirePlayerBool = None
                if v.seasonsPlayed > 15:
                    x = randint(1,10)
                    if x > 4:
                        retirePlayerBool = True
                elif v.seasonsPlayed > 10:
                    x = randint(1,10)
                    if x > 6:
                        retirePlayerBool = True
                elif v.seasonsPlayed >= 7:
                    x = randint(1,10)
                    if x > 8:
                        retirePlayerBool = True
                else:
                    retirePlayerBool = False

                if retirePlayerBool:
                    v.previousTeam = team.name
                    v.team = 'Retired'
                    retiredPlayersList.append(v)
                    activePlayerList.remove(v)
                    if v.position is FloosPlayer.Position.QB:
                        activeQbList.remove(v)
                    elif v.position is FloosPlayer.Position.RB:
                        activeRbList.remove(v)
                    elif v.position is FloosPlayer.Position.WR:
                        activeWrList.remove(v)
                    elif v.position is FloosPlayer.Position.TE:
                        activeTeList.remove(v)
                    elif v.position is FloosPlayer.Position.K:
                        activeKList.remove(v)
                    team.rosterDict[k] = None

                    name = v.name
                    if name.endswith('IV'):
                        name = name.replace('IV', 'V')
                    elif name.endswith('VIII'):
                        name = name.replace('VIII', 'IX')
                    elif name.endswith('IX'):
                        name = name.replace('IX', 'X')
                    elif name.endswith('III'):
                        name = name.replace('III', 'IV')
                    elif name.endswith('V') or name.endswith('II') or name.endswith('X'):
                        name += 'I'
                    else:
                        name += ' II'
                    unusedNamesList.append(name)
                else:
                    x = randint(1,100)
                    if v.playerTier is FloosPlayer.PlayerTier.SuperStar:
                        if x > 99:
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                        else:
                            v.term = getPlayerTerm(v.playerTier)
                    elif v.playerTier is FloosPlayer.PlayerTier.Elite:
                        if x > 90:
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                        else:
                            v.term = getPlayerTerm(v.playerTier)
                    elif v.playerTier is FloosPlayer.PlayerTier.AboveAverage:
                        if x > 65:
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                        else:
                            v.term = getPlayerTerm(v.playerTier)
                    elif v.playerTier is FloosPlayer.PlayerTier.Average:
                        if x > 40:
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                        else:
                            v.term = getPlayerTerm(v.playerTier)
                    elif v.playerTier is FloosPlayer.PlayerTier.BelowAverage:
                        if x > 15:
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                        else:
                            v.term = getPlayerTerm(v.playerTier)

        for k,v in team.reserveRosterDict.items():
            if v is not None:
                v: FloosPlayer.Player
                v.term -= 1
                if v.term == 0:
                    retirePlayerBool = None
                    if v.seasonsPlayed > 15:
                        x = randint(1,10)
                        if x > 4:
                            retirePlayerBool = True
                    elif v.seasonsPlayed > 10:
                        x = randint(1,10)
                        if x > 6:
                            retirePlayerBool = True
                    elif v.seasonsPlayed >= 7:
                        x = randint(1,10)
                        if x > 8:
                            retirePlayerBool = True
                    else:
                        retirePlayerBool = False

                    if retirePlayerBool:
                        v.previousTeam = team.name
                        v.team = 'Retired'
                        retiredPlayersList.append(v)
                        activePlayerList.remove(v)
                        if v.position is FloosPlayer.Position.QB:
                            activeQbList.remove(v)
                        elif v.position is FloosPlayer.Position.RB:
                            activeRbList.remove(v)
                        elif v.position is FloosPlayer.Position.WR:
                            activeWrList.remove(v)
                        elif v.position is FloosPlayer.Position.TE:
                            activeTeList.remove(v)
                        elif v.position is FloosPlayer.Position.K:
                            activeKList.remove(v)
                        team.reserveRosterDict[k] = None

                        name = v.name
                        if name.endswith('IV'):
                            name = name.replace('IV', 'V')
                        elif name.endswith('VIII'):
                            name = name.replace('VIII', 'IX')
                        elif name.endswith('IX'):
                            name = name.replace('IX', 'X')
                        elif name.endswith('III'):
                            name = name.replace('III', 'IV')
                        elif name.endswith('V') or name.endswith('II') or name.endswith('X'):
                            name += 'I'
                        else:
                            name += ' II'
                        unusedNamesList.append(name)
                    else:
                        x = randint(1,100)
                        if v.playerTier is FloosPlayer.PlayerTier.SuperStar:
                            if x > 99:
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                            else:
                                v.term = getPlayerTerm(v.playerTier)
                        elif v.playerTier is FloosPlayer.PlayerTier.Elite:
                            if x > 90:
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                            else:
                                v.term = getPlayerTerm(v.playerTier)
                        elif v.playerTier is FloosPlayer.PlayerTier.AboveAverage:
                            if x > 65:
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                            else:
                                v.term = getPlayerTerm(v.playerTier)
                        elif v.playerTier is FloosPlayer.PlayerTier.Average:
                            if x > 40:
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                            else:
                                v.term = getPlayerTerm(v.playerTier)
                        elif v.playerTier is FloosPlayer.PlayerTier.BelowAverage:
                            if x > 15:
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                            else:
                                v.term = getPlayerTerm(v.playerTier)
                    
    for player in activePlayerList:
        if player.team is None:
            pass
        player.offseasonTraining()

    rookieDraftList = []

    for x in range(len(teamList)):
        player = None
        seed = randint(50,100)
        y = randint(0,4)
        if y == 0:
            player = FloosPlayer.PlayerQB(seed)
            activeQbList.append(player)
        elif y == 1:
            player = FloosPlayer.PlayerRB(seed)
            activeRbList.append(player)
        elif y == 2:
            player = FloosPlayer.PlayerWR(seed)
            activeWrList.append(player)
        elif y == 3:
            player = FloosPlayer.PlayerTE(seed)
            activeTeList.append(player)
        elif y == 4:
            player = FloosPlayer.PlayerK(seed)
            activeKList.append(player)
        player.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
        player.id = (len(activePlayerList) + len(retiredPlayersList) + 1)
        activePlayerList.append(player)
        rookieDraftList.append(player)

    sortPlayers()
    list.sort(rookieDraftList, key=lambda player: player.attributes.overallRating, reverse=True)
    draftSelectionDict = {}
    for team in rookieDraftOrder:
        team: FloosTeam.Team
        draftSelection: FloosPlayer.Player = None
        for player in rookieDraftList:
            player: FloosPlayer.Player
            if player.position is FloosPlayer.Position.QB:
                if team.rosterDict['qb'] is None or team.reserveRosterDict['qb'] is None:
                    if team.rosterDict['qb'] is None:
                        draftSelection = player
                        team.rosterDict['qb'] = draftSelection
                        break
                    elif player.attributes.overallRating > team.rosterDict['qb'].attributes.overallRating:
                        draftSelection = player
                        team.reserveRosterDict['qb'] = draftSelection
                        break
                    else:
                        continue
                else:
                    continue
            elif player.position is FloosPlayer.Position.RB:
                if team.rosterDict['rb'] is None or team.reserveRosterDict['rb'] is None:
                    if team.rosterDict['rb'] is None:
                        draftSelection = player
                        team.rosterDict['rb'] = draftSelection
                        break
                    elif player.attributes.overallRating > team.rosterDict['rb'].attributes.overallRating:
                        draftSelection = player
                        team.reserveRosterDict['rb'] = draftSelection
                        break
                    else:
                        continue
                else:
                    continue
            elif player.position is FloosPlayer.Position.WR:
                if team.rosterDict['wr'] is None or team.reserveRosterDict['wr'] is None:
                    if team.rosterDict['wr'] is None:
                        draftSelection = player
                        team.rosterDict['wr'] = draftSelection
                        break
                    elif player.attributes.overallRating > team.rosterDict['wr'].attributes.overallRating:
                        draftSelection = player
                        team.reserveRosterDict['wr'] = draftSelection
                        break
                    else:
                        continue
                else:
                    continue
            elif player.position is FloosPlayer.Position.TE:
                if team.rosterDict['te'] is None or team.reserveRosterDict['te'] is None:
                    if team.rosterDict['te'] is None:
                        draftSelection = player
                        team.rosterDict['te'] = draftSelection
                        break
                    elif player.attributes.overallRating > team.rosterDict['te'].attributes.overallRating:
                        draftSelection = player
                        team.reserveRosterDict['te'] = draftSelection
                        break
                    else:
                        continue
                else:
                    continue
            elif player.position is FloosPlayer.Position.K:
                if team.rosterDict['k'] is None or team.reserveRosterDict['k'] is None:
                    if team.rosterDict['k'] is None:
                        draftSelection = player
                        team.rosterDict['k'] = draftSelection
                        break
                    elif player.attributes.overallRating > team.rosterDict['k'].attributes.overallRating:
                        draftSelection = player
                        team.reserveRosterDict['k'] = draftSelection
                        break
                    else:
                        continue
                else:
                    continue

        if draftSelection is not None:
            draftSelection.team = team
            draftSelection.term = getPlayerTerm(draftSelection.playerTier)
            rookieDraftList.remove(draftSelection)
            draftSelectionDict[team.name] = {'name': draftSelection.name, 'pos': draftSelection.position.name, 'rating': draftSelection.attributes.overallRating, 'tier': draftSelection.playerTier.name, 'term': draftSelection.term}
        else:
            draftSelectionDict[team.name] = 'No Selection'
        
    rookieDraftHistoryDict['offseason {}'.format(seasonsPlayed)] = draftSelectionDict

    for player in rookieDraftList:
        player.team = 'Free Agent'
        freeAgentList.append(player)


    freeAgentQbList : list[FloosPlayer.Player] = []
    freeAgentRbList : list[FloosPlayer.Player] = []
    freeAgentWrList : list[FloosPlayer.Player] = []
    freeAgentTeList : list[FloosPlayer.Player] = []
    freeAgentKList : list[FloosPlayer.Player] = []

    for player in freeAgentList:
        if player.position.value == 1:
            freeAgentQbList.append(player)
        elif player.position.value == 2:
            freeAgentRbList.append(player)
        elif player.position.value == 3:
            freeAgentWrList.append(player)
        elif player.position.value == 4:
            freeAgentTeList.append(player)
        elif player.position.value == 5:
            freeAgentKList.append(player)

    list.sort(freeAgentQbList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(freeAgentRbList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(freeAgentWrList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(freeAgentTeList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(freeAgentKList, key=lambda player: player.attributes.overallRating, reverse=True)
    list.sort(freeAgentList, key=lambda player: player.attributes.overallRating, reverse=True)

    teamsComplete = 0
    while teamsComplete < len(teamList):
        teamsComplete = 0
        team: FloosTeam.Team
        for team in teamList:
            selectedPlayer = None
            openRosterPosList = []
            openReservePosList = []
            for k,v in team.rosterDict.items():
                if v is None:
                    openRosterPosList.append(k)
            for k,v in team.reserveRosterDict.items():
                if v is None:
                    openReservePosList.append(k)
            if len(openRosterPosList) > 0:
                pos = choice(openRosterPosList)
                if pos == 'qb':
                    selectedPlayer = freeAgentQbList.pop(0)
                elif pos == 'rb':
                    selectedPlayer = freeAgentRbList.pop(0)
                elif pos == 'wr':
                    selectedPlayer = freeAgentWrList.pop(0)
                elif pos == 'te':
                    selectedPlayer = freeAgentTeList.pop(0)
                elif pos == 'k':
                    selectedPlayer = freeAgentKList.pop(0)

                freeAgentList.remove(selectedPlayer)
                selectedPlayer.team = team
                team.rosterDict[pos] = selectedPlayer
                selectedPlayer.term = getPlayerTerm(selectedPlayer.playerTier)
                freeAgencyDict[team.name] = {'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'rating': selectedPlayer.attributes.overallRating, 'tier': selectedPlayer.playerTier.name, 'term': selectedPlayer.term, 'previousTeam': selectedPlayer.previousTeam, 'roster': "starting"}
                continue
            elif len(openReservePosList) > 0 and len(freeAgentList) > 0:
                pos = choice(openReservePosList)
                if pos == 'qb' and len(freeAgentQbList) > 0 and freeAgentQbList[0].attributes.overallRating > team.rosterDict['qb'].attributes.overallRating:
                    selectedPlayer = freeAgentQbList.pop(0)
                elif pos == 'rb' and len(freeAgentRbList) > 0 and freeAgentRbList[0].attributes.overallRating > team.rosterDict['rb'].attributes.overallRating:
                    selectedPlayer = freeAgentRbList.pop(0)
                elif pos == 'wr' and len(freeAgentWrList) > 0 and freeAgentWrList[0].attributes.overallRating > team.rosterDict['wr'].attributes.overallRating:
                    selectedPlayer = freeAgentWrList.pop(0)
                elif pos == 'te' and len(freeAgentTeList) > 0 and freeAgentTeList[0].attributes.overallRating > team.rosterDict['te'].attributes.overallRating:
                    selectedPlayer = freeAgentTeList.pop(0)
                elif pos == 'k' and len(freeAgentKList) > 0 and freeAgentKList[0].attributes.overallRating > team.rosterDict['k'].attributes.overallRating:
                    selectedPlayer = freeAgentKList.pop(0)
                
                if selectedPlayer is not None:
                    freeAgentList.remove(selectedPlayer)
                    selectedPlayer.team = team
                    team.reserveRosterDict[pos] = selectedPlayer
                    selectedPlayer.term = getPlayerTerm(selectedPlayer.playerTier)
                    freeAgencyDict[team.name] = {'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'rating': selectedPlayer.attributes.overallRating, 'tier': selectedPlayer.playerTier.name, 'term': selectedPlayer.term, 'previousTeam': selectedPlayer.previousTeam, 'roster': "reserve"}
                    continue
                else:
                    teamsComplete += 1
                    continue
            else:
                teamsComplete += 1
                continue
    for player in freeAgentList:
        player.team = 'Free Agent'

    freeAgencyHistoryDict['offseason {}'.format(seasonsPlayed)] = freeAgencyDict

    for team in teamList:
            team.updateDefense()
    
def getPerformanceRating():
    qbStatsPassCompList = []
    qbStatsPassYardsList = []
    qbStatsTdsList = []
    qbStatsIntsList = []
    for qb in activeQbList:
        qb: FloosPlayer.PlayerQB
        if qb.seasonStatsDict['passYards'] > 0:
            qbStatsPassCompList.append(qb.seasonStatsDict['passCompPerc'])
            qbStatsPassYardsList.append(qb.seasonStatsDict['passYards'])
            qbStatsTdsList.append(qb.seasonStatsDict['tds'])
            qbStatsIntsList.append(qb.seasonStatsDict['ints'])

    for qb in activeQbList:
        qb: FloosPlayer.PlayerQB
        if qb.seasonStatsDict['passYards'] > 0:
            passCompPercRating = stats.percentileofscore(qbStatsPassCompList, qb.seasonStatsDict['passCompPerc'], 'rank')
            passYardsRating = stats.percentileofscore(qbStatsPassYardsList, qb.seasonStatsDict['passYards'], 'rank')
            tdsRating = stats.percentileofscore(qbStatsTdsList, qb.seasonStatsDict['tds'], 'rank')
            intsRating = 100 - stats.percentileofscore(qbStatsIntsList, qb.seasonStatsDict['ints'], 'rank')
            qb.seasonPerformanceRating = round(((passCompPercRating*1.3)+(passYardsRating*.6)+(tdsRating*1.2)+(intsRating*.4))/4)

    rbStatsYprList = []
    rbStatsRunYardsList = []
    rbStatsTdsList = []
    rbStatsFumblesList = []
    for rb in activeRbList:
        rb: FloosPlayer.PlayerRB
        if rb.seasonStatsDict['runYards'] > 0:
            rbStatsYprList.append(rb.seasonStatsDict['ypr'])
            rbStatsRunYardsList.append(rb.seasonStatsDict['runYards'])
            rbStatsTdsList.append(rb.seasonStatsDict['tds'])
            rbStatsFumblesList.append(rb.seasonStatsDict['fumblesLost'])

    for rb in activeRbList:
        rb: FloosPlayer.PlayerRB
        if rb.seasonStatsDict['runYards'] > 0:
            yprRating = stats.percentileofscore(rbStatsYprList, rb.seasonStatsDict['ypr'], 'rank')
            runYardsRating = stats.percentileofscore(rbStatsRunYardsList, rb.seasonStatsDict['runYards'], 'rank')
            tdsRating = stats.percentileofscore(rbStatsTdsList, rb.seasonStatsDict['tds'], 'rank')
            fumblesRating = 100 - stats.percentileofscore(rbStatsFumblesList, rb.seasonStatsDict['fumblesLost'], 'rank')
            rb.seasonPerformanceRating = round(((yprRating*1.2)+(runYardsRating*.6)+(tdsRating*1.3)+(fumblesRating*.4))/4)

    wrStatsRcvPercList = []
    wrStatsRcvYardsList = []
    wrStatsTdsList = []
    for wr in activeWrList:
        wr: FloosPlayer.PlayerWR
        if wr.seasonStatsDict['receptions'] > 0:
            wrStatsRcvPercList.append(wr.seasonStatsDict['rcvPerc'])
            wrStatsRcvYardsList.append(wr.seasonStatsDict['rcvYards'])
            wrStatsTdsList.append(wr.seasonStatsDict['tds'])

    for wr in activeWrList:
        wr: FloosPlayer.PlayerWR
        if wr.seasonStatsDict['receptions'] > 0:
            rcvPercRating = stats.percentileofscore(wrStatsRcvPercList, wr.seasonStatsDict['rcvPerc'], 'rank')
            rcvYardsRating = stats.percentileofscore(wrStatsRcvYardsList, wr.seasonStatsDict['rcvYards'], 'rank')
            tdsRating = stats.percentileofscore(wrStatsTdsList, wr.seasonStatsDict['tds'], 'rank')
            wr.seasonPerformanceRating = round(((rcvPercRating*1.3)+(rcvYardsRating*.5)+(tdsRating*1.2))/3)

    teStatsRcvPercList = []
    teStatsRcvYardsList = []
    teStatsTdsList = []
    for te in activeTeList:
        te: FloosPlayer.PlayerTE
        if te.seasonStatsDict['receptions'] > 0:
            teStatsRcvPercList.append(te.seasonStatsDict['rcvPerc'])
            teStatsRcvYardsList.append(te.seasonStatsDict['rcvYards'])
            teStatsTdsList.append(te.seasonStatsDict['tds'])

    for te in activeTeList:
        te: FloosPlayer.PlayerTE
        if te.seasonStatsDict['receptions'] > 0:
            rcvPercRating = stats.percentileofscore(teStatsRcvPercList, te.seasonStatsDict['rcvPerc'], 'rank')
            rcvYardsRating = stats.percentileofscore(teStatsRcvYardsList, te.seasonStatsDict['rcvYards'], 'rank')
            tdsRating = stats.percentileofscore(teStatsTdsList, te.seasonStatsDict['tds'], 'rank')
            te.seasonPerformanceRating = round(((rcvPercRating*1.3)+(rcvYardsRating*.5)+(tdsRating*1.2))/3)

    kStatsFgPercList = []
    kStatsFgsList = []
    for k in activeKList:
        k: FloosPlayer.PlayerK
        if k.seasonStatsDict['fgAtt'] > 0:
            kStatsFgPercList.append(k.seasonStatsDict['fgPerc'])
            kStatsFgsList.append(k.seasonStatsDict['fgs'])

    for k in activeKList:
        k: FloosPlayer.PlayerK
        if k.seasonStatsDict['fgAtt'] > 0:
            fgPercRating = stats.percentileofscore(kStatsFgPercList, k.seasonStatsDict['fgPerc'], 'rank')
            fgsRating = stats.percentileofscore(kStatsFgsList, k.seasonStatsDict['fgs'], 'rank')
            k.seasonPerformanceRating = round(((fgPercRating*1.5)+(fgsRating*.5))/2)

    defenseStatsSacksList = []
    defenseStatsIntsList = []
    defenseStatsFumblesList = []
    defenseStatsPassYardsList = []
    defenseStatsRunYardsList = []
    defenseStatsTotalYardsList = []
    defenseStatsPassTdsList = []
    defenseStatsRunTdsList = []
    defenseStatsTotalTdsList = []
    
    for team in teamList:
        team: FloosTeam.Team
        defenseStatsSacksList.append(team.seasonTeamStats['Defense']['sacks'])
        defenseStatsIntsList.append(team.seasonTeamStats['Defense']['ints'])
        defenseStatsFumblesList.append(team.seasonTeamStats['Defense']['fumRec'])
        defenseStatsPassYardsList.append(team.seasonTeamStats['Defense']['passYardsAlwd'])
        defenseStatsRunYardsList.append(team.seasonTeamStats['Defense']['runYardsAlwd'])
        defenseStatsTotalYardsList.append(team.seasonTeamStats['Defense']['totalYardsAlwd'])
        defenseStatsPassTdsList.append(team.seasonTeamStats['Defense']['passTdsAlwd'])
        defenseStatsRunTdsList.append(team.seasonTeamStats['Defense']['runTdsAlwd'])
        defenseStatsTotalTdsList.append(team.seasonTeamStats['Defense']['tdsAlwd'])

    for team in teamList:
        team: FloosTeam.Team
        sacksRating = stats.percentileofscore(defenseStatsSacksList, team.seasonTeamStats['Defense']['sacks'], 'rank')
        intsRating = stats.percentileofscore(defenseStatsIntsList, team.seasonTeamStats['Defense']['ints'], 'rank')
        fumblesRating = 100 - stats.percentileofscore(defenseStatsFumblesList, team.seasonTeamStats['Defense']['fumRec'], 'rank')
        passYardsRating = stats.percentileofscore(defenseStatsPassYardsList, team.seasonTeamStats['Defense']['passYardsAlwd'], 'rank')
        runYardsRating = stats.percentileofscore(defenseStatsRunYardsList, team.seasonTeamStats['Defense']['runYardsAlwd'], 'rank')
        totalYardsRating = stats.percentileofscore(defenseStatsTotalYardsList, team.seasonTeamStats['Defense']['totalYardsAlwd'], 'rank')
        passTdsRating = stats.percentileofscore(defenseStatsPassTdsList, team.seasonTeamStats['Defense']['passTdsAlwd'], 'rank')
        runTdsRating = stats.percentileofscore(defenseStatsRunTdsList, team.seasonTeamStats['Defense']['runTdsAlwd'], 'rank')
        totalTdsRating = stats.percentileofscore(defenseStatsTotalTdsList, team.seasonTeamStats['Defense']['tdsAlwd'], 'rank')
        
        team.defenseSeasonPerformanceRating = round(((sacksRating*.6)+(intsRating*.8)+(fumblesRating*.8)+(passYardsRating*1.1)+(runYardsRating*1.1)+(totalYardsRating*1.2)+(passTdsRating*1.1)+(runTdsRating*1.1)+(totalTdsRating*1.2))/9)


async def startLeague():
    global seasonsPlayed
    global totalSeasons
    global config
    global activeSeason
    global seasonList

    print('Floosball v{}'.format(__version__))
    print('Reading config...')
    config = FloosMethods.getConfig()
    leagueConfig = config['leagueConfig']
    totalSeasons = leagueConfig['totalSeasons']
    deleteDataOnStart = leagueConfig['deleteDataOnRestart']
    saveSeasonProgress = leagueConfig['saveSeasonProgress']
    print('Config done')

    if saveSeasonProgress:
        print('Save Season Progress enabled')
        seasonsPlayed = config['leagueConfig']['lastSeason']
        totalSeasons += seasonsPlayed

    if os.path.isdir('data'):
        if deleteDataOnStart:
            print('Deleting previous data...')
            for f in os.listdir('data'):
                os.remove(os.path.join('data', f))
            print('Previous data deleted')
    else:
        print('Creating data directory')
        os.mkdir('data')

    print('Creating players...')
    getPlayers(config)
    print('Player creation done')
    print('Creating teams...')
    getTeams(config)
    print('Team creation done')

    if not os.path.exists("data/teamData.json"):
        print('Starting player draft...')
        playerDraft()
        print('Draft complete')
    else:
        print('Skipping draft')

    print('Initializing teams...')
    initTeams()
    #print('Cleaning up players...')
    #initPlayers()
    print('Saving player data...')
    savePlayerData()
    print('Creating divisions...')
    getDivisons(config)
    if not os.path.exists("data/divisionData.json"):
        initDivisions()

    print('Initialization complete!')
    while seasonsPlayed < totalSeasons:
        print('Season {} start'.format(seasonsPlayed+1))
        activeSeason = Season()
        seasonList.append(activeSeason)
        activeSeason.createSchedule()
        await activeSeason.startSeason()
        seasonsPlayed += 1
        offseason()

        if saveSeasonProgress:
            print('Updating config after season end...')
            FloosMethods.saveConfig(seasonsPlayed, 'leagueConfig', 'lastSeason')
        await asyncio.sleep(60)
