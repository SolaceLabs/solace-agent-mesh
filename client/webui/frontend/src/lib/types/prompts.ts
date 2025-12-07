/**
 * TypeScript types for Prompt Library feature
 */

export interface Prompt {
    id: string;
    promptText: string;
    groupId: string;
    userId: string;
    version: number;
    // Versioned metadata fields
    name?: string;
    description?: string;
    category?: string;
    command?: string;
    createdAt: number; // epoch milliseconds
    updatedAt: number; // epoch milliseconds
}

export interface PromptGroup {
    id: string;
    name: string;
    description?: string;
    category?: string;
    command?: string;
    userId: string;
    authorName?: string;
    productionPromptId?: string;
    isShared: boolean;
    isPinned: boolean;
    createdAt: number; // epoch milliseconds
    updatedAt: number; // epoch milliseconds
    productionPrompt?: Prompt;
    _editingPromptId?: string;
    _isEditingActiveVersion?: boolean;
    _selectedVersionId?: string;
}

export interface PromptGroupCreate {
    name: string;
    description?: string;
    category?: string;
    command?: string;
    initial_prompt: string;
}

export interface PromptGroupUpdate {
    name?: string;
    description?: string;
    category?: string;
    command?: string;
}

export interface PromptCreate {
    promptText: string;
}

export interface PromptGroupListResponse {
    groups: PromptGroup[];
    total: number;
    skip: number;
    limit: number;
}

// AI-Assisted Builder Types
export interface PromptChatMessage {
    role: "user" | "assistant";
    content: string;
}

export interface PromptBuilderChatRequest {
    message: string;
    conversation_history: PromptChatMessage[];
    current_template?: Record<string, unknown>;
}

export interface PromptBuilderChatResponse {
    message: string;
    template_updates: Record<string, unknown>;
    confidence: number;
    ready_to_save: boolean;
}

export interface TemplateConfig {
    name?: string;
    category?: string;
    command?: string;
    promptText?: string;
    description?: string;
    detected_variables?: string[];
}
