"""Batched random number generation for improved performance"""

import random
from typing import List, Iterator, Optional
from threading import Lock
from logger_config import get_logger

logger = get_logger("floosball.random_batch")

class RandomBatch:
    """Batch random number generator for improved performance"""
    
    def __init__(self, batch_size: int = 1000):
        self.batch_size = batch_size
        self._randint_cache: List[int] = []
        self._random_cache: List[float] = []
        self._cache_lock = Lock()
        self._generation_count = 0
        
    def _refill_randint_cache(self, min_val: int, max_val: int):
        """Refill the randint cache with new values"""
        with self._cache_lock:
            # Only refill if cache is actually empty (double-check)
            if not self._randint_cache:
                self._randint_cache = [
                    random.randint(min_val, max_val) 
                    for _ in range(self.batch_size)
                ]
                self._generation_count += 1
                logger.debug(f"Generated batch #{self._generation_count} of randint({min_val}, {max_val})")
    
    def _refill_random_cache(self):
        """Refill the random float cache with new values"""
        with self._cache_lock:
            if not self._random_cache:
                self._random_cache = [
                    random.random() 
                    for _ in range(self.batch_size)
                ]
                self._generation_count += 1
                logger.debug(f"Generated batch #{self._generation_count} of random floats")
    
    def randint(self, min_val: int, max_val: int) -> int:
        """Get a random integer from the batch cache"""
        # For now, we'll use separate caches for different ranges
        # In a more sophisticated implementation, we could normalize ranges
        if not self._randint_cache:
            self._refill_randint_cache(min_val, max_val)
        
        with self._cache_lock:
            if self._randint_cache:
                value = self._randint_cache.pop()
                # Adjust value to the requested range if needed
                if value < min_val or value > max_val:
                    # Fallback to direct generation for mismatched ranges
                    return random.randint(min_val, max_val)
                return value
            else:
                # Cache empty, generate directly
                return random.randint(min_val, max_val)
    
    def random(self) -> float:
        """Get a random float from the batch cache"""
        if not self._random_cache:
            self._refill_random_cache()
        
        with self._cache_lock:
            if self._random_cache:
                return self._random_cache.pop()
            else:
                return random.random()
    
    def choice(self, sequence):
        """Random choice using batched random"""
        if not sequence:
            raise IndexError("Cannot choose from empty sequence")
        
        # Use batched random to get index
        random_val = self.random()
        index = int(random_val * len(sequence))
        return sequence[index]
    
    def shuffle(self, sequence):
        """Shuffle sequence using batched random"""
        # For small sequences, use standard shuffle
        if len(sequence) < 10:
            random.shuffle(sequence)
            return
        
        # For larger sequences, use batched random
        for i in range(len(sequence) - 1, 0, -1):
            j = int(self.random() * (i + 1))
            sequence[i], sequence[j] = sequence[j], sequence[i]
    
    def get_cache_stats(self) -> dict:
        """Get statistics about cache usage"""
        with self._cache_lock:
            return {
                'randint_cache_size': len(self._randint_cache),
                'random_cache_size': len(self._random_cache),
                'batch_size': self.batch_size,
                'generation_count': self._generation_count
            }
    
    def clear_caches(self):
        """Clear all caches"""
        with self._cache_lock:
            self._randint_cache.clear()
            self._random_cache.clear()
            logger.debug("Cleared all random number caches")

class RangeSpecificBatch:
    """More sophisticated batch generator for specific ranges"""
    
    def __init__(self, batch_size: int = 500):
        self.batch_size = batch_size
        self._range_caches = {}  # Dict of (min, max) -> List[int]
        self._cache_lock = Lock()
        self._hit_count = 0
        self._miss_count = 0
    
    def _get_cache_key(self, min_val: int, max_val: int) -> tuple:
        """Get cache key for a range"""
        return (min_val, max_val)
    
    def randint(self, min_val: int, max_val: int) -> int:
        """Get random int with range-specific caching"""
        cache_key = self._get_cache_key(min_val, max_val)
        
        with self._cache_lock:
            # Check if we have cached values for this range
            if cache_key in self._range_caches and self._range_caches[cache_key]:
                self._hit_count += 1
                return self._range_caches[cache_key].pop()
            
            # Cache miss - generate new batch for this range
            self._miss_count += 1
            new_batch = [
                random.randint(min_val, max_val)
                for _ in range(self.batch_size)
            ]
            self._range_caches[cache_key] = new_batch
            
            logger.debug(f"Generated new batch for range ({min_val}, {max_val})")
            return new_batch.pop()
    
    def get_stats(self) -> dict:
        """Get cache performance statistics"""
        with self._cache_lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate_percent': round(hit_rate, 2),
                'cached_ranges': len(self._range_caches),
                'total_cached_values': sum(len(cache) for cache in self._range_caches.values())
            }
    
    def clear_least_used_ranges(self, keep_count: int = 5):
        """Clear least recently used range caches, keeping only the specified count"""
        with self._cache_lock:
            if len(self._range_caches) > keep_count:
                # Sort by cache size (assuming more used ranges have fewer remaining values)
                sorted_ranges = sorted(self._range_caches.items(), 
                                     key=lambda x: len(x[1]), reverse=True)
                
                # Keep only the top ranges
                self._range_caches = dict(sorted_ranges[:keep_count])
                logger.debug(f"Cleared old range caches, kept {keep_count} most used ranges")

# Global batch generators
default_batch = RandomBatch()
range_batch = RangeSpecificBatch()

# Convenience functions that can replace standard random calls
def batched_randint(min_val: int, max_val: int) -> int:
    """Batched version of random.randint()"""
    return range_batch.randint(min_val, max_val)

def batched_random() -> float:
    """Batched version of random.random()"""
    return default_batch.random()

def batched_choice(sequence):
    """Batched version of random.choice()"""
    return default_batch.choice(sequence)

def get_batch_stats() -> dict:
    """Get statistics from all batch generators"""
    return {
        'default_batch': default_batch.get_cache_stats(),
        'range_batch': range_batch.get_stats()
    }

def log_batch_performance():
    """Log batch generator performance statistics"""
    stats = get_batch_stats()
    logger.info(f"Random batch performance: {stats}")

def clear_all_batch_caches():
    """Clear all batch generator caches"""
    default_batch.clear_caches()
    range_batch.clear_least_used_ranges(0)  # Clear all
    logger.info("Cleared all random batch caches")