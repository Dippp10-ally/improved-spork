
import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

USERNAME = "Dippp10-ally"
API = "https://api.github.com"

# Exactly 13 approved-user files
APPROVED_FILES = [
    Path(f"approved_users_part_{i}.txt")
    for i in range(1, 14)
]

OUTPUT_FILE = Path("follow_results.json")

DAILY_LIMIT = 20
TOKEN = os.environ.get("FOLLOW_TOKEN")


def api_request(url, method="GET"):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + TOKEN,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Dippp10-Follow-System"
    }

    request = urllib.request.Request(
        url,
        data=b"" if method == "PUT" else None,
        headers=headers,
        method=method
    )

    return urllib.request.urlopen(request, timeout=30)


def get_approved_users():
    users = []
    seen = set()

    for file in APPROVED_FILES:

        if not file.exists():
            print("Missing file:", file)
            continue

        print("Reading:", file)

        with file.open("r", encoding="utf-8") as f:
            for line in f:

                login = line.strip().lstrip("@")

                if not login or login.startswith("#"):
                    continue

                # GitHub username validation
                if (
                    len(login) > 39
                    or not re.fullmatch(
                        r"(?!.*--)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?",
                        login
                    )
                ):
                    print("Invalid username skipped:", login)
                    continue

                if login.lower() == USERNAME.lower():
                    continue

                if login.lower() in seen:
                    continue

                seen.add(login.lower())
                users.append(login)

    print("Total unique approved users:", len(users))

    return users


def main():

    if not TOKEN:
        raise SystemExit("FOLLOW_TOKEN is missing.")

    # Verify token owner
    with api_request(API + "/user") as response:
        account = json.loads(response.read().decode("utf-8"))

    if account.get("login", "").lower() != USERNAME.lower():
        raise SystemExit(
            "Token does not belong to Dippp10-ally. Stopping."
        )

    users = get_approved_users()

    if not users:
        raise SystemExit("No valid approved usernames found.")

    results = []
    newly_followed = 0

    for login in users:

        # Stop after 20 new follows
        if newly_followed >= DAILY_LIMIT:
            break

        url = API + "/user/following/" + login

        try:

            # Check existing following status
            try:
                with api_request(url):
                    print("Already following:", login)

                    results.append({
                        "username": login,
                        "status": "already_following"
                    })

                    continue

            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise

            # Follow approved account
            with api_request(url, "PUT"):
                print("Followed successfully:", login)

            newly_followed += 1

            results.append({
                "username": login,
                "status": "followed"
            })

            time.sleep(2)

        except urllib.error.HTTPError as error:

            print("GitHub error:", login, error.code)

            results.append({
                "username": login,
                "status": "error",
                "http_code": error.code
            })

        except Exception as error:

            print("Request failed:", login, str(error))

            results.append({
                "username": login,
                "status": "error",
                "message": str(error)
            })

    OUTPUT_FILE.write_text(
        json.dumps({
            "account": USERNAME,
            "approved_files": len(APPROVED_FILES),
            "processed": len(results),
            "newly_followed": newly_followed,
            "results": results
        }, indent=2),
        encoding="utf-8"
    )

    print("\n========== SUMMARY ==========")
    print("Processed:", len(results))
    print("Newly followed:", newly_followed)
    print("Daily limit:", DAILY_LIMIT)
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
