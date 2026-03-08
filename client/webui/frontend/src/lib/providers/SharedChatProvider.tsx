/**
 * SharedChatProvider - A minimal ChatContext provider for shared/read-only sessions.
 *
 * This provider allows reusing existing chat components (ArtifactPanel, ArtifactCard, etc.)
 * in shared session views without requiring the full ChatProvider functionality.
 *
 * All write operations are no-ops, and the context provides read-only access to artifacts
 * and other shared session data.
 */

import { useState, useRef, useMemo, useCallback, useEffect, type ReactNode } from "react";
import { ChatContext, type ChatContextValue } from "@/lib/contexts/ChatContext";
import type { ArtifactInfo, FileAttachment, RAGSearchResult } from "@/lib/types";
import { getSharedArtifactContent } from "@/lib/api/shareApi";

interface SharedChatProviderProps {
    children: ReactNode;
    /** Artifacts to display in the shared session */
    artifacts: ArtifactInfo[];
    /** RAG data for the shared session */
    ragData?: RAGSearchResult[];
    /** Session ID (for context compatibility) */
    sessionId?: string;
    /** Share ID for fetching artifact content */
    shareId: string;
}

/**
 * A minimal ChatContext provider for shared/read-only sessions.
 * Provides read-only access to artifacts and disables all write operations.
 */
