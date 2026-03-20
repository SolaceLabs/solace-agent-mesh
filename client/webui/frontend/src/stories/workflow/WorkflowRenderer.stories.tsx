import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import WorkflowRenderer from "@/lib/components/activities/FlowChart/WorkflowRenderer";
import { visualizerSteps } from "../data/visualizerSteps";

const meta = {
    title: "Workflow/WorkflowVisualization/WorkflowRenderer",
    component: WorkflowRenderer,
    parameters: {
        layout: "fullscreen",
    },
    decorators: [
        Story => (
            <div className="h-full w-full bg-(--background-w10) p-8">
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof WorkflowRenderer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        processedSteps: visualizerSteps,
        agentNameMap: {
            OrchestratorAgent: "Orchestrator",
            ValidatorAgent: "Validator",
        },
        showDetail: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        // Two User nodes: one at the top (request) and one at the bottom (response)
        expect(await canvas.findAllByText("User")).toHaveLength(2);
        expect(canvas.getByText("Orchestrator")).toBeInTheDocument();
        expect(canvas.getByText("Validator")).toBeInTheDocument();
    },
};

export const CollapsedDetail: Story = {
    args: {
        ...Default.args,
        showDetail: false,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Orchestrator")).toBeInTheDocument();
        expect(canvas.getByText("Validator")).toBeInTheDocument();
        expect(canvas.getAllByText("LLM")).toHaveLength(1);
    },
};

export const Empty: Story = {
    args: {
        processedSteps: [],
        agentNameMap: {},
        showDetail: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        // Should render without errors - no nodes expected
        expect(canvas.queryByText("Orchestrator")).not.toBeInTheDocument();
    },
};
