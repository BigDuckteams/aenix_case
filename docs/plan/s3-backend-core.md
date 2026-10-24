# S3. Backend: проекты, версии, сборка, запуск

**Часы:** H6–16 · **Трек:** B (Backend/Runtime) · **Веха:** M1 · **Требования:** FR-01, FR-08, FR-09, FR-10, FR-19

## Цель

Дать frontend рабочий API: импорт проекта, версии и файлы, граф, сборка `javac`, запуск `java` с лимитами и потоком событий. Это основа, на которую ложатся правка (S5) и проверка поведения (S6).

## Зависимости

S0.2–S0.3, S1.1 (схемы). Эндпоинты графа подключаются к engine из S2 по мере готовности (до этого — заглушки на моках).

## Задачи

| ID | Задача | Ч | Результат и тесты |
|---|---|---|---|
| S3.1 | `services/projects.py`, `services/versions.py`: создание проекта и версии (`origin`, `parent_id`, `content_hash`), HEAD, хранение файлов; хеш содержимого | 1 | Тесты: создание, цепочка версий |
| S3.2 | **Импорт** (`POST /projects`): multipart `.java`/`.zip`, JSON с текстом, `sample_id`; защита от zip-slip и лимиты ([08 § 11](../08-api.md#11-лимиты-и-безопасность)); UTF-8/BOM; определение `main`-классов; разбор и список синтаксических ошибок; `GET /samples`, `GET/PATCH/DELETE /projects` | 1,5 | Тесты: каждый способ импорта, zip-slip, не-UTF-8, несколько main |
| S3.3 | **Версии и файлы:** `versions`, `restore`, `undo`, `redo`, `files` (GET/PUT/POST/DELETE; схлопывание подряд идущих `code_edit`), `diff`, `parse` (живой разбор без сохранения), `export/source` (файл/zip) | 1,5 | Тесты API; zip компилируется `javac` |
| S3.4 | `engine/runtime/workspace.py`, `compiler.py`: материализация версии в `builds/<hash>/src`, `javac --release 21 -encoding UTF-8 -g -Xlint:all`, разбор диагностик (`file:line:col`), кеш по хешу, таймаут; `POST /build` | 1,5 | Тесты: успех, ошибка с позицией, кеш-попадание, кириллица в сообщениях |
| S3.5 | `engine/runtime/runner.py`: `java` с флагами кодировок и локали ([07 § 2.3](../07-behavior-verification.md#23-запуск)), stdin из строки, аргументы, лимиты вывода (обрезка + флаг), таймаут, **убийство дерева процессов** (Windows `taskkill /T`, Linux — группа процессов), `setrlimit` на Linux, разбор необработанного исключения, пользователь `runner` в контейнере | 2 | Тесты: кириллица во вводе/выводе, таймаут, `while(true)`, большой вывод, исключение, код выхода, `System.exit(3)` |
| S3.6 | `jobs/run_manager.py`: реестр задач asyncio, семафор по `JB_MAX_PARALLEL_RUNS`, буфер событий (replay), отмена; `POST /projects/{id}/runs` (`kind=run`), `GET /runs/{id}`, `GET /runs/{id}/events` (SSE через `sse-starlette`, heartbeat), `POST /runs/{id}/cancel`; пометка «прерван перезапуском» при старте | 2 | Тесты: поток событий, replay, отмена, очередь при превышении параллелизма |
| S3.7 | Подключение engine: `GET /structure`, `/flow`, `/tree`, `/nodes/{id}`, `/locate` (кеш по `content_hash`); пока S2 не готов — отдача фикстур | 1 | Контрактные тесты по схемам S1 |
| S3.8 | Сквозные API-тесты и обработка ошибок ([02 § 8](../02-architecture.md#8-обработка-ошибок)); единый формат ошибок; логирование с `request_id` | 0,75 | Сквозной тест «импорт → граф → запуск → вывод» |
| S3.9 | Сидирование демо (`JB_SEED_DEMO`): создание проекта `demo-orders` при старте | 0,25 | Проект появляется на чистой БД |

Порядок: S3.1 → S3.2 → S3.3 (параллельно S3.4 → S3.5 → S3.6) → S3.7 → S3.8.

## Артефакты

- `backend/app/{api,services,jobs}`, `backend/engine/runtime/*`.
- Тесты `integration/` с JDK (метка `jdk`).

## Статус выполнения

| Задача | Состояние | Примечание |
|---|---|---|
| S3.1 Сервисы проектов и версий | ✅ | `services/projects.py`, `services/versions.py`: создание проекта и версии (`origin`, `parent_id`, `content_hash`), HEAD, файлы версии, схлопывание подряд идущих `code_edit` в HEAD без потомков, `409 VERSION_CONFLICT` по `base_version_id`, удаление проекта со всеми данными |
| S3.2 Импорт | ✅ | `POST /projects`: multipart (`files[]` или `archive`), JSON с текстом, `sample_id`; `services/importing.py`: нормализация путей (zip-slip, абсолютные, диск `C:`), только `.java`, UTF-8 с удалением BOM, файл ≤ 2 МБ, архив ≤ 10 МБ (и ≤ 50 МБ распакованного), ≤ 200 файлов, дубли; `main`-классы и синтаксические ошибки в ответе. `GET /samples`, `GET/PATCH/DELETE /projects`. Импорт `demo-orders` ≈ 30 мс |
| S3.3 Версии и файлы | ✅ | `versions`, `versions/{id}`, `restore` (версия `revert`), `undo`, `redo`, `files` (GET/PUT/POST/DELETE), `diff` (unified + тексты сторон), `parse` (живой разбор без сохранения), `export/source` (zip `src/…`, воспроизводимый побайтно, или один файл). Zip компилируется `javac` (тест с меткой `jdk`) |
| S3.4 Сборка | ✅ | Движок: `workspace.py`, `compiler.py`; API: `POST /build` (HEAD или `version_id`), диагностики с `node_id` (самый глубокий блок графа под позицией), `cached` |
| S3.5 Запуск | ✅ | `engine/runtime/runner.py`: флаги кодировок и локали, чистое окружение, stdin из строки, лимит вывода с обрезкой, таймаут, отмена, убийство дерева процессов, разбор необработанного исключения. `setrlimit` и `killpg` (Linux) написаны, но локально не выполнялись — их проверит CI. **Исправлено:** на Windows `println` печатал `
` — добавлен `-Dline.separator=<LF>` |
| S3.6 `RunManager` и SSE | ✅ | `jobs/run_manager.py`: задачи asyncio, семафор по `JB_MAX_PARALLEL_RUNS`, очередь (сверх лимита — `429 BUSY`), буфер событий с replay и `Last-Event-ID`, отмена (в очереди — мгновенно, на ходу — убийство JVM), пометка «прерван перезапуском» при старте, восстановление событий из БД после перезапуска. `jobs/handlers.py`: вид `run`. `POST /projects/{id}/runs`, `GET /runs/{id}`, `GET /runs/{id}/events`, `POST /runs/{id}/cancel`, `GET /projects/{id}/runs`. Остальные виды запусков отвечают `501` до S6 |
| S3.7 Эндпоинты графа | ✅ | `structure` (types/methods/deps), `flow`, `tree`, `nodes/{id}` и `nodes/lookup`, `locate`; кеш движка по `content_hash`; граф по любой версии (`version_id`) |
| S3.8 Сквозные тесты | ✅ | Сквозной тест «импорт → граф → запуск → вывод» на `demo-orders` по трём сценариям корпуса (вывод побайтно совпадает с эталоном); единый формат ошибок и `request_id` — с S1 |
| S3.9 Сидирование демо | ✅ | `JB_SEED_DEMO=1`: проект «Demo: заказы» из `samples/demo-orders` с 11 сценариями на пустой БД; повторный старт ничего не делает |

Решения:

- Запуск синхронный и потоковый (`subprocess` + потоки чтения), а не `asyncio.create_subprocess_exec`: так он не зависит от политики цикла событий (на Windows `uvicorn --reload` использует селекторный цикл без подпроцессов). `RunManager` вызывает его через `asyncio.to_thread`.
- Вывод программы приходит в SSE событиями `log` **после** завершения запуска (чанками по 8 КБ), а не по мере печати: раннер собирает вывод целиком. Живой вывод — улучшение к S4/S6, если понадобится для долгих сценариев.
- Целевой уровень `--release 21`; на более старом JDK берётся версия самого JDK. Проверено на JDK 17, на JDK 21 — в джобе `backend-jdk`.
- Вердикт запуска `run`: `PASS` — код 0; `FAIL` — ненулевой код или необработанное исключение; `TIMEOUT`; `ERROR` — лимит вывода или внутренняя ошибка. Статус запуска `done` — программа отработала (вердикт в элементе), `failed` — не собралась, `error` — сбой запуска, `cancelled` — отмена.
- В таблицу `run_item` добавлена колонка `name` (у запуска `run` нет сценария). БД создаётся `create_all` без миграций: старую локальную `data/app.db` нужно удалить.
- Нет JDK на сервере → `503 JDK_UNAVAILABLE` (сборка) или статус запуска `error` с событием `error`.
- Тесты API: `backend/tests/integration/test_{projects,versions,graph,export,run_manager,seeding}_api.py` без JDK и `test_runs_api.py` с меткой `jdk`; `test_runtime.py` — движок. Локально: `JB_JAVA_HOME=<путь к JDK> uv run pytest`.

## Критерии выхода

- [x] Импорт `demo-orders` любым способом ≤ 2 с; `main`-класс определён (≈ 10–30 мс).
- [x] `javac` собирает версию; ошибки с позицией; повторная сборка с тем же хешем мгновенная (`cached: true`).
- [x] `java` запускает программу с кириллицей во вводе и выводе; таймаут и лимиты работают; дерево процессов убивается. Проверено на Windows и JDK 17; **Docker и Linux — не проверены** (CI).
- [x] SSE: события `log`, `result`, `done`; поздний подписчик получает replay.
- [x] Версии: undo/redo, restore, diff; экспорт zip компилируется `javac`.
- [x] Эндпоинты графа отвечают на `demo-orders` на реальном engine.

## Остаётся проверить

- JDK 21 и Linux: джоб `backend-jdk` в CI, ветки `setrlimit`/`killpg`, сборка Docker-образа.
- `test_health_ok_with_installed_jdk` и `test_jdk.py` требуют JDK 21+ в `PATH`: локально (JDK 17 вне `PATH`) падают по замыслу.
