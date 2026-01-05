from flask import Blueprint, request, jsonify
from api.db import get_db
import api.config
import logging
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)
recommendations_bp = Blueprint('recommendations', __name__, url_prefix='/recommendations')

@recommendations_bp.route('/')
def get_recommendations():
    """Return recommendations for a group of users based on predicted ratings."""
    
    # Parse query parameters
    watchers_param = request.args.get('watchers')
    if not watchers_param:
        return jsonify({"error": "watchers parameter is required"}), 400
    
    watchers = [w.strip() for w in watchers_param.split(',')]
    
    logger.info(f"Getting recommendations for watchers: {watchers}")
    
    # Optional parameters with defaults
    try:
        num_recs = int(request.args.get('num_recs', 3))
    except ValueError:
        return jsonify({"error": "num_recs must be an integer"}), 400
    
    try:
        offset = int(request.args.get('offset', 0))
        if offset < 0:
            return jsonify({"error": "offset must be a non-negative integer"}), 400
    except ValueError:
        return jsonify({"error": "offset must be an integer"}), 400
    
    ok_to_have_watched = []
    if request.args.get('ok_to_have_watched'):
        ok_to_have_watched = [w.strip() for w in request.args.get('ok_to_have_watched').split(',')]
    
    try:
        max_ok_to_have_watched = int(request.args.get('max_ok_to_have_watched', 0))
    except ValueError:
        return jsonify({"error": "max_ok_to_have_watched must be an integer"}), 400
    
    # Validate ok_to_have_watched is subset of watchers
    for user in ok_to_have_watched:
        if user not in watchers:
            return jsonify({"error": f"User {user} in ok_to_have_watched must be in watchers"}), 400
    
    # Build MongoDB query
    mongo_query = {}
    
    # Parse numeric filters for MongoDB
    rating_filters = {}
    year_filters = {}
    runtime_filters = {}
    
    # Rating filters
    avg_rating_gte = request.args.get('metadata.avg_rating_gte')
    avg_rating_lte = request.args.get('metadata.avg_rating_lte')
    if avg_rating_gte or avg_rating_lte:
        rating_filters = {}
        if avg_rating_gte:
            try:
                rating_filters['$gte'] = float(avg_rating_gte)
            except ValueError:
                return jsonify({"error": "metadata.avg_rating_gte must be a number"}), 400
        if avg_rating_lte:
            try:
                rating_filters['$lte'] = float(avg_rating_lte)
            except ValueError:
                return jsonify({"error": "metadata.avg_rating_lte must be a number"}), 400
        
        if rating_filters:
            mongo_query['metadata.avg_rating'] = rating_filters
    
    # Year filters
    year_gte = request.args.get('metadata.year_gte')
    year_lte = request.args.get('metadata.year_lte')
    if year_gte or year_lte:
        year_filters = {}
        if year_gte:
            try:
                year_filters['$gte'] = int(year_gte)
            except ValueError:
                return jsonify({"error": "metadata.year_gte must be an integer"}), 400
        if year_lte:
            try:
                year_filters['$lte'] = int(year_lte)
            except ValueError:
                return jsonify({"error": "metadata.year_lte must be an integer"}), 400
        
        if year_filters:
            mongo_query['metadata.year'] = year_filters
    
    # Runtime filters
    runtime_gte = request.args.get('metadata.runtime_gte')
    runtime_lte = request.args.get('metadata.runtime_lte')
    if runtime_gte or runtime_lte:
        runtime_filters = {}
        if runtime_gte:
            try:
                runtime_filters['$gte'] = int(runtime_gte)
            except ValueError:
                return jsonify({"error": "metadata.runtime_gte must be an integer"}), 400
        if runtime_lte:
            try:
                runtime_filters['$lte'] = int(runtime_lte)
            except ValueError:
                return jsonify({"error": "metadata.runtime_lte must be an integer"}), 400
        
        if runtime_filters:
            mongo_query['metadata.runtime'] = runtime_filters
    
    # Parse text field filters for MongoDB
    text_filters = {}
    
    # Text fields to filter
    text_fields = ['directors', 'actors', 'studios', 'themes', 'description', 'crew', 'genres']
    for field in text_fields:
        param_value = request.args.get(field)
        if param_value:
            search_terms = [s.strip() for s in param_value.split(',')]
            text_filters[field] = search_terms
            
            # Build MongoDB query for text filters
            if field == 'description':
                # For description, we need to search within the text
                description_queries = [{"metadata.description": {"$regex": term, "$options": "i"}} 
                                      for term in search_terms]
                if description_queries:
                    if '$and' not in mongo_query:
                        mongo_query['$and'] = []
                    mongo_query['$and'].extend(description_queries)
            elif field == 'crew':
                # For crew, we need to search within crew.name fields
                crew_queries = [{"metadata.crew.name": {"$regex": term, "$options": "i"}} 
                               for term in search_terms]
                if crew_queries:
                    if '$and' not in mongo_query:
                        mongo_query['$and'] = []
                    mongo_query['$and'].extend(crew_queries)
            else:
                # For arrays like directors, actors, studios, themes, genres
                field_queries = []
                for term in search_terms:
                    # Search for substring match in array elements
                    field_queries.append({f"metadata.{field}": {"$regex": term, "$options": "i"}})
                
                if field_queries:
                    if '$and' not in mongo_query:
                        mongo_query['$and'] = []
                    mongo_query['$and'].extend(field_queries)
    
    logger.info(f"MongoDB query: {mongo_query}")
    
    # Get database connection
    db = get_db()
    
    # Get filtered films from the database
    films_collection = db.films
    
    # We need films that have predicted_reviews for all watchers
    # Also need to apply watched filters
    all_films = list(films_collection.find(mongo_query))
    
    logger.info(f"Films after database query: {len(all_films)}")
    
    # Now filter in Python for the remaining criteria that can't be easily done in MongoDB
    filtered_films = []
    skipped_reasons = {
        'no_predicted_reviews': 0,
        'no_prediction_for_all_watchers': 0,
        'failed_watched_filters': 0
    }
    
    for film in all_films:
        # Check if film has predicted_reviews
        if 'predicted_reviews' not in film:
            skipped_reasons['no_predicted_reviews'] += 1
            continue
        
        # Check watched status for watchers
        if not passes_watched_filters(film, watchers, ok_to_have_watched, max_ok_to_have_watched):
            skipped_reasons['failed_watched_filters'] += 1
            continue
        
        # Calculate average predicted rating for this group of watchers
        avg_predicted_rating = calculate_average_predicted_rating(film, watchers)
        if avg_predicted_rating is None:
            skipped_reasons['no_prediction_for_all_watchers'] += 1
            continue
        
        # Add film with its average predicted rating
        filtered_films.append({
            'film': film,
            'avg_predicted_rating': avg_predicted_rating,
            'avg_letterboxd_rating': film.get('metadata', {}).get('avg_rating', 0),
            'title': film.get('film_title', 'Unknown')
        })
    
    logger.info(f"Films after Python filtering: {len(filtered_films)}")
    logger.info(f"Skipped reasons: {skipped_reasons}")
    
    # Sort by average predicted rating (descending)
    filtered_films.sort(key=lambda x: x['avg_predicted_rating'], reverse=True)
    
    # Apply offset and limit to get the requested slice
    start_idx = offset
    end_idx = offset + num_recs
    
    # Ensure we don't go out of bounds
    if start_idx >= len(filtered_films):
        top_films = []
    else:
        top_films = filtered_films[start_idx:end_idx]
    
    logger.info(f"Returning films {start_idx} to {min(end_idx, len(filtered_films))} of {len(filtered_films)}")
    
    # Prepare response
    recommendations = []
    for film_data in top_films:
        film = film_data['film']
        recommendations.append({
            'film_id': film.get('film_id'),
            'film_title': film.get('film_title'),
            'film_link': film.get('film_link'),
            'avg_predicted_rating': round(film_data['avg_predicted_rating'], 2),
            'avg_letterboxd_rating': film_data['avg_letterboxd_rating'],
            'metadata': {
                'directors': film.get('metadata', {}).get('directors', []),
                'year': film.get('metadata', {}).get('year'),
                'runtime': film.get('metadata', {}).get('runtime'),
                'genres': film.get('metadata', {}).get('genres', []),
                'themes': film.get('metadata', {}).get('themes', []),
                'description': film.get('metadata', {}).get('description', '')
            },
            'predicted_ratings': {
                watcher: get_predicted_rating(film, watcher)
                for watcher in watchers
            }
        })
    
    return jsonify({
        'recommendations': recommendations,
        'stats': {
            'total_films_in_db': films_collection.count_documents({}),
            'films_after_filtering': len(filtered_films),
            'recommendations_returned': len(recommendations),
            'has_more': (offset + num_recs) < len(filtered_films),
            'offset': offset,
            'limit': num_recs,
            'total_available': len(filtered_films),
            'skipped_reasons': skipped_reasons
        },
        'parameters': {
            'watchers': watchers,
            'num_recs': num_recs,
            'offset': offset,
            'ok_to_have_watched': ok_to_have_watched,
            'max_ok_to_have_watched': max_ok_to_have_watched,
            'filters_applied': {
                'numeric': {
                    'avg_rating': rating_filters,
                    'year': year_filters,
                    'runtime': runtime_filters
                },
                'text': text_filters
            }
        }
    })

