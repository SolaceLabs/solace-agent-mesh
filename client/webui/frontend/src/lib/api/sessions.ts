import { api } from "./client";

export interface BulkDeleteOptions {
    sessionIds?: string[];
    deleteAll?: boolean;
    startDate?: number;
    endDate?: number;
}

export interface BulkDeleteResult {
    deletedCount: number;
    failedCount: number;
    totalRequested: number;
}

/**
 * Bulk delete sessions based on various criteria
 */
export async function bulkDeleteSessions(options: BulkDeleteOptions): Promise<BulkDeleteResult> {
    return api.webui.post<BulkDeleteResult>("/api/v1/sessions/bulk-delete", {
        session_ids: options.sessionIds,
        delete_all: options.deleteAll,
        start_date: options.startDate,
        end_date: options.endDate,
    });
}

/**
 * Delete all sessions for the current user
 */
export async function deleteAllSessions(): Promise<BulkDeleteResult> {
    return bulkDeleteSessions({ deleteAll: true });
}
