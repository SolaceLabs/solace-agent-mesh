import { PromptTemplateBuilder } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { http, HttpResponse } from "msw";

const handlers = [
    http.get("*/api/v1/prompts/chat/init", () => {
        return HttpResponse.json({
            message: "Hi! I'll help you create an effective prompt template. What kind of task or interaction would you like this prompt to handle?",
        });
    }),
    http.post("*/api/v1/prompts/chat", () => {
        return HttpResponse.json({
            message: "I understand you want to create a prompt template. Let me help you with that.",
            template_updates: {},
            ready_to_save: false,
        });
    }),
];

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
        msw: { handlers },
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
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const editManually = await canvas.findByTestId("editManuallyButton");
        expect(editManually).toBeVisible();
    },
};

export const AIAssistedModeValidationErrors: Story = {
    args: {},
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const editManually = await canvas.findByTestId("editManuallyButton");
        expect(editManually).toBeVisible();

        const createButton = await canvas.findByTestId("createPromptButton");
        createButton.click();
    },
};

export const ManualMode: Story = {
    args: { initialMode: "manual" },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const buildWithAI = await canvas.findByTestId("buildWithAIButton");
        expect(buildWithAI).toBeVisible();
    },
};

export const ManualModeValidationErrors: Story = {
    args: { initialMode: "manual" },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const buildWithAI = await canvas.findByTestId("buildWithAIButton");
        expect(buildWithAI).toBeVisible();

        const createButton = await canvas.findByTestId("createPromptButton");
        createButton.click();
    },
};
