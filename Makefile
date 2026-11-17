.PHONY: setup runtime dashboard test test-runtime test-dashboard dev

setup:
	./scripts/setup.sh

runtime:
	cd runtime && . .venv/bin/activate && PYTHONPATH=.. python -m physical_ai

dashboard:
	cd apps/dashboard && npm run dev -- --port 3000

dev:
	./scripts/dev.sh

test: test-runtime test-dashboard

test-runtime:
	cd runtime && . .venv/bin/activate && PYTHONPATH=.. pytest -q

test-dashboard:
	cd apps/dashboard && npm test
