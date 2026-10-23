# Сломанные файлы

Устойчивость разбора и сборки. Первая строка каждого файла — `// broken: syntax` или `// broken: semantic`.

| Файл | Дефект | Ожидание |
|---|---|---|
| `MissingSemicolon.java` | нет `;` после `return value * 2` | tree-sitter находит `MISSING`/`ERROR`; граф `total` и `main` строится; `javac` падает |
| `UnbalancedBraces.java` | не закрыта фигурная скобка `if` | tree-sitter находит `ERROR`; остальные методы доступны; `javac` падает |
| `TypeMismatch.java` | несовместимые типы и неизвестное имя | синтаксис корректен, ошибки только у `javac` (стадия `compile` gate) |

`scripts/verify_corpus.py` проверяет, что `javac` на каждом из этих файлов падает.
