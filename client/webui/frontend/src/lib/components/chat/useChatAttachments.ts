import { useCallback, useRef, useState } from "react";
import type { NavigateFunction } from "react-router-dom";

import { api, getErrorFromResponse } from "@/lib/api";
import { type ArtifactWithSession, getArtifactApiUrl } from "@/lib/api/artifacts";
import { getErrorMessage } from "@/lib/utils";
import type { PasteMetadata, PastedTextItem } from "./paste";

interface UseChatAttachmentsOptions {
    isResponding: boolean;
    addNotification: (message: string, type?: "success" | "info" | "warning") => void;
    displayError: (error: { title: string; error: string }) => void;
    handleSwitchSession: (sessionId: string) => Promise<void> | void;
    navigate: NavigateFunction;
}

/**
 * Frozen snapshot of every attachment slice the user had at submit time, used
 * to restore the input row if the submit fails. Held by `ChatInputArea.onSubmit`
 * across the async upload/send work.
 */
export interface ChatAttachmentsCapture {
    files: File[];
    artifactRefs: ArtifactWithSession[];
    pastedTextItems: PastedTextItem[];
}

export interface UseChatAttachmentsResult {
    // State
    selectedFiles: File[];
    selectedArtifactRefs: ArtifactWithSession[];
    pendingPastedTextItems: PastedTextItem[];
    selectedPendingPasteId: string | null;
    previewingArtifact: ArtifactWithSession | null;
    previewingLocalFile: File | null;
    showAttachArtifactDialog: boolean;
    showArtifactForm: boolean;

    // Setters that callers outside the hook need (paste handler, drag-drop,
    // snip-to-chat event). Kept narrow — anything that mutates state through
    // user-removal pathways goes through the dedicated handlers below so the
    // intentional-clear flag stays accurate.
    setSelectedFiles: React.Dispatch<React.SetStateAction<File[]>>;
    setPendingPastedTextItems: React.Dispatch<React.SetStateAction<PastedTextItem[]>>;
    setSelectedArtifactRefs: React.Dispatch<React.SetStateAction<ArtifactWithSession[]>>;
    setPreviewingArtifact: (a: ArtifactWithSession | null) => void;
    setPreviewingLocalFile: (f: File | null) => void;
    setShowAttachArtifactDialog: (b: boolean) => void;

    // Handlers
    handleAttachArtifacts: (artifactsToAttach: ArtifactWithSession[]) => void;
    handleRemoveArtifactRef: (uri: string) => void;
    handleRemoveFile: (index: number) => void;
    handleRemovePendingPaste: (id: string) => void;
    handlePendingPasteClick: (id: string) => void;
    handleSaveMetadata: (metadata: PasteMetadata) => void;
    handleCancelArtifactForm: () => void;
    handlePreviewArtifactDownload: (artifact: ArtifactWithSession) => Promise<void>;
    handlePreviewGoToChat: (artifact: ArtifactWithSession) => Promise<void>;
    handlePreviewGoToProject: (artifact: ArtifactWithSession) => void;

    /** Snapshot the three slices that need restoring, then clear them. */
    captureAndClearForSubmit: () => ChatAttachmentsCapture;
    /**
     * Restore slices from a snapshot, but only those the user hasn't touched
     * since `captureAndClearForSubmit` was called. If the user explicitly
     * removed an item during the in-flight submit, the restore for that slice
     * is suppressed — restoring would silently re-add what the user just dropped.
     */
    restoreFromCapture: (capture: ChatAttachmentsCapture) => void;
}

/**
 * Encapsulates the chat input's attachment state machine: the files, existing-
 * artifact references, pending pasted text, and the modal/dialog flags around
 * them. Also owns the capture/restore-on-failure logic and the
 * "user explicitly cleared during submit" flag described in
 * `restoreFromCapture`.
 */
