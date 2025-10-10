from collections import defaultdict
from dotenv import load_dotenv
import logging
import os
from pymongo import MongoClient
import statistics

def compute_film_stats(db, films_collection_name):
    films_collection = db[films_collection_name]
    films = list(films_collection.find({}))

    logging.info("Computing film statistics...")

    for film in films:
        reviews = film.get('reviews', [])
        watches = film.get('watches', [])

        num_ratings = len(reviews)
        num_watches = len(watches) + num_ratings

        # Sum ratings values
        ratings = [r['rating'] for r in reviews if 'rating' in r]
        total_rating = sum(ratings)

        # Count likes
        num_likes = sum(1 for r in reviews if r.get('is_liked'))
        num_likes += sum(1 for w in watches if w.get('is_liked'))

        # Calculate averages and ratios
        avg_rating = (total_rating / num_ratings) if num_ratings > 0 else None
        like_ratio = (num_likes / num_watches) if num_watches > 0 else None
        
        # Calculate standard deviation
        stdev_rating = statistics.stdev(ratings) if len(ratings) > 1 else None

        # Update the film in the DB
        films_collection.update_one(
            {'film_id': film['film_id']},
            {'$set': {
                'num_ratings': num_ratings,
                'avg_rating': avg_rating,
                'stdev_rating': stdev_rating,
                'num_likes': num_likes,
                'num_watches': num_watches,
                'like_ratio': like_ratio
            }}
        )

    logging.info("Film statistics updated successfully.")

