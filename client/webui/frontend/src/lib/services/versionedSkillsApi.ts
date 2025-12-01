/**
 * API service for the versioned skill system.
 *
 * Provides methods for:
 * - Listing and searching skill groups
 * - Getting skill group details with versions
 * - Creating new skills (group + initial version)
 * - Creating new versions
 * - Rollback to previous versions
 * - Managing skill sharing
 */

import type { SkillGroup, SkillGroupSummary, SkillVersion, SkillGroupListResponse, SkillGroupFilters, CreateSkillRequest, CreateVersionRequest, RollbackRequest, ShareSkillRequest, SkillGroupHealth } from "../types/versioned-skills";

import { mapSkillGroupFromApi, mapSkillGroupSummaryFromApi, mapSkillVersionFromApi, mapCreateSkillRequestToApi, mapCreateVersionRequestToApi } from "../types/versioned-skills";

const API_BASE = "/api/v1/skills";

/**
 * Fetch wrapper with error handling.
 */
async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options?.headers,
        },
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
        return {} as T;
    }

    return response.json();
}

// ============================================================================
// Skill Group Operations
// ============================================================================

/**
 * List skill groups with optional filters.
 */
export async function listSkillGroups(filters?: SkillGroupFilters): Promise<SkillGroupListResponse> {
    const params = new URLSearchParams();

    if (filters?.query) params.append("query", filters.query);
    if (filters?.scope) params.append("scope", filters.scope);
    if (filters?.type) params.append("type", filters.type);
    if (filters?.agentName) params.append("agent", filters.agentName);
    if (filters?.includeArchived) params.append("include_archived", "true");
    if (filters?.page) params.append("page", filters.page.toString());
    if (filters?.pageSize) params.append("page_size", filters.pageSize.toString());

    const queryString = params.toString();
    const url = queryString ? `${API_BASE}?${queryString}` : API_BASE;

    const response = await fetchApi<Record<string, unknown>>(url);

    return {
        skills: ((response.skills as unknown[]) || []).map(s => mapSkillGroupSummaryFromApi(s as Record<string, unknown>)),
        total: response.total as number,
        page: response.page as number,
        pageSize: response.page_size as number,
    };
}

/**
 * Alias for listSkillGroups for backward compatibility.
 */
export async function listSkills(filters?: SkillGroupFilters): Promise<SkillGroupListResponse> {
    return listSkillGroups(filters);
}

/**
 * Get a skill group by ID.
 */
export async function getSkillGroup(groupId: string, includeVersions: boolean = false): Promise<SkillGroup> {
    const params = new URLSearchParams();
    if (includeVersions) params.append("include_versions", "true");

    const queryString = params.toString();
    const url = queryString ? `${API_BASE}/${groupId}?${queryString}` : `${API_BASE}/${groupId}`;

    const response = await fetchApi<Record<string, unknown>>(url);
    return mapSkillGroupFromApi(response);
}

/**
 * Create a new skill (group + initial version).
 */
export async function createSkillGroup(request: CreateSkillRequest): Promise<SkillGroup> {
    const response = await fetchApi<Record<string, unknown>>(API_BASE, {
        method: "POST",
        body: JSON.stringify(mapCreateSkillRequestToApi(request)),
    });
    return mapSkillGroupFromApi(response);
}

/**
 * Delete a skill group (and all its versions).
 */
export async function deleteSkillGroup(groupId: string): Promise<void> {
    await fetchApi<void>(`${API_BASE}/${groupId}`, {
        method: "DELETE",
    });
}

/**
 * Archive a skill group (soft delete).
 */
export async function archiveSkillGroup(groupId: string): Promise<SkillGroup> {
    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/${groupId}/archive`, {
        method: "POST",
    });
    return mapSkillGroupFromApi(response);
}

// ============================================================================
// Version Operations
// ============================================================================

/**
 * List all versions of a skill group.
 */
export async function listVersions(groupId: string): Promise<SkillVersion[]> {
    const response = await fetchApi<unknown[]>(`${API_BASE}/${groupId}/versions`);
    return response.map(v => mapSkillVersionFromApi(v as Record<string, unknown>));
}

/**
 * Get a specific version of a skill.
 */
export async function getVersion(groupId: string, versionId: string): Promise<SkillVersion> {
    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/${groupId}/versions/${versionId}`);
    return mapSkillVersionFromApi(response);
}

/**
 * Create a new version of a skill.
 */
export async function createVersion(groupId: string, request: CreateVersionRequest): Promise<SkillVersion> {
    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/${groupId}/versions`, {
        method: "POST",
        body: JSON.stringify(mapCreateVersionRequestToApi(request)),
    });
    return mapSkillVersionFromApi(response);
}

/**
 * Rollback a skill to a previous version.
 */
export async function rollbackToVersion(groupId: string, request: RollbackRequest): Promise<SkillGroup> {
    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/${groupId}/rollback`, {
        method: "POST",
        body: JSON.stringify({ version_id: request.versionId }),
    });
    return mapSkillGroupFromApi(response);
}

