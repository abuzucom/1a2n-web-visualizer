# make lint covers only the AGENTS.md style checks below, not the app's own
# lint (npm run lint, which runs ESLint and ruff); the two are additive.
.PHONY: sync check lint

sync:
	python3 scripts/sync.py

check:
	python3 scripts/sync.py --check

lint:
	python3 scripts/lint_style.py
	python3 scripts/check_us_spelling.py AGENTS.md
	python3 scripts/check_english_only.py AGENTS.md
