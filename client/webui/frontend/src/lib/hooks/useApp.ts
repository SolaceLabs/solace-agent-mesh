import { useState, useEffect, useCallback } from "react";
import type { App, AppVersionsResponse, DeployAppResponse, Environment, PromoteVersionResponse } from "../types";

interface AppUpdate {
    name?: string;
    description?: string;
    isPublic?: boolean;
}

interface RegenerateIconResponse {
    success: boolean;
    iconEmoji: string | null;
    iconBackground: string | null;
    error: string | null;
}

interface UseAppResult {
    app: App | null;
    loading: boolean;
    error: string | null;
    deploy: () => Promise<DeployAppResponse | null>;
    deployToEnvironment: (environment: Environment) => Promise<DeployAppResponse | null>;
    deploying: boolean;
    refetch: () => void;
    // Version management
    versions: AppVersionsResponse | null;
    loadingVersions: boolean;
    fetchVersions: () => Promise<void>;
    promoteVersion: (version: string, environment: Environment) => Promise<PromoteVersionResponse | null>;
    promoting: boolean;
    // Settings
    updateApp: (updates: AppUpdate) => Promise<boolean>;
    updating: boolean;
    // Tags
    setAppTags: (tags: string[]) => Promise<boolean>;
    // Icon
    regenerateIcon: () => Promise<RegenerateIconResponse | null>;
    regeneratingIcon: boolean;
}

export function useApp(appId: string | undefined): UseAppResult {
    const [app, setApp] = useState<App | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [deploying, setDeploying] = useState(false);

    // Version state
    const [versions, setVersions] = useState<AppVersionsResponse | null>(null);
    const [loadingVersions, setLoadingVersions] = useState(false);
    const [promoting, setPromoting] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [regeneratingIcon, setRegeneratingIcon] = useState(false);

    const fetchApp = useCallback(async () => {
        if (!appId) {
            setApp(null);
            setLoading(false);
            return;
        }

        try {
            setLoading(true);
            setError(null);

            const response = await fetch(`/api/v1/apps/${appId}`);

            if (!response.ok) {
                throw new Error("Failed to fetch app");
            }

            const data = await response.json();
            setApp(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, [appId]);

    const fetchVersions = useCallback(async () => {
        if (!appId) return;

        try {
            setLoadingVersions(true);

            const response = await fetch(`/api/v1/apps/${appId}/versions`);

            if (!response.ok) {
                throw new Error("Failed to fetch versions");
            }

            const data: AppVersionsResponse = await response.json();
            setVersions(data);
        } catch (err) {
            console.error("Failed to fetch versions:", err);
        } finally {
            setLoadingVersions(false);
        }
    }, [appId]);

    const deploy = useCallback(async (): Promise<DeployAppResponse | null> => {
        if (!appId) return null;

        try {
            setDeploying(true);

            const response = await fetch(`/api/v1/apps/${appId}/deploy`, {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error("Failed to deploy app");
            }

            const data: DeployAppResponse = await response.json();

            // Refetch app and versions to get updated status
            await Promise.all([fetchApp(), fetchVersions()]);

            return data;
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
            return null;
        } finally {
            setDeploying(false);
        }
    }, [appId, fetchApp, fetchVersions]);

    const deployToEnvironment = useCallback(async (environment: Environment): Promise<DeployAppResponse | null> => {
        if (!appId) return null;

        try {
            setDeploying(true);

            const response = await fetch(`/api/v1/apps/${appId}/deploy?environment=${environment}`, {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error(`Failed to deploy app to ${environment}`);
            }

            const data: DeployAppResponse = await response.json();

            // Refetch app and versions to get updated status
            await Promise.all([fetchApp(), fetchVersions()]);

            return data;
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
            return null;
        } finally {
            setDeploying(false);
        }
    }, [appId, fetchApp, fetchVersions]);

    const promoteVersion = useCallback(async (version: string, environment: Environment): Promise<PromoteVersionResponse | null> => {
        if (!appId) return null;

        try {
            setPromoting(true);

            const response = await fetch(
                `/api/v1/apps/${appId}/promote?version=${encodeURIComponent(version)}&environment=${environment}`,
                { method: "POST" }
            );

            if (!response.ok) {
                throw new Error(`Failed to promote version to ${environment}`);
            }

            const data: PromoteVersionResponse = await response.json();

            // Refetch app and versions to get updated status
            await Promise.all([fetchApp(), fetchVersions()]);

            return data;
        } catch (err) {
            console.error("Failed to promote version:", err);
            return null;
        } finally {
            setPromoting(false);
        }
    }, [appId, fetchApp, fetchVersions]);

    const updateApp = useCallback(async (updates: AppUpdate): Promise<boolean> => {
        if (!appId) return false;

        try {
            setUpdating(true);

            // Convert frontend field names to backend field names
            const backendUpdates: Record<string, unknown> = {};
            if (updates.name !== undefined) backendUpdates.name = updates.name;
            if (updates.description !== undefined) backendUpdates.description = updates.description;
            if (updates.isPublic !== undefined) backendUpdates.is_public = updates.isPublic;

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

            // Refetch app to get updated data
            await fetchApp();
            return true;
        } catch (err) {
            console.error("Failed to update app:", err);
            return false;
        } finally {
            setUpdating(false);
        }
    }, [appId, fetchApp]);

    const setAppTags = useCallback(async (tags: string[]): Promise<boolean> => {
        if (!appId) return false;

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

            // Refetch app to get updated data
            await fetchApp();
            return true;
        } catch (err) {
            console.error("Failed to update tags:", err);
            return false;
        }
    }, [appId, fetchApp]);

    const regenerateIcon = useCallback(async (): Promise<RegenerateIconResponse | null> => {
        if (!appId) return null;

        try {
            setRegeneratingIcon(true);

            const response = await fetch(`/api/v1/apps/${appId}/regenerate-icon`, {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error("Failed to regenerate icon");
            }

            const data: RegenerateIconResponse = await response.json();

            // Refetch app to get updated icon
            await fetchApp();

            return data;
        } catch (err) {
            console.error("Failed to regenerate icon:", err);
            return null;
        } finally {
            setRegeneratingIcon(false);
        }
    }, [appId, fetchApp]);

    useEffect(() => {
        fetchApp();
    }, [fetchApp]);

    return {
        app,
        loading,
        error,
        deploy,
        deployToEnvironment,
        deploying,
        refetch: fetchApp,
        versions,
        loadingVersions,
        fetchVersions,
        promoteVersion,
        promoting,
        updateApp,
        updating,
        setAppTags,
        regenerateIcon,
        regeneratingIcon,
    };
}
