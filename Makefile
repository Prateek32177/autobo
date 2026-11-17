.PHONY: setup start stop status doctor runtime dashboard test test-runtime test-dashboard test-sdk build-dashboard dev

setup:
	./scripts/setup.sh

start:
	./scripts/start.sh

stop:
	./scripts/stop.sh

status:
	./scripts/status.sh

doctor:
	./scripts/doctor.sh

# Back-compat alias
dev: start

runtime:
	cd runtime && . .venv/bin/activate && PYTHONPATH=.. python -m physical_ai

dashboard:
	cd apps/dashboard && npm run dev -- --port 3000

test: test-runtime test-dashboard test-sdk

test-runtime:
	cd runtime && . .venv/bin/activate && PYTHONPATH=.. pytest -q

test-dashboard:
	cd apps/dashboard && npm test

test-sdk:
	cd runtime && . .venv/bin/activate && pytest -q ../sdk/python/tests

build-dashboard:
	cd apps/dashboard && npm run build
