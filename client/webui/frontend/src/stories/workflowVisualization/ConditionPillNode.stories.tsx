import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import ConditionPillNode from "@/lib/components/workflowVisualization/nodes/ConditionPillNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Components/WorkflowVisualization/ConditionPillNode",
    component: ConditionPillNode,
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
} satisfies Meta<typeof ConditionPillNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const conditionNode: LayoutNode = {
    id: "condition_1",
    type: "condition",
    x: 0,
    y: 0,
    width: 200,
    height: 28,
    children: [],
    data: {
        label: "{{priority}} == 'high'",
        caseNumber: 1,
        isDefaultCase: false,
    },
};

const defaultConditionNode: LayoutNode = {
    id: "condition_default",
    type: "condition",
    x: 0,
    y: 0,
    width: 120,
    height: 28,
    children: [],
    data: {
        label: "Default",
        isDefaultCase: true,
    },
};

export const Default: Story = {
    args: {
        node: conditionNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("1")).toBeInTheDocument();
    },
};

export const DefaultCase: Story = {
    args: {
        node: defaultConditionNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Default")).toBeInTheDocument();
    },
};
