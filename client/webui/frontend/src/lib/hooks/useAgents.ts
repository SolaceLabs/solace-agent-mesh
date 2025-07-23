import { useState, useEffect, useCallback } from "react";

import type { AgentCard } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

interface UseAgentsReturn {
    agents: AgentCard[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

export const useAgents = (): UseAgentsReturn => {
    const { configServerUrl } = useConfigContext();
    const [agents, setAgents] = useState<AgentCard[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchAgents = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch(`${apiPrefix}/agents`, { credentials: "include" });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Failed to fetch agents: ${response.statusText}` }));
                throw new Error(errorData.message || `Failed to fetch agents: ${response.statusText}`);
            }
            const data: AgentCard[] = await response.json();
            setAgents(data);
        } catch (err: unknown) {
            console.error("Error fetching agents:", err);
            setError(err instanceof Error ? err.message : "Could not load agent information.");
            setAgents([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix]);

    useEffect(() => {
        fetchAgents();
    }, [fetchAgents]);

    return {
        agents,
        isLoading,
        error,
        refetch: fetchAgents,
    };
};
