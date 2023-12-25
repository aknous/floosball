import json
import os
from random import randint, seed, shuffle
import copy
import asyncio
from secrets import choice
from unicodedata import name
import numpy as np
from scipy import stats
import statistics
import floosball_game as FloosGame
import floosball_team as FloosTeam
import floosball_player as FloosPlayer
import floosball_methods as FloosMethods
import datetime
import math
 

__version__ = '0.9.0_alpha'

config = None
totalSeasons = 0
seasonsPlayed = 0
cap = 0
activePlayerList = []
unusedNamesList = []
freeAgentList = []
rookieDraftList = []
retiredPlayersList = []
newlyRetiredPlayersList = []
hallOfFame = []

activeQbList = []
activeRbList = []
activeWrList = []
activeTeList = []
activeKList = []
activeDbList = []
activeLbList = []
activeDeList = []
activeDlList = []

freeAgencyOrder = []
freeAgencyHistoryDict = {}
teamList = []
divisionList = []   
scheduleList = []
seasonList = []
activeSeason = None
leagueChampion: FloosTeam.Team = None
championshipHistory = []
scheduleScheme = [
    ('1112','1314','1516','2122','2324','2526','3132','3334','3536','4142','4344','4546'),
    ('1311','1215','1614','2321','2225','2624','3331','3235','3634','4341','4245','4644'),
    ('1116','1213','1415','2126','2223','2425','3136','3233','3435','4146','4243','4445'),
    ('1114','1612','1513','2124','2622','2523','3134','3632','3533','4144','4642','4543'),
    ('1511','1412','1316','2521','2422','2326','3531','3432','3336','4541','4442','4346'),

    ('1121','1222','1323','1424','1525','1626','3141','3242','3343','3444','3545','3646'),
    ('2112','2213','2314','2415','2516','2611','4132','4233','4334','4435','4536','4631'),
    ('1123','1224','1325','1426','1521','1622','3143','3244','3345','3446','3541','3642'),
    ('2114','2215','2316','2411','2512','2613','4134','4235','4336','4431','4532','4633'),
    ('1125','1226','1321','1422','1523','1624','3145','3246','3341','3442','3543','3644'),
    ('2116','2211','2312','2413','2514','2615','4136','4231','4332','4433','4534','4635'),

    ('1131','1232','1333','1434','1535','1636','2141','2242','2343','2444','2545','2646'),
    ('3112','3213','3314','3415','3516','3611','4122','4223','4324','4425','4526','4621'),
    ('1133','1234','1335','1436','1531','1632','2143','2244','2345','2446','2541','2642'),
    ('3114','3215','3316','3411','3512','3613','4124','4225','4326','4421','4522','4623'),
    ('1135','1236','1331','1432','1533','1634','2145','2246','2341','2442','2543','2644'),
    ('3116','3211','3312','3413','3514','3615','4126','4221','4322','4423','4524','4625'),

    ('1141','1242','1343','1444','1545','1646','2131','2232','2333','2434','2535','2636'),
    ('4112','4213','4314','4415','4516','4611','3122','3223','3324','3425','3526','3621'),
    ('1143','1244','1345','1446','1541','1642','2133','2234','2335','2436','2531','2632'),
    ('4114','4215','4316','4411','4512','4613','3124','3225','3326','3421','3522','3623'),
    ('1145','1246','1341','1442','1543','1644','2135','2236','2331','2432','2533','2634'),
    ('4116','4211','4312','4413','4514','4615','3126','3221','3322','3423','3524','3625'),

    ('1211','1413','1615','2122','2423','2625','3231','3433','3635','4241','4443','4645'),
    ('1113','1512','1416','2123','2522','2426','3133','3532','3436','4143','4542','4446'),
    ('1611','1312','1514','2621','2322','2524','3631','3332','3534','4641','4342','4544'),
    ('1411','1216','1315','2421','2226','2325','3431','3236','3335','4441','4246','4345'),
    ('1115','1214','1613','2125','2224','2623','3135','3234','3633','4145','4244','4643')]


