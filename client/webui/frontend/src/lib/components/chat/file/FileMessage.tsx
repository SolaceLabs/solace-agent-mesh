import React, { useMemo, useState, useEffect, useCallback } from "react";

import { Download, Eye } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";
import { downloadFile, parseArtifactUri } from "@/lib/utils/download";
import { authenticatedFetch } from "@/lib/utils/api";
import { cn } from "@/lib/utils";

import { getFileIcon } from "./fileUtils";
import { getRenderType, getFileContent } from "../preview/previewUtils";
import { ContentRenderer } from "../preview/ContentRenderer";
import { MessageBanner } from "../../common";

const INLINE_RENDERABLE_TYPES = ["image", "audio", "markdown", "csv", "json", "yaml"];

interface FileAttachmentMessageProps {
    fileAttachment: FileAttachment;
    isEmbedded?: boolean;
}

export const FileAttachmentMessage: React.FC<Readonly<FileAttachmentMessageProps>> = ({ fileAttachment, isEmbedded = false }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const [renderError, setRenderError] = useState<string | null>(null);

    const renderType = useMemo(() => getRenderType(fileAttachment.name, fileAttachment.mime_type), [fileAttachment.name, fileAttachment.mime_type]);

    useEffect(() => {
        const fetchContentFromUri = async () => {
            if (!fileAttachment.uri || !renderType || !INLINE_RENDERABLE_TYPES.includes(renderType)) {
                return;
            }

            setIsLoading(true);
            setError(null);

            try {
                const parsedUri = parseArtifactUri(fileAttachment.uri);
                if (!parsedUri) throw new Error("Invalid artifact URI.");

                const { filename, version } = parsedUri;
                const apiUrl = `/api/v1/artifacts/${encodeURIComponent(filename)}/versions/${version || "latest"}`;

                const response = await authenticatedFetch(apiUrl);
                if (!response.ok) throw new Error(`Failed to fetch artifact content: ${response.statusText}`);

                const blob = await response.blob();
                const base64data = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        if (typeof reader.result === "string") {
                            resolve(reader.result.split(",")[1]);
                        } else {
                            reject(new Error("Failed to read artifact content as a data URL."));
                        }
                    };
                    reader.onerror = () => {
                        reject(reader.error || new Error("An unknown error occurred while reading the file."));
                    };
                    reader.readAsDataURL(blob);
                });

                setFetchedContent(base64data);
            } catch (e) {
                console.error("Error fetching inline content:", e);
                setError(e instanceof Error ? e.message : "Unknown error fetching content.");
            } finally {
                setIsLoading(false);
            }
        };

        if (fileAttachment.uri && !fileAttachment.content) {
            fetchContentFromUri();
        }
    }, [fileAttachment.uri, fileAttachment.content, renderType]);

    const contentToRender = fetchedContent || fileAttachment.content;

    const renderFallbackBadge = () => <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} className="ml-4" isEmbedded={isEmbedded} />;

    if (isEmbedded) {
        return renderFallbackBadge();
    }

    if (renderType && INLINE_RENDERABLE_TYPES.includes(renderType)) {
        if (isLoading) {
            return (
                <div className="ml-4 my-2 p-4 border rounded-lg max-w-2xl h-24 flex items-center justify-center bg-muted">
                    <Spinner />
                </div>
            );
        }

        if (error) {
            return (
                <div className="ml-4 my-2">
                    <MessageBanner variant="error" message={error} />
                </div>
            );
        }

        if (contentToRender) {
            const finalContent = getFileContent({ ...fileAttachment, content: contentToRender });
            if (!finalContent) {
                return renderFallbackBadge();
            }

            const scrollableRenderTypes = ["csv", "json", "yaml", "markdown"];
            const rendererContainerStyle: React.CSSProperties =
                renderType && scrollableRenderTypes.includes(renderType) ? { maxHeight: "400px", overflowY: "auto" } : {};

            const noBorderRenderTypes = ["image", "audio"];
            const containerClasses = cn(
                "relative group max-w-2xl my-2 overflow-hidden bg-background ml-4",
                !noBorderRenderTypes.includes(renderType || "") && "border rounded-lg"
            );

            return (
                <div className={containerClasses}>
                    {renderError && <MessageBanner variant="error" message={renderError} />}
                    <div style={rendererContainerStyle}>
                        <ContentRenderer content={finalContent} rendererType={renderType} mime_type={fileAttachment.mime_type} setRenderError={setRenderError} />
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/20 hover:bg-black/40 text-white"
                        onClick={() => downloadFile(fileAttachment)}
                        tooltip="Download"
                    >
                        <Download className="h-4 w-4" />
                    </Button>
                </div>
            );
        }
    }

    return renderFallbackBadge();
};

interface FileMessageProps {
    filename: string;
    mimeType?: string;
    className?: string;
    onDownload?: () => void;
    isEmbedded?: boolean;
}

export const FileMessage: React.FC<Readonly<FileMessageProps>> = ({ filename, mimeType, className, onDownload, isEmbedded = false }) => {
    const { artifacts, setPreviewArtifact, openSidePanelTab } = useChatContext();

    const artifact: ArtifactInfo | undefined = useMemo(() => artifacts.find(artifact => artifact.filename === filename), [artifacts, filename]);
    const FileIcon = useMemo(() => getFileIcon(artifact || { filename, mime_type: mimeType || "", size: 0, last_modified: "" }), [artifact, filename, mimeType]);

    const handlePreviewClick = useCallback(
        (e: React.MouseEvent) => {
            e.stopPropagation();
            if (artifact) {
                openSidePanelTab("files");
                setPreviewArtifact(artifact);
            }
        },
        [artifact, openSidePanelTab, setPreviewArtifact]
    );

    const handleDownloadClick = useCallback(() => {
        if (onDownload) {
            onDownload();
        }
    }, [onDownload]);

    return (
        <div className={`flex flex-shrink items-center gap-2 rounded-lg bg-[var(--accent-background)] px-2 py-1 h-11 max-w-xs ${className || ""}`}>
            {FileIcon}
            <span className="min-w-0 flex-1 truncate text-sm leading-9" title={filename}>
                <strong>
                    <code>{filename}</code>
                </strong>
            </span>

            {artifact && !isEmbedded && (
                <Button variant="ghost" onClick={handlePreviewClick} tooltip="Preview">
                    <Eye className="h-4 w-4" />
                </Button>
            )}

            {onDownload && (
                <Button variant="ghost" onClick={handleDownloadClick} tooltip="Download file">
                    <Download className="h-4 w-4" />
                </Button>
            )}
        </div>
    );
};
