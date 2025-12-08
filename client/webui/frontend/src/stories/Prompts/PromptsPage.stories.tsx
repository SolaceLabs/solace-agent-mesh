import { PromptsPage } from "@/lib";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { http, HttpResponse } from "msw";
import { defaultPromptGroups, languagePromptGroup } from "./data";
import { expect, userEvent, within } from "storybook/test";

const handlers = [
    http.get("*/api/v1/prompts/groups/all", () => {
        return HttpResponse.json(defaultPromptGroups);
    }),
];

const meta = {
    title: "Pages/Prompts/PromptsPage",
    component: PromptsPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The main chat page component that displays the chat interface, side panels, and handles user interactions.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof PromptsPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const createPromptLabel = await canvas.findByText("Create New Prompt");
        expect(createPromptLabel).toBeInTheDocument();
    },
};

export const AIAssistanceDisabled: Story = {
    parameters: {
        msw: { handlers },
    },
    args: {
        configContext: {
            configFeatureEnablement: {
                promptAIAssisted: false,
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const buildWithAIButton = await canvas.findByTestId("buildWithAIButton");
        expect(buildWithAIButton).toBeDisabled();
    },
};

export const WithPromptOpen: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const prompt = await canvas.findByTestId(languagePromptGroup.id);
        prompt.click();
        const startNewChat = await canvas.findByTestId("startNewChatButton");
        expect(startNewChat).toBeInTheDocument();
    },
};

export const WithSearchTerm: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const search = await canvas.findByTestId("promptSearchInput");
        await userEvent.type(search, "language");

        const promptGroup = await canvas.findByTestId(languagePromptGroup.id);
        expect(promptGroup).toBeVisible();
    },
};

export const WithSearchTermNoResults: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const search = await canvas.findByTestId("promptSearchInput");
        await userEvent.type(search, "asdf");

        expect(canvas.findByTestId("startNewChatButton", {}, { timeout: 1000 })).rejects.toThrowError();
    },
};

export const WithTagSelected: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const tags = await canvas.findByTestId("promptTags");
        tags.click();
        const communicationFilter = await canvas.findByTestId(`category-checkbox-${languagePromptGroup.category}`);
        communicationFilter.click();
        expect(communicationFilter).toBeChecked();

        const clearFiltersButton = await canvas.findByTestId("clearFiltersButton");
        expect(clearFiltersButton).toBeVisible();

        const promptGroup = await canvas.findByTestId(languagePromptGroup.id);
        expect(promptGroup).toBeVisible();
    },
};

export const NoPrompts: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/prompts/groups/all", () => {
                    return HttpResponse.json([]);
                }),
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const buildWithAIButton = await canvas.findByTestId("Build with AI");
        expect(buildWithAIButton).toBeInTheDocument();
    },
};
