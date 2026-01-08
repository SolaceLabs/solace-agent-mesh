import type { Part } from "./be";
import type { FileAttachment } from "./fe";

/**
 * Serialized message bubble format for backend storage.
 * This is the persisted format, distinct from the runtime MessageFE type.
 */
export interface MessageBubble {
    id: string;
    type: "user" | "agent" | "artifact_notification";
    text: string;
    parts?: Part[];
    files?: FileAttachment[];
    uploadedFiles?: Array<{ name: string; type: string }>;
    artifactNotification?: { name: string; version?: number };
    isError?: boolean;
}

/**
 * Task metadata format for backend storage.
 */
export interface TaskMetadata {
    schema_version: number;
    status?: string;
    agent_name?: string;
    feedback?: {
        type: "up" | "down";
        text?: string;
        submitted?: boolean;
    };
    [key: string]: unknown;
}

/**
 * Stored task data structure (any version).
 */
export interface StoredTaskData {
    taskId: string;
    messageBubbles: string; // JSON string
    taskMetadata?: string | null; // JSON string
    createdTime: number;
    userMessage?: string;
}

/**
 * Parsed task structure (after JSON parsing but before migration)
 */
export interface ParsedTaskData extends Omit<StoredTaskData, "messageBubbles" | "taskMetadata"> {
    messageBubbles: MessageBubble[];
    taskMetadata: TaskMetadata | null;
}
