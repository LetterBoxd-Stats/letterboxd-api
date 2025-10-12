from flask import Blueprint, request
from api.db import get_db
import logging
import api.config

logger = logging.getLogger(__name__)
superlatives_bp = Blueprint('superlatives', __name__, url_prefix='/superlatives')

@superlatives_bp.route('/')
def get_superlatives():
    db = get_db()
    superlatives = list(db[api.config.DB_SUPERLATIVES_COLLECTION].find({}, {'_id': 0}))
    return superlatives