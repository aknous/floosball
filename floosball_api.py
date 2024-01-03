import math
from random import randint
from re import T
#from turtle import home
import floosball
import floosball_game as FloosGame
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import json
import uvicorn
import datetime
from operator import itemgetter
from floosball_player import Player, Position, PlayerServiceTime

from floosball_team import Team

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://floosball.com"
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
                teamDict['name'] = team.name
                teamDict['city'] = team.city
                teamDict['color'] = team.color
                teamDict['id'] = team.id
                teamDict['elo'] = team.elo
                teamDict['eliminated'] = team.eliminated
                teamDict['wins'] = team.seasonTeamStats['wins']
                teamDict['losses'] = team.seasonTeamStats['losses']
                teamDict['clinchedPlayoffs'] = team.clinchedPlayoffs
                teamDict['clinchedDivision'] = team.clinchedDivision
                teamDict['clinchedTopSeed'] = team.clinchedTopSeed
                teamDict['leagueChampion'] = team.leagueChampion
                teamDict['winningStreak'] = team.winningStreak
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
                teamDict['name'] = team.name
                teamDict['city'] = team.city
                teamDict['color'] = team.color
                teamDict['id'] = team.id
                teamDict['elo'] = team.elo
                teamDict['division'] = team.division
                teamDict['eliminated'] = team.eliminated
                teamDict['championships'] = team.leagueChampionships
                teamDict['regularSeasonChampions'] = team.regularSeasonChampions
                teamDict['divisionChampionships'] = team.divisionChampionships
                teamDict['ratingStars'] = round((((team.overallRating - 60)/60)*4)+1)
                teamDict['offenseRatingStars'] = round((((team.offenseRating - 60)/40)*4)+1)
                teamDict['defenseRatingStars'] = team.defenseOverallTier
                teamDict['runDefenseRating'] = round((((team.defenseRunCoverageRating - 60)/40)*4)+1)
                teamDict['passDefenseRating'] = round((((team.defensePassCoverageRating - 60)/60)*4)+1)
                teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating
                teamDict['wins'] = team.seasonTeamStats['wins']
                teamDict['losses'] = team.seasonTeamStats['losses']
                teamDict['allTimeStats'] = team.allTimeTeamStats
                teamDict['history'] = team.statArchive
                teamDict['clinchedPlayoffs'] = team.clinchedPlayoffs
                teamDict['clinchedDivision'] = team.clinchedDivision
                teamDict['clinchedTopSeed'] = team.clinchedTopSeed
                teamDict['leagueChampion'] = team.leagueChampion
                teamDict['winningStreak'] = team.winningStreak

                pointDiff = team.seasonTeamStats['Offense']['pts'] - team.seasonTeamStats['Defense']['ptsAlwd']
                if pointDiff >= 0:
                    teamDict['pointDiff'] = '+{}'.format(pointDiff)
                else:
                    teamDict['pointDiff'] = '{}'.format(pointDiff)

                return teamDict

