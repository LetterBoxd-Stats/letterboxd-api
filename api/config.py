from dotenv import load_dotenv
import logging
import os

# Load environment variables once (for dev + prod)
load_dotenv()

ENV = os.getenv('ENV')
LETTERBOXD_USERNAMES = os.getenv('LETTERBOXD_USERNAMES', '').split(',')
DB_URI = os.getenv('DB_URI')
DB_NAME = os.getenv('DB_NAME')
DB_USERS_COLLECTION = os.getenv('DB_USERS_COLLECTION')
DB_FILMS_COLLECTION = os.getenv('DB_FILMS_COLLECTION')
FRONTEND_URL = os.getenv('FRONTEND_URL')  # Default to localhost for dev

def configure_logging():
    logging.basicConfig(
        level=logging.DEBUG if ENV == 'dev' else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(),  # Console logs
            # Uncomment to log to file:
            # logging.FileHandler("app.log"),
        ]
    )
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Silence Flask request logs if needed
