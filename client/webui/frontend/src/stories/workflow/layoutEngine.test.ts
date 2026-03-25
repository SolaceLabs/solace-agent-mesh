import { describe, test, expect } from "vitest";

import { processWorkflowConfig } from "@/lib/components/workflowVisualization/utils/layoutEngine";
import { LAYOUT_CONSTANTS } from "@/lib/components/workflowVisualization/utils/types";
import type { WorkflowConfig, WorkflowNodeConfig } from "@/lib/utils/agentUtils";

const { NODE_WIDTHS, NODE_HEIGHTS, SPACING } = LAYOUT_CONSTANTS;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConfig(nodes: WorkflowNodeConfig[]): WorkflowConfig {
    return { nodes } as WorkflowConfig;
}

function agentNode(id: string, depends_on: string[] = []): WorkflowNodeConfig {
    return { id, type: "agent", agent_name: id, depends_on } as WorkflowNodeConfig;
}

function nodeById(result: ReturnType<typeof processWorkflowConfig>, id: string) {
    const node = result.nodes.find(n => n.id === id);
    if (!node) throw new Error(`Node "${id}" not found in layout result`);
    return node;
}

// ---------------------------------------------------------------------------
// Empty config
// ---------------------------------------------------------------------------

describe("empty config", () => {
    test("returns start and end nodes", () => {
        const result = processWorkflowConfig(makeConfig([]));
        expect(result.nodes).toHaveLength(2);
        expect(result.nodes[0].id).toBe("__start__");
        expect(result.nodes[1].id).toBe("__end__");
    });

    test("start and end are connected by a single edge", () => {
        const result = processWorkflowConfig(makeConfig([]));
        expect(result.edges).toHaveLength(1);
        expect(result.edges[0].source).toBe("__start__");
        expect(result.edges[0].target).toBe("__end__");
    });

});

// ---------------------------------------------------------------------------
// Single agent node
// ---------------------------------------------------------------------------

describe("single agent node", () => {
    test("agent node has correct dimensions", () => {
        const result = processWorkflowConfig(makeConfig([agentNode("step1")]));
        const node = nodeById(result, "step1");
        expect(node.width).toBe(NODE_WIDTHS.AGENT);
        expect(node.height).toBe(NODE_HEIGHTS.AGENT);
    });

    test("start -> agent -> end edges exist", () => {
        const result = processWorkflowConfig(makeConfig([agentNode("step1")]));
        const sources = result.edges.map(e => e.source);
        const targets = result.edges.map(e => e.target);
        expect(sources).toContain("__start__");
        expect(targets).toContain("step1");
        expect(sources).toContain("step1");
        expect(targets).toContain("__end__");
    });
});

// ---------------------------------------------------------------------------
// Linear chain (A -> B -> C)
// ---------------------------------------------------------------------------

describe("linear chain", () => {
    const nodes = [agentNode("a"), agentNode("b", ["a"]), agentNode("c", ["b"])];

    test("nodes are laid out vertically (increasing y)", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const ya = nodeById(result, "a").y;
        const yb = nodeById(result, "b").y;
        const yc = nodeById(result, "c").y;
        expect(yb).toBeGreaterThan(ya);
        expect(yc).toBeGreaterThan(yb);
    });

    test("edges form the chain", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const edgePairs = result.edges.map(e => `${e.source}->${e.target}`);
        expect(edgePairs).toContain("a->b");
        expect(edgePairs).toContain("b->c");
    });
});

// ---------------------------------------------------------------------------
// Parallel nodes (both depend on A, then merge to C)
// ---------------------------------------------------------------------------

describe("parallel nodes", () => {
    const nodes = [agentNode("a"), agentNode("b1", ["a"]), agentNode("b2", ["a"]), agentNode("c", ["b1", "b2"])];

    test("parallel nodes are at the same level (same y)", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const yb1 = nodeById(result, "b1").y;
        const yb2 = nodeById(result, "b2").y;
        expect(yb1).toBe(yb2);
    });

    test("merge node is below parallel nodes", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const yb1 = nodeById(result, "b1").y;
        const yc = nodeById(result, "c").y;
        expect(yc).toBeGreaterThan(yb1);
    });
});

