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

/** Normalize snake_case fields from the backend to camelCase to match the Session type. */
function normalizeSession(raw: Record<string, unknown>): Session {
    return {
        ...raw,
        agentId: (raw.agentId ?? raw.agent_id ?? null) as Session["agentId"],
        projectId: (raw.projectId ?? raw.project_id ?? null) as Session["projectId"],
        projectName: (raw.projectName ?? raw.project_name ?? null) as Session["projectName"],
        createdTime: (raw.createdTime ?? raw.created_time ?? "") as string,
        updatedTime: (raw.updatedTime ?? raw.updated_time ?? "") as string,
        userId: (raw.userId ?? raw.user_id) as Session["userId"],
        hasRunningBackgroundTask: (raw.hasRunningBackgroundTask ?? raw.has_running_background_task) as Session["hasRunningBackgroundTask"],
        ownerDisplayName: (raw.ownerDisplayName ?? raw.owner_display_name ?? null) as Session["ownerDisplayName"],
        ownerEmail: (raw.ownerEmail ?? raw.owner_email ?? null) as Session["ownerEmail"],
    } as Session;
}

export const getRecentSessions = async (maxItems: number): Promise<Session[]> => {
    const result = await api.webui.get<PaginatedSessionsResponse>(`/api/v1/sessions?pageNumber=1&pageSize=${maxItems}`);
    return (result.data || []).map(s => normalizeSession(s as unknown as Record<string, unknown>));
};

export const getPaginatedSessions = async (pageNumber: number = 1, pageSize: number = 20, source?: string): Promise<PaginatedSessionsResponse> => {
    let url = `/api/v1/sessions?pageNumber=${pageNumber}&pageSize=${pageSize}`;
    if (source) url += `&source=${source}`;
    const result = await api.webui.get<PaginatedSessionsResponse>(url);
    return { ...result, data: (result.data || []).map(s => normalizeSession(s as unknown as Record<string, unknown>)) };
};

export const getSessionChatTasks = async (sessionId: string) => {
    return api.webui.get(`/api/v1/sessions/${sessionId}/chat-tasks`);
};
