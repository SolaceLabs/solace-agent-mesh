/**
 * SAM SDK Client implementation.
 */

import type {
  AgentCallOptions,
  AgentCallResult,
  AgentsAPI,
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
  private async sendRequest<T = any>(type: MessageType, payload: any, options?: any): Promise<T> {
    const id = this.sendMessage(type, payload);

    return new Promise((resolve, reject) => {
      this.pendingMessages.set(id, { resolve, reject, options });

      // Timeout after 30 seconds
      setTimeout(() => {
        if (this.pendingMessages.has(id)) {
          this.pendingMessages.delete(id);
          reject(new Error('Request timed out'));
        }
      }, 30000);
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
        pending.options?.onArtifact?.(message.payload);
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
        // Don't send callbacks over postMessage
        const { onText, onStatus, onArtifact, ...payloadOptions } = options;
        return this.sendRequest(MessageType.AGENT_CALL, { agentName, ...payloadOptions }, options);
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
   * Artifacts API.
   */
  get artifacts(): ArtifactsAPI {
    return {
      upload: async (file: File): Promise<string> => {
        await this.ready();
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
        });
        return response.artifactId;
      },

      download: async (artifactId: string): Promise<Blob> => {
        await this.ready();
        const response = await this.sendRequest(MessageType.ARTIFACT_DOWNLOAD, { artifactId });

        // Convert base64 back to Blob
        const base64Response = await fetch(response.data);
        return base64Response.blob();
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
