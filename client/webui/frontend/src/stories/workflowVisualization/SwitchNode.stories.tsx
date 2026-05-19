import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import SwitchNode from "@/lib/components/workflowVisualization/nodes/SwitchNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "WorkflowVisualization/SwitchNode",
    component: SwitchNode,
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
} satisfies Meta<typeof SwitchNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseNode: LayoutNode = {
    id: "switch-1",
    type: "switch",
    x: 0,
    y: 0,
    width: 320,
    height: 120,
    children: [],
    data: {
        label: "Switch",
    },
};

export const NoCases: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Switch")).toBeInTheDocument();
        expect(canvas.getByText("0 cases")).toBeInTheDocument();
    },
};

export const WithCases: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                cases: [
                    { condition: "x == 1", node: "n1" },
                    { condition: "x == 2", node: "n2" },
                ],
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("2 cases")).toBeInTheDocument();
        expect(canvas.getByText("x == 1")).toBeInTheDocument();
        expect(canvas.getByText("x == 2")).toBeInTheDocument();
    },
};

export const WithCasesAndDefault: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                cases: [{ condition: "x == 1", node: "n1" }],
                defaultCase: "n-default",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("2 cases")).toBeInTheDocument();
        expect(canvas.getByText("default")).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: baseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("Switch");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const Highlighted: Story = {
    args: { node: baseNode, isHighlighted: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("Switch");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/ring-2/);
    },
};

export const InvokesOnClick: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("Switch");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(baseNode);
    },
};
