import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen } from "storybook/test";
import WorkflowNodeDetailPanel from "@/lib/components/workflowVisualization/WorkflowNodeDetailPanel";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";

const meta: Meta<typeof WorkflowNodeDetailPanel> = {
    title: "Workflow Visualization/WorkflowNodeDetailPanel",
    component: WorkflowNodeDetailPanel,
    tags: ["autodocs"],
    decorators: [
        Story => (
            <div className="h-screen bg-white dark:bg-gray-900">
                <Story />
            </div>
        ),
    ],
};

export default meta;
type Story = StoryObj<typeof meta>;

const createLoopNode = (delay?: string): LayoutNode => ({
    id: "polling_loop",
    type: "loop",
    x: 0,
    y: 0,
    width: 200,
    height: 60,
    children: [],
    data: {
        label: "Polling Loop",
        condition: "{{check_status.output.ready}} == false",
        maxIterations: 10,
        ...(delay && { delay }),
    },
});

export const LoopNodeWithDelay: Story = {
    args: {
        node: createLoopNode("5s"),
        workflowConfig: null,
        agents: [],
    },
    play: async () => {
        // Verify delay is rendered
        expect(screen.getByText("Delay")).toBeInTheDocument();
        expect(screen.getByText("5s")).toBeInTheDocument();
    },
};

export const LoopNodeWithoutDelay: Story = {
    args: {
        node: createLoopNode(),
        workflowConfig: null,
        agents: [],
    },
    play: async () => {
        // Verify node ID appears in the Node ID section
        expect(screen.getByText("polling_loop")).toBeInTheDocument();

        // Verify type label "Loop" appears in the UI (title and Node Type section)
        const loopElements = screen.getAllByText("Loop");
        expect(loopElements.length).toBeGreaterThanOrEqual(2);

        // Verify expected properties are rendered
        expect(screen.getByText("Max Iterations")).toBeInTheDocument();
        expect(screen.getByText("10")).toBeInTheDocument();
        expect(screen.getByText("Condition")).toBeInTheDocument();

        // Verify delay is NOT rendered
        const delayLabel = screen.queryByText("Delay");
        expect(delayLabel).not.toBeInTheDocument();
    },
};
