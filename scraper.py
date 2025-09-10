from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dotenv import load_dotenv
import logging
import os
from pymongo import MongoClient
import re
import requests
import time

def convert_stars_to_number(stars: str) -> float | None:
    """Convert star string (e.g., '★★½') to numeric value."""
    if not stars:
        return None
    return stars.count('★') + 0.5 * stars.count('½')

def extract_film_data(data: dict, div: BeautifulSoup) -> str | None:
    """Extract film info from poster div and store in data['films']."""
    if not div or 'data-film-id' not in div.attrs:
        return None
    film_id = div['data-film-id']
    if film_id not in data['films']:
        film_title = div.find('img')['alt'] if div.find('img') else None
        film_link = div.get('data-target-link')
        data['films'][film_id] = {
            'title': film_title,
            'link': 'https://letterboxd.com' + film_link if film_link else None,
            'reviews': [],
            'watches': []
        }
    return film_id

def record_review_or_watch(data: dict, username: str, film_id: str, rating: float | None, is_liked: bool):
    """Add review or watch to both user and film entries."""
    film_data = data['films'][film_id]
    user_entry = {
        'film_id': film_id,
        'film_title': film_data['title'],
        'film_link': film_data['link'],
        'is_liked': is_liked
    }

    if rating is not None:
        user_entry['rating'] = rating
        data['users'][username]['reviews'].append(user_entry)
        data['films'][film_id]['reviews'].append({
            'user': username,
            'rating': rating,
            'is_liked': is_liked
        })
    else:
        data['users'][username]['watches'].append(user_entry)
        data['films'][film_id]['watches'].append({
            'user': username,
            'is_liked': is_liked
        })

def scrape_letterboxd_page(data: dict, username: str, page_num: int) -> bool:
    """Scrape a single Letterboxd page for the given user."""
    url = f"https://letterboxd.com/{username}/films/by/date/page/{page_num}/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    film_items = soup.select('ul.poster-list li') or soup.select('ul.grid li')
    for item in film_items:
        div = item.select_one('div.react-component') or item.select_one('div.linked-film-poster')
        film_id = extract_film_data(data, div)
        if not film_id:
            continue

        # Rating: use data-rating if available, fallback to star parsing
        rating = None
        if div:
            rating_str = div.get('data-rating')
            rating = float(rating_str) if rating_str else None
        if rating is None:
            rating_span = item.select_one('span.rating')
            rating = convert_stars_to_number(rating_span.text.strip()) if rating_span else None

        # Like status
        is_liked = item.select_one('span.like') is not None

        record_review_or_watch(data, username, film_id, rating, is_liked)

    # Check for next page
    return bool(soup.select_one('div.pagination a.next'))

def upsert_collection(collection, match: dict, data: dict):
    """Helper function to upsert MongoDB document."""
    collection.replace_one(match, data, upsert=True)

def scrape_letterboxd_users_data(db, users_collection_name: str, films_collection_name: str, usernames: list[str]):
    data = {"users": {username: {"reviews": [], "watches": []} for username in usernames}, "films": {}}

    for username in usernames:
        data['users'][username]['last_update_time'] = datetime.now(timezone.utc)
        page_num = 1
        while True:
            logging.info(f"Scraping {username} page {page_num}...")
            time.sleep(15)  # avoid rate limits
            has_next_page = scrape_letterboxd_page(data, username, page_num)
            if has_next_page:
                page_num += 1
            else:
                break

    # Upload to MongoDB
    logging.info("Uploading scraped data to MongoDB...")
    users_collection = db[users_collection_name]
    films_collection = db[films_collection_name]

    for username, user_data in data['users'].items():
        upsert_collection(users_collection, {"username": username}, {
            "username": username,
            "reviews": user_data['reviews'],
            "watches": user_data.get('watches', []),
            "last_update_time": user_data['last_update_time']
        })
    for film_id, film_data in data['films'].items():
        films_collection.update_one(
            {"film_id": film_id},
            {
                "$set": {
                    "film_title": film_data['title'],
                    "film_link": film_data['link'],
                    "reviews": {"$each": film_data['reviews']},
                    "watches": {"$each": film_data['watches']}
                }
            },
            upsert=True
        )

    logging.info("Data scraped and saved to database")

