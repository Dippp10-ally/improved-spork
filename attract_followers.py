
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

JSON_FILE = Path("potential_followers.json")
TXT_FILE = Path("potential_followers.txt")

# Existing GitHub Actions secrets
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
FOLLOWING_TOKEN5 = os.getenv("FOLLOWING_TOKEN5")

TOKEN = GITHUB_TOKEN or FOLLOWING_TOKEN5

if not TOKEN:
    raise SystemExit("GITHUB_TOKEN or FOLLOWING_TOKEN5 is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Dippp10-ally-discovery"
}

SEARCH_QUERIES = [
    "type:user followers:>5",
    "type:user followers:>10",
    "type:user repos:>2",
    "type:user repos:>5"
]


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
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        print(f"Search API error: HTTP {error.code}")
        print(error.read().decode("utf-8", errors="replace")[:250])
        return {}

    except Exception as error:
        print(f"Search failed: {error}")
        return {}


def load_existing():
    names = set()

    if JSON_FILE.exists():
        try:
            data = json.loads(JSON_FILE.read_text(encoding="utf-8"))

            if isinstance(data, dict):
                data = data.get("usernames", [])

            if isinstance(data, list):
                for item in data:
                    name = item if isinstance(item, str) else (
                        item.get("login", "") if isinstance(item, dict) else ""
                    )
                    if name:
                        names.add(name)

        except (OSError, json.JSONDecodeError):
            print("Existing JSON could not be read.")

    if TXT_FILE.exists():
        names.update(
            line.strip()
            for line in TXT_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    return names


def main():
    discovered = load_existing()

    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")

        for page in (1, 2):
            result = search_users(query, page)

            for user in result.get("items", []):
                login = user.get("login", "").strip()

                if (
                    login
                    and login.lower() != USERNAME.lower()
                    and re.fullmatch(r"[A-Za-z0-9-]{1,39}", login)
                ):
                    discovered.add(login)

    names = sorted(discovered, key=str.lower)

    JSON_FILE.write_text(
        json.dumps({
            "account": USERNAME,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(names),
            "usernames": names
        }, indent=2),
        encoding="utf-8"
    )

    TXT_FILE.write_text(
        "\n".join(names) + ("\n" if names else ""),
        encoding="utf-8"
    )

    print(f"Discovery complete: {len(names)} usernames saved.")
    print("Saved potential_followers.json")
    print("Saved potential_followers.txt")


if __name__ == "__main__":
    main()
