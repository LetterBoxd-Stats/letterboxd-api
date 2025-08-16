import logging
from pymongo import MongoClient
import config

logger = logging.getLogger(__name__)

def get_db():
    logger.info("Connecting to MongoDB...")
    client = MongoClient(config.DB_URI)
    db = client[config.DB_NAME]
    logger.info("Connected to MongoDB")
    return db