def compute_user_stats(db, users_collection_name, films_collection_name):
    films_collection = db[films_collection_name]
    users_collection = db[users_collection_name]
    users = list(users_collection.find({}))

    logging.info("Preloading films from DB...")
    films = {film['film_id']: film for film in films_collection.find({})}
    logging.info(f"Loaded {len(films)} films into memory.")

    logging.info("Computing user statistics...")

    # Define all genres
    all_genres = [
        "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
        "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery",
        "Romance", "Science Fiction", "Thriller", "War", "Western", "TV Movie"
    ]

    for user in users:
        reviews = user.get('reviews', [])
        watches = user.get('watches', [])
        
        # Combine reviews and watches for film interactions
        all_interactions = reviews + watches

        # Counts
        num_ratings = len(reviews)
        num_watches = num_ratings + len(watches)

        # Extract ratings (only from reviews)
        ratings = [r['rating'] for r in reviews if 'rating' in r]

        # Likes (from both reviews and watches)
        num_likes = sum(1 for r in reviews if r.get('is_liked'))
        num_likes += sum(1 for w in watches if w.get('is_liked'))

        # Averages (only from reviews with ratings)
        avg_rating = (sum(ratings) / num_ratings) if num_ratings > 0 else None
        like_ratio = (num_likes / num_watches) if num_watches > 0 else None

        # Rating distribution (0.5 → 5.0 in 0.5 steps) - only from reviews
        rating_distr = {str(i): ratings.count(i) for i in [x * 0.5 for x in range(1, 11)]}

        # Median, Mode, Stdev - only from reviews with ratings
        median_rating = statistics.median(ratings) if ratings else None
        try:
            mode_rating = statistics.mode(ratings) if ratings else None
        except statistics.StatisticsError:
            mode_rating = None
        stdev_rating = statistics.stdev(ratings) if len(ratings) > 1 else None

        # Pairwise diffs vs. group - only from reviews with ratings
        diffs = []
        abs_diffs = []

        # Pairwise agreement dict: {other_username: [diffs]}
        pairwise_diffs = defaultdict(list)
        pairwise_abs_diffs = defaultdict(list)

        # Genre statistics - from ALL interactions (reviews + watches)
        genre_counts = {genre: 0 for genre in all_genres}
        genre_ratings = {genre: [] for genre in all_genres}  # Only from reviews with ratings
        total_runtime = 0
        total_years = 0
        count_with_runtime = 0
        count_with_year = 0

        # Process ALL interactions for genre, runtime, and year stats
        for interaction in all_interactions:
            film = films.get(interaction['film_id'])
            if not film:
                continue

            # Genre statistics - count for all interactions
            if 'metadata' in film:
                for genre in film['metadata'].get('genres', []):
                    if genre in genre_counts:
                        genre_counts[genre] += 1
                        # Only add rating if this is a review with a rating
                        if 'rating' in interaction:
                            genre_ratings[genre].append(interaction['rating'])
                
                # Runtime and year - for all interactions
                year = film['metadata'].get('year')
                if year:
                    total_years += year
                    count_with_year += 1
                runtime = film['metadata'].get('runtime')
                if runtime:
                    total_runtime += runtime
                    count_with_runtime += 1

        # Only process pairwise differences for reviews with ratings
        for r in reviews:
            if 'rating' not in r:
                continue
            film = films.get(r['film_id'])
            if not film:
                continue

            # Get all other reviewers for this film
            other_reviews = [
                rev for rev in film.get('reviews', [])
                if rev.get('rating') is not None and rev.get('user') != user['username']
            ]

            if not other_reviews:
                continue

            for o in other_reviews:
                diff = r['rating'] - o['rating']
                diffs.append(diff)
                abs_diffs.append(abs(diff))

                pairwise_diffs[o['user']].append(diff)
                pairwise_abs_diffs[o['user']].append(abs(diff))

        # Calculate genre percentages and average ratings
        genre_stats = {}
        for genre in all_genres:
            count = genre_counts[genre]
            percentage = (count / num_watches * 100) if num_watches > 0 else 0
            avg_genre_rating = statistics.mean(genre_ratings[genre]) if genre_ratings[genre] else None
            genre_stddev = statistics.stdev(genre_ratings[genre]) if len(genre_ratings[genre]) > 1 else None
            genre_stats[genre] = {
                'count': count,
                'percentage': percentage,
                'avg_rating': avg_genre_rating,
                'stddev': genre_stddev
            }

        mean_diff = (sum(diffs) / len(diffs)) if diffs else None
        mean_abs_diff = (sum(abs_diffs) / len(abs_diffs)) if abs_diffs else None

        # Summarize pairwise agreements
        agreement_stats = {}
        for other, difflist in pairwise_abs_diffs.items():
            mean_diff_with_other = (sum(pairwise_diffs[other]) / len(pairwise_diffs[other])) if pairwise_diffs[other] else None
            mean_abs_diff_with_other = (sum(difflist) / len(difflist)) if difflist else None
            agreement_stats[other] = {
                'mean_diff': mean_diff_with_other,
                'mean_abs_diff': mean_abs_diff_with_other,
                'num_shared': len(difflist)  # how many films both rated
            }

        # Calculate average movie length and year
        avg_runtime = (total_runtime / count_with_runtime) if count_with_runtime > 0 else None
        avg_year_watched = (total_years / count_with_year) if count_with_year > 0 else None

        # Update user stats in DB
        users_collection.update_one(
            {'username': user['username']},
            {'$set': {
                'stats': {
                    'num_watches': num_watches,
                    'num_ratings': num_ratings,
                    'avg_rating': avg_rating,
                    'median_rating': median_rating,
                    'mode_rating': mode_rating,
                    'stdev_rating': stdev_rating,
                    'mean_diff': mean_diff,
                    'mean_abs_diff': mean_abs_diff,
                    'pairwise_agreement': agreement_stats,
                    'rating_distribution': rating_distr,
                    'num_likes': num_likes,
                    'like_ratio': like_ratio,
                    'genre_stats': genre_stats,
                    'avg_runtime': avg_runtime,
                    'total_runtime': total_runtime if total_runtime > 0 else None,
                    'avg_year_watched': avg_year_watched
                }
            }}
        )

    logging.info("User statistics updated successfully.")

