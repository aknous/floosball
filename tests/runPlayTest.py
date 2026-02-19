import numpy as np
import matplotlib.pyplot as plt
from random import randint
import seaborn as sns
import pandas as pd
import statistics


def scaleValue(value, minTarget, maxTarget, minSource, maxSource):
    return round(minTarget + ((value - minSource) / (maxSource - minSource)) * (maxTarget - minTarget))

def CreateBaseCurve(runnerPower, runnerAgility, runnerSpeed, blocker, defense, yardages):

    offenseContribution1 = .6 * ((runnerPower*1.3) + (blocker*.7)/2) / 100
    offenseContribution2 = .6 * runnerAgility / 100
    offenseContribution3 = .6 * runnerSpeed / 100
    defenseContribution = .4 * defense / 100

    # Base decay rate based on contributions
    baseDecayRate = round(0.1 + .8 * (np.exp(defenseContribution) - offenseContribution1),3)

    # Regular run curve (base)
    baseCurve = np.exp(-baseDecayRate * yardages)
    baseCurve /= np.sum(baseCurve)  # Normalize

    return baseCurve, baseDecayRate




#yardages = np.arange(0, 80)

scenarios = [
    {
        "runnerPower": 95,
        "runnerSpeed": 95,
        "runnerAgility": 95,
        "blocker": 80,
        "defense": 65,
        "touchdowns": 0
    },
    {
        "runnerPower": 95,
        "runnerSpeed": 95,
        "runnerAgility": 95,
        "blocker": 80,
        "defense": 80,
        "touchdowns": 0
    },
    {
        "runnerPower": 95,
        "runnerSpeed": 95,
        "runnerAgility": 95,
        "blocker": 80,
        "defense": 95,
        "touchdowns": 0
    },
    {
        "runnerPower": 80,
        "runnerSpeed": 80,
        "runnerAgility": 80,
        "blocker": 80,
        "defense": 80,
        "touchdowns": 0
    },
    {
        "runnerPower": 65,
        "runnerSpeed": 65,
        "runnerAgility": 65,
        "blocker": 80,
        "defense": 80,
        "touchdowns": 0
    },


]

plt.figure(figsize=(20, 15))

colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'black', 'yellow', 'cyan', 'magenta', 'olive', 'lime', 'teal', 'coral', 'gold', 'navy', 'indigo', 'maroon', 'crimson', 'orchid', 'salmon', 'sienna', 'tan', 'turquoise', 'violet']

totalYardsDict = {}
yardsListDict = {}

