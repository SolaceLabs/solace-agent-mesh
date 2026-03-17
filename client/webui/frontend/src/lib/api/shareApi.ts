/**
 * API client for chat sharing operations
 */

import { api } from "./client";
import type {
    ShareLink,
    CreateShareLinkRequest,
    UpdateShareLinkRequest,
    SharedSessionView,
    ShareLinksListResponse,
    ShareUsersResponse,
    BatchAddShareUsersRequest,
    BatchAddShareUsersResponse,
    BatchDeleteShareUsersRequest,
    BatchDeleteShareUsersResponse,
    SharedWithMeItem,
    ForkSharedChatResponse,
} from "../types/share";

const SHARE_BASE = "/api/v1/share";

/**
 * Create a share link for a session
 */
export async function createShareLink(sessionId: string, options: CreateShareLinkRequest = {}): Promise<ShareLink> {
    return api.webui.post<ShareLink>(`${SHARE_BASE}/${sessionId}`, options);
}

/**
 * Get existing share link for a session
 */
export async function getShareLinkForSession(sessionId: string): Promise<ShareLink | null> {
    const response = await api.webui.get(`${SHARE_BASE}/link/${sessionId}`, { fullResponse: true });
    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to get share link" }));
        throw new Error(error.detail || "Failed to get share link");
    }
    return response.json();
}

/**
 * List all share links created by the user
 */
export async function listShareLinks(
    params: {
        page?: number;
        pageSize?: number;
        search?: string;
    } = {}
): Promise<ShareLinksListResponse> {
    const queryParams = new URLSearchParams();
    if (params.page != null) queryParams.append("page", params.page.toString());
    if (params.pageSize != null) queryParams.append("pageSize", params.pageSize.toString());
    if (params.search) queryParams.append("search", params.search);

    const qs = queryParams.toString();
    return api.webui.get<ShareLinksListResponse>(`${SHARE_BASE}${qs ? `?${qs}` : ""}`);
}

/**
 * View a shared session (sends credentials for auth-required shares)
 */
export async function viewSharedSession(shareId: string): Promise<SharedSessionView> {
    return api.webui.get<SharedSessionView>(`${SHARE_BASE}/${shareId}`, { credentials: "include" });
}

/**
 * Update share link settings
 */
export async function updateShareLink(shareId: string, options: UpdateShareLinkRequest): Promise<ShareLink> {
    return api.webui.patch<ShareLink>(`${SHARE_BASE}/${shareId}`, options);
}

/**
 * Delete a share link
 */
export async function deleteShareLink(shareId: string): Promise<void> {
    await api.webui.delete(`${SHARE_BASE}/${shareId}`);
}

/**
 * Get artifact content from a shared session
 * @param shareId - The share ID
 * @param filename - The artifact filename
 * @returns Promise with content (base64) and mimeType
 */
export async function getSharedArtifactContent(shareId: string, filename: string): Promise<{ content: string; mimeType: string }> {
    const encodedFilename = encodeURIComponent(filename);
    const response = await api.webui.get(`${SHARE_BASE}/${shareId}/artifacts/${encodedFilename}`, { fullResponse: true, credentials: "include" });

    if (!response.ok) {
        throw new Error(`Failed to fetch shared artifact content: ${response.statusText}`);
    }

    const contentType = response.headers.get("Content-Type") || "application/octet-stream";
    const mimeType = contentType.split(";")[0].trim();
    const blob = await response.blob();

    // Convert blob to base64
    const content = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result?.toString().split(",")[1] || "");
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });

    return { content, mimeType };
}

/**
 * Download a shared artifact as a blob (for direct download)
 */
export async function downloadSharedArtifact(shareId: string, filename: string): Promise<Blob> {
    const encodedFilename = encodeURIComponent(filename);
    const response = await api.webui.get(`${SHARE_BASE}/${shareId}/artifacts/${encodedFilename}`, { fullResponse: true, credentials: "include" });

    if (!response.ok) {
        throw new Error(`Failed to download: ${response.statusText}`);
    }

    return response.blob();
}

// Share User Management APIs

/**
 * Get users with access to a share link
 */
export async function getShareUsers(shareId: string): Promise<ShareUsersResponse> {
    return api.webui.get<ShareUsersResponse>(`${SHARE_BASE}/${shareId}/users`);
}

/**
 * Add users to a share link
 */
export async function addShareUsers(shareId: string, data: BatchAddShareUsersRequest): Promise<BatchAddShareUsersResponse> {
    return api.webui.post<BatchAddShareUsersResponse>(`${SHARE_BASE}/${shareId}/users`, data);
}

/**
 * Remove users from a share link
 */
export async function deleteShareUsers(shareId: string, data: BatchDeleteShareUsersRequest): Promise<BatchDeleteShareUsersResponse> {
    // ApiClient.delete() doesn't support a request body in its type signature,
    // but the backend DELETE endpoint requires one. Use the fullResponse overload
    // and pass body via a type assertion (the runtime accepts it fine).
    const opts = {
        fullResponse: true as const,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response: Response = await (api.webui.delete as any)(`${SHARE_BASE}/${shareId}/users`, opts);
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to delete share users" }));
        throw new Error(error.detail || "Failed to delete share users");
    }
    return response.json();
}

// Shared-with-me APIs

/**
 * List all chats shared with the current user
 */
export async function listSharedWithMe(): Promise<SharedWithMeItem[]> {
    return api.webui.get<SharedWithMeItem[]>(`${SHARE_BASE}/shared-with-me`);
}

/**
 * Update the snapshot timestamp for a share.
 * - Without userEmail: updates the current user's own snapshot (viewer use case).
 * - With userEmail: owner updates a specific user's snapshot.
 */
export async function updateShareSnapshot(shareId: string, userEmail?: string): Promise<{ snapshot_time: number }> {
    const body = userEmail ? { user_email: userEmail } : undefined;
    return api.webui.post<{ snapshot_time: number }>(`${SHARE_BASE}/${shareId}/update-snapshot`, body);
}

/**
 * Fork a shared chat into the user's own sessions
 */
export async function forkSharedChat(shareId: string): Promise<ForkSharedChatResponse> {
    return api.webui.post<ForkSharedChatResponse>(`${SHARE_BASE}/${shareId}/fork`);
}
