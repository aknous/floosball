import sys
import matplotlib
matplotlib.use('Agg')
import floosball
import floosball_game
import floosball_methods as FloosMethods

import pandas
import csv
from sklearn import tree
from sklearn.tree import DecisionTreeClassifier
import matplotlib.pyplot as plt

config = FloosMethods.getConfig()
floosball.getPlayers(config)
floosball.getTeams(config)
floosball.playerDraft()
floosball.initTeams()

game = floosball_game.Game(floosball.teamList[0], floosball.teamList[1])
game.playGame()

features = ['Down', 'YardsTo1', 'YardsToEz', 'PlaysLeft', 'ScoreDiff', 'Grade']

with open('data.csv', mode='w') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=features)

    for item in game.gameFeed:
        for type, event in item.items():
            if event == 'play':
                event: floosball_game.Play
                writer.writeheader()
                writer.writerow({'Down': event.down, 'YardsTo1': event.yardsTo1st, 'YardsToEz': event.yardsToEndzone, 'PlaysLeft': event.playsLeft, 'ScoreDiff': event.offenseScore - event.defenseScore, 'Grade': event.grade})


# df = pandas.read_csv("data.csv")

# d = {'Run': 0, 'Pass1': 1, 'Pass2': 2, 'Pass3': 3, 'Pass4': 4, 'Punt': 5, 'FG': 6}
# df['Play'] = df['Play'].map(d)



# x = df[features]
# y = df['Play']

# dtree = DecisionTreeClassifier()
# dtree = dtree.fit(x, y)

# print(dtree.predict([[2, 5, 65, 45, 7, 2]]))