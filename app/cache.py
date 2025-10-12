"""
Redis caching utilities for the GitHub Auth App
"""
import json
import redis
from typing import Optional, Any, Union
from .config import settings
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis cache client wrapper with connection management"""
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._connection_pool = None
    
    def _get_client(self) -> redis.Redis:
        """Get or create Redis client with connection pooling"""
        if self._redis_client is None:
            try:
                # Parse Redis URL or use individual components
                if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                    self._redis_client = redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True
                    )
                else:
                    # Fallback to individual settings
                    host = getattr(settings, 'REDIS_HOST', 'redis')
                    port = getattr(settings, 'REDIS_PORT', 6379)
                    db = getattr(settings, 'REDIS_DB', 0)
                    
                    self._redis_client = redis.Redis(
                        host=host,
                        port=port,
                        db=db,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True
                    )
                
                # Test connection
                self._redis_client.ping()
                logger.info("Redis connection established successfully")
                
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                # Return a mock client that does nothing
                return MockRedisClient()
        
        return self._redis_client
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            client = self._get_client()
            value = client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache with optional expiration"""
        try:
            client = self._get_client()
            serialized_value = json.dumps(value)
            return client.set(key, serialized_value, ex=expire)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            client = self._get_client()
            return bool(client.delete(key))
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            client = self._get_client()
            return bool(client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key"""
        try:
            client = self._get_client()
            return bool(client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    def flushdb(self) -> bool:
        """Flush current database"""
        try:
            client = self._get_client()
            return client.flushdb()
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            client = self._get_client()
            return client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


class MockRedisClient:
    """Mock Redis client for when Redis is unavailable"""
    
    def get(self, key: str) -> Optional[str]:
        return None
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        return True
    
    def delete(self, key: str) -> bool:
        return True
    
    def exists(self, key: str) -> bool:
        return False
    
    def expire(self, key: str, seconds: int) -> bool:
        return True
    
    def flushdb(self) -> bool:
        return True
    
    def ping(self) -> bool:
        return False


# Global cache instance
cache = RedisCache()


# Cache key generators
def user_cache_key(user_id: Union[int, str]) -> str:
    """Generate cache key for user data"""
    return f"user:{user_id}"


def github_repo_cache_key(user_id: Union[int, str], repo_name: str) -> str:
    """Generate cache key for GitHub repository data"""
    return f"repo:{user_id}:{repo_name}"


def github_org_cache_key(user_id: Union[int, str]) -> str:
    """Generate cache key for GitHub organizations"""
    return f"orgs:{user_id}"


def session_cache_key(session_id: str) -> str:
    """Generate cache key for session data"""
    return f"session:{session_id}"


def oauth_token_cache_key(user_id: Union[int, str]) -> str:
    """Generate cache key for OAuth tokens"""
    return f"oauth_token:{user_id}"


# Cache decorators
def cached(expire: int = 300, key_func: Optional[callable] = None):
    """
    Decorator to cache function results
    
    Args:
        expire: Cache expiration time in seconds (default: 5 minutes)
        key_func: Function to generate cache key from function arguments
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, expire=expire)
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """
    Decorator to invalidate cache entries matching a pattern
    
    Args:
        pattern: Cache key pattern to invalidate
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            # Note: This is a simplified version
            # In production, you might want to use Redis SCAN to find matching keys
            logger.info(f"Cache invalidation triggered for pattern: {pattern}")
            return result
        return wrapper
    return decorator
