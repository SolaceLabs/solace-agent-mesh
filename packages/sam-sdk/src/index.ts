/**
 * SAM SDK - TypeScript SDK for SAM iframe applications.
 *
 * @packageDocumentation
 */

export { SAMClient } from './client';
export type {
  AgentCallOptions,
  AgentCallResult,
  AgentInfo,
  AgentsAPI,
  ArtifactObject,
  ArtifactUploadOptions,
  ArtifactUploadResult,
  ArtifactsAPI,
  ConsoleAPI,
  LogEntry,
  SAMMessage,
  StorageAPI,
  Theme,
  UIAPI,
  SAMAPI,
} from './types';
export { MessageType } from './types';

/**
 * Singleton SAM client instance.
 */
import { SAMClient } from './client';
export const SAM = new SAMClient();
