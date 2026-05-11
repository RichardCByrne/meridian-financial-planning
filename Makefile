# Convenience targets. Most useful from a unix-like shell — Windows users can
# invoke the underlying commands directly.

PROJECT       ?= meridian
REGION        ?= europe-west1
REPO          ?= meridian
SERVICE       ?= meridian-api
IMAGE          = $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)/$(SERVICE)

.PHONY: test test-backend test-frontend build-backend deploy-backend deploy-frontend

test: test-backend test-frontend

test-backend:
	cd backend && .venv/bin/python -m pytest

test-frontend:
	cd frontend && npm run lint && npm run build

build-backend:
	docker build -t $(IMAGE):dev backend

# One-shot manual deploy (CI prefers cloudbuild.yaml).
deploy-backend:
	gcloud builds submit --config cloudbuild.yaml \
		--substitutions _REGION=$(REGION),_REPO=$(REPO),_SERVICE=$(SERVICE),_CLOUD_SQL_INSTANCE=$(CLOUD_SQL_INSTANCE)

deploy-frontend:
	cd frontend && npm run build && firebase deploy --only hosting
