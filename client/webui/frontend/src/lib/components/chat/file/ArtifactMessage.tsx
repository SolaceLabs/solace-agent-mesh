import React, { useCallback, useEffect, useMemo, useState } from "react";

import { useChatContext, useArtifactRendering } from "@/lib/hooks";
import type { FileAttachment } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";
import { downloadFile, parseArtifactUri } from "@/lib/utils/download";
import { formatBytes, formatRelativeTime } from "@/lib/utils/format";

import { MessageBanner } from "../../common";
import { ContentRenderer } from "../preview/ContentRenderer";
import { getFileContent, getRenderType } from "../preview/previewUtils";
import { ArtifactBar } from "../artifact/ArtifactBar";
import { ArtifactTransitionOverlay } from "../artifact/ArtifactTransitionOverlay";
import { Spinner } from "../../ui";

type ArtifactMessageProps = (
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
    }
) & {
    context?: "chat" | "list";
    uniqueKey?: string; // Optional unique key for expansion state (e.g., taskId-filename)
};

export const ArtifactMessage: React.FC<ArtifactMessageProps> = props => {
    const { artifacts, setPreviewArtifact, openSidePanelTab, sessionId, openDeleteModal, markArtifactAsDisplayed, downloadAndResolveArtifact, navigateArtifactVersion } = useChatContext();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const [renderError, setRenderError] = useState<string | null>(null);
    const [isInfoExpanded, setIsInfoExpanded] = useState(false);
    const [isDownloading, setIsDownloading] = useState(false);

    const artifact = useMemo(() => artifacts.find(art => art.filename === props.name), [artifacts, props.name]);
    const context = props.context || "chat";

    // Extract version from URI if available
    const version = useMemo(() => {
        const fileAttachment = props.status === "completed" ? props.fileAttachment : undefined;
        if (fileAttachment?.uri) {
            const parsed = parseArtifactUri(fileAttachment.uri);
            return parsed?.version !== null && parsed?.version !== undefined ? parseInt(parsed.version) : undefined;
        }
        return undefined;
    }, [props.status, props.status === "completed" ? props.fileAttachment : undefined]);

    // Get file info for rendering decisions
    const fileAttachment = props.status === "completed" ? props.fileAttachment : undefined;
    const fileName = fileAttachment?.name || props.name;
    const fileMimeType = fileAttachment?.mime_type;

    // Detect if artifact has been deleted: completed but not in artifacts list
    const isDeleted = useMemo(() => {
        return props.status === "completed" && !artifact;
    }, [props.status, artifact]);

    // Use the artifact rendering hook to determine rendering behavior
    // This uses local state, so each component instance has its own expansion state
    const { shouldRender, isExpandable, isExpanded, toggleExpanded } = useArtifactRendering({
        filename: fileName,
        mimeType: fileMimeType,
    });

    // Check if this should auto-render (images and audio)
    const shouldAutoRender = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "image" || renderType === "audio";
    }, [fileName, fileMimeType]);

    const handlePreviewClick = useCallback(async () => {
        if (artifact) {
            openSidePanelTab("files");
            setPreviewArtifact(artifact);

            // If this artifact has a specific version from the chat message, navigate to it
            if (version !== undefined) {
                // Wait a bit for the preview to open, then navigate to the specific version
                setTimeout(async () => {
                    await navigateArtifactVersion(artifact.filename, version);
                }, 100);
            }
        }
    }, [artifact, openSidePanelTab, setPreviewArtifact, version, navigateArtifactVersion]);

    const handleDownloadClick = useCallback(() => {
        // Build the file to download from available sources
        let fileToDownload: FileAttachment | null = null;

        // Try to use artifact from global state (has URI) or fileAttachment prop (might have content)
        if (artifact) {
            fileToDownload = {
                name: artifact.filename,
                mime_type: artifact.mime_type,
                uri: artifact.uri,
                size: artifact.size,
                last_modified: artifact.last_modified,
            };
            // If artifact doesn't have URI, try to use content from fileAttachment
            if (!fileToDownload.uri && fileAttachment?.content) {
                fileToDownload.content = fileAttachment.content;
            }
        } else if (fileAttachment) {
            fileToDownload = fileAttachment;
        }

        if (fileToDownload) {
            downloadFile(fileToDownload, sessionId);
        } else {
            console.error(`No file to download for artifact: ${props.name}`);
        }
    }, [artifact, fileAttachment, sessionId]);

    const handleDeleteClick = useCallback(() => {
        if (artifact) {
            openDeleteModal(artifact);
        }
    }, [artifact, openDeleteModal]);

    const handleInfoClick = useCallback(() => {
        setIsInfoExpanded(!isInfoExpanded);
    }, [isInfoExpanded]);

    // Auto-expand for images and audio when completed
    useEffect(() => {
        if (props.status === "completed" && shouldAutoRender && !isExpanded) {
            toggleExpanded();
        }
    }, [props.status, shouldAutoRender, isExpanded, fileName, toggleExpanded]);

    // Mark artifact as displayed when rendered
    useEffect(() => {
        if (shouldRender && artifact) {
            markArtifactAsDisplayed(artifact.filename, true);
        }

        return () => {
            // Unmark when component unmounts or stops rendering
            if (artifact) {
                markArtifactAsDisplayed(artifact.filename, false);
            }
        };
    }, [shouldRender, fileName, markArtifactAsDisplayed]); // Only depend on filename, not the whole artifact object

    // Check if we should render content inline (for images and audio)
    const shouldRenderInline = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "image" || renderType === "audio";
    }, [fileName, fileMimeType]);

    // Check if this is specifically an image for special styling
    const isImage = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "image";
    }, [fileName, fileMimeType]);

    // Update fetched content when accumulated content changes (for progressive rendering during streaming)
    useEffect(() => {
        if (props.status === "in-progress" && artifact?.accumulatedContent && shouldRender) {
            setFetchedContent(artifact.accumulatedContent);
        }
    }, [artifact?.accumulatedContent, props.status, fileName, shouldRender, isExpanded]);

    // Trigger download when artifact completes and needs embed resolution
    useEffect(() => {
        const triggerDownload = async () => {
            if (artifact?.needsEmbedResolution && props.status === "completed" && shouldRender && !isDownloading) {
                setIsDownloading(true);
                try {
                    const fileData = await downloadAndResolveArtifact(artifact.filename);
                    if (fileData?.content) {
                        setFetchedContent(fileData.content);
                    }
                } catch (err) {
                    console.error(`Error downloading ${fileName}:`, err);
                } finally {
                    setIsDownloading(false);
                }
            }
        };

        triggerDownload();
    }, [artifact?.needsEmbedResolution, props.status, shouldRender, fileName, artifact?.filename, downloadAndResolveArtifact, isDownloading]);

    // Fetch content from URI for completed artifacts when needed for rendering
    useEffect(() => {
        const fetchContentFromUri = async () => {
            if (isLoading || !shouldRender) {
                return;
            }

            // For in-progress artifacts, only use accumulated content if available
            if (props.status === "in-progress") {
                if (artifact?.accumulatedContent) {
                    setFetchedContent(artifact.accumulatedContent);
                }
                return;
            }

            // For completed artifacts, proceed with full content fetching
            if (props.status !== "completed") {
                return;
            }

            // If we have accumulated content, use it (download will happen separately)
            if (artifact?.accumulatedContent) {
                setFetchedContent(artifact.accumulatedContent);
                return;
            }

            // Check if we already have fetched content or content from fileAttachment
            const fileContent = fileAttachment?.content;
            if (fetchedContent || fileContent) {
                if (fileContent && !fetchedContent) {
                    setFetchedContent(fileContent);
                }
                return;
            }

            const fileUri = fileAttachment?.uri;
            if (!fileUri) {
                return; // No URI to fetch from
            }

            setIsLoading(true);
            setError(null);

            try {
                const parsedUri = parseArtifactUri(fileUri);
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

        fetchContentFromUri();
    }, [props.status, shouldRender, fileAttachment, sessionId, isLoading, fetchedContent, artifact?.accumulatedContent, fileName, isExpanded, artifact]);

    // Prepare actions for the artifact bar
    const actions = useMemo(() => {
        if (props.status === "failed") return undefined;

        if (context === "list") {
            return {
                onInfo: handleInfoClick,
                onDownload: props.status === "completed" ? handleDownloadClick : undefined,
                onDelete: artifact && props.status === "completed" ? handleDeleteClick : undefined,
            };
        } else {
            // In chat context, show preview, download, and info actions
            // Expand is handled via expandable/onToggleExpand props, not actions
            return {
                onPreview: props.status === "completed" ? handlePreviewClick : undefined,
                onDownload: props.status === "completed" ? handleDownloadClick : undefined,
                onInfo: handleInfoClick,
            };
        }
    }, [props.status, context, handleDownloadClick, artifact, handleDeleteClick, handleInfoClick, handlePreviewClick, isExpandable, toggleExpanded]);

    // Get description from global artifacts instead of message parts
    const artifactFromGlobal = useMemo(() => artifacts.find(art => art.filename === props.name), [artifacts, props.name]);

    const description = artifactFromGlobal?.description;

    // For rendering content, we need the actual content
    const contentToRender = fetchedContent || fileAttachment?.content;
    const renderType = getRenderType(fileName, fileMimeType);

    // Prepare expanded content if we have content to render
    let expandedContent: React.ReactNode = null;

    if (isLoading) {
        expandedContent = (
            <div className="bg-muted flex h-25 items-center justify-center">
                <Spinner />
            </div>
        );
    } else if (error) {
        expandedContent = <MessageBanner variant="error" message={error} />;
    } else if (contentToRender && renderType) {
        try {
            // For in-progress artifacts, fileAttachment may be undefined, so create a minimal one
            const fileForRendering: FileAttachment = fileAttachment || {
                name: fileName,
                mime_type: fileMimeType,
            };

            const finalContent = getFileContent({
                ...fileForRendering,
                content: contentToRender,
                // @ts-ignore - Add flag to indicate if content is plain text from streaming
                // Content is plain text if: (1) it's from accumulated content during streaming, OR (2) we're in progress state
                isPlainText: (artifact?.isAccumulatedContentPlainText && fetchedContent === artifact?.accumulatedContent) ||
                             (props.status === "in-progress" && !!fetchedContent)
            });

            if (finalContent) {
                expandedContent = (
                    <div className="group relative max-w-full overflow-hidden">
                        {renderError && <MessageBanner variant="error" message={renderError} />}
                        <div
                            style={{
                                maxHeight: shouldRenderInline && !isImage ? "300px" : isImage ? "none" : "400px",
                                overflowY: isImage ? "visible" : "auto",
                            }}
                            className={isImage ? "drop-shadow-md" : ""}
                        >
                            <ContentRenderer content={finalContent} rendererType={renderType} mime_type={fileAttachment?.mime_type} setRenderError={setRenderError} />
                        </div>
                        <ArtifactTransitionOverlay isVisible={isDownloading} message="Resolving embeds..." />
                    </div>
                );
            }
        } catch (error) {
            console.error("Failed to process file content:", error);
            expandedContent = <MessageBanner variant="error" message="Failed to process file content for rendering" />;
        }
    }

    // For inline rendering (images/audio), always show the content regardless of expansion state
    const shouldShowContent = shouldRenderInline || (shouldRender && isExpanded);

    // Prepare info content for expansion
    const infoContent = useMemo(() => {
        if (!isInfoExpanded || !artifact) return null;

        return (
            <div className="space-y-2 text-sm">
                {artifact.description && (
                    <div>
                        <span className="text-secondary-foreground">Description:</span>
                        <div className="mt-1">{artifact.description}</div>
                    </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                    <div>
                        <span className="text-secondary-foreground">Size:</span>
                        <div>{formatBytes(artifact.size)}</div>
                    </div>
                    <div>
                        <span className="text-secondary-foreground">Modified:</span>
                        <div>{formatRelativeTime(artifact.last_modified)}</div>
                    </div>
                </div>
                {artifact.mime_type && (
                    <div>
                        <span className="text-secondary-foreground">Type:</span>
                        <div>{artifact.mime_type}</div>
                    </div>
                )}
                {artifact.uri && (
                    <div>
                        <span className="text-secondary-foreground">URI:</span>
                        <div className="text-xs break-all">{artifact.uri}</div>
                    </div>
                )}
            </div>
        );
    }, [isInfoExpanded, artifact]);

    // Determine what content to show in expanded area - can show both info and content
    const finalExpandedContent = useMemo(() => {
        const hasInfo = isInfoExpanded && infoContent;
        const hasContent = shouldShowContent && expandedContent;

        if (hasInfo && hasContent) {
            return (
                <div className="space-y-4">
                    {infoContent}
                    <hr className="border-t" />
                    {expandedContent}
                </div>
            );
        }

        if (hasInfo) {
            return infoContent;
        }

        if (hasContent) {
            return expandedContent;
        }

        return undefined;
    }, [isInfoExpanded, infoContent, shouldShowContent, expandedContent, fileName]);

    // Render the bar with expanded content inside
    return (
        <ArtifactBar
            filename={fileName}
            description={description || ""}
            mimeType={fileMimeType}
            size={fileAttachment?.size}
            status={props.status}
            expandable={isExpandable && context === "chat"} // Allow expansion in chat context for user-controllable files
            expanded={shouldShowContent || isInfoExpanded}
            onToggleExpand={isExpandable && context === "chat" ? toggleExpanded : undefined}
            actions={actions}
            bytesTransferred={props.status === "in-progress" ? props.bytesTransferred : undefined}
            error={props.status === "failed" ? props.error : undefined}
            expandedContent={finalExpandedContent}
            context={context}
            isDeleted={isDeleted}
            version={version}
        />
    );
};
