import type { Meta, StoryObj } from "@storybook/react-vite";
import { within, expect } from "storybook/test";

import { ModelSetupDialog } from "@/lib/components/models/ModelSetupDialog";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { Button } from "@/lib/components/ui";

const meta = {
    title: "Pages/Models/ModelSetupDialog",
    component: ModelSetupDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog shown on first entry when no default LLM models are configured. Displays different content for admin vs non-admin users.",
            },
        },
    },
} satisfies Meta<typeof ModelSetupDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const AdminVariant: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        hasWritePermissions: true,
    },
    play: async () => {
        const dialog = await within(document.body).findByRole("dialog");
        const content = within(dialog);

        expect(content.getByText("Set Up Your Default LLM Models")).toBeInTheDocument();
        expect(content.getByRole("button", { name: /Skip for Now/i })).toBeInTheDocument();
        expect(content.getByRole("button", { name: /Add Model/i })).toBeInTheDocument();
    },
};

export const NonAdminVariant: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        hasWritePermissions: false,
    },
    play: async () => {
        const dialog = await within(document.body).findByRole("dialog");
        const content = within(dialog);

        expect(content.getByText("No Default LLM Models Available")).toBeInTheDocument();
        expect(content.getByText(/Contact an administrator/)).toBeInTheDocument();
        expect(content.getByRole("button", { name: /Close/i })).toBeInTheDocument();

        // Admin-only buttons should NOT be present
        expect(content.queryByRole("button", { name: /Add Model/i })).not.toBeInTheDocument();
        expect(content.queryByRole("button", { name: /Skip for Now/i })).not.toBeInTheDocument();
    },
};

export const WarningBannerAdmin: StoryObj = {
    parameters: {
        layout: "fullscreen",
    },
    render: () => (
        <div style={{ padding: "1rem", width: "100vw" }}>
            <MessageBanner
                variant="warning"
                style={{ alignItems: "center" }}
                message={
                    <div className="flex w-full items-center justify-between gap-3">
                        <span>No model has been set up. Some features may not work as intended without a configured model.</span>
                        <Button variant="outline" size="sm" className="shrink-0">
                            Add Model
                        </Button>
                    </div>
                }
            />
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        expect(canvas.getByText(/No model has been set up/)).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: /Add Model/i })).toBeInTheDocument();
        expect(canvas.queryByText(/Contact your administrator/)).not.toBeInTheDocument();
    },
};

export const WarningBannerNonAdmin: StoryObj = {
    parameters: {
        layout: "fullscreen",
    },
    render: () => (
        <div style={{ padding: "1rem", width: "100vw" }}>
            <MessageBanner
                variant="warning"
                style={{ alignItems: "center" }}
                message={
                    <div className="flex w-full items-center justify-between gap-3">
                        <span>No model has been set up. Some features may not work as intended without a configured model. Contact your administrator for assistance.</span>
                    </div>
                }
            />
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        expect(canvas.getByText(/No model has been set up/)).toBeInTheDocument();
        expect(canvas.getByText(/Contact your administrator/)).toBeInTheDocument();
        expect(canvas.queryByRole("button", { name: /Add Model/i })).not.toBeInTheDocument();
    },
};
