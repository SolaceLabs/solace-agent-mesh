/* eslint-disable @typescript-eslint/no-explicit-any */

// This file is the single source of truth for A2A protocol types in the frontend.
// It re-exports types from the official @a2a-js/sdk to ensure compliance.

import type {
    AgentCard,
    AgentExtension,
    AgentProvider,
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
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
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
    AgentExtension,
    AgentProvider,
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
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
};

/**
 * A UI-specific interface that extends the official A2A AgentCard with additional
 * properties needed for rendering, like a display_name.
 */
export interface AgentInfo extends AgentCard {
    display_name?: string;
    last_seen?: string;
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
}


