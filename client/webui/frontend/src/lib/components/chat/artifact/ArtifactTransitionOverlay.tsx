import React from "react";
import { Loader2 } from "lucide-react";

interface ArtifactTransitionOverlayProps {
    isVisible: boolean;
    message?: string;
}

/**
 * Semi-transparent overlay shown during the transition from cached content
 * to backend-fetched content with resolved embeds.
 */
export const ArtifactTransitionOverlay: React.FC<ArtifactTransitionOverlayProps> = ({
    isVisible,
    message = "Resolving embeds..."
}) => {
    if (!isVisible) return null;

    return (
        <div
            className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm transition-opacity duration-200"
            style={{
                opacity: isVisible ? 1 : 0,
                pointerEvents: isVisible ? 'auto' : 'none'
            }}
        >
            <div className="flex flex-col items-center gap-3 rounded-lg bg-card p-6 shadow-lg">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">{message}</p>
            </div>
        </div>
    );
};
