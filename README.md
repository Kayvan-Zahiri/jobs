# Job Scraper 🔍

Automated job alert system that monitors career pages at top AI companies and emails you when new matching jobs are posted in **San Francisco**.

## Companies Tracked

| Company      | Type               | Career Board                                              |
|--------------|--------------------|------------------------------------------------------------|
| Anthropic    | Frontier AI Lab    | [Greenhouse](https://boards.greenhouse.io/anthropic)       |
| DeepMind     | Frontier AI Lab    | [Greenhouse](https://boards.greenhouse.io/deepmind)        |
| Scale AI     | AI-Native Startup  | [Greenhouse](https://boards.greenhouse.io/scaleai)         |
| Together AI  | AI-Native Startup  | [Greenhouse](https://boards.greenhouse.io/togetherai)      |
| Databricks   | AI / Data Platform | [Greenhouse](https://boards.greenhouse.io/databricks)      |
| Figma        | Tech Startup       | [Greenhouse](https://boards.greenhouse.io/figma)           |
| Vercel       | Tech Startup       | [Greenhouse](https://boards.greenhouse.io/vercel)          |

## Target Roles

The scraper matches listings whose titles contain (case-insensitive):

- `software engineer`
- `ai engineer`
- `machine learning engineer` / `ml engineer`
- `data engineer`
- `data scientist`
- `applied scientist`
- `research engineer`

## Filters

| Filter      | Value                          |
|-------------|--------------------------------|
| **Location**| San Francisco only             |
| **Recency** | Posted within the last 14 days |

## How It Works

1. **Scraper** hits the public Greenhouse JSON API for each company
2. Filters jobs by **title keyword** → **SF location** → **recency**
3. Compares against `seen_jobs.json` to detect **new** postings only
4. Sends an email alert via Gmail SMTP for any new matches
5. Commits the updated `seen_jobs.json` back to the repo

## Schedule

Runs **4× per day** via GitHub Actions:

| Run | UTC Time | PST Time  |
|-----|----------|-----------|
| 1   | 00:00    | 5:00 PM   |
| 2   | 06:00    | 11:00 PM  |
| 3   | 12:00    | 5:00 AM   |
| 4   | 18:00    | 11:00 AM  |

You can also trigger it manually from the **Actions** tab → **Job Scraper — Daily Alerts** → **Run workflow**.

## Setup — GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** and add:

| Secret               | Description                                                               |
|----------------------|---------------------------------------------------------------------------|
| `GMAIL_USER`         | Your Gmail address (e.g. `you@gmail.com`)                                 |
| `GMAIL_APP_PASSWORD` | 16-character Gmail App Password ([generate here](https://myaccount.google.com/apppasswords)) |
| `NOTIFY_EMAIL`       | *(optional)* Recipient email — defaults to `GMAIL_USER`                   |

> **Important:** You must have **2-Step Verification** enabled on your Google account to generate an App Password.

## Adding More Companies

Edit `COMPANIES` in `scraper/job_scraper.py`. Any company using Greenhouse can be added with:

```python
{
    "name": "Company Name",
    "api_url": "https://boards-api.greenhouse.io/v1/boards/<slug>/jobs",
}
```

Find a company's slug by visiting their Greenhouse careers page URL.

## Local Testing

```bash
# Set credentials (optional — scraper runs fine without, just skips email)
export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"

# Run
python scraper/job_scraper.py
```
