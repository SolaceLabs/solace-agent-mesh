import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";
import { DeleteProjectFileDialog } from "@/lib";
import { pdfArtifact } from "../data/artifactInfo";

const meta = {
    title: "Pages/Projects/DeleteProjectFileDialog",
    component: DeleteProjectFileDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Confirmation dialog for deleting a project file.",
            },
        },
    },
} satisfies Meta<typeof DeleteProjectFileDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default state - confirmation dialog
 */
export const Default: Story = {
    args: {
        isOpen: true,
        fileToDelete: pdfArtifact,
        setFileToDelete: () => alert("File deletion cancelled."),
        handleConfirmDelete: () => alert("File will be deleted."),
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("api-documentation.pdf")).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Delete" })).toBeInTheDocument();
    },
};
