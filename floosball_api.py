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
    dict = {}
    if id is None:
        for team in floosball.teamList:
            teamDict = {}
            teamDict['id'] = team.id
            teamDict['rating'] = team.overallRating
            teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            dict[team.name] = teamDict
    else:
        for team in floosball.teamList:
            if team.id == int(id):
                dict['name'] = team.name
                dict['rating'] = team.overallRating
                dict['offense'] = team.offenseRating
                dict['defense'] = team.defenseRating
                dict['runDefense'] = team.runDefenseRating
                dict['passDefense'] = team.passDefenseRating
                dict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
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
                dict['roster'] = rosterDict
    return dict

@app.get('/players')
async def returnPlayers(id = None):
    dict = {}
    if id is None:
        for player in floosball.activePlayerList:
            playerDict = {}
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
            dict[player.name] = playerDict
    else:
        id = int(id)
        for player in floosball.activePlayerList:
            player: Player
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
    dict = {}
    for division in floosball.divisionList:
        teamDict = {}
        for team in division.teamList:
            teamDict[team.name] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
        dict[division.name] = teamDict
    return dict

@app.get('/schedule')
async def returnSchedule(week = None):
    dict = {}
    if week is None:
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            gameDict = {}
            for x in range(0,len(weekGameList)):
                game = weekGameList[x]
                if game.status is FloosGame.GameStatus.Scheduled:
                    gameDict[game.id] = '{0} {1}-{2} vs. {3} {4}-{5}'.format(game.awayTeam.name, game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'], game.homeTeam.name, game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
                elif game.status is FloosGame.GameStatus.Active:
                    scoreDict = {}
                    scoreDict['teams'] = '{0} vs. {1}'.format(game.awayTeam.name, game.homeTeam.name)
                    scoreDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                    gameDict[game.id] = scoreDict
                elif game.status is FloosGame.GameStatus.Final:
                    resultsDict = {}
                    resultsDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
                    if game.homeTeam.name == game.winningTeam.name:
                        resultsDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
                    elif game.awayTeam.name == game.winningTeam.name:
                        resultsDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                    gameDict[game.id] = resultsDict
            dict['Week {}'.format(y+1)] = gameDict
    else:
        dict['week'] = week
        weekGameList = floosball.scheduleList[int(week)-1]
        for x in range(0,len(weekGameList)):
            game = weekGameList[x]
            if game.status is FloosGame.GameStatus.Scheduled:
                dict[game.id] = '{0} {1}-{2} vs. {3} {4}-{5}'.format(game.awayTeam.name, game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'], game.homeTeam.name, game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
            elif game.status is FloosGame.GameStatus.Active:
                scoreDict = {}
                scoreDict['teams'] = '{0} vs. {1}'.format(game.awayTeam.name, game.homeTeam.name)
                scoreDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                dict[game.id] = scoreDict
            elif game.status is FloosGame.GameStatus.Final:
                resultsDict = {}
                resultsDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
                if game.homeTeam.name == game.winningTeam.name:
                    resultsDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
                elif game.awayTeam.name == game.winningTeam.name:
                    resultsDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                dict[game.id] = resultsDict
    return dict

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
                    if game.status is FloosGame.GameStatus.Scheduled:
                        dict[game.id] = '{0} {1}-{2} vs. {3} {4}-{5}'.format(game.awayTeam.name, game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'], game.homeTeam.name, game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
                    elif game.status is FloosGame.GameStatus.Active:
                        scoreDict = {}
                        scoreDict['teams'] = '{0} vs. {1}'.format(game.awayTeam.name, game.homeTeam.name)
                        scoreDict['status'] = game.status.name
                        scoreDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
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
                    elif game.status is FloosGame.GameStatus.Final:
                        resultsDict = {}
                        resultsDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
                        resultsDict['status'] = game.status.name
                        if game.homeTeam.name == game.winningTeam.name:
                            resultsDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
                        elif game.awayTeam.name == game.winningTeam.name:
                            resultsDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
                        dict[game.id] = resultsDict
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
            gameDict['teams'] = '{0} vs. {1}'.format(game.awayTeam.name, game.homeTeam.name)
            gameDict['id'] = game.id
            gameDict['status'] = game.status.name
            gameDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
            if game.currentQuarter == 5:
                gameDict['quarter'] = 'OT'
            else:
                gameDict['quarter'] = game.currentQuarter
            gameDict['plays'] = game.totalPlays
            gameDict['poss'] = game.offensiveTeam.name
            gameDict['down'] = game.down
            if game.yardsToEndzone < 10:
                gameDict['yardsTo1stDwn'] = game.yardsToEndzone
            else:
                gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
            gameDict['yardsToEZ'] = game.yardsToEndzone
            if game.totalPlays > 0:
                playDict = {}
                if game.totalPlays >= 3:
                    playDict[game.totalPlays - 2] = game.playsDict[str(game.totalPlays-2)]['playText']
                if game.totalPlays >= 2:
                    playDict[game.totalPlays - 1] = game.playsDict[str(game.totalPlays-1)]['playText']
                playDict[game.totalPlays] = game.playsDict[str(game.totalPlays)]['playText']
                gameDict['lastPlay'] = playDict
        elif game.status is FloosGame.GameStatus.Final:
            gameDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
            gameDict['id'] = game.id
            gameDict['status'] = game.status.name
            if game.homeTeam.name == game.winningTeam.name:
                gameDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
            elif game.awayTeam.name == game.winningTeam.name:
                gameDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
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

