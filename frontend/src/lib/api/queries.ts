import { queryOptions } from "@tanstack/react-query";

import { api } from "./client";
import type { components } from "./schema";

type ApiResult<T> = { data?: T; error?: components["schemas"]["ErrorResponse"] };

// Ошибки backend приходят в едином формате {"error": {"code", "message"}} (docs/08-api.md § 1).
function unwrap<T>({ data, error }: ApiResult<T>): T {
  if (error || data === undefined) {
    throw new Error(error?.error?.message ?? "Backend недоступен");
  }
  return data;
}

export const healthQuery = queryOptions({
  queryKey: ["health"],
  queryFn: async () => unwrap(await api.GET("/api/health")),
  retry: false,
  refetchInterval: 15_000,
});

export const structureQuery = (projectId: number, mode: "types" | "methods" | "deps" = "methods") =>
  queryOptions({
    queryKey: ["structure", projectId, mode],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/structure", {
          params: { path: { project_id: projectId }, query: { mode } },
        }),
      ),
    retry: false,
  });

export const flowQuery = (projectId: number, methodId: string | null) =>
  queryOptions({
    queryKey: ["flow", projectId, methodId],
    enabled: methodId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/flow", {
          params: { path: { project_id: projectId }, query: { method_id: methodId ?? "" } },
        }),
      ),
    retry: false,
  });

export const analysisQuery = (projectId: number) =>
  queryOptions({
    queryKey: ["analysis", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/analysis", {
          params: { path: { project_id: projectId } },
        }),
      ),
    retry: false,
  });

export const scenariosQuery = (projectId: number) =>
  queryOptions({
    queryKey: ["scenarios", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/scenarios", {
          params: { path: { project_id: projectId } },
        }),
      ),
    retry: false,
  });
