
import json
import os
import re
import sqlite3
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

USERNAME = "Dippp10-ally"
API = "https://api.github.com"
FOLLOW_TOKEN = os.getenv("FOLLOW_TOKEN")

if not FOLLOW_TOKEN:
    raise SystemExit("FOLLOW_TOKEN is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {FOLLOW_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Dippp10-ally-review"
}

DB_FILE = Path("approved_review.sqlite")
RESULT_FILE = Path("follow_results.json")
REVIEW_FILE = Path("users_to_review.txt")
MAX_REVIEW = 1000


def api_get(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        import json as json_module
        return json_module.loads(response.read().decode("utf-8"))


def load_following():
    following = set()
    page = 1

    while True:
        url = (
            f"{API}/users/{USERNAME}/following"
            f"?per_page=100&page={page}"
        )
        data = api_get(url)

        if not isinstance(data, list):
            raise RuntimeError("Could not retrieve following list.")

        if not data:
            break

        for user in data:
            login = user.get("login")
            if login:
                following.add(login.lower())

        page += 1

    return following


def main():
    if DB_FILE.exists():
        DB_FILE.unlink()

    connection = sqlite3.connect(DB_FILE)
    connection.execute(
        "CREATE TABLE approved (login TEXT PRIMARY KEY)"
    )

    raw_count = 0

    for number in range(1, 14):
        path = Path(f"approved_users_part_{number}.txt")

        if not path.exists():
            print(f"Missing file: {path}")
            continue

        with path.open(encoding="utf-8", errors="ignore") as file:
            for line in file:
                name = line.strip()

                if (
                    name
                    and not name.startswith("#")
                    and re.fullmatch(r"[A-Za-z0-9-]{1,39}", name)
                    and name.lower() != USERNAME.lower()
                ):
                    raw_count += 1
                    connection.execute(
                        "INSERT OR IGNORE INTO approved(login) VALUES (?)",
                        (name,)
                    )

        connection.commit()
        print(f"Processed {path}")

    approved_count = connection.execute(
        "SELECT COUNT(*) FROM approved"
    ).fetchone()[0]

    following = load_following()

    already_count = 0
    review_count = 0
    sample = []

    cursor = connection.execute(
        "SELECT login FROM approved ORDER BY login COLLATE NOCASE"
    )

    for (name,) in cursor:
        if name.lower() in following:
            already_count += 1
        else:
            review_count += 1
            if len(sample) < MAX_REVIEW:
                sample.append(name)

    report = {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "approved_lines_processed": raw_count,
        "unique_approved_users": approved_count,
        "already_following": already_count,
        "not_yet_following": review_count,
        "review_sample_limit": MAX_REVIEW,
        "review_sample": sample
    }

    RESULT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    REVIEW_FILE.write_text(
        "# First 1000 accounts for manual review\n"
        + "\n".join(
            f"{name} - https://github.com/{name}"
            for name in sample
        )
        + "\n",
        encoding="utf-8"
    )

    connection.close()
    DB_FILE.unlink(missing_ok=True)

    print(f"Unique approved accounts: {approved_count}")
    print(f"Already following: {already_count}")
    print(f"Not yet following: {review_count}")
    print(f"Review sample saved: {len(sample)}")


if __name__ == "__main__":
    main()
