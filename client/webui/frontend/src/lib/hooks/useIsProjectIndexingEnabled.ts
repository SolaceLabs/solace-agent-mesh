import { useBooleanFlagValue } from "@openfeature/react-sdk";

/**
 * Hook to check if project indexing is enabled.
 * Controls whether the DocumentSourcesPanel is shown instead of the RAGInfoPanel.
 */
export function useIsProjectIndexingEnabled(): boolean {
    return useBooleanFlagValue("project_indexing", false);
}
