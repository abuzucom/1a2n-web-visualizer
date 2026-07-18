# Jira Integration

GitHub Actions links pull requests and successful GitHub Pages deployments to
Jira Cloud at `https://abuzucom.atlassian.net`, using project `VID`.

## Secrets

Add these repository or organization secrets:

- `JIRA_EMAIL`: Atlassian account email used by the API token
- `JIRA_API_TOKEN`: Atlassian API token with permission to browse, comment on,
  create, and add remote links to `VID` issues, plus deployment permission

The workflows skip cleanly when either secret is absent, which keeps pull
requests from forks from failing.

## Issue Linking

The pull request workflow runs only after a maintainer applies the `needs-jira`
label. It searches the branch name, title, body, and commit messages for keys
such as `VID-123`. It adds a remote link and an idempotent status comment to
each matching issue.

If no issue key is present, it does nothing unless a maintainer also applies
the `jira-create` label. With both labels present, it creates a `Task` in `VID`
with the `github-pr` label, then links the pull request to the new issue.

Maintainer process:

1. Review the PR and confirm the intended Jira issue or title.
2. Apply `needs-jira` to enable synchronization.
3. Add `jira-create` only when creating a new Jira Task is explicitly desired.
4. Remove `needs-jira` to stop future PR synchronization.

The PR workflow uses `pull_request_target` but checks out only the trusted
default branch. It never executes code from the PR branch with Jira secrets.

## Deployments

The Pages deployment workflow publishes a successful deployment record to
Jira's deployment API. It associates the deployment with any `VID-*` keys in
the deployment commit message or ref.
