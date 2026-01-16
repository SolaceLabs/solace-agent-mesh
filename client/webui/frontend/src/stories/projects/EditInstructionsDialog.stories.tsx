import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";
import { EditInstructionsDialog } from "@/lib";
import { populatedProject, emptyProject } from "../data/projects";

const meta = {
    title: "Pages/Projects/EditInstructionsDialog",
    component: EditInstructionsDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for editing project instructions. Validates character limit at 4000 characters.",
            },
        },
    },
} satisfies Meta<typeof EditInstructionsDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default state with existing instructions
 */
export const Default: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Will close the dialog."),
        onSave: async () => {},
        project: populatedProject,
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeEnabled();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeEnabled();
    },
};

/**
 * Empty state - no existing instructions
 */
export const Empty: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Will close the dialog."),
        onSave: async () => {},
        project: emptyProject,
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const textarea = await dialogContent.findByPlaceholderText("Add instructions for this project...");
        expect(textarea).toHaveValue("");
    },
};

/**
 * Character limit error - 4001 characters
 */
export const InstructionCharacterLimitError: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Will close the dialog."),
        onSave: async () => {},
        project: emptyProject,
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const textarea = await dialogContent.findByPlaceholderText("Add instructions for this project...");

        const atLimitText = "a".repeat(4000);
        await userEvent.click(textarea);
        await userEvent.paste(atLimitText);
        expect(await dialogContent.findByText("4000 / 4000")).toBeInTheDocument();

        await userEvent.type(textarea, "b");
        expect(await dialogContent.findByText("Instructions must be less than 4000 characters")).toBeInTheDocument();

        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeDisabled();
    },
};
