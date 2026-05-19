import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import AgentNode from "@/lib/components/workflowVisualization/nodes/AgentNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "WorkflowVisualization/AgentNode",
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

const baseNode: LayoutNode = {
    id: "agent-1",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: {
        label: "MyAgent",
        agentName: "MyAgent",
    },
};

export const Default: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyAgent")).toBeInTheDocument();
        expect(canvas.getByText("Agent")).toBeInTheDocument();
    },
};

export const FallsBackToLabelWhenNoAgentName: Story = {
    args: {
        node: { ...baseNode, data: { label: "FallbackLabel" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("FallbackLabel")).toBeInTheDocument();
    },
};

export const TruncatesLongName: Story = {
    args: {
        node: {
            ...baseNode,
            data: { ...baseNode.data, agentName: "an-extremely-long-agent-name-that-should-be-truncated" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const name = await canvas.findByText("an-extremely-long-agent-name-that-should-be-truncated");
        expect(name.className).toMatch(/truncate/);
    },
};

export const Selected: Story = {
    args: { node: baseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyAgent");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const Highlighted: Story = {
    args: { node: baseNode, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyAgent");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/ring-2/);
        expect(clickable.className).toMatch(/ring-\(--warning-wMain\)/);
    },
};

export const InvokesOnClick: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyAgent");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(baseNode);
    },
};

export const InvokesOnKeyboardActivation: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("MyAgent");
        const clickable = label.closest("[role='button']") as HTMLElement;
        clickable.focus();
        await userEvent.keyboard("{Enter}");
        expect(args.onClick).toHaveBeenCalledTimes(1);
        await userEvent.keyboard(" ");
        expect(args.onClick).toHaveBeenCalledTimes(2);
    },
};
