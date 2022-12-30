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
 

__version__ = '0.3.0_alpha'

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
freeAgencyOrder = []
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


colorList = [   
                '#F1C40F',
                '#651FFF',
                '#C0392B',
                '#58D68D',
                '#F39C12',
                '#7FB3D5',
                '#FF6D00',
                '#2980B9',
                '#FF1744',
                '#FF4081',
                '#D500F9',
                '#9C27B0',
                '#304FFE',
                '#64B5F6',
                '#2196F3',
                '#00B0FF',
                '#26C6DA',
                '#00E5FF',
                '#26A69A',
                '#1DE9B6',
                '#00C853',
                '#F57F17',
                '#FFC400',
                '#FF3D00'      
            ]
    

class Division:
    def __init__(self, name):
        self.name = name
        self.teamList = []

class Season:
    def __init__(self):
        self.currentSeason = seasonsPlayed + 1
        self.activeGames = None
        self.currentWeek = None
        self.currentWeekText = None
        self.leagueHighlights = []

    def createSchedule(self):
        numOfWeeks = len(scheduleScheme)
        scheduleList.clear()
        for week in range(0, numOfWeeks):
            gameList = []
            numOfGames = int(len(teamList)/2)
            for x in range(0, numOfGames):
                game = scheduleScheme[week][x]
                homeTeam:FloosTeam.Team = divisionList[int(game[0]) - 1].teamList[int(game[1]) - 1]
                awayTeam:FloosTeam.Team = divisionList[int(game[2]) - 1].teamList[int(game[3]) - 1]
                newGame = FloosGame.Game(homeTeam,awayTeam)
                newGame.id = 's{0}w{1}g{2}'.format(self.currentSeason, week+1, x+1)
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.isRegularSeasonGame = True
                homeTeam.schedule.append(newGame)
                awayTeam.schedule.append(newGame)
                gameList.append(newGame)
            scheduleList.append(gameList)

    def getSeasonStats(self):
        dict = {}
        jsonFile = open("data/teamData.json", "w+")
        for team in teamList:
            team: FloosTeam.Team
            teamDict = {}
            rosterDict = {}
            reserveDict = {}
            for pos, player in team.rosterDict.items():
                playerDict = {}
                player: FloosPlayer.Player
                player.seasonsPlayed += 1
                if player.seasonStatsDict['passing']['yards'] > 0:
                    player.careerStatsDict['passing']['att'] += player.seasonStatsDict['passing']['att']
                    player.careerStatsDict['passing']['comp'] += player.seasonStatsDict['passing']['comp']
                    player.careerStatsDict['passing']['tds'] += player.seasonStatsDict['passing']['tds']
                    player.careerStatsDict['passing']['ints'] += player.seasonStatsDict['passing']['ints']
                    player.careerStatsDict['passing']['yards'] += player.seasonStatsDict['passing']['yards']
                    player.careerStatsDict['passing']['ypc'] = round(player.careerStatsDict['passing']['yards']/player.careerStatsDict['passing']['comp'])
                    player.careerStatsDict['passing']['compPerc'] = round((player.careerStatsDict['passing']['comp']/player.careerStatsDict['passing']['att'])*100)
                    team.seasonTeamStats['Offense']['passYards'] += player.seasonStatsDict['passing']['yards']
                if player.seasonStatsDict['receiving']['yards'] > 0:
                    player.careerStatsDict['receiving']['receptions'] += player.seasonStatsDict['receiving']['receptions']
                    player.careerStatsDict['receiving']['targets'] += player.seasonStatsDict['receiving']['targets']
                    player.careerStatsDict['receiving']['yac'] += player.seasonStatsDict['receiving']['yac']
                    player.careerStatsDict['receiving']['yards'] += player.seasonStatsDict['receiving']['yards']
                    player.careerStatsDict['receiving']['tds'] += player.seasonStatsDict['receiving']['tds']
                    if player.careerStatsDict['receiving']['receptions'] > 0:
                        player.careerStatsDict['receiving']['ypr'] = round(player.careerStatsDict['receiving']['yards']/player.careerStatsDict['receiving']['receptions'])
                        player.careerStatsDict['receiving']['rcvPerc'] = round((player.careerStatsDict['receiving']['receptions']/player.careerStatsDict['receiving']['targets'])*100)
                if player.seasonStatsDict['rushing']['carries'] > 0:
                    player.careerStatsDict['rushing']['carries'] += player.seasonStatsDict['rushing']['carries']
                    player.careerStatsDict['rushing']['yards'] += player.seasonStatsDict['rushing']['yards']
                    player.careerStatsDict['rushing']['tds'] += player.seasonStatsDict['rushing']['tds']
                    player.careerStatsDict['rushing']['fumblesLost'] += player.seasonStatsDict['rushing']['fumblesLost']
                    player.careerStatsDict['rushing']['ypc'] = round(player.careerStatsDict['rushing']['yards']/player.careerStatsDict['rushing']['carries'])
                    team.seasonTeamStats['Offense']['runYards'] += player.seasonStatsDict['rushing']['yards']
                if player.seasonStatsDict['kicking']['fgAtt'] > 0:
                    if player.seasonStatsDict['kicking']['fgs'] > 0:
                        player.seasonStatsDict['kicking']['fgPerc'] = round((player.seasonStatsDict['kicking']['fgs']/player.seasonStatsDict['kicking']['fgAtt'])*100)
                    else:
                        player.seasonStatsDict['kicking']['fgPerc'] = 0

                    player.careerStatsDict['kicking']['fgAtt'] += player.seasonStatsDict['kicking']['fgAtt']
                    player.careerStatsDict['kicking']['fgs'] += player.seasonStatsDict['kicking']['fgs']
                    if player.careerStatsDict['kicking']['fgs'] > 0:
                        player.careerStatsDict['kicking']['fgPerc'] = round((player.careerStatsDict['kicking']['fgs']/player.careerStatsDict['kicking']['fgAtt'])*100)
                    else:
                        player.careerStatsDict['kicking']['fgPerc'] = 0
                    team.seasonTeamStats['Offense']['tds'] += (player.seasonStatsDict['passing']['tds'] + player.seasonStatsDict['rushing']['tds'] + player.seasonStatsDict['receiving']['tds'])

                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['pos'] = player.position.name
                playerDict['rating'] = player.attributes.overallRating
                playerDict['seasonsPlayed'] = player.seasonsPlayed
                playerDict['gamesPlayed'] = player.gamesPlayed
                playerDict['term'] = player.term
                playerDict['seasonStats'] = player.seasonStatsDict
                rosterDict[pos] = playerDict

            for pos, player in team.reserveRosterDict.items():
                playerDict = {}
                player: FloosPlayer.Player
                if player is not None:
                    player.seasonsPlayed += 1
                if player is not None and player.gamesPlayed > 0:
                    if player.seasonStatsDict['passing']['yards'] > 0:
                        player.careerStatsDict['passing']['att'] += player.seasonStatsDict['passing']['att']
                        player.careerStatsDict['passing']['comp'] += player.seasonStatsDict['passing']['comp']
                        player.careerStatsDict['passing']['tds'] += player.seasonStatsDict['passing']['tds']
                        player.careerStatsDict['passing']['ints'] += player.seasonStatsDict['passing']['ints']
                        player.careerStatsDict['passing']['yards'] += player.seasonStatsDict['passing']['yards']
                        player.careerStatsDict['passing']['ypc'] = round(player.careerStatsDict['passing']['yards']/player.careerStatsDict['passing']['comp'])
                        player.careerStatsDict['passing']['compPerc'] = round((player.careerStatsDict['passing']['comp']/player.careerStatsDict['passing']['att'])*100)
                        team.seasonTeamStats['Offense']['passYards'] += player.seasonStatsDict['passing']['yards']
                    if player.seasonStatsDict['receiving']['yards'] > 0:
                        player.careerStatsDict['receiving']['receptions'] += player.seasonStatsDict['receiving']['receptions']
                        player.careerStatsDict['receiving']['targets'] += player.seasonStatsDict['receiving']['targets']
                        player.careerStatsDict['receiving']['yac'] += player.seasonStatsDict['receiving']['yac']
                        player.careerStatsDict['receiving']['yards'] += player.seasonStatsDict['receiving']['yards']
                        player.careerStatsDict['receiving']['tds'] += player.seasonStatsDict['receiving']['tds']
                    if player.careerStatsDict['receiving']['receptions'] > 0:
                            player.careerStatsDict['receiving']['ypr'] = round(player.careerStatsDict['receiving']['yards']/player.careerStatsDict['receiving']['receptions'])
                            player.careerStatsDict['receiving']['rcvPerc'] = round((player.careerStatsDict['receiving']['receptions']/player.careerStatsDict['receiving']['targets'])*100)
                    if player.seasonStatsDict['rushing']['carries'] > 0:
                        player.careerStatsDict['rushing']['carries'] += player.seasonStatsDict['rushing']['carries']
                        player.careerStatsDict['rushing']['yards'] += player.seasonStatsDict['rushing']['yards']
                        player.careerStatsDict['rushing']['tds'] += player.seasonStatsDict['rushing']['tds']
                        player.careerStatsDict['rushing']['fumblesLost'] += player.seasonStatsDict['rushing']['fumblesLost']
                        player.careerStatsDict['rushing']['ypc'] = round(player.careerStatsDict['rushing']['yards']/player.careerStatsDict['rushing']['carries'])
                        team.seasonTeamStats['Offense']['runYards'] += player.seasonStatsDict['rushing']['yards']
                    if player.seasonStatsDict['kicking']['fgAtt'] > 0:
                        if player.seasonStatsDict['kicking']['fgs'] > 0:
                            player.seasonStatsDict['kicking']['fgPerc'] = round((player.seasonStatsDict['kicking']['fgs']/player.seasonStatsDict['kicking']['fgAtt'])*100)
                        else:
                            player.seasonStatsDict['kicking']['fgPerc'] = 0

                        player.careerStatsDict['kicking']['fgAtt'] += player.seasonStatsDict['kicking']['fgAtt']
                        player.careerStatsDict['kicking']['fgs'] += player.seasonStatsDict['kicking']['fgs']
                        if player.careerStatsDict['kicking']['fgs'] > 0:
                            player.careerStatsDict['kicking']['fgPerc'] = round((player.careerStatsDict['kicking']['fgs']/player.careerStatsDict['kicking']['fgAtt'])*100)
                        else:
                            player.careerStatsDict['kicking']['fgPerc'] = 0
                        team.seasonTeamStats['Offense']['tds'] += (player.seasonStatsDict['passing']['tds'] + player.seasonStatsDict['rushing']['tds'] + player.seasonStatsDict['receiving']['tds'])

                    playerDict['name'] = player.name
                    playerDict['id'] = player.id
                    playerDict['pos'] = player.position.value
                    playerDict['rating'] = player.attributes.overallRating
                    playerDict['seasonsPlayed'] = player.seasonsPlayed
                    playerDict['gamesPlayed'] = player.gamesPlayed
                    playerDict['term'] = player.term
                    playerDict['seasonStats'] = player.seasonStatsDict
                    reserveDict[pos] = playerDict


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

            teamDict['name'] = team.name
            teamDict['city'] = team.city
            teamDict['abbr'] = team.abbr
            teamDict['color'] = team.color
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
            teamDict['gmScore'] = team.gmScore
            teamDict['defenseTier'] = team.defenseTier
            teamDict['leagueChampionships'] = team.leagueChampionships
            teamDict['rosterHistory'] = team.rosterHistory
            teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating
            teamDict['roster'] = rosterDict
            teamDict['reserves'] = reserveDict
            dict[team.id] = teamDict

        jsonFile.write(json.dumps(dict, indent=4))
        jsonFile.close()

        savePlayerData()

    def clearSeasonStats(self):
        for player in activePlayerList:
            player: FloosPlayer.Player
            player.seasonStatsDict['rating'] = player.playerTier.value
            seasonStatsCopy = copy.deepcopy(player.seasonStatsDict)
            player.seasonStatsArchive.pop(0)
            player.seasonStatsArchive.insert(0, seasonStatsCopy)
            player.seasonStatsDict = copy.deepcopy(FloosPlayer.playerStatsDict)
            player.gamesPlayed = 0

        for team in teamList:
            team: FloosTeam.Team
            team.statArchive.insert(0,team.seasonTeamStats)
            team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)
            team.schedule = []
 

    async def startSeason(self):
        global freeAgencyOrder
        weekDict = {}
        seasonDict = {}
        gameDictTemp = {}
        freeAgencyOrder = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)

        for team in teamList:
            team: FloosTeam.Team
            team.eliminated = False
            team.seasonTeamStats['season'] = self.currentSeason

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

        for player in activePlayerList:
            if isinstance(player.team, FloosTeam.Team):
                player.seasonStatsDict['team'] = player.team.abbr
                player.seasonStatsDict['color'] = player.team.color
            else:
                player.seasonStatsDict['team'] = 'FA'
                player.seasonStatsDict['color'] = '#94a3b8'
            player.seasonStatsDict['season'] = self.currentSeason
            player.seasonStatsDict['gp'] = player.gamesPlayed
            player.seasonStatsDict['rating'] = player.playerTier.value
            player.seasonStatsArchive.insert(0,player.seasonStatsDict)


        self.leagueHighlights.insert(0, {'event':  {'text': 'Season {} Start'.format(self.currentSeason)}})

        for week in scheduleList:
            self.currentWeek = scheduleList.index(week)+1
            self.currentWeekText = 'Week {}'.format(self.currentWeek)
            self.activeGames = week
            gameDict = gameDictTemp.copy()
            self.leagueHighlights = []

            for game in range(0,len(week)):
                week[game].leagueHighlights = self.leagueHighlights

            self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})

            gamesList = [week[game].playGame() for game in range(0,len(week))]
            await asyncio.wait(gamesList)

            for game in range(0,len(week)):
                strGame = 'Game {}'.format(game + 1)
                week[game].postgame()
                gameResults = week[game].gameDict
                gameDict[strGame] = gameResults
            weekDict = FloosMethods._prepare_for_serialization(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(self.currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()
            
            for division in divisionList:
                list.sort(division.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            getPerformanceRating()
            sortPlayers()
            sortDefenses()
            self.leagueHighlights.insert(0, {'event': {'text': '{} End'.format(self.currentWeekText)}})
            await asyncio.sleep(30)

        #seasonDict['games'] = weekDict
        leagueChampion = await self.playPlayoffs()

        self.getSeasonStats()

        standingsDict = {}
        divStandingsTempDict = {}
        jsonFile = open("data/divisionData.json", "w+")
        for division in divisionList:
            list.sort(division.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            divStandingsDict = divStandingsTempDict.copy()
            #print("\n{0} Division".format(division.name))
            for team in division.teamList:
                divStandingsDict[team.name] = '{0} - {1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            standingsDict[division.name] = divStandingsDict

        jsonFile.write(json.dumps(standingsDict, indent=4))
        jsonFile.close()

        seasonDict['standings'] = standingsDict
        seasonDict['champion'] = leagueChampion.name
        leagueChampion.seasonTeamStats['leagueChamp'] = True

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
        list.sort(teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)

    async def playPlayoffs(self):
        champ = None
        playoffDict = {}
        playoffTeamsList = []
        nonDivWinnersList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)
        x = 0
        for division in divisionList:
            list.sort(division.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            division.teamList[0].seasonTeamStats['divPLace'] = '1st'
            division.teamList[1].seasonTeamStats['divPLace'] = '2nd'
            division.teamList[2].seasonTeamStats['divPLace'] = '3rd'
            division.teamList[3].seasonTeamStats['divPLace'] = '4th'
            playoffTeamsList.append(division.teamList[0])
            nonDivWinnersList.append(division.teamList[1])
            nonDivWinnersList.append(division.teamList[2])
            nonDivWinnersList.append(division.teamList[3])

        list.sort(nonDivWinnersList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
        playoffTeamsList.append(nonDivWinnersList.pop(0))
        playoffTeamsList.append(nonDivWinnersList.pop(0))
        playoffTeamsList.append(nonDivWinnersList.pop(0))
        playoffTeamsList.append(nonDivWinnersList.pop(0))
        freeAgencyOrder.extend(nonDivWinnersList)
        list.sort(freeAgencyOrder, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)

        numOfRounds = FloosMethods.getPower(2, len(playoffTeamsList))

        for team in playoffTeamsList:
            team: FloosTeam.Team
            team.playoffAppearances += 1
            team.seasonTeamStats['madePlayoffs'] = True

        for team in nonDivWinnersList:
            team: FloosTeam.Team
            team.eliminated = True

        for x in range(numOfRounds):

            playoffGamesList = []
            playoffGamesTaskList = []
            self.leagueHighlights = []
            currentRound = x + 1
            hiSeed = 0
            lowSeed = len(playoffTeamsList) - 1
            gameNumber = 1

            list.sort(playoffTeamsList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            while lowSeed > hiSeed:
                newGame = FloosGame.Game(playoffTeamsList[hiSeed], playoffTeamsList[lowSeed])
                newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.isRegularSeasonGame = False
                playoffGamesList.append(newGame)
                playoffGamesTaskList.append(newGame.playGame())
                newGame.leagueHighlights = self.leagueHighlights
                hiSeed += 1
                lowSeed -= 1
                gameNumber += 1
            
            scheduleList.append(playoffGamesList)

            self.activeGames = playoffGamesList
            if x < numOfRounds - 1:
                self.currentWeek = 'Playoffs Round {}'.format(x+1)
                self.currentWeekText = 'Playoffs Round {}'.format(x+1)
                self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeek)}})
            else:
                self.currentWeek = 'Floos Bowl'
                self.currentWeekText = 'Floos Bowl'
                self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeek)}})
            await asyncio.wait(playoffGamesTaskList)

            for game in playoffGamesList:
                game: FloosGame.Game
                game.postgame()
                gameResults = game.gameDict
                if len(playoffGamesList) == 1:
                    playoffTeamsList.clear()
                    game.winningTeam.leagueChampionships.append('Season {}'.format(seasonsPlayed+1))
                    champ = game.winningTeam
                    game.losingTeam.eliminated = True
                    playoffDict['Floos Bowl'] = gameResults
                    freeAgencyOrder.append(game.losingTeam)
                    freeAgencyOrder.append(champ)
                else:
                    playoffDict[game.id] = gameResults
                    for team in playoffTeamsList:
                        if team.name == gameResults['losingTeam']:
                            team.eliminated = True
                            freeAgencyOrder.append(team)
                            playoffTeamsList.remove(team)
                            break

            jsonFile = open(os.path.join('{}/games'.format(strCurrentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()
            if x < numOfRounds - 1:
                sortPlayers()
                sortDefenses()
                await asyncio.sleep(30)

        return champ


def getPlayerTerm(rating):
        if rating > 90:
            return randint(3,5)
        elif rating < 75:
            return 1
        else:
            return randint(1,3)

def playerDraft():
    draftOrderList = []
    draftQueueList = teamList.copy()
    playerDraftList = activePlayerList.copy()
    rounds = 6

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
    
    list.sort(draftQbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftRbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftWrList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftTeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftKList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(playerDraftList, key=lambda player: player.attributes.skillRating, reverse=True)


    for x in range(len(teamList)):
        rand = randint(0,len(draftQueueList) - 1)
        draftOrderList.insert(x, draftQueueList[rand])
        draftQueueList.pop(rand)

    for x in range(1, int(rounds+1)):
        #print('\nRound {0}'.format(x))
        for team in draftOrderList:
            team: FloosTeam.Team
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
                    if team.rosterDict['wr1'] is None:
                        team.rosterDict['wr1'] = selectedPlayer
                    elif team.rosterDict['wr2'] is None:
                        team.rosterDict['wr2'] = selectedPlayer
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
                if team.rosterDict['wr1'] is None or team.rosterDict['wr2'] is None:
                    openPosList.append(FloosPlayer.Position.WR.value)
                if team.rosterDict['te'] is None:
                    openPosList.append(FloosPlayer.Position.TE.value)
                if team.rosterDict['k'] is None:
                    openPosList.append(FloosPlayer.Position.K.value)
                z = choice(openPosList)

                if z == FloosPlayer.Position.QB.value:
                    if team.gmScore >= len(draftQbList):
                        i = len(draftQbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftQbList.pop(randint(0,i))
                    team.rosterDict['qb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.RB.value:
                    if team.gmScore >= len(draftRbList):
                        i = len(draftRbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftRbList.pop(randint(0,i))
                    team.rosterDict['rb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.WR.value:
                    if team.gmScore >= len(draftWrList):
                        i = len(draftWrList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftWrList.pop(randint(0,i))
                    if team.rosterDict['wr1'] is None:
                        team.rosterDict['wr1'] = selectedPlayer
                    elif team.rosterDict['wr2'] is None:
                        team.rosterDict['wr2'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.TE.value:
                    if team.gmScore >= len(draftTeList):
                        i = len(draftTeList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftTeList.pop(randint(0,i))
                    team.rosterDict['te'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.K.value:
                    if team.gmScore >= len(draftKList):
                        i = len(draftKList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftKList.pop(randint(0,i))
                    team.rosterDict['k'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)

            selectedPlayer.team = team
            selectedPlayer.term = getPlayerTerm(selectedPlayer.playerRating)
            selectedPlayer.seasonStatsDict['team'] = selectedPlayer.team.name
            team.rosterHistory.append({'season': seasonsPlayed+1, 'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'tier': selectedPlayer.playerTier.value, 'isAddition': True})
                
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
        newDict['seasonPerformanceRating'] = activePlayerList[x].seasonPerformanceRating
        newDict['playerRating'] = activePlayerList[x].playerRating
        newDict['freeAgentYears'] = activePlayerList[x].freeAgentYears
        newDict['serviceTime'] = activePlayerList[x].serviceTime.name
        newDict['attributes'] = activePlayerList[x].attributes
        newDict['careerStats'] = activePlayerList[x].careerStatsDict

        archiveDict = {}
        y = 0
        for item in activePlayerList[x].seasonStatsArchive:
            y += 1
            archiveDict[y] = item

        newDict['seasonStatsArchive'] = archiveDict
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

                if player['serviceTime'] == 'Rookie':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
                elif player['serviceTime'] == 'Intermediate':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Intermediate
                elif player['serviceTime'] == 'Professional':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Professional
                elif player['serviceTime'] == 'Veteran':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Veteran
                elif player['serviceTime'] == 'Retired':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Retired

                newPlayer.name = player['name']
                newPlayer.id = player['id']
                newPlayer.team = player['team']
                newPlayer.seasonsPlayed = player['seasonsPlayed']
                newPlayer.playerRating = player['playerRating']
                newPlayer.freeAgentYears = player['freeAgentYears']
                newPlayer.seasonPerformanceRating = player['seasonPerformanceRating']
                newPlayer.attributes.overallRating = player['attributes']['overallRating']
                newPlayer.attributes.skillRating = player['attributes']['skillRating']
                newPlayer.attributes.speed = player['attributes']['speed']
                newPlayer.attributes.hands = player['attributes']['hands']
                newPlayer.attributes.agility = player['attributes']['agility']
                newPlayer.attributes.power = player['attributes']['power']
                newPlayer.attributes.armStrength = player['attributes']['armStrength']
                newPlayer.attributes.accuracy = player['attributes']['accuracy']
                newPlayer.attributes.legStrength = player['attributes']['legStrength']

                newPlayer.attributes.potentialSkillRating = player['attributes']['potentialSkillRating']

                if newPlayer.position is FloosPlayer.Position.QB:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialArmStrength']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialAccuracy']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.RB:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialSpeed']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialPower']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.WR:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialSpeed']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialHands']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.TE:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialPower']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialHands']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.K:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialLegStrength']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialAccuracy']


                newPlayer.attributes.confidence = player['attributes']['confidence']
                newPlayer.attributes.determination = player['attributes']['determination']
                newPlayer.attributes.discipline = player['attributes']['discipline']
                newPlayer.attributes.focus = player['attributes']['focus']
                newPlayer.attributes.instinct = player['attributes']['instinct']
                newPlayer.attributes.creativity = player['attributes']['creativity']
                newPlayer.attributes.luck = player['attributes']['luck']
                newPlayer.attributes.attitude = player['attributes']['attitude']
                newPlayer.attributes.playMakingAbility = player['attributes']['playMakingAbility']
                newPlayer.attributes.xFactor = player['attributes']['xFactor']

                newPlayer.careerStatsDict = player['careerStats']

                statArchive: dict = player['seasonStatsArchive']

                for k,v in statArchive.items():
                    index = int(k) - 1
                    newPlayer.seasonStatsArchive.insert(index, v)

                activePlayerList.append(newPlayer)

        jsonFile.close()
        getUnusedNames()

    else:
        numOfPlayers = 150
        id = 1
        for x in _config['players']:
            unusedNamesList.append(x)
        for x in range(numOfPlayers):
            player = None
            y = x%6
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
            elif y == 5:
                player = FloosPlayer.PlayerWR()
                activeWrList.append(player)
            player.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
            player.id = id
            activePlayerList.append(player)
            id += 1
        saveUnusedNames()

    sortPlayers()


def getTeams(_config):

    if os.path.exists("data/teamData.json"):
        with open('data/teamData.json') as jsonFile:
            teamData = json.load(jsonFile)
            for x in teamData:
                team = teamData[x]
                newTeam = FloosTeam.Team(team['name'])
                newTeam.id = team['id']
                newTeam.city = team['city']
                newTeam.abbr = team['abbr']
                newTeam.color = team['color']
                newTeam.offenseRating = team['offenseRating']
                newTeam.runDefenseRating = team['runDefenseRating']
                newTeam.passDefenseRating = team['passDefenseRating']
                newTeam.defenseRating = team['defenseRating']
                newTeam.defenseLuck = team['defenseLuck']
                newTeam.defenseDiscipline = team['defenseDiscipline']
                newTeam.gmScore = team['gmScore']
                newTeam.defenseTier = team['defenseTier']
                newTeam.defenseSeasonPerformanceRating = team['defenseSeasonPerformanceRating']
                newTeam.overallRating = team['overallRating']
                newTeam.allTimeTeamStats = team['allTimeTeamStats']
                newTeam.leagueChampionships = team['leagueChampionships']
                newTeam.playoffAppearances = team['playoffAppearances']
                newTeam.rosterHistory = team['rosterHistory']


                teamRoster = team['roster']
                for pos, player in teamRoster.items():
                    for z in activePlayerList:
                        z:FloosPlayer.Player
                        if z.name == player['name']:
                            newTeam.rosterDict[pos] = z
                            break

                teamReserveRoster = team['reserves']
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
            team = FloosTeam.Team(x['name'])
            team.city = x['city']
            team.abbr = x['abbr']
            team.color = colorList.pop(randint(0,len(colorList)-1))
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
    jsonFile = open("data/teamData.json", "w+")
    for team in teamList:
        team: FloosTeam.Team
        team.setupTeam()
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['abbr'] = team.abbr
        teamDict['color'] = team.color
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
        teamDict['gmScore'] = team.gmScore
        teamDict['defenseTier'] = team.defenseTier
        teamDict['leagueChampionships'] = team.leagueChampionships
        teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating


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
        teamDict['roster'] = rosterDict
        teamDict['reserves'] = reserveRosterDict

        dict[team.id] = teamDict
    sortDefenses()
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()


def initPlayers():
    pass

def sortPlayers():
    for playerList in playerLists:
        ratingList = []
        for player in playerList:
            player: FloosPlayer.Player
            ratingList.append(player.playerRating)

        tierS = np.percentile(ratingList, 96)
        tierA = np.percentile(ratingList, 80)
        tierB = np.percentile(ratingList, 40)
        tierC = np.percentile(ratingList, 10)

        for player in playerList:
            if player.playerRating >= tierS:
                player.playerTier = FloosPlayer.PlayerTier.TierS
            elif player.playerRating >= tierA:
                player.playerTier = FloosPlayer.PlayerTier.TierA
            elif player.playerRating >= tierB:
                player.playerTier = FloosPlayer.PlayerTier.TierB
            elif player.playerRating >= tierC:
                player.playerTier = FloosPlayer.PlayerTier.TierC
            else:
                player.playerTier = FloosPlayer.PlayerTier.TierD


def sortDefenses():
    teamDefenseRatingList = []
    for team in teamList:
        team: FloosTeam.Team
        teamDefenseRatingList.append(team.defenseOverallRating)
    
    tier5perc = np.percentile(teamDefenseRatingList, 96)
    tier4perc = np.percentile(teamDefenseRatingList, 80)
    tier3perc = np.percentile(teamDefenseRatingList, 40)
    tier2perc = np.percentile(teamDefenseRatingList, 10)

    for team in teamList:
        team: FloosTeam.Team
        if team.defenseOverallRating >= tier5perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierS.value
        elif team.defenseOverallRating >= tier4perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierA.value
        elif team.defenseOverallRating >= tier3perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierB.value
        elif team.defenseOverallRating >= tier2perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierC.value
        else:
            team.defenseTier = FloosPlayer.PlayerTier.TierD.value


        
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

async def offseason():
    activeSeason.currentWeek = 'Offseason'
    freeAgencyDict = {}
    for player in freeAgentList:
        player: FloosPlayer.Player
        player.freeAgentYears += 1
        player.seasonPerformanceRating = 0

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
                

                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has retired after {} seasons'.format(player.name, player.seasonsPlayed)}})

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
            v.seasonPerformanceRating = 0
            if v.seasonsPlayed >= 1 and v.seasonsPlayed < 4:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Intermediate
            elif v.seasonsPlayed >= 4 and v.seasonsPlayed < 7:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Professional
            else:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Veteran

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
                    team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': v.playerTier.value, 'isAddition': False})
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

                    activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has retired after {} seasons'.format(player.name, player.seasonsPlayed)}})

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
                    if v.playerTier is FloosPlayer.PlayerTier.TierS:
                        if x > 60:
                            team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(v.name)}})
                        else:
                            v.term = getPlayerTerm(v.playerRating)
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                    elif v.playerTier is FloosPlayer.PlayerTier.TierA:
                        if x > 40:
                            team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(v.name)}})
                        else:
                            v.term = getPlayerTerm(v.playerRating)
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                    elif v.playerTier is FloosPlayer.PlayerTier.TierB:
                        if x > 20:
                            team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(v.name)}})
                        else:
                            v.term = getPlayerTerm(v.playerRating)
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                    elif v.playerTier is FloosPlayer.PlayerTier.TierC:
                        if x > 10:
                            team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(v.name)}})
                        else:
                            v.term = getPlayerTerm(v.playerRating)
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                    elif v.playerTier is FloosPlayer.PlayerTier.TierD:
                        if x > 5:
                            team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                            v.previousTeam = team.name
                            v.team = 'Free Agent'
                            freeAgentList.append(v)
                            team.rosterDict[k] = None
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(v.name)}})
                        else:
                            v.term = getPlayerTerm(v.playerRating)
                            activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})

        for k,v in team.reserveRosterDict.items():
            if v is not None:
                v: FloosPlayer.Player
                v.seasonPerformanceRating = 0
                if v.seasonsPlayed >= 1 and v.seasonsPlayed < 4:
                    v.serviceTime = FloosPlayer.PlayerServiceTime.Intermediate
                elif v.seasonsPlayed >= 4 and v.seasonsPlayed < 7:
                    v.serviceTime = FloosPlayer.PlayerServiceTime.Professional
                else:
                    v.serviceTime = FloosPlayer.PlayerServiceTime.Veteran

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
                        team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': v.playerTier.value, 'isAddition': False})
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

                        activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has retired after {} seasons'.format(player.name, player.seasonsPlayed)}})

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
                        if v.playerTier is FloosPlayer.PlayerTier.TierS:
                            if x > 60:
                                team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(player.name)}})
                            else:
                                v.term = getPlayerTerm(v.playerRating)
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                        elif v.playerTier is FloosPlayer.PlayerTier.TierA:
                            if x > 40:
                                team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(player.name)}})
                            else:
                                v.term = getPlayerTerm(v.playerRating)
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                        elif v.playerTier is FloosPlayer.PlayerTier.TierB:
                            if x > 20:
                                team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(player.name)}})
                            else:
                                v.term = getPlayerTerm(v.playerRating)
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                        elif v.playerTier is FloosPlayer.PlayerTier.TierC:
                            if x > 10:
                                team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(player.name)}})
                            else:
                                v.term = getPlayerTerm(v.playerRating)
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                        elif v.playerTier is FloosPlayer.PlayerTier.TierD:
                            if x > 5:
                                team.rosterHistory.append({'season': seasonsPlayed+1, 'name': v.name, 'pos': v.position.name, 'tier': round((((v.attributes.overallRating - 60)/40)*4)+1), 'isAddition': False})
                                v.previousTeam = team.name
                                v.team = 'Free Agent'
                                freeAgentList.append(v)
                                team.reserveRosterDict[k] = None
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(player.name)}})
                            else:
                                v.term = getPlayerTerm(v.playerRating)
                                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, v.name, v.position.name, v.term)}})
                    
    for player in activePlayerList:
        if player.team is None:
            pass
        player.offseasonTraining()

    for x in range(len(teamList)):
        player = None
        seed = randint(15,100)
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
        player.team = 'Free Agent'
        player.id = (len(activePlayerList) + len(retiredPlayersList) + 1)
        activePlayerList.append(player)
        freeAgentList.append(player)

    saveUnusedNames()
    sortPlayers()

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

    list.sort(freeAgentQbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentRbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentWrList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentTeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentKList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentList, key=lambda player: player.attributes.skillRating, reverse=True)

    teamsComplete = 0
    while teamsComplete < len(teamList):
        teamsComplete = 0
        team: FloosTeam.Team
        for team in freeAgencyOrder:
            selectedPlayer = None
            openRosterPosList = []
            openReservePosList = []
            if team.faComplete:
                teamsComplete += 1
                continue
                
            await asyncio.sleep(2)

            for k,v in team.rosterDict.items():
                if v is None:
                    openRosterPosList.append(k)
            for k,v in team.reserveRosterDict.items():
                if v is None:
                    openReservePosList.append(k)
            if len(openRosterPosList) > 0:
                pos = choice(openRosterPosList)
                if pos == 'qb':
                    if team.gmScore >= len(freeAgentQbList):
                        i = len(freeAgentQbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentQbList.pop(randint(0,i))
                elif pos == 'rb':
                    if team.gmScore >= len(freeAgentRbList):
                        i = len(freeAgentRbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentRbList.pop(randint(0,i))
                elif pos == 'wr1':
                    if team.gmScore >= len(freeAgentWrList):
                        i = len(freeAgentWrList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentWrList.pop(randint(0,i))
                elif pos == 'wr2':
                    if team.gmScore >= len(freeAgentWrList):
                        i = len(freeAgentWrList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentWrList.pop(randint(0,i))
                elif pos == 'te':
                    if team.gmScore >= len(freeAgentTeList):
                        i = len(freeAgentTeList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentTeList.pop(randint(0,i))
                elif pos == 'k':
                    if team.gmScore >= len(freeAgentKList):
                        i = len(freeAgentKList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentKList.pop(randint(0,i))

                freeAgentList.remove(selectedPlayer)
                selectedPlayer.team = team
                team.rosterDict[pos] = selectedPlayer
                selectedPlayer.term = getPlayerTerm(selectedPlayer.playerRating)
                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, selectedPlayer.name, selectedPlayer.position.name, selectedPlayer.term)}})
                team.rosterHistory.append({'season': seasonsPlayed+1, 'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'tier': selectedPlayer.playerTier.value, 'isAddition': True})
                freeAgencyDict[team.name] = {'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'rating': selectedPlayer.attributes.skillRating, 'tier': selectedPlayer.playerTier.value, 'term': selectedPlayer.term, 'previousTeam': selectedPlayer.previousTeam, 'roster': "Starting"}
                continue
            elif len(openReservePosList) > 0 and len(freeAgentList) > 0:
                pos = choice(openReservePosList)
                if pos == 'qb' and len(freeAgentQbList) > 0:
                    if team.gmScore >= len(freeAgentQbList):
                        i = len(freeAgentQbList) - 1
                    else:
                        i = team.gmScore
                    n = randint(0,i)
                    if freeAgentQbList[n].attributes.skillRating > team.rosterDict['qb'].attributes.skillRating:
                        selectedPlayer = freeAgentQbList.pop(n)
                elif pos == 'rb' and len(freeAgentRbList) > 0:
                    if team.gmScore >= len(freeAgentRbList):
                        i = len(freeAgentRbList) - 1
                    else:
                        i = team.gmScore
                    n = randint(0,i)
                    if freeAgentRbList[n].attributes.skillRating > team.rosterDict['rb'].attributes.skillRating:
                        selectedPlayer = freeAgentRbList.pop(n)
                elif pos == 'wr1' and len(freeAgentWrList) > 0:
                    if team.gmScore >= len(freeAgentWrList):
                        i = len(freeAgentWrList) - 1
                    else:
                        i = team.gmScore
                    n = randint(0,i)
                    if freeAgentWrList[n].attributes.skillRating > team.rosterDict['wr1'].attributes.skillRating:
                        selectedPlayer = freeAgentWrList.pop(n)
                elif pos == 'wr2' and len(freeAgentWrList) > 0:
                    if team.gmScore >= len(freeAgentWrList):
                        i = len(freeAgentWrList) - 1
                    else:
                        i = team.gmScore
                    n = randint(0,i)
                    if freeAgentWrList[n].attributes.skillRating > team.rosterDict['wr2'].attributes.skillRating:
                        selectedPlayer = freeAgentWrList.pop(n)
                elif pos == 'te' and len(freeAgentTeList) > 0:
                    if team.gmScore >= len(freeAgentTeList):
                        i = len(freeAgentTeList) - 1
                    else:
                        i = team.gmScore
                    n = randint(0,i)
                    if freeAgentTeList[n].attributes.skillRating > team.rosterDict['te'].attributes.skillRating:
                        selectedPlayer = freeAgentTeList.pop(n)
                elif pos == 'k' and len(freeAgentKList) > 0:
                    if team.gmScore >= len(freeAgentKList):
                        i = len(freeAgentKList) - 1
                    else:
                        i = team.gmScore
                    n = randint(0,i)
                    if freeAgentKList[n].attributes.skillRating > team.rosterDict['k'].attributes.skillRating:
                        selectedPlayer = freeAgentKList.pop(n)

                if selectedPlayer is not None:
                    freeAgentList.remove(selectedPlayer)
                    selectedPlayer.team = team
                    team.reserveRosterDict[pos] = selectedPlayer
                    selectedPlayer.term = getPlayerTerm(selectedPlayer.playerRating)
                    activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, selectedPlayer.name, selectedPlayer.position.name, selectedPlayer.term)}})
                    team.rosterHistory.append({'season': seasonsPlayed+1, 'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'tier': selectedPlayer.playerTier.value, 'isAddition': True})
                    freeAgencyDict[team.name] = {'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'rating': selectedPlayer.attributes.skillRating, 'tier': selectedPlayer.playerTier.value, 'term': selectedPlayer.term, 'previousTeam': selectedPlayer.previousTeam, 'roster': "Reserve"}
                    continue
                else:
                    teamsComplete += 1
                    team.faComplete = True
                    continue
            else:
                teamsComplete += 1
                team.faComplete = True
                continue
    for player in freeAgentList:
        player.team = 'Free Agent'

    freeAgencyHistoryDict['offseason {}'.format(seasonsPlayed)] = freeAgencyDict

    for team in teamList:
        team.faComplete = False
        team.updateDefense()
    sortDefenses()
    
def getPerformanceRating():
    qbStatsPassCompList = []
    qbStatsPassYardsList = []
    qbStatsTdsList = []
    qbStatsIntsList = []
    for qb in activeQbList:
        qb: FloosPlayer.PlayerQB
        if qb.seasonStatsDict['passing']['yards'] > 0:
            qbStatsPassCompList.append(qb.seasonStatsDict['passing']['compPerc'])
            qbStatsPassYardsList.append(qb.seasonStatsDict['passing']['yards'])
            qbStatsTdsList.append(qb.seasonStatsDict['passing']['tds'])
            qbStatsIntsList.append(qb.seasonStatsDict['passing']['ints'])

    for qb in activeQbList:
        qb: FloosPlayer.PlayerQB
        if qb.seasonStatsDict['passing']['yards'] > 0:
            passCompPercRating = stats.percentileofscore(qbStatsPassCompList, qb.seasonStatsDict['passing']['compPerc'], 'rank')
            passYardsRating = stats.percentileofscore(qbStatsPassYardsList, qb.seasonStatsDict['passing']['yards'], 'rank')
            tdsRating = stats.percentileofscore(qbStatsTdsList, qb.seasonStatsDict['passing']['tds'], 'rank')
            intsRating = 100 - stats.percentileofscore(qbStatsIntsList, qb.seasonStatsDict['passing']['ints'], 'rank')
            qb.seasonPerformanceRating = round(((passCompPercRating*.6)+(passYardsRating*1.2)+(tdsRating*1.2)+(intsRating*1))/4)

    rbStatsYprList = []
    rbStatsRunYardsList = []
    rbStatsTdsList = []
    rbStatsFumblesList = []
    for rb in activeRbList:
        rb: FloosPlayer.PlayerRB
        if rb.seasonStatsDict['rushing']['yards'] > 0:
            rbStatsYprList.append(rb.seasonStatsDict['rushing']['ypc'])
            rbStatsRunYardsList.append(rb.seasonStatsDict['rushing']['yards'])
            rbStatsTdsList.append(rb.seasonStatsDict['rushing']['tds'])
            rbStatsFumblesList.append(rb.seasonStatsDict['rushing']['fumblesLost'])

    for rb in activeRbList:
        rb: FloosPlayer.PlayerRB
        if rb.seasonStatsDict['rushing']['yards'] > 0:
            yprRating = stats.percentileofscore(rbStatsYprList, rb.seasonStatsDict['rushing']['ypc'], 'rank')
            runYardsRating = stats.percentileofscore(rbStatsRunYardsList, rb.seasonStatsDict['rushing']['yards'], 'rank')
            tdsRating = stats.percentileofscore(rbStatsTdsList, rb.seasonStatsDict['rushing']['tds'], 'rank')
            fumblesRating = 100 - stats.percentileofscore(rbStatsFumblesList, rb.seasonStatsDict['rushing']['fumblesLost'], 'rank')
            rb.seasonPerformanceRating = round(((yprRating*1)+(runYardsRating*1.2)+(tdsRating*1.2)+(fumblesRating*.6))/4)

    wrStatsRcvPercList = []
    wrStatsRcvYardsList = []
    wrStatsYACList = []
    wrStatsTdsList = []
    for wr in activeWrList:
        wr: FloosPlayer.PlayerWR
        if wr.seasonStatsDict['receiving']['receptions'] > 0:
            wrStatsRcvPercList.append(wr.seasonStatsDict['receiving']['rcvPerc'])
            wrStatsRcvYardsList.append(wr.seasonStatsDict['receiving']['yards'])
            wrStatsYACList.append(wr.seasonStatsDict['receiving']['yac'])
            wrStatsTdsList.append(wr.seasonStatsDict['receiving']['tds'])

    for wr in activeWrList:
        wr: FloosPlayer.PlayerWR
        if wr.seasonStatsDict['receiving']['receptions'] > 0:
            rcvPercRating = stats.percentileofscore(wrStatsRcvPercList, wr.seasonStatsDict['receiving']['rcvPerc'], 'rank')
            rcvYardsRating = stats.percentileofscore(wrStatsRcvYardsList, wr.seasonStatsDict['receiving']['yards'], 'rank')
            yacRating = stats.percentileofscore(wrStatsYACList, wr.seasonStatsDict['receiving']['yac'], 'rank')
            tdsRating = stats.percentileofscore(wrStatsTdsList, wr.seasonStatsDict['receiving']['tds'], 'rank')
            wr.seasonPerformanceRating = round(((rcvPercRating*1)+(rcvYardsRating*.8)+(tdsRating*1)+(yacRating*1.2))/4)

    teStatsRcvPercList = []
    teStatsRcvYardsList = []
    teStatsTdsList = []
    for te in activeTeList:
        te: FloosPlayer.PlayerTE
        if te.seasonStatsDict['receiving']['receptions'] > 0:
            teStatsRcvPercList.append(te.seasonStatsDict['receiving']['rcvPerc'])
            teStatsRcvYardsList.append(te.seasonStatsDict['receiving']['yards'])
            teStatsTdsList.append(te.seasonStatsDict['receiving']['tds'])

    for te in activeTeList:
        te: FloosPlayer.PlayerTE
        if te.seasonStatsDict['receiving']['receptions'] > 0:
            rcvPercRating = stats.percentileofscore(teStatsRcvPercList, te.seasonStatsDict['receiving']['rcvPerc'], 'rank')
            rcvYardsRating = stats.percentileofscore(teStatsRcvYardsList, te.seasonStatsDict['receiving']['yards'], 'rank')
            tdsRating = stats.percentileofscore(teStatsTdsList, te.seasonStatsDict['receiving']['tds'], 'rank')
            te.seasonPerformanceRating = round(((rcvPercRating*1)+(rcvYardsRating*.8)+(tdsRating*1.2))/3)

    kStatsFgPercList = []
    kStatsFgsList = []
    kStatsFgAvgList = []
    for k in activeKList:
        k: FloosPlayer.PlayerK
        if k.seasonStatsDict['kicking']['fgAtt'] > 0:
            kStatsFgPercList.append(k.seasonStatsDict['kicking']['fgPerc'])
            kStatsFgsList.append(k.seasonStatsDict['kicking']['fgs'])
            kStatsFgAvgList.append(k.seasonStatsDict['kicking']['fgAvg'])

    for k in activeKList:
        k: FloosPlayer.PlayerK
        if k.seasonStatsDict['kicking']['fgAtt'] > 0:
            fgPercRating = stats.percentileofscore(kStatsFgPercList, k.seasonStatsDict['kicking']['fgPerc'], 'rank')
            fgsRating = stats.percentileofscore(kStatsFgsList, k.seasonStatsDict['kicking']['fgs'], 'rank')
            fgAvgRating = stats.percentileofscore(kStatsFgAvgList, k.seasonStatsDict['kicking']['fgAvg'], 'rank')
            k.seasonPerformanceRating = round(((fgPercRating*1.3)+(fgsRating*.5)+(fgAvgRating*1.2))/3)

    defenseStatsSacksList = []
    defenseStatsIntsList = []
    defenseStatsFumblesList = []
    defenseStatsPassYardsList = []
    defenseStatsRunYardsList = []
    defenseStatsTotalYardsList = []
    defenseStatsPassTdsList = []
    defenseStatsRunTdsList = []
    defenseStatsTotalTdsList = []
    defenseStatsTotalPtsList = []
    
    for team in teamList:
        team: FloosTeam.Team
        defenseStatsSacksList.append(team.seasonTeamStats['Defense']['avgSacks'])
        defenseStatsIntsList.append(team.seasonTeamStats['Defense']['avgInts'])
        defenseStatsFumblesList.append(team.seasonTeamStats['Defense']['avgFumRec'])
        defenseStatsPassYardsList.append(team.seasonTeamStats['Defense']['avgPassYardsAlwd'])
        defenseStatsRunYardsList.append(team.seasonTeamStats['Defense']['avgRunYardsAlwd'])
        defenseStatsTotalYardsList.append(team.seasonTeamStats['Defense']['avgYardsAlwd'])
        defenseStatsPassTdsList.append(team.seasonTeamStats['Defense']['avgPassTdsAlwd'])
        defenseStatsRunTdsList.append(team.seasonTeamStats['Defense']['avgRunTdsAlwd'])
        defenseStatsTotalTdsList.append(team.seasonTeamStats['Defense']['avgTdsAlwd'])
        defenseStatsTotalPtsList.append(team.seasonTeamStats['Defense']['avgPtsAlwd'])

    for team in teamList:
        team: FloosTeam.Team
        sacksRating = stats.percentileofscore(defenseStatsSacksList, team.seasonTeamStats['Defense']['avgSacks'], 'rank')
        intsRating = stats.percentileofscore(defenseStatsIntsList, team.seasonTeamStats['Defense']['avgInts'], 'rank')
        fumblesRating = stats.percentileofscore(defenseStatsFumblesList, team.seasonTeamStats['Defense']['avgFumRec'], 'rank')
        passYardsRating = 100 - stats.percentileofscore(defenseStatsPassYardsList, team.seasonTeamStats['Defense']['avgPassYardsAlwd'], 'rank')
        runYardsRating = 100 - stats.percentileofscore(defenseStatsRunYardsList, team.seasonTeamStats['Defense']['avgRunYardsAlwd'], 'rank')
        totalYardsRating = 100 - stats.percentileofscore(defenseStatsTotalYardsList, team.seasonTeamStats['Defense']['avgYardsAlwd'], 'rank')
        passTdsRating = 100 - stats.percentileofscore(defenseStatsPassTdsList, team.seasonTeamStats['Defense']['avgPassTdsAlwd'], 'rank')
        runTdsRating = 100 - stats.percentileofscore(defenseStatsRunTdsList, team.seasonTeamStats['Defense']['avgRunTdsAlwd'], 'rank')
        totalTdsRating = 100 - stats.percentileofscore(defenseStatsTotalTdsList, team.seasonTeamStats['Defense']['avgTdsAlwd'], 'rank')
        totalPtsRating = 100 - stats.percentileofscore(defenseStatsTotalPtsList, team.seasonTeamStats['Defense']['avgPtsAlwd'], 'rank')
        
        team.defenseSeasonPerformanceRating = round(((sacksRating*.6)+(intsRating*.8)+(fumblesRating*.8)+(passYardsRating*1)+(runYardsRating*1)+(totalYardsRating*1.2)+(passTdsRating*1)+(runTdsRating*1)+(totalTdsRating*1.2)+(totalPtsRating*1.4))/10)

    list.sort(activeQbList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeRbList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeWrList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeTeList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeKList, key=lambda player: player.seasonPerformanceRating, reverse=True)

def saveUnusedNames():
    global unusedNamesList
    jsonFile = open("data/unusedNames.json", "w+")
    unusedNamesDict = {}
    y = 0
    for item in unusedNamesList:
        y += 1
        unusedNamesDict[y] = item
    jsonFile.write(json.dumps(unusedNamesDict, indent=4))
    jsonFile.close()

def getUnusedNames():
    global unusedNamesList
    jsonFile = open("data/unusedNames.json", "r")
    if os.path.exists("data/unusedNames.json"):
        with open('data/unusedNames.json') as jsonFile:
            unusedNames:dict = json.load(jsonFile)
            for name in unusedNames.values():
                unusedNamesList.append(name)
    jsonFile.close()



async def startLeague():
    global seasonsPlayed
    global totalSeasons
    global config
    global activeSeason
    global seasonList

    print('Floosball v{}'.format(__version__))
    #print('Reading config...')
    config = FloosMethods.getConfig()
    leagueConfig = config['leagueConfig']
    totalSeasons = leagueConfig['totalSeasons']
    deleteDataOnStart = leagueConfig['deleteDataOnRestart']
    saveSeasonProgress = leagueConfig['saveSeasonProgress']
    #print('Config done')

    if saveSeasonProgress:
        #print('Save Season Progress enabled')
        seasonsPlayed = config['leagueConfig']['lastSeason']
        totalSeasons += seasonsPlayed

    if os.path.isdir('data'):
        if deleteDataOnStart:
            #print('Deleting previous data...')
            for f in os.listdir('data'):
                os.remove(os.path.join('data', f))
            #print('Previous data deleted')
    else:
        #print('Creating data directory')
        os.mkdir('data')

    #print('Creating players...')
    getPlayers(config)
    #print('Player creation done')
    #print('Creating teams...')
    getTeams(config)
    #print('Team creation done')

    if not os.path.exists("data/teamData.json"):
        #print('Starting player draft...')
        playerDraft()
        #print('Draft complete')
    else:
        print('Skipping draft')

    #print('Initializing teams...')
    initTeams()
    #print('Cleaning up players...')
    #initPlayers()
    #print('Saving player data...')
    savePlayerData()
    #print('Creating divisions...')
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

        if saveSeasonProgress:
            #print('Updating config after season end...')
            FloosMethods.saveConfig(seasonsPlayed, 'leagueConfig', 'lastSeason')
        await asyncio.sleep(60)
        activeSeason.clearSeasonStats()
        await offseason()