from random import randint
from re import T
import floosball
import floosball_game as FloosGame
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import json
import uvicorn
from floosball_player import Player, Position

from floosball_team import Team

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.create_task(floosball.startLeague())

@app.get('/teams')
async def returnTeams(id = None):
    teamList = []
    if id is None:
        for team in floosball.teamList:
            team: Team
            teamDict = {}
            teamDict['name'] = team.name
            teamDict['id'] = team.id
            teamDict['rating'] = team.overallRating
            teamDict['offenseRating'] = team.offenseRating
            teamDict['defenseRating'] = team.defenseRating
            teamDict['runDefenseRating'] = team.runDefenseRating
            teamDict['passDefenseRating'] = team.passDefenseRating
            teamDict['wins'] = team.seasonTeamStats['wins']
            teamDict['losses'] = team.seasonTeamStats['losses']
            teamList.append(teamDict)
        return teamList
    else:
        for team in floosball.teamList:
            if team.id == int(id):
                teamDict = {}
                teamDict['name'] = team.name
                teamDict['id'] = team.id
                teamDict['rating'] = team.overallRating
                teamDict['offenseRating'] = team.offenseRating
                teamDict['defenseRating'] = team.defenseRating
                teamDict['runDefenseRating'] = team.runDefenseRating
                teamDict['passDefenseRating'] = team.passDefenseRating
                teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating
                teamDict['wins'] = team.seasonTeamStats['wins']
                teamDict['losses'] = team.seasonTeamStats['losses']
                rosterDict = {}
                for pos, player in team.rosterDict.items():
                    playerDict = {}
                    playerDict['name'] = player.name
                    playerDict['id'] = player.id
                    playerDict['rating'] = player.attributes.overallRating
                    playerDict['stars'] = player.playerTier.value
                    playerDict['term'] = player.term
                    playerDict['seasonPerformanceRating'] = player.seasonPerformanceRating
                    playerDict['seasonStats'] = player.seasonStatsDict
                    rosterDict[pos] = playerDict
                teamDict['roster'] = rosterDict
                return teamDict

@app.get('/players')
async def returnPlayers(id = None):
    playerList = []
    if id is None:
        for player in floosball.activePlayerList:
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['position'] = player.position.name
            playerDict['stars'] = player.playerTier.value
            playerDict['term'] = player.term
            playerDict['rating'] = player.attributes.overallRating
            if isinstance(player.team, str):
                playerDict['team'] = player.team
            elif player.team is None:
                playerDict['team'] = 'Free Agent'
            else:
                playerDict['team'] = player.team.name
            playerList.append(playerDict)
        return playerList
    else:
        id = int(id)
        for player in floosball.activePlayerList:
            player: Player
            dict = {}
            if player.id == id:
                dict['name'] = player.name
                if isinstance(player.team, str):
                    dict['team'] = player.team
                elif player.team is None:
                    dict['team'] = 'Free Agent'
                else:
                    dict['team'] = player.team.name
                dict['position'] = player.position.name
                dict['rating'] = player.attributes.overallRating
                dict['stars'] = player.playerTier.value
                dict['term'] = player.term
                attDict = {}
                if player.position is Position.QB:
                    attDict['armStrength'] = player.attributes.armStrength
                    attDict['accuracy'] = player.attributes.accuracy
                    attDict['agility'] = player.attributes.agility
                elif player.position is Position.RB:
                    attDict['speed'] = player.attributes.speed
                    attDict['power'] = player.attributes.power
                    attDict['agility'] = player.attributes.agility
                elif player.position is Position.WR:
                    attDict['speed'] = player.attributes.speed
                    attDict['hands'] = player.attributes.hands
                    attDict['agility'] = player.attributes.agility
                elif player.position is Position.TE:
                    attDict['speed'] = player.attributes.hands
                    attDict['power'] = player.attributes.power
                    attDict['agility'] = player.attributes.agility
                elif player.position is Position.K:
                    attDict['legStrength'] = player.attributes.legStrength
                    attDict['accuracy'] = player.attributes.accuracy
                dict['attributes'] = attDict
                if player.seasonPerformanceRating > 0:
                    dict['seasonPerformanceRating'] = player.seasonPerformanceRating
                dict['season stats'] = player.seasonStatsDict
                dict['career stats'] = player.careerStatsDict
        return dict

@app.get('/standings')
async def returnStandings():
    standingsList = []
    for division in floosball.divisionList:
        division: floosball.Division
        divDict = {}
        teamsList = []
        divDict['name'] = division.name
        for team in division.teamList:
            team: Team
            teamDict = {}
            teamDict['name'] = team.name
            teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            teamsList.append(teamDict)
            divDict['standings'] = teamsList
        standingsList.append(divDict)
    return standingsList

