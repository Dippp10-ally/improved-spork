
import json
import os
import urllib.request
import urllib.error

from pathlib import Path
from datetime import datetime, timezone

# =====================================
# CONFIGURATION
# =====================================

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

TOKEN = os.getenv("FOLLOW_TOKEN")

MAX_USERS_PER_RUN = 100
TOTAL_PARTS = 13

PROGRESS_FILE = Path("approved_following_progress.json")
REPORT_FILE = Path("follow_report.md")

if not TOKEN:
    raise SystemExit("FOLLOW_TOKEN is missing.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "improved-spork-follow",
    "X-GitHub-Api-Version": "2022-11-28",
}


# =====================================
# GITHUB API
# =====================================

def api_request(url, method="GET"):

    request = urllib.request.Request(
        url,
        headers=HEADERS,
        method=method,
        data=b"" if method == "PUT" else None
    )

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:

            if method == "GET":
                return response.status, json.loads(
                    response.read().decode("utf-8")
                )

            return response.status, None

    except urllib.error.HTTPError as error:

        if error.code == 404:
            return 404, None

        raise RuntimeError(
            f"GitHub API error {error.code}: "
            f"{error.read().decode('utf-8', errors='replace')}"
        ) from error


# =====================================
# VERIFY ACCOUNT
# =====================================

def verify_account():

    status, account = api_request(
        f"{API}/user"
    )

    if status != 200:
        raise SystemExit("Unable to verify GitHub account.")

    if account.get("login", "").lower() != USERNAME.lower():
        raise SystemExit(
            "FOLLOW_TOKEN belongs to another account."
        )

    print(f"Authenticated: {account['login']}")


# =====================================
# LOAD ALL 13 APPROVED FILES
# =====================================

def load_approved_users():

    users = []
    seen = set()

    for part in range(1, TOTAL_PARTS + 1):

        file = Path(
            f"approved_users_part_{part}.txt"
        )

        if not file.exists():
            raise SystemExit(
                f"Missing approved file: {file}"
            )

        print(f"Reading: {file}")

        for line in file.read_text(
            encoding="utf-8"
        ).splitlines():

            username = line.strip()

            if not username:
                continue

            if username.startswith("#"):
                continue

            if "/" in username or any(
                char.isspace() for char in username
            ):
                print(f"Invalid entry skipped: {username}")
                continue

            key = username.lower()

            if key not in seen:
                seen.add(key)
                users.append(username)

    print(f"Approved files: {TOTAL_PARTS}")
    print(f"Unique approved users: {len(users)}")

    return users


# =====================================
# PROGRESS
# =====================================

def load_progress():

    if PROGRESS_FILE.exists():

        return json.loads(
            PROGRESS_FILE.read_text(
                encoding="utf-8"
            )
        )

    return {"next_index": 0}


def save_progress(index):

    temporary = PROGRESS_FILE.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(
            {"next_index": index},
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    temporary.replace(PROGRESS_FILE)


# =====================================
# CHECK FOLLOWING STATUS
# =====================================

def is_following(username):

    status, _ = api_request(
        f"{API}/user/following/{username}"
    )

    if status == 404:
        return False

    return True


# =====================================
# FOLLOW APPROVED USER
# =====================================

def follow_user(username):

    status, _ = api_request(
        f"{API}/user/following/{username}",
        method="PUT"
    )

    return status == 204


# =====================================
# MAIN
# =====================================

def main():

    verify_account()

    approved = load_approved_users()

    progress = load_progress()

    index = int(
        progress.get("next_index", 0)
    )

    if index < 0 or index > len(approved):
        raise SystemExit("Invalid saved progress index.")

    followed = []
    already_following = []
    failed = []

    processed = 0

    print("=" * 45)
    print("APPROVED FOLLOWING WORKFLOW")
    print("=" * 45)

    print(f"Starting index: {index}")
    print(f"Total approved: {len(approved)}")

    while (
        index < len(approved)
        and processed < MAX_USERS_PER_RUN
    ):

        target = approved[index]

        try:

            if target.lower() == USERNAME.lower():
                already_following.append(target)

            elif is_following(target):

                already_following.append(target)
                print(f"ALREADY FOLLOWING: {target}")

            elif follow_user(target):

                followed.append(target)
                print(f"FOLLOWED: {target}")

            else:

                failed.append(target)
                print(f"NOT CONFIRMED: {target}")

        except RuntimeError as error:

            print(f"STOPPED: {error}")
            failed.append(target)
            break

        index += 1
        processed += 1

        # Save progress after each processed user.
        save_progress(index)

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    report = [
        "# Approved Following Report",
        "",
        f"Account: {USERNAME}",
        f"Date UTC: {today}",
        f"Processed: {processed}",
        f"Successfully followed: {len(followed)}",
        f"Already following: {len(already_following)}",
        f"Failed: {len(failed)}",
        f"Remaining: {len(approved) - index}",
        f"Next index: {index}",
        "",
        "## Successfully followed",
        *[f"- {u}" for u in followed],
        "",
        "## Already following",
        *[f"- {u}" for u in already_following],
        "",
        "## Failed",
        *[f"- {u}" for u in failed],
        ""
    ]

    REPORT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    print("=" * 45)
    print(f"Processed: {processed}")
    print(f"New follows: {len(followed)}")
    print(f"Already following: {len(already_following)}")
    print(f"Failed: {len(failed)}")
    print(f"Next index: {index}")
    print(f"Remaining: {len(approved) - index}")
    print("=" * 45)


if __name__ == "__main__":
    main()
