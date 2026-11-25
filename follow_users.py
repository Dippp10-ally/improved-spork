
import json
import os
import re
import time
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
STATE_FILE = Path("follow_state.json")

# Conservative daily limit for this workflow.
MAX_FOLLOWS_PER_RUN = 10


def api_request(url, method="GET"):
    request = urllib.request.Request(
        url,
        headers=HEADERS,
        method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, body

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")

        if error.code == 403:
            if (
                error.headers.get("X-RateLimit-Remaining") == "0"
                or "rate limit" in body.lower()
            ):
                raise RuntimeError("GitHub API rate limit reached.")

        return error.code, body


def get_following():
    following = set()
    page = 1

    while True:
        url = (
            f"{API}/users/{USERNAME}/following"
            f"?per_page=100&page={page}"
        )

        status, body = api_request(url)

        if status != 200:
            raise RuntimeError(
                f"Could not load following list: HTTP {status}"
            )

        users = json.loads(body)

        if not users:
            break

        for user in users:
            login = user.get("login")
            if login:
                following.add(login.lower())

        page += 1

    return following


def load_approved():
    approved = set()

    for number in range(1, 14):
        path = Path(f"approved_users_part_{number}.txt")

        if not path.exists():
            print(f"Missing file: {path}")
            continue

        with path.open(
            encoding="utf-8",
            errors="ignore"
        ) as file:

            for line in file:
                name = line.strip()

                if (
                    name
                    and not name.startswith("#")
                    and re.fullmatch(r"[A-Za-z0-9-]{1,39}", name)
                    and name.lower() != USERNAME.lower()
                ):
                    approved.add(name)

    return sorted(approved, key=str.lower)


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8"
    )


def follow_user(name):
    url = f"{API}/user/following/{name}"

    status, _ = api_request(url, method="PUT")

    return status in (204, 304)


def main():
    approved = load_approved()

    print(f"Approved unique accounts: {len(approved)}")

    following = get_following()
    state = load_state()

    successful = []
    already_following = []
    failed = []

    attempts = 0

    for name in approved:

        login = name.lower()

        if login in following:
            already_following.append(name)
            continue

        if state.get(login) == "success":
            # Verify actual GitHub following state before skipping.
            print(f"Previously processed: {name}")

        if attempts >= MAX_FOLLOWS_PER_RUN:
            break

        attempts += 1

        try:
            if follow_user(name):
                successful.append(name)
                following.add(login)
                state[login] = "success"

                print(f"Follow request accepted: {name}")

            else:
                failed.append(name)
                print(f"Follow request unsuccessful: {name}")

        except RuntimeError:
            save_state(state)
            print("Stopping because of GitHub API rate limits.")
            raise

        except Exception as error:
            failed.append(name)
            print(f"Error for {name}: {error}")

        time.sleep(2)

    save_state(state)

    report = {
        "account": USERNAME,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "approved_accounts": len(approved),
        "following_before": len(get_following()) - len(successful),
        "following_after": len(get_following()),
        "successful_requests": successful,
        "successful_count": len(successful),
        "already_following_count": len(already_following),
        "failed_accounts": failed,
        "failed_count": len(failed),
        "attempted_count": attempts
    }

    RESULT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print("\nFOLLOW REPORT")
    print("Successful:", len(successful))
    print("Already following:", len(already_following))
    print("Failed:", len(failed))
    print("Following now:", report["following_after"])


if __name__ == "__main__":
    main()
