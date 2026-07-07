# keeplix 本地开发命令。无 just/docker 也可用：make dev / make test / make lint。
# （可选）装了 just 可用 justfile，效果等价。

BACKEND := backend
FRONTEND := frontend
PY := cd $(BACKEND) && uv run python
UV := cd $(BACKEND) && uv run

.PHONY: help install dev dev-be dev-fe test lint typecheck migrate db reset

help:
	@echo "keeplix 常用命令:"
	@echo "  make install   装前后端依赖"
	@echo "  make dev       同时起前后端（前台）"
	@echo "  make dev-be    只起后端 :8000"
	@echo "  make dev-fe    只起前端 :3000"
	@echo "  make migrate   应用数据库迁移"
	@echo "  make test      跑后端测试"
	@echo "  make lint      ruff + mypy + 前端 build 检查"

install:
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm install

migrate:
	$(UV) alembic upgrade head

db: migrate

reset:
	cd $(BACKEND) && rm -f keeplix.db && $(UV) alembic upgrade head

dev-be:
	cd $(BACKEND) && uv run uvicorn keeplix.main:app --reload --port 8000

dev-fe:
	cd $(FRONTEND) && npm run dev

# 同时起前后端（前台）。需要的话各自另开终端用 dev-be / dev-fe。
dev:
	@echo "请分别在两个终端运行: make dev-be  与  make dev-fe"

test:
	$(UV) pytest -q

lint:
	$(UV) ruff check keeplix tests
	$(UV) mypy keeplix || true
	cd $(FRONTEND) && npm run build

typecheck:
	cd $(FRONTEND) && npx tsc --noEmit
