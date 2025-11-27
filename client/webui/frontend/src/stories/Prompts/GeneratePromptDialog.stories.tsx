import { GeneratePromptDialog } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { within, screen, expect } from "storybook/test";

const meta = {
    title: "Pages/Prompts/GeneratePromptDialog",
    component: GeneratePromptDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The dialog for generating a prompt",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof GeneratePromptDialog>;

export default meta;
type Story = StoryObj<typeof GeneratePromptDialog>;

export const Default: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Generation will be cancelled"),
        onGenerate: () => alert("Prompt will be generated"),
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const dialogContent = within(dialog);

        const button = await dialogContent.findByTestId("generatePromptButton");
        expect(button).toBeInTheDocument();
    },
};

export const NoInputValidationError: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Generation will be cancelled"),
        onGenerate: () => alert("Prompt will be generated"),
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        const dialogContent = within(dialog);

        const importButton = await dialogContent.findByTestId("generatePromptButton");
        expect(importButton).toBeInTheDocument();
        importButton.click();
    },
};
