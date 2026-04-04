import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";

import { ChatSidePanel } from "@/lib/components/chat/ChatSidePanel";
import { mockMessages } from "../mocks/data";
import type { MessageFE } from "@/lib/types/fe";
import {
    simpleToolCallMonitoredTasks,
    peerDelegationMonitoredTasks,
    taskFailedMonitoredTasks,
    workflowMonitoredTasks,
    inProgressMonitoredTasks,
    artifactCreationMonitoredTasks,
    parallelToolCallMonitoredTasks,
    workflowMapMonitoredTasks,
} from "../data/a2aEventSSEPayloads";

const meta = {
    title: "Activities/ActivityWorkflow",
    component: ChatSidePanel,
    parameters: {
        layout: "fullscreen",
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            isTaskMonitorConnected: true,
            isTaskMonitorConnecting: false,
            isReconnecting: false,
        },
        configContext: {
            persistenceEnabled: false,
        },
    },
    args: {
        isSidePanelCollapsed: false,
        onCollapsedToggle: () => {},
        setIsSidePanelCollapsed: () => {},
    },
    decorators: [
        Story => (
            <div style={{ height: "700px", width: "500px" }}>
                <Story />
            </div>
        ),
    ],
    tags: ["autodocs"],
} satisfies Meta<typeof ChatSidePanel>;

export default meta;
type Story = StoryObj<typeof meta>;

// --- Completed: Simple Tool Call ---
// Covers: USER_REQUEST, AGENT_LLM_CALL, AGENT_LLM_RESPONSE_TOOL_DECISION,
//         AGENT_TOOL_INVOCATION_START, AGENT_TOOL_EXECUTION_RESULT,
//         AGENT_RESPONSE_TEXT, TASK_COMPLETED

export const SimpleToolCall: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: simpleToolCallMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // FlowChartDetails renders user request and status
        await canvas.findByText("What is the weather in San Francisco?");
        await canvas.findByText("Completed");

        // Activity tab is active
        expect(canvas.getByRole("tab", { name: /Activity/i, selected: true })).toBeInTheDocument();

        // Collapse panel button is visible (panel is expanded)
        await canvas.findByTestId("collapsePanel");
    },
};

// --- Completed: Peer Delegation ---
// Covers: Sub-task nesting, AGENT_LLM_RESPONSE_TO_AGENT (child task text response),
//         peer delegation info linking parent → child task

export const PeerDelegation: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: peerDelegationMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Validate order #5678 and check inventory");
        await canvas.findByText("Completed");
    },
};

// --- Failed: Database Connection Timeout ---
// Covers: TASK_FAILED with error details

export const TaskFailed: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: taskFailedMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Connect to the production database and fetch all user records");
        await canvas.findByText("Failed");
    },
};

// --- Completed: Workflow Execution ---
// Covers: WORKFLOW_EXECUTION_START, WORKFLOW_NODE_EXECUTION_START,
//         WORKFLOW_NODE_EXECUTION_RESULT, WORKFLOW_EXECUTION_RESULT

export const WorkflowExecution: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: workflowMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Run the data processing pipeline on Q4 sales data");
        await canvas.findByText("Completed");
    },
};

// --- In Progress: Task Still Working ---
// Covers: Working state with no terminal event, status bubble message,
//         LoadingMessageRow with spinner and status text

const inProgressLoadingMessage: MessageFE = {
    isUser: false,
    parts: [{ kind: "text", text: "Analyzing sentiment data..." }],
    isStatusBubble: true,
    isComplete: false,
    taskId: "task-1",
    metadata: { sessionId: "mock-session-id", lastProcessedEventSequence: 5 },
};

export const InProgress: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            currentTaskId: "task-1",
            messages: [...mockMessages, inProgressLoadingMessage],
            isResponding: true,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: inProgressMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // FlowChartDetails renders user request
        await canvas.findByText("Analyze the customer feedback data and generate a sentiment report");

        // Status should show the loading text from the status bubble message
        // (FlowChartDetails finds isStatusBubble message and passes text to LoadingMessageRow)
        await canvas.findByText("Analyzing sentiment data...");

        // Should NOT show terminal status badges
        expect(canvas.queryByText("Completed")).not.toBeInTheDocument();
        expect(canvas.queryByText("Failed")).not.toBeInTheDocument();
    },
};

// --- Completed: Artifact Creation ---
// Covers: AGENT_ARTIFACT_NOTIFICATION via artifact_saved signal

export const ArtifactCreation: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: artifactCreationMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Generate a sales report PDF for Q4");
        await canvas.findByText("Completed");
    },
};

// --- Completed: Parallel Tool Calls ---
// Covers: AGENT_LLM_RESPONSE_TOOL_DECISION (isParallel), multiple tool invocations/results,
//         AGENT_LLM_RESPONSE_TO_AGENT (text response after tool results),
//         follow-up AGENT_LLM_CALL after tool execution

export const ParallelToolCalls: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: parallelToolCallMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Get the weather in New York and London simultaneously");
        await canvas.findByText("Completed");
    },
};

// --- Completed: Workflow with Map Progress and Agent Request ---
// Covers: WORKFLOW_MAP_PROGRESS, WORKFLOW_AGENT_REQUEST (structured invocation)

export const WorkflowMapProgress: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: "task-1",
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: workflowMapMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        await canvas.findByText("Process all customer files through the review pipeline");
        await canvas.findByText("Completed");
    },
};

// --- Empty State: No Task Selected ---

export const NoTaskSelected: Story = {
    parameters: {
        chatContext: {
            sessionId: "mock-session-id",
            messages: mockMessages,
            isResponding: false,
            isCancelling: false,
            selectedAgentName: "OrchestratorAgent",
            activeSidePanelTab: "activity",
            isSidePanelCollapsed: false,
            taskIdInSidePanel: null,
            artifacts: [],
            artifactsLoading: false,
        },
        taskContext: {
            monitoredTasks: {},
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Should show the empty state message
        await canvas.findByText("No task selected to display");
    },
};
