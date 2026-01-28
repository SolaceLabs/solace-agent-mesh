import React, { useCallback, useEffect, useMemo, useState } from "react";

import { useChatContext, useArtifactRendering } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import type { FileAttachment, MessageFE } from "@/lib/types";
import { api } from "@/lib/api";
import { isDeepResearchReportFilename } from "@/lib/utils/deepResearchUtils";
import { downloadFile, parseArtifactUri } from "@/lib/utils/download";
import { Spinner } from "@/lib/components/ui/spinner";

import { MessageBanner } from "../../common";
import { ContentRenderer } from "../preview/ContentRenderer";
import { getFileContent, getRenderType } from "../preview/previewUtils";
import { ArtifactBar } from "../artifact/ArtifactBar";
import { ArtifactTransitionOverlay } from "../artifact/ArtifactTransitionOverlay";
import { FileDetails } from "./FileDetails";

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
    isStreaming?: boolean;
    message?: MessageFE; // Optional message to get taskId for ragData lookup
};

export const ArtifactMessage: React.FC<ArtifactMessageProps> = props => {
    const { artifacts, setPreviewArtifact, openSidePanelTab, sessionId, openDeleteModal, markArtifactAsDisplayed, downloadAndResolveArtifact, navigateArtifactVersion, ragData } = useChatContext();
    const { activeProject } = useProjectContext();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const [renderError, setRenderError] = useState<string | null>(null);
    const [isInfoExpanded, setIsInfoExpanded] = useState(false);
    const [isDownloading, setIsDownloading] = useState(false);

    const artifact = useMemo(() => artifacts.find(art => art.filename === props.name), [artifacts, props.name]);
    const context = props.context || "chat";
    const isStreaming = props.isStreaming;

    // Check if this artifact is from a project (should not be deletable)
    const isProjectArtifact = artifact?.source === "project";

    // Extract version from URI if available
    const version = useMemo(() => {
        const fileAttachment = props.status === "completed" ? props.fileAttachment : undefined;
        if (fileAttachment?.uri) {
            const parsed = parseArtifactUri(fileAttachment.uri);
            return parsed?.version !== null && parsed?.version !== undefined ? parseInt(parsed.version) : undefined;
        }
        return undefined;
    }, [props]);

    // Get file info for rendering decisions
    const fileAttachment = props.status === "completed" ? props.fileAttachment : undefined;
    const fileName = fileAttachment?.name || props.name;
    const fileMimeType = fileAttachment?.mime_type;

    // Detect if artifact has been deleted: completed but not in artifacts list
    const isDeleted = useMemo(() => {
        return props.status === "completed" && !artifact;
    }, [props.status, artifact]);

    // Determine if this should auto-expand based on context
    const shouldAutoExpand = useMemo(() => {
        // Don't auto-expand deleted artifacts
        if (isDeleted) {
            return false;
        }

        // Don't auto-expand deep research reports - they are shown inline without expander
        if (isDeepResearchReportFilename(fileName)) {
            return false;
        }

        const renderType = getRenderType(fileName, fileMimeType);
        const isAutoRenderType = renderType === "image" || renderType === "audio" || renderType === "markdown";

        // Check if it's specifically a .txt file (not other text-based files like code, XML, etc.)
        const isTxtFile = fileName.toLowerCase().endsWith(".txt") || fileName.toLowerCase().endsWith(".text");
        const shouldAutoExpandText = renderType === "text" && isTxtFile;

        // Only auto-expand images/audio/markdown/.txt files in chat context, never in list context
        return (isAutoRenderType || shouldAutoExpandText) && context === "chat";
    }, [fileName, fileMimeType, context, isDeleted]);

    // Use the artifact rendering hook to determine rendering behavior
    // This uses local state, so each component instance has its own expansion state
    const { shouldRender, isExpandable, isExpanded, toggleExpanded } = useArtifactRendering({
        filename: fileName,
        mimeType: fileMimeType,
        shouldAutoExpand,
    });

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
            downloadFile(fileToDownload, sessionId, activeProject?.id);
        } else {
            console.error(`No file to download for artifact: ${props.name}`);
        }
    }, [artifact, fileAttachment, sessionId, activeProject?.id, props.name]);

    const handleDeleteClick = useCallback(() => {
        if (artifact) {
            openDeleteModal(artifact);
        }
    }, [artifact, openDeleteModal]);

    const handleInfoClick = useCallback(() => {
        setIsInfoExpanded(!isInfoExpanded);
    }, [isInfoExpanded]);

    // Mark artifact as displayed when rendered
    useEffect(() => {
        const filename = artifact?.filename;
        if (shouldRender && filename) {
            markArtifactAsDisplayed(filename, true);
        }

        return () => {
            // Unmark when component unmounts or stops rendering
            if (filename) {
                markArtifactAsDisplayed(filename, false);
            }
        };
    }, [shouldRender, artifact?.filename, markArtifactAsDisplayed]);

    // Check if this is specifically an image for special styling
    const isImage = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "image";
    }, [fileName, fileMimeType]);

    // Check if this is text or markdown for no-scroll expansion
    const isTextOrMarkdown = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "text" || renderType === "markdown";
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

                const { sessionId: uriSessionId, filename, version } = parsedUri;

                // Construct API URL based on context
                // Priority 1: Session ID from URI (artifact was created in this session)
                // Priority 2: Current session context (active chat)
                // Priority 3: Project context (pre-session, project artifacts)
                let apiUrl: string;
                const effectiveSessionId = uriSessionId || sessionId;
                if (effectiveSessionId && effectiveSessionId.trim() && effectiveSessionId !== "null" && effectiveSessionId !== "undefined") {
                    apiUrl = `/api/v1/artifacts/${effectiveSessionId}/${encodeURIComponent(filename)}/versions/${version || "latest"}`;
                }
                // Priority 3: Project context (pre-session, project artifacts)
                else if (activeProject?.id) {
                    apiUrl = `/api/v1/artifacts/null/${encodeURIComponent(filename)}/versions/${version || "latest"}?project_id=${activeProject.id}`;
                }
                // Fallback: no context (will likely fail but let backend handle it)
                else {
                    apiUrl = `/api/v1/artifacts/null/${encodeURIComponent(filename)}/versions/${version || "latest"}`;
                }

                const response = await api.webui.get(apiUrl, { fullResponse: true });
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
    }, [props.status, shouldRender, fileAttachment, sessionId, activeProject?.id, isLoading, fetchedContent, artifact?.accumulatedContent, fileName, isExpanded, artifact]);

    // Get ragData for this task if message is provided
    const taskRagData = useMemo(() => {
        if (!props.message?.taskId || !ragData) return undefined;
        return ragData.find(r => r.taskId === props.message?.taskId);
    }, [props.message?.taskId, ragData]);

    // Prepare actions for the artifact bar
    const actions = useMemo(() => {
        if (props.status === "failed") return undefined;

        if (context === "list") {
            return {
                onInfo: handleInfoClick,
                onDownload: props.status === "completed" ? handleDownloadClick : undefined,
                // Hide delete button for artifacts with source="project" (they came from project files)
                onDelete: artifact && props.status === "completed" && !isProjectArtifact ? handleDeleteClick : undefined,
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
    }, [props.status, context, handleDownloadClick, artifact, handleDeleteClick, handleInfoClick, handlePreviewClick, isProjectArtifact]);

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
                // @ts-expect-error - Add flag to indicate if content is plain text from streaming
                // Content is plain text if: (1) it's from accumulated content during streaming, OR (2) we're in progress state
                isPlainText: (artifact?.isAccumulatedContentPlainText && fetchedContent === artifact?.accumulatedContent) || (props.status === "in-progress" && !!fetchedContent),
            });

            if (finalContent) {
                // Determine max height and overflow behavior based on content type
                let maxHeight: string;
                let height: string | undefined;
                let overflowY: "visible" | "auto";

                if (isImage) {
                    // Images: no height limit, no scroll
                    maxHeight = "none";
                    overflowY = "visible";
                } else if (isTextOrMarkdown) {
                    // Text/Markdown: safety max height of 6000px, scroll if overflow (auto-expanded)
                    maxHeight = "6000px";
                    overflowY = "auto";
                } else if (renderType === "audio") {
                    // Audio: 300px with scroll (auto-expanded)
                    maxHeight = "300px";
                    overflowY = "auto";
                } else if (renderType === "html") {
                    // HTML: fixed height of 900px (iframes need explicit height, not maxHeight)
                    height = "600px";
                    maxHeight = "600px";
                    overflowY = "auto";
                } else {
                    // All other types (CSV, JSON, YAML, Mermaid, etc.): 900px with scroll
                    maxHeight = "600px";
                    overflowY = "auto";
                }

                expandedContent = (
                    <div className="group relative max-w-full overflow-hidden">
                        {renderError && <MessageBanner variant="error" message={renderError} />}
                        <div
                            style={{
                                height,
                                maxHeight,
                                overflowY,
                            }}
                            className={isImage ? "drop-shadow-md" : ""}
                        >
                            <ContentRenderer content={finalContent} rendererType={renderType} mime_type={fileAttachment?.mime_type} setRenderError={setRenderError} isStreaming={isStreaming} ragData={taskRagData} />
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

    // Show content when it should render and is expanded
    const shouldShowContent = shouldRender && isExpanded;

    // Prepare info content for expansion
    const infoContent = useMemo(() => {
        if (!isInfoExpanded || !artifact) return null;

        return <FileDetails description={artifact.description ?? undefined} size={artifact.size} lastModified={artifact.last_modified} mimeType={artifact.mime_type} />;
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
    }, [isInfoExpanded, infoContent, shouldShowContent, expandedContent]);

    // Render the bar with expanded content inside
    return (
        <ArtifactBar
            filename={fileName}
            description={description || ""}
            mimeType={fileMimeType}
            size={fileAttachment?.size}
            status={props.status}
            expandable={isExpandable && context === "chat" && !isDeepResearchReportFilename(fileName)} // Allow expansion in chat context for user-controllable files, but not for deep research reports (shown inline)
            expanded={isExpanded || isInfoExpanded}
            onToggleExpand={isExpandable && context === "chat" ? toggleExpanded : undefined}
            actions={actions}
            bytesTransferred={props.status === "in-progress" ? props.bytesTransferred : undefined}
            error={props.status === "failed" ? props.error : undefined}
            expandedContent={finalExpandedContent}
            context={context}
            isDeleted={isDeleted}
            version={version}
            source={artifact?.source}
        />
    );
};
