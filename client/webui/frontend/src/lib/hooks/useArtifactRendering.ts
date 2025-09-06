import { useState, useCallback, useMemo } from "react";
import { shouldAutoRender, isUserControllableRendering } from "@/lib/components/chat/file/fileUtils";

interface ArtifactRenderingState {
    expandedArtifacts: Set<string>;
}

interface UseArtifactRenderingOptions {
    filename?: string;
    mimeType?: string;
}

interface UseArtifactRenderingReturn {
    shouldRender: boolean;
    isExpandable: boolean;
    isExpanded: boolean;
    toggleExpanded: () => void;
}

/**
 * Custom hook to manage artifact rendering state and decisions
 */
export const useArtifactRendering = ({ 
    filename, 
    mimeType 
}: UseArtifactRenderingOptions): UseArtifactRenderingReturn => {
    const [state, setState] = useState<ArtifactRenderingState>({
        expandedArtifacts: new Set<string>()
    });

    // Determine if this artifact should auto-render
    const shouldAutoRenderArtifact = useMemo(() => {
        return shouldAutoRender(filename, mimeType);
    }, [filename, mimeType]);

    // Determine if this artifact supports user-controlled rendering
    const isUserControllable = useMemo(() => {
        return isUserControllableRendering(filename, mimeType);
    }, [filename, mimeType]);

    // Check if this specific artifact is expanded
    const isExpanded = useMemo(() => {
        if (!filename) return false;
        return state.expandedArtifacts.has(filename);
    }, [filename, state.expandedArtifacts]);

    // Determine final rendering decision
    const shouldRender = useMemo(() => {
        if (shouldAutoRenderArtifact) {
            // Images and audio always render
            return true;
        }
        
        if (isUserControllable) {
            // Text-based files render only when expanded
            return isExpanded;
        }
        
        // Non-renderable files don't render
        return false;
    }, [shouldAutoRenderArtifact, isUserControllable, isExpanded]);

    // Determine if the artifact is expandable
    const isExpandable = useMemo(() => {
        return isUserControllable;
    }, [isUserControllable]);

    // Toggle expanded state for this artifact
    const toggleExpanded = useCallback(() => {
        if (!filename || !isExpandable) return;
        
        setState(prevState => {
            const newExpandedArtifacts = new Set(prevState.expandedArtifacts);
            
            if (newExpandedArtifacts.has(filename)) {
                newExpandedArtifacts.delete(filename);
            } else {
                newExpandedArtifacts.add(filename);
            }
            
            return {
                ...prevState,
                expandedArtifacts: newExpandedArtifacts
            };
        });
    }, [filename, isExpandable]);

    return {
        shouldRender,
        isExpandable,
        isExpanded,
        toggleExpanded
    };
};

/**
 * Hook for managing global artifact rendering preferences
 * This can be extended in the future to include user settings
 */
export const useArtifactRenderingPreferences = () => {
    // Future: This could read from user preferences/settings
    // For now, we use the default behavior defined in the design
    
    const getAutoRenderPreference = useCallback((filename?: string, mimeType?: string) => {
        return shouldAutoRender(filename, mimeType);
    }, []);

    const getUserControllablePreference = useCallback((filename?: string, mimeType?: string) => {
        return isUserControllableRendering(filename, mimeType);
    }, []);

    return {
        getAutoRenderPreference,
        getUserControllablePreference
    };
};
