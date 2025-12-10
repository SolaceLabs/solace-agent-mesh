/**
 * SAM SDK Client implementation.
 */

import type {
  AgentCallOptions,
  AgentCallResult,
  AgentInfo,
  AgentsAPI,
  ArtifactObject,
  ArtifactUploadOptions,
  ArtifactUploadResult,
  ArtifactsAPI,
  SAMMessage,
  StorageAPI,
  Theme,
  UIAPI,
} from './types';
import { MessageType } from './types';

/**
 * Generate unique message ID.
 */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * SAM SDK Client.
 */
export class SAMClient {
  private isReady = false;
  private readyPromise: Promise<void>;
  private pendingMessages = new Map<string, { resolve: (value: any) => void; reject: (error: any) => void; options?: any }>();
  private themeCallbacks = new Set<(theme: Theme) => void>();
  private currentTheme: Theme = 'light';
  private persistentSessionId: string | null = null; // Auto-managed session for persistent mode

  constructor() {
    // Listen for messages from parent
    window.addEventListener('message', this.handleMessage.bind(this));

    // Request initialization from parent
    this.readyPromise = new Promise((resolve) => {
      this.sendMessage(MessageType.INIT, {});

      const checkReady = () => {
        if (this.isReady) {
          resolve();
        } else {
          setTimeout(checkReady, 100);
        }
      };
      checkReady();
    });
  }

  /**
   * Wait for SDK to be ready.
   */
  async ready(): Promise<void> {
    return this.readyPromise;
  }

  /**
   * Send message to parent frame.
   */
  private sendMessage(type: MessageType, payload: any): string {
    const id = generateId();
    const message: SAMMessage = { type, id, payload };

    if (window.parent) {
      window.parent.postMessage(message, '*');
    }

    return id;
  }

  /**
   * Send message and wait for response.
   */
  private async sendRequest<T = any>(type: MessageType, payload: any, options?: any, timeoutMs?: number): Promise<T> {
    const id = this.sendMessage(type, payload);

    // Default timeout: 5 minutes for agent calls, 30 seconds for others
    const defaultTimeout = type === MessageType.AGENT_CALL ? 300000 : 30000;
    const timeout = timeoutMs ?? defaultTimeout;

    return new Promise((resolve, reject) => {
      this.pendingMessages.set(id, { resolve, reject, options });

      // Timeout after specified duration
      setTimeout(() => {
        if (this.pendingMessages.has(id)) {
          this.pendingMessages.delete(id);
          reject(new Error(`Request timed out after ${timeout / 1000} seconds`));
        }
      }, timeout);
    });
  }

  /**
   * Handle messages from parent frame.
   */
  private handleMessage(event: MessageEvent) {
    const message = event.data as SAMMessage;

    if (!message || !message.type) {
      return;
    }

    // Handle READY message
    if (message.type === MessageType.READY) {
      this.isReady = true;
      this.currentTheme = message.payload?.theme || 'light';
      return;
    }

    // Handle theme change
    if (message.type === MessageType.THEME_CHANGED) {
      this.currentTheme = message.payload.theme;
      this.themeCallbacks.forEach((callback) => callback(message.payload.theme));
      return;
    }

    // Handle responses to pending requests
    const pending = this.pendingMessages.get(message.id);
    if (pending) {
      // Handle streaming events
      if (message.type === MessageType.AGENT_STREAM) {
        pending.options?.onText?.(message.payload.text);
        return;
      }
      if (message.type === MessageType.AGENT_STATUS) {
        pending.options?.onStatus?.(message.payload.status);
        return;
      }
      if (message.type === MessageType.AGENT_ARTIFACT) {
        // Wrap the artifact with download capability before passing to callback
        const wrappedArtifact = this.createArtifactObject(message.payload);
        pending.options?.onArtifact?.(wrappedArtifact);
        return;
      }

      this.pendingMessages.delete(message.id);

      if (message.type.endsWith(':error')) {
        pending.reject(new Error(message.payload?.error || 'Unknown error'));
      } else {
        pending.resolve(message.payload);
      }
    }
  }

  /**
   * Agents API.
   */
  get agents(): AgentsAPI {
    return {
      call: async (agentName: string, options: AgentCallOptions): Promise<AgentCallResult> => {
        await this.ready();

        // Use explicit sessionId if provided, otherwise use persistent session (default behavior)
        const effectiveSessionId = options.sessionId || this.persistentSessionId;

        // Convert File objects to base64 for postMessage transfer
        const fileData = options.files ? await Promise.all(
          options.files.map(async (file) => ({
            name: file.name,
            type: file.type,
            size: file.size,
            data: await new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(reader.result as string);
              reader.onerror = reject;
              reader.readAsDataURL(file);
            })
          }))
        ) : undefined;

        // Don't send callbacks, File objects, timeout, or sessionId over postMessage (handled separately)
        const { onText, onStatus, onArtifact, files, timeout, sessionId, ...payloadOptions } = options;
        const result = await this.sendRequest<AgentCallResult>(
          MessageType.AGENT_CALL,
          { agentName, ...payloadOptions, files: fileData, sessionId: effectiveSessionId },
          options,
          timeout
        );

        // Store returned session ID for future calls (persistent mode)
        if (result.sessionId) {
          this.persistentSessionId = result.sessionId;
        }

        // Wrap artifacts array items (could be URI strings or artifact objects)
        if (result.artifacts && result.artifacts.length > 0) {
          result.artifacts = result.artifacts.map((item: any) => {
            // If it's already a string URI, convert to artifact object
            if (typeof item === 'string') {
              return this.createArtifactObject({
                name: item.split('/').pop()?.split('?')[0] || 'artifact',
                file: { uri: item }
              });
            }
            // If it's an artifact object, wrap it with download method
            if (typeof item === 'object') {
              return this.createArtifactObject(item);
            }
            return item;
          });
        }

        return result;
      },

