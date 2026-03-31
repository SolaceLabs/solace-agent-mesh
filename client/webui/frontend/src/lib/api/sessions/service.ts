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

export const getRecentSessions = async (maxItems: number): Promise<Session[]> => {
    const result = await api.webui.get<PaginatedSessionsResponse>(`/api/v1/sessions?pageNumber=1&pageSize=${maxItems}`);
    return result.data || [];
};

export const getPaginatedSessions = async (pageNumber: number = 1, pageSize: number = 20): Promise<PaginatedSessionsResponse> => {
    return api.webui.get(`/api/v1/sessions?pageNumber=${pageNumber}&pageSize=${pageSize}`);
};
