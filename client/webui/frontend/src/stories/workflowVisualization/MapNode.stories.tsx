import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import MapNode from "@/lib/components/workflowVisualization/nodes/MapNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "WorkflowVisualization/MapNode",
    component: MapNode,
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
} satisfies Meta<typeof MapNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const innerAgent: LayoutNode = {
    id: "agent-1",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "InnerAgent" },
};

const compactNode: LayoutNode = {
    id: "map-compact",
    type: "map",
    x: 0,
    y: 0,
    width: 320,
    height: 80,
    children: [],
    data: { label: "Map" },
};

const expandedNode: LayoutNode = {
    id: "map-expanded",
    type: "map",
    x: 0,
    y: 0,
    width: 320,
    height: 300,
    children: [innerAgent],
    data: { label: "Map" },
};

export const CompactNoChildren: Story = {
    args: { node: compactNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
        expect(canvas.queryByRole("button", { name: /expand/i })).not.toBeInTheDocument();
    },
};

export const CompactWithChildNodeIdShowsExpandButton: Story = {
    args: {
        node: { ...compactNode, data: { ...compactNode.data, childNodeId: "agent-1" } },
        onExpand: fn(),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("Map");
        expect(canvas.getByRole("button", { name: /expand/i })).toBeInTheDocument();
    },
};

export const CollapsedFromExpanded: Story = {
    args: {
        node: { ...expandedNode, isCollapsed: true },
        onExpand: fn(),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: /expand/i })).toBeInTheDocument();
    },
};

export const Expanded: Story = {
    args: {
        node: expandedNode,
        onCollapse: fn(),
        renderChildren: children => children.map(c => <div key={c.id}>{c.data.label}</div>),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
        expect(canvas.getByText("InnerAgent")).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: /collapse/i })).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: compactNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("Map");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const Highlighted: Story = {
    args: { node: compactNode, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("Map");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/ring-2/);
    },
};

export const InvokesOnExpand: Story = {
    args: {
        node: {
            ...compactNode,
            isCollapsed: true,
            data: { ...compactNode.data, childNodeId: "agent-1" },
        },
        onExpand: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("Map");
        await userEvent.click(canvas.getByRole("button", { name: /expand/i }));
        expect(args.onExpand).toHaveBeenCalledTimes(1);
        expect(args.onExpand).toHaveBeenCalledWith(compactNode.id);
    },
};

export const InvokesOnCollapse: Story = {
    args: { node: expandedNode, onCollapse: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("Map");
        await userEvent.click(canvas.getByRole("button", { name: /collapse/i }));
        expect(args.onCollapse).toHaveBeenCalledTimes(1);
        expect(args.onCollapse).toHaveBeenCalledWith(expandedNode.id);
    },
};

export const InvokesOnClick: Story = {
    args: { node: compactNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("Map");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(compactNode);
    },
};
