import type { Meta, StoryObj } from "@storybook/react-vite";
import { within, expect } from "storybook/test";

import { ModelSetupDialog } from "@/lib/components/models/ModelSetupDialog";

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
        expect(content.getByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
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
        expect(content.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
        expect(content.queryByRole("button", { name: /Skip for Now/i })).not.toBeInTheDocument();
    },
};
