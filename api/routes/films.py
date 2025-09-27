from flask import Blueprint, request, jsonify
from api.db import get_db
from api.helpers import get_film_sort_fields, get_film_filter_query
import logging
import re

logger = logging.getLogger(__name__)
films_bp = Blueprint('films', __name__, url_prefix='/films')

@films_bp.route('/')
def get_films():
    db = get_db()
    films_collection = db['films']

    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    sort_field = request.args.get('sort_by', 'film_title')
    sort_order = request.args.get('sort_order', 'asc')

    if sort_field not in get_film_sort_fields():
        return jsonify({'error': f'Invalid sort field: {sort_field}'}), 400
    sort_direction = 1 if sort_order == 'asc' else -1

    filter_query = get_film_filter_query(request.args)
    if 'error' in filter_query:
        return jsonify(filter_query), 400

    # Case-insensitive collation for all queries
    collation = {'locale': 'en', 'strength': 2}

    skip = (page - 1) * limit

    try:
        total_films = films_collection.count_documents(filter_query, collation=collation)
        logger.info(f"Filter query: {filter_query}")
        logger.info(f"Total films count: {total_films}")
    except Exception as e:
        logger.error(f"Error counting documents: {e}")
        return jsonify({'error': 'Database error when counting films'}), 500

    films_cursor = films_collection.find(filter_query, {"_id": 0}) \
        .sort(sort_field, sort_direction) \
        .collation(collation) \
        .skip(skip).limit(limit)

    films_list = list(films_cursor)
    logger.info(f"Actual films returned: {len(films_list)}")

    total_pages = (total_films + limit - 1) // limit
    if page > total_pages and total_films > 0:
        return jsonify({'error': 'Page number out of range'}), 400

    return jsonify({
        'films': films_list,
        'page': page,
        'per_page': limit,
        'total_pages': total_pages,
        'total_films': total_films
    })


@films_bp.route('/<film_id>')
def get_film(film_id):
    db = get_db()
    film = db['films'].find_one({'film_id': film_id}, {'_id': 0})
    if film:
        return film
    return {'error': 'Film not found'}, 404