// ============================================================================
// Sharing Operations
// ============================================================================

/**
 * Share a skill with another user.
 */
export async function shareSkillGroup(groupId: string, request: ShareSkillRequest): Promise<void> {
    await fetchApi<{ message: string }>(`${API_BASE}/${groupId}/share`, {
        method: "POST",
        body: JSON.stringify({
            target_user_id: request.targetUserId,
            role: request.role || "viewer",
        }),
    });
}

/**
 * Remove a user's access to a skill.
 */
export async function unshareSkillGroup(groupId: string, targetUserId: string): Promise<void> {
    await fetchApi<void>(`${API_BASE}/${groupId}/share/${targetUserId}`, {
        method: "DELETE",
    });
}

// ============================================================================
// Agent-specific Operations
// ============================================================================

/**
 * Get skills available to a specific agent.
 */
export async function getSkillsForAgent(agentName: string, includeGlobal: boolean = true, pageSize: number = 50): Promise<SkillGroupSummary[]> {
    const params = new URLSearchParams();
    params.append("include_global", includeGlobal.toString());
    params.append("page_size", pageSize.toString());

    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/agent/${agentName}?${params.toString()}`);

    return ((response.skills as unknown[]) || []).map(s => mapSkillGroupSummaryFromApi(s as Record<string, unknown>));
}

// ============================================================================
// Search Operations
// ============================================================================

/**
 * Search for skill groups.
 */
export async function searchSkillGroups(query: string, agentName?: string, limit: number = 20): Promise<SkillGroupSummary[]> {
    const params = new URLSearchParams();
    params.append("query", query);
    if (agentName) params.append("agent", agentName);
    params.append("page_size", limit.toString());

    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}?${params.toString()}`);

    return ((response.skills as unknown[]) || []).map(s => mapSkillGroupSummaryFromApi(s as Record<string, unknown>));
}

/**
 * Semantic search for skill groups using embeddings.
 */
export async function semanticSearchSkillGroups(query: string, agentName?: string, limit: number = 10): Promise<SkillGroupSummary[]> {
    const params = new URLSearchParams();
    params.append("query", query);
    if (agentName) params.append("agent", agentName);
    params.append("limit", limit.toString());

    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/search/semantic?${params.toString()}`);

    return ((response.skills as unknown[]) || []).map(s => mapSkillGroupSummaryFromApi(s as Record<string, unknown>));
}

// ============================================================================
// Health/Monitoring Operations
// ============================================================================

/**
 * Get health metrics for a skill group.
 */
export async function getSkillGroupHealth(groupId: string): Promise<SkillGroupHealth> {
    const group = await getSkillGroup(groupId);

    return {
        groupId: group.id,
        groupName: group.name,
        successRate: group.successRate || 0,
        usageCount: 0, // Would need to be calculated from usage data
        failureCount: 0, // Would need to be calculated from usage data
        needsAttention: (group.successRate || 0) < 0.7,
        attentionReason: (group.successRate || 0) < 0.7 ? "Low success rate" : undefined,
        versionCount: group.versionCount,
        lastVersionCreatedAt: group.productionVersion?.createdAt,
    };
}

/**
 * Get skill groups that need attention.
 */
export async function getSkillGroupsNeedingAttention(limit: number = 10): Promise<SkillGroupHealth[]> {
    const response = await listSkillGroups({ pageSize: 100 });

    const healthMetrics: SkillGroupHealth[] = response.skills.map(skill => ({
        groupId: skill.id,
        groupName: skill.name,
        successRate: skill.successRate || 0,
        usageCount: 0,
        failureCount: 0,
        needsAttention: (skill.successRate || 0) < 0.7,
        attentionReason: (skill.successRate || 0) < 0.7 ? "Low success rate" : undefined,
        versionCount: skill.versionCount,
    }));

    return healthMetrics.filter(h => h.needsAttention).slice(0, limit);
}

// ============================================================================
// Export Operations
// ============================================================================

/**
 * Export a skill group to a file.
 */
export async function exportSkillGroup(groupId: string, format: "zip" | "json" | "markdown" = "markdown"): Promise<Blob> {
    const response = await fetch(`${API_BASE}/${groupId}/export?format=${format}`, {
        headers: {
            "Content-Type": "application/json",
        },
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.blob();
}

/**
 * Alias for exportSkillGroup for backward compatibility.
 */
export async function exportSkill(groupId: string, format: "zip" | "json" | "markdown" = "markdown"): Promise<Blob> {
    return exportSkillGroup(groupId, format);
}
