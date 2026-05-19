import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import WorkflowGroup from "@/lib/components/activities/FlowChart/nodes/WorkflowGroup";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/WorkflowGroup",
    component: WorkflowGroup,
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
} satisfies Meta<typeof WorkflowGroup>;

export default meta;
type Story = StoryObj<typeof meta>;

const agentChild = (id: string, label: string): LayoutNode => ({
    id,
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label },
});

const collapsedNode: LayoutNode = {
    id: "wf-collapsed",
    type: "group",
    x: 0,
    y: 0,
    width: 280,
    height: 50,
    children: [],
    data: { label: "MyWorkflow", isCollapsed: true },
};

const expandedNode: LayoutNode = {
    id: "wf-expanded",
    type: "group",
    x: 0,
    y: 0,
    width: 320,
    height: 300,
    children: [agentChild("agent-1", "InnerAgent")],
    data: { label: "MyWorkflow", isExpanded: true },
};

export const Collapsed: Story = {
    args: {
        node: collapsedNode,
        onExpand: fn(),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyWorkflow")).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: /expand/i })).toBeInTheDocument();
    },
};

export const CollapsedWithoutExpandHandler: Story = {
    args: { node: collapsedNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyWorkflow")).toBeInTheDocument();
        expect(canvas.queryByRole("button", { name: /expand/i })).not.toBeInTheDocument();
    },
};

export const CollapsedSelected: Story = {
    args: { node: collapsedNode, isSelected: true, onExpand: fn() },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyWorkflow");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const CollapsedProcessing: Story = {
    args: {
        node: { ...collapsedNode, data: { ...collapsedNode.data, hasProcessingChildren: true } },
        onExpand: fn(),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyWorkflow");
        // Halo wraps the collapsed div itself
        const wrapper = label.closest("[role='button']") as HTMLElement;
        expect(wrapper.className).toMatch(/processing-halo/);
    },
};

export const Expanded: Story = {
    args: { node: expandedNode, onCollapse: fn() },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyWorkflow")).toBeInTheDocument();
        expect(canvas.getByText("InnerAgent")).toBeInTheDocument();
    },
};

export const ExpandedShowsCollapseButton: Story = {
    args: { node: expandedNode, onCollapse: fn() },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("MyWorkflow");
        expect(canvas.getByRole("button", { name: /collapse/i })).toBeInTheDocument();
    },
};

export const ExpandedHidesCollapseButtonWithoutHandler: Story = {
    args: { node: expandedNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("MyWorkflow");
        expect(canvas.queryByRole("button", { name: /collapse/i })).not.toBeInTheDocument();
    },
};

export const InvokesOnExpand: Story = {
    args: { node: collapsedNode, onExpand: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("MyWorkflow");
        await userEvent.click(canvas.getByRole("button", { name: /expand/i }));
        expect(args.onExpand).toHaveBeenCalledTimes(1);
        expect(args.onExpand).toHaveBeenCalledWith(collapsedNode.id);
    },
};

export const InvokesOnCollapse: Story = {
    args: { node: expandedNode, onCollapse: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("MyWorkflow");
        await userEvent.click(canvas.getByRole("button", { name: /collapse/i }));
        expect(args.onCollapse).toHaveBeenCalledTimes(1);
        expect(args.onCollapse).toHaveBeenCalledWith(expandedNode.id);
    },
};

export const InvokesOnClickWhenCollapsed: Story = {
    args: { node: collapsedNode, onClick: fn(), onExpand: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyWorkflow");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(collapsedNode);
    },
};

export const InvokesOnClickOnExpandedHeader: Story = {
    args: { node: expandedNode, onClick: fn(), onCollapse: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyWorkflow");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(expandedNode);
    },
};

export const InvokesOnChildClick: Story = {
    args: { node: expandedNode, onChildClick: fn(), onCollapse: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const child = await canvas.findByText("InnerAgent");
        await userEvent.click(child);
        expect(args.onChildClick).toHaveBeenCalledTimes(1);
    },
};