export function SharedChatProvider({ children, artifacts: initialArtifacts, ragData = [], sessionId = "", shareId }: SharedChatProviderProps) {
    // State for artifacts and preview
    // Mark all artifacts as needing embed resolution so ArtifactMessage will fetch content
    const [artifacts, setArtifactsState] = useState<ArtifactInfo[]>(() => initialArtifacts.map(a => ({ ...a, needsEmbedResolution: true })));
    // Track which artifacts have had download attempts to prevent infinite retries
    const downloadAttemptedRef = useRef<Set<string>>(new Set());
    const [previewArtifact, setPreviewArtifact] = useState<ArtifactInfo | null>(null);

    // Update artifacts when initialArtifacts changes (e.g., when session data loads)
    useEffect(() => {
        setArtifactsState(initialArtifacts.map(a => ({ ...a, needsEmbedResolution: true })));
    }, [initialArtifacts]);
    const [previewFileContent, setPreviewFileContent] = useState<FileAttachment | null>(null);
    const [previewedArtifactAvailableVersions, setPreviewedArtifactAvailableVersions] = useState<number[] | null>(null);
    const [currentPreviewedVersionNumber, setCurrentPreviewedVersionNumber] = useState<number | null>(null);
    const [expandedDocumentFilename, setExpandedDocumentFilename] = useState<string | null>(null);

    // Refs
    const latestStatusText = useRef<string | null>(null);

    // Open artifact for preview - fetches content and sets preview state
    const openArtifactForPreview = useCallback(
        async (artifactFilename: string): Promise<FileAttachment | null> => {
            if (!shareId) return null;

            const artifact = artifacts.find(a => a.filename === artifactFilename);
            if (!artifact) return null;

            try {
                const content = await getSharedArtifactContent(shareId, artifactFilename);
                const fileAttachment: FileAttachment = {
                    name: artifact.filename,
                    mime_type: artifact.mime_type,
                    content: content.content,
                    size: artifact.size,
                };

                setPreviewFileContent(fileAttachment);
                setPreviewArtifact(artifact);

                // Set version info if available
                if (artifact.versionCount && artifact.versionCount > 1) {
                    const versions = Array.from({ length: artifact.versionCount }, (_, i) => i + 1);
                    setPreviewedArtifactAvailableVersions(versions);
                    setCurrentPreviewedVersionNumber(artifact.version || artifact.versionCount);
                } else {
                    setPreviewedArtifactAvailableVersions(null);
                    setCurrentPreviewedVersionNumber(null);
                }

                return fileAttachment;
            } catch (error) {
                console.error("Failed to fetch artifact content:", error);
                return null;
            }
        },
        [shareId, artifacts]
    );

    // Navigate to a specific artifact version
    // Note: Version navigation is not supported in shared sessions as the API doesn't support it
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const navigateArtifactVersion = useCallback(async (_artifactFilename: string, _targetVersion: number): Promise<FileAttachment | null> => {
        // Version navigation not supported in shared sessions
        console.warn("Version navigation is not supported in shared sessions");
        return null;
    }, []);

    // Download and resolve artifact for embedded display
    const downloadAndResolveArtifact = useCallback(
        async (filename: string): Promise<FileAttachment | null> => {
            if (!shareId) return null;

            // Check if we've already attempted this download to prevent infinite retries
            if (downloadAttemptedRef.current.has(filename)) {
                return null;
            }

            const artifact = artifacts.find(a => a.filename === filename);
            if (!artifact) return null;

            // Mark as attempted before making the request
            downloadAttemptedRef.current.add(filename);

            try {
                const content = await getSharedArtifactContent(shareId, filename);

                // On success, update the artifact to remove needsEmbedResolution
                setArtifactsState(prev => prev.map(a => (a.filename === filename ? { ...a, needsEmbedResolution: false } : a)));

                return {
                    name: artifact.filename,
                    mime_type: artifact.mime_type,
                    content: content.content,
                    size: artifact.size,
                };
            } catch (error) {
                console.error("Failed to download artifact:", error);

                // On failure, also remove needsEmbedResolution to prevent infinite retries
                setArtifactsState(prev => prev.map(a => (a.filename === filename ? { ...a, needsEmbedResolution: false } : a)));

                return null;
            }
        },
        [shareId, artifacts]
    );

    // Create the context value with all required properties
    const contextValue: ChatContextValue = useMemo(
        () => ({
            // State - Read-only values
            configCollectFeedback: false,
            sessionId,
            sessionName: null,
            messages: [],
            isResponding: false,
            currentTaskId: null,
            selectedAgentName: "",
            notifications: [],
            isCancelling: false,
            latestStatusText,
            isLoadingSession: false,

            // Agents - Empty for shared sessions
            agents: [],
            agentsError: null,
            agentsLoading: false,
            agentsRefetch: async () => {},
            agentNameDisplayNameMap: {},

            // Artifacts
            artifacts,
            artifactsLoading: false,
            artifactsRefetch: async () => {},
            setArtifacts: () => {},
            taskIdInSidePanel: null,

            // RAG State
            ragData,
            ragEnabled: ragData.length > 0,
            expandedDocumentFilename,

            // Side Panel Control State
            isSidePanelCollapsed: false,
            activeSidePanelTab: "files",

            // Delete Modal State - Disabled for shared sessions
            isDeleteModalOpen: false,
            artifactToDelete: null,
            sessionToDelete: null,

            // Artifact Edit Mode State - Disabled for shared sessions
            isArtifactEditMode: false,
            selectedArtifactFilenames: new Set<string>(),
            isBatchDeleteModalOpen: false,

            // Versioning Preview State
            previewArtifact,
            previewedArtifactAvailableVersions,
            currentPreviewedVersionNumber,
            previewFileContent,
            submittedFeedback: {},

            // Pending prompt - Not used in shared sessions
            pendingPrompt: null,

            // Background Task Monitoring State - Not used in shared sessions
            backgroundTasks: [],
            backgroundNotifications: [],

            // Actions - Most are no-ops for shared sessions
            setSessionId: () => {},
            setSessionName: () => {},
            setMessages: () => {},
            setTaskIdInSidePanel: () => {},
            handleNewSession: async () => {},
            startNewChatWithPrompt: () => {},
            clearPendingPrompt: () => {},
            handleSwitchSession: async () => {},
            handleSubmit: async () => {},
            handleCancel: () => {},
            addNotification: () => {},
            setSelectedAgentName: () => {},
            uploadArtifactFile: async () => null,

            // Side Panel Control Actions
            setIsSidePanelCollapsed: () => {},
            setActiveSidePanelTab: () => {},
            openSidePanelTab: () => {},

            // Delete Modal Actions - No-ops for shared sessions
            openDeleteModal: () => {},
            closeDeleteModal: () => {},
            confirmDelete: async () => {},
            openSessionDeleteModal: () => {},
            closeSessionDeleteModal: () => {},
            confirmSessionDelete: async () => {},

            // Artifact Edit Mode Actions - No-ops for shared sessions
            setIsArtifactEditMode: () => {},
            setSelectedArtifactFilenames: () => {},
            handleDeleteSelectedArtifacts: () => {},
            confirmBatchDeleteArtifacts: async () => {},
            setIsBatchDeleteModalOpen: () => {},

            // Preview Actions - These work for viewing
            setPreviewArtifact,
            openArtifactForPreview,
            navigateArtifactVersion,

            // Artifact Display and Cache Management
            markArtifactAsDisplayed: () => {},
            downloadAndResolveArtifact,

            // Session Management Actions - No-ops for shared sessions
            updateSessionName: async () => {},
            deleteSession: async () => {},
            handleFeedbackSubmit: async () => {},

            displayError: () => {},

            // Background Task Monitoring Actions
            isTaskRunningInBackground: () => false,

            // RAG Panel State Actions
            setExpandedDocumentFilename,
        }),
        [sessionId, artifacts, ragData, expandedDocumentFilename, previewArtifact, previewedArtifactAvailableVersions, currentPreviewedVersionNumber, previewFileContent, openArtifactForPreview, navigateArtifactVersion, downloadAndResolveArtifact]
    );

    return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
}
