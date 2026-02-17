import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen } from "storybook/test";
import EndNode from "@/lib/components/workflowVisualization/nodes/EndNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Components/WorkflowVisualization/EndNode",
    component: EndNode,
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
} satisfies Meta<typeof EndNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const endNode: LayoutNode = {
    id: "__end__",
    type: "end",
    x: 0,
    y: 0,
    width: 100,
    height: 40,
    children: [],
    data: {
        label: "End",
    },
};

export const Default: Story = {
    args: {
        node: endNode,
    },
    play: async () => {
        const endNodeElement = screen.getByText("End");
        expect(endNodeElement).toBeInTheDocument();

        const container = endNodeElement.closest("div");
        expect(container?.onclick).toBeNull();
    },
};