// ---------------------------------------------------------------------------
// Switch node
// ---------------------------------------------------------------------------

describe("switch node", () => {
    const switchNode: WorkflowNodeConfig = {
        id: "router",
        type: "switch",
        depends_on: [],
        cases: [
            { condition: "x > 0", node: "pos" },
            { condition: "x < 0", node: "neg" },
        ],
        default: "zero",
    } as unknown as WorkflowNodeConfig;

    const nodes = [
        switchNode,
        agentNode("pos", ["router"]),
        agentNode("neg", ["router"]),
        agentNode("zero", ["router"]),
        agentNode("done", ["pos", "neg", "zero"]),
    ];

    test("switch node has correct width", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        expect(nodeById(result, "router").width).toBe(NODE_WIDTHS.SWITCH_COLLAPSED);
    });

    test("switch node height accounts for cases and default", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        // 2 cases + 1 default = 3 rows; height must be > AGENT height
        expect(nodeById(result, "router").height).toBeGreaterThan(NODE_HEIGHTS.AGENT);
    });

    test("condition pill nodes are inserted between switch and targets", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const pillNodes = result.nodes.filter(n => n.type === "condition");
        // One pill per case + one for default = 3
        expect(pillNodes).toHaveLength(3);
    });

    test("condition pill dimensions match constants", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const pill = result.nodes.find(n => n.type === "condition")!;
        expect(pill).toBeDefined();
        // Width is dynamic (based on label length), height matches constant
        expect(pill.height).toBe(NODE_HEIGHTS.CONDITION_PILL);
    });

    test("branch targets are at the same level", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const ypos = nodeById(result, "pos").y;
        const yneg = nodeById(result, "neg").y;
        const yzero = nodeById(result, "zero").y;
        expect(ypos).toBe(yneg);
        expect(yneg).toBe(yzero);
    });

    test("switch node data carries cases and defaultCase", () => {
        const result = processWorkflowConfig(makeConfig(nodes));
        const router = nodeById(result, "router");
        expect(router.data.cases).toHaveLength(2);
        expect(router.data.defaultCase).toBe("zero");
    });
});

// ---------------------------------------------------------------------------
// Map container node
// ---------------------------------------------------------------------------

describe("map container node", () => {
    const childNode = agentNode("child");
    const mapNode: WorkflowNodeConfig = {
        id: "mapper",
        type: "map",
        node: "child",
        items: "$.items",
        depends_on: [],
    } as unknown as WorkflowNodeConfig;

    test("map node contains child when not collapsed", () => {
        const result = processWorkflowConfig(makeConfig([mapNode, childNode]));
        const mapper = nodeById(result, "mapper");
        expect(mapper.children).toHaveLength(1);
        expect(mapper.children[0].id).toBe("child");
    });

    test("map node has no children when collapsed", () => {
        const result = processWorkflowConfig(makeConfig([mapNode, childNode]), new Set(["mapper"]));
        const mapper = nodeById(result, "mapper");
        expect(mapper.children).toHaveLength(0);
    });

    test("collapsed map node uses SWITCH_COLLAPSED width", () => {
        const result = processWorkflowConfig(makeConfig([mapNode, childNode]), new Set(["mapper"]));
        expect(nodeById(result, "mapper").width).toBe(NODE_WIDTHS.SWITCH_COLLAPSED);
    });

    test("child node is not rendered as a top-level node", () => {
        const result = processWorkflowConfig(makeConfig([mapNode, childNode]));
        // child is a container child — it should not appear as a top-level node
        expect(result.nodes.find(n => n.id === "child")).toBeUndefined();
    });
});

// ---------------------------------------------------------------------------
// Loop container node
// ---------------------------------------------------------------------------

