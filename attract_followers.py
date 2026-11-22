
import os
import json
import urllib.request
import urllib.parse
from pathlib import Path

USERNAME = "Dippp10-ally"

TOKEN = (
    os.getenv("GITHUB_TOKEN")
    or os.getenv("FOLLOWING_TOKEN5")
)

API = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Dippp10-ally-discovery"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def api_get(url):
    request = urllib.request.Request(
        url, headers=HEADERS
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def discover_users():
    discovered = set()

    queries = [
        "type:user followers:>5",
        "type:user repos:>2",
        "type:user language:Python"
    ]

    for query in queries:
        url = API + "/search/users?" + urllib.parse.urlencode({
            "q": query,
            "per_page": 30
        })

        try:
            result = api_get(url)

            for user in result.get("items", []):
                login = user.get("login")

                if login and login.lower() != USERNAME.lower():
                    discovered.add(login)

        except Exception as error:
            print("Discovery error:", error)

    path = Path("potential_followers.json")

    existing = set()

    if path.exists():
        try:
            existing = set(json.loads(path.read_text()))
        except (ValueError, TypeError):
            pass

    combined = sorted(existing | discovered, key=str.lower)

    path.write_text(
        json.dumps(combined, indent=2),
        encoding="utf-8"
    )

    print("New developers:", len(discovered))
    print("Total discovered:", len(combined))


if __name__ == "__main__":
    discover_users()
