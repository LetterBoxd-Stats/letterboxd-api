from flask import Blueprint, request
from api.db import get_db
import api.config
import logging

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/')
def get_users():
    db = get_db()
    users = list(db[api.config.DB_USERS_COLLECTION].find({}, {'_id': 0, 'reviews': 0, 'watches': 0}))
    return users

@users_bp.route('/<username>')
def get_user(username):
    include_films = request.args.get('include_films', 'false').lower() == 'true'

    db = get_db()
    if include_films:
        user = db[api.config.DB_USERS_COLLECTION].find_one({'username': username}, {'_id': 0})
    else:
        user = db[api.config.DB_USERS_COLLECTION].find_one({'username': username}, {'_id': 0, 'reviews': 0, 'watches': 0})
    if user:
        return user
    return {'error': 'User not found'}, 404
