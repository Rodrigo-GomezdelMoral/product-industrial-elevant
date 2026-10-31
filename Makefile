PYTHON ?= python
AZURITE = mcr.microsoft.com/azure-storage/azurite:3.37.0@sha256:830430c1da1a2d537e08f3e6764dd1f5ae00cf0346bcaf625b968ec3f0971fd5
COSMOS = mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-EN20261019@sha256:db53613dae19d0a3d5ad50688d14aa6e957af082dafea56b52e1bd3a6b3f1406

.PHONY: install lint type test check emulators serve web

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

type:
	mypy

test:
	pytest -q

check: lint type test

emulators:
	docker run -d --rm --name elevant-azurite -p 10000:10000 $(AZURITE) azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck
	docker run -d --rm --name elevant-cosmos -p 8081:8081 -p 8080:8080 $(COSMOS) --enable-explorer false
	until curl -sf http://localhost:8080/ready > /dev/null; do sleep 2; done

serve:
	ELEVANT_DOUBLES=true $(PYTHON) -m uvicorn app.main:app --reload

web:
	cd web && npm ci && npm run build && npx playwright test
