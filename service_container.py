"""Service container for dependency injection and global state management"""

from typing import Dict, Any, Optional, Type, Callable
from threading import Lock
from logger_config import get_logger

logger = get_logger("floosball.services")

class ServiceContainer:
    """Dependency injection container for managing services and global state"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._lock = Lock()
    
    def registerService(self, name: str, serviceInstance: Any):
        """Register a service instance"""
        with self._lock:
            self._services[name] = serviceInstance
            logger.debug(f"Registered service: {name}")
    
    def registerFactory(self, name: str, factoryFunc: Callable):
        """Register a factory function for creating service instances"""
        with self._lock:
            self._factories[name] = factoryFunc
            logger.debug(f"Registered factory: {name}")
    
    def registerSingleton(self, name: str, factoryFunc: Callable):
        """Register a singleton service (created once, reused)"""
        with self._lock:
            self._factories[name] = factoryFunc
            logger.debug(f"Registered singleton: {name}")
    
    def getService(self, name: str) -> Any:
        """Get a service by name"""
        with self._lock:
            # Check if it's a direct service
            if name in self._services:
                return self._services[name]
            
            # Check if it's a singleton (already created)
            if name in self._singletons:
                return self._singletons[name]
            
            # Check if we have a factory for it
            if name in self._factories:
                factory = self._factories[name]
                instance = factory()
                
                # If this was registered as singleton, cache it
                if name in self._singletons or name.endswith('_singleton'):
                    self._singletons[name] = instance
                
                return instance
            
            raise ValueError(f"Service '{name}' not found in container")
    
    def hasService(self, name: str) -> bool:
        """Check if a service is available"""
        with self._lock:
            return (name in self._services or 
                   name in self._singletons or 
                   name in self._factories)
    
    def listServices(self) -> list:
        """List all available services"""
        with self._lock:
            allServices = set()
            allServices.update(self._services.keys())
            allServices.update(self._singletons.keys())
            allServices.update(self._factories.keys())
            return sorted(list(allServices))
    
    def clearService(self, name: str):
        """Remove a service from the container"""
        with self._lock:
            self._services.pop(name, None)
            self._singletons.pop(name, None)
            self._factories.pop(name, None)
            logger.debug(f"Cleared service: {name}")
    
    def clearAll(self):
        """Clear all services"""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._singletons.clear()
            logger.debug("Cleared all services")

class GameStateManager:
    """Manages global game state to avoid global variables"""
    
    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._lock = Lock()
    
    def setState(self, key: str, value: Any):
        """Set a state value"""
        with self._lock:
            self._state[key] = value
            logger.debug(f"Set game state: {key}")
    
    def getState(self, key: str, default: Any = None) -> Any:
        """Get a state value"""
        with self._lock:
            return self._state.get(key, default)
    
    def updateState(self, updates: Dict[str, Any]):
        """Update multiple state values"""
        with self._lock:
            self._state.update(updates)
            logger.debug(f"Updated game state: {list(updates.keys())}")
    
    def clearState(self, key: Optional[str] = None):
        """Clear specific state or all state"""
        with self._lock:
            if key:
                self._state.pop(key, None)
                logger.debug(f"Cleared game state: {key}")
            else:
                self._state.clear()
                logger.debug("Cleared all game state")
    
    def getAllState(self) -> Dict[str, Any]:
        """Get copy of all current state"""
        with self._lock:
            return self._state.copy()

class ConfigurationManager:
    """Centralized configuration management"""
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._lock = Lock()
        self._config_loaded = False
    
    def loadConfig(self, configData: Dict[str, Any]):
        """Load configuration data"""
        with self._lock:
            self._config = configData.copy()
            self._config_loaded = True
            logger.info("Configuration loaded")
    
    def getConfig(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        with self._lock:
            return self._config.get(key, default)
    
    def getNestedConfig(self, *keys, default: Any = None) -> Any:
        """Get nested configuration value"""
        with self._lock:
            current = self._config
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
    
    def setConfig(self, key: str, value: Any):
        """Set configuration value"""
        with self._lock:
            self._config[key] = value
            logger.debug(f"Updated config: {key}")
    
    def isLoaded(self) -> bool:
        """Check if configuration is loaded"""
        with self._lock:
            return self._config_loaded

# Global service container instance
container = ServiceContainer()
gameState = GameStateManager()
configManager = ConfigurationManager()

# Register core services
container.registerService('game_state', gameState)
container.registerService('config_manager', configManager)

def getService(name: str) -> Any:
    """Convenience function to get service from global container"""
    return container.getService(name)

def registerService(name: str, service: Any):
    """Convenience function to register service in global container"""
    container.registerService(name, service)

def registerFactory(name: str, factory: Callable):
    """Convenience function to register factory in global container"""
    container.registerFactory(name, factory)

# Game state convenience functions
def setGameState(key: str, value: Any):
    """Set global game state"""
    gameState.setState(key, value)

def getGameState(key: str, default: Any = None) -> Any:
    """Get global game state"""
    return gameState.getState(key, default)

def updateGameState(updates: Dict[str, Any]):
    """Update multiple game state values"""
    gameState.updateState(updates)

# Configuration convenience functions  
def loadGameConfig(configData: Dict[str, Any]):
    """Load game configuration"""
    configManager.loadConfig(configData)

def getGameConfig(key: str, default: Any = None) -> Any:
    """Get game configuration value"""
    return configManager.getConfig(key, default)

def getNestedGameConfig(*keys, default: Any = None) -> Any:
    """Get nested game configuration value"""
    return configManager.getNestedConfig(*keys, default=default)

# Factory functions for common services
def createRatingCache():
    """Factory for rating cache service"""
    from rating_cache import RatingCalculationCache
    return RatingCalculationCache()

def createStatsPool():
    """Factory for stats pool service"""
    from stats_optimization import StatsPool
    return StatsPool()

def createRandomBatch():
    """Factory for random batch service"""
    from random_batch import RangeSpecificBatch
    return RangeSpecificBatch()

# Register factories for lazy loading
registerFactory('rating_cache', createRatingCache)
registerFactory('stats_pool', createStatsPool)
registerFactory('random_batch', createRandomBatch)

def initializeServices():
    """Initialize all core services"""
    logger.info("Initializing service container...")
    
    # Pre-load critical services
    ratingCache = getService('rating_cache')
    statsPool = getService('stats_pool')
    randomBatch = getService('random_batch')
    
    logger.info(f"Services initialized: {container.listServices()}")

def shutdownServices():
    """Cleanup and shutdown services"""
    logger.info("Shutting down services...")
    
    # Clear all caches and pools
    try:
        ratingCache = getService('rating_cache')
        ratingCache.cleanupExpiredEntries()
    except:
        pass
    
    try:
        randomBatch = getService('random_batch')
        randomBatch.clearLeastUsedRanges(0)
    except:
        pass
    
    # Clear global state
    gameState.clearState()
    
    logger.info("Services shutdown complete")