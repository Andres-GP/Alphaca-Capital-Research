import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_mongo_client():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI missing in .env")

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=3000,
        socketTimeoutMS=30000,
        maxPoolSize=50,
        minPoolSize=5,
        retryWrites=True,
        w="majority"
    )

    try:
        client.admin.command("ping")
        logger.info("MongoDB connection established.")
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise ConnectionError(f"Cannot connect to MongoDB: {e}")

    return client


def get_mongo_db(db_name=None):
    client = get_mongo_client()
    if db_name is None:
        db_name = os.getenv("MONGODB_DB_NAME", "trading_data")
    return client[db_name]


def get_mongo_collection(collection_name, db_name=None):
    db = get_mongo_db(db_name)
    return db[collection_name]


class MongoConnection:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            cls._client = get_mongo_client()
        return cls._client

    @classmethod
    def get_db(cls, db_name=None):
        client = cls.get_client()
        if db_name is None:
            db_name = os.getenv("MONGODB_DB_NAME", "trading_data")
        return client[db_name]

    @classmethod
    def close(cls):
        if cls._client:
            cls._client.close()
            cls._client = None
            logger.info("MongoDB connection closed.")