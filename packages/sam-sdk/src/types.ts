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
}

/**
 * Agent call result.
 */
export interface AgentCallResult {
  response: string;
  artifacts?: string[];
  metadata?: Record<string, any>;
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
}

/**
 * Artifact operations.
 */
export interface ArtifactsAPI {
  upload(file: File): Promise<string>;
  download(artifactId: string): Promise<Blob>;
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
