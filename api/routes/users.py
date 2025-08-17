from flask import Blueprint
from api.db import get_db
import logging

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/')
def get_users():
    db = get_db()
    users = list(db['users'].find({}, {'_id': 0, 'reviews': 0, 'watches': 0}))
    return users

@users_bp.route('/<username>')
def get_user(username):
    db = get_db()
    user = db['users'].find_one({'username': username}, {'_id': 0})
    if user:
        return user
    return {'error': 'User not found'}, 404
