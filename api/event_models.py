"""
Event Models for WebSocket Broadcasting
Defines standardized event formats for game updates, season progress, and other real-time data
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class EventType(Enum):
    """Types of events that can be broadcast via WebSocket"""
    
    # Game events
    GAME_START = "game_start"
    GAME_END = "game_end"
    GAME_STATE = "game_state"  # Comprehensive state after every play
    
    # Legacy events (deprecated - use GAME_STATE instead)
    PLAY_COMPLETE = "play_complete"
    SCORE_UPDATE = "score_update"
    QUARTER_END = "quarter_end"
    HALFTIME = "halftime"
    OVERTIME_START = "overtime_start"
    WIN_PROBABILITY_UPDATE = "win_probability_update"
    GAME_STATE_UPDATE = "game_state_update"
    
    # Season events
    SEASON_START = "season_start"
    SEASON_END = "season_end"
    WEEK_START = "week_start"
    WEEK_END = "week_end"
    DAY_COMPLETE = "day_complete"
    REGULAR_SEASON_COMPLETE = "regular_season_complete"
    
    # Standings events
    STANDINGS_UPDATE = "standings_update"

    # Fantasy events
    LEADERBOARD_UPDATE = "leaderboard_update"

    # League news (clinches, eliminations, championships)
    LEAGUE_NEWS = "league_news"

    # Awards
    MVP_ANNOUNCEMENT = "mvp_announcement"
    
    # Player events
    PLAYER_STAT_UPDATE = "player_stat_update"
    PLAYER_INJURY = "player_injury"
    
    # Offseason events
    OFFSEASON_START         = "offseason_start"
    OFFSEASON_PICK          = "offseason_pick"
    OFFSEASON_CUT           = "offseason_cut"
    OFFSEASON_TEAM_COMPLETE = "offseason_team_complete"
    OFFSEASON_COMPLETE      = "offseason_complete"

    # System events
    ERROR = "error"
    INFO = "info"


class GameEvent:
    """Factory for creating game-related event messages"""
    
    @staticmethod
    def gameStart(gameId: int, homeTeam: Dict, awayTeam: Dict, startTime: datetime) -> Dict[str, Any]:
        """Create a game start event"""
        return {
            'event': EventType.GAME_START.value,
            'gameId': gameId,
            'homeTeam': homeTeam,
            'awayTeam': awayTeam,
            'startTime': startTime.isoformat() if isinstance(startTime, datetime) else startTime,
            'message': f"{awayTeam.get('name', 'Away')} at {homeTeam.get('name', 'Home')}"
        }
    
    @staticmethod
    def gameEnd(gameId: int, finalScore: Dict[str, int], winner: str, stats: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a game end event"""
        homeScore = finalScore.get('home', 0)
        awayScore = finalScore.get('away', 0)
        if homeScore > awayScore:
            homeWinProbability, awayWinProbability = 100.0, 0.0
        elif awayScore > homeScore:
            homeWinProbability, awayWinProbability = 0.0, 100.0
        else:
            homeWinProbability, awayWinProbability = 50.0, 50.0
        return {
            'event': EventType.GAME_END.value,
            'gameId': gameId,
            'finalScore': finalScore,
            'winner': winner,
            'homeWinProbability': homeWinProbability,
            'awayWinProbability': awayWinProbability,
            'stats': stats or {},
            'message': f"Final: {finalScore['away']} - {finalScore['home']}"
        }
    
    @staticmethod
    def playComplete(gameId: int, playData: Dict[str, Any]) -> Dict[str, Any]:
        """Create a play completion event"""
        return {
            'event': EventType.PLAY_COMPLETE.value,
            'gameId': gameId,
            'play': playData,
            'message': playData.get('description', 'Play complete')
        }
    
    @staticmethod
    def scoreUpdate(gameId: int, homeScore: int, awayScore: int, scoringPlay: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a score update event"""
        return {
            'event': EventType.SCORE_UPDATE.value,
            'gameId': gameId,
            'homeScore': homeScore,
            'awayScore': awayScore,
            'scoringPlay': scoringPlay,
            'message': f"Score: {awayScore} - {homeScore}"
        }
    
    @staticmethod
    def winProbabilityUpdate(gameId: int, homeWinProb: float, awayWinProb: float, 
                              homeWpa: float = 0.0, awayWpa: float = 0.0,
                              previousHomeWp: float = None, previousAwayWp: float = None,
                              factors: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a win probability update event with WPA (Win Probability Added)"""
        event = {
            'event': EventType.WIN_PROBABILITY_UPDATE.value,
            'gameId': gameId,
            'homeWinProbability': round(homeWinProb, 1),
            'awayWinProbability': round(awayWinProb, 1),
            'homeWpa': round(homeWpa, 2),  # Win Probability Added for home team
            'awayWpa': round(awayWpa, 2),  # Win Probability Added for away team
            'factors': factors or {},
            'message': f"Win Prob: {round(homeWinProb, 1)}% - {round(awayWinProb, 1)}%"
        }
        
        # Include previous values if provided
        if previousHomeWp is not None:
            event['previousHomeWinProbability'] = round(previousHomeWp, 1)
        if previousAwayWp is not None:
            event['previousAwayWinProbability'] = round(previousAwayWp, 1)
        
        return event
    
    @staticmethod
    def quarterEnd(gameId: int, quarter: int, homeScore: int, awayScore: int) -> Dict[str, Any]:
        """Create a quarter end event"""
        quarterName = {1: "1st Quarter", 2: "2nd Quarter", 3: "3rd Quarter", 4: "4th Quarter"}.get(quarter, f"Q{quarter}")
        return {
            'event': EventType.QUARTER_END.value,
            'gameId': gameId,
            'quarter': quarter,
            'homeScore': homeScore,
            'awayScore': awayScore,
            'message': f"End of {quarterName}"
        }
    
    @staticmethod
    def halftimeEvent(gameId: int, homeScore: int, awayScore: int, stats: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a halftime event"""
        return {
            'event': EventType.HALFTIME.value,
            'gameId': gameId,
            'homeScore': homeScore,
            'awayScore': awayScore,
            'halftimeStats': stats,
            'message': f"Halftime: {awayScore} - {homeScore}"
        }    
    @staticmethod
    def gameStateUpdate(gameId: int, stateData: Dict[str, Any]) -> Dict[str, Any]:
        """Create a game state update event with current down/distance/possession"""
        return {
            'event': EventType.GAME_STATE_UPDATE.value,
            'gameId': gameId,
            'state': stateData,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def gameState(gameId: int, gameState: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a comprehensive game state event broadcast after every play.
        This single event replaces score_update, play_complete, and game_state_update.
        
        Expected gameState structure:
        {
            'status': 'Active'|'Scheduled'|'Final',
            'homeScore': int,
            'awayScore': int,
            'quarterScores': {
                'home': {'q1': int, 'q2': int, 'q3': int, 'q4': int, 'ot': int},
                'away': {'q1': int, 'q2': int, 'q3': int, 'q4': int, 'ot': int}
            },
            'possession': str (team abbr),
            'homeTeamPoss': bool,
            'awayTeamPoss': bool,
            'quarter': int,
            'timeRemaining': str,
            'down': int,
            'distance': int (yards to first down),
            'yardLine': str (e.g., 'BAL 25'),
            'yardsToEndzone': int,
            'yardsToSafety': int,
            'lastPlay': {
                'playNumber': int,
                'quarter': int,
                'timeRemaining': str,
                'down': int,
                'distance': int,
                'yardLine': str,
                'playType': str,
                'yardsGained': int,
                'description': str,
                'playResult': str,
                'isTouchdown': bool,
                'isTurnover': bool,
                'isSack': bool,
                'offensiveTeam': str,
                'defensiveTeam': str
            },
            'homeWinProbability': float,
            'awayWinProbability': float,
            'homeWpa': float,
            'awayWpa': float,
            'isHalftime': bool,
            'isOvertime': bool
        }
        """
        return {
            'event': EventType.GAME_STATE.value,
            'gameId': gameId,
            'timestamp': datetime.now().isoformat(),
            **gameState  # Spread all game state fields into the event
        }

class SeasonEvent:
    """Factory for creating season-related event messages"""
    
    @staticmethod
    def seasonStart(seasonNumber: int, totalWeeks: int) -> Dict[str, Any]:
        """Create a season start event"""
        return {
            'event': EventType.SEASON_START.value,
            'seasonNumber': seasonNumber,
            'totalWeeks': totalWeeks,
            'message': f"Season {seasonNumber} begins"
        }
    
    @staticmethod
    def seasonEnd(seasonNumber: int, champion: Dict[str, Any], standings: List[Dict]) -> Dict[str, Any]:
        """Create a season end event"""
        return {
            'event': EventType.SEASON_END.value,
            'seasonNumber': seasonNumber,
            'champion': champion,
            'finalStandings': standings,
            'message': f"Season {seasonNumber} complete - Champion: {champion.get('name', 'TBD')}"
        }
    
    @staticmethod
    def weekStart(seasonNumber: int, weekNumber: int, games: List[Dict], weekText: str = None) -> Dict[str, Any]:
        """Create a week start event"""
        text = weekText or f'Week {weekNumber}'
        return {
            'event': EventType.WEEK_START.value,
            'seasonNumber': seasonNumber,
            'weekNumber': weekNumber,
            'weekText': text,
            'gamesCount': len(games),
            'games': games,
            'message': f"{text} begins"
        }
    
    @staticmethod
    def weekEnd(seasonNumber: int, weekNumber: int, results: List[Dict]) -> Dict[str, Any]:
        """Create a week end event"""
        return {
            'event': EventType.WEEK_END.value,
            'seasonNumber': seasonNumber,
            'weekNumber': weekNumber,
            'results': results,
            'message': f"Week {weekNumber} complete"
        }

    @staticmethod
    def dayComplete(dayNumber: int) -> Dict[str, Any]:
        """Broadcast after the last round of a regular-season game day"""
        return {
            'event': EventType.DAY_COMPLETE.value,
            'dayNumber': dayNumber,
            'message': f'Day {dayNumber} complete — Day {dayNumber + 1} begins tomorrow at 11am'
        }

    @staticmethod
    def regularSeasonComplete() -> Dict[str, Any]:
        """Broadcast after round 28 (end of Day 4, regular season done)"""
        return {
            'event': EventType.REGULAR_SEASON_COMPLETE.value,
            'message': 'Regular season complete — Playoffs begin tomorrow'
        }

    @staticmethod
    def mvpAnnouncement(mvpData: Dict[str, Any], seasonNumber: int) -> Dict[str, Any]:
        """Broadcast MVP announcement after regular season"""
        return {
            'event': EventType.MVP_ANNOUNCEMENT.value,
            'seasonNumber': seasonNumber,
            'mvp': mvpData,
            'message': f"Season {seasonNumber} MVP: {mvpData['name']} ({mvpData['position']}, {mvpData['team']})"
        }


class LeagueNewsEvent:
    """Factory for league-wide news events (clinches, eliminations, championships)"""

    @staticmethod
    def leagueNews(text: str) -> Dict[str, Any]:
        return {
            'event': EventType.LEAGUE_NEWS.value,
            'text': text,
            'timestamp': datetime.now().isoformat()
        }


class OffseasonEvent:
    """Factory for offseason free agency events"""

    @staticmethod
    def start(draftOrder: list) -> Dict[str, Any]:
        return {
            'event': EventType.OFFSEASON_START.value,
            'timestamp': datetime.now().isoformat(),
            'draftOrder': draftOrder,
        }

    @staticmethod
    def pick(teamName: str, teamAbbr: str, playerName: str,
             position: str, rating: float, tier: str) -> Dict[str, Any]:
        return {
            'event': EventType.OFFSEASON_PICK.value,
            'timestamp': datetime.now().isoformat(),
            'teamName': teamName,
            'teamAbbr': teamAbbr,
            'playerName': playerName,
            'position': position,
            'rating': rating,
            'tier': tier,
        }

    @staticmethod
    def cut(teamName: str, teamAbbr: str, playerName: str,
            position: str, rating: float, tier: str = '') -> Dict[str, Any]:
        return {
            'event': EventType.OFFSEASON_CUT.value,
            'timestamp': datetime.now().isoformat(),
            'teamName': teamName,
            'teamAbbr': teamAbbr,
            'playerName': playerName,
            'position': position,
            'rating': rating,
            'tier': tier,
        }

    @staticmethod
    def team_complete(teamName: str, teamAbbr: str) -> Dict[str, Any]:
        return {
            'event': EventType.OFFSEASON_TEAM_COMPLETE.value,
            'timestamp': datetime.now().isoformat(),
            'teamName': teamName,
            'teamAbbr': teamAbbr,
        }

    @staticmethod
    def complete(remainingFreeAgents: int) -> Dict[str, Any]:
        return {
            'event': EventType.OFFSEASON_COMPLETE.value,
            'timestamp': datetime.now().isoformat(),
            'remainingFreeAgents': remainingFreeAgents,
        }


class StandingsEvent:
    """Factory for creating standings update events"""
    
    @staticmethod
    def standingsUpdate(standings: List[Dict[str, Any]], changedTeams: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a standings update event"""
        return {
            'event': EventType.STANDINGS_UPDATE.value,
            'standings': standings,
            'changedTeams': changedTeams or [],
            'message': "Standings updated"
        }


class PlayerEvent:
    """Factory for creating player-related event messages"""
    
    @staticmethod
    def statUpdate(playerId: int, playerName: str, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Create a player stat update event"""
        return {
            'event': EventType.PLAYER_STAT_UPDATE.value,
            'playerId': playerId,
            'playerName': playerName,
            'stats': stats,
            'message': f"Stats updated for {playerName}"
        }
    
    @staticmethod
    def gameStatsUpdate(gameId: int, homePlayerStats: List[Dict[str, Any]], 
                         awayPlayerStats: List[Dict[str, Any]],
                         homeTeamStats: Optional[Dict[str, Any]] = None,
                         awayTeamStats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a comprehensive game stats update event with all player and team stats"""
        return {
            'event': 'player_stats_update',
            'gameId': gameId,
            'homePlayerStats': homePlayerStats,
            'awayPlayerStats': awayPlayerStats,
            'homeTeamStats': homeTeamStats or {},
            'awayTeamStats': awayTeamStats or {},
            'message': f"Player stats updated for game {gameId}"
        }


class SystemEvent:
    """Factory for creating system event messages"""
    
    @staticmethod
    def error(message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        """Create an error event"""
        return {
            'event': EventType.ERROR.value,
            'message': message,
            'details': details or {},
            'severity': 'error'
        }
    
    @staticmethod
    def info(message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Create an info event"""
        return {
            'event': EventType.INFO.value,
            'message': message,
            'data': data or {},
            'severity': 'info'
        }
