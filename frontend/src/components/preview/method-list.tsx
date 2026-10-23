import { Badge } from "@/components/ui/badge";
import type { components } from "@/lib/api/schema";
import type { MethodGroup } from "@/lib/graph/outline";
import { cn } from "@/lib/utils";

type StructureNode = components["schemas"]["StructureNode"];

type Props = {
  groups: MethodGroup[];
  selectedId: string | null;
  onSelect: (method: StructureNode) => void;
};

export function MethodList({ groups, selectedId, onSelect }: Props) {
  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <section key={group.typeName}>
          <h3 className="px-2 pb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {group.typeName}
          </h3>
          <ul>
            {group.methods.map((method) => (
              <li key={method.id}>
                <button
                  type="button"
                  onClick={() => onSelect(method)}
                  aria-current={method.method_id === selectedId ? "true" : undefined}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm hover:bg-accent",
                    method.method_id === selectedId && "bg-accent",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">
                    {method.signature ?? method.name}
                  </span>
                  {method.complexity && <Badge variant="secondary">{method.complexity}</Badge>}
                  {method.findings_count > 0 && (
                    <Badge variant="destructive">{method.findings_count}</Badge>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