describe("loop container node", () => {
    const childNode = agentNode("loop-child");
    const loopNode: WorkflowNodeConfig = {
        id: "looper",
        type: "loop",
        node: "loop-child",
        condition: "$.done == false",
        max_iterations: 10,
        depends_on: [],
    } as unknown as WorkflowNodeConfig;

    test("loop node height includes condition row when expanded", () => {
        const result = processWorkflowConfig(makeConfig([loopNode, childNode]));
        const looper = nodeById(result, "looper");
        // With condition + max_iterations, height > CONTAINER_HEADER alone
        expect(looper.height).toBeGreaterThan(NODE_HEIGHTS.CONTAINER_HEADER);
    });

    test("collapsed loop node uses CONTAINER_HEADER height", () => {
        const result = processWorkflowConfig(makeConfig([loopNode, childNode]), new Set(["looper"]));
        expect(nodeById(result, "looper").height).toBe(NODE_HEIGHTS.CONTAINER_HEADER);
    });

    test("loop node data carries condition, maxIterations, and childNodeId", () => {
        const result = processWorkflowConfig(makeConfig([loopNode, childNode]));
        const node = nodeById(result, "looper");
        expect(node.data.condition).toBe("$.done == false");
        expect(node.data.maxIterations).toBe(10);
        expect(node.data.childNodeId).toBe("loop-child");
    });
});

// ---------------------------------------------------------------------------
// Known workflows (agent treated as workflow)
// ---------------------------------------------------------------------------

describe("known workflows", () => {
    test("agent in knownWorkflows gets 'workflow' visual type", () => {
        const result = processWorkflowConfig(makeConfig([agentNode("sub-flow")]), new Set(), new Set(["sub-flow"]));
        expect(nodeById(result, "sub-flow").type).toBe("workflow");
    });

    test("explicit workflow type node gets 'workflow' visual type", () => {
        const workflowNode: WorkflowNodeConfig = {
            id: "wf1",
            type: "workflow",
            workflow_name: "my-workflow",
            depends_on: [],
        } as unknown as WorkflowNodeConfig;
        const result = processWorkflowConfig(makeConfig([workflowNode]));
        expect(nodeById(result, "wf1").type).toBe("workflow");
    });
});

// ---------------------------------------------------------------------------
// Layout invariants
// ---------------------------------------------------------------------------

describe("layout invariants", () => {
    test("all nodes have non-negative x and y", () => {
        const nodes = [agentNode("a"), agentNode("b", ["a"]), agentNode("c", ["a"])];
        const result = processWorkflowConfig(makeConfig(nodes));
        for (const node of result.nodes) {
            expect(node.x).toBeGreaterThanOrEqual(0);
            expect(node.y).toBeGreaterThanOrEqual(0);
        }
    });

    test("totalHeight >= height of all levels stacked", () => {
        const nodes = [agentNode("a"), agentNode("b", ["a"]), agentNode("c", ["b"])];
        const result = processWorkflowConfig(makeConfig(nodes));
        // 4 levels (start, a, b, c + end) × min AGENT height
        expect(result.totalHeight).toBeGreaterThan(NODE_HEIGHTS.AGENT * 3 + SPACING.VERTICAL * 2);
    });

    test("each edge references existing node ids", () => {
        const nodes = [agentNode("a"), agentNode("b", ["a"])];
        const result = processWorkflowConfig(makeConfig(nodes));
        const ids = new Set(result.nodes.map(n => n.id));
        for (const edge of result.edges) {
            expect(ids.has(edge.source)).toBe(true);
            expect(ids.has(edge.target)).toBe(true);
        }
    });

    test("no duplicate node ids", () => {
        const nodes = [agentNode("a"), agentNode("b", ["a"]), agentNode("c", ["b"])];
        const result = processWorkflowConfig(makeConfig(nodes));
        const ids = result.nodes.map(n => n.id);
        expect(new Set(ids).size).toBe(ids.length);
    });

    test("no duplicate edge ids", () => {
        const nodes = [agentNode("a"), agentNode("b", ["a"]), agentNode("c", ["a"])];
        const result = processWorkflowConfig(makeConfig(nodes));
        const edgeIds = result.edges.map(e => e.id);
        expect(new Set(edgeIds).size).toBe(edgeIds.length);
    });
});