export function useChatAttachments({ addNotification, displayError, handleSwitchSession, navigate }: UseChatAttachmentsOptions): UseChatAttachmentsResult {
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [selectedArtifactRefs, setSelectedArtifactRefs] = useState<ArtifactWithSession[]>([]);
    const [pendingPastedTextItems, setPendingPastedTextItems] = useState<PastedTextItem[]>([]);
    const [selectedPendingPasteId, setSelectedPendingPasteId] = useState<string | null>(null);
    const [previewingArtifact, setPreviewingArtifact] = useState<ArtifactWithSession | null>(null);
    const [previewingLocalFile, setPreviewingLocalFile] = useState<File | null>(null);
    const [showAttachArtifactDialog, setShowAttachArtifactDialog] = useState(false);
    const [showArtifactForm, setShowArtifactForm] = useState(false);

    // Per-slice "user explicitly cleared during the in-flight submit" flags.
    // captureAndClearForSubmit() resets these; user-removal handlers set them to
    // true; restoreFromCapture() consults them so a restore can't bring back
    // items the user just deliberately dropped.
    const userClearedFiles = useRef(false);
    const userClearedArtifactRefs = useRef(false);
    const userClearedPastedText = useRef(false);

    const handleAttachArtifacts = useCallback((artifactsToAttach: ArtifactWithSession[]) => {
        setSelectedArtifactRefs(prev => {
            const existingUris = new Set(prev.map(a => a.uri).filter(Boolean));
            const deduped = artifactsToAttach.filter(a => a.uri && !existingUris.has(a.uri));
            return deduped.length ? [...prev, ...deduped] : prev;
        });
    }, []);

    const handleRemoveArtifactRef = useCallback((uri: string) => {
        userClearedArtifactRefs.current = true;
        setSelectedArtifactRefs(prev => prev.filter(a => a.uri !== uri));
    }, []);

    const handleRemoveFile = useCallback((index: number) => {
        userClearedFiles.current = true;
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    }, []);

    const handleRemovePendingPaste = useCallback((id: string) => {
        userClearedPastedText.current = true;
        setPendingPastedTextItems(prev => prev.filter(item => item.id !== id));
    }, []);

    const handlePendingPasteClick = useCallback((id: string) => {
        setSelectedPendingPasteId(id);
        setShowArtifactForm(true);
    }, []);

    const handleSaveMetadata = useCallback(
        (metadata: PasteMetadata) => {
            if (!selectedPendingPasteId) return;
            setPendingPastedTextItems(prev =>
                prev.map(item =>
                    item.id === selectedPendingPasteId
                        ? {
                              ...item,
                              content: metadata.content,
                              filename: metadata.filename,
                              mimeType: metadata.mimeType,
                              description: metadata.description,
                              isConfigured: true,
                          }
                        : item
                )
            );
            setSelectedPendingPasteId(null);
            setShowArtifactForm(false);
        },
        [selectedPendingPasteId]
    );

    const handleCancelArtifactForm = useCallback(() => {
        setSelectedPendingPasteId(null);
        setShowArtifactForm(false);
    }, []);

    const handlePreviewArtifactDownload = useCallback(
        async (artifact: ArtifactWithSession) => {
            try {
                const response = await api.webui.get(getArtifactApiUrl(artifact), { fullResponse: true });
                if (!response.ok) {
                    throw new Error(await getErrorFromResponse(response));
                }
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = downloadUrl;
                link.download = artifact.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(downloadUrl);
                addNotification(`Downloaded ${artifact.filename}`, "success");
            } catch (error) {
                displayError({ title: "Download Failed", error: getErrorMessage(error) });
            }
        },
        [addNotification, displayError]
    );

    const handlePreviewGoToChat = useCallback(
        async (artifact: ArtifactWithSession) => {
            setPreviewingArtifact(null);
            await handleSwitchSession(artifact.sessionId);
            navigate("/chat");
        },
        [handleSwitchSession, navigate]
    );

    const handlePreviewGoToProject = useCallback(
        (artifact: ArtifactWithSession) => {
            // The dialog hides Go-to-Project when projectId is missing, so this
            // path is only reached for valid project artifacts.
            setPreviewingArtifact(null);
            navigate(`/projects/${artifact.projectId}`);
        },
        [navigate]
    );

    const captureAndClearForSubmit = useCallback((): ChatAttachmentsCapture => {
        // Reset cleared-during-submit flags before clearing — any subsequent
        // user-removal during the async work flips them on for restoreFromCapture.
        userClearedFiles.current = false;
        userClearedArtifactRefs.current = false;
        userClearedPastedText.current = false;

        const capture: ChatAttachmentsCapture = {
            files: [...selectedFiles],
            artifactRefs: [...selectedArtifactRefs],
            pastedTextItems: [...pendingPastedTextItems],
        };

        setSelectedFiles([]);
        setSelectedArtifactRefs([]);
        setPendingPastedTextItems([]);

        return capture;
    }, [selectedFiles, selectedArtifactRefs, pendingPastedTextItems]);

    const restoreFromCapture = useCallback((capture: ChatAttachmentsCapture) => {
        // Per-slice rule: skip restore if the user explicitly cleared the slice
        // during the in-flight submit OR added new items themselves. Both signal
        // intent we shouldn't override.
        if (!userClearedFiles.current) {
            setSelectedFiles(current => (current.length > 0 ? current : capture.files));
        }
        if (!userClearedArtifactRefs.current) {
            setSelectedArtifactRefs(current => (current.length > 0 ? current : capture.artifactRefs));
        }
        if (!userClearedPastedText.current) {
            setPendingPastedTextItems(current => (current.length > 0 ? current : capture.pastedTextItems));
        }
    }, []);

    return {
        selectedFiles,
        selectedArtifactRefs,
        pendingPastedTextItems,
        selectedPendingPasteId,
        previewingArtifact,
        previewingLocalFile,
        showAttachArtifactDialog,
        showArtifactForm,

        setSelectedFiles,
        setPendingPastedTextItems,
        setSelectedArtifactRefs,
        setPreviewingArtifact,
        setPreviewingLocalFile,
        setShowAttachArtifactDialog,

        handleAttachArtifacts,
        handleRemoveArtifactRef,
        handleRemoveFile,
        handleRemovePendingPaste,
        handlePendingPasteClick,
        handleSaveMetadata,
        handleCancelArtifactForm,
        handlePreviewArtifactDownload,
        handlePreviewGoToChat,
        handlePreviewGoToProject,

        captureAndClearForSubmit,
        restoreFromCapture,
    };
}
