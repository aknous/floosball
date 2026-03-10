"""Response builders to eliminate API endpoint code duplication"""

from typing import Dict, Any, List, Optional, Union
from constants import RATING_SCALE_MIN, RATING_RANGE, STARS_MAX, PERCENTAGE_MULTIPLIER
from logger_config import get_logger

logger = get_logger("floosball.api_builders")

class ResponseBuilder:
    """Base class for building API responses consistently"""
    
    @staticmethod
    def calculateStarRating(rating: int, minRating: int = RATING_SCALE_MIN,
                             ratingRange: int = RATING_RANGE) -> int:
        """Calculate star rating from numeric rating.

        Equal-width bands across the 60-100 range:
          1★: 60-67  |  2★: 68-75  |  3★: 76-83  |  4★: 84-91  |  5★: 92-100
        """
        return min(5, max(1, (rating - minRating) // 8 + 1))
    
    @staticmethod
    def calculateWinPercentage(wins: int, losses: int) -> str:
        """Calculate win percentage as formatted string"""
        if wins + losses > 0:
            return '{:.3f}'.format(round(wins / (wins + losses), 3))
        return '0.000'
    
    @staticmethod
    def safePercentage(numerator: int, denominator: int) -> int:
        """Calculate percentage safely handling division by zero"""
        if denominator > 0:
            return round((numerator / denominator) * PERCENTAGE_MULTIPLIER)
        return 0

class TeamResponseBuilder(ResponseBuilder):
    """Builder for team-related API responses"""
    
    @staticmethod
    def buildBasicTeamDict(team) -> Dict[str, Any]:
        """Build basic team information dictionary"""
        wins = team.seasonTeamStats['wins']
        losses = team.seasonTeamStats['losses']
        
        return {
            'name': team.name,
            'city': team.city,
            'color': team.color,
            'secondaryColor': getattr(team, 'secondaryColor', team.color),
            'tertiaryColor': getattr(team, 'tertiaryColor', team.color),
            'id': team.id,
            'elo': team.elo,
            'eliminated': team.eliminated,
            'wins': wins,
            'losses': losses,
            'winPerc': TeamResponseBuilder.calculateWinPercentage(wins, losses),
            'clinchedPlayoffs': team.clinchedPlayoffs,
            'clinchedTopSeed': team.clinchedTopSeed,
            'leagueChampion': team.leagueChampion,
            'floosbowlChampion': team.floosbowlChampion,
            'winningStreak': team.winningStreak,
            'streak': team.seasonTeamStats.get('streak', 0)
        }
    
    @staticmethod
    def buildTeamWithRatings(team) -> Dict[str, Any]:
        """Build team dictionary with rating information"""
        team_dict = TeamResponseBuilder.buildBasicTeamDict(team)
        
        # Add rating calculations
        team_dict.update({
            'ratingStars': TeamResponseBuilder.calculateStarRating(team.overallRating, RATING_SCALE_MIN, RATING_SCALE_MIN),
            'offenseRatingStars': TeamResponseBuilder.calculateStarRating(team.offenseRating),
            'runDefenseRating': TeamResponseBuilder.calculateStarRating(team.defenseRunCoverageRating),
            'passDefenseRating': TeamResponseBuilder.calculateStarRating(team.defensePassCoverageRating, RATING_SCALE_MIN, RATING_SCALE_MIN),
            'overallRating': team.overallRating,
            'offenseRating': team.offenseRating,
            'defenseRunCoverageRating': team.defenseRunCoverageRating,
            'defensePassCoverageRating': team.defensePassCoverageRating
        })
        
        return team_dict
    
    @staticmethod
    def buildTeamListResponse(teams: List) -> List[Dict[str, Any]]:
        """Build response for list of teams"""
        return [TeamResponseBuilder.buildTeamWithRatings(team) for team in teams]

class PlayerResponseBuilder(ResponseBuilder):
    """Builder for player-related API responses"""
    
    @staticmethod
    def buildBasicPlayerDict(player) -> Dict[str, Any]:
        """Build basic player information dictionary"""
        team = player.team
        hasTeamObj = team and not isinstance(team, str)
        return {
            'name': player.name,
            'id': player.id,
            'position': player.position.name,
            'team': team.name if hasTeamObj else (team if isinstance(team, str) else None),
            'teamCity': team.city if hasTeamObj else None,
            'teamColor': team.color if hasTeamObj else None,
            'teamSecondaryColor': team.secondaryColor if hasTeamObj else None,
            'teamId': team.id if hasTeamObj else None,
            'teamAbbr': team.abbr if hasTeamObj else None,
            'seasonsPlayed': player.seasonsPlayed,
            'ratingStars': PlayerResponseBuilder.calculateStarRating(player.playerRating),
            'playerRating': player.playerRating
        }
    
    @staticmethod
    def buildPlayerWithAttributes(player) -> Dict[str, Any]:
        """Build player dictionary with detailed attributes"""
        player_dict = PlayerResponseBuilder.buildBasicPlayerDict(player)
        
        # Add position-specific attributes
        attr_dict = {}
        
        pos = player.position.name if hasattr(player.position, 'name') else str(player.position)

        if pos == 'QB':
            attr_dict.update({
                'att1': 'Arm Strength',
                'att1Value': player.attributes.armStrength,
                'att1stars': PlayerResponseBuilder.calculateStarRating(player.attributes.armStrength),
                'att2': 'Accuracy',
                'att2Value': player.attributes.accuracy,
                'att2stars': PlayerResponseBuilder.calculateStarRating(player.attributes.accuracy),
                'att3': 'Agility',
                'att3Value': player.attributes.agility,
                'att3stars': PlayerResponseBuilder.calculateStarRating(player.attributes.agility),
                'att1PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialArmStrength),
                'att2PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialAccuracy),
                'att3PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialAgility)
            })
        elif pos == 'RB':
            attr_dict.update({
                'att1': 'Speed',
                'att1Value': player.attributes.speed,
                'att1stars': PlayerResponseBuilder.calculateStarRating(player.attributes.speed),
                'att2': 'Power',
                'att2Value': player.attributes.power,
                'att2stars': PlayerResponseBuilder.calculateStarRating(player.attributes.power),
                'att3': 'Agility',
                'att3Value': player.attributes.agility,
                'att3stars': PlayerResponseBuilder.calculateStarRating(player.attributes.agility),
                'att1PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialSpeed),
                'att2PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialPower),
                'att3PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialAgility)
            })
        elif pos == 'WR':
            attr_dict.update({
                'att1': 'Speed',
                'att1Value': player.attributes.speed,
                'att1stars': PlayerResponseBuilder.calculateStarRating(player.attributes.speed),
                'att2': 'Hands',
                'att2Value': player.attributes.hands,
                'att2stars': PlayerResponseBuilder.calculateStarRating(player.attributes.hands),
                'att3': 'Agility',
                'att3Value': player.attributes.agility,
                'att3stars': PlayerResponseBuilder.calculateStarRating(player.attributes.agility),
                'att1PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialSpeed),
                'att2PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialHands),
                'att3PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialAgility)
            })
        elif pos == 'TE':
            attr_dict.update({
                'att1': 'Hands',
                'att1Value': player.attributes.hands,
                'att1stars': PlayerResponseBuilder.calculateStarRating(player.attributes.hands),
                'att2': 'Power',
                'att2Value': player.attributes.power,
                'att2stars': PlayerResponseBuilder.calculateStarRating(player.attributes.power),
                'att3': 'Agility',
                'att3Value': player.attributes.agility,
                'att3stars': PlayerResponseBuilder.calculateStarRating(player.attributes.agility),
                'att1PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialHands),
                'att2PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialPower),
                'att3PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialAgility)
            })
        elif pos == 'K':
            attr_dict.update({
                'att1': 'Leg Strength',
                'att1Value': player.attributes.legStrength,
                'att1stars': PlayerResponseBuilder.calculateStarRating(player.attributes.legStrength),
                'att2': 'Accuracy',
                'att2Value': player.attributes.accuracy,
                'att2stars': PlayerResponseBuilder.calculateStarRating(player.attributes.accuracy),
                'att1PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialLegStrength),
                'att2PotStars': PlayerResponseBuilder.calculateStarRating(player.attributes.potentialAccuracy)
            })
        
        # Add common attributes
        attr_dict.update({
            'playmakingStars': PlayerResponseBuilder.calculateStarRating(player.attributes.playMakingAbility),
            'playmakingValue': player.attributes.playMakingAbility,
            'xFactorStars': PlayerResponseBuilder.calculateStarRating(player.attributes.xFactor),
            'xFactorValue': player.attributes.xFactor
        })
        
        # Add season performance if available
        if hasattr(player, 'seasonPerformanceRating') and player.seasonPerformanceRating > 0:
            attr_dict['seasonPerformanceRatingStars'] = PlayerResponseBuilder.calculateStarRating(player.seasonPerformanceRating)
            attr_dict['seasonPerformanceRating'] = player.seasonPerformanceRating
        
        player_dict['attributes'] = attr_dict
        return player_dict
    
    @staticmethod
    def buildPlayerWithStats(player) -> Dict[str, Any]:
        """Build player dictionary with game statistics"""
        player_dict = PlayerResponseBuilder.buildBasicPlayerDict(player)
        
        # Add game stats with calculated percentages
        stats = player.gameStatsDict
        stats_dict = {}
        
        # Passing stats
        if stats['passing']['att'] > 0:
            stats_dict['passing'] = {
                **stats['passing'],
                'compPerc': PlayerResponseBuilder.safePercentage(
                    stats['passing']['comp'], 
                    stats['passing']['att']
                )
            }
        
        # Receiving stats 
        if stats['receiving']['targets'] > 0:
            stats_dict['receiving'] = {
                **stats['receiving'],
                'rcvPerc': PlayerResponseBuilder.safePercentage(
                    stats['receiving']['receptions'],
                    stats['receiving']['targets']
                )
            }
        
        # Kicking stats
        if stats['kicking']['fgAtt'] > 0:
            stats_dict['kicking'] = {
                **stats['kicking'],
                'fgPerc': PlayerResponseBuilder.safePercentage(
                    stats['kicking']['fgs'],
                    stats['kicking']['fgAtt']
                )
            }
        
        # Add other non-zero stats categories
        for category in ['rushing']:
            if any(value > 0 for value in stats[category].values() if isinstance(value, (int, float))):
                stats_dict[category] = stats[category]
        
        stats_dict['fantasyPoints'] = stats['fantasyPoints']
        stats_dict['gp'] = stats['gp']
        
        player_dict['gameStats'] = stats_dict
        return player_dict

class GameResponseBuilder(ResponseBuilder):
    """Builder for game-related API responses"""
    
    @staticmethod
    def buildBasicGameDict(game) -> Dict[str, Any]:
        """Build basic game information dictionary"""
        from constants import GAME_MAX_PLAYS  # Import here to avoid circular imports
        
        return {
            'id': game.id,
            'homeTeam': game.homeTeam.name,
            'homeTeamCity': game.homeTeam.city,
            'homeTeamColor': game.homeTeam.color,
            'homeTeamId': game.homeTeam.id,
            'awayTeam': game.awayTeam.name,
            'awayTeamCity': game.awayTeam.city,
            'awayTeamColor': game.awayTeam.color,
            'awayTeamId': game.awayTeam.id,
            'homeScore': game.homeScore,
            'awayScore': game.awayScore,
            'playsLeft': GAME_MAX_PLAYS - game.totalPlays,
            'isComplete': game.status.name == 'Final' if hasattr(game.status, 'name') else False,
            'winningTeam': game.winningTeam.name if game.winningTeam else None
        }
    
    @staticmethod
    def buildGameWithProbabilities(game) -> Dict[str, Any]:
        """Build game dictionary with win probabilities - frontend compatible"""
        from constants import GAME_MAX_PLAYS  # Import here to avoid circular imports
        
        # Build nested team objects for frontend
        homeTeam = {
            'id': str(game.homeTeam.id),
            'name': game.homeTeam.name,
            'city': game.homeTeam.city,
            'abbr': game.homeTeam.abbr if hasattr(game.homeTeam, 'abbr') and game.homeTeam.abbr else game.homeTeam.name[:3].upper(),
            'color': game.homeTeam.color,
            'secondaryColor': getattr(game.homeTeam, 'secondaryColor', game.homeTeam.color),
            'tertiaryColor': getattr(game.homeTeam, 'tertiaryColor', game.homeTeam.color),
            'record': f"{game.homeTeam.seasonTeamStats.get('wins', 0)}-{game.homeTeam.seasonTeamStats.get('losses', 0)}" if hasattr(game.homeTeam, 'seasonTeamStats') else "0-0",
            'elo': game.homeTeam.elo
        }
        
        awayTeam = {
            'id': str(game.awayTeam.id),
            'name': game.awayTeam.name,
            'city': game.awayTeam.city,
            'abbr': game.awayTeam.abbr if hasattr(game.awayTeam, 'abbr') and game.awayTeam.abbr else game.awayTeam.name[:3].upper(),
            'color': game.awayTeam.color,
            'secondaryColor': getattr(game.awayTeam, 'secondaryColor', game.awayTeam.color),
            'tertiaryColor': getattr(game.awayTeam, 'tertiaryColor', game.awayTeam.color),
            'record': f"{game.awayTeam.seasonTeamStats.get('wins', 0)}-{game.awayTeam.seasonTeamStats.get('losses', 0)}" if hasattr(game.awayTeam, 'seasonTeamStats') else "0-0",
            'elo': game.awayTeam.elo
        }
        
        # Calculate quarter (use currentQuarter, not quarter)
        quarter = game.currentQuarter if hasattr(game, 'currentQuarter') else 1
        
        # Format time remaining using formatTime method
        timeRemaining = game.formatTime(game.gameClockSeconds) if hasattr(game, 'gameClockSeconds') and hasattr(game, 'formatTime') else '15:00'
        
        # Format down and distance
        down = getattr(game, 'down', None)
        yardsToFirstDown = getattr(game, 'yardsToFirstDown', None)
        yardLine = getattr(game, 'yardLine', None)
        possession = getattr(game, 'possession', None)
        
        # Determine possession team ID
        possessionTeamId = None
        if possession == 'home':
            possessionTeamId = str(game.homeTeam.id)
        elif possession == 'away':
            possessionTeamId = str(game.awayTeam.id)
        
        # Format down text
        downText = None
        if down is not None and down in [1, 2, 3, 4] and yardsToFirstDown is not None and yardLine is not None:
            try:
                downSuffix = ['1st', '2nd', '3rd', '4th'][down - 1]
                yardsToFirstDownInt = int(yardsToFirstDown) if isinstance(yardsToFirstDown, str) else yardsToFirstDown
                
                # Parse yardLine - format is "TEAM YD" (e.g., "BAL 15")
                # If it's the defensive team's side and within 10 yards, show "& Goal"
                if isinstance(yardLine, str) and ' ' in yardLine:
                    yardLineParts = yardLine.split()
                    if len(yardLineParts) == 2:
                        yardLineTeam = yardLineParts[0]
                        yardLineNum = int(yardLineParts[1])
                        
                        # Get defensive team abbreviation
                        offensiveTeamAbbr = None
                        defensiveTeamAbbr = None
                        if hasattr(game, 'offensiveTeam') and hasattr(game, 'defensiveTeam'):
                            offensiveTeamAbbr = game.offensiveTeam.abbr if hasattr(game.offensiveTeam, 'abbr') else None
                            defensiveTeamAbbr = game.defensiveTeam.abbr if hasattr(game.defensiveTeam, 'abbr') else None
                        
                        # Show "& Goal" only if on defensive team's side within 10 yards
                        if defensiveTeamAbbr and yardLineTeam == defensiveTeamAbbr and yardLineNum <= 10:
                            downText = f"{downSuffix} & Goal"
                        else:
                            downText = f"{downSuffix} & {yardsToFirstDownInt}"
                    else:
                        downText = f"{downSuffix} & {yardsToFirstDownInt}"
                else:
                    downText = f"{downSuffix} & {yardsToFirstDownInt}"
            except (ValueError, TypeError):
                downText = None
        
        return {
            'id': str(game.id),
            'seasonNumber': game.seasonNumber,
            'week': game.week,
            'playoffRound': game.playoffRound,
            'gameType': game.gameType,
            'gameNumber': game.gameNumber,
            'displayId': game.getDisplayId() if hasattr(game, 'getDisplayId') else f"game_{game.id}",
            'homeTeam': homeTeam,
            'awayTeam': awayTeam,
            'status': game.status.name if hasattr(game.status, 'name') else str(game.status),
            'homeScore': game.homeScore,
            'awayScore': game.awayScore,
            'quarterScores': {
                'home': {
                    'q1': getattr(game, 'homeScoreQ1', 0),
                    'q2': getattr(game, 'homeScoreQ2', 0),
                    'q3': getattr(game, 'homeScoreQ3', 0),
                    'q4': getattr(game, 'homeScoreQ4', 0)
                },
                'away': {
                    'q1': getattr(game, 'awayScoreQ1', 0),
                    'q2': getattr(game, 'awayScoreQ2', 0),
                    'q3': getattr(game, 'awayScoreQ3', 0),
                    'q4': getattr(game, 'awayScoreQ4', 0)
                }
            },
            'quarter': quarter,
            'timeRemaining': timeRemaining,
            'possession': possessionTeamId,
            'down': down,
            'yardsToFirstDown': yardsToFirstDown,
            'yardLine': yardLine,
            'downText': downText,
            'homeWinProbability': GameResponseBuilder.finalWinProbability(game, 'home'),
            'awayWinProbability': GameResponseBuilder.finalWinProbability(game, 'away'),
            'playsLeft': GAME_MAX_PLAYS - game.totalPlays,
            'isComplete': game.status.name == 'Final' if hasattr(game.status, 'name') else False,
            'winningTeam': game.winningTeam.name if game.winningTeam else None,
            'isUpsetAlert': getattr(game, 'isUpsetAlert', False),
            'isFeatured': getattr(game, 'isFeatured', False),
            'gameStats': game._buildGameStatsSnapshot() if hasattr(game, '_buildGameStatsSnapshot') else None,
        }

    @staticmethod
    def finalWinProbability(game, side: str) -> float:
        """Return win probability, forcing 100/0 for Final games regardless of stored value."""
        isFinal = hasattr(game.status, 'name') and game.status.name == 'Final'
        if isFinal:
            if game.homeScore > game.awayScore:
                return 100.0 if side == 'home' else 0.0
            elif game.awayScore > game.homeScore:
                return 0.0 if side == 'home' else 100.0
            else:
                return 50.0
        storedWp = game.homeTeamWinProbability if side == 'home' else game.awayTeamWinProbability
        return round(storedWp, 1) if storedWp is not None else 50.0

    @staticmethod
    def buildGamesListResponse(games: List) -> List[Dict[str, Any]]:
        """Build response for list of games"""
        return [GameResponseBuilder.buildGameWithProbabilities(game) for game in games]

class LeagueResponseBuilder(ResponseBuilder):
    """Builder for league-wide responses"""
    
    @staticmethod
    def buildStandingsResponse(teams: List) -> Dict[str, Any]:
        """Build league standings response"""
        team_standings = []
        
        for team in teams:
            team_dict = TeamResponseBuilder.buildTeamWithRatings(team)
            # Add standings-specific fields
            team_dict.update({
                'pointsFor': team.seasonTeamStats.get('pointsFor', 0),
                'pointsAgainst': team.seasonTeamStats.get('pointsAgainst', 0),
                'streak': team.seasonTeamStats.get('streak', 0)
            })
            team_standings.append(team_dict)
        
        # Sort by wins/losses
        team_standings.sort(key=lambda x: (x['wins'], -x['losses']), reverse=True)
        
        return {
            'standings': team_standings,
            'totalTeams': len(team_standings)
        }
    
    @staticmethod
    def buildScheduleResponse(games_by_week: Dict) -> Dict[str, Any]:
        """Build schedule response organized by week"""
        schedule = {}
        
        for week, games in games_by_week.items():
            schedule[week] = GameResponseBuilder.build_games_list_response(games)
        
        return {
            'schedule': schedule,
            'totalWeeks': len(schedule)
        }

# Convenience functions for common response patterns
def build_error_response(message: str, code: int = 400) -> Dict[str, Any]:
    """Build standardized error response"""
    return {
        'error': True,
        'message': message,
        'code': code
    }

def build_success_response(data: Any, message: str = "Success") -> Dict[str, Any]:
    """Build standardized success response"""
    return {
        'success': True,
        'message': message,
        'data': data
    }