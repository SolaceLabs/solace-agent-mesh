/**
 * API service for the SAM Skill Learning System.
 */

import type { SkillSummary, SkillDetail, CreateSkillRequest, UpdateSkillRequest, SearchSkillsRequest, SearchSkillsResponse, FeedbackRequest, ShareSkillRequest, SkillHealth, SkillFilters } from "../types/skills";

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

/**
 * List skills with optional filters.
 */
export async function listSkills(filters?: SkillFilters): Promise<SkillSummary[]> {
    const params = new URLSearchParams();

    if (filters?.agentName) params.append("agent", filters.agentName);
    if (filters?.userId) params.append("user_id", filters.userId);
    if (filters?.skillType) params.append("type", filters.skillType);
    if (filters?.scope) params.append("scope", filters.scope);
    if (filters?.limit) params.append("page_size", filters.limit.toString());
    if (filters?.offset) {
        const page = Math.floor((filters.offset || 0) / (filters.limit || 20)) + 1;
        params.append("page", page.toString());
    }

    const queryString = params.toString();
    const url = queryString ? `${API_BASE}?${queryString}` : API_BASE;

    const response = await fetchApi<SearchSkillsResponse>(url);
    return response.skills;
}

/**
 * Get a skill by ID.
 */
export async function getSkill(skillId: string): Promise<SkillDetail> {
    return fetchApi<SkillDetail>(`${API_BASE}/${skillId}`);
}

/**
 * Create a new skill.
 */
export async function createSkill(request: CreateSkillRequest): Promise<SkillDetail> {
    return fetchApi<SkillDetail>(API_BASE, {
        method: "POST",
        body: JSON.stringify(request),
    });
}

/**
 * Update an existing skill.
 */
export async function updateSkill(skillId: string, request: UpdateSkillRequest): Promise<SkillDetail> {
    return fetchApi<SkillDetail>(`${API_BASE}/${skillId}`, {
        method: "PUT",
        body: JSON.stringify(request),
    });
}

/**
 * Delete a skill.
 */
export async function deleteSkill(skillId: string): Promise<void> {
    await fetchApi<void>(`${API_BASE}/${skillId}`, {
        method: "DELETE",
    });
}

/**
 * Search for skills.
 */
export async function searchSkills(request: SearchSkillsRequest): Promise<SearchSkillsResponse> {
    const params = new URLSearchParams();
    params.append("query", request.query);
    if (request.agentName) params.append("agent", request.agentName);
    if (request.scope) params.append("scope", request.scope);
    if (request.limit) params.append("page_size", request.limit.toString());

    // Use semantic search endpoint if requested
    if (request.useSemantic) {
        return fetchApi<SearchSkillsResponse>(`${API_BASE}/search/semantic?${params.toString()}`);
    }

    return fetchApi<SearchSkillsResponse>(`${API_BASE}?${params.toString()}`);
}

/**
 * Get skills available to an agent.
 */
export async function getSkillsForAgent(agentName: string, userId?: string, includeGlobal: boolean = true, limit: number = 50): Promise<SkillSummary[]> {
    const params = new URLSearchParams();
    if (userId) params.append("user_id", userId);
    params.append("include_global", includeGlobal.toString());
    params.append("page_size", limit.toString());

    const response = await fetchApi<SearchSkillsResponse>(`${API_BASE}/agent/${agentName}?${params.toString()}`);
    return response.skills;
}

/**
 * Submit feedback for a skill.
 */
export async function submitFeedback(request: FeedbackRequest): Promise<void> {
    await fetchApi<{ id: string }>(`${API_BASE}/${request.skillId}/feedback`, {
        method: "POST",
        body: JSON.stringify({
            feedback_type: request.feedbackType,
            comment: request.comment,
            correction_data: request.correctionData,
            task_id: request.taskId,
        }),
    });
}

/**
 * Share a skill with another user.
 */
export async function shareSkill(request: ShareSkillRequest): Promise<void> {
    await fetchApi<{ message: string }>(`${API_BASE}/${request.skillId}/share`, {
        method: "POST",
        body: JSON.stringify({
            target_user_id: request.targetUserId,
            target_agent: request.targetAgent,
            permission: request.permission,
        }),
    });
}

/**
 * Get health metrics for a skill.
 * Note: This endpoint may not be implemented yet.
 */
export async function getSkillHealth(skillId: string): Promise<SkillHealth> {
    const skill = await getSkill(skillId);

    // Calculate health from skill data
    const successRate = skill.successCount + skill.failureCount > 0 ? skill.successCount / (skill.successCount + skill.failureCount) : 0;

    return {
        skillId: skill.id,
        skillName: skill.name,
        successRate: successRate,
        usageCount: skill.usageCount,
        failureCount: skill.failureCount,
        needsAttention: successRate < 0.7 && skill.usageCount > 5,
        attentionReason: successRate < 0.7 ? "Low success rate" : undefined,
    };
}

/**
 * Get skills that need attention.
 * Note: This is a client-side implementation.
 */
export async function getSkillsNeedingAttention(limit: number = 10): Promise<SkillHealth[]> {
    const skills = await listSkills({ limit: 100 });

    const healthMetrics: SkillHealth[] = skills.map(skill => {
        const successRate = skill.successRate || 0;
        return {
            skillId: skill.id,
            skillName: skill.name,
            successRate: successRate,
            usageCount: skill.usageCount,
            failureCount: 0, // Not available in summary
            needsAttention: successRate < 0.7 && skill.usageCount > 5,
            attentionReason: successRate < 0.7 ? "Low success rate" : undefined,
        };
    });

    return healthMetrics.filter(h => h.needsAttention).slice(0, limit);
}

/**
 * Sync static skill files to the database.
 * Note: This endpoint may need to be implemented on the backend.
 */
export async function syncStaticSkills(): Promise<{ count: number }> {
    // This would call a backend endpoint to sync static skills
    // For now, return a placeholder
    console.warn("syncStaticSkills: Backend endpoint not yet implemented");
    return { count: 0 };
}

/**
 * Export a skill to a file.
 * Returns a download URL or triggers a download.
 */
export async function exportSkillToFile(skillId: string, format: "zip" | "json" | "markdown" = "markdown"): Promise<Blob> {
    const response = await fetch(`${API_BASE}/${skillId}/export?format=${format}`, {
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
 * Regenerate embeddings for skills.
 * TODO: This endpoint is not yet implemented on the backend.
 */
export async function regenerateEmbeddings(skillIds?: string[]): Promise<{ count: number }> {
    // TODO: Implement backend endpoint POST /api/v1/skills/embeddings/regenerate
    console.warn("regenerateEmbeddings: Backend endpoint not yet implemented", { skillIds });
    return { count: 0 };
}
