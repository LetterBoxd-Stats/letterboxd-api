from dotenv import load_dotenv
import logging
import os
from pymongo import MongoClient

import logging

def compute_stats(db, users_collection_name, films_collection_name):
    users = list(db[users_collection_name].find({}))
    films = list(db[films_collection_name].find({}))
    
    # Build film lookup by ID for fast access
    film_lookup = {film['film_id']: film for film in films}
    
    # Initialize stats
    for film in film_lookup.values():
        film.update({
            'num_watches': 0,
            'num_ratings': 0,
            'avg_rating': 0.0,
            'num_likes': 0,
            'like_ratio': 0.0
        })

    def update_film_from_review(film_id, review):
        film = film_lookup.get(film_id)
        if not film:
            return
        film['num_watches'] += 1
        film['num_ratings'] += 1
        film['avg_rating'] += review['rating']
        if review.get('is_liked'):
            film['num_likes'] += 1

    def update_film_from_watch(film_id, watch):
        film = film_lookup.get(film_id)
        if not film:
            return
        film['num_watches'] += 1
        if watch.get('is_liked'):
            film['num_likes'] += 1

    # Accumulate stats
    logging.info("Accumulating user reviews and watches...")
    for user in users:
        for film_id, review in user.get('reviews', {}).items():
            update_film_from_review(film_id, review)
        for film_id, watch in user.get('watches', {}).items():
            update_film_from_watch(film_id, watch)

    # Finalize stats and update DB
    films_collection = db[films_collection_name]
    logging.info("Finalizing film statistics...")
    for film in film_lookup.values():
        num_ratings = film['num_ratings']
        num_watches = film['num_watches']
        film['avg_rating'] = (film['avg_rating'] / num_ratings) if num_ratings > 0 else None
        film['like_ratio'] = (film['num_likes'] / num_watches) if num_watches > 0 else None

        films_collection.update_one(
            {'film_id': film['film_id']},
            {'$set': {
                'num_ratings': film['num_ratings'],
                'avg_rating': film['avg_rating'],
                'num_likes': film['num_likes'],
                'num_watches': film['num_watches'],
                'like_ratio': film['like_ratio']
            }}
        )

    logging.info("Computed and updated film statistics in database")


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
    compute_stats(db, users_collection_name, films_collection_name)

if __name__ == "__main__":
    main()