import logging
from typing import Optional
from redis import Redis
from redis.sentinel import Sentinel
from config import get_config_by_name

# Global variables
redis_client: Optional[Redis] = None
sentinel: Optional[Sentinel] = None


def get_redis_client() -> Redis:
    global redis_client, sentinel
    if redis_client is None:
        connection_type = get_config_by_name("REDIS_OR_SENTINEL", "REDIS").upper()

        if connection_type == "SENTINEL":
            sentinel_hosts = get_config_by_name("REDIS_HOST").split(',')
            sentinel_port = int(get_config_by_name("REDIS_PORT", "26379"))
            master_name = get_config_by_name("REDIS_MASTER_NAME", "mymaster")
            db = int(get_config_by_name("REDIS_DB", "0"))

            sentinel_nodes = [(host.strip(), sentinel_port) for host in sentinel_hosts]
            logging.info(f"Connecting to Redis Sentinel: Hosts={sentinel_hosts}, Port={sentinel_port}, Master={master_name}")

            try:
                sentinel = Sentinel(
                    sentinel_nodes,
                    socket_timeout=0.1,
                    db=db
                )
                redis_client = sentinel.master_for(
                    master_name,
                    socket_timeout=0.1,
                    db=db
                )
                # Test the connection
                redis_client.ping()
                logging.info("Successfully connected to Redis through Sentinel")
            except Exception as e:
                logging.error(f"Failed to connect to Redis Sentinel: {str(e)}")
                raise
        else:  # REDIS
            host = get_config_by_name("REDIS_HOST")
            port = int(get_config_by_name("REDIS_PORT", "6379"))
            db = int(get_config_by_name("REDIS_DB", "0"))

            logging.info(f"Connecting to Redis: Host={host}, Port={port}, DB={db}")

            try:
                redis_client = Redis(
                    host=host,
                    port=port,
                    db=db,
                    socket_timeout=0.1
                )
                # Test the connection
                redis_client.ping()
                logging.info("Successfully connected to Redis")
            except Exception as e:
                logging.error(f"Failed to connect to Redis: {str(e)}")
                raise

    return redis_client


def init_redis_cache():
    get_redis_client()


def get_redis_cache(key: str) -> Optional[bytes]:
    try:
        return get_redis_client().get(key)
    except Exception as e:
        logging.error(f"Error getting key {key} from Redis: {str(e)}")
        return None


def set_redis_cache(key: str, value: str, expire: int = None):
    try:
        get_redis_client().set(key, value, ex=expire)
    except Exception as e:
        logging.error(f"Error setting key {key} in Redis: {str(e)}")


def redis_health_check() -> bool:
    try:
        get_redis_client().ping()
        return True
    except Exception as e:
        logging.error(f"Redis health check failed: {str(e)}")
        return False
