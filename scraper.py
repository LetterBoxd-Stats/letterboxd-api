# api/scraper.py
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dotenv import load_dotenv
import logging
import os
from pymongo import MongoClient
import requests
import time

def convert_stars_to_number(stars):
    if not stars:
        return None
    full_stars = stars.count('★')
    half_stars = stars.count('½')
    return full_stars + 0.5 * half_stars

def extract_film_data(data, div):
        film_id = div['data-film-id'] if div and 'data-film-id' in div.attrs else None
        if film_id is None:
            return False
        if film_id not in data['films']:
            film_title = div.find('img')['alt'] if div else None
            film_link = div['data-target-link'] if div and 'data-target-link' in div.attrs else None
            data['films'][film_id] = {
                'title': film_title,
                'link': 'letterboxd.com' + film_link
            }
        return film_id

def extract_user_review(data, review, film_id, username):
    rating_span = review.select_one('p.poster-viewingdata span.rating')
    stars = rating_span.text.strip() if rating_span else None
    rating = convert_stars_to_number(stars)
    is_liked = (review.select_one('p.poster-viewingdata span.like') is not None)
    if rating is not None:
        data['users'][username]['reviews'][film_id] = {
            'rating': rating,
            'is_liked': is_liked
        }
    else:
        data['users'][username]['watches'][film_id] = {
            'is_liked': is_liked
        }

# returns True if there is another page
def scrape_letterboxd_page(data, username, page_num):
    url = f"https://letterboxd.com/{username}/films/by/rated-date/page/{page_num}/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    reviews = soup.select('.poster-container')
    for review in reviews:
        div = review.select_one('div.linked-film-poster')

        # Extract film data
        film_id = extract_film_data(data, div)
        if film_id is not False:
            extract_user_review(data, review, film_id, username)
    
    # Check if there is a next page
    next_page = soup.select_one('div.pagination a.next')
    return (next_page is not None)

def scrape_letterboxd_users_data(db, users_collection_name, films_collection_name, usernames):
    data = {"users": {username: {"reviews": {}, "watches": {}} for username in usernames}, "films": {}}

    for i, username in enumerate(usernames):
        page_num = 1
        data['users'][username]['last_update_time'] = datetime.now(timezone.utc)
        while page_num > 0:
            logging.info(f"Scraping {username} page {page_num}...")
            time.sleep(15)  # Sleep to avoid hitting the server too hard
            has_next_page = scrape_letterboxd_page(data, username, page_num)
            if has_next_page: page_num += 1
            else: break
    
    # Upload to MongoDB
    logging.info("Uploading scraped data to MongoDB...")
    users_collection = db[users_collection_name]
    films_collection = db[films_collection_name]
    for username, user_data in data['users'].items():
        users_collection.replace_one(
            {"username": username},  # Match condition
            {
                "username": username,
                "reviews": user_data['reviews'],
                "watches": user_data.get('watches', {}),
                "last_update_time": user_data['last_update_time']
            }, 
            upsert=True
        )
    for film_id, film_data in data['films'].items():
        films_collection.replace_one(
            {"film_id": film_id},  # Match condition
            {
                "film_id": film_id,
                "film_title": film_data['title'],
                "film_link": film_data['link']
            },
            upsert=True
        )
    
    logging.info("Data scraped and saved to database")

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

    # Get usernames from environment variable
    usernames = os.getenv('LETTERBOXD_USERNAMES', '').split(',')

    # Scrape data
    scrape_letterboxd_users_data(db, users_collection_name, films_collection_name, usernames)

if __name__ == "__main__":
    main()