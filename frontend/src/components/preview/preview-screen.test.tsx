import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ru } from "@/lib/i18n/ru";

async function renderScreen() {
  const { PreviewScreen } = await import("@/components/preview/preview-screen");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PreviewScreen />
    </QueryClientProvider>,
  );
}

describe("PreviewScreen на моках", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_MOCK", "1");
    vi.resetModules();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("показывает список методов и блок-схему выбранного по умолчанию метода", async () => {
    await renderScreen();
    expect(await screen.findByRole("button", { name: /mergeDuplicates\(\)/ })).toBeInTheDocument();
    expect(screen.getByText(ru.preview.mockBadge)).toBeInTheDocument();

    const nodes = await screen.findAllByTestId("flow-node");
    expect(nodes.length).toBeGreaterThanOrEqual(15);
    const kinds = new Set(nodes.map((node) => node.getAttribute("data-kind")));
    expect(kinds).toContain("loop_foreach");
    expect(kinds).toContain("condition");
    expect(screen.getAllByText("PERF-01").length).toBeGreaterThan(0);
  });

  it("переключает схему при выборе другого метода", async () => {
    const user = userEvent.setup();
    await renderScreen();
    await screen.findAllByTestId("flow-node");
    await user.click(screen.getByRole("button", { name: /buildCsv\(\)/ }));
    await waitFor(() => expect(screen.getAllByTestId("flow-node")).toHaveLength(5));
    expect(screen.getByRole("button", { name: /buildCsv\(\)/ })).toHaveAttribute("aria-current", "true");
  });

  it("для метода без мока показывает понятную ошибку", async () => {
    const user = userEvent.setup();
    await renderScreen();
    await screen.findAllByTestId("flow-node");
    await user.click(screen.getByRole("button", { name: /printReport\(\)/ }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(ru.preview.loadError)).toBeInTheDocument();
    expect(within(alert).getByText(/нет блок-схемы/)).toBeInTheDocument();
  });

  it("фильтр сокращает список методов", async () => {
    const user = userEvent.setup();
    await renderScreen();
    await screen.findByRole("button", { name: /mergeDuplicates\(\)/ });
    await user.type(screen.getByLabelText(ru.preview.filter), "distinct");
    expect(screen.queryByRole("button", { name: /mergeDuplicates\(\)/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /distinctCustomers\(\)/ })).toBeInTheDocument();
    await user.clear(screen.getByLabelText(ru.preview.filter));
    await user.type(screen.getByLabelText(ru.preview.filter), "такого нет");
    expect(await screen.findByText(ru.preview.nothingFound)).toBeInTheDocument();
  });
});

describe("PreviewScreen без моков и без backend", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("показывает подсказку, если API недоступен", async () => {
    vi.resetModules();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { error: { code: "NOT_IMPLEMENTED", message: "Эндпоинт ещё не реализован (этап S3)" } },
          { status: 501 },
        ),
      ),
    );
    await renderScreen();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/этап S3/)).toBeInTheDocument();
    expect(screen.queryByText(ru.preview.mockBadge)).not.toBeInTheDocument();
  });
});
