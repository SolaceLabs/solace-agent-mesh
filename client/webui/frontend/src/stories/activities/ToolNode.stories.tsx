import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import ToolNode from "@/lib/components/activities/FlowChart/nodes/ToolNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/ToolNode",
    component: ToolNode,
    parameters: {
        layout: "centered",
    },
    decorators: [
        Story => (
            <div className="flex items-center justify-center bg-(--background-w10) p-8">
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof ToolNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseNode: LayoutNode = {
    id: "tool-1",
    type: "tool",
    x: 0,
    y: 0,
    width: 225,
    height: 50,
    children: [],
    data: {
        label: "search_tool",
    },
};

export const Default: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("search_tool")).toBeInTheDocument();
        expect(canvasElement.querySelector('[data-testid="tool-node-search_tool"]')).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: baseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const node = canvasElement.querySelector('[data-testid="tool-node-search_tool"]') as HTMLElement;
        expect(node.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const Processing: Story = {
    args: { node: { ...baseNode, data: { ...baseNode.data, status: "in-progress" } } },
    play: async ({ canvasElement }) => {
        const node = canvasElement.querySelector('[data-testid="tool-node-search_tool"]') as HTMLElement;
        expect(node.className).toMatch(/processing-halo/);
    },
};

export const NotProcessingWhenCompleted: Story = {
    args: { node: { ...baseNode, data: { ...baseNode.data, status: "completed" } } },
    play: async ({ canvasElement }) => {
        const node = canvasElement.querySelector('[data-testid="tool-node-search_tool"]') as HTMLElement;
        expect(node.className).not.toMatch(/processing-halo/);
    },
};

export const WithSingleArtifact: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                createdArtifacts: [{ filename: "result.json" }],
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("1 artifact")).toBeInTheDocument();
    },
};

export const WithMultipleArtifacts: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                createdArtifacts: [
                    { filename: "a.json" },
                    { filename: "b.json" },
                    { filename: "c.json" },
                ],
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("3 artifacts")).toBeInTheDocument();
    },
};

export const TruncatesLongLabel: Story = {
    args: {
        node: { ...baseNode, data: { ...baseNode.data, label: "an_unreasonably_long_tool_name_that_overflows" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("an_unreasonably_long_tool_name_that_overflows");
        expect(label.className).toMatch(/truncate/);
    },
};

export const InvokesOnClick: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const node = canvasElement.querySelector('[data-testid="tool-node-search_tool"]') as HTMLElement;
        await userEvent.click(node);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(baseNode);
    },
};

export const InvokesOnKeyboardActivation: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const node = canvasElement.querySelector('[data-testid="tool-node-search_tool"]') as HTMLElement;
        node.focus();
        await userEvent.keyboard("{Enter}");
        expect(args.onClick).toHaveBeenCalledTimes(1);
        await userEvent.keyboard(" ");
        expect(args.onClick).toHaveBeenCalledTimes(2);
    },
};
