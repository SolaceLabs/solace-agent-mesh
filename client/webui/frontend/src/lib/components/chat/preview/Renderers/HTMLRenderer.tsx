import React, { useMemo } from "react";

import type { BaseRendererProps } from ".";

export const HtmlRenderer: React.FC<BaseRendererProps> = ({ content, setRenderError }) => {
    const preparedContent = useMemo(() => {
        const cleanHtml = content;

        // This regex finds script tags and wraps their content in an IIFE
        const wrappedContent = cleanHtml.replace(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi, (match: string, scriptContent: string) => {
            const scriptTagMatch = match.match(/<script(\s[^>]*)?>/i);
            const attributes = scriptTagMatch && scriptTagMatch[1] ? scriptTagMatch[1] : "";
            return `<script${attributes}>(function() {\ntry {\n${scriptContent}\n} catch (e) { console.error('Error in sandboxed script:', e); }\n})();</script>`;
        });
        return wrappedContent;
    }, [content]);

    return (
        <div className="h-full w-full overflow-hidden border dark:bg-gray-400">
            <iframe
                srcDoc={preparedContent}
                title="HTML Preview"
                // Security sandbox: allow scripts and same-origin (for relative paths within srcDoc), allow-downloads if needed, but restrict others like top-navigation.
                sandbox="allow-scripts allow-same-origin allow-downloads allow-forms allow-popups"
                allow="autoplay"
                className="h-full w-full border-none"
                onError={() => setRenderError("Failed to load HTML content.")}
                onLoad={() => setRenderError(null)}
            />
        </div>
    );
};
