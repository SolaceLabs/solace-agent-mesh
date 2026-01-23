import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";
import { DeleteProjectDialog } from "@/lib";
import { weatherProject } from "../data/projects";

const meta = {
    title: "Pages/Projects/DeleteProjectDialog",
    component: DeleteProjectDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Confirmation dialog for deleting a project. Shows the project's name in bold and warns about permanent deletion.",
            },
        },
    },
} satisfies Meta<typeof DeleteProjectDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default state - confirmation dialog with project name
 */
export const Default: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Project deletion will cancel. Dialog will close."),
        onConfirm: async () => {},
        project: weatherProject,
        isDeleting: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);
        expect(await dialogContent.findByRole("button", { name: "Delete" })).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Cancel" })).toBeInTheDocument();

        const projectName = await dialogContent.findByText(weatherProject.name);
        expect(projectName.tagName).toBe("STRONG");
        expect(projectName).toBeInTheDocument();
    },
};

/**
 * Loading state - buttons disabled while deleting
 */
export const Loading: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Project deletion will cancel. Dialog will close."),
        onConfirm: async () => {},
        project: weatherProject,
        isDeleting: true,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByRole("button", { name: "Delete" })).toBeDisabled();
        expect(await dialogContent.findByRole("button", { name: "Cancel" })).toBeDisabled();
    },
};
