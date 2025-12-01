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

/**
 * Versioned Skills Types
 * These types support the skill versioning system (skill_groups/skill_versions)
 */

/**
 * Role for skill group access
 */
export type SkillGroupRole = "owner" | "editor" | "viewer";

/**
 * Individual version of a skill
 */
export interface SkillVersion {
    id: string;
    groupId: string;
    version: number;
    description: string;
    markdownContent?: string;
    summary?: string;
    steps: SkillStep[];
    agentChain: AgentChainNode[];
    sourceTaskId?: string;
    relatedTaskIds: string[];
    involvedAgents: string[];
    complexityScore: number;
    createdByUserId?: string;
    creationReason?: string;
    createdAt: string;
}

/**
 * Skill group summary for listing
 */
export interface SkillGroupSummary {
    id: string;
    name: string;
    description?: string;
    category?: string;
    type: SkillType;
    scope: SkillScope;
    ownerAgentName?: string;
    isArchived: boolean;
    versionCount: number;
    successRate?: number;
    productionVersionId?: string;
}

/**
 * Skill group (container for versions)
 */
export interface SkillGroup {
    id: string;
    name: string;
    description?: string;
    category?: string;
    type: SkillType;
    scope: SkillScope;
    ownerAgentName?: string;
    ownerUserId?: string;
    isArchived: boolean;
    versionCount: number;
    successRate?: number;
    createdAt: string;
    updatedAt: string;
    productionVersion?: SkillVersion;
    productionVersionId?: string;
}

/**
 * Skill group list response
 */
export interface SkillGroupListResponse {
    skills: SkillGroup[];
    total: number;
    page: number;
    pageSize: number;
}

/**
 * Request to create a new skill (with versioning)
 */
export interface CreateSkillGroupRequest {
    name: string;
    description: string;
    scope?: SkillScope;
    category?: string;
    ownerAgent?: string;
    markdownContent?: string;
    summary?: string;
    steps?: SkillStep[];
    agentChain?: AgentChainNode[];
}

/**
 * Request to create a new version
 */
export interface CreateVersionRequest {
    description: string;
    creationReason: string;
    markdownContent?: string;
    summary?: string;
    steps?: SkillStep[];
    agentChain?: AgentChainNode[];
    setAsProduction?: boolean;
}

/**
 * Request to rollback to a version
 */
export interface RollbackRequest {
    versionId: string;
}

/**
 * Request to share a skill group
 */
export interface ShareSkillGroupRequest {
    targetUserId: string;
    role?: SkillGroupRole;
}
