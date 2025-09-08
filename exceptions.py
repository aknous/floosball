"""Custom exceptions for Floosball application"""

class FloosballException(Exception):
    """Base exception class for all Floosball-specific errors"""
    pass

class ValidationError(FloosballException):
    """Raised when input validation fails"""
    pass

class ConfigurationError(FloosballException):
    """Raised when there are configuration-related errors"""
    pass

class FileOperationError(FloosballException):
    """Raised when file operations fail"""
    pass

class PlayerError(FloosballException):
    """Raised when player-related operations fail"""
    pass

class TeamError(FloosballException):
    """Raised when team-related operations fail"""
    pass

class GameSimulationError(FloosballException):
    """Raised when game simulation encounters errors"""
    pass

class DatabaseError(FloosballException):
    """Raised when database operations fail"""
    pass

class APIError(FloosballException):
    """Raised when API operations fail"""
    pass

class StatisticsError(FloosballException):
    """Raised when statistics calculations fail"""
    pass