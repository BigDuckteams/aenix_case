import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";
import { flowOutline, methodGroups, nodeDepth } from "@/lib/graph/outline";
import flowsJson from "@/mocks/fixtures/flows.json";
import structureJson from "@/mocks/fixtures/structure.json";

const flows = flowsJson as unknown as Record<string, components["schemas"]["FlowGraph"]>;
const flow = flows["Main.java#Main.mergeDuplicates()"];
const structure = structureJson as unknown as components["schemas"]["StructureGraph"];

describe("nodeDepth", () => {
  it("считает вложенность по структурному пути", () => {
    expect(nodeDepth("Main.java#Main.run()")).toBe(0);
    expect(nodeDepth("Main.java#Main.run()/foreach[0]")).toBe(1);
    expect(nodeDepth("Main.java#Main.run()/foreach[0]/foreach[0]/if[0]/then/op[0]")).toBe(4);
  });
});

describe("flowOutline", () => {
  const items = flowOutline(flow);

  it("начинается с метода и идёт в порядке кода", () => {
    expect(items[0].node.kind).toBe("method");
    const lines = items.map((item) => item.node.range.start_line);
    expect(lines).toEqual([...lines].sort((a, b) => a - b));
    expect(items).toHaveLength(flow.nodes.length);
  });

  it("вложенность растёт внутри циклов и ветвей", () => {
    const innerOperation = items.find((item) => item.node.id.endsWith("foreach[0]/foreach[0]/if[0]/then/op[0]"));
    expect(innerOperation?.depth).toBe(4);
    expect(items.find((item) => item.node.kind === "return")?.depth).toBe(1);
  });

  it("условие знает свои исходы Да/Нет", () => {
    const condition = items.find((item) => item.node.id.endsWith("foreach[0]/if[0]"));
    const labels = condition?.outgoing.map(({ edge }) => edge.label);
    expect(labels).toContain("Да");
    // рёбра call ведут в схемы других методов, остальные — к блокам этой схемы
    const local = condition?.outgoing.filter(({ edge }) => edge.kind !== "call") ?? [];
    expect(local.every(({ target }) => target !== undefined)).toBe(true);
  });
});

describe("methodGroups", () => {
  it("группирует методы по типам и фильтрует по подстроке", () => {
    const groups = methodGroups(structure);
    expect(groups.map((g) => g.typeName)).toContain("Main");
    const filtered = methodGroups(structure, "merge");
    expect(filtered).toHaveLength(1);
    expect(filtered[0].methods.map((m) => m.name)).toEqual(["mergeDuplicates"]);
    expect(methodGroups(structure, "несуществующее")).toEqual([]);
  });

  it("не включает поля", () => {
    const names = methodGroups(structure).flatMap((g) => g.methods.map((m) => m.kind));
    expect(new Set(names)).toEqual(new Set(["method", "constructor"]));
  });
});
