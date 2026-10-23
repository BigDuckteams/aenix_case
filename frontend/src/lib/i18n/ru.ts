// Все строки интерфейса живут здесь: один язык в MVP, но без «зашитых» строк в JSX.
export const ru = {
  app: {
    title: "Java Blueprints",
    subtitle: "Визуальная среда программирования",
    description:
      "Java-код как граф: разбор, диагностика, оптимизация и проверка сохранения поведения.",
  },
  preview: {
    title: "Предпросмотр контракта",
    subtitle: "Список методов и блок-схема из API (в режиме моков — из фикстур)",
    mockBadge: "моки",
    open: "Предпросмотр на моках",
    methods: "Методы",
    filter: "Фильтр методов…",
    flow: "Блок-схема",
    nothingFound: "Ничего не найдено",
    pickMethod: "Выберите метод слева",
    loadError: "Не удалось загрузить данные",
    loadErrorHint:
      "Запустите frontend в режиме моков (NEXT_PUBLIC_MOCK=1, pnpm dev:mock) или дождитесь реализации эндпоинтов этапа S3.",
    nodes: "блоков",
    edges: "переходов",
    lines: "строки",
    back: "На главную",
  },
  health: {
    title: "Состояние сервиса",
    loading: "Проверяем backend…",
    unavailable: "Backend недоступен",
    unavailableHint: "Запустите backend (uv run uvicorn app.main:app) или docker compose up.",
    ok: "Всё работает",
    degraded: "Есть проблемы",
    version: "Версия",
    javac: "JDK (javac)",
    java: "JDK (java)",
    db: "База данных",
    dbOk: "доступна",
    dbError: "ошибка",
    notFound: "не найден",
  },
} as const;
