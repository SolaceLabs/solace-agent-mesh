import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen } from "storybook/test";
import StartNode from "@/lib/components/workflowVisualization/nodes/StartNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow Visualization/StartNode",
    component: StartNode,
    parameters: {
        layout: "fullscreen",
    },
    decorators: [
        Story => (
            <div className="flex h-screen items-center justify-center bg-white p-8 dark:bg-gray-900">
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof StartNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const startNode: LayoutNode = {
    id: "__start__",
    type: "start",
    x: 0,
    y: 0,
    width: 100,
    height: 40,
    children: [],
    data: {
        label: "Start",
    },
};

export const Default: Story = {
    args: {
        node: startNode,
        isHighlighted: false,
    },
    play: async () => {
        const startNodeElement = screen.getByText("Start");
        expect(startNodeElement).toBeInTheDocument();

        const container = startNodeElement.closest("div");
        expect(container?.onclick).toBeNull();
    },
};
