/**
 * TypeScript types for Prompt Library feature
 */

export interface Prompt {
    id: string;
    prompt_text: string;
    group_id: string;
    user_id: string;
    version: number;
    created_at: number;  // epoch milliseconds
    updated_at: number;  // epoch milliseconds
}

export interface PromptGroup {
    id: string;
    name: string;
    description?: string;
    category?: string;
    command?: string;
    user_id: string;
    author_name?: string;
    production_prompt_id?: string;
    is_shared: boolean;
    is_pinned: boolean;
    created_at: number;  // epoch milliseconds
    updated_at: number;  // epoch milliseconds
    production_prompt?: Prompt;
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
    prompt_text: string;
}

export interface PromptGroupListResponse {
    groups: PromptGroup[];
    total: number;
    skip: number;
    limit: number;
}

// AI-Assisted Builder Types
export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
}

export interface PromptBuilderChatRequest {
    message: string;
    conversation_history: ChatMessage[];
    current_template?: Record<string, unknown>;
}

export interface PromptBuilderChatResponse {
    message: string;
    template_updates: Record<string, unknown>;
    confidence: number;
    ready_to_save: boolean;
}