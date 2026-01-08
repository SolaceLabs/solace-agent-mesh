import React from "react";

import type { BaseRendererProps } from ".";

/**
 * ImageRenderer component to render image content.
 */
export const ImageRenderer: React.FC<BaseRendererProps> = ({ content, mime_type, setRenderError }) => {
    const imageUrl = `data:${mime_type || "image/png"};base64,${content}`;

    return (
        <div className="flex h-auto w-auto max-w-[100vw] items-center justify-center p-4">
            <img src={imageUrl} onError={() => setRenderError("Failed to load image")} onLoad={() => setRenderError(null)} alt="Preview" className="h-full w-full object-contain" />
        </div>
    );
};
