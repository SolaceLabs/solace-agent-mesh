import React, { createContext, type FormEvent } from "react";

import type { ArtifactInfo, FileAttachment, MessageFE, Notification } from "@/lib/types";

export interface ChatState {
    sessionId: string;
    messages: MessageFE[];
    userInput: string;
    isResponding: boolean;
    currentTaskId: string | null;
    selectedAgentName: string;
    notifications: Notification[];
    isCancelling: boolean;
    // Chat Side Panel State
    artifacts: ArtifactInfo[];
    artifactsLoading: boolean;
    artifactsRefetch: () => Promise<void>;
    taskIdInSidePanel: string | null;
    // Side Panel Control State
    isSidePanelCollapsed: boolean;
    activeSidePanelTab: "files" | "workflow";
    // Delete Modal State
    isDeleteModalOpen: boolean;
    artifactToDelete: ArtifactInfo | null;
    // Artifact Edit Mode State
    isArtifactEditMode: boolean;
    selectedArtifactFilenames: Set<string>;
    isBatchDeleteModalOpen: boolean;
    // Versioning Preview State
    previewArtifact: ArtifactInfo | null;
    previewedArtifactAvailableVersions: number[] | null;
    currentPreviewedVersionNumber: number | null;
    previewFileContent: FileAttachment | null;
}

export interface ChatActions {
    setMessages: React.Dispatch<React.SetStateAction<MessageFE[]>>;
    setUserInput: React.Dispatch<React.SetStateAction<string>>;
    setTaskIdInSidePanel: React.Dispatch<React.SetStateAction<string | null>>;
    handleNewSession: () => void;
    handleSubmit: (event: FormEvent, files?: File[] | null, message?: string | null) => Promise<void>;
    handleCancel: () => void;
    addNotification: (message: string, type?: "success" | "info" | "error") => void;
    setSelectedAgentName: React.Dispatch<React.SetStateAction<string>>;
    uploadArtifactFile: (file: File) => Promise<void>;
    /** Side Panel Control Actions */
    setIsSidePanelCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
    setActiveSidePanelTab: React.Dispatch<React.SetStateAction<"files" | "workflow">>;
    openSidePanelTab: (tab: "files" | "workflow") => void;
    /** Delete Modal Actions */
    openDeleteModal: (artifact: ArtifactInfo) => void;
    closeDeleteModal: () => void;
    confirmDelete: () => Promise<void>;
    /** Artifact Edit Mode Actions */
    setIsArtifactEditMode: React.Dispatch<React.SetStateAction<boolean>>;
    setSelectedArtifactFilenames: React.Dispatch<React.SetStateAction<Set<string>>>;
    handleDeleteSelectedArtifacts: () => void;
    confirmBatchDeleteArtifacts: () => Promise<void>;
    setIsBatchDeleteModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
    /** Versioning Preview Actions */
    setPreviewArtifact: React.Dispatch<React.SetStateAction<ArtifactInfo | null>>;
    openArtifactForPreview: (artifactFilename: string, autoRun?: boolean) => Promise<FileAttachment | null>;
    navigateArtifactVersion: (artifactFilename: string, targetVersion: number) => Promise<FileAttachment | null>;
    /** Message Attachment Preview Action */
    openMessageAttachmentForPreview: (file: FileAttachment, autoRun?: boolean) => void;
}

export type ChatContextValue = ChatState & ChatActions;

export const ChatContext = createContext<ChatContextValue | undefined>(undefined);
