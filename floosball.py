import json
import os
from random import randint, seed, shuffle
from random_batch import batched_randint
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
import glob
import random
from logger_config import main_logger
from serializers import ModernSerializer
from managers.playerManager import PlayerManager
from config_manager import get_config, save_config_value
 

__version__ = '0.9.0_alpha'

config = None
totalSeasons = 0
seasonsPlayed = 0
cap = 0
playerManager = None
activePlayerList = []
unusedNamesList = []
freeAgentList = []
rookieDraftList = []
retiredPlayersList = []
newlyRetiredPlayersList = []
hallOfFame = []
standingsHistory = []

activeQbList = []
activeRbList = []
activeWrList = []
activeTeList = []
activeKList = []

freeAgencyOrder = []
freeAgencyHistoryDict = {}
teamList = []
leagueList = []   
scheduleList = []
seasonList = []
activeSeason = None
floosbowlChampion: FloosTeam.Team = None
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
                },
                'points': {
                    'record': 'Fantasy Points',
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
            'leagueTitles': {
                'record': 'League Titles',
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
            if player.gameStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['passing']['game']['points']['value']:
                allTimeRecordsDict['players']['passing']['game']['points']['value'] = player.gameStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['passing']['game']['points']['name'] = player.name
                allTimeRecordsDict['players']['passing']['game']['points']['id'] = player.id

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
            if player.gameStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['rushing']['game']['points']['value']:
                allTimeRecordsDict['players']['rushing']['game']['points']['value'] = player.gameStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['rushing']['game']['points']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['game']['points']['id'] = player.id
        
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
            
            if player.position == FloosPlayer.Position.WR or player.position == FloosPlayer.Position.TE:
                if player.gameStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['receiving']['game']['points']['value']:
                    allTimeRecordsDict['players']['receiving']['game']['points']['value'] = player.gameStatsDict['fantasyPoints']
                    allTimeRecordsDict['players']['receiving']['game']['points']['name'] = player.name
                    allTimeRecordsDict['players']['receiving']['game']['points']['id'] = player.id
        
        if player.gameStatsDict['kicking']['fgs'] > 0:
            if player.gameStatsDict['kicking']['fgs'] > allTimeRecordsDict['players']['kicking']['game']['fgs']['value']:
                allTimeRecordsDict['players']['kicking']['game']['fgs']['value'] = player.gameStatsDict['kicking']['fgs']
                allTimeRecordsDict['players']['kicking']['game']['fgs']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['game']['fgs']['id'] = player.id
            if player.gameStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['kicking']['game']['points']['value']:
                allTimeRecordsDict['players']['kicking']['game']['points']['value'] = player.gameStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['kicking']['game']['points']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['game']['points']['id'] = player.id
        
        if player.gameStatsDict['kicking']['fgYards'] > 0:
            if player.gameStatsDict['kicking']['fgYards'] > allTimeRecordsDict['players']['kicking']['game']['fgYards']['value']:
                allTimeRecordsDict['players']['kicking']['game']['fgYards']['value'] = player.gameStatsDict['kicking']['fgYards']
                allTimeRecordsDict['players']['kicking']['game']['fgYards']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['game']['fgYards']['id'] = player.id

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
            if player.careerStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['passing']['career']['points']['value']:
                allTimeRecordsDict['players']['passing']['career']['points']['value'] = player.careerStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['passing']['career']['points']['name'] = player.name
                allTimeRecordsDict['players']['passing']['career']['points']['id'] = player.id

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
            if player.careerStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['rushing']['career']['points']['value']:
                allTimeRecordsDict['players']['rushing']['career']['points']['value'] = player.careerStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['rushing']['career']['points']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['career']['points']['id'] = player.id
        
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
            if player.position == FloosPlayer.Position.WR or player.position == FloosPlayer.Position.TE:
                if player.careerStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['receiving']['career']['points']['value']:
                    allTimeRecordsDict['players']['receiving']['career']['points']['value'] = player.careerStatsDict['fantasyPoints']
                    allTimeRecordsDict['players']['receiving']['career']['points']['name'] = player.name
                    allTimeRecordsDict['players']['receiving']['career']['points']['id'] = player.id
        
        if player.careerStatsDict['kicking']['fgs'] > 0:
            if player.careerStatsDict['kicking']['fgs'] > allTimeRecordsDict['players']['kicking']['career']['fgs']['value']:
                allTimeRecordsDict['players']['kicking']['career']['fgs']['value'] = player.careerStatsDict['kicking']['fgs']
                allTimeRecordsDict['players']['kicking']['career']['fgs']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['career']['fgs']['id'] = player.id
            if player.careerStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['kicking']['career']['points']['value']:
                allTimeRecordsDict['players']['kicking']['career']['points']['value'] = player.careerStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['kicking']['career']['points']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['career']['points']['id'] = player.id
        
        if player.careerStatsDict['kicking']['fgYards'] > 0:
            if player.careerStatsDict['kicking']['fgYards'] > allTimeRecordsDict['players']['kicking']['career']['fgYards']['value']:
                allTimeRecordsDict['players']['kicking']['career']['fgYards']['value'] = player.careerStatsDict['kicking']['fgYards']
                allTimeRecordsDict['players']['kicking']['career']['fgYards']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['career']['fgYards']['id'] = player.id

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

            if len(team.floosbowlChampionships) > allTimeRecordsDict['team']['allTime']['titles']['value']:
                allTimeRecordsDict['team']['allTime']['titles']['value'] = len(team.floosbowlChampionships)
                allTimeRecordsDict['team']['allTime']['titles']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['titles']['id'] = team.id

            if len(team.leagueChampionships) > allTimeRecordsDict['team']['allTime']['leagueTitles']['value']:
                allTimeRecordsDict['team']['allTime']['leagueTitles']['value'] = len(team.leagueChampionships)
                allTimeRecordsDict['team']['allTime']['leagueTitles']['name'] = '{} {}'.format(team.city, team.name)
                allTimeRecordsDict['team']['allTime']['leagueTitles']['id'] = team.id

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
            if player.seasonStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['passing']['season']['points']['value']:
                allTimeRecordsDict['players']['passing']['season']['points']['value'] = player.seasonStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['passing']['season']['points']['name'] = player.name
                allTimeRecordsDict['players']['passing']['season']['points']['id'] = player.id
                allTimeRecordsDict['players']['passing']['season']['points']['season'] = season

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
            if player.seasonStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['rushing']['season']['points']['value']:
                allTimeRecordsDict['players']['rushing']['season']['points']['value'] = player.seasonStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['rushing']['season']['points']['name'] = player.name
                allTimeRecordsDict['players']['rushing']['season']['points']['id'] = player.id
                allTimeRecordsDict['players']['rushing']['season']['points']['season'] = season
        
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
            if player.position == FloosPlayer.Position.WR or player.position == FloosPlayer.Position.TE:
                if player.seasonStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['receiving']['season']['points']['value']:
                    allTimeRecordsDict['players']['receiving']['season']['points']['value'] = player.seasonStatsDict['fantasyPoints']
                    allTimeRecordsDict['players']['receiving']['season']['points']['name'] = player.name
                    allTimeRecordsDict['players']['receiving']['season']['points']['id'] = player.id
                    allTimeRecordsDict['players']['receiving']['season']['points']['season'] = season
        
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
            if player.seasonStatsDict['fantasyPoints'] > allTimeRecordsDict['players']['kicking']['season']['points']['value']:
                allTimeRecordsDict['players']['kicking']['season']['points']['value'] = player.seasonStatsDict['fantasyPoints']
                allTimeRecordsDict['players']['kicking']['season']['points']['name'] = player.name
                allTimeRecordsDict['players']['kicking']['season']['points']['id'] = player.id
                allTimeRecordsDict['players']['kicking']['season']['points']['season'] = season

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

    
class League:
    def __init__(self, config):
        self.name = config['name']
        self.teamList = []

class Season:
    def __init__(self):
        self.currentSeason = seasonsPlayed + 1
        self.activeGames = None
        self.currentWeek = None
        self.currentWeekText = None
        self.leagueHighlights = []
        self.playoffTeams = {}
        self.nonPlayoffTeams = {}

    def updatePlayoffPicture(self):

        for league in leagueList:
            league: League
            sliceIndex = int(len(league.teamList)/2)
            playoffTeams = league.teamList[:sliceIndex]
            nonPlayoffTeams = league.teamList[sliceIndex:]
            list.sort(league.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            self.playoffTeams[league.name] = playoffTeams
            self.nonPlayoffTeams[league.name] = nonPlayoffTeams



    def checkForClinches(self):

        for league in leagueList:
            team1: FloosTeam.Team = league.teamList[0]
            team2: FloosTeam.Team = league.teamList[1]
            playoffTeamList = self.playoffTeams[league.name]
            nonPlayoffTeamsList = self.nonPlayoffTeams[league.name]

            lastTeamIn = playoffTeamList[len(playoffTeamList)-1]
            firstTeamOut = nonPlayoffTeamsList[0]

            if not team1.clinchedTopSeed:
                team1.clinchedTopSeed = FloosMethods.checkIfClinched(team1.seasonTeamStats['wins'], team2.seasonTeamStats['wins'], 28 - self.currentWeek)
                if team1.clinchedTopSeed:
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched the #1 seed'.format(team1.city, team1.name)}})
                elif self.currentWeek == 28:
                    team1.clinchedTopSeed = True
                    self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched the #1 seed'.format(team1.city, team1.name)}})

            if self.currentWeek == 28:
                for team in playoffTeamList:
                    team: FloosTeam.Team
                    if not team.clinchedPlayoffs:
                        team.clinchedPlayoffs = True
                        self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}})
                for team in nonPlayoffTeamsList:
                    team: FloosTeam.Team
                    if not team.eliminated:
                        team.eliminated = True
                        self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
            else:
                for team in playoffTeamList:
                    team:FloosTeam.Team
                    if not team.clinchedPlayoffs and not team.eliminated:
                        team.clinchedPlayoffs = FloosMethods.checkIfClinched(team.seasonTeamStats['wins'], firstTeamOut.seasonTeamStats['wins'], 28 - self.currentWeek)
                        if team.clinchedPlayoffs:
                            self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have clinched a playoff berth'.format(team.city, team.name)}})
                for team in nonPlayoffTeamsList:
                    team:FloosTeam.Team
                    if team.seasonTeamStats['winPerc'] < .45 and self.currentWeek >= 14:
                        team.pressureModifier = .9
                    if not team.clinchedPlayoffs and not team.eliminated:
                        team.eliminated = FloosMethods.checkIfEliminated(team.seasonTeamStats['wins'], lastTeamIn.seasonTeamStats['wins'], 28 - self.currentWeek)
                        if team.eliminated:
                            self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
                            team.pressureModifier = .7
                        else:
                            if team.seasonTeamStats['wins'] + (28 - self.currentWeek) == lastTeamIn.seasonTeamStats['wins']:
                                self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} are on the brink of elimination!'.format(team.city, team.name)}})
                                if (28-self.currentWeek) <= 5:
                                    team.pressureModifier = 2


    def generateSchedule(self):
        schedule = []

        league1Teams = list.copy(leagueList[0].teamList)
        league2Teams = list.copy(leagueList[1].teamList)
        intraleagueGames = []
        league1Games = self.generateIntraleagueGames(league1Teams)
        league2Games = self.generateIntraleagueGames(league2Teams)
        interleagueGames = self.generateInterleagueGames(league1Teams,league2Teams)

        for x in range(len(league1Games)):
            week = []
            week.extend(league1Games[x])
            week.extend(league2Games[x])
            intraleagueGames.append(week)

        schedule = interleagueGames + intraleagueGames
        random.shuffle(schedule)
        return schedule


    def generateIntraleagueGames(self, teams):
        n = len(teams)
        tempTeams = teams.copy()
        weeks = []

        for week in range(n - 1):
            games = []
            for i in range(n // 2):
                if week % 2 == 0:
                    home = tempTeams[i]
                    away = tempTeams[n - 1 - i]
                    games.append((home, away))
                else:
                    home = tempTeams[n - 1 - i]
                    away = tempTeams[i]
                    games.append((home, away))

            weeks.append(games)
            tempTeams.insert(1, tempTeams.pop())

        reverseWeeks = []
        for week in weeks:
            reverse = [(away, home) for home, away in week]
            reverseWeeks.append(reverse)

        weeks.extend(reverseWeeks)
        return weeks

    
    def generateInterleagueGames(self, league1, league2):
        weeks = []
        group1Weeks = []
        group2Weeks = []
        league1Group1Teams = []
        league1Group2Teams = []
        league2Group1Teams = []
        league2Group2Teams = []

        for x in range(len(leagueList[0].teamList)):
            if x < (len(leagueList[0].teamList) / 2):
                league1Group1Teams.append(league1.pop(random.randrange(len(league1))))
                league2Group1Teams.append(league2.pop(random.randrange(len(league2))))
            else:
                league1Group2Teams.append(league1.pop(random.randrange(len(league1))))
                league2Group2Teams.append(league2.pop(random.randrange(len(league2))))

        for x in range(len(league1Group1Teams)):
            games = []
            for y in range(len(league1Group1Teams)):
                a = x+y
                z = int(a % (len(league1Group1Teams)))
                if y % 2 == 0:
                    games.append((league1Group1Teams[y], league2Group1Teams[z]))
                else:
                    games.append((league2Group1Teams[z], league1Group1Teams[y]))
            group1Weeks.append(games)

        for x in range(len(league1Group2Teams)):
            games = []
            for y in range(len(league1Group2Teams)):
                a = x+y
                z = int(a % (len(league1Group2Teams)))
                if y % 2 == 0:
                    games.append((league1Group2Teams[y], league2Group2Teams[z]))
                else:
                    games.append((league2Group2Teams[z], league1Group2Teams[y]))
            group2Weeks.append(games)

        for x in range(len(group1Weeks)):
            week = []
            week.extend(group1Weeks[x])
            week.extend(group2Weeks[x])
            weeks.append(week)

        return weeks


    def createSchedule(self):
        numOfWeeks = int(((len(leagueList[0].teamList) - 1) * 2) + (len(leagueList[0].teamList) / 2))
        schedule = self.generateSchedule()
        scheduleList.clear()
        dateTimeNow = datetime.datetime.utcnow()
        for week in range(0, numOfWeeks):
            gameList = []
            numOfGames = int(len(teamList)/2)
            weekStartTime = self.getWeekStartTime(dateTimeNow, week)
            for x in range(0, numOfGames):
                game = schedule[week][x]
                homeTeam:FloosTeam.Team = game[0]
                awayTeam:FloosTeam.Team = game[1]
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
        global standingsHistory
        for team in teamList:
            jsonFile = open("data/teamData/team{}.json".format(team.id), "w+")
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
                    player.careerStatsDict['passing']['ypc'] = round(player.careerStatsDict['passing']['yards']/player.careerStatsDict['passing']['comp'],2)
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
                        player.careerStatsDict['receiving']['ypr'] = round(player.careerStatsDict['receiving']['yards']/player.careerStatsDict['receiving']['receptions'],2)
                        player.careerStatsDict['receiving']['rcvPerc'] = round((player.careerStatsDict['receiving']['receptions']/player.careerStatsDict['receiving']['targets'])*100)
                if player.seasonStatsDict['rushing']['carries'] > 0:
                    #player.careerStatsDict['rushing']['carries'] += player.seasonStatsDict['rushing']['carries']
                    #player.careerStatsDict['rushing']['yards'] += player.seasonStatsDict['rushing']['yards']
                    #player.careerStatsDict['rushing']['tds'] += player.seasonStatsDict['rushing']['tds']
                    #player.careerStatsDict['rushing']['fumblesLost'] += player.seasonStatsDict['rushing']['fumblesLost']
                    player.careerStatsDict['rushing']['20+'] += player.seasonStatsDict['rushing']['20+']
                    player.careerStatsDict['rushing']['ypc'] = round(player.careerStatsDict['rushing']['yards']/player.careerStatsDict['rushing']['carries'],2)
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

                player.careerStatsDict['fantasyPoints'] += player.seasonStatsDict['fantasyPoints']
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
                playerDict['currentNumber'] = player.currentNumber
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
            teamDict['defenseRunCoverageRating'] = team.defenseRunCoverageRating
            teamDict['defensePassCoverageRating'] = team.defensePassCoverageRating
            teamDict['defensePassRushRating'] = team.defensePassRushRating
            teamDict['defensePassRating'] = team.defensePassRating
            teamDict['defenseRating'] = team.defenseRating
            #teamDict['defenseLuck'] = team.defenseLuck
            #teamDict['defenseDiscipline'] = team.defenseDiscipline
            teamDict['overallRating'] = team.overallRating
            teamDict['allTimeTeamStats'] = team.allTimeTeamStats
            teamDict['playoffAppearances'] = team.playoffAppearances
            teamDict['gmScore'] = team.gmScore
            teamDict['defenseTier'] = team.defenseOverallTier
            teamDict['leagueChampionships'] = team.leagueChampionships
            teamDict['floosbowlChampionships'] = team.floosbowlChampionships
            teamDict['regularSeasonChampions'] = team.regularSeasonChampions
            teamDict['rosterHistory'] = team.rosterHistory
            teamDict['defenseSeasonPerformanceRating'] = team.defenseSeasonPerformanceRating
            teamDict['roster'] = rosterDict
            jsonFile.write(json.dumps(teamDict, indent=4))
            jsonFile.close()

        playerManager.savePlayerData()

        leagueList = []
        for league in leagueList:
            leagueDict = {}
            tempTeamList = []
            leagueDict['leagueName'] = league.name
            league: League
            for team in league.teamList:
                team: FloosTeam.Team
                teamDict = {}
                teamDict['name'] = team.name
                teamDict['city'] = team.city
                teamDict['color'] = team.color
                teamDict['id'] = team.id
                teamDict['elo'] = team.elo
                teamDict['wins'] = team.seasonTeamStats['wins']
                teamDict['losses'] = team.seasonTeamStats['losses']
                teamDict['clinchedPlayoffs'] = team.clinchedPlayoffs
                teamDict['clinchedTopSeed'] = team.clinchedTopSeed
                teamDict['leagueChampion'] = team.leagueChampion
                teamDict['floosbowlChampion'] = team.floosbowlChampion
                if (team.seasonTeamStats['wins']+team.seasonTeamStats['losses']) > 0:
                    teamDict['winPerc'] = '{:.3f}'.format(round(team.seasonTeamStats['wins']/(team.seasonTeamStats['wins']+team.seasonTeamStats['losses']),3))
                else:
                    teamDict['winPerc'] = '0.000'

                if team.seasonTeamStats['scoreDiff'] >= 0:
                    teamDict['pointDiff'] = '+{}'.format(team.seasonTeamStats['scoreDiff'])
                else:
                    teamDict['pointDiff'] = '{}'.format(team.seasonTeamStats['scoreDiff'])
                tempTeamList.append(teamDict)
            list.sort(tempTeamList, key=lambda team: team['winPerc'], reverse=True)
            leagueDict['teams'] = tempTeamList
            leagueList.append(leagueDict)
        standingsHistory.append(leagueList)
        

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
        global floosbowlChampion
        weekDict = {}
        seasonDict = {}
        gameDictTemp = {}
        freeAgencyOrder = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)

        for team in teamList:
            team: FloosTeam.Team
            team.eliminated = False
            team.clinchedPlayoffs = False
            team.clinchedTopSeed = False
            team.leagueChampion = False
            team.floosbowlChampion = False
            team.winningStreak = False
            team.seasonTeamStats['season'] = self.currentSeason
            rosterDict = {}
            for pos, player in team.rosterDict.items():
                player: FloosPlayer.Player
                rosterDict[pos] = {'name': player.name, 'pos': player.position.name, 'rating': player.attributes.overallRating, 'stars': player.playerTier.value, 'termRemaining': player.termRemaining, 'id': player.id, 'number': player.currentNumber}
            rosterDict['defense'] = {'passDefenseStars': round((((team.defensePassRating - 60)/40)*4)+1), 'runDefenseStars': round((((team.defenseRunCoverageRating - 60)/40)*4)+1), 'passDefenseRating': team.defensePassRating, 'runDefenseRating': team.defenseRunCoverageRating}
            team.rosterHistory.append({'season': self.currentSeason, 'roster': rosterDict})

            if self.currentSeason > 1:
                previousSeason = team.statArchive[0]
                if previousSeason['madePlayoffs']:
                    if not previousSeason['floosbowlChamp']:
                        if previousSeason['leageChamp'] and previousSeason['topSeed']:
                            team.pressureModifier = 1.5
                        elif previousSeason['leageChamp'] or previousSeason['topSeed']:
                            team.pressureModifier = 1.4
                        else:
                            team.pressureModifier = 1.2
                else:
                    if previousSeason['winPerc'] < .25:
                        team.pressureModifier = .7
                    elif previousSeason['winPerc'] < .4:
                        team.pressureModifier = .8
                    elif previousSeason['winPerc'] < .5:
                        team.pressureModifier = .9
                    else:
                        team.pressureModifier = 1


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

            #await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < weekStartTime:
            #     await asyncio.sleep(30)

            self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})
            await asyncio.wait(gamesList)

            for game in range(0,len(self.activeGames)):
                strGame = 'Game {}'.format(game + 1)
                gameResults = self.activeGames[game].gameDict
                gameDict[strGame] = gameResults
                checkTeamGameRecords(self.activeGames[game])
            weekDict = ModernSerializer.serialize(gameDict)
            jsonFile = open(os.path.join(weekFilePath, '{}.json'.format(self.currentWeekText)), "w+")
            jsonFile.write(json.dumps(weekDict, indent=4))
            jsonFile.close()
            
            for league in leagueList:
                list.sort(league.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            list.sort(teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            getPerformanceRating(self.currentWeek)
            playerManager.sortPlayersByPosition()
            sortDefenses()
            self.updatePlayoffPicture()
            self.checkForClinches()
            checkPlayerGameRecords()
            checkCareerRecords()
            checkSeasonRecords(self.currentSeason)
            self.leagueHighlights.insert(0, {'event': {'text': '{} End'.format(self.currentWeekText)}})
            #await asyncio.sleep(120)

        list.sort(teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
        bestTeam:FloosTeam.Team = teamList[0]
        bestTeam.regularSeasonChampions.append('Season {}'.format(seasonsPlayed+1))
        #seasonDict['games'] = weekDict
        floosbowlChampion = await self.playPlayoffs()
        floosbowlChampion.seasonTeamStats['floosbowlChamp'] = True
        floosbowlChampion.floosbowlChampion = True

        self.saveSeasonStats()

        standingsDict = {}
        leagueStandingsTempDict = {}
        jsonFile = open("data/leagueData.json", "w+")
        for league in leagueList:
            list.sort(league.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            leagueStandingsDict = leagueStandingsTempDict.copy()
            #print("\n{0} Division".format(division.name))
            for team in league.teamList:
                leagueStandingsDict[team.name] = '{0} - {1}'.format(team.seasonTeamStats['wins'], team.seasonTeamStats['losses'])
            standingsDict[league.name] = leagueStandingsDict

        jsonFile.write(json.dumps(standingsDict, indent=4))
        jsonFile.close()

        seasonDict['standings'] = standingsDict
        seasonDict['champion'] = floosbowlChampion.name

        _serialzedDict = ModernSerializer.serialize(seasonDict)

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
            dict['runDefenseRating'] = team.defenseRunCoverageRating
            dict['passDefenseRating'] = team.defensePassCoverageRating
            dict['leagueChampionships'] = team.leagueChampionships
            dict['floosbowlChampionships'] = team.floosbowlChampionships
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
                playerDict['number'] = player.currentNumber
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
        global scheduleList
        champ = None
        playoffDict = {}
        playoffTeams = {}
        playoffsByeTeams = {}
        playoffsNonByeTeams = {}
        nonPlayoffTeamList = []
        strCurrentSeason = 'season{}'.format(self.currentSeason)
        x = 0
        for league in leagueList:
            playoffTeamsList = []
            playoffsByeTeamList = []
            playoffsNonByeTeamList = []
            list.sort(league.teamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

            playoffTeamsList.extend(league.teamList[:int(len(league.teamList)/2)])
            nonPlayoffTeamList.extend(league.teamList[int(len(league.teamList)/2):])
            playoffsByeTeamList.extend(playoffTeamsList[:2])
            playoffsNonByeTeamList.extend(playoffTeamsList[2:])
            list.sort(playoffsByeTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
            list.sort(playoffsNonByeTeamList, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

            playoffsByeTeamList[0].clinchedTopSeed = True
            playoffsByeTeamList[0].seasonTeamStats['topSeed'] = True

            playoffTeams[league.name] = playoffTeamsList.copy()
            playoffsByeTeams[league.name] = playoffsByeTeamList.copy()
            playoffsNonByeTeams[league.name] = playoffsNonByeTeamList.copy()

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
        

        freeAgencyOrder.extend(nonPlayoffTeamList)
        list.sort(freeAgencyOrder, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=False)

        numOfRounds = FloosMethods.getPower(2, len(teamList)/2)

        for x in range(numOfRounds):

            playoffGamesDict = {}
            playoffGamesList = []
            playoffGamesTaskList = []
            self.leagueHighlights = []
            currentRound = x + 1
            gameNumber = 1
            roundStartTime = self.getWeekStartTime(datetime.datetime.utcnow(), 28 + currentRound)


            if x < numOfRounds - 1:
                for league in leagueList:
                    teamsInRound = []
                    gamesList = []

                    if currentRound == 1:
                        teamsInRound.extend(playoffsNonByeTeams[league.name])
                        for team in playoffTeams[league.name]:
                            team: FloosTeam.Team
                            team.pressureModifier = 1.5

                    else:
                        teamsInRound.extend(playoffTeams[league.name])
                        for team in playoffTeams[league.name]:
                            team: FloosTeam.Team
                            team.pressureModifier += .2

                    list.sort(teamsInRound, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)

                    hiSeed = 0
                    lowSeed = len(teamsInRound) - 1

                    while lowSeed > hiSeed:
                        newGame = FloosGame.Game(teamsInRound[hiSeed], teamsInRound[lowSeed])
                        newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
                        newGame.status = FloosGame.GameStatus.Scheduled
                        newGame.startTime = roundStartTime
                        newGame.isRegularSeasonGame = False
                        newGame.calculateWinProbability()
                        gamesList.append(newGame)
                        playoffGamesTaskList.append(newGame.playGame())
                        newGame.leagueHighlights = self.leagueHighlights
                        hiSeed += 1
                        lowSeed -= 1
                        gameNumber += 1
                    
                    playoffGamesDict[league.name] = gamesList.copy()
                    playoffGamesList.extend(gamesList)

                

                self.currentWeek = 'Playoffs Round {}'.format(x+1)
                self.currentWeekText = 'Playoffs Round {}'.format(x+1)
            else:
                floosbowlTeams = []
                for league in leagueList:
                    floosbowlTeams.extend(playoffTeams[league.name])
                for team in floosbowlTeams:
                    team.leagueChampion = True
                list.sort(floosbowlTeams, key=lambda team: (team.seasonTeamStats['winPerc'],team.seasonTeamStats['scoreDiff']), reverse=True)
                newGame = FloosGame.Game(floosbowlTeams[0], floosbowlTeams[1])
                newGame.id = 's{0}r{1}g{2}'.format(self.currentSeason, currentRound, gameNumber)
                newGame.status = FloosGame.GameStatus.Scheduled
                newGame.startTime = roundStartTime
                newGame.isRegularSeasonGame = False
                newGame.calculateWinProbability()
                playoffGamesList.append(newGame)
                playoffGamesTaskList.append(newGame.playGame())
                newGame.leagueHighlights = self.leagueHighlights
                self.currentWeek = 'Floos Bowl'
                self.currentWeekText = 'Floos Bowl'
                newGame.homeTeam.pressureModifier = 2.5
                newGame.awayTeam.pressureModifier = 2.5

            self.activeGames = playoffGamesList
            scheduleList.append({'startTime': roundStartTime, 'games': playoffGamesList})

            self.leagueHighlights.insert(0, {'event': {'text': '{} Starting Soon...'.format(self.currentWeekText)}})

            #await asyncio.sleep(30)
            # while datetime.datetime.utcnow() < roundStartTime:
            #     await asyncio.sleep(30)
                
            self.leagueHighlights.insert(0, {'event': {'text': '{} Start'.format(self.currentWeekText)}})
            await asyncio.wait(playoffGamesTaskList)

            if len(playoffGamesList) == 1:
                game: FloosGame.Game = playoffGamesList[0]
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
                for league in leagueList:
                    for game in playoffGamesDict[league.name]:
                        game: FloosGame.Game
                        gameResults = game.gameDict
                        playoffDict[game.id] = gameResults
                        for team in playoffTeams[league.name]:
                            if team.name == gameResults['losingTeam']:
                                team.eliminated = True
                                self.leagueHighlights.insert(0, {'event': {'text': '{0} {1} have faded from playoff contention'.format(team.city, team.name)}})
                                freeAgencyOrder.append(team)
                                playoffTeams[league.name].remove(team)
                                break

                

            jsonFile = open(os.path.join('{}/games'.format(strCurrentSeason), 'postseason.json'), "w+")
            jsonFile.write(json.dumps(playoffDict, indent=4))
            jsonFile.close()
            if x < numOfRounds - 1:
                playerManager.sortPlayersByPosition()
                sortDefenses()
                #await asyncio.sleep(30)

        return champ

def setNewElo():
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
            team.elo = round((team.elo+1500)/2)
            
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



def getTeams(_config):

    if os.path.exists("data/teamData"):
        fileList = glob.glob("data/teamData/team*.json")
        for file in fileList:
            with open(file) as jsonFile:
                team = json.load(jsonFile)
                newTeam = FloosTeam.Team(team['name'])
                newTeam.id = team['id']
                newTeam.city = team['city']
                newTeam.abbr = team['abbr']
                newTeam.color = team['color']
                newTeam.offenseRating = team['offenseRating']
                newTeam.defenseRunCoverageRating = team['defenseRunCoverageRating']
                newTeam.defensePassCoverageRating = team['defensePassCoverageRating']
                newTeam.defensePassRushRating = team['defensePassRushRating']
                newTeam.defenseRating = team['defenseRating']
                newTeam.gmScore = team['gmScore']
                newTeam.defenseOverallTier = team['defenseTier']
                newTeam.defenseSeasonPerformanceRating = team['defenseSeasonPerformanceRating']
                newTeam.overallRating = team['overallRating']
                newTeam.allTimeTeamStats = team['allTimeTeamStats']
                newTeam.leagueChampionships = team['leagueChampionships']
                newTeam.floosbowlChampionships = team['floosbowlChampionships']
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

def getLeagues(_config):

    if os.path.exists("data/leagueData.json"):
        with open('data/leagueData.json') as jsonFile:
            leagueData = json.load(jsonFile)
            for x in leagueData:
                league = League(x)
                jteamList = leagueData[x]
                for team in jteamList:
                    for y in teamList:
                        if y.name == team:
                            league.teamList.append(y)
                            break
                leagueList.append(league)
    else:
        for x in _config['leagues']:
            league = League(x)
            leagueList.append(league)

def initTeams():
    if not os.path.exists('data/teamData'):
        os.makedirs('data/teamData')
    for team in teamList:
        jsonFile = open("data/teamData/team{}.json".format(team.id), "w+")
        team: FloosTeam.Team
        team.setupTeam()
        teamDict = {}
        teamDict['name'] = team.name
        teamDict['city'] = team.city
        teamDict['abbr'] = team.abbr
        teamDict['color'] = team.color
        teamDict['id'] = team.id
        teamDict['offenseRating'] = team.offenseRating
        teamDict['defenseRunCoverageRating'] = team.defenseRunCoverageRating
        teamDict['defensePassRating'] = team.defensePassRating
        teamDict['defensePassCoverageRating'] = team.defensePassCoverageRating
        teamDict['defensePassRushRating'] = team.defensePassRushRating
        teamDict['defenseRating'] = team.defenseRating
        #teamDict['defenseLuck'] = team.defenseLuck
        #teamDict['defenseDiscipline'] = team.defenseDiscipline
        teamDict['overallRating'] = team.overallRating
        teamDict['allTimeTeamStats'] = team.allTimeTeamStats
        teamDict['floosbowlChampionships'] = team.floosbowlChampionships
        teamDict['regularSeasonChampions'] = team.regularSeasonChampions
        teamDict['leagueChampionships'] = team.leagueChampionships
        teamDict['playoffAppearances'] = team.playoffAppearances
        teamDict['gmScore'] = team.gmScore
        teamDict['defenseTier'] = team.defenseOverallTier
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

        jsonFile.write(json.dumps(teamDict, indent=4))
        jsonFile.close()

    sortDefenses()


def initPlayers():
    pass



def sortDefenses():
    teamDefenseOverallRatingList = []
    teamDefensePassRatingList = []
    teamDefenseRunRatingList = []

    for team in teamList:
        team: FloosTeam.Team
        teamDefenseOverallRatingList.append(team.defenseOverallRating)
        teamDefensePassRatingList.append(team.defensePassRating)
        teamDefenseRunRatingList.append(team.defenseRunCoverageRating)
    
    tier5perc = np.percentile(teamDefenseOverallRatingList, 95)
    tier4perc = np.percentile(teamDefenseOverallRatingList, 80)
    tier3perc = np.percentile(teamDefenseOverallRatingList, 30)
    tier2perc = np.percentile(teamDefenseOverallRatingList, 10)

    for team in teamList:
        team: FloosTeam.Team
        if team.defenseOverallRating >= tier5perc:
            team.defenseOverallTier = FloosPlayer.PlayerTier.TierS.value
        elif team.defenseOverallRating >= tier4perc:
            team.defenseOverallTier = FloosPlayer.PlayerTier.TierA.value
        elif team.defenseOverallRating >= tier3perc:
            team.defenseOverallTier = FloosPlayer.PlayerTier.TierB.value
        elif team.defenseOverallRating >= tier2perc:
            team.defenseOverallTier = FloosPlayer.PlayerTier.TierC.value
        else:
            team.defenseOverallTier = FloosPlayer.PlayerTier.TierD.value

    tier5perc = np.percentile(teamDefensePassRatingList, 95)
    tier4perc = np.percentile(teamDefensePassRatingList, 80)
    tier3perc = np.percentile(teamDefensePassRatingList, 30)
    tier2perc = np.percentile(teamDefensePassRatingList, 10)

    for team in teamList:
        team: FloosTeam.Team
        if team.defensePassRating >= tier5perc:
            team.defensePassTier = FloosPlayer.PlayerTier.TierS.value
        elif team.defensePassRating >= tier4perc:
            team.defensePassTier = FloosPlayer.PlayerTier.TierA.value
        elif team.defensePassRating >= tier3perc:
            team.defensePassTier = FloosPlayer.PlayerTier.TierB.value
        elif team.defensePassRating >= tier2perc:
            team.defensePassTier = FloosPlayer.PlayerTier.TierC.value
        else:
            team.defensePassTier = FloosPlayer.PlayerTier.TierD.value

    tier5perc = np.percentile(teamDefenseRunRatingList, 95)
    tier4perc = np.percentile(teamDefenseRunRatingList, 80)
    tier3perc = np.percentile(teamDefenseRunRatingList, 30)
    tier2perc = np.percentile(teamDefenseRunRatingList, 10)

    for team in teamList:
        team: FloosTeam.Team
        if team.defenseRunCoverageRating >= tier5perc:
            team.defenseRunTier = FloosPlayer.PlayerTier.TierS.value
        elif team.defenseRunCoverageRating >= tier4perc:
            team.defenseRunTier = FloosPlayer.PlayerTier.TierA.value
        elif team.defenseRunCoverageRating >= tier3perc:
            team.defenseRunTier = FloosPlayer.PlayerTier.TierB.value
        elif team.defenseRunCoverageRating >= tier2perc:
            team.defenseRunTier = FloosPlayer.PlayerTier.TierC.value
        else:
            team.defenseRunTier = FloosPlayer.PlayerTier.TierD.value


        
def initLeagues():
    tempTeamList = teamList.copy()
    numOfLeagues = len(leagueList)
    y = 0
    while len(tempTeamList) > 0:
        x = randint(0,len(tempTeamList)-1)
        # if len(tempTeamList) % 2 == 0:
        #     divisionList[0].teamList.append(tempTeamList[x])
        # else:
        #     divisionList[1].teamList.append(tempTeamList[x])
        leagueList[y].teamList.append(tempTeamList[x])
        y += 1
        if y == numOfLeagues:
            y = 0
        tempTeamList.remove(tempTeamList[x])
    for league in leagueList:
        for team in league.teamList:
            team.league = league.name

async def offseason():
    activeSeason.currentWeek = 'Offseason'
    activeSeason.currentWeekText = 'Offseason'
    newPlayerCount = 12
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

    numOfPlayers = newPlayerCount
    if len(newlyRetiredPlayersList) > newPlayerCount:
        numOfPlayers = len(newlyRetiredPlayersList)
    meanPlayerSkill = 80
    stdDevPlayerSkill = 7

    playerAverages = np.random.normal(meanPlayerSkill, stdDevPlayerSkill, numOfPlayers)
    playerAverages = np.clip(playerAverages, 60, 100)
    playerAverages: list = playerAverages.tolist()

    for player in newlyRetiredPlayersList:
        player: FloosPlayer.Player
        newPlayer: FloosPlayer.Player = None
        seed = int(playerAverages.pop(randint(0,len(playerAverages)-1)))
        if player.position is FloosPlayer.Position.QB:
            newPlayer = FloosPlayer.PlayerQB(seed)
            activeQbList.append(newPlayer)
        elif player.position is FloosPlayer.Position.RB:
            newPlayer = FloosPlayer.PlayerRB(seed)
            activeRbList.append(newPlayer)
        elif player.position is FloosPlayer.Position.WR:
            newPlayer = FloosPlayer.PlayerWR(seed)
            activeWrList.append(newPlayer)
        elif player.position is FloosPlayer.Position.TE:
            newPlayer = FloosPlayer.PlayerTE(seed)
            activeTeList.append(newPlayer)
        elif player.position is FloosPlayer.Position.K:
            newPlayer = FloosPlayer.PlayerK(seed)
            activeKList.append(newPlayer)
        
        newPlayer.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
        newPlayer.team = 'Free Agent'
        newPlayer.id = (len(activePlayerList) + len(retiredPlayersList) + 1)
        activePlayerList.append(newPlayer)
        freeAgentList.append(newPlayer)

    if newPlayerCount > len(newlyRetiredPlayersList):
        posList = [FloosPlayer.Position.QB, FloosPlayer.Position.RB, FloosPlayer.Position.WR, FloosPlayer.Position.TE, FloosPlayer.Position.K]
        seed = int(playerAverages.pop(randint(0,len(playerAverages)-1)))
        for x in range(newPlayerCount - len(newlyRetiredPlayersList)):
            r = batched_randint(0, len(posList)-1)
            pos = posList[r]
            player = None
            if pos is FloosPlayer.Position.QB:
                player = FloosPlayer.PlayerQB(seed)
                activeQbList.append(player)
            if pos is FloosPlayer.Position.RB:
                player = FloosPlayer.PlayerRB(seed)
                activeRbList.append(player)
            if pos is FloosPlayer.Position.WR:
                player = FloosPlayer.PlayerWR(seed)
                activeWrList.append(player)
            if pos is FloosPlayer.Position.TE:
                player = FloosPlayer.PlayerTE(seed)
                activeTeList.append(player)
            if pos is FloosPlayer.Position.K:
                player = FloosPlayer.PlayerK(seed)
                activeKList.append(player)

            player.name = unusedNamesList.pop(randint(0,len(unusedNamesList)-1))
            player.team = 'Free Agent'
            player.id = (len(activePlayerList) + len(retiredPlayersList) + 1)
            activePlayerList.append(player)
            freeAgentList.append(player)

    playerManager.saveUnusedNames()
    playerManager.sortPlayersByPosition()

    freeAgentQbList : list[FloosPlayer.Player] = []
    freeAgentRbList : list[FloosPlayer.Player] = []
    freeAgentWrList : list[FloosPlayer.Player] = []
    freeAgentTeList : list[FloosPlayer.Player] = []
    freeAgentKList : list[FloosPlayer.Player] = []

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

    list.sort(freeAgentQbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentRbList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentWrList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentTeList, key=lambda player: player.attributes.skillRating, reverse=True)
    list.sort(freeAgentKList, key=lambda player: player.attributes.skillRating, reverse=True)
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
                
            #await asyncio.sleep(2)

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
    inductHallOfFame()
    
def getPerformanceRating(week):
    baseAdjustmentFactor = .2
    gameFactor = min(1, week / 4)
    effectiveAdjustment = baseAdjustmentFactor * gameFactor

    qbStats = {
        "passComp": [qb.seasonStatsDict['passing']['compPerc'] for qb in activeQbList if qb.seasonStatsDict['passing']['yards'] > 0],
        "passYards": [qb.seasonStatsDict['passing']['yards'] for qb in activeQbList if qb.seasonStatsDict['passing']['yards'] > 0],
        "tds": [qb.seasonStatsDict['passing']['tds'] for qb in activeQbList if qb.seasonStatsDict['passing']['yards'] > 0],
        "ints": [qb.seasonStatsDict['passing']['ints'] for qb in activeQbList if qb.seasonStatsDict['passing']['yards'] > 0]
    }

    for qb in activeQbList:
        if qb.seasonStatsDict['passing']['yards'] > 0:
            compPerc = qb.seasonStatsDict['passing']['compPerc']
            passYards = qb.seasonStatsDict['passing']['yards']
            tds = qb.seasonStatsDict['passing']['tds']
            ints = qb.seasonStatsDict['passing']['ints']

            passCompPercRating = stats.percentileofscore(qbStats["passComp"], compPerc, 'rank')
            passYardsRating = stats.percentileofscore(qbStats["passYards"], passYards, 'rank')
            tdsRating = stats.percentileofscore(qbStats["tds"], tds, 'rank')
            intsRating = 100 - stats.percentileofscore(qbStats["ints"], ints, 'rank')

            weightedScore = round(((passCompPercRating * 1.2) + (passYardsRating * 1.0) + (tdsRating * 1.0) + (intsRating * .8)) / 4)

            qb.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

    qbBaseSkills = [p.attributes.skillRating for p in activeQbList]
    qbPerformances = [p.seasonPerformanceRating for p in activeQbList]

    qbBaseSkillPercentiles = [stats.percentileofscore(qbBaseSkills, x) for x in qbBaseSkills]
    qbPerformancePercentiles = [stats.percentileofscore(qbPerformances, x) for x in qbPerformances]

    for i, player in enumerate(activeQbList):
        player: FloosPlayer.Player
        percentileDifference = qbPerformancePercentiles[i] - qbBaseSkillPercentiles[i]
        adjustment = effectiveAdjustment * percentileDifference
        player.playerRating = round(player.attributes.skillRating + adjustment)

    rbStats = {
        "ypc": [rb.seasonStatsDict['rushing']['ypc'] for rb in activeRbList if rb.seasonStatsDict['rushing']['yards'] > 0],
        "rushYards": [rb.seasonStatsDict['rushing']['yards'] for rb in activeRbList if rb.seasonStatsDict['rushing']['yards'] > 0],
        "tds": [rb.seasonStatsDict['rushing']['tds'] for rb in activeRbList if rb.seasonStatsDict['rushing']['yards'] > 0],
        "fumbles": [rb.seasonStatsDict['rushing']['fumblesLost'] for rb in activeRbList if rb.seasonStatsDict['rushing']['yards'] > 0]
    }

    for rb in activeRbList:
        if rb.seasonStatsDict['rushing']['yards'] > 0:
            ypc = rb.seasonStatsDict['rushing']['ypc']
            rushYards = rb.seasonStatsDict['rushing']['yards']
            tds = rb.seasonStatsDict['rushing']['tds']
            fumbles = rb.seasonStatsDict['rushing']['fumblesLost']

            ypcRating = stats.percentileofscore(rbStats["ypc"], ypc, 'rank')
            rushYardsRating = stats.percentileofscore(rbStats["rushYards"], rushYards, 'rank')
            tdsRating = stats.percentileofscore(rbStats["tds"], tds, 'rank')
            fumblesRating = 100 - stats.percentileofscore(rbStats["fumbles"], fumbles, 'rank')

            weightedScore = ((ypcRating * 1.2) + (rushYardsRating * 1.2) + (tdsRating * 1.0) + (fumblesRating * .6)) / 4

            rb.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

    rbBaseSkills = [p.attributes.skillRating for p in activeRbList]
    rbPerformances = [p.seasonPerformanceRating for p in activeRbList]

    rbBaseSkillPercentiles = [stats.percentileofscore(rbBaseSkills, x) for x in rbBaseSkills]
    rbPerformancePercentiles = [stats.percentileofscore(rbPerformances, x) for x in rbPerformances]

    for i, player in enumerate(activeRbList):
        player: FloosPlayer.Player
        percentileDifference = rbPerformancePercentiles[i] - rbBaseSkillPercentiles[i]
        adjustment = effectiveAdjustment * percentileDifference
        player.playerRating = round(player.attributes.skillRating + adjustment)

    wrStats = {
        "receptions": [wr.seasonStatsDict['receiving']['receptions'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0],
        "drops": [wr.seasonStatsDict['receiving']['drops'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0],
        "rcvPerc": [wr.seasonStatsDict['receiving']['rcvPerc'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0],
        "rcvYards": [wr.seasonStatsDict['receiving']['yards'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0],
        "ypr": [wr.seasonStatsDict['receiving']['ypr'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0],
        "yac": [wr.seasonStatsDict['receiving']['yac'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0],
        "tds": [wr.seasonStatsDict['receiving']['tds'] for wr in activeWrList if wr.seasonStatsDict['receiving']['yards'] > 0]
    }

    for wr in activeWrList:
        if wr.seasonStatsDict['receiving']['yards'] > 0:
            receptions = wr.seasonStatsDict['receiving']['receptions']
            drops = wr.seasonStatsDict['receiving']['drops']
            rcvPerc = wr.seasonStatsDict['receiving']['rcvPerc']
            rcvYards = wr.seasonStatsDict['receiving']['yards']
            ypr = wr.seasonStatsDict['receiving']['ypr']
            yac = wr.seasonStatsDict['receiving']['yac']
            tds = wr.seasonStatsDict['receiving']['tds']

            recRating = stats.percentileofscore(wrStats["ypr"], receptions, 'rank')
            dropsRating = 100 - stats.percentileofscore(wrStats["drops"], drops, 'rank')
            rcvPercRating = stats.percentileofscore(wrStats["rcvPerc"], rcvPerc, 'rank')
            rcvYardsRating = stats.percentileofscore(wrStats["rcvYards"], rcvYards, 'rank')
            yprRating = stats.percentileofscore(wrStats["ypr"], ypr, 'rank')
            yacRating = stats.percentileofscore(wrStats["yac"], yac, 'rank')
            tdsRating = stats.percentileofscore(wrStats["tds"], tds, 'rank')

            weightedScore = ((recRating * .8) + (dropsRating * 1.2) + (rcvPercRating * 1.4) + (rcvYardsRating * 1.0) + (yprRating * 1.0) + (yacRating * 1) + (tdsRating * .6)) / 7

            wr.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

    wrBaseSkills = [p.attributes.skillRating for p in activeWrList]
    wrPerformances = [p.seasonPerformanceRating for p in activeWrList]

    wrBaseSkillPercentiles = [stats.percentileofscore(wrBaseSkills, x) for x in wrBaseSkills]
    wrPerformancePercentiles = [stats.percentileofscore(wrPerformances, x) for x in wrPerformances]

    for i, player in enumerate(activeWrList):
        player: FloosPlayer.Player
        percentileDifference = wrPerformancePercentiles[i] - wrBaseSkillPercentiles[i]
        adjustment = effectiveAdjustment * percentileDifference
        player.playerRating = round(player.attributes.skillRating + adjustment)

    teStats = {
        "receptions": [te.seasonStatsDict['receiving']['receptions'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0],
        "drops": [te.seasonStatsDict['receiving']['drops'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0],
        "rcvPerc": [te.seasonStatsDict['receiving']['rcvPerc'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0],
        "rcvYards": [te.seasonStatsDict['receiving']['yards'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0],
        "ypr": [te.seasonStatsDict['receiving']['ypr'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0],
        "yac": [te.seasonStatsDict['receiving']['yac'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0],
        "tds": [te.seasonStatsDict['receiving']['tds'] for te in activeTeList if te.seasonStatsDict['receiving']['yards'] > 0]
    }

    for te in activeTeList:
        if te.seasonStatsDict['receiving']['yards'] > 0:
            receptions = te.seasonStatsDict['receiving']['receptions']
            drops = te.seasonStatsDict['receiving']['drops']
            rcvPerc = te.seasonStatsDict['receiving']['rcvPerc']
            rcvYards = te.seasonStatsDict['receiving']['yards']
            ypr = te.seasonStatsDict['receiving']['ypr']
            yac = te.seasonStatsDict['receiving']['yac']
            tds = te.seasonStatsDict['receiving']['tds']

            recRating = stats.percentileofscore(teStats["ypr"], receptions, 'rank')
            dropsRating = 100 - stats.percentileofscore(teStats["drops"], drops, 'rank')
            rcvPercRating = stats.percentileofscore(teStats["rcvPerc"], rcvPerc, 'rank')
            rcvYardsRating = stats.percentileofscore(teStats["rcvYards"], rcvYards, 'rank')
            yprRating = stats.percentileofscore(teStats["ypr"], ypr, 'rank')
            yacRating = stats.percentileofscore(teStats["yac"], yac, 'rank')
            tdsRating = stats.percentileofscore(teStats["tds"], tds, 'rank')

            weightedScore = ((recRating * .8) + (dropsRating * 1.2) + (rcvPercRating * 1.4) + (rcvYardsRating * 1.0) + (yprRating * 1.0) + (yacRating * 1) + (tdsRating * .6)) / 7

            te.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

    teBaseSkills = [p.attributes.skillRating for p in activeTeList]
    tePerformances = [p.seasonPerformanceRating for p in activeTeList]

    teBaseSkillPercentiles = [stats.percentileofscore(teBaseSkills, x) for x in teBaseSkills]
    tePerformancePercentiles = [stats.percentileofscore(tePerformances, x) for x in tePerformances]

    for i, player in enumerate(activeTeList):
        player: FloosPlayer.Player
        percentileDifference = tePerformancePercentiles[i] - teBaseSkillPercentiles[i]
        adjustment = effectiveAdjustment * percentileDifference
        player.playerRating = round(player.attributes.skillRating + adjustment)

    kStats = {
        "fgPerc": [k.seasonStatsDict['kicking']['fgPerc'] for k in activeKList if k.seasonStatsDict['kicking']['fgPerc'] > 0],
        "fgs": [k.seasonStatsDict['kicking']['fgs'] for k in activeKList if k.seasonStatsDict['kicking']['fgs'] > 0],
        "fgAvg": [k.seasonStatsDict['kicking']['fgAvg'] for k in activeKList if k.seasonStatsDict['kicking']['fgAvg'] > 0]
    }

    for k in activeKList:
        if k.seasonStatsDict['kicking']['fgs'] > 0:
            fgPerc = k.seasonStatsDict['kicking']['fgPerc']
            fgs = k.seasonStatsDict['kicking']['fgs']
            fgAvg = k.seasonStatsDict['kicking']['fgAvg']

            fgPercRating = stats.percentileofscore(kStats["fgPerc"], fgPerc, 'rank')
            fgsRating = stats.percentileofscore(kStats["fgs"], fgs, 'rank')
            fgAvgRating = stats.percentileofscore(kStats["fgAvg"], fgAvg, 'rank')

            weightedScore = ((fgPercRating * 1.3) + (fgsRating * .7) + (fgAvgRating * 1)) / 3

            k.seasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

    kBaseSkills = [p.attributes.skillRating for p in activeKList]
    kPerformances = [p.seasonPerformanceRating for p in activeKList]

    kBaseSkillPercentiles = [stats.percentileofscore(kBaseSkills, x) for x in kBaseSkills]
    kPerformancePercentiles = [stats.percentileofscore(kPerformances, x) for x in kPerformances]

    for i, player in enumerate(activeKList):
        player: FloosPlayer.Player
        percentileDifference = kPerformancePercentiles[i] - kBaseSkillPercentiles[i]
        adjustment = effectiveAdjustment * percentileDifference
        player.playerRating = round(player.attributes.skillRating + adjustment)


    defStats = {
        "runYardsAlwd": [team.seasonTeamStats['Defense']['runYardsAlwd'] for team in teamList],
        "runTdsAlwd": [team.seasonTeamStats['Defense']['runTdsAlwd'] for team in teamList],
        "passYardsAlwd": [team.seasonTeamStats['Defense']['passYardsAlwd'] for team in teamList],
        "passTdsAlwd": [team.seasonTeamStats['Defense']['passTdsAlwd'] for team in teamList],
        "ints": [team.seasonTeamStats['Defense']['ints'] for team in teamList],
        "sacks": [team.seasonTeamStats['Defense']['sacks'] for team in teamList],
        "fumRec": [team.seasonTeamStats['Defense']['fumRec'] for team in teamList],
        "safeties": [team.seasonTeamStats['Defense']['safeties'] for team in teamList],
        "totalYardsAlwd": [team.seasonTeamStats['Defense']['totalYardsAlwd'] for team in teamList],
        "ptsAlwd": [team.seasonTeamStats['Defense']['ptsAlwd'] for team in teamList]
    }

    for team in teamList:
        team: FloosTeam.Team
        runYardsAlwd = team.seasonTeamStats['Defense']['runYardsAlwd']
        runTdsAlwd = team.seasonTeamStats['Defense']['runTdsAlwd']
        passYardsAlwd = team.seasonTeamStats['Defense']['passYardsAlwd']
        passTdsAlwd = team.seasonTeamStats['Defense']['passTdsAlwd']
        ints = team.seasonTeamStats['Defense']['ints']
        sacks = team.seasonTeamStats['Defense']['sacks']
        fumRec = team.seasonTeamStats['Defense']['fumRec']
        safeties = team.seasonTeamStats['Defense']['safeties']
        totalYardsAlwd = team.seasonTeamStats['Defense']['totalYardsAlwd']
        ptsAlwd = team.seasonTeamStats['Defense']['ptsAlwd']

        runYardsAlwdRating = 100 - stats.percentileofscore(defStats["runYardsAlwd"], runYardsAlwd, 'rank')
        runTdsAlwdRating = 100 - stats.percentileofscore(defStats["runTdsAlwd"], runTdsAlwd, 'rank')
        passYardsAlwdRating = 100 - stats.percentileofscore(defStats["passYardsAlwd"], passYardsAlwd, 'rank')
        passTdsAlwdRating = 100 - stats.percentileofscore(defStats["passTdsAlwd"], passTdsAlwd, 'rank')
        intsRating = stats.percentileofscore(defStats["ints"], ints, 'rank')
        sacksRating = stats.percentileofscore(defStats["sacks"], sacks, 'rank')
        fumRecRating = stats.percentileofscore(defStats["fumRec"], fumRec, 'rank')
        safetiesRating = stats.percentileofscore(defStats["safeties"], safeties, 'rank')
        totalYardsAlwdRating = 100 - stats.percentileofscore(defStats["totalYardsAlwd"], totalYardsAlwd, 'rank')
        ptsAlwdRating = 100 - stats.percentileofscore(defStats["ptsAlwd"], ptsAlwd, 'rank')

        runDefWeightedScore = ((runYardsAlwdRating * 1.2) + (runTdsAlwdRating * .8)) / 2
        passDefWeightedScore = ((passYardsAlwdRating * 1.4) + (passTdsAlwdRating * 1) + (intsRating * 1) + (sacksRating * .6)) / 4
        generalDefWeightedScore = ((fumRecRating * .6) + (safetiesRating * .4) + (totalYardsAlwdRating * 1.4) + (ptsAlwdRating * 1.6)) / 4

        team.defenseRunCoverageSeasonPerformanceRating = np.clip(round(runDefWeightedScore), 60, 100)
        team.defensePassCoverageSeasonPerformanceRating = np.clip(round(passDefWeightedScore), 60, 100)
        generalDefSeasonPerformanceRating = np.clip(round(generalDefWeightedScore), 60, 100)

        weightedScore = round(np.mean([team.defenseRunCoverageSeasonPerformanceRating, team.defensePassCoverageSeasonPerformanceRating, generalDefSeasonPerformanceRating]))
        
        team.defenseSeasonPerformanceRating = round(FloosMethods.scaleValue(weightedScore, 60, 100, 0, 100))

    defBaseSkills = [t.defenseRating for t in teamList]
    defPerformances = [t.defenseSeasonPerformanceRating for t in teamList]

    defBaseSkillPercentiles = [stats.percentileofscore(defBaseSkills, x) for x in defBaseSkills]
    defPerformancePercentiles = [stats.percentileofscore(defPerformances, x) for x in defPerformances]

    for i, team in enumerate(teamList):
        team: FloosTeam.Team
        percentileDifference = defPerformancePercentiles[i] - defBaseSkillPercentiles[i]
        adjustment = effectiveAdjustment * percentileDifference
        team.defenseOverallTier = round(team.defenseRating + adjustment)
    

    list.sort(activeQbList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeRbList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeWrList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeTeList, key=lambda player: player.seasonPerformanceRating, reverse=True)
    list.sort(activeKList, key=lambda player: player.seasonPerformanceRating, reverse=True)


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
    
    # Initialize service container at application startup
    from service_container import initializeServices, setGameState, getGameState, loadGameConfig, getService
    initializeServices()
    
    # Initialize default game state values
    setGameState('cap', 0)
    setGameState('totalSeasons', 0)
    setGameState('seasonsPlayed', 0)
    setGameState('seasonList', [])
    setGameState('activeSeason', None)
    
    # Initialize PlayerManager
    global playerManager
    playerManager = PlayerManager(getService('game_state'))
    
    # Set up backward compatibility - global variables now reference PlayerManager
    global activePlayerList, freeAgentList, retiredPlayersList, hallOfFame
    global activeQbList, activeRbList, activeWrList, activeTeList, activeKList
    global rookieDraftList, newlyRetiredPlayersList
    
    activePlayerList = playerManager.activePlayers
    freeAgentList = playerManager.freeAgents  
    retiredPlayersList = playerManager.retiredPlayers
    hallOfFame = playerManager.hallOfFame
    rookieDraftList = playerManager.rookieDraftList
    newlyRetiredPlayersList = playerManager.newlyRetiredPlayers
    
    activeQbList = playerManager.activeQbs
    activeRbList = playerManager.activeRbs
    activeWrList = playerManager.activeWrs
    activeTeList = playerManager.activeTes
    activeKList = playerManager.activeKs

    main_logger.info('Floosball v{}'.format(__version__))
    #print('Reading config...')
    config = get_config()
    loadGameConfig(config)
    
    # Use service container for cleaner config access
    from service_container import update_game_state, get_nested_game_config
    cap = get_nested_game_config('leagueConfig', 'cap')
    totalSeasons = get_nested_game_config('leagueConfig', 'totalSeasons')
    deleteDataOnStart = get_nested_game_config('leagueConfig', 'deleteDataOnRestart')
    saveSeasonProgress = get_nested_game_config('leagueConfig', 'saveSeasonProgress')
    
    # Use update_state for more efficient batch updates
    update_game_state({
        'cap': cap,
        'totalSeasons': totalSeasons
    })
    #print('Config done')

    if saveSeasonProgress:
        #print('Save Season Progress enabled')
        seasonsPlayed = get_nested_game_config('leagueConfig', 'lastSeason')
        totalSeasons += seasonsPlayed
        # Use batch update for better performance
        update_game_state({
            'seasonsPlayed': seasonsPlayed,
            'totalSeasons': totalSeasons
        })

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
    playerManager.generatePlayers(config)
    #print('Player creation done')
    #print('Creating teams...')
    getTeams(config)
    #print('Team creation done')
    
    # Store team list in service container for PlayerManager access
    setGameState('teamList', teamList)

    if not os.path.exists("data/teamData"):
        #print('Starting player draft...')
        playerManager.conductInitialDraft()
        #print('Draft complete')
    else:
        main_logger.info('Skipping draft')

    #print('Initializing teams...')
    initTeams()
    #print('Cleaning up players...')
    #initPlayers()
    #print('Saving player data...')
    playerManager.savePlayerData()
    #print('Creating divisions...')
    getLeagues(config)
    if not os.path.exists("data/leagueData.json"):
        initLeagues()

    main_logger.info('Initialization complete!')
    while seasonsPlayed < totalSeasons:
        main_logger.info('Season {} start'.format(seasonsPlayed+1))
        setNewElo()
        activeSeason = Season()
        seasonList.append(activeSeason)
        # Use batch update for season state
        update_game_state({
            'activeSeason': activeSeason,
            'seasonList': seasonList
        })
        activeSeason.createSchedule()
        await activeSeason.startSeason()
        seasonsPlayed += 1
        setGameState('seasonsPlayed', seasonsPlayed)

        if saveSeasonProgress:
            #print('Updating config after season end...')
            save_config_value(seasonsPlayed, 'leagueConfig', 'lastSeason')
        #await asyncio.sleep(30)
        await offseason()
        #await asyncio.sleep(120)
        activeSeason.clearPlayerSeasonStats()
        activeSeason.clearTeamSeasonStats()