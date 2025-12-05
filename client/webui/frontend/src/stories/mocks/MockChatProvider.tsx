import { ChatContext, type ChatContextValue } from "@/lib/contexts/ChatContext";
import React, { useState } from "react";
import { mockAgentCards } from "./data";
import { transformAgentCard } from "@/lib/hooks/useAgentCards";

type DefaultMockContextType = Omit<ChatContextValue, "setIsSidePanelCollapsed">;

// Transform AgentCard to AgentCardInfo using the exported utility
const transformedMockAgents = mockAgentCards.map(transformAgentCard);

// Generate agentNameDisplayNameMap from transformed agents
const agentNameDisplayNameMap = transformedMockAgents.reduce(
    (acc, agent) => {
        if (agent.name) {
            acc[agent.name] = agent.displayName || agent.name;
        }
        return acc;
    },
    {} as Record<string, string>
);

// Minimal default mock values - stories can override as needed
const defaultMockChatContext: DefaultMockContextType = {
    // Core state
    sessionId: "",
    messages: [],
    agents: transformedMockAgents,
    agentNameDisplayNameMap,
    selectedAgentName: transformedMockAgents[0]?.name || "",

    // Loading states
    isResponding: false,
    agentsLoading: false,
    artifactsLoading: false,
    isLoadingSession: false,
    isCancelling: false,

    // Collections
    notifications: [],
    artifacts: [],
    submittedFeedback: {},
    selectedArtifactFilenames: new Set(),

    // Nullable state
    currentTaskId: null,
    agentsError: null,
    taskIdInSidePanel: null,
    artifactToDelete: null,
    previewArtifact: null,
    previewedArtifactAvailableVersions: null,
    currentPreviewedVersionNumber: null,
    previewFileContent: null,
    sessionName: null,
    sessionToDelete: null,
    latestStatusText: React.createRef<string | null>(),

    // UI state
    isSidePanelCollapsed: false,
    activeSidePanelTab: "files",
    isDeleteModalOpen: false,
    isArtifactEditMode: false,
    isBatchDeleteModalOpen: false,
    configCollectFeedback: false,

    // Artifact rendering
    artifactRenderingState: { expandedArtifacts: new Set<string>() },

    // Background task monitoring
    backgroundTasks: [],
    backgroundNotifications: [],

    // No-op functions
    setMessages: () => {},
    setTaskIdInSidePanel: () => {},
    handleNewSession: async () => {},
    handleSubmit: async () => {},
    handleCancel: async () => {},
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
    setSessionId: () => {},
    setSessionName: () => {},
    handleSwitchSession: async () => {},
    openSessionDeleteModal: () => {},
    closeSessionDeleteModal: () => {},
    confirmSessionDelete: async () => {},
    updateSessionName: async () => {},
    deleteSession: async () => {},
    handleFeedbackSubmit: async () => {},
    toggleArtifactExpanded: () => {},
    isArtifactExpanded: () => false,
    setArtifactRenderingState: () => {},
    markArtifactAsDisplayed: () => {},
    downloadAndResolveArtifact: async () => null,
    agentsRefetch: async () => {},
    artifactsRefetch: async () => {},
    setArtifacts: () => {},
    displayError: () => {},

    // Prompt handling
    pendingPrompt: null,
    startNewChatWithPrompt: async () => {},
    clearPendingPrompt: () => {},
    isTaskRunningInBackground: () => false,
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
