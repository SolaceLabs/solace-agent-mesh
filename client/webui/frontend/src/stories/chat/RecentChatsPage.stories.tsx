import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { RecentChatsPage } from "@/lib/components/pages/RecentChatsPage";
import { sessions } from "../data/sessions";

const paginatedResponse = {
    data: sessions,
    meta: { pagination: { pageNumber: 1, count: sessions.length, pageSize: 20, nextPage: null, totalPages: 1 } },
};

const emptyPaginatedResponse = {
    data: [],
    meta: { pagination: { pageNumber: 1, count: 0, pageSize: 20, nextPage: null, totalPages: 0 } },
};

const handlers = [http.get("*/api/v1/sessions", () => HttpResponse.json(paginatedResponse)), http.get("*/api/v1/config/features", () => HttpResponse.json({}))];

const emptyHandlers = [http.get("*/api/v1/sessions", () => HttpResponse.json(emptyPaginatedResponse)), http.get("*/api/v1/config/features", () => HttpResponse.json({}))];

const meta = {
    title: "Pages/RecentChats/RecentChatsPage",
    component: RecentChatsPage,
    parameters: {
        layout: "fullscreen",
        msw: { handlers },
        configContext: {
            configFeatureEnablement: { newNavigation: true },
            persistenceEnabled: true,
        },
        chatContext: { sessionId: "session-1" },
    },
} satisfies Meta<typeof RecentChatsPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithSessions: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Recent Chats");
        await canvas.findByText("Session 1");
        await canvas.findByText("Session 2");
        await canvas.findByText("Session 3");
        await canvas.findByText("New Chat", { selector: "button" });
    },
};

export const Empty: Story = {
    parameters: {
        msw: { handlers: emptyHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Recent Chats");
        await canvas.findByText("No chat sessions available");
    },
};

export const WithActiveSession: Story = {
    parameters: {
        chatContext: { sessionId: "session-2" },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        const session2 = await canvas.findByText("Session 2");
        const card = session2.closest("[class*='bg-']");
        expect(card).toBeTruthy();
    },
};
