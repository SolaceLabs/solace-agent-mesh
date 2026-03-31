import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, waitFor, within, userEvent } from "storybook/test";
import FlowChartPanel from "@/lib/components/activities/FlowChart/FlowChartPanel";
import { visualizerSteps } from "../data/visualizerSteps";

const meta = {
    title: "Workflow/FlowChartPanel",
    component: FlowChartPanel,
    parameters: {
        layout: "fullscreen",
        chatContext: {
            agentNameDisplayNameMap: {
                OrchestratorAgent: "Orchestrator",
                ValidatorAgent: "Validator",
            },
            agentsRefetch: async () => {},
        },
        taskContext: {
            highlightedStepId: null,
            setHighlightedStepId: () => {},
        },
    },
    decorators: [
        Story => (
            <div className="h-full w-full bg-(--background-w10)">
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof FlowChartPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        processedSteps: visualizerSteps,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        // Top and bottom User nodes
        expect(await canvas.findAllByText("User")).toHaveLength(2);
        expect(canvas.getByText("Orchestrator")).toBeInTheDocument();
        expect(canvas.getByText("Validator")).toBeInTheDocument();
        // Controls bar
        expect(canvas.getByText("Detail Mode")).toBeInTheDocument();
    },
};

export const Empty: Story = {
    args: {
        processedSteps: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("No steps to display in flow chart.")).toBeInTheDocument();
    },
};

export const Collapse: Story = {
    args: {
        processedSteps: visualizerSteps,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup();

        // Start in detail mode — Validator's LLM is visible
        expect(await canvas.findAllByText("LLM")).toHaveLength(2);

        await user.click(canvas.getByRole("switch"));
        await waitFor(() => expect(canvas.getAllByText("LLM")).toHaveLength(1));
    },
};

export const AgentNodeDialog: Story = {
    args: {
        processedSteps: visualizerSteps,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup();

        // Click the Orchestrator node to open the details dialog
        const orchestratorNode = await canvas.findByText("Orchestrator");
        await user.click(orchestratorNode);

        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        expect(await within(dialog).findByRole("heading", { name: "Orchestrator" })).toBeInTheDocument();
        expect(within(dialog).getByRole("button", { name: /close/i })).toBeInTheDocument();
    },
};

export const UserNodeDialog: Story = {
    args: {
        processedSteps: visualizerSteps,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup();

        // Click the User node to open the details dialog
        const userNodes = await canvas.findAllByText("User");
        await user.click(userNodes[0]);

        let dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        expect(await within(dialog).findByText("REQUEST")).toBeInTheDocument();

        await user.click(within(dialog).getByRole("button", { name: /close/i }));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

        await user.click(userNodes[1]);
        dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        expect(await within(dialog).findByText("Final Output")).toBeInTheDocument();
    },
};
