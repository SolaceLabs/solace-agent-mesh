import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { Download, File as FileIconLucide, X } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
import { formatTimestamp } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";
import { ContentRenderer } from "@/lib/components/chat/preview/ContentRenderer";
import { getFileContent, getRenderType } from "@/lib/components/chat/preview/previewUtils";
import type { FileAttachment } from "@/lib/types";

interface LocalFilePreviewProps {
    file: File;
    onClose: () => void;
    onDownload?: (file: File) => void;
}

/**
 * Preview modal for a locally-selected File (not yet uploaded). Mirrors the
 * layout of StandaloneArtifactPreview but sources bytes from the File object
 * instead of the artifacts API — so it works for drag-and-dropped / picked
 * files the moment they enter the input area.
 */
export const LocalFilePreview = memo(function LocalFilePreview({ file, onClose, onDownload }: LocalFilePreviewProps) {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<FileAttachment | null>(null);

    const rendererType = useMemo(() => getRenderType(file.name, file.type), [file.name, file.type]);
    const canPreview = !!rendererType;

    // Create (and later revoke) an object URL so binary renderers (PDF, images)
    // can load via `url` without needing base64-in-memory.
    const blobUrl = useMemo(() => URL.createObjectURL(file), [file]);
    useEffect(() => {
        return () => {
            URL.revokeObjectURL(blobUrl);
        };
    }, [blobUrl]);

    // Read the file as base64 once; text/json/csv/markdown renderers need the
    // raw content, and image/audio/docx/pptx renderers take base64 directly.
    useEffect(() => {
        if (!canPreview) {
            setIsLoading(false);
            return;
        }

        let cancelled = false;
        setIsLoading(true);
        setError(null);

        const reader = new FileReader();
        reader.onload = () => {
            if (cancelled) return;
            const result = reader.result as string;
            const commaIdx = result.indexOf(",");
            const base64 = commaIdx >= 0 ? result.substring(commaIdx + 1) : result;

            setFileContent({
                name: file.name,
                mime_type: file.type || "application/octet-stream",
                content: base64,
                last_modified: new Date(file.lastModified).toISOString(),
                size: file.size,
                url: blobUrl,
            });
            setIsLoading(false);
        };
        reader.onerror = () => {
            if (cancelled) return;
            setError("Failed to read file");
            setIsLoading(false);
        };
        reader.readAsDataURL(file);

        return () => {
            cancelled = true;
            reader.abort();
        };
    }, [file, blobUrl, canPreview]);

    const handleDefaultDownload = useCallback(() => {
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = file.name;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }, [blobUrl, file.name]);

    const download = onDownload ? () => onDownload(file) : handleDefaultDownload;

    const content = useMemo(() => getFileContent(fileContent), [fileContent]);
    const renderer = useMemo(() => {
        if (!canPreview || !rendererType || !content) return null;
        return <ContentRenderer content={content} rendererType={rendererType} mime_type={file.type} url={fileContent?.url} filename={file.name} setRenderError={setError} />;
    }, [canPreview, rendererType, content, file.type, file.name, fileContent?.url]);

    return (
        <div className="flex h-full flex-col border-l">
            <div className="flex items-center gap-3 border-b px-3 py-2">
                <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-semibold" title={file.name}>
                        {file.name}
                    </h3>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                        <span>{formatBytes(file.size)}</span>
                        <span>•</span>
                        <span>{formatTimestamp(new Date(file.lastModified).toISOString())}</span>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={download}>
                        <Download className="mr-1 h-4 w-4" />
                        Download
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            </div>

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
                        <div className="text-sm text-(--secondary-text-wMain)">Preview not available for this file type</div>
                        <Button variant="default" className="mt-4" onClick={download}>
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
        </div>
    );
});
