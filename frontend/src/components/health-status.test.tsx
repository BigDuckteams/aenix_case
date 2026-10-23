import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthStatus } from "@/components/health-status";
import { ru } from "@/lib/i18n/ru";

const okHealth = {
  status: "ok" as const,
  version: "0.1.0",
  javac: "21.0.4",
  java: "21.0.4",
  db: "ok" as const,
  problems: [],
};

describe("HealthStatus", () => {
  it("показывает версии и статус при успехе", () => {
    render(<HealthStatus data={okHealth} />);
    expect(screen.getByText(ru.health.ok)).toBeInTheDocument();
    expect(screen.getAllByText("21.0.4")).toHaveLength(2);
    expect(screen.getByText(ru.health.dbOk)).toBeInTheDocument();
  });

  it("перечисляет проблемы, если backend сообщает degraded", () => {
    render(
      <HealthStatus
        data={{
          ...okHealth,
          status: "degraded",
          javac: null,
          problems: ["javac не найден: проверьте PATH или JB_JAVA_HOME"],
        }}
      />,
    );
    expect(screen.getByText(ru.health.degraded)).toBeInTheDocument();
    expect(screen.getByText(/javac не найден/)).toBeInTheDocument();
    expect(screen.getAllByText(ru.health.notFound).length).toBeGreaterThan(0);
  });

  it("показывает состояние загрузки", () => {
    render(<HealthStatus isLoading />);
    expect(screen.getByText(ru.health.loading)).toBeInTheDocument();
  });

  it("показывает подсказку, когда backend недоступен", () => {
    render(<HealthStatus error={new Error("boom")} />);
    expect(screen.getByText(ru.health.unavailable)).toBeInTheDocument();
    expect(screen.getByText(ru.health.unavailableHint)).toBeInTheDocument();
  });
});
