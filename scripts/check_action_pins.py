"""Require GitHub Actions to use immutable commit references."""

from pathlib import Path
import re
import sys


ACTION_RE = re.compile(r"^\s*uses:\s*([^\s#]+)")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def main() -> int:
    workflow_dir = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    failures: list[str] = []

    for workflow in sorted(workflow_dir.glob("*.y*ml")):
        for line_number, line in enumerate(workflow.read_text().splitlines(), 1):
            match = ACTION_RE.match(line)
            if match is None:
                continue

            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if "@" not in reference:
                failures.append(f"{workflow}:{line_number}: missing action ref: {reference}")
                continue

            action, version = reference.rsplit("@", 1)
            if not SHA_RE.fullmatch(version):
                failures.append(
                    f"{workflow}:{line_number}: {action} must use a 40-character commit SHA"
                )

    if failures:
        print("Mutable GitHub Actions references found:")
        print("\n".join(failures))
        return 1

    print("All GitHub Actions use commit SHA references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
