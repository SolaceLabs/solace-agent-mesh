import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Download, Eye, FileText, Loader2 } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { FileAttachment } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";
import { downloadFile, parseArtifactUri } from "@/lib/utils/download";
import { formatBytes } from "@/lib/utils/format";
import { cn } from "@/lib/utils";

import { MessageBanner } from "../../common";
import { ContentRenderer } from "../preview/ContentRenderer";
import { getFileContent, getRenderType } from "../preview/previewUtils";
import { FileMessage } from "./FileMessage";

const INLINE_RENDERABLE_TYPES = ["image", "audio", "markdown", "csv", "json", "yaml", "text"];

type ArtifactMessageProps =
    | {
          status: "in-progress";
          name: string;
          bytesTransferred: number;
      }
    | {
          status: "completed";
          name: string;
          fileAttachment: FileAttachment;
      }
    | {
          status: "failed";
          name: string;
          error?: string;
      };

export const ArtifactMessage: React.FC<ArtifactMessageProps> = props => {
    const { artifacts, setPreviewArtifact, openSidePanelTab, sessionId } = useChatContext();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const [renderError, setRenderError] = useState<string | null>(null);

    const artifact = useMemo(() => artifacts.find(art => art.filename === props.name), [artifacts, props.name]);

    const handlePreviewClick = useCallback(() => {
        if (artifact) {
            openSidePanelTab("files");
            setPreviewArtifact(artifact);
        }
    }, [artifact, openSidePanelTab, setPreviewArtifact]);

    // Fetch content from URI for completed artifacts
    useEffect(() => {
        const fetchContentFromUri = async (fileAttachment: FileAttachment) => {
            const renderType = getRenderType(fileAttachment.name, fileAttachment.mime_type);
            if (!fileAttachment.uri || !renderType || !INLINE_RENDERABLE_TYPES.includes(renderType)) {
                return;
            }

            setIsLoading(true);
            setError(null);

            try {
                const parsedUri = parseArtifactUri(fileAttachment.uri);
                if (!parsedUri) throw new Error("Invalid artifact URI.");

                const { filename, version } = parsedUri;
                const apiUrl = `/api/v1/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions/${version || "latest"}`;

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

        if (props.status === "completed" && props.fileAttachment.uri && !props.fileAttachment.content) {
            fetchContentFromUri(props.fileAttachment);
        }
    }, [props, sessionId]);

    switch (props.status) {
        case "in-progress":
            return (
                <div className="ml-4 flex max-w-xs items-center gap-2 rounded-lg bg-[var(--accent-background)] px-2 py-1 h-11">
                    <FileText className="h-4 w-4 flex-shrink-0" />
                    <div className="min-w-0 flex-1 truncate">
                        <div className="text-sm font-semibold" title={props.name}>
                            <code>{props.name}</code>
                        </div>
                        <div className="text-xs text-muted-foreground">Authoring artifact... {formatBytes(props.bytesTransferred)}</div>
                    </div>
                    <Loader2 className="h-4 w-4 animate-spin" />
                </div>
            );

        case "failed":
            return (
                <div className="ml-4 flex max-w-xs items-center gap-2 rounded-lg bg-destructive/10 px-2 py-1 h-11 text-destructive">
                    <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                    <div className="min-w-0 flex-1 truncate">
                        <div className="text-sm font-semibold" title={props.name}>
                            <code>{props.name}</code>
                        </div>
                        <div className="text-xs">Failed to create artifact</div>
                    </div>
                </div>
            );

        case "completed": {
            const { fileAttachment } = props;
            const renderType = getRenderType(fileAttachment.name, fileAttachment.mime_type);
            const contentToRender = fetchedContent || fileAttachment.content;

            const renderFallbackBadge = () => <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} className="ml-4" />;

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

                    const scrollableRenderTypes = ["csv", "json", "yaml", "markdown", "text"];
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
                            <div className="absolute top-2 right-2 z-20 flex items-center gap-0.5 rounded-md bg-black/60 p-0.5 opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100 dark:bg-zinc-200/60">
                                {artifact && (
                                    <Button variant="ghost" size="icon" className="h-7 w-7 text-white hover:bg-white/20 dark:text-zinc-900 dark:hover:bg-black/10 dark:hover:text-zinc-900" onClick={handlePreviewClick} tooltip="Preview">
                                        <Eye className="h-4 w-4" />
                                    </Button>
                                )}
                                <Button variant="ghost" size="icon" className="h-7 w-7 text-white hover:bg-white/20 dark:text-zinc-900 dark:hover:bg-black/10 dark:hover:text-zinc-900" onClick={() => downloadFile(fileAttachment)} tooltip="Download">
                                    <Download className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    );
                }
            }

            return renderFallbackBadge();
        }

        default:
            return null;
    }
};
