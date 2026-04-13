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
    parallelPeerMonitoredTasks,
    mixedParallelMonitoredTasks,
    workflowMapMonitoredTasks,
} from "../data/a2aEventSSEPayloads";

// Helper to find the closest common ancestor of two elements within a boundary
const findCommonAncestor = (a: Element, b: Element, boundary: Element): Element | null => {
    let current: Element | null = a;
    while (current && current !== boundary) {
        if (current.contains(b)) return current;
        current = current.parentElement;
    }
    return null;
};

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

        // FlowChartDetails: request text and completed status
        expect(await canvas.findByText("What is the weather in San Francisco?")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Activity tab is selected, panel is expanded
        expect(canvas.getByRole("tab", { name: /Activity/i, selected: true })).toBeInTheDocument();
        expect(await canvas.findByTestId("collapsePanel")).toBeInTheDocument();
    },
};

// --- Completed: Peer Delegation ---
// Covers: Sub-task nesting, AGENT_LLM_RESPONSE_TO_AGENT (child task text response),
//         peer delegation info linking parent -> child task

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

        expect(await canvas.findByText("Validate order #5678 and check inventory")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Delegated peer agent is rendered as a sub-agent node
        expect(await canvas.findByText("ValidatorAgent")).toBeInTheDocument();
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

        expect(await canvas.findByText("Connect to the production database and fetch all user records")).toBeInTheDocument();
        expect(await canvas.findByText("Failed")).toBeInTheDocument();

        // Tool was invoked before failure
        expect(await canvas.findByTestId("tool-node-query_database")).toBeInTheDocument();
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

        expect(await canvas.findByText("Run the data processing pipeline on Q4 sales data")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Workflow group node renders the workflow name
        expect(await canvas.findByText("Data Processing Pipeline")).toBeInTheDocument();
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
        expect(await canvas.findByText("Analyze the customer feedback data and generate a sentiment report")).toBeInTheDocument();

        // Status shows the loading text from the status bubble message
        expect(await canvas.findByText("Analyzing sentiment data...")).toBeInTheDocument();

        // Should NOT show terminal status badges
        expect(canvas.queryByText("Completed")).not.toBeInTheDocument();
        expect(canvas.queryByText("Failed")).not.toBeInTheDocument();

        // Tool invocation is in progress
        expect(await canvas.findByTestId("tool-node-analyze_sentiment")).toBeInTheDocument();
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

        expect(await canvas.findByText("Generate a sales report PDF for Q4")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Tool node for report generation is rendered
        expect(await canvas.findByTestId("tool-node-generate_report")).toBeInTheDocument();

        // Artifact badge shows on the tool node (artifact_saved linked to this tool)
        expect(await canvas.findByText("1 artifact")).toBeInTheDocument();
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

        expect(await canvas.findByText("Get the weather in New York and London simultaneously")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Both parallel tool nodes are rendered (same tool name, two instances)
        const toolNodes = canvasElement.querySelectorAll('[data-testid="tool-node-get_weather"]');
        expect(toolNodes.length).toBe(2);

        // Verify parallel layout: both tool nodes share a common ancestor
        // with flex-direction: row (the parallelBlock container renders children side-by-side)
        const commonAncestor = findCommonAncestor(toolNodes[0], toolNodes[1], canvasElement);
        expect(commonAncestor).not.toBeNull();
        expect(window.getComputedStyle(commonAncestor!).flexDirection).toBe("row");
    },
};

// --- Completed: Parallel Peer Delegation ---
// Covers: Multiple peer agents (ValidatorAgent + ShippingAgent) invoked in parallel,
//         each with their own sub-task, rendered side-by-side via parallelPeerGroupMap

export const ParallelPeerDelegation: Story = {
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
            monitoredTasks: parallelPeerMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        expect(await canvas.findByText("Check order #9999 validity and fetch shipping estimate")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Both parallel peer agents are rendered as sub-agent nodes
        const validatorNode = await canvas.findByText("ValidatorAgent");
        expect(validatorNode).toBeInTheDocument();
        const shippingNode = await canvas.findByText("ShippingAgent");
        expect(shippingNode).toBeInTheDocument();

        // Verify parallel layout: both agent nodes share a common ancestor with flex-direction: row
        const commonAncestor = findCommonAncestor(validatorNode, shippingNode, canvasElement);
        expect(commonAncestor).not.toBeNull();
        expect(window.getComputedStyle(commonAncestor!).flexDirection).toBe("row");
    },
};

// --- Completed: Mixed Parallel Peer Delegation ---
// Covers: Two peer agents in parallel where:
//   - AnalysisAgent makes sequential tool calls (fetch_data -> analyze_data)
//   - ReportAgent makes parallel tool calls (generate_chart + generate_summary)

export const MixedParallelPeerDelegation: Story = {
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
            monitoredTasks: mixedParallelMonitoredTasks,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        expect(await canvas.findByText("Analyze Q1 sales data and produce a report with charts")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Both parallel peer agents are rendered
        expect(await canvas.findByText("AnalysisAgent")).toBeInTheDocument();
        expect(await canvas.findByText("ReportAgent")).toBeInTheDocument();

        // AnalysisAgent's sequential tools
        const fetchDataNode = await canvas.findByTestId("tool-node-fetch_data");
        expect(fetchDataNode).toBeInTheDocument();
        const analyzeDataNode = await canvas.findByTestId("tool-node-analyze_data");
        expect(analyzeDataNode).toBeInTheDocument();

        // Sequential verification: closest common ancestor should have flex-direction: column
        const seqAncestor = findCommonAncestor(fetchDataNode, analyzeDataNode, canvasElement);
        expect(seqAncestor).not.toBeNull();
        expect(window.getComputedStyle(seqAncestor!).flexDirection).toBe("column");

        // ReportAgent's parallel tools
        const chartNode = await canvas.findByTestId("tool-node-generate_chart");
        expect(chartNode).toBeInTheDocument();
        const summaryNode = await canvas.findByTestId("tool-node-generate_summary");
        expect(summaryNode).toBeInTheDocument();

        // Parallel verification: closest common ancestor should have flex-direction: row
        const parAncestor = findCommonAncestor(chartNode, summaryNode, canvasElement);
        expect(parAncestor).not.toBeNull();
        expect(window.getComputedStyle(parAncestor!).flexDirection).toBe("row");
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

        expect(await canvas.findByText("Process all customer files through the review pipeline")).toBeInTheDocument();
        expect(await canvas.findByText("Completed")).toBeInTheDocument();

        // Workflow group node renders the workflow name
        expect(await canvas.findByText("Customer Review Pipeline")).toBeInTheDocument();
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

        expect(await canvas.findByText("No task selected to display")).toBeInTheDocument();
    },
};
