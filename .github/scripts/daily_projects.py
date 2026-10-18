import csv
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_FILE = ROOT / "repository-tasks.json"
REPORT_FILE = ROOT / "project-report.csv"

OWNER = os.environ.get("OWNER", "").strip()
EVENT_NAME = os.environ.get("EVENT_NAME", "")
SCHEDULE_EXPR = os.environ.get("SCHEDULE_EXPR", "")
MANUAL_BATCH = os.environ.get("MANUAL_BATCH", "")
RUN_NUMBER = os.environ.get("RUN_NUMBER", "0")

CRON_BATCHES = {
    "0 1 * * *": 1,
    "0 5 * * *": 2,
    "0 9 * * *": 3,
    "0 13 * * *": 4,
    "0 17 * * *": 5,
}

REPORT_FIELDS = [
    "timestamp_utc",
    "batch",
    "repository",
    "task",
    "status",
    "details",
    "repository_url",
    "stars",
]


def run(command, cwd=None, check=True, capture=True):
    """Run a command without exposing secret environment variables."""
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and result.returncode != 0:
        error = (result.stderr or result.stdout or "Command failed").strip()
        raise RuntimeError(error[-1500:])
    return result


def normalize_repo_name(value):
    """Convert human-friendly repo labels into safe GitHub repo names."""
    name = str(value or "").strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", name)
    name = re.sub(r"-+", "-", name).strip(".-")

    if not name or name in {".", ".."}:
        raise ValueError("Invalid repository name")

    if len(name) > 100:
        raise ValueError("Repository name is too long")

    return name


def load_tasks():
    if not TASK_FILE.is_file():
        raise FileNotFoundError(
            f"Task catalogue not found: {TASK_FILE.name}"
        )

    with TASK_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        tasks = data
    elif isinstance(data, dict):
        tasks = data.get("repositories")
    else:
        tasks = None

    if not isinstance(tasks, list):
        raise ValueError(
            'Expected a JSON array or an object containing "repositories".'
        )

    return tasks


def selected_batch():
    if EVENT_NAME == "workflow_dispatch":
        if MANUAL_BATCH not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Choose a manual batch from 1 to 5.")
        return int(MANUAL_BATCH)

    if SCHEDULE_EXPR not in CRON_BATCHES:
        raise ValueError(
            f"Unknown schedule expression: {SCHEDULE_EXPR!r}"
        )

    return CRON_BATCHES[SCHEDULE_EXPR]


def select_tasks(tasks, batch):
    """
    Select 10 consecutive tasks per run.

    Each UTC day covers up to 50 consecutive catalogue entries.
    Larger catalogues rotate forward on subsequent days.
    """
    if not tasks:
        return []

    day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
    daily_start = ((day_of_year - 1) * 50) % len(tasks)
    start = (daily_start + (batch - 1) * 10) % len(tasks)

    if len(tasks) < 10:
        return tasks[:10]

    return [tasks[(start + i) % len(tasks)] for i in range(10)]


def make_files(repo_dir, files):
    """Create new files only; never overwrite project-owned files."""
    existing = [name for name in files if (repo_dir / name).exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing file(s): "
            + ", ".join(existing)
        )

    for name, content in files.items():
        path = repo_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def handle_empty_input_validation(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/input_validation.py": '''"""Reusable validation for required text values."""


def require_non_empty(value, field_name="value"):
    """Return stripped text or raise ValueError for blank input."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")

    return cleaned
''',
        "tests/test_input_validation.py": '''import pytest

from src.input_validation import require_non_empty


def test_rejects_empty_string():
    with pytest.raises(ValueError):
        require_non_empty("")


def test_rejects_whitespace_only():
    with pytest.raises(ValueError):
        require_non_empty("   ")


def test_returns_trimmed_text():
    assert require_non_empty("  hello  ") == "hello"


def test_rejects_non_string_input():
    with pytest.raises(TypeError):
        require_non_empty(None)
''',
    }
    make_files(repo_dir, files)
    return "tests/test_input_validation.py"


def handle_boundary_tests(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/range_utils.py": '''"""Small, reusable numeric range utilities."""


def is_within_range(value, lower, upper):
    """Return whether value is inside the inclusive range."""
    if lower > upper:
        raise ValueError("lower must be less than or equal to upper")
    return lower <= value <= upper
''',
        "tests/test_range_utils.py": '''import pytest

from src.range_utils import is_within_range


def test_includes_lower_boundary():
    assert is_within_range(1, 1, 5)


def test_includes_upper_boundary():
    assert is_within_range(5, 1, 5)


def test_includes_middle_value():
    assert is_within_range(3, 1, 5)


def test_excludes_values_outside_range():
    assert not is_within_range(0, 1, 5)
    assert not is_within_range(6, 1, 5)


def test_rejects_reversed_range():
    with pytest.raises(ValueError):
        is_within_range(3, 5, 1)
