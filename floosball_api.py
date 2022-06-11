from random import randint
import floosball
import floosball_methods as FloosMethods
import floosball_game as FloosGame
from fastapi import FastAPI
import asyncio
import json

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.create_task(floosball.startLeague())

@app.get('/teams')
async def returnTeams(id = None):
    dict = {}
    if id is None:
        for team in floosball.teamList:
            dict[team.id] = team.name
    else:
        for team in floosball.teamList:
            if team.id == int(id):
                dict['name'] = team.name
                dict['rating'] = team.overallRating
                dict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
                rosterDict = {}
                rosterDict['QB'] = team.rosterDict['qb'].name
                rosterDict['RB'] = team.rosterDict['rb'].name
                rosterDict['WR'] = team.rosterDict['wr'].name
                rosterDict['TE'] = team.rosterDict['te'].name
                rosterDict['K'] = team.rosterDict['k'].name
                dict['roster'] = rosterDict
    return dict

@app.get('/players')
async def returnPlayers(id = None):
    dict = {}
    if id is None:
        for player in floosball.playerList:
            dict[player.id] = player.name
    else:
        id = int(id)
        for player in floosball.playerList:
            if player.id == id:
                dict['name'] = player.name
                dict['team'] = player.team
                dict['positon'] = player.position.name
                dict['rating'] = player.attributes.overallRating
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
                        scoreDict['quarter'] = game.currentQuarter
                        scoreDict['plays'] = game.totalPlays
                        scoreDict['poss.'] = game.offensiveTeam.name
                        scoreDict['down'] = game.down
                        scoreDict['yardsToGo'] = game.yardsToFirstDown
                        scoreDict['yardsToEZ'] = game.yardsToEndzone
                        if game.totalPlays > 0:
                            scoreDict['lastPlay'] = game.playsDict[str(game.totalPlays)]['playText']
                        dict[game.id] = scoreDict
                    elif game.status is FloosGame.GameStatus.Final:
                        resultsDict = {}
                        resultsDict['teams'] = '{0} def. {1}'.format(game.winningTeam.name, game.losingTeam.name)
                        scoreDict['status'] = game.status.name
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
    dict = {}
    activeGameList = floosball.activeSeason.activeGames
    dict['week'] = floosball.activeSeason.currentWeek
    for x in range(0,len(activeGameList)):
        game = activeGameList[x]
        scoreDict = {}
        if game.status is FloosGame.GameStatus.Active:
            scoreDict['teams'] = '{0} vs. {1}'.format(game.awayTeam.name, game.homeTeam.name)
            scoreDict['status'] = game.status.name
            scoreDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
            scoreDict['quarter'] = game.currentQuarter
            scoreDict['plays'] = game.totalPlays
            scoreDict['poss.'] = game.offensiveTeam.name
            scoreDict['down'] = game.down
            scoreDict['yardsToGo'] = game.yardsToFirstDown
            scoreDict['yardsToEZ'] = game.yardsToEndzone
            if game.totalPlays > 0:
                scoreDict['lastPlay'] = game.playsDict[str(game.totalPlays)]['playText']
        elif game.status is FloosGame.GameStatus.Final:
            scoreDict['teams'] = '{0} vs. {1}'.format(game.winningTeam.name, game.losingTeam.name)
            scoreDict['status'] = game.status.name
            if game.homeTeam.name == game.winningTeam.name:
                scoreDict['score'] = '{0}-{1}'.format(game.homeScore, game.awayScore)
            elif game.awayTeam.name == game.winningTeam.name:
                scoreDict['score'] = '{0}-{1}'.format(game.awayScore, game.homeScore)
        dict[game.id] = scoreDict
    return dict

@app.get('/results')
async def returnResults(week = None):
    dict = {}
    if week is None:
        dict['week'] = floosball.activeSeason.currentWeek
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
                dict[game.id] = resultsDict
    else:
        dict['week'] = week
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
                dict[game.id] = resultsDict
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
        


