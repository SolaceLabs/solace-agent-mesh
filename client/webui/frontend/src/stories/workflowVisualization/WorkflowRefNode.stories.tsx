import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import WorkflowRefNode from "@/lib/components/workflowVisualization/nodes/WorkflowRefNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "WorkflowVisualization/WorkflowRefNode",
    component: WorkflowRefNode,
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
} satisfies Meta<typeof WorkflowRefNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseNode: LayoutNode = {
    id: "wfref-1",
    type: "workflow",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: {
        label: "ChildFlow",
        workflowName: "ChildFlow",
    },
};

export const Default: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ChildFlow")).toBeInTheDocument();
        expect(canvas.getByText("Workflow")).toBeInTheDocument();
    },
};

export const FallsBackToAgentName: Story = {
    args: {
        node: { ...baseNode, data: { label: "ignored", agentName: "FromAgentName" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("FromAgentName")).toBeInTheDocument();
    },
};

export const FallsBackToLabel: Story = {
    args: {
        node: { ...baseNode, data: { label: "JustLabel" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("JustLabel")).toBeInTheDocument();
    },
};

export const TruncatesLongName: Story = {
    args: {
        node: {
            ...baseNode,
            data: { ...baseNode.data, workflowName: "an-extremely-long-workflow-name-that-must-truncate" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const name = await canvas.findByText("an-extremely-long-workflow-name-that-must-truncate");
        expect(name.className).toMatch(/truncate/);
    },
};

export const Selected: Story = {
    args: { node: baseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("ChildFlow");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const Highlighted: Story = {
    args: { node: baseNode, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("ChildFlow");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/ring-2/);
    },
};

export const InvokesOnClick: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("ChildFlow");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(baseNode);
    },
};
