import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import AgentNode from "@/lib/components/workflowVisualization/nodes/AgentNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Components/WorkflowVisualization/AgentNode",
    component: AgentNode,
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
} satisfies Meta<typeof AgentNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const agentNode: LayoutNode = {
    id: "validate_order",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: {
        label: "OrderValidator",
    },
};

export const Default: Story = {
    args: {
        node: agentNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("OrderValidator")).toBeInTheDocument();
        expect(canvas.getByText("Agent")).toBeInTheDocument();
    },
};