def passes_numeric_filters(film: Dict, filters: Dict) -> bool:
    """Check if film passes all numeric filters."""
    metadata = film.get('metadata', {})
    
    # Check avg_rating filter
    if 'metadata.avg_rating_gte' in filters:
        avg_rating = metadata.get('avg_rating')
        if avg_rating is None or avg_rating < filters['metadata.avg_rating_gte']:
            return False
    
    if 'metadata.avg_rating_lte' in filters:
        avg_rating = metadata.get('avg_rating')
        if avg_rating is None or avg_rating > filters['metadata.avg_rating_lte']:
            return False
    
    # Check year filter
    if 'metadata.year_gte' in filters:
        year = metadata.get('year')
        if year is None or year < filters['metadata.year_gte']:
            return False
    
    if 'metadata.year_lte' in filters:
        year = metadata.get('year')
        if year is None or year > filters['metadata.year_lte']:
            return False
    
    # Check runtime filter
    if 'metadata.runtime_gte' in filters:
        runtime = metadata.get('runtime')
        if runtime is None or runtime < filters['metadata.runtime_gte']:
            return False
    
    if 'metadata.runtime_lte' in filters:
        runtime = metadata.get('runtime')
        if runtime is None or runtime > filters['metadata.runtime_lte']:
            return False
    
    return True

