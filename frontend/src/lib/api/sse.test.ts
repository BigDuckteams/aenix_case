import { afterEach, describe, expect, it, vi } from "vitest";

import eventsJson from "@/mocks/fixtures/run-8-events.json";

import { RUN_EVENT_NAMES, type RunEvent } from "./sse";

class FakeEventSource {
  static last: FakeEventSource;
  listeners = new Map<string, (message: MessageEvent<string>) => void>();
  closed = false;
  constructor(public url: string) {
    FakeEventSource.last = this;
  }
  addEventListener(name: string, listener: (message: MessageEvent<string>) => void) {
    this.listeners.set(name, listener);
  }
  close() {
    this.closed = true;
  }
  emit(name: string, data: unknown) {
    this.listeners.get(name)?.({ data: JSON.stringify(data) } as MessageEvent<string>);
  }
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.useRealTimers();
  vi.resetModules();
});

describe("openRunEvents", () => {
  it("подписывается на все события контракта и закрывается на done", async () => {
    vi.resetModules();
    const { openRunEvents } = await import("./sse");
    const received: RunEvent[] = [];
    openRunEvents(7, (event) => received.push(event), {
      eventSource: FakeEventSource as unknown as typeof EventSource,
    });
    const source = FakeEventSource.last;
    expect(source.url).toBe("/api/runs/7/events");
    expect([...source.listeners.keys()].sort()).toEqual([...RUN_EVENT_NAMES].sort());

    source.emit("status", { status: "running" });
    source.emit("progress", { done: 1, total: 3 });
    expect(source.closed).toBe(false);
    source.emit("done", {});
    expect(received.map((e) => e.event)).toEqual(["status", "progress", "done"]);
    expect(source.closed).toBe(true);
  });

  it("отписка закрывает источник", async () => {
    vi.resetModules();
    const { openRunEvents } = await import("./sse");
    const close = openRunEvents(1, () => {}, {
      eventSource: FakeEventSource as unknown as typeof EventSource,
    });
    close();
    expect(FakeEventSource.last.closed).toBe(true);
  });

  it("в режиме моков проигрывает фикстуру по таймеру и умеет отменяться", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK", "1");
    vi.resetModules();
    vi.useFakeTimers();
    const { openRunEvents } = await import("./sse");
    const received: RunEvent[] = [];
    const cancel = openRunEvents(8, (event) => received.push(event), { mockIntervalMs: 10 });
    await vi.dynamicImportSettled();
    await vi.advanceTimersByTimeAsync(10 * eventsJson.length);
    expect(received).toHaveLength(eventsJson.length);
    expect(received[0].event).toBe("status");
    expect(received.at(-1)?.event).toBe("done");

    received.length = 0;
    const cancelled = openRunEvents(8, (event) => received.push(event), { mockIntervalMs: 10 });
    await vi.dynamicImportSettled();
    cancelled();
    await vi.advanceTimersByTimeAsync(10 * eventsJson.length);
    expect(received).toHaveLength(0);
    cancel();
  });
});
