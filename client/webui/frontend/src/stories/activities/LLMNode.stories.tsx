import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import LLMNode from "@/lib/components/activities/FlowChart/nodes/LLMNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/LLMNode",
    component: LLMNode,
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
} satisfies Meta<typeof LLMNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseNode: LayoutNode = {
    id: "llm-1",
    type: "llm",
    x: 0,
    y: 0,
    width: 200,
    height: 50,
    children: [],
    data: {
        label: "gpt-4o",
    },
};

const findClickable = (canvas: ReturnType<typeof within>) => canvas.getByRole("button");

export const Default: Story = {
    args: {
        node: baseNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("gpt-4o")).toBeInTheDocument();
        const clickable = findClickable(canvas);
        expect(clickable).toBeInTheDocument();
        expect(clickable).toHaveAttribute("tabIndex", "0");
    },
};

export const Selected: Story = {
    args: {
        node: baseNode,
        isSelected: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("gpt-4o");
        const clickable = findClickable(canvas);
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const Processing: Story = {
    args: {
        node: { ...baseNode, data: { ...baseNode.data, status: "in-progress" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("gpt-4o");
        const clickable = findClickable(canvas);
        expect(clickable.className).toMatch(/processing-halo/);
    },
};

export const NotProcessingWhenStatusIsCompleted: Story = {
    args: {
        node: { ...baseNode, data: { ...baseNode.data, status: "completed" } },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("gpt-4o");
        const clickable = findClickable(canvas);
        expect(clickable.className).not.toMatch(/processing-halo/);
    },
};

export const TruncatesLongLabel: Story = {
    args: {
        node: {
            ...baseNode,
            data: { ...baseNode.data, label: "a-very-long-llm-model-name-that-should-truncate" },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("a-very-long-llm-model-name-that-should-truncate");
        expect(label.className).toMatch(/truncate/);
    },
};

export const InvokesOnClick: Story = {
    args: {
        node: baseNode,
        onClick: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("gpt-4o");
        const clickable = findClickable(canvas);
        await userEvent.click(clickable);
        expect(args.onClick).toHaveBeenCalledTimes(1);
        expect(args.onClick).toHaveBeenCalledWith(baseNode);
    },
};

export const InvokesOnKeyboardActivation: Story = {
    args: {
        node: baseNode,
        onClick: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("gpt-4o");
        const clickable = findClickable(canvas);
        clickable.focus();
        await userEvent.keyboard("{Enter}");
        expect(args.onClick).toHaveBeenCalledTimes(1);
        await userEvent.keyboard(" ");
        expect(args.onClick).toHaveBeenCalledTimes(2);
    },
};

export const NoOnClickHandlerDoesNotThrow: Story = {
    args: {
        node: baseNode,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("gpt-4o");
        const clickable = findClickable(canvas);
        await userEvent.click(clickable);
        expect(clickable).toBeInTheDocument();
    },
};
