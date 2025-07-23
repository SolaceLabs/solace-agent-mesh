/* eslint-disable @typescript-eslint/no-explicit-any */

// TypeScript definitions mirroring the Python types used by the frontend.

// Basic JSON-RPC Types

export interface JSONRPCError {
    code: number;
    message: string;
    data?: any; // Can be more specific if needed
}

export interface JSONRPCResponse {
    jsonrpc?: "2.0";
    id?: number | string | null;
    result?: any | null; // Specific types like Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent will be used in context
    error?: JSONRPCError | null;
}

// Message Part Types

export interface FileContent {
    name?: string | null;
    mimeType?: string | null;
    bytes?: string | null; // Assuming base64 string
    uri?: string | null;
}

export interface TextPart {
    type: "text";
    text: string;
    metadata?: { [key: string]: any } | null;
}

export interface FilePart {
    type: "file";
    file: FileContent;
    metadata?: { [key: string]: any } | null;
}

export interface DataPart {
    type: "data";
    data: { [key: string]: any };
    metadata?: { [key: string]: any } | null;
}

// Union type for Message Parts
export type Part = TextPart | FilePart | DataPart;

// Message Type

export interface Message {
    role: "user" | "agent";
    parts: Part[];
    metadata?: { [key: string]: any; agent_name?: string } | null;
}

// Task Related Types

// Using string union for TaskState as enums can behave slightly differently
export type TaskState = "submitted" | "working" | "input-required" | "completed" | "canceled" | "failed" | "unknown";

export interface TaskStatus {
    state: TaskState;
    message?: Message | null;
    timestamp: string; // ISO date string from backend
}

export interface Artifact {
    name?: string | null;
    description?: string | null;
    parts: Part[];
    metadata?: { [key: string]: any; agent_name?: string } | null;
    index?: number;
    append?: boolean | null;
    lastChunk?: boolean | null;
}

export interface Task {
    id: string;
    sessionId?: string | null;
    status: TaskStatus;
    artifacts?: Artifact[] | null;
    history?: Message[] | null;
    metadata?: { [key: string]: any } | null;
}

// Event Types (for SSE)

export interface TaskStatusUpdateEvent {
    id: string; // Task ID
    status: TaskStatus;
    final?: boolean; // Optional boolean, defaults to false if missing
    metadata?: { [key: string]: any } | null;
}

export interface TaskArtifactUpdateEvent {
    id: string; // Task ID
    artifact: Artifact;
    metadata?: { [key: string]: any } | null;
}

// Specific Result Types for JSONRPCResponse
// These help type checking where the result structure is known

export type TaskResponseResult = Task;
export type TaskStatusUpdateResult = TaskStatusUpdateEvent;
export type TaskArtifactUpdateResult = TaskArtifactUpdateEvent;

export interface JSONRPCResponseWithTask extends JSONRPCResponse {
    result?: TaskResponseResult | null;
}

export interface JSONRPCResponseWithStatusUpdate extends JSONRPCResponse {
    result?: TaskStatusUpdateResult | null;
}

export interface JSONRPCResponseWithArtifactUpdate extends JSONRPCResponse {
    result?: TaskArtifactUpdateResult | null;
}

// Union type for possible streaming results
export type StreamingResult = TaskStatusUpdateResult | TaskArtifactUpdateResult;

export interface JSONRPCResponseStreaming extends JSONRPCResponse {
    result?: StreamingResult | null;
}

// Added for Artifact Panel feature
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

// ADD AgentProvider, AgentAuthentication, AgentCard interfaces
export interface AgentProvider {
    name?: string | null;
    url?: string | null;
}

export interface AgentAuthentication {
    type: string; // e.g., "none", "oauth2_client_credentials"
    token_url?: string | null;
    // client_id_env_var and client_secret_env_var are intentionally omitted for frontend security
    scopes?: string[] | null;
}

export interface AgentTool {
    id: string;
    name: string;
    description: string;
    tags?: string[] | null;
    examples?: string[] | null;
    inputModes?: string[] | null;
    outputModes?: string[] | null;
}

export interface AgentSkill {
    id: string;
    name: string;
    description: string;
    tags?: string[] | null;
    examples?: string[] | null;
    inputModes?: string[] | null;
    outputModes?: string[] | null;
}

export interface AgentCard {
    name: string;
    display_name?: string | null;
    description?: string | null;
    version?: string | null;
    url?: string | null;
    provider?: AgentProvider | null;
    documentationUrl?: string | null;
    capabilities?: { [key: string]: any } | null; // e.g., {"streaming": true, "pushNotifications": false}
    authentication?: AgentAuthentication | null;
    defaultInputModes?: string[] | null;
    defaultOutputModes?: string[] | null;
    skills?: AgentSkill[] | null;
    tools?: AgentTool[] | null;
    peer_agents?: { [agentName: string]: any }; // Map of peer agents this agent can call
    model_settings?: { [key: string]: any } | null;
    a2a_protocol_version?: string | null;
    adk_version?: string | null;
    sac_version?: string | null;
    last_seen?: string | null; // ISO 8601 timestamp
}
