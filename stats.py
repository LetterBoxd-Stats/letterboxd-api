from dotenv import load_dotenv
import logging
import os
from pymongo import MongoClient

import logging
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

def compute_user_stats(db, users_collection_name):
    users_collection = db[users_collection_name]
    users = list(users_collection.find({}))

    logging.info("Computing user statistics...")

    for user in users:
        reviews = user.get('reviews', [])
        watches = user.get('watches', [])

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

        # Compute rating distribution
        rating_distr = {}
        for i in range(0.5, 5.5, 0.5):
            rating_distr[str(i)] = sum(1 for r in reviews if r.get('rating') == i)

        # Update the user in the DB
        users_collection.update_one(
            {'user_id': user['user_id']},
            {'$set': {
                'stats': {
                    'num_watches': num_watches,
                    'num_ratings': num_ratings,
                    'avg_rating': avg_rating,
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
    compute_user_stats(db, users_collection_name)

if __name__ == "__main__":
    main()