allTimeRecordsDict = {
    'players': {
        'passing': {
            'game': {
                'yards': {
                    'record': 'Pass Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tds': {
                    'record': 'Pass TDs',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'comps': {
                    'record': 'Completions',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'ints': {
                    'record': 'Most Interceptions',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'career': {
                'yards': {
                    'record': 'Pass Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tds': {
                    'record': 'Pass TDs',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'comps': {
                    'record': 'Completions',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'ints': {
                    'record': 'Most Interceptions',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'season': {
                'yards': {
                    'record': 'Pass Yards',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'tds': {
                    'record': 'Pass TDs',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'comps': {
                    'record': 'Completions',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'ints': {
                    'record': 'Most Interceptions',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                }
            }
        },
        'rushing': {
            'game': {
                'yards': {
                    'record': 'Rush Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tds': {
                    'record': 'Rush TDs',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'fumbles': {
                    'record': 'Most Fumbles',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'career': {
                'yards': {
                    'record': 'Rush Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tds': {
                    'record': 'Rush TDs',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'fumbles': {
                    'record': 'Most Fumbles',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'season': {
                'yards': {
                    'record': 'Rush Yards',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'tds': {
                    'record': 'Rush TDs',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'fumbles': {
                    'record': 'Most Fumbles',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                }
            }
        },
        'receiving': {
            'game': {
                'yards': {
                    'record': 'Receiving Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tds': {
                    'record': 'Receiving TDs',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'receptions': {
                    'record': 'Receptions',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'career': {
                'yards': {
                    'record': 'Receiving Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tds': {
                    'record': 'Receiving TDs',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'receptions': {
                    'record': 'Receptions',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'season': {
                'yards': {
                    'record': 'Receiving Yards',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'tds': {
                    'record': 'Receiving TDs',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'receptions': {
                    'record': 'Receptions',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                }
            }
        },
        'kicking': {
            'game': {
                'fgs': {
                    'record': 'Field Goals',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'fgYards': {
                    'record': 'Total FG Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'career': {
                'fgs': {
                    'record': 'Field Goals',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'fgYards': {
                    'record': 'Total FG Yards',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'season': {
                'fgs': {
                    'record': 'Field Goals',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'fgYards': {
                    'record': 'Total FG Yards',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                }
            }
        },
        'defense': {
            'game': {
                'ints': {
                    'record': 'Interceptions',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'sacks': {
                    'record': 'Sacks',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tackles': {
                    'record': 'Tackles',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'fumRec': {
                    'record': 'Fumble Recoveries',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'career': {
                'ints': {
                    'record': 'Interceptions',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'sacks': {
                    'record': 'Sacks',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'tackles': {
                    'record': 'Tackles',
                    'name': None,
                    'id': 0,
                    'value': 0
                },
                'fumRec': {
                    'record': 'Fumble Recoveries',
                    'name': None,
                    'id': 0,
                    'value': 0
                }
            },
            'season': {
                'ints': {
                    'record': 'Interceptions',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'sacks': {
                    'record': 'Sacks',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'tackles': {
                    'record': 'Tackles',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                },
                'fumRec': {
                    'record': 'Fumble Recoveries',
                    'name': None,
                    'id': 0,
                    'value': 0,
                    'season': 0
                }
            }
        }
    },
    'team': {
        'game': {
            'yards': {
                'record': 'Yards',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'tds': {
                'record': 'TDs',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'pts': {
                'record': 'Total Points',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            }
        },
        'allTime': {
            'wins': {
                'record': 'Most Wins',
                'name': None,
                'id': 0,
                'value': 0,
            },
            'losses': {
                'record': 'Most Losses',
                'name': None,
                'id': 0,
                'value': 0,
            },
            'titles': {
                'record': 'FloosBowl Titles',
                'name': None,
                'id': 0,
                'value': 0,
            },
            'divTitles': {
                'record': 'Division Titles',
                'name': None,
                'id': 0,
                'value': 0,
            },
            'regSeasonTitles': {
                'record': 'Regular Season Titles',
                'name': None,
                'id': 0,
                'value': 0,
            }
        },
        'season': {
            'yards': {
                'record': 'Yards',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'tds': {
                'record': 'TDs',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'pts': {
                'record': 'Total Points',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'ints': {
                'record': 'Most Interceptions',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'fumRec': {
                'record': 'Most Fumble Recoveries',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            },
            'elo': {
                'record': 'Highest Rating',
                'name': None,
                'id': 0,
                'value': 0,
                'season': 0
            }
        }
    }
}


colorList = [   
                '#F1C40F',
                '#651FFF',
                '#C0392B',
                '#58D68D',
                '#F39C12',
                '#7FB3D5',
                '#FF6D00',
                '#2980B9',
                '#FF1744',
                '#FF4081',
                '#D500F9',
                '#9C27B0',
                '#304FFE',
                '#64B5F6',
                '#2196F3',
                '#00B0FF',
                '#26C6DA',
                '#00E5FF',
                '#26A69A',
                '#1DE9B6',
                '#00C853',
                '#F57F17',
                '#FFC400',
                '#FF3D00',
                '#1abc9c',
                '#e74c3c',
                '#2ecc71',
                '#3498db',
                '#2980b9',
                '#27ae60',
                '#d35400',
                '#c0392b',
                '#e67e22',
                '#8e44ad',
                '#9b59b6',
                '#f39c12',
                '#44bd32',
                '#e84118',
                '#00a8ff',
                '#487eb0',
                '#EA2027',
                '#009432',
                '#EE5A24',
                '#0652DD',
                '#B53471',
                '#ED4C67',
                '#B33771',
                '#FC427B',
                '#20bf6b',
                '#eb3b5a',
                '#3867d6',
                '#2d98da',
                '#fc5c65',
                '#fa8231',
                '#f7b731',
                '#0fb9b1',
                '#a55eea',
                '#b71540',
                '#2ed573',
                '#3742fa',
                '#ff4757',
                '#ff6348',
                '#1e90ff',
                '#05c46b',
                '#ff3f34',
                '#3c40c6',
                '#00d8d6',
                '#ffa801',
                '#0fbcf9',
                '#f53b57'
            ]

dateNow = datetime.datetime.now()
dateNowUtc = datetime.datetime.utcnow()
if dateNow.day == dateNowUtc.day:
    utcOffset = dateNowUtc.hour - dateNow.hour
elif dateNowUtc.day > dateNow.day:
    utcOffset = (dateNowUtc.hour + 24) - dateNow.hour
elif dateNow.day > dateNowUtc.day:
    utcOffset = dateNowUtc.hour - (dateNow.hour + 24)


def checkPlayerGameRecords():
    for player in activePlayerList:
        player: FloosPlayer.Player
        if player.gameStatsDict['passing']['att'] > 0:
            if player.gameStatsDict['passing']['comp'] > allTimeRecordsDict['players']['passing']['game']['comps']['value']:
                allTimeRecordsDict['players']['passing']['game']['comps']['value'] = player.gameStatsDict['passing']['comp']
                allTimeRecordsDict['players']['passing']['game']['comps']['name'] = player.name
                allTimeRecordsDict['players']['passing']['game']['comps']['id'] = player.id
            if player.gameStatsDict['passing']['yards'] > allTimeRecordsDict['players']['passing']['game']['yards']['value']:
                allTimeRecordsDict['players']['passing']['game']['yards']['value'] = player.gameStatsDict['passing']['yards']
                allTimeRecordsDict['players']['passing']['game']['yards']['name'] = player.name
                allTimeRecordsDict['players']['passing']['game']['yards']['id'] = player.id
            if player.gameStatsDict['passing']['tds'] > allTimeRecordsDict['players']['passing']['game']['tds']['value']:
                allTimeRecordsDict['players']['passing']['game']['tds']['value'] = player.gameStatsDict['passing']['tds']
                allTimeRecordsDict['players']['passing']['game']['tds']['name'] = player.name
                allTimeRecordsDict['players']['passing']['game']['tds']['id'] = player.id
            if player.gameStatsDict['passing']['ints'] > allTimeRecordsDict['players']['passing']['game']['ints']['value']:
                allTimeRecordsDict['players']['passing']['game']['ints']['value'] = player.gameStatsDict['passing']['ints']
                allTimeRecordsDict['players']['passing']['game']['ints']['name'] = player.name
                allTimeRecordsDict['players']['passing']['game']['ints']['id'] = player.id

        if player.gameStatsDict['rushing']['carries'] > 0:
            if player.gameStatsDict['rushing']['yards'] > allTimeRecordsDict['players']['rushing']['game']['yards']['value']:
                allTimeRecordsDict['players']['rushing']['game']['yards']['value'] = player.gameStatsDict['rushing']['yards']
                allTimeRecordsDict['players']['rushing']['game']['yards']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['game']['yards']['id'] = player.id
            if player.gameStatsDict['rushing']['tds'] > allTimeRecordsDict['players']['rushing']['game']['tds']['value']:
                allTimeRecordsDict['players']['rushing']['game']['tds']['value'] = player.gameStatsDict['rushing']['tds']
                allTimeRecordsDict['players']['rushing']['game']['tds']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['game']['tds']['id'] = player.id
            if player.gameStatsDict['rushing']['fumblesLost'] > allTimeRecordsDict['players']['rushing']['game']['fumbles']['value']:
                allTimeRecordsDict['players']['rushing']['game']['fumbles']['value'] = player.gameStatsDict['rushing']['fumblesLost']
                allTimeRecordsDict['players']['rushing']['game']['fumbles']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['game']['fumbles']['id'] = player.id
        
        if player.gameStatsDict['receiving']['receptions'] > 0:
            if player.gameStatsDict['receiving']['yards'] > allTimeRecordsDict['players']['receiving']['game']['yards']['value']:
                allTimeRecordsDict['players']['receiving']['game']['yards']['value'] = player.gameStatsDict['receiving']['yards']
                allTimeRecordsDict['players']['receiving']['game']['yards']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['game']['yards']['id'] = player.id
            if player.gameStatsDict['receiving']['tds'] > allTimeRecordsDict['players']['receiving']['game']['tds']['value']:
                allTimeRecordsDict['players']['receiving']['game']['tds']['value'] = player.gameStatsDict['receiving']['tds']
                allTimeRecordsDict['players']['receiving']['game']['tds']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['game']['tds']['id'] = player.id
            if player.gameStatsDict['receiving']['receptions'] > allTimeRecordsDict['players']['receiving']['game']['receptions']['value']:
                allTimeRecordsDict['players']['receiving']['game']['receptions']['value'] = player.gameStatsDict['receiving']['receptions']
                allTimeRecordsDict['players']['receiving']['game']['receptions']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['game']['receptions']['id'] = player.id
        
        if player.gameStatsDict['kicking']['fgs'] > 0:
            if player.gameStatsDict['kicking']['fgs'] > allTimeRecordsDict['players']['kicking']['game']['fgs']['value']:
                allTimeRecordsDict['players']['kicking']['game']['fgs']['value'] = player.gameStatsDict['kicking']['fgs']
                allTimeRecordsDict['players']['kicking']['game']['fgs']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['game']['fgs']['id'] = player.id
        
        if player.gameStatsDict['kicking']['fgYards'] > 0:
            if player.gameStatsDict['kicking']['fgYards'] > allTimeRecordsDict['players']['kicking']['game']['fgYards']['value']:
                allTimeRecordsDict['players']['kicking']['game']['fgYards']['value'] = player.gameStatsDict['kicking']['fgYards']
                allTimeRecordsDict['players']['kicking']['game']['fgYards']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['game']['fgYards']['id'] = player.id
        
        if player.gameStatsDict['defense']['ints'] > 0:
            if player.gameStatsDict['defense']['ints'] > allTimeRecordsDict['players']['defense']['game']['ints']['value']:
                allTimeRecordsDict['players']['defense']['game']['ints']['value'] = player.gameStatsDict['defense']['ints']
                allTimeRecordsDict['players']['defense']['game']['ints']['name'] = player.name
                allTimeRecordsDict['players']['defense']['game']['ints']['id'] = player.id
        
        if player.gameStatsDict['defense']['sacks'] > 0:
            if player.gameStatsDict['defense']['sacks'] > allTimeRecordsDict['players']['defense']['game']['sacks']['value']:
                allTimeRecordsDict['players']['defense']['game']['sacks']['value'] = player.gameStatsDict['defense']['sacks']
                allTimeRecordsDict['players']['defense']['game']['sacks']['name'] = player.name
                allTimeRecordsDict['players']['defense']['game']['sacks']['id'] = player.id
        
        if player.gameStatsDict['defense']['tackles'] > 0:
            if player.gameStatsDict['defense']['tackles'] > allTimeRecordsDict['players']['defense']['game']['tackles']['value']:
                allTimeRecordsDict['players']['defense']['game']['tackles']['value'] = player.gameStatsDict['defense']['tackles']
                allTimeRecordsDict['players']['defense']['game']['tackles']['name'] = player.name
                allTimeRecordsDict['players']['defense']['game']['tackles']['id'] = player.id
        
        if player.gameStatsDict['defense']['fumRec'] > 0:
            if player.gameStatsDict['defense']['fumRec'] > allTimeRecordsDict['players']['defense']['game']['fumRec']['value']:
                allTimeRecordsDict['players']['defense']['game']['fumRec']['value'] = player.gameStatsDict['defense']['fumRec']
                allTimeRecordsDict['players']['defense']['game']['fumRec']['name'] = player.name
                allTimeRecordsDict['players']['defense']['game']['fumRec']['id'] = player.id

def checkTeamGameRecords(game:FloosGame.Game):
    if game.homeScore > allTimeRecordsDict['team']['game']['pts']['value']:
        allTimeRecordsDict['team']['game']['pts']['value'] = game.homeScore
        allTimeRecordsDict['team']['game']['pts']['name'] = '{} {}'.format(game.homeTeam.city, game.homeTeam.name)
        allTimeRecordsDict['team']['game']['pts']['id'] = game.homeTeam.id
    if (game.homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + game.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds']) > allTimeRecordsDict['team']['game']['tds']['value']:
        allTimeRecordsDict['team']['game']['tds']['value'] = (game.homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + game.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
        allTimeRecordsDict['team']['game']['tds']['name'] = '{} {}'.format(game.homeTeam.city, game.homeTeam.name)
        allTimeRecordsDict['team']['game']['tds']['id'] = game.homeTeam.id
    if (game.homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + game.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards']) > allTimeRecordsDict['team']['game']['yards']['value']:
        allTimeRecordsDict['team']['game']['yards']['value'] = (game.homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + game.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
        allTimeRecordsDict['team']['game']['yards']['name'] = '{} {}'.format(game.homeTeam.city, game.homeTeam.name)
        allTimeRecordsDict['team']['game']['yards']['id'] = game.homeTeam.id
        
    if game.awayScore > allTimeRecordsDict['team']['game']['pts']['value']:
        allTimeRecordsDict['team']['game']['pts']['value'] = game.awayScore
        allTimeRecordsDict['team']['game']['pts']['name'] = '{} {}'.format(game.awayTeam.city, game.awayTeam.name)
        allTimeRecordsDict['team']['game']['pts']['id'] = game.awayTeam.id
    if (game.awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + game.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds']) > allTimeRecordsDict['team']['game']['tds']['value']:
        allTimeRecordsDict['team']['game']['tds']['value'] = (game.awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + game.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
        allTimeRecordsDict['team']['game']['tds']['name'] = '{} {}'.format(game.awayTeam.city, game.awayTeam.name)
        allTimeRecordsDict['team']['game']['tds']['id'] = game.awayTeam.id
    if (game.awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + game.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards']) > allTimeRecordsDict['team']['game']['yards']['value']:
        allTimeRecordsDict['team']['game']['yards']['value'] = (game.awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + game.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
        allTimeRecordsDict['team']['game']['yards']['name'] = '{} {}'.format(game.awayTeam.city, game.awayTeam.name)
        allTimeRecordsDict['team']['game']['yards']['id'] = game.awayTeam.id



def checkCareerRecords():
    for player in activePlayerList:
        player: FloosPlayer.Player
        if player.careerStatsDict['passing']['att'] > 0:
            if player.careerStatsDict['passing']['comp'] > allTimeRecordsDict['players']['passing']['career']['comps']['value']:
                allTimeRecordsDict['players']['passing']['career']['comps']['value'] = player.careerStatsDict['passing']['comp']
                allTimeRecordsDict['players']['passing']['career']['comps']['name'] = player.name
                allTimeRecordsDict['players']['passing']['career']['comps']['id'] = player.id
            if player.careerStatsDict['passing']['yards'] > allTimeRecordsDict['players']['passing']['career']['yards']['value']:
                allTimeRecordsDict['players']['passing']['career']['yards']['value'] = player.careerStatsDict['passing']['yards']
                allTimeRecordsDict['players']['passing']['career']['yards']['name'] = player.name
                allTimeRecordsDict['players']['passing']['career']['yards']['id'] = player.id
            if player.careerStatsDict['passing']['tds'] > allTimeRecordsDict['players']['passing']['career']['tds']['value']:
                allTimeRecordsDict['players']['passing']['career']['tds']['value'] = player.careerStatsDict['passing']['tds']
                allTimeRecordsDict['players']['passing']['career']['tds']['name'] = player.name
                allTimeRecordsDict['players']['passing']['career']['tds']['id'] = player.id
            if player.careerStatsDict['passing']['ints'] > allTimeRecordsDict['players']['passing']['career']['ints']['value']:
                allTimeRecordsDict['players']['passing']['career']['ints']['value'] = player.careerStatsDict['passing']['ints']
                allTimeRecordsDict['players']['passing']['career']['ints']['name'] = player.name
                allTimeRecordsDict['players']['passing']['career']['ints']['id'] = player.id

        if player.careerStatsDict['rushing']['carries'] > 0:
            if player.careerStatsDict['rushing']['yards'] > allTimeRecordsDict['players']['rushing']['career']['yards']['value']:
                allTimeRecordsDict['players']['rushing']['career']['yards']['value'] = player.careerStatsDict['rushing']['yards']
                allTimeRecordsDict['players']['rushing']['career']['yards']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['career']['yards']['id'] = player.id
            if player.careerStatsDict['rushing']['tds'] > allTimeRecordsDict['players']['rushing']['career']['tds']['value']:
                allTimeRecordsDict['players']['rushing']['career']['tds']['value'] = player.careerStatsDict['rushing']['tds']
                allTimeRecordsDict['players']['rushing']['career']['tds']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['career']['tds']['id'] = player.id
            if player.careerStatsDict['rushing']['fumblesLost'] > allTimeRecordsDict['players']['rushing']['career']['fumbles']['value']:
                allTimeRecordsDict['players']['rushing']['career']['fumbles']['value'] = player.careerStatsDict['rushing']['fumblesLost']
                allTimeRecordsDict['players']['rushing']['career']['fumbles']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['career']['fumbles']['id'] = player.id
        
        if player.careerStatsDict['receiving']['receptions'] > 0:
            if player.careerStatsDict['receiving']['yards'] > allTimeRecordsDict['players']['receiving']['career']['yards']['value']:
                allTimeRecordsDict['players']['receiving']['career']['yards']['value'] = player.careerStatsDict['receiving']['yards']
                allTimeRecordsDict['players']['receiving']['career']['yards']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['career']['yards']['id'] = player.id
            if player.careerStatsDict['receiving']['tds'] > allTimeRecordsDict['players']['receiving']['career']['tds']['value']:
                allTimeRecordsDict['players']['receiving']['career']['tds']['value'] = player.careerStatsDict['receiving']['tds']
                allTimeRecordsDict['players']['receiving']['career']['tds']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['career']['tds']['id'] = player.id
            if player.careerStatsDict['receiving']['receptions'] > allTimeRecordsDict['players']['receiving']['career']['receptions']['value']:
                allTimeRecordsDict['players']['receiving']['career']['receptions']['value'] = player.careerStatsDict['receiving']['receptions']
                allTimeRecordsDict['players']['receiving']['career']['receptions']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['career']['receptions']['id'] = player.id
        
        if player.careerStatsDict['kicking']['fgs'] > 0:
            if player.careerStatsDict['kicking']['fgs'] > allTimeRecordsDict['players']['kicking']['career']['fgs']['value']:
                allTimeRecordsDict['players']['kicking']['career']['fgs']['value'] = player.careerStatsDict['kicking']['fgs']
                allTimeRecordsDict['players']['kicking']['career']['fgs']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['career']['fgs']['id'] = player.id
        
        if player.careerStatsDict['kicking']['fgYards'] > 0:
            if player.careerStatsDict['kicking']['fgYards'] > allTimeRecordsDict['players']['kicking']['career']['fgYards']['value']:
                allTimeRecordsDict['players']['kicking']['career']['fgYards']['value'] = player.careerStatsDict['kicking']['fgYards']
                allTimeRecordsDict['players']['kicking']['career']['fgYards']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['career']['fgYards']['id'] = player.id
        
        if player.careerStatsDict['defense']['ints'] > 0:
            if player.careerStatsDict['defense']['ints'] > allTimeRecordsDict['players']['defense']['career']['ints']['value']:
                allTimeRecordsDict['players']['defense']['career']['ints']['value'] = player.careerStatsDict['defense']['ints']
                allTimeRecordsDict['players']['defense']['career']['ints']['name'] = player.name
                allTimeRecordsDict['players']['defense']['career']['ints']['id'] = player.id
        
        if player.careerStatsDict['defense']['sacks'] > 0:
            if player.careerStatsDict['defense']['sacks'] > allTimeRecordsDict['players']['defense']['career']['sacks']['value']:
                allTimeRecordsDict['players']['defense']['career']['sacks']['value'] = player.careerStatsDict['defense']['sacks']
                allTimeRecordsDict['players']['defense']['career']['sacks']['name'] = player.name
                allTimeRecordsDict['players']['defense']['career']['sacks']['id'] = player.id
        
        if player.careerStatsDict['defense']['tackles'] > 0:
            if player.careerStatsDict['defense']['tackles'] > allTimeRecordsDict['players']['defense']['career']['tackles']['value']:
                allTimeRecordsDict['players']['defense']['career']['tackles']['value'] = player.careerStatsDict['defense']['tackles']
                allTimeRecordsDict['players']['defense']['career']['tackles']['name'] = player.name
                allTimeRecordsDict['players']['defense']['career']['tackles']['id'] = player.id
        
        if player.careerStatsDict['defense']['fumRec'] > 0:
            if player.careerStatsDict['defense']['fumRec'] > allTimeRecordsDict['players']['defense']['career']['fumRec']['value']:
                allTimeRecordsDict['players']['defense']['career']['fumRec']['value'] = player.careerStatsDict['defense']['fumRec']
                allTimeRecordsDict['players']['defense']['career']['fumRec']['name'] = player.name
                allTimeRecordsDict['players']['defense']['career']['fumRec']['id'] = player.id

    for team in teamList:
            team: FloosTeam.Team
            if team.allTimeTeamStats['wins'] > allTimeRecordsDict['team']['allTime']['wins']['value']:
                allTimeRecordsDict['team']['allTime']['wins']['value'] = team.allTimeTeamStats['wins']
                allTimeRecordsDict['team']['allTime']['wins']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['wins']['id'] = team.id

            if team.allTimeTeamStats['losses'] > allTimeRecordsDict['team']['allTime']['losses']['value']:
                allTimeRecordsDict['team']['allTime']['losses']['value'] = team.allTimeTeamStats['losses']
                allTimeRecordsDict['team']['allTime']['losses']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['losses']['id'] = team.id

            if len(team.leagueChampionships) > allTimeRecordsDict['team']['allTime']['titles']['value']:
                allTimeRecordsDict['team']['allTime']['titles']['value'] = len(team.leagueChampionships)
                allTimeRecordsDict['team']['allTime']['titles']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['titles']['id'] = team.id

            if len(team.divisionChampionships) > allTimeRecordsDict['team']['allTime']['divTitles']['value']:
                allTimeRecordsDict['team']['allTime']['divTitles']['value'] = len(team.divisionChampionships)
                allTimeRecordsDict['team']['allTime']['divTitles']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['divTitles']['id'] = team.id

            if len(team.regularSeasonChampions) > allTimeRecordsDict['team']['allTime']['regSeasonTitles']['value']:
                allTimeRecordsDict['team']['allTime']['regSeasonTitles']['value'] = len(team.regularSeasonChampions)
                allTimeRecordsDict['team']['allTime']['regSeasonTitles']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['regSeasonTitles']['id'] = team.id


def checkSeasonRecords(season):
    for player in activePlayerList:
        player: FloosPlayer.Player
        if player.seasonStatsDict['passing']['att'] > 0:
            if player.seasonStatsDict['passing']['comp'] > allTimeRecordsDict['players']['passing']['season']['comps']['value']:
                allTimeRecordsDict['players']['passing']['season']['comps']['value'] = player.seasonStatsDict['passing']['comp']
                allTimeRecordsDict['players']['passing']['season']['comps']['name'] = player.name
                allTimeRecordsDict['players']['passing']['season']['comps']['id'] = player.id
                allTimeRecordsDict['players']['passing']['season']['comps']['season'] = season
            if player.seasonStatsDict['passing']['yards'] > allTimeRecordsDict['players']['passing']['season']['yards']['value']:
                allTimeRecordsDict['players']['passing']['season']['yards']['value'] = player.seasonStatsDict['passing']['yards']
                allTimeRecordsDict['players']['passing']['season']['yards']['name'] = player.name
                allTimeRecordsDict['players']['passing']['season']['yards']['id'] = player.id
                allTimeRecordsDict['players']['passing']['season']['yards']['season'] = season
            if player.seasonStatsDict['passing']['tds'] > allTimeRecordsDict['players']['passing']['season']['tds']['value']:
                allTimeRecordsDict['players']['passing']['season']['tds']['value'] = player.seasonStatsDict['passing']['tds']
                allTimeRecordsDict['players']['passing']['season']['tds']['name'] = player.name
                allTimeRecordsDict['players']['passing']['season']['tds']['id'] = player.id
                allTimeRecordsDict['players']['passing']['season']['tds']['season'] = season
            if player.seasonStatsDict['passing']['ints'] > allTimeRecordsDict['players']['passing']['season']['ints']['value']:
                allTimeRecordsDict['players']['passing']['season']['ints']['value'] = player.seasonStatsDict['passing']['ints']
                allTimeRecordsDict['players']['passing']['season']['ints']['name'] = player.name
                allTimeRecordsDict['players']['passing']['season']['ints']['id'] = player.id
                allTimeRecordsDict['players']['passing']['season']['ints']['season'] = season

        if player.seasonStatsDict['rushing']['carries'] > 0:
            if player.seasonStatsDict['rushing']['yards'] > allTimeRecordsDict['players']['rushing']['season']['yards']['value']:
                allTimeRecordsDict['players']['rushing']['season']['yards']['value'] = player.seasonStatsDict['rushing']['yards']
                allTimeRecordsDict['players']['rushing']['season']['yards']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['season']['yards']['id'] = player.id
                allTimeRecordsDict['players']['rushing']['season']['yards']['season'] = season
            if player.seasonStatsDict['rushing']['tds'] > allTimeRecordsDict['players']['rushing']['season']['tds']['value']:
                allTimeRecordsDict['players']['rushing']['season']['tds']['value'] = player.seasonStatsDict['rushing']['tds']
                allTimeRecordsDict['players']['rushing']['season']['tds']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['season']['tds']['id'] = player.id
                allTimeRecordsDict['players']['rushing']['season']['tds']['season'] = season
            if player.seasonStatsDict['rushing']['fumblesLost'] > allTimeRecordsDict['players']['rushing']['season']['fumbles']['value']:
                allTimeRecordsDict['players']['rushing']['season']['fumbles']['value'] = player.seasonStatsDict['rushing']['fumblesLost']
                allTimeRecordsDict['players']['rushing']['season']['fumbles']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['season']['fumbles']['id'] = player.id
                allTimeRecordsDict['players']['rushing']['season']['fumbles']['season'] = season
        
        if player.seasonStatsDict['receiving']['receptions'] > 0:
            if player.seasonStatsDict['receiving']['yards'] > allTimeRecordsDict['players']['receiving']['season']['yards']['value']:
                allTimeRecordsDict['players']['receiving']['season']['yards']['value'] = player.seasonStatsDict['receiving']['yards']
                allTimeRecordsDict['players']['receiving']['season']['yards']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['season']['yards']['id'] = player.id
                allTimeRecordsDict['players']['receiving']['season']['yards']['season'] = season
            if player.seasonStatsDict['receiving']['tds'] > allTimeRecordsDict['players']['receiving']['season']['tds']['value']:
                allTimeRecordsDict['players']['receiving']['season']['tds']['value'] = player.seasonStatsDict['receiving']['tds']
                allTimeRecordsDict['players']['receiving']['season']['tds']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['season']['tds']['id'] = player.id
                allTimeRecordsDict['players']['receiving']['season']['tds']['season'] = season
            if player.seasonStatsDict['receiving']['receptions'] > allTimeRecordsDict['players']['receiving']['season']['receptions']['value']:
                allTimeRecordsDict['players']['receiving']['season']['receptions']['value'] = player.seasonStatsDict['receiving']['receptions']
                allTimeRecordsDict['players']['receiving']['season']['receptions']['name'] = player.name
                allTimeRecordsDict['players']['receiving']['season']['receptions']['id'] = player.id
                allTimeRecordsDict['players']['receiving']['season']['receptions']['season'] = season
        
        if player.seasonStatsDict['kicking']['fgs'] > 0:
            if player.seasonStatsDict['kicking']['fgs'] > allTimeRecordsDict['players']['kicking']['season']['fgs']['value']:
                allTimeRecordsDict['players']['kicking']['season']['fgs']['value'] = player.seasonStatsDict['kicking']['fgs']
                allTimeRecordsDict['players']['kicking']['season']['fgs']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['season']['fgs']['id'] = player.id
                allTimeRecordsDict['players']['kicking']['season']['fgs']['season'] = season
            if player.seasonStatsDict['kicking']['fgYards'] > allTimeRecordsDict['players']['kicking']['season']['fgYards']['value']:
                allTimeRecordsDict['players']['kicking']['season']['fgYards']['value'] = player.seasonStatsDict['kicking']['fgYards']
                allTimeRecordsDict['players']['kicking']['season']['fgYards']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['season']['fgYards']['id'] = player.id
                allTimeRecordsDict['players']['kicking']['season']['fgYards']['season'] = season
        
        if player.seasonStatsDict['defense']['ints'] > 0:
            if player.seasonStatsDict['defense']['ints'] > allTimeRecordsDict['players']['defense']['season']['ints']['value']:
                allTimeRecordsDict['players']['defense']['season']['ints']['value'] = player.seasonStatsDict['defense']['ints']
                allTimeRecordsDict['players']['defense']['season']['ints']['name'] = player.name
                allTimeRecordsDict['players']['defense']['season']['ints']['id'] = player.id
                allTimeRecordsDict['players']['defense']['season']['ints']['season'] = season
        
        if player.seasonStatsDict['defense']['sacks'] > 0:
            if player.seasonStatsDict['defense']['sacks'] > allTimeRecordsDict['players']['defense']['season']['sacks']['value']:
                allTimeRecordsDict['players']['defense']['season']['sacks']['value'] = player.seasonStatsDict['defense']['sacks']
                allTimeRecordsDict['players']['defense']['season']['sacks']['name'] = player.name
                allTimeRecordsDict['players']['defense']['season']['sacks']['id'] = player.id
                allTimeRecordsDict['players']['defense']['season']['sacks']['season'] = season
        
        if player.seasonStatsDict['defense']['tackles'] > 0:
            if player.seasonStatsDict['defense']['tackles'] > allTimeRecordsDict['players']['defense']['season']['tackles']['value']:
                allTimeRecordsDict['players']['defense']['season']['tackles']['value'] = player.seasonStatsDict['defense']['tackles']
                allTimeRecordsDict['players']['defense']['season']['tackles']['name'] = player.name
                allTimeRecordsDict['players']['defense']['season']['tackles']['id'] = player.id
                allTimeRecordsDict['players']['defense']['season']['tackles']['season'] = season
        
        if player.seasonStatsDict['defense']['fumRec'] > 0:
            if player.seasonStatsDict['defense']['fumRec'] > allTimeRecordsDict['players']['defense']['season']['fumRec']['value']:
                allTimeRecordsDict['players']['defense']['season']['fumRec']['value'] = player.seasonStatsDict['defense']['fumRec']
                allTimeRecordsDict['players']['defense']['season']['fumRec']['name'] = player.name
                allTimeRecordsDict['players']['defense']['season']['fumRec']['id'] = player.id
                allTimeRecordsDict['players']['defense']['season']['fumRec']['season'] = season

        for team in teamList:
            team: FloosTeam.Team
            if team.seasonTeamStats['Offense']['totalYards'] > allTimeRecordsDict['team']['season']['yards']['value']:
                allTimeRecordsDict['team']['season']['yards']['value'] = team.seasonTeamStats['Offense']['totalYards']
                allTimeRecordsDict['team']['season']['yards']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['season']['yards']['id'] = team.id
                allTimeRecordsDict['team']['season']['yards']['season'] = season
    
            if team.seasonTeamStats['Offense']['tds'] > allTimeRecordsDict['team']['season']['tds']['value']:
                allTimeRecordsDict['team']['season']['tds']['value'] = team.seasonTeamStats['Offense']['tds']
                allTimeRecordsDict['team']['season']['tds']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['season']['tds']['id'] = team.id
                allTimeRecordsDict['team']['season']['tds']['season'] = season
    
            if team.seasonTeamStats['Offense']['pts'] > allTimeRecordsDict['team']['season']['pts']['value']:
                allTimeRecordsDict['team']['season']['pts']['value'] = team.seasonTeamStats['Offense']['pts']
                allTimeRecordsDict['team']['season']['pts']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['season']['pts']['id'] = team.id
                allTimeRecordsDict['team']['season']['pts']['season'] = season
    
            if team.seasonTeamStats['Defense']['ints'] > allTimeRecordsDict['team']['season']['ints']['value']:
                allTimeRecordsDict['team']['season']['ints']['value'] = team.seasonTeamStats['Defense']['ints']
                allTimeRecordsDict['team']['season']['ints']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['season']['ints']['id'] = team.id
                allTimeRecordsDict['team']['season']['ints']['season'] = season
    
            if team.seasonTeamStats['Defense']['fumRec'] > allTimeRecordsDict['team']['season']['fumRec']['value']:
                allTimeRecordsDict['team']['season']['fumRec']['value'] = team.seasonTeamStats['Defense']['fumRec']
                allTimeRecordsDict['team']['season']['fumRec']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['season']['fumRec']['id'] = team.id
                allTimeRecordsDict['team']['season']['fumRec']['season'] = season
    
            if team.elo > allTimeRecordsDict['team']['season']['elo']['value']:
                allTimeRecordsDict['team']['season']['elo']['value'] = team.elo
                allTimeRecordsDict['team']['season']['elo']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['season']['elo']['id'] = team.id
                allTimeRecordsDict['team']['season']['elo']['season'] = season





    
class Division:
    def __init__(self, name):
        self.name = name
        self.teamList = []

class Season:
    def __init__(self):
        self.currentSeason = seasonsPlayed + 1
        self.activeGames = None
        self.currentWeek = None
        self.currentWeekText = None
        self.leagueHighlights = []
        self.divisionLeadersList = []
        self.nonDivisionLeaderPlayoffTeamsList = []
        self.nonPlayoffTeamsList = []

    def updatePlayoffPicture(self):
        nonDivisionLeaderTeamList = []
        self.divisionLeadersList.clear()
        self.nonDivisionLeaderPlayoffTeamsList.clear()
        self.nonPlayoffTeamsList.clear()

        for division in divisionList:
                division: Division
                for t in range(len(division.teamList)):
                    if t == 0:
                        self.divisionLeadersList.append(division.teamList[t])
                    else:
                        nonDivisionLeaderTeamList.append(division.teamList[t])

        list.sort(self.divisionLeadersList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
        list.sort(nonDivisionLeaderTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

        for t in range(len(nonDivisionLeaderTeamList)):
            if t < 8:
                self.nonDivisionLeaderPlayoffTeamsList.append(nonDivisionLeaderTeamList[t])
            else:
                self.nonPlayoffTeamsList.append(nonDivisionLeaderTeamList[t])

        list.sort(self.nonDivisionLeaderPlayoffTeamsList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
        list.sort(self.nonPlayoffTeamsList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)



    def checkForClinches(self):
        team1: FloosTeam.Team = teamList[0]
        team2: FloosTeam.Team = teamList[1]
        team12: FloosTeam.Team = self.nonDivisionLeaderPlayoffTeamsList[7]
        team13: FloosTeam.Team = self.nonPlayoffTeamsList[0]
        for division in divisionList:
            division: Division
            divTeam1: FloosTeam.Team = division.teamList[0]
            divTeam2: FloosTeam.Team = division.teamList[1] 

            if not divTeam1.clinchedDivision:
                divTeam1.clinchedDivision = FloosMethods.checkIfClinched(divTeam1.seasonTeamStats['wins'], divTeam2.seasonTeamStats['wins'], 28 - self.currentWeek)
                if divTeam1.clinchedDivision:
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have won the {2} Division'.format(divTeam1.city, divTeam1.name, divTeam1.division)}})
                    if not divTeam1.clinchedPlayoffs:
                        divTeam1.clinchedPlayoffs = True
                        self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(divTeam1.city, divTeam1.name)}})
                elif self.currentWeek == 28:
                    divTeam1.clinchedDivision =  True
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have won the {2} Division'.format(divTeam1.city, divTeam1.name, divTeam1.division)}})
                    if not divTeam1.clinchedPlayoffs:
                        divTeam1.clinchedPlayoffs = True
                        self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(divTeam1.city, divTeam1.name)}})

        for team in self.divisionLeadersList:
            team: FloosTeam.Team
            if not team.clinchedPlayoffs:
                team.clinchedPlayoffs = FloosMethods.checkIfClinched(team.seasonTeamStats['wins'], team13.seasonTeamStats['wins'], 28 - self.currentWeek)
                if team.clinchedPlayoffs:
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}}) 

        if not team1.clinchedTopSeed:
            team1.clinchedTopSeed = FloosMethods.checkIfClinched(team1.seasonTeamStats['wins'], team2.seasonTeamStats['wins'], 28 - self.currentWeek)
            if team1.clinchedTopSeed:
                self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched the #1 seed'.format(team1.city, team1.name)}})
            elif self.currentWeek == 28:
                team1.clinchedTopSeed = True
                self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched the #1 seed'.format(team1.city, team1.name)}})

        

        if self.currentWeek == 28:
            for team in self.nonDivisionLeaderPlayoffTeamsList:
                team: FloosTeam.Team
                if not team.clinchedPlayoffs:
                    team.clinchedPlayoffs = True
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}})
            for team in self.nonPlayoffTeamsList:
                team: FloosTeam.Team
                if not team.eliminated:
                    team.eliminated = True
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
        else:
            for team in self.nonDivisionLeaderPlayoffTeamsList:
                team:FloosTeam.Team
                if not team.clinchedPlayoffs and not team.eliminated:
                    team.clinchedPlayoffs = FloosMethods.checkIfClinched(team.seasonTeamStats['wins'], team13.seasonTeamStats['wins'], 28 - self.currentWeek)
                    if team.clinchedPlayoffs:
                        self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}})
            for team in self.nonPlayoffTeamsList:
                team:FloosTeam.Team
                if not team.clinchedPlayoffs and not team.eliminated:
                    team.eliminated = FloosMethods.checkIfEliminated(team.seasonTeamStats['wins'], team12.seasonTeamStats['wins'], 28 - self.currentWeek)
                    if team.eliminated:
                        self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})


    def createSchedule(self):
        numOfWeeks = len(scheduleScheme)
        scheduleList.clear()
        dateTimeNow = datetime.datetime.utcnow()
        for week in range(0, numOfWeeks):
            gameList = []
            numOfGames = int(len(teamList)/2)
            weekStartTime = self.getWeekStartTime(dateTimeNow, week)
            for x in range(0, numOfGames):
                game = scheduleScheme[week][x]
                homeTeam:FloosTeam.Team = divisionList[int(game[0]) - 1].teamList[int(game[1]) - 1]
                awayTeam:FloosTeam.Team = divisionList[int(game[2]) - 1].teamList[int(game[3]) - 1]
                newGame = FloosGame.Game(homeTeam,awayTeam)
                newGame.id = 's{0}w{1}g{2}'.format(self.currentSeason, week+1, x+1)
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.isRegularSeasonGame = True
                newGame.startTime = weekStartTime
                homeTeam.schedule.append(newGame)
                awayTeam.schedule.append(newGame)
                gameList.append(newGame)
            scheduleList.append({'startTime': weekStartTime, 'games': gameList})

    def getWeekStartTime(self, now:datetime.datetime, week:int):
        global dateNowUtc
        global dateNow
        global utcOffset

        startDay = 4
        monthDays = 0
        startTimeHoursList = [11, 12, 13, 14, 15, 16, 17]

        if now.month == 1 or now.month == 3 or now.month == 5 or now.month == 7 or now.month == 8 or now.month == 10 or now.month == 12:
            monthDays = 31
        elif now.month == 4 or now.month == 6 or now.month == 9 or now.month == 11:
            monthDays = 30
        elif now.month == 2:
            if (now.year % 4) == 0:
                monthDays = 29
            else:
                monthDays = 28

        startTimeHour = startTimeHoursList[week%7]


        todayWeekDay = dateNowUtc.isoweekday()

        if week > 28:
            if week == 32:
                if todayWeekDay == startDay + 5:
                    startDayOffset = 0
                else:
                    startDayOffset = (startDay + 5) - todayWeekDay
            else:
                if todayWeekDay == startDay + 5:
                    startDayOffset = startDay + 4
                elif todayWeekDay == startDay + 4:
                    startDayOffset = 0
                else:
                    startDayOffset = (startDay + 4) - todayWeekDay
            dayOffset = startDayOffset
        else:
            if todayWeekDay == startDay - 1:
                startDayOffset = startDay - 1
            elif todayWeekDay == startDay:
                startDayOffset = 0
            else:
                startDayOffset = startDay + 7 - todayWeekDay

            dayOffset = math.floor((week)/7) + startDayOffset


        if (now.day + dayOffset) > monthDays:
            if now.month + 1 > 12:
                return datetime.datetime(now.year + 1, 1, dayOffset - (monthDays - now.day), startTimeHour)
            else:
                return datetime.datetime(now.year, now.month + 1, dayOffset - (monthDays - now.day), startTimeHour)
        else:
            if startTimeHour + utcOffset == 24:
                return datetime.datetime(now.year, now.month, now.day + dayOffset, 0)
            else:
                return datetime.datetime(now.year, now.month, now.day + dayOffset, startTimeHour + utcOffset)
            

    def saveSeasonStats(self):
        dict = {}
        jsonFile = open("data/teamData.json", "w+")
        for team in teamList:
            team: FloosTeam.Team
            teamDict = {}
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                playerDict = {}
                player: FloosPlayer.Player
                player.seasonsPlayed += 1
                if player.seasonStatsDict['passing']['yards'] > 0:
                    #player.careerStatsDict['passing']['att'] += player.seasonStatsDict['passing']['att']
                    #player.careerStatsDict['passing']['comp'] += player.seasonStatsDict['passing']['comp']
                    #player.careerStatsDict['passing']['tds'] += player.seasonStatsDict['passing']['tds']
                    #player.careerStatsDict['passing']['ints'] += player.seasonStatsDict['passing']['ints']
                    #player.careerStatsDict['passing']['yards'] += player.seasonStatsDict['passing']['yards']
                    #player.careerStatsDict['passing']['missedPass'] += player.seasonStatsDict['passing']['missedPass']
                    player.careerStatsDict['passing']['20+'] += player.seasonStatsDict['passing']['20+']
                    player.careerStatsDict['passing']['ypc'] = round(player.careerStatsDict['passing']['yards']/player.careerStatsDict['passing']['comp'])
                    player.careerStatsDict['passing']['compPerc'] = round((player.careerStatsDict['passing']['comp']/player.careerStatsDict['passing']['att'])*100)
                    if player.seasonStatsDict['passing']['longest'] > player.careerStatsDict['passing']['longest']:
                        player.careerStatsDict['passing']['longest'] = player.seasonStatsDict['passing']['longest']
                    team.seasonTeamStats['Offense']['passYards'] += player.seasonStatsDict['passing']['yards']
                if player.seasonStatsDict['receiving']['yards'] > 0:
                    #player.careerStatsDict['receiving']['receptions'] += player.seasonStatsDict['receiving']['receptions']
                    #player.careerStatsDict['receiving']['targets'] += player.seasonStatsDict['receiving']['targets']
                    #player.careerStatsDict['receiving']['yac'] += player.seasonStatsDict['receiving']['yac']
                    #player.careerStatsDict['receiving']['yards'] += player.seasonStatsDict['receiving']['yards']
                    #player.careerStatsDict['receiving']['tds'] += player.seasonStatsDict['receiving']['tds']
                    #player.careerStatsDict['receiving']['drops'] += player.seasonStatsDict['receiving']['drops']
                    player.careerStatsDict['receiving']['20+'] += player.seasonStatsDict['receiving']['20+']
                    if player.seasonStatsDict['receiving']['longest'] > player.careerStatsDict['receiving']['longest']:
                        player.careerStatsDict['receiving']['longest'] = player.seasonStatsDict['receiving']['longest']
                    if player.careerStatsDict['receiving']['receptions'] > 0:
                        player.careerStatsDict['receiving']['ypr'] = round(player.careerStatsDict['receiving']['yards']/player.careerStatsDict['receiving']['receptions'])
                        player.careerStatsDict['receiving']['rcvPerc'] = round((player.careerStatsDict['receiving']['receptions']/player.careerStatsDict['receiving']['targets'])*100)
                if player.seasonStatsDict['rushing']['carries'] > 0:
                    #player.careerStatsDict['rushing']['carries'] += player.seasonStatsDict['rushing']['carries']
                    #player.careerStatsDict['rushing']['yards'] += player.seasonStatsDict['rushing']['yards']
                    #player.careerStatsDict['rushing']['tds'] += player.seasonStatsDict['rushing']['tds']
                    #player.careerStatsDict['rushing']['fumblesLost'] += player.seasonStatsDict['rushing']['fumblesLost']
                    player.careerStatsDict['rushing']['20+'] += player.seasonStatsDict['rushing']['20+']
                    player.careerStatsDict['rushing']['ypc'] = round(player.careerStatsDict['rushing']['yards']/player.careerStatsDict['rushing']['carries'])
                    if player.seasonStatsDict['rushing']['longest'] > player.careerStatsDict['rushing']['longest']:
                        player.careerStatsDict['rushing']['longest'] = player.seasonStatsDict['rushing']['longest']
                    team.seasonTeamStats['Offense']['runYards'] += player.seasonStatsDict['rushing']['yards']
                if player.seasonStatsDict['kicking']['fgAtt'] > 0:
                    if player.seasonStatsDict['kicking']['fgs'] > 0:
                        player.seasonStatsDict['kicking']['fgPerc'] = round((player.seasonStatsDict['kicking']['fgs']/player.seasonStatsDict['kicking']['fgAtt'])*100)
                    else:
                        player.seasonStatsDict['kicking']['fgPerc'] = 0

                    #player.careerStatsDict['kicking']['fgAtt'] += player.seasonStatsDict['kicking']['fgAtt']
                    #player.careerStatsDict['kicking']['fgs'] += player.seasonStatsDict['kicking']['fgs']
                    #player.careerStatsDict['kicking']['fg45+'] += player.seasonStatsDict['kicking']['fg45+']
                    #player.careerStatsDict['kicking']['fgYards'] += player.seasonStatsDict['kicking']['fgYards']
                    if player.seasonStatsDict['kicking']['longest'] > player.careerStatsDict['kicking']['longest']:
                        player.careerStatsDict['kicking']['longest'] = player.seasonStatsDict['kicking']['longest']
                    if player.careerStatsDict['kicking']['fgs'] > 0:
                        player.careerStatsDict['kicking']['fgPerc'] = round((player.careerStatsDict['kicking']['fgs']/player.careerStatsDict['kicking']['fgAtt'])*100)
                    else:
                        player.careerStatsDict['kicking']['fgPerc'] = 0
                    team.seasonTeamStats['Offense']['tds'] += (player.seasonStatsDict['passing']['tds'] + player.seasonStatsDict['rushing']['tds'] + player.seasonStatsDict['receiving']['tds'])

                if isinstance(player, FloosPlayer.PlayerDB) or isinstance(player, FloosPlayer.PlayerDefBasic):
                    #player.careerStatsDict['defense']['tackles'] += player.seasonStatsDict['defense']['tackles']
                    #player.careerStatsDict['defense']['sacks'] += player.seasonStatsDict['defense']['sacks']
                    #player.careerStatsDict['defense']['fumRec'] += player.seasonStatsDict['defense']['fumRec']
                    #player.careerStatsDict['defense']['ints'] += player.seasonStatsDict['defense']['ints']
                    #player.careerStatsDict['defense']['passTargets'] += player.seasonStatsDict['defense']['passTargets']
                    #player.careerStatsDict['defense']['passDisruptions'] += player.seasonStatsDict['defense']['passDisruptions']
                    if player.careerStatsDict['defense']['passTargets'] > 0:
                        player.careerStatsDict['defense']['passDisPerc'] = round((player.careerStatsDict['defense']['passDisruptions']/player.careerStatsDict['defense']['passTargets'])*100)

                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['pos'] = player.position.name
                playerDict['rating'] = player.attributes.overallRating
                playerDict['seasonsPlayed'] = player.seasonsPlayed
                playerDict['gamesPlayed'] = player.gamesPlayed
                playerDict['term'] = player.term
                playerDict['termRemaining'] = player.termRemaining
                playerDict['capHit'] = player.capHit
                playerDict['seasonStats'] = player.seasonStatsDict
                rosterDict[pos] = playerDict


            team.seasonTeamStats['Offense']['totalYards'] = team.seasonTeamStats['Offense']['passYards'] + team.seasonTeamStats['Offense']['runYards']
            team.seasonTeamStats['winPerc'] = round(team.seasonTeamStats['wins']/(team.seasonTeamStats['wins']+team.seasonTeamStats['losses']),3)
            team.allTimeTeamStats['wins'] += team.seasonTeamStats['wins']
            team.allTimeTeamStats['losses'] += team.seasonTeamStats['losses']
            team.allTimeTeamStats['Offense']['tds'] += team.seasonTeamStats['Offense']['tds']
            team.allTimeTeamStats['Offense']['fgs'] += team.seasonTeamStats['Offense']['fgs']
            team.allTimeTeamStats['Offense']['passYards'] += team.seasonTeamStats['Offense']['passYards']
            team.allTimeTeamStats['Offense']['runYards'] += team.seasonTeamStats['Offense']['runYards']
            team.allTimeTeamStats['Offense']['totalYards'] += team.seasonTeamStats['Offense']['totalYards']
            team.allTimeTeamStats['Defense']['sacks'] += team.seasonTeamStats['Defense']['sacks']
            team.allTimeTeamStats['Defense']['ints'] += team.seasonTeamStats['Defense']['ints']
            team.allTimeTeamStats['Defense']['fumRec'] += team.seasonTeamStats['Defense']['fumRec']
            team.allTimeTeamStats['winPerc'] = round(team.allTimeTeamStats['wins']/(team.allTimeTeamStats['wins']+team.allTimeTeamStats['losses']),3)

            teamDict['name'] = team.name
            teamDict['city'] = team.city
            teamDict['abbr'] = team.abbr
            teamDict['color'] = team.color
            teamDict['id'] = team.id
            teamDict['offenseRating'] = team.offenseRating
            teamDict['runDefenseRating'] = team.runDefenseRating
            teamDict['passDefenseRating'] = team.passDefenseRating
            teamDict['defenseRating'] = team.defenseRating
            #teamDict['defenseLuck'] = team.defenseLuck
            #teamDict['defenseDiscipline'] = team.defenseDiscipline
            teamDict['overallRating'] = team.overallRating
            teamDict['allTimeTeamStats'] = team.allTimeTeamStats
            teamDict['leagueChampionships'] = team.leagueChampionships
            teamDict['playoffAppearances'] = team.playoffAppearances
            teamDict['gmScore'] = team.gmScore
            teamDict['defenseTier'] = team.defenseTier
            teamDict['leagueChampionships'] = team.leagueChampionships
            teamDict['rosterHistory'] = team.rosterHistory
            teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating
            teamDict['roster'] = rosterDict
            dict[team.id] = teamDict

        jsonFile.write(json.dumps(dict, indent=4))
        jsonFile.close()
        savePlayerData()

    def clearPlayerSeasonStats(self):
        for player in activePlayerList:
            player: FloosPlayer.Player
            if player.seasonsPlayed > 0:
                player.seasonStatsDict['rating'] = player.playerTier.value
                seasonStatsCopy = copy.deepcopy(player.seasonStatsDict)
                player.seasonStatsArchive.pop(0)
                player.seasonStatsArchive.insert(0, seasonStatsCopy)
                player.seasonStatsDict = copy.deepcopy(FloosPlayer.playerStatsDict)
                player.gamesPlayed = 0

    def clearTeamSeasonStats(self):
        for team in teamList:
            team: FloosTeam.Team
            team.seasonTeamStats['elo'] = team.elo
            team.seasonTeamStats['overallRating'] = team.overallRating
            team.statArchive.insert(0,team.seasonTeamStats)
            team.seasonTeamStats = copy.deepcopy(FloosTeam.teamStatsDict)
            team.schedule = []
 

    async def startSeason(self):
        global freeAgencyOrder
        global leagueChampion
        weekDict = {}
        seasonDict = {}
        gameDictTemp = {}
        freeAgencyOrder = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)

        for team in teamList:
            team: FloosTeam.Team
            team.eliminated = False
            team.clinchedDivision = False
            team.clinchedPlayoffs = False
            team.clinchedTopSeed = False
            team.leagueChampion = False
            team.winningStreak = False
            team.seasonTeamStats['season'] = self.currentSeason
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                player: FloosPlayer.Player
                rosterDict[pos] = {'name': player.name, 'pos': player.position.name, 'rating': player.playerTier.value, 'termRemaining': player.termRemaining, 'id': player.id}
            team.rosterHistory.append({'season': self.currentSeason, 'roster': rosterDict})


        weekFilePath = '{}/games'.format(strCurrentSeason)
        if os.path.isdir(weekFilePath):
            for f in os.listdir(weekFilePath):
                os.remove(os.path.join(weekFilePath, f))
        else:
            if not os.path.isdir(strCurrentSeason):
                os.mkdir(strCurrentSeason)
                os.mkdir('{}/games'.format(strCurrentSeason))
            else:
                os.mkdir('{}/games'.format(strCurrentSeason))

        for player in activePlayerList:
            if isinstance(player.team, FloosTeam.Team):
                player.seasonStatsDict['team'] = player.team.abbr
                player.seasonStatsDict['color'] = player.team.color
            else:
                player.seasonStatsDict['team'] = 'FA'
                player.seasonStatsDict['color'] = '#94a3b8'
            player.seasonStatsDict['season'] = self.currentSeason
            player.seasonStatsDict['gp'] = player.gamesPlayed
            player.seasonStatsDict['rating'] = player.playerTier.value
            player.seasonStatsArchive.insert(0,player.seasonStatsDict)


        self.leagueHighlights.insert(0, {'event':  {'text': 'Season {} Start'.format(self.currentSeason)}})

        for week in scheduleList:
            weekStartTime: datetime.datetime = week['startTime']
            weekSetupTime: datetime.datetime = weekStartTime - datetime.timedelta(minutes=10)

            timeToWeekStart = weekStartTime - datetime.datetime.utcnow()
            timeToWeekStartMinutes = timeToWeekStart.total_seconds()/60
            
            if timeToWeekStartMinutes > 60:
                if self.currentWeek is not None:
                    pass
                    # while datetime.datetime.utcnow().day < weekStartTime.day:
                    #     await asyncio.sleep(30)
                self.currentWeek = scheduleList.index(week)+1
                self.currentWeekText = 'Week {}'.format(self.currentWeek)
                self.activeGames = week['games']
                gameDict = gameDictTemp.copy()
                self.leagueHighlights = []
                for game in range(0,len(self.activeGames)):
                    self.activeGames[game].leagueHighlights = self.leagueHighlights
                    self.activeGames[game].calculateWinProbability()

                #while datetime.datetime.utcnow() < weekSetupTime:
                #   await asyncio.sleep(30)

            else:
                #while datetime.datetime.utcnow() < weekSetupTime:
                #   await asyncio.sleep(30)
                self.currentWeek = scheduleList.index(week)+1
                self.currentWeekText = 'Week {}'.format(self.currentWeek)
                self.activeGames = week['games']
                gameDict = gameDictTemp.copy()
                self.leagueHighlights = []
                for game in range(0,len(self.activeGames)):
                    self.activeGames[game].leagueHighlights = self.leagueHighlights
                    self.activeGames[game].calculateWinProbability()
                
            self.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            

            gamesList = [self.activeGames[game].playGame() for game in range(0,len(self.activeGames))]

            await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < weekStartTime:
            #     await asyncio.sleep(30)

            self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})
            await asyncio.wait(gamesList)

            for game in range(0,len(self.activeGames)):
                strGame = 'Game {}'.format(game + 1)
                gameResults = self.activeGames[game].gameDict
                gameDict[strGame] = gameResults
                checkTeamGameRecords(self.activeGames[game])
            weekDict = FloosMethods._prepare_for_serialization(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(self.currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()
            
            for division in divisionList:
                list.sort(division.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            list.sort(teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            getPerformanceRating()
            sortPlayers()
            sortDefenses()
            self.updatePlayoffPicture()
            self.checkForClinches()
            checkPlayerGameRecords()
            checkCareerRecords()
            checkSeasonRecords(self.currentSeason)
            self.leagueHighlights.insert(0, {'event': {'text': '{} End'.format(self.currentWeekText)}})
            await asyncio.sleep(30)

        list.sort(teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
        bestTeam:FloosTeam.Team = teamList[0]
        bestTeam.regularSeasonChampions.append('Season {}'.format(seasonsPlayed+1))
        #seasonDict['games'] = weekDict
        leagueChampion = await self.playPlayoffs()

        self.saveSeasonStats()

        standingsDict = {}
        divStandingsTempDict = {}
        jsonFile = open("data/divisionData.json", "w+")
        for division in divisionList:
            list.sort(division.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            divStandingsDict = divStandingsTempDict.copy()
            #print("\n{0} Division".format(division.name))
            for team in division.teamList:
                divStandingsDict[team.name] = '{0} - {1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            standingsDict[division.name] = divStandingsDict

        jsonFile.write(json.dumps(standingsDict, indent=4))
        jsonFile.close()

        seasonDict['standings'] = standingsDict
        seasonDict['champion'] = leagueChampion.name
        leagueChampion.seasonTeamStats['leagueChamp'] = True
        leagueChampion.leagueChampion = True

        _serialzedDict = FloosMethods._prepare_for_serialization(seasonDict)

        if os.path.isdir(strCurrentSeason):
            for f in os.listdir(strCurrentSeason):
                if os.path.isfile(os.path.join(strCurrentSeason, f)):
                    os.remove(os.path.join(strCurrentSeason, f))
        else:
            os.mkdir(strCurrentSeason)
        jsonFile = open(os.path.join(strCurrentSeason, 'seasonData.json'), "w+")
        jsonFile.write(json.dumps(_serialzedDict, indent=4))
        jsonFile.close()

        teamDict = {}
        for team in teamList:
            team: FloosTeam.Team
            dict = {}
            team.saveRoster()
            dict['id'] = team.id
            dict['rating'] = team.overallRating
            dict['offenseRating'] = team.offenseRating
            dict['defenseRating'] = team.defenseRating
            dict['runDefenseRating'] = team.runDefenseRating
            dict['passDefenseRating'] = team.passDefenseRating
            dict['leagueChampionships'] = team.leagueChampionships
            dict['playoffAppearances'] = team.playoffAppearances
            dict['seasonTeamStats'] = team.seasonTeamStats
            dict['playerCap'] = team.playerCap
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                player: FloosPlayer.Player
                playerDict = {}
                playerDict['name'] = player.name
                playerDict['id'] = player.id
                playerDict['tier'] = player.playerTier.name
                playerDict['overallRating'] = player.attributes.overallRating
                playerDict['seasonsPlayed'] = player.seasonsPlayed
                playerDict['term'] = player.term
                playerDict['termRemaining'] = player.termRemaining
                playerDict['seasonPerformanceRating'] = player.seasonPerformanceRating
                playerDict['seasonStatsDict'] = player.seasonStatsDict
                rosterDict[pos] = playerDict
            dict['roster'] = rosterDict
            teamDict[team.name] = dict
        jsonFile = open(os.path.join(strCurrentSeason, 'teamData.json'), "w+")
        jsonFile.write(json.dumps(teamDict, indent=4))
        jsonFile.close()
        list.sort(teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)

    async def playPlayoffs(self):
        champ = None
        playoffDict = {}
        nonDivisionWinnersList = []
        playoffTeamsList = []
        playoffsByeTeamList = []
        playoffsNonByeTeamList = []
        nonPlayoffTeamList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)
        x = 0
        for division in divisionList:
            list.sort(division.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            division.teamList[0].clinchedDivision = True
            division.teamList[0].divisionChampionships.append('Season {}'.format(seasonsPlayed+1))
            division.teamList[0].seasonTeamStats['divPlace'] = '1st'
            division.teamList[0].seasonTeamStats['divisionChamp'] = True
            division.teamList[1].seasonTeamStats['divPlace'] = '2nd'
            division.teamList[2].seasonTeamStats['divPlace'] = '3rd'
            division.teamList[3].seasonTeamStats['divPlace'] = '4th'
            division.teamList[4].seasonTeamStats['divPlace'] = '5th'
            division.teamList[5].seasonTeamStats['divPlace'] = '6th'

            playoffsByeTeamList.append(division.teamList[0])
            nonDivisionWinnersList.append(division.teamList[1])
            nonDivisionWinnersList.append(division.teamList[2])
            nonDivisionWinnersList.append(division.teamList[3])
            nonDivisionWinnersList.append(division.teamList[4])
            nonDivisionWinnersList.append(division.teamList[5])

        list.sort(playoffsByeTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

        for team in nonDivisionWinnersList:
            team: FloosTeam.Team
            if team.clinchedPlayoffs:
                playoffsNonByeTeamList.append(team)
            elif team.eliminated:
                nonPlayoffTeamList.append(team)

        list.sort(playoffsNonByeTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

        playoffsByeTeamList[0].clinchedTopSeed = True
        playoffsByeTeamList[0].seasonTeamStats['topSeed'] = True
        
        freeAgencyOrder.extend(nonPlayoffTeamList)
        list.sort(freeAgencyOrder, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)

        numOfRounds = FloosMethods.getPower(2, len(playoffsByeTeamList) + len(playoffsNonByeTeamList))

        while len(playoffsNonByeTeamList) > 8:
            playoffsNonByeTeamList.pop()

        for team in playoffsByeTeamList:
            team: FloosTeam.Team
            team.playoffAppearances += 1
            team.seasonTeamStats['madePlayoffs'] = True
            team.clinchedPlayoffs = True
            team.winningStreak = False
        for team in playoffsNonByeTeamList:
            team: FloosTeam.Team
            team.playoffAppearances += 1
            team.seasonTeamStats['madePlayoffs'] = True
            team.winningStreak = False
            if not team.clinchedPlayoffs:
                team.clinchedPlayoffs = True
                team.eliminated = False
                self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}})

        for team in nonPlayoffTeamList:
            team: FloosTeam.Team
            team.winningStreak = False
            if not team.eliminated:
                team.eliminated = True
                team.clinchedPlayoffs = False
                self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
                

        for x in range(numOfRounds):

            playoffGamesList = []
            playoffGamesTaskList = []
            self.leagueHighlights = []
            currentRound = x + 1
            gameNumber = 1
            roundStartTime = self.getWeekStartTime(datetime.datetime.utcnow(), 28 + currentRound)

            if currentRound == 1:
                playoffTeamsList.extend(playoffsNonByeTeamList)

            list.sort(playoffTeamsList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

            if currentRound == 2:

                for z in range(len(playoffsByeTeamList)):
                    playoffTeamsList.insert(0, playoffsByeTeamList.pop())

                playoffsByeTeamList.clear()
                playoffsNonByeTeamList.clear()

            hiSeed = 0
            lowSeed = len(playoffTeamsList) - 1

            while lowSeed > hiSeed:
                newGame = FloosGame.Game(playoffTeamsList[hiSeed], playoffTeamsList[lowSeed])
                newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.startTime = roundStartTime
                newGame.isRegularSeasonGame = False
                newGame.calculateWinProbability()
                playoffGamesList.append(newGame)
                playoffGamesTaskList.append(newGame.playGame())
                newGame.leagueHighlights = self.leagueHighlights
                hiSeed += 1
                lowSeed -= 1
                gameNumber += 1
            
            scheduleList.append({'startTime': roundStartTime, 'games': playoffGamesList})

            self.activeGames = playoffGamesList
            if x < numOfRounds - 1:
                self.currentWeek = 'Playoffs Round {}'.format(x+1)
                self.currentWeekText = 'Playoffs Round {}'.format(x+1)
            else:
                self.currentWeek = 'Floos Bowl'
                self.currentWeekText = 'Floos Bowl'

            self.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < roundStartTime:
            #     await asyncio.sleep(30)
                
            self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})
            await asyncio.wait(playoffGamesTaskList)

            for game in playoffGamesList:
                game: FloosGame.Game
                gameResults = game.gameDict
                if len(playoffGamesList) == 1:
                    playoffTeamsList.clear()
                    game.winningTeam.leagueChampionships.append('Season {}'.format(seasonsPlayed+1))
                    champ: FloosTeam.Team = game.winningTeam
                    runnerUp: FloosTeam.Team = game.losingTeam
                    runnerUp.eliminated = True
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} are Floos Bowl champions!'.format(champ.city, champ.name)}})
                    playoffDict['Floos Bowl'] = gameResults
                    freeAgencyOrder.append(runnerUp)
                    freeAgencyOrder.append(champ)
                    for player in champ.rosterDict.values():
                        player:FloosPlayer.Player
                        player.leagueChampionships.append({'Season': seasonsPlayed+1, 'team': player.team.abbr, 'teamColor': player.team.color})
                    
                    championshipHistory.insert(0, { 'season': self.currentSeason,
                                                    'champion': '{} {}'.format(game.winningTeam.city, game.winningTeam.name),
                                                    'championColor': game.winningTeam.color,
                                                    'championId': game.winningTeam.id,
                                                    'championRecord': '{}-{}'.format(game.winningTeam.seasonTeamStats['wins'],game.winningTeam.seasonTeamStats['losses']),
                                                    'championElo': game.winningTeam.elo,
                                                    'runnerUp': '{} {}'.format(game.losingTeam.city, game.losingTeam.name),
                                                    'runnerUpColor': game.losingTeam.color,
                                                    'runnerUpId': game.losingTeam.id,
                                                    'runnerUpRecord': '{}-{}'.format(game.losingTeam.seasonTeamStats['wins'],game.losingTeam.seasonTeamStats['losses']),
                                                    'runnerUpElo': game.losingTeam.elo
                                                    })
                else:
                    playoffDict[game.id] = gameResults
                    for team in playoffTeamsList:
                        if team.name == gameResults['losingTeam']:
                            team.eliminated = True
                            self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
                            freeAgencyOrder.append(team)
                            playoffTeamsList.remove(team)
                            break

            jsonFile = open(os.path.join('{}/games'.format(strCurrentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()
            if x < numOfRounds - 1:
                sortPlayers()
                sortDefenses()
                await asyncio.sleep(30)

        return champ

def setNewingElo():
    ratingList = []
    eloList = []
    for team in teamList:
        team: FloosTeam.Team
        ratingList.append(team.overallRating)
        eloList.append(team.elo)
    
    meanRating = round(statistics.mean(ratingList))

    for team in teamList:
        team: FloosTeam.Team
        if len(team.statArchive):
            lastRating = team.statArchive[0]['overallRating']
            ratingDiff = round(team.overallRating / lastRating, 2)
            team.elo = round(team.elo * ratingDiff)
            
        else:
            teamRatingRank = round(team.overallRating / meanRating, 2)
            team.elo = round(team.elo * teamRatingRank)


def getPlayerTerm(tier: FloosPlayer.PlayerTier):
        if tier is FloosPlayer.PlayerTier.TierS:
            return randint(4,6)
        if tier is FloosPlayer.PlayerTier.TierA:
            return randint(3,4)
        elif tier is FloosPlayer.PlayerTier.TierD:
            return 1
        else:
            return randint(1,3)

def playerDraft():
    draftOrderList = []
    draftQueueList = teamList.copy()
    playerDraftList = activePlayerList.copy()
    rounds = 11

    draftQbList : list[FloosPlayer.Player] = []
    draftRbList : list[FloosPlayer.Player] = []
    draftWrList : list[FloosPlayer.Player] = []
    draftTeList : list[FloosPlayer.Player] = []
    draftKList : list[FloosPlayer.Player] = []
    draftDbList : list[FloosPlayer.Player] = []
    draftLbList : list[FloosPlayer.Player] = []
    draftDeList : list[FloosPlayer.Player] = []
    draftDlList : list[FloosPlayer.Player] = []

    for player in activePlayerList:
        if player.position.value == 1:
            draftQbList.append(player)
        elif player.position.value == 2:
            draftRbList.append(player)
        elif player.position.value == 3:
            draftWrList.append(player)
        elif player.position.value == 4:
            draftTeList.append(player)
        elif player.position.value == 5:
            draftKList.append(player)
        elif player.position.value == 6:
            draftDbList.append(player)
        elif player.position.value == 7:
            draftLbList.append(player)
        elif player.position.value == 8:
            draftDlList.append(player)
        elif player.position.value == 9:
            draftDeList.append(player)
    
    list.sort(draftQbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftRbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftWrList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftTeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftKList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftDbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftLbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftDlList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(draftDeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(playerDraftList, key=lambda player: player.attributes.skillRating, reverse=True)


    for x in range(len(teamList)):
        rand = randint(0,len(draftQueueList) - 1)
        draftOrderList.insert(x, draftQueueList[rand])
        draftQueueList.pop(rand)

    for x in range(1, int(rounds+1)):
        #print('\nRound {0}'.format(x))
        for team in draftOrderList:
            team: FloosTeam.Team
            openPosList = []
            selectedPlayer = None
            bestAvailablePlayer: FloosPlayer.Player = playerDraftList[0]
            if x == 1:
                if bestAvailablePlayer.position.value == 1:
                    selectedPlayer = draftQbList.pop(0)
                    team.rosterDict['qb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 2:
                    selectedPlayer = draftRbList.pop(0)
                    team.rosterDict['rb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 3:
                    selectedPlayer = draftWrList.pop(0)
                    if team.rosterDict['wr1'] is None:
                        team.rosterDict['wr1'] = selectedPlayer
                    elif team.rosterDict['wr2'] is None:
                        team.rosterDict['wr2'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 4:
                    selectedPlayer = draftTeList.pop(0)
                    team.rosterDict['te'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 5:
                    selectedPlayer = draftKList.pop(0)
                    team.rosterDict['k'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 6:
                    selectedPlayer = draftDbList.pop(0)
                    if team.rosterDict['db1'] is None:
                        team.rosterDict['db1'] = selectedPlayer
                    elif team.rosterDict['db2'] is None:
                        team.rosterDict['db2'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 7:
                    selectedPlayer = draftLbList.pop(0)
                    team.rosterDict['lb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 8:
                    selectedPlayer = draftDlList.pop(0)
                    team.rosterDict['dl'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif bestAvailablePlayer.position.value == 9:
                    selectedPlayer = draftDeList.pop(0)
                    team.rosterDict['de'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
            else:
                if team.rosterDict['qb'] is None:
                    openPosList.append(FloosPlayer.Position.QB.value)
                if team.rosterDict['rb'] is None:
                    openPosList.append(FloosPlayer.Position.RB.value)
                if team.rosterDict['wr1'] is None or team.rosterDict['wr2'] is None:
                    openPosList.append(FloosPlayer.Position.WR.value)
                if team.rosterDict['te'] is None:
                    openPosList.append(FloosPlayer.Position.TE.value)
                if team.rosterDict['k'] is None:
                    openPosList.append(FloosPlayer.Position.K.value)
                if team.rosterDict['db1'] is None or team.rosterDict['db2'] is None:
                    openPosList.append(FloosPlayer.Position.DB.value)
                if team.rosterDict['lb'] is None:
                    openPosList.append(FloosPlayer.Position.LB.value)
                if team.rosterDict['dl'] is None:
                    openPosList.append(FloosPlayer.Position.DL.value)
                if team.rosterDict['de'] is None:
                    openPosList.append(FloosPlayer.Position.DE.value)
                z = choice(openPosList)

                if z == FloosPlayer.Position.QB.value:
                    if team.gmScore >= len(draftQbList):
                        i = len(draftQbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftQbList.pop(randint(0,i))
                    team.rosterDict['qb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.RB.value:
                    if team.gmScore >= len(draftRbList):
                        i = len(draftRbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftRbList.pop(randint(0,i))
                    team.rosterDict['rb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.WR.value:
                    if team.gmScore >= len(draftWrList):
                        i = len(draftWrList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftWrList.pop(randint(0,i))
                    if team.rosterDict['wr1'] is None:
                        team.rosterDict['wr1'] = selectedPlayer
                    elif team.rosterDict['wr2'] is None:
                        team.rosterDict['wr2'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.TE.value:
                    if team.gmScore >= len(draftTeList):
                        i = len(draftTeList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftTeList.pop(randint(0,i))
                    team.rosterDict['te'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.K.value:
                    if team.gmScore >= len(draftKList):
                        i = len(draftKList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftKList.pop(randint(0,i))
                    team.rosterDict['k'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.DB.value:
                    if team.gmScore >= len(draftDbList):
                        i = len(draftDbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftDbList.pop(randint(0,i))
                    if team.rosterDict['db1'] is None:
                        team.rosterDict['db1'] = selectedPlayer
                    elif team.rosterDict['db2'] is None:
                        team.rosterDict['db2'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.LB.value:
                    if team.gmScore >= len(draftLbList):
                        i = len(draftLbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftLbList.pop(randint(0,i))
                    team.rosterDict['lb'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.DL.value:
                    if team.gmScore >= len(draftDlList):
                        i = len(draftDlList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftDlList.pop(randint(0,i))
                    team.rosterDict['dl'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)
                elif z == FloosPlayer.Position.DE.value:
                    if team.gmScore >= len(draftDeList):
                        i = len(draftDeList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = draftDeList.pop(randint(0,i))
                    team.rosterDict['de'] = selectedPlayer
                    playerDraftList.remove(selectedPlayer)

            selectedPlayer.team = team
            selectedPlayer.term = getPlayerTerm(selectedPlayer.playerTier)
            selectedPlayer.termRemaining = selectedPlayer.term
            selectedPlayer.seasonStatsDict['team'] = selectedPlayer.team.name

            #assign player number
            team.assignPlayerNumber(selectedPlayer)
            team.playerCap += selectedPlayer.capHit

        draftOrderList.reverse()
                
    for player in draftQbList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftRbList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftWrList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftTeList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftKList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftDbList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftLbList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftDlList:
        player.team = 'Free Agent'
        freeAgentList.append(player)
    for player in draftDeList:
        player.team = 'Free Agent'
        freeAgentList.append(player)

def savePlayerData():
    playerDict = {}
    tempPlayerDict = {}
    for x in range(len(activePlayerList)):
        key = 'Player {}'.format(x + 1)
        newDict = tempPlayerDict.copy()
        newDict['name'] = activePlayerList[x].name
        newDict['id'] = activePlayerList[x].id
        newDict['currentNumber'] = activePlayerList[x].currentNumber
        newDict['preferredNumber'] = activePlayerList[x].preferredNumber
        newDict['tier'] = activePlayerList[x].playerTier.name
        newDict['team'] = activePlayerList[x].team
        newDict['position'] = activePlayerList[x].position
        newDict['seasonsPlayed'] = activePlayerList[x].seasonsPlayed
        newDict['term'] = activePlayerList[x].term
        newDict['termRemaining'] = activePlayerList[x].termRemaining
        newDict['capHit'] = activePlayerList[x].capHit
        newDict['seasonPerformanceRating'] = activePlayerList[x].seasonPerformanceRating
        newDict['playerRating'] = activePlayerList[x].playerRating
        newDict['freeAgentYears'] = activePlayerList[x].freeAgentYears
        newDict['serviceTime'] = activePlayerList[x].serviceTime.name
        newDict['attributes'] = activePlayerList[x].attributes
        newDict['careerStats'] = activePlayerList[x].careerStatsDict

        archiveDict = {}
        y = 0
        for item in activePlayerList[x].seasonStatsArchive:
            y += 1
            archiveDict[y] = item

        newDict['seasonStatsArchive'] = archiveDict
        playerDict[key] = newDict

    dict = FloosMethods._prepare_for_serialization(playerDict)
    jsonFile = open("data/playerData.json", "w+") 
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()

    
def getPlayers(_config):

    if os.path.exists("data/playerData.json"):
        with open('data/playerData.json') as jsonFile:
            playerData = json.load(jsonFile)
            for x in playerData:
                player = playerData[x]
                if player['position'] == 'QB':
                    newPlayer = FloosPlayer.PlayerQB()
                    activeQbList.append(newPlayer)
                elif player['position'] == 'RB':
                    newPlayer = FloosPlayer.PlayerRB()
                    activeRbList.append(newPlayer)
                elif player['position'] == 'WR':
                    newPlayer = FloosPlayer.PlayerWR()
                    activeWrList.append(newPlayer)
                elif player['position'] == 'TE':
                    newPlayer = FloosPlayer.PlayerTE()
                    activeTeList.append(newPlayer)
                elif player['position'] == 'K':
                    newPlayer = FloosPlayer.PlayerK()
                    activeKList.append(newPlayer)
                elif player['position'] == 'DB':
                    newPlayer = FloosPlayer.PlayerDB()
                    activeDbList.append(newPlayer)
                elif player['position'] == 'LB':
                    newPlayer = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.LB)
                    activeLbList.append(newPlayer)
                elif player['position'] == 'DE':
                    newPlayer = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DE)
                    activeDeList.append(newPlayer)
                elif player['position'] == 'DL':
                    newPlayer = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DL)
                    activeDlList.append(newPlayer)

                if player['serviceTime'] == 'Rookie':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Rookie
                elif player['serviceTime'] == 'Veteran1':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Veteran1
                elif player['serviceTime'] == 'Veteran2':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Veteran2
                elif player['serviceTime'] == 'Veteran3':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Veteran3
                elif player['serviceTime'] == 'Retired':
                    newPlayer.serviceTime = FloosPlayer.PlayerServiceTime.Retired

                newPlayer.name = player['name']
                newPlayer.id = player['id']
                newPlayer.team = player['team']
                newPlayer.term = player['term']
                newPlayer.currentNumber = player['currentNumber']
                newPlayer.preferredNumber = player['prefferedNumber']
                newPlayer.termRemaining = player['termRemaining']
                newPlayer.capHit = player['capHit']
                newPlayer.seasonsPlayed = player['seasonsPlayed']
                newPlayer.playerRating = player['playerRating']
                newPlayer.freeAgentYears = player['freeAgentYears']
                newPlayer.seasonPerformanceRating = player['seasonPerformanceRating']
                newPlayer.attributes.overallRating = player['attributes']['overallRating']
                newPlayer.attributes.skillRating = player['attributes']['skillRating']
                newPlayer.attributes.speed = player['attributes']['speed']
                newPlayer.attributes.hands = player['attributes']['hands']
                newPlayer.attributes.agility = player['attributes']['agility']
                newPlayer.attributes.power = player['attributes']['power']
                newPlayer.attributes.armStrength = player['attributes']['armStrength']
                newPlayer.attributes.accuracy = player['attributes']['accuracy']
                newPlayer.attributes.legStrength = player['attributes']['legStrength']

                newPlayer.attributes.potentialSkillRating = player['attributes']['potentialSkillRating']

                if newPlayer.position is FloosPlayer.Position.QB:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialArmStrength']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialAccuracy']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.RB or isinstance(newPlayer, FloosPlayer.PlayerDefBasic):
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialSpeed']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialPower']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.WR or newPlayer.position is FloosPlayer.Position.DB:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialSpeed']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialHands']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.TE:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialPower']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialHands']
                    newPlayer.attributes.potentialAgility = player['attributes']['potentialAgility']
                elif newPlayer.position is FloosPlayer.Position.K:
                    newPlayer.attributes.potentialArmStrength = player['attributes']['potentialLegStrength']
                    newPlayer.attributes.potentialAccuracy = player['attributes']['potentialAccuracy']


                newPlayer.attributes.confidenceModifier = player['attributes']['confidence']
                newPlayer.attributes.determinationModifier = player['attributes']['determination']
                newPlayer.attributes.discipline = player['attributes']['discipline']
                newPlayer.attributes.focus = player['attributes']['focus']
                newPlayer.attributes.instinct = player['attributes']['instinct']
                newPlayer.attributes.creativity = player['attributes']['creativity']
                newPlayer.attributes.luckModifier = player['attributes']['luck']
                newPlayer.attributes.attitude = player['attributes']['attitude']
                newPlayer.attributes.playMakingAbility = player['attributes']['playMakingAbility']
                newPlayer.attributes.xFactor = player['attributes']['xFactor']

                newPlayer.careerStatsDict = player['careerStats']

                statArchive: dict = player['seasonStatsArchive']

                for k,v in statArchive.items():
                    index = int(k) - 1
                    newPlayer.seasonStatsArchive.insert(index, v)

                activePlayerList.append(newPlayer)

        jsonFile.close()
        getUnusedNames()

    else:
        numOfPlayers = 264
        id = 1
        for x in _config['players']:
            unusedNamesList.append(x)
        for x in range(numOfPlayers):
            player = None
            y = x%11
            if y == 0:
                player = FloosPlayer.PlayerQB()
                activeQbList.append(player)
            elif y == 1:
                player = FloosPlayer.PlayerRB()
                activeRbList.append(player)
            elif y == 2:
                player = FloosPlayer.PlayerWR()
                activeWrList.append(player)
            elif y == 3:
                player = FloosPlayer.PlayerTE()
                activeTeList.append(player)
            elif y == 4:
                player = FloosPlayer.PlayerK()
                activeKList.append(player)
            elif y == 5:
                player = FloosPlayer.PlayerWR()
                activeWrList.append(player)
            elif y == 6:
                player = FloosPlayer.PlayerDB()
                activeDbList.append(player)
            elif y == 7:
                player = FloosPlayer.PlayerDB()
                activeDbList.append(player)
            elif y == 8:
                player = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.LB)
                activeLbList.append(player)
            elif y == 9:
                player = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DE)
                activeDeList.append(player)
            elif y == 10:
                player = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DL)
                activeDlList.append(player)
            player.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
            player.id = id
            activePlayerList.append(player)
            id += 1
        saveUnusedNames()

    sortPlayers()


def getTeams(_config):

    if os.path.exists("data/teamData.json"):
        with open('data/teamData.json') as jsonFile:
            teamData = json.load(jsonFile)
            for x in teamData:
                team = teamData[x]
                newTeam = FloosTeam.Team(team['name'])
                newTeam.id = team['id']
                newTeam.city = team['city']
                newTeam.abbr = team['abbr']
                newTeam.color = team['color']
                newTeam.offenseRating = team['offenseRating']
                newTeam.runDefenseRating = team['runDefenseRating']
                newTeam.passDefenseRating = team['passDefenseRating']
                newTeam.defenseRating = team['defenseRating']
                newTeam.gmScore = team['gmScore']
                newTeam.defenseTier = team['defenseTier']
                newTeam.defenseSeasonPerformanceRating = team['defenseSeasonPerformanceRating']
                newTeam.overallRating = team['overallRating']
                newTeam.allTimeTeamStats = team['allTimeTeamStats']
                newTeam.leagueChampionships = team['leagueChampionships']
                newTeam.divisionChampionships = team['divisionChampionships']
                newTeam.regularSeasonChampions = team['regularSeasonChampions']
                newTeam.playoffAppearances = team['playoffAppearances']
                if 'rosterHistory' in team:
                    newTeam.rosterHistory = team['rosterHistory']

                teamRoster = team['roster']
                for pos, player in teamRoster.items():
                    for z in activePlayerList:
                        z:FloosPlayer.Player
                        if z.name == player['name']:
                            newTeam.rosterDict[pos] = z
                            newTeam.playerCap += z.capHit
                            newTeam.playerNumbersList.append(player['currentNumber'])
                            break

                teamList.append(newTeam)

    else:
        id = 1
        for x in _config['teams']:
            team = FloosTeam.Team(x['name'])
            team.city = x['city']
            team.abbr = x['abbr']
            team.color = x['color']
            #team.color = colorList.pop(randint(0,len(colorList)-1))
            team.id = id
            teamList.append(team)
            id += 1

def getDivisons(_config):

    if os.path.exists("data/divisionData.json"):
        with open('data/divisionData.json') as jsonFile:
            divisionData = json.load(jsonFile)
            for x in divisionData:
                division = Division(x)
                jteamList = divisionData[x]
                for team in jteamList:
                    for y in teamList:
                        if y.name == team:
                            division.teamList.append(y)
                            break
                divisionList.append(division)


    else:
        for x in _config['divisions']:
            division = Division(x)
            divisionList.append(division)

def initTeams():
    dict = {}
    jsonFile = open("data/teamData.json", "w+")
    for team in teamList:
        team: FloosTeam.Team
        team.setupTeam()
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['abbr'] = team.abbr
        teamDict['color'] = team.color
        teamDict['id'] = team.id
        teamDict['offenseRating'] = team.offenseRating
        teamDict['runDefenseRating'] = team.runDefenseRating
        teamDict['passDefenseRating'] = team.passDefenseRating
        teamDict['defenseRating'] = team.defenseRating
        #teamDict['defenseLuck'] = team.defenseLuck
        #teamDict['defenseDiscipline'] = team.defenseDiscipline
        teamDict['overallRating'] = team.overallRating
        teamDict['allTimeTeamStats'] = team.allTimeTeamStats
        teamDict['leagueChampionships'] = team.leagueChampionships
        teamDict['regularSeasonChampions'] = team.regularSeasonChampions
        teamDict['divisionChampionships'] = team.divisionChampionships
        teamDict['playoffAppearances'] = team.playoffAppearances
        teamDict['gmScore'] = team.gmScore
        teamDict['defenseTier'] = team.defenseTier
        teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating


        rosterDict = {}
        
        for pos, player in team.rosterDict.items():
            player:FloosPlayer.Player
            playerDict = {}
            playerDict['name'] = player.name
            playerDict['id'] = player.id
            playerDict['tier'] = player.playerTier.name
            playerDict['overallRating'] = player.attributes.overallRating
            playerDict['term'] = player.term
            playerDict['termRemaining'] = player.termRemaining
            playerDict['seasonsPlayed'] = player.seasonsPlayed
            playerDict['careerStatsDict'] = player.careerStatsDict
            if player.team is not team:
                player.team = team
            rosterDict[pos] = playerDict

        teamDict['roster'] = rosterDict

        dict[team.id] = teamDict
    sortDefenses()
    jsonFile.write(json.dumps(dict, indent=4))
    jsonFile.close()


def initPlayers():
    pass

def sortPlayers():
    ratingList = []
    for player in activePlayerList:
        player: FloosPlayer.Player
        ratingList.append(player.playerRating)
    tierS = np.percentile(ratingList, 96)
    tierA = np.percentile(ratingList, 85)
    tierB = np.percentile(ratingList, 40)
    tierC = np.percentile(ratingList, 10)
    for player in activePlayerList:
        if player.playerRating >= tierS:
            player.playerTier = FloosPlayer.PlayerTier.TierS
        elif player.playerRating >= tierA:
            player.playerTier = FloosPlayer.PlayerTier.TierA
        elif player.playerRating >= tierB:
            player.playerTier = FloosPlayer.PlayerTier.TierB
        elif player.playerRating >= tierC:
            player.playerTier = FloosPlayer.PlayerTier.TierC
        else:
            player.playerTier = FloosPlayer.PlayerTier.TierD
        if player.team is None or player.team == 'Free Agent':
            player.capHit = player.playerTier.value


def sortDefenses():
    teamDefenseRatingList = []
    for team in teamList:
        team: FloosTeam.Team
        teamDefenseRatingList.append(team.defenseOverallRating)
    
    tier5perc = np.percentile(teamDefenseRatingList, 95)
    tier4perc = np.percentile(teamDefenseRatingList, 80)
    tier3perc = np.percentile(teamDefenseRatingList, 30)
    tier2perc = np.percentile(teamDefenseRatingList, 10)

    for team in teamList:
        team: FloosTeam.Team
        if team.defenseOverallRating >= tier5perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierS.value
        elif team.defenseOverallRating >= tier4perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierA.value
        elif team.defenseOverallRating >= tier3perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierB.value
        elif team.defenseOverallRating >= tier2perc:
            team.defenseTier = FloosPlayer.PlayerTier.TierC.value
        else:
            team.defenseTier = FloosPlayer.PlayerTier.TierD.value


        
def initDivisions():
    tempTeamList = teamList.copy()
    numOfDivisions = len(divisionList)
    y = 0
    while len(tempTeamList) > 0:
        x = randint(0,len(tempTeamList)-1)
        # if len(tempTeamList) % 2 == 0:
        #     divisionList[0].teamList.append(tempTeamList[x])
        # else:
        #     divisionList[1].teamList.append(tempTeamList[x])
        divisionList[y].teamList.append(tempTeamList[x])
        y += 1
        if y == numOfDivisions:
            y = 0
        tempTeamList.remove(tempTeamList[x])
    for division in divisionList:
        for team in division.teamList:
            team.division = division.name

async def offseason():
    activeSeason.currentWeek = 'Offseason'
    activeSeason.currentWeekText = 'Offseason'
    newPlayerCount = 6
    freeAgencyDict = {}
    for player in freeAgentList:
        player: FloosPlayer.Player
        player.freeAgentYears += 1
        retirePlayerBool = False

        if player.freeAgentYears > 3:
            x = randint(1,10)
            if player.playerTier.value == 1 and x > 3:
                retirePlayerBool = True
            elif player.playerTier.value == 2 and x > 5:
                retirePlayerBool = True
            elif x > 8:
                retirePlayerBool = True

            if retirePlayerBool: 
                player.team = 'Retired'
                player.serviceTime = FloosPlayer.PlayerServiceTime.Retired
                retiredPlayersList.append(player)
                newlyRetiredPlayersList.append(player)
                freeAgentList.remove(player)
                activePlayerList.remove(player)
                if player.position is FloosPlayer.Position.QB:
                    activeQbList.remove(player)
                elif player.position is FloosPlayer.Position.RB:
                    activeRbList.remove(player)
                elif player.position is FloosPlayer.Position.WR:
                    activeWrList.remove(player)
                elif player.position is FloosPlayer.Position.TE:
                    activeTeList.remove(player)
                elif player.position is FloosPlayer.Position.K:
                    activeKList.remove(player)
                elif player.position is FloosPlayer.Position.DB:
                    activeDbList.remove(player)
                elif player.position is FloosPlayer.Position.LB:
                    activeLbList.remove(player)
                elif player.position is FloosPlayer.Position.DL:
                    activeDlList.remove(player)
                elif player.position is FloosPlayer.Position.DE:
                    activeDeList.remove(player)
                

                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has retired after {} seasons'.format(player.name, player.seasonsPlayed)}})

                name = player.name
                if name.endswith('Jr.'):
                    name = name.replace('Jr.', 'III')
                elif name.endswith('IV'):
                    name = name.replace('IV', 'V')
                elif name.endswith('VIII'):
                    name = name.replace('VIII', 'IX')
                elif name.endswith('IX'):
                    name = name.replace('IX', 'X')
                elif name.endswith('III'):
                    name = name.replace('III', 'IV')
                elif name.endswith('V') or name.endswith('X'):
                    name += 'I'
                else:
                    name += ' Jr.'
                unusedNamesList.append(name)


    for team in teamList:
        team.cutsAvailable = 2

        for k,v in team.rosterDict.items():
            v: FloosPlayer.Player
            if v.seasonsPlayed >= 1 and v.seasonsPlayed < 4:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Veteran1
            elif v.seasonsPlayed >= 4 and v.seasonsPlayed < 7:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Veteran2
            elif v.seasonsPlayed >= 7 and v.seasonsPlayed <= 10:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Veteran3
            else:
                v.serviceTime = FloosPlayer.PlayerServiceTime.Veteran4

            retirePlayerBool = None
            v.termRemaining -= 1
            if v.seasonsPlayed > v.attributes.longevity:
                if v.termRemaining == 0:
                    if v.seasonsPlayed > 15:
                        x = randint(1,100)
                        if x > 10:
                            retirePlayerBool = True
                    elif v.seasonsPlayed > 10:
                        x = randint(1,100)
                        if x > 35:
                            retirePlayerBool = True
                    elif v.seasonsPlayed >= 7:
                        x = randint(1,100)
                        if x > 95:
                            retirePlayerBool = True
                    else:
                        retirePlayerBool = False
                else:
                    if v.seasonsPlayed > 15:
                        x = randint(1,100)
                        if x > 30:
                            retirePlayerBool = True
                    elif v.seasonsPlayed > 10:
                        x = randint(1,100)
                        if x > 75:
                            retirePlayerBool = True
                    elif v.seasonsPlayed >= 7:
                        x = randint(1,100)
                        if x > 90:
                            retirePlayerBool = True
                    else:
                        retirePlayerBool = False

            if retirePlayerBool:
                v.previousTeam = team.name
                v.seasonPerformanceRating = 0
                team.playerCap -= v.capHit
                team.playerNumbersList.remove(v.currentNumber)
                v.team = 'Retired'
                v.serviceTime = FloosPlayer.PlayerServiceTime.Retired
                retiredPlayersList.append(v)
                newlyRetiredPlayersList.append(v)
                activePlayerList.remove(v)
                if v.position is FloosPlayer.Position.QB:
                    activeQbList.remove(v)
                elif v.position is FloosPlayer.Position.RB:
                    activeRbList.remove(v)
                elif v.position is FloosPlayer.Position.WR:
                    activeWrList.remove(v)
                elif v.position is FloosPlayer.Position.TE:
                    activeTeList.remove(v)
                elif v.position is FloosPlayer.Position.K:
                    activeKList.remove(v)
                elif v.position is FloosPlayer.Position.DB:
                    activeDbList.remove(v)
                elif v.position is FloosPlayer.Position.LB:
                    activeLbList.remove(v)
                elif v.position is FloosPlayer.Position.DL:
                    activeDlList.remove(v)
                elif v.position is FloosPlayer.Position.DE:
                    activeDeList.remove(v)
                team.rosterDict[k] = None
                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has retired after {} seasons'.format(player.name, player.seasonsPlayed)}})
                name = v.name
                if name.endswith('Jr.'):
                    name = name.replace('Jr.', 'III')
                elif name.endswith('IV'):
                    name = name.replace('IV', 'V')
                elif name.endswith('VIII'):
                    name = name.replace('VIII', 'IX')
                elif name.endswith('IX'):
                    name = name.replace('IX', 'X')
                elif name.endswith('III'):
                    name = name.replace('III', 'IV')
                elif name.endswith('V') or name.endswith('X'):
                    name += 'I'
                else:
                    name += ' Jr.'
                unusedNamesList.append(name)
            elif v.termRemaining == 0:
                v.previousTeam = team.name
                team.playerCap -= v.capHit
                team.playerNumbersList.remove(v.currentNumber)
                v.team = 'Free Agent'
                freeAgentList.append(v)
                team.rosterDict[k] = None

                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has become a Free Agent'.format(v.name)}})

                    
    for player in activePlayerList:
        if player.team is None:
            pass
        player.offseasonTraining()
        player.seasonPerformanceRating = 0


    for player in newlyRetiredPlayersList:
        player: FloosPlayer.Player
        newPlayer: FloosPlayer.Player = None
        if player.position is FloosPlayer.Position.QB:
            newPlayer = FloosPlayer.PlayerQB()
            activeQbList.append(newPlayer)
        elif player.position is FloosPlayer.Position.RB:
            newPlayer = FloosPlayer.PlayerRB()
            activeRbList.append(newPlayer)
        elif player.position is FloosPlayer.Position.WR:
            newPlayer = FloosPlayer.PlayerWR()
            activeWrList.append(newPlayer)
        elif player.position is FloosPlayer.Position.TE:
            newPlayer = FloosPlayer.PlayerTE()
            activeTeList.append(newPlayer)
        elif player.position is FloosPlayer.Position.K:
            newPlayer = FloosPlayer.PlayerK()
            activeKList.append(newPlayer)
        elif player.position is FloosPlayer.Position.DB:
            newPlayer = FloosPlayer.PlayerDB()
            activeDbList.append(newPlayer)
        elif player.position is FloosPlayer.Position.LB:
            newPlayer = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.LB)
            activeLbList.append(newPlayer)
        elif player.position is FloosPlayer.Position.DE:
            newPlayer = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DE)
            activeDeList.append(newPlayer)
        elif player.position is FloosPlayer.Position.DL:
            newPlayer = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DL)
            activeDlList.append(newPlayer)
        
        newPlayer.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
        newPlayer.team = 'Free Agent'
        newPlayer.id = (len(activePlayerList) + len(retiredPlayersList) + 1)
        activePlayerList.append(newPlayer)
        freeAgentList.append(newPlayer)

    if newPlayerCount > len(newlyRetiredPlayersList):
        posList = [FloosPlayer.Position.QB, FloosPlayer.Position.RB, FloosPlayer.Position.WR, FloosPlayer.Position.TE, FloosPlayer.Position.K, FloosPlayer.Position.DB, FloosPlayer.Position.LB, FloosPlayer.Position.DE, FloosPlayer.Position.DL]
        for x in range(newPlayerCount - len(newlyRetiredPlayersList)):
            r = randint(0, len(posList)-1)
            pos = posList.pop(r)
            player = None
            if pos is FloosPlayer.Position.QB:
                player = FloosPlayer.PlayerQB()
                activeQbList.append(player)
            if pos is FloosPlayer.Position.RB:
                player = FloosPlayer.PlayerRB()
                activeRbList.append(player)
            if pos is FloosPlayer.Position.WR:
                player = FloosPlayer.PlayerWR()
                activeWrList.append(player)
            if pos is FloosPlayer.Position.TE:
                player = FloosPlayer.PlayerTE()
                activeTeList.append(player)
            if pos is FloosPlayer.Position.K:
                player = FloosPlayer.PlayerK()
                activeKList.append(player)
            if pos is FloosPlayer.Position.DB:
                player = FloosPlayer.PlayerDB()
                activeDbList.append(player)
            if pos is FloosPlayer.Position.LB:
                player = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.LB)
                activeLbList.append(player)
            if pos is FloosPlayer.Position.DL:
                player = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DL)
                activeDlList.append(player)
            if pos is FloosPlayer.Position.DE:
                player = FloosPlayer.PlayerDefBasic(FloosPlayer.Position.DE)
                activeDeList.append(player)

            player.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
            player.team = 'Free Agent'
            player.id = (len(activePlayerList) + len(retiredPlayersList) + 1)
            activePlayerList.append(player)
            freeAgentList.append(player)

    saveUnusedNames()
    sortPlayers()

    freeAgentQbList : list[FloosPlayer.Player] = []
    freeAgentRbList : list[FloosPlayer.Player] = []
    freeAgentWrList : list[FloosPlayer.Player] = []
    freeAgentTeList : list[FloosPlayer.Player] = []
    freeAgentKList : list[FloosPlayer.Player] = []
    freeAgentDbList : list[FloosPlayer.Player] = []
    freeAgentLbList : list[FloosPlayer.Player] = []
    freeAgentDlList : list[FloosPlayer.Player] = []
    freeAgentDeList : list[FloosPlayer.Player] = []

    for player in freeAgentList:
        if player.position.value == 1:
            freeAgentQbList.append(player)
        elif player.position.value == 2:
            freeAgentRbList.append(player)
        elif player.position.value == 3:
            freeAgentWrList.append(player)
        elif player.position.value == 4:
            freeAgentTeList.append(player)
        elif player.position.value == 5:
            freeAgentKList.append(player)
        elif player.position.value == 6:
            freeAgentDbList.append(player)
        elif player.position.value == 7:
            freeAgentLbList.append(player)
        elif player.position.value == 8:
            freeAgentDlList.append(player)
        elif player.position.value == 9:
            freeAgentDeList.append(player)

    list.sort(freeAgentQbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentRbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentWrList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentTeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentKList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentDbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentLbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentDlList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentDeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentList, key=lambda player: player.attributes.skillRating, reverse=True)

    teamsComplete = 0
    while teamsComplete < len(teamList):
        teamsComplete = 0
        team: FloosTeam.Team
        for team in freeAgencyOrder:
            selectedPlayer = None
            openRosterPosList = []
            if team.faComplete:
                teamsComplete += 1
                continue
                
            await asyncio.sleep(2)

            if team.cutsAvailable > 0:
                cutPlayer:FloosPlayer.Player = None
                newPlayer:FloosPlayer.Player = None
                eligiblePlayersToCutList = []
                for k,v in team.rosterDict.items():
                    v:FloosPlayer.Player
                    if v is not None and v.playerTier.value <= 3:
                        if v.position is FloosPlayer.Position.QB and len(freeAgentQbList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.RB and len(freeAgentRbList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.WR and len(freeAgentWrList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.TE and len(freeAgentTeList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.K and len(freeAgentKList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.DB and len(freeAgentDbList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.LB and len(freeAgentLbList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.DE and len(freeAgentDeList) == 0:
                            eligiblePlayersToCutList.append(k)
                        elif v.position is FloosPlayer.Position.DL and len(freeAgentDlList) == 0:
                            eligiblePlayersToCutList.append(k)
                while len(eligiblePlayersToCutList) > 0: 
                    pos = choice(eligiblePlayersToCutList)
                    currentPlayer:FloosPlayer.Player = team.rosterDict[pos]
                    compPlayer:FloosPlayer.Player = None

                    if pos == 'qb' and len(freeAgentQbList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'rb' and len(freeAgentRbList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'wr1' and len(freeAgentWrList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'wr2' and len(freeAgentWrList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'te' and len(freeAgentTeList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'k' and len(freeAgentKList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'db1' and len(freeAgentDbList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'db2' and len(freeAgentDbList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'lb' and len(freeAgentLbList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'de' and len(freeAgentDeList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None
                    if pos == 'dl' and len(freeAgentDlList) == 0:
                        eligiblePlayersToCutList.remove(pos)
                        pos = None

                    if pos is None and len(eligiblePlayersToCutList) > 0:
                        pos = choice(eligiblePlayersToCutList)
                    else:
                        continue

                    if pos == 'qb':
                        if team.gmScore >= len(freeAgentQbList):
                            i = len(freeAgentQbList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentQbList[randint(0,i)]
                    elif pos == 'rb':
                        if team.gmScore >= len(freeAgentRbList):
                            i = len(freeAgentRbList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentRbList[randint(0,i)]
                    elif pos == 'wr1' or pos == 'wr2':
                        if team.gmScore >= len(freeAgentWrList):
                            i = len(freeAgentWrList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentWrList[randint(0,i)]
                    elif pos == 'te':
                        if team.gmScore >= len(freeAgentTeList):
                            i = len(freeAgentTeList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentTeList[randint(0,i)]
                    elif pos == 'k':
                        if team.gmScore >= len(freeAgentKList):
                            i = len(freeAgentKList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentKList[randint(0,i)]
                    elif pos == 'db1' or pos == 'db2':
                        if team.gmScore >= len(freeAgentDbList):
                            i = len(freeAgentDbList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentDbList[randint(0,i)]
                    elif pos == 'lb':
                        if team.gmScore >= len(freeAgentLbList):
                            i = len(freeAgentLbList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentLbList[randint(0,i)]
                    elif pos == 'de':
                        if team.gmScore >= len(freeAgentDeList):
                            i = len(freeAgentDeList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentDeList[randint(0,i)]
                    elif pos == 'dl':
                        if team.gmScore >= len(freeAgentDlList):
                            i = len(freeAgentDlList) - 1
                        else:
                            i = team.gmScore    
                        compPlayer = freeAgentDlList[randint(0,i)]

                    if (compPlayer.playerTier.value - 1) > currentPlayer.playerTier.value:
                        cutPlayer = currentPlayer
                        newPlayer = compPlayer

                        team.rosterDict[pos] = newPlayer
                        newPlayer.term = getPlayerTerm(newPlayer.playerTier)
                        newPlayer.termRemaining = newPlayer.term
                        newPlayer.team = team
                        newPlayer.freeAgentYears = 0
                        cutPlayer.termRemaining = 0
                        cutPlayer.team = 'Free Agent'
                        cutPlayer.previousTeam = team.name
                        team.playerNumbersList.remove(cutPlayer.currentNumber)
                        team.assignPlayerNumber(newPlayer)
                        team.playerCap -= cutPlayer.capHit
                        team.playerCap += newPlayer.capHit
                        freeAgentList.append(cutPlayer)
                        freeAgentList.remove(newPlayer)
                        activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has cut {}'.format(team.name, cutPlayer.name)}})
                        activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, newPlayer.name, newPlayer.position.name, newPlayer.term)}})
                        
                        if newPlayer.position is FloosPlayer.Position.QB:
                            freeAgentQbList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.RB:
                            freeAgentRbList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.WR:
                            freeAgentWrList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.TE:
                            freeAgentTeList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.K:
                            freeAgentKList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.DB:
                            freeAgentDbList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.LB:
                            freeAgentLbList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.DE:
                            freeAgentDeList.remove(newPlayer)
                        elif newPlayer.position is FloosPlayer.Position.DL:
                            freeAgentDlList.remove(newPlayer)

                        if cutPlayer.position is FloosPlayer.Position.QB:
                            freeAgentQbList.append(cutPlayer)
                            list.sort(freeAgentQbList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.RB:
                            freeAgentRbList.append(cutPlayer)
                            list.sort(freeAgentRbList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.WR:
                            freeAgentWrList.append(cutPlayer)
                            list.sort(freeAgentWrList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.TE:
                            freeAgentTeList.append(cutPlayer)
                            list.sort(freeAgentTeList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.K:
                            freeAgentKList.append(cutPlayer)
                            list.sort(freeAgentKList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.DB:
                            freeAgentDbList.append(cutPlayer)
                            list.sort(freeAgentDbList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.LB:
                            freeAgentLbList.append(cutPlayer)
                            list.sort(freeAgentLbList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.DE:
                            freeAgentDeList.append(cutPlayer)
                            list.sort(freeAgentDeList, key=lambda player: player.attributes.skillRating, reverse=True)
                        elif cutPlayer.position is FloosPlayer.Position.DL:
                            freeAgentDlList.append(cutPlayer)
                            list.sort(freeAgentDlList, key=lambda player: player.attributes.skillRating, reverse=True)

                        break

                    else:
                        eligiblePlayersToCutList.remove(pos)

                team.cutsAvailable -= 1
                if cutPlayer is not None:
                    continue


            for k,v in team.rosterDict.items():
                if v is None:
                    openRosterPosList.append(k)
            if len(openRosterPosList) > 0:
                pos = choice(openRosterPosList)
                if pos == 'qb':
                    if team.gmScore >= len(freeAgentQbList):
                        i = len(freeAgentQbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentQbList.pop(randint(0,i))
                elif pos == 'rb':
                    if team.gmScore >= len(freeAgentRbList):
                        i = len(freeAgentRbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentRbList.pop(randint(0,i))
                elif pos == 'wr1':
                    if team.gmScore >= len(freeAgentWrList):
                        i = len(freeAgentWrList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentWrList.pop(randint(0,i))
                elif pos == 'wr2':
                    if team.gmScore >= len(freeAgentWrList):
                        i = len(freeAgentWrList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentWrList.pop(randint(0,i))
                elif pos == 'te':
                    if team.gmScore >= len(freeAgentTeList):
                        i = len(freeAgentTeList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentTeList.pop(randint(0,i))
                elif pos == 'k':
                    if team.gmScore >= len(freeAgentKList):
                        i = len(freeAgentKList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentKList.pop(randint(0,i))
                elif pos == 'db1':
                    if team.gmScore >= len(freeAgentDbList):
                        i = len(freeAgentDbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentDbList.pop(randint(0,i))
                elif pos == 'db2':
                    if team.gmScore >= len(freeAgentDbList):
                        i = len(freeAgentDbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentDbList.pop(randint(0,i))
                elif pos == 'lb':
                    if team.gmScore >= len(freeAgentLbList):
                        i = len(freeAgentLbList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentLbList.pop(randint(0,i))
                elif pos == 'dl':
                    if team.gmScore >= len(freeAgentDlList):
                        i = len(freeAgentDlList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentDlList.pop(randint(0,i))
                elif pos == 'de':
                    if team.gmScore >= len(freeAgentDeList):
                        i = len(freeAgentDeList) - 1
                    else:
                        i = team.gmScore
                    selectedPlayer = freeAgentDeList.pop(randint(0,i))

                freeAgentList.remove(selectedPlayer)
                selectedPlayer.team = team
                team.playerCap += selectedPlayer.capHit
                team.rosterDict[pos] = selectedPlayer
                team.assignPlayerNumber(selectedPlayer)
                selectedPlayer.term = getPlayerTerm(selectedPlayer.playerTier)
                selectedPlayer.termRemaining = selectedPlayer.term
                selectedPlayer.freeAgentYears = 0
                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} signed {} ({}) for {} season(s)'.format(team.name, selectedPlayer.name, selectedPlayer.position.name, selectedPlayer.term)}})
                freeAgencyDict[team.name] = {'name': selectedPlayer.name, 'pos': selectedPlayer.position.name, 'rating': selectedPlayer.attributes.skillRating, 'tier': selectedPlayer.playerTier.value, 'term': selectedPlayer.term, 'previousTeam': selectedPlayer.previousTeam, 'roster': "Starting"}
                continue
            else:
                teamsComplete += 1
                team.faComplete = True
                continue
    for player in freeAgentList:
        player.team = 'Free Agent'

    freeAgencyHistoryDict['offseason {}'.format(seasonsPlayed)] = freeAgencyDict

    for team in teamList:
        team.faComplete = False
        team.updateDefense()
    sortDefenses()
    setNewingElo()
    inductHallOfFame()
    
def getPerformanceRating():
    qbStatsPassCompList = []
    qbStatsPassMissList = []
    qbStatsPassYardsList = []
    qbStatsTdsList = []
    qbStatsIntsList = []
    for qb in activeQbList:
        qb: FloosPlayer.PlayerQB
        if qb.seasonStatsDict['passing']['yards'] > 0:
            qbStatsPassCompList.append(qb.seasonStatsDict['passing']['compPerc'])
            qbStatsPassMissList.append(qb.seasonStatsDict['passing']['missedPass'])
            qbStatsPassYardsList.append(qb.seasonStatsDict['passing']['yards'])
            qbStatsTdsList.append(qb.seasonStatsDict['passing']['tds'])
            qbStatsIntsList.append(qb.seasonStatsDict['passing']['ints'])

    for qb in activeQbList:
        qb: FloosPlayer.PlayerQB
        if qb.seasonStatsDict['passing']['yards'] > 0:
            passCompPercRating = stats.percentileofscore(qbStatsPassCompList, qb.seasonStatsDict['passing']['compPerc'], 'rank')
            passMissesRating = 100 - stats.percentileofscore(qbStatsPassMissList, qb.seasonStatsDict['passing']['missedPass'], 'rank')
            passYardsRating = stats.percentileofscore(qbStatsPassYardsList, qb.seasonStatsDict['passing']['yards'], 'rank')
            tdsRating = stats.percentileofscore(qbStatsTdsList, qb.seasonStatsDict['passing']['tds'], 'rank')
            intsRating = 100 - stats.percentileofscore(qbStatsIntsList, qb.seasonStatsDict['passing']['ints'], 'rank')
            qb.seasonPerformanceRating = round(((passCompPercRating*.8)+(passYardsRating*1.2)+(tdsRating*1.2)+(intsRating*1)+(passMissesRating*.8))/5)

    rbStatsYprList = []
    rbStatsRunYardsList = []
    rbStatsTdsList = []
    rbStatsFumblesList = []
    for rb in activeRbList:
        rb: FloosPlayer.PlayerRB
        if rb.seasonStatsDict['rushing']['yards'] > 0:
            rbStatsYprList.append(rb.seasonStatsDict['rushing']['ypc'])
            rbStatsRunYardsList.append(rb.seasonStatsDict['rushing']['yards'])
            rbStatsTdsList.append(rb.seasonStatsDict['rushing']['tds'])
            rbStatsFumblesList.append(rb.seasonStatsDict['rushing']['fumblesLost'])

    for rb in activeRbList:
        rb: FloosPlayer.PlayerRB
        if rb.seasonStatsDict['rushing']['yards'] > 0:
            yprRating = stats.percentileofscore(rbStatsYprList, rb.seasonStatsDict['rushing']['ypc'], 'rank')
            runYardsRating = stats.percentileofscore(rbStatsRunYardsList, rb.seasonStatsDict['rushing']['yards'], 'rank')
            tdsRating = stats.percentileofscore(rbStatsTdsList, rb.seasonStatsDict['rushing']['tds'], 'rank')
            fumblesRating = 100 - stats.percentileofscore(rbStatsFumblesList, rb.seasonStatsDict['rushing']['fumblesLost'], 'rank')
            rb.seasonPerformanceRating = round(((yprRating*1)+(runYardsRating*1.2)+(tdsRating*1.2)+(fumblesRating*.6))/4)

    wrStatsReceptionsList = []
    wrStatsDropsList = []
    wrStatsRcvPercList = []
    wrStatsRcvYardsList = []
    wrStatsYACList = []
    wrStatsTdsList = []
    for wr in activeWrList:
        wr: FloosPlayer.PlayerWR
        if wr.seasonStatsDict['receiving']['receptions'] > 0:
            wrStatsReceptionsList.append(wr.seasonStatsDict['receiving']['receptions'])
            wrStatsDropsList.append(wr.seasonStatsDict['receiving']['drops'])
            wrStatsRcvPercList.append(wr.seasonStatsDict['receiving']['rcvPerc'])
            wrStatsRcvYardsList.append(wr.seasonStatsDict['receiving']['yards'])
            wrStatsYACList.append(wr.seasonStatsDict['receiving']['yac'])
            wrStatsTdsList.append(wr.seasonStatsDict['receiving']['tds'])

    for wr in activeWrList:
        wr: FloosPlayer.PlayerWR
        if wr.seasonStatsDict['receiving']['receptions'] > 0:
            receptionsRating = stats.percentileofscore(wrStatsReceptionsList, wr.seasonStatsDict['receiving']['receptions'], 'rank')
            dropsRating = 100 - stats.percentileofscore(wrStatsDropsList, wr.seasonStatsDict['receiving']['drops'], 'rank')
            rcvPercRating = stats.percentileofscore(wrStatsRcvPercList, wr.seasonStatsDict['receiving']['rcvPerc'], 'rank')
            rcvYardsRating = stats.percentileofscore(wrStatsRcvYardsList, wr.seasonStatsDict['receiving']['yards'], 'rank')
            yacRating = stats.percentileofscore(wrStatsYACList, wr.seasonStatsDict['receiving']['yac'], 'rank')
            tdsRating = stats.percentileofscore(wrStatsTdsList, wr.seasonStatsDict['receiving']['tds'], 'rank')
            wr.seasonPerformanceRating = round(((rcvPercRating*.4)+(rcvYardsRating*1.2)+(tdsRating*1.2)+(yacRating*1.2)+(receptionsRating*1)+(dropsRating*1))/6)

    teStatsReceptionsList = []
    teStatsDropsList = []
    teStatsRcvPercList = []
    teStatsRcvYardsList = []
    teStatsTdsList = []
    for te in activeTeList:
        te: FloosPlayer.PlayerTE
        if te.seasonStatsDict['receiving']['receptions'] > 0:
            teStatsReceptionsList.append(te.seasonStatsDict['receiving']['receptions'])
            teStatsDropsList.append(te.seasonStatsDict['receiving']['drops'])
            teStatsRcvPercList.append(te.seasonStatsDict['receiving']['rcvPerc'])
            teStatsRcvYardsList.append(te.seasonStatsDict['receiving']['yards'])
            teStatsTdsList.append(te.seasonStatsDict['receiving']['tds'])

    for te in activeTeList:
        te: FloosPlayer.PlayerTE
        if te.seasonStatsDict['receiving']['receptions'] > 0:
            receptionsRating = stats.percentileofscore(teStatsReceptionsList, te.seasonStatsDict['receiving']['receptions'], 'rank')
            dropsRating = 100 - stats.percentileofscore(teStatsDropsList, te.seasonStatsDict['receiving']['drops'], 'rank')
            rcvPercRating = stats.percentileofscore(teStatsRcvPercList, te.seasonStatsDict['receiving']['rcvPerc'], 'rank')
            rcvYardsRating = stats.percentileofscore(teStatsRcvYardsList, te.seasonStatsDict['receiving']['yards'], 'rank')
            tdsRating = stats.percentileofscore(teStatsTdsList, te.seasonStatsDict['receiving']['tds'], 'rank')
            te.seasonPerformanceRating = round(((rcvPercRating*.6)+(rcvYardsRating*1.2)+(tdsRating*1.2)+(receptionsRating*1)+(dropsRating*1))/5)

    kStatsFgPercList = []
    kStatsFgsList = []
    kStatsFgAvgList = []
    for k in activeKList:
        k: FloosPlayer.PlayerK
        if k.seasonStatsDict['kicking']['fgAtt'] > 0:
            kStatsFgPercList.append(k.seasonStatsDict['kicking']['fgPerc'])
            kStatsFgsList.append(k.seasonStatsDict['kicking']['fgs'])
            kStatsFgAvgList.append(k.seasonStatsDict['kicking']['fgAvg'])

    for k in activeKList:
        k: FloosPlayer.PlayerK
        if k.seasonStatsDict['kicking']['fgAtt'] > 0:
            fgPercRating = stats.percentileofscore(kStatsFgPercList, k.seasonStatsDict['kicking']['fgPerc'], 'rank')
            fgsRating = stats.percentileofscore(kStatsFgsList, k.seasonStatsDict['kicking']['fgs'], 'rank')
            fgAvgRating = stats.percentileofscore(kStatsFgAvgList, k.seasonStatsDict['kicking']['fgAvg'], 'rank')
            k.seasonPerformanceRating = round(((fgPercRating*1.3)+(fgsRating*.5)+(fgAvgRating*1.2))/3)

    dbStatsIntsList = []
    dbStatsPassDisList = []
    dbStatsPassDisPercList = []
    for db in activeDbList:
        db: FloosPlayer.PlayerDB
        if db.seasonStatsDict['defense']['passTargets'] > 0:
            dbStatsIntsList.append(db.seasonStatsDict['defense']['ints'])
            dbStatsPassDisList.append(db.seasonStatsDict['defense']['passDisruptions'])
            dbStatsPassDisPercList.append(db.seasonStatsDict['defense']['passDisPerc'])

    for db in activeDbList:
        db: FloosPlayer.PlayerDB
        if db.seasonStatsDict['defense']['passTargets'] > 0:
            intsRating = stats.percentileofscore(dbStatsIntsList, db.seasonStatsDict['defense']['ints'], 'rank')
            passDisRating = stats.percentileofscore(dbStatsPassDisList, db.seasonStatsDict['defense']['passDisruptions'], 'rank')
            passDisPercRating = stats.percentileofscore(dbStatsPassDisPercList, db.seasonStatsDict['defense']['passDisPerc'], 'rank')
            db.seasonPerformanceRating = round(((intsRating*1)+(passDisRating*.8)+(passDisPercRating*1.2))/3)

    lbStatsIntsList = []
    lbStatsPassDisList = []
    lbStatsPassDisPercList = []
    lbStatsFumRecList = []
    for lb in activeLbList:
        lb: FloosPlayer.PlayerDefBasic
        if lb.seasonStatsDict['defense']['passTargets'] > 0:
            lbStatsIntsList.append(lb.seasonStatsDict['defense']['ints'])
            lbStatsPassDisList.append(lb.seasonStatsDict['defense']['passDisruptions'])
            lbStatsPassDisPercList.append(lb.seasonStatsDict['defense']['passDisPerc'])
            lbStatsFumRecList.append(lb.seasonStatsDict['defense']['fumRec'])

    for lb in activeLbList:
        lb: FloosPlayer.PlayerDefBasic
        if lb.seasonStatsDict['defense']['passTargets'] > 0:
            intsRating = stats.percentileofscore(lbStatsIntsList, lb.seasonStatsDict['defense']['ints'], 'rank')
            passDisRating = stats.percentileofscore(lbStatsPassDisList, lb.seasonStatsDict['defense']['passDisruptions'], 'rank')
            passDisPercRating = stats.percentileofscore(lbStatsPassDisPercList, lb.seasonStatsDict['defense']['passDisPerc'], 'rank')
            fumRecRating = stats.percentileofscore(lbStatsFumRecList, lb.seasonStatsDict['defense']['fumRec'], 'rank')
            lb.seasonPerformanceRating = round(((intsRating*1)+(passDisRating*.8)+(passDisPercRating*1)+(fumRecRating*1.2))/4)

    deStatsIntsList = []
    deStatsPassDisList = []
    deStatsPassDisPercList = []
    deStatsFumRecList = []
    for de in activeDeList:
        de: FloosPlayer.PlayerDefBasic
        if de.seasonStatsDict['defense']['passTargets'] > 0:
            deStatsIntsList.append(de.seasonStatsDict['defense']['ints'])
            deStatsPassDisList.append(de.seasonStatsDict['defense']['passDisruptions'])
            deStatsPassDisPercList.append(de.seasonStatsDict['defense']['passDisPerc'])
            deStatsFumRecList.append(de.seasonStatsDict['defense']['fumRec'])

    for de in activeDeList:
        de: FloosPlayer.PlayerDefBasic
        if de.seasonStatsDict['defense']['passTargets'] > 0:
            intsRating = stats.percentileofscore(deStatsIntsList, de.seasonStatsDict['defense']['ints'], 'rank')
            passDisRating = stats.percentileofscore(deStatsPassDisList, de.seasonStatsDict['defense']['passDisruptions'], 'rank')
            passDisPercRating = stats.percentileofscore(deStatsPassDisPercList, de.seasonStatsDict['defense']['passDisPerc'], 'rank')
            fumRecRating = stats.percentileofscore(deStatsFumRecList, de.seasonStatsDict['defense']['fumRec'], 'rank')
            de.seasonPerformanceRating = round(((intsRating*.5)+(passDisRating*.8)+(passDisPercRating*1.2)+(fumRecRating*1.5))/4)

    dlStatsSacksList = []
    dlStatsFumRecList = []
    for dl in activeDlList:
        dl: FloosPlayer.PlayerDefBasic
        dlStatsSacksList.append(dl.seasonStatsDict['defense']['sacks'])
        dlStatsFumRecList.append(dl.seasonStatsDict['defense']['fumRec'])

    for dl in activeDlList:
        dl: FloosPlayer.PlayerDefBasic
        sacksRating = stats.percentileofscore(dlStatsSacksList, dl.seasonStatsDict['defense']['sacks'], 'rank')
        fumRecRating = stats.percentileofscore(dlStatsFumRecList, dl.seasonStatsDict['defense']['fumRec'], 'rank')
        dl.seasonPerformanceRating = round(((sacksRating*1.4)+(fumRecRating*.6))/2)

    defenseStatsSacksList = []
    defenseStatsIntsList = []
    defenseStatsFumblesList = []
    defenseStatsPassYardsList = []
    defenseStatsRunYardsList = []
    defenseStatsTotalYardsList = []
    defenseStatsPassTdsList = []
    defenseStatsRunTdsList = []
    defenseStatsTotalTdsList = []
    defenseStatsTotalPtsList = []
    
    for team in teamList:
        team: FloosTeam.Team
        defenseStatsSacksList.append(team.seasonTeamStats['Defense']['avgSacks'])
        defenseStatsIntsList.append(team.seasonTeamStats['Defense']['avgInts'])
        defenseStatsFumblesList.append(team.seasonTeamStats['Defense']['avgFumRec'])
        defenseStatsPassYardsList.append(team.seasonTeamStats['Defense']['avgPassYardsAlwd'])
        defenseStatsRunYardsList.append(team.seasonTeamStats['Defense']['avgRunYardsAlwd'])
        defenseStatsTotalYardsList.append(team.seasonTeamStats['Defense']['avgYardsAlwd'])
        defenseStatsPassTdsList.append(team.seasonTeamStats['Defense']['avgPassTdsAlwd'])
        defenseStatsRunTdsList.append(team.seasonTeamStats['Defense']['avgRunTdsAlwd'])
        defenseStatsTotalTdsList.append(team.seasonTeamStats['Defense']['avgTdsAlwd'])
        defenseStatsTotalPtsList.append(team.seasonTeamStats['Defense']['avgPtsAlwd'])

    for team in teamList:
        team: FloosTeam.Team
        sacksRating = stats.percentileofscore(defenseStatsSacksList, team.seasonTeamStats['Defense']['avgSacks'], 'rank')
        intsRating = stats.percentileofscore(defenseStatsIntsList, team.seasonTeamStats['Defense']['avgInts'], 'rank')
        fumblesRating = stats.percentileofscore(defenseStatsFumblesList, team.seasonTeamStats['Defense']['avgFumRec'], 'rank')
        passYardsRating = 100 - stats.percentileofscore(defenseStatsPassYardsList, team.seasonTeamStats['Defense']['avgPassYardsAlwd'], 'rank')
        runYardsRating = 100 - stats.percentileofscore(defenseStatsRunYardsList, team.seasonTeamStats['Defense']['avgRunYardsAlwd'], 'rank')
        totalYardsRating = 100 - stats.percentileofscore(defenseStatsTotalYardsList, team.seasonTeamStats['Defense']['avgYardsAlwd'], 'rank')
        passTdsRating = 100 - stats.percentileofscore(defenseStatsPassTdsList, team.seasonTeamStats['Defense']['avgPassTdsAlwd'], 'rank')
        runTdsRating = 100 - stats.percentileofscore(defenseStatsRunTdsList, team.seasonTeamStats['Defense']['avgRunTdsAlwd'], 'rank')
        totalTdsRating = 100 - stats.percentileofscore(defenseStatsTotalTdsList, team.seasonTeamStats['Defense']['avgTdsAlwd'], 'rank')
        totalPtsRating = 100 - stats.percentileofscore(defenseStatsTotalPtsList, team.seasonTeamStats['Defense']['avgPtsAlwd'], 'rank')
        
        team.defenseSeasonPerformanceRating = round(((sacksRating*.6)+(intsRating*.8)+(fumblesRating*.8)+(passYardsRating*1)+(runYardsRating*1)+(totalYardsRating*1.2)+(passTdsRating*1)+(runTdsRating*1)+(totalTdsRating*1.2)+(totalPtsRating*1.4))/10)

    list.sort(activeQbList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeRbList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeWrList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeTeList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeKList, key=lambda player: player.seasonPerformanceRating, reverse=True)

def saveUnusedNames():
    global unusedNamesList
    jsonFile = open("data/unusedNames.json", "w+")
    unusedNamesDict = {}
    y = 0
    for item in unusedNamesList:
        y += 1
        unusedNamesDict[y] = item
    jsonFile.write(json.dumps(unusedNamesDict, indent=4))
    jsonFile.close()

def getUnusedNames():
    global unusedNamesList
    jsonFile = open("data/unusedNames.json", "r")
    if os.path.exists("data/unusedNames.json"):
        with open('data/unusedNames.json') as jsonFile:
            unusedNames:dict = json.load(jsonFile)
            for name in unusedNames.values():
                unusedNamesList.append(name)
    jsonFile.close()

def inductHallOfFame():
    if len(newlyRetiredPlayersList) > 0:
        for player in newlyRetiredPlayersList:
            player:FloosPlayer.Player
            if player.playerTier.value == 5:
                hallOfFame.append(player)
                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has been inducted into the Floosball Hall of Fame'.format(player.name)}})
            elif player.playerTier.value == 4 and len(player.leagueChampionships):
                hallOfFame.append(player)
                activeSeason.leagueHighlights.insert(0, {'event':  {'text': '{} has been inducted into the Floosball Hall of Fame'.format(player.name)}})
        newlyRetiredPlayersList.clear()

async def startLeague():
    global cap
    global seasonsPlayed
    global totalSeasons
    global config
    global activeSeason
    global seasonList

    print('Floosball v{}'.format(__version__))
    #print('Reading config...')
    config = FloosMethods.getConfig()
    leagueConfig = config['leagueConfig']
    cap = leagueConfig['cap']
    totalSeasons = leagueConfig['totalSeasons']
    deleteDataOnStart = leagueConfig['deleteDataOnRestart']
    saveSeasonProgress = leagueConfig['saveSeasonProgress']
    #print('Config done')

    if saveSeasonProgress:
        #print('Save Season Progress enabled')
        seasonsPlayed = config['leagueConfig']['lastSeason']
        totalSeasons += seasonsPlayed

    if os.path.isdir('data'):
        if deleteDataOnStart:
            #print('Deleting previous data...')
            for f in os.listdir('data'):
                os.remove(os.path.join('data', f))
            #print('Previous data deleted')
    else:
        #print('Creating data directory')
        os.mkdir('data')

    #print('Creating players...')
    getPlayers(config)
    #print('Player creation done')
    #print('Creating teams...')
    getTeams(config)
    #print('Team creation done')

    if not os.path.exists("data/teamData.json"):
        #print('Starting player draft...')
        playerDraft()
        #print('Draft complete')
    else:
        print('Skipping draft')

    #print('Initializing teams...')
    initTeams()
    #print('Cleaning up players...')
    #initPlayers()
    #print('Saving player data...')
    savePlayerData()
    #print('Creating divisions...')
    getDivisons(config)
    if not os.path.exists("data/divisionData.json"):
        initDivisions()

    print('Initialization complete!')
    setNewingElo()
    while seasonsPlayed < totalSeasons:
        print('Season {} start'.format(seasonsPlayed+1))
        activeSeason = Season()
        seasonList.append(activeSeason)
        activeSeason.createSchedule()
        await activeSeason.startSeason()
        seasonsPlayed += 1

        if saveSeasonProgress:
            #print('Updating config after season end...')
            FloosMethods.saveConfig(seasonsPlayed, 'leagueConfig', 'lastSeason')
        await asyncio.sleep(30)
        await offseason()
        await asyncio.sleep(120)
        activeSeason.clearPlayerSeasonStats()
        activeSeason.clearTeamSeasonStats()