def passes_text_filters(film: Dict, text_filters: Dict) -> bool:
    """Check if film passes all text filters."""
    metadata = film.get('metadata', {})
    
    for field, search_terms in text_filters.items():
        if field == 'directors':
            directors = metadata.get('directors', [])
            if not any_contains_all_terms(directors, search_terms):
                return False
        
        elif field == 'actors':
            actors = metadata.get('actors', [])
            if not any_contains_all_terms(actors, search_terms):
                return False
        
        elif field == 'studios':
            studios = metadata.get('studios', [])
            if not any_contains_all_terms(studios, search_terms):
                return False
        
        elif field == 'themes':
            themes = metadata.get('themes', [])
            if not any_contains_all_terms(themes, search_terms):
                return False
        
        elif field == 'description':
            description = metadata.get('description', '').lower()
            if not all(term in description for term in search_terms):
                return False
        
        elif field == 'crew':
            crew = metadata.get('crew', [])
            crew_names = [member.get('name', '').lower() for member in crew]
            if not any_contains_all_terms(crew_names, search_terms):
                return False
        
        elif field == 'genres':
            genres = metadata.get('genres', [])
            if not all(term in [g.lower() for g in genres] for term in search_terms):
                return False
    
    return True

def any_contains_all_terms(items: List[str], terms: List[str]) -> bool:
    """Check if any item contains all search terms."""
    for item in items:
        item_lower = str(item).lower()
        if all(term in item_lower for term in terms):
            return True
    return False

def passes_watched_filters(film: Dict, watchers: List[str], 
                          ok_to_have_watched: List[str], max_ok_to_have_watched: int) -> bool:
    """Check if film passes watched status filters."""
    # Get users who have watched this film
    watched_users = set()
    
    # Check watches list
    for watch in film.get('watches', []):
        if 'user' in watch:
            watched_users.add(watch['user'])
    
    # Check reviews list (if someone rated it, they've watched it)
    for review in film.get('reviews', []):
        if 'user' in review:
            watched_users.add(review['user'])
    
    # Check which watchers have watched this film
    watchers_who_have_watched = [w for w in watchers if w in watched_users]
    
    # Apply ok_to_have_watched filter
    watchers_not_allowed_to_have_watched = [w for w in watchers_who_have_watched 
                                           if w not in ok_to_have_watched]
    
    # Check if too many people have watched it
    if len(watchers_who_have_watched) > max_ok_to_have_watched:
        return False
    
    # Check if non-allowed users have watched it
    if len(watchers_not_allowed_to_have_watched) > 0:
        return False
    
    return True

def calculate_average_predicted_rating(film: Dict, watchers: List[str]) -> Optional[float]:
    """Calculate average predicted rating for a group of watchers."""
    total_rating = 0
    count = 0
    
    for watcher in watchers:
        predicted_rating = get_predicted_rating(film, watcher)
        if predicted_rating is None:
            return None  # Return None if any watcher doesn't have a prediction
        total_rating += predicted_rating
        count += 1
    
    if count == 0:
        return None
    
    return total_rating / count

def get_predicted_rating(film: Dict, username: str) -> Optional[float]:
    """Get predicted rating for a specific user from predicted_reviews."""
    for pred_review in film.get('predicted_reviews', []):
        if pred_review.get('user') == username:
            rating = pred_review.get('predicted_rating')
            # Ensure rating is a valid number
            if rating is not None:
                try:
                    return float(rating)
                except (ValueError, TypeError):
                    return None
    return None