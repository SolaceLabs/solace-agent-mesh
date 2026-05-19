import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within, userEvent, fn } from "storybook/test";

import AgentNode from "@/lib/components/activities/FlowChart/nodes/AgentNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/AgentNode",
    component: AgentNode,
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
} satisfies Meta<typeof AgentNode>;

export default meta;
type Story = StoryObj<typeof meta>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const leafNode: LayoutNode = {
    id: "agent-leaf",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "MyAgent" },
};

const toolChild: LayoutNode = {
    id: "tool-1",
    type: "tool",
    x: 0,
    y: 0,
    width: 280,
    height: 50,
    children: [],
    data: { label: "search_tool" },
};

const agentWithChildren: LayoutNode = {
    id: "agent-with-children",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 200,
    children: [toolChild],
    data: { label: "ParentAgent" },
};

const pillNode: LayoutNode = {
    id: "pill-node",
    type: "agent",
    x: 0,
    y: 0,
    width: 120,
    height: 40,
    children: [],
    data: { label: "Start", variant: "pill" },
};

const branchChild1: LayoutNode = {
    id: "branch-child-1",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "BranchAgent1" },
};

const branchChild2: LayoutNode = {
    id: "branch-child-2",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "BranchAgent2" },
};

// ---------------------------------------------------------------------------
// Regular node variants
// ---------------------------------------------------------------------------

export const Default: Story = {
    args: { node: leafNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyAgent")).toBeInTheDocument();
        expect(canvas.queryByRole("button", { name: /expand/i })).not.toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: leafNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyAgent")).toBeInTheDocument();
    },
};

export const Processing: Story = {
    args: { node: { ...leafNode, data: { ...leafNode.data, status: "in-progress" } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyAgent")).toBeInTheDocument();
        expect(canvasElement.querySelector(".processing-halo")).toBeInTheDocument();
    },
};

export const Skipped: Story = {
    args: { node: { ...leafNode, data: { ...leafNode.data, isSkipped: true } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyAgent")).toBeInTheDocument();
    },
};

export const Collapsed: Story = {
    args: {
        node: { ...agentWithChildren, data: { ...agentWithChildren.data, isCollapsed: true } },
        onExpand: fn(),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ParentAgent")).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: /expand/i })).toBeInTheDocument();
        expect(canvas.queryByText("search_tool")).not.toBeInTheDocument();
    },
};

export const WithChildren: Story = {
    args: { node: agentWithChildren },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ParentAgent")).toBeInTheDocument();
        expect(canvas.getByText("search_tool")).toBeInTheDocument();
    },
};

export const WithParallelBranches: Story = {
    args: {
        node: {
            ...leafNode,
            id: "agent-parallel",
            parallelBranches: [[branchChild1], [branchChild2]],
            data: { label: "ParallelAgent" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ParallelAgent")).toBeInTheDocument();
        expect(canvas.getByText("BranchAgent1")).toBeInTheDocument();
        expect(canvas.getByText("BranchAgent2")).toBeInTheDocument();
    },
};

// ---------------------------------------------------------------------------
// Pill variants
// ---------------------------------------------------------------------------

export const PillSimple: Story = {
    args: { node: pillNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Start")).toBeInTheDocument();
    },
};

export const PillError: Story = {
    args: { node: { ...pillNode, data: { ...pillNode.data, label: "Failed", status: "error" } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Failed")).toBeInTheDocument();
    },
};

export const PillWithSequentialChildren: Story = {
    args: {
        node: {
            ...pillNode,
            id: "pill-sequential",
            children: [toolChild],
            data: { ...pillNode.data, label: "Fork" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Fork")).toBeInTheDocument();
        expect(canvas.getByText("search_tool")).toBeInTheDocument();
    },
};

export const PillWithParallelBranches: Story = {
    args: {
        node: {
            ...pillNode,
            id: "pill-parallel",
            parallelBranches: [[branchChild1], [branchChild2]],
            data: { ...pillNode.data, label: "Map" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
        expect(canvas.getByText("BranchAgent1")).toBeInTheDocument();
        expect(canvas.getByText("BranchAgent2")).toBeInTheDocument();
    },
};

// ---------------------------------------------------------------------------
// Interaction tests
// ---------------------------------------------------------------------------

export const ClickInteraction: Story = {
    args: {
        node: leafNode,
        onClick: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup();
        await user.click(await canvas.findByText("MyAgent"));
        expect(args.onClick).toHaveBeenCalledOnce();
        expect(args.onClick).toHaveBeenCalledWith(leafNode);
    },
};

export const ExpandInteraction: Story = {
    args: {
        node: { ...agentWithChildren, data: { ...agentWithChildren.data, isCollapsed: true } },
        onExpand: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup();
        await user.click(await canvas.findByRole("button", { name: /expand/i }));
        expect(args.onExpand).toHaveBeenCalledOnce();
        expect(args.onExpand).toHaveBeenCalledWith(agentWithChildren.id);
    },
};

export const CollapseInteraction: Story = {
    args: {
        node: { ...agentWithChildren, data: { ...agentWithChildren.data, isExpanded: true } },
        onCollapse: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup();
        await user.click(await canvas.findByRole("button", { name: /collapse/i }));
        expect(args.onCollapse).toHaveBeenCalledOnce();
        expect(args.onCollapse).toHaveBeenCalledWith(agentWithChildren.id);
    },
};