def extract_film_metadata(soup: BeautifulSoup) -> dict:
    """Extract metadata from a film's BeautifulSoup page."""
    metadata = {}

    year = soup.select_one('a[href*="/films/year/"]')
    metadata['year'] = int(year.text.strip()) if year else None

    metadata['genres'] = [g.text for g in soup.select('div#tab-genres a[href*="/films/genre/"]')]

    description = soup.select_one('div.truncate p')
    metadata['description'] = description.text.strip() if description else None

    metadata['directors'] = list(set([d.text.strip() for d in soup.select('a[href*="/director/"]')]))

    metadata['actors'] = [a.text.strip() for a in soup.select('a[href*="/actor/"]')]

    crew = []
    crew_section = soup.select_one("div#tab-crew")
    if crew_section:
        for a in crew_section.select("a.text-slug"):
            href = a["href"].strip("/")
            parts = href.split("/")
            role = parts[0] if len(parts) >= 2 else None
            crew.append({
                "name": a.get_text(strip=True),
                "role": role
            })
    metadata['crew'] = crew

    metadata['studios'] = [a.text.strip() for a in soup.select('a[href*="/studio/"]')]

    themes = [a.text.strip() for a in soup.select('a[href*="/films/theme/"]')]
    mini_themes = [a.text.strip() for a in soup.select('a[href*="/films/mini-theme/"]')]
    metadata['themes'] = themes + mini_themes

    runtime_text = soup.select_one('p.text-link.text-footer')
    runtime = None
    if runtime_text:
        match = re.search(r'(\d+)\s*mins', runtime_text.text)
        if match:
            runtime = int(match.group(1))
    metadata['runtime'] = runtime

    avg_rating = None
    avg_meta = soup.select_one('meta[name="twitter:data2"]')
    if avg_meta:
        match = re.search(r'([\d.]+)', avg_meta["content"])
        if match:
            avg_rating = float(match.group(1))
    metadata['avg_rating'] = avg_rating

    backdrop_url = None
    backdrop_div = soup.select_one('div.backdrop-wrapper')
    if backdrop_div and backdrop_div.has_attr("data-backdrop"):
        backdrop_url = backdrop_div["data-backdrop"]
    metadata['backdrop_url'] = backdrop_url

    return metadata

def scrape_letterboxd_films_data(db, films_collection_name, scrape_all_films=False):
    films_collection = db[films_collection_name]

    if not scrape_all_films:
        films_missing_metadata = films_collection.find({
            "$or": [
                {"metadata": {"$exists": False}},
                {"metadata": None},
            ]
        })
    else:
        films_missing_metadata = films_collection.find({})

    for film in films_missing_metadata:
        film_id = film['film_id']
        film_link = film.get('film_link')
        if not film_link:
            continue

        logging.info(f"New movie! Scraping metadata for {film['film_title']} ({film_id})...")

        time.sleep(15)  # rate limit safety
        response = requests.get(film_link)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Metadata extraction
        try:
            metadata = extract_film_metadata(soup)
            films_collection.update_one(
                {"film_id": film_id},
                {"$set": {"metadata": metadata}}
            )
        except Exception as e:
            logging.error(f"Error extracting metadata for {film['film_title']} ({film_id}): {e}")
            continue

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    load_dotenv()

    # MongoDB config
    mongo_uri = os.getenv('DB_URI')
    db_name = os.getenv('DB_NAME')
    client = MongoClient(mongo_uri)
    db = client[db_name]

    users_collection_name = os.getenv('DB_USERS_COLLECTION')
    films_collection_name = os.getenv('DB_FILMS_COLLECTION')
    usernames = os.getenv('LETTERBOXD_USERNAMES', '').split(',')

    scrape_letterboxd_users_data(db, users_collection_name, films_collection_name, usernames)
    scrape_letterboxd_films_data(db, films_collection_name)

if __name__ == "__main__":
    main()
