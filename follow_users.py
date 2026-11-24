
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
    "User-Agent": "Dippp10-ally"
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
        raise


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
            raise RuntimeError("Invalid following response")

        if not data:
            break

        for user in data:
            login = user.get("login")
            if login:
                following.add(login.lower())

        page += 1

    return following


def main():
    approved = set()

    for number in range(1, 14):
        path = Path(f"approved_users_part_{number}.txt")

        if not path.exists():
            print(f"Missing: {path}")
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
                    approved.add(name)

    following = load_following()

    review = sorted(
        (name for name in approved
         if name.lower() not in following),
        key=str.lower
    )

    report = {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "unique_approved_users": len(approved),
        "already_following": len(approved) - len(review),
        "not_yet_following": len(review),
        "current_following_count": len(following),
        "review_sample": review[:1000]
    }

    RESULT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    REVIEW_FILE.write_text(
        "# Accounts available for manual review\n"
        + "\n".join(
            f"https://github.com/{name}" for name in review[:1000]
        ) + "\n",
        encoding="utf-8"
    )

    print("Approved:", len(approved))
    print("Already following:", len(approved) - len(review))
    print("Not yet following:", len(review))
    print("Current following:", len(following))


if __name__ == "__main__":
    main()
