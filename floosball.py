import json
import os
from random import randint
import copy
import asyncio
import statistics
import matplotlib.pyplot as plt
import numpy as np
import floosball_game as FloosGame
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_methods as FloosMethods
 
config = None
totalSeasons = 0
seasonsPlayed = 0
playerList = []
freeAgentList = []
teamList = []
divisionList = []   
scheduleList = []
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
                newGame.id = '{0}0{1}0{2}'.format(self.currentSeason, week+1, x+1)
                newGame.status = FloosGame.GameStatus.Scheduled
                gameList.append(newGame)
                # print("{0} v. {1}".format(awayTeam.name, homeTeam.name))
            scheduleList.append(gameList)

    def getSeasonStats(self):
        dict = {}
        y = 0
        jsonFile = open("data/teamData.json", "w+")
        for team in teamList:

            for player in team.rosterDict.values():
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

    async def startSeason(self):
        weekDict = {}
        seasonDict = {}
        gameDictTemp = {}
        strCurrentSeason = 'season{}'.format(self.currentSeason)

        weekFilePath = '{}/games'.format(strCurrentSeason)
        if os.path.isdir(weekFilePath):
            for f in os.listdir(weekFilePath):
                os.remove(os.path.join(weekFilePath, f))
        else:
            os.mkdir(weekFilePath)

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
                week[game].saveGameData()
                gameResults = week[game].gameDict
                gameDict[strGame] = gameResults
            weekDict = FloosMethods._prepare_for_serialization(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()

        for team in teamList:
            team.seasonTeamStats['winPerc'] = round((team.seasonTeamStats['wins']/(team.seasonTeamStats['wins'] + team.seasonTeamStats['losses'])),3)

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
            teamDict[team.name] = FloosMethods._prepare_for_serialization(team)

        jsonFile = open(os.path.join(strCurrentSeason, 'teamData.json'), "w+")
        jsonFile.write(json.dumps(teamDict, indent=4))
        jsonFile.close()

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

        numOfRounds = FloosMethods.getPower(2, len(playoffTeamsList))

        for x in range(numOfRounds):

            playoffGamesList = []
            playoffGamesTaskList = []
            currentRound = x + 1
            hiSeed = 0
            lowSeed = len(playoffTeamsList) - 1
            gameNumber = 1

            list.sort(playoffTeamsList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)

            while lowSeed > hiSeed:
                newGame = FloosGame.Game(playoffTeamsList[hiSeed], playoffTeamsList[lowSeed])
                newGame.id = 'PO{0}{1}{2}'.format(self.currentSeason, currentRound, gameNumber)
                playoffGamesList.append(newGame)
                playoffGamesTaskList.append(newGame.playGame())
                hiSeed += 1
                lowSeed -= 1
                gameNumber += 1

            self.activeGames = playoffGamesList
            await asyncio.wait(playoffGamesTaskList)

            for game in playoffGamesList:
                game.saveGameData()
                gameResults = game.gameDict
                if len(playoffGamesList) == 1:
                    playoffTeamsList.clear()
                    game.winningTeam.leagueChampionships += 1
                    champ = newGame.winningTeam
                    playoffDict['Championship'] = gameResults
                else:
                    playoffDict[game.id] = gameResults
                    for team in playoffTeamsList:
                        if team.name == gameResults['losingTeam']:
                            losingTeam = playoffTeamsList.pop(playoffTeamsList.index(team))
                            break

            jsonFile = open(os.path.join('{}/games'.format(strCurrentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()

        return champ

"""     def startSeason(self):
        weekDict = {}
        seasonDict = {}
        gameDictTemp = {}
        strCurrentSeason = 'season{}'.format(self.currentSeason)

        weekFilePath = '{}/games'.format(strCurrentSeason)
        if os.path.isdir(weekFilePath):
            for f in os.listdir(weekFilePath):
                os.remove(os.path.join(weekFilePath, f))
        else:
            os.mkdir(weekFilePath)

        for week in scheduleList:
            #print("\n-------------------------------------------------\n")
            #print("Week {0}".format(scheduleList.index(week)+1))
            self.currentWeek = scheduleList.index(week)+1
            currentWeekText = 'Week {}'.format(self.currentWeek)
            self.activeGames = week
            gameDict = gameDictTemp.copy()

            for game in range(0,len(week)):
                strGame = 'Game {}'.format(game + 1)
                week[game].playGame()
                week[game].postgame()
                week[game].saveGameData()
                gameResults = week[game].gameDict
                gameDict[strGame] = gameResults
            weekDict = FloosMethods._prepare_for_serialization(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()

        for team in teamList:
            team.seasonTeamStats['winPerc'] = round((team.seasonTeamStats['wins']/(team.seasonTeamStats['wins'] + team.seasonTeamStats['losses'])),3)

        #seasonDict['games'] = weekDict
        leagueChampion = self.playPlayoffs()

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
            teamDict[team.name] = FloosMethods._prepare_for_serialization(team)

        jsonFile = open(os.path.join(strCurrentSeason, 'teamData.json'), "w+")
        jsonFile.write(json.dumps(teamDict, indent=4))
        jsonFile.close()

        self.clearSeasonStats()

    def playPlayoffs(self):
        #print("\nFLOOSBALL DIVISIONAL ROUND")
        champ = None
        playoffDict = {}
        playoffTeamsList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)
        x = 0
        divisionalGamesList = []
        for division in divisionList:
            x += 1
            strRound = 'Divisonal Game {}'.format(x)
            list.sort(division.teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)
            division.teamList[0].divisionChampionships += 1
            division.teamList[0].playoffAppearances += 1
            division.teamList[1].playoffAppearances += 1
            newGame = FloosGame.Game(division.teamList[0], division.teamList[1])
            newGame.id = '888{0}0{1}'.format(self.currentSeason, x)
            newGame.playGame()
            newGame.saveGameData()
            gameResults = newGame.gameDict
            playoffTeamsList.append(newGame.winningTeam)
            playoffDict[strRound] = gameResults
        
        list.sort(playoffTeamsList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=True)

        numOfRounds = FloosMethods.getPower(2, len(playoffTeamsList))
        winningTeamsList = []
        losingTeam = None

        for x in range(numOfRounds):
            # if (x + 1) == numOfRounds:
            #     #print("\nFLOOSBALL CHAMPIONSHIP GAME")
            # else:
            #     #print("\nFLOOSBALL PLAYOFFS ROUND {0}".format(x + 2))
            if x >= 1:
                playoffTeamsList = winningTeamsList

            playoffGamesList = []
            numOfGames = int(len(playoffTeamsList)/2)

            for y in range(numOfGames):
                strPlayoffGame = 'Playoff Game {}'.format(y + 1)
                lastSeed = len(playoffTeamsList) - 1
                newGame = FloosGame.Game(playoffTeamsList[0], playoffTeamsList[lastSeed])
                newGame.id = '999{0}{1}'.format(self.currentSeason, y+1)
                playoffGamesList.append(newGame)

            for game in playoffGamesList:
                game.playGame()
                game.saveGameData()
                gameResults = game.gameDict
                if numOfGames == 1:
                    playoffTeamsList.clear()
                    game.winningTeam.leagueChampionships += 1
                    champ = newGame.winningTeam
                    playoffDict['Championship'] = gameResults
                else:
                    playoffDict[strPlayoffGame] = gameResults
                    if playoffTeamsList[0].name == gameResults['winningTeam']:
                        losingTeam = playoffTeamsList.pop(lastSeed)
                        winningTeamsList.append(playoffTeamsList.pop(0))
                    elif playoffTeamsList[lastSeed].name == gameResults['winningTeam']:
                        winningTeamsList.append(playoffTeamsList.pop(lastSeed))
                        losingTeam = playoffTeamsList.pop(0)
                    lastSeed = len(playoffTeamsList) - 1
            jsonFile = open(os.path.join('{}/games'.format(strCurrentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()

        return champ """
    
    

def draft():
    draftOrderList = []
    draftQueueList = teamList.copy()
    playerDraftList = playerList.copy()
    rounds = 15

    draftQbList : list[FloosPlayer.Player] = []
    draftRbList : list[FloosPlayer.Player] = []
    draftWrList : list[FloosPlayer.Player] = []
    draftTeList : list[FloosPlayer.Player] = []
    draftKList : list[FloosPlayer.Player] = []

    for player in playerList:
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
    list.sort(playerDraftList, key=lambda player: player.attributes.overallRating, reverse=True)

    #print('\n Available Players by Position')
    #print('\n QBs = {0} | RBs = {1} | WRs = {2} | TEs = {3} | Ks = {4}'.format(qbs, rbs, wrs, tes, ks))


    for x in range(len(teamList)):
        rand = randint(0,len(draftQueueList) - 1)
        draftOrderList.insert(x, draftQueueList[rand])
        draftQueueList.pop(rand)

    for x in range(1, int(rounds)):
        #print('\nRound {0}'.format(x))
        for team in draftOrderList:

            if x == 1:
                if playerDraftList[0].position.value == 1:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif playerDraftList[0].position.value == 2:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif playerDraftList[0].position.value == 3:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif playerDraftList[0].position.value == 4:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif playerDraftList[0].position.value == 5:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 1 and team.rosterDict['qb'] is None:
                team.rosterDict['qb'] = draftQbList.pop(0)
            elif playerDraftList[0].position.value == 2 and team.rosterDict['rb'] is None:
                team.rosterDict['rb'] = draftRbList.pop(0)
            elif playerDraftList[0].position.value == 3 and team.rosterDict['wr'] is None:
                team.rosterDict['wr'] = draftWrList.pop(0)
            elif playerDraftList[0].position.value == 4 and team.rosterDict['te'] is None:
                team.rosterDict['te'] = draftTeList.pop(0)
            elif playerDraftList[0].position.value == 5 and team.rosterDict['k'] is None:
                team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 1 and team.rosterDict['qb'] is not None:
                if team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 2 and team.rosterDict['rb'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 3 and team.rosterDict['wr'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 4 and team.rosterDict['te'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['k'] is None:
                    team.rosterDict['k'] = draftKList.pop(0)
            elif playerDraftList[0].position.value == 5 and team.rosterDict['k'] is not None:
                if team.rosterDict['qb'] is None:
                    team.rosterDict['qb'] = draftQbList.pop(0)
                elif team.rosterDict['rb'] is None:
                    team.rosterDict['rb'] = draftRbList.pop(0)
                elif team.rosterDict['wr'] is None:
                    team.rosterDict['wr'] = draftWrList.pop(0)
                elif team.rosterDict['te'] is None:
                    team.rosterDict['te'] = draftTeList.pop(0)

            #print('{0} took {1}, {2}, rated {3}'.format(team.name, pick.name, pick.position, pick.overallRating))
    for player in draftQbList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftRbList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftWrList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftTeList:
        freeAgentList.append(player)
        player.team = 'Free Agent'
    for player in draftKList:
        freeAgentList.append(player)
        player.team = 'Free Agent'

    # print("\n")
    # print("\nFree Agents")
    # for player in playerDraftList:
    #     print("{0} | {1} | {2}".format(player.name, player.overallRating, player.position))

def savePlayerData():
    playerDict = {}
    tempPlayerDict = {}
    for x in range(len(playerList)):
        key = 'Player {}'.format(x + 1)
        newDict = tempPlayerDict.copy()
        newDict['name'] = playerList[x].name
        newDict['id'] = playerList[x].id
        newDict['tier'] = playerList[x].playerTier.name
        newDict['team'] = playerList[x].team
        newDict['position'] = playerList[x].position
        newDict['seasonsPlayed'] = playerList[x].seasonsPlayed
        newDict['attributes'] = playerList[x].attributes
        newDict['careerStats'] = playerList[x].careerStatsDict
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
                    newPlayer.attributes.skillRating = player['skillRating']
                    newPlayer.attributes.armStrength = player['armStrength']
                    newPlayer.attributes.accuracy = player['accuracy']
                elif player['position'] == 'RB':
                    newPlayer = FloosPlayer.PlayerRB()
                    newPlayer.attributes.skillRating = player['skillRating']
                elif player['position'] == 'WR':
                    newPlayer = FloosPlayer.PlayerWR()
                    newPlayer.attributes.skillRating = player['skillRating']
                elif player['position'] == 'TE':
                    newPlayer = FloosPlayer.PlayerTE()
                    newPlayer.attributes.skillRating = player['skillRating']
                elif player['position'] == 'K':
                    newPlayer = FloosPlayer.PlayerK()
                    newPlayer.attributes.skillRating = player['skillRating']
                    newPlayer.attributes.legStrength = player['legStrength']
                    newPlayer.attributes.accuracy = player['accuracy']

                newPlayer.name = player['name']
                newPlayer.id = player['id']
                newPlayer.attributes.overallRating = player['overallRating']
                newPlayer.attributes.speed = player['speed']
                newPlayer.attributes.hands = player['hands']
                newPlayer.attributes.agility = player['agility']
                newPlayer.attributes.power = player['power']
                newPlayer.careerStatsDict = player['careerStats']

                playerList.append(newPlayer)
        jsonFile.close()

    else:
        id = 1
        for x in _config['players']:
            y = randint(1,5)
            player = None
            if y == 1:
                player = FloosPlayer.PlayerQB()
            elif y == 2:
                player = FloosPlayer.PlayerRB()
            elif y == 3:
                player = FloosPlayer.PlayerWR()
            elif y == 4:
                player = FloosPlayer.PlayerTE()
            elif y == 5:
                player = FloosPlayer.PlayerK()
            player.name = x
            player.id = id
            playerList.append(player)
            id += 1

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
                newTeam.overallRating = team['overallRating']
                newTeam.allTimeTeamStats = team['allTimeTeamStats']

                teamRoster = team['rosterDict']
                for player in teamRoster.values():
                    for z in playerList:
                        if z.name == player['name']:
                            if z.position.value == 1:
                                newTeam.rosterDict['qb'] = z
                            elif z.position.value == 2:
                                newTeam.rosterDict['rb'] = z
                            elif z.position.value == 3:
                                newTeam.rosterDict['wr'] = z
                            elif z.position.value == 4:
                                newTeam.rosterDict['te'] = z
                            elif z.position.value == 5:
                                newTeam.rosterDict['k'] = z
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

    for team in teamList:
        for player in team.rosterDict.values():
            player.team = team

    jsonFile = open("data/teamData.json", "w+")
    for team in teamList:
        team.setupTeam()
        y += 1
        dict[y] = FloosMethods._prepare_for_serialization(team)
        
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()
        
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
    # for division in divisionList:
    #     print("\n{0} Division\n".format(division.name))
    #     for team in division.teamList:
    #         print(team.name)

def offseason():
    for player in playerList:
        player.offseasonTraining()
        player.attributes.calculateIntangibles()
        player.updateRating()

    list.sort(teamList, key=lambda team: team.seasonTeamStats['winPerc'], reverse=False)

    freeAgencyRound = 0
    while freeAgencyRound < config['leagueConfig']['freeAgencyRounds']:
        for team in teamList:
            team.offseasonMoves(freeAgentList)
        freeAgencyRound += 1

    for team in teamList:
            team.updateDefense()
            team.updateRating()
    

def getConfig():
    fileObjext = open("config.json", "r")
    jsonContent = fileObjext.read()
    config = json.loads(jsonContent)
    fileObjext.close()
    return config

async def startLeague():
    global seasonsPlayed
    global totalSeasons
    global config
    global activeSeason

    config = getConfig()
    totalSeasons = config['leagueConfig']['seasons']
    deleteDataOnStart = config['leagueConfig']['deleteDataOnRestart']

    if os.path.isdir('data'):
        if deleteDataOnStart:
            for f in os.listdir('data'):
                os.remove(os.path.join('data', f))
    else:
        os.mkdir('data')

    getPlayers(config)
    getTeams(config)

    if not os.path.exists("data/teamData.json"):
        draft()

    initTeams()
    savePlayerData()
    getDivisons(config)
    if not os.path.exists("data/divisionData.json"):
        initDivisions()

    
    while seasonsPlayed < totalSeasons:
        activeSeason = Season()
        activeSeason.createSchedule()
        await activeSeason.startSeason()
        offseason()
        seasonsPlayed += 1


""" def startLeague():
    global seasonsPlayed
    global totalSeasons
    global config
    global activeSeason

    config = getConfig()
    totalSeasons = config['leagueConfig']['seasons']
    deleteDataOnStart = config['leagueConfig']['deleteDataOnRestart']

    if os.path.isdir('data'):
        if deleteDataOnStart:
            for f in os.listdir('data'):
                os.remove(os.path.join('data', f))
    else:
        os.mkdir('data')

    getPlayers(config)

    # ratingList = []
    # ratingDict = {}
    # for player in playerList:
    #     ratingList.append(player.attributes.overallRating)
    # avgRating = statistics.mean(ratingList)
    # print('Player Rating Mean = {}'.format(statistics.mean(ratingList)))
    # print('Player Rating Median = {}'.format(statistics.median(ratingList)))
    # print('Player Rating Mode = {}'.format(statistics.mode(ratingList)))
    # print('Player Rating Variance = {}'.format(statistics.variance(ratingList)))
    
    # for x in range(70, 100):
    #     ratingDict[x] = 0
    # for x in ratingList:
    #     ratingDict[x] += 1

    

    # axisX = np.array(list(ratingDict.keys()))
    # axisY = np.array(list(ratingDict.values()))

    # plt.bar(axisX,axisY)
    # plt.show()

    getTeams(config)

    if not os.path.exists("data/teamData.json"):
        draft()

    initTeams()
    savePlayerData()
    getDivisons(config)
    if not os.path.exists("data/divisionData.json"):
        initDivisions()

    
    while seasonsPlayed < totalSeasons:
        activeSeason = Season()
        activeSeason.createSchedule()
        asyncio.run(activeSeason.startSeason())
        #activeSeason.startSeason()
        offseason()
        seasonsPlayed += 1

startLeague() """