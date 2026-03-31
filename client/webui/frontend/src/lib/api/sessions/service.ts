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

export interface TransferContextRequest {
    sourceAgentName: string;
    targetAgentName: string;
}

export interface TransferContextResponse {
    contextTransferred: boolean;
    message: string;
}

export const transferContext = async (sessionId: string, request: TransferContextRequest): Promise<TransferContextResponse> => {
    const raw = await api.webui.post<{ context_transferred: boolean; message: string }>(`/api/v1/sessions/${sessionId}/transfer-context`, {
        source_agent_name: request.sourceAgentName,
        target_agent_name: request.targetAgentName,
    });
    return {
        contextTransferred: raw.context_transferred,
        message: raw.message,
    };
};
