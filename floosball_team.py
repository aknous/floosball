from random import randint
import statistics
import copy
import floosball_methods as FloosMethods
import floosball_player as FloosPlayer



teamStatsDict = {'wins': 0, 'losses': 0, 'winPerc': 0, 'Offense': {'tds': 0, 'passYards': 0, 'runYards': 0, 'totalYards': 0}, 'Defense': {'sacks': 0, 'ints': 0, 'fumRec': 0}}

class Team:
    def __init__(self, name):
        self.name = name
        self.id = 0
        self.offenseRating = 0
        self.runDefenseRating = 0
        self.passDefenseRating = 0
        self.defenseRating = 0
        self.overallRating = 0
        self.leagueChampionships = 0
        self.playoffAppearances = 0

        self.seasonTeamStats = copy.deepcopy(teamStatsDict)
        self.allTimeTeamStats = copy.deepcopy(teamStatsDict)
        self.rosterDict : dict[str, FloosPlayer.Player] = {'qb': None, 'rb': None, 'wr': None, 'te': None, 'k': None}

    def setupTeam(self):
      
        if self.overallRating == 0:
            count = 0
            rating = 0

            for player in self.rosterDict.values():
                rating += player.attributes.overallRating 
                count += 1
            self.offenseRating = round(rating/count)
            x = randint(1, 100)
            if x >= 98:
                self.runDefenseRating = randint(95, 100)
                self.passDefenseRating = randint(95, 100)
            elif x >= 90 and x < 98:
                self.runDefenseRating = randint(90, 94)
                self.passDefenseRating = randint(90, 94)
            elif x >= 70 and x < 90:
                self.runDefenseRating = randint(80, 89)
                self.passDefenseRating = randint(80, 89)
            else:
                self.runDefenseRating = randint(70, 85)
                self.passDefenseRating = randint(70, 85)
            self.defenseRating = round(statistics.mean([self.runDefenseRating, self.passDefenseRating]))
            self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))

    def updateRating(self):
        count = 0
        rating = 0
        for player in self.rosterDict.values():
            rating += player.attributes.overallRating 
            count += 1
        self.offenseRating = round(rating/count)
        self.overallRating = round(statistics.mean([self.offenseRating, self.runDefenseRating, self.passDefenseRating]))

    def updateDefense(self):
        self.passDefenseRating += randint(-5, 5)
        if self.passDefenseRating > 100:
            self.passDefenseRating = 100
        elif self.passDefenseRating < 0:
            self.passDefenseRating = 0
        self.runDefenseRating += randint(-5, 5)
        if self.runDefenseRating > 100:
            self.runDefenseRating = 100
        elif self.runDefenseRating < 0:
            self.runDefenseRating = 0

        self.defenseRating = round(statistics.mean([self.runDefenseRating, self.passDefenseRating]))

    def offseasonMoves(self, playerList):
        bestPlayer = None
        hiSkillDiff = 0

        #for player in playerList:
        for x in range(len(playerList)):
            if x < len(playerList):
                if playerList[x].position.value == 1:
                    if playerList[x].attributes.skillRating > self.rosterDict['qb'].attributes.skillRating:
                        skillDiff =  playerList[x].attributes.skillRating - self.rosterDict['qb'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestPlayer = playerList.pop(x)
                elif playerList[x].position.value == 2:
                    if playerList[x].attributes.skillRating > self.rosterDict['rb'].attributes.skillRating:
                        skillDiff =  playerList[x].attributes.skillRating - self.rosterDict['rb'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestPlayer = playerList.pop(x)
                elif playerList[x].position.value == 3:
                    if playerList[x].attributes.skillRating > self.rosterDict['wr'].attributes.skillRating:
                        skillDiff =  playerList[x].attributes.skillRating - self.rosterDict['wr'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestPlayer = playerList.pop(x)
                elif playerList[x].position.value == 4:
                    if playerList[x].attributes.skillRating > self.rosterDict['te'].attributes.skillRating:
                        skillDiff =  playerList[x].attributes.skillRating - self.rosterDict['te'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestPlayer = playerList.pop(x)
                elif playerList[x].position.value == 5:
                    if playerList[x].attributes.skillRating > self.rosterDict['k'].attributes.skillRating:
                        skillDiff =  playerList[x].attributes.skillRating - self.rosterDict['k'].attributes.skillRating
                        if skillDiff > hiSkillDiff:
                            bestPlayer = playerList.pop(x)

        if bestPlayer is not None:
            if bestPlayer.position.value == 1:
                playerList.append(self.rosterDict['qb'])
                self.rosterDict['qb'].team = 'Free Agent'
                self.rosterDict['qb'] = bestPlayer
                self.rosterDict['qb'].team = self
            elif bestPlayer.position.value == 2:
                playerList.append(self.rosterDict['rb'])
                self.rosterDict['rb'].team = 'Free Agent'
                self.rosterDict['rb'] = bestPlayer
                self.rosterDict['rb'].team = self
            elif bestPlayer.position.value == 3:
                playerList.append(self.rosterDict['wr'])
                self.rosterDict['wr'].team = 'Free Agent'
                self.rosterDict['wr'] = bestPlayer
                self.rosterDict['wr'].team = self
            elif bestPlayer.position.value == 4:
                playerList.append(self.rosterDict['te'])
                self.rosterDict['te'].team = 'Free Agent'
                self.rosterDict['te'] = bestPlayer
                self.rosterDict['te'].team = self
            elif bestPlayer.position.value == 5:
                playerList.append(self.rosterDict['k'])
                self.rosterDict['k'].team = 'Free Agent'
                self.rosterDict['k'] = bestPlayer
                self.rosterDict['k'].team = self