for x, scenario in enumerate(scenarios):
    color = colors[x]
    runnerPower = scenario['runnerPower']
    runnerAgility = scenario['runnerAgility']
    runnerSpeed = scenario['runnerSpeed']
    blocker = scenario['blocker']
    defense = scenario['defense']
    #runner = randint(60, 100)
    #blocker = randint(60, 100)
    #defense = randint(60, 100)
    #baseCurve, baseDecayRate = CreateBaseCurve(runner, blocker, defense)
    #plt.plot(yardages, baseCurve, color=color, linestyle="-", linewidth=2, label=f'baseDecayRate: {baseDecayRate} - Runner: {runner} - Blocker: {blocker} - Defense: {defense}')

    #chosenYards = np.random.choice(yardages, p=baseCurve, size=1000)
    #data[f'{runner}-{blocker}-{defense}'] = chosenYards
    totalYards = 0
    yardsList = []
    for a in range(0, 1):
        yardsToEndzone = 80
        gameYards = 0

        stage1Offense = (((((runnerPower*1.4) + (runnerAgility*.6))/2)*1.3) + (blocker*.7))/2
        offenseContribution1 = .9 * stage1Offense / 100
        offenseContribution2 = 1.2 * ((runnerSpeed*1.4) + (runnerAgility*.6)/2) / 100
        defenseContribution = .4 * defense / 100

        stage1DecayRate = round(0.1 + .4 * (np.exp(defenseContribution) - offenseContribution1),3)
        stage2DecayRate = round(0.1 + .1 * (np.exp(defenseContribution) - offenseContribution2),3)
        stage1PeakYards = min(4, max(0, int((stage1Offense - defense) / 3)))

        stage2Yardages = np.arange(0,60)

        stage2Curve = np.exp(-stage2DecayRate * stage2Yardages)
        stage2Curve /= np.sum(stage2Curve)  # Normalize
        #plt.plot(stage2Yardages, stage2Curve, color=color, linestyle="-", linewidth=2, label=f'baseDecayRate: {stage2DecayRate} - Runner: {runnerAgility} - Blocker: {blocker} - Defense: {defense}')
        
        for i in range(0,1):
            yards = 0

            if yardsToEndzone >= 10:
                stage1MaxYards = 10
            else:
                stage1MaxYards = yardsToEndzone+5

            stage1Yardages = np.arange(0,stage1MaxYards+1)

            mean_stage1 = (((runnerPower*.6 + runnerAgility*.4) * 0.8 + blocker * 0.2) - defense) / 5
            mean_stage1 = min(stage1MaxYards+1, max(0, mean_stage1))  # Clamp to range [0, 10]
            relative_strength = ((((runnerPower*.6 + runnerAgility*.4) * 0.8 + blocker)*2) - defense) / 100
            absolute_skill = (((runnerPower*.6 + runnerAgility*.4) * 0.8 + blocker * 0.2) + defense) / 200
            std_dev_stage1 = max(1, (stage1MaxYards+1 - 0) / 4 * (1 + relative_strength) * absolute_skill)

            # Create a bell curve (Gaussian distribution)
            stage1Curve = np.exp(-((stage1Yardages - mean_stage1) ** 2) / (2 * std_dev_stage1 ** 2))
            stage1Curve /= np.sum(stage1Curve)  # Normalize to ensure it sums to 1

            plt.plot(stage1Yardages, stage1Curve, color=color, linestyle="-", linewidth=2, label=f'baseDecayRate: {stage1DecayRate} - Runner: {runnerAgility} - Blocker: {blocker} - Defense: {defense}')
            #stage1Curve = np.exp(-stage1DecayRate * stage1Yardages)
            #if stage1PeakYards > 0:
            #    stage1Curve[stage1PeakYards] *= 2
            #stage1Curve /= np.sum(stage1Curve)  # Normalize

            
            stage1YardsGained = np.random.choice(stage1Yardages, p=stage1Curve)
            
            yards += stage1YardsGained

            if yards >= yardsToEndzone or stage1YardsGained < stage1MaxYards * .5:
                gameYards += yards
                yardsToEndzone -= yards
                if yardsToEndzone <= 0:
                    scenario['touchdowns'] += 1
                    yardsToEndzone = 80
                continue

            yardsToEndzone -= yards

            if yardsToEndzone >= 10:
                stage2MaxYards = 10
            else:
                stage2MaxYards = yardsToEndzone+5

            stage2Yardages = np.arange(0,stage2MaxYards+1)

            stage2Curve = np.exp(-stage2DecayRate * stage2Yardages)
            stage2Curve /= np.sum(stage2Curve)  # Normalize
            #plt.plot(stage2Yardages, stage2Curve, color=color, linestyle="-", linewidth=2, label=f'baseDecayRate: {stage2DecayRate} - Runner: {runnerAgility} - Blocker: {blocker} - Defense: {defense}')
        

            stage2YardsGained = np.random.choice(stage2Yardages, p=stage2Curve)
            yards += stage2YardsGained

            gameYards += yards
            yardsToEndzone -= yards
            if yardsToEndzone <= 0:
                scenario['touchdowns'] += 1
                yardsToEndzone = 80



        yardsList.append(gameYards)
        totalYards += gameYards

    
    totalYardsDict[f'scenerio{x}'] = totalYards
    yardsListDict[f'scenerio{x}'] = yardsList

df1 = pd.DataFrame(totalYardsDict, index=[0])
df2 = pd.DataFrame(yardsListDict)
#sns.barplot(data=df1)
#sns.violinplot(data=df2)





plt.xlabel('Yardage')
plt.ylabel('Probability')
plt.legend(loc='upper right', fontsize=8)

plt.grid()
plt.show()