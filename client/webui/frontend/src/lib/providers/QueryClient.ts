import { QueryClient } from "@tanstack/react-query";

/**
 * Shared QueryClient instance used across the application.
 * Export this to allow manual query invalidation or cache manipulation.
 */
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1000 * 60 * 5,
        },
    },
});
