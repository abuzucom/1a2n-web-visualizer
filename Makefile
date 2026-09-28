# make lint covers only the AGENTS.md policy checks below, not the app's own
# lint (npm run lint, which runs ESLint and ruff); the two are additive.
.PHONY: sync check lint test identity changelog

# Overridable so a platform without this name can supply its own:
#   make test PYTHON=py
PYTHON ?= python3

PROSE_FILES = AGENTS.md README.md CHANGELOG.md SECURITY.md \
	docs/template-drift.md docs/repo-guide.md docs/project-orientation.md \
	docs/gate-threat-model.md plan/HANDOFF.md.example

sync:
	$(PYTHON) scripts/sync.py

check:
	$(PYTHON) scripts/sync.py --check

changelog:
	$(PYTHON) scripts/check_changelog.py

lint:
	$(PYTHON) scripts/lint_style.py
	$(PYTHON) scripts/check_us_spelling.py $(PROSE_FILES)
	$(PYTHON) scripts/check_english_only.py $(PROSE_FILES)
	$(PYTHON) scripts/check_hedging.py $(PROSE_FILES)
	$(PYTHON) scripts/check_conflict_markers.py

test:
	$(PYTHON) scripts/run_tests.py

identity:
	$(PYTHON) scripts/check_git_identity.py --advise
