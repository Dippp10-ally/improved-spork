
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "Dippp10-ally"
API = "https://api.github.com"
TOKEN = os.getenv("FOLLOW_TOKEN")

if not TOKEN:
    raise SystemExit("FOLLOW_TOKEN is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "improved-spork-tracker",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get_json(url):
    request = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"GitHub API error {error.code}: "
            f"{error.read().decode('utf-8', errors='replace')}"
        ) from error


def get_following():
    users = []
    page = 1

    while True:
        batch = get_json(
            f"{API}/users/{USERNAME}/following"
            f"?per_page=100&page={page}"
        )

        if not batch:
            break

        users.extend(
            user["login"] for user in batch if user.get("login")
        )

        if len(batch) < 100:
            break

        page += 1

    return sorted(set(users), key=str.lower)


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    following = get_following()

    history_path = Path("following_history.json")

    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = []

    previous = history[-1] if history else None
    previous_users = set(previous.get("users", [])) if previous else set()

    new_users = sorted(set(following) - previous_users)
    removed_users = sorted(previous_users - set(following))

    history = [
        item for item in history
        if item.get("date") != today
    ]

    history.append({
        "date": today,
        "count": len(following),
        "users": following
    })

    history = history[-365:]

    history_path.write_text(
        json.dumps(history, indent=2) + "\n",
        encoding="utf-8"
    )

    report = [
        "# GitHub Following Report",
        "",
        f"Account: {USERNAME}",
        f"Date UTC: {today}",
        f"Following now: {len(following)}",
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
        *[f"- {u}" for u in following],
    ]

    Path("following_report.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print("\nDAILY FOLLOWING REPORT")
    print("=" * 40)
    print(f"Following now: {len(following)}")
    print(f"New following: {len(new_users)}")
    print(f"Removed following: {len(removed_users)}")


if __name__ == "__main__":
    main()
