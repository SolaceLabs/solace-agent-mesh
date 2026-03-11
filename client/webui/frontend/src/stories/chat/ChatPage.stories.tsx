import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { mockMessages, mockLoadingMessage } from "../mocks/data";
import { ChatPage } from "@/lib/components/pages/ChatPage";
import { expect, screen, userEvent, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { defaultPromptGroups } from "../data/prompts";
import type { MessageFE } from "@/lib/types/fe";

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

export const WithLongInput: Story = {
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
        const chatInput = await canvas.findByTestId("chat-input");

        const longContent = Array(25).fill("This is a line of text to test the input area scrolling behavior.").join("\n");

        chatInput.textContent = longContent;
        chatInput.dispatchEvent(new InputEvent("input", { bubbles: true }));

        // Verify the input has overflow-y-auto and max-h-50 working
        expect(chatInput.scrollHeight).toBeGreaterThan(chatInput.clientHeight);
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

// Mock messages for collaborative chat showing conversation between Alice (owner) and Bob (collaborator)
const collaborativeMessages: MessageFE[] = [
    // Alice's messages before sharing (indices 0, 1, 2, 3)
    {
        isUser: true,
        parts: [{ kind: "text", text: "Hi! Can you help me create a Python script to process CSV files?" }],
    },
    {
        isUser: false,
        parts: [{ kind: "text", text: "I'd be happy to help! I'll create a script that reads CSV files, processes the data, and generates reports." }],
    },
    {
        isUser: true,
        parts: [{ kind: "text", text: "Great! Can you also add error handling for missing columns?" }],
    },
    {
        isUser: false,
        parts: [
            { kind: "text", text: "I've created a Python script with comprehensive error handling for missing columns." },
            {
                kind: "artifact",
                status: "completed",
                name: "csv_processor.py",
                description: "Python script for CSV processing",
                file: {
                    name: "csv_processor.py",
                    mime_type: "text/x-python",
                    size: 2400,
                    last_modified: new Date().toISOString(),
                },
            },
        ],
    },
    // Share notification will appear here at index 3
    // Bob's messages after being added (indices 4, 5, 6, 7, 8, 9)
    {
        isUser: true,
        parts: [{ kind: "text", text: "Thanks for adding me! Does this handle different CSV delimiters like semicolons?" }],
    },
    {
        isUser: false,
        parts: [{ kind: "text", text: "Yes! The script uses Python's csv.Sniffer to automatically detect delimiters including semicolons, tabs, and pipes." }],
    },
    {
        isUser: true,
        parts: [{ kind: "text", text: "That's a good point! We often get files with different formats from various sources." }],
    },
    {
        isUser: false,
        parts: [{ kind: "text", text: "Exactly! The auto-detection feature will handle all those cases seamlessly." }],
    },
    {
        isUser: true,
        parts: [{ kind: "text", text: "Can we also add a summary statistics feature to the script?" }],
    },
    {
        isUser: false,
        parts: [{ kind: "text", text: "Absolutely! I'll add a summary module that calculates count, mean, median, and standard deviation for numeric columns." }],
    },
];

export const CollaborativeChat: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-collaborative-session",
            sessionName: "Python Script Development",
            messages: collaborativeMessages,
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
};
