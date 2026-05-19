import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import AgentNode from "@/lib/components/workflowVisualization/nodes/AgentNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "Workflow/WorkflowVisualization/AgentNode",
    component: AgentNode,
    parameters: { layout: "centered" },
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

const agentNode: LayoutNode = {
    id: "validate_order",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label: "OrderValidator" },
};

export const Default: Story = {
    args: { node: agentNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("OrderValidator")).toBeInTheDocument();
        expect(canvas.getByText("Agent")).toBeInTheDocument();
    },
};

export const PrefersAgentName: Story = {
    args: {
        node: { ...agentNode, data: { label: "fallback", agentName: "PreferredName" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("PreferredName")).toBeInTheDocument();
    },
};

export const SelectedAndHighlighted: Story = {
    args: { node: agentNode, isSelected: true, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const wrapper = (await canvas.findByText("OrderValidator")).closest("[role='button']") as HTMLElement;
        expect(wrapper).toHaveAttribute("data-selected", "true");
        expect(wrapper).toHaveAttribute("data-highlighted", "true");
    },
};

export const ClickInteraction: Story = {
    args: { node: agentNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await userEvent.click(await canvas.findByText("OrderValidator"));
        expect(args.onClick).toHaveBeenCalledWith(agentNode);
    },
};
