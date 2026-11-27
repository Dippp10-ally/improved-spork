
import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "Dippp10-ally"
API = "https://api.github.com"
TOKEN = os.getenv("FOLLOW_TOKEN")

MAX_NEW_FOLLOWS = 20

RESULT_FILE = Path("follow_results.json")
STATE_FILE = Path("followed_users.json")

if not TOKEN:
    raise SystemExit("FOLLOW_TOKEN is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "improved-spork",
    "X-GitHub-Api-Version": "2022-11-28",
}


def api(path, method="GET"):
    request = urllib.request.Request(
        API + path,
        data=b"" if method == "PUT" else None,
        headers=HEADERS,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("message", body)
        except json.JSONDecodeError:
            message = body
        return error.code, message


def load_users():
    users = set()

    for number in range(1, 14):
        path = Path(f"approved_users_part_{number}.txt")

        if not path.exists():
            raise SystemExit(f"Missing file: {path}")

        for line in path.read_text(encoding="utf-8").splitlines():
            name = line.strip()

            if (
                name
                and not name.startswith("#")
                and re.fullmatch(r"[A-Za-z0-9-]{1,39}", name)
                and name.lower() != USERNAME.lower()
            ):
                users.add(name)

    return sorted(users, key=str.lower)


def load_state():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {name.lower() for name in data.get("successful", [])}
    except (json.JSONDecodeError, OSError):
        raise SystemExit("Invalid followed_users.json; refusing to reset progress.")


def main():
    status, account = api("/user")

    if status != 200 or account.get("login", "").lower() != USERNAME.lower():
        raise SystemExit(f"GitHub authentication failed: {status}")

    approved = load_users()
    completed = load_state()

    successful = []
    already = []
    failed = []
    attempts = 0

    print(f"Date UTC: {datetime.now(timezone.utc).isoformat()}")
    print(f"Approved unique users: {len(approved)}")

    for target in approved:
        if attempts >= MAX_NEW_FOLLOWS:
            break

        if target.lower() in completed:
            continue

        check_status, message = api(f"/user/following/{target}")

        if check_status == 204:
            already.append(target)
            completed.add(target.lower())
            continue

        if check_status != 404:
            failed.append({
                "username": target,
                "status": check_status,
                "error": str(message)
            })
            print(f"Check failed: {target}, HTTP {check_status}")
            if check_status in (401, 403):
                break
            continue

        attempts += 1

        follow_status, message = api(
            f"/user/following/{target}", "PUT"
        )

        if follow_status == 204:
            successful.append(target)
            completed.add(target.lower())
            print(f"Follow successful: {target}")
        else:
            failed.append({
                "username": target,
                "status": follow_status,
                "error": str(message)
            })
            print(f"Follow failed: {target}, HTTP {follow_status}")

            if follow_status in (401, 403, 422):
                break

    STATE_FILE.write_text(
        json.dumps({
            "account": USERNAME,
            "successful": sorted(completed),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }, indent=2) + "\n",
        encoding="utf-8"
    )

    status, account = api("/user")

    if status != 200:
        raise SystemExit("Could not retrieve final following count.")

    report = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "approved_unique_accounts": len(approved),
        "successful": len(successful),
        "already_following": len(already),
        "failed": len(failed),
        "following_now": account["following"],
        "successful_usernames": successful,
        "already_following_usernames": already,
        "failed_requests": failed
    }

    RESULT_FILE.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8"
    )

    print("\nFOLLOW REPORT")
    print(f"Successful: {len(successful)}")
    print(f"Already following: {len(already)}")
    print(f"Failed: {len(failed)}")
    print(f"Following now: {account['following']}")


if __name__ == "__main__":
    main()