def compute_superlatives(db, users_collection_name, films_collection_name, superlatives_collection_name):
    users_collection = db[users_collection_name]
    films_collection = db[films_collection_name]
    superlatives_collection = db[superlatives_collection_name]
    
    logging.info("Computing superlatives...")
    
    # Clear existing superlatives
    superlatives_collection.delete_many({})
    
    # Get all users with stats
    users = list(users_collection.find({"stats": {"$exists": True}}))
    films = list(films_collection.find({"num_ratings": {"$gte": 3}}))  # Only films with at least 3 ratings
    
    superlatives = []
    
    # User Superlatives
    
    # 1. Positive Polly (highest average rating)
    positive_users = sorted([u for u in users if u['stats'].get('avg_rating') is not None], 
                           key=lambda x: x['stats']['avg_rating'], reverse=True)
    superlatives.append({
        "name": "Positive Polly",
        "description": "User with the highest average rating",
        "first": [positive_users[0]['username']] if positive_users else [],
        "first_value": positive_users[0]['stats']['avg_rating'] if positive_users else None,
        "second": [positive_users[1]['username']] if len(positive_users) > 1 else [],
        "second_value": positive_users[1]['stats']['avg_rating'] if len(positive_users) > 1 else None,
        "third": [positive_users[2]['username']] if len(positive_users) > 2 else [],
        "third_value": positive_users[2]['stats']['avg_rating'] if len(positive_users) > 2 else None
    })
    
    # 2. Positive Polly (Comparative) (most positive average rating difference)
    comp_positive_users = sorted([u for u in users if u['stats'].get('mean_diff') is not None], 
                                key=lambda x: x['stats']['mean_diff'], reverse=True)
    superlatives.append({
        "name": "Positive Polly (Comparative)",
        "description": "User with the most positive average rating difference compared to other users",
        "first": [comp_positive_users[0]['username']] if comp_positive_users else [],
        "first_value": comp_positive_users[0]['stats']['mean_diff'] if comp_positive_users else None,
        "second": [comp_positive_users[1]['username']] if len(comp_positive_users) > 1 else [],
        "second_value": comp_positive_users[1]['stats']['mean_diff'] if len(comp_positive_users) > 1 else None,
        "third": [comp_positive_users[2]['username']] if len(comp_positive_users) > 2 else [],
        "third_value": comp_positive_users[2]['stats']['mean_diff'] if len(comp_positive_users) > 2 else None
    })
    
    # 3. Negative Nelly (lowest average rating)
    negative_users = sorted([u for u in users if u['stats'].get('avg_rating') is not None], 
                           key=lambda x: x['stats']['avg_rating'])
    superlatives.append({
        "name": "Negative Nelly",
        "description": "User with the lowest average rating",
        "first": [negative_users[0]['username']] if negative_users else [],
        "first_value": negative_users[0]['stats']['avg_rating'] if negative_users else None,
        "second": [negative_users[1]['username']] if len(negative_users) > 1 else [],
        "second_value": negative_users[1]['stats']['avg_rating'] if len(negative_users) > 1 else None,
        "third": [negative_users[2]['username']] if len(negative_users) > 2 else [],
        "third_value": negative_users[2]['stats']['avg_rating'] if len(negative_users) > 2 else None
    })

    # 4. Negative Nelly (Comparative) (most negative average rating difference)
    comp_negative_users = sorted([u for u in users if u['stats'].get('mean_diff') is not None], 
                                key=lambda x: x['stats']['mean_diff'])
    superlatives.append({
        "name": "Negative Nelly (Comparative)",
        "description": "User with the most negative average rating difference compared to other users",
        "first": [comp_negative_users[0]['username']] if comp_negative_users else [],
        "first_value": comp_negative_users[0]['stats']['mean_diff'] if comp_negative_users else None,
        "second": [comp_negative_users[1]['username']] if len(comp_negative_users) > 1 else [],
        "second_value": comp_negative_users[1]['stats']['mean_diff'] if len(comp_negative_users) > 1 else None,
        "third": [comp_negative_users[2]['username']] if len(comp_negative_users) > 2 else [],
        "third_value": comp_negative_users[2]['stats']['mean_diff'] if len(comp_negative_users) > 2 else None
    })
    
    # 5. BFFs (lowest mean absolute difference)
    agreeable_pairs = []
    for user in users:
        if 'pairwise_agreement' in user['stats']:
            for other_user, stats in user['stats']['pairwise_agreement'].items():
                if stats['num_shared'] >= 3:  # Minimum shared films
                    agreeable_pairs.append({
                        'user1': user['username'],
                        'user2': other_user,
                        'mean_abs_diff': stats['mean_abs_diff'],
                        'num_shared': stats['num_shared']
                    })
    
    agreeable_pairs = sorted([p for p in agreeable_pairs if p['mean_abs_diff'] is not None], 
                            key=lambda x: x['mean_abs_diff'])
    
    # Remove duplicates (A-B and B-A)
    unique_pairs = []
    seen_pairs = set()
    for pair in agreeable_pairs:
        pair_key = frozenset([pair['user1'], pair['user2']])
        if pair_key not in seen_pairs:
            unique_pairs.append(pair)
            seen_pairs.add(pair_key)
    
    superlatives.append({
        "name": "BFFs",
        "description": "Pair of users with the lowest mean absolute rating difference",
        "first": [f"{unique_pairs[0]['user1']} & {unique_pairs[0]['user2']}"] if unique_pairs else [],
        "first_value": unique_pairs[0]['mean_abs_diff'] if unique_pairs else None,
        "second": [f"{unique_pairs[1]['user1']} & {unique_pairs[1]['user2']}"] if len(unique_pairs) > 1 else [],
        "second_value": unique_pairs[1]['mean_abs_diff'] if len(unique_pairs) > 1 else None,
        "third": [f"{unique_pairs[2]['user1']} & {unique_pairs[2]['user2']}"] if len(unique_pairs) > 2 else [],
        "third_value": unique_pairs[2]['mean_abs_diff'] if len(unique_pairs) > 2 else None
    })
    
    # 6. Enemies (highest mean absolute difference)
    disagreeable_pairs = sorted(unique_pairs, key=lambda x: x['mean_abs_diff'], reverse=True)
    superlatives.append({
        "name": "Enemies",
        "description": "Pair of users with the highest mean absolute rating difference",
        "first": [f"{disagreeable_pairs[0]['user1']} & {disagreeable_pairs[0]['user2']}"] if disagreeable_pairs else [],
        "first_value": disagreeable_pairs[0]['mean_abs_diff'] if disagreeable_pairs else None,
        "second": [f"{disagreeable_pairs[1]['user1']} & {disagreeable_pairs[1]['user2']}"] if len(disagreeable_pairs) > 1 else [],
        "second_value": disagreeable_pairs[1]['mean_abs_diff'] if len(disagreeable_pairs) > 1 else None,
        "third": [f"{disagreeable_pairs[2]['user1']} & {disagreeable_pairs[2]['user2']}"] if len(disagreeable_pairs) > 2 else [],
        "third_value": disagreeable_pairs[2]['mean_abs_diff'] if len(disagreeable_pairs) > 2 else None
    })
    
    # 7. Best Attention Span (highest average runtime)
    runtime_users = sorted([u for u in users if u['stats'].get('avg_runtime') is not None], 
                          key=lambda x: x['stats']['avg_runtime'], reverse=True)
    superlatives.append({
        "name": "Best Attention Span",
        "description": "User with the highest average movie runtime",
        "first": [runtime_users[0]['username']] if runtime_users else [],
        "first_value": runtime_users[0]['stats']['avg_runtime'] if runtime_users else None,
        "second": [runtime_users[1]['username']] if len(runtime_users) > 1 else [],
        "second_value": runtime_users[1]['stats']['avg_runtime'] if len(runtime_users) > 1 else None,
        "third": [runtime_users[2]['username']] if len(runtime_users) > 2 else [],
        "third_value": runtime_users[2]['stats']['avg_runtime'] if len(runtime_users) > 2 else None
    })
    
    # 8. TikTok Brain (lowest average runtime)
    short_runtime_users = sorted([u for u in users if u['stats'].get('avg_runtime') is not None], 
                                key=lambda x: x['stats']['avg_runtime'])
    superlatives.append({
        "name": "TikTok Brain",
        "description": "User with the lowest average movie runtime",
        "first": [short_runtime_users[0]['username']] if short_runtime_users else [],
        "first_value": short_runtime_users[0]['stats']['avg_runtime'] if short_runtime_users else None,
        "second": [short_runtime_users[1]['username']] if len(short_runtime_users) > 1 else [],
        "second_value": short_runtime_users[1]['stats']['avg_runtime'] if len(short_runtime_users) > 1 else None,
        "third": [short_runtime_users[2]['username']] if len(short_runtime_users) > 2 else [],
        "third_value": short_runtime_users[2]['stats']['avg_runtime'] if len(short_runtime_users) > 2 else None
    })
    
    # 9. Unc (lowest average release year)
    oldest_users = sorted([u for u in users if u['stats'].get('avg_year_watched') is not None], 
                         key=lambda x: x['stats']['avg_year_watched'])
    superlatives.append({
        "name": "Unc",
        "description": "User with the lowest average movie release year",
        "first": [oldest_users[0]['username']] if oldest_users else [],
        "first_value": oldest_users[0]['stats']['avg_year_watched'] if oldest_users else None,
        "second": [oldest_users[1]['username']] if len(oldest_users) > 1 else [],
        "second_value": oldest_users[1]['stats']['avg_year_watched'] if len(oldest_users) > 1 else None,
        "third": [oldest_users[2]['username']] if len(oldest_users) > 2 else [],
        "third_value": oldest_users[2]['stats']['avg_year_watched'] if len(oldest_users) > 2 else None
    })
    
    # 10. Modernist (highest average release year)
    newest_users = sorted([u for u in users if u['stats'].get('avg_year_watched') is not None], 
                         key=lambda x: x['stats']['avg_year_watched'], reverse=True)
    superlatives.append({
        "name": "Modernist",
        "description": "User with the highest average movie release year",
        "first": [newest_users[0]['username']] if newest_users else [],
        "first_value": newest_users[0]['stats']['avg_year_watched'] if newest_users else None,
        "second": [newest_users[1]['username']] if len(newest_users) > 1 else [],
        "second_value": newest_users[1]['stats']['avg_year_watched'] if len(newest_users) > 1 else None,
        "third": [newest_users[2]['username']] if len(newest_users) > 2 else [],
        "third_value": newest_users[2]['stats']['avg_year_watched'] if len(newest_users) > 2 else None
    })
    
    # Film Superlatives
    
    # 11. Best movie (highest average rating)
    best_films = sorted([f for f in films if f.get('avg_rating') is not None], 
                       key=lambda x: x['avg_rating'], reverse=True)
    superlatives.append({
        "name": "Best Movie",
        "description": "Film with the highest average rating (minimum 3 ratings)",
        "first": [best_films[0]['film_title']] if best_films else [],
        "first_value": best_films[0]['avg_rating'] if best_films else None,
        "second": [best_films[1]['film_title']] if len(best_films) > 1 else [],
        "second_value": best_films[1]['avg_rating'] if len(best_films) > 1 else None,
        "third": [best_films[2]['film_title']] if len(best_films) > 2 else [],
        "third_value": best_films[2]['avg_rating'] if len(best_films) > 2 else None
    })
    
    # 12. Worst movie (lowest average rating)
    worst_films = sorted([f for f in films if f.get('avg_rating') is not None], 
                        key=lambda x: x['avg_rating'])
    superlatives.append({
        "name": "Worst Movie",
        "description": "Film with the lowest average rating (minimum 3 ratings)",
        "first": [worst_films[0]['film_title']] if worst_films else [],
        "first_value": worst_films[0]['avg_rating'] if worst_films else None,
        "second": [worst_films[1]['film_title']] if len(worst_films) > 1 else [],
        "second_value": worst_films[1]['avg_rating'] if len(worst_films) > 1 else None,
        "third": [worst_films[2]['film_title']] if len(worst_films) > 2 else [],
        "third_value": worst_films[2]['avg_rating'] if len(worst_films) > 2 else None
    })
    
    # 13. Most underrated movie (highest positive difference from letterboxd average)
    # Note: This requires letterboxd average rating in film data
    underrated_films = []
    for film in films:
        if film.get('avg_rating') is not None and film.get('metadata') is not None and film['metadata'].get('avg_rating') is not None:
            diff = film['avg_rating'] - film['metadata']['avg_rating']
            underrated_films.append((film, diff))
    
    underrated_films = sorted(underrated_films, key=lambda x: x[1], reverse=True)
    superlatives.append({
        "name": "Most Underrated Movie",
        "description": "Film with the highest positive rating difference from Letterboxd average",
        "first": [underrated_films[0][0]['film_title']] if underrated_films else [],
        "first_value": underrated_films[0][1] if underrated_films else None,
        "second": [underrated_films[1][0]['film_title']] if len(underrated_films) > 1 else [],
        "second_value": underrated_films[1][1] if len(underrated_films) > 1 else None,
        "third": [underrated_films[2][0]['film_title']] if len(underrated_films) > 2 else [],
        "third_value": underrated_films[2][1] if len(underrated_films) > 2 else None
    })
    
    # 14. Most overrated movie (highest negative difference from letterboxd average)
    overrated_films = sorted(underrated_films, key=lambda x: x[1])
    superlatives.append({
        "name": "Most Overrated Movie",
        "description": "Film with the highest negative rating difference from Letterboxd average",
        "first": [overrated_films[0][0]['film_title']] if overrated_films else [],
        "first_value": overrated_films[0][1] if overrated_films else None,
        "second": [overrated_films[1][0]['film_title']] if len(overrated_films) > 1 else [],
        "second_value": overrated_films[1][1] if len(overrated_films) > 1 else None,
        "third": [overrated_films[2][0]['film_title']] if len(overrated_films) > 2 else [],
        "third_value": overrated_films[2][1] if len(overrated_films) > 2 else None
    })
    
    # 15. Hit or Miss (highest standard deviation)
    disagreeable_films = sorted([f for f in films if f.get('stdev_rating') is not None], 
                               key=lambda x: x['stdev_rating'], reverse=True)
    superlatives.append({
        "name": "Hit or Miss",
        "description": "Film with the highest standard deviation in ratings",
        "first": [disagreeable_films[0]['film_title']] if disagreeable_films else [],
        "first_value": disagreeable_films[0]['stdev_rating'] if disagreeable_films else None,
        "second": [disagreeable_films[1]['film_title']] if len(disagreeable_films) > 1 else [],
        "second_value": disagreeable_films[1]['stdev_rating'] if len(disagreeable_films) > 1 else None,
        "third": [disagreeable_films[2]['film_title']] if len(disagreeable_films) > 2 else [],
        "third_value": disagreeable_films[2]['stdev_rating'] if len(disagreeable_films) > 2 else None
    })
    
    # Handle ties for all superlatives
    for superlative in superlatives:
        handle_ties(superlative, users, films)
    
    # Insert all superlatives into the database
    if superlatives:
        superlatives_collection.insert_many(superlatives)
    
    logging.info(f"Computed {len(superlatives)} superlatives and saved to database.")

