import { useState, useCallback, useRef, useMemo } from "react";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";
import { getArtifactContent, getArtifactUrl, getErrorMessage } from "@/lib/utils";
import { api } from "@/lib/api";

// Types
export interface ArtifactPreviewState {
    filename: string | null;
    availableVersions: number[] | null;
    currentVersion: number | null;
    content: FileAttachment | null;
}

interface UseArtifactPreviewOptions {
    sessionId: string;
    projectId?: string;
    artifacts: ArtifactInfo[];
    setError?: (error: { title: string; error: string }) => void;
}

interface UseArtifactPreviewReturn {
    // State
    preview: ArtifactPreviewState;
    previewArtifact: ArtifactInfo | null;
    isLoading: boolean;

    // Actions
    openPreview: (filename: string) => Promise<FileAttachment | null>;
    navigateToVersion: (filename: string, version: number) => Promise<FileAttachment | null>;
    closePreview: () => void;
    setPreviewByArtifact: (artifact: ArtifactInfo | null) => void;
}

/**
 * Custom hook to manage artifact preview functionality
 * Handles opening artifacts, navigating versions, and managing preview state
 */
export const useArtifactPreview = ({ sessionId, projectId, artifacts, setError }: UseArtifactPreviewOptions): UseArtifactPreviewReturn => {
    // State
    const [preview, setPreview] = useState<ArtifactPreviewState>({
        filename: null,
        availableVersions: null,
        currentVersion: null,
        content: null,
    });

    const [isLoading, setIsLoading] = useState(false);

    // Track in-flight fetches to prevent duplicates
    const fetchInProgressRef = useRef<Set<string>>(new Set());

    // Derive preview artifact from artifacts array
    const previewArtifact = useMemo(() => {
        if (!preview.filename) return null;
        return artifacts.find(a => a.filename === preview.filename) || null;
    }, [artifacts, preview.filename]);

    /**
     * Helper to get file attachment data
     */
    const getFileAttachment = useCallback(
        (filename: string, mimeType: string, content: string): FileAttachment => {
            const artifactInfo = artifacts.find(a => a.filename === filename);
            return {
                name: filename,
                mime_type: mimeType,
                content: content,
                last_modified: artifactInfo?.last_modified || new Date().toISOString(),
            };
        },
        [artifacts]
    );

    /**
     * Open an artifact for preview, loading the latest version
     */
    const openPreview = useCallback(
        async (filename: string): Promise<FileAttachment | null> => {
            // Prevent duplicate fetches
            if (fetchInProgressRef.current.has(filename)) {
                return null;
            }

            fetchInProgressRef.current.add(filename);
            setIsLoading(true);

            // Clear state if opening a different file
            if (preview.filename !== filename) {
                setPreview({
                    filename,
                    availableVersions: null,
                    currentVersion: null,
                    content: null,
                });
            }

            try {
                // Fetch available versions
                const versionsUrl = getArtifactUrl({
                    filename,
                    sessionId,
                    projectId,
                });
                const availableVersions: number[] = await api.webui.get(versionsUrl);

                if (!availableVersions || availableVersions.length === 0) {
                    throw new Error("No versions available");
                }

                const sortedVersions = availableVersions.sort((a, b) => a - b);
                const latestVersion = Math.max(...availableVersions);

                // Fetch content for latest version
                const { content, mimeType } = await getArtifactContent({
                    filename,
                    sessionId,
                    projectId,
                    version: latestVersion,
                });

                const fileData = getFileAttachment(filename, mimeType, content);
                const isProjectArtifactPreview = !!projectId && (!sessionId || sessionId === "null" || sessionId === "undefined");

                // Update all preview state atomically
                setPreview({
                    filename,
                    availableVersions: isProjectArtifactPreview ? [latestVersion] : sortedVersions,
                    currentVersion: latestVersion,
                    content: fileData,
                });

                return fileData;
            } catch (error) {
                const errorMessage = getErrorMessage(error, "Failed to load artifact preview.");
                setError?.({ title: "Artifact Preview Failed", error: errorMessage });
                return null;
            } finally {
                setIsLoading(false);
                fetchInProgressRef.current.delete(filename);
            }
        },
        [sessionId, projectId, preview.filename, getFileAttachment, setError]
    );

    /**
     * Navigate to a specific version of the currently previewed artifact
     */
    const navigateToVersion = useCallback(
        async (filename: string, targetVersion: number): Promise<FileAttachment | null> => {
            // Verify versions are loaded
            if (!preview.availableVersions || preview.availableVersions.length === 0) {
                return null;
            }

            // Verify target version exists
            if (!preview.availableVersions.includes(targetVersion)) {
                console.warn(`Requested version ${targetVersion} not available for ${filename}`);
                return null;
            }

            setIsLoading(true);

            // Clear content while navigating
            setPreview(prev => ({
                ...prev,
                content: null,
            }));

            try {
                // Fetch content for target version
                const { content, mimeType } = await getArtifactContent({
                    filename,
                    sessionId,
                    projectId,
                    version: targetVersion,
                });

                const fileData = getFileAttachment(filename, mimeType, content);

                // Update version and content
                setPreview(prev => ({
                    ...prev,
                    currentVersion: targetVersion,
                    content: fileData,
                }));

                return fileData;
            } catch (error) {
                const errorMessage = getErrorMessage(error, "Failed to fetch artifact version.");
                setError?.({ title: "Artifact Version Preview Failed", error: errorMessage });
                return null;
            } finally {
                setIsLoading(false);
            }
        },
        [sessionId, projectId, preview.availableVersions, getFileAttachment, setError]
    );

    /**
     * Close the preview, clearing all state
     */
    const closePreview = useCallback(() => {
        setPreview({
            filename: null,
            availableVersions: null,
            currentVersion: null,
            content: null,
        });
    }, []);

    /**
     * Set preview by artifact object (for compatibility with existing code)
     */
    const setPreviewByArtifact = useCallback(
        (artifact: ArtifactInfo | null) => {
            if (artifact) {
                // Only reset if different file
                if (preview.filename !== artifact.filename) {
                    setPreview({
                        filename: artifact.filename,
                        availableVersions: null,
                        currentVersion: null,
                        content: null,
                    });
                }
            } else {
                closePreview();
            }
        },
        [preview.filename, closePreview]
    );

    return {
        preview,
        previewArtifact,
        isLoading,
        openPreview,
        navigateToVersion,
        closePreview,
        setPreviewByArtifact,
    };
};