@app.get('/players')
async def returnPlayers(id = None):
    playerList = []
    if id is None:
        for player in floosball.activePlayerList:
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['rank'] = player.serviceTime
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
    elif id == 'FA':
        for player in floosball.freeAgentList:
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['rank'] = player.serviceTime
            playerDict['id'] = player.id
            playerDict['team'] = 'Free Agent'
            playerDict['position'] = player.position.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['seasons'] = player.seasonsPlayed
            playerList.append(playerDict)
        return playerList
    elif id == 'Retired':
        for player in floosball.retiredPlayersList:
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['rank'] = player.serviceTime
            playerDict['id'] = player.id
            playerDict['team'] = 'Retired'
            playerDict['position'] = player.position.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['seasons'] = player.seasonsPlayed
            playerList.append(playerDict)
        return playerList
    elif id == 'HoF':
        for player in floosball.hallOfFame:
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['rank'] = player.serviceTime
            playerDict['id'] = player.id
            playerDict['team'] = 'Retired'
            playerDict['position'] = player.position.name
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['seasons'] = player.seasonsPlayed
            playerList.append(playerDict)
        return playerList
    else:
        id = int(id)
        selectedPlayer: Player = None
        if selectedPlayer is None:
            for player in floosball.retiredPlayersList:
                if player.id == id:
                    selectedPlayer = player
        if selectedPlayer is None:
            for player in floosball.hallOfFame:
                if player.id == id:
                    selectedPlayer = player
        if selectedPlayer is None:
            for player in floosball.activePlayerList:
                if player.id == id:
                    selectedPlayer = player

        if selectedPlayer is not None:
            dict = {}
            dict['name'] = selectedPlayer.name
            dict['rank'] = selectedPlayer.serviceTime
            dict['number'] = selectedPlayer.currentNumber
            if selectedPlayer.serviceTime.value == 'Retired':
                dict['team'] = 'Retired'
                dict['city'] = ''
                dict['color'] = '#94a3b8'
            elif selectedPlayer.team is None or selectedPlayer.team == 'Free Agent':
                dict['team'] = 'Free Agent'
                dict['city'] = ''
                dict['color'] = '#94a3b8'
            else:
                dict['team'] = selectedPlayer.team.name
                dict['city'] = selectedPlayer.team.city
                dict['color'] = selectedPlayer.team.color
            dict['position'] = selectedPlayer.position.name
            dict['tierStars'] = selectedPlayer.playerTier.value
            dict['ratingValue'] = selectedPlayer.attributes.overallRating
            dict['ratingStars'] = selectedPlayer.playerTier.value
            dict['term'] = selectedPlayer.term
            dict['termRemaining'] = selectedPlayer.termRemaining
            dict['championships'] = selectedPlayer.leagueChampionships
            attDict = {}
            if selectedPlayer.position is Position.QB:
                attDict['att1Name'] = 'Arm Strength'
                attDict['att2Name'] = 'Accuracy'
                attDict['att3Name'] = 'Agility'
                attDict['att1stars'] = round((((selectedPlayer.attributes.armStrength - 60)/40)*4)+1)
                attDict['att2stars'] = round((((selectedPlayer.attributes.accuracy - 60)/40)*4)+1)
                attDict['att3stars'] = round((((selectedPlayer.attributes.agility - 60)/40)*4)+1)
                attDict['att1value'] = selectedPlayer.attributes.armStrength
                attDict['att2value'] = selectedPlayer.attributes.accuracy
                attDict['att3value'] = selectedPlayer.attributes.agility
                attDict['att1PotStars'] = round((((selectedPlayer.attributes.potentialArmStrength - 60)/40)*4)+1)
                attDict['att2PotStars'] = round((((selectedPlayer.attributes.potentialAccuracy - 60)/40)*4)+1)
                attDict['att3PotStars'] = round((((selectedPlayer.attributes.potentialAgility - 60)/40)*4)+1)
            elif selectedPlayer.position is Position.RB:
                attDict['att1Name'] = 'Speed'
                attDict['att2Name'] = 'Power'
                attDict['att3Name'] = 'Agility'
                attDict['att1stars'] = round((((selectedPlayer.attributes.speed - 60)/40)*4)+1)
                attDict['att2stars'] = round((((selectedPlayer.attributes.power - 60)/40)*4)+1)
                attDict['att3stars'] = round((((selectedPlayer.attributes.agility - 60)/40)*4)+1)
                attDict['att1value'] = selectedPlayer.attributes.speed
                attDict['att2value'] = selectedPlayer.attributes.power
                attDict['att3value'] = selectedPlayer.attributes.agility
                attDict['att1PotStars'] = round((((selectedPlayer.attributes.potentialSpeed - 60)/40)*4)+1)
                attDict['att2PotStars'] = round((((selectedPlayer.attributes.potentialPower - 60)/40)*4)+1)
                attDict['att3PotStars'] = round((((selectedPlayer.attributes.potentialAgility - 60)/40)*4)+1)
            elif selectedPlayer.position is Position.WR:
                attDict['att1Name'] = 'Speed'
                attDict['att2Name'] = 'Hands'
                attDict['att3Name'] = 'Agility'
                attDict['att1stars'] = round((((selectedPlayer.attributes.speed - 60)/40)*4)+1)
                attDict['att2stars'] = round((((selectedPlayer.attributes.hands - 60)/40)*4)+1)
                attDict['att3stars'] = round((((selectedPlayer.attributes.agility - 60)/40)*4)+1)
                attDict['att1value'] = selectedPlayer.attributes.speed
                attDict['att2value'] = selectedPlayer.attributes.hands
                attDict['att3value'] = selectedPlayer.attributes.agility
                attDict['att1PotStars'] = round((((selectedPlayer.attributes.potentialSpeed - 60)/40)*4)+1)
                attDict['att2PotStars'] = round((((selectedPlayer.attributes.potentialHands - 60)/40)*4)+1)
                attDict['att3PotStars'] = round((((selectedPlayer.attributes.potentialAgility - 60)/40)*4)+1)
            elif selectedPlayer.position is Position.TE:
                attDict['att1Name'] = 'Hands'
                attDict['att2Name'] = 'Power'
                attDict['att3Name'] = 'Agility'
                attDict['att1stars'] = round((((selectedPlayer.attributes.hands - 60)/40)*4)+1)
                attDict['att2stars'] = round((((selectedPlayer.attributes.power - 60)/40)*4)+1)
                attDict['att3stars'] = round((((selectedPlayer.attributes.agility - 60)/40)*4)+1)
                attDict['att1value'] = selectedPlayer.attributes.hands
                attDict['att2value'] = selectedPlayer.attributes.power
                attDict['att3value'] = selectedPlayer.attributes.agility
                attDict['att1PotStars'] = round((((selectedPlayer.attributes.potentialHands - 60)/40)*4)+1)
                attDict['att2PotStars'] = round((((selectedPlayer.attributes.potentialPower - 60)/40)*4)+1)
                attDict['att3PotStars'] = round((((selectedPlayer.attributes.potentialAgility - 60)/40)*4)+1)
            elif selectedPlayer.position is Position.K:
                attDict['att1Name'] = 'Leg Strength'
                attDict['att2Name'] = 'Accuracy'
                attDict['att3Name'] = ''
                attDict['att1stars'] = round((((selectedPlayer.attributes.legStrength - 60)/40)*4)+1)
                attDict['att2stars'] = round((((selectedPlayer.attributes.accuracy - 60)/40)*4)+1)
                attDict['att3stars'] = 0
                attDict['att1value'] = selectedPlayer.attributes.legStrength
                attDict['att2value'] = selectedPlayer.attributes.accuracy
                attDict['att3value'] = 0
                attDict['att1PotStars'] = round((((selectedPlayer.attributes.potentialLegStrength - 60)/40)*4)+1)
                attDict['att2PotStars'] = round((((selectedPlayer.attributes.potentialAccuracy - 60)/40)*4)+1)
                attDict['att3PotStars'] = 0
            attDict['playmakingStars'] = round((((selectedPlayer.attributes.playMakingAbility - 60)/40)*4)+1)
            attDict['playmakingValue'] = selectedPlayer.attributes.playMakingAbility
            attDict['xFactorStars'] = round((((selectedPlayer.attributes.xFactor - 60)/40)*4)+1)
            attDict['xFactorValue'] = selectedPlayer.attributes.xFactor
            dict['attributes'] = attDict
            if selectedPlayer.seasonPerformanceRating > 0:
                dict['seasonPerformanceRatingStars'] = round(((selectedPlayer.seasonPerformanceRating * 4)/100)+1)
                dict['seasonPerformanceRatingValue'] = selectedPlayer.seasonPerformanceRating
            else:
                dict['seasonPerformanceRatingStars'] = 0
                dict['seasonPerformanceRatingValue'] = 0
            dict['stats'] = selectedPlayer.seasonStatsArchive
            dict['allTimeStats'] = selectedPlayer.careerStatsDict
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
async def returnSchedule(id = None):
    for team in floosball.teamList:
            if team.id == int(id):
                scheduleList = []
                x = 1
                for game in team.schedule:
                    game: FloosGame.Game
                    gameDict = {}
                    gameDict['id'] = game.id
                    gameDict['week'] = 'Week {}'.format(x)
                    gameDict['startTime'] = datetime.datetime.timestamp(game.startTime)
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
                    gameDict['playsLeft'] = 132 - game.totalPlays
                    if game.yardsToEndzone < 10:
                        gameDict['yardsTo1stDwn'] = game.yardsToEndzone
                        gameDict['downText'] = '{0} & Goal'.format(down)
                    else:
                        gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
                        gameDict['downText'] = '{0} & {1}'.format(down, game.yardsToFirstDown)
                    gameDict['yardsToEZ'] = game.yardsToEndzone
                    gameDict['yardLine'] = game.yardLine
                    if game.status is FloosGame.GameStatus.Scheduled:
                        gameDict['homeTeamElo'] = game.homeTeam.elo
                        gameDict['awayTeamElo'] = game.awayTeam.elo
                    else:
                        gameDict['homeTeamElo'] = game.homeTeamElo
                        gameDict['awayTeamElo'] = game.awayTeamElo
                    scheduleList.append(gameDict)
                    x += 1
                return scheduleList


