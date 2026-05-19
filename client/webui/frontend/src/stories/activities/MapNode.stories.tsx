import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import MapNode from "@/lib/components/activities/FlowChart/nodes/MapNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/MapNode",
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

const childAgent = (id: string, label: string, iterationIndex?: number): LayoutNode => ({
    id,
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: { label, ...(iterationIndex !== undefined ? { iterationIndex } : {}) },
});

const compactNode: LayoutNode = {
    id: "map-compact",
    type: "map",
    x: 0,
    y: 0,
    width: 200,
    height: 50,
    children: [],
    data: { label: "" },
};

const expandedSingleBranch: LayoutNode = {
    id: "map-single-branch",
    type: "map",
    x: 0,
    y: 0,
    width: 320,
    height: 200,
    children: [childAgent("agent-1", "Worker", 0)],
    data: { label: "ParallelMap" },
};

const expandedTwoBranches: LayoutNode = {
    id: "map-two-branches",
    type: "map",
    x: 0,
    y: 0,
    width: 320,
    height: 200,
    children: [
        childAgent("agent-1", "BranchOne", 0),
        childAgent("agent-2", "BranchTwo", 1),
    ],
    data: { label: "ForkMap" },
};

export const CompactNoChildren: Story = {
    args: { node: compactNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
    },
};

export const CompactWithCustomLabel: Story = {
    args: { node: { ...compactNode, data: { label: "MyMap" } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("MyMap")).toBeInTheDocument();
    },
};

export const CompactSelected: Story = {
    args: { node: compactNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const mapText = await canvas.findByText("Map");
        const clickable = mapText.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const ExpandedSingleBranch: Story = {
    args: { node: expandedSingleBranch },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ParallelMap")).toBeInTheDocument();
        expect(canvas.getByText("Worker")).toBeInTheDocument();
    },
};

export const ExpandedTwoBranches: Story = {
    args: { node: expandedTwoBranches },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ForkMap")).toBeInTheDocument();
        expect(canvas.getByText("BranchOne")).toBeInTheDocument();
        expect(canvas.getByText("BranchTwo")).toBeInTheDocument();
    },
};

export const ExpandedFallsBackToDefaultLabel: Story = {
    args: { node: { ...expandedSingleBranch, data: { label: "" } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Map")).toBeInTheDocument();
    },
};

export const InvokesOnClickInCompactMode: Story = {
    args: { node: compactNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const mapText = await canvas.findByText("Map");
        const clickable = mapText.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(compactNode);
    },
};

export const InvokesOnClickInExpandedMode: Story = {
    args: { node: expandedSingleBranch, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const header = await canvas.findByText("ParallelMap");
        const clickable = header.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(expandedSingleBranch);
    },
};

export const InvokesOnChildClick: Story = {
    args: { node: expandedSingleBranch, onChildClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const childLabel = await canvas.findByText("Worker");
        await userEvent.click(childLabel);
        expect(args.onChildClick).toHaveBeenCalledTimes(1);
    },
};
