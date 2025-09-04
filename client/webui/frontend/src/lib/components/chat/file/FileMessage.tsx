import React, { useMemo, useState, useEffect } from "react";

import { Download, Eye } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";
import { downloadFile, parseArtifactUri } from "@/lib/utils/download";
import { authenticatedFetch } from "@/lib/utils/api";

import { getFileIcon } from "./fileUtils";
import { getRenderType, getFileContent } from "../preview/previewUtils";
import { ContentRenderer } from "../preview/ContentRenderer";
import { MessageBanner } from "../../common";

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
    const inlineRenderableTypes = ["image", "audio", "markdown", "csv", "json", "yaml"];

    useEffect(() => {
        const fetchContentFromUri = async () => {
            if (!fileAttachment.uri || !renderType || !inlineRenderableTypes.includes(renderType)) {
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
                const reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = () => {
                    const base64data = (reader.result as string).split(",")[1];
                    setFetchedContent(base64data);
                    setIsLoading(false);
                };
                reader.onerror = () => {
                    throw new Error("Failed to read artifact content as base64.");
                };
            } catch (e) {
                console.error("Error fetching inline content:", e);
                setError(e instanceof Error ? e.message : "Unknown error fetching content.");
                setIsLoading(false);
            }
        };

        if (fileAttachment.uri && !fileAttachment.content) {
            fetchContentFromUri();
        }
    }, [fileAttachment.uri, fileAttachment.content, renderType, inlineRenderableTypes]);

    const contentToRender = fetchedContent || fileAttachment.content;

    if (isEmbedded) {
        return <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} className="ml-4" isEmbedded={isEmbedded} />;
    }

    if (renderType && inlineRenderableTypes.includes(renderType)) {
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
                return <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} className="ml-4" isEmbedded={isEmbedded} />;
            }

            const rendererContainerStyle: React.CSSProperties =
                renderType === "csv" || renderType === "json" || renderType === "yaml" || renderType === "markdown" ? { maxHeight: "400px", overflowY: "auto" } : {};

            return (
                <div className="relative group max-w-2xl my-2 border rounded-lg overflow-hidden bg-background ml-4">
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

    return <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} className="ml-4" isEmbedded={isEmbedded} />;
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

    return (
        <div className={`flex flex-shrink items-center gap-2 rounded-lg bg-[var(--accent-background)] px-2 py-1 h-11 max-w-xs ${className || ""}`}>
            {FileIcon}
            <span className="min-w-0 flex-1 truncate text-sm leading-9" title={filename}>
                <strong>
                    <code>{filename}</code>
                </strong>
            </span>

            {artifact && !isEmbedded && (
                <Button
                    variant="ghost"
                    onClick={e => {
                        e.stopPropagation();
                        openSidePanelTab("files");
                        setPreviewArtifact(artifact);
                    }}
                    tooltip="Preview"
                >
                    <Eye className="h-4 w-4" />
                </Button>
            )}

            {onDownload && (
                <Button variant="ghost" onClick={() => onDownload()} tooltip="Download file">
                    <Download className="h-4 w-4" />
                </Button>
            )}
        </div>
    );
};
