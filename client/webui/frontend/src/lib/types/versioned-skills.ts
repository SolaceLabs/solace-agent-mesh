/**
 * TypeScript types for the versioned skill system.
 *
 * These types support the new versioning pattern where:
 * - SkillGroup: Container for skill versions
 * - SkillVersion: Individual version of a skill
 */

// ============================================================================
// Enums
// ============================================================================

export type SkillType = "learned" | "authored";
export type SkillScope = "agent" | "user" | "shared" | "global";
export type SkillGroupRole = "owner" | "editor" | "viewer";

// ============================================================================
// Skill Step and Agent Chain
// ============================================================================

export interface SkillStep {
    stepNumber: number;
    description: string;
    toolName?: string;
    toolParameters?: Record<string, unknown>;
    agentName?: string;
}

export interface AgentChainNode {
    agentName: string;
    order: number;
    role?: string;
    toolsUsed: string[];
}

// ============================================================================
// Skill Version
// ============================================================================

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

// ============================================================================
// Skill Group
// ============================================================================

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
}

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

// ============================================================================
// API Request Types
// ============================================================================

export interface CreateSkillRequest {
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

export interface CreateVersionRequest {
    description: string;
    creationReason: string;
    markdownContent?: string;
    summary?: string;
    steps?: SkillStep[];
    agentChain?: AgentChainNode[];
    setAsProduction?: boolean;
}

export interface RollbackRequest {
    versionId: string;
}

export interface ShareSkillRequest {
    targetUserId: string;
    role?: SkillGroupRole;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface SkillGroupListResponse {
    skills: SkillGroupSummary[];
    total: number;
    page: number;
    pageSize: number;
}

// ============================================================================
// Filter Types
// ============================================================================

export interface SkillGroupFilters {
    query?: string;
    scope?: SkillScope;
    type?: SkillType;
    agentName?: string;
    includeArchived?: boolean;
    page?: number;
    pageSize?: number;
}

// ============================================================================
// Version History Types
// ============================================================================

export interface VersionHistoryItem {
    version: SkillVersion;
    isProduction: boolean;
    canRollback: boolean;
}

// ============================================================================
// Skill Health Types (for monitoring)
// ============================================================================

export interface SkillGroupHealth {
    groupId: string;
    groupName: string;
    successRate: number;
    usageCount: number;
    failureCount: number;
    needsAttention: boolean;
    attentionReason?: string;
    versionCount: number;
    lastVersionCreatedAt?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Convert API response to camelCase.
 */
export function mapSkillGroupFromApi(data: Record<string, unknown>): SkillGroup {
    return {
        id: data.id as string,
        name: data.name as string,
        description: data.description as string | undefined,
        category: data.category as string | undefined,
        type: data.type as SkillType,
        scope: data.scope as SkillScope,
        ownerAgentName: data.owner_agent_name as string | undefined,
        ownerUserId: data.owner_user_id as string | undefined,
        isArchived: data.is_archived as boolean,
        versionCount: data.version_count as number,
        successRate: data.success_rate as number | undefined,
        createdAt: data.created_at as string,
        updatedAt: data.updated_at as string,
        productionVersion: data.production_version ? mapSkillVersionFromApi(data.production_version as Record<string, unknown>) : undefined,
    };
}

export function mapSkillGroupSummaryFromApi(data: Record<string, unknown>): SkillGroupSummary {
    return {
        id: data.id as string,
        name: data.name as string,
        description: data.description as string | undefined,
        category: data.category as string | undefined,
        type: data.type as SkillType,
        scope: data.scope as SkillScope,
        ownerAgentName: data.owner_agent_name as string | undefined,
        isArchived: data.is_archived as boolean,
        versionCount: data.version_count as number,
        successRate: data.success_rate as number | undefined,
        productionVersionId: data.production_version_id as string | undefined,
    };
}

export function mapSkillVersionFromApi(data: Record<string, unknown>): SkillVersion {
    return {
        id: data.id as string,
        groupId: data.group_id as string,
        version: data.version as number,
        description: data.description as string,
        markdownContent: data.markdown_content as string | undefined,
        summary: data.summary as string | undefined,
        steps: ((data.steps as unknown[]) || []).map(mapSkillStepFromApi),
        agentChain: ((data.agent_chain as unknown[]) || []).map(mapAgentChainNodeFromApi),
        sourceTaskId: data.source_task_id as string | undefined,
        relatedTaskIds: (data.related_task_ids as string[]) || [],
        involvedAgents: (data.involved_agents as string[]) || [],
        complexityScore: data.complexity_score as number,
        createdByUserId: data.created_by_user_id as string | undefined,
        creationReason: data.creation_reason as string | undefined,
        createdAt: data.created_at as string,
    };
}

export function mapSkillStepFromApi(data: unknown): SkillStep {
    const step = data as Record<string, unknown>;
    return {
        stepNumber: step.step_number as number,
        description: step.description as string,
        toolName: step.tool_name as string | undefined,
        toolParameters: step.tool_parameters as Record<string, unknown> | undefined,
        agentName: step.agent_name as string | undefined,
    };
}

export function mapAgentChainNodeFromApi(data: unknown): AgentChainNode {
    const node = data as Record<string, unknown>;
    return {
        agentName: node.agent_name as string,
        order: node.order as number,
        role: node.role as string | undefined,
        toolsUsed: (node.tools_used as string[]) || [],
    };
}

/**
 * Convert request to snake_case for API.
 */
export function mapCreateSkillRequestToApi(request: CreateSkillRequest): Record<string, unknown> {
    return {
        name: request.name,
        description: request.description,
        scope: request.scope,
        category: request.category,
        owner_agent: request.ownerAgent,
        markdown_content: request.markdownContent,
        summary: request.summary,
        steps: request.steps?.map(mapSkillStepToApi),
        agent_chain: request.agentChain?.map(mapAgentChainNodeToApi),
    };
}

export function mapCreateVersionRequestToApi(request: CreateVersionRequest): Record<string, unknown> {
    return {
        description: request.description,
        creation_reason: request.creationReason,
        markdown_content: request.markdownContent,
        summary: request.summary,
        steps: request.steps?.map(mapSkillStepToApi),
        agent_chain: request.agentChain?.map(mapAgentChainNodeToApi),
        set_as_production: request.setAsProduction ?? true,
    };
}

export function mapSkillStepToApi(step: SkillStep): Record<string, unknown> {
    return {
        step_number: step.stepNumber,
        description: step.description,
        tool_name: step.toolName,
        tool_parameters: step.toolParameters,
        agent_name: step.agentName,
    };
}

export function mapAgentChainNodeToApi(node: AgentChainNode): Record<string, unknown> {
    return {
        agent_name: node.agentName,
        order: node.order,
        role: node.role,
        tools_used: node.toolsUsed,
    };
}
