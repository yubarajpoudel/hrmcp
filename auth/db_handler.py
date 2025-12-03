from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict
from core.env.env_utils import get_settings

settings = get_settings()

# MongoDB connection string
MONGODB_URL = settings.MONGODB_URL
DATABASE_NAME = settings.DATABASE_NAME
USERS_COLLECTION = settings.USER

class DatabaseHandler:
    client: Optional[AsyncIOMotorClient] = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        if cls.client is None:
            cls.client = AsyncIOMotorClient(MONGODB_URL)
            print(f"Connected to MongoDB at {DATABASE_NAME}")
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            print("Closed MongoDB connection")
    
    @classmethod
    def get_database(cls):
        """Get database instance"""
        if cls.client is None:
            raise Exception("Database not connected. Call connect_db() first.")
        return cls.client[DATABASE_NAME]
    
    @classmethod
    async def create_user(cls, user_data: Dict) -> Dict:
        """
        Create a new user in the database
        
        Args:
            user_data: Dictionary containing user information
                - username (required)
                - hashed_password (required)
                - email (optional)
                - full_name (optional)
                - role (optional)
                - disabled (optional, default: False)
        
        Returns:
            Created user document
        """
        db = cls.get_database()
        users_collection = db[USERS_COLLECTION]
        
        # Check if user already exists
        existing_user = await users_collection.find_one({"username": user_data["username"]})
        if existing_user:
            raise ValueError(f"User with username '{user_data['username']}' already exists")
        
        # Set defaults
        user_data.setdefault("disabled", False)
        
        # Insert user
        result = await users_collection.insert_one(user_data)
        user_data["_id"] = str(result.inserted_id)
        
        return user_data
    
    @classmethod
    async def get_user(cls, username: str) -> Optional[Dict]:
        """
        Get user by username
        
        Args:
            username: Username to search for
        
        Returns:
            User document if found, None otherwise
        """
        db = cls.get_database()
        users_collection = db[USERS_COLLECTION]
        
        user = await users_collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])
        return user
    
    @classmethod
    async def update_user(cls, username: str, update_data: Dict) -> bool:
        """
        Update user information
        
        Args:
            username: Username to update
            update_data: Dictionary of fields to update
        
        Returns:
            True if updated, False if user not found
        """
        db = cls.get_database()
        users_collection = db[USERS_COLLECTION]
        
        result = await users_collection.update_one(
            {"username": username},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @classmethod
    async def delete_user(cls, username: str) -> bool:
        """
        Delete user by username
        
        Args:
            username: Username to delete
        
        Returns:
            True if deleted, False if user not found
        """
        db = cls.get_database()
        users_collection = db[USERS_COLLECTION]
        
        result = await users_collection.delete_one({"username": username})
        return result.deleted_count > 0
