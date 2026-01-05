import { useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { createFileSizeErrorMessage, blobToBase64, getErrorMessage } from "@/lib/utils";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";

interface UseArtifactOperationsOptions {
    sessionId: string;
    artifacts: ArtifactInfo[];
    setArtifacts: React.Dispatch<React.SetStateAction<ArtifactInfo[]>>;
    artifactsRefetch: () => Promise<void>;
    addNotification: (message: string, type?: "success" | "info" | "warning") => void;
    setError: (error: { title: string; error: string }) => void;
    previewArtifact: { filename: string } | null;
    closePreview: () => void;
}

interface UseArtifactOperationsReturn {
    // Upload
    uploadArtifactFile: (file: File, overrideSessionId?: string, description?: string, silent?: boolean) => Promise<{ uri: string; sessionId: string } | { error: string } | null>;

    // Delete - Single
    isDeleteModalOpen: boolean;
    artifactToDelete: ArtifactInfo | null;
    openDeleteModal: (artifact: ArtifactInfo) => void;
    closeDeleteModal: () => void;
    confirmDelete: () => Promise<void>;

    // Delete - Batch
    isArtifactEditMode: boolean;
    setIsArtifactEditMode: React.Dispatch<React.SetStateAction<boolean>>;
    selectedArtifactFilenames: Set<string>;
    setSelectedArtifactFilenames: React.Dispatch<React.SetStateAction<Set<string>>>;
    isBatchDeleteModalOpen: boolean;
    setIsBatchDeleteModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
    handleDeleteSelectedArtifacts: () => void;
    confirmBatchDeleteArtifacts: () => Promise<void>;

    // Download
    downloadAndResolveArtifact: (filename: string) => Promise<FileAttachment | null>;
}

/**
 * Utility function to create file attachment from artifact info
 */
const getFileAttachment = (artifactInfos: ArtifactInfo[], filename: string, mimeType: string, content: string): FileAttachment => {
    const artifactInfo = artifactInfos.find(a => a.filename === filename);
    return {
        name: filename,
        mime_type: mimeType,
        content: content,
        last_modified: artifactInfo?.last_modified || new Date().toISOString(),
    };
};

/**
 * Custom hook to manage artifact CRUD operations
 * Handles upload, download, delete (single and batch), and modal state
 */
export const useArtifactOperations = ({ sessionId, artifacts, setArtifacts, artifactsRefetch, addNotification, setError, previewArtifact, closePreview }: UseArtifactOperationsOptions): UseArtifactOperationsReturn => {
    // Delete Modal State
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [artifactToDelete, setArtifactToDelete] = useState<ArtifactInfo | null>(null);
    const [isBatchDeleteModalOpen, setIsBatchDeleteModalOpen] = useState(false);

    // Edit Mode State
    const [isArtifactEditMode, setIsArtifactEditMode] = useState(false);
    const [selectedArtifactFilenames, setSelectedArtifactFilenames] = useState<Set<string>>(new Set());

    // Track in-flight artifact downloads to prevent duplicates
    const artifactDownloadInProgressRef = useRef<Set<string>>(new Set());

    /**
     * Upload an artifact file to the backend
     */
    const uploadArtifactFile = useCallback(
        async (file: File, overrideSessionId?: string, description?: string, silent: boolean = false): Promise<{ uri: string; sessionId: string } | { error: string } | null> => {
            const effectiveSessionId = overrideSessionId || sessionId;
            const formData = new FormData();
            formData.append("upload_file", file);
            formData.append("filename", file.name);
            formData.append("sessionId", effectiveSessionId || "");

            if (description) {
                const metadata = { description };
                formData.append("metadata_json", JSON.stringify(metadata));
            }

            try {
                const response = await api.webui.post("/api/v1/artifacts/upload", formData, { fullResponse: true });

                if (response.status === 413) {
                    const errorData = await response.json().catch(() => ({ message: `Failed to upload ${file.name}.` }));
                    const actualSize = errorData.actual_size_bytes;
                    const maxSize = errorData.max_size_bytes;
                    const errorMessage = actualSize && maxSize ? createFileSizeErrorMessage(file.name, actualSize, maxSize) : errorData.message || `File "${file.name}" exceeds the maximum allowed size.`;
                    setError({ title: "File Upload Failed", error: errorMessage });
                    return { error: errorMessage };
                }

                if (!response.ok) {
                    throw new Error(
                        await response
                            .json()
                            .then((d: { message?: string }) => d.message)
                            .catch(() => `Failed to upload ${file.name}.`)
                    );
                }

                const result = await response.json();
                if (!silent) {
                    addNotification(`File "${file.name}" uploaded.`, "success");
                }
                await artifactsRefetch();
                return result.uri && result.sessionId ? { uri: result.uri, sessionId: result.sessionId } : null;
            } catch (error) {
                const errorMessage = getErrorMessage(error, `Failed to upload "${file.name}".`);
                setError({ title: "File Upload Failed", error: errorMessage });
                return { error: errorMessage };
            }
        },
        [sessionId, addNotification, artifactsRefetch, setError]
    );

    /**
     * Internal function to delete an artifact
     */
    const deleteArtifactInternal = useCallback(
        async (filename: string) => {
            try {
                await api.webui.delete(`/api/v1/artifacts/${sessionId}/${encodeURIComponent(filename)}`);
                addNotification(`File "${filename}" deleted.`, "success");
                artifactsRefetch();
            } catch (error) {
                setError({ title: "File Deletion Failed", error: getErrorMessage(error, `Failed to delete ${filename}.`) });
            }
        },
        [sessionId, addNotification, artifactsRefetch, setError]
    );

    /**
     * Open delete confirmation modal for a single artifact
     */
    const openDeleteModal = useCallback((artifact: ArtifactInfo) => {
        setArtifactToDelete(artifact);
        setIsDeleteModalOpen(true);
    }, []);

    /**
     * Close delete confirmation modal
     */
    const closeDeleteModal = useCallback(() => {
        setArtifactToDelete(null);
        setIsDeleteModalOpen(false);
    }, []);

    /**
     * Confirm and execute single artifact deletion
     */
    const confirmDelete = useCallback(async () => {
        if (artifactToDelete) {
            // Check if the artifact being deleted is currently being previewed
            const isCurrentlyPreviewed = previewArtifact?.filename === artifactToDelete.filename;

            await deleteArtifactInternal(artifactToDelete.filename);

            // If the deleted artifact was being previewed, close the preview
            if (isCurrentlyPreviewed) {
                closePreview();
            }
        }
        closeDeleteModal();
    }, [artifactToDelete, deleteArtifactInternal, closeDeleteModal, previewArtifact, closePreview]);

    /**
     * Open batch delete modal
     */
    const handleDeleteSelectedArtifacts = useCallback(() => {
        if (selectedArtifactFilenames.size === 0) {
            return;
        }
        setIsBatchDeleteModalOpen(true);
    }, [selectedArtifactFilenames]);

    /**
     * Confirm and execute batch artifact deletion
     */
    const confirmBatchDeleteArtifacts = useCallback(async () => {
        setIsBatchDeleteModalOpen(false);
        const filenamesToDelete = Array.from(selectedArtifactFilenames);
        let successCount = 0;
        let errorCount = 0;

        for (const filename of filenamesToDelete) {
            try {
                await api.webui.delete(`/api/v1/artifacts/${sessionId}/${encodeURIComponent(filename)}`);
                successCount++;
            } catch (error: unknown) {
                console.error(error);
                errorCount++;
            }
        }

        if (successCount > 0) addNotification(`${successCount} files(s) deleted.`, "success");
        if (errorCount > 0) {
            setError({ title: "File Deletion Failed", error: `${errorCount} file(s) failed to delete.` });
        }

        artifactsRefetch();
        setSelectedArtifactFilenames(new Set());
        setIsArtifactEditMode(false);
    }, [selectedArtifactFilenames, addNotification, artifactsRefetch, sessionId, setError]);

    /**
     * Download and resolve artifact with embeds
     */
    const downloadAndResolveArtifact = useCallback(
        async (filename: string): Promise<FileAttachment | null> => {
            // Prevent duplicate downloads for the same file
            if (artifactDownloadInProgressRef.current.has(filename)) {
                console.log(`[useArtifactOperations] Skipping duplicate download for ${filename} - already in progress`);
                return null;
            }

            // Mark this file as being downloaded
            artifactDownloadInProgressRef.current.add(filename);

            try {
                // Find the artifact in state
                const artifact = artifacts.find(art => art.filename === filename);
                if (!artifact) {
                    console.error(`Artifact ${filename} not found in state`);
                    return null;
                }

                // Fetch the latest version with embeds resolved
                const availableVersions: number[] = await api.webui.get(`/api/v1/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions`);
                if (!availableVersions || availableVersions.length === 0) {
                    throw new Error("No versions available");
                }

                const latestVersion = Math.max(...availableVersions);
                const contentResponse = await api.webui.get(`/api/v1/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions/${latestVersion}`, { fullResponse: true });
                if (!contentResponse.ok) {
                    throw new Error(`Failed to fetch artifact content: ${contentResponse.statusText}`);
                }

                const blob = await contentResponse.blob();
                const base64Content = await blobToBase64(blob);
                const fileData = getFileAttachment(artifacts, filename, artifact.mime_type || "application/octet-stream", base64Content);

                // Clear the accumulated content and flags after successful download
                setArtifacts(prevArtifacts => {
                    return prevArtifacts.map(art =>
                        art.filename === filename
                            ? {
                                  ...art,
                                  accumulatedContent: undefined,
                                  needsEmbedResolution: false,
                              }
                            : art
                    );
                });

                return fileData;
            } catch (error) {
                setError({ title: "File Download Failed", error: getErrorMessage(error, `Failed to download ${filename}.`) });
                return null;
            } finally {
                // Remove from in-progress set immediately when done
                artifactDownloadInProgressRef.current.delete(filename);
            }
        },
        [sessionId, artifacts, setArtifacts, setError]
    );

    return {
        uploadArtifactFile,
        isDeleteModalOpen,
        artifactToDelete,
        openDeleteModal,
        closeDeleteModal,
        confirmDelete,
        isArtifactEditMode,
        setIsArtifactEditMode,
        selectedArtifactFilenames,
        setSelectedArtifactFilenames,
        isBatchDeleteModalOpen,
        setIsBatchDeleteModalOpen,
        handleDeleteSelectedArtifacts,
        confirmBatchDeleteArtifacts,
        downloadAndResolveArtifact,
    };
};
