import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";
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

const createMapNode = (): LayoutNode => ({
    id: "process_items",
    type: "map",
    x: 0,
    y: 0,
    width: 200,
    height: 60,
    children: [],
    data: {
        label: "Process Items",
        items: "{{input.items}}",
    },
});

const createSwitchNode = (): LayoutNode => ({
    id: "route_request",
    type: "switch",
    x: 0,
    y: 0,
    width: 200,
    height: 60,
    children: [],
    data: {
        label: "Route Request",
        cases: [
            { condition: "{{input.type}} == 'A'", node: "handle_a" },
            { condition: "{{input.type}} == 'B'", node: "handle_b" },
        ],
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

        // Verify description for loop nodes is rendered
        expect(screen.getByText("Repeats a node until a condition becomes false. The first iteration always runs; the condition is checked before subsequent iterations.")).toBeInTheDocument();

        // Verify delay is NOT rendered
        const delayLabel = screen.queryByText("Delay");
        expect(delayLabel).not.toBeInTheDocument();
    },
};

export const MapNode: Story = {
    args: {
        node: createMapNode(),
        workflowConfig: null,
        agents: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify node ID appears in the panel
        const processItemsElements = canvas.getAllByText("process_items");
        expect(processItemsElements.length).toBeGreaterThanOrEqual(2);

        // Verify description for map nodes is rendered
        expect(canvas.getByText("Executes a node for each item in a collection. Items are processed in parallel by default.")).toBeInTheDocument();

        // Verify items property is rendered
        expect(canvas.getByText("Items")).toBeInTheDocument();
        expect(canvas.getByText("{{input.items}}")).toBeInTheDocument();
    },
};

export const SwitchNode: Story = {
    args: {
        node: createSwitchNode(),
        workflowConfig: null,
        agents: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify node ID appears in the panel
        const routeRequestElements = canvas.getAllByText("route_request");
        expect(routeRequestElements.length).toBeGreaterThanOrEqual(2);

        // Verify description for switch nodes is rendered
        expect(canvas.getByText("Routes execution based on conditions. Cases are evaluated in order; the first match wins.")).toBeInTheDocument();

        // Verify cases are rendered
        expect(canvas.getByText("Cases")).toBeInTheDocument();
    },
};
