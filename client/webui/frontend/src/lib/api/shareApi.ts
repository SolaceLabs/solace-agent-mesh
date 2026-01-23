/**
 * API client for chat sharing operations
 */

import type { ShareLink, CreateShareLinkRequest, UpdateShareLinkRequest, SharedSessionView, ShareLinksListResponse } from "../types/share";

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
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        console.error("Failed to copy to clipboard:", err);
        return false;
    }
}

/**
 * Get access type display text
 */
export function getAccessTypeDisplay(accessType: string): {
    label: string;
    icon: string;
    description: string;
} {
    switch (accessType) {
        case "public":
            return {
                label: "Public Access",
                icon: "🌐",
                description: "Anyone with the link can view",
            };
        case "authenticated":
            return {
                label: "Authenticated Users Only",
                icon: "🔒",
                description: "Requires login to view",
            };
        case "domain-restricted":
            return {
                label: "Domain-Restricted",
                icon: "🏢",
                description: "Restricted to specific email domains",
            };
        default:
            return {
                label: "Unknown",
                icon: "❓",
                description: "Unknown access type",
            };
    }
}
