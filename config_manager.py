"""Configuration management with caching and proper error handling"""

import json
import os
import time
from typing import Any, Dict, Optional, Union
from threading import Lock
from dataclasses import dataclass
from validators import InputValidator, ConfigValidator
from exceptions import ConfigurationError, FileOperationError
from logger_config import get_logger

logger = get_logger("floosball.config")

@dataclass
class CacheEntry:
    """Represents a cached configuration entry"""
    data: Dict[str, Any]
    timestamp: float
    file_path: str
    file_mtime: float

class ConfigManager:
    """
    Centralized configuration manager with caching and validation
    Replaces the repeated file operations in floosball_methods.py
    """
    
    def __init__(self, default_ttl: int = 300):  # 5 minute default TTL
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_lock = Lock()
        self._default_ttl = default_ttl
        
    def get_config(self, config_path: str = "config.json", ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        Get configuration with caching and validation
        
        Args:
            config_path: Path to configuration file
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            Dictionary containing configuration data
            
        Raises:
            ConfigurationError: If configuration is invalid
            FileOperationError: If file operations fail
        """
        ttl = ttl or self._default_ttl
        current_time = time.time()
        
        with self._cache_lock:
            # Check if we have a valid cache entry
            if config_path in self._cache:
                cache_entry = self._cache[config_path]
                
                # Check if cache is still valid (TTL and file modification time)
                cache_age = current_time - cache_entry.timestamp
                
                try:
                    current_mtime = os.path.getmtime(config_path)
                    file_unchanged = current_mtime == cache_entry.file_mtime
                    cache_valid = cache_age < ttl and file_unchanged
                    
                    if cache_valid:
                        logger.debug(f"Using cached config for {config_path}")
                        return cache_entry.data.copy()  # Return copy to prevent mutations
                        
                except OSError as e:
                    logger.warning(f"Could not check file modification time for {config_path}: {e}")
                    # File might have been deleted, invalidate cache
                    del self._cache[config_path]
            
            # Cache miss or invalid - load fresh data
            logger.debug(f"Loading fresh config from {config_path}")
            return self._load_and_cache_config(config_path)
    
    def _load_and_cache_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file and cache it"""
        try:
            # Validate file exists and is readable
            validated_path = InputValidator.validate_file_exists(config_path)
            
            # Load and validate JSON
            config_data = InputValidator.validate_json_file(validated_path)
            
            # Apply configuration-specific validation
            if config_path.endswith("config.json"):
                config_data = ConfigValidator.validate_league_config(config_data)
            
            # Override sensitive values from env vars when present
            _envOverrides = {
                'adminPassword': os.environ.get('ADMIN_PASSWORD'),
                'clerkJwksUrl': os.environ.get('CLERK_JWKS_URL'),
                'resendApiKey': os.environ.get('RESEND_API_KEY'),
                'emailFrom': os.environ.get('EMAIL_FROM'),
            }
            for key, val in _envOverrides.items():
                if val is not None:
                    config_data[key] = val

            # Cache the data
            file_mtime = os.path.getmtime(validated_path)
            cache_entry = CacheEntry(
                data=config_data.copy(),
                timestamp=time.time(),
                file_path=validated_path,
                file_mtime=file_mtime
            )
            
            self._cache[config_path] = cache_entry
            logger.info(f"Cached configuration from {config_path}")
            
            return config_data
            
        except (FileOperationError, ConfigurationError):
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            raise ConfigurationError(f"Unexpected error loading config from {config_path}: {e}")
    
    def save_config(self, config_data: Dict[str, Any], config_path: str = "config.json") -> None:
        """
        Save configuration to file and update cache
        
        Args:
            config_data: Configuration data to save
            config_path: Path to save configuration file
            
        Raises:
            ConfigurationError: If configuration data is invalid
            FileOperationError: If file operations fail
        """
        try:
            # Validate configuration data before saving
            if config_path.endswith("config.json"):
                validated_data = ConfigValidator.validate_league_config(config_data)
            else:
                validated_data = config_data
            
            # Create backup of existing file if it exists
            backup_path = None
            if os.path.exists(config_path):
                backup_path = f"{config_path}.backup"
                try:
                    os.rename(config_path, backup_path)
                except OSError as e:
                    logger.warning(f"Could not create backup of {config_path}: {e}")
            
            # Write new configuration
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(validated_data, f, indent=4, ensure_ascii=False)
                
                logger.info(f"Configuration saved to {config_path}")
                
                # Update cache
                with self._cache_lock:
                    file_mtime = os.path.getmtime(config_path)
                    cache_entry = CacheEntry(
                        data=validated_data.copy(),
                        timestamp=time.time(),
                        file_path=config_path,
                        file_mtime=file_mtime
                    )
                    self._cache[config_path] = cache_entry
                
                # Remove backup on successful write
                if backup_path and os.path.exists(backup_path):
                    os.remove(backup_path)
                    
            except Exception as e:
                # Restore backup on failure
                if backup_path and os.path.exists(backup_path):
                    os.rename(backup_path, config_path)
                raise FileOperationError(f"Failed to write config to {config_path}: {e}")
                
        except (ConfigurationError, FileOperationError):
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            raise ConfigurationError(f"Unexpected error saving config to {config_path}: {e}")
    
    def update_config_value(self, key1: str, key2: Optional[str], value: Any, 
                           config_path: str = "config.json") -> None:
        """
        Update a specific configuration value (replaces saveConfig from floosball_methods.py)
        
        Args:
            key1: First level key
            key2: Second level key (optional)
            value: Value to set
            config_path: Path to configuration file
        """
        try:
            # Get current configuration
            config = self.get_config(config_path)
            
            # Update the value
            if key2 is None:
                config[key1] = value
            else:
                if key1 not in config:
                    config[key1] = {}
                config[key1][key2] = value
            
            # Save updated configuration
            self.save_config(config, config_path)
            
            logger.info(f"Updated config: {key1}.{key2} = {value}" if key2 else f"Updated config: {key1} = {value}")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to update config value {key1}.{key2}: {e}")
    
    def clear_cache(self, config_path: Optional[str] = None) -> None:
        """
        Clear cached configuration data
        
        Args:
            config_path: Specific path to clear (clears all if None)
        """
        with self._cache_lock:
            if config_path:
                if config_path in self._cache:
                    del self._cache[config_path]
                    logger.debug(f"Cleared cache for {config_path}")
            else:
                cache_count = len(self._cache)
                self._cache.clear()
                logger.debug(f"Cleared all cached configurations ({cache_count} entries)")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached configurations"""
        with self._cache_lock:
            current_time = time.time()
            cache_info = {}
            
            for path, entry in self._cache.items():
                cache_age = current_time - entry.timestamp
                cache_info[path] = {
                    'age_seconds': cache_age,
                    'file_path': entry.file_path,
                    'cached_at': entry.timestamp,
                    'file_mtime': entry.file_mtime
                }
            
            return cache_info
    
    def preload_configs(self, config_paths: list) -> None:
        """Preload multiple configuration files into cache"""
        for config_path in config_paths:
            try:
                self.get_config(config_path)
                logger.debug(f"Preloaded config: {config_path}")
            except Exception as e:
                logger.warning(f"Failed to preload config {config_path}: {e}")

# Global instance for use throughout the application
config_manager = ConfigManager()

# Convenience functions for backwards compatibility
def get_config() -> Dict[str, Any]:
    """Get main configuration (backwards compatible)"""
    return config_manager.get_config("config.json")

def save_config_value(value: Any, key1: str, key2: Optional[str] = None) -> None:
    """Save configuration value (backwards compatible)"""  
    config_manager.update_config_value(key1, key2, value)