import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import ConditionPillNode from "@/lib/components/workflowVisualization/nodes/ConditionPillNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta = {
    title: "WorkflowVisualization/ConditionPillNode",
    component: ConditionPillNode,
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
} satisfies Meta<typeof ConditionPillNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const caseNode: LayoutNode = {
    id: "pill-1",
    type: "condition",
    x: 0,
    y: 0,
    width: 120,
    height: 28,
    children: [],
    data: {
        label: "x == 1",
        conditionLabel: "x == 1",
        caseNumber: 1,
    },
};

const defaultNode: LayoutNode = {
    id: "pill-default",
    type: "condition",
    x: 0,
    y: 0,
    width: 80,
    height: 28,
    children: [],
    data: {
        label: "Default",
        isDefaultCase: true,
    },
};

export const CaseWithNumber: Story = {
    args: { node: caseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("1")).toBeInTheDocument();
        expect(canvas.getByText("x == 1")).toBeInTheDocument();
    },
};

export const DefaultCase: Story = {
    args: { node: defaultNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Default")).toBeInTheDocument();
        // No case number divider for default
        expect(canvas.queryByText("1")).not.toBeInTheDocument();
    },
};

export const FallsBackToLabel: Story = {
    args: {
        node: {
            ...caseNode,
            data: { ...caseNode.data, conditionLabel: undefined, label: "fallback" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("fallback")).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: caseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("x == 1");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const InvokesOnClick: Story = {
    args: { node: caseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("x == 1");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(caseNode);
    },
};

export const HighlightsReferencedNodesOnHover: Story = {
    args: {
        node: {
            ...caseNode,
            data: { ...caseNode.data, conditionLabel: "{{NodeA.output.value > 0}}" },
        },
        onHighlightNodes: fn(),
        knownNodeIds: new Set(["NodeA", "NodeB"]),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("{{NodeA.output.value > 0}}");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.hover(clickable);
        expect(args.onHighlightNodes).toHaveBeenCalled();
        const lastCall = (args.onHighlightNodes as ReturnType<typeof fn>).mock.calls.at(-1);
        expect(lastCall?.[0]).toContain("NodeA");
    },
};

export const ClearsHighlightOnUnhover: Story = {
    args: {
        node: {
            ...caseNode,
            data: { ...caseNode.data, conditionLabel: "{{NodeA.output.value}}" },
        },
        onHighlightNodes: fn(),
        knownNodeIds: new Set(["NodeA"]),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("{{NodeA.output.value}}");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.hover(clickable);
        await userEvent.unhover(clickable);
        const lastCall = (args.onHighlightNodes as ReturnType<typeof fn>).mock.calls.at(-1);
        expect(lastCall?.[0]).toEqual([]);
    },
};
