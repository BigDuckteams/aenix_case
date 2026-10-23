import { MOCK_MODE } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];

// Типы событий — из OpenAPI (docs/08-api.md § 9): дискриминатор — поле event.
export type RunEvent =
  | Schemas["StatusEvent"]
  | Schemas["LogEvent"]
  | Schemas["GateEvent"]
  | Schemas["ItemEvent"]
  | Schemas["StepEvent"]
  | Schemas["ProgressEvent"]
  | Schemas["ResultEvent"]
  | Schemas["ErrorEvent"]
  | Schemas["DoneEvent"];

export const RUN_EVENT_NAMES = [
  "status",
  "log",
  "gate",
  "item",
  "step",
  "progress",
  "result",
  "error",
  "done",
] as const satisfies ReadonlyArray<RunEvent["event"]>;

type Options = {
  /** Пауза между событиями при реплее моков, мс. */
  mockIntervalMs?: number;
  /** Подмена EventSource (для тестов). */
  eventSource?: typeof EventSource;
};

/**
 * Подписка на SSE запуска. Возвращает функцию отписки.
 * Сервер повторяет события с начала для поздних подписчиков, поэтому повторное подключение
 * EventSource после обрыва безопасно. В режиме моков события берутся из фикстуры и
 * проигрываются по таймеру.
 */
export function openRunEvents(
  runId: number,
  onEvent: (event: RunEvent) => void,
  options: Options = {},
): () => void {
  if (MOCK_MODE) return replayMock(onEvent, options.mockIntervalMs ?? 150);

  const Source = options.eventSource ?? EventSource;
  const source = new Source(`/api/runs/${runId}/events`);
  for (const name of RUN_EVENT_NAMES) {
    source.addEventListener(name, (message) => {
      const data = JSON.parse((message as MessageEvent<string>).data) as RunEvent["data"];
      onEvent({ event: name, data } as RunEvent);
      if (name === "done") source.close();
    });
  }
  return () => source.close();
}

function replayMock(onEvent: (event: RunEvent) => void, intervalMs: number): () => void {
  let cancelled = false;
  const timers: ReturnType<typeof setTimeout>[] = [];
  void import("@/mocks/fixtures/run-8-events.json").then(({ default: events }) => {
    (events as RunEvent[]).forEach((event, index) => {
      timers.push(
        setTimeout(() => {
          if (!cancelled) onEvent(event);
        }, index * intervalMs),
      );
    });
  });
  return () => {
    cancelled = true;
    timers.forEach(clearTimeout);
  };
}
