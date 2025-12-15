import { useState, useEffect, useCallback } from "react";
import type { App } from "../types";

interface AppUpdate {
    name?: string;
    description?: string;
    isPublic?: boolean;
    iconEmoji?: string;
    iconBackground?: string;
}

interface RegenerateIconResponse {
    success: boolean;
    iconEmoji: string | null;
    iconBackground: string | null;
    error: string | null;
}

interface UseAppsResult {
    apps: App[];
    loading: boolean;
    error: string | null;
    refetch: () => void;
    updateApp: (appId: string, updates: AppUpdate) => Promise<boolean>;
    setAppTags: (appId: string, tags: string[]) => Promise<boolean>;
    generateIcon: (appId: string) => Promise<RegenerateIconResponse | null>;
    generatingIconFor: string | null;
}

export function useApps(): UseAppsResult {
    const [apps, setApps] = useState<App[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [generatingIconFor, setGeneratingIconFor] = useState<string | null>(null);

    const fetchApps = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await fetch("/api/v1/apps?pageNumber=1&pageSize=100");

            if (!response.ok) {
                throw new Error("Failed to fetch apps");
            }

            const data = await response.json();
            setApps(data.data || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, []);

    const updateApp = useCallback(async (appId: string, updates: AppUpdate): Promise<boolean> => {
        try {
            // Convert frontend field names to backend field names
            const backendUpdates: Record<string, unknown> = {};
            if (updates.name !== undefined) backendUpdates.name = updates.name;
            if (updates.description !== undefined) backendUpdates.description = updates.description;
            if (updates.isPublic !== undefined) backendUpdates.is_public = updates.isPublic;
            if (updates.iconEmoji !== undefined) backendUpdates.icon_emoji = updates.iconEmoji;
            if (updates.iconBackground !== undefined) backendUpdates.icon_background = updates.iconBackground;

            const response = await fetch(`/api/v1/apps/${appId}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(backendUpdates),
            });

            if (!response.ok) {
                throw new Error("Failed to update app");
            }

            // Refetch apps to get updated data
            await fetchApps();
            return true;
        } catch (err) {
            console.error("Failed to update app:", err);
            return false;
        }
    }, [fetchApps]);

    const setAppTags = useCallback(async (appId: string, tags: string[]): Promise<boolean> => {
        try {
            const response = await fetch(`/api/v1/apps/${appId}/tags`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(tags),
            });

            if (!response.ok) {
                throw new Error("Failed to update tags");
            }

            // Refetch apps to get updated data
            await fetchApps();
            return true;
        } catch (err) {
            console.error("Failed to update tags:", err);
            return false;
        }
    }, [fetchApps]);

    const generateIcon = useCallback(async (appId: string): Promise<RegenerateIconResponse | null> => {
        try {
            setGeneratingIconFor(appId);

            const response = await fetch(`/api/v1/apps/${appId}/generate-icon`, {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error("Failed to generate icon");
            }

            const data: RegenerateIconResponse = await response.json();

            // Don't update local state - just return the generated icon
            // The caller (AppSettingsDialog) will track it locally and save via updateApp
            return data;
        } catch (err) {
            console.error("Failed to generate icon:", err);
            return null;
        } finally {
            setGeneratingIconFor(null);
        }
    }, []);

    useEffect(() => {
        fetchApps();
    }, [fetchApps]);

    return {
        apps,
        loading,
        error,
        refetch: fetchApps,
        updateApp,
        setAppTags,
        generateIcon,
        generatingIconFor,
    };
}
