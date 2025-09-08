from random_batch import batched_randint
import math
from constants import ELO_DIVISOR, TIER_S_MIN, TIER_S_MAX, TIER_D_MIN, TIER_D_MAX

def scaleValue(value, minTarget, maxTarget, minSource, maxSource):
    return round(minTarget + ((value - minSource) / (maxSource - minSource)) * (maxTarget - minTarget))


def calculateProbability(rating1, rating2):
    return round(1.0 * 1.0 / (1 + 1.0 * math.pow(10, 1.0 * (rating1 - rating2) / ELO_DIVISOR)), 2)

def checkIfClinched(team1Wins, team2Wins, numOfGamesRemaining):
    if team2Wins + numOfGamesRemaining < team1Wins:
        return True
    else:
        return False
    
def checkIfEliminated(team1Wins, team2Wins, numOfGamesRemaining):
    if team1Wins + numOfGamesRemaining < team2Wins:
        return True
    else:
        return False



            


def getStat(min, max, weight):
    x = batched_randint(min,max)
    if weight == 1:
        if x >= 95:
            return batched_randint(TIER_S_MIN, TIER_S_MAX)
        elif x < 95 and x >= 75:
            return batched_randint(85, 94)
        elif x < 75 and x >= 25:
            return batched_randint(75, 84)
        else:
            return batched_randint(TIER_D_MIN, TIER_D_MAX)
    else:
        return x




def getPower(x, y):
    z = 1
    while z < y:
        if (x**z) >= y:
            return z
        else:
            z += 1
    return 0