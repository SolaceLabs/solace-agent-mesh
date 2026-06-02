import { api } from "@/lib/api";
import type { Session } from "@/lib/types";

export interface PaginatedSessionsResponse {
    data: Session[];
    meta: {
        pagination: {
            pageNumber: number;
            count: number;
            pageSize: number;
            nextPage: number | null;
            totalPages: number;
        };
    };
}

export const getRecentSessions = async (maxItems: number, agentId?: string): Promise<Session[]> => {
    let url = `/api/v1/sessions?pageNumber=1&pageSize=${maxItems}`;
    if (agentId) url += `&agent_id=${encodeURIComponent(agentId)}`;
    const result = await api.webui.get<PaginatedSessionsResponse>(url);
    return result.data || [];
};

export const getPaginatedSessions = async (pageNumber: number = 1, pageSize: number = 20, source?: string, agentId?: string): Promise<PaginatedSessionsResponse> => {
    let url = `/api/v1/sessions?pageNumber=${pageNumber}&pageSize=${pageSize}`;
    if (source) url += `&source=${source}`;
    if (agentId) url += `&agent_id=${encodeURIComponent(agentId)}`;
    return api.webui.get(url);
};

export const getSessionChatTasks = async (sessionId: string) => {
    return api.webui.get(`/api/v1/sessions/${sessionId}/chat-tasks`);
};

export const markSessionViewed = async (sessionId: string): Promise<{ lastViewedAt: number }> => {
    return api.webui.post(`/api/v1/sessions/${sessionId}/viewed`, {});
};
