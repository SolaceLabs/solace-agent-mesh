import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, within } from "storybook/test";
import AgentNode from "@/lib/components/workflowVisualization/nodes/AgentNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";
import { assertSelectedAndHighlightedByText, centeredWorkflowNodeDecorator, clickNodeAndAssert, createLayoutNode } from "./helpers/workflowStoryHelpers";

const meta = {
    title: "Workflow/WorkflowVisualization/AgentNode",
    component: AgentNode,
    parameters: { layout: "centered" },
    decorators: [centeredWorkflowNodeDecorator],
} satisfies Meta<typeof AgentNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const agentNode: LayoutNode = createLayoutNode({
    id: "validate_order",
    type: "agent",
    data: { label: "OrderValidator" },
});

export const Default: Story = {
    args: { node: agentNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("OrderValidator")).toBeInTheDocument();
        expect(canvas.getByText("Agent")).toBeInTheDocument();
    },
};

export const PrefersAgentName: Story = {
    args: {
        node: { ...agentNode, data: { label: "fallback", agentName: "PreferredName" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("PreferredName")).toBeInTheDocument();
    },
};

export const SelectedAndHighlighted: Story = {
    args: { node: agentNode, isSelected: true, isHighlighted: true },
    play: async ({ canvasElement }) => {
        await assertSelectedAndHighlightedByText(canvasElement, "OrderValidator");
    },
};

export const ClickInteraction: Story = {
    args: { node: agentNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        await clickNodeAndAssert(canvasElement, "OrderValidator", args.onClick, agentNode);
    },
};
