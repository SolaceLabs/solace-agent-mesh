import React, { createContext, type FormEvent } from "react";

import type { AgentCardInfo, ArtifactInfo, ArtifactRenderingState, BackgroundTaskNotification, BackgroundTaskState, FileAttachment, MessageFE, Notification, Session } from "@/lib/types";

/** Pending prompt data for starting a new chat with a prompt template */
export interface PendingPromptData {
    promptText: string;
    groupId: string;
    groupName: string;
}

export interface ChatState {
    configCollectFeedback: boolean;
    sessionId: string;
    sessionName: string | null;
    messages: MessageFE[];
    isResponding: boolean;
    currentTaskId: string | null;
    selectedAgentName: string;
    notifications: Notification[];
    isCancelling: boolean;
    latestStatusText: React.RefObject<string | null>;
    isLoadingSession: boolean;
    // Agents
    agents: AgentCardInfo[];
    agentsError: string | null;
    agentsLoading: boolean;
    agentsRefetch: () => Promise<void>;
    agentNameDisplayNameMap: Record<string, string>;
    // Chat Side Panel State
    artifacts: ArtifactInfo[];
    artifactsLoading: boolean;
    artifactsRefetch: () => Promise<void>;
    setArtifacts: React.Dispatch<React.SetStateAction<ArtifactInfo[]>>;
    taskIdInSidePanel: string | null;
    // Side Panel Control State
    isSidePanelCollapsed: boolean;
    activeSidePanelTab: "files" | "workflow";
    // Delete Modal State
    isDeleteModalOpen: boolean;
    artifactToDelete: ArtifactInfo | null;
    sessionToDelete: Session | null;
    // Artifact Edit Mode State
    isArtifactEditMode: boolean;
    selectedArtifactFilenames: Set<string>;
    isBatchDeleteModalOpen: boolean;
    // Versioning Preview State
    previewArtifact: ArtifactInfo | null;
    previewedArtifactAvailableVersions: number[] | null;
    currentPreviewedVersionNumber: number | null;
    previewFileContent: FileAttachment | null;
    submittedFeedback: Record<string, { type: "up" | "down"; text: string }>;
    // Artifact Rendering State
    artifactRenderingState: ArtifactRenderingState;
    // Pending prompt for starting new chat
    pendingPrompt: PendingPromptData | null;
    // Background Task Monitoring State
    backgroundTasks: BackgroundTaskState[];
    backgroundNotifications: BackgroundTaskNotification[];
}

export interface ChatActions {
    setSessionId: React.Dispatch<React.SetStateAction<string>>;
    setSessionName: React.Dispatch<React.SetStateAction<string | null>>;
    setMessages: React.Dispatch<React.SetStateAction<MessageFE[]>>;
    setTaskIdInSidePanel: React.Dispatch<React.SetStateAction<string | null>>;
    handleNewSession: (preserveProjectContext?: boolean) => Promise<void>;
    /** Start a new chat session with a prompt template pre-filled */
    startNewChatWithPrompt: (promptData: PendingPromptData) => void;
    /** Clear the pending prompt (called after it's been applied) */
    clearPendingPrompt: () => void;
    handleSwitchSession: (sessionId: string) => Promise<void>;
    handleSubmit: (event: FormEvent, files?: File[] | null, message?: string | null, overrideSessionId?: string | null) => Promise<void>;
    handleCancel: () => void;
    addNotification: (message: string, type?: "success" | "info" | "warning") => void;
    setSelectedAgentName: React.Dispatch<React.SetStateAction<string>>;
    uploadArtifactFile: (file: File, overrideSessionId?: string, description?: string, silent?: boolean) => Promise<{ uri: string; sessionId: string } | { error: string } | null>;
    /** Side Panel Control Actions */
    setIsSidePanelCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
    setActiveSidePanelTab: React.Dispatch<React.SetStateAction<"files" | "workflow">>;
    openSidePanelTab: (tab: "files" | "workflow") => void;

    openDeleteModal: (artifact: ArtifactInfo) => void;
    closeDeleteModal: () => void;
    confirmDelete: () => Promise<void>;
    openSessionDeleteModal: (session: Session) => void;
    closeSessionDeleteModal: () => void;
    confirmSessionDelete: () => Promise<void>;

    setIsArtifactEditMode: React.Dispatch<React.SetStateAction<boolean>>;
    setSelectedArtifactFilenames: React.Dispatch<React.SetStateAction<Set<string>>>;
    handleDeleteSelectedArtifacts: () => void;
    confirmBatchDeleteArtifacts: () => Promise<void>;
    setIsBatchDeleteModalOpen: React.Dispatch<React.SetStateAction<boolean>>;

    setPreviewArtifact: (artifact: ArtifactInfo | null) => void;
    openArtifactForPreview: (artifactFilename: string, autoRun?: boolean) => Promise<FileAttachment | null>;
    navigateArtifactVersion: (artifactFilename: string, targetVersion: number) => Promise<FileAttachment | null>;

    /** Artifact Display and Cache Management */
    markArtifactAsDisplayed: (filename: string, displayed: boolean) => void;
    downloadAndResolveArtifact: (filename: string) => Promise<FileAttachment | null>;

    /** Artifact Rendering Actions */
    toggleArtifactExpanded: (filename: string) => void;
    isArtifactExpanded: (filename: string) => boolean;
    setArtifactRenderingState: React.Dispatch<React.SetStateAction<ArtifactRenderingState>>;

    /* Session Management Actions */
    updateSessionName: (sessionId: string, newName: string, showNotification?: boolean) => Promise<void>;
    deleteSession: (sessionId: string) => Promise<void>;
    handleFeedbackSubmit: (taskId: string, feedbackType: "up" | "down", feedbackText: string) => Promise<void>;

    displayError: ({ title, error }: { title: string; error: string }) => void;

    /** Background Task Monitoring Actions */
    isTaskRunningInBackground: (taskId: string) => boolean;
}

export type ChatContextValue = ChatState & ChatActions;

export const ChatContext = createContext<ChatContextValue | undefined>(undefined);
