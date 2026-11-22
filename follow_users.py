
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

TOKEN = os.getenv("FOLLOW_TOKEN")

if not TOKEN:
    raise SystemExit("FOLLOW_TOKEN is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Dippp10-ally-approved-review"
}

RESULT_FILE = Path("follow_results.json")
REVIEW_FILE = Path("users_to_review.txt")


def api_get(url):
    request = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        print(f"GitHub API error: HTTP {error.code}")
        print(error.read().decode("utf-8", errors="replace")[:250])
        return None

    except Exception as error:
        print(f"Request failed: {error}")
        return None


def load_approved_users():
    users = set()

    for number in range(1, 14):
        path = Path(f"approved_users_part_{number}.txt")

        if not path.exists():
            print(f"Missing: {path}")
            continue

        with path.open(encoding="utf-8") as file:
            for line in file:
                name = line.strip()

                if (
                    name
                    and not name.startswith("#")
                    and re.fullmatch(r"[A-Za-z0-9-]{1,39}", name)
                    and name.lower() != USERNAME.lower()
                ):
                    users.add(name)

    return sorted(users, key=str.lower)


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
            raise SystemExit("Could not retrieve following list.")

        if not data:
            break

        for user in data:
            if user.get("login"):
                following.add(user["login"].lower())

        page += 1

    return following


def main():
    approved = load_approved_users()
    following = load_following()

    already_following = [
        name for name in approved if name.lower() in following
    ]

    to_review = [
        name for name in approved if name.lower() not in following
    ]

    report = {
        "account": USERNAME,
        "date": datetime.now(timezone.utc).isoformat(),
        "approved_count": len(approved),
        "already_following_count": len(already_following),
        "review_count": len(to_review),
        "already_following": already_following,
        "users_to_review": to_review
    }

    RESULT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    lines = [
        "# Review these approved GitHub accounts before following",
        ""
    ]

    lines.extend(
        f"{name} - https://github.com/{name}"
        for name in to_review
    )

    REVIEW_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print(f"Approved accounts: {len(approved)}")
    print(f"Already following: {len(already_following)}")
    print(f"Ready for review: {len(to_review)}")
    print("Saved follow_results.json")
    print("Saved users_to_review.txt")


if __name__ == "__main__":
    main()