def handle_ties(superlative, users, films):
    """Handle ties for all positions in a superlative"""
    if not superlative['first'] or superlative['first_value'] is None:
        return
    
    # Determine if this is a user or film superlative
    is_user_superlative = 'username' in (superlative['first'][0] if superlative['first'] else '')
    
    # Handle first place ties
    first_value = superlative['first_value']
    all_first = find_all_with_value(superlative['name'], first_value, users, films, is_user_superlative)
    
    if len(all_first) > 1:
        superlative['first'] = all_first
        # If exactly 2 films tied for first: clear second place but keep third
        if len(all_first) == 2:
            superlative['second'] = []
            superlative['second_value'] = None
        # If 3+ films tied for first: clear both second and third places
        elif len(all_first) > 2:
            superlative['second'] = []
            superlative['second_value'] = None
            superlative['third'] = []
            superlative['third_value'] = None
    
    # Handle second place ties (only if first place has a single winner)
    if (superlative['second'] and superlative['second_value'] is not None and 
        len(superlative['first']) == 1):
        second_value = superlative['second_value']
        all_second = find_all_with_value(superlative['name'], second_value, users, films, is_user_superlative)
        # Remove any that are already in first place
        all_second = [c for c in all_second if c not in superlative['first']]
        
        if len(all_second) > 1:
            superlative['second'] = all_second
            # Clear third place since second place is now a tie
            superlative['third'] = []
            superlative['third_value'] = None
    
    # Handle third place ties (allowed if: first place single winner + second place single winner, OR first place 2-way tie)
    if (superlative['third'] and superlative['third_value'] is not None and 
        (len(superlative['first']) == 1 and len(superlative['second']) == 1) or  # single winners for 1st and 2nd
        (len(superlative['first']) == 2 and not superlative['second'])):  # 2-way tie for 1st, no 2nd place
        third_value = superlative['third_value']
        all_third = find_all_with_value(superlative['name'], third_value, users, films, is_user_superlative)
        # Remove any that are already in first or second place
        all_third = [c for c in all_third if c not in superlative['first'] and c not in superlative['second']]
        
        if len(all_third) > 1:
            superlative['third'] = all_third

