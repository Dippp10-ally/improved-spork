
import json
import os
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime, timezone

USERNAME = "Dippp10-ally"
API = "https://api.github.com"
TOKEN = os.getenv("FOLLOWING_TOKEN5")

TARGET_ACCOUNTS = 20_000_000
MAX_PAGES_PER_QUERY = 10

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

JSON_FILE = Path("potential_followers.json")
TXT_FILE = Path("potential_followers.txt")


def load_existing():
    if not JSON_FILE.exists():
        return set()

    try:
        data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
        return {
            name for name in data.get("usernames", [])
            if isinstance(name, str)
        }
    except (OSError, ValueError):
        return set()


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

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def save_results(names):
    ordered = sorted(names, key=str.lower)

    data = {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "saved_count": len(ordered),
        "target_accounts": TARGET_ACCOUNTS,
        "usernames": ordered
    }

    JSON_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

    TXT_FILE.write_text(
        "\n".join(ordered) + ("\n" if ordered else ""),
        encoding="utf-8"
    )


def main():
    discovered = load_existing()

    print(f"Previously saved: {len(discovered):,}")

    for query in QUERIES:
        if len(discovered) >= TARGET_ACCOUNTS:
            break

        print(f"\nSearching: {query}")

        for page in range(1, MAX_PAGES_PER_QUERY + 1):
            try:
                result = search_users(query, page)

                users = result.get("items", [])

                if not users:
                    break

                for user in users:
                    login = user.get("login", "").strip()

                    if (
                        login
                        and login.lower() != USERNAME.lower()
                        and re.fullmatch(
                            r"[A-Za-z0-9-]{1,39}", login
                        )
                    ):
                        discovered.add(login)

                    if len(discovered) >= TARGET_ACCOUNTS:
                        break

                save_results(discovered)

                print(
                    f"Saved: {len(discovered):,} / "
                    f"{TARGET_ACCOUNTS:,}"
                )

                if len(users) < 100:
                    break

                time.sleep(2.1)

            except urllib.error.HTTPError as error:
                print("GitHub HTTP error:", error.code)
                if error.code == 403:
                    print("Check GitHub API rate limits.")
                break

            except Exception as error:
                print("Search failed:", error)
                break

    save_results(discovered)

    print("\nDiscovery completed.")
    print("Total unique usernames:", f"{len(discovered):,}")
    print("Target:", f"{TARGET_ACCOUNTS:,}")


if __name__ == "__main__":
    main()
