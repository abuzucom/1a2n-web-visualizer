"""Require current code-owner approval for sensitive pull-request changes."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import PurePosixPath
from typing import Any


CODE_OWNER = "itsjustatank"
MAX_FILE_PAGES = 50
AGENT_FILES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "CONVENTIONS.md",
    ".cursorrules", ".clinerules", ".windsurfrules",
}
PROTECTED_PREFIXES = (
    ".github/",
    "scripts/",
    "tools/",
    "patches/",
    "src/js/",
    "src/vendor/",
)
PROTECTED_FILES = {
    "package.json", "package-lock.json", "Dockerfile", "docker-compose.yml",
    "Caddyfile", ".dockerignore",
}


def is_protected(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name in AGENT_FILES:
        return True
    if name in PROTECTED_FILES or normalized.startswith(PROTECTED_PREFIXES):
        return True
    return normalized.startswith("src/") and normalized.endswith((".html", ".htm"))


def github_get(path: str) -> Any:
    token = os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def load_event() -> dict[str, Any]:
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as event_file:
        return json.load(event_file)


def changed_files(event: dict[str, Any]) -> list[str]:
    repository = event["repository"]["full_name"]
    number = event["pull_request"]["number"]
    files = []
    page = 1
    for page in range(1, MAX_FILE_PAGES + 1):
        batch = github_get(f"/repos/{repository}/pulls/{number}/files?per_page=100&page={page}")
        files.extend(item["filename"] for item in batch)
        if len(batch) < 100:
            return files
    raise RuntimeError(f"pull request file list exceeded {MAX_FILE_PAGES * 100} files")


def current_owner_approval(event: dict[str, Any]) -> bool:
    repository = event["repository"]["full_name"]
    number = event["pull_request"]["number"]
    head_sha = event["pull_request"]["head"]["sha"]
    reviews = github_get(f"/repos/{repository}/pulls/{number}/reviews?per_page=100")
    return any(
        review.get("user", {}).get("login", "").lower() == CODE_OWNER.lower()
        and review.get("state") == "APPROVED"
        and review.get("commit_id") == head_sha
        for review in reviews
    )


def main() -> int:
    event = load_event()
    protected = sorted(path for path in changed_files(event) if is_protected(path))
    if not protected:
        print("No protected files changed.")
        return 0
    print("Protected files changed:")
    print("\n".join(f"- {path}" for path in protected))
    if current_owner_approval(event):
        print(f"Current approval from @{CODE_OWNER} found.")
        return 0
    print(f"Approval from @{CODE_OWNER} on the current commit is required.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
