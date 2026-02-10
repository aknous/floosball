"""
RecordManager - Centralized record tracking for Floosball

Handles all record checking and updating for player and team records across
game, season, and career categories. Replaces scattered record management 
functions from floosball.py
"""

from typing import Dict, Any
import floosball_player as FloosPlayer
import floosball_team as FloosTeam
from logger_config import getLogger

class RecordManager:
    """Manages all record tracking operations for players and teams"""
    
    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        self.logger = getLogger("floosball.record_manager")
        self._records = None  # Lazy initialization
        self._championshipRecords: list[Dict[str, Any]] = []  # Placeholder for championship records if needed
    
    def _initializeRecordStructure(self) -> Dict[str, Any]:
        """Initialize the complete record structure - moved from floosball.py"""
        return {
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
                'fantasy': {
                    'game': {
                        'qb': {
                            'record': 'QB Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'rb': {
                            'record': 'RB Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'wr': {
                            'record': 'WR Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'te': {
                            'record': 'TE Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'k': {
                            'record': 'K Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        }
                    },
                    'season': {
                        'qb': {
                            'record': 'QB Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0,
                            'season': 0
                        },
                        'rb': {
                            'record': 'RB Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0,
                            'season': 0
                        },
                        'wr': {
                            'record': 'WR Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0,
                            'season': 0
                        },
                        'te': {
                            'record': 'TE Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0,
                            'season': 0
                        },
                        'k': {
                            'record': 'K Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0,
                            'season': 0
                        }
                    },
                    'career': {
                        'qb': {
                            'record': 'QB Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'rb': {
                            'record': 'RB Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'wr': {
                            'record': 'WR Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'te': {
                            'record': 'TE Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        },
                        'k': {
                            'record': 'K Fantasy Points',
                            'name': None,
                            'id': 0,
                            'value': 0
                        }
                    }
                },
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
    
    def getRecords(self) -> Dict[str, Any]:
        """Get the records dictionary - public accessor method"""
        if self._records is None:
            self._records = self._initializeRecordStructure()
        return self._records
    
    def setRecords(self, records: Dict[str, Any]) -> None:
        """Set the records dictionary - for loading from persistence"""
        self._records = records
    
    def loadRecordsFromFile(self, filePath: str = "data/allTimeRecords.json") -> None:
        """Load records from JSON file and ensure complete structure"""
        import json
        import os
        
        try:
            if os.path.exists(filePath):
                with open(filePath, 'r') as f:
                    loaded_records = json.load(f)
                
                # Get the complete structure template
                complete_structure = self._initializeRecordStructure()
                
                # Merge loaded records with complete structure to fill any missing sections
                self._records = self._mergeRecordStructures(complete_structure, loaded_records)
                
                self.logger.info(f"Loaded records from {filePath} and validated structure")
            else:
                self._records = self._initializeRecordStructure()
                self.logger.info("Initialized new record structure")
        except Exception as e:
            self.logger.error(f"Failed to load records from {filePath}: {e}")
            self._records = self._initializeRecordStructure()
    
    def _mergeRecordStructures(self, complete: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge loaded records with complete structure to fill missing sections"""
        result = complete.copy()
        
        for key, value in loaded.items():
            if key in result:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    # Recursively merge nested dictionaries
                    result[key] = self._mergeRecordStructures(result[key], value)
                else:
                    # Use the loaded value
                    result[key] = value
            else:
                # Add new key from loaded data
                result[key] = value
        
        return result
    
    def saveRecordsToFile(self, filePath: str = "data/allTimeRecords.json") -> None:
        """Save records to JSON file"""
        import json
        import os
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filePath), exist_ok=True)
            
            with open(filePath, 'w') as f:
                json.dump(self.getRecords(), f, indent=4)
            self.logger.info(f"Saved records to {filePath}")
        except Exception as e:
            self.logger.error(f"Failed to save records to {filePath}: {e}")
    
    def resetRecords(self) -> None:
        """Reset all records to initial state"""
        self._records = self._initializeRecordStructure()
        self.logger.info("Reset all records to initial state")
    
    def getRecordStatistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about current records"""
        records = self.getRecords()
        
        def count_records(section: Dict[str, Any]) -> int:
            count = 0
            for key, value in section.items():
                if isinstance(value, dict):
                    if 'value' in value and value['value'] > 0:
                        count += 1
                    else:
                        count += count_records(value)
            return count
        
        player_records = count_records(records.get('players', {}))
        team_records = count_records(records.get('team', {}))
        
        return {
            'totalPlayerRecords': player_records,
            'totalTeamRecords': team_records,
            'totalRecords': player_records + team_records,
            'hasRecords': player_records > 0 or team_records > 0
        }
        
    def processPostGameStats(self, gameInstance) -> None:
        """
        Process all post-game statistics for teams and players.
        Replaces the large postgame() method from floosball_game.py
        """
        if not hasattr(gameInstance, 'isRegularSeasonGame'):
            self.logger.warning("Game instance missing isRegularSeasonGame attribute")
            return
            
        self.logger.debug(f"Processing post-game stats for {gameInstance.homeTeam.name} vs {gameInstance.awayTeam.name}")
        
        # Only process season stats for regular season games
        if gameInstance.isRegularSeasonGame:
            self._updateTeamSeasonStats(gameInstance)
            self._updatePlayerSeasonStats(gameInstance)
            self._updateWinStreaks(gameInstance)
        
        # Always update career stats for all games
        self._updatePlayerCareerStats(gameInstance)
        
        self.logger.debug("Post-game stat processing complete")
    
    def _updateTeamSeasonStats(self, gameInstance) -> None:
        """Update team season statistics from game results (matches original postgame exactly)"""
        try:
            homeTeam: FloosTeam.Team = gameInstance.homeTeam
            awayTeam: FloosTeam.Team = gameInstance.awayTeam

            # Home team offensive stats (lines 1226-1236)
            homeTeam.seasonTeamStats['Offense']['pts'] += gameInstance.homeScore
            homeTeam.seasonTeamStats['Offense']['runTds'] += homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds']
            homeTeam.seasonTeamStats['Offense']['passTds'] += homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds']
            homeTeam.seasonTeamStats['Offense']['tds'] += (homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
            homeTeam.seasonTeamStats['Offense']['fgs'] += homeTeam.rosterDict['k'].gameStatsDict['kicking']['fgs']
            homeTeam.seasonTeamStats['Offense']['passYards'] += homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards']
            homeTeam.seasonTeamStats['Offense']['runYards'] += homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards']
            homeTeam.seasonTeamStats['Offense']['totalYards'] += (homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
            homeScoreDiff = gameInstance.homeScore - homeTeam.gameDefenseStats['ptsAlwd']
            homeTeam.seasonTeamStats['scoreDiff'] += homeScoreDiff

            # Away team offensive stats (lines 1238-1248)
            awayTeam.seasonTeamStats['Offense']['pts'] += gameInstance.awayScore
            awayTeam.seasonTeamStats['Offense']['runTds'] += awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds']
            awayTeam.seasonTeamStats['Offense']['passTds'] += awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds']
            awayTeam.seasonTeamStats['Offense']['tds'] += (awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
            awayTeam.seasonTeamStats['Offense']['fgs'] += awayTeam.rosterDict['k'].gameStatsDict['kicking']['fgs']
            awayTeam.seasonTeamStats['Offense']['passYards'] += awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards']
            awayTeam.seasonTeamStats['Offense']['runYards'] += awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards']
            awayTeam.seasonTeamStats['Offense']['totalYards'] += (awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
            awayScoreDiff = gameInstance.awayScore - awayTeam.gameDefenseStats['ptsAlwd']
            awayTeam.seasonTeamStats['scoreDiff'] += awayScoreDiff

            # Winning team defensive stats (lines 1258-1269)
            winningTeam: FloosTeam.Team = gameInstance.winningTeam
            winningTeam.seasonTeamStats['Defense']['ints'] += winningTeam.gameDefenseStats['ints']
            winningTeam.seasonTeamStats['Defense']['fumRec'] += winningTeam.gameDefenseStats['fumRec']
            winningTeam.seasonTeamStats['Defense']['sacks'] += winningTeam.gameDefenseStats['sacks']
            winningTeam.seasonTeamStats['Defense']['safeties'] += winningTeam.gameDefenseStats['safeties']
            winningTeam.seasonTeamStats['Defense']['runYardsAlwd'] += winningTeam.gameDefenseStats['runYardsAlwd']
            winningTeam.seasonTeamStats['Defense']['passYardsAlwd'] += winningTeam.gameDefenseStats['passYardsAlwd']
            winningTeam.seasonTeamStats['Defense']['totalYardsAlwd'] += winningTeam.gameDefenseStats['totalYardsAlwd']
            winningTeam.seasonTeamStats['Defense']['runTdsAlwd'] += winningTeam.gameDefenseStats['runTdsAlwd']
            winningTeam.seasonTeamStats['Defense']['passTdsAlwd'] += winningTeam.gameDefenseStats['passTdsAlwd']
            winningTeam.seasonTeamStats['Defense']['tdsAlwd'] += winningTeam.gameDefenseStats['tdsAlwd']
            winningTeam.seasonTeamStats['Defense']['ptsAlwd'] += winningTeam.gameDefenseStats['ptsAlwd']
            winningTeam.seasonTeamStats['winPerc'] = round(winningTeam.seasonTeamStats['wins']/(winningTeam.seasonTeamStats['wins']+winningTeam.seasonTeamStats['losses']),3)

            # Losing team defensive stats (lines 1281-1292)
            losingTeam: FloosTeam.Team = gameInstance.losingTeam
            losingTeam.seasonTeamStats['Defense']['ints'] += losingTeam.gameDefenseStats['ints']
            losingTeam.seasonTeamStats['Defense']['fumRec'] += losingTeam.gameDefenseStats['fumRec']
            losingTeam.seasonTeamStats['Defense']['sacks'] += losingTeam.gameDefenseStats['sacks']
            losingTeam.seasonTeamStats['Defense']['safeties'] += losingTeam.gameDefenseStats['safeties']
            losingTeam.seasonTeamStats['Defense']['runYardsAlwd'] += losingTeam.gameDefenseStats['runYardsAlwd']
            losingTeam.seasonTeamStats['Defense']['passYardsAlwd'] += losingTeam.gameDefenseStats['passYardsAlwd']
            losingTeam.seasonTeamStats['Defense']['totalYardsAlwd'] += losingTeam.gameDefenseStats['totalYardsAlwd']
            losingTeam.seasonTeamStats['Defense']['runTdsAlwd'] += losingTeam.gameDefenseStats['runTdsAlwd']
            losingTeam.seasonTeamStats['Defense']['passTdsAlwd'] += losingTeam.gameDefenseStats['passTdsAlwd']
            losingTeam.seasonTeamStats['Defense']['tdsAlwd'] += losingTeam.gameDefenseStats['tdsAlwd']
            losingTeam.seasonTeamStats['Defense']['ptsAlwd'] += losingTeam.gameDefenseStats['ptsAlwd']
            losingTeam.seasonTeamStats['winPerc'] = round(losingTeam.seasonTeamStats['wins']/(losingTeam.seasonTeamStats['wins']+losingTeam.seasonTeamStats['losses']),3)
            
            # Defensive fantasy points calculation (lines 1295-1319)
            # Home team defensive fantasy points
            if homeTeam.gameDefenseStats['ptsAlwd'] >= 35:
                homeTeam.gameDefenseStats['fantasyPoints'] += -4
            elif homeTeam.gameDefenseStats['ptsAlwd'] >= 28 and homeTeam.gameDefenseStats['ptsAlwd'] < 35:
                homeTeam.gameDefenseStats['fantasyPoints'] += -1
            elif homeTeam.gameDefenseStats['ptsAlwd'] >= 14 and homeTeam.gameDefenseStats['ptsAlwd'] <= 21:
                homeTeam.gameDefenseStats['fantasyPoints'] += 1
            elif homeTeam.gameDefenseStats['ptsAlwd'] >= 7 and homeTeam.gameDefenseStats['ptsAlwd'] <= 13:
                homeTeam.gameDefenseStats['fantasyPoints'] += 4
            elif homeTeam.gameDefenseStats['ptsAlwd'] >= 1 and homeTeam.gameDefenseStats['ptsAlwd'] <= 6:
                homeTeam.gameDefenseStats['fantasyPoints'] += 7
            elif homeTeam.gameDefenseStats['ptsAlwd'] == 0:
                homeTeam.gameDefenseStats['fantasyPoints'] += 10

            # Away team defensive fantasy points
            if awayTeam.gameDefenseStats['ptsAlwd'] >= 35:
                awayTeam.gameDefenseStats['fantasyPoints'] += -4
            elif awayTeam.gameDefenseStats['ptsAlwd'] >= 28 and awayTeam.gameDefenseStats['ptsAlwd'] < 35:
                awayTeam.gameDefenseStats['fantasyPoints'] += -1
            elif awayTeam.gameDefenseStats['ptsAlwd'] >= 14 and awayTeam.gameDefenseStats['ptsAlwd'] <= 21:
                awayTeam.gameDefenseStats['fantasyPoints'] += 1
            elif awayTeam.gameDefenseStats['ptsAlwd'] >= 7 and awayTeam.gameDefenseStats['ptsAlwd'] <= 13:
                awayTeam.gameDefenseStats['fantasyPoints'] += 4
            elif awayTeam.gameDefenseStats['ptsAlwd'] >= 1 and awayTeam.gameDefenseStats['ptsAlwd'] <= 6:
                awayTeam.gameDefenseStats['fantasyPoints'] += 7
            elif awayTeam.gameDefenseStats['ptsAlwd'] == 0:
                awayTeam.gameDefenseStats['fantasyPoints'] += 10
            
        except Exception as e:
            self.logger.error(f"Error updating team season stats: {e}")
    
    def _updateWinStreaks(self, gameInstance) -> None:
        """Update win/loss streaks for teams (matches original lines 1250-1279)"""
        try:
            winningTeam: FloosTeam.Team = gameInstance.winningTeam
            losingTeam: FloosTeam.Team = gameInstance.losingTeam

            if not winningTeam or not losingTeam:
                return
            
            # Update winning streak (lines 1250-1256)
            if winningTeam.seasonTeamStats['streak'] >= 0:
                winningTeam.seasonTeamStats['streak'] += 1
                if winningTeam.seasonTeamStats['streak'] > 3 and not winningTeam.winningStreak:
                    winningTeam.winningStreak = True
                    # Add league highlight for hot streak
                    if hasattr(gameInstance, 'leagueHighlights'):
                        gameInstance.leagueHighlights.insert(0, {
                            'event': {'text': f'{winningTeam.city} {winningTeam.name} are on a hot streak!'}
                        })
            else:
                winningTeam.seasonTeamStats['streak'] = 1

            # Update losing streak (lines 1272-1279)
            if losingTeam.seasonTeamStats['streak'] >= 0:
                losingTeam.seasonTeamStats['streak'] = -1
                if losingTeam.winningStreak:
                    losingTeam.winningStreak = False
                    # Add league highlight for ended streak
                    if hasattr(gameInstance, 'leagueHighlights'):
                        gameInstance.leagueHighlights.insert(0, {
                            'event': {'text': f'{winningTeam.city} {winningTeam.name} ended the {losingTeam.city} {losingTeam.name} hot streak!'}
                        })
            else:
                losingTeam.seasonTeamStats['streak'] -= 1
                
        except Exception as e:
            self.logger.error(f"Error updating win streaks: {e}")
    
    def _updatePlayerSeasonStats(self, gameInstance) -> None:
        """Update player season statistics from game results"""
        try:
            # Process both teams
            for team in [gameInstance.homeTeam, gameInstance.awayTeam]:
                if not hasattr(team, 'rosterDict'):
                    continue
                    
                for position, player in team.rosterDict.items():
                    if player is None or not hasattr(player, 'gameStatsDict'):
                        continue
                    
                    self._accumulatePlayerSeasonStats(player, position)
                    
        except Exception as e:
            self.logger.error(f"Error updating player season stats: {e}")

    def _accumulatePlayerSeasonStats(self, player: FloosPlayer.Player, position: str) -> None:
        """Accumulate game stats into season stats for a player"""
        try:
            if not hasattr(player, 'seasonStatsDict'):
                player.seasonStatsDict = {}
            
            gameStats = player.gameStatsDict
            seasonStats = player.seasonStatsDict
            
            # Note: postgameChanges() is already called in floosball_game.py after each game
            # Accumulate stats based on position - this is a simplified version
            # The full implementation would mirror the original postgame() logic

            player.seasonStatsDict['fantasyPoints'] += player.gameStatsDict['fantasyPoints']
            if position == 'qb' and 'passing' in gameStats:
                if 'passing' not in seasonStats:
                    seasonStats['passing'] = {
                            'att': 0, 
                            'comp': 0, 
                            'compPerc': 0, 
                            'missedPass': 0,
                            'tds': 0, 
                            'ints': 0, 
                            'yards': 0, 
                            'ypc': 0, 
                            '20+': 0,
                            'longest': 0
                        }
                
                if player.gameStatsDict['passing']['att'] > 0:
                    passing = seasonStats['passing']
                    gamePassing = gameStats['passing']
                    if gamePassing['comp'] > 0:
                        gamePassing['ypc'] = round(gamePassing['yards']/gamePassing['comp'], 2)
                        gamePassing['compPerc'] = round((gamePassing['comp']/gamePassing['att'])*100)

                    # Use .get() for backwards compatibility with old player data
                    passing['20+'] = passing.get('20+', 0) + gamePassing.get('20+', 0)

                    if gamePassing.get('longest', 0) > passing.get('longest', 0):
                        passing['longest'] = gamePassing['longest']

                    if passing['comp'] > 0:
                        passing['ypc'] = round(passing['yards']/passing['comp'], 2)
                        passing['compPerc'] = round((passing['comp']/passing['att'])*100)

            if position == 'wr' and 'receiving' in gameStats:
                if 'receiving' not in seasonStats:
                    seasonStats['receiving'] = {
                            'receptions': 0, 
                            'targets': 0, 
                            'rcvPerc': 0, 
                            'drops': 0,
                            'yards': 0,
                            'yac': 0, 
                            'ypr': 0, 
                            'tds': 0,
                            '20+': 0,
                            'longest': 0
                        }
                if player.gameStatsDict['receiving']['receptions'] > 0:
                    receiving = seasonStats['receiving']
                    gameReceiving = gameStats['receiving']
                    if gameReceiving['yards'] > 0:
                        gameReceiving['ypr'] = round(gameReceiving['yards']/gameReceiving['receptions'],2)
                        gameReceiving['rcvPerc'] = round((gameReceiving['receptions']/gameReceiving['targets'])*100)

                    # Use .get() for backwards compatibility with old player data
                    receiving['20+'] = receiving.get('20+', 0) + gameReceiving.get('20+', 0)

                    if gameReceiving.get('longest', 0) > receiving.get('longest', 0):
                        receiving['longest'] = gameReceiving['longest']

                    if receiving['yards'] > 0:
                        receiving['ypr'] = round(receiving['yards']/receiving['receptions'],2)
                        receiving['rcvPerc'] = round((receiving['receptions']/receiving['targets'])*100)

            if position == 'rb' and 'rushing' in gameStats:
                if 'rushing' not in seasonStats:
                    seasonStats['rushing'] = {
                            'carries': 0,
                            'yards': 0, 
                            'ypc': 0, 
                            'tds': 0, 
                            'fumblesLost': 0, 
                            '20+': 0,
                            'longest': 0
                        }
                if player.gameStatsDict['rushing']['carries'] > 0:
                    rushing = seasonStats['rushing']
                    gameRushing = gameStats['rushing']
                    gameRushing['ypc'] = round(gameRushing['yards']/gameRushing['carries'],2)

                    # Use .get() for backwards compatibility with old player data
                    rushing['20+'] = rushing.get('20+', 0) + gameRushing.get('20+', 0)

                    if gameRushing.get('longest', 0) > rushing.get('longest', 0):
                        rushing['longest'] = gameRushing['longest']

                    if rushing['carries'] > 0:
                        rushing['ypc'] = round(rushing['yards']/rushing['carries'],2)

            if position == 'k' and 'kicking' in gameStats:
                if 'kicking' not in seasonStats:
                    seasonStats['kicking'] = {
                            'fgAtt': 0, 
                            'fgs': 0, 
                            'fgPerc': 0,
                            'fgYards': 0,
                            'fgAvg': 0,
                            'fg45+': 0,
                            'fgUnder20att': 0,
                            'fgUnder20': 0,
                            'fgUnder20perc': 0,
                            'fg20to40att': 0,
                            'fg20to40': 0,
                            'fg20to40perc': 0,
                            'fg40to50att': 0,
                            'fg40to50': 0,
                            'fg40to50perc': 0,
                            'fgOver50att': 0,
                            'fgOver50': 0,
                            'fgOver50perc': 0,
                            'longest': 0
                        }
                if player.gameStatsDict['kicking']['fgAtt'] > 0:
                    kicking = seasonStats['kicking']
                    gameKicking = gameStats['kicking']
                    if gameKicking['fgs'] > 0:
                        gameKicking['fgPerc'] = round((gameKicking['fgs']/gameKicking['fgAtt'])*100)
                    else:
                        gameKicking['fgPerc'] = 0

                    # Use .get() for backwards compatibility with old player data
                    if gameKicking.get('longest', 0) > kicking.get('longest', 0):
                        kicking['longest'] = gameKicking['longest']

                    if kicking['fgs'] > 0:
                        kicking['fgPerc'] = round((kicking['fgs']/kicking['fgAtt'])*100)
                        kicking['fgAvg'] = round(kicking['fgYards']/kicking['fgs'])

                        if kicking['fgUnder20att'] > 0:
                            kicking['fgUnder20perc'] = round((kicking['fgUnder20']/kicking['fgUnder20att'])*100)
                        else:
                            kicking['fgUnder20perc'] = 'N/A'

                        if kicking['fg20to40att'] > 0:
                            kicking['fg20to40perc'] = round((kicking['fg20to40']/kicking['fg20to40att'])*100)
                        else:
                            kicking['fg20to40perc'] = 'N/A'

                        if kicking['fg40to50att'] > 0:
                            kicking['fg40to50perc'] = round((kicking['fg40to50']/kicking['fg40to50att'])*100)
                        else:
                            kicking['fg40to50perc'] = 'N/A'

                        if kicking['fgOver50att'] > 0:
                            kicking['fgOver50perc'] = round((kicking['fgOver50']/kicking['fgOver50att'])*100)
                        else:
                            kicking['fgOver50perc'] = 'N/A'

                    else:
                        kicking['fgPerc'] = 0

        except Exception as e:
            self.logger.error(f"Error accumulating season stats for player {player.name}: {e}")
    
    def _updatePlayerCareerStats(self, gameInstance) -> None:
        """Update career statistics for all players in the game"""
        # Similar to season stats but accumulate into career totals
        # Implementation would depend on how career stats are structured
        pass
    
    def checkPlayerGameRecords(self, allTimeRecordsDict: Dict[str, Any] = None) -> None:
        """
        Check and update player game records
        Replaces checkPlayerGameRecords() function from floosball.py
        """
        # Use internal records if no external dict provided
        if allTimeRecordsDict is None:
            allTimeRecordsDict = self.getRecords()
            
        activePlayerList = self.serviceContainer.getService('player_manager').activePlayers
        
        for player in activePlayerList:
            self._checkPassingGameRecords(player, allTimeRecordsDict)
            self._checkRushingGameRecords(player, allTimeRecordsDict)
            self._checkReceivingGameRecords(player, allTimeRecordsDict)
            self._checkKickingGameRecords(player, allTimeRecordsDict)
            self._checkDefenseGameRecords(player, allTimeRecordsDict)
            # Fantasy records were in original - need position-based logic
            self._checkFantasyGameRecords(player, allTimeRecordsDict)
            
    def _checkPassingGameRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check passing game records for a player"""
        passing_stats = player.gameStatsDict['passing']
        passing_records = records['players']['passing']['game']
        
        if passing_stats['att'] > 0:
            # Completions
            if passing_stats['comp'] > passing_records['comps']['value']:
                passing_records['comps'].update({
                    'value': passing_stats['comp'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Passing yards
            if passing_stats['yards'] > passing_records['yards']['value']:
                passing_records['yards'].update({
                    'value': passing_stats['yards'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Passing TDs
            if passing_stats['tds'] > passing_records['tds']['value']:
                passing_records['tds'].update({
                    'value': passing_stats['tds'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Interceptions
            if passing_stats['ints'] > passing_records['ints']['value']:
                passing_records['ints'].update({
                    'value': passing_stats['ints'],
                    'name': player.name,
                    'id': player.id
                })
                
    def _checkRushingGameRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check rushing game records for a player"""
        rushing_stats = player.gameStatsDict['rushing']
        rushing_records = records['players']['rushing']['game']
        
        if rushing_stats.get('carries', 0) > 0:  # Original used 'carries', not 'att'
            # Rushing yards
            if rushing_stats['yards'] > rushing_records['yards']['value']:
                rushing_records['yards'].update({
                    'value': rushing_stats['yards'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Rushing TDs
            if rushing_stats['tds'] > rushing_records['tds']['value']:
                rushing_records['tds'].update({
                    'value': rushing_stats['tds'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Fumbles lost (missing from original implementation)
            if rushing_stats.get('fumblesLost', 0) > rushing_records.get('fumbles', {}).get('value', 0):
                if 'fumbles' not in rushing_records:
                    rushing_records['fumbles'] = {'value': 0, 'name': '', 'id': 0}
                rushing_records['fumbles'].update({
                    'value': rushing_stats.get('fumblesLost', 0),
                    'name': player.name,
                    'id': player.id
                })
                
    def _checkReceivingGameRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check receiving game records for a player"""
        receiving_stats = player.gameStatsDict['receiving']
        receiving_records = records['players']['receiving']['game']
        
        if receiving_stats.get('receptions', 0) > 0:  # Original used 'receptions', not 'targets'
            # Receptions
            if receiving_stats['receptions'] > receiving_records['receptions']['value']:
                receiving_records['receptions'].update({
                    'value': receiving_stats['receptions'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Receiving yards
            if receiving_stats['yards'] > receiving_records['yards']['value']:
                receiving_records['yards'].update({
                    'value': receiving_stats['yards'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Receiving TDs
            if receiving_stats['tds'] > receiving_records['tds']['value']:
                receiving_records['tds'].update({
                    'value': receiving_stats['tds'],
                    'name': player.name,
                    'id': player.id
                })
                
    def _checkKickingGameRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check kicking game records for a player"""
        kicking_stats = player.gameStatsDict['kicking']
        kicking_records = records['players']['kicking']['game']
        
        if kicking_stats.get('fgs', 0) > 0:  # Original used 'fgs', not 'fgAtt'
            # Field goals made
            if kicking_stats['fgs'] > kicking_records['fgs']['value']:
                kicking_records['fgs'].update({
                    'value': kicking_stats['fgs'],
                    'name': player.name,
                    'id': player.id
                })
            
            # Field goal yards (missing from original implementation)
            if kicking_stats.get('fgYards', 0) > kicking_records.get('fgYards', {}).get('value', 0):
                if 'fgYards' not in kicking_records:
                    kicking_records['fgYards'] = {'value': 0, 'name': '', 'id': 0}
                kicking_records['fgYards'].update({
                    'value': kicking_stats.get('fgYards', 0),
                    'name': player.name,
                    'id': player.id
                })
                
    def _checkDefenseGameRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check defensive game records for a player"""
        defense_stats = player.gameStatsDict.get('defense', {})
        defense_records = records.get('players', {}).get('defense', {}).get('game', {})
        
        # Defensive interceptions
        if defense_stats.get('interceptions', 0) > defense_records.get('interceptions', {}).get('value', 0):
            if 'interceptions' not in defense_records:
                defense_records['interceptions'] = {'value': 0, 'name': '', 'id': 0}
            defense_records['interceptions'].update({
                'value': defense_stats['interceptions'],
                'name': player.name,
                'id': player.id
            })
        
        # Sacks
        if defense_stats.get('sacks', 0) > defense_records.get('sacks', {}).get('value', 0):
            if 'sacks' not in defense_records:
                defense_records['sacks'] = {'value': 0, 'name': '', 'id': 0}
            defense_records['sacks'].update({
                'value': defense_stats['sacks'],
                'name': player.name,
                'id': player.id
            })
        
        # Tackles
        if defense_stats.get('tackles', 0) > defense_records.get('tackles', {}).get('value', 0):
            if 'tackles' not in defense_records:
                defense_records['tackles'] = {'value': 0, 'name': '', 'id': 0}
            defense_records['tackles'].update({
                'value': defense_stats['tackles'],
                'name': player.name,
                'id': player.id
            })
        
        # Fumble recoveries
        if defense_stats.get('fumbleRecoveries', 0) > defense_records.get('fumbleRecoveries', {}).get('value', 0):
            if 'fumbleRecoveries' not in defense_records:
                defense_records['fumbleRecoveries'] = {'value': 0, 'name': '', 'id': 0}
            defense_records['fumbleRecoveries'].update({
                'value': defense_stats['fumbleRecoveries'],
                'name': player.name,
                'id': player.id
            })
                
    def _checkFantasyGameRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check fantasy game records for a player - matches original position-based logic"""
        fantasyPoints = player.gameStatsDict['fantasyPoints']
        
        if player.position == FloosPlayer.Position.QB:
            qbFantasyRecords = records['players']['fantasy']['game']['qb']
            if fantasyPoints > qbFantasyRecords.get('value', 0):
                qbFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.RB:
            rbFantasyRecords = records['players']['fantasy']['game']['rb']
            if fantasyPoints > rbFantasyRecords.get('value', 0):
                rbFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.WR:
            wrFantasyRecords = records['players']['fantasy']['game']['wr']
            if fantasyPoints > wrFantasyRecords.get('value', 0):
                wrFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.TE:
            teFantasyRecords = records['players']['fantasy']['game']['te']
            if fantasyPoints > teFantasyRecords.get('value', 0):
                teFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.K:
            kFantasyRecords = records['players']['fantasy']['game']['k']
            if fantasyPoints > kFantasyRecords.get('value', 0):
                kFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
    
    def checkTeamGameRecords(self, game, allTimeRecordsDict: Dict[str, Any] = None) -> None:
        """
        Check and update team game records
        Replaces checkTeamGameRecords() function from floosball.py
        """
        # Use internal records if no external dict provided
        if allTimeRecordsDict is None:
            allTimeRecordsDict = self.getRecords()
            
        team_records = allTimeRecordsDict['team']['game']
        
        # Check home team records
        self._checkTeamGameRecord(game.homeTeam, game.homeScore, team_records, 'pts')
        
        homeTeamTds = (game.homeTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + 
                      game.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
        self._checkTeamGameRecord(game.homeTeam, homeTeamTds, team_records, 'tds')
        
        homeTeamYards = (game.homeTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + 
                        game.homeTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
        self._checkTeamGameRecord(game.homeTeam, homeTeamYards, team_records, 'yards')
        
        # Check away team records  
        self._checkTeamGameRecord(game.awayTeam, game.awayScore, team_records, 'pts')
        
        awayTeamTds = (game.awayTeam.rosterDict['qb'].gameStatsDict['passing']['tds'] + 
                      game.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['tds'])
        self._checkTeamGameRecord(game.awayTeam, awayTeamTds, team_records, 'tds')
        
        awayTeamYards = (game.awayTeam.rosterDict['qb'].gameStatsDict['passing']['yards'] + 
                        game.awayTeam.rosterDict['rb'].gameStatsDict['rushing']['yards'])
        self._checkTeamGameRecord(game.awayTeam, awayTeamYards, team_records, 'yards')
        
    def _checkTeamGameRecord(self, team, value: int, team_records: Dict[str, Any], record_type: str) -> None:
        """Check and update a specific team game record"""
        if value > team_records[record_type]['value']:
            team_records[record_type].update({
                'value': value,
                'name': f'{team.city} {team.name}',
                'id': team.id
            })
    
    def checkCareerRecords(self, allTimeRecordsDict: Dict[str, Any] = None) -> None:
        """
        Check and update career records for all active players
        Replaces checkCareerRecords() function from floosball.py
        """
        # Use internal records if no external dict provided
        if allTimeRecordsDict is None:
            allTimeRecordsDict = self.getRecords()
            
        activePlayerList = self.serviceContainer.getService('player_manager').activePlayers
        
        for player in activePlayerList:
            self._checkCareerPassingRecords(player, allTimeRecordsDict)
            self._checkCareerRushingRecords(player, allTimeRecordsDict)
            self._checkCareerReceivingRecords(player, allTimeRecordsDict)
            self._checkCareerKickingRecords(player, allTimeRecordsDict)
            self._checkCareerDefenseRecords(player, allTimeRecordsDict)
            # Career fantasy points were in original - critical missing call
            self._checkCareerFantasyRecords(player, allTimeRecordsDict)
            
        # Add team records checking
        self._checkCareerTeamRecords(allTimeRecordsDict)
            
    def _checkCareerPassingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check career passing records for a player"""
        career_stats = player.careerStatsDict['passing']
        career_records = records['players']['passing']['career']
        
        # Original had eligibility check - only check if player has passing attempts
        if career_stats.get('att', 0) == 0:
            return
        
        # Career passing yards
        if career_stats['yards'] > career_records['yards']['value']:
            career_records['yards'].update({
                'value': career_stats['yards'],
                'name': player.name,
                'id': player.id
            })
        
        # Career passing TDs
        if career_stats['tds'] > career_records['tds']['value']:
            career_records['tds'].update({
                'value': career_stats['tds'],
                'name': player.name,
                'id': player.id
            })
        
        # Career completions
        if career_stats['comp'] > career_records['comps']['value']:
            career_records['comps'].update({
                'value': career_stats['comp'],
                'name': player.name,
                'id': player.id
            })
        
        # Career interceptions
        if career_stats['ints'] > career_records['ints']['value']:
            career_records['ints'].update({
                'value': career_stats['ints'],
                'name': player.name,
                'id': player.id
            })
            
    def _checkCareerRushingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check career rushing records for a player"""
        career_stats = player.careerStatsDict['rushing']
        career_records = records['players']['rushing']['career']
        
        # Original had eligibility check - only check if player has rushing attempts
        if career_stats.get('carries', 0) == 0:
            return
        
        # Career rushing yards
        if career_stats['yards'] > career_records['yards']['value']:
            career_records['yards'].update({
                'value': career_stats['yards'],
                'name': player.name,
                'id': player.id
            })
        
        # Career rushing TDs
        if career_stats['tds'] > career_records['tds']['value']:
            career_records['tds'].update({
                'value': career_stats['tds'],
                'name': player.name,
                'id': player.id
            })
            
    def _checkCareerReceivingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check career receiving records for a player"""
        career_stats = player.careerStatsDict['receiving']
        career_records = records['players']['receiving']['career']
        
        # Original had eligibility check - only check if player has receptions
        if career_stats.get('receptions', 0) == 0:
            return
        
        # Career receiving yards
        if career_stats['yards'] > career_records['yards']['value']:
            career_records['yards'].update({
                'value': career_stats['yards'],
                'name': player.name,
                'id': player.id
            })
        
        # Career receiving TDs
        if career_stats['tds'] > career_records['tds']['value']:
            career_records['tds'].update({
                'value': career_stats['tds'],
                'name': player.name,
                'id': player.id
            })
        
        # Career receptions
        if career_stats['receptions'] > career_records['receptions']['value']:
            career_records['receptions'].update({
                'value': career_stats['receptions'],
                'name': player.name,
                'id': player.id
            })
        
        # Career fumbles lost (missing from original implementation)
        if career_stats.get('fumblesLost', 0) > career_records.get('fumbles', {}).get('value', 0):
            if 'fumbles' not in career_records:
                career_records['fumbles'] = {'value': 0, 'name': '', 'id': 0}
            career_records['fumbles'].update({
                'value': career_stats.get('fumblesLost', 0),
                'name': player.name,
                'id': player.id
            })
            
    def _checkCareerKickingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check career kicking records for a player"""
        career_stats = player.careerStatsDict['kicking']
        career_records = records['players']['kicking']['career']
        
        # Original had eligibility check - only check if player has field goal attempts
        if career_stats.get('fgs', 0) == 0:
            return
        
        # Career field goals
        if career_stats['fgs'] > career_records['fgs']['value']:
            career_records['fgs'].update({
                'value': career_stats['fgs'],
                'name': player.name,
                'id': player.id
            })
        
        # Career field goal yards (missing from original implementation)
        if career_stats.get('fgYards', 0) > career_records.get('fgYards', {}).get('value', 0):
            if 'fgYards' not in career_records:
                career_records['fgYards'] = {'value': 0, 'name': '', 'id': 0}
            career_records['fgYards'].update({
                'value': career_stats.get('fgYards', 0),
                'name': player.name,
                'id': player.id
            })
    
    def _checkCareerDefenseRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check career defensive records for a player"""
        career_stats = player.careerStatsDict.get('defense', {})
        career_records = records.get('players', {}).get('defense', {}).get('career', {})
        
        # Career defensive interceptions
        if career_stats.get('interceptions', 0) > career_records.get('interceptions', {}).get('value', 0):
            if 'interceptions' not in career_records:
                career_records['interceptions'] = {'value': 0, 'name': '', 'id': 0}
            career_records['interceptions'].update({
                'value': career_stats['interceptions'],
                'name': player.name,
                'id': player.id
            })
        
        # Career sacks
        if career_stats.get('sacks', 0) > career_records.get('sacks', {}).get('value', 0):
            if 'sacks' not in career_records:
                career_records['sacks'] = {'value': 0, 'name': '', 'id': 0}
            career_records['sacks'].update({
                'value': career_stats['sacks'],
                'name': player.name,
                'id': player.id
            })
        
        # Career tackles
        if career_stats.get('tackles', 0) > career_records.get('tackles', {}).get('value', 0):
            if 'tackles' not in career_records:
                career_records['tackles'] = {'value': 0, 'name': '', 'id': 0}
            career_records['tackles'].update({
                'value': career_stats['tackles'],
                'name': player.name,
                'id': player.id
            })
        
        # Career fumble recoveries
        if career_stats.get('fumbleRecoveries', 0) > career_records.get('fumbleRecoveries', {}).get('value', 0):
            if 'fumbleRecoveries' not in career_records:
                career_records['fumbleRecoveries'] = {'value': 0, 'name': '', 'id': 0}
            career_records['fumbleRecoveries'].update({
                'value': career_stats['fumbleRecoveries'],
                'name': player.name,
                'id': player.id
            })
    
    def _checkCareerTeamRecords(self, records: Dict[str, Any]) -> None:
        """Check career team records"""
        teamList = self.serviceContainer.getService('team_manager').teams
        team_records = records.get('team', {}).get('allTime', {})  # Fixed: Original used 'allTime', not 'career'
        
        for team in teamList:
            # All-time wins
            wins = team.allTimeTeamStats.get('wins', 0)
            if wins > team_records.get('wins', {}).get('value', 0):
                if 'wins' not in team_records:
                    team_records['wins'] = {'value': 0, 'name': '', 'id': 0}
                team_records['wins'].update({
                    'value': wins,
                    'name': f'{team.city} {team.name}',
                    'id': team.id
                })
            
            # All-time losses
            losses = team.allTimeTeamStats.get('losses', 0)
            if losses > team_records.get('losses', {}).get('value', 0):
                if 'losses' not in team_records:
                    team_records['losses'] = {'value': 0, 'name': '', 'id': 0}
                team_records['losses'].update({
                    'value': losses,
                    'name': f'{team.city} {team.name}',
                    'id': team.id
                })
            
            # Floosball championships (original field name was 'titles')
            floosbowlTitles = len(team.floosbowlChampionships) if hasattr(team, 'floosbowlChampionships') else 0
            if floosbowlTitles > team_records.get('titles', {}).get('value', 0):
                if 'titles' not in team_records:
                    team_records['titles'] = {'value': 0, 'name': '', 'id': 0}
                team_records['titles'].update({
                    'value': floosbowlTitles,
                    'name': f'{team.city} {team.name}',
                    'id': team.id
                })
            
            # League championships (original field name was 'leagueTitles')
            leagueTitles = len(team.leagueChampionships) if hasattr(team, 'leagueChampionships') else 0
            if leagueTitles > team_records.get('leagueTitles', {}).get('value', 0):
                if 'leagueTitles' not in team_records:
                    team_records['leagueTitles'] = {'value': 0, 'name': '', 'id': 0}
                team_records['leagueTitles'].update({
                    'value': leagueTitles,
                    'name': f'{team.city} {team.name}',
                    'id': team.id
                })
            
            # Regular season championships (original field name was 'regSeasonTitles')
            regularSeasonTitles = len(team.regularSeasonChampions) if hasattr(team, 'regularSeasonChampions') else 0
            if regularSeasonTitles > team_records.get('regSeasonTitles', {}).get('value', 0):
                if 'regSeasonTitles' not in team_records:
                    team_records['regSeasonTitles'] = {'value': 0, 'name': '', 'id': 0}
                team_records['regSeasonTitles'].update({
                    'value': regularSeasonTitles,
                    'name': f'{team.city} {team.name}',
                    'id': team.id
                })
            
    def _checkCareerFantasyRecords(self, player: FloosPlayer.Player, records: Dict[str, Any]) -> None:
        """Check career fantasy records for a player"""
        fantasyPoints = player.careerStatsDict['fantasyPoints']
        
        if player.position == FloosPlayer.Position.QB:
            qbFantasyRecords = records['players']['fantasy']['career']['qb']
            if fantasyPoints > qbFantasyRecords.get('value', 0):
                qbFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.RB:
            rbFantasyRecords = records['players']['fantasy']['career']['rb']
            if fantasyPoints > rbFantasyRecords.get('value', 0):
                rbFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.WR:
            wrFantasyRecords = records['players']['fantasy']['career']['wr']
            if fantasyPoints > wrFantasyRecords.get('value', 0):
                wrFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.TE:
            teFantasyRecords = records['players']['fantasy']['career']['te']
            if fantasyPoints > teFantasyRecords.get('value', 0):
                teFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
        elif player.position == FloosPlayer.Position.K:
            kFantasyRecords = records['players']['fantasy']['career']['k']
            if fantasyPoints > kFantasyRecords.get('value', 0):
                kFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id
                })
    
    def checkSeasonRecords(self, season, allTimeRecordsDict: Dict[str, Any] = None) -> None:
        """
        Check and update season records for all active players
        Replaces checkSeasonRecords() function from floosball.py
        """
        # Use internal records if no external dict provided
        if allTimeRecordsDict is None:
            allTimeRecordsDict = self.getRecords()
            
        activePlayerList = self.serviceContainer.getService('player_manager').activePlayers
        
        for player in activePlayerList:
            self._checkSeasonPassingRecords(player, allTimeRecordsDict, season)
            self._checkSeasonRushingRecords(player, allTimeRecordsDict, season)
            self._checkSeasonReceivingRecords(player, allTimeRecordsDict, season)
            self._checkSeasonKickingRecords(player, allTimeRecordsDict, season)
            self._checkSeasonDefenseRecords(player, allTimeRecordsDict, season)
            # Season fantasy points were in original - matches position-based logic from game records
            self._checkSeasonFantasyRecords(player, allTimeRecordsDict, season)
            
        # Check team season records
        self._checkTeamSeasonRecords(season, allTimeRecordsDict)
            
    def _checkSeasonPassingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any], season) -> None:
        """Check season passing records for a player"""
        season_stats = player.seasonStatsDict['passing']
        season_records = records['players']['passing']['season']
        
        # Original had eligibility check - only check if player has passing attempts
        if season_stats.get('att', 0) == 0:
            return
        
        # Season passing yards
        if season_stats['yards'] > season_records['yards']['value']:
            season_records['yards'].update({
                'value': season_stats['yards'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season passing TDs
        if season_stats['tds'] > season_records['tds']['value']:
            season_records['tds'].update({
                'value': season_stats['tds'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season completions
        if season_stats['comp'] > season_records['comps']['value']:
            season_records['comps'].update({
                'value': season_stats['comp'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season interceptions
        if season_stats['ints'] > season_records['ints']['value']:
            season_records['ints'].update({
                'value': season_stats['ints'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
            
    def _checkSeasonRushingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any], season) -> None:
        """Check season rushing records for a player"""
        season_stats = player.seasonStatsDict['rushing']
        season_records = records['players']['rushing']['season']
        
        # Original had eligibility check - only check if player has carries
        if season_stats.get('carries', 0) == 0:
            return
        
        # Season rushing yards
        if season_stats['yards'] > season_records['yards']['value']:
            season_records['yards'].update({
                'value': season_stats['yards'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season rushing TDs
        if season_stats['tds'] > season_records['tds']['value']:
            season_records['tds'].update({
                'value': season_stats['tds'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season fumbles lost (missing from original implementation)
        if season_stats.get('fumblesLost', 0) > season_records.get('fumbles', {}).get('value', 0):
            if 'fumbles' not in season_records:
                season_records['fumbles'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
            season_records['fumbles'].update({
                'value': season_stats.get('fumblesLost', 0),
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
            
    def _checkSeasonReceivingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any], season) -> None:
        """Check season receiving records for a player"""
        season_stats = player.seasonStatsDict['receiving']
        season_records = records['players']['receiving']['season']
        
        # Original had eligibility check - only check if player has receptions
        if season_stats.get('receptions', 0) == 0:
            return
        
        # Season receiving yards
        if season_stats['yards'] > season_records['yards']['value']:
            season_records['yards'].update({
                'value': season_stats['yards'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season receiving TDs
        if season_stats['tds'] > season_records['tds']['value']:
            season_records['tds'].update({
                'value': season_stats['tds'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season receptions
        if season_stats['receptions'] > season_records['receptions']['value']:
            season_records['receptions'].update({
                'value': season_stats['receptions'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
            
    def _checkSeasonKickingRecords(self, player: FloosPlayer.Player, records: Dict[str, Any], season) -> None:
        """Check season kicking records for a player"""
        season_stats = player.seasonStatsDict['kicking']
        season_records = records['players']['kicking']['season']
        
        # Original had eligibility check - only check if player has field goal attempts
        if season_stats.get('fgs', 0) == 0:
            return
        
        # Season field goals
        if season_stats['fgs'] > season_records['fgs']['value']:
            season_records['fgs'].update({
                'value': season_stats['fgs'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season field goal yards (missing from original implementation)
        if season_stats.get('fgYards', 0) > season_records.get('fgYards', {}).get('value', 0):
            if 'fgYards' not in season_records:
                season_records['fgYards'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
            season_records['fgYards'].update({
                'value': season_stats.get('fgYards', 0),
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
            
    def _checkSeasonFantasyRecords(self, player: FloosPlayer.Player, records: Dict[str, Any], season) -> None:
        """Check season fantasy records for a player - matches original position-based logic"""
        fantasyPoints = player.seasonStatsDict['fantasyPoints']
        
        if player.position == FloosPlayer.Position.QB:
            qbFantasyRecords = records['players']['fantasy']['season']['qb']
            if fantasyPoints > qbFantasyRecords.get('value', 0):
                qbFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id,
                    'season': season
                })
        elif player.position == FloosPlayer.Position.RB:
            rbFantasyRecords = records['players']['fantasy']['season']['rb']
            if fantasyPoints > rbFantasyRecords.get('value', 0):
                rbFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id,
                    'season': season
                })
        elif player.position == FloosPlayer.Position.WR:
            wrFantasyRecords = records['players']['fantasy']['season']['wr']
            if fantasyPoints > wrFantasyRecords.get('value', 0):
                wrFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id,
                    'season': season
                })
        elif player.position == FloosPlayer.Position.TE:
            teFantasyRecords = records['players']['fantasy']['season']['te']
            if fantasyPoints > teFantasyRecords.get('value', 0):
                teFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id,
                    'season': season
                })
        elif player.position == FloosPlayer.Position.K:
            kFantasyRecords = records['players']['fantasy']['season']['k']
            if fantasyPoints > kFantasyRecords.get('value', 0):
                kFantasyRecords.update({
                    'value': fantasyPoints,
                    'name': player.name,
                    'id': player.id,
                    'season': season
                })
    
    def _checkSeasonDefenseRecords(self, player: FloosPlayer.Player, records: Dict[str, Any], season) -> None:
        """Check season defensive records for a player"""
        season_stats = player.seasonStatsDict.get('defense', {})
        season_records = records.get('players', {}).get('defense', {}).get('season', {})
        
        # Season defensive interceptions
        if season_stats.get('interceptions', 0) > season_records.get('interceptions', {}).get('value', 0):
            if 'interceptions' not in season_records:
                season_records['interceptions'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
            season_records['interceptions'].update({
                'value': season_stats['interceptions'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season sacks
        if season_stats.get('sacks', 0) > season_records.get('sacks', {}).get('value', 0):
            if 'sacks' not in season_records:
                season_records['sacks'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
            season_records['sacks'].update({
                'value': season_stats['sacks'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season tackles
        if season_stats.get('tackles', 0) > season_records.get('tackles', {}).get('value', 0):
            if 'tackles' not in season_records:
                season_records['tackles'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
            season_records['tackles'].update({
                'value': season_stats['tackles'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
        
        # Season fumble recoveries
        if season_stats.get('fumbleRecoveries', 0) > season_records.get('fumbleRecoveries', {}).get('value', 0):
            if 'fumbleRecoveries' not in season_records:
                season_records['fumbleRecoveries'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
            season_records['fumbleRecoveries'].update({
                'value': season_stats['fumbleRecoveries'],
                'name': player.name,
                'id': player.id,
                'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
            })
    
    def _checkTeamSeasonRecords(self, season, records: Dict[str, Any]) -> None:
        """Check team season records"""
        teamList = self.serviceContainer.getService('team_manager').teams
        team_season_records = records.get('team', {}).get('season', {})
        
        for team in teamList:
            # Check if team has season stats
            if not hasattr(team, 'seasonTeamStats') or not team.seasonTeamStats:
                continue
            
            # Season total yards (original accessed via ['Offense']['totalYards'])
            offenseStats = team.seasonTeamStats.get('Offense', {})
            totalYards = offenseStats.get('totalYards', 0)
            if totalYards > team_season_records.get('yards', {}).get('value', 0):
                if 'yards' not in team_season_records:
                    team_season_records['yards'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
                team_season_records['yards'].update({
                    'value': totalYards,
                    'name': f'{team.city} {team.name}',
                    'id': team.id,
                    'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
                })
            
            # Season touchdowns (original field was 'tds')
            touchdowns = offenseStats.get('tds', 0)
            if touchdowns > team_season_records.get('tds', {}).get('value', 0):
                if 'tds' not in team_season_records:
                    team_season_records['tds'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
                team_season_records['tds'].update({
                    'value': touchdowns,
                    'name': f'{team.city} {team.name}',
                    'id': team.id,
                    'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
                })
            
            # Season points (original field was 'pts')
            points = offenseStats.get('pts', 0)
            if points > team_season_records.get('pts', {}).get('value', 0):
                if 'pts' not in team_season_records:
                    team_season_records['pts'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
                team_season_records['pts'].update({
                    'value': points,
                    'name': f'{team.city} {team.name}',
                    'id': team.id,
                    'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
                })
            
            # Defensive stats (original accessed via ['Defense'])
            defenseStats = team.seasonTeamStats.get('Defense', {})
            
            # Season interceptions (original field was 'ints')
            interceptions = defenseStats.get('ints', 0)
            if interceptions > team_season_records.get('ints', {}).get('value', 0):
                if 'ints' not in team_season_records:
                    team_season_records['ints'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
                team_season_records['ints'].update({
                    'value': interceptions,
                    'name': f'{team.city} {team.name}',
                    'id': team.id,
                    'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
                })
            
            # Season fumble recoveries (original field was 'fumRec')
            fumbleRecoveries = defenseStats.get('fumRec', 0)
            if fumbleRecoveries > team_season_records.get('fumRec', {}).get('value', 0):
                if 'fumRec' not in team_season_records:
                    team_season_records['fumRec'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
                team_season_records['fumRec'].update({
                    'value': fumbleRecoveries,
                    'name': f'{team.city} {team.name}',
                    'id': team.id,
                    'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
                })
            
            # Season ELO rating
            if hasattr(team, 'elo') and team.elo > team_season_records.get('elo', {}).get('value', 0):
                if 'elo' not in team_season_records:
                    team_season_records['elo'] = {'value': 0, 'name': '', 'id': 0, 'season': 0}
                team_season_records['elo'].update({
                    'value': team.elo,
                    'name': f'{team.city} {team.name}',
                    'id': team.id,
                    'season': season.currentSeason if hasattr(season, 'currentSeason') else 0
                })
    
    def getRecordStatistics(self, allTimeRecordsDict: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive record statistics"""
        return {
            'totalRecords': self._countRecords(allTimeRecordsDict),
            'playerRecords': self._countPlayerRecords(allTimeRecordsDict),
            'teamRecords': self._countTeamRecords(allTimeRecordsDict)
        }
    
    def _countRecords(self, records: Dict[str, Any]) -> int:
        """Count total number of records"""
        total = 0
        for category in records.values():
            if isinstance(category, dict):
                total += self._countRecords(category)
            else:
                total += 1
        return total
    
    def _countPlayerRecords(self, records: Dict[str, Any]) -> int:
        """Count player-specific records"""
        if 'players' in records:
            return self._countRecords(records['players'])
        return 0
    
    def _countTeamRecords(self, records: Dict[str, Any]) -> int:
        """Count team-specific records"""
        if 'team' in records:
            return self._countRecords(records['team'])
        return 0
    
    def updateChampionshipHistory(self, season, winningTeam, losingTeam) -> None:
        """Update championship history for teams"""
        self._championshipRecords.insert(0, { 'season': season,
                                                'champion': '{} {}'.format(winningTeam.city, winningTeam.name),
                                                'championColor': winningTeam.color,
                                                'championId': winningTeam.id,
                                                'championRecord': '{}-{}'.format(winningTeam.seasonTeamStats['wins'],winningTeam.seasonTeamStats['losses']),
                                                'championElo': winningTeam.elo,
                                                'runnerUp': '{} {}'.format(losingTeam.city, losingTeam.name),
                                                'runnerUpColor': losingTeam.color,
                                                'runnerUpId': losingTeam.id,
                                                'runnerUpRecord': '{}-{}'.format(losingTeam.seasonTeamStats['wins'],losingTeam.seasonTeamStats['losses']),
                                                'runnerUpElo': losingTeam.elo
                                                })