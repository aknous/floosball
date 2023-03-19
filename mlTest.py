import sys
import matplotlib
matplotlib.use('Agg')

import pandas
import csv
from sklearn import tree
from sklearn.tree import DecisionTreeClassifier
import matplotlib.pyplot as plt




df = pandas.read_csv("data.csv")

d = {'Run': 0, 'Pass1': 1, 'Pass2': 2, 'Pass3': 3, 'Pass4': 4, 'Punt': 5, 'FG': 6}
df['Play'] = df['Play'].map(d)

features = ['Down', 'YardsTo1', 'YardsToEz', 'PlaysLeft', 'ScoreDiff', 'Grade']

x = df[features]
y = df['Play']

dtree = DecisionTreeClassifier()
dtree = dtree.fit(x, y)

tree.plot_tree(dtree, feature_names=features)

# #Two  lines to make our compiler able to draw:
plt.savefig('dtData', format='pdf')
sys.stdout.flush()
# print(dtree.predict([[2, 3, 34, 45, 0, 2]]))