def find_all_with_value(superlative_name, value, users, films, is_user_superlative):
    """Find all users or films with the given value for the superlative"""
    if is_user_superlative:
        return [user['username'] for user in users if get_user_value(user, superlative_name) == value]
    else:
        return [film['film_title'] for film in films if get_film_value(film, superlative_name) == value]

def find_next_unique_value(superlative_name, current_value, users, films, is_user_superlative, reverse=False):
    """Find the next unique value after the current value"""
    if is_user_superlative:
        all_values = sorted(set([get_user_value(user, superlative_name) for user in users if get_user_value(user, superlative_name) is not None]), reverse=reverse)
    else:
        all_values = sorted(set([get_film_value(film, superlative_name) for film in films if get_film_value(film, superlative_name) is not None]), reverse=reverse)
    
    try:
        current_index = all_values.index(current_value)
        if current_index + 1 < len(all_values):
            return all_values[current_index + 1]
    except ValueError:
        pass
    
    return None

def is_high_value_better(superlative_name):
    """Determine if higher values are better for this superlative"""
    high_value_better = [
        "Positive Polly", "Positive Polly (Comparative)", "Best Attention Span", 
        "Modernist", "Best Movie", "Most Underrated Movie", "Hit or Miss"
    ]
    return superlative_name in high_value_better

