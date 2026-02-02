from flask import Flask, send_from_directory
from flask_cors import CORS
import logging
import api.config
from api.routes.films import films_bp
from api.routes.users import users_bp
from api.routes.superlatives import superlatives_bp
from api.routes.recommendations import recommendations_bp

api.config.configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

allowed_origins = "*" if api.config.ENV == 'dev' else [api.config.FRONTEND_URL]
CORS(app, resources={r"/*": {"origins": allowed_origins}})

# Register Blueprints
app.register_blueprint(films_bp)
app.register_blueprint(users_bp)
app.register_blueprint(superlatives_bp)
app.register_blueprint(recommendations_bp)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/openapi.json')
def openapi():
    return send_from_directory(app.root_path, 'openapi.json')

@app.route('/docs')
def api_docs():
    return '''
    <!doctype html>
    <html>
      <head>
        <title>Letterboxd API Reference</title>
        <meta charset="utf-8" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1" />
        <style>
          body { margin: 0; }
        </style>
      </head>
      <body>
        <script
          id="api-reference"
          data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    '''


if __name__ == '__main__':
    app.run(debug=(api.config.ENV == 'dev'), port=api.config.PORT)
