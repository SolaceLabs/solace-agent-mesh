/* eslint-disable @typescript-eslint/no-explicit-any */

// This file is the single source of truth for A2A protocol types in the frontend.
// It re-exports types from the official @a2a-js/sdk to ensure compliance.

import type {
    AgentCard,
    AgentSkill,
    Artifact,
    CancelTaskRequest,
    DataPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
    JSONRPCError,
    JSONRPCErrorResponse,
    JSONRPCResponse,
    Message,
    Part,
    SendMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
} from "@a2a-js/sdk";

// Re-export all the necessary types from the SDK.
export type {
    AgentCard,
    AgentSkill,
    Artifact,
    CancelTaskRequest,
    DataPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
    JSONRPCError,
    JSONRPCErrorResponse,
    JSONRPCResponse,
    Message,
    Part,
    SendMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
};

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
 * Represents a tool execution event for display in a message bubble.
 */
export interface ToolEvent {
    toolName: string;
    data: any;
}

/**
 * Represents a UI notification (toast).
 */
export interface Notification {
    id: string;
    message: string;
    type?: "success" | "info" | "error";
}

/**
 * Represents a message object tailored for the frontend, extending the core A2A `Message`.
 * It includes additional state for UI rendering purposes.
 */
export interface MessageFE extends Message {
    isStatusBubble?: boolean;
    isComplete?: boolean;
    isError?: boolean;
    uploadedFiles?: File[]; // For files being uploaded by the user
    toolEvents?: ToolEvent[];
    artifactNotification?: {
        name: string;
        version?: string;
    };
    // The 'text' content for display will be derived from `parts`.
    // The 'files' for display will be derived from `parts`.
}
