import { describe, it, expect } from "vitest";
import { processWorkflowConfig } from "./layoutEngine";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";

describe("processWorkflowConfig – implicit switch dependencies", () => {
    it("creates edges from switch to case targets that have no explicit depends_on", () => {
        const config: WorkflowConfig = {
            nodes: [
                {
                    id: "start_agent",
                    type: "agent",
                    agent_name: "Starter",
                },
                {
                    id: "my_switch",
                    type: "switch",
                    depends_on: ["start_agent"],
                    cases: [
                        { condition: "x == 1", node: "branch_a" },
                        { condition: "x == 2", node: "branch_b" },
                    ],
                    default: "branch_default",
                },
                {
                    id: "branch_a",
                    type: "agent",
                    agent_name: "AgentA",
                    // No depends_on — should get implicit dependency on my_switch
                },
                {
                    id: "branch_b",
                    type: "agent",
                    agent_name: "AgentB",
                    // No depends_on — should get implicit dependency on my_switch
                },
                {
                    id: "branch_default",
                    type: "agent",
                    agent_name: "AgentDefault",
                    // No depends_on — should get implicit dependency on my_switch
                },
            ],
        };

        const result = processWorkflowConfig(config);

        // Switch edges are routed through condition pill nodes:
        //   my_switch -> __condition_my_switch_<target>__ -> <target>
        // Verify the full path exists for each branch target.
        for (const targetId of ["branch_a", "branch_b", "branch_default"]) {
            const pillId = `__condition_my_switch_${targetId}__`;
            const switchToPill = result.edges.find(e => e.source === "my_switch" && e.target === pillId);
            const pillToTarget = result.edges.find(e => e.source === pillId && e.target === targetId);
            expect(switchToPill, `expected edge my_switch -> ${pillId}`).toBeDefined();
            expect(pillToTarget, `expected edge ${pillId} -> ${targetId}`).toBeDefined();
        }
    });

    it("does not duplicate dependency when case target already has explicit depends_on", () => {
        const config: WorkflowConfig = {
            nodes: [
                {
                    id: "my_switch",
                    type: "switch",
                    cases: [{ condition: "x == 1", node: "branch_a" }],
                },
                {
                    id: "branch_a",
                    type: "agent",
                    agent_name: "AgentA",
                    depends_on: ["my_switch"], // Explicit dependency already present
                },
            ],
        };

        const result = processWorkflowConfig(config);

        // Edges are routed via condition pills, so check the full path exists exactly once
        const pillId = "__condition_my_switch_branch_a__";
        const switchToPill = result.edges.filter(e => e.source === "my_switch" && e.target === pillId);
        const pillToTarget = result.edges.filter(e => e.source === pillId && e.target === "branch_a");
        expect(switchToPill).toHaveLength(1);
        expect(pillToTarget).toHaveLength(1);
    });
});
