import { useState, useEffect, useCallback } from "react";
import type { App } from "../types";

interface UseAppsResult {
    apps: App[];
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useApps(): UseAppsResult {
    const [apps, setApps] = useState<App[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

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

    useEffect(() => {
        fetchApps();
    }, [fetchApps]);

    return {
        apps,
        loading,
        error,
        refetch: fetchApps,
    };
}
