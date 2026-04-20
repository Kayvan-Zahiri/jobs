"""
Job Scraper — Monitors company career pages for new job postings.

Supports two ATS platforms:
  • Greenhouse (boards-api.greenhouse.io)
  • Ashby (api.ashbyhq.com)

Filters by title keywords, San Francisco location, and recency.
Sends email alerts via Gmail SMTP when new matching jobs are found.

Usage:
    python scraper/job_scraper.py

Environment Variables (set via GitHub Secrets):
    GMAIL_USER          - Gmail address to send from
    GMAIL_APP_PASSWORD  - Gmail App Password (16-char, no spaces)
    NOTIFY_EMAIL        - (optional) Recipient email; defaults to GMAIL_USER
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# ── Configuration ──────────────────────────────────────────────────────────────

COMPANIES = [
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  HIGH MATCH — Skills directly map to the company's stack
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        # You literally work with LiveKit right now at Anoten
        "name": "LiveKit",
        "platform": "ashby",
        "slug": "livekit",
    },
    {
        # Voice AI — your current domain
        "name": "ElevenLabs",
        "platform": "ashby",
        "slug": "elevenlabs",
    },
    {
        # Voice AI agents platform
        "name": "Vapi",
        "platform": "ashby",
        "slug": "Vapi",
    },
    {
        # LLM tooling, RAG — you've built RAG apps
        "name": "LangChain",
        "platform": "ashby",
        "slug": "langchain",
    },
    {
        # You have Dagster experience from Spaly Labs
        "name": "Dagster Labs",
        "platform": "greenhouse",
        "slug": "dagsterlabs",
    },
    {
        # ETL pipelines — you built pipelines with dlt/dbt
        "name": "Fivetran",
        "platform": "greenhouse",
        "slug": "fivetran",
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  STRONG MATCH — AI-native startups, good pay, right level
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        # Vector DB / RAG infrastructure
        "name": "Pinecone",
        "platform": "ashby",
        "slug": "pinecone",
    },
    {
        # Serverless ML compute — Python-heavy
        "name": "Modal",
        "platform": "ashby",
        "slug": "modal",
    },
    {
        # AI code editor — GenAI product
        "name": "Cursor",
        "platform": "ashby",
        "slug": "cursor",
    },
    {
        # AI coding / GenAI platform
        "name": "Replit",
        "platform": "ashby",
        "slug": "Replit",
    },
    {
        # Data labeling + AI infra — directly relevant
        "name": "Scale AI",
        "platform": "greenhouse",
        "slug": "scaleai",
    },
    {
        # AI training infrastructure
        "name": "Together AI",
        "platform": "greenhouse",
        "slug": "togetherai",
    },
    {
        # Distributed ML, Ray — you have distributed computing exp
        "name": "Anyscale",
        "platform": "ashby",
        "slug": "anyscale",
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  REACH — Frontier labs (worth monitoring, more competitive)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "Anthropic",
        "platform": "greenhouse",
        "slug": "anthropic",
    },
    {
        "name": "Perplexity",
        "platform": "ashby",
        "slug": "Perplexity",
    },
    {
        # Data + AI platform
        "name": "Databricks",
        "platform": "greenhouse",
        "slug": "databricks",
    },
]

# Keywords to match in job titles (case-insensitive).
# A job matches if ANY keyword appears in its title.
TARGET_TITLE_KEYWORDS = [
    "software engineer",
    "ai engineer",
    "machine learning engineer",
    "ml engineer",
    "data engineer",
    "data scientist",
    "applied scientist",
    "research engineer",
]

# Location filter — only include jobs mentioning San Francisco.
LOCATION_KEYWORDS = [
    "san francisco",
    "sf",
]

# Only alert on jobs published within the last N days.
MAX_JOB_AGE_DAYS = 14

# File that persists which job IDs we've already seen.
SEEN_JOBS_FILE = Path(__file__).resolve().parent / "seen_jobs.json"


# ── Platform-specific fetchers ─────────────────────────────────────────────────

def _http_get_json(url: str) -> dict | list | None:
    """Helper: GET a URL, return parsed JSON or None on error."""
    req = Request(url, headers={"User-Agent": "JobScraper/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError) as exc:
        print(f"  ⚠  Error fetching {url}: {exc}")
        return None


def fetch_greenhouse(slug: str) -> list[dict]:
    """Fetch jobs from Greenhouse and normalize to common format."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    data = _http_get_json(url)
    if not data:
        return []

    normalized = []
    for job in data.get("jobs", []):
        normalized.append({
            "id": str(job["id"]),
            "title": job.get("title", "").strip(),
            "location": job.get("location", {}).get("name", ""),
            "url": job.get("absolute_url", ""),
            "published": job.get("first_published", ""),
        })
    return normalized


