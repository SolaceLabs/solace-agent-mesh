import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import LoopNode from "@/lib/components/workflowVisualization/nodes/LoopNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow/WorkflowVisualization/LoopNode",
    component: LoopNode,
    parameters: { layout: "centered" },
    decorators: [
        Story => (
            <div className="flex items-center justify-center bg-(--background-w10) p-8">
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
    height: 80,
    children: [],
    data: {
        label: "Retry Loop",
        condition: "{{check_status.output.ready}} == false",
        maxIterations: 5,
        delay: "2s",
    },
};

const childAgent: LayoutNode = {
    id: "check_status",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "StatusChecker" },
};

const loopNodeWithChildren: LayoutNode = {
    ...loopNode,
    width: 328,
    height: 200,
    children: [childAgent],
};

export const CollapsedLeaf: Story = {
    args: { node: loopNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(canvas.getByText("max: 5")).toBeInTheDocument();
    },
};

export const CollapsedWithChildAvailable: Story = {
    args: {
        node: { ...loopNode, isCollapsed: true, data: { ...loopNode.data, childNodeId: "check_status" } },
        onExpand: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const expandBtn = await canvas.findByRole("button", { name: /expand/i });
        await userEvent.click(expandBtn);
        expect(args.onExpand).toHaveBeenCalledWith("retry_loop");
    },
};

export const ExpandedWithChildren: Story = {
    args: {
        node: loopNodeWithChildren,
        renderChildren: children => children.map(child => <div key={child.id}>{child.data.label}</div>),
        onCollapse: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(canvas.getByText("StatusChecker")).toBeInTheDocument();
        expect(canvas.getByText(/while:/)).toBeInTheDocument();
        const collapseBtn = canvas.getByRole("button", { name: /collapse/i });
        await userEvent.click(collapseBtn);
        expect(args.onCollapse).toHaveBeenCalledWith("retry_loop");
    },
};

export const ExpandedNoCondition: Story = {
    args: {
        node: { ...loopNodeWithChildren, data: { label: "Plain Loop" } },
        renderChildren: children => children.map(child => <div key={child.id}>{child.data.label}</div>),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(canvas.queryByText(/while:/)).not.toBeInTheDocument();
    },
};

export const TruncatesLongCondition: Story = {
    args: {
        node: {
            ...loopNodeWithChildren,
            data: {
                ...loopNode.data,
                condition: "{{very_long_node_name.output.some_property}} == 'some-really-long-expected-value'",
            },
        },
        renderChildren: children => children.map(child => <div key={child.id}>{child.data.label}</div>),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText(/while:.*\.\.\./)).toBeInTheDocument();
    },
};

export const SelectedAndHighlighted: Story = {
    args: { node: loopNode, isSelected: true, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const wrapper = (await canvas.findByText("Loop")).closest("[role='button']") as HTMLElement;
        expect(wrapper).toHaveAttribute("data-selected", "true");
        expect(wrapper).toHaveAttribute("data-highlighted", "true");
    },
};

export const ClickInteraction: Story = {
    args: { node: loopNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await userEvent.click(await canvas.findByText("Loop"));
        expect(args.onClick).toHaveBeenCalledWith(loopNode);
    },
};