def get_user_value(user, superlative_name):
    """Helper function to get the appropriate value for a user based on superlative name"""
    stats = user.get('stats', {})
    if superlative_name == "Positive Polly":
        return stats.get('avg_rating')
    elif superlative_name == "Positive Polly (Comparative)":
        return stats.get('mean_diff')
    elif superlative_name == "Negative Nelly":
        return stats.get('avg_rating')
    elif superlative_name == "Negative Nelly (Comparative)":
        return stats.get('mean_diff')
    elif superlative_name == "Best Attention Span":
        return stats.get('avg_runtime')
    elif superlative_name == "TikTok Brain":
        return stats.get('avg_runtime')
    elif superlative_name == "Unc":
        return stats.get('avg_year_watched')
    elif superlative_name == "Modernist":
        return stats.get('avg_year_watched')
    elif superlative_name == "BFFs" or superlative_name == "Enemies":
        # These are handled separately in the pairs logic
        return None
    return None

def get_film_value(film, superlative_name):
    """Helper function to get the appropriate value for a film based on superlative name"""
    if superlative_name == "Best Movie":
        return film.get('avg_rating')
    elif superlative_name == "Worst Movie":
        return film.get('avg_rating')
    elif superlative_name == "Hit or Miss":
        return film.get('stdev_rating')
    elif superlative_name == "Most Underrated Movie" or superlative_name == "Most Overrated Movie":
        # These are handled separately with diff calculation
        if film.get('avg_rating') is not None and film.get('metadata') is not None and film['metadata'].get('avg_rating') is not None:
            return film['avg_rating'] - film['metadata']['avg_rating']
    return None

def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Load environment variables
    load_dotenv()

    # MongoDB configuration
    logging.info("Connecting to MongoDB...")
    mongo_uri = os.getenv('DB_URI')
    db_name = os.getenv('DB_NAME')
    users_collection_name = os.getenv('DB_USERS_COLLECTION')
    films_collection_name = os.getenv('DB_FILMS_COLLECTION')
    superlatives_collection_name = os.getenv('DB_SUPERLATIVES_COLLECTION')
    client = MongoClient(mongo_uri)
    db = client[db_name]
    logging.info("Connected to MongoDB")

    # Compute statistics
    # compute_film_stats(db, films_collection_name)
    compute_user_stats(db, users_collection_name, films_collection_name)
    compute_superlatives(db, users_collection_name, films_collection_name, superlatives_collection_name)

if __name__ == "__main__":
    main()