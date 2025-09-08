"""Rating calculation caching system to improve performance"""

import time
import hashlib
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from threading import Lock
from logger_config import get_logger

logger = get_logger("floosball.rating_cache")

@dataclass
class CacheEntry:
    """Represents a cached rating calculation"""
    value: float
    timestamp: float
    attributes_hash: str

class RatingCalculationCache:
    """Cache for expensive rating calculations"""
    
    def __init__(self, ttl_seconds: int = 60):  # 1 minute default TTL
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_lock = Lock()
        self._ttl = ttl_seconds
        self._hit_count = 0
        self._miss_count = 0
    
    def _generate_attributes_hash(self, attributes: Any) -> str:
        """Generate a hash of the attributes that affect rating calculations"""
        # Get the key attributes that affect ratings
        key_attrs = []
        
        # Position-specific attributes
        if hasattr(attributes, 'armStrength'):
            key_attrs.extend([
                getattr(attributes, 'armStrength', 0),
                getattr(attributes, 'accuracy', 0),
                getattr(attributes, 'agility', 0)
            ])
        elif hasattr(attributes, 'speed'):
            key_attrs.extend([
                getattr(attributes, 'speed', 0),
                getattr(attributes, 'power', 0) or getattr(attributes, 'hands', 0),
                getattr(attributes, 'agility', 0)
            ])
        elif hasattr(attributes, 'legStrength'):
            key_attrs.extend([
                getattr(attributes, 'legStrength', 0),
                getattr(attributes, 'accuracy', 0)
            ])
        
        # Common attributes that affect all ratings
        key_attrs.extend([
            getattr(attributes, 'playMakingAbility', 0),
            getattr(attributes, 'xFactor', 0),
            getattr(attributes, 'confidenceModifier', 0),
            getattr(attributes, 'determinationModifier', 0),
            getattr(attributes, 'attitude', 0),
            getattr(attributes, 'discipline', 0)
        ])
        
        # Convert to string and hash
        attrs_str = ','.join(map(str, key_attrs))
        return hashlib.md5(attrs_str.encode()).hexdigest()
    
    def get_cached_rating(self, cache_key: str, attributes: Any) -> Optional[float]:
        """Get cached rating if valid, None otherwise"""
        with self._cache_lock:
            if cache_key not in self._cache:
                self._miss_count += 1
                return None
            
            entry = self._cache[cache_key]
            current_time = time.time()
            
            # Check if cache entry is expired
            if current_time - entry.timestamp > self._ttl:
                del self._cache[cache_key]
                self._miss_count += 1
                return None
            
            # Check if attributes have changed
            current_hash = self._generate_attributes_hash(attributes)
            if entry.attributes_hash != current_hash:
                del self._cache[cache_key]
                self._miss_count += 1
                return None
            
            self._hit_count += 1
            logger.debug(f"Cache hit for {cache_key}")
            return entry.value
    
    def cache_rating(self, cache_key: str, rating: float, attributes: Any) -> None:
        """Cache a rating calculation result"""
        with self._cache_lock:
            attributes_hash = self._generate_attributes_hash(attributes)
            entry = CacheEntry(
                value=rating,
                timestamp=time.time(),
                attributes_hash=attributes_hash
            )
            self._cache[cache_key] = entry
            logger.debug(f"Cached rating for {cache_key}: {rating}")
    
    def invalidate_cache(self, cache_key: Optional[str] = None) -> None:
        """Invalidate specific cache entry or all entries"""
        with self._cache_lock:
            if cache_key:
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    logger.debug(f"Invalidated cache for {cache_key}")
            else:
                cache_count = len(self._cache)
                self._cache.clear()
                logger.debug(f"Invalidated all cache entries ({cache_count} entries)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self._cache_lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate_percent': round(hit_rate, 2),
                'cache_size': len(self._cache),
                'ttl_seconds': self._ttl
            }
    
    def cleanup_expired_entries(self) -> int:
        """Remove expired cache entries and return count removed"""
        with self._cache_lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if current_time - entry.timestamp > self._ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)

# Global cache instance
rating_cache = RatingCalculationCache()

class CachedRatingMixin:
    """Mixin to add caching to rating calculations"""
    
    def get_cached_skill_rating(self) -> float:
        """Get cached skill rating or calculate and cache if needed"""
        cache_key = f"{self.__class__.__name__}_{id(self)}_skill"
        
        cached_rating = rating_cache.get_cached_rating(cache_key, self.attributes)
        if cached_rating is not None:
            return cached_rating
        
        # Calculate rating (this logic will vary by position)
        rating = self._calculate_skill_rating()
        rating_cache.cache_rating(cache_key, rating, self.attributes)
        return rating
    
    def get_cached_overall_rating(self) -> float:
        """Get cached overall rating or calculate and cache if needed"""
        cache_key = f"{self.__class__.__name__}_{id(self)}_overall"
        
        cached_rating = rating_cache.get_cached_rating(cache_key, self.attributes)
        if cached_rating is not None:
            return cached_rating
        
        # Use cached skill rating for overall calculation
        skill_rating = self.get_cached_skill_rating()
        rating = round(((skill_rating*2) + (self.attributes.playMakingAbility*1.5) + (self.attributes.xFactor*1.5))/5)
        rating_cache.cache_rating(cache_key, rating, self.attributes)
        return rating
    
    def invalidate_rating_cache(self):
        """Invalidate this object's cached ratings"""
        skill_key = f"{self.__class__.__name__}_{id(self)}_skill"
        overall_key = f"{self.__class__.__name__}_{id(self)}_overall"
        rating_cache.invalidate_cache(skill_key)
        rating_cache.invalidate_cache(overall_key)
    
    def _calculate_skill_rating(self) -> float:
        """Override this in subclasses with position-specific logic"""
        raise NotImplementedError("Subclasses must implement _calculate_skill_rating")

def log_cache_stats():
    """Log current cache statistics"""
    stats = rating_cache.get_cache_stats()
    logger.info(f"Rating cache stats: {stats}")

def cleanup_rating_cache():
    """Cleanup expired rating cache entries"""
    count = rating_cache.cleanup_expired_entries()
    if count > 0:
        logger.info(f"Cleaned up {count} expired rating cache entries")