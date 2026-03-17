/**
 * API client for chat sharing operations
 */

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

const API_BASE = "/api/v1";

/**
 * Create a share link for a session
 */
export async function createShareLink(sessionId: string, options: CreateShareLinkRequest = {}): Promise<ShareLink> {
    const response = await fetch(`${API_BASE}/share/${sessionId}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(options),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to create share link" }));
        throw new Error(error.detail || "Failed to create share link");
    }

    // Backend returns ShareLinkResponse directly (not wrapped in { data: ... })
    const data: ShareLink = await response.json();
    return data;
}

/**
 * Get existing share link for a session
 */
export async function getShareLinkForSession(sessionId: string): Promise<ShareLink | null> {
    const response = await fetch(`${API_BASE}/share/link/${sessionId}`, {
        method: "GET",
        credentials: "include",
    });

    if (response.status === 404) {
        return null;
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to get share link" }));
        throw new Error(error.detail || "Failed to get share link");
    }

    // Backend returns ShareLinkResponse directly (not wrapped in { data: ... })
    const data: ShareLink = await response.json();
    return data;
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
    if (params.page) queryParams.append("page", params.page.toString());
    if (params.pageSize) queryParams.append("pageSize", params.pageSize.toString());
    if (params.search) queryParams.append("search", params.search);

    const response = await fetch(`${API_BASE}/share?${queryParams}`, {
        method: "GET",
        credentials: "include",
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to list share links" }));
        throw new Error(error.detail || "Failed to list share links");
    }

    return await response.json();
}

/**
 * View a shared session (public endpoint, no auth required for public shares)
 */
export async function viewSharedSession(shareId: string): Promise<SharedSessionView> {
    const response = await fetch(`${API_BASE}/share/${shareId}`, {
        method: "GET",
        credentials: "include", // Include credentials in case auth is required
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to view shared session" }));

        // Provide more specific error messages
        if (response.status === 401) {
            throw new Error("Authentication required to view this shared session");
        } else if (response.status === 403) {
            throw new Error(error.detail || "You do not have access to this shared session");
        } else if (response.status === 404) {
            throw new Error("Shared session not found");
        }

        throw new Error(error.detail || "Failed to view shared session");
    }

    // Backend returns SharedSessionView directly (not wrapped in { data: ... })
    const data: SharedSessionView = await response.json();
    return data;
}

/**
 * Update share link settings
 */
export async function updateShareLink(shareId: string, options: UpdateShareLinkRequest): Promise<ShareLink> {
    const response = await fetch(`${API_BASE}/share/${shareId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(options),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to update share link" }));
        throw new Error(error.detail || "Failed to update share link");
    }

    // Backend returns ShareLinkResponse directly (not wrapped in { data: ... })
    const data: ShareLink = await response.json();
    return data;
}

/**
 * Delete a share link
 */
export async function deleteShareLink(shareId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/share/${shareId}`, {
        method: "DELETE",
        credentials: "include",
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to delete share link" }));
        throw new Error(error.detail || "Failed to delete share link");
    }
}

/**
 * Get artifact content from a shared session
 * @param shareId - The share ID
 * @param filename - The artifact filename
 * @returns Promise with content (base64) and mimeType
 */
export async function getSharedArtifactContent(shareId: string, filename: string): Promise<{ content: string; mimeType: string }> {
    const encodedFilename = encodeURIComponent(filename);
    const response = await fetch(`${API_BASE}/share/${shareId}/artifacts/${encodedFilename}`, {
        method: "GET",
        credentials: "include",
    });

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
    const response = await fetch(`${API_BASE}/share/${shareId}/artifacts/${encodedFilename}`, {
        method: "GET",
        credentials: "include",
    });

    if (!response.ok) {
        throw new Error(`Failed to download: ${response.statusText}`);
    }

    return await response.blob();
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
    // Try the modern Clipboard API first
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch {
            // Fall through to legacy fallback
        }
    }

    // Legacy fallback for non-HTTPS contexts (e.g. local dev on HTTP)
    try {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        const success = document.execCommand("copy");
        document.body.removeChild(textarea);
        return success;
    } catch (err) {
        console.error("Failed to copy to clipboard:", err);
        return false;
    }
}

// Share User Management APIs

/**
 * Get users with access to a share link
 */
export async function getShareUsers(shareId: string): Promise<ShareUsersResponse> {
    const response = await fetch(`${API_BASE}/share/${shareId}/users`, {
        method: "GET",
        credentials: "include",
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to get share users" }));
        throw new Error(error.detail || "Failed to get share users");
    }

    return await response.json();
}

/**
 * Add users to a share link
 */
export async function addShareUsers(shareId: string, data: BatchAddShareUsersRequest): Promise<BatchAddShareUsersResponse> {
    const response = await fetch(`${API_BASE}/share/${shareId}/users`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(data),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to add share users" }));
        throw new Error(error.detail || "Failed to add share users");
    }

    return await response.json();
}

/**
 * Remove users from a share link
 */
export async function deleteShareUsers(shareId: string, data: BatchDeleteShareUsersRequest): Promise<BatchDeleteShareUsersResponse> {
    const response = await fetch(`${API_BASE}/share/${shareId}/users`, {
        method: "DELETE",
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(data),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to delete share users" }));
        throw new Error(error.detail || "Failed to delete share users");
    }

    return await response.json();
}

// Shared-with-me APIs

/**
 * List all chats shared with the current user
 */
export async function listSharedWithMe(): Promise<SharedWithMeItem[]> {
    const response = await fetch(`${API_BASE}/share/shared-with-me`, {
        method: "GET",
        credentials: "include",
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to list shared chats" }));
        throw new Error(error.detail || "Failed to list shared chats");
    }

    return await response.json();
}

/**
 * Update the snapshot timestamp for a share.
 * - Without userEmail: updates the current user's own snapshot (viewer use case).
 * - With userEmail: owner updates a specific user's snapshot.
 */
export async function updateShareSnapshot(shareId: string, userEmail?: string): Promise<{ snapshot_time: number }> {
    const options: RequestInit = {
        method: "POST",
        credentials: "include",
    };

    if (userEmail) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify({ user_email: userEmail });
    }

    const response = await fetch(`${API_BASE}/share/${shareId}/update-snapshot`, options);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to update snapshot" }));
        throw new Error(error.detail || "Failed to update snapshot");
    }

    return response.json();
}

/**
 * Fork a shared chat into the user's own sessions
 */
export async function forkSharedChat(shareId: string): Promise<ForkSharedChatResponse> {
    const response = await fetch(`${API_BASE}/share/${shareId}/fork`, {
        method: "POST",
        credentials: "include",
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to fork shared chat" }));
        throw new Error(error.detail || "Failed to fork shared chat");
    }

    return await response.json();
}