@app.get('/game')
async def returnGame(id = None):
    if id is None:
        return 'No ID specified'
    else:
        gameDict = {}
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList['games'])):
                game = weekGameList['games'][x]
                game: FloosGame.Game
                if id == game.id:
                    gameDict['status'] = game.status.name
                    gameDict['startTime'] = datetime.datetime.timestamp(game.startTime)
                    gameDict['homeCity'] = game.homeTeam.city
                    gameDict['homeTeam'] = game.homeTeam.name
                    gameDict['homeTeamColor'] = game.homeTeam.color
                    gameDict['homeTeamWinProbability'] = round(game.homeTeamWinProbability*100)
                    gameDict['homeTeamRecord'] = '{0}-{1}'.format(game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
                    gameDict['awayCity'] = game.awayTeam.city
                    gameDict['awayTeam'] = game.awayTeam.name
                    gameDict['awayTeamColor'] = game.awayTeam.color
                    gameDict['awayTeamWinProbability'] = round(game.awayTeamWinProbability*100)
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
                    if game.yardsToEndzone <= 10:
                        gameDict['yardsTo1stDwn'] = game.yardsToEndzone
                        gameDict['downText'] = '{0} & Goal'.format(down)
                    else:
                        gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
                        gameDict['downText'] = '{0} & {1}'.format(down, game.yardsToFirstDown)
                    gameDict['yardsToEZ'] = game.yardsToEndzone
                    gameDict['yardLine'] = game.yardLine
                    gameDict['playsLeft'] = 132 - game.totalPlays
                    if game.status is FloosGame.GameStatus.Scheduled:
                        gameDict['homeTeamElo'] = game.homeTeam.elo
                        gameDict['awayTeamElo'] = game.awayTeam.elo
                    else:
                        gameDict['homeTeamElo'] = game.homeTeamElo
                        gameDict['awayTeamElo'] = game.awayTeamElo
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
        gameDict['startTime'] = datetime.datetime.timestamp(game.startTime)
        gameDict['game'] = x+1
        gameDict['status'] = game.status.name
        gameDict['isHalftime'] = game.isHalftime
        gameDict['isOvertime'] = game.isOvertime
        gameDict['homeCity'] = game.homeTeam.city
        gameDict['homeTeam'] = game.homeTeam.name
        gameDict['homeTeamColor'] = game.homeTeam.color
        gameDict['homeTeamWinProbability'] = round(game.homeTeamWinProbability*100)
        gameDict['homeTeamRecord'] = '{0}-{1}'.format(game.homeTeam.seasonTeamStats['wins'], game.homeTeam.seasonTeamStats['losses'])
        gameDict['awayCity'] = game.awayTeam.city
        gameDict['awayTeam'] = game.awayTeam.name
        gameDict['awayTeamColor'] = game.awayTeam.color
        gameDict['awayTeamWinProbability'] = round(game.awayTeamWinProbability*100)
        gameDict['awayTeamRecord'] = '{0}-{1}'.format(game.awayTeam.seasonTeamStats['wins'], game.awayTeam.seasonTeamStats['losses'])
        gameDict['homeScore'] = game.homeScore
        gameDict['awayScore'] = game.awayScore
        gameDict['homeIsEliminated'] = game.homeTeam.eliminated
        gameDict['awayIsEliminated'] = game.awayTeam.eliminated
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
        gameDict['playsLeft'] = 132 - game.totalPlays
        if game.yardsToEndzone < 10:
            gameDict['yardsTo1stDwn'] = game.yardsToEndzone
            gameDict['downText'] = '{0} & Goal'.format(down)
        else:
            gameDict['yardsTo1stDwn'] = game.yardsToFirstDown
            gameDict['downText'] = '{0} & {1}'.format(down, game.yardsToFirstDown)
        gameDict['yardsToEZ'] = game.yardsToEndzone
        gameDict['yardLine'] = game.yardLine
        if game.status is FloosGame.GameStatus.Scheduled:
            gameDict['homeTeamElo'] = game.homeTeam.elo
            gameDict['awayTeamElo'] = game.awayTeam.elo
        else:
            gameDict['homeTeamElo'] = game.homeTeamElo
            gameDict['awayTeamElo'] = game.awayTeamElo
        gameList.append(gameDict)
    list.sort(gameList, key=itemgetter('status'), reverse=False)
    return gameList

@app.get('/results')
async def returnResults(week = None):
    gameList = []
    weekGameList = floosball.scheduleList[int(week)-1]
    for x in range(0,len(weekGameList['games'])):
        game: FloosGame.Game = weekGameList['games'][x]
        gameDict = {}
        gameDict['id'] = game.id
        gameDict['status'] = game.status.name
        gameDict['startTime'] = datetime.datetime.timestamp(game.startTime)
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
        if game.homeScore > game.awayScore:
            gameDict['homeWinner'] = True
            gameDict['awayWinner'] = False
        else:
            gameDict['awayWinner'] = True
            gameDict['homeWinner'] = False
        if game.status is FloosGame.GameStatus.Final:
            gameDict['homeElo'] = game.homeTeamElo
            gameDict['awayElo'] = game.awayTeamElo
        else:
            gameDict['homeElo'] = game.homeTeam.elo
            gameDict['awayElo'] = game.awayTeam.elo

        gameList.append(gameDict)
    return gameList

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
    
@app.get('/powerRankings')
async def returnPowerRankings():
    teamListRanked = floosball.teamList.copy()
    list.sort(teamListRanked, key=lambda team: (team.elo,team.overallRating), reverse=True)
    teamList = []
    for team in teamListRanked:
        team: Team
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['color'] = team.color
        teamDict['id'] = team.id
        teamDict['elo'] = team.elo
        teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
        teamDict['eliminated'] = team.eliminated
        teamDict['winningStreak'] = team.winningStreak
        teamList.append(teamDict)
    return teamList

@app.get('/playoffPicture')
async def returnPlayoffPicture():
    playoffList = []
    divisionLeadersList = []
    playoffTeamsList = []
    nonPlayoffTeamsList = []

    for team in floosball.activeSeason.divisionLeadersList:
        team: Team
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['color'] = team.color
        teamDict['id'] = team.id
        teamDict['elo'] = team.elo
        teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
        teamDict['eliminated'] = team.eliminated
        teamDict['clinchedPlayoffs'] = team.clinchedPlayoffs
        teamDict['clinchedDivision'] = team.clinchedDivision
        teamDict['clinchedTopSeed'] = team.clinchedTopSeed
        teamDict['leagueChampion'] = team.leagueChampion
        teamDict['winningStreak'] = team.winningStreak
        divisionLeadersList.append(teamDict)

    for team in floosball.activeSeason.nonDivisionLeaderPlayoffTeamsList:
        team: Team
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['color'] = team.color
        teamDict['id'] = team.id
        teamDict['elo'] = team.elo
        teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
        teamDict['eliminated'] = team.eliminated
        teamDict['clinchedPlayoffs'] = team.clinchedPlayoffs
        teamDict['clinchedDivision'] = team.clinchedDivision
        teamDict['clinchedTopSeed'] = team.clinchedTopSeed
        teamDict['leagueChampion'] = team.leagueChampion
        teamDict['winningStreak'] = team.winningStreak
        playoffTeamsList.append(teamDict)

    for team in floosball.activeSeason.nonPlayoffTeamsList:
        team: Team
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['color'] = team.color
        teamDict['id'] = team.id
        teamDict['elo'] = team.elo
        teamDict['record'] = '{0}-{1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
        teamDict['eliminated'] = team.eliminated
        teamDict['clinchedPlayoffs'] = team.clinchedPlayoffs
        teamDict['clinchedDivision'] = team.clinchedDivision
        teamDict['clinchedTopSeed'] = team.clinchedTopSeed
        teamDict['leagueChampion'] = team.leagueChampion
        teamDict['winningStreak'] = team.winningStreak
        nonPlayoffTeamsList.append(teamDict)

    divisionLeadersDict = {'divisionLeaders': divisionLeadersList}
    playoffTeamsDict = {'playoffTeams': playoffTeamsList}
    nonPlayoffTeamsDict = {'nonPlayoffTeams': nonPlayoffTeamsList}
    playoffList.append(divisionLeadersDict)
    playoffList.append(playoffTeamsDict)
    playoffList.append(nonPlayoffTeamsDict)
    return playoffList


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
    
@app.get('/championshipHistory')
async def returnChampionshipHistory():
    return floosball.championshipHistory

@app.get('/records')
async def returnRecords(selection):
    gameRecordsList = []
    seasonRecordsList = []
    careerRecordsList = []
    recordsDict:dict = []
    if selection == '1':
        recordsDict = floosball.allTimeRecordsDict['players']['passing']
    elif selection == '2':
        recordsDict = floosball.allTimeRecordsDict['players']['rushing']
    elif selection == '3':
        recordsDict = floosball.allTimeRecordsDict['players']['receiving']
    elif selection == '4':
        recordsDict = floosball.allTimeRecordsDict['players']['kicking']
    elif selection == '5':
        recordsDict = floosball.allTimeRecordsDict['team']


    for k,v in recordsDict.items():
        v:dict
        if k == 'career' or k == 'allTime':
            for record in v.values():
                careerRecordsList.append(record)
        elif k == 'season':
            for record in v.values():
                seasonRecordsList.append(record)
        elif k == 'game':
            for record in v.values():
                gameRecordsList.append(record)

    return {'game': gameRecordsList,'career': careerRecordsList, 'season': seasonRecordsList}


@app.get('/gameStats')
async def returnGameStats(id = None):
    if id is None:
        return 'No ID specified'
    else:
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList['games'])):
                game: FloosGame.Game = weekGameList['games'][x]
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
        eventList = []
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList['games'])):
                game: FloosGame.Game = weekGameList['games'][x]
                if id == game.id:
                    for entry in game.gameFeed:
                        entry: dict
                        for k,v in entry.items():
                            if k == 'event':
                                v['type'] = 'event'
                                eventList.append(v)
                            elif k == 'play':
                                play: FloosGame.Play = v
                                playDict = {}
                                playDict['type'] = 'play'
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
                                eventList.append(playDict)
                    return(eventList)
        else:
            return 'Game Not Found'

