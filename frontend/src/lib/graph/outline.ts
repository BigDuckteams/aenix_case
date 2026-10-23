import type { components } from "@/lib/api/schema";

type FlowGraph = components["schemas"]["FlowGraph"];
type FlowNode = components["schemas"]["FlowNode"];
type FlowEdge = components["schemas"]["FlowEdge"];
type StructureGraph = components["schemas"]["StructureGraph"];
type StructureNode = components["schemas"]["StructureNode"];

export type OutlineItem = {
  node: FlowNode;
  /** Вложенность по структурному пути id (циклы и ветки), 0 — сам метод. */
  depth: number;
  /** Исходящие рёбра с узлом-получателем (если он в этой схеме). */
  outgoing: Array<{ edge: FlowEdge; target?: FlowNode }>;
};

/** Глубина узла: число сегментов вида `kind[index]` после ключа члена в id. */
export function nodeDepth(id: string): number {
  const path = id.split("#")[1] ?? "";
  const segments = path.split("/").slice(1);
  return segments.filter((segment) => /\[\d+\]$/.test(segment)).length;
}

/**
 * Линейное представление блок-схемы в порядке следования кода. Это временный вид S1:
 * холст React Flow + ELK появится на этапе S4, а список уже проверяет, что контракт
 * `FlowGraph` достаточен для отображения вложенности, ветвлений и бейджей.
 */
export function flowOutline(flow: FlowGraph): OutlineItem[] {
  const byId = new Map(flow.nodes.map((node) => [node.id, node]));
  const outgoing = new Map<string, FlowEdge[]>();
  for (const edge of flow.edges) {
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge]);
  }
  const order = (a: FlowNode, b: FlowNode) =>
    a.range.start_line - b.range.start_line || a.range.start_col - b.range.start_col;
  return [...flow.nodes].sort(order).map((node) => ({
    node,
    depth: nodeDepth(node.id),
    outgoing: (outgoing.get(node.id) ?? []).map((edge) => ({ edge, target: byId.get(edge.target) })),
  }));
}

export type MethodGroup = { typeName: string; methods: StructureNode[] };

/** Методы и конструкторы проекта, сгруппированные по типам, для списка слева. */
export function methodGroups(structure: StructureGraph, filter = ""): MethodGroup[] {
  const needle = filter.trim().toLowerCase();
  const types = structure.nodes.filter((node) => node.node_type === "type");
  const groups: MethodGroup[] = [];
  for (const type of types) {
    const methods = structure.nodes.filter(
      (node) =>
        node.parent_id === type.id &&
        node.method_id !== null &&
        (needle === "" || (node.signature ?? node.name).toLowerCase().includes(needle)),
    );
    if (methods.length > 0) groups.push({ typeName: type.name, methods });
  }
  return groups;
}
