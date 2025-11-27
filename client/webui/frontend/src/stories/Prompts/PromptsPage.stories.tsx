import { PromptsPage } from "@/lib";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { http, HttpResponse } from "msw";
import { defaultPromptGroups, languagePromptGroup } from "./data";
import { userEvent, within } from "storybook/test";

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
};

export const WithPromptOpen: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const prompt = await canvas.findByTestId(languagePromptGroup.id);
        prompt.click();
    },
};

export const WithFilterSelected: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const search = await canvas.findByTestId("promptSearchInput");
        await userEvent.type(search, "language");
    },
};

export const WithFilterSelectedNoResults: Story = {
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const search = await canvas.findByTestId("promptSearchInput");
        await userEvent.type(search, "asdf");
    },
};

export const NoPrompts: Story = {};
