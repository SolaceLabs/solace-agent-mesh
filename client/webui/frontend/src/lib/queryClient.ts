import { QueryClient } from "@tanstack/react-query";

/**
 * The QueryClient instance for managing server state and caching.
 * Exported by @SolaceLabs/solace-agent-mesh-ui for use in SAM enterprise. Which requires the same query client instance.
 */
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1000 * 60 * 5,
        },
    },
});