''',
    }
    make_files(repo_dir, files)
    return "tests/test_range_utils.py"


def normalize_task(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


TASK_HANDLERS = {
    "add input validation for empty values": handle_empty_input_validation,
    "add unit tests for boundary conditions": handle_boundary_tests,
}


def get_repo(full_name):
    result = run(
        ["gh", "repo", "view", full_name, "--json", "name,url"],
        check=False,
    )
    return result.returncode == 0


def ensure_repo(full_name, description):
    """
    Ensure repository exists. Returns True if the repo was created by this call,
    False if it already existed or creation failed.
    """
    if get_repo(full_name):
        return False

    # Try to create the repository. Use check=False and inspect result so the
    # caller can handle failures without raising.
    result = run(
        ["gh", "repo", "create", full_name, "--public", "--add-readme", "--description", description[:300]],
        check=False,
    )
    return result.returncode == 0


def get_star_count(full_name):
    result = run(
        ["gh", "api", f"repos/{full_name}", "--jq", ".stargazers_count"],
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def process_one(item, batch):
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "timestamp_utc": now,
        "batch": batch,
        "repository": "",
        "task": "",
        "status": "",
        "details": "",
        "repository_url": "",
        "stars": "",
    }

    try:
        if not isinstance(item, dict):
            raise ValueError("Task entry must be a JSON object")

        repo_value = item.get("repo") or item.get("repository")
        task_value = item.get("task")
        commit_message = str(
            item.get("commit") or "chore: apply tested task improvement"
        ).strip()

        repo_name = normalize_repo_name(repo_value)
        task_text = str(task_value or "").strip()
        full_name = f"{OWNER}/{repo_name}"

        row["repository"] = full_name
        row["task"] = task_text

        if not OWNER:
            raise ValueError("OWNER environment variable is missing")

        if not task_text:
            raise ValueError("Task description is empty")

        handler = TASK_HANDLERS.get(normalize_task(task_text))
        if handler is None:
            row["status"] = "UNSUPPORTED"
            row["details"] = (
                "No verified implementation exists for this exact task. "
                "Add a reviewed handler before automating it."
            )
            return row

        # ensure_repo now returns True if it created the repo
        created = ensure_repo(full_name, task_text)
        if created:
            # Star only newly created repositories. Non-fatal if it fails.
            star_result = run(
                ["gh", "api", "-X", "PUT", f"user/starred/{full_name}"],
                check=False,
                capture=True,
            )
            if star_result.returncode == 0:
                # update star count after starring
                row["stars"] = get_star_count(full_name)
            else:
                # record a non-fatal warning in details; continue processing
                warning = (star_result.stderr or star_result.stdout or "").strip()
                if warning:
                    row["details"] = (row.get("details", "") + " STAR_WARNING: " + warning[:1500]).strip()

        with tempfile.TemporaryDirectory(prefix="repo-task-") as temp:
            clone_dir = Path(temp) / repo_name

            run([
                "gh", "repo", "clone", full_name, str(clone_dir)
            ])

            test_file = handler(clone_dir)

            # Run only the test file introduced by this handler.
            test_result = run(
                ["python", "-m", "pytest", "-q", test_file],
                cwd=clone_dir,
                check=False,
            )

            if test_result.returncode != 0:
                details = (
                    (test_result.stdout or "")
                    + "\n"
                    + (test_result.stderr or "")
                ).strip()
                row["status"] = "TEST_FAILED"
                row["details"] = details[-2500:]
                # update stars before returning
                row["repository_url"] = f"https://github.com/{full_name}"
                row["stars"] = get_star_count(full_name)
                return row

            run(
                ["git", "config", "user.name", "github-actions[bot]"],
                cwd=clone_dir,
            )
            run(
                ["git", "config", "user.email",
                 "41898282+github-actions[bot]@users.noreply.github.com"],
                cwd=clone_dir,
            )
            run(["git", "add", "--", "src", "tests"], cwd=clone_dir)

            staged = run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=clone_dir,
                check=False,
            )

            if staged.returncode == 0:
                row["status"] = "NO_CHANGE"
                row["details"] = "No staged changes were available to commit."
                row["repository_url"] = f"https://github.com/{full_name}"
                row["stars"] = row.get("stars") or get_star_count(full_name)
                return row

            run(
                ["git", "commit", "-m", commit_message[:200]],
                cwd=clone_dir,
            )
            run(["git", "push"], cwd=clone_dir)

        row["status"] = "SUCCESS"
        row["details"] = f"Targeted tests passed; committed {commit_message[:200]}."
        row["repository_url"] = f"https://github.com/{full_name}"
        row["stars"] = row.get("stars") or get_star_count(full_name)
        return row

    except FileExistsError as exc:
        row["status"] = "SKIPPED"
        row["details"] = str(exc)
    except Exception as exc:
        row["status"] = "ERROR"
        row["details"] = str(exc)[-2500:]

    if row["repository"]:
        row["repository_url"] = (
            f"https://github.com/{row['repository']}"
        )
        row["stars"] = row["stars"] or get_star_count(row["repository"])

    return row


def main():
    batch = selected_batch()
    tasks = load_tasks()
    selected = select_tasks(tasks, batch)

    rows = [process_one(item, batch) for item in selected]

    with REPORT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    print(f"Batch: {batch}")
    print(f"Selected tasks: {len(selected)}")
    print("Results:", json.dumps(counts, sort_keys=True))
    print(f"Report written to {REPORT_FILE.name}")

    # Unsupported tasks and individual repository errors are recorded
    # rather than aborting the rest of the batch.
    if not selected:
        print("The task catalogue is empty.")


if __name__ == "__main__":
    main()
