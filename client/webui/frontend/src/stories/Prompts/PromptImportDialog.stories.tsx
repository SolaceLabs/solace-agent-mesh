import { PromptImportDialog } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { within, screen, expect } from "storybook/test";

const meta = {
    title: "Pages/Prompts/PromptImportDialog",
    component: PromptImportDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The dialog for importing a prompt",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof PromptImportDialog>;

export default meta;
type Story = StoryObj<typeof PromptImportDialog>;

export const Default: Story = {
    args: {
        open: true,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const dialogContent = within(dialog);

        const importButton = await dialogContent.findByTestId("dialogConfirmButton");
        expect(importButton).toBeInTheDocument();
    },
};
