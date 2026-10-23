# Java Blueprints

Визуальная среда программирования для Java: программа показывается одновременно как код и как граф (блок-схема). Инструмент находит дефекты и оценивает сложность по Big O, помогает оптимизировать код и разбить монолит на классы, а после каждого преобразования доказывает автотестами, что поведение сохранилось.

Кейс AXENIX, 48-часовой хакатон. Документация и план разработки — в [docs/](docs/README.md).

**Стек:** Python 3.12 + FastAPI + tree-sitter-java (backend), Next.js + shadcn/ui + React Flow + Monaco (frontend), SQLite, JDK 21 для сборки и запуска Java.

## Быстрый старт

### Docker (рекомендуется)

```bash
docker compose up --build
```

Приложение: <http://localhost:3000>. Наружу открыт только frontend, он проксирует `/api/*` в backend.

### Локально (для разработки)

Нужны Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22+, pnpm и JDK 21+ (`javac` в `PATH`). Проверить окружение:

```bash
python scripts/doctor.py
```

Backend (порт 8000):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Frontend (порт 3000, `/api` проксируется на `localhost:8000`):

```bash
cd frontend
pnpm install
pnpm dev
```

Проверка связки: <http://localhost:3000> показывает состояние сервиса (версия, JDK, БД); то же — `GET http://localhost:8000/api/health`.

### Тесты и проверки

```bash
cd backend  && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
cd frontend && pnpm lint && pnpm typecheck && pnpm test
```

### Контракт API

Схемы API описаны в Pydantic; TypeScript-типы для frontend генерируются из OpenAPI. После изменения схем:

```bash
cd backend  && uv run python -m app.export_openapi ../frontend/openapi.json
cd frontend && pnpm gen:api
```

Обновлённые `frontend/openapi.json` и `frontend/src/lib/api/schema.d.ts` коммитятся; CI проверяет, что они актуальны.

## Структура

```
backend/    FastAPI (app/) и ядро без веб-зависимостей (engine/): разбор Java, граф, правка, анализ, запуск, проверка
frontend/   Next.js, shadcn/ui, граф и редактор
samples/    корпус Java-примеров (демо-монолит, фикстуры scope)
reports/    результаты проверки поведения для сдачи
scripts/    служебные скрипты (doctor.py)
docs/       документация и план разработки
```

## Статус

| Этап | Состояние |
|---|---|
| S0 Каркас и окружение | сделан: backend, frontend, тесты, CI, Dockerfile; спайк tree-sitter-java зелёный. Сборка Docker-образов не проверена (нет Docker на машине разработки) |
| S1–S10 | по [плану](docs/plan/README.md) |
