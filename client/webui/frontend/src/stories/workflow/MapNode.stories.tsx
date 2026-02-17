import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import MapNode from "@/lib/components/workflowVisualization/nodes/MapNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Components/WorkflowVisualization/MapNode",
    component: MapNode,
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
} satisfies Meta<typeof MapNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const mapNode: LayoutNode = {
    id: "process_items",
    type: "map",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: {
        label: "Process Items",
        items: "{{workflow.input.order_items}}",
    },
};

const mapNodeWithChildren: LayoutNode = {
    id: "process_items",
    type: "map",
    x: 0,
    y: 0,
    width: 328,
    height: 148,
    children: [
        {
            id: "item_processor",
            type: "agent",
            x: 0,
            y: 0,
            width: 280,
            height: 56,
            children: [],
            data: {
                label: "ItemProcessor",
            },
        },
    ],
    data: {
        label: "Process Items",
        items: "{{workflow.input.order_items}}",
    },
};

export const Default: Story = {
    args: {
        node: mapNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
    },
};

export const WithChildren: Story = {
    args: {
        node: mapNodeWithChildren,
        renderChildren: children => children.map(child => <div key={child.id}>{child.data.label}</div>),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
        expect(await canvas.findByText("ItemProcessor")).toBeInTheDocument();
    },
};
