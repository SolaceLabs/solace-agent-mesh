import { useState, useEffect, useCallback } from "react";
import type { App, DeployAppResponse } from "../types";

interface UseAppResult {
    app: App | null;
    loading: boolean;
    error: string | null;
    deploy: () => Promise<DeployAppResponse | null>;
    deploying: boolean;
    refetch: () => void;
}

export function useApp(appId: string): UseAppResult {
    const [app, setApp] = useState<App | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [deploying, setDeploying] = useState(false);

    const fetchApp = useCallback(async () => {
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

    const deploy = useCallback(async (): Promise<DeployAppResponse | null> => {
        try {
            setDeploying(true);

            const response = await fetch(`/api/v1/apps/${appId}/deploy`, {
                method: "POST",
            });

            if (!response.ok) {
                throw new Error("Failed to deploy app");
            }

            const data: DeployAppResponse = await response.json();

            // Refetch app to get updated status
            await fetchApp();

            return data;
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
            return null;
        } finally {
            setDeploying(false);
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
        deploying,
        refetch: fetchApp,
    };
}
