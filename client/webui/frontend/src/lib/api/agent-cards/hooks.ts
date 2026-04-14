import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";

import { agentCardKeys } from "./keys";
import { fetchAgentCards, transformAgentCard } from "./service";

import type { AgentCardInfo } from "@/lib/types";

export interface UseAgentCardsReturn {
    agents: AgentCardInfo[];
    agentNameMap: Record<string, string>;
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

/**
 * Hook to fetch and cache discovered agent cards.
 * Uses React Query so the cache can be invalidated when model configurations change.
 */
export const useAgentCards = (): UseAgentCardsReturn => {
    const {
        data: agents = [],
        isLoading,
        error: queryError,
        refetch: queryRefetch,
    } = useQuery({
        queryKey: agentCardKeys.lists(),
        queryFn: async () => {
            const data = await fetchAgentCards();
            return data.map(transformAgentCard);
        },
        retry: 0,
        refetchOnMount: "always",
    });

    const error = queryError ? (queryError instanceof Error ? queryError.message : "Could not load agent information.") : null;

    const agentNameMap = useMemo(() => {
        const nameDisplayNameMap: Record<string, string> = {};
        agents.forEach(agent => {
            if (agent.name) {
                nameDisplayNameMap[agent.name] = agent.displayName || agent.name;
            }
        });
        return nameDisplayNameMap;
    }, [agents]);

    const refetch = useCallback(async () => {
        await queryRefetch();
    }, [queryRefetch]);

    return useMemo(
        () => ({
            agents,
            agentNameMap,
            isLoading,
            error,
            refetch,
        }),
        [agents, agentNameMap, isLoading, error, refetch]
    );
};
