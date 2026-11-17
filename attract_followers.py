
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

USERNAME = "Dippp10-ally"
OUTPUT = Path("potential_followers.json")

QUERIES = [
    "python open source",
    "AI open source",
    "finance programming",
    "good-first-issues",
    "machine learning open source",
    "web development contributor",
    "github open source contributor"
]


def github_search(query):
    params = urllib.parse.urlencode({
        "q": query,
        "per_page": 20
    })

    url = "https://api.github.com/search/users?" + params

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Dippp10-Growth-System"
    }

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    developers = {}

    for query in QUERIES:
        try:
            results = github_search(query)

            for user in results.get("items", []):
                login = user.get("login", "")

                if not login or login.lower() == USERNAME.lower():
                    continue

                developers[login] = {
                    "username": login,
                    "profile": user.get("html_url"),
                    "invitation": (
                        "Hello " + login +
                        "! I enjoy contributing to open-source projects. "
                        "Please explore my GitHub profile: "
                        "https://github.com/" + USERNAME +
                        " and feel free to connect or collaborate."
                    )
                }

            print("Completed:", query)

        except urllib.error.HTTPError as error:
            print("GitHub HTTP error:", error.code)
            print(error.read().decode("utf-8", errors="replace"))

        except Exception as error:
            print("Search failed:", str(error))

    OUTPUT.write_text(
        json.dumps(
            list(developers.values())[:20]            
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\nPotential collaborators:", len(developers))
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()


