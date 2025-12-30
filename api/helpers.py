import re

def get_film_fields():
    return [
        'film_id', 'film_title', 'film_link', 'avg_rating',
        'like_ratio', 'num_likes', 'num_ratings', 'num_watches',
        # Metadata fields from film page scraping
        'metadata.avg_rating', 'metadata.year', 'metadata.runtime',
        'metadata.genres', 'metadata.directors', 'metadata.actors',
        'metadata.studios', 'metadata.themes', 'metadata.description',
        'metadata.crew', 'metadata.backdrop_url'
    ]

def get_film_sort_fields():
    return [
        'film_id', 'film_title', 'film_link', 'avg_rating',
        'like_ratio', 'num_likes', 'num_ratings', 'num_watches',
        'metadata.avg_rating', 'metadata.year', 'metadata.runtime'
    ]

def get_film_filter_query(args):
    filter_query = {}
    
    # Start with simple field filters
    fields = {
        'avg_rating': float,
        'like_ratio': float,
        'num_likes': int,
        'num_ratings': int,
        'num_watches': int,
        'metadata.avg_rating': float,
        'metadata.year': int,
        'metadata.runtime': int
    }

    for field, cast in fields.items():
        gte_key = f"{field}_gte"
        lte_key = f"{field}_lte"
        range_filter = {}
        if gte_key in args:
            try: range_filter['$gte'] = cast(args[gte_key])
            except ValueError: return {'error': f'Invalid value for {gte_key}'}
        if lte_key in args:
            try: range_filter['$lte'] = cast(args[lte_key])
            except ValueError: return {'error': f'Invalid value for {lte_key}'}
        if range_filter: 
            filter_query[field] = range_filter

    # Handle genres separately first (array field)
    if 'genres' in args:
        values = [v.strip() for v in args['genres'].split(',') if v.strip()]
        if values:
            filter_query['metadata.genres'] = {'$all': values}

    # Text field filters
    text_fields = [
        'metadata.directors',
        'metadata.actors',
        'metadata.studios', 
        'metadata.themes',
        'metadata.description',
        'film_title'
    ]
    
    for field in text_fields:
        param_name = field.replace('metadata.', '')
        if param_name in args:
            values = [v.strip() for v in args[param_name].split(',') if v.strip()]
            if values:
                # Use $and if we already have other conditions
                if len(filter_query) > 0 or '$and' in filter_query:
                    if '$and' not in filter_query:
                        # Convert existing query to $and format
                        existing_conditions = [{k: v} for k, v in filter_query.items()]
                        filter_query = {'$and': existing_conditions}
                    
                    # Add text conditions to $and
                    for value in values:
                        regex_pattern = f'.*{re.escape(value)}.*'
                        filter_query['$and'].append({field: {'$regex': regex_pattern, '$options': 'i'}})
                else:
                    # Simple case: just add the regex directly
                    if len(values) == 1:
                        regex_pattern = f'.*{re.escape(values[0])}.*'
                        filter_query[field] = {'$regex': regex_pattern, '$options': 'i'}
                    else:
                        # Multiple values need $and
                        and_conditions = []
                        for value in values:
                            regex_pattern = f'.*{re.escape(value)}.*'
                            and_conditions.append({field: {'$regex': regex_pattern, '$options': 'i'}})
                        filter_query['$and'] = and_conditions

    # Crew field
    if 'crew' in args:
        values = [v.strip() for v in args['crew'].split(',') if v.strip()]
        if values:
            if len(filter_query) > 0 or '$and' in filter_query:
                if '$and' not in filter_query:
                    existing_conditions = [{k: v} for k, v in filter_query.items()]
                    filter_query = {'$and': existing_conditions}
                
                for value in values:
                    regex_pattern = f'.*{re.escape(value)}.*'
                    filter_query['$and'].append({'metadata.crew.name': {'$regex': regex_pattern, '$options': 'i'}})
            else:
                if len(values) == 1:
                    regex_pattern = f'.*{re.escape(values[0])}.*'
                    filter_query['metadata.crew.name'] = {'$regex': regex_pattern, '$options': 'i'}
                else:
                    and_conditions = []
                    for value in values:
                        regex_pattern = f'.*{re.escape(value)}.*'
                        and_conditions.append({'metadata.crew.name': {'$regex': regex_pattern, '$options': 'i'}})
                    filter_query['$and'] = and_conditions

    # User-based filters - handle these last as they're complex
    user_filters = ['watched_by', 'not_watched_by', 'rated_by', 'not_rated_by']
    user_conditions = []
    
    for user_filter in user_filters:
        if user_filter in args:
            users = [u.strip() for u in args[user_filter].split(',') if u.strip()]
            if users:
                if user_filter == 'watched_by':
                    for user in users:
                        user_conditions.append({
                            '$or': [
                                {'watches': {'$elemMatch': {'user': user}}},
                                {'reviews': {'$elemMatch': {'user': user}}}
                            ]
                        })
                elif user_filter == 'not_watched_by':
                    for user in users:
                        user_conditions.append({
                            '$nor': [
                                {
                                    '$or': [
                                        {'watches': {'$elemMatch': {'user': user}}},
                                        {'reviews': {'$elemMatch': {'user': user}}}
                                    ]
                                }
                            ]
                        })
                elif user_filter == 'rated_by':
                    for user in users:
                        user_conditions.append({
                            'reviews': {'$elemMatch': {'user': user}}
                        })
                elif user_filter == 'not_rated_by':
                    for user in users:
                        user_conditions.append({
                            '$nor': [
                                {'reviews': {'$elemMatch': {'user': user}}}
                            ]
                        })
    
    # Combine user conditions with existing query
    if user_conditions:
        if len(filter_query) > 0 or '$and' in filter_query:
            if '$and' not in filter_query:
                existing_conditions = [{k: v} for k, v in filter_query.items()]
                filter_query = {'$and': existing_conditions}
            filter_query['$and'].extend(user_conditions)
        else:
            if len(user_conditions) == 1:
                filter_query = user_conditions[0]
            else:
                filter_query['$and'] = user_conditions
    
    return filter_query