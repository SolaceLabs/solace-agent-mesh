import { memo, useMemo } from "react";
import { Download, File as FileIconLucide } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { getFileContent } from "@/lib/components/chat/preview/previewUtils";
import type { FileAttachment } from "@/lib/types";

interface FilePreviewBodyProps {
    fileContent: FileAttachment | null;
    isLoading: boolean;
    error: string | null;
    setError: (err: string | null) => void;
    canPreview: boolean;
    rendererType: ReturnType<typeof import("@/lib/components/chat/preview/previewUtils").getRenderType>;
    /** Used by ContentRenderer for type-specific decoding. */
    mimeType: string;
    filename: string;
    /** Shown in the "no preview available" fallback state. */
    fallbackText?: string;
    /** Action for the "no preview" Download button. */
    onDownload: () => void;
}

/**
 * Shared body for `LocalFilePreview` and `StandaloneArtifactPreview`. Both
 * surface the same loading / error / "no preview" / ContentRenderer states;
 * the only meaningful difference between them is header chrome and source.
 */
export const FilePreviewBody = memo(function FilePreviewBody({ fileContent, isLoading, error, setError, canPreview, rendererType, mimeType, filename, fallbackText, onDownload }: FilePreviewBodyProps) {
    const content = useMemo(() => getFileContent(fileContent), [fileContent]);
    const renderer = useMemo(() => {
        if (!canPreview || !rendererType || !content) return null;
        return <ContentRenderer content={content} rendererType={rendererType} mime_type={mimeType} url={fileContent?.url} filename={filename} setRenderError={setError} />;
    }, [canPreview, rendererType, content, mimeType, fileContent?.url, filename, setError]);

    return (
        <div className="min-h-0 flex-1 overflow-auto">
            {isLoading && !renderer && (
                <div className="flex h-full items-center justify-center">
                    <Spinner size="medium" variant="muted" />
                </div>
            )}

            {error && (
                <div className="flex h-full flex-col items-center justify-center p-4">
                    <div className="mb-2 text-sm text-(--error-wMain)">Error loading preview</div>
                    <div className="text-xs text-(--secondary-text-wMain)">{error}</div>
                </div>
            )}

            {!isLoading && !error && !canPreview && (
                <div className="flex h-full flex-col items-center justify-center p-4">
                    <FileIconLucide className="mb-4 h-12 w-12 text-(--secondary-text-wMain)" />
                    <div className="text-sm text-(--secondary-text-wMain)">{fallbackText ?? "Preview not available"}</div>
                    <Button variant="default" className="mt-4" onClick={onDownload}>
                        <Download className="mr-2 h-4 w-4" />
                        Download File
                    </Button>
                </div>
            )}

            {renderer && (
                <div className="relative h-full w-full">
                    {renderer}
                    {isLoading && (
                        <div className="overlay-backdrop absolute inset-0 flex items-center justify-center">
                            <Spinner size="medium" variant="muted" />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
});
