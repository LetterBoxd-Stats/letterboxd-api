from flask import Flask
from flask_cors import CORS
import logging
import api.config
from api.routes.films import films_bp
from api.routes.users import users_bp
from api.routes.superlatives import superlatives_bp

api.config.configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

allowed_origins = "*" if api.config.ENV == 'dev' else [api.config.FRONTEND_URL]
CORS(app, resources={r"/*": {"origins": allowed_origins}})

# Register Blueprints
app.register_blueprint(films_bp)
app.register_blueprint(users_bp)
app.register_blueprint(superlatives_bp)

@app.route('/')
def home():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=(api.config.ENV == 'dev'), port=api.config.PORT)
