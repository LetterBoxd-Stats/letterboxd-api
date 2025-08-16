from flask import Flask
from flask_cors import CORS
import logging
import config
from routes.films import films_bp
from routes.users import users_bp

config.configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

allowed_origins = "*" if config.ENV == 'dev' else [config.FRONTEND_URL]
CORS(app, resources={r"/*": {"origins": allowed_origins}})

# Register Blueprints
app.register_blueprint(films_bp)
app.register_blueprint(users_bp)

@app.route('/')
def home():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=(config.ENV == 'dev'))
