import React, { useEffect, useState, useMemo } from "react";

import { MarkdownRenderer } from "@/lib/components/chat/preview/Renderers";
import { stripReportMetadataSections, isDeepResearchReportFilename } from "@/lib/utils/deepResearchUtils";
import { api } from "@/lib/api";
import { parseArtifactUri } from "@/lib/utils/download";
import type { ArtifactInfo, RAGSearchResult } from "@/lib/types";

interface DeepResearchReportContentProps {
    artifact: ArtifactInfo;
    sessionId: string;
    ragData?: RAGSearchResult;
    onContentLoaded?: (content: string) => void;
}

export const DeepResearchReportContent: React.FC<DeepResearchReportContentProps> = ({ artifact, sessionId, ragData, onContentLoaded }) => {
    const [content, setContent] = useState<string | null>(null);
    const [loadedFilename, setLoadedFilename] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isDeepResearchReport = useMemo(() => {
        return isDeepResearchReportFilename(artifact.filename);
    }, [artifact.filename]);

    // Reset content when artifact changes
    useEffect(() => {
        if (loadedFilename && loadedFilename !== artifact.filename) {
            setContent(null);
            setLoadedFilename(null);
            setError(null);
        }
    }, [artifact.filename, loadedFilename]);

    useEffect(() => {
        const fetchContent = async () => {
            if (!isDeepResearchReport) {
                return;
            }

            // Skip if we already have content for this specific artifact
            if (content && loadedFilename === artifact.filename) {
                return;
            }

            if (artifact.accumulatedContent) {
                setContent(artifact.accumulatedContent);
                setLoadedFilename(artifact.filename);
                return;
            }

            const fileUri = artifact.uri;
            if (!fileUri) {
                return;
            }

            setIsLoading(true);
            setError(null);

            try {
                const parsedUri = parseArtifactUri(fileUri);
                if (!parsedUri) {
                    throw new Error("Invalid artifact URI.");
                }

                const { sessionId: uriSessionId, filename, version } = parsedUri;
                // Use session ID from URI if available, otherwise fall back to prop
                // This ensures we fetch from the correct session where the artifact was created
                const effectiveSessionId = uriSessionId || sessionId;

                const apiUrl = `/api/v1/artifacts/${effectiveSessionId}/${encodeURIComponent(filename)}/versions/${version || "latest"}`;

                const response = await api.webui.get(apiUrl, { fullResponse: true });
                if (!response.ok) {
                    throw new Error(`Failed to fetch artifact content: ${response.statusText}`);
                }

                const text = await response.text();
                setContent(text);
                setLoadedFilename(artifact.filename);
            } catch (e) {
                console.error("Error fetching deep research report content:", e);
                setError(e instanceof Error ? e.message : "Unknown error fetching content.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchContent();
    }, [isDeepResearchReport, artifact, sessionId, content, loadedFilename]);

    const filteredContent = useMemo(() => {
        if (!content) {
            return null;
        }
        return stripReportMetadataSections(content);
    }, [content]);

    // Notify parent when content is loaded
    useEffect(() => {
        if (filteredContent && onContentLoaded) {
            onContentLoaded(filteredContent);
        }
    }, [filteredContent, onContentLoaded]);

    if (!isDeepResearchReport) {
        return null;
    }

    if (isLoading) {
        return <div className="text-muted-foreground py-2 text-sm">Loading report...</div>;
    }

    if (error) {
        return <div className="text-destructive py-2 text-sm">{error}</div>;
    }

    if (!filteredContent) {
        return null;
    }

    return <MarkdownRenderer content={filteredContent} setRenderError={() => {}} ragData={ragData} />;
};

export default DeepResearchReportContent;
