# Вне рамок кейса

Код с конструкциями, которые инструмент не анализирует и не правит ([04 § 9.3](../../docs/04-code-graph-model.md)), но обязан сохранить, скомпилировать и корректно запустить. Остальной корпус таких конструкций не содержит (`scripts/verify_corpus.py` это проверяет).

| Пример | Что внутри |
|---|---|
| `threads/` | потоки, `ExecutorService`, `synchronized` |
| `time-and-files/` | `java.time`, `java.nio.file` |
| `reflection-and-net/` | рефлексия, `java.net.URI` |
