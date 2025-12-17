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

Returns a paginated list of scraped film entries according to the query parameters:

```json
{
	"films": [
		{
			"film_id": "34722",
			"film_link": "letterboxd.com/film/inception/",
			"film_title": "Inception",
			"avg_rating": 3.75,
			"stddev_rating": 0.354,
			"like_ratio": 0.25,
			"num_likes": 1,
			"num_ratings": 2,
			"num_watches": 4,
			"reviews": [
				{
					"user": "samuelmgaines",
					"rating": 4,
					"is_liked": false
				},
				{
					"user": "devinbaron",
					"rating": 3.5,
					"is_liked": true
				}
			],
			"watches": [
				{
					"user": "embrune",
					"is_liked": false
				},
				{
					"user": "nkilpatrick",
					"is_liked": false
				}
			],
			"last_metadata_update_time": "Thu, 11 Sep 2025 06:27:09 GMT",
			"metadata": {
				"actors": ["Leonardo DiCaprio"],
				"avg_rating": 4.03,
				"backdrop_url": "https://fake-url.com",
				"crew": [
					{
						"name": "Christopher Nolan",
						"role": "director"
					}
				],
				"description": "A good movie about dreams and stuff",
				"directors": ["Christopher Nolan"],
				"genres": ["Sci-Fi"],
				"runtime": 124,
				"studios": ["Movie Studio"],
				"themes": ["Dreaming"],
				"year": 2015
			}
		}
	],
	"page": 1,
	"per_page": 1,
	"total_pages": 16,
	"total_films": 16
}
```

### `GET /films/{film_id}`

Returns the film entry for the specified `film_id`:

```json
{
	"film_id": "34722",
	"film_title": "Inception",
	"film_link": "https://letterboxd.com/film/inception/",
	"avg_rating": 3.75,
	"stddev_rating": 0.354,
	"like_ratio": 0.25,
	"num_likes": 1,
	"num_ratings": 2,
	"num_watches": 4,
	"reviews": [
		{
			"user": "samuelmgaines",
			"rating": 4,
			"is_liked": false
		},
		{
			"user": "devinbaron",
			"rating": 3.5,
			"is_liked": true
		}
	],
	"watches": [
		{
			"user": "embrune",
			"is_liked": false
		},
		{
			"user": "nkilpatrick",
			"is_liked": false
		}
	],
	"metadata": {
		"actors": ["Leonardo DiCaprio"],
		"avg_rating": 4.03,
		"backdrop_url": "https://fake-url.com",
		"crew": [
			{
				"name": "Christopher Nolan",
				"role": "director"
			}
		],
		"description": "A good movie about dreams and stuff",
		"directors": ["Christopher Nolan"],
		"genres": ["Sci-Fi"],
		"runtime": 124,
		"studios": ["Movie Studio"],
		"themes": ["Dreaming"],
		"year": 2015
	}
}
```

### `GET /users`

Returns all users and their scraped review data:

```json
[
	{
		"username": "samuelmgaines",
		"last_update_time": "Tue, 22 Jul 2025 05:09:48 GMT",
		"stats": {
			"num_watches": 2,
			"num_ratings": 1,
			"avg_rating": 4.5,
			"median_rating": 4.5,
			"mode_rating": 4.5,
			"stdev_rating": 0,
			"rating_distr": {
				"0.5": 0,
				"1.0": 0,
				"1.5": 0,
				"2.0": 0,
				"2.5": 0,
				"3.0": 0,
				"3.5": 0,
				"4.0": 0,
				"4.5": 1,
				"5.0": 0
			},
			"num_likes": 1,
			"like_ratio": 0.5,
			"mean_abs_diff": 0.5,
			"mean_diff": 0.5,
			"pairwise_agreement": {
				"devinbaron": {
					"mean_abs_diff": 0.5,
					"mean_diff": 0.5,
					"num_shared": 1
				}
			},
			"genre_stats": {
				"Horror": {
					"count": 1,
					"percentage": 33.333,
					"avg_rating": 4.5,
					"stddev": null,
					"num_likes": 1,
					"like_ratio": 1
				}
			},
			"avg_runtime": 102.3,
			"total_runtime": 306.9,
			"avg_year_watched": 2012.3
		}
	}
]
```

### `GET /users/{username}`

Returns the user with the specified `username` and their scraped review data.

Query parameters:

-   `include_films`: boolean, optional (default `false`). Determines whether to include `reviews` and `watches` arrays, which can be large.

```json
{
	"username": "samuelmgaines",
	"last_update_time": "Tue, 22 Jul 2025 05:09:48 GMT",
	"reviews": [
		{
			"film_id": "34772",
			"film_title": "Inception",
			"film_link": "https://letterboxd.com/film/inception/",
			"rating": 4.5,
			"is_liked": false
		}
	],
	"watches": [
		{
			"film_id": "51621",
			"film_title": "Good Will Hunting",
			"film_link": "https://letterboxd.com/film/good-will-hunting/",
			"is_liked": true
		}
	],
	"stats": {
		"num_watches": 2,
		"num_ratings": 1,
		"avg_rating": 4.5,
		"median_rating": 4.5,
		"mode_rating": 4.5,
		"stdev_rating": 0,
		"rating_distr": {
			"0.5": 0,
			"1": 0,
			"1.5": 0,
			"2": 0,
			"2.5": 0,
			"3": 0,
			"3.5": 0,
			"4": 0,
			"4.5": 1,
			"5": 0
		},
		"num_likes": 1,
		"like_ratio": 0.5,
		"mean_abs_diff": 0.5,
		"mean_diff": 0.5,
		"pairwise_agreement": {
			"devinbaron": {
				"mean_abs_diff": 0.5,
				"mean_diff": 0.5,
				"num_shared": 1
			}
		},
		"genre_stats": {
			"Horror": {
				"count": 1,
				"percentage": 33.333,
				"avg_rating": 4.5,
				"stddev": null,
				"num_likes": 1,
				"like_ratio": 1
			}
		},
		"avg_runtime": 102.3,
		"total_runtime": 306.9,
		"avg_year_watched": 2012.3
	}
}
```

### `GET /superlatives`

Returns a list of superlatives.

```json
[
	{
		"category": "User Superlatives",
		"superlatives": [
			{
				"description": "User with the highest average rating",
				"first": ["Martendo24680"],
				"first_value": 3.5062380038387717,
				"name": "Positive Polly",
				"second": ["devinbaron"],
				"second_value": 3.4747774480712166,
				"third": ["samuelmgaines"],
				"third_value": 3.4536082474226806
			}
		]
	},
	{
		"category": "Film Superlatives",
		"superlatives": [
			{
				"description": "Film with the highest negative rating difference from Letterboxd average",
				"first": ["La Haine"],
				"first_value": -1.6349999999999998,
				"name": "Most Overrated Movie",
				"second": ["A Minecraft Movie", "Tangled"],
				"second_value": -1.5099999999999998,
				"third": [],
				"third_value": null
			}
		]
	}
]
```

### `GET /predict/{film_id}`

Returns a list of rating and like predictions for each user for the given film.

```json
{
	"film_id": "51816",
	"film_title": "The Godfather Part II",
	"predictions": [
		{
			"already_rated": false,
			"already_watched": false,
			"film_id": "51816",
			"predicted_like": true,
			"predicted_rating": 3.49,
			"username": "samuelmgaines"
		},
		{
			"already_rated": true,
			"already_watched": true,
			"film_id": "51816",
			"predicted_like": true,
			"predicted_rating": 3.5,
			"username": "devinbaron"
		}
	],
	"total_users": 2
}
```

---

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