@app.get('/highlights')
async def returnHighlights(id = None):
    if id is None:
        eventList = []
        highlights = []
        for x in range(len(floosball.activeSeason.leagueHighlights)):
            if x < 30:
                highlights.append(floosball.activeSeason.leagueHighlights[x])
            else:
                break

        for entry in highlights:
            entry: dict
            for k,v in entry.items():
                if k == 'event':
                    v['type'] = 'event'
                    eventList.append(v)
                elif k == 'play':
                    play: FloosGame.Play = v
                    playDict = {}
                    playDict['type'] = 'play'
                    playDict['playText'] = play.playText
                    playDict['team'] = play.offense.name
                    playDict['homeAbbr'] = play.homeAbbr
                    playDict['awayAbbr'] = play.awayAbbr
                    playDict['yardage'] = play.yardage
                    playDict['result'] = play.playResult.value
                    playDict['homeScore'] = play.homeTeamScore
                    playDict['awayScore'] = play.awayTeamScore
                    playDict['color'] = play.offense.color
                    playDict['scoreChange'] = play.scoreChange
                    playDict['isTd'] = play.isTd
                    playDict['isFg'] = play.isFgGood
                    playDict['isSafety'] = play.isSafety
                    eventList.append(playDict)
        return(eventList)

    else:
        eventList = []
        for y in range(len(floosball.scheduleList)):
            weekGameList = floosball.scheduleList[y]
            for x in range(0,len(weekGameList['games'])):
                game: FloosGame.Game = weekGameList['games'][x]
                if id == game.id:
                    for entry in game.highlights:
                        entry: dict
                        for k,v in entry.items():
                            if k == 'event':
                                v['type'] = 'event'
                                eventList.append(v)
                            elif k == 'play':
                                play: FloosGame.Play = v
                                playDict = {}
                                playDict['type'] = 'play'
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
                                eventList.append(playDict)
                    return(eventList)
        else:
            return 'Game Not Found'

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
            teamDict['city'] = team.city
            teamDict['id'] = team.id
            teamDict['ratingStars'] = team.defenseOverallTier
            teamDict['stat1'] = team.seasonTeamStats['Defense']['sacks']
            teamDict['stat2'] = team.seasonTeamStats['Defense']['ints']
            teamDict['stat3'] = team.seasonTeamStats['Defense']['fumRec']
            teamDict['stat4'] = team.seasonTeamStats['Defense']['passYardsAlwd']
            teamDict['stat5'] = team.seasonTeamStats['Defense']['runYardsAlwd']
            teamDict['stat6'] = team.seasonTeamStats['Defense']['totalYardsAlwd']
            teamDict['stat7'] = team.seasonTeamStats['Defense']['avgYardsAlwd']
            teamDict['stat8'] = team.seasonTeamStats['Defense']['runTdsAlwd']
            teamDict['stat9'] = team.seasonTeamStats['Defense']['passTdsAlwd']
            teamDict['stat10'] = team.seasonTeamStats['Defense']['tdsAlwd']
            teamDict['stat11'] = team.seasonTeamStats['Defense']['avgTdsAlwd']
            teamDict['stat12'] = team.seasonTeamStats['Defense']['ptsAlwd']
            teamDict['stat13'] = team.seasonTeamStats['Defense']['avgPtsAlwd']
            statList.append(teamDict)
    elif pos == 'O':
        for team in floosball.teamList:
            teamDict = {}
            team: Team
            teamDict['name'] = team.name
            teamDict['city'] = team.city
            teamDict['ratingStars'] = team.defenseOverallTier
            teamDict['seasonStats'] = team.seasonTeamStats['Offense']
            statList.append(teamDict)
    else:
        if pos == 'Passing':
            playerList = floosball.activeQbList
        elif pos == 'Rushing':
            playerList = floosball.activeRbList
        elif pos == 'Receiving':
            playerList.extend(floosball.activeWrList)
            playerList.extend(floosball.activeTeList)
            playerList.extend(floosball.activeRbList)
        elif pos == 'Kicking':
            playerList.extend(floosball.activeKList)

        for player in playerList:
            player: Player
            playerDict = {}
            if isinstance(player.team, Team):
                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['pos'] = player.position.name
                playerDict['abbr'] = player.team.abbr
                playerDict['rank'] = player.serviceTime
                playerDict['ratingStars'] = player.playerTier.value
                if pos == 'Passing':
                    playerDict['stat1'] = player.seasonStatsDict['passing']['att']
                    playerDict['stat2'] = player.seasonStatsDict['passing']['comp']
                    playerDict['stat3'] = player.seasonStatsDict['passing']['compPerc']
                    playerDict['stat4'] = player.seasonStatsDict['passing']['yards']
                    playerDict['stat5'] = player.seasonStatsDict['passing']['ypc']
                    playerDict['stat6'] = player.seasonStatsDict['passing']['tds']
                    playerDict['stat7'] = player.seasonStatsDict['passing']['ints']
                elif pos == 'Rushing':
                    playerDict['stat1'] = player.seasonStatsDict['rushing']['carries']
                    playerDict['stat2'] = player.seasonStatsDict['rushing']['yards']
                    playerDict['stat3'] = player.seasonStatsDict['rushing']['ypc']
                    playerDict['stat4'] = player.seasonStatsDict['rushing']['tds']
                    playerDict['stat5'] = player.seasonStatsDict['rushing']['fumblesLost']
                elif pos == 'Receiving':
                    playerDict['stat1'] = player.seasonStatsDict['receiving']['receptions']
                    playerDict['stat2'] = player.seasonStatsDict['receiving']['targets']
                    playerDict['stat3'] = player.seasonStatsDict['receiving']['rcvPerc']
                    playerDict['stat4'] = player.seasonStatsDict['receiving']['yards']
                    playerDict['stat5'] = player.seasonStatsDict['receiving']['yac']
                    playerDict['stat6'] = player.seasonStatsDict['receiving']['ypr']
                    playerDict['stat7'] = player.seasonStatsDict['receiving']['tds']
                elif pos == 'Kicking':
                    playerDict['stat1'] = player.seasonStatsDict['kicking']['fgs']
                    playerDict['stat2'] = player.seasonStatsDict['kicking']['fgAtt']
                    playerDict['stat3'] = player.seasonStatsDict['kicking']['fgPerc']
                    playerDict['stat4'] = player.seasonStatsDict['kicking']['fgAvg']
                statList.append(playerDict)

    list.sort(statList, key=itemgetter('ratingStars'), reverse=True)
    return statList

