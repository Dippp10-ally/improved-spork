
import json
import os
import re
import urllib.request
import urllib.error
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime, timezone

USERNAME = "Dippp10-ally"
API = "https://api.github.com"
TOKEN = os.getenv("FOLLOWING_TOKEN5")

if not TOKEN:
    raise SystemExit("FOLLOWING_TOKEN5 is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Dippp10-ally-discovery"
}

QUERIES = [
    "type:user followers:>5",
    "type:user followers:>10",
    "type:user repos:>2",
    "type:user repos:>5"
]

MAX_SAVED = 1000


def search_users(query, page):
    params = urlencode({
        "q": query,
        "per_page": 100,
        "page": page
    })

    request = urllib.request.Request(
        f"{API}/search/users?{params}",
        headers=HEADERS
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        print(f"GitHub search HTTP error: {error.code}")
        raise


def main():
    discovered = set()

    for query in QUERIES:
        print(f"Searching: {query}")

        for page in (1, 2):
            try:
                result = search_users(query, page)

            except Exception as error:
                print(f"Search failed: {error}")
                continue

            for user in result.get("items", []):
                login = user.get("login", "").strip()

                if (
                    login
                    and login.lower() != USERNAME.lower()
                    and re.fullmatch(
                        r"[A-Za-z0-9-]{1,39}", login
                    )
                ):
                    discovered.add(login)

                if len(discovered) >= MAX_SAVED:
                    break

            if len(discovered) >= MAX_SAVED:
                break

    names = sorted(discovered, key=str.lower)[:MAX_SAVED]

    data = {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "saved_count": len(names),
        "maximum_saved": MAX_SAVED,
        "usernames": names
    }

    Path("potential_followers.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

    Path("potential_followers.txt").write_text(
        "\n".join(names) + ("\n" if names else ""),
        encoding="utf-8"
    )

    print(f"Saved {len(names)} discovered usernames.")


if __name__ == "__main__":
    main()
