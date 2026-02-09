import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { mockMessages, mockLoadingMessage } from "../mocks/data";
import { ChatPage } from "@/lib/components/pages/ChatPage";
import { expect, screen, userEvent, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { defaultPromptGroups } from "../data/prompts";

const handlers = [
    http.get("*/api/v1/prompts/groups/all", () => {
        return HttpResponse.json(defaultPromptGroups);
    }),
];

const meta = {
    title: "Pages/Chat/ChatPage",
    component: ChatPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The main chat page component that displays the chat interface, side panels, and handles user interactions.",
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
} satisfies Meta<typeof ChatPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            activeSidePanelTab: "files",
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByTestId("expandPanel");
        await canvas.findByTestId("sendMessage");
    },
};

export const WithLoadingMessage: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            currentTaskId: "mock-task-id",
            messages: [...mockMessages, mockLoadingMessage],
            isResponding: true,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            activeSidePanelTab: "files",
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByTestId("expandPanel");
        await canvas.findByTestId("viewActivity");
        await canvas.findByTestId("cancel");
    },
};

export const WithSidePanelOpen: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            isSidePanelTransitioning: false,
            activeSidePanelTab: "files",
            artifacts: [],
            artifactsLoading: false,
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Open side panel to trigger resize of panel
        const openRightSidePanel = await canvas.findByTestId("expandPanel");
        openRightSidePanel.click();

        await canvas.findByTestId("collapsePanel");
        await canvas.findByText("No files available");
    },
};

export const NewSessionDialog: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            isSidePanelTransitioning: false,
            activeSidePanelTab: "files",
            artifacts: [],
            artifactsLoading: false,
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Open side panel to trigger resize of panel
        const openLeftSidePanel = await canvas.findByTestId("showSessionsPanel");
        openLeftSidePanel.click();

        await canvas.findByTestId("hideChatSessions");

        // Open chat session dialog
        const startNewChatSessionButton = await canvas.findByTestId("startNewChat");
        startNewChatSessionButton.click();

        // Verify dialog
        await screen.findByRole("dialog");
        await screen.findByRole("button", { name: "Start New Chat" });
    },
};

export const WithPromptDialogOpen: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            isSidePanelTransitioning: false,
            activeSidePanelTab: "files",
            artifacts: [],
            artifactsLoading: false,
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const chatInput = await canvas.findByTestId("chat-input");
        await userEvent.type(chatInput, "/");
        const promptCommand = await canvas.findByTestId("promptCommand");
        expect(promptCommand).toBeVisible();
    },
};

export const AgentDropdownFiltersWorkflows: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            activeSidePanelTab: "files",
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify that OrchestratorAgent text is visible (selected)
        await canvas.findByText("OrchestratorAgent");

        // Verify that MockWorkflow is NOT visible anywhere on the page
        // This confirms workflows are filtered out from the agent dropdown
        const mockWorkflowElements = canvasElement.innerHTML.includes("MockWorkflow");
        expect(mockWorkflowElements).toBe(false);
    },
};
