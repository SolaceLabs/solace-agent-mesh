import type { AgentCard } from "@/lib/types/be";
import type { MessageFE } from "@/lib/types/fe";

export const mockAgentCards: AgentCard[] = [
    {
        name: "OrchestratorAgent",
        description: "The Orchestrator component. It manages tasks, and coordinating multi-agent workflows.",
        url: "solace:beta/a2a/v1/agent/request/OrchestratorAgent",
        version: "1.0.0-alpha",
        capabilities: {
            streaming: true,
            pushNotifications: false,
            stateTransitionHistory: false,
            extensions: [
                {
                    params: {
                        tools: [
                            {
                                description:
                                    "\n    Lists all available data artifact filenames and their versions for the current session.\n    Includes a summary of the latest version's metadata for each artifact.\n\n    Args:\n        tool_context: The context provided by the ADK framework.\n\n    Returns:\n        A dictionary containing the list of artifacts with metadata summaries or an error.\n    ",
                                id: "list_artifacts",
                                name: "list_artifacts",
                                tags: [],
                            },
                            {
                                description:
                                    "\n    Loads the content or metadata of a specific artifact version.\n    Early-stage embeds in the filename argument are resolved.\n\n    If load_metadata_only is True, loads the full metadata dictionary.\n    Otherwise, loads text content (potentially truncated) or binary metadata summary.\n\n    Args:\n        filename: The name of the artifact to load. May contain embeds.\n        version: The specific version number to load. Must be explicitly provided.\n        load_metadata_only (bool): If True, load only the metadata JSON. Default False.\n        max_content_length (Optional[int]): Maximum character length for text content.\n                                           If None, uses app configuration. Range: 100-100,000.\n        tool_context: The context provided by the ADK framework.\n\n    Returns:\n        A dictionary containing the artifact details and content/metadata or an error.\n    ",
                                id: "load_artifact",
                                name: "load_artifact",
                                tags: [],
                            },
                        ],
                    },
                    uri: "https://solace.com/a2a/extensions/sam/tools",
                },
            ],
        },
        defaultInputModes: ["text"],
        defaultOutputModes: ["text", "file"],
        skills: [],
        protocolVersion: "",
    },
    {
        name: "MockWorkflow",
        description: "A mock workflow agent used for testing workflow filtering.",
        url: "solace:beta/a2a/v1/agent/request/MockWorkflow",
        version: "1.0.0-alpha",
        capabilities: {
            streaming: true,
            pushNotifications: false,
            stateTransitionHistory: false,
            extensions: [
                {
                    params: {
                        type: "workflow",
                    },
                    uri: "https://solace.com/a2a/extensions/agent-type",
                },
            ],
        },
        defaultInputModes: ["text"],
        defaultOutputModes: ["text"],
        skills: [],
        protocolVersion: "",
    },
];

export const getMockAgentCards = (count: number): AgentCard[] => {
    const agentCards: AgentCard[] = [];
    for (let i = 0; i < count; i++) {
        agentCards.push({
            name: `YamlAgent ${i}`,
            description: `This is mock yaml agent ${i}.`,
            url: `solace:beta/a2a/v1/agent/request/YamlAgent${i}`,
            version: "1.0.0-alpha",
            capabilities: {
                streaming: true,
                pushNotifications: false,
                stateTransitionHistory: false,
                extensions: [],
            },
            defaultInputModes: ["text"],
            defaultOutputModes: ["text"],
            skills: [],
            protocolVersion: "",
        });
    }
    return agentCards;
};

export const mockMessages: MessageFE[] = [
    {
        isUser: false,
        parts: [
            {
                kind: "text",
                text: "Hi! I'm the Orchestrator Agent. How can I help?",
            },
        ],
        isComplete: true,
        metadata: { sessionId: "mock-session-id", lastProcessedEventSequence: 0 },
    },
    {
        isUser: true,
        parts: [
            {
                kind: "text",
                text: "Hello! I need help with a coding task.",
            },
        ],
        isComplete: true,
        metadata: { sessionId: "mock-session-id", lastProcessedEventSequence: 1 },
    },
    {
        isUser: false,
        parts: [
            {
                kind: "text",
                text: "I'd be happy to help with your coding task. Could you please provide more details about what you're working on?",
            },
        ],
        isComplete: true,
        metadata: { sessionId: "mock-session-id", lastProcessedEventSequence: 2 },
    },
];

export const mockLoadingMessage: MessageFE = {
    isUser: false,
    parts: [
        {
            kind: "text",
            text: "Working on your request...",
        },
    ],
    isStatusBubble: true,
    isComplete: false,
    taskId: "mock-task-id",
    metadata: { sessionId: "mock-session-id", lastProcessedEventSequence: 5 },
};

export const mockToolsets = [
    {
        id: "artifact_management",
        name: "Artifact Management",
        description: "List, read, create, update, and delete artifacts.",
    },
    {
        id: "data_analysis",
        name: "Data Analysis",
        description: "Create static chart images from data in JSON or YAML format.",
    },
    {
        id: "web",
        name: "Web Access",
        description: "Access the web to find information to complete user requests.",
    },
];
