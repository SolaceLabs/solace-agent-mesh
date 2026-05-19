import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, within } from "storybook/test";
import WorkflowRefNode from "@/lib/components/workflowVisualization/nodes/WorkflowRefNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";
import { assertSelectedAndHighlightedByText, centeredWorkflowNodeDecorator, clickNodeAndAssert, createLayoutNode } from "./helpers/workflowStoryHelpers";

const meta = {
    title: "Workflow/WorkflowVisualization/WorkflowRefNode",
    component: WorkflowRefNode,
    parameters: { layout: "centered" },
    decorators: [centeredWorkflowNodeDecorator],
} satisfies Meta<typeof WorkflowRefNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const workflowRefNode: LayoutNode = createLayoutNode({
    id: "nested_workflow",
    type: "workflow",
    data: {
        workflowName: "NestedWorkflow",
        label: "Process Suborder",
    },
});

export const Default: Story = {
    args: { node: workflowRefNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("NestedWorkflow")).toBeInTheDocument();
        expect(canvas.getByText("Workflow")).toBeInTheDocument();
    },
};

export const FallsBackToLabel: Story = {
    args: {
        node: { ...workflowRefNode, data: { label: "OnlyLabel" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("OnlyLabel")).toBeInTheDocument();
    },
};

export const SelectedAndHighlighted: Story = {
    args: { node: workflowRefNode, isSelected: true, isHighlighted: true },
    play: async ({ canvasElement }) => {
        await assertSelectedAndHighlightedByText(canvasElement, "NestedWorkflow");
    },
};

export const ClickInteraction: Story = {
    args: { node: workflowRefNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        await clickNodeAndAssert(canvasElement, "NestedWorkflow", args.onClick, workflowRefNode);
    },
};