@app.get('/topPlayers')
async def returnTopPlayers(pos = None):
    playerList = []
    if pos == 'QB':
        qbList = floosball.activeQbList.copy()
        topQbList = []

        if floosball.activeSeason.currentWeek == 1:
            list.sort(qbList, key=lambda player: player.attributes.overallRating, reverse=True)
        else:
            list.sort(qbList, key=lambda player: player.seasonStatsDict['fantasyPoints'], reverse=True)

        for player in qbList:
            player: Player
            if isinstance(player.team, Team):
                topQbList.append(player)
            if len(topQbList) == 5:
                break
            
        for player in topQbList:
            player: Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['rank'] = player.serviceTime
            playerDict['team'] = player.team.name
            playerDict['abbr'] = player.team.abbr
            playerDict['city'] = player.team.city
            playerDict['color'] = player.team.color
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['yards'] = player.seasonStatsDict['passing']['yards']
            playerDict['tds'] = player.seasonStatsDict['passing']['tds']
            playerDict['pts'] = player.seasonStatsDict['fantasyPoints']
            playerList.append(playerDict)
    elif pos == 'RB':
        rbList = floosball.activeRbList.copy()
        topRbList = []

        if floosball.activeSeason.currentWeek == 1:
            list.sort(rbList, key=lambda player: player.attributes.overallRating, reverse=True)
        else:
            list.sort(rbList, key=lambda player: player.seasonStatsDict['fantasyPoints'], reverse=True)

        for player in rbList:
            player: Player
            if isinstance(player.team, Team):
                topRbList.append(player)
            if len(topRbList) == 5:
                break
            
        for player in topRbList:
            player: Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['rank'] = player.serviceTime
            playerDict['team'] = player.team.name
            playerDict['abbr'] = player.team.abbr
            playerDict['city'] = player.team.city
            playerDict['color'] = player.team.color
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['yards'] = player.seasonStatsDict['rushing']['yards']
            playerDict['tds'] = player.seasonStatsDict['rushing']['tds']
            playerDict['pts'] = player.seasonStatsDict['fantasyPoints']
            playerList.append(playerDict)
    elif pos == 'WR':
        wrList = floosball.activeWrList.copy()
        topWrList = []

        if floosball.activeSeason.currentWeek == 1:
            list.sort(wrList, key=lambda player: player.attributes.overallRating, reverse=True)
        else:
            list.sort(wrList, key=lambda player: player.seasonStatsDict['fantasyPoints'], reverse=True)

        for player in wrList:
            player: Player
            if isinstance(player.team, Team):
                topWrList.append(player)
            if len(topWrList) == 5:
                break
            
        for player in topWrList:
            player: Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['rank'] = player.serviceTime
            playerDict['team'] = player.team.name
            playerDict['abbr'] = player.team.abbr
            playerDict['city'] = player.team.city
            playerDict['color'] = player.team.color
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['yards'] = player.seasonStatsDict['receiving']['yards']
            playerDict['tds'] = player.seasonStatsDict['receiving']['tds']
            playerDict['pts'] = player.seasonStatsDict['fantasyPoints']
            playerList.append(playerDict)
    elif pos == 'TE':
        teList = floosball.activeTeList.copy()
        topTeList = []

        if floosball.activeSeason.currentWeek == 1:
            list.sort(teList, key=lambda player: player.attributes.overallRating, reverse=True)
        else:
            list.sort(teList, key=lambda player: player.seasonStatsDict['fantasyPoints'], reverse=True)

        for player in teList:
            player: Player
            if isinstance(player.team, Team):
                topTeList.append(player)
            if len(topTeList) == 5:
                break
            
        for player in topTeList:
            player: Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['rank'] = player.serviceTime
            playerDict['team'] = player.team.name
            playerDict['abbr'] = player.team.abbr
            playerDict['city'] = player.team.city
            playerDict['color'] = player.team.color
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['yards'] = player.seasonStatsDict['receiving']['yards']
            playerDict['tds'] = player.seasonStatsDict['receiving']['tds']
            playerDict['pts'] = player.seasonStatsDict['fantasyPoints']
            playerList.append(playerDict)
    elif pos == 'K':
        kList = floosball.activeKList.copy()
        topKList = []

        if floosball.activeSeason.currentWeek == 1:
            list.sort(kList, key=lambda player: player.attributes.overallRating, reverse=True)
        else:
            list.sort(kList, key=lambda player: player.seasonStatsDict['fantasyPoints'], reverse=True)

        for player in kList:
            player: Player
            if isinstance(player.team, Team):
                topKList.append(player)
            if len(topKList) == 5:
                break
            
        for player in topKList:
            player: Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['rank'] = player.serviceTime
            playerDict['team'] = player.team.name
            playerDict['abbr'] = player.team.abbr
            playerDict['city'] = player.team.city
            playerDict['color'] = player.team.color
            playerDict['ratingStars'] = player.playerTier.value
            playerDict['pts'] = player.seasonStatsDict['fantasyPoints']
            playerList.append(playerDict)
    elif pos == 'D':
        dList = floosball.teamList.copy()
        topDList = []

        if floosball.activeSeason.currentWeek == 1:
            list.sort(dList, key=lambda team: team.defenseRating, reverse=True)
        else:
            list.sort(dList, key=lambda team: team.seasonTeamStats['Defense']['fantasyPoints'], reverse=True)

        for team in dList:
            team: Team
            topDList.append(team)
            if len(topDList) == 5:
                break
            
        for team in topDList:
            team: Team
            playerDict = {}
            playerDict['name'] = team.name
            playerDict['id'] = team.id
            playerDict['abbr'] = team.abbr
            playerDict['city'] = team.city
            playerDict['color'] = team.color
            playerDict['ratingStars'] = team.defenseOverallTier
            playerDict['pts'] = team.seasonTeamStats['Defense']['fantasyPoints']
            playerList.append(playerDict)

    return playerList


