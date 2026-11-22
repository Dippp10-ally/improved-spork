
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "Dippp10-ally"
TOKEN = os.getenv("GITHUB_TOKEN")

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "improved-spork-follower-tracker"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_followers():
    users = []
    page = 1

    while True:
        url = (
            f"{API}/users/{USERNAME}/followers"
            f"?per_page=100&page={page}"
        )

        request = urllib.request.Request(url, headers=HEADERS)

        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.loads(response.read().decode("utf-8"))

        if not batch:
            break

        users.extend(
            item["login"] for item in batch if item.get("login")
        )

        if len(batch) < 100:
            break

        page += 1

    return sorted(set(users), key=str.lower)


def main():
    followers = get_followers()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    history_path = Path("follower_history.json")

    if history_path.exists():
        try:
            history = json.loads(history_path.read_text())
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []
    else:
        history = []

    previous_count = history[-1].get("count", 0) if history else 0

    history.append({
        "date": today,
        "count": len(followers)
    })

    # Keep only the latest 365 daily records.
    history = history[-365:]

    history_path.write_text(
        json.dumps(history, indent=2) + "\n",
        encoding="utf-8"
    )

    report = [
        "# GitHub Follower Report",
        "",
        f"- Account: {USERNAME}",
        f"- Date (UTC): {today}",
        f"- Current followers: {len(followers)}",
        f"- Change since previous recorded run: "
        f"{len(followers) - previous_count:+d}",
        "",
        "## Latest follower usernames",
        ""
    ]

    report.extend(f"- {name}" for name in followers[:1000])

    Path("follower_report.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print(f"Current followers: {len(followers)}")
    print(f"Previous recorded count: {previous_count}")
    print(f"Report updated for {USERNAME}")


if __name__ == "__main__":
    main()
