SHELL := /bin/sh
.DEFAULT_GOAL := help
UV ?= uv
COMPOSE := docker compose --project-name efren-bot
TEST_DATABASE_URL ?= postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test

.PHONY: help lock sync up down logs config lint web-check check test test-db test-unit test-integration test-web demo
.PHONY: bridge-init bridge-up bridge-runner bridge-verify-policy
.PHONY: collection-runner

help:
	@echo "Preparación: make lock | sync | config"
	@echo "Demo local: make up | down | logs | check | test | demo"
	@echo "Antes de make test: make test-db (DB separada 55433/efren_bot_test)"
	@echo "Host: make collection-runner | support-runner | review-runner (ver docs/)"

lock:
	$(UV) lock

sync:
	$(UV) sync --frozen

up:
	$(COMPOSE) up --build --detach --wait --wait-timeout 90

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs --follow --tail=100

config:
	$(COMPOSE) config --quiet

lint:
	$(UV) run --frozen ruff check src tests migrations
	$(UV) run --frozen ruff format --check src tests migrations

web-check:
	npm --prefix apps/web ci
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run build

check: config lint web-check

test: test-unit test-integration test-web

test-db:
	$(COMPOSE) --profile test up --detach --wait --wait-timeout 60 test-db

test-unit:
	$(UV) run --frozen pytest -m "not integration" tests

test-integration:
	DATABASE_URL="$(TEST_DATABASE_URL)" $(UV) run --frozen pytest -m integration tests

test-web:
	npm --prefix apps/web run test -- --run

demo:
	$(COMPOSE) exec -T api python -m efren_bot.demo

bridge-init:
	$(UV) run --frozen python -m efren_bot.bridge.init

bridge-verify-policy:
	$(UV) run --frozen python -m efren_bot.bridge.verify

bridge-up:
	$(UV) run --frozen python -m efren_bot.bridge.preflight
	CLAUDE_BRIDGE_UID="$$(id -u)" CLAUDE_BRIDGE_GID="$$(id -g)" $(COMPOSE) -f compose.yaml -f compose.claude.yaml up --build --detach --wait --wait-timeout 90

bridge-runner:
	CLAUDE_BRIDGE_ENABLED=true CLAUDE_BRIDGE_TOKEN_FILE="$(CURDIR)/.local/bridge/token" CLAUDE_BRIDGE_PROFILE_FILE="$(CURDIR)/.local/bridge/profile.json" $(UV) run --frozen python -m efren_bot.bridge.runner

collection-runner:
	$(UV) run --frozen python -m efren_bot.collection.runner

.PHONY: support-runner
support-runner:
	$(UV) run --frozen python -m efren_bot.support.runner

.PHONY: review-runner
review-runner:
	$(UV) run --frozen python -m efren_bot.review.runner

.PHONY: factory-worker factory-rehearsal
# Host process: pulls sources, runs queued jobs through scraft-ops, performs approved effects.
# Mocked unless FACTORY_* is configured (see docs/factory.md). Never run it in Docker.
FACTORY_PULL ?= slack
FACTORY_ARGS ?=
factory-worker:
	$(UV) run --frozen python -m efren_bot.factory.worker --pull $(FACTORY_PULL) $(FACTORY_ARGS)

# One request by hand through the same funnel: make factory-submit PROJECT=landing TEXT="..."
.PHONY: factory-submit
factory-submit:
	$(UV) run --frozen python -m efren_bot.factory.submit --project "$(PROJECT)" --text "$(TEXT)"

# Rehearsal with the real scraft-ops binary and a FAKE agent: no model, network or credentials.
# Usage: make factory-rehearsal SCRAFT_OPS_BIN=/path/to/scraft-ops
factory-rehearsal:
	SCRAFT_OPS_BIN="$(SCRAFT_OPS_BIN)" DATABASE_URL="$(TEST_DATABASE_URL)" $(UV) run --frozen pytest tests/test_factory_*.py
