import logging
import sys
from logging.handlers import RotatingFileHandler
import os

class FloosballLogger:
    """Centralized logging configuration for Floosball"""
    
    def __init__(self, name: str = "floosball", level: str = "INFO", 
                 logToFile: bool = True, logToConsole: bool = True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Clear any existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        if logToConsole:
            consoleHandler = logging.StreamHandler(sys.stdout)
            consoleHandler.setLevel(logging.INFO)
            consoleHandler.setFormatter(formatter)
            self.logger.addHandler(consoleHandler)
        
        # File handler with rotation
        if logToFile:
            # Create logs directory if it doesn't exist
            if not os.path.exists('logs'):
                os.makedirs('logs')
            
            fileHandler = RotatingFileHandler(
                'logs/floosball.log',
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            fileHandler.setLevel(logging.DEBUG)
            fileHandler.setFormatter(formatter)
            self.logger.addHandler(fileHandler)
    
    def getLogger(self):
        return self.logger

# Global logger instances for different components
def getLogger(componentName: str = "floosball") -> logging.Logger:
    """Get a logger instance for a specific component"""
    loggerConfig = FloosballLogger(name=componentName)
    return loggerConfig.getLogger()

# Specialized loggers for different parts of the system
gameLogger = getLogger("floosball.game")
playerLogger = getLogger("floosball.player")
teamLogger = getLogger("floosball.team")
apiLogger = getLogger("floosball.api")
mainLogger = getLogger("floosball.main")
statsLogger = getLogger("floosball.stats")
simulationLogger = getLogger("floosball.simulation")

# Backward compatibility
def get_logger(componentName: str = "floosball") -> logging.Logger:
    """Backward compatibility function - use getLogger instead"""
    return getLogger(componentName)