@app.get('/schedule')
async def returnSchedule(week = None):
    scheduleList = []
    if week is None:
        weekDict = {}
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            gameList = []
            for x in range(0,len(weekGameList)):
                game: FloosGame.Game = weekGameList[x]
                gameDict = {}
                gameDict['id'] = game.id
                gameDict['homeTeam'] = game.homeTeam
                gameDict['awayTeam'] = game.awayTeam
                gameDict['status'] = game.status.name
                gameList.append(gameDict)
            weekDict['Week {}'.format(y+1)] = gameDict
            scheduleList.append(weekDict)
        return scheduleList
    else:
        gameDict = {}
        weekGameList = floosball.scheduleList[int(week)-1]
        for x in range(0,len(weekGameList)):
            game: FloosGame.Game = weekGameList[x]
            gameDict = {}
            gameDict['id'] = game.id
            gameDict['homeTeam'] = game.homeTeam
            gameDict['awayTeam'] = game.awayTeam
            gameDict['status'] = game.status.name
            scheduleList.append(gameDict)
        return scheduleList

@app.get('/game')
async def returnGame(id = None):
    if id is None:
        return 'No ID specified'
    else:
        dict = {}
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList)):
                game = weekGameList[x]
                if id == game.id:
                    if game.status is FloosGame.GameStatus.Active:
                        scoreDict = {}
                        scoreDict['status'] = game.status.name
                        scoreDict['homeTeam'] = game.homeTeam.name
                        scoreDict['awayTeam'] = game.awayTeam.name
                        scoreDict['homeScore'] = game.homeScore
                        scoreDict['awayScore'] = game.awayScore
                        if game.currentQuarter == 5:
                            scoreDict['quarter'] = 'OT'
                        else:
                            scoreDict['quarter'] = game.currentQuarter
                        scoreDict['plays'] = game.totalPlays
                        scoreDict['poss'] = game.offensiveTeam.name
                        scoreDict['down'] = game.down
                        if game.yardsToEndzone < 10:
                            scoreDict['yardsTo1stDwn'] = game.yardsToEndzone
                        else:
                            scoreDict['yardsTo1stDwn'] = game.yardsToFirstDown
                        scoreDict['yardsToEZ'] = game.yardsToEndzone
                        if game.totalPlays > 0:
                            playDict = {}
                            if game.totalPlays >= 3:
                                playDict[game.totalPlays - 2] = game.playsDict[str(game.totalPlays-2)]['playText']
                            if game.totalPlays >= 2:
                                playDict[game.totalPlays - 1] = game.playsDict[str(game.totalPlays-1)]['playText']
                            playDict[game.totalPlays] = game.playsDict[str(game.totalPlays)]['playText']
                            scoreDict['lastPlay'] = playDict
                        dict[game.id] = scoreDict
                    else:
                        gameDict = {}
                        gameDict['status'] = game.status.name
                        gameDict['homeTeam'] = game.homeTeam.name
                        gameDict['awayTeam'] = game.awayTeam.name
                        gameDict['homeScore'] = game.homeScore
                        gameDict['awayScore'] = game.awayScore
                        gameDict['quarter'] = ''
                        gameDict['plays'] = ''
                        gameDict['poss'] = ''
                        gameDict['down'] = ''
                        gameDict['yardsTo1stDwn'] = ''
                        gameDict['yardsToEZ'] = ''
                        gameDict['lastPlay'] = ''
                        dict[game.id] = gameDict
                    break
        if len(dict) == 0:
            return 'Game Not Found'
        else: return dict

@app.get('/activeGames')
async def returnActiveGames():
    gameList = []
    activeGameList = floosball.activeSeason.activeGames
    for x in range(0,len(activeGameList)):
        gameDict = {}
        game = activeGameList[x]
        if game.status is FloosGame.GameStatus.Active:
            gameDict['id'] = game.id
            gameDict['homeTeam'] = game.homeTeam.name
            gameDict['awayTeam'] = game.awayTeam.name
            gameDict['homeScore'] = game.homeScore
            gameDict['awayScore'] = game.awayScore
            if game.currentQuarter == 5:
                gameDict['quarter'] = 'OT'
            else:
                gameDict['quarter'] = game.currentQuarter
            gameDict['plays'] = game.totalPlays
            gameDict['poss'] = game.offensiveTeam.name
            gameDict['down'] = game.down
            gameDict['playsLeft'] = 132 - game.totalPlays
            if game.yardsToEndzone < 10:
                gameDict['yardsTo1stDwn'] = game.yardsToEndzone
            else:
                gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
            gameDict['yardsToEZ'] = game.yardsToEndzone
            if game.totalPlays > 0:
                gameDict['lastPlay'] = game.playsDict[str(game.totalPlays)]['playText']
            else:
                gameDict['lastPlay'] = ''
            gameList.append(gameDict)
    return gameList

