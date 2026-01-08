import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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

/**
 * QueryProvider wraps the React Query QueryClientProvider with the shared queryClient instance.
 * This provides a single import for consumers without needing to know about QueryClientProvider.
 */
export const QueryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
