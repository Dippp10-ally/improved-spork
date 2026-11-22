
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

JSON_FILE = Path("potential_followers.json")
TXT_FILE = Path("potential_followers.txt")

TOKEN = (
    os.getenv("GITHUB_TOKEN")
    or os.getenv("FOLLOWING_TOKEN5")
)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Dippp10-ally-discovery"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

QUERIES = [
    "type:user followers:>5",
    "type:user repos:>2",
    "type:user language:Python",
    "type:user language:JavaScript",
    "type:user language:Java",
    "type:user followers:>10"
]


def api_get(url):
    req = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def discover_users():
    discovered = {}

    for query in QUERIES:
        print("Searching:", query)

        for page in range(1, 3):
            params = urllib.parse.urlencode({
                "q": query,
                "per_page": 100,
                "page": page
            })

            url = f"{API}/search/users?{params}"

            try:
                result = api_get(url)

                for user in result.get("items", []):
                    login = user.get("login")

                    if login and login.lower() != USERNAME.lower():
                        discovered[login.lower()] = login

                if page * 100 >= result.get("total_count", 0):
                    break

            except urllib.error.HTTPError as error:
                print("API error:", error.code)
                break

            except Exception as error:
                print("Search error:", error)
                break

    return discovered


def load_existing():
    if not JSON_FILE.exists():
        return {}

    try:
        data = json.loads(
            JSON_FILE.read_text(encoding="utf-8")
        )

        users = {}

        for item in data:
            name = (
                item if isinstance(item, str)
                else item.get("login", "")
            )

            if name and name.lower() != USERNAME.lower():
                users[name.lower()] = name

        return users

    except (ValueError, TypeError):
        print("Could not read existing JSON.")
        return {}


def save_files(users):
    usernames = sorted(
        users.values(),
        key=str.lower
    )

    # JSON output
    JSON_FILE.write_text(
        json.dumps(usernames, indent=2),
        encoding="utf-8"
    )

    # TXT output: one username per line
    TXT_FILE.write_text(
        "\n".join(usernames) + (
            "\n" if usernames else ""
        ),
        encoding="utf-8"
    )

    print("\nFiles updated:")
    print(JSON_FILE)
    print(TXT_FILE)


def main():
    print("GitHub developer discovery")
    print("Account:", USERNAME)

    existing = load_existing()
    discovered = discover_users()

    new_users = {
        key: value
        for key, value in discovered.items()
        if key not in existing
    }

    combined = {**existing, **discovered}

    save_files(combined)

    print("\nDiscovery completed")
    print("New developers:", len(new_users))
    print("Previous developers:", len(existing))
    print("Total unique usernames:", len(combined))

    print("\nApproved files remain separate:")
    for i in range(1, 14):
        print(f"approved_users_part_{i}.txt")


if __name__ == "__main__":
    main()
