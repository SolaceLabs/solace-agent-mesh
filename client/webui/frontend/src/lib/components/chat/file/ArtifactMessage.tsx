import React, { useCallback, useEffect, useMemo, useState } from "react";

import { useChatContext, useArtifactRendering } from "@/lib/hooks";
import type { FileAttachment, ArtifactPart } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";
import { downloadFile, parseArtifactUri } from "@/lib/utils/download";
import { generateFileTypePreview } from "./fileUtils";

import { MessageBanner } from "../../common";
import { ContentRenderer } from "../preview/ContentRenderer";
import { getFileContent, getRenderType } from "../preview/previewUtils";
import { ArtifactBar } from "../artifact/ArtifactBar";

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
    console.log(`[ArtifactMessage] Rendering with props:`, props);
    console.log(`[ArtifactMessage] Props type check - status: ${props.status}, name: ${props.name}`);
    if (props.status === "in-progress") {
        console.log(`[ArtifactMessage] In-progress artifact - bytesTransferred: ${props.bytesTransferred}`);
    }
    const { artifacts, setPreviewArtifact, openSidePanelTab, sessionId, messages } = useChatContext();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const [renderError, setRenderError] = useState<string | null>(null);

    const artifact = useMemo(() => artifacts.find(art => art.filename === props.name), [artifacts, props.name]);

    // Get file info for rendering decisions
    const fileAttachment = props.status === "completed" ? props.fileAttachment : undefined;
    const fileName = fileAttachment?.name || props.name;
    const fileMimeType = fileAttachment?.mime_type;
    
    // Use the artifact rendering hook to determine rendering behavior
    const { shouldRender, isExpandable, isExpanded, toggleExpanded } = useArtifactRendering({
        filename: fileName,
        mimeType: fileMimeType
    });

    // Check if this should auto-render (images and audio)
    const shouldAutoRender = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "image" || renderType === "audio";
    }, [fileName, fileMimeType]);

    const handlePreviewClick = useCallback(() => {
        if (artifact) {
            openSidePanelTab("files");
            setPreviewArtifact(artifact);
        }
    }, [artifact, openSidePanelTab, setPreviewArtifact]);

    const handleDownloadClick = useCallback(() => {
        if (fileAttachment) {
            downloadFile(fileAttachment);
        }
    }, [fileAttachment]);

    // Auto-expand for images and audio when completed
    useEffect(() => {
        if (props.status === "completed" && shouldAutoRender && !isExpanded) {
            console.log(`[ArtifactMessage] Auto-expanding ${fileName} for auto-render`);
            toggleExpanded();
        }
    }, [props.status, shouldAutoRender, isExpanded, toggleExpanded, fileName]);

    // Check if we should render content inline (for images and audio)
    const shouldRenderInline = useMemo(() => {
        const renderType = getRenderType(fileName, fileMimeType);
        return renderType === "image" || renderType === "audio";
    }, [fileName, fileMimeType]);

    // Fetch content from URI for completed artifacts when needed for rendering
    useEffect(() => {
        const fetchContentFromUri = async () => {
            if (isLoading || fetchedContent || !shouldRender) {
                return;
            }

            const fileUri = fileAttachment?.uri;
            const fileContent = fileAttachment?.content;
            
            if (!fileUri || fileContent) {
                return; // Already have content or no URI to fetch from
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

        if (props.status === "completed" && shouldRender) {
            fetchContentFromUri();
        }
    }, [props.status, shouldRender, fileAttachment, sessionId, isLoading, fetchedContent]);

    // Generate content preview for the file icon
    const contentPreview = useMemo(() => {
        if (props.status === "completed" && fileAttachment) {
            try {
                const contentToUse = fetchedContent || fileAttachment.content;
                if (contentToUse) {
                    const decodedContent = getFileContent({ ...fileAttachment, content: contentToUse });
                    if (decodedContent) {
                        return generateFileTypePreview(decodedContent, fileName, fileMimeType);
                    }
                }
            } catch (error) {
                console.warn("Failed to generate content preview:", error);
                // Return fallback preview
                return `${fileName}\n${fileMimeType || 'Unknown type'}`;
            }
        }
        return undefined;
    }, [props.status, fileAttachment, fetchedContent, fileName, fileMimeType]);

    // Prepare actions for the artifact bar
    const actions = useMemo(() => {
        if (props.status !== "completed") return undefined;
        
        return {
            onDownload: handleDownloadClick,
            onPreview: artifact ? handlePreviewClick : undefined,
        };
    }, [props.status, handleDownloadClick, artifact, handlePreviewClick]);

    // Get description from global artifacts instead of message parts
    const artifactFromGlobal = useMemo(() => 
        artifacts.find(art => art.filename === props.name), 
        [artifacts, props.name]
    );
    
    const description = artifactFromGlobal?.description;

    // For rendering content, we need the actual content
    const contentToRender = fetchedContent || fileAttachment?.content;
    const renderType = getRenderType(fileName, fileMimeType);

    // Prepare expanded content if we have content to render
    let expandedContent: React.ReactNode = null;
    
    if (isLoading) {
        expandedContent = (
            <div className="p-4 h-24 flex items-center justify-center bg-muted">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            </div>
        );
    } else if (error) {
        expandedContent = <MessageBanner variant="error" message={error} />;
    } else if (contentToRender && renderType) {
        try {
            const finalContent = getFileContent({ ...fileAttachment!, content: contentToRender });
            if (finalContent) {
                expandedContent = (
                    <div className="relative group max-w-full overflow-hidden">
                        {renderError && <MessageBanner variant="error" message={renderError} />}
                        <div style={{ maxHeight: shouldRenderInline ? "300px" : "400px", overflowY: "auto" }}>
                            <ContentRenderer 
                                content={finalContent} 
                                rendererType={renderType} 
                                mime_type={fileAttachment?.mime_type} 
                                setRenderError={setRenderError} 
                            />
                        </div>
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

    // Render the bar with expanded content inside
    return (
        <ArtifactBar
            filename={fileName}
            description={description}
            mimeType={fileMimeType}
            size={fileAttachment?.size}
            status={props.status}
            expandable={isExpandable && !shouldRenderInline} // Don't show expand button for inline content
            expanded={shouldShowContent}
            onToggleExpand={isExpandable && !shouldRenderInline ? toggleExpanded : undefined}
            actions={actions}
            bytesTransferred={props.status === "in-progress" ? props.bytesTransferred : undefined}
            error={props.status === "failed" ? props.error : undefined}
            content={contentPreview}
            expandedContent={shouldShowContent ? expandedContent : undefined}
        />
    );
};
