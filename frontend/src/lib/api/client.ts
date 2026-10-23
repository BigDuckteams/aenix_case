import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Пути в схеме уже содержат префикс /api; запросы идут на тот же origin,
// а Next.js проксирует /api/* в backend (rewrites в next.config.ts).
export const api = createClient<paths>({ baseUrl: "" });
