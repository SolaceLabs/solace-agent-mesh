import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import LoopNode from "@/lib/components/workflowVisualization/nodes/LoopNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Components/WorkflowVisualization/LoopNode",
    component: LoopNode,
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
} satisfies Meta<typeof LoopNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const loopNode: LayoutNode = {
    id: "retry_loop",
    type: "loop",
    x: 0,
    y: 0,
    width: 280,
    height: 120,
    children: [],
    data: {
        label: "Retry Loop",
        condition: "{{check_status.output.ready}} == false",
        maxIterations: 5,
        delay: "2s",
    },
};

const loopNodeWithChildren: LayoutNode = {
    id: "retry_loop",
    type: "loop",
    x: 0,
    y: 0,
    width: 328,
    height: 176,
    children: [
        {
            id: "check_status",
            type: "agent",
            x: 0,
            y: 0,
            width: 280,
            height: 56,
            children: [],
            data: {
                label: "StatusChecker",
            },
        },
    ],
    data: {
        label: "Retry Loop",
        condition: "{{check_status.output.ready}} == false",
        maxIterations: 5,
        delay: "2s",
    },
};

export const Default: Story = {
    args: {
        node: loopNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(canvas.getByText("max: 5")).toBeInTheDocument();
    },
};

export const WithChildren: Story = {
    args: {
        node: loopNodeWithChildren,
        renderChildren: children => children.map(child => <div key={child.id}>{child.data.label}</div>),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(await canvas.findByText("StatusChecker")).toBeInTheDocument();
    },
};
