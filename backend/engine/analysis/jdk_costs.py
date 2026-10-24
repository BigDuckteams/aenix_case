"""Каталог стоимости методов JDK (docs/05 § 3.4). Таблица данных: расширяется без правки алгоритма."""

from __future__ import annotations

from engine.analysis.complexity import LOGN, NLOGN, ONE, Cost, N

LIST_LIKE = frozenset(
    {"ArrayList", "List", "Vector", "Stack", "CopyOnWriteArrayList", "Collection", "Iterable"}
)
LINKED = frozenset({"LinkedList"})
HASHED = frozenset(
    {
        "HashSet",
        "HashMap",
        "Set",
        "Map",
        "LinkedHashMap",
        "LinkedHashSet",
        "ConcurrentHashMap",
        "EnumMap",
        "EnumSet",
        "IdentityHashMap",
    }
)
TREED = frozenset({"TreeSet", "TreeMap", "SortedMap", "SortedSet", "NavigableMap", "NavigableSet"})
QUEUES = frozenset({"ArrayDeque", "Deque", "Queue"})
HEAPS = frozenset({"PriorityQueue"})
STRINGS = frozenset({"String"})
BUILDERS = frozenset({"StringBuilder", "StringBuffer"})
STREAMS = frozenset({"Stream", "IntStream", "LongStream", "DoubleStream"})
COLLECTIONS = LIST_LIKE | LINKED | HASHED | TREED | QUEUES | HEAPS

#: методы, перебирающие все элементы
_LINEAR_ALL = {
    "forEach",
    "removeIf",
    "replaceAll",
    "addAll",
    "removeAll",
    "retainAll",
    "containsAll",
    "toArray",
    "stream",
    "clear",
    "equals",
    "hashCode",
    "toString",
    "iterator",
}

#: имя метода → стоимость, по семействам типов
_TABLE: dict[str, dict[str, Cost]] = {
    "list": {
        "get": ONE,
        "set": ONE,
        "size": ONE,
        "isEmpty": ONE,
        "add": ONE,
        "push": ONE,
        "peek": ONE,
        "pop": ONE,
        "addLast": ONE,
        "contains": N,
        "indexOf": N,
        "lastIndexOf": N,
        "remove": N,
        "sort": NLOGN,
        "subList": ONE,
        "getFirst": ONE,
        "getLast": ONE,
    },
    "linked": {
        "get": N,
        "set": N,
        "size": ONE,
        "isEmpty": ONE,
        "add": ONE,
        "addFirst": ONE,
        "addLast": ONE,
        "removeFirst": ONE,
        "removeLast": ONE,
        "poll": ONE,
        "pollFirst": ONE,
        "pollLast": ONE,
        "peek": ONE,
        "push": ONE,
        "pop": ONE,
        "getFirst": ONE,
        "getLast": ONE,
        "offer": ONE,
        "contains": N,
        "indexOf": N,
        "lastIndexOf": N,
        "remove": N,
        "sort": NLOGN,
    },
    "hashed": {
        "add": ONE,
        "put": ONE,
        "get": ONE,
        "contains": ONE,
        "containsKey": ONE,
        "remove": ONE,
        "getOrDefault": ONE,
        "merge": ONE,
        "putIfAbsent": ONE,
        "computeIfAbsent": ONE,
        "compute": ONE,
        "size": ONE,
        "isEmpty": ONE,
        "containsValue": N,
        "keySet": ONE,
        "values": ONE,
        "entrySet": ONE,
    },
    "treed": {
        "add": LOGN,
        "put": LOGN,
        "get": LOGN,
        "contains": LOGN,
        "containsKey": LOGN,
        "remove": LOGN,
        "floor": LOGN,
        "ceiling": LOGN,
        "floorKey": LOGN,
        "ceilingKey": LOGN,
        "first": LOGN,
        "last": LOGN,
        "firstKey": LOGN,
        "lastKey": LOGN,
        "pollFirst": LOGN,
        "size": ONE,
        "isEmpty": ONE,
        "merge": LOGN,
        "getOrDefault": LOGN,
    },
    "queue": {
        "add": ONE,
        "offer": ONE,
        "poll": ONE,
        "peek": ONE,
        "push": ONE,
        "pop": ONE,
        "size": ONE,
        "isEmpty": ONE,
        "addFirst": ONE,
        "addLast": ONE,
        "removeFirst": ONE,
        "removeLast": ONE,
        "contains": N,
        "remove": N,
    },
    "heap": {
        "add": LOGN,
        "offer": LOGN,
        "poll": LOGN,
        "peek": ONE,
        "size": ONE,
        "isEmpty": ONE,
        "remove": N,
        "contains": N,
    },
    # Длина строки считается константой, пока строка не накапливается в цикле (см. PERF-03):
    # иначе каждый ``equals``/``split`` по короткой строке давал бы лишний множитель ``n``.
    "string": {
        "length": ONE,
        "charAt": ONE,
        "isEmpty": ONE,
        "concat": ONE,
        "substring": ONE,
        "indexOf": ONE,
        "lastIndexOf": ONE,
        "contains": ONE,
        "equals": ONE,
        "equalsIgnoreCase": ONE,
        "compareTo": ONE,
        "toCharArray": ONE,
        "split": ONE,
        "replace": ONE,
        "replaceAll": ONE,
        "format": ONE,
        "trim": ONE,
        "toUpperCase": ONE,
        "toLowerCase": ONE,
        "startsWith": ONE,
        "endsWith": ONE,
        "matches": ONE,
        "join": ONE,
        "repeat": ONE,
        "strip": ONE,
        "chars": ONE,
        "hashCode": ONE,
    },
    "builder": {
        "append": ONE,
        "toString": N,
        "length": ONE,
        "charAt": ONE,
        "reverse": N,
        "insert": N,
        "deleteCharAt": N,
        "indexOf": N,
        "delete": N,
        "setLength": ONE,
        "setCharAt": ONE,
    },
    "stream": {
        "filter": N,
        "map": N,
        "mapToInt": N,
        "mapToObj": N,
        "mapToLong": N,
        "mapToDouble": N,
        "forEach": N,
        "collect": N,
        "count": N,
        "reduce": N,
        "distinct": N,
        "anyMatch": N,
        "allMatch": N,
        "noneMatch": N,
        "sum": N,
        "average": N,
        "max": N,
        "min": N,
        "toList": N,
        "boxed": N,
        "flatMap": N,
        "peek": N,
        "skip": N,
        "limit": ONE,
        "sorted": NLOGN,
        "findFirst": ONE,
        "findAny": ONE,
        "toArray": N,
    },
}