def fetch_ashby(slug: str) -> list[dict]:
    """Fetch jobs from Ashby and normalize to common format."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    data = _http_get_json(url)
    if not data:
        return []

    normalized = []
    for job in data.get("jobs", []):
        # Build location string from primary + secondary locations
        locations = []
        if job.get("location"):
            locations.append(job["location"])
        for sec in job.get("secondaryLocations", []):
            if isinstance(sec, str):
                locations.append(sec)

        normalized.append({
            "id": str(job["id"]),
            "title": job.get("title", "").strip(),
            "location": " | ".join(locations) if locations else "",
            "url": job.get("jobUrl", ""),
            "published": job.get("publishedAt", ""),
        })
    return normalized


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "ashby": fetch_ashby,
}


# ── Filtering ──────────────────────────────────────────────────────────────────

def matches_title(title: str) -> bool:
    """Return True if the job title contains any target keyword."""
    title_lower = title.lower().strip()
    return any(kw in title_lower for kw in TARGET_TITLE_KEYWORDS)


def matches_location(location_name: str) -> bool:
    """Return True if the location mentions San Francisco."""
    loc_lower = location_name.lower()
    return any(kw in loc_lower for kw in LOCATION_KEYWORDS)


def is_recent(published_str: str) -> bool:
    """Return True if the job was published within MAX_JOB_AGE_DAYS."""
    if not published_str:
        return True  # If no date, include it to be safe
    try:
        pub_date = datetime.fromisoformat(published_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_JOB_AGE_DAYS)
        return pub_date >= cutoff
    except (ValueError, TypeError):
        return True  # Include if we can't parse


# ── State persistence ──────────────────────────────────────────────────────────

def load_seen_jobs() -> dict:
    """Load previously seen job IDs from disk."""
    if SEEN_JOBS_FILE.exists():
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen_jobs(seen: dict) -> None:
    """Persist seen job IDs to disk."""
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen, f, indent=2)


# ── Email ──────────────────────────────────────────────────────────────────────

def build_email_body(new_jobs: list[dict]) -> str:
    """Compose a nicely-formatted email body for new job alerts."""
    lines = [
        "🚀 New Job Postings Found!\n",
        f"Scan time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n",
        f"Total new matches: {len(new_jobs)}\n",
        "─" * 60,
    ]
    for job in new_jobs:
        lines.append(f"\n🏢  {job['company']}")
        lines.append(f"📋  {job['title']}")
        lines.append(f"📍  {job['location']}")
        lines.append(f"🔗  {job['url']}")
        lines.append(f"📅  Published: {job['published']}")
        lines.append("─" * 60)

    lines.append("\n— Sent by your Job Scraper bot 🤖")
    return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    """Send an email via Gmail SMTP using environment credentials."""
    sender = (os.environ.get("GMAIL_USER") or "").strip()
    password = (os.environ.get("GMAIL_APP_PASSWORD") or "").strip()
    recipient = (os.environ.get("NOTIFY_EMAIL") or sender).strip()

    if not sender or not password:
        print("  ⚠  GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping email.")
        return
    if not recipient:
        print("  ⚠  NOTIFY_EMAIL resolved empty — skipping email.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print(f"  ✅  Email sent to {recipient}")
    except Exception as exc:
        print(f"  ❌  Failed to send email: {exc}")
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Job Scraper — Starting scan")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Location filter: San Francisco")
    print(f"  Max job age: {MAX_JOB_AGE_DAYS} days")
    print(f"  Companies: {len(COMPANIES)}")
    print("=" * 60)

    seen = load_seen_jobs()
    all_new_jobs: list[dict] = []

    for company in COMPANIES:
        name = company["name"]
        platform = company["platform"]
        slug = company["slug"]
        fetcher = FETCHERS[platform]

        print(f"\n🔍  Scanning {name} ({platform})...")
        jobs = fetcher(slug)
        print(f"  → {len(jobs)} total listings")

        # Filter pipeline: title → location → recency
        title_matches = [j for j in jobs if matches_title(j["title"])]
        print(f"  → {len(title_matches)} match target title keywords")

        loc_matches = [j for j in title_matches if matches_location(j["location"])]
        print(f"  → {len(loc_matches)} in San Francisco")

        recent_matches = [j for j in loc_matches if is_recent(j["published"])]
        print(f"  → {len(recent_matches)} posted within last {MAX_JOB_AGE_DAYS} days")

        company_seen = seen.get(name, [])

        for job in recent_matches:
            job_id = job["id"]
            if job_id not in company_seen:
                job["company"] = name
                all_new_jobs.append(job)
                company_seen.append(job_id)
                print(f"  🆕  NEW: {job['title']} ({job['location']})")

        seen[name] = company_seen

    # Send notification if we found new jobs (before persisting, so a failed
    # send doesn't silently mark jobs as seen).
    if all_new_jobs:
        print(f"\n📬  {len(all_new_jobs)} new job(s) found — sending email...")
        subject = f"🔔 {len(all_new_jobs)} New Job Alert(s) — Job Scraper"
        body = build_email_body(all_new_jobs)
        send_email(subject, body)
    else:
        print("\n✅  No new matching jobs found this run.")

    # Persist updated seen-list only after a successful email (or no-op).
    save_seen_jobs(seen)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
