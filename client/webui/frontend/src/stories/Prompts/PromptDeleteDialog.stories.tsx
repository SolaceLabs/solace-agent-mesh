import { PromptDeleteDialog } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";

const meta = {
    title: "Pages/Prompts/PromptDeleteDialog",
    component: PromptDeleteDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The dialog for deleting a prompt",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof PromptDeleteDialog>;

export default meta;
type Story = StoryObj<typeof PromptDeleteDialog>;

export const Default: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Deletion will be cancelled"),
        onConfirm: () => alert("Prompt will be deleted"),
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const dialogContent = within(dialog);
        const deleteButton = await dialogContent.findByTestId("dialogConfirmButton");
        expect(deleteButton).toBeInTheDocument();
    },
};
