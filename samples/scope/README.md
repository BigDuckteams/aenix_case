# Фикстуры scope

Минимальные программы по строкам таблицы покрытия [04 § 9](../../docs/04-code-graph-model.md#9-покрытие-java-scope): по одной на строку. Каждая читает данные из `stdin`, печатает результат и имеет не меньше двух сценариев. `expected_kinds.json` перечисляет виды блоков, которые обязаны появиться в блок-схемах (проверяет `test_scope_matrix.py` с S2).

Состояние: первый проход (S1.6) — по одной фикстуре на строку; конструкции добавляются по ходу S2, когда разбор покажет пробелы. Разделы 1–4 нужны к H6, бонусный — к H12.

## Раздел 1. Язык и `java.lang`

| Фикстура | Что демонстрирует | Сценариев |
|---|---|---|
| `01-arrays` | Массивы: одномерные, двумерные, ступенчатые, инициализаторы | 3 |
| `01-classes` | Пользовательские классы: поля, конструктор, методы, несколько типов в файле | 3 |
| `01-control` | if/else if/else, switch (оператор и выражение), стрелочный case, yield | 3 |
| `01-ctors` | Конструкторы, this(...), super(...), блоки инициализации | 3 |
| `01-expr` | Выражения: арифметика, логика, сравнения, приведение, тернарный, битовые, составные | 3 |
| `01-fields` | Поля: static, final, константы, значения по умолчанию | 3 |
| `01-inheritance` | Наследование: abstract, super, @Override, полиморфизм | 3 |
| `01-interfaces` | Интерфейсы: абстрактные, default и static методы, несколько реализаций | 3 |
| `01-jumps` | break, continue, return, переходы по меткам | 3 |
| `01-lang` | java.lang: Object, String, StringBuilder, Math, System, Integer/Long/Double/Character/Boolean | 3 |
| `01-loops` | Циклы: for, for each, while, do-while, метки | 3 |
| `01-methods` | Методы: перегрузка, static, varargs, рекурсия | 3 |
| `01-nested` | Вложенные, внутренние, локальные и анонимные классы | 3 |
| `01-try` | try/catch/finally, multi-catch, throw, try-with-resources | 3 |
| `01-types` | Примитивы, обёртки, автобоксинг, приведение типов, переполнение | 3 |

## Раздел 2. Консольный ввод-вывод

| Фикстура | Что демонстрирует | Сценариев |
|---|---|---|
| `02-charsets` | Кодировки: StandardCharsets.UTF_8, PrintStream с UTF-8, байты и строки | 3 |
| `02-format` | Форматирование: String.format, printf, Formatter, спецификаторы | 3 |
| `02-output` | Вывод: print, println, printf, System.err | 3 |
| `02-reader` | BufferedReader(InputStreamReader(System.in, UTF-8)): readLine до конца ввода | 3 |
| `02-scanner` | Scanner: nextInt, nextDouble, next, nextLine, hasNext* | 3 |

## Раздел 3. Коллекции `java.util`

| Фикстура | Что демонстрирует | Сценариев |
|---|---|---|
| `03-comparator` | Comparator: comparing, thenComparing, reversed, лямбды, компаратор-класс | 3 |
| `03-factories` | Фабрики List.of, Set.of, Map.of, copyOf и неизменяемость | 3 |
| `03-iter` | Iterable и Iterator: явный итератор с remove, for each по своему Iterable | 3 |
| `03-list` | List: ArrayList и LinkedList, add/get/set/remove/contains/indexOf/subList/sort | 3 |
| `03-map` | Map: HashMap, TreeMap, LinkedHashMap; get, put, getOrDefault, merge, computeIfAbsent, entrySet | 3 |
| `03-optional` | Optional: of, empty, ofNullable, map, filter, orElse, ifPresent | 3 |
| `03-set` | Set: HashSet, LinkedHashSet, TreeSet и их операции | 3 |
| `03-utils` | Collections и Arrays: sort, max, reverse, unmodifiableList, fill, asList, copyOf, equals | 3 |

## Раздел 4. Исключения

| Фикстура | Что демонстрирует | Сценариев |
|---|---|---|
| `04-checked` | Проверяемые и непроверяемые исключения; обязательный catch | 3 |
| `04-custom` | Собственные исключения: проверяемые и непроверяемые, цепочки причин | 3 |
| `04-jdk` | Типовые исключения JDK: NumberFormat, InputMismatch, NoSuchElement, IllegalArgument, Arithmetic, NullPointer, IndexOutOfBounds | 4 |
| `04-throws` | throws в сигнатурах, цепочка вызовов, обработка на верхнем уровне | 3 |
| `04-uncaught` | Необработанное исключение: аварийное завершение с кодом 1 | 3 |

## Бонусный scope

| Фикстура | Что демонстрирует | Сценариев |
|---|---|---|
| `b1-enum` | enum: поля, конструкторы, методы, тела констант, values/valueOf, switch, EnumMap | 3 |
| `b1-record` | record: компактный конструктор, методы, статические члены, вложенные record | 3 |
| `b2-generics` | Дженерики: классы, методы, интерфейсы, ограничения, wildcard, diamond | 3 |
| `b3-lambda` | Лямбды, java.util.function, ссылки на методы, замыкания | 3 |
| `b4-stream` | Stream API и Collectors: конвейеры filter/map/sorted/distinct/limit/reduce/collect | 3 |
