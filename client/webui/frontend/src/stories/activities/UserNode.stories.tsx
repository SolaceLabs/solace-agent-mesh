import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";

import UserNode from "@/lib/components/activities/FlowChart/nodes/UserNode";
import type { LayoutNode } from "@/lib/components/activities/FlowChart/utils/types";

const meta = {
    title: "Activities/FlowChart/UserNode",
    component: UserNode,
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
} satisfies Meta<typeof UserNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const baseNode: LayoutNode = {
    id: "user-1",
    type: "user",
    x: 0,
    y: 0,
    width: 100,
    height: 50,
    children: [],
    data: {
        label: "User",
    },
};

export const Default: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("User")).toBeInTheDocument();
        expect(canvasElement.querySelector('[data-testid="userNode"]')).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: baseNode, isSelected: true },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("User");
        const clickable = label.closest("[role='button']") as HTMLElement;
        expect(clickable.className).toMatch(/!border-\(--accent-n2-wMain\)/);
    },
};

export const CustomLabel: Story = {
    args: { node: { ...baseNode, data: { label: "Alice" } } },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Alice")).toBeInTheDocument();
    },
};

export const InvokesOnClick: Story = {
    args: { node: baseNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("User");
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
        const label = await canvas.findByText("User");
        const clickable = label.closest("[role='button']") as HTMLElement;
        clickable.focus();
        await userEvent.keyboard("{Enter}");
        expect(args.onClick).toHaveBeenCalledTimes(1);
        await userEvent.keyboard(" ");
        expect(args.onClick).toHaveBeenCalledTimes(2);
    },
};

export const NoHandlerDoesNotThrow: Story = {
    args: { node: baseNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const label = await canvas.findByText("User");
        const clickable = label.closest("[role='button']") as HTMLElement;
        await userEvent.click(clickable);
        expect(clickable).toBeInTheDocument();
    },
};
