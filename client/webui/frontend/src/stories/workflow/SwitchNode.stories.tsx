import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, within } from "storybook/test";
import SwitchNode from "@/lib/components/workflowVisualization/nodes/SwitchNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";
import { assertSelectedAndHighlightedByText, centeredWorkflowNodeDecorator, clickNodeAndAssert, createLayoutNode } from "./helpers/workflowStoryHelpers";

const meta = {
    title: "Workflow/WorkflowVisualization/SwitchNode",
    component: SwitchNode,
    parameters: { layout: "centered" },
    decorators: [centeredWorkflowNodeDecorator],
} satisfies Meta<typeof SwitchNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const switchNode: LayoutNode = createLayoutNode({
    id: "check_priority",
    type: "switch",
    width: 280,
    height: 120,
    data: {
        label: "Check Priority",
        cases: [
            { condition: "{{priority}} == 'high'", node: "fast_path" },
            { condition: "{{priority}} == 'low'", node: "slow_path" },
        ],
    },
});

export const Default: Story = {
    args: { node: switchNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Switch")).toBeInTheDocument();
        expect(canvas.getByText("2 cases")).toBeInTheDocument();
        expect(canvas.getByText("{{priority}} == 'high'")).toBeInTheDocument();
    },
};

export const WithDefaultCase: Story = {
    args: {
        node: {
            ...switchNode,
            data: { ...switchNode.data, defaultCase: "fallback_path" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("3 cases")).toBeInTheDocument();
        expect(canvas.getByText("default")).toBeInTheDocument();
    },
};

export const NoCases: Story = {
    args: {
        node: { ...switchNode, data: { label: "Empty Switch" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("0 cases")).toBeInTheDocument();
    },
};

export const SelectedAndHighlighted: Story = {
    args: { node: switchNode, isSelected: true, isHighlighted: true },
    play: async ({ canvasElement }) => {
        await assertSelectedAndHighlightedByText(canvasElement, "Switch");
    },
};

export const ClickInteraction: Story = {
    args: { node: switchNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        await clickNodeAndAssert(canvasElement, "Switch", args.onClick, switchNode);
    },
};
