import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import WorkflowNodeDetailPanel from "@/lib/components/workflowVisualization/WorkflowNodeDetailPanel";
import type { LayoutNode } from "@/lib/components/workflowVisualization/utils/types";
import type { AgentCardInfo } from "@/lib/types";

const meta: Meta<typeof WorkflowNodeDetailPanel> = {
    title: "Workflow/WorkflowVisualization/WorkflowNodeDetailPanel",
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

const mockValidateOrderAgent: AgentCardInfo = {
    name: "validate_order",
    displayName: "OrderValidator",
    description: "Validates order data and ensures all required fields are present",
    version: "1.0.0",
    capabilities: {},
    defaultInputModes: [],
    defaultOutputModes: [],
    protocolVersion: "1.0",
    provider: { organization: "solace", url: "" },
    url: "",
    skills: [],
};

const loopNode: LayoutNode = {
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
        delay: "5s",
    },
};

const agentNode: LayoutNode = {
    id: "validate_order",
    type: "agent",
    x: 0,
    y: 0,
    width: 280,
    height: 56,
    children: [],
    data: {
        agentName: "validate_order",
        label: "OrderValidator",
        originalConfig: {
            id: "validate_order",
            type: "agent",
            agent_name: "validate_order",
            input: {
                order_data: "{{workflow.input.order}}",
                customer_id: "{{workflow.input.customer_id}}",
            },
            input_schema_override: {
                type: "object",
                properties: {
                    order_data: { type: "object", description: "Order details to validate" },
                    customer_id: { type: "string", description: "Customer identifier" },
                },
                required: ["order_data"],
            },
            output_schema_override: {
                type: "object",
                properties: {
                    is_valid: { type: "boolean", description: "Whether order is valid" },
                    validation_errors: { type: "array", items: { type: "string" }, description: "List of validation errors" },
                },
            },
        },
    },
};

const mapNode: LayoutNode = {
    id: "process_items",
    type: "map",
    x: 0,
    y: 0,
    width: 200,
    height: 60,
    children: [],
    data: {
        label: "Process Items",
        items: "{{workflow.input.order_items}}",
    },
};

const switchNode: LayoutNode = {
    id: "check_priority",
    type: "switch",
    x: 0,
    y: 0,
    width: 200,
    height: 60,
    children: [],
    data: {
        label: "Check Priority",
        cases: [
            { condition: "{{priority}} == 'high'", node: "fast_path" },
            { condition: "{{priority}} == 'low'", node: "slow_path" },
        ],
    },
};

export const LoopNode: Story = {
    args: {
        node: loopNode,
        workflowConfig: null,
        agents: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByRole("complementary", { name: "Node details panel" })).toBeInTheDocument();
        // Panel shows node ID as title; appears multiple times in panel
        expect(canvas.getAllByText("polling_loop").length).toBeGreaterThan(0);
        expect(canvas.getByText("Max Iterations")).toBeInTheDocument();
    },
};

export const AgentNode: Story = {
    args: {
        node: agentNode,
        workflowConfig: null,
        agents: [mockValidateOrderAgent],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByRole("complementary", { name: "Node details panel" })).toBeInTheDocument();
        // Panel shows agent displayName; may appear multiple times
        expect(canvas.getAllByText("OrderValidator").length).toBeGreaterThan(0);
        expect(canvas.getByRole("tab", { name: "Input" })).toBeInTheDocument();
        expect(canvas.getByRole("tab", { name: "Output" })).toBeInTheDocument();
    },
};

export const MapNode: Story = {
    args: {
        node: mapNode,
        workflowConfig: null,
        agents: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByRole("complementary", { name: "Node details panel" })).toBeInTheDocument();
        // Panel shows node ID as title; appears multiple times in panel
        expect(canvas.getAllByText("process_items").length).toBeGreaterThan(0);
        expect(canvas.getByText("Items")).toBeInTheDocument();
    },
};

export const SwitchNode: Story = {
    args: {
        node: switchNode,
        workflowConfig: null,
        agents: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByRole("complementary", { name: "Node details panel" })).toBeInTheDocument();
        // Panel shows node ID as title; appears multiple times in panel
        expect(canvas.getAllByText("check_priority").length).toBeGreaterThan(0);
        expect(canvas.getByText("Cases")).toBeInTheDocument();
    },
};
