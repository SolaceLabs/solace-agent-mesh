import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import WorkflowRefNode from "@/lib/components/workflowVisualization/nodes/WorkflowRefNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow/WorkflowVisualization/WorkflowRefNode",
    component: WorkflowRefNode,
    parameters: { layout: "centered" },
    decorators: [
        Story => (
            <div className="flex items-center justify-center bg-(--background-w10) p-8">
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof WorkflowRefNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const workflowRefNode: LayoutNode = {
    id: "nested_workflow",
    type: "workflow",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: {
        workflowName: "NestedWorkflow",
        label: "Process Suborder",
    },
};

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
        const canvas = within(canvasElement);
        const wrapper = (await canvas.findByText("NestedWorkflow")).closest("[role='button']") as HTMLElement;
        expect(wrapper).toHaveAttribute("data-selected", "true");
        expect(wrapper).toHaveAttribute("data-highlighted", "true");
    },
};

export const ClickInteraction: Story = {
    args: { node: workflowRefNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await userEvent.click(await canvas.findByText("NestedWorkflow"));
        expect(args.onClick).toHaveBeenCalledWith(workflowRefNode);
    },
};
