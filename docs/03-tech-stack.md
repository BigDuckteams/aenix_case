# 03. Стек, библиотеки и решения

Точные версии фиксируются lock-файлами (`uv.lock`, `pnpm-lock.yaml`) на этапе S0. Ниже — мажорные версии и назначение.

## 1. Стек

| Слой | Технология | Зачем |
|---|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn | Требование стека; async для фоновых запусков и SSE |
| Разбор Java | py-tree-sitter + tree-sitter-java | CST с точными диапазонами; переживает ошибки синтаксиса; поддерживает Java 21 (record, sealed, switch-выражения, лямбды, дженерики) |
| Исполнение Java | JDK 21 (Eclipse Temurin) | `javac` и `java` для сборки, запуска, gate и трассировки |
| Хранение | SQLite + SQLModel | Решение пользователя: один файл, без отдельного сервиса |
| Frontend | Next.js (App Router) + React 19 + TypeScript | Требование стека |
| UI-кит | shadcn/ui + Tailwind CSS v4 + lucide-react | Требование стека; тёмная тема по макету |
| Граф | `@xyflow/react` (React Flow 12) + `elkjs` | Кастомные узлы, вложенные контейнеры (циклы, try), иерархическая раскладка |
| Редактор кода | Monaco (`@monaco-editor/react`) | Подсветка Java, декорации, маркеры, встроенный diff-редактор |
| Инфраструктура | Docker, Docker Compose | Воспроизводимая сборка для сдачи |

## 2. Backend-библиотеки

| Пакет | Назначение |
|---|---|
| `fastapi`, `uvicorn[standard]` | HTTP API |
| `pydantic` v2, `pydantic-settings` | Схемы API и engine; конфигурация из env |
| `sqlmodel` | ORM поверх SQLAlchemy для SQLite |
| `tree-sitter`, `tree-sitter-java` | Разбор Java. **Важно:** API py-tree-sitter менялся между версиями 0.2x (`Language`, `Query`, `QueryCursor`). Обёртку пишем в одном модуле `engine/java/ts.py` и фиксируем версию |
| `networkx` | Графы вызовов и зависимостей членов; кластеризация Louvain для декомпозиции |
| `sse-starlette` | Server-Sent Events |
| `python-multipart` | Загрузка файлов |
| stdlib `difflib`, `hashlib`, `zipfile`, `asyncio.subprocess`, `resource` | Diff, хеши, архивы (с защитой от zip-slip), подпроцессы, лимиты |
| `pytest`, `pytest-asyncio`, `httpx2` | Тесты (`httpx2` — клиент, который Starlette `TestClient` требует вместо устаревшего `httpx`) |
| `ruff` | Линтер и форматтер |
| `mypy` (желательно) | Статическая типизация engine |

## 3. Frontend-библиотеки

| Пакет | Назначение |
|---|---|
| `next`, `react`, `react-dom`, `typescript` | Основа |
| `tailwindcss` v4, shadcn/ui (CLI `shadcn`) | Компоненты: Button, DropdownMenu, Tabs, Resizable, ScrollArea, Input, Textarea, Badge, Card, Dialog, Sheet, Tooltip, Command, ContextMenu, Progress, Table, Select, Collapsible, Alert, Skeleton, Sonner, Chart |
| `lucide-react` | Иконки блоков и панелей |
| `@xyflow/react` | Холст графа |
| `elkjs` | Раскладка (layered, иерархия), в Web Worker |
| `@monaco-editor/react` | Редактор и diff |
| `@tanstack/react-query` v5 | Серверное состояние, кеш, инвалидация |
| `zustand` v5 | Клиентское состояние рабочей области |
| `openapi-typescript`, `openapi-fetch` | Типы и клиент, сгенерированные из OpenAPI FastAPI |
| `react-hook-form`, `zod` | Формы инспектора узла (через shadcn Form) |
| `react-dropzone` | Импорт файлов перетаскиванием |
| `recharts` (через shadcn Chart) | Графики бенчмарка и роста сложности |
| `vitest`, `@testing-library/react` | Модульные тесты |
| `@playwright/test` | E2E демо-пути |
| `eslint` (конфиг Next), `prettier` | Качество кода |

