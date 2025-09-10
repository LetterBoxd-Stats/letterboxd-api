"""
Letterboxd Scraper

A module for scraping user data and film metadata from Letterboxd.
Handles rate limiting and stores data in MongoDB.
"""

import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LetterboxdScraper:
    """Main class for scraping Letterboxd data."""
    
    def __init__(self, db_uri: str, db_name: str):
        """Initialize the scraper with database connection.
        
        Args:
            db_uri: MongoDB connection URI
            db_name: Name of the database to use
        """
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.request_delay = 15  # seconds between requests to avoid rate limiting
    
    def convert_stars_to_number(self, stars: str) -> Optional[float]:
        """Convert star string (e.g., '★★½') to numeric value.
        
        Args:
            stars: String containing star and half-star characters
            
        Returns:
            Numeric rating value or None if input is empty
        """
        if not stars:
            return None
        return stars.count('★') + 0.5 * stars.count('½')
    
    def extract_film_data(self, data: Dict, div: BeautifulSoup) -> Optional[str]:
        """Extract film info from poster div and store in data['films'].
        
        Args:
            data: Dictionary containing film and user data
            div: BeautifulSoup element containing film information
            
        Returns:
            Film ID if found, None otherwise
        """
        if not div or 'data-film-id' not in div.attrs:
            return None
            
        film_id = div['data-film-id']
        if film_id not in data['films']:
            film_title = div.find('img')['alt'] if div.find('img') else None
            film_link = div.get('data-target-link')
            
            data['films'][film_id] = {
                'title': film_title,
                'link': f'https://letterboxd.com{film_link}' if film_link else None,
                'reviews': [],
                'watches': []
            }
            
        return film_id
    
    def record_review_or_watch(
        self, 
        data: Dict, 
        username: str, 
        film_id: str, 
        rating: Optional[float], 
        is_liked: bool
    ):
        """Add review or watch to both user and film entries.
        
        Args:
            data: Dictionary containing film and user data
            username: Letterboxd username
            film_id: ID of the film
            rating: Numeric rating or None for watches
            is_liked: Whether the user liked the film
        """
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
    
    def scrape_user_page(self, data: Dict, username: str, page_num: int) -> bool:
        """Scrape a single Letterboxd page for the given user.
        
        Args:
            data: Dictionary to store scraped data
            username: Letterboxd username to scrape
            page_num: Page number to scrape
            
        Returns:
            True if there are more pages to scrape, False otherwise
        """
        url = f"https://letterboxd.com/{username}/films/by/date/page/{page_num}/"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page_num} for user {username}: {e}")
            return False
            
        soup = BeautifulSoup(response.text, 'html.parser')
        film_items = soup.select('ul.poster-list li') or soup.select('ul.grid li')
        
        for item in film_items:
            div = item.select_one('div.react-component') or item.select_one('div.linked-film-poster')
            film_id = self.extract_film_data(data, div)
            
            if not film_id:
                continue

            # Extract rating
            rating = None
            if div:
                rating_str = div.get('data-rating')
                rating = float(rating_str) if rating_str else None
                
            if rating is None:
                rating_span = item.select_one('span.rating')
                if rating_span:
                    rating = self.convert_stars_to_number(rating_span.text.strip())

            # Extract like status
            is_liked = item.select_one('span.like') is not None
            self.record_review_or_watch(data, username, film_id, rating, is_liked)

        # Check for next page
        return bool(soup.select_one('div.pagination a.next'))
    
    def upsert_collection(self, collection: Collection, match: Dict, data: Dict):
        """Helper function to upsert MongoDB document.
        
        Args:
            collection: MongoDB collection
            match: Query to match documents
            data: Data to upsert
        """
        collection.replace_one(match, data, upsert=True)
    
    def scrape_users_data(
        self, 
        users_collection_name: str, 
        films_collection_name: str, 
        usernames: List[str]
    ):
        """Scrape data for multiple Letterboxd users.
        
        Args:
            users_collection_name: Name of the MongoDB users collection
            films_collection_name: Name of the MongoDB films collection
            usernames: List of Letterboxd usernames to scrape
        """
        data = {
            "users": {username: {"reviews": [], "watches": []} for username in usernames},
            "films": {}
        }

        for username in usernames:
            logger.info(f"Scraping data for user: {username}")
            data['users'][username]['last_update_time'] = datetime.now(timezone.utc)
            page_num = 1
            
            while True:
                logger.info(f"Scraping {username} page {page_num}...")
                time.sleep(self.request_delay)
                
                has_next_page = self.scrape_user_page(data, username, page_num)
                if not has_next_page:
                    break
                    
                page_num += 1

        # Upload to MongoDB
        logger.info("Uploading scraped data to MongoDB...")
        users_collection = self.db[users_collection_name]
        films_collection = self.db[films_collection_name]

        for username, user_data in data['users'].items():
            self.upsert_collection(users_collection, {"username": username}, {
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

        logger.info("Data scraped and saved to database")
    
    def get_films_to_update(self, films_collection, scrape_all_films=False):
        """
        Get films that need metadata updates based on smart criteria.
        
        Newer films are updated more frequently to capture rating changes,
        while older films are updated less frequently.
        
        Args:
            films_collection: MongoDB collection of films
            scrape_all_films: If True, scrape all films regardless of update time
            
        Returns:
            MongoDB cursor for films that need updating
        """
        if scrape_all_films:
            return films_collection.find({})
        
        now = datetime.now(timezone.utc)
        
        # Define update frequency rules based on film age
        # Newer films get updated more frequently
        update_rules = [
            # Films from current year: update weekly
            {"year": now.year, "update_frequency_days": 7},
            # Films from previous year: update every 2 weeks
            {"year": now.year - 1, "update_frequency_days": 14},
            # Films from 2-5 years ago: update monthly
            {"year_range": (now.year - 5, now.year - 2), "update_frequency_days": 30},
            # Older films: update quarterly
            {"max_year": now.year - 6, "update_frequency_days": 90}
        ]
        
        # Build the query for films that need updating
        update_queries = []
        
        for rule in update_rules:
            # Calculate the cutoff date for this rule
            cutoff_date = now - timedelta(days=rule["update_frequency_days"])
            
            # Build the year filter based on rule type
            year_filter = {}
            if "year" in rule:
                year_filter = {"metadata.year": rule["year"]}
            elif "year_range" in rule:
                min_year, max_year = rule["year_range"]
                year_filter = {
                    "metadata.year": {
                        "$gte": min_year,
                        "$lte": max_year
                    }
                }
            elif "max_year" in rule:
                year_filter = {"metadata.year": {"$lte": rule["max_year"]}}
            
            # Add query for films matching this rule that need updating
            update_queries.append({
                # Films with metadata that match the year criteria
                **year_filter,
                # AND either have no last_metadata_update_time or it's older than the cutoff
                "$or": [
                    {"last_metadata_update_time": {"$exists": False}},
                    {"last_metadata_update_time": {"$lte": cutoff_date}},
                    {"last_metadata_update_time": None}
                ]
            })
        
        # Also include films that have no metadata at all
        no_metadata_query = {
            "$or": [
                {"metadata": {"$exists": False}},
                {"metadata": None}
            ]
        }
        
        # Combine all queries with OR
        final_query = {
            "$or": update_queries + [no_metadata_query]
        }
        
        return films_collection.find(final_query)
        
    def extract_film_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract metadata from a film's BeautifulSoup page.
        
        Args:
            soup: BeautifulSoup object of the film page
            
        Returns:
            Dictionary containing extracted film metadata
        """
        metadata = {}

        # Extract year
        year = soup.select_one('a[href*="/films/year/"]')
        metadata['year'] = int(year.text.strip()) if year else None

        # Extract genres
        metadata['genres'] = [
            g.text for g in soup.select('div#tab-genres a[href*="/films/genre/"]')
        ]

        # Extract description
        description = soup.select_one('div.truncate p')
        metadata['description'] = description.text.strip() if description else None

        # Extract directors
        metadata['directors'] = list(set([
            d.text.strip() for d in soup.select('a[href*="/director/"]')
        ]))

        # Extract actors
        metadata['actors'] = [
            a.text.strip() for a in soup.select('a[href*="/actor/"]')
        ]

        # Extract crew
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

        # Extract studios
        metadata['studios'] = [
            a.text.strip() for a in soup.select('a[href*="/studio/"]')
        ]

        # Extract themes
        themes = [a.text.strip() for a in soup.select('a[href*="/films/theme/"]')]
        mini_themes = [a.text.strip() for a in soup.select('a[href*="/films/mini-theme/"]')]
        metadata['themes'] = themes + mini_themes

        # Extract runtime
        runtime_text = soup.select_one('p.text-link.text-footer')
        runtime = None
        if runtime_text:
            match = re.search(r'(\d+)\s*mins', runtime_text.text)
            if match:
                runtime = int(match.group(1))
        metadata['runtime'] = runtime

        # Extract average rating
        avg_rating = None
        avg_meta = soup.select_one('meta[name="twitter:data2"]')
        if avg_meta:
            match = re.search(r'([\d.]+)', avg_meta["content"])
            if match:
                avg_rating = float(match.group(1))
        metadata['avg_rating'] = avg_rating

        # Extract backdrop URL
        backdrop_url = None
        backdrop_div = soup.select_one('div.backdrop-wrapper')
        if backdrop_div and backdrop_div.has_attr("data-backdrop"):
            backdrop_url = backdrop_div["data-backdrop"]
        metadata['backdrop_url'] = backdrop_url

        return metadata
    
    def scrape_films_data(self, films_collection_name: str, scrape_all_films: bool = False):
        """Scrape metadata for films.
        
        Args:
            films_collection_name: Name of the MongoDB films collection
            scrape_all_films: Whether to scrape all films or only those missing metadata
        """
        films_collection = self.db[films_collection_name]

        films_to_update = self.get_films_to_update(films_collection, scrape_all_films)

        for film in films_to_update:
            film_id = film['film_id']
            film_link = film.get('film_link')
            
            if not film_link:
                continue

            logger.info(f"Scraping metadata for {film['film_title']} ({film_id})...")
            time.sleep(self.request_delay)
            
            try:
                response = requests.get(film_link)
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to fetch film page {film_link}: {e}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')

            # Metadata extraction
            try:
                metadata = self.extract_film_metadata(soup)
                current_time = datetime.now(timezone.utc)
                
                films_collection.update_one(
                    {"film_id": film_id},
                    {
                        "$set": {
                            "metadata": metadata,
                            "last_metadata_update_time": current_time
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Error extracting metadata for {film['film_title']} ({film_id}): {e}")
                continue


def main():
    """Main function to run the Letterboxd scraper."""
    load_dotenv()
    
    # MongoDB config
    mongo_uri = os.getenv('DB_URI')
    db_name = os.getenv('DB_NAME')
    
    if not mongo_uri or not db_name:
        logger.error("Missing required environment variables: DB_URI and DB_NAME")
        return
    
    users_collection_name = os.getenv('DB_USERS_COLLECTION')
    films_collection_name = os.getenv('DB_FILMS_COLLECTION')
    usernames = os.getenv('LETTERBOXD_USERNAMES', '').split(',')
    
    # Remove any empty strings from usernames
    usernames = [username for username in usernames if username]
    
    if not usernames:
        logger.error("No usernames provided in LETTERBOXD_USERNAMES environment variable")
        return
    
    # Initialize and run scraper
    scraper = LetterboxdScraper(mongo_uri, db_name)
    # scraper.scrape_users_data(users_collection_name, films_collection_name, usernames)
    scraper.scrape_films_data(films_collection_name)


if __name__ == "__main__":
    main()