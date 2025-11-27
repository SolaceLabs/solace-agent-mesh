import { PromptTemplateBuilder } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { within } from "storybook/test";

const meta = {
    title: "Pages/Prompts/PromptTemplateBuilder",
    component: PromptTemplateBuilder,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The component for templating and building custom prompts",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof PromptTemplateBuilder>;

export default meta;
type Story = StoryObj<typeof PromptTemplateBuilder>;

export const Default: Story = {
    args: {},
};

export const ManualMode: Story = {
    args: { initialMode: "manual" },
};

export const ManualModeValidationErrors: Story = {
    args: { initialMode: "manual" },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const createButton = await canvas.findByTestId("createPromptButton");
        createButton.click();
    },
};
