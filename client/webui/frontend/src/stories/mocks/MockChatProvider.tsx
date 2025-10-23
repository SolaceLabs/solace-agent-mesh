import { ChatContext, type ChatContextValue } from "@/lib/contexts/ChatContext";
import React, { useState } from "react";
import { mockAgentCards } from "./data";

type DefaultMockContextType = Omit<ChatContextValue, "setIsSidePanelCollapsed">;

// Default mock values for ChatContext
const defaultMockChatContext: DefaultMockContextType = {
    // State
    sessionId: "mock-session-id",
    messages: [],
    userInput: "",
    isResponding: false,
    currentTaskId: null,
    selectedAgentName: "MockAgent",
    notifications: [],
    agents: mockAgentCards,
    agentsLoading: false,
    agentsError: null,
    agentsRefetch: async () => {},
    isCancelling: false,
    artifacts: [],
    artifactsLoading: false,
    artifactsRefetch: async () => {},
    taskIdInSidePanel: null,
    isSidePanelCollapsed: false,
    activeSidePanelTab: "files",
    isDeleteModalOpen: false,
    artifactToDelete: null,
    isArtifactEditMode: false,
    selectedArtifactFilenames: new Set(),
    isBatchDeleteModalOpen: false,
    previewArtifact: null,
    previewedArtifactAvailableVersions: null,
    currentPreviewedVersionNumber: null,
    previewFileContent: null,

    // Actions
    setMessages: () => {},
    setUserInput: () => {},
    setTaskIdInSidePanel: () => {},
    handleNewSession: () => {},
    handleSubmit: async () => {},
    handleCancel: () => {},
    addNotification: () => {},
    setSelectedAgentName: () => {},
    uploadArtifactFile: async () => null,
    setActiveSidePanelTab: () => {},
    openSidePanelTab: () => {},
    openDeleteModal: () => {},
    closeDeleteModal: () => {},
    confirmDelete: async () => {},
    setIsArtifactEditMode: () => {},
    setSelectedArtifactFilenames: () => {},
    handleDeleteSelectedArtifacts: () => {},
    confirmBatchDeleteArtifacts: async () => {},
    setIsBatchDeleteModalOpen: () => {},
    setPreviewArtifact: () => {},
    openArtifactForPreview: async () => null,
    navigateArtifactVersion: async () => null,
    openMessageAttachmentForPreview: () => {},
    latestStatusText: React.createRef<string | null>(),
    sessionName: null,
    sessionToDelete: null,
    setSessionId: function (): void {},
    setSessionName: function (): void {},
    handleSwitchSession: function (): Promise<void> {
        return Promise.resolve();
    },
    openSessionDeleteModal: function (): void {},
    closeSessionDeleteModal: function (): void {},
    confirmSessionDelete: function (): Promise<void> {
        return Promise.resolve();
    },
    updateSessionName: function (): Promise<void> {
        return Promise.resolve();
    },
    deleteSession: function (): Promise<void> {
        return Promise.resolve();
    },
    configCollectFeedback: false,
    submittedFeedback: {},
    handleFeedbackSubmit: function (): Promise<void> {
        return Promise.resolve();
    },
};

interface MockChatProviderProps {
    children: React.ReactNode;
    mockValues?: Partial<ChatContextValue>;
}

export const MockChatProvider: React.FC<MockChatProviderProps> = ({ children, mockValues = {} }) => {
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState(mockValues.isSidePanelCollapsed ?? defaultMockChatContext.isSidePanelCollapsed);

    // Create the context value with the stateful values and their setters
    const contextValue: ChatContextValue = {
        ...defaultMockChatContext,
        ...mockValues,
        isSidePanelCollapsed,
        setIsSidePanelCollapsed,
    };

    return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
};
