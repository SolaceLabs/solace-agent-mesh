/* eslint-disable @typescript-eslint/no-explicit-any */

import type { LucideIcon } from "lucide-react";

import type { AgentCard, AgentSkill, Part } from "./be";

export interface A2AEventSSEPayload {
    event_type: "a2a_message" | string;
    timestamp: string; // ISO 8601
    solace_topic: string;
    direction: "request" | "response" | "status_update" | "artifact_update" | "discovery" | string;
    source_entity: string;
    target_entity: string;
    message_id?: string | null; // JSON-RPC ID
    task_id?: string | null; // A2A Task ID
    payload_summary: {
        method?: string;
        params_preview?: string;
    };
    full_payload: Record<string, any>; // The full A2A JSON-RPC message or other payload
}

export interface TaskFE {
    taskId: string;
    initialRequestText: string; // Truncated text from the first 'request' event
    events: A2AEventSSEPayload[]; // Ordered list of raw SSE event payloads
    firstSeen: Date;
    lastUpdated: Date;
    parentTaskId?: string | null;
}

export interface TaskStoreState {
    tasks: Record<string, TaskFE>;
    taskOrder: string[]; // Array of taskIds to maintain insertion order or sorted order
}

/**
 * Represents a tool event in the chat conversation.
 */
export interface ToolEvent {
    toolName: string;
    data: unknown; // The result data from the tool
}

/**
 * @deprecated use AgentCardInfo
 */
export interface AgentInfo extends AgentCard {
    display_name?: string;
    last_seen?: string;
    peer_agents?: string[];
    tools?: AgentSkill[];
}

/**
 * A UI-specific interface that extends the official A2A AgentCard with additional
 * properties needed for rendering, like a displayName.
 */
export interface AgentCardInfo extends AgentInfo {
    displayName?: string;
    peerAgents?: string[];
    tools?: AgentSkill[];
}

// This is a UI-specific type for managing artifacts in the side panel.
// It is distinct from the A2A `Artifact` type.
export interface ArtifactInfo {
    filename: string;
    mime_type: string;
    size: number; // in bytes
    last_modified: string; // ISO 8601 timestamp
    uri?: string; // Optional but recommended artifact URI
    version?: number; // Optional: Represents the latest version number when listing
    versionCount?: number; // Optional: Total number of available versions
    description?: string | null; // Optional: Description of the artifact
    schema?: string | null | object; // Optional: Schema for the structure artifact
    accumulatedContent?: string; // Optional: Accumulated content during creation (plain text from streaming)
    isAccumulatedContentPlainText?: boolean; // Optional: True if accumulatedContent is plain text, false if base64
    isDisplayed?: boolean; // Optional: Tracks if artifact is currently visible to user
    needsEmbedResolution?: boolean; // Optional: Tracks if artifact needs download for embed resolution
    source?: string; // Optional: Source of the artifact (e.g., "project")
}

/**
 * Represents a file attached to a message, primarily for UI rendering.
 * This is distinct from the A2A `FilePart` but can be derived from it.
 */
export interface FileAttachment {
    name: string;
    content?: string; // Base64 encoded content
    mime_type?: string;
    last_modified?: string; // ISO 8601 timestamp
    size?: number;
    uri?: string;
}

/**
 * Represents a UI notification (toast).
 */
export interface Notification {
    id: string;
    message: string;
    type?: "info" | "success" | "warning";
}

export interface ArtifactPart {
    kind: "artifact";
    status: "in-progress" | "completed" | "failed";
    name: string;
    description?: string;
    bytesTransferred?: number;
    file?: FileAttachment; // The completed file info
    error?: string;
}

export type PartFE = Part | ArtifactPart;

/**
 * State for managing artifact rendering preferences and expanded state
 */
export interface ArtifactRenderingState {
    expandedArtifacts: Set<string>;
}

/**
 * Represents a single message in the chat conversation.
 */
export interface MessageFE {
    taskId?: string; // The ID of the task that generated this message
    role?: "user" | "agent";
    isStatusBubble?: boolean; // Added to indicate a temporary status message
    isUser: boolean; // True if the message is from the user, false if from the agent/system
    isStatusMessage?: boolean; // True if this is a temporary status message (e.g., "Agent is thinking")
    isThinkingMessage?: boolean; // Specific flag for the "thinking" status message
    isComplete?: boolean; // ADDED: True if the agent response associated with this message is complete
    isError?: boolean; // ADDED: True if this message represents an error/failure
    uploadedFiles?: File[]; // Array of files uploaded by the user with this message
    toolEvents?: ToolEvent[]; // --- NEW: Array to hold tool call results ---
    authenticationLink?: {
        url: string;
        text: string;
        targetAgent?: string;
        gatewayTaskId?: string;
        authenticationAttempted?: boolean; // Track if auth button was clicked
        rejected?: boolean; // Track if reject button was clicked
    };
    metadata?: {
        // Optional metadata, e.g., for feedback or correlation
        messageId?: string; // Unique ID for the agent's message (if provided by backend)
        sessionId?: string; // The A2A session ID associated with this message exchange
        lastProcessedEventSequence?: number; // Sequence number of the last SSE event processed for this bubble
    };
    parts: PartFE[];
}

// Layout Types

export const LayoutType = {
    GRID: "grid",
    HIERARCHICAL: "hierarchical",
    AUTO: "auto",
    CARDS: "cards",
} as const;

export type LayoutType = (typeof LayoutType)[keyof typeof LayoutType];

export interface LayoutConfig {
    type: string | LayoutType;
    spacing: {
        horizontal: number;
        vertical: number;
    };
    viewport: {
        width: number;
        height: number;
    };
    padding: number;
}

export interface CommunicationEdgeData extends Record<string, unknown> {
    communicationType: "bidirectional" | "unidirectional";
    sourceHandle?: string;
    targetHandle?: string;
}

export interface AgentNodeData extends Record<string, unknown> {
    label: string;
    agentName: string;
    status: "online" | "offline";
    description?: string;
}

// Navigation Types

export interface NavigationItem {
    id: string;
    label: string;
    icon: LucideIcon;
    onClick?: () => void;
    path?: string;
    active?: boolean;
    disabled?: boolean;
    showDividerAfter?: boolean;
    badge?: string;
}

export interface NavigationConfig {
    items: NavigationItem[];
    bottomItems?: NavigationItem[];
}

export interface NavigationContextValue {
    activeItem: string | null;
    setActiveItem: (itemId: string) => void;
    items: NavigationItem[];
    setItems: (items: NavigationItem[]) => void;
}

export interface Session {
    id: string;
    createdTime: string;
    updatedTime: string;
    name: string | null;
    projectId?: string | null;
    projectName?: string | null;
    hasRunningBackgroundTask?: boolean;
}
