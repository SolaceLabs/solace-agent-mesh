import { describe, it, expect } from "vitest";
import { processAgentConfig } from "./layoutEngine";
import type { AgentDiagramConfig } from "./types";
import { AGENT_LAYOUT_CONSTANTS as C } from "./types";

describe("processAgentConfig", () => {
    it("returns a single agent-header node when there are no skills or tools", () => {
        const config: AgentDiagramConfig = { name: "TestAgent" };
        const result = processAgentConfig(config);

        expect(result.nodes).toHaveLength(1);
        expect(result.nodes[0].type).toBe("agent-header");
        expect(result.nodes[0].data.label).toBe("TestAgent");
        expect(result.edges).toHaveLength(0);
    });

    it("positions skills below the agent header", () => {
        const config: AgentDiagramConfig = {
            name: "MyAgent",
            skills: [{ name: "SkillA" }, { name: "SkillB" }],
        };
        const result = processAgentConfig(config);

        const agentNode = result.nodes.find(n => n.type === "agent-header")!;
        const skillNodes = result.nodes.filter(n => n.type === "skill");

        expect(skillNodes).toHaveLength(2);
        // Skills should be below the agent
        for (const skill of skillNodes) {
            expect(skill.y).toBeGreaterThan(agentNode.y + agentNode.height);
        }
    });

    it("positions tools to the right of the agent header", () => {
        const config: AgentDiagramConfig = {
            name: "MyAgent",
            tools: [{ tool_type: "mcp", tool_name: "ToolA" }],
        };
        const result = processAgentConfig(config);

        const agentNode = result.nodes.find(n => n.type === "agent-header")!;
        const toolNodes = result.nodes.filter(n => n.type === "tool");

        expect(toolNodes).toHaveLength(1);
        expect(toolNodes[0].x).toBeGreaterThan(agentNode.x + agentNode.width);
    });

    it("creates edges from agent header to each skill and tool", () => {
        const config: AgentDiagramConfig = {
            name: "MyAgent",
            skills: [{ name: "SkillA" }],
            tools: [{ tool_type: "mcp", tool_name: "ToolA" }],
        };
        const result = processAgentConfig(config);

        expect(result.edges).toHaveLength(2);
        for (const edge of result.edges) {
            expect(edge.source).toBe("agent-header");
        }
        const targets = result.edges.map(e => e.target);
        expect(targets).toContain("skill-0");
        expect(targets).toContain("tool-0");
    });

    it("skips builtin-group tools", () => {
        const config: AgentDiagramConfig = {
            name: "MyAgent",
            tools: [
                { tool_type: "builtin-group", tool_name: "Builtins" },
                { tool_type: "mcp", tool_name: "RealTool" },
            ],
        };
        const result = processAgentConfig(config);

        const toolNodes = result.nodes.filter(n => n.type === "tool");
        expect(toolNodes).toHaveLength(1);
        expect(toolNodes[0].data.label).toBe("RealTool");
    });

    it("renders toolsets as toolset-group nodes", () => {
        const config: AgentDiagramConfig = {
            name: "MyAgent",
            toolsets: ["artifact_management", "data_tools"],
        };
        const result = processAgentConfig(config);

        const toolsetNodes = result.nodes.filter(n => n.type === "toolset-group");
        expect(toolsetNodes).toHaveLength(2);
        expect(toolsetNodes[0].data.label).toBe("Artifact Management");
        expect(toolsetNodes[1].data.label).toBe("Data Tools");
    });

    it("calculates totalWidth and totalHeight including padding", () => {
        const config: AgentDiagramConfig = { name: "Alone" };
        const result = processAgentConfig(config);

        expect(result.totalWidth).toBe(C.PADDING + C.NODE_WIDTHS.AGENT_HEADER + C.PADDING);
        expect(result.totalHeight).toBe(C.PADDING + C.NODE_HEIGHTS.AGENT_HEADER + C.PADDING);
    });

    it("stacks multiple tools vertically with correct spacing", () => {
        const config: AgentDiagramConfig = {
            name: "MyAgent",
            tools: [
                { tool_type: "mcp", tool_name: "T1" },
                { tool_type: "mcp", tool_name: "T2" },
                { tool_type: "mcp", tool_name: "T3" },
            ],
        };
        const result = processAgentConfig(config);

        const toolNodes = result.nodes.filter(n => n.type === "tool");
        expect(toolNodes).toHaveLength(3);

        for (let i = 1; i < toolNodes.length; i++) {
            const gap = toolNodes[i].y - toolNodes[i - 1].y;
            expect(gap).toBe(C.NODE_HEIGHTS.TOOL + C.SPACING.HORIZONTAL);
        }
    });

    it("handles config with both skills, tools, and toolsets", () => {
        const config: AgentDiagramConfig = {
            name: "FullAgent",
            description: "A fully loaded agent",
            skills: [{ name: "S1" }, { name: "S2" }],
            tools: [{ tool_type: "mcp", tool_name: "T1" }],
            toolsets: ["my_toolset"],
        };
        const result = processAgentConfig(config);

        const agentNodes = result.nodes.filter(n => n.type === "agent-header");
        const skillNodes = result.nodes.filter(n => n.type === "skill");
        const toolNodes = result.nodes.filter(n => n.type === "tool");
        const toolsetNodes = result.nodes.filter(n => n.type === "toolset-group");

        expect(agentNodes).toHaveLength(1);
        expect(skillNodes).toHaveLength(2);
        expect(toolNodes).toHaveLength(1);
        expect(toolsetNodes).toHaveLength(1);

        // toolset + tool = 2 right-column nodes, 2 skills = 2 bottom nodes → 4 edges
        expect(result.edges).toHaveLength(4);
    });
});
