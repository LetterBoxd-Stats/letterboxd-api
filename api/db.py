import logging
from pymongo import MongoClient
import api.config

logger = logging.getLogger(__name__)

def get_db():
    logger.info("Connecting to MongoDB...")
    client = MongoClient(api.config.DB_URI)
    db = client[api.config.DB_NAME]
    logger.info("Connected to MongoDB")
    return db