      list: async (): Promise<AgentInfo[]> => {
        await this.ready();
        const response = await this.sendRequest(MessageType.AGENT_LIST, {});
        return response.agents || [];
      },
    };
  }

  /**
   * Storage API.
   */
  get storage(): StorageAPI {
    return {
      get: async <T = any>(key: string): Promise<T | null> => {
        await this.ready();
        const response = await this.sendRequest(MessageType.STORAGE_GET, { key });
        return response.value;
      },

      set: async <T = any>(key: string, value: T): Promise<void> => {
        await this.ready();
        await this.sendRequest(MessageType.STORAGE_SET, { key, value });
      },

      delete: async (key: string): Promise<void> => {
        await this.ready();
        await this.sendRequest(MessageType.STORAGE_DELETE, { key });
      },

      list: async (prefix?: string): Promise<string[]> => {
        await this.ready();
        const response = await this.sendRequest(MessageType.STORAGE_LIST, { prefix });
        return response.keys;
      },

      clear: async (): Promise<void> => {
        await this.ready();
        await this.sendRequest(MessageType.STORAGE_CLEAR, {});
      },
    };
  }

  /**
   * Helper to convert base64 data URL to Blob.
   */
  private base64ToBlob(dataUrl: string, mimeType: string = 'application/octet-stream'): Blob {
    // Handle both data URLs and raw base64
    const base64Data = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
    const byteCharacters = atob(base64Data);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  }

  /**
   * Create artifact object with download method.
   */
  private createArtifactObject(artifactData: any): ArtifactObject {
    return {
      name: artifactData.name || 'unknown',
      file: artifactData.file,
      download: async (): Promise<Blob> => {
        // If bytes are present, convert directly to Blob
        if (artifactData.file?.bytes) {
          return this.base64ToBlob(
            artifactData.file.bytes,
            artifactData.file.mimeType || 'application/octet-stream'
          );
        }
        // Otherwise download from URI
        if (artifactData.file?.uri) {
          return this.downloadFromUri(artifactData.file.uri);
        }
        throw new Error('Artifact has no bytes or URI available for download');
      }
    };
  }

  /**
   * Download artifact from URI.
   */
  private async downloadFromUri(uri: string): Promise<Blob> {
    await this.ready();
    const response = await this.sendRequest(MessageType.ARTIFACT_DOWNLOAD, { artifactId: uri });
    // Convert base64 back to Blob
    const base64Response = await fetch(response.data);
    return base64Response.blob();
  }

  /**
   * Artifacts API.
   */
  get artifacts(): ArtifactsAPI {
    return {
      upload: async (file: File, options?: ArtifactUploadOptions): Promise<ArtifactUploadResult> => {
        await this.ready();

        // Determine effective session ID:
        // 1. Explicit sessionId from options (null = force new session)
        // 2. Fall back to persistent session if no explicit sessionId provided
        let effectiveSessionId: string | null | undefined;
        if (options && 'sessionId' in options) {
          // Explicit control: use provided sessionId (could be null for new session)
          effectiveSessionId = options.sessionId;
        } else {
          // Default: use persistent session
          effectiveSessionId = this.persistentSessionId;
        }

        // Convert file to base64 for transfer
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.onerror = reject;
          reader.readAsDataURL(file);
        });

        const response = await this.sendRequest(MessageType.ARTIFACT_UPLOAD, {
          name: file.name,
          type: file.type,
          size: file.size,
          data: base64,
          sessionId: effectiveSessionId,  // null = force new session, undefined/string = use that session
        });

        const result = {
          artifactId: response.artifactId,
          sessionId: response.sessionId,
          filename: response.filename,
          size: response.size,
          mimeType: response.mimeType,
          metadata: response.metadata || {},
          createdAt: response.createdAt
        };

        // Store returned session ID for future operations (unless explicit control was used)
        if (result.sessionId && !(options && 'sessionId' in options)) {
          // Only update persistent session if app didn't explicitly control it
          this.persistentSessionId = result.sessionId;
        }

        return result;
      },

      download: async (uriOrArtifact: string | ArtifactObject): Promise<Blob> => {
        // If it's already an ArtifactObject, call its download method
        if (typeof uriOrArtifact === 'object' && 'download' in uriOrArtifact) {
          return uriOrArtifact.download();
        }
        // Otherwise it's a URI string
        return this.downloadFromUri(uriOrArtifact as string);
      },

      fromUri: (uri: string): ArtifactObject => {
        return this.createArtifactObject({
          name: uri.split('/').pop()?.split('?')[0] || 'artifact',
          file: { uri }
        });
      },
    };
  }

  /**
   * UI API.
   */
  get ui(): UIAPI {
    return {
      getTheme: (): Theme => {
        return this.currentTheme;
      },

      onThemeChange: (callback: (theme: Theme) => void): (() => void) => {
        this.themeCallbacks.add(callback);

        // Return unsubscribe function
        return () => {
          this.themeCallbacks.delete(callback);
        };
      },
    };
  }
}