@app.get('/results')
async def returnResults(week = None):
    dict = {}
    weekDict = {}
    if week is None:
        strWeek = 'Week {}'.format(floosball.activeSeason.currentWeek)
        activeGameList = floosball.activeSeason.activeGames
        for x in range(0,len(activeGameList)):
            game = activeGameList[x]
            if game.status is FloosGame.GameStatus.Final:
                resultsDict = {}
                resultsDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
                if game.homeTeam.name == game.winningTeam.name:
                    resultsDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
                elif game.awayTeam.name == game.winningTeam.name:
                    resultsDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                weekDict[game.id] = resultsDict
        dict[strWeek] = weekDict
    else:
        strWeek = 'Week {}'.format(week)
        weekGameList = floosball.scheduleList[int(week)-1]
        for x in range(0,len(weekGameList)):
            game = weekGameList[x]
            if game.status is FloosGame.GameStatus.Final:
                resultsDict = {}
                resultsDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
                if game.homeTeam.name == game.winningTeam.name:
                    resultsDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
                elif game.awayTeam.name == game.winningTeam.name:
                    resultsDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                weekDict[game.id] = resultsDict
        dict[strWeek] = weekDict
    return dict

@app.get('/lastPlay')
async def returnLastPlay(id = None):
    activeGameList = floosball.activeSeason.activeGames
    if id is None:
        return 'No ID specified'
    else:
        for game in activeGameList:
            if game.id == id:
                if game.totalPlays > 0:
                    play = {game.offensiveTeam.name: game.playsDict[str(game.totalPlays)]['playText']}
                    return play
                else:
                    return 'No Plays!'
        return 'Game Not In Progress'

@app.get('/seasonResults')
async def returnSeasonResults(season = None):
    if season is None:
        season = floosball.seasonsPlayed
    
    filePath = 'season{}/seasonData.json'.format(season)
    if os.path.exists(filePath):
        with open(filePath) as jsonFile:
            seasonData = json.load(jsonFile)
            return seasonData
    else:
        return 'No Data'

@app.get('/gameStats')
async def returnGameStats(id = None):
    if id is None:
        return 'No ID specified'
    else:
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList)):
                game = weekGameList[x]
                if id == game.id:
                    if game.status is FloosGame.GameStatus.Active:
                        return game.getGameData()
                    elif game.status is FloosGame.GameStatus.Final:
                        return game.gameDict
        else:
            return 'Game Not Found'

@app.get('/plays')
async def returnGameStats(id = None):
    if id is None:
        return 'No ID specified'
    else:
        dict = {}
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList)):
                game = weekGameList[x]
                if id == game.id:
                    for k,v in game.playsDict.items():
                        dict[k] = v['playText']
                    return dict
        else:
            return 'Game Not Found'

@app.get('/draftResults')
async def returnDraftResults(season = None):
    if season is None:
        return floosball.rookieDraftHistoryDict
    else:
        return floosball.rookieDraftHistoryDict['offseason {}'.format(season)]

@app.get('/freeAgency')
async def returnDraftResults(season = None):
    if season is None:
        return floosball.freeAgencyHistoryDict
    else:
        return floosball.freeAgencyHistoryDict['offseason {}'.format(season)]

@app.get('/roster')
async def returnTeamRosters(id = None, season = None):
    rosterDict = {}
    if id is None and season is None:
        team: Team
        for team in floosball.teamList:
            rosterDict[team.name] = team.rosterHistoryList[len(team.rosterHistoryList)-1]
        return rosterDict
    elif id is None:
        team: Team
        for team in floosball.teamList:
            rosterDict[team.name] = team.rosterHistoryList[int(season)-1]
        return rosterDict
    elif season is None:
        team: Team
        for team in floosball.teamList:
            if team.id == int(id):
                rosterDict[team.name] = team.rosterHistoryList
                break
        return rosterDict
    else:
        team: Team
        for team in floosball.teamList:
            if team.id == int(id):
                rosterDict[team.name] = team.rosterHistoryList[int(season)-1]
                break
        return rosterDict



            

@app.get('/info')
async def returnInfo():
    return floosball.__version__


uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

