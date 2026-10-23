# Frontend

Next.js (App Router) + TypeScript + shadcn/ui + Tailwind CSS. Подробности — в [docs/09-frontend.md](../docs/09-frontend.md).

```bash
pnpm install
pnpm dev          # http://localhost:3000, /api/* проксируется на BACKEND_URL (по умолчанию http://localhost:8000)
pnpm lint
pnpm typecheck    # next typegen + tsc --noEmit
pnpm test         # vitest
pnpm gen:api      # типы из openapi.json (его выгружает backend: см. корневой README)
```

Заметки:

- Компоненты `src/components/ui/` — исходники shadcn/ui (стиль new-york), `components.json` совместим с CLI `shadcn add`.
- Шрифты (Inter, JetBrains Mono) подключены из npm (`@fontsource-variable/*`): сборка не зависит от Google Fonts.
- Все строки интерфейса — в `src/lib/i18n/ru.ts`.
- В `next.config.ts` отключено сжатие (`compress: false`), иначе SSE-события запусков приходят пачкой.
