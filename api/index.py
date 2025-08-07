from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from pymongo import MongoClient
import sys

sys.path.append(os.path.dirname(__file__))  # Add /api to sys.path
import config

config.configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure allowed origins
if config.ENV == 'dev':
    allowed_origins = "*"  # Allow all in development
else:
    allowed_origins = [config.FRONTEND_URL]

CORS(app, resources={r"/*": {"origins": allowed_origins}})

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
        # Connect to DB
        db, _, films_collection_name = connect_to_db()
        logger.info("Fetching films from database...")
        films_collection = db[films_collection_name]

        # Get query params for pagination
        page = int(request.args.get('page', 1))  # default page = 1
        limit = int(request.args.get('limit', 20))  # default limit = 20

        # Calculate skip for MongoDB
        skip = (page - 1) * limit

        # Get total count
        total_films = films_collection.count_documents({})

        # Fetch paginated data
        films_cursor = films_collection.find({}, {'_id': 0}).skip(skip).limit(limit)
        films = list(films_cursor)

        # Calculate total pages
        total_pages = (total_films + limit - 1) // limit  # ceiling division
        if page > total_pages and total_films > 0:
            return jsonify({'error': 'Page number out of range'}), 400
        logger.info(f"Fetched {len(films)} films from database.")

        # Return paginated response
        return jsonify({
            "films": films,
            "page": page,
            "per_page": limit,
            "total_pages": total_pages,
            "total_films": total_films
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/films/<film_id>')
def film(film_id):
    try:
        db, _, films_collection_name = connect_to_db()
        logger.info(f"Fetching film with ID '{film_id}' from database...")
        films_collection = db[films_collection_name]
        film = films_collection.find_one({'film_id': film_id}, {'_id': 0})
        if film:
            logger.info(f"Fetched film with ID '{film_id}' from database.")
            return film
        else:
            logger.warning(f"Film with ID '{film_id}' not found.")
            return {'error': 'Film not found'}, 404
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
        return users
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
            return user
        else:
            logger.warning(f"User '{username}' not found.")
            return {'error': 'User not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    app.run(debug=(config.ENV == 'dev'))
