import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { http, HttpResponse } from "msw";

import NodeDetailsCard from "@/lib/components/activities/FlowChart/NodeDetailsCard";
import type { VisualizerStep } from "@/lib/types";

// Helper to create base step properties
const baseStepProps = {
    rawEventIds: [] as string[],
    nestingLevel: 0,
    owningTaskId: "task-1",
};

// Helper to create artifact tool invocation/result step pairs
const createArtifactToolSteps = (filename: string, id: string) => {
    const invocationStep: VisualizerStep = {
        id: `${id}-invocation`,
        type: "AGENT_TOOL_INVOCATION_START",
        timestamp: new Date().toISOString(),
        title: "Tool Invocation",
        data: {
            toolInvocationStart: {
                functionCallId: `call-${id}`,
                toolName: "_notify_artifact_save",
                toolArguments: { filename, version: 0, status: "success" },
            },
        },
        ...baseStepProps,
    };

    const resultStep: VisualizerStep = {
        id: `${id}-result`,
        type: "AGENT_TOOL_EXECUTION_RESULT",
        timestamp: new Date().toISOString(),
        title: "Tool Result",
        data: {
            toolResult: {
                toolName: "_notify_artifact_save",
                resultData: {
                    filename,
                    version: 0,
                    status: "success",
                    message: "Artifact has been created and provided to the requester",
                },
            },
        },
        ...baseStepProps,
    };

    return { invocationStep, resultStep };
};

// Sample HTML content for artifact preview
const sampleHtmlContent = `<!DOCTYPE html>
<html>
<head>
    <title>Sample Dashboard</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f5f5f5; }
        .card { background: white; padding: 20px; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
    </style>
</head>
<body>
    <h1>Sample Dashboard</h1>
    <div class="card">
        <h2>Welcome</h2>
        <p>This is a sample HTML artifact rendered in the NodeDetailsCard.</p>
    </div>
</body>
</html>`;

// Sample long text
const longTextContent = "Text text text. ".repeat(100);

// Convert strings to base64
const htmlBase64 = btoa(sampleHtmlContent);
const textBase64 = btoa(longTextContent);

// Pre-built artifact tool steps
const htmlArtifactSteps = createArtifactToolSteps("sample_webpage.html", "html");
const textArtifactSteps = createArtifactToolSteps("analysis_report.txt", "text");

const mockUserRequestStep: VisualizerStep = {
    id: "step-1",
    type: "USER_REQUEST",
    timestamp: new Date().toISOString(),
    title: "User Request",
    data: { text: "Generate a sample HTML dashboard" },
    ...baseStepProps,
};

const handlers = [
    http.get("*/api/v1/artifacts/:sessionId/:filename/versions/:version", ({ params }) => {
        const filename = params.filename as string;

        if (filename.endsWith(".txt")) {
            return new HttpResponse(
                Uint8Array.from(atob(textBase64), c => c.charCodeAt(0)),
                {
                    headers: {
                        "Content-Type": "text/plain",
                    },
                }
            );
        }
        return new HttpResponse(
            Uint8Array.from(atob(htmlBase64), c => c.charCodeAt(0)),
            {
                headers: {
                    "Content-Type": "text/html",
                },
            }
        );
    }),
];

const meta = {
    title: "Workflow/NodeDetailsCard",
    component: NodeDetailsCard,
    parameters: {
        layout: "fullscreen",
        msw: { handlers },
        chatContext: {
            sessionId: "test-session-123",
            artifacts: [],
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return (
                // Mimics the DialogContent container from FlowChartPanel.tsx
                <div className="overflow-hidden p-4">
                    <div className="bg-background flex h-[50vh-100px] w-[60vw] flex-col rounded-lg border shadow-lg">{storyResult}</div>
                </div>
            );
        },
    ],
    tags: ["autodocs"],
} satisfies Meta<typeof NodeDetailsCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const User: Story = {
    args: {
        nodeDetails: {
            nodeType: "user",
            label: "User Request",
            description: "Initial user request",
            requestStep: mockUserRequestStep,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("User Request")).toBeInTheDocument();
        expect(canvas.getByText("User Input")).toBeInTheDocument();
        expect(canvas.getByText("Generate a sample HTML dashboard")).toBeInTheDocument();
    },
};

