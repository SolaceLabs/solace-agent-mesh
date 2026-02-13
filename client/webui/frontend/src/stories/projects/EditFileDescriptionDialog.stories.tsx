import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";
import { EditFileDescriptionDialog } from "@/lib";
import { pdfArtifact, jsonArtifact } from "../data/artifactInfo";

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
        expect(await dialogContent.findByText("api-documentation.pdf")).toBeInTheDocument();
        expect(await dialogContent.findByText("API reference documentation")).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeInTheDocument();
    },
};

/**
 * Description exceeds the max length limit — validation error shown, Save button disabled
 */
export const DescriptionOverLimit: Story = {
    args: {
        isOpen: true,
        artifact: jsonArtifact,
        onClose: () => {},
        onSave: async () => {},
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const dialogContent = within(dialog);

        const descriptionBox = await dialogContent.findByRole("textbox");
        await userEvent.click(descriptionBox);
        await userEvent.paste("a".repeat(1001));

        expect(await dialogContent.findByText(/must not exceed/i)).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeDisabled();
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

        expect(await dialogContent.findByText("package.json")).toBeInTheDocument();

        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeEnabled();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeEnabled();
    },
};
