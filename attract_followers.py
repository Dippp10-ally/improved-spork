
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

TOKEN = os.environ.get("FOLLOWING_TOKEN5")

STATE_FILE = Path("follower_state.json")
REPORT_FILE = Path("follower_growth.json")
DISCOVERY_FILE = Path("candidate_developers.json")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}" if TOKEN else "",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Dippp10-Inbound-Growth"
}


def api(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


def discover_developers():
    queries = [
        "stars:>10 language:Python",
        "stars:>10 language:JavaScript",
        "stars:>10 language:Java"
    ]

    developers = {}

    for query in queries:
        url = API + "/search/repositories?" + urllib.parse.urlencode({
            "q": query,
            "sort": "updated",
            "per_page": 10
        })

        try:
            repositories = api(url)

            for repo in repositories.get("items", []):
                endpoint = (
                    API + "/repos/"
                    + repo["full_name"]
                    + "/contributors?per_page=30"
                )

                for user in api(endpoint):
                    login = user.get("login", "")

                    if not login or login.lower() == USERNAME.lower():
                        continue

                    developers.setdefault(login.lower(), {
                        "username": login,
                        "profile": user.get("html_url"),
                        "repository": repo["full_name"],
                        "contributions": user.get("contributions", 0)
                    })

        except urllib.error.HTTPError as error:
            print("Discovery HTTP error:", error.code)

        except Exception as error:
            print("Discovery error:", str(error))

    save_json(DISCOVERY_FILE, {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_discovered": len(developers),
        "developers": list(developers.values())
    })

    print("Developers discovered:", len(developers))


def get_followers():
    followers = set()

    for page in range(1, 1001):
        url = (
            API + "/users/" + USERNAME
            + "/followers?per_page=100&page=" + str(page)
        )

        data = api(url)

        for user in data:
            followers.add(user["login"].lower())

        if len(data) < 100:
            break

    return followers


def monitor_followers():
    profile = api(API + "/users/" + USERNAME)
    current = get_followers()

    state = load_json(STATE_FILE, {
        "previous_followers": [],
        "first_run": True
    })

    previous = {
        user.lower()
        for user in state.get("previous_followers", [])
    }

    if state.get("first_run", True):
        new_followers = []
        lost_followers = []
        print("Initial follower baseline established.")
    else:
        new_followers = sorted(current - previous)
        lost_followers = sorted(previous - current)

    report = {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "followers": profile.get("followers", 0),
        "following": profile.get("following", 0),
        "public_repositories": profile.get("public_repos", 0),
        "new_followers": new_followers,
        "new_followers_count": len(new_followers),
        "lost_followers": lost_followers,
        "lost_followers_count": len(lost_followers)
    }

    save_json(REPORT_FILE, report)

    save_json(STATE_FILE, {
        "previous_followers": sorted(current),
        "first_run": False,
        "last_updated": report["updated_at"]
    })

    print("\n===== FOLLOWER GROWTH =====")
    print("Followers:", profile.get("followers", 0))
    print("New followers:", len(new_followers))
    print("Lost followers:", len(lost_followers))
    print("Following:", profile.get("following", 0))
    print("Reports saved.")


def main():
    if not TOKEN:
        raise SystemExit("FOLLOWING_TOKEN5 is missing.")

    account = api(API + "/user")

    if account.get("login", "").lower() != USERNAME.lower():
        raise SystemExit("GitHub token account mismatch.")

    discover_developers()
    monitor_followers()


if __name__ == "__main__":
    main()
