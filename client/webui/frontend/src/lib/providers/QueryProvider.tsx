import React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./QueryClient";

/**
 * QueryProvider wraps the React Query QueryClientProvider with the shared queryClient instance.
 * This provides a single import for consumers without needing to know about QueryClientProvider.
 */
export const QueryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
