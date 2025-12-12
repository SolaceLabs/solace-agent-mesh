/**
 * API client for user profile operations including avatar management
 */

import { authenticatedFetch } from "../utils/api";

const API_BASE = "/api/v1/user";

export interface UserProfile {
    userId: string;
    displayName?: string;
    email?: string;
    avatarUrl?: string;
    createdAt: number;
    updatedAt: number;
}

export interface AvatarUploadResponse {
    avatarUrl: string;
    storageType: string;
    message: string;
}

/**
 * Get the current user's profile
 */
export async function getUserProfile(): Promise<UserProfile> {
    const response = await authenticatedFetch(`${API_BASE}/profile`, {
        method: "GET",
        credentials: "include",
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch user profile: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Upload a new avatar image
 */
export async function uploadAvatar(file: File, storageType: "local" | "s3" = "local"): Promise<AvatarUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("storage_type", storageType);

    const response = await authenticatedFetch(`${API_BASE}/avatar`, {
        method: "POST",
        credentials: "include",
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || "Failed to upload avatar");
    }

    return response.json();
}

/**
 * Delete the current user's avatar
 */
export async function deleteAvatar(): Promise<void> {
    const response = await authenticatedFetch(`${API_BASE}/avatar`, {
        method: "DELETE",
        credentials: "include",
    });

    if (!response.ok && response.status !== 204) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || "Failed to delete avatar");
    }
}
