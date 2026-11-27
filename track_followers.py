
import json
import os
import urllib.request
import urllib.error

from datetime import datetime, timezone
from pathlib import Path

# ==============================
# CONFIGURATION
# ==============================

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

TOKEN = os.getenv("FOLLOW_TOKEN")

PER_PAGE = 100
MAX_PAGES_PER_RUN = 1

PROGRESS_PATH = Path("following_progress.json")
HISTORY_PATH = Path("following_history.json")
REPORT_PATH = Path("following_report.md")

if not TOKEN:
    raise SystemExit("FOLLOW_TOKEN is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "improved-spork-tracker",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ==============================
# GITHUB API
# ==============================

def get_json(url):
    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"GitHub API error {error.code}: "
            f"{error.read().decode('utf-8', errors='replace')}"
        ) from error


# ==============================
# PROGRESS MANAGEMENT
# ==============================

def load_progress():

    if PROGRESS_PATH.exists():

        progress = json.loads(
            PROGRESS_PATH.read_text(
                encoding="utf-8"
            )
        )

        return {
            "next_page": max(
                1, int(progress.get("next_page", 1))
            ),
            "users": progress.get("users", []),
            "scan_started": progress.get("scan_started")
        }

    return {
        "next_page": 1,
        "users": [],
        "scan_started": None
    }


def save_progress(progress):

    temporary = PROGRESS_PATH.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(progress, indent=2) + "\n",
        encoding="utf-8"
    )

    temporary.replace(PROGRESS_PATH)


# ==============================
# HISTORY
# ==============================

def load_history():

    if HISTORY_PATH.exists():

        return json.loads(
            HISTORY_PATH.read_text(
                encoding="utf-8"
            )
        )

    return []


# ==============================
# COMPLETE SCAN
# ==============================

def finish_scan(users):

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    users = sorted(
        set(users),
        key=str.lower
    )

    history = load_history()

    previous = history[-1] if history else None

    previous_users = (
        set(previous.get("users", []))
        if previous else set()
    )

    new_users = sorted(
        set(users) - previous_users,
        key=str.lower
    )

    removed_users = sorted(
        previous_users - set(users),
        key=str.lower
    )

    history = [
        item for item in history
        if item.get("date") != today
    ]

    history.append({
        "date": today,
        "count": len(users),
        "users": users
    })

    history = history[-365:]

    HISTORY_PATH.write_text(
        json.dumps(history, indent=2) + "\n",
        encoding="utf-8"
    )

    report = [
        "# GitHub Following Report",
        "",
        f"Account: {USERNAME}",
        f"Date UTC: {today}",
        f"Following now: {len(users)}",
        f"New following: {len(new_users)}",
        f"Removed following: {len(removed_users)}",
        "",
        "## Newly followed",
        *[f"- {u}" for u in new_users],
        "",
        "## Removed from following",
        *[f"- {u}" for u in removed_users],
        "",
        "## Current following",
        *[f"- {u}" for u in users]
    ]

    REPORT_PATH.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print("FOLLOWING SCAN COMPLETED")
    print(f"Total following: {len(users)}")
    print(f"New following: {len(new_users)}")
    print(f"Removed following: {len(removed_users)}")


# ==============================
# MAIN PAGINATION
# ==============================

def main():

    progress = load_progress()

    page = progress["next_page"]

    users = set(progress["users"])

    if not progress["scan_started"]:

        progress["scan_started"] = (
            datetime.now(timezone.utc).isoformat()
        )

    print("=" * 45)
    print("CONTINUOUS FOLLOWING TRACKER")
    print("=" * 45)

    print(f"Starting page: {page}")
    print(f"Previously collected: {len(users)}")

    pages_processed = 0
    scan_complete = False

    while pages_processed < MAX_PAGES_PER_RUN:

        url = (
            f"{API}/users/{USERNAME}/following"
            f"?per_page={PER_PAGE}&page={page}"
        )

        print(f"Requesting page {page}")

        batch = get_json(url)

        if not isinstance(batch, list):
            raise RuntimeError(
                "Unexpected GitHub API response."
            )

        if not batch:

            scan_complete = True
            break

        page_users = {
            user["login"]
            for user in batch
            if user.get("login")
        }

        users.update(page_users)

        print(f"Page {page} returned: {len(batch)}")
        print(f"Unique collected: {len(users)}")

        pages_processed += 1

        if len(batch) < PER_PAGE:

            scan_complete = True
            break

        page += 1

    if scan_complete:

        finish_scan(users)

        # Reset only after the entire scan is complete.
        save_progress({
            "next_page": 1,
            "users": [],
            "scan_started": None
        })

        print("Scan completed.")
        print("Next full scan starts at page 1.")

    else:

        progress["next_page"] = page + 1

        progress["users"] = sorted(
            users,
            key=str.lower
        )

        save_progress(progress)

        print("Progress saved successfully.")
        print(f"Next page: {progress['next_page']}")
        print(f"Collected usernames: {len(users)}")

    print("=" * 45)


if __name__ == "__main__":
    main()
