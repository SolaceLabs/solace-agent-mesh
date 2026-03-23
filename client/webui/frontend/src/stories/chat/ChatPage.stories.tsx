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

const mockResearchProgressMessage = {
    isUser: false,
    isComplete: false,
    taskId: "mock-research-task-id",
    parts: [
        {
            kind: "data",
            data: {
                type: "deep_research_progress",
                phase: "searching",
                status_text: "Searching for relevant sources...",
                progress_percentage: 40,
                current_iteration: 2,
                total_iterations: 5,
                sources_found: 8,
                current_query: "latest advances in large language models 2024",
                fetching_urls: [
                    { url: "https://arxiv.org/abs/2401.00001", title: "Advances in LLMs", favicon: "" },
                    { url: "https://openai.com/research", title: "OpenAI Research Blog", favicon: "" },
                ],
                elapsed_seconds: 45,
                max_runtime_seconds: 300,
                query_history: [
                    {
                        query: "large language model benchmarks 2024",
                        timestamp: "2024-01-01T00:00:00Z",
                        urls: [{ url: "https://arxiv.org/abs/2401.00001", title: "LLM Benchmarks Survey", favicon: "" }],
                    },
                ],
            },
        },
    ],
    metadata: { sessionId: "mock-session-id", lastProcessedEventSequence: 10 },
};

export const WithResearchInProgress: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            currentTaskId: "mock-research-task-id",
            messages: [...mockMessages, mockResearchProgressMessage],
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
        await canvas.findByText(/Searching for relevant sources/i);
    },
};

export const WithResearchComplete: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: [
                ...mockMessages,
                {
                    ...mockResearchProgressMessage,
                    isComplete: true,
                    parts: [
                        {
                            kind: "data",
                            data: {
                                ...mockResearchProgressMessage.parts[0].data,
                                phase: "writing",
                                status_text: "Research complete",
                                progress_percentage: 100,
                                current_iteration: 5,
                                sources_found: 2,
                            },
                        },
                        {
                            kind: "text",
                            text: "Based on my research, here is a summary of the latest advances in large language models...",
                        },
                    ],
                },
            ],
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            isSidePanelCollapsed: true,
            activeSidePanelTab: "files",
            ragData: [
                {
                    taskId: "mock-research-task-id",
                    searchType: "deep_research",
                    query: "latest advances in large language models 2024",
                    timestamp: "2024-01-01T00:00:00Z",
                    sources: [
                        {
                            citationId: "1",
                            title: "Advances in LLMs",
                            url: "https://arxiv.org/abs/2401.00001",
                            contentPreview: "[Full Content Fetched] LLM research...",
                            metadata: { fetched: true, favicon: "" },
                        },
                        {
                            citationId: "2",
                            title: "OpenAI Research Blog",
                            url: "https://openai.com/research",
                            contentPreview: "[Full Content Fetched] OpenAI research...",
                            metadata: { fetched: true, favicon: "" },
                        },
                    ],
                },
            ],
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("Research complete");
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
