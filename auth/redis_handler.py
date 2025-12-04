# connect with redis
# handle the failover mechanism of redis connection
# handle the connection pool of redis
# handle the connection timeout of redis
# add the getter and setter functions
# implement the connection pool cleanup function
# get the data from mongodb and store it in redis if the key is not present
import redis
from core.env.env_utils import get_settings
from auth.queue_manager import QueueManager
from auth.db_handler import DatabaseHandler

class RedisHandler:
    def __init__(self):
        settings = get_settings()
        self.redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, username=settings.REDIS_USER, password=settings.REDIS_PASSWORD, decode_responses=True) 
        print("Redis connected")
    
    def set_key(self, key, value):
        # update the value in redis
        self.redis_client.set(key, str(value))
        # send the value to update in mongo in the queue (async operation)
        try:
            queue_update_mongo(key, value)
        except Exception as e:
            print(f"Error queuing mongo update: {e}")
    
    async def get_key(self, key):
        return await self.load_data_from_db_ifnotexists(key)
    
    def delete_key(self, key):
        self.redis_client.delete(key)
    
    def close(self):
        self.redis_client.close()
    
    def test_redis_connected(self):
        """Test if Redis connection is alive"""
        try:
            self.redis_client.ping()
            return True
        except redis.ConnectionError:
            return False 

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def close_instance(cls):
        if hasattr(cls, "_instance"):
            cls._instance.close()
            del cls._instance
    
    async def load_data_from_db_ifnotexists(self, key):
        # Check if key exists in Redis
        value = self.redis_client.get(key)
        if not value:
            # retrieve the value from mongodb
            # store the value in redis
            # return the value
            tokenDocument = await DatabaseHandler.get_database().get_collection("token").find_one({"_id": key})
            if tokenDocument:
                self.redis_client.set(key, tokenDocument["usage"])
                return tokenDocument["usage"]
            return None
        return value


def update_mongo_sync(key, value):
    try:
        # Use synchronous pymongo client for RQ worker
        db = DatabaseHandler.get_database()
        result = db.get_collection("token").update_one(
            {"_id": key}, 
            {"$inc": {"usage": value}},
            upsert=True
        )
        print(f"MongoDB updated: {key} incremented by {value}, matched: {result.matched_count}, modified: {result.modified_count}")
        return True
    except Exception as e:
        print(f"Error updating MongoDB: {e}")
        return False

def queue_update_mongo(key, value):
    """Push the MongoDB update task to the queue"""
    redis_client = RedisHandler.get_instance().redis_client
    queue_manager = QueueManager(redis_client).enqueue(update_mongo_sync, key, value)
    queue_manager.start_worker()