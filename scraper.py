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
        """Make HTTP request with smart delay, retry logic, and header validation."""
        for attempt in range(max_retries):
            try:
                self._smart_delay(url)
                response = self.session.get(url, timeout=30)
                
                # Validate response headers before proceeding
                if not self._validate_response_headers(response):
                    logger.warning(f"Response header validation failed for {url}, attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep((2 ** attempt) + random.uniform(0.1, 1.0))
                        continue
                    else:
                        return None
                
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
    
    def validate_letterboxd_structure(self) -> bool:
        """
        Validate that Letterboxd pages have the expected structure before scraping.
        
        Returns:
            True if all validations pass, False otherwise
        """
        logger.info("Validating Letterboxd page structure...")
        
        test_cases = [
            self._validate_user_page_structure,
            self._validate_film_page_structure,
            self._validate_film_list_structure,
            self._validate_pagination_structure
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            try:
                if not test_case():
                    all_passed = False
                    logger.error(f"Validation failed: {test_case.__name__}")
            except Exception as e:
                logger.error(f"Validation error in {test_case.__name__}: {e}")
                all_passed = False
        
        if all_passed:
            logger.info("All Letterboxd structure validations passed!")
        else:
            logger.error("Letterboxd structure validations failed! Aborting scrape.")
        
        return all_passed

    def _validate_user_page_structure(self) -> bool:
        """Validate that user pages have the expected structure."""
        # Test with a known public user profile
        test_user = "devinbaron"  # Using one of your usernames
        url = f"https://letterboxd.com/{test_user}/films/by/date/"
        
        response = self._make_request(url)
        if not response:
            logger.error(f"Failed to fetch test user page: {url}")
            return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check critical selectors
        critical_selectors = [
            'ul.poster-list li',  # Film items in grid view
            'ul.grid li',         # Film items in list view (fallback)
            'div.pagination',     # Pagination container
            'div.react-component', # Film poster components
            'span.rating',        # Rating stars
            'span.like'           # Like indicator
        ]
        
        for selector in critical_selectors:
            elements = soup.select(selector)
            if not elements:
                logger.warning(f"Selector not found on user page: {selector}")
                # Don't fail immediately for all selectors, some might be optional
        
        # Check for essential elements
        essential_elements = [
            ('film items', bool(soup.select('ul.poster-list li') or soup.select('ul.grid li'))),
            ('pagination', bool(soup.select_one('div.pagination'))),
            ('film posters', bool(soup.select('div[data-film-id]'))),
        ]
        
        for element_name, exists in essential_elements:
            if not exists:
                logger.error(f"Essential element missing from user page: {element_name}")
                return False
        
        logger.info("User page structure validation passed")
        return True

    def _validate_film_page_structure(self) -> bool:
        """Validate that film pages have the expected structure."""
        # Test with a known film
        test_films = [
            "https://letterboxd.com/film/the-shawshank-redemption/",
            "https://letterboxd.com/film/pulp-fiction/",
            "https://letterboxd.com/film/the-dark-knight/"
        ]
        
        for film_url in test_films:
            response = self._make_request(film_url)
            if not response:
                logger.error(f"Failed to fetch test film page: {film_url}")
                continue  # Try next film
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check critical metadata selectors
            critical_selectors = [
                'a[href*="/films/year/"]',           # Year
                'div#tab-genres a[href*="/films/genre/"]',  # Genres
                'div.truncate p',                    # Description
                'a[href*="/director/"]',             # Directors
                'a[href*="/actor/"]',                # Actors
                'div#tab-crew',                      # Crew section
                'a[href*="/studio/"]',               # Studios
                'meta[name="twitter:data2"]',        # Average rating
                'div.backdrop-wrapper'               # Backdrop
            ]
            
            found_selectors = 0
            for selector in critical_selectors:
                elements = soup.select(selector)
                if elements:
                    found_selectors += 1
                else:
                    logger.warning(f"Selector not found on film page {film_url}: {selector}")
            
            # Require at least 70% of critical selectors to be present
            if found_selectors / len(critical_selectors) < 0.7:
                logger.error(f"Film page structure significantly changed: {film_url}")
                return False
            
            # Check for essential metadata
            essential_metadata = [
                ('year', soup.select_one('a[href*="/films/year/"]')),
                ('title', soup.select_one('h1.film-title')),
            ]
            
            for metadata_name, element in essential_metadata:
                if not element:
                    logger.error(f"Essential metadata missing from film page: {metadata_name}")
                    return False
        
        logger.info("Film page structure validation passed")
        return True

    def _validate_film_list_structure(self) -> bool:
        """Validate that film list items have the expected data attributes."""
        test_user = "devinbaron"
        url = f"https://letterboxd.com/{test_user}/films/by/date/page/1/"
        
        response = self._make_request(url)
        if not response:
            logger.error("Failed to fetch film list for validation")
            return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        film_items = soup.select('ul.poster-list li') or soup.select('ul.grid li')
        
        if not film_items:
            logger.error("No film items found in list")
            return False
        
        # Check a sample of film items for required data attributes
        sample_size = min(5, len(film_items))
        valid_items = 0
        
        for i in range(sample_size):
            item = film_items[i]
            div = item.select_one('div.react-component') or item.select_one('div.linked-film-poster')
            
            if div and 'data-film-id' in div.attrs:
                valid_items += 1
                
                # Check for optional but important attributes
                if 'data-target-link' not in div.attrs:
                    logger.warning("data-target-link attribute missing from film item")
                if 'data-rating' not in div.attrs:
                    logger.warning("data-rating attribute missing from film item")
        
        # Require at least 60% of sample items to be valid
        if valid_items / sample_size < 0.6:
            logger.error("Film item structure significantly changed")
            return False
        
        logger.info("Film list structure validation passed")
        return True

    def _validate_pagination_structure(self) -> bool:
        """Validate that pagination works as expected."""
        test_user = "devinbaron"
        url = f"https://letterboxd.com/{test_user}/films/by/date/page/1/"
        
        response = self._make_request(url)
        if not response:
            logger.error("Failed to fetch page for pagination validation")
            return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        pagination = soup.select_one('div.pagination')
        
        if not pagination:
            logger.warning("No pagination found - user might have only one page")
            return True  # This isn't necessarily a failure
        
        # Check pagination elements
        pagination_elements = pagination.select('a')
        if not pagination_elements:
            logger.warning("Pagination found but no links")
            return True  # Not necessarily a failure
        
        # Check if next page link exists
        next_page = pagination.select_one('a.next')
        if not next_page:
            logger.info("Single page of results - pagination validation passed")
            return True
        
        logger.info("Pagination structure validation passed")
        return True

    def _validate_response_headers(self, response: requests.Response) -> bool:
        """Validate that response headers indicate a successful request."""
        if response.status_code != 200:
            logger.error(f"Unexpected status code: {response.status_code}")
            return False
        
        # Check for rate limiting headers
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            if remaining < 10:
                logger.warning(f"Low rate limit remaining: {remaining}")
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            logger.error(f"Unexpected content type: {content_type}")
            return False
        
        return True
    
    def record_review_or_watch(
        self, 
        data: Dict, 
        username: str, 
        film_id: str, 
        rating: Optional[float], 
        is_liked: bool
    ):
        """Add review or watch to both user and film entries."""
        film_data = data['films'][film_id]
        current_time = datetime.now(timezone.utc)
        
        user_entry = {
            'film_id': film_id,
            'film_title': film_data['title'],
            'film_link': film_data['link'],
            'is_liked': is_liked,
            'last_updated': current_time
        }

        if rating is not None:
            # This is a review
            user_entry['rating'] = rating
            data['users'][username]['reviews'].append(user_entry)
            
            data['films'][film_id]['reviews'].append({
                'user': username,
                'rating': rating,
                'is_liked': is_liked,
                'last_updated': current_time
            })
        else:
            # This is a watch
            data['users'][username]['watches'].append(user_entry)
            data['films'][film_id]['watches'].append({
                'user': username,
                'is_liked': is_liked,
                'last_updated': current_time
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
        """Scrape data for a single user by completely replacing arrays."""
        logger.info(f"Scraping data for user: {username}")
        
        data = {
            "users": {username: {"reviews": [], "watches": []}},
            "films": {}
        }
        
        current_time = datetime.now(timezone.utc)
        data['users'][username]['last_update_time'] = current_time
        page_num = 1
        total_films = 0
        
        while True:
            logger.info(f"Scraping {username} page {page_num}...")
            
            has_next_page, films_processed = self.scrape_user_page(data, username, page_num)
            total_films += films_processed
            
            if not has_next_page or films_processed == 0:
                break
                
            page_num += 1
        
        # Update user document - completely replace arrays
        users_collection.update_one(
            {"username": username},
            {
                "$set": {
                    "username": username,
                    "reviews": data['users'][username]['reviews'],
                    "watches": data['users'][username]['watches'],
                    "last_update_time": current_time
                }
            },
            upsert=True
        )
        
        # For films, we need to be more careful since multiple users contribute
        for film_id, film_data in data['films'].items():
            # First remove any existing entries from this user
            films_collection.update_one(
                {"film_id": film_id},
                {
                    "$pull": {
                        "reviews": {"user": username},
                        "watches": {"user": username}
                    }
                }
            )
            
            # Then add the new entries
            if film_data['reviews']:
                films_collection.update_one(
                    {"film_id": film_id},
                    {
                        "$push": {"reviews": {"$each": film_data['reviews']}}
                    }
                )
            
            if film_data['watches']:
                films_collection.update_one(
                    {"film_id": film_id},
                    {
                        "$push": {"watches": {"$each": film_data['watches']}}
                    }
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
        """Scrape data for multiple Letterboxd users in parallel."""
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
        Python-based approach to avoid complex MongoDB aggregation.
        """
        if scrape_all_films:
            return films_collection.find({})
        
        now = datetime.now(timezone.utc)  # This is timezone-aware
        
        # Get all candidate films first (in batches to avoid memory issues)
        films_to_update_ids = []
        batch_size = 1000
        
        # Use batches to avoid loading all films into memory at once
        for batch_start in range(0, 1000000, batch_size):  # Arbitrary large number
            batch = list(films_collection.find({}).skip(batch_start).limit(batch_size))
            if not batch:
                break
                
            for film in batch:
                film_id = film.get('film_id')
                last_update = film.get('last_metadata_update_time')
                metadata = film.get('metadata', {})
                film_year = metadata.get('year') if metadata else None
                
                # Check if film has no metadata
                if metadata is None or not metadata:
                    films_to_update_ids.append(film_id)
                    continue
                    
                # Determine update frequency based on film year
                update_frequency_days = self._get_update_frequency(film_year, now.year)
                
                # Calculate staggered cutoff date based on film_id hash
                cutoff_date = self._get_staggered_cutoff_date(now, update_frequency_days, film_id)
                
                # Check if film needs updating - handle timezone comparison
                if last_update is None:
                    films_to_update_ids.append(film_id)
                else:
                    # Ensure both datetimes are timezone-aware for comparison
                    if last_update.tzinfo is None:
                        # If last_update is naive, assume it's UTC and make it aware
                        last_update_aware = last_update.replace(tzinfo=timezone.utc)
                    else:
                        last_update_aware = last_update
                    
                    if last_update_aware <= cutoff_date:
                        films_to_update_ids.append(film_id)
        
        # Return cursor for films that need updating
        if films_to_update_ids:
            return films_collection.find({"film_id": {"$in": films_to_update_ids}})
        else:
            return films_collection.find({"film_id": {"$in": []}})  # Empty cursor

    def _get_staggered_cutoff_date(self, now, frequency_days, film_id):
        """Calculate staggered cutoff date based on film_id."""
        # Create a consistent hash from film_id (handle various ID formats)
        film_str = str(film_id)
        
        # Use a simple hash function that works for all ID types
        if film_str.isdigit() and len(film_str) >= 4:
            # For numeric IDs, use the last few digits
            film_hash = int(film_str[-4:]) % 10000
        else:
            # For string IDs, use Python's built-in hash
            film_hash = abs(hash(film_str)) % 10000
        
        # Convert to a fraction between 0-1
        fraction = film_hash / 10000.0
        
        # Calculate staggered cutoff (spread across the frequency period)
        staggered_days = frequency_days * fraction
        cutoff_date = now - timedelta(days=staggered_days)
        
        # Ensure cutoff_date is timezone-aware (same as 'now')
        return cutoff_date

    def _get_update_frequency(self, film_year, current_year):
        """Determine update frequency based on film age."""
        if film_year is None:
            return 7  # Default for films without year data
        
        age = current_year - film_year
        
        if age <= 0:  # Current year
            return 7
        elif age == 1:  # Previous year
            return 14
        elif 2 <= age <= 5:  # 2-5 years old
            return 30
        else:  # 6+ years old
            return 90
    
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
        """Scrape metadata for films in the database in parallel."""        
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

    # Run validation first
    # if not scraper.validate_letterboxd_structure():
    #     logger.error("Letterboxd structure validation failed. Aborting.")
    #     return
    
    # Scrape user data in parallel
    # scraper.scrape_users_data(users_collection_name, films_collection_name, usernames)
    
    # Scrape film metadata in parallel
    scraper.scrape_films_data(films_collection_name)


if __name__ == "__main__":
    main()