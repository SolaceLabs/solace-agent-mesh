import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";
import { AddProjectFilesDialog } from "@/lib";
import { createMockFile, createMockFileList } from "../utils/mockFileHelpers";

const meta = {
    title: "Pages/Projects/AddProjectFilesDialog",
    component: AddProjectFilesDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for adding files to a project. Allows users to add descriptions for each uploaded file.",
            },
        },
    },
} satisfies Meta<typeof AddProjectFilesDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default state with single file
 */
export const Default: Story = {
    args: {
        isOpen: true,
        files: createMockFileList([createMockFile("api-documentation.pdf", 524288, "application/pdf")]),
        onClose: () => alert("Will close the dialog."),
        onConfirm: () => {},
        isSubmitting: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const descriptionBox = await dialogContent.findByRole("textbox");
        await userEvent.type(descriptionBox, "API documentation for the project.");

        expect(await dialogContent.findByText("api-documentation.pdf")).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Upload 1 File(s)" })).toBeInTheDocument();
    },
};

/**
 * Multiple files selected
 */
export const MultipleFiles: Story = {
    args: {
        isOpen: true,
        files: createMockFileList([createMockFile("api-documentation.pdf", 524288, "application/pdf"), createMockFile("architecture-diagram.png", 204800, "image/png"), createMockFile("package.json", 1024, "application/json")]),
        onClose: () => alert("Will close the dialog."),
        onConfirm: () => {},
        isSubmitting: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("api-documentation.pdf")).toBeInTheDocument();
        expect(await dialogContent.findByText("architecture-diagram.png")).toBeInTheDocument();
        expect(await dialogContent.findByText("package.json")).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Upload 3 File(s)" })).toBeEnabled();
    },
};

/**
 * Loading state while uploading
 */
export const Loading: Story = {
    args: {
        isOpen: true,
        files: createMockFileList([createMockFile("api-documentation.pdf", 524288, "application/pdf")]),
        onClose: () => alert("Will close the dialog."),
        onConfirm: () => {},
        isSubmitting: true,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const descriptionBox = await dialogContent.findByRole("textbox");
        expect(descriptionBox).toBeDisabled();

        expect(await dialogContent.findByRole("button", { name: "Upload 1 File(s)" })).toBeDisabled();
        expect(await dialogContent.findByRole("button", { name: "Cancel" })).toBeDisabled();
    },
};
