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
        total_rating = sum(r['rating'] for r in reviews if 'rating' in r)

        # Count likes
        num_likes = sum(1 for r in reviews if r.get('is_liked'))
        num_likes += sum(1 for w in watches if w.get('is_liked'))

        # Calculate averages and ratios
        avg_rating = (total_rating / num_ratings) if num_ratings > 0 else None
        like_ratio = (num_likes / num_watches) if num_watches > 0 else None

        # Update the film in the DB
        films_collection.update_one(
            {'film_id': film['film_id']},
            {'$set': {
                'num_ratings': num_ratings,
                'avg_rating': avg_rating,
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

    for user in users:
        reviews = user.get('reviews', [])
        watches = user.get('watches', [])

        # Counts
        num_ratings = len(reviews)
        num_watches = num_ratings + len(watches)

        # Extract ratings
        ratings = [r['rating'] for r in reviews if 'rating' in r]

        # Likes
        num_likes = sum(1 for r in reviews if r.get('is_liked'))
        num_likes += sum(1 for w in watches if w.get('is_liked'))

        # Averages
        avg_rating = (sum(ratings) / num_ratings) if num_ratings > 0 else None
        like_ratio = (num_likes / num_watches) if num_watches > 0 else None

        # Rating distribution (0.5 → 5.0 in 0.5 steps)
        rating_distr = {str(i): ratings.count(i) for i in [x * 0.5 for x in range(1, 11)]}

        # Median, Mode, Stdev
        median_rating = statistics.median(ratings) if ratings else None
        try:
            mode_rating = statistics.mode(ratings) if ratings else None
        except statistics.StatisticsError:
            mode_rating = None
        stdev_rating = statistics.stdev(ratings) if len(ratings) > 1 else None

        # Pairwise diffs vs. group
        diffs = []
        abs_diffs = []

        # Pairwise agreement dict: {other_username: [diffs]}
        pairwise_diffs = defaultdict(list)
        pairwise_abs_diffs = defaultdict(list)

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
                    'like_ratio': like_ratio
                }
            }}
        )

    logging.info("User statistics updated successfully.")

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
    client = MongoClient(mongo_uri)
    db = client[db_name]
    logging.info("Connected to MongoDB")

    # Compute statistics
    compute_film_stats(db, films_collection_name)
    compute_user_stats(db, users_collection_name, films_collection_name)

if __name__ == "__main__":
    main()