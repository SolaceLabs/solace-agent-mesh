import React, { useState, useEffect, useMemo, useRef } from "react";

import { Loader2 } from "lucide-react";

import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";
import { isDeepResearchReportFilename } from "@/lib/utils/deepResearchUtils";

import { MessageBanner } from "../../common";
import { ContentRenderer } from "../preview/ContentRenderer";
import { canPreviewArtifact, getFileContent, getRenderType } from "../preview/previewUtils";
import { ArtifactPreviewDownload } from "./ArtifactPreviewDownload";
import { ArtifactTransitionOverlay } from "./ArtifactTransitionOverlay";

const EmptyState: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
    return <div className="text-muted-foreground flex h-[50vh] items-center justify-center">{children || "No preview available"}</div>;
};

export const ArtifactPreviewContent: React.FC<{ artifact: ArtifactInfo }> = ({ artifact }) => {
    const { openArtifactForPreview, previewFileContent, markArtifactAsDisplayed, downloadAndResolveArtifact, ragData } = useChatContext();
    const preview = useMemo(() => canPreviewArtifact(artifact), [artifact]);

    // Find RAG data for deep research reports
    // The RAG metadata stores the artifact filename to associate sources with the report
    const artifactRagData = useMemo(() => {
        if (!isDeepResearchReportFilename(artifact.filename) || !ragData || ragData.length === 0) {
            return undefined;
        }

        // Find RAG data where the artifact filename matches
        const matchingRagData = ragData.find(r => {
            const artifactFilenameFromRag = r.metadata?.artifactFilename as string | undefined;
            return artifactFilenameFromRag === artifact.filename;
        });

        // If no direct match, try to find deep research RAG data (fallback for single report scenarios)
        if (!matchingRagData) {
            const deepResearchRagData = ragData.filter(r => r.searchType === "deep_research");
            if (deepResearchRagData.length === 1) {
                return deepResearchRagData[0];
            }
        }

        return matchingRagData;
    }, [artifact.filename, ragData]);

    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [cachedContent, setCachedContent] = useState<FileAttachment | null>(null);
    const [isDownloading, setIsDownloading] = useState(false);

    // Track in-flight fetches to prevent duplicate requests
    const isFetchingRef = useRef(false);
    const lastFetchedFilenameRef = useRef<string | null>(null);
    const isDownloadingRef = useRef(false);

    // Mark artifact as displayed when preview opens
    useEffect(() => {
        markArtifactAsDisplayed(artifact.filename, true);

        return () => {
            markArtifactAsDisplayed(artifact.filename, false);
        };
    }, [artifact.filename, markArtifactAsDisplayed]);

    useEffect(() => {
        setIsLoading(false);
        setError(null);
        setCachedContent(null);
        // Reset fetch tracking when filename changes
        isFetchingRef.current = false;
        lastFetchedFilenameRef.current = null;
    }, [artifact.filename]); // Only depend on filename to avoid infinite loops

    // Update cached content when accumulated content changes (for progressive rendering)
    useEffect(() => {
        if (artifact.accumulatedContent) {
            const cachedFile: FileAttachment = {
                name: artifact.filename,
                mime_type: artifact.mime_type,
                content: artifact.accumulatedContent,
                last_modified: artifact.last_modified,
                // @ts-expect-error - Add custom property to track if content is plain text
                isPlainText: artifact.isAccumulatedContentPlainText,
            };
            setCachedContent(cachedFile);
        }
    }, [artifact.accumulatedContent, artifact.filename, artifact.mime_type, artifact.last_modified, artifact.isAccumulatedContentPlainText]);

    // Fetch data when preview opens or filename changes
    useEffect(() => {
        async function fetchData() {
            // Prevent duplicate fetches in React Strict Mode and rapid re-renders
            if (isFetchingRef.current && lastFetchedFilenameRef.current === artifact.filename) {
                return;
            }

            // Mark as fetching
            isFetchingRef.current = true;
            lastFetchedFilenameRef.current = artifact.filename;

            try {
                setIsLoading(true);
                setError(null);

                if (!artifact.accumulatedContent) {
                    // No cached content, fetch from backend
                    await openArtifactForPreview(artifact.filename);
                } else {
                    // Already have cached content from streaming
                    setIsLoading(false);
                }
            } catch (err) {
                console.error("Error fetching artifact content:", err);
                setError(err instanceof Error ? err.message : "Failed to load artifact content");
            } finally {
                setIsLoading(false);
                // Keep isFetchingRef.current as true to prevent re-fetches for the same file
            }
        }

        if (preview?.canPreview) {
            fetchData();
        }
    }, [artifact.filename, openArtifactForPreview, preview, artifact.accumulatedContent]);

    // Trigger download for embed resolution when artifact completes
    useEffect(() => {
        async function triggerDownload() {
            // Prevent duplicate downloads in React Strict Mode and rapid re-renders
            if (artifact.needsEmbedResolution && !isDownloading && !isDownloadingRef.current) {
                isDownloadingRef.current = true;
                setIsDownloading(true);
                try {
                    const resolvedContent = await downloadAndResolveArtifact(artifact.filename);
                    if (resolvedContent) {
                        // Add isPlainText: false because downloaded content is base64
                        setCachedContent({ ...resolvedContent, isPlainText: false } as FileAttachment & { isPlainText: boolean });
                    }
                } catch (err) {
                    console.error(`[ArtifactPreviewContent] Error downloading ${artifact.filename}:`, err);
                } finally {
                    setIsDownloading(false);
                    isDownloadingRef.current = false;
                }
            }
        }

        triggerDownload();
    }, [artifact.needsEmbedResolution, artifact.filename, downloadAndResolveArtifact, isDownloading]);

    if (error) {
        return (
            <div className="flex h-full w-full flex-col">
                <MessageBanner variant="error" message="Error rendering preview" />
                <EmptyState>No preview available</EmptyState>
            </div>
        );
    }

    if (isLoading) {
        return (
            <EmptyState>
                <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
            </EmptyState>
        );
    }

    if (!preview.canPreview) {
        return <ArtifactPreviewDownload artifact={artifact} message={preview.reason ?? ""} />;
    }

    // Use cached content if available, otherwise fall back to previewFileContent
    // But only if it matches the current artifact filename to avoid showing stale content
    const contentSource = cachedContent || (previewFileContent?.name === artifact.filename ? previewFileContent : null);
    // Use MIME type from contentSource (version-specific) if available, otherwise fall back to artifact.mime_type
    // This ensures each version is rendered according to its own MIME type, not the latest version's
    const effectiveMimeType = contentSource?.mime_type || artifact.mime_type;
    const rendererType = getRenderType(artifact.filename, effectiveMimeType);
    const content = getFileContent(contentSource);

    if (!rendererType || !content) {
        return <EmptyState>No preview available</EmptyState>;
    }

    return (
        <div className="relative h-full w-full">
            <ContentRenderer content={content} rendererType={rendererType} mime_type={contentSource?.mime_type} setRenderError={setError} ragData={artifactRagData} />
            <ArtifactTransitionOverlay isVisible={isDownloading} message="Resolving embeds..." />
        </div>
    );
};
