import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { WorkflowList } from "@/lib/components/workflows/WorkflowList";
import { mockWorkflows } from "../data/workflows";

const meta = {
    title: "Workflow/WorkflowList",
    component: WorkflowList,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "List component for displaying and managing workflows with search, filtering, and detail panel.",
            },
        },
    },
    decorators: [
        Story => (
            <div style={{ height: "100vh", width: "100vw" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof WorkflowList>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        workflows: mockWorkflows,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify table is visible
        expect(await canvas.findByRole("table", { name: "Workflows" })).toBeInTheDocument();

        // Verify column headers
        expect(await canvas.findByText("Name")).toBeInTheDocument();
        expect(await canvas.findByText("Version")).toBeInTheDocument();
        expect(await canvas.findByText("Status")).toBeInTheDocument();

        // Verify workflows are displayed
        expect(await canvas.findByText("Complete Order Workflow")).toBeInTheDocument();
        expect(await canvas.findByText("SimpleLoopWorkflow")).toBeInTheDocument();
    },
};

export const EmptyList: Story = {
    args: {
        workflows: [],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify onboarding view is shown when no workflows exist
        expect(await canvas.findByText("Workflows give enterprises production-ready, best-practice agent patterns that are predictable and reliable.")).toBeInTheDocument();
        expect(await canvas.findByText("Learn how to create workflows")).toBeInTheDocument();
    },
};
