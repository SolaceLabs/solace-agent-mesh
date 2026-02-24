import { api } from "@/lib/api";
import type { Session } from "@/lib/types";

export interface PaginatedSessionsResponse {
    data: Session[];
    totalItems: number;
    totalPages: number;
    currentPage: number;
}

export const getRecentSessions = async (maxItems: number): Promise<Session[]> => {
    const result = await api.webui.get<PaginatedSessionsResponse>(`/api/v1/sessions?pageNumber=1&pageSize=${maxItems}`);
    return result.data || [];
};

export const getSession = async (sessionId: string): Promise<Session> => {
    const result = await api.webui.get<{ data: Session }>(`/api/v1/sessions/${sessionId}`);
    return result.data;
};
