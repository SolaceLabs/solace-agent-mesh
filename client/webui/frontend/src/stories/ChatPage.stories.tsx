import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { mockMessages, mockLoadingMessage } from "./mocks/data";
import { ChatPage } from "@/lib/components/pages/ChatPage";
import { screen, within } from "storybook/test";

const meta = {
    title: "Pages/ChatPage",
    component: ChatPage,
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
} satisfies Meta<typeof ChatPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            userInput: "",
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

        await canvas.findByTestId("Expand Panel");
        await canvas.findByTestId("Send message");
    },
};

export const WithLoadingMessage: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: [...mockMessages, mockLoadingMessage],
            userInput: "",
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

        await canvas.findByTestId("Expand Panel");
        await canvas.findByTestId("View Agent Workflow");
        await canvas.findByTestId("Cancel");
    },
};

export const WithSidePanelOpen: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            userInput: "",
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
        const openRightSidePanel = await canvas.findByTestId("Expand Panel");
        openRightSidePanel.click();

        await canvas.findByTestId("Collapse Panel");
        await canvas.findByText("No files available");
    },
};

export const NewSessionDialog: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            userInput: "",
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
        const openLeftSidePanel = await canvas.findByTestId("Show Sessions Panel");
        openLeftSidePanel.click();

        await canvas.findByTestId("Collapse Sessions Panel");

        // Open chat session dialog
        const startNewChatSessionButton = await canvas.findByTestId("Start New Chat Session");
        startNewChatSessionButton.click();

        // Verify dialog
        await screen.findByRole("dialog");
        await screen.findByRole("button", { name: "Start New Chat" });
    },
};