export const Agent: Story = {
    args: {
        nodeDetails: {
            nodeType: "agent",
            label: "Assistant Agent",
            description: "Main assistant agent",
            requestStep: mockUserRequestStep,
            resultStep: {
                id: "step-4",
                type: "AGENT_RESPONSE_TEXT",
                timestamp: new Date().toISOString(),
                title: "Agent Response",
                data: { text: "I've created the HTML dashboard for you." },
                ...baseStepProps,
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Assistant Agent")).toBeInTheDocument();
        expect(canvas.getByText("REQUEST")).toBeInTheDocument();
        expect(canvas.getByText("RESULT")).toBeInTheDocument();
        expect(canvas.getByText("I've created the HTML dashboard for you.")).toBeInTheDocument();
    },
};

export const LLM: Story = {
    args: {
        nodeDetails: {
            nodeType: "llm",
            label: "LLM Call",
            description: "Language model inference",
            requestStep: {
                id: "step-5",
                type: "AGENT_LLM_CALL",
                timestamp: new Date().toISOString(),
                title: "LLM Request",
                data: {
                    llmCall: {
                        modelName: "gpt-4",
                        promptPreview: "You are a helpful assistant...",
                    },
                },
                ...baseStepProps,
            },
            resultStep: {
                id: "step-6",
                type: "AGENT_LLM_RESPONSE_TO_AGENT",
                timestamp: new Date().toISOString(),
                title: "LLM Response",
                data: {
                    llmResponseToAgent: {
                        modelName: "gpt-4",
                        responsePreview: "I'll help you create that dashboard...",
                        response: "I'll help you create that dashboard with all the requested features.",
                        isFinalResponse: false,
                    },
                },
                ...baseStepProps,
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("LLM Call")).toBeInTheDocument();
        expect(canvas.getByText("LLM Request")).toBeInTheDocument();
        expect(canvas.getByText("LLM Response")).toBeInTheDocument();
        expect(canvas.getAllByText("gpt-4")).toHaveLength(2);
    },
};

export const Switch: Story = {
    args: {
        nodeDetails: {
            nodeType: "switch",
            label: "Route Decision",
            description: "Conditional routing",
            requestStep: {
                id: "step-7",
                type: "WORKFLOW_NODE_EXECUTION_START",
                timestamp: new Date().toISOString(),
                title: "Switch Node",
                data: {
                    workflowNodeExecutionStart: {
                        nodeId: "switch-1",
                        nodeType: "switch",
                        cases: [
                            { condition: "input.type === 'report'", node: "report-agent" },
                            { condition: "input.type === 'chart'", node: "chart-agent" },
                        ],
                        defaultBranch: "fallback-agent",
                    },
                },
                ...baseStepProps,
            },
            resultStep: {
                id: "step-8",
                type: "WORKFLOW_NODE_EXECUTION_RESULT",
                timestamp: new Date().toISOString(),
                title: "Switch Result",
                data: {
                    workflowNodeExecutionResult: {
                        nodeId: "switch-1",
                        status: "success",
                        metadata: {
                            selected_branch: "report-agent",
                            selected_case_index: 0,
                        },
                    },
                },
                ...baseStepProps,
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Route Decision")).toBeInTheDocument();
        expect(canvas.getByText("Switch Node")).toBeInTheDocument();
        expect(canvas.getByText("Cases:")).toBeInTheDocument();
        expect(canvas.getAllByText("report-agent")).toHaveLength(2);
        expect(canvas.getByText("Selected Branch:")).toBeInTheDocument();
    },
};

export const Loop: Story = {
    args: {
        nodeDetails: {
            nodeType: "loop",
            label: "Iteration Loop",
            description: "Loop through items",
            requestStep: {
                id: "step-9",
                type: "WORKFLOW_NODE_EXECUTION_START",
                timestamp: new Date().toISOString(),
                title: "Loop Node",
                data: {
                    workflowNodeExecutionStart: {
                        nodeId: "loop-1",
                        nodeType: "loop",
                        condition: "items.length > 0",
                        maxIterations: 10,
                        loopDelay: "1s",
                    },
                },
                ...baseStepProps,
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Iteration Loop")).toBeInTheDocument();
        expect(canvas.getByText("Loop Node")).toBeInTheDocument();
        expect(canvas.getByText("items.length > 0")).toBeInTheDocument();
        expect(canvas.getByText("10")).toBeInTheDocument();
    },
};

export const ToolWithHTMLArtifact: Story = {
    args: {
        nodeDetails: {
            nodeType: "tool",
            label: "_notify_artifact_save",
            description: "Tool Node",
            requestStep: htmlArtifactSteps.invocationStep,
            resultStep: htmlArtifactSteps.resultStep,
            createdArtifacts: [
                {
                    filename: "sample_webpage.html",
                    version: 0,
                    mimeType: "text/html",
                    description: "Complete HTML webpage demonstrating various elements",
                },
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findAllByText("_notify_artifact_save")).toHaveLength(3);
        expect(canvas.getByText("CREATED ARTIFACTS")).toBeInTheDocument();
        expect(canvas.getAllByText("sample_webpage.html")).toHaveLength(3);
        await canvas.findByTitle("HTML Preview");
    },
};

export const ToolWithTruncatedArtifact: Story = {
    args: {
        nodeDetails: {
            nodeType: "tool",
            label: "_notify_artifact_save",
            description: "Tool Node with truncated text",
            requestStep: textArtifactSteps.invocationStep,
            resultStep: textArtifactSteps.resultStep,
            createdArtifacts: [
                {
                    filename: "analysis_report.txt",
                    version: 0,
                    mimeType: "text/plain",
                    description: "Analysis report that exceeds 1000 characters and will be truncated",
                },
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findAllByText("_notify_artifact_save")).toHaveLength(3);
        expect(canvas.getAllByText("analysis_report.txt")).toHaveLength(3);
        // Wait for truncation message to appear (async content load)
        await canvas.findByText("Content truncated at first 1,000 characters", {}, { timeout: 3000 });
    },
};
