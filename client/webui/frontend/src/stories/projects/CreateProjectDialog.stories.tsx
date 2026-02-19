import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";
import { CreateProjectDialog } from "@/lib";

const meta = {
    title: "Pages/Projects/CreateProjectDialog",
    component: CreateProjectDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for creating a new project. Asks for project name (required) and description (optional; max 1000 characters).",
            },
        },
    },
} satisfies Meta<typeof CreateProjectDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default state with empty form
 */
export const Default: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Project creation will cancel. Dialog will close."),
        onSubmit: async () => {},
        isSubmitting: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByRole("button", { name: "Create Project" })).toBeInTheDocument();
    },
};

/**
 * Empty state - shows validation error when submitting without name
 */
export const Empty: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Project creation will cancel. Dialog will close."),
        onSubmit: async () => {},
        isSubmitting: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);
        const submitButton = await dialogContent.findByRole("button", { name: "Create Project" });

        await userEvent.click(submitButton);
        expect(await dialogContent.findByText("Project name is required")).toBeInTheDocument();
    },
};

/**
 * Description character limit error - 1001 characters
 */
export const DescriptionCharacterLimitError: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Project creation will cancel. Dialog will close."),
        onSubmit: async () => {},
        isSubmitting: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const descriptionInput = await dialogContent.findByLabelText("Description");
        const atLimitText = "a".repeat(1000);

        await userEvent.click(descriptionInput);
        await userEvent.paste(atLimitText);
        expect(await dialogContent.findByText("1000 / 1000")).toBeInTheDocument();

        await userEvent.type(descriptionInput, "b");
        expect(await dialogContent.findByText("Description must be less than 1000 characters")).toBeInTheDocument();

        expect(await dialogContent.findByRole("button", { name: "Create Project" })).toBeDisabled();
    },
};

/**
 * Submitting state - buttons disabled while creating
 */
export const Submitting: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Bad. cannot close the dialog while submitting."),
        onSubmit: async () => {},
        isSubmitting: true,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const submitButton = await dialogContent.findByRole("button", { name: "Create Project" });
        const cancelButton = await dialogContent.findByRole("button", { name: "Cancel" });

        expect(submitButton).toBeDisabled();
        expect(cancelButton).toBeDisabled();
    },
};
