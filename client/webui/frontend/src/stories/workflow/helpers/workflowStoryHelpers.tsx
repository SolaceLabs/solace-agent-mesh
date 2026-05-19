import type { Decorator } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

export const centeredWorkflowNodeDecorator: Decorator = Story => (
    <div className="flex items-center justify-center bg-(--background-w10) p-8">
        <Story />
    </div>
);

export const centeredEdgeLayerDecorator: Decorator = Story => (
    <div className="relative bg-(--background-w10) p-8" style={{ width: 400, height: 300 }}>
        <Story />
    </div>
);

export const createLayoutNode = (node: Partial<LayoutNode> & Pick<LayoutNode, "id" | "type" | "data">): LayoutNode => ({
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    ...node,
});

export const renderChildLabels = (children: LayoutNode[]) => children.map(child => <div key={child.id}>{child.data.label}</div>);

export const assertSelectedAndHighlightedByText = async (canvasElement: HTMLElement, text: string) => {
    const canvas = within(canvasElement);
    const wrapper = (await canvas.findByText(text)).closest("[role='button']") as HTMLElement;
    expect(wrapper).not.toBeNull();
};

export const assertSelectedByText = async (canvasElement: HTMLElement, text: string) => {
    const canvas = within(canvasElement);
    const wrapper = (await canvas.findByText(text)).closest("[role='button']") as HTMLElement;
    expect(wrapper).not.toBeNull();
};

export const clickNodeAndAssert = async (canvasElement: HTMLElement, label: string, onClick: unknown, expectedNode: LayoutNode) => {
    expect(onClick).toBeDefined();
    const canvas = within(canvasElement);
    await userEvent.click(await canvas.findByText(label));
    expect(onClick as (node: LayoutNode) => void).toHaveBeenCalledWith(expectedNode);
};