@app.get('/fantasySeason')
async def returnFantasySeason(pos = None):
    fantasyList = []
    if pos == 'D':
        for team in floosball.teamList:
            team: Team
            teamDict = {}
            teamDict['name'] = team.name
            teamDict['id'] = team.id
            teamDict['team'] = team.name
            teamDict['abbr'] = team.abbr
            teamDict['city'] = team.city
            teamDict['color'] = team.color
            teamDict['ratingStars'] = team.defenseRating
            teamDict['fantasyPoints'] = team.seasonTeamStats['Defense']['fantasyPoints']
            fantasyList.append(teamDict)
        list.sort(fantasyList, key=lambda team: team['fantasyPoints'], reverse=True)
    else:
        playerList = []
        if pos == 'QB':
            playerList = floosball.activeQbList.copy()
        elif pos == 'RB':
            playerList = floosball.activeRbList.copy()
        elif pos == 'WR':
            playerList = floosball.activeWrList.copy()
        elif pos == 'TE':
            playerList = floosball.activeTeList.copy()
        elif pos == 'K':
            playerList = floosball.activeKList.copy()

        for player in playerList:
            player: Player
            playerDict = {}
            if isinstance(player.team, Team):
                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['team'] = player.team.name
                playerDict['abbr'] = player.team.abbr
                playerDict['city'] = player.team.city
                playerDict['color'] = player.team.color
                playerDict['ratingStars'] = player.playerTier.value
                playerDict['fantasyPoints'] = player.seasonStatsDict['fantasyPoints']
                fantasyList.append(playerDict)

        list.sort(fantasyList, key=lambda player: player['fantasyPoints'], reverse=True)

    return fantasyList

