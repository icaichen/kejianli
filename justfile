# 可选：装了 just (https://github.com/casey/just) 可用这些命令。等价于 Makefile。
# 未装 just 时用 make ... 即可。

backend := "backend"
frontend := "frontend"

default:
    @just --list

install:
    cd {{backend}} && uv sync
    cd {{frontend}} && npm install

migrate:
    cd {{backend}} && uv run alembic upgrade head

reset:
    cd {{backend}} && rm -f keeplix.db && uv run alembic upgrade head

dev-be:
    cd {{backend}} && uv run uvicorn keeplix.main:app --reload --port 8000

dev-fe:
    cd {{frontend}} && npm run dev

dev:
    ./scripts/dev.sh

test:
    cd {{backend}} && uv run pytest -q

lint:
    cd {{backend}} && uv run ruff check keeplix tests
    cd {{frontend}} && npm run build

tracking-due:
    cd {{backend}} && uv run python -m keeplix.jobs.tracking