## 4. Инструменты разработки

| Инструмент | Назначение |
|---|---|
| `uv` | Менеджер Python-зависимостей и окружений (`uv sync`, `uv run`) |
| `pnpm` | Менеджер Node-зависимостей |
| Node.js 22 LTS | Среда frontend |
| GitHub Actions | CI: ruff + pytest, eslint + vitest + build |

## 5. Принятые решения (ADR)

### ADR-01. Разбор Java: tree-sitter-java в Python *(решение пользователя)*

- **Контекст.** Нужны разбор и обратная генерация кода из графа, анализ, декомпозиция. Стек backend — Python.
- **Решение.** py-tree-sitter + tree-sitter-java. Семантическую модель (символы, области видимости, вызовы) пишем сами.
- **Альтернативы.** JavaParser в отдельном Java-сервисе: точнее разрешает символы, но добавляет второй язык и ещё один сервис. javalang: только Java 8, бонусный scope не закрыть.
- **Последствия.** Разрешение вызовов идёт по имени, числу аргументов и (по возможности) статическому типу получателя — для монолита на 1000 строк этого достаточно. Перегрузки с одинаковым числом параметров разрешаем по типам литералов и объявленных переменных, при неоднозначности — консервативно (все кандидаты). Окончательную корректность проверяет `javac` в quality gate.

### ADR-02. Код — источник истины, граф — проекция

