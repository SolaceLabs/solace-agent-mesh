import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";

import { VisualizerStepCard } from "@/lib/components/activities/VisualizerStepCard";

const baseStep = {
    rawEventIds: [] as string[],
    nestingLevel: 0,
    owningTaskId: "task-1",
};

const ts = new Date().toISOString();

const meta = {
    title: "Activities/VisualizerStepCard",
    component: VisualizerStepCard,
    parameters: {
        chatContext: {
            sessionId: "test-session",
            artifacts: [],
        },
    },
    decorators: [
        Story => (
            <div className="max-w-xl p-4">
                <Story />
            </div>
        ),
    ],
    tags: ["autodocs"],
} satisfies Meta<typeof VisualizerStepCard>;

export default meta;
type Story = StoryObj<typeof meta>;

// --- Basic step types ---

export const UserRequest: Story = {
    args: {
        step: {
            id: "s-1",
            type: "USER_REQUEST",
            timestamp: ts,
            title: "User Request",
            data: { text: "Generate a report summarizing Q4 sales data across all regions." },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("User Request")).toBeInTheDocument();
        expect(canvas.getByText(/Q4 sales data/)).toBeInTheDocument();
    },
};

export const AgentResponseText: Story = {
    args: {
        step: {
            id: "s-2",
            type: "AGENT_RESPONSE_TEXT",
            timestamp: ts,
            title: "Agent Response",
            data: { text: "Here is the summary you requested. The total revenue for Q4 was **$2.4M**." },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Agent Response")).toBeInTheDocument();
    },
};

export const TaskCompleted: Story = {
    args: {
        step: {
            id: "s-3",
            type: "TASK_COMPLETED",
            timestamp: ts,
            title: "Task Completed",
            data: { finalMessage: "All tasks finished successfully." },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Task Completed")).toBeInTheDocument();
        expect(canvas.getByText("All tasks finished successfully.")).toBeInTheDocument();
    },
};

export const TaskFailed: Story = {
    args: {
        step: {
            id: "s-4",
            type: "TASK_FAILED",
            timestamp: ts,
            title: "Task Failed",
            data: {
                errorDetails: {
                    message: "Connection timeout while fetching data from external API.",
                    code: "ERR_TIMEOUT",
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Task Failed")).toBeInTheDocument();
        expect(canvas.getByText(/Connection timeout/)).toBeInTheDocument();
    },
};

// --- LLM steps ---

export const LLMCall: Story = {
    args: {
        step: {
            id: "s-5",
            type: "AGENT_LLM_CALL",
            timestamp: ts,
            title: "LLM Call",
            data: {
                llmCall: {
                    modelName: "gpt-4o",
                    promptPreview: "You are a helpful assistant. The user wants a quarterly report...",
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("LLM Call")).toBeInTheDocument();
        expect(canvas.getByText("gpt-4o")).toBeInTheDocument();
    },
};

export const LLMResponseToAgent: Story = {
    args: {
        step: {
            id: "s-6",
            type: "AGENT_LLM_RESPONSE_TO_AGENT",
            timestamp: ts,
            title: "LLM Response",
            data: {
                llmResponseToAgent: {
                    modelName: "gpt-4o",
                    responsePreview: "I'll generate the report by first querying the database...",
                    response: "I'll generate the report by first querying the database for Q4 sales figures across all regions, then summarize the findings.",
                    isFinalResponse: false,
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("LLM Response")).toBeInTheDocument();
        expect(canvas.getByText("Show details")).toBeInTheDocument();
    },
};

// --- Tool decision & invocation ---

export const ToolDecision: Story = {
    args: {
        step: {
            id: "s-7",
            type: "AGENT_LLM_RESPONSE_TOOL_DECISION",
            timestamp: ts,
            title: "Tool Decision",
            data: {
                toolDecision: {
                    isParallel: false,
                    decisions: [
                        {
                            functionCallId: "call-1",
                            toolName: "query_database",
                            toolArguments: { query: "SELECT * FROM sales" },
                            isPeerDelegation: false,
                        },
                    ],
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Tool Decision")).toBeInTheDocument();
        expect(canvas.getByText("query_database")).toBeInTheDocument();
    },
};

export const ToolInvocationStart: Story = {
    args: {
        step: {
            id: "s-8",
            type: "AGENT_TOOL_INVOCATION_START",
            timestamp: ts,
            title: "Tool Invocation: query_database",
            data: {
                toolInvocationStart: {
                    functionCallId: "call-1",
                    toolName: "query_database",
                    toolArguments: { query: "SELECT region, SUM(revenue) FROM sales WHERE quarter='Q4' GROUP BY region" },
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Tool Invocation: query_database")).toBeInTheDocument();
        expect(canvas.getAllByText(/query_database/)).toHaveLength(2);
    },
};

export const ToolExecutionResult: Story = {
    args: {
        step: {
            id: "s-9",
            type: "AGENT_TOOL_EXECUTION_RESULT",
            timestamp: ts,
            title: "Tool Result: query_database",
            data: {
                toolResult: {
                    toolName: "query_database",
                    resultData: {
                        rows: [
                            { region: "North America", revenue: 1200000 },
                            { region: "Europe", revenue: 800000 },
                            { region: "Asia Pacific", revenue: 400000 },
                        ],
                    },
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Tool Result: query_database")).toBeInTheDocument();
        expect(canvas.getAllByText(/query_database/)).toHaveLength(2);
    },
};

// --- Artifact ---

export const ArtifactNotification: Story = {
    args: {
        step: {
            id: "s-10",
            type: "AGENT_ARTIFACT_NOTIFICATION",
            timestamp: ts,
            title: "Artifact: quarterly_report.pdf",
            data: {
                artifactNotification: {
                    artifactName: "quarterly_report.pdf",
                    version: 1,
                    mimeType: "application/pdf",
                    description: "Q4 Sales Report with charts and regional breakdown",
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getAllByText(/quarterly_report.pdf/)).toHaveLength(2);
        expect(canvas.getByText("View File")).toBeInTheDocument();
    },
};

// --- Workflow steps ---

export const WorkflowExecutionStart: Story = {
    args: {
        step: {
            id: "s-11",
            type: "WORKFLOW_EXECUTION_START",
            timestamp: ts,
            title: "Workflow: Report Pipeline",
            data: {
                workflowExecutionStart: {
                    workflowName: "Report Pipeline",
                    executionId: "exec-001",
                    workflowInput: { quarter: "Q4", regions: ["NA", "EU", "APAC"] },
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getAllByText(/Report Pipeline/)).toHaveLength(2);
    },
};

export const WorkflowNodeStart: Story = {
    args: {
        step: {
            id: "s-12",
            type: "WORKFLOW_NODE_EXECUTION_START",
            timestamp: ts,
            title: "Switch Node: Route by Type",
            data: {
                workflowNodeExecutionStart: {
                    nodeId: "switch-1",
                    nodeType: "switch",
                    condition: "input.reportType === 'financial'",
                    trueBranch: "financial-agent",
                    falseBranch: "general-agent",
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Switch Node: Route by Type")).toBeInTheDocument();
        expect(canvas.getByText(/input.reportType/)).toBeInTheDocument();
    },
};

export const WorkflowNodeResult: Story = {
    args: {
        step: {
            id: "s-13",
            type: "WORKFLOW_NODE_EXECUTION_RESULT",
            timestamp: ts,
            title: "Node Result: switch-1",
            data: {
                workflowNodeExecutionResult: {
                    nodeId: "switch-1",
                    status: "success",
                    metadata: {
                        condition: "input.reportType === 'financial'",
                        condition_result: true,
                    },
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Node Result: switch-1")).toBeInTheDocument();
        expect(canvas.getByText("True")).toBeInTheDocument();
    },
};

export const WorkflowExecutionResult: Story = {
    args: {
        step: {
            id: "s-14",
            type: "WORKFLOW_EXECUTION_RESULT",
            timestamp: ts,
            title: "Workflow Completed",
            data: {
                workflowExecutionResult: {
                    status: "success",
                    workflowOutput: { reportUrl: "/artifacts/quarterly_report.pdf", totalRevenue: 2400000 },
                },
            },
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Workflow Completed")).toBeInTheDocument();
        expect(canvas.getByText("success")).toBeInTheDocument();
    },
};

// --- Delegation info ---

export const WithDelegationInfo: Story = {
    args: {
        step: {
            id: "s-15",
            type: "AGENT_TOOL_INVOCATION_START",
            timestamp: ts,
            title: "Delegating to AnalystAgent",
            data: {
                toolInvocationStart: {
                    functionCallId: "call-3",
                    toolName: "delegate_to_analyst",
                    toolArguments: { task: "Analyze Q4 trends" },
                    isPeerInvocation: true,
                },
            },
            delegationInfo: [
                {
                    functionCallId: "call-3",
                    peerAgentName: "AnalystAgent",
                    subTaskId: "subtask-abc123def456",
                },
            ],
            ...baseStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getAllByText(/AnalystAgent/)).toHaveLength(2);
    },
};

// --- Variants ---

export const Highlighted: Story = {
    args: {
        step: {
            id: "s-16",
            type: "USER_REQUEST",
            timestamp: ts,
            title: "Highlighted Step",
            data: { text: "This step is highlighted to indicate it's currently selected." },
            ...baseStep,
        },
        isHighlighted: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Highlighted Step")).toBeInTheDocument();
    },
};

export const PopoverVariant: Story = {
    args: {
        step: {
            id: "s-17",
            type: "AGENT_RESPONSE_TEXT",
            timestamp: ts,
            title: "Popover Variant",
            data: { text: "This card uses the popover styling variant." },
            ...baseStep,
        },
        variant: "popover",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Popover Variant")).toBeInTheDocument();
    },
};
