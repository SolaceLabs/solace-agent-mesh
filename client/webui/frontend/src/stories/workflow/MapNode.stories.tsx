import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import MapNode from "@/lib/components/workflowVisualization/nodes/MapNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow/WorkflowVisualization/MapNode",
    component: MapNode,
    parameters: { layout: "centered" },
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

const mapNode: LayoutNode = {
    id: "process_items",
    type: "map",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "Process Items", items: "{{workflow.input.order_items}}" },
};

const childAgent: LayoutNode = {
    id: "item_processor",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "ItemProcessor" },
};

const mapNodeWithChildren: LayoutNode = {
    ...mapNode,
    width: 328,
    height: 148,
    children: [childAgent],
};

export const CollapsedLeaf: Story = {
    args: { node: mapNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
    },
};

export const CollapsedWithChildAvailable: Story = {
    args: {
        node: { ...mapNode, isCollapsed: true, data: { ...mapNode.data, childNodeId: "item_processor" } },
        onExpand: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const expandBtn = await canvas.findByRole("button", { name: /expand/i });
        await userEvent.click(expandBtn);
        expect(args.onExpand).toHaveBeenCalledWith("process_items");
    },
};

export const ExpandedWithChildren: Story = {
    args: {
        node: mapNodeWithChildren,
        renderChildren: children => children.map(child => <div key={child.id}>{child.data.label}</div>),
        onCollapse: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
        expect(canvas.getByText("ItemProcessor")).toBeInTheDocument();
        const collapseBtn = canvas.getByRole("button", { name: /collapse/i });
        await userEvent.click(collapseBtn);
        expect(args.onCollapse).toHaveBeenCalledWith("process_items");
    },
};

export const SelectedAndHighlighted: Story = {
    args: { node: mapNode, isSelected: true, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const wrapper = (await canvas.findByText("Map")).closest("[role='button']") as HTMLElement;
        expect(wrapper).toHaveAttribute("data-selected", "true");
        expect(wrapper).toHaveAttribute("data-highlighted", "true");
    },
};

export const ClickInteraction: Story = {
    args: { node: mapNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await userEvent.click(await canvas.findByText("Map"));
        expect(args.onClick).toHaveBeenCalledWith(mapNode);
    },
};
