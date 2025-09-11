"""
Letterboxd Scraper

A module for scraping user data and film metadata from Letterboxd.
Handles rate limiting and stores data in MongoDB.
"""

import logging
import os
import re
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

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
        self.request_delay = 2  # Reduced base delay for parallel processing
        self.max_workers = 3  # Number of concurrent threads
        self.domain_delays = {}  # Track delays per domain to avoid rate limiting
        self.session = self._create_session()
    
    def _create_session(self):
        """Create a requests session with retry capabilities."""
        session = requests.Session()
        # Add headers to mimic a real browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        return session
    
    def _smart_delay(self, url: str):
        """
        Implement smart delay to avoid rate limiting.
        Tracks delays per domain and uses random jitter.
        """
        domain = urlparse(url).netloc
        current_time = time.time()
        
        # Check if we need to delay for this domain
        if domain in self.domain_delays:
            elapsed = current_time - self.domain_delays[domain]
            if elapsed < self.request_delay:
                sleep_time = self.request_delay - elapsed + random.uniform(0.1, 0.5)  # Add jitter
                time.sleep(sleep_time)
        
        # Update last request time for this domain
        self.domain_delays[domain] = current_time
    
    def _make_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP request with smart delay and retry logic."""
        for attempt in range(max_retries):
            try:
                self._smart_delay(url)
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # Check if we're being rate limited
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 30))
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                    time.sleep(retry_after)
                    continue
                    
                return response
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 1.0)
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All request attempts failed for {url}: {e}")
                    return None
        
        return None
    
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
    
    def scrape_user_page(self, data: Dict, username: str, page_num: int) -> Tuple[bool, int]:
        """Scrape a single Letterboxd page for the given user.
        
        Args:
            data: Dictionary to store scraped data
            username: Letterboxd username to scrape
            page_num: Page number to scrape
            
        Returns:
            Tuple of (has_next_page, films_processed_count)
        """
        url = f"https://letterboxd.com/{username}/films/by/date/page/{page_num}/"
        
        response = self._make_request(url)
        if not response:
            return False, 0
            
        soup = BeautifulSoup(response.text, 'html.parser')
        film_items = soup.select('ul.poster-list li') or soup.select('ul.grid li')
        films_processed = 0
        
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
            films_processed += 1

        # Check for next page
        return bool(soup.select_one('div.pagination a.next')), films_processed
    
    def scrape_user_data(self, username: str, users_collection: Collection, films_collection: Collection) -> bool:
        """Scrape data for a single user."""
        logger.info(f"Scraping data for user: {username}")
        
        data = {
            "users": {username: {"reviews": [], "watches": []}},
            "films": {}
        }
        
        data['users'][username]['last_update_time'] = datetime.now(timezone.utc)
        page_num = 1
        total_films = 0
        
        while True:
            logger.info(f"Scraping {username} page {page_num}...")
            
            has_next_page, films_processed = self.scrape_user_page(data, username, page_num)
            total_films += films_processed
            
            if not has_next_page or films_processed == 0:
                break
                
            page_num += 1
        
        # Upload to MongoDB
        if username in data['users']:  # CORRECTED: Check 'users' instead of 'user'
            user_data = data['users'][username]
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
                        "film_link": film_data['link']
                    },
                    "$push": {
                        "reviews": {"$each": film_data['reviews']},
                        "watches": {"$each": film_data['watches']}
                    }
                },
                upsert=True
            )
        
        logger.info(f"Completed scraping {username} with {total_films} films processed")
        return True
    
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
        """Scrape data for multiple Letterboxd users in parallel.
        
        Args:
            users_collection_name: Name of the MongoDB users collection
            films_collection_name: Name of the MongoDB films collection
            usernames: List of Letterboxd usernames to scrape
        """
        users_collection = self.db[users_collection_name]
        films_collection = self.db[films_collection_name]
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scraping tasks
            future_to_user = {
                executor.submit(self.scrape_user_data, username, users_collection, films_collection): username 
                for username in usernames
            }
            
            # Process results as they complete
            successful_scrapes = 0
            for future in as_completed(future_to_user):
                username = future_to_user[future]
                try:
                    success = future.result()
                    if success:
                        successful_scrapes += 1
                except Exception as e:
                    logger.error(f"Error scraping user {username}: {e}")
        
        logger.info(f"Completed scraping {successful_scrapes}/{len(usernames)} users")
    
    def get_films_to_update(self, films_collection, scrape_all_films=False):
        """
        Get films that need metadata updates with staggered scheduling.
        
        Uses a hash of film_id to distribute updates evenly across time periods
        to avoid the "thundering herd" problem.
        """
        if scrape_all_films:
            return films_collection.find({})
        
        now = datetime.now(timezone.utc)
        
        # Build the query for films that need updating
        update_queries = []
        
        # 1. Films with NO metadata at all - update immediately (no staggering)
        no_metadata_query = {
            "$or": [
                {"metadata": {"$exists": False}},
                {"metadata": None}
            ]
        }
        update_queries.append(no_metadata_query)
        
        # 2. Films WITH metadata - apply staggered updating based on year
        update_rules = [
            # Films from current year: update weekly (spread across the week)
            {"year": now.year, "update_frequency_days": 7},
            # Films from previous year: update every 2 weeks (spread across 2 weeks)
            {"year": now.year - 1, "update_frequency_days": 14},
            # Films from 2-5 years ago: update monthly (spread across the month)
            {"year_range": (now.year - 5, now.year - 2), "update_frequency_days": 30},
            # Older films: update quarterly (spread across the quarter)
            {"max_year": now.year - 6, "update_frequency_days": 90}
        ]
        
        for rule in update_rules:
            # Calculate the base cutoff date for this rule
            base_cutoff_date = now - timedelta(days=rule["update_frequency_days"])
            
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
            
            # Create a query that staggers updates based on film_id hash
            # This distributes films evenly across the update period
            staggered_query = {
                # Films with metadata that match the year criteria
                **year_filter,
                # AND have a last_metadata_update_time that's older than their staggered cutoff
                "$expr": {
                    "$or": [
                        {"$eq": ["$last_metadata_update_time", None]},
                        {
                            "$lte": [
                                "$last_metadata_update_time",
                                {
                                    "$add": [
                                        base_cutoff_date,
                                        {
                                            "$multiply": [
                                                rule["update_frequency_days"] * 24 * 60 * 60 * 1000,  # Convert days to milliseconds
                                                {
                                                    "$mod": [
                                                        {"$toInt": {"$substr": [{"$toString": "$film_id"}, -6, 6]}},  # Use last 6 digits of film_id
                                                        1000000  # Mod by 1,000,000 to get a value between 0-999999
                                                    ]
                                                },
                                                1000000.0  # Divide by 1,000,000 to get a fraction between 0-1
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
            
            update_queries.append(staggered_query)
        
        # Combine all queries with OR
        final_query = {
            "$or": update_queries
        }
        
        return films_collection.find(final_query)
    
    def scrape_film_metadata(self, film: Dict, films_collection: Collection) -> bool:
        """Scrape metadata for a single film."""
        film_id = film['film_id']
        film_link = film.get('film_link')
        
        if not film_link:
            return False

        logger.info(f"Scraping metadata for {film['film_title']} ({film_id})...")
        
        response = self._make_request(film_link)
        if not response:
            return False
            
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
            return True
        except Exception as e:
            logger.error(f"Error extracting metadata for {film['film_title']} ({film_id}): {e}")
            return False
        
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
        """Scrape metadata for films in parallel.
        
        Args:
            films_collection_name: Name of the MongoDB films collection
            scrape_all_films: Whether to scrape all films or only those missing metadata
        """
        films_collection = self.db[films_collection_name]
        films_to_update = list(self.get_films_to_update(films_collection, scrape_all_films))
        
        if not films_to_update:
            logger.info("No films need metadata updates")
            return
        
        logger.info(f"Scraping metadata for {len(films_to_update)} films")
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all film scraping tasks
            future_to_film = {
                executor.submit(self.scrape_film_metadata, film, films_collection): film['film_id'] 
                for film in films_to_update
            }
            
            # Process results as they complete
            successful_scrapes = 0
            for future in as_completed(future_to_film):
                film_id = future_to_film[future]
                try:
                    success = future.result()
                    if success:
                        successful_scrapes += 1
                except Exception as e:
                    logger.error(f"Error scraping film {film_id}: {e}")
        
        logger.info(f"Completed scraping metadata for {successful_scrapes}/{len(films_to_update)} films")


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
    
    # Scrape user data in parallel
    scraper.scrape_users_data(users_collection_name, films_collection_name, usernames)
    
    # Scrape film metadata in parallel
    # scraper.scrape_films_data(films_collection_name)


if __name__ == "__main__":
    main()