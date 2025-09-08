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
        """Calculate star rating from numeric rating"""
        return round((((rating - minRating) / ratingRange) * STARS_MAX) + 1)
    
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
            'id': team.id,
            'elo': team.elo,
            'eliminated': team.eliminated,
            'wins': wins,
            'losses': losses,
            'winPerc': TeamResponseBuilder.calculate_win_percentage(wins, losses),
            'clinchedPlayoffs': team.clinchedPlayoffs,
            'clinchedTopSeed': team.clinchedTopSeed,
            'leagueChampion': team.leagueChampion,
            'floosbowlChampion': team.floosbowlChampion,
            'winningStreak': team.winningStreak
        }
    
    @staticmethod
    def buildTeamWithRatings(team) -> Dict[str, Any]:
        """Build team dictionary with rating information"""
        team_dict = TeamResponseBuilder.build_basic_team_dict(team)
        
        # Add rating calculations
        team_dict.update({
            'ratingStars': TeamResponseBuilder.calculate_star_rating(team.overallRating, RATING_SCALE_MIN, RATING_SCALE_MIN),
            'offenseRatingStars': TeamResponseBuilder.calculate_star_rating(team.offenseRating),
            'runDefenseRating': TeamResponseBuilder.calculate_star_rating(team.defenseRunCoverageRating),
            'passDefenseRating': TeamResponseBuilder.calculate_star_rating(team.defensePassCoverageRating, RATING_SCALE_MIN, RATING_SCALE_MIN),
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
    def build_basic_player_dict(player) -> Dict[str, Any]:
        """Build basic player information dictionary"""
        return {
            'name': player.name,
            'id': player.id,
            'position': player.position.name,
            'team': player.team.name if player.team else None,
            'teamCity': player.team.city if player.team else None,
            'teamColor': player.team.color if player.team else None,
            'seasonsPlayed': player.seasonsPlayed,
            'ratingStars': PlayerResponseBuilder.calculate_star_rating(player.playerRating),
            'playerRating': player.playerRating
        }
    
    @staticmethod
    def build_player_with_attributes(player) -> Dict[str, Any]:
        """Build player dictionary with detailed attributes"""
        player_dict = PlayerResponseBuilder.build_basic_player_dict(player)
        
        # Add position-specific attributes
        attr_dict = {}
        
        if hasattr(player.attributes, 'armStrength'):  # QB
            attr_dict.update({
                'att1': 'Arm Strength',
                'att1Value': player.attributes.armStrength,
                'att1stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.armStrength),
                'att2': 'Accuracy', 
                'att2Value': player.attributes.accuracy,
                'att2stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.accuracy),
                'att3': 'Agility',
                'att3Value': player.attributes.agility,
                'att3stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.agility),
                
                # Potential attributes
                'att1PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialArmStrength),
                'att2PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialAccuracy),
                'att3PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialAgility)
            })
        elif hasattr(player.attributes, 'speed'):  # Skill positions
            if hasattr(player.attributes, 'power'):  # RB
                attr_dict.update({
                    'att1': 'Speed',
                    'att1Value': player.attributes.speed,
                    'att1stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.speed),
                    'att2': 'Power',
                    'att2Value': player.attributes.power, 
                    'att2stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.power),
                    'att3': 'Agility',
                    'att3Value': player.attributes.agility,
                    'att3stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.agility),
                    
                    # Potential
                    'att1PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialSpeed),
                    'att2PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialPower),
                    'att3PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialAgility)
                })
            else:  # WR/TE - hands instead of power
                attr_dict.update({
                    'att1': 'Speed',
                    'att1Value': player.attributes.speed,
                    'att1stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.speed),
                    'att2': 'Hands',
                    'att2Value': player.attributes.hands,
                    'att2stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.hands),
                    'att3': 'Agility', 
                    'att3Value': player.attributes.agility,
                    'att3stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.agility),
                    
                    # Potential
                    'att1PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialSpeed),
                    'att2PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialHands),
                    'att3PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialAgility)
                })
        elif hasattr(player.attributes, 'legStrength'):  # Kicker
            attr_dict.update({
                'att1': 'Leg Strength',
                'att1Value': player.attributes.legStrength,
                'att1stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.legStrength),
                'att2': 'Accuracy',
                'att2Value': player.attributes.accuracy,
                'att2stars': PlayerResponseBuilder.calculate_star_rating(player.attributes.accuracy),
                
                # Potential
                'att1PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialLegStrength),
                'att2PotStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.potentialAccuracy)
            })
        
        # Add common attributes
        attr_dict.update({
            'playmakingStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.playMakingAbility),
            'playmakingValue': player.attributes.playMakingAbility,
            'xFactorStars': PlayerResponseBuilder.calculate_star_rating(player.attributes.xFactor),
            'xFactorValue': player.attributes.xFactor
        })
        
        # Add season performance if available
        if hasattr(player, 'seasonPerformanceRating') and player.seasonPerformanceRating > 0:
            attr_dict['seasonPerformanceRatingStars'] = PlayerResponseBuilder.calculate_star_rating(player.seasonPerformanceRating)
            attr_dict['seasonPerformanceRating'] = player.seasonPerformanceRating
        
        player_dict['attributes'] = attr_dict
        return player_dict
    
    @staticmethod
    def build_player_with_stats(player) -> Dict[str, Any]:
        """Build player dictionary with game statistics"""
        player_dict = PlayerResponseBuilder.build_basic_player_dict(player)
        
        # Add game stats with calculated percentages
        stats = player.gameStatsDict
        stats_dict = {}
        
        # Passing stats
        if stats['passing']['att'] > 0:
            stats_dict['passing'] = {
                **stats['passing'],
                'compPerc': PlayerResponseBuilder.safe_percentage(
                    stats['passing']['comp'], 
                    stats['passing']['att']
                )
            }
        
        # Receiving stats 
        if stats['receiving']['targets'] > 0:
            stats_dict['receiving'] = {
                **stats['receiving'],
                'rcvPerc': PlayerResponseBuilder.safe_percentage(
                    stats['receiving']['receptions'],
                    stats['receiving']['targets']
                )
            }
        
        # Kicking stats
        if stats['kicking']['fgAtt'] > 0:
            stats_dict['kicking'] = {
                **stats['kicking'],
                'fgPerc': PlayerResponseBuilder.safe_percentage(
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
    def build_basic_game_dict(game) -> Dict[str, Any]:
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
            'isComplete': game.isComplete,
            'winningTeam': game.winningTeam.name if game.winningTeam else None
        }
    
    @staticmethod
    def build_game_with_probabilities(game) -> Dict[str, Any]:
        """Build game dictionary with win probabilities"""
        game_dict = GameResponseBuilder.build_basic_game_dict(game)
        
        game_dict.update({
            'homeTeamWinProbability': round(game.homeTeamWinProbability * PERCENTAGE_MULTIPLIER),
            'awayTeamWinProbability': round(game.awayTeamWinProbability * PERCENTAGE_MULTIPLIER)
        })
        
        return game_dict
    
    @staticmethod
    def build_games_list_response(games: List) -> List[Dict[str, Any]]:
        """Build response for list of games"""
        return [GameResponseBuilder.build_game_with_probabilities(game) for game in games]

class LeagueResponseBuilder(ResponseBuilder):
    """Builder for league-wide responses"""
    
    @staticmethod
    def build_standings_response(teams: List) -> Dict[str, Any]:
        """Build league standings response"""
        team_standings = []
        
        for team in teams:
            team_dict = TeamResponseBuilder.build_team_with_ratings(team)
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
    def build_schedule_response(games_by_week: Dict) -> Dict[str, Any]:
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