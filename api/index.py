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

def get_film_fields():
    return [
        'film_id', 'film_title', 'film_link', 'avg_rating', 'like_ratio', 'num_likes', 'num_ratings', 'num_watches'
    ]

def get_film_filter_query(args):
    filter_query = {}
    # Define which fields are expected and their cast types
    fields = {
        'avg_rating': float,
        'like_ratio': float,
        'num_likes': int,
        'num_ratings': int,
        'num_watches': int
    }

    for field, cast in fields.items():
        gte_key = f"{field}_gte"
        lte_key = f"{field}_lte"
        range_filter = {}

        if gte_key in args:
            try:
                range_filter['$gte'] = cast(args[gte_key])
            except ValueError:
                return {'error': f'Invalid value for {gte_key}'}

        if lte_key in args:
            try:
                range_filter['$lte'] = cast(args[lte_key])
            except ValueError:
                return {'error': f'Invalid value for {lte_key}'}

        if range_filter:
            filter_query[field] = range_filter

    return filter_query

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

        # Get query params for sorting
        sort_field = request.args.get('sort_by', 'film_title')

        allowed_fields = get_film_fields()
        if sort_field not in allowed_fields:
            return jsonify({'error': f'Invalid sort field: {sort_field}'}), 400
        
        if sort_field in ['film_title', 'film_id', 'film_link']:
            sort_order = request.args.get('sort_order', 'asc')
        else:
            sort_order = request.args.get('sort_order', 'desc')
        
        if sort_order not in ['asc', 'desc']:
            return jsonify({'error': f'Invalid sort order: {sort_order}. Must be "asc" or "desc".'}), 400
        sort_direction = 1 if sort_order == 'asc' else -1

        # Filter films based on query parameters
        filter_query = get_film_filter_query(request.args)
        if 'error' in filter_query:
            return jsonify(filter_query), 400

        # Calculate skip for MongoDB
        skip = (page - 1) * limit

        # Get total count
        total_films = films_collection.count_documents(filter_query)

        # Fetch paginated data
        films_cursor = films_collection.find(filter_query, {'_id': 0}) \
            .sort(sort_field, sort_direction)

        if sort_field == 'film_title':
            films_cursor = films_cursor.collation({'locale': 'en', 'strength': 1})

        films_cursor = films_cursor.skip(skip).limit(limit)

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
