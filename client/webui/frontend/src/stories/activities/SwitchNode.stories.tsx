import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import SwitchNode from "@/lib/components/activities/FlowChart/nodes/SwitchNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/SwitchNode",
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
    width: 280,
    height: 80,
    children: [],
    data: {
        label: "OriginalLabel",
    },
};

export const NoCases: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Switch")).toBeInTheDocument();
        expect(canvas.queryByText(/cases$/)).not.toBeInTheDocument();
    },
};

export const IgnoresDataLabel: Story = {
    args: { node: { ...baseNode, data: { ...baseNode.data, label: "ShouldNotAppear" } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Switch")).toBeInTheDocument();
        expect(canvas.queryByText("ShouldNotAppear")).not.toBeInTheDocument();
    },
};

export const WithCasesCount: Story = {
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
    },
};

export const WithCasesAndDefault: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                cases: [{ condition: "x == 1", node: "n1" }],
                defaultBranch: "n-default",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("2 cases")).toBeInTheDocument();
    },
};

export const WithSelectedBranch: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                cases: [{ condition: "x == 1", node: "branch-a" }],
                selectedBranch: "branch-a",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("branch-a")).toBeInTheDocument();
    },
};

export const WithDefaultSelectedBranch: Story = {
    args: {
        node: {
            ...baseNode,
            data: {
                ...baseNode.data,
                defaultBranch: "n-default",
                selectedBranch: "default",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("default")).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: baseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const header = await canvas.findByText("Switch");
        const clickable = header.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const InvokesOnClick: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const header = await canvas.findByText("Switch");
        const clickable = header.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(baseNode);
    },
};
