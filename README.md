# Letterboxd API

This is a Flask-based API for scraping and storing [Letterboxd](https://letterboxd.com) user review data. It supports scheduled or manual scraping, stores results in MongoDB, and exposes public film and user data via HTTP endpoints.

Deployed on [Vercel](https://vercel.com), and configurable via environment variables.

---

## Endpoints

### `GET /`

Returns a simple greeting.

### `GET /films`

Returns all scraped film entries:

```json
[
	{
		"film_id": "34722",
		"film_link": "letterboxd.com/film/inception/",
		"film_title": "Inception"
	},
	{
		"film_id": "51621",
		"film_link": "letterboxd.com/film/good-will-hunting/",
		"film_title": "Good Will Hunting"
	}
]
```

### `GET /films/{film_id}`

Returns the film entry for the specified `film_id`:

```json
{
	"film_id": "34722",
	"film_title": "Inception",
	"film_link": "letterboxd.com/film/inception/"
}
```

### `POST /scrape`

Triggers scraping for the usernames defined in the `LETTERBOXD_USERNAMES` environment variable. Results are saved to MongoDB.

### `GET /users`

Returns all users and their scraped review data:

```json
[
	{
		"username": "samuelmgaines",
		"last_update_time": "Tue, 22 Jul 2025 05:09:48 GMT",
		"reviews": {
			"34722": {
				"rating": 4.5,
				"is_liked": false
			}
		},
		"watches": {
			"51621": {
				"is_liked": true
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
	"reviews": {
		"34772": {
			"rating": 4.5,
			"is_liked": false
		}
	},
	"watches": {
		"51621": {
			"is_liked": true
		}
	}
}
```

## Environment Variables

These variables are loaded via dotenv for local development and should also be added to your Vercel project settings for production.

| Secret Name            | Description                                 |
| ---------------------- | ------------------------------------------- |
| `DB_URI`               | MongoDB connection URI                      |
| `DB_NAME`              | MongoDB database name                       |
| `DB_USERS_COLLECTION`  | Collection name for user reviews            |
| `DB_FILMS_COLLECTION`  | Collection name for film metadata           |
| `LETTERBOXD_USERNAMES` | Comma-separated list of usernames to scrape |
| `ENV`                  | Set to `prod` or `dev`                      |

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
python api/index.py
```

## Deployment (Vercel)

-   Code is located in the `api/` directory as required by Vercel for Python APIs.

-   Add environment variables in the Vercel dashboard.

-   Vercel automatically installs dependencies from `requirements.txt` at the root directory.

## Scraping

Scraping is triggered manually via the `POST /scrape` endpoint.

Additionally, this project includes a preconfigured GitHub Actions workflow that automatically triggers the `/scrape` endpoint on a schedule (see `.github/workflows/scrape.yml`). This GitHub Action can also be run manually through the GitHub GUI.

To enable it:

### 1. Fork or clone the repository

If you're setting this up in your own GitHub repo, ensure the `.github/workflows/scrape.yml` file exists.

### 2. Add required secret

Go to **Settings → Secrets and variables → Actions** in your GitHub repo, and add the following secret:

| Secret Name      | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `DEPLOYMENT_URL` | Your deployed app's full URL (e.g. `https://your-app.vercel.app`) |

### 3. Confirm the schedule

The default schedule is defined using cron syntax in the workflow file. For example:

```yaml
schedule:
    - cron: "0 4 * * *" # Runs every day at 4:00 AM UTC
```

## Logging

Logs are handled using Python's `logging` module and will appear in:

-   Your terminal (local dev)
-   Vercel logs (production)

## Project Structure

```bash
.github/
├──workflows/
    ├── scrape.yml     # Scrape scheduler (GitHub Actions)
api/
├── index.py           # Flask app and endpoints
├── scraper.py         # Letterboxd scraping logic
├── config.py          # Logging and environment loading
.env
.gitignore
README.md
requirements.txt
vercel.json
```
