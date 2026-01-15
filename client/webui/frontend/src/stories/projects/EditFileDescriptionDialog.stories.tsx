import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";
import { EditFileDescriptionDialog } from "@/lib";
import { pdfArtifact, jsonArtifact } from "./data";

const meta = {
    title: "Pages/Projects/EditFileDescriptionDialog",
    component: EditFileDescriptionDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for editing the description of an uploaded project file.",
            },
        },
    },
} satisfies Meta<typeof EditFileDescriptionDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default state with existing description
 */
export const Default: Story = {
    args: {
        isOpen: true,
        artifact: pdfArtifact,
        onClose: () => alert("Dialog will close."),
        onSave: async () => {},
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);
        expect(await dialogContent.findByText("api-documentation.pdf")).toBeVisible();
        expect(await dialogContent.findByText("API reference documentation")).toBeVisible();
        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeVisible();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeVisible();
    },
};

/**
 * Empty state - no existing description
 */
export const Empty: Story = {
    args: {
        isOpen: true,
        artifact: jsonArtifact,
        onClose: () => alert("Dialog will close."),
        onSave: async () => {},
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("package.json")).toBeVisible();

        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeEnabled();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeEnabled();
        
    },
};
