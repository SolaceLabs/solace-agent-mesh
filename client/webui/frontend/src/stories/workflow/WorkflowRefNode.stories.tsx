import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import WorkflowRefNode from "@/lib/components/workflowVisualization/nodes/WorkflowRefNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow/WorkflowVisualization/WorkflowRefNode",
    component: WorkflowRefNode,
    parameters: {
        layout: "centered",
    },
    decorators: [
        Story => (
            <div className="flex items-center justify-center bg-white p-8 dark:bg-gray-900">
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
    args: {
        node: workflowRefNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("NestedWorkflow")).toBeInTheDocument();
        expect(canvas.getByText("Workflow")).toBeInTheDocument();
    },
};
