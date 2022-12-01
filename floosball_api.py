import math
from random import randint
from re import T
from turtle import home
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
    if id is None:
        divList = []
        for division in floosball.divisionList:
            divDict = {}
            teamList = []
            divDict['divisionName'] = division.name
            division: floosball.Division
            for team in division.teamList:
                team: Team
                teamDict = {}
                scheduleList = []
                teamDict['name'] = team.name
                teamDict['city'] = team.city
                teamDict['color'] = team.color
                teamDict['id'] = team.id
                teamDict['championships'] = team.leagueChampionships
                teamDict['eliminated'] = team.eliminated
                teamDict['ratingStars'] = round((((team.overallRating - 60)/40)*4)+1)
                teamDict['offenseRatingStars'] = round((((team.offenseRating - 60)/40)*4)+1)
                teamDict['defenseRatingStars'] = team.defenseTier
                teamDict['runDefenseRating'] = round((((team.runDefenseRating - 60)/40)*4)+1)
                teamDict['passDefenseRating'] = round((((team.passDefenseRating - 60)/40)*4)+1)
                teamDict['wins'] = team.seasonTeamStats['wins']
                teamDict['losses'] = team.seasonTeamStats['losses']
                if (team.seasonTeamStats['wins']+team.seasonTeamStats['losses']) > 0:
                    teamDict['winPerc'] = '{:.3f}'.format(round(team.seasonTeamStats['wins']/(team.seasonTeamStats['wins']+team.seasonTeamStats['losses']),3))
                else:
                    teamDict['winPerc'] = '0.000'

                if team.seasonTeamStats['scoreDiff'] >= 0:
                    teamDict['pointDiff'] = '+{}'.format(team.seasonTeamStats['scoreDiff'])
                else:
                    teamDict['pointDiff'] = '{}'.format(team.seasonTeamStats['scoreDiff'])

                teamDict['divWins'] = team.seasonTeamStats['divWins']
                teamDict['divLosses'] = team.seasonTeamStats['divLosses']
                teamDict['divWinPerc'] = team.seasonTeamStats['divWinPerc']
                if team.seasonTeamStats['streak'] >= 0:
                    teamDict['streak'] = 'W{}'.format(team.seasonTeamStats['streak'])
                else:
                    teamDict['streak'] = 'L{}'.format(abs(team.seasonTeamStats['streak']))
                teamList.append(teamDict)
            list.sort(teamList, key=lambda team: team['winPerc'], reverse=True)
            divDict['teams'] = teamList
            divList.append(divDict)
        list.sort(divList, key=lambda division: division['divisionName'])
        return divList
    else:
        for team in floosball.teamList:
            if team.id == int(id):
                teamDict = {}
                scheduleList = []
                teamDict['name'] = team.name
                teamDict['city'] = team.city
                teamDict['color'] = team.color
                teamDict['id'] = team.id
                teamDict['eliminated'] = team.eliminated
                teamDict['championships'] = team.leagueChampionships
                teamDict['ratingStars'] = round((((team.overallRating - 60)/60)*4)+1)
                teamDict['offenseRatingStars'] = round((((team.offenseRating - 60)/40)*4)+1)
                teamDict['defenseRatingStars'] = team.defenseTier
                teamDict['runDefenseRating'] = round((((team.runDefenseRating - 60)/40)*4)+1)
                teamDict['passDefenseRating'] = round((((team.passDefenseRating - 60)/60)*4)+1)
                teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating
                teamDict['wins'] = team.seasonTeamStats['wins']
                teamDict['losses'] = team.seasonTeamStats['losses']

                pointDiff = team.seasonTeamStats['Offense']['pts'] - team.seasonTeamStats['Defense']['ptsAlwd']
                if pointDiff >= 0:
                    teamDict['pointDiff'] = '+{}'.format(pointDiff)
                else:
                    teamDict['pointDiff'] = '{}'.format(pointDiff)

                x = 1
                for game in team.schedule:
                    game: FloosGame.Game
                    gameDict = {}
                    if game.homeTeam.name == team.name:
                        gameDict['isHomeTeam'] = True
                        gameDict['vsTeam'] = game.awayTeam.name
                        gameDict['vsTeamID'] = game.awayTeam.id
                        gameDict['vsCity'] = game.awayTeam.city
                        gameDict['vsAbbr'] = game.awayTeam.abbr
                        gameDict['vsColor'] = game.awayTeam.color
                        gameDict['vsRecord'] = '{}-{}'.format(game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'])
                        if game.homeScore > game.awayScore and game.status.name == 'Final':
                            gameDict['isWin'] = True
                        else:
                            gameDict['isWin'] = False
                    else:
                        gameDict['isHomeTeam'] = False
                        gameDict['vsTeam'] = game.homeTeam.name
                        gameDict['vsTeamID'] = game.homeTeam.id
                        gameDict['vsCity'] = game.homeTeam.city
                        gameDict['vsAbbr'] = game.homeTeam.abbr
                        gameDict['vsColor'] = game.homeTeam.color
                        gameDict['vsRecord'] = '{}-{}'.format(game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
                        if game.awayScore > game.homeScore and game.status.name == 'Final':
                            gameDict['isWin'] = True
                        else:
                            gameDict['isWin'] = False

                    gameDict['status'] = game.status.name
                    gameDict['id'] = game.id
                    gameDict['week'] = 'Week {}'.format(x)
                    gameDict['homeScore'] = game.homeScore
                    gameDict['awayScore'] = game.awayScore
                    scheduleList.append(gameDict)
                    x += 1
                teamDict['schedule'] = scheduleList
                rosterDict = {}
                for pos, player in team.rosterDict.items():
                    playerDict = {}
                    playerDict['name'] = player.name
                    playerDict['pos'] = player.position.name
                    playerDict['id'] = player.id
                    playerDict['rating'] = player.attributes.overallRating
                    playerDict['ratingStars'] = player.playerTier.value
                    playerDict['term'] = player.term
                    playerDict['gamesPlayed'] = player.gamesPlayed
                    playerDict['seasonPerformanceRating'] = player.seasonPerformanceRating
                    playerDict['seasonStats'] = player.seasonStatsDict
                    rosterDict[pos] = playerDict
                teamDict['roster'] = rosterDict
                reserveList = []
                for pos, player in team.reserveRosterDict.items():
                    if isinstance(player, Player):
                        playerDict = {}
                        playerDict['name'] = player.name
                        playerDict['id'] = player.id
                        playerDict['pos'] = player.position.name
                        playerDict['rating'] = player.attributes.overallRating
                        playerDict['ratingStars'] = player.playerTier.value
                        playerDict['term'] = player.term
                        playerDict['gamesPlayed'] = player.gamesPlayed
                        playerDict['seasonPerformanceRating'] = player.seasonPerformanceRating
                        playerDict['seasonStats'] = player.seasonStatsDict
                        reserveList.append(playerDict)
                teamDict['reserves'] = reserveList
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
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['seasons'] = player.seasonsPlayed
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
                dict['ratingStars'] = player.playerTier.value
                dict['rating'] = player.attributes.overallRating
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
                dict['seasonStats'] = player.seasonStatsDict
                dict['careerStats'] = player.careerStatsDict
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
            teamDict['name'] = '{0} {1}'.format(team.city, team.name)
            teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            teamDict['winPerc'] = team.seasonTeamStats['winPerc']
            pointDiff = team.seasonTeamStats['Offense']['pts'] - team.seasonTeamStats['Defense']['ptsAlwd']
            if pointDiff >= 0:
                teamDict['pointDiff'] = '+{}'.format(pointDiff)
            else:
                teamDict['pointDiff'] = '{}'.format(pointDiff)
            if team.seasonTeamStats['streak'] >= 0:
                teamDict['streak'] = 'W{}'.format(team.seasonTeamStats['streak'])
            else:
                teamDict['streak'] = 'L{}'.format(abs(team.seasonTeamStats['streak']))
            teamsList.append(teamDict)
            divDict['standings'] = teamsList
        standingsList.append(divDict)
    return standingsList

@app.get('/schedule')
async def returnSchedule():
    weekDict = {}
    for y in range(len(floosball.scheduleList)):
        weekGameList = floosball.scheduleList[y]
        gameList = []
        for x in range(0,len(weekGameList)):
            game: FloosGame.Game = weekGameList[x]
            gameDict = {}
            gameDict['id'] = game.id
            gameDict['homeTeam'] = game.homeTeam.name
            gameDict['homeCity'] = game.homeTeam.city
            gameDict['homeColor'] = game.homeTeam.color
            gameDict['homeRecord'] = '{}-{}'.format(game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
            gameDict['awayTeam'] = game.awayTeam.name
            gameDict['awayCity'] = game.awayTeam.city
            gameDict['awayColor'] = game.awayTeam.color
            gameDict['awayRecord'] = '{}-{}'.format(game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'])
            gameDict['status'] = game.status.name
            gameDict['homeScore'] = game.homeScore
            gameDict['awayScore'] = game.awayScore
            if game.status.name == 'Final':
                gameDict['winningTeam'] = game.winningTeam.name
                gameDict['losingTeam'] = game.losingTeam.name
            else:
                gameDict['winningTeam'] = None
                gameDict['losingTeam'] = None
            gameList.append(gameDict)
        weekDict['Week {}'.format(y+1)] = gameList
    return weekDict

@app.get('/game')
async def returnGame(id = None):
    if id is None:
        return 'No ID specified'
    else:
        gameDict = {}
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList)):
                game = weekGameList[x]
                game: FloosGame.Game
                if id == game.id:
                    gameDict['status'] = game.status.name
                    gameDict['homeCity'] = game.homeTeam.city
                    gameDict['homeTeam'] = game.homeTeam.name
                    gameDict['homeTeamColor'] = game.homeTeam.color
                    gameDict['homeTeamRecord'] = '{0}-{1}'.format(game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
                    gameDict['awayCity'] = game.awayTeam.city
                    gameDict['awayTeam'] = game.awayTeam.name
                    gameDict['awayTeamColor'] = game.awayTeam.color
                    gameDict['awayTeamRecord'] = '{0}-{1}'.format(game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'])
                    gameDict['homeScore'] = game.homeScore
                    gameDict['awayScore'] = game.awayScore
                    if game.currentQuarter == 5:
                        gameDict['quarter'] = 'OT'
                    else:
                        gameDict['quarter'] = game.currentQuarter
                    gameDict['plays'] = game.totalPlays
                    if game.offensiveTeam == game.homeTeam:
                        gameDict['homeTeamPoss'] = True
                        gameDict['awayTeamPoss'] = False
                    else:
                        gameDict['homeTeamPoss'] = False
                        gameDict['awayTeamPoss'] = True
                    if game.offensiveTeam == game.homeTeam:
                        gameDict['homeTeamPoss'] = True
                        gameDict['awayTeamPoss'] = False
                    else:
                        gameDict['homeTeamPoss'] = False
                        gameDict['awayTeamPoss'] = True
                    gameDict['down'] = game.down
                    if game.down == 1:
                        down = '1st'
                    elif game.down == 2:
                        down = '2nd'
                    elif game.down == 3:
                        down = '3rd'
                    elif game.down == 4:
                        down = '4th'
                    gameDict['downText'] = '{0} & {1}'.format(down, game.yardsToFirstDown)
                    if game.yardsToEndzone < 10:
                        gameDict['yardsTo1stDwn'] = game.yardsToEndzone
                    else:
                        gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
                    gameDict['yardsToEZ'] = game.yardsToEndzone
                    gameDict['yardLine'] = game.yardLine
                    gameDict['playsLeft'] = 132 - game.totalPlays
                    return gameDict
        if len(dict) == 0:
            return 'Game Not Found'
        else: return dict

@app.get('/currentGames')
async def returnCurrentGames():
    gameList = []
    activeGameList = floosball.activeSeason.activeGames
    for x in range(0,len(activeGameList)):
        gameDict = {}
        game: FloosGame.Game = activeGameList[x]
        gameDict['id'] = game.id
        gameDict['game'] = x+1
        gameDict['status'] = game.status.name
        gameDict['isHalftime'] = game.isHalftime
        gameDict['isOvertime'] = game.isOvertime
        gameDict['homeCity'] = game.homeTeam.city
        gameDict['homeTeam'] = game.homeTeam.name
        gameDict['homeTeamColor'] = game.homeTeam.color
        gameDict['homeTeamRecord'] = '{0}-{1}'.format(game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
        gameDict['awayCity'] = game.awayTeam.city
        gameDict['awayTeam'] = game.awayTeam.name
        gameDict['awayTeamColor'] = game.awayTeam.color
        gameDict['awayTeamRecord'] = '{0}-{1}'.format(game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'])
        gameDict['homeScore'] = game.homeScore
        gameDict['awayScore'] = game.awayScore
        if game.currentQuarter == 5:
            gameDict['quarter'] = 'OT'
        else:
            gameDict['quarter'] = game.currentQuarter
        gameDict['plays'] = game.totalPlays
        if game.offensiveTeam == game.homeTeam:
            gameDict['homeTeamPoss'] = True
            gameDict['awayTeamPoss'] = False
        else:
            gameDict['homeTeamPoss'] = False
            gameDict['awayTeamPoss'] = True
        gameDict['down'] = game.down
        if game.down == 1:
            down = '1st'
        elif game.down == 2:
            down = '2nd'
        elif game.down == 3:
            down = '3rd'
        elif game.down == 4:
            down = '4th'
        else:
            down = '1st'
        gameDict['downText'] = '{0} & {1}'.format(down, game.yardsToFirstDown)
        gameDict['playsLeft'] = 132 - game.totalPlays
        if game.yardsToEndzone < 10:
            gameDict['yardsTo1stDwn'] = game.yardsToEndzone
        else:
            gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
        gameDict['yardsToEZ'] = game.yardsToEndzone
        gameDict['yardLine'] = game.yardLine
        gameList.append(gameDict)
    return gameList

@app.get('/results')
async def returnResults(week = None, season = None):
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
                game: FloosGame.Game = weekGameList[x]
                if id == game.id:
                    if game.status is FloosGame.GameStatus.Active:
                        return game.getGameData()
                    elif game.status is FloosGame.GameStatus.Final:
                        return game.gameDict['gameStats']
        else:
            return 'Game Not Found'

@app.get('/plays')
async def returnPlays(id = None):
    if id is None:
        return 'No ID specified'
    else:
        playList = []
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList)):
                game: FloosGame.Game = weekGameList[x]
                if id == game.id:
                    for play in game.playsList:
                        play: FloosGame.Play
                        playDict = {}
                        playDict['playText'] = play.playText
                        playDict['team'] = play.offense.name
                        playDict['homeAbbr'] = game.homeTeam.abbr
                        playDict['awayAbbr'] = game.awayTeam.abbr
                        playDict['yardLine'] = play.yardLine
                        if play.down == 1:
                            down = '1st'
                        elif play.down == 2:
                            down = '2nd'
                        elif play.down == 3:
                            down = '3rd'
                        elif play.down == 4:
                            down = '4th'
                        else:
                            down = '1st'
                        playDict['down'] = '{} & {}'.format(down, play.yardsTo1st)
                        playDict['result'] = play.playResult.value
                        playDict['homeScore'] = play.homeTeamScore
                        playDict['awayScore'] = play.awayTeamScore
                        playDict['color'] = play.offense.color
                        playDict['quarter'] = play.quarter
                        playDict['playsLeft'] = play.playsLeft
                        playDict['scoreChange'] = play.scoreChange
                        playDict['isTd'] = play.isTd
                        playDict['isFg'] = play.isFgGood
                        playDict['isSafety'] = play.isSafety
                        playList.append(playDict)
                    return(playList)
        else:
            return 'Game Not Found'

@app.get('/scoringPlays')
async def returnScoringPlays(id = None):
    if id is None:
        return 'No ID specified'
    else:
        playList = []
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList)):
                game: FloosGame.Game = weekGameList[x]
                if id == game.id:
                    for play in game.scoringPlaysList:
                        play: FloosGame.Play
                        playDict = {}
                        playDict['playText'] = play.playText
                        playDict['team'] = play.offense.name
                        playDict['homeAbbr'] = game.homeTeam.abbr
                        playDict['awayAbbr'] = game.awayTeam.abbr
                        playDict['yardLine'] = play.yardLine
                        if play.down == 1:
                            down = '1st'
                        elif play.down == 2:
                            down = '2nd'
                        elif play.down == 3:
                            down = '3rd'
                        elif play.down == 4:
                            down = '4th'
                        else:
                            down = '1st'
                        playDict['down'] = '{} & {}'.format(down, play.yardsTo1st)
                        playDict['yardage'] = play.yardage
                        playDict['result'] = play.playResult.value
                        playDict['homeScore'] = play.homeTeamScore
                        playDict['awayScore'] = play.awayTeamScore
                        playDict['color'] = play.offense.color
                        playDict['quarter'] = play.quarter
                        playDict['playsLeft'] = play.playsLeft
                        playDict['scoreChange'] = play.scoreChange
                        playDict['isTd'] = play.isTd
                        playDict['isFg'] = play.isFgGood
                        playDict['isSafety'] = play.isSafety
                        playList.append(playDict)
                    return(playList)
        else:
            return 'Game Not Found'

@app.get('/draftResults')
async def returnDraftResults(season = None, id = None):
    if id is None:
        if season is None:
            return floosball.rookieDraftHistoryDict
        else:
            return floosball.rookieDraftHistoryDict['offseason {}'.format(season)]
    else:
        for team in floosball.teamList:
            team: Team
            if team.id == int(id):
                return team.draftHistory

@app.get('/freeAgency')
async def returnDraftResults(season = None, id = None):
    if id is None:
        if season is None:
            return floosball.freeAgencyHistoryDict
        else:
            return floosball.freeAgencyHistoryDict['offseason {}'.format(season)]
    else:
        for team in floosball.teamList:
            team: Team
            if team.id == int(id):
                return team.freeAgentHistory

@app.get('/rosterHistory')
async def returnTeamRosters(id = None):
    team: Team
    for team in floosball.teamList:
        if team.id == int(id):
            return team.rosterHistory

@app.get('/playerStats')
async def returnPlayerStats(pos = None):
    statList = []
    playerList = []
    if pos == 'D':
        for team in floosball.teamList:
            teamDict = {}
            team: Team
            teamDict['name'] = team.name
            teamDict['ratingStars'] = team.defenseTier
            teamDict['seasonStats'] = team.seasonTeamStats['Defense']
            statList.append(teamDict)
    elif pos == 'O':
        for team in floosball.teamList:
            teamDict = {}
            team: Team
            teamDict['name'] = team.name
            teamDict['ratingStars'] = team.defenseTier
            teamDict['seasonStats'] = team.seasonTeamStats['Offense']
            statList.append(teamDict)
    else:
        if pos == 'QB':
            playerList = floosball.activeQbList
        elif pos == 'RB':
            playerList = floosball.activeRbList
        elif pos == 'WR':
            playerList = floosball.activeWrList
        elif pos == 'TE':
            playerList = floosball.activeTeList
        elif pos == 'K':
            playerList = floosball.activeKList

        for player in playerList:
            player: Player
            playerDict = {}
            if isinstance(player.team, Team):
                playerDict['name'] = player.name
                playerDict['team'] = player.team.name
                playerDict['ratingStars'] = player.playerTier.value
                playerDict['seasonStats'] = player.seasonStatsDict
                statList.append(playerDict)
    return statList


@app.get('/seasonInfo')
async def returnSeasonInfo():
    return {'season': floosball.activeSeason.currentSeason, 'currentWeek': floosball.activeSeason.currentWeek}
            

@app.get('/info')
async def returnInfo():
    return floosball.__version__



uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

