import { useState, useCallback, useMemo } from "react";
import { shouldAutoRender, isUserControllableRendering } from "@/lib/components/chat/file/fileUtils";

interface UseArtifactRenderingOptions {
    filename?: string;
    mimeType?: string;
    shouldAutoExpand?: boolean;
}

interface UseArtifactRenderingReturn {
    shouldRender: boolean;
    isExpandable: boolean;
    isExpanded: boolean;
    toggleExpanded: () => void;
}

/**
 * Custom hook to manage artifact rendering state and decisions
 * Uses local component state to ensure each instance has independent expansion
 */
export const useArtifactRendering = ({
    filename,
    mimeType,
    shouldAutoExpand
}: UseArtifactRenderingOptions): UseArtifactRenderingReturn => {
    // Determine if this artifact should auto-render (images and audio)
    const shouldAutoRenderArtifact = useMemo(() => {
        return shouldAutoRender(filename, mimeType);
    }, [filename, mimeType]);

    // Initialize expansion state based on shouldAutoExpand parameter
    // This allows the caller to control whether artifacts start expanded
    const [isExpanded, setIsExpanded] = useState(() => shouldAutoExpand ?? shouldAutoRenderArtifact);

    // Determine if this artifact supports user-controlled rendering
    const isUserControllable = useMemo(() => {
        return isUserControllableRendering(filename, mimeType);
    }, [filename, mimeType]);

    // Determine final rendering decision
    const shouldRender = useMemo(() => {
        if (isUserControllable) {
            // User-controllable files (including images and audio) render only when expanded
            return isExpanded;
        }

        // Non-renderable files don't render
        return false;
    }, [isUserControllable, isExpanded]);

    // Determine if the artifact is expandable
    const isExpandable = useMemo(() => {
        return isUserControllable;
    }, [isUserControllable]);

    // Toggle expanded state for this artifact
    const toggleExpanded = useCallback(() => {
        if (!filename || !isExpandable) {
            console.log(`[useArtifactRendering] Toggle blocked - filename: ${filename}, isExpandable: ${isExpandable}`);
            return;
        }

        setIsExpanded(prev => {
            const newValue = !prev;
            console.log(`[useArtifactRendering] ${newValue ? 'Expanding' : 'Collapsing'} ${filename}`);
            return newValue;
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
