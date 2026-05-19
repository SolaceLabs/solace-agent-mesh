import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import LoopNode from "@/lib/components/activities/FlowChart/nodes/LoopNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/LoopNode",
    component: LoopNode,
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
} satisfies Meta<typeof LoopNode>;

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

const compactNode: LayoutNode = {
    id: "loop-1",
    type: "loop",
    x: 0,
    y: 0,
    width: 200,
    height: 50,
    children: [],
    data: {
        label: "OriginalLabel",
        maxIterations: 100,
    },
};

const expandedNode: LayoutNode = {
    id: "loop-2",
    type: "loop",
    x: 0,
    y: 0,
    width: 280,
    height: 200,
    children: [agentChild("iter-1", "IterationAgent")],
    data: {
        label: "ProcessingLoop",
        maxIterations: 5,
    },
};

export const CompactNoChildren: Story = {
    args: {
        node: compactNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(canvas.getByText("max: 100")).toBeInTheDocument();
    },
};

export const CompactIgnoresDataLabel: Story = {
    args: {
        node: { ...compactNode, data: { ...compactNode.data, label: "ShouldNotAppear" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
        expect(canvas.queryByText("ShouldNotAppear")).not.toBeInTheDocument();
    },
};

export const CompactWithCustomMaxIterations: Story = {
    args: {
        node: { ...compactNode, data: { ...compactNode.data, maxIterations: 7 } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("max: 7")).toBeInTheDocument();
    },
};

export const ExpandedWithChildren: Story = {
    args: {
        node: expandedNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("ProcessingLoop")).toBeInTheDocument();
        expect(canvas.getByText("max: 5")).toBeInTheDocument();
        expect(canvas.getByText("IterationAgent")).toBeInTheDocument();
    },
};

export const ExpandedFallsBackToDefaultLabel: Story = {
    args: {
        node: { ...expandedNode, data: { ...expandedNode.data, label: "" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loop")).toBeInTheDocument();
    },
};

export const ExpandedWithShortCondition: Story = {
    args: {
        node: { ...expandedNode, data: { ...expandedNode.data, condition: "x < 5" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("while: x < 5")).toBeInTheDocument();
    },
};

export const ExpandedWithLongConditionTruncates: Story = {
    args: {
        node: {
            ...expandedNode,
            data: {
                ...expandedNode.data,
                condition: "this_is_a_very_long_loop_condition_that_should_be_truncated",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const conditionEl = await canvas.findByText(/^while:/);
        expect(conditionEl.textContent).toMatch(/\.\.\.$/);
        expect(conditionEl.textContent?.length).toBeLessThanOrEqual("while: ".length + 30 + 3);
    },
};

export const ShowsIterationCounterWhenInProgress: Story = {
    args: {
        node: {
            ...expandedNode,
            data: { ...expandedNode.data, status: "in-progress", currentIteration: 3 },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Processing iteration 3...")).toBeInTheDocument();
    },
};

export const HidesIterationCounterWhenNotInProgress: Story = {
    args: {
        node: {
            ...expandedNode,
            data: { ...expandedNode.data, status: "completed", currentIteration: 3 },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("ProcessingLoop");
        expect(canvas.queryByText(/Processing iteration/)).not.toBeInTheDocument();
    },
};

export const HidesIterationCounterWhenIterationNotAhead: Story = {
    args: {
        node: {
            ...expandedNode,
            data: { ...expandedNode.data, status: "in-progress", currentIteration: 1 },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("ProcessingLoop");
        expect(canvas.queryByText(/Processing iteration/)).not.toBeInTheDocument();
    },
};

export const SelectedCompact: Story = {
    args: {
        node: compactNode,
        isSelected: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const loopText = await canvas.findByText("Loop");
        const clickable = loopText.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const InvokesOnClickInCompactMode: Story = {
    args: {
        node: compactNode,
        onClick: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const loopText = await canvas.findByText("Loop");
        const clickable = loopText.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(compactNode);
    },
};

export const InvokesOnClickInExpandedMode: Story = {
    args: {
        node: expandedNode,
        onClick: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const header = await canvas.findByText("ProcessingLoop");
        const clickable = header.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(expandedNode);
    },
};
