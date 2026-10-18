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


def handle_required_fields_validation(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/required_fields.py": '''"""Validation helpers for required values."""


def require_required_field(value, field_name="field"):
    """Ensure a field is present and not blank."""
    if value is None:
        raise ValueError(f"{field_name} is required")
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned
''',
        "tests/test_required_fields.py": '''import pytest

from src.required_fields import require_required_field


def test_rejects_none():
    with pytest.raises(ValueError):
        require_required_field(None, "name")


def test_rejects_blank_string():
    with pytest.raises(ValueError):
        require_required_field("   ", "name")


def test_returns_trimmed_string():
    assert require_required_field("  alice  ", "name") == "alice"
''',
    }
    make_files(repo_dir, files)
    return "tests/test_required_fields.py"


def handle_missing_configuration_validation(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/config_validation.py": '''"""Validation helpers for configuration dictionaries."""


def require_config_value(config, key):
    """Return the configured value or raise when it is missing."""
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary")
    if key not in config or config[key] is None:
        raise ValueError(f"{key} is required")
    value = config[key]
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{key} must not be empty")
    return value
''',
        "tests/test_config_validation.py": '''import pytest

from src.config_validation import require_config_value


def test_returns_config_value():
    assert require_config_value({"host": "localhost"}, "host") == "localhost"


def test_raises_for_missing_key():
    with pytest.raises(ValueError):
        require_config_value({}, "host")


def test_raises_for_blank_string():
    with pytest.raises(ValueError):
        require_config_value({"token": "   "}, "token")
''',
    }
    make_files(repo_dir, files)
    return "tests/test_config_validation.py"


def handle_null_value_tests(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/null_utils.py": '''"""Helpers for None-safe operations."""


def coalesce(value, default=None):
    """Return the default when value is None."""
    return default if value is None else value
''',
        "tests/test_null_utils.py": '''from src.null_utils import coalesce


def test_coalesce_returns_default_for_none():
    assert coalesce(None, 5) == 5


def test_coalesce_preserves_value():
    assert coalesce(0, 5) == 0
''',
    }
    make_files(repo_dir, files)
    return "tests/test_null_utils.py"


def handle_empty_collections_tests(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/collection_utils.py": '''"""Collection helpers."""


def is_empty_collection(value):
    """Treat None and empty values as empty collections."""
    return value is None or (hasattr(value, "__len__") and len(value) == 0)
''',
        "tests/test_collection_utils.py": '''from src.collection_utils import is_empty_collection


def test_none_is_empty():
    assert is_empty_collection(None)


def test_empty_list_is_empty():
    assert is_empty_collection([])


def test_non_empty_is_not_empty():
    assert not is_empty_collection([1])
''',
    }
    make_files(repo_dir, files)
    return "tests/test_collection_utils.py"


def handle_numeric_validation(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/number_validation.py": '''"""Numeric validation helpers."""


def is_positive_int(value):
    """Return True when value is a positive integer."""
    return isinstance(value, int) and value > 0
''',
        "tests/test_number_validation.py": '''from src.number_validation import is_positive_int


def test_positive_int():
    assert is_positive_int(3)


def test_zero_is_not_positive():
    assert not is_positive_int(0)


def test_non_int_is_false():
    assert not is_positive_int("3")
''',
    }
    make_files(repo_dir, files)
    return "tests/test_number_validation.py"


def handle_duplicate_values(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/duplicate_utils.py": '''"""Helpers for duplicate values."""


def unique(values):
    """Return values without duplicates while preserving order."""
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
''',
        "tests/test_duplicate_utils.py": '''from src.duplicate_utils import unique


def test_unique_removes_duplicates():
    assert unique([1, 2, 1, 3]) == [1, 2, 3]


def test_unique_keeps_order():
    assert unique(["b", "a", "b"]) == ["b", "a"]
''',
    }
    make_files(repo_dir, files)
    return "tests/test_duplicate_utils.py"


def handle_invalid_file_path_handling(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/file_utils.py": '''"""File system helpers."""

from pathlib import Path


def file_exists(path):
    """Return True when the path exists."""
    return Path(path).exists()
''',
        "tests/test_file_utils.py": '''from pathlib import Path

from src.file_utils import file_exists


def test_existing_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("ok")
    assert file_exists(str(path))


def test_missing_file(tmp_path):
    assert not file_exists(str(tmp_path / "missing.txt"))
''',
    }
    make_files(repo_dir, files)
    return "tests/test_file_utils.py"


def handle_logging_for_failures(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/logging_utils.py": '''"""Small logging helpers."""

import logging


def get_logger(name="app"):
    """Return a configured logger with a console handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
''',
        "tests/test_logging_utils.py": '''import logging

from src.logging_utils import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("example")
    assert isinstance(logger, logging.Logger)
''',
    }
    make_files(repo_dir, files)
    return "tests/test_logging_utils.py"


def handle_timeout_reporting(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/timeout_utils.py": '''"""Timeout helpers."""


def validate_timeout(seconds):
    """Reject negative timeouts."""
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    return seconds
''',
        "tests/test_timeout_utils.py": '''import pytest

from src.timeout_utils import validate_timeout


def test_accepts_valid_timeout():
    assert validate_timeout(3) == 3


def test_rejects_negative_timeout():
    with pytest.raises(ValueError):
        validate_timeout(-1)
''',
    }
    make_files(repo_dir, files)
    return "tests/test_timeout_utils.py"


def handle_retry_behavior(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/retry_utils.py": '''"""Simple retry helper."""


def retry_once(fn):
    """Retry a callback once after a failure."""

    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return fn(*args, **kwargs)

    return wrapped
''',
        "tests/test_retry_utils.py": '''from src.retry_utils import retry_once


def test_retry_once_recovers_after_failure():
    calls = {"count": 0}

    @retry_once
    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary fault")
        return "ok"

    assert flaky() == "ok"
''',
    }
    make_files(repo_dir, files)
    return "tests/test_retry_utils.py"


def handle_documentation_examples(repo_dir):
    files = {
        "docs/usage.md": '# Usage\n\n```bash\npython app.py --help\n```\n',
        "tests/test_usage_docs.py": '''from pathlib import Path


def test_usage_doc_exists():
    path = Path("docs/usage.md")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Usage" in text
    assert "python app.py --help" in text
''',
    }
    make_files(repo_dir, files)
    return "tests/test_usage_docs.py"


def handle_invalid_input_error_handling(repo_dir):
    files = {
        "src/__init__.py": '"""Project source package."""\n',
        "src/input_errors.py": '''"""Error-reporting helpers for invalid input."""


def explain_invalid_input(value, field_name="value"):
    """Return a helpful validation message for the offending value."""
    if value is None:
        return f"{field_name} is required"
    if isinstance(value, str) and not value.strip():
        return f"{field_name} must not be empty"
    return f"invalid {field_name}: {value!r}"
''',
        "tests/test_input_errors.py": '''from src.input_errors import explain_invalid_input


def test_reports_none_as_missing():
    assert explain_invalid_input(None, "name") == "name is required"


def test_reports_blank_value():
    assert explain_invalid_input("   ", "name") == "name must not be empty"


def test_reports_invalid_value():
    assert "invalid name" in explain_invalid_input(5, "name")
''',
    }
    make_files(repo_dir, files)
    return "tests/test_input_errors.py"


def handle_configuration_docs(repo_dir):
    files = {
        "docs/configuration.md": '# Configuration\n\nSet the `TOKEN` environment variable before running the app.\n',
        "tests/test_configuration_docs.py": '''from pathlib import Path


def test_configuration_doc_exists():
    doc = Path("docs/configuration.md")
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "Configuration" in text
    assert "TOKEN" in text
''',
    }
    make_files(repo_dir, files)
    return "tests/test_configuration_docs.py"


def normalize_task(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


TASK_HANDLERS = {
    "add input validation for empty values": handle_empty_input_validation,
    "add unit tests for boundary conditions": handle_boundary_tests,
    "add validation for required fields": handle_required_fields_validation,
    "add validation for required options": handle_required_fields_validation,
    "add validation for empty input": handle_empty_input_validation,
    "add tests for null values": handle_null_value_tests,
    "add tests for empty collections": handle_empty_collections_tests,
    "handle missing configuration values": handle_missing_configuration_validation,
    "improve handling of missing environment variables": handle_missing_configuration_validation,
    "validate configuration file structure": handle_missing_configuration_validation,
    "add validation for numeric input": handle_numeric_validation,
    "handle invalid file paths": handle_invalid_file_path_handling,
    "handle unavailable files gracefully": handle_invalid_file_path_handling,
    "improve logging for failed operations": handle_logging_for_failures,
    "improve timeout error reporting": handle_timeout_reporting,
    "add tests for retry behavior": handle_retry_behavior,
    "document command usage examples": handle_documentation_examples,
    "document configuration options": handle_configuration_docs,
    "add usage examples to documentation": handle_documentation_examples,
    "document supported input formats": handle_documentation_examples,
    "document retry configuration": handle_documentation_examples,
    "improve readme troubleshooting guidance": handle_documentation_examples,
    "update readme with installation instructions": handle_documentation_examples,
    "improve error handling for invalid input": handle_invalid_input_error_handling,
    "improve malformed data handling": handle_invalid_input_error_handling,
    "add duplicate input handling": handle_duplicate_values,
    "handle unexpected response data": handle_invalid_input_error_handling,
    "add tests for default configuration": handle_missing_configuration_validation,
    "add tests for default values": handle_null_value_tests,
    "handle missing directories safely": handle_invalid_file_path_handling,
    "add validation for identifier formats": handle_required_fields_validation,
    "add validation for string length limits": handle_required_fields_validation,
    "handle invalid date input": handle_invalid_input_error_handling,
    "add validation for supported formats": handle_required_fields_validation,
    "handle unsupported options": handle_required_fields_validation,
    "add tests for repeated operations": handle_retry_behavior,
    "add tests for duplicate values": handle_duplicate_values,
    "add tests for invalid arguments": handle_invalid_input_error_handling,
    "add tests for large input values": handle_numeric_validation,
    "add tests for case-sensitive input": handle_required_fields_validation,
    "add tests for error conditions": handle_invalid_input_error_handling,
    "handle unexpected response data": handle_invalid_input_error_handling,
    "handle invalid date input": handle_invalid_input_error_handling,
    "handle missing directories safely": handle_invalid_file_path_handling,
    "handle invalid configuration": handle_missing_configuration_validation,
    "add tests for minimum input values": handle_numeric_validation,
    "handle missing configuration values gracefully": handle_missing_configuration_validation,
    "add tests for invalid input": handle_invalid_input_error_handling,
    "add validation for whitespace-only input": handle_empty_input_validation,
    "add tests for default values": handle_null_value_tests,
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
