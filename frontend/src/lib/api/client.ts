import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Режим моков: NEXT_PUBLIC_MOCK=1 (см. frontend/README.md). Переменная подставляется при сборке,
// поэтому без неё код моков и фикстуры в бандл не попадают.
export const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK === "1";

// Пути в схеме уже содержат префикс /api; запросы идут на тот же origin,
// а Next.js проксирует /api/* в backend (rewrites в next.config.ts). Origin берётся из window:
// конструктор Request вне браузера (тесты, Node) не принимает относительные адреса.
export const api = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  fetch: MOCK_MODE
    ? async (request) => (await import("@/mocks/mock-fetch")).mockFetch(request)
    : undefined,
});
