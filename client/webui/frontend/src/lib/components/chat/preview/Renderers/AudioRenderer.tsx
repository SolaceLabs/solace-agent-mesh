import React from "react";

import type { BaseRendererProps } from ".";

/**
 * AudioRenderer component to render audio content.
 */
export const AudioRenderer: React.FC<BaseRendererProps> = ({ content, mime_type, setRenderError }) => {
    const audioSrc = `data:${mime_type || "audio/mpeg"};base64,${content}`;

    return (
        <div className="flex h-auto max-w-[100vw] items-center justify-center p-4">
            <audio controls className="w-full" onLoad={() => setRenderError(null)} onError={() => setRenderError("Failed to load audio content.")}>
                <source src={audioSrc} type={mime_type || "audio/mpeg"} />
                Your browser does not support the audio element.
            </audio>
        </div>
    );
};
