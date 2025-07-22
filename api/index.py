import config
from flask import Flask
import logging
from pymongo import MongoClient
from scraper import scrape_letterboxd_users_data

config.configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================
# Helper Functions
# ============================

def connect_to_db():
    logger.info("Connecting to MongoDB...")
    client = MongoClient(config.DB_URI)
    db = client[config.DB_NAME]
    logger.info("Connected to MongoDB")
    return db, config.DB_USERS_COLLECTION, config.DB_FILMS_COLLECTION


# ============================
# Routes
# ============================

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/films')
def films():
    try:
        db, _, films_collection_name = connect_to_db()
        logger.info("Fetching films from database...")
        films_collection = db[films_collection_name]
        films = list(films_collection.find({}, {'_id': 0}))
        logger.info(f"Fetched {len(films)} films from database.")
        return {'films': films}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/films/<film_id>')
def film(film_id):
    try:
        db, _, films_collection_name = connect_to_db()
        logger.info(f"Fetching film with ID '{film_id}' from database...")
        films_collection = db[films_collection_name]
        film = films_collection.find_one({'film_id': film_id}, {'_id': 0})
        if film:
            logger.info(f"Fetched film with ID '{film_id}' from database.")
            return {'film': film}
        else:
            logger.warning(f"Film with ID '{film_id}' not found.")
            return {'error': 'Film not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        db, users_collection_name, films_collection_name = connect_to_db()
        usernames = config.LETTERBOXD_USERNAMES
        scrape_letterboxd_users_data(db, users_collection_name, films_collection_name, usernames)
        return {'message': 'Scraping completed successfully'}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/users')
def users():
    try:
        db, users_collection_name, _ = connect_to_db()
        logger.info("Fetching users from database...")
        users_collection = db[users_collection_name]
        users = list(users_collection.find({}, {'_id': 0}))
        logger.info(f"Fetched {len(users)} users from database.")
        return {'users': users}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/users/<username>')
def user(username):
    try:
        db, users_collection_name, _ = connect_to_db()
        logger.info(f"Fetching user '{username}' from database...")
        users_collection = db[users_collection_name]
        user = users_collection.find_one({'username': username}, {'_id': 0})
        if user:
            logger.info(f"Fetched user '{username}' from database.")
            return {'user': user}
        else:
            logger.warning(f"User '{username}' not found.")
            return {'error': 'User not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    app.run(debug=(config.ENV == 'dev'))
