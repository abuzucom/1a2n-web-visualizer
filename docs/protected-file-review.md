# Protected File Review

Protected files require the trusted `Protected file review` check.

## Owner PRs

Pull requests authored by `@itsjustatank` pass the owner-approval portion of
the check after the protected-file and CI checks pass. GitHub does not allow a
user to approve their own pull request.

## Agent PRs

Agents should open pull requests using a separate bot or GitHub App identity,
not `@itsjustatank`'s personal token. Protected-file changes from another
identity require an approval from `@itsjustatank` on the current commit.

The workflow runs from `pull_request_target`, checks out only the trusted
default branch, and never executes code from the pull request branch.

## Branch Settings

Require pull requests and the protected-file status check on `develop`. Do not
enable GitHub's global code-owner approval requirement for this single-owner
repository, because it would make owner-authored pull requests unmergeable.
