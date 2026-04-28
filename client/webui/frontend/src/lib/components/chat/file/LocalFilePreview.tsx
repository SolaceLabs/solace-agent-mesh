import { memo, useCallback } from "react";
import { Download, X } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { formatTimestamp } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";

import { FilePreviewBody } from "./FilePreviewBody";
import { useLocalFileSource } from "./useFileAttachmentSource";

interface LocalFilePreviewProps {
    file: File;
    onClose: () => void;
    onDownload?: (file: File) => void;
}

/**
 * Preview modal for a locally-selected File (not yet uploaded). Shares its
 * body (loading/error/ContentRenderer states) with `StandaloneArtifactPreview`
 * via `FilePreviewBody`; only the header chrome differs.
 */
export const LocalFilePreview = memo(function LocalFilePreview({ file, onClose, onDownload }: LocalFilePreviewProps) {
    const source = useLocalFileSource(file);

    const handleDefaultDownload = useCallback(() => {
        if (!source.fileContent?.url) return;
        const link = document.createElement("a");
        link.href = source.fileContent.url;
        link.download = file.name;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }, [source.fileContent?.url, file.name]);

    const download = onDownload ? () => onDownload(file) : handleDefaultDownload;

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

            <FilePreviewBody
                fileContent={source.fileContent}
                isLoading={source.isLoading}
                error={source.error}
                setError={source.setError}
                canPreview={source.canPreview}
                rendererType={source.rendererType}
                mimeType={file.type}
                filename={file.name}
                fallbackText="Preview not available for this file type"
                onDownload={download}
            />
        </div>
    );
});
