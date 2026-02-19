import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { WorkflowDetailPanel } from "@/lib/components/workflows/WorkflowDetailPanel";
import { completeOrderWorkflow, completeOrderWorkflowConfig } from "../data/workflows";

const meta = {
    title: "Workflow/WorkflowDetailPanel",
    component: WorkflowDetailPanel,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Side panel component for displaying detailed workflow information including description, version, and node count.",
            },
        },
    },
    decorators: [
        Story => (
            <div style={{ height: "100vh", width: "400px", marginLeft: "auto" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof WorkflowDetailPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        workflow: completeOrderWorkflow,
        config: completeOrderWorkflowConfig,
        onClose: () => alert("Close clicked"),
        showOpenButton: false, // Hide Open Workflow button in Storybook to prevent navigation
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify panel renders with workflow data
        expect(await canvas.findByRole("complementary", { name: "Workflow details panel" })).toBeInTheDocument();
        expect(await canvas.findByText("Complete Order Workflow")).toBeInTheDocument();
        expect(await canvas.findByText("Workflow Details")).toBeInTheDocument();
        expect(await canvas.findByText("Version")).toBeInTheDocument();
        expect(await canvas.findByText("Nodes")).toBeInTheDocument();
        expect(await canvas.findByRole("tab", { name: "Input" })).toBeInTheDocument();
        expect(await canvas.findByRole("tab", { name: "Output" })).toBeInTheDocument();
    },
};

export const Output: Story = {
    args: {
        workflow: completeOrderWorkflow,
        config: completeOrderWorkflowConfig,
        onClose: () => alert("Close clicked"),
        showOpenButton: false, // Hide Open Workflow button in Storybook to prevent navigation
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify panel renders with workflow data
        expect(await canvas.findByRole("complementary", { name: "Workflow details panel" })).toBeInTheDocument();
        expect(await canvas.findByText("Complete Order Workflow")).toBeInTheDocument();

        (await canvas.findByRole("tab", { name: "Output" })).click();
        expect(await canvas.findByText("Output Mapping")).toBeInTheDocument();
    },
};
