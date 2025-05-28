# api/scraper.py
import json
import requests
from bs4 import BeautifulSoup

def convert_stars_to_number(stars):
    if not stars:
        return None
    full_stars = stars.count('★')
    half_stars = stars.count('½')
    return full_stars + 0.5 * half_stars

def scrape_letterboxd_data(usernames=['samuelmgaines', 'embrune', 'devinbaron', 'Martendo24680', 'stephaniebrown2', 'nkilpatrick']):
    data = {"users": {username: [] for username in usernames}, "films": {}}

    for username in usernames:
        url = f"https://letterboxd.com/{username}/films/"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        reviews = soup.select('.poster-container')
        for review in reviews:
            div = review.select_one('div.linked-film-poster')

            # Extract film data
            film_id = div['data-film-id'] if div and 'data-film-id' in div.attrs else None
            if film_id is None:
                continue
            if film_id not in data['films']:
                film_title = div.find('img')['alt'] if div else None
                film_link = div['data-target-link'] if div and 'data-target-link' in div.attrs else None
                data['films'][film_id] = {
                    'title': film_title,
                    'link': film_link
                }
            
            # Extract user review
            rating_span = review.select_one('p.poster-viewingdata span.rating')
            stars = rating_span.text.strip() if rating_span else None
            rating = convert_stars_to_number(stars)
            if rating is not None:
                data['users'][username].append({
                    'film_id': film_id,
                    'rating': rating
                })

    # Save to JSON
    with open('api/data.json', 'w') as f:
        json.dump(data, f, indent=2)

def main():
    scrape_letterboxd_data()
    print("Data scraped and saved to api/data.json")

if __name__ == "__main__":
    main()