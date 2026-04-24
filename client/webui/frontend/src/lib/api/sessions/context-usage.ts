/**
 * API client for session context usage and manual compaction.
 */

import { api } from "@/lib/api";
import type { ContextUsage, CompactSessionRequest, CompactSessionResponse } from "@/lib/types";

/**
 * Get context window usage for a session.
 */
export async function getSessionContextUsage(sessionId: string, model?: string, agentName?: string): Promise<ContextUsage> {
    const params = new URLSearchParams();
    if (model) params.append("model", model);
    if (agentName) params.append("agent_name", agentName);
    const query = params.toString() ? `?${params}` : "";
    return api.webui.get<ContextUsage>(`/api/v1/sessions/${sessionId}/context-usage${query}`);
}

/**
 * Manually compact a session's conversation history using progressive summarization.
 */
export async function compactSession(sessionId: string, request?: CompactSessionRequest): Promise<CompactSessionResponse> {
    return api.webui.post<CompactSessionResponse>(`/api/v1/sessions/${sessionId}/compact`, request ?? {});
}
