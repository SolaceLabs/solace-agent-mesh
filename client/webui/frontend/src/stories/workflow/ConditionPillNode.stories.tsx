import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import ConditionPillNode from "@/lib/components/workflowVisualization/nodes/ConditionPillNode";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";
import { assertSelectedByText, centeredWorkflowNodeDecorator, clickNodeAndAssert, createLayoutNode } from "./helpers/workflowStoryHelpers";

const meta = {
    title: "Workflow/WorkflowVisualization/ConditionPillNode",
    component: ConditionPillNode,
    parameters: { layout: "centered" },
    decorators: [centeredWorkflowNodeDecorator],
} satisfies Meta<typeof ConditionPillNode>;

export default meta;
type Story = StoryObj<typeof meta>;

const conditionNode: LayoutNode = createLayoutNode({
    id: "condition_1",
    type: "condition",
    width: 200,
    height: 28,
    data: {
        label: "{{priority}} == 'high'",
        caseNumber: 1,
        isDefaultCase: false,
    },
});

const defaultConditionNode: LayoutNode = createLayoutNode({
    id: "condition_default",
    type: "condition",
    width: 120,
    height: 28,
    data: { label: "Default", isDefaultCase: true },
});

export const Default: Story = {
    args: { node: conditionNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("1")).toBeInTheDocument();
        expect(canvas.getByText(/priority/)).toBeInTheDocument();
    },
};

export const DefaultCase: Story = {
    args: { node: defaultConditionNode },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Default")).toBeInTheDocument();
    },
};

export const Selected: Story = {
    args: { node: conditionNode, isSelected: true },
    play: async ({ canvasElement }) => {
        await assertSelectedByText(canvasElement, "1");
    },
};

export const ClickInteraction: Story = {
    args: { node: conditionNode, onClick: fn() },
    play: async ({ canvasElement, args }) => {
        await clickNodeAndAssert(canvasElement, "1", args.onClick, conditionNode);
    },
};

export const HighlightsReferencedNodesOnHover: Story = {
    args: {
        node: {
            ...conditionNode,
            data: {
                label: "{{validate_order.output.ok}} == true",
                caseNumber: 1,
                isDefaultCase: false,
            },
        },
        knownNodeIds: new Set(["validate_order", "other_node"]),
        onHighlightNodes: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const pill = (await canvas.findByText("1")).closest("[role='button']") as HTMLElement;
        await userEvent.hover(pill);
        expect(args.onHighlightNodes).toHaveBeenCalledWith(["validate_order"]);
        await userEvent.unhover(pill);
        expect(args.onHighlightNodes).toHaveBeenLastCalledWith([]);
    },
};

export const HoverWithoutKnownReferences: Story = {
    args: {
        node: {
            ...conditionNode,
            data: { label: "static condition", caseNumber: 2, isDefaultCase: false },
        },
        knownNodeIds: new Set(["validate_order"]),
        onHighlightNodes: fn(),
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        const pill = (await canvas.findByText("2")).closest("[role='button']") as HTMLElement;
        await userEvent.hover(pill);
        expect(args.onHighlightNodes).not.toHaveBeenCalled();
    },
};
