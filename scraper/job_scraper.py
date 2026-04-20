"""
Job Scraper — Monitors company career pages for new job postings.

Uses the Greenhouse Job Board API to fetch job listings for configured
companies.  When a new matching job is detected (by title keyword AND
San Francisco location), an email alert is sent via Gmail SMTP.
Seen job IDs are persisted in a JSON file to avoid duplicate notifications.

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
    # ─── Frontier AI Labs ──────────────────────────────────────────
    {
        "name": "Anthropic",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs",
    },
    {
        "name": "DeepMind",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/deepmind/jobs",
    },
    # ─── AI-Native Startups ────────────────────────────────────────
    {
        "name": "Scale AI",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/scaleai/jobs",
    },
    {
        "name": "Together AI",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/togetherai/jobs",
    },
    {
        "name": "Databricks",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/databricks/jobs",
    },
    {
        "name": "Figma",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/figma/jobs",
    },
    {
        "name": "Vercel",
        "api_url": "https://boards-api.greenhouse.io/v1/boards/vercel/jobs",
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_jobs(api_url: str) -> list[dict]:
    """Fetch all jobs from a Greenhouse Job Board API endpoint."""
    req = Request(api_url, headers={"User-Agent": "JobScraper/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("jobs", [])
    except (URLError, HTTPError) as exc:
        print(f"  ⚠  Error fetching {api_url}: {exc}")
        return []


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
    if not published_str or published_str == "N/A":
        return True  # If no date, include it to be safe
    try:
        # Greenhouse dates look like: "2026-04-15T16:57:11-04:00"
        pub_date = datetime.fromisoformat(published_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_JOB_AGE_DAYS)
        return pub_date >= cutoff
    except (ValueError, TypeError):
        return True  # Include if we can't parse


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
    sender = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("NOTIFY_EMAIL", sender)

    if not sender or not password:
        print("  ⚠  GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping email.")
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
    print("=" * 60)

    seen = load_seen_jobs()
    all_new_jobs: list[dict] = []

    for company in COMPANIES:
        name = company["name"]
        print(f"\n🔍  Scanning {name}...")
        jobs = fetch_jobs(company["api_url"])
        print(f"  → Found {len(jobs)} total listings")

        # Filter pipeline: title → location → recency
        title_matches = [j for j in jobs if matches_title(j.get("title", ""))]
        print(f"  → {len(title_matches)} match target title keywords")

        loc_matches = [
            j for j in title_matches
            if matches_location(j.get("location", {}).get("name", ""))
        ]
        print(f"  → {len(loc_matches)} in San Francisco")

        recent_matches = [
            j for j in loc_matches
            if is_recent(j.get("first_published", ""))
        ]
        print(f"  → {len(recent_matches)} posted within last {MAX_JOB_AGE_DAYS} days")

        company_seen = seen.get(name, [])

        for job in recent_matches:
            job_id = str(job["id"])
            if job_id not in company_seen:
                new_job = {
                    "company": name,
                    "title": job["title"].strip(),
                    "location": job.get("location", {}).get("name", "N/A"),
                    "url": job.get("absolute_url", ""),
                    "published": job.get("first_published", "N/A"),
                    "id": job_id,
                }
                all_new_jobs.append(new_job)
                company_seen.append(job_id)
                print(f"  🆕  NEW: {new_job['title']} ({new_job['location']})")

        seen[name] = company_seen

    # Persist updated seen-list
    save_seen_jobs(seen)

    # Send notification if we found new jobs
    if all_new_jobs:
        print(f"\n📬  {len(all_new_jobs)} new job(s) found — sending email...")
        subject = f"🔔 {len(all_new_jobs)} New Job Alert(s) — Job Scraper"
        body = build_email_body(all_new_jobs)
        send_email(subject, body)
    else:
        print("\n✅  No new matching jobs found this run.")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
