import { Badge } from "@/components/ui/badge";
import type { components } from "@/lib/api/schema";
import { ru } from "@/lib/i18n/ru";
import { flowOutline, type OutlineItem } from "@/lib/graph/outline";
import { cn } from "@/lib/utils";

type FlowGraph = components["schemas"]["FlowGraph"];
type NodeKind = components["schemas"]["FlowNode"]["kind"];

// Цвета блоков — по макету (docs/09-frontend.md § 3.3): фиолетовый «Метод», синий «Переменная»,
// оранжевый «Условие», зелёный «Возврат», бирюзовый «Операция»/«Цикл». Классы записаны целиком,
// чтобы Tailwind их увидел.
const KIND_STYLES: Partial<Record<NodeKind, string>> = {
  method: "border-violet-500/50 bg-violet-500/10",
  var_decl: "border-blue-500/50 bg-blue-500/10",
  assign: "border-teal-500/50 bg-teal-500/10",
  operation: "border-teal-500/50 bg-teal-500/10",
  condition: "border-orange-500/50 bg-orange-500/10",
  loop_for: "border-cyan-500/50 bg-cyan-500/10",
  loop_foreach: "border-cyan-500/50 bg-cyan-500/10",
  loop_while: "border-cyan-500/50 bg-cyan-500/10",
  return: "border-green-500/50 bg-green-500/10",
  break: "border-red-500/40 bg-red-500/10",
  continue: "border-red-500/40 bg-red-500/10",
  throw: "border-red-500/40 bg-red-500/10",
};

function EdgeHints({ item }: { item: OutlineItem }) {
  const hints = item.outgoing.filter(({ edge }) => edge.kind !== "next");
  if (hints.length === 0) return null;
  return (
    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
      {hints.map(({ edge, target }) => (
        <li key={edge.id}>
          <span className="font-medium text-foreground/80">{edge.label ?? edge.kind}</span>
          {" → "}
          {target ? `${target.label} (${ru.preview.lines} ${target.range.start_line})` : edge.target}
        </li>
      ))}
    </ul>
  );
}

export function FlowOutline({ flow }: { flow: FlowGraph }) {
  const items = flowOutline(flow);
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        <span className="font-mono text-foreground">{flow.signature}</span>
        {" · "}
        {flow.nodes.length} {ru.preview.nodes}, {flow.edges.length} {ru.preview.edges}
      </p>
      <ol className="space-y-1.5">
        {items.map((item) => (
          <li
            key={item.node.id}
            data-testid="flow-node"
            data-kind={item.node.kind}
            style={{ marginLeft: item.depth * 20 }}
          >
            <div className={cn("rounded-md border px-3 py-1.5 text-sm", KIND_STYLES[item.node.kind])}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{item.node.label}</Badge>
                <code className="min-w-0 flex-1 truncate font-mono text-xs">{item.node.code}</code>
                {item.node.complexity && <Badge variant="secondary">{item.node.complexity}</Badge>}
                {item.node.badges.map((badge) => (
                  <Badge
                    key={`${badge.kind}:${badge.label}`}
                    variant={badge.kind === "defect" ? "destructive" : "secondary"}
                  >
                    {badge.label}
                  </Badge>
                ))}
                <span className="text-xs text-muted-foreground">L{item.node.range.start_line}</span>
              </div>
              <EdgeHints item={item} />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