@app.get('/fantasyGame')
async def returnFantasyGame(pos = None):
    fantasyList = []
    if pos == 'D':
        for team in floosball.teamList:
            team: Team
            teamDict = {}
            teamDict['name'] = team.name
            teamDict['id'] = team.id
            teamDict['team'] = team.name
            teamDict['abbr'] = team.abbr
            teamDict['city'] = team.city
            teamDict['color'] = team.color
            teamDict['ratingStars'] = team.defenseRating
            teamDict['fantasyPoints'] = team.gameDefenseStats['fantasyPoints']
            fantasyList.append(teamDict)
        list.sort(fantasyList, key=lambda team: team['fantasyPoints'], reverse=True)
    else:
        playerList = []
        if pos == 'QB':
            playerList = floosball.activeQbList.copy()
        elif pos == 'RB':
            playerList = floosball.activeRbList.copy()
        elif pos == 'WR':
            playerList = floosball.activeWrList.copy()
        elif pos == 'TE':
            playerList = floosball.activeTeList.copy()
        elif pos == 'K':
            playerList = floosball.activeKList.copy()

        for player in playerList:
            player: Player
            playerDict = {}
            if isinstance(player.team, Team):
                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['team'] = player.team.name
                playerDict['abbr'] = player.team.abbr
                playerDict['city'] = player.team.city
                playerDict['color'] = player.team.color
                playerDict['ratingStars'] = player.playerTier.value
                playerDict['fantasyPoints'] = player.gameStatsDict['fantasyPoints']
                fantasyList.append(playerDict)
        list.sort(fantasyList, key=lambda player: player['fantasyPoints'], reverse=True)

    return fantasyList

@app.get('/seasonInfo')
async def returnSeasonInfo():
    return {'season': floosball.activeSeason.currentSeason, 'currentWeek': floosball.activeSeason.currentWeek, 'currentWeekText': floosball.activeSeason.currentWeekText, 'totalWeeks': len(floosball.scheduleList)}

@app.get('/champion')
async def returnChampion():
    if isinstance(floosball.leagueChampion, Team):
        return {'team': '{} {}'.format(floosball.leagueChampion.city, floosball.leagueChampion.name), 'color': floosball.leagueChampion.color, 'id': floosball.leagueChampion.id}
    else: return {}
            

@app.get('/info')
async def returnInfo():
    return floosball.__version__



uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

