import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";

import { ModelDeleteDialog } from "@/lib/components/models";

const meta = {
    title: "Pages/Models/ModelDeleteDialog",
    component: ModelDeleteDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Confirmation dialog for deleting a model configuration. Default models (general, planning) show a read-only message. Custom models require typing DELETE to confirm.",
            },
        },
    },
} satisfies Meta<typeof ModelDeleteDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Custom model - requires typing DELETE to confirm
 */
export const Default: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        onConfirm: async () => {},
        modelAlias: "my-gpt-4",
        isLoading: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const content = within(dialog);

        expect(content.getByText("Delete Model")).toBeInTheDocument();
        expect(content.getByText(/code-based agents/)).toBeInTheDocument();
        expect(content.getByText(/DELETE/)).toBeInTheDocument();

        const deleteButton = content.getByRole("button", { name: "Delete" });
        expect(deleteButton).toBeDisabled();

        const cancelButton = content.getByRole("button", { name: "Cancel" });
        expect(cancelButton).toBeEnabled();
    },
};

/**
 * Delete button becomes enabled after typing DELETE
 */
export const ConfirmEnabled: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        onConfirm: async () => {},
        modelAlias: "my-gpt-4",
        isLoading: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const content = within(dialog);

        const input = content.getByRole("textbox");
        await userEvent.type(input, "DELETE");

        const deleteButton = content.getByRole("button", { name: "Delete" });
        expect(deleteButton).toBeEnabled();
    },
};

/**
 * Loading state - shows progress bar, buttons disabled
 */
export const Loading: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        onConfirm: async () => {},
        modelAlias: "my-gpt-4",
        isLoading: true,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const content = within(dialog);

        const deleteButton = content.getByRole("button", { name: "Delete" });
        expect(deleteButton).toBeDisabled();

        const cancelButton = content.getByRole("button", { name: "Cancel" });
        expect(cancelButton).toBeDisabled();

        const input = content.getByRole("textbox");
        expect(input).toBeDisabled();
    },
};

/**
 * Default model (general) - cannot be deleted
 */
export const DefaultModelGeneral: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        onConfirm: async () => {},
        modelAlias: "general",
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const content = within(dialog);

        expect(content.getByText("Cannot Delete Model")).toBeInTheDocument();
        expect(content.getByText(/General model cannot be deleted/)).toBeInTheDocument();
        expect(content.getByRole("button", { name: "Close" })).toBeInTheDocument();

        expect(content.queryByRole("textbox")).not.toBeInTheDocument();
        expect(content.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    },
};

/**
 * Default model (planning) - cannot be deleted
 */
export const DefaultModelPlanning: Story = {
    args: {
        open: true,
        onOpenChange: () => {},
        onConfirm: async () => {},
        modelAlias: "planning",
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const content = within(dialog);

        expect(content.getByText("Cannot Delete Model")).toBeInTheDocument();
        expect(content.getByText(/Planning model cannot be deleted/)).toBeInTheDocument();
    },
};
