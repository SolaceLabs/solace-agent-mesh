import { useEffect } from "react";

import type { Decorator, Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";

import { ModelDeleteDialog } from "@/lib/components/models";
import { pluginRegistry } from "@/lib/plugins";
import { PLUGIN_TYPES } from "@/lib/plugins/constants";

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
        modelId: "model-123",
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
        modelId: "model-456",
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
 * Enterprise plugin overrides the delete dialog - standard confirmation is replaced entirely
 */
const withMockDeletePlugin: Decorator = Story => {
    pluginRegistry.registerPlugin({
        type: PLUGIN_TYPES.DIALOG,
        id: "model-delete-dialog",
        label: "Enterprise Delete Dialog",
        render: (data: unknown) => {
            const { open, onOpenChange, onConfirm, modelAlias } = data as {
                open: boolean;
                onOpenChange: (open: boolean) => void;
                onConfirm: () => void;
                modelAlias: string;
            };
            if (!open) return null;
            return (
                <div role="dialog" aria-label="Enterprise Delete Dialog" className="rounded-lg border bg-(--background-w10) p-6">
                    <h2>Enterprise Delete: {modelAlias}</h2>
                    <p>This is a custom enterprise delete dialog injected via plugin.</p>
                    <button onClick={onConfirm}>Confirm Enterprise Delete</button>
                    <button onClick={() => onOpenChange(false)}>Cancel</button>
                </div>
            );
        },
    });

    useEffect(() => {
        return () => {
            // Clear the plugin from the registry
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            delete (pluginRegistry as any)._plugins["model-delete-dialog"];
        };
    }, []);

    return <Story />;
};

export const WithPluginDialog: Story = {
    name: "With Plugin Dialog (Enterprise Override)",
    decorators: [withMockDeletePlugin],
    args: {
        open: true,
        onOpenChange: () => {},
        onConfirm: async () => {},
        modelId: "model-enterprise-123",
        modelAlias: "enterprise-model",
        isLoading: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog", { name: "Enterprise Delete Dialog" });
        const content = within(dialog);

        expect(content.getByText(/Enterprise Delete: enterprise-model/)).toBeInTheDocument();
        expect(content.getByText(/custom enterprise delete dialog/)).toBeInTheDocument();
        expect(content.getByRole("button", { name: "Confirm Enterprise Delete" })).toBeInTheDocument();
        expect(content.getByRole("button", { name: "Cancel" })).toBeInTheDocument();

        // Standard dialog content should NOT be present
        expect(screen.queryByText("Delete Model")).not.toBeInTheDocument();
        expect(screen.queryByText(/Type.*DELETE.*to confirm/)).not.toBeInTheDocument();
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
        modelId: "general-model-id",
        modelAlias: "general",
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const content = within(dialog);

        expect(content.getByText("Unable to Delete")).toBeInTheDocument();
        expect(content.getByText(/cannot be deleted/)).toBeInTheDocument();
        expect(content.getByRole("button", { name: "Close" })).toBeInTheDocument();

        expect(content.queryByRole("textbox")).not.toBeInTheDocument();
        expect(content.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    },
};
