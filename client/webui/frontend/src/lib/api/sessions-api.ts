/**
 * Sessions API Client
 * Handles session-related API calls including compression
 */

import { authenticatedFetch } from "../utils/api";

export interface CompressAndBranchRequest {
    agentId?: string;
    name?: string;
    llmProvider?: string;
    llmModel?: string;
}

export interface CompressAndBranchResponse {
    newSessionId: string;
    parentSessionId: string;
    summaryTaskId: string;
    compressedMessageCount: number;
    sessionName: string;
    createdTime: number;
}

/**
 * Compress a session's conversation history and create a new session with the summary
 * @param sessionId - The session ID to compress
 * @param request - Optional compression parameters
 * @returns Promise with the new session details
 */
export async function compressAndBranchSession(sessionId: string, request: CompressAndBranchRequest = {}): Promise<CompressAndBranchResponse> {
    const response = await authenticatedFetch(`/api/v1/sessions/${sessionId}/compress-and-branch`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        credentials: "include",
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Failed to compress session: ${error}`);
    }

    return response.json();
}
