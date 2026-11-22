
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

JSON_FILE = Path("potential_followers.json")
TXT_FILE = Path("potential_followers.txt")

SEARCH_QUERIES = [
    "type:user followers:>5",
    "type:user repos:>2",
    "type:user followers:>10",
    "type:user repos:>5"
]

TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Dippp10-ally-developer-discovery"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def search_users(query, page):
    from urllib.parse import urlencode

    params = urlencode({
        "q": query,
        "per_page": 100,
        "page": page
    })

    url = f"{API}/search/users?{params}"

    request = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        print(f"Search error {error.code}: {message[:250]}")
        return {}

    except Exception as error:
        print(f"Request failed: {error}")
        return {}


def load_existing():
    names = set()

    if JSON_FILE.exists():
        try:
            data = json.loads(JSON_FILE.read_text(encoding="utf-8"))

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        names.add(item)
                    elif isinstance(item, dict) and item.get("login"):
                        names.add(item["login"])

        except (json.JSONDecodeError, OSError):
            print("Could not read existing JSON; starting fresh.")

    if TXT_FILE.exists():
        try:
            for line in TXT_FILE.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    names.add(line.strip())
        except OSError:
            pass

    return names


def main():
    discovered = load_existing()

    for query in SEARCH_QUERIES:
        print(f"\nSearching: {query}")

        for page in (1, 2):
            result = search_users(query, page)

            for user in result.get("items", []):
                login = user.get("login", "").strip()

                if not login:
                    continue

                if login.lower() == USERNAME.lower():
                    continue

                if re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
                    discovered.add(login)

            print(f"Page {page}: {len(result.get('items', []))} results")

    sorted_names = sorted(discovered, key=str.lower)

    JSON_FILE.write_text(
        json.dumps({
            "account": USERNAME,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(sorted_names),
            "usernames": sorted_names
        }, indent=2),
        encoding="utf-8"
    )

    TXT_FILE.write_text(
        "\n".join(sorted_names) + ("\n" if sorted_names else ""),
        encoding="utf-8"
    )

    print("\nDiscovery completed.")
    print(f"Total saved usernames: {len(sorted_names)}")
    print(f"JSON file: {JSON_FILE}")
    print(f"TXT file: {TXT_FILE}")


if __name__ == "__main__":
    main()
