
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

if not TOKEN:
    raise SystemExit("FOLLOW_TOKEN secret is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "improved-spork",
    "X-GitHub-Api-Version": "2022-11-28",
}


def request_api(path, method="GET"):
    request = urllib.request.Request(
        API + path,
        data=b"" if method == "PUT" else None,
        headers=HEADERS,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("message", body)
        except json.JSONDecodeError:
            message = body
        return error.code, message


def load_approved():
    users = set()

    for number in range(1, 14):
        path = Path(f"approved_users_part_{number}.txt")

        if not path.exists():
            raise SystemExit(f"Missing subfile: {path}")

        lines = path.read_text(encoding="utf-8").splitlines()

        for line in lines:
            name = line.strip()

            if (
                name
                and not name.startswith("#")
                and re.fullmatch(r"[A-Za-z0-9-]{1,39}", name)
                and name.lower() != USERNAME.lower()
            ):
                users.add(name)

    return sorted(users, key=str.lower)


def main():
    now = datetime.now(timezone.utc).isoformat()

    status, account = request_api("/user")

    if status != 200:
        raise SystemExit(f"Authentication error: {status}: {account}")

    if account.get("login", "").lower() != USERNAME.lower():
        raise SystemExit("Token belongs to a different GitHub account.")

    approved = load_approved()

    successful = []
    already = []
    failed = []
    attempts = 0

    print("FOLLOW APPROVED USERS")
    print("=" * 40)
    print(f"Account: {USERNAME}")
    print(f"Date UTC: {now}")
    print(f"Approved unique accounts: {len(approved)}")

    for target in approved:
        if attempts >= MAX_NEW_FOLLOWS:
            break

        check_status, check_message = request_api(
            f"/user/following/{target}"
        )

        if check_status == 204:
            already.append(target)
            print(f"Already following: {target}")
            continue

        if check_status != 404:
            failed.append({
                "username": target,
                "stage": "check",
                "status": check_status,
                "error": str(check_message)
            })
            print(f"Check failed: {target}: HTTP {check_status}")
            if check_status in (401, 403):
                break
            continue

        attempts += 1

        follow_status, follow_message = request_api(
            f"/user/following/{target}", "PUT"
        )

        if follow_status == 204:
            successful.append(target)
            print(f"Follow successful: {target}")
        else:
            failed.append({
                "username": target,
                "stage": "follow",
                "status": follow_status,
                "error": str(follow_message)
            })
            print(
                f"Follow unsuccessful: {target} "
                f"HTTP {follow_status}: {follow_message}"
            )

            if follow_status in (401, 403, 422):
                break

    status, account = request_api("/user")

    if status != 200:
        raise SystemExit("Could not retrieve final following count.")

    report = {
        "date_utc": now,
        "account": USERNAME,
        "approved_unique_accounts": len(approved),
        "attempts": attempts,
        "successful": len(successful),
        "already_following": len(already),
        "failed": len(failed),
        "following_now": account["following"],
        "successful_usernames": successful,
        "already_following_usernames": already,
        "failed_requests": failed,
    }

    RESULT_FILE.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8"
    )

    print("\nFOLLOW REPORT")
    print("=" * 40)
    print(f"Successful: {len(successful)}")
    print(f"Already following: {len(already)}")
    print(f"Failed: {len(failed)}")
    print(f"Following now: {account['following']}")


if __name__ == "__main__":
    main()
