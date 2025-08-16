def get_film_fields():
    return [
        'film_id', 'film_title', 'film_link', 'avg_rating',
        'like_ratio', 'num_likes', 'num_ratings', 'num_watches'
    ]

def get_film_filter_query(args):
    filter_query = {}
    fields = {
        'avg_rating': float,
        'like_ratio': float,
        'num_likes': int,
        'num_ratings': int,
        'num_watches': int
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
        if range_filter: filter_query[field] = range_filter

    # Require all listed users to be/not be in watches/reviews
    if 'watched_by' in args:
        users = [u.strip() for u in args['watched_by'].split(',') if u.strip()]
        if users:
            and_conditions = []
            for user in users:
                and_conditions.append({
                    '$or': [
                        {'watches': {'$elemMatch': {'user': user}}},
                        {'reviews': {'$elemMatch': {'user': user}}}
                    ]
                })
            filter_query['$and'] = and_conditions
    if 'not_watched_by' in args:
        users = [u.strip() for u in args['not_watched_by'].split(',') if u.strip()]
        if users:
            filter_query['$nor'] = [{
                '$or': [
                    {'watches': {'$elemMatch': {'user': user}}},
                    {'reviews': {'$elemMatch': {'user': user}}}
                ]
            } for user in users]
    if 'rated_by' in args:
        users = [u.strip() for u in args['rated_by'].split(',') if u.strip()]
        if users:
            and_conditions = []
            for user in users:
                and_conditions.append({
                    'reviews': {'$elemMatch': {'user': user}}
                })
            filter_query['$and'] = and_conditions
    if 'not_rated_by' in args:
        users = [u.strip() for u in args['not_rated_by'].split(',') if u.strip()]
        if users:
            filter_query['$nor'] = [{
                'reviews': {'$elemMatch': {'user': user}}
            } for user in users]
    
    return filter_query
