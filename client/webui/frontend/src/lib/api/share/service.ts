/**
 * API service functions for chat sharing operations
 *
 * The backend returns snake_case JSON. This service maps responses
 * to the camelCase FE types defined in types/share.ts.
 */

import { api } from "../client";
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
} from "../../types/share";

const SHARE_BASE = "/api/v1/share";

/** Recursively converts snake_case object keys to camelCase */
function toCamelCase<T>(obj: unknown): T {
    if (Array.isArray(obj)) {
        return obj.map(item => toCamelCase(item)) as T;
    }
    if (obj !== null && typeof obj === "object" && !(obj instanceof Blob) && !(obj instanceof Date)) {
        const result: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
            const camelKey = key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
            result[camelKey] = toCamelCase(value);
        }
        return result as T;
    }
    return obj as T;
}

export async function createShareLink(sessionId: string, options: CreateShareLinkRequest = {}): Promise<ShareLink> {
    const raw = await api.webui.post(`${SHARE_BASE}/${sessionId}`, options);
    return toCamelCase<ShareLink>(raw);
}

export async function getShareLinkForSession(sessionId: string): Promise<ShareLink | null> {
    const response = await api.webui.get(`${SHARE_BASE}/link/${sessionId}`, { fullResponse: true });
    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Failed to get share link" }));
        throw new Error(error.detail || "Failed to get share link");
    }
    const raw = await response.json();
    return toCamelCase<ShareLink>(raw);
}

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
    const raw = await api.webui.get(`${SHARE_BASE}${qs ? `?${qs}` : ""}`);
    return toCamelCase<ShareLinksListResponse>(raw);
}

export async function viewSharedSession(shareId: string): Promise<SharedSessionView> {
    const raw = await api.webui.get(`${SHARE_BASE}/${shareId}`, { credentials: "include" });
    return toCamelCase<SharedSessionView>(raw);
}

export async function updateShareLink(shareId: string, options: UpdateShareLinkRequest): Promise<ShareLink> {
    const raw = await api.webui.patch(`${SHARE_BASE}/${shareId}`, options);
    return toCamelCase<ShareLink>(raw);
}

export async function deleteShareLink(shareId: string): Promise<void> {
    await api.webui.delete(`${SHARE_BASE}/${shareId}`);
}

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

export async function downloadSharedArtifact(shareId: string, filename: string): Promise<Blob> {
    const encodedFilename = encodeURIComponent(filename);
    const response = await api.webui.get(`${SHARE_BASE}/${shareId}/artifacts/${encodedFilename}`, { fullResponse: true, credentials: "include" });

    if (!response.ok) {
        throw new Error(`Failed to download: ${response.statusText}`);
    }

    return response.blob();
}

export async function getShareUsers(shareId: string): Promise<ShareUsersResponse> {
    const raw = await api.webui.get(`${SHARE_BASE}/${shareId}/users`);
    return toCamelCase<ShareUsersResponse>(raw);
}

export async function addShareUsers(shareId: string, data: BatchAddShareUsersRequest): Promise<BatchAddShareUsersResponse> {
    const raw = await api.webui.post(`${SHARE_BASE}/${shareId}/users`, data);
    return toCamelCase<BatchAddShareUsersResponse>(raw);
}

export async function deleteShareUsers(shareId: string, data: BatchDeleteShareUsersRequest): Promise<BatchDeleteShareUsersResponse> {
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
    const raw = await response.json();
    return toCamelCase<BatchDeleteShareUsersResponse>(raw);
}

export async function listSharedWithMe(): Promise<SharedWithMeItem[]> {
    const raw = await api.webui.get(`${SHARE_BASE}/shared-with-me`);
    return toCamelCase<SharedWithMeItem[]>(raw);
}

export async function updateShareSnapshot(shareId: string, userEmail?: string): Promise<{ snapshotTime: number }> {
    const body = userEmail ? { user_email: userEmail } : undefined;
    const raw = await api.webui.post(`${SHARE_BASE}/${shareId}/update-snapshot`, body);
    return toCamelCase<{ snapshotTime: number }>(raw);
}

export async function forkSharedChat(shareId: string): Promise<ForkSharedChatResponse> {
    const raw = await api.webui.post(`${SHARE_BASE}/${shareId}/fork`);
    return toCamelCase<ForkSharedChatResponse>(raw);
}
