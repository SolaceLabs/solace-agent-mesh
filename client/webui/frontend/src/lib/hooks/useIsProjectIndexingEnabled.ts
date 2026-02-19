import { useConfigContext } from "./useConfigContext";

/**
 * Hook to check if project indexing is enabled.
 * Controls whether the DocumentSourcesPanel is shown instead of the RAGInfoPanel.
 */
export function useIsProjectIndexingEnabled(): boolean {
    const { configFeatureEnablement } = useConfigContext();
    return configFeatureEnablement?.projectIndexing ?? false;
}
