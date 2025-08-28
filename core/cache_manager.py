"""
Cache manager for real-time processing

Manages in-memory caching of processed geometry data to enable
fast parameter updates without reprocessing the entire model.
"""

import time
from typing import Dict, Any, Optional
import logging
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Thread-safe in-memory cache for geometry and processing results
    """
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initialize cache manager
        
        Args:
            max_size: Maximum number of cached items
            ttl: Time to live in seconds (default: 1 hour)
        """
        self.max_size = max_size
        self.ttl = ttl
        
        # Thread-safe cache storage
        self._geometry_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._client_cache: Dict[str, set] = {}  # Track cache keys per client
        self._lock = threading.RLock()
        
        logger.info(f"Cache manager initialized with max_size={max_size}, ttl={ttl}s")
    
    def get_geometry(self, model_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached geometry data
        
        Args:
            model_hash: Hash of the model data
            
        Returns:
            Cached geometry data or None if not found/expired
        """
        with self._lock:
            if model_hash not in self._geometry_cache:
                return None
            
            cache_entry = self._geometry_cache[model_hash]
            
            # Check if entry has expired
            if time.time() - cache_entry['timestamp'] > self.ttl:
                logger.info(f"Cache entry expired for hash {model_hash}")
                del self._geometry_cache[model_hash]
                return None
            
            # Move to end (LRU behavior)
            self._geometry_cache.move_to_end(model_hash)
            
            logger.debug(f"Cache hit for hash {model_hash}")
            return cache_entry['data']
    
    def set_geometry(self, model_hash: str, geometry_data: Dict[str, Any]):
        """
        Store geometry data in cache
        
        Args:
            model_hash: Hash of the model data
            geometry_data: Geometry data to cache
        """
        with self._lock:
            # Remove oldest items if cache is full
            while len(self._geometry_cache) >= self.max_size:
                oldest_key = next(iter(self._geometry_cache))
                logger.info(f"Evicting oldest cache entry: {oldest_key}")
                del self._geometry_cache[oldest_key]
            
            # Store new entry
            self._geometry_cache[model_hash] = {
                'data': geometry_data,
                'timestamp': time.time()
            }
            
            logger.info(f"Cached geometry for hash {model_hash}. Cache size: {len(self._geometry_cache)}")
    
    def remove_client_cache(self, client_id: str):
        """
        Remove all cache entries associated with a client
        
        Args:
            client_id: Client identifier
        """
        with self._lock:
            if client_id in self._client_cache:
                for cache_key in self._client_cache[client_id]:
                    if cache_key in self._geometry_cache:
                        del self._geometry_cache[cache_key]
                        logger.debug(f"Removed cache entry {cache_key} for client {client_id}")
                
                del self._client_cache[client_id]
                logger.info(f"Cleaned up cache for client {client_id}")
    
    def track_client_cache(self, client_id: str, cache_key: str):
        """
        Track cache keys used by a client for cleanup
        
        Args:
            client_id: Client identifier
            cache_key: Cache key to track
        """
        with self._lock:
            if client_id not in self._client_cache:
                self._client_cache[client_id] = set()
            self._client_cache[client_id].add(cache_key)
    
    def clear_expired(self):
        """Remove all expired cache entries"""
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._geometry_cache.items():
                if current_time - entry['timestamp'] > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._geometry_cache[key]
                logger.debug(f"Removed expired cache entry: {key}")
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def clear_all(self):
        """Clear all cache entries"""
        with self._lock:
            count = len(self._geometry_cache)
            self._geometry_cache.clear()
            self._client_cache.clear()
            logger.info(f"Cleared all {count} cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._geometry_cache),
                'max_size': self.max_size,
                'ttl': self.ttl,
                'clients_tracked': len(self._client_cache)
            }