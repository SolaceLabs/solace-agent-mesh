/**
 * TypeScript types for the SAM Skill Learning System.
 */

/**
 * Skill type - learned from tasks or authored manually
 */
export type SkillType = "learned" | "authored";

/**
 * Skill scope - visibility and access level
 */
export type SkillScope = "user" | "shared" | "global" | "agent";

/**
 * A step in a skill procedure
 */
export interface SkillStep {
    stepNumber: number;
    description: string;
    toolName?: string;
    toolParameters?: Record<string, unknown>;
    expectedOutput?: string;
    agentName?: string;
    // Legacy aliases for backward compatibility
    action?: string;
    agent?: string;
    tool?: string;
}

/**
 * A node in the agent chain
 */
export interface AgentChainNode {
    agentName: string;
    order: number;
    role?: string;
    toolsUsed: string[];
}

/**
 * Skill summary for listing
 */
export interface SkillSummary {
    id: string;
    name: string;
    description: string;
    type: SkillType;
    scope: SkillScope;
    ownerAgent?: string;
    tags: string[];
    successRate?: number;
    usageCount: number;
    isActive: boolean;
}

/**
 * Full skill details
 */
export interface Skill {
    id: string;
    name: string;
    description: string;
    type: SkillType;
    scope: SkillScope;
    ownerUserId?: string;
    ownerAgent?: string;
    tags: string[];
    steps: SkillStep[];
    agentChain: AgentChainNode[];
    preconditions: string[];
    postconditions: string[];
    successCount: number;
    failureCount: number;
    usageCount: number;
    successRate?: number;
    isActive: boolean;
    createdAt: string;
    updatedAt: string;
    metadata?: Record<string, unknown>;
    // Additional fields for display
    summary?: string;
    markdownContent?: string;
    involvedAgents?: string[];
    userCorrections?: number;
}

// Alias for backward compatibility
export type SkillDetail = Skill;

/**
 * Search results response
 */
export interface SkillSearchResponse {
    skills: SkillSummary[];
    total: number;
    page: number;
    pageSize: number;
    // Alias for backward compatibility
    results?: SkillSummary[];
}

// Alias for backward compatibility
export type SearchSkillsResponse = SkillSearchResponse;

/**
 * Request to create a new skill
 */
export interface SkillCreateRequest {
    name: string;
    description: string;
    scope?: SkillScope;
    ownerAgent?: string;
    tags?: string[];
    steps?: SkillStep[];
    agentChain?: AgentChainNode[];
    preconditions?: string[];
    postconditions?: string[];
    metadata?: Record<string, unknown>;
}

// Alias for backward compatibility
export type CreateSkillRequest = SkillCreateRequest;

/**
 * Request to update a skill
 */
export interface SkillUpdateRequest {
    name?: string;
    description?: string;
    scope?: SkillScope;
    tags?: string[];
    steps?: SkillStep[];
    agentChain?: AgentChainNode[];
    preconditions?: string[];
    postconditions?: string[];
    metadata?: Record<string, unknown>;
    isActive?: boolean;
}

// Alias for backward compatibility
export type UpdateSkillRequest = SkillUpdateRequest;

/**
 * Request to share a skill
 */
export interface SkillShareRequest {
    skillId: string;
    targetUserId?: string;
    targetAgent?: string;
    permission?: "read" | "write";
}

// Alias for backward compatibility
export type ShareSkillRequest = SkillShareRequest;

/**
 * Feedback type
 */
export type FeedbackType = "thumbs_up" | "thumbs_down" | "correction" | "comment";

/**
 * Request to submit feedback on a skill
 */
export interface SkillFeedbackRequest {
    skillId: string;
    feedbackType: FeedbackType;
    comment?: string;
    correctionData?: Record<string, unknown>;
    taskId?: string;
}

// Alias for backward compatibility
export type FeedbackRequest = SkillFeedbackRequest;

/**
 * Feedback submission response
 */
export interface SkillFeedbackResponse {
    id: string;
    skillId: string;
    feedbackType: FeedbackType;
    createdAt: string;
}

/**
 * Skill search parameters
 */
export interface SkillSearchParams {
    query?: string;
    scope?: SkillScope;
    agent?: string;
    tags?: string[];
    type?: SkillType;
    page?: number;
    pageSize?: number;
}

/**
 * Search skills request
 */
export interface SearchSkillsRequest {
    query: string;
    agentName?: string;
    userId?: string;
    scope?: SkillScope;
    tags?: string[];
    limit?: number;
    offset?: number;
    useSemantic?: boolean;
}

/**
 * Skill filters for listing
 */
export interface SkillFilters {
    agentName?: string;
    userId?: string;
    skillType?: SkillType;
    scope?: SkillScope;
    limit?: number;
    offset?: number;
}

/**
 * Skill health metrics
 */
export interface SkillHealth {
    skillId: string;
    skillName: string;
    successRate: number;
    usageCount: number;
    failureCount: number;
    lastUsed?: string;
    needsAttention: boolean;
    attentionReason?: string;
}
