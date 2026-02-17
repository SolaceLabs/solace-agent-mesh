import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import SwitchNode from "@/lib/components/workflowVisualization/nodes/SwitchNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Components/WorkflowVisualization/SwitchNode",
    component: SwitchNode,
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
} satisfies Meta<typeof SwitchNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const switchNode: LayoutNode = {
    id: "check_priority",
    type: "switch",
    x: 0,
    y: 0,
    width: 280,
    height: 120,
    children: [],
    data: {
        label: "Check Priority",
        cases: [
            { condition: "{{priority}} == 'high'", node: "fast_path" },
            { condition: "{{priority}} == 'low'", node: "slow_path" },
        ],
    },
};

export const Default: Story = {
    args: {
        node: switchNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Switch")).toBeInTheDocument();
        expect(canvas.getByText("2 cases")).toBeInTheDocument();
    },
};
