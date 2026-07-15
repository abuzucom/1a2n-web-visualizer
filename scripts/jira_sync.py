"""Link GitHub pull requests and deployments to Jira Cloud issues."""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://abuzucom.atlassian.net").rstrip("/")
PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "VID")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH", "")
ISSUE_KEY_RE = re.compile(rf"\b{re.escape(PROJECT_KEY)}-\d+\b", re.IGNORECASE)


def adf_text(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def jira_request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    credentials = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{JIRA_BASE_URL}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira API {method} {path} failed ({error.code}): {detail}") from error


def github_request(path: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def load_event() -> dict[str, Any]:
    if not EVENT_PATH:
        raise RuntimeError("GITHUB_EVENT_PATH is not set")
    with open(EVENT_PATH, encoding="utf-8") as event_file:
        return json.load(event_file)


def issue_keys(values: list[str]) -> set[str]:
    return {match.upper() for value in values for match in ISSUE_KEY_RE.findall(value or "")}


def plain_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(plain_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(plain_text(item) for item in value)
    return str(value) if isinstance(value, str) else ""


def add_remote_link(issue_key: str, pr_url: str, title: str) -> None:
    links = jira_request("GET", f"/rest/api/3/issue/{issue_key}/remotelink") or []
    global_id = f"github-pr:{pr_url}"
    if any(link.get("globalId") == global_id for link in links):
        return
    jira_request(
        "POST",
        f"/rest/api/3/issue/{issue_key}/remotelink",
        {
            "globalId": global_id,
            "object": {"url": pr_url, "title": title},
        },
    )


def add_comment(issue_key: str, marker: str, text: str) -> None:
    comments = jira_request("GET", f"/rest/api/3/issue/{issue_key}/comment?maxResults=100") or {}
    if marker in plain_text(comments):
        return
    jira_request("POST", f"/rest/api/3/issue/{issue_key}/comment", {"body": adf_text(f"{marker}\n{text}")})


def escape_jql(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def find_existing_pr_issue(pr_url: str) -> str | None:
    jql = (
        f'project = {PROJECT_KEY} AND labels = github-pr '
        f'AND description ~ "{escape_jql(pr_url)}"'
    )
    query = urllib.parse.urlencode({"jql": jql, "maxResults": 1, "fields": "key"})
    result = jira_request("GET", f"/rest/api/3/search/jql?{query}") or {}
    issues = result.get("issues", [])
    return issues[0]["key"] if issues else None


def create_issue(pr_url: str, title: str, branch: str) -> str:
    summary = f"[GitHub PR] {title}"[:255]
    description = f"Created from GitHub pull request {pr_url}.\nBranch: {branch}"
    created = jira_request(
        "POST",
        "/rest/api/3/issue",
        {
            "fields": {
                "project": {"key": PROJECT_KEY},
                "summary": summary,
                "description": adf_text(description),
                "issuetype": {"name": "Task"},
                "labels": ["github-pr"],
            }
        },
    )
    return created["key"]


def pr_sync(event: dict[str, Any]) -> None:
    pr = event["pull_request"]
    repository = event["repository"]["full_name"]
    number = pr["number"]
    pr_url = pr["html_url"]
    action = event.get("action", "updated")
    commit_messages = []
    if GITHUB_TOKEN:
        commits = github_request(f"/repos/{repository}/pulls/{number}/commits?per_page=100")
        commit_messages = [commit["commit"]["message"] for commit in commits]
    keys = issue_keys([pr.get("title", ""), pr.get("body", ""), pr["head"]["ref"], *commit_messages])
    if not keys:
        existing = find_existing_pr_issue(pr_url)
        keys = {existing or create_issue(pr_url, pr.get("title", "Untitled PR"), pr["head"]["ref"])}
    state = "merged" if pr.get("merged") else action
    for key in sorted(keys):
        add_remote_link(key, pr_url, f"GitHub PR #{number}: {pr.get('title', 'Untitled PR')}")
        add_comment(key, f"[github-pr:{repository}#{number}:{action}]", f"PR status: {state}\n{pr_url}")
    print(f"Linked PR #{number} to {', '.join(sorted(keys))}")


def deployment_sync(event: dict[str, Any]) -> None:
    commit_message = event.get("head_commit", {}).get("message", "")
    repository = event["repository"]["full_name"]
    sources = [commit_message, event.get("ref", "")]
    commit_sha = os.environ.get("GITHUB_SHA", "")
    if GITHUB_TOKEN and commit_sha:
        pull_requests = github_request(f"/repos/{repository}/commits/{commit_sha}/pulls")
        for pull_request in pull_requests:
            sources.extend([
                pull_request.get("title", ""),
                pull_request.get("body", ""),
                pull_request.get("head", {}).get("ref", ""),
            ])
    keys = sorted(issue_keys(sources))
    run_number = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    run_attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    payload = {
        "deployments": [{
            "deploymentSequenceNumber": run_number,
            "updateSequenceNumber": run_attempt,
            "associations": [{"associationType": "issueKeys", "values": keys}],
            "displayName": "GitHub Pages",
            "description": f"Deploy {os.environ.get('GITHUB_SHA', '')[:12]}",
            "url": os.environ.get("JIRA_DEPLOYMENT_URL", ""),
            "lastUpdated": dt.datetime.now(dt.timezone.utc).isoformat(),
            "state": "successful",
            "pipeline": {
                "id": f"{repository}:deploy",
                "displayName": "Deploy to GitHub Pages",
                "url": f"https://github.com/{repository}/actions",
            },
            "environment": {"id": "github-pages", "displayName": "GitHub Pages", "type": "production"},
        }]
    }
    jira_request("POST", "/rest/deployments/0.1/bulk", payload)
    print(f"Published GitHub Pages deployment for {', '.join(keys) or 'no linked issue'}")


def main() -> int:
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        print("Jira secrets are not configured; skipping Jira sync.")
        return 0
    event = load_event()
    try:
        if sys.argv[1] == "deployment":
            deployment_sync(event)
        else:
            pr_sync(event)
    except (KeyError, RuntimeError, urllib.error.URLError) as error:
        print(f"Jira sync failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
