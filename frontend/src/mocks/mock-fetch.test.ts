import { afterEach, describe, expect, it, vi } from "vitest";

import { MOCK_FLOWS, mockFetch, resolveMock } from "@/mocks/mock-fetch";

const url = (path: string) => new URL(path, "http://localhost");

describe("resolveMock", () => {
  it("отдаёт фикстуры по путям контракта", () => {
    expect(resolveMock("GET", url("/api/health")).body).toMatchObject({ status: "ok" });
    expect(resolveMock("GET", url("/api/projects/1")).body).toMatchObject({ id: 1, main_class: "Main" });
    expect(resolveMock("GET", url("/api/projects/1/structure?mode=methods")).body).toMatchObject({
      mode: "methods",
    });
    const scenarios = resolveMock("GET", url("/api/projects/1/scenarios")).body as {
      scenarios: unknown[];
    };
    expect(scenarios.scenarios.length).toBeGreaterThanOrEqual(8);
  });

  it("выбирает блок-схему по method_id", () => {
    const id = encodeURIComponent("Main.java#Main.mergeDuplicates()");
    const reply = resolveMock("GET", url(`/api/projects/1/flow?method_id=${id}`));
    expect(reply.status).toBe(200);
    expect(reply.body).toBe(MOCK_FLOWS.mergeDuplicates);
  });

  it("для метода без мока возвращает 404 в формате ошибки", () => {
    const id = encodeURIComponent("Main.java#Main.printReport()");
    const reply = resolveMock("GET", url(`/api/projects/1/flow?method_id=${id}`));
    expect(reply.status).toBe(404);
    expect(reply.body).toMatchObject({ error: { code: "NOT_FOUND" } });
  });

  it("запуск создаётся как 202 с run_id", () => {
    const reply = resolveMock("POST", url("/api/projects/1/runs"));
    expect(reply).toEqual({ status: 202, body: { run_id: 8, status: "queued" } });
    expect((resolveMock("GET", url("/api/runs/8")).body as { id: number }).id).toBe(8);
  });

  it("файл по пути и неизвестный запуск", () => {
    expect(resolveMock("GET", url("/api/projects/1/files/Main.java")).status).toBe(200);
    expect(resolveMock("GET", url("/api/projects/1/files/Other.java")).status).toBe(404);
    expect(resolveMock("GET", url("/api/runs/99")).status).toBe(404);
  });

  it("для остального отвечает 501 NOT_IMPLEMENTED", () => {
    const reply = resolveMock("POST", url("/api/projects/1/ops"));
    expect(reply.status).toBe(501);
    expect(reply.body).toMatchObject({ error: { code: "NOT_IMPLEMENTED" } });
  });
});

describe("mockFetch и клиент", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("возвращает Response с JSON", async () => {
    const response = await mockFetch(new Request("http://localhost/api/health"));
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ status: "ok" });
  });

  it("клиент openapi-fetch в режиме моков не обращается к сети", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK", "1");
    vi.resetModules();
    const network = vi.fn(() => Promise.reject(new Error("сеть недоступна")));
    vi.stubGlobal("fetch", network);
    const { api, MOCK_MODE } = await import("@/lib/api/client");
    expect(MOCK_MODE).toBe(true);
    const { data, error } = await api.GET("/api/projects/{project_id}/flow", {
      params: {
        path: { project_id: 1 },
        query: { method_id: "Main.java#Main.buildCsv()" },
      },
    });
    expect(error).toBeUndefined();
    expect(data?.nodes.length).toBeGreaterThanOrEqual(5);
    expect(network).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("ошибка контракта приходит в поле error", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK", "1");
    vi.resetModules();
    const { api } = await import("@/lib/api/client");
    const { data, error } = await api.POST("/api/projects/{project_id}/ops", {
      params: { path: { project_id: 1 } },
      body: { base_version_id: 1, ops: [{ op: "delete_node", node_id: "a" }] },
    });
    expect(data).toBeUndefined();
    expect(error?.error.code).toBe("NOT_IMPLEMENTED");
  });
});
