import React, { useState, useEffect, useMemo } from "react";

import { Loader2 } from "lucide-react";

import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo } from "@/lib/types";

import { MessageBanner } from "../../common";
import { ContentRenderer } from "../preview/ContentRenderer";
import { canPreviewArtifact, getFileContent, getRenderType } from "../preview/previewUtils";
import { ArtifactPreviewDownload } from "./ArtifactPreviewDownload";

const EmptyState: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
    return <div className="text-muted-foreground flex h-[50vh] items-center justify-center">{children || "No preview available"}</div>;
};

export const ArtifactPreviewContent: React.FC<{ artifact: ArtifactInfo }> = ({ artifact }) => {
    const { openArtifactForPreview, previewFileContent } = useChatContext();
    const preview = useMemo(() => canPreviewArtifact(artifact), [artifact]);

    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setIsLoading(false);
        setError(null);
    }, [artifact]);

    useEffect(() => {
        async function fetchData() {
            try {
                setIsLoading(true);
                setError(null);

                await openArtifactForPreview(artifact.filename);
            } catch (err) {
                console.error("Error fetching artifact content:", err);
                setError(err instanceof Error ? err.message : "Failed to load artifact content");
            } finally {
                setIsLoading(false);
            }
        }

        if (preview?.canPreview) {
            fetchData();
        }
    }, [artifact, openArtifactForPreview, preview]);

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

    const rendererType = getRenderType(artifact.filename, artifact.mime_type);
    const content = getFileContent(previewFileContent);

    if (!rendererType || !content) {
        return <EmptyState>No preview available</EmptyState>;
    }

    return <ContentRenderer content={content} rendererType={rendererType} mime_type={previewFileContent?.mime_type} setRenderError={setError} />;
};
