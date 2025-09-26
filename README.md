# Letterboxd API

This is a Flask-based API for scraping and storing [Letterboxd](https://letterboxd.com) user review data. It supports scheduled and manual scraping, stores results in MongoDB, and exposes public film and user data via HTTP endpoints.

Deployed on [Vercel](https://vercel.com), and configurable via environment variables.

---

## Endpoints

### `GET /`

Returns a simple greeting.

### `GET /films`

Query Parameters:

-   `page`: integer, optional (defualt `1`).
-   `limit`: integer, optional (default `20`). Number of films per page.
-   `sort_by`: string, optional (default `film_title`). Name of the field to sort by.
-   `sort_order`: string, optional (default `asc` for string fields and `desc` for numerical fields). Order to sort the results (`asc` for ascending, `desc` for descending).
-   `{field_name}_gte`: number, optional. Filters results by field greater than or equal to value.
-   `{field_name}_lte`: number, optional. Filters results by field less than or equal to value.
-   `watched_by`: string, optional. Comma-separated list of usernames. Filters results to only those containing each specified user in either `reviews` or `watches`.
-   `not_watched_by`: string, optional. Comma-separated list of usernames. Filters results to only those containing none of the specified users in `reviews` and `watches`.
-   `rated_by`: string, optional. Comma-separated list of usernames. Filters results to only those containing each specified user in `reviews`.
-   `not_rated_by`: string, optional. Comma-separated list of usernames. Filters results to only those containing none of the specified users in `reviews`.

Returns a paginated list of scraped film entries according to the query parameters:

```json
{
	"films": [
		{
			"film_id": "34722",
			"film_link": "letterboxd.com/film/inception/",
			"film_title": "Inception",
			"avg_rating": 3.75,
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

Query parameters:

-   `include_films`: boolean, optional (default `false`). Determines whether to include `reviews` and `watches` arrays, which can be large.

```json
{
	"film_id": "34722",
	"film_title": "Inception",
	"film_link": "https://letterboxd.com/film/inception/",
	"avg_rating": 3.75,
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
			}
		}
	}
]
```

### `GET /users/{username}`

Returns the user with the specified `username` and their scraped review data:

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
		}
	}
}
```

---

## Environment Variables

These variables are loaded via dotenv for local development and should also be added to both your Vercel project settings and your GitHub Action repository secrets for production.

| Secret Name            | Description                                 |
| ---------------------- | ------------------------------------------- |
| `DB_URI`               | MongoDB connection URI                      |
| `DB_NAME`              | MongoDB database name                       |
| `DB_USERS_COLLECTION`  | Collection name for user reviews            |
| `DB_FILMS_COLLECTION`  | Collection name for film metadata           |
| `LETTERBOXD_USERNAMES` | Comma-separated list of usernames to scrape |
| `ENV`                  | Set to `prod` or `dev`                      |
| `FRONTEND_URL`         | The URL of your production frontend         |

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

## Scraping and Stats

This project includes a preconfigured GitHub Actions workflow that automatically triggers the scraper and computes stats on a schedule (see `.github/workflows/scrape.yml`). This GitHub Action can also be triggered manually through the GitHub GUI. If you're setting this up in your own GitHub repo, ensure your GitHub repository secrets are configured.

The schedule is defined using cron syntax in the workflow file:

```yaml
schedule:
    - cron: "0 8 * * *" # runs every day at 8:00 AM UTC (2:00 AM CST / 3:00 AM CDT)
```

There is a separate preconfigured GitHub Actions workflow that triggers only a computation of the stats (see `.github/workflows/stats.yml`). This action is triggered manually through the GitHub GUI.

---

## Logging

Logs are handled using Python's `logging` module and will appear in:

-   Your terminal (local dev)
-   Vercel logs (production)

---

## Project Structure

```bash
.github/
├──workflows/
    ├── scrape.yml     # Scrape action configuration
	├── stats.yml	   # Compute stats action configuration
api/
├── __init__.py
├── index.py           # Flask app and endpoints
├── config.py          # Logging and environment loading
├── db.py			   # Database configuration
├── helpers.py	       # Helper functions
├── routes/
	├── films.py	   # Logic for films routes
	├── users.py	   # Logic for users routes
.env                   # Local environment variables (not in repository)
.gitignore
README.md
requirements.txt
scraper.py             # Scraping functionality
stats.py			   # Stats computation
vercel.json
```
