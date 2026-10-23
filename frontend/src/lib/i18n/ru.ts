// Все строки интерфейса живут здесь: один язык в MVP, но без «зашитых» строк в JSX.
export const ru = {
  app: {
    title: "Java Blueprints",
    subtitle: "Визуальная среда программирования",
    description:
      "Java-код как граф: разбор, диагностика, оптимизация и проверка сохранения поведения.",
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
