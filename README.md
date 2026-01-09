# Letterboxd API

This is a Flask-based API for exposing [Letterboxd](https://letterboxd.com) user review data via HTTP endpoints.

Deployed on [Vercel](https://vercel.com), and configurable via environment variables.

Production Base URL: https://letterboxd-api-zeta.vercel.app/

---

## Endpoints

### `GET /`

Returns a simple greeting.

### `GET /films`

#### Query Parameters:

-   `page`: integer, optional (default: `1`)
-   `limit`: integer, optional (default: `20`) - Number of films per page
-   `sort_by`: string, optional (default: `film_title`) - Field to sort by (see Sortable Fields)
-   `sort_order`: string, optional (default: `asc` for string fields, `desc` for numerical fields) - Sort direction (`asc` for ascending, `desc` for descending)

    **Numeric Filters**

-   `avg_rating_gte` / `avg_rating_lte`: integer, optional - Average rating from your scraped users
-   `like_ratio_gte` / `like_ratio_lte`: integer, optional - Ratio of likes to watches/ratings
-   `num_likes_gte` / `num_likes_lte`: integer, optional - Number of likes from your users
-   `num_ratings_gte` / `num_ratings_lte`: integer, optional - Number of ratings from your users
-   `num_watches_gte` / `num_watches_lte`: integer, optional - Number of watches from your users
-   `metadata.avg_rating_gte` / `metadata.avg_rating_lte`: integer, optional - Letterboxd's overall average rating
-   `metadata.year_gte` / `metadata.year_lte`: integer, optional - Film release year
-   `metadata.runtime_gte` / `metadata.runtime_lte`: integer, optional - Film runtime in minutes

    **Text Field Filters**

-   `film_title`: string, optional - Comma-separated list of film title substring (e.g., `godfather,part`)
-   `directors`: string, optional - Comma-separated list of director name substrings (e.g., `directors=Nolan,Christopher`)
-   `actors`: string, optional - Comma-separated list of actor name substrings (e.g., `actors=Leo,DeCap`)
-   `studios`: string, optional - Comma-separated list of studio name substrings (e.g., `studios=Warner,Universal`)
-   `themes`: string, optional - Comma-separated list of theme substrings (e.g., `themes=Noir,Romance`)
-   `description`: string, optional - Comma-separated list of description substrings (e.g., `description=space,mission`)
-   `crew`: string, optional - Comma-separated list of crew member name substrings (e.g., `crew=Johnny`)
-   `genres`: string, optional - Comma-separated list of genres (e.g., `genres=Comedy,Drama`)

    **User-Based Filters**

-   `watched_by`: string, optional - Comma-separated list of usernames (AND logic - films must be watched by ALL specified users)
-   `not_watched_by`: string, optional - Comma-separated list of usernames (films must NOT be watched by ANY specified users)
-   `rated_by`: string, optional - Comma-separated list of usernames (AND logic - films must be rated by ALL specified users)
-   `not_rated_by`: string, optional - Comma-separated list of usernames (films must NOT be rated by ANY specified users)

    **Sortable Fields**

-   `film_id`, `film_title`, `film_link`
-   `avg_rating`, `like_ratio`, `num_likes`, `num_ratings`, `num_watches`
-   `metadata.avg_rating`, `metadata.year`, `metadata.runtime`

#### Examples

```bash
# 90s dramas with high Letterboxd ratings
/films?metadata.year_gte=1990&metadata.year_lte=1999&genres=Drama&metadata.avg_rating_gte=4.0

# Christopher Nolan films watched by specific users
/films?directors=Christopher,Nolan&watched_by=user1,user2&sort_by=metadata.year&sort_order=desc

# Short comedies with specific actors
/films?genres=Comedy&metadata.runtime_lte=100&actors=Jim,Carrey&page=2&limit=10

# Films with cinematographer in crew, sorted by runtime
/films?crew=cinematographer&sort_by=metadata.runtime&sort_order=desc
```

Returns a paginated list of scraped film entries according to the query parameters.

### `GET /films/{film_id}`

Returns the film entry for the specified `film_id`.

### `GET /users`

Returns all users and their scraped review data:

### `GET /users/{username}`

Returns the user with the specified `username` and their scraped review data.

#### Query Parameters

-   `include_films`: boolean, optional (default `false`). Determines whether to include `reviews` and `watches` arrays, which can be large.

### `GET /superlatives`

Returns a list of superlatives grouped within categories.

### `GET /recommendations`

Return a list of recommendations for a group of users to watch. Default behavior is to recommend movies all watchers have not seen.

#### Query Parameters

-   `watchers`: string, required - Comma-separated list of usernames to recommend for
-   `num_recs`: integer, optional (default `3`) - Number of movies to recommend
-   `offset`: integer, optional (default `0`) - Number of recommendations to skip
-   `ok_to_have_watched`: string, optional - Comma-separated subset of `watchers` to override default not-watched filter. Can be set to `"all"`
-   `max_ok_to_have_watched`: integer, optional (default `0`) - Maximum number of `ok_to_have_watched` that have already watched the movie

    **Numeric Filters**

-   `metadata.avg_rating_gte` / `metadata.avg_rating_lte`: integer, optional - Letterboxd's overall average rating
-   `metadata.year_gte` / `metadata.year_lte`: integer, optional - Film release year
-   `metadata.runtime_gte` / `metadata.runtime_lte`: integer, optional - Film runtime in minutes

    **Text Field Filters**

-   `directors`: string, optional - Comma-separated list of director name substrings (e.g., `directors=Nolan,Christopher`)
-   `actors`: string, optional - Comma-separated list of actor name substrings (e.g., `actors=Leo,DeCap`)
-   `studios`: string, optional - Comma-separated list of studio name substrings (e.g., `studios=Warner,Universal`)
-   `themes`: string, optional - Comma-separated list of theme substrings (e.g., `themes=Noir,Romance`)
-   `description`: string, optional - Comma-separated list of description substrings (e.g., `description=space,mission`)
-   `crew`: string, optional - Comma-separated list of crew member name substrings (e.g., `crew=Johnny`)
-   `genres`: string, optional - Comma-separated list of genres (e.g., `genres=Comedy,Drama`)

## Environment Variables

These variables are loaded via dotenv for local development and should also be added to both your Vercel project settings and your GitHub Action repository secrets for production.

| Secret Name                  | Description                                                            |
| ---------------------------- | ---------------------------------------------------------------------- |
| `DB_URI`                     | MongoDB connection URI                                                 |
| `DB_NAME`                    | MongoDB database name                                                  |
| `DB_USERS_COLLECTION`        | Collection name for user reviews                                       |
| `DB_FILMS_COLLECTION`        | Collection name for film metadata                                      |
| `DB_SUPERLATIVES_COLLECTION` | Collection name for superlatives                                       |
| `DB_MODELS_COLLECTION`       | Collection name for prediction models                                  |
| `LETTERBOXD_USERNAMES`       | Comma-separated list of usernames to scrape                            |
| `LETTERBOXD_GENRES`          | Comma-separated list of genres in LetterBoxd                           |
| `ENV`                        | Environment (`prod` or `dev`)                                          |
| `FRONTEND_URL`               | The URL of your production frontend                                    |
| `PORT`                       | The port to run the API on (default `5000`, do not populate in Vercel) |

---

## Local Development

1. Clone the repo

2. Set up a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the server:

```bash
python -m api.index
```

---

## Deployment (Vercel)

-   Code is located in the `api/` directory as required by Vercel for Python APIs.

-   Add environment variables in the Vercel dashboard.

-   Vercel automatically installs dependencies from `requirements.txt` at the root directory.

---

## Project Structure

```bash
.github/
├── CODEOWNERS		   		# List of codeowners that must approve PR
api/
├── __init__.py
├── index.py           		# Flask app and endpoints
├── config.py          		# Logging and environment loading
├── db.py			   		# Database configuration
├── helpers.py	       		# Helper functions
├── routes/
	├── films.py	   		# Logic for films routes
	├── users.py	   		# Logic for users routes
	├── superlatives.py		# Logic for users routes
.env                   		# Local environment variables (not in repository)
.gitignore
README.md
requirements.txt
vercel.json
```
