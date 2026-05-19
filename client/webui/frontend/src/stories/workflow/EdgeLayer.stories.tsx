import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import EdgeLayer from "@/lib/components/workflowVisualization/edges/EdgeLayer";
import type { Edge } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow/WorkflowVisualization/EdgeLayer",
    component: EdgeLayer,
    parameters: { layout: "centered" },
    decorators: [
        Story => (
            <div className="relative bg-(--background-w10) p-8" style={{ width: 400, height: 300 }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof EdgeLayer>;

export default meta;
type Story = StoryObj<typeof meta>;

const bezierEdge: Edge = {
    id: "edge_bezier",
    source: "a",
    target: "b",
    sourceX: 50,
    sourceY: 50,
    targetX: 250,
    targetY: 200,
    label: "yes",
};

const straightEdge: Edge = {
    id: "edge_straight",
    source: "c",
    target: "d",
    sourceX: 100,
    sourceY: 100,
    targetX: 100,
    targetY: 250,
    isStraight: true,
};

const conditionPillEdge: Edge = {
    id: "edge_pill",
    source: "switch_1",
    target: "__condition_1",
    sourceX: 200,
    sourceY: 50,
    targetX: 200,
    targetY: 150,
};

export const Empty: Story = {
    args: { edges: [], width: 400, height: 300 },
    play: async ({ canvasElement }) => {
        const svg = canvasElement.querySelector("[data-testid='edge-layer']");
        expect(svg).toBeInTheDocument();
        expect(canvasElement.querySelectorAll("[data-testid='edge-group']").length).toBe(0);
    },
};

export const BezierEdgeWithLabel: Story = {
    args: { edges: [bezierEdge], width: 400, height: 300 },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("yes")).toBeInTheDocument();
        const renderedPath = canvasElement.querySelector("[data-testid='edge-path'][data-edge-id='edge_bezier']") as SVGPathElement | null;
        expect(renderedPath?.getAttribute("marker-end")).toContain("arrowhead");
    },
};

export const StraightEdgeNoLabel: Story = {
    args: { edges: [straightEdge], width: 400, height: 300 },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const renderedPath = canvasElement.querySelector("[data-testid='edge-path'][data-edge-id='edge_straight']") as SVGPathElement | null;
        expect(renderedPath?.getAttribute("d")).toMatch(/^M .* L .*/);
        expect(canvas.queryByText("yes")).not.toBeInTheDocument();
    },
};

export const ConditionPillEdgeHasNoArrowhead: Story = {
    args: { edges: [conditionPillEdge], width: 400, height: 300 },
    play: async ({ canvasElement }) => {
        const renderedPath = canvasElement.querySelector("[data-testid='edge-path'][data-edge-id='edge_pill']") as SVGPathElement | null;
        expect(renderedPath?.getAttribute("marker-end")).toBeNull();
    },
};

export const MultipleEdges: Story = {
    args: { edges: [bezierEdge, straightEdge, conditionPillEdge], width: 400, height: 300 },
    play: async ({ canvasElement }) => {
        expect(canvasElement.querySelectorAll("[data-testid='edge-group']").length).toBe(3);
    },
};