- **Решение.** Граф не хранится. Каждая операция над графом превращается в `TextEdit` по диапазонам CST, после чего файл перепарсивается.
- **Почему.** Нет рассинхронизации и сложного merge; форматирование и комментарии сохраняются; round-trip без правок тривиально точен.
- **Последствия.** ID узлов вычисляются из структурного пути (см. [04 § 5.3](04-code-graph-model.md#53-идентификаторы-узлов)); после операции backend возвращает `focus_node_id`.

### ADR-03. Без LLM *(решение пользователя)*

- **Решение.** Все «интеллектуальные» функции детерминированы:
  - объяснения находок — шаблоны с подставленными фактами (имена, числа, строки);
  - оптимизации — каталог автоисправлений с формальными предусловиями;
  - сценарии — вывод формата ввода + словарь констант из кода + мутации с обратной связью по покрытию;
  - декомпозиция — лексикон ролей + граф зависимостей членов + Louvain с фиксированным seed;
  - имена выделенных методов и классов — эвристики, пользователь может переименовать.
- **Последствия.** Результат воспроизводим и объясним. Набор оптимизаций ограничен каталогом; для остального даются рекомендации без автоисправления.

### ADR-04. SQLite + SQLModel *(решение пользователя)*

- **Решение.** Один файл БД в томе `/data`, `create_all` без миграций, WAL.
- **Последствия.** Один процесс backend; схема меняется пересозданием БД (на хакатоне допустимо).

### ADR-05. Golden master на уровне программы

- **Контекст.** Контракт кейса — сохранение поведения программы.
- **Решение.** Поведение = нормализованный stdout/stderr + код выхода + тип и сообщение необработанного исключения на наборе сценариев. Эталон записывается на «Оригинале».
- **Альтернативы.** Модульные тесты методов: сигнатуры и расположение методов меняются при декомпозиции, а для пользовательских типов нужна генерация объектов. Для контракта кейса это не нужно: наблюдаемое поведение проверяется на уровне программы.
- **Последствия.** Качество проверки зависит от сценариев, поэтому генератор сценариев с покрытием узлов — обязательная часть MVP, а покрытие показывается пользователю.

### ADR-06. Java выполняется подпроцессами в контейнере backend

- **Решение.** JDK 21 копируется в образ backend (multi-stage из `eclipse-temurin:21-jdk`). Запуски — `asyncio.create_subprocess_exec` с лимитами, от пользователя `runner`.
- **Альтернатива.** Отдельный sandbox-контейнер на запуск (docker-in-docker): старт медленнее, нужен доступ к Docker socket. Для доверенного входа избыточно.

### ADR-07. React Flow + ELK для графа

- **Решение.** `@xyflow/react` с кастомными узлами; `elkjs` (layered, `hierarchyHandling: INCLUDE_CHILDREN`) для блок-схем с вложенными контейнерами, как в макете.
- **Альтернативы.** dagre не умеет составные узлы; Rete.js заточен под «порты-сокеты» и хуже подходит для блок-схемы из макета.

### ADR-08. Monaco для кода

- **Решение.** Monaco: подсветка Java, `deltaDecorations` для выделения узла, `setModelMarkers` для находок и ошибок компиляции, `DiffEditor` для сравнения с оригиналом.
- **Альтернатива.** CodeMirror 6 легче, но diff и маркеры пришлось бы собирать самим.

### ADR-09. Фоновые задачи на asyncio + SSE

- **Решение.** In-process `RunManager`; поток событий — SSE.
- **Альтернативы.** Celery/RQ + Redis — лишняя инфраструктура. WebSocket нужен только для интерактивного stdin, а stdin у нас задаётся заранее.

### ADR-10. Типизированный контракт из OpenAPI

- **Решение.** Pydantic-схемы → OpenAPI FastAPI → `openapi-typescript` → `openapi-fetch`. Скрипт `pnpm gen:api`.
- **Почему.** Один источник правды для контракта; frontend можно начинать на моках с теми же типами (contract-first).

### ADR-11. Кодировки и координаты

- **Решение.** Внутри engine — байтовые смещения tree-sitter (UTF-8). На границе API все диапазоны переводятся в `{line, column}` (строки с 1, колонки в UTF-16 с 1) — как в Monaco. Кириллица в строках и комментариях иначе сдвигает подсветку.
- **Запуск:** `javac -encoding UTF-8`; `java -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`; `LANG=C.UTF-8` в контейнере.

### ADR-12. Фиксированная локаль запуска

- **Решение.** `-Duser.language=en -Duser.country=US -Duser.timezone=UTC` (настраивается в проекте).
- **Почему.** `String.format("%.2f")` зависит от локали (`3,14` против `3.14`). Эталон и проверка запускаются с одинаковой локалью, иначе тесты нестабильны.

## 6. Структура репозитория

```
/
├── README.md                    # что это, как запустить (комплект сдачи 01)
├── SOLUTION.md                  # описание решения (комплект сдачи 04)
├── docker-compose.yml
├── .github/workflows/ci.yml
├── docs/                        # эта документация
├── samples/                     # корпус Java-примеров (см. 10-quality-and-testing.md)
│   ├── demo-orders/             # демо-монолит ≈1000 строк + scenarios/
│   ├── analyzer-pairs/          # пример со слайда 5
│   └── scope/                   # фикстуры по разделам scope
├── reports/                     # экспортированные отчёты проверки поведения (комплект сдачи 03)
├── backend/
│   ├── pyproject.toml, uv.lock, Dockerfile
│   ├── app/
│   │   ├── main.py              # create_app()
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── api/                 # роутеры
│   │   ├── services/
│   │   ├── jobs/
│   │   ├── db/
│   │   └── schemas/             # Pydantic-схемы API
│   ├── engine/
│   │   ├── java/                # ts.py, cst.py, semantic.py, symbols.py, purity.py
│   │   ├── graph/               # structure.py, flow.py, ids.py, ranges.py
│   │   ├── edit/                # ops.py, textedit.py, templates.py, validate.py, indent.py, rename.py
│   │   ├── analysis/            # cost_model.py, complexity.py, rules/, metrics.py, clones.py, findings.py
│   │   ├── transform/           # base.py, fixes/, extract_method.py, decompose/
│   │   ├── runtime/             # workspace.py, compiler.py, runner.py, instrument.py, java/JbTrace.java
│   │   └── verify/              # scenarios.py, normalize.py, baseline.py, compare.py, report.py, generator/, benchmark.py
│   └── tests/                   # unit/, integration/, snapshots/
└── frontend/
    ├── package.json, pnpm-lock.yaml, next.config.ts, components.json, Dockerfile
    ├── src/
    │   ├── app/                 # page.tsx, projects/[id]/page.tsx, layout.tsx
    │   ├── components/          # ui/ (shadcn), workspace/, graph/, code/, analysis/, tests/, decompose/
    │   ├── lib/api/             # schema.d.ts (генерируется), client.ts, queries.ts, sse.ts
    │   ├── lib/i18n/ru.ts       # все строки интерфейса
    │   ├── stores/
    │   └── workers/elk.worker.ts
    └── e2e/
```

## 7. Соглашения

- **Язык:** интерфейс и документация на русском; код, идентификаторы и коммиты — на английском (коммиты можно на русском, но единообразно).
- **Python:** `ruff format` + `ruff check`; типизация везде в `engine`; engine не импортирует `app`.
- **TypeScript:** `strict: true`; без `any` в API-слое; все строки UI — в `lib/i18n/ru.ts`.
- **Контракт:** любое изменение схемы API → выгрузка OpenAPI (`python -m app.export_openapi`) → `pnpm gen:api` → коммит `openapi.json` и `schema.d.ts`.
- **Ветки:** trunk-based: короткие ветки `feat/sN-…`, PR в `main`, CI зелёный перед merge.
- **ID в коде и задачах:** требования `FR-xx`, правила `PERF-xx/BUG-xx/MAINT-xx`, преобразования `OPT-xx/FIX-xx/CLEAN-xx/REF-xx`, задачи плана `Sx.y`.

## 8. Фактические версии и отклонения (итоги S0)

Зафиксированы при создании каркаса; уточняют таблицы выше.

| Что | Факт | Комментарий |
|---|---|---|
| tree-sitter | `tree-sitter 0.26.0` + `tree-sitter-java 0.23.5` | API: `Language`, `Parser`, `Query` + `QueryCursor`; спайк зелёный (Java 21: `record`, `enum` с телами, `sealed`, switch-выражения, лямбды, ссылки на методы, дженерики; кириллица, эмодзи, CRLF, табы) |
| Python | цель **3.12** (Docker, CI); на машине разработки 3.14 | `requires-python = ">=3.12"`; `uv.lock` универсальный |
| JDK | цель **21** (Docker, CI); на машине разработки JDK 26 | `javac --release 21` собирает под 21; `/api/health` помечает `degraded`, если JDK старше 21 |
| Node.js / pnpm | цель Node 22 (Docker, CI); локально Node 24, pnpm 12.15 | `packageManager` в `frontend/package.json` |
| Next.js | 16.4.2 (Turbopack), React 19.3, Tailwind CSS 4.3 | Из шаблона отключены `cacheComponents` и `partialPrefetching`: приложение — клиентская рабочая область на TanStack Query, модель Cache Components только усложняет её. Типы маршрутов (`LayoutProps`, `PageProps`) генерирует `next typegen`, он входит в `pnpm typecheck` |
| shadcn/ui | Компоненты скопированы из официального репозитория `shadcn-ui/ui`, `apps/v4/registry/new-york-v4/ui` (стиль new-york, пакет `radix-ui`) | CLI `shadcn init` не смог достучаться до `ui.shadcn.com` (таймаут соединения), поэтому `components.json` и файлы созданы вручную; `lib/utils.ts` — стандартный `cn`. Когда реестр станет доступен, `shadcn add <компонент>` работает как обычно. Импорты `from "cn"` заменены на `@/lib/utils` |
| Шрифты | `@fontsource-variable/inter` и `@fontsource-variable/jetbrains-mono` (с кириллицей) | Вместо `next/font/google`: сборка и Docker не зависят от доступности Google Fonts |
| HTTP-клиент тестов | `httpx2` | Starlette `TestClient` объявил `httpx` устаревшим |
| Docker | Dockerfile и compose написаны, **сборка не проверена** | На машине разработки нет Docker; проверить на чистой машине (S10.7) или раньше |
