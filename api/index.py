from flask import Flask

app = Flask(__name__)

def get_db_config():
    import os
    from dotenv import load_dotenv

    load_dotenv()  # Load environment variables from .env file

    db_uri = os.getenv('DB_URI')
    db_name = os.getenv('DB_NAME')
    users_collection_name = os.getenv('DB_USERS_COLLECTION')
    films_collection_name = os.getenv('DB_FILMS_COLLECTION')

    if not all([db_uri, db_name, users_collection_name, films_collection_name]):
        raise ValueError("Missing one or more database configuration variables")

    return db_uri, db_name, users_collection_name, films_collection_name

def connect_to_db():
    from pymongo import MongoClient
    db_uri, db_name, users_collection_name, films_collection_name = get_db_config()
    
    client = MongoClient(db_uri)
    db = client[db_name]
    
    return db, users_collection_name, films_collection_name

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/about')
def about():
    return 'About'

@app.route('/films')
def films():
    # Connect to MongoDB
    try:
        db, _users_collection_name, films_collection_name = connect_to_db()
        films_collection = db[films_collection_name]
        # Fetch all films
        films = list(films_collection.find({}, {'_id': 0}))  # Exclude MongoDB's default _id field
        return {'films': films}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/users')
def users():
    # Connect to MongoDB
    try:
        db, users_collection_name, _films_collection_name = connect_to_db()
        users_collection = db[users_collection_name]
        # Fetch all users
        users = list(users_collection.find({}, {'_id': 0}))  # Exclude MongoDB's default _id field
        return {'users': users}
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
    is_debug = os.getenv('ENV') == 'dev'
    app.run(debug=is_debug)