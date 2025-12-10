/**
 * Type definitions for SAM SDK.
 */

/**
 * Message types for parent-child iframe communication.
 */
export enum MessageType {
  // Initialization
  INIT = 'sam:init',
  READY = 'sam:ready',

  // Agent calls
  AGENT_CALL = 'sam:agent:call',
  AGENT_RESPONSE = 'sam:agent:response',
  AGENT_ERROR = 'sam:agent:error',
  AGENT_STREAM = 'sam:agent:stream',
  AGENT_STATUS = 'sam:agent:status',
  AGENT_ARTIFACT = 'sam:agent:artifact',
  AGENT_LIST = 'sam:agent:list',
  AGENT_LIST_RESPONSE = 'sam:agent:list:response',

  // Storage operations
  STORAGE_GET = 'sam:storage:get',
  STORAGE_SET = 'sam:storage:set',
  STORAGE_DELETE = 'sam:storage:delete',
  STORAGE_LIST = 'sam:storage:list',
  STORAGE_CLEAR = 'sam:storage:clear',
  STORAGE_RESPONSE = 'sam:storage:response',

  // Artifacts
  ARTIFACT_UPLOAD = 'sam:artifact:upload',
  ARTIFACT_DOWNLOAD = 'sam:artifact:download',
  ARTIFACT_RESPONSE = 'sam:artifact:response',

  // UI theme
  THEME_GET = 'sam:theme:get',
  THEME_RESPONSE = 'sam:theme:response',
  THEME_CHANGED = 'sam:theme:changed',
}

/**
 * Base message structure for all postMessage communication.
 */
export interface SAMMessage {
  type: MessageType;
  id: string;
  payload?: any;
}

/**
 * Theme type (light or dark).
 */
export type Theme = 'light' | 'dark';

/**
 * Agent call options.
 */
export interface AgentCallOptions {
  prompt: string;
  context?: Record<string, any>;
  stream?: boolean;
  files?: File[]; // Optional: Attach documents/images to agent call
  sessionId?: string; // Optional: Explicit session ID (SDK manages automatically if not provided)
  timeout?: number; // Optional: Timeout in milliseconds (default: 300000 / 5 minutes)
  onText?: (text: string) => void;
  onStatus?: (status: string) => void;
  onArtifact?: (artifact: ArtifactObject) => void;
}

/**
 * Agent call result.
 */
export interface AgentCallResult {
  response: string;
  sessionId: string; // Session ID for this conversation (for subsequent calls)
  artifacts?: ArtifactObject[]; // Array of artifact objects with .download() method
  metadata?: Record<string, any>;
}

/**
 * Agent metadata.
 */
export interface AgentInfo {
  id: string;
  name: string;
  description?: string;
  version?: string;
  capabilities?: string[];
}

/**
 * Storage operations.
 */
export interface StorageAPI {
  get<T = any>(key: string): Promise<T | null>;
  set<T = any>(key: string, value: T): Promise<void>;
  delete(key: string): Promise<void>;
  list(prefix?: string): Promise<string[]>;
  clear(): Promise<void>;
}

/**
 * Agent operations.
 */
export interface AgentsAPI {
  call(agentName: string, options: AgentCallOptions): Promise<AgentCallResult>;
  list(): Promise<AgentInfo[]>;
}

/**
 * Result of artifact upload operation.
 */
export interface ArtifactUploadResult {
  artifactId: string;       // URI of the uploaded artifact
  sessionId: string;        // Session ID for this upload
  filename: string;         // Original filename
  size: number;             // File size in bytes
  mimeType: string;         // MIME type of the file
  metadata: Record<string, any>;  // Additional metadata
  createdAt: string;        // ISO timestamp of creation
}

/**
 * Options for artifact upload.
 */
export interface ArtifactUploadOptions {
  sessionId?: string | null;  // Explicit session ID (null = force new session, undefined = use persistent session)
}

/**
 * Artifact object with download capability.
 * Can be received from onArtifact callbacks or created from URIs.
 */
export interface ArtifactObject {
  name: string;
  file?: {
    uri?: string;
    bytes?: string;
    mimeType?: string;
  };
  download(): Promise<Blob>;
}

/**
 * Artifact operations.
 */
export interface ArtifactsAPI {
  upload(file: File, options?: ArtifactUploadOptions): Promise<ArtifactUploadResult>;
  download(uriOrArtifact: string | ArtifactObject): Promise<Blob>;
  fromUri(uri: string): ArtifactObject;
}

/**
 * UI operations.
 */
export interface UIAPI {
  getTheme(): Theme;
  onThemeChange(callback: (theme: Theme) => void): () => void;
}

/**
 * Main SAM SDK interface.
 */
export interface SAMAPI {
  ready(): Promise<void>;
  agents: AgentsAPI;
  storage: StorageAPI;
  artifacts: ArtifactsAPI;
  ui: UIAPI;
}