#: статические методы: ``(Тип, метод)`` → стоимость
_STATIC: dict[tuple[str, str], Cost] = {
    ("Collections", "sort"): NLOGN,
    ("Arrays", "sort"): NLOGN,
    ("Collections", "max"): N,
    ("Collections", "min"): N,
    ("Collections", "reverse"): N,
    ("Collections", "shuffle"): N,
    ("Collections", "frequency"): N,
    ("Collections", "binarySearch"): LOGN,
    ("Arrays", "binarySearch"): LOGN,
    ("Arrays", "fill"): N,
    ("Arrays", "copyOf"): N,
    ("Arrays", "copyOfRange"): N,
    ("Arrays", "toString"): N,
    ("Arrays", "asList"): ONE,
    ("Arrays", "stream"): ONE,
    ("Arrays", "equals"): N,
    ("Arrays", "hashCode"): N,
    ("List", "copyOf"): N,
    ("Set", "copyOf"): N,
    ("Map", "copyOf"): N,
    ("List", "of"): ONE,
    ("Set", "of"): ONE,
    ("Map", "of"): ONE,
    ("String", "valueOf"): ONE,
    ("String", "format"): ONE,
    ("String", "join"): ONE,
    ("Collectors", "groupingBy"): N,
    ("Collectors", "toMap"): N,
    ("Collectors", "toList"): N,
    ("Collectors", "toSet"): N,
    ("Collectors", "joining"): N,
    ("Collectors", "counting"): N,
}

#: типы, все методы которых считаются O(1) (известная стоимость, без метки «неизвестно»)
CONSTANT_OWNERS = frozenset(
    {
        "Math",
        "Integer",
        "Long",
        "Double",
        "Boolean",
        "Character",
        "Objects",
        "Optional",
        "System",
        "PrintStream",
        "Scanner",
        "BufferedReader",
        "Random",
        "Thread",
        "Instant",
        "Duration",
        "LocalDate",
        "LocalDateTime",
        "BigDecimal",
        "BigInteger",
        "Float",
        "Short",
        "Byte",
        "Number",
        "Map.Entry",
        "Entry",
        "StringJoiner",
        "UUID",
        "Pattern",
        "Matcher",
        "Iterator",
        "Comparator",
    }
)

#: методы-потребители, вызывающие переданную лямбду по разу на элемент
CONSUMERS = frozenset(
    {
        "forEach",
        "removeIf",
        "replaceAll",
        "map",
        "filter",
        "mapToInt",
        "mapToObj",
        "mapToLong",
        "mapToDouble",
        "flatMap",
        "anyMatch",
        "allMatch",
        "noneMatch",
        "peek",
        "reduce",
        "collect",
        "sorted",
        "max",
        "min",
        "computeIfAbsent",
        "merge",
        "compute",
        "sort",
    }
)


def family(type_name: str | None) -> str | None:
    if type_name is None:
        return None
    if type_name in LINKED:
        return "linked"
    if type_name in LIST_LIKE:
        return "list"
    if type_name in HASHED:
        return "hashed"
    if type_name in TREED:
        return "treed"
    if type_name in QUEUES:
        return "queue"
    if type_name in HEAPS:
        return "heap"
    if type_name in STRINGS:
        return "string"
    if type_name in BUILDERS:
        return "builder"
    if type_name in STREAMS:
        return "stream"
    return None


def is_collection(type_name: str | None) -> bool:
    return type_name in COLLECTIONS


def call_cost(owner_type: str | None, name: str, *, static: bool = False) -> Cost | None:
    """Стоимость вызова JDK-метода; ``None`` — метод каталогу неизвестен."""
    if owner_type is None:
        return None
    if static and (owner_type, name) in _STATIC:
        return _STATIC[(owner_type, name)]
    fam = family(owner_type)
    if fam is not None:
        found = _TABLE[fam].get(name)
        if found is not None:
            return found
        if name in _LINEAR_ALL:
            return N
        return None
    if owner_type in CONSTANT_OWNERS:
        return ONE
    return None
