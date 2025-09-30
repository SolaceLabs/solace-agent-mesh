import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PanelLeftIcon, Edit } from "lucide-react";
import type { ImperativePanelHandle } from "react-resizable-panels";

import { Header } from "@/lib/components/header";
import { ChatInputArea, ChatMessage, LoadingMessageRow } from "@/lib/components/chat";
import type { TextPart } from "@/lib/types";
import { Button, ChatMessageList, CHAT_STYLES } from "@/lib/components/ui";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { useChatContext, useTaskContext } from "@/lib/hooks";

import { ChatSidePanel } from "../chat/ChatSidePanel";
import { ChatSessionDialog } from "../chat/ChatSessionDialog";
import { SessionSidePanel } from "../chat/SessionSidePanel";
import { ChatSessionDeleteDialog } from "../chat/ChatSessionDeleteDialog";
import type { ChatMessageListRef } from "../ui/chat/chat-message-list";

// Constants for sidepanel behavior
const COLLAPSED_SIZE = 4; // icon-only mode size
const PANEL_SIZES_CLOSED = {
    chatPanelSizes: {
        default: 50,
        min: 30,
        max: 96,
    },
    sidePanelSizes: {
        default: 50,
        min: 20,
        max: 70,
    },
};
const PANEL_SIZES_OPEN = {
    chatPanelSizes: { ...PANEL_SIZES_CLOSED.chatPanelSizes, min: 50 },
    sidePanelSizes: { ...PANEL_SIZES_CLOSED.sidePanelSizes, max: 50 },
};

export function ChatPage() {
    const {
        agents,
        sessionId,
        messages,
        setMessages,
        selectedAgentName,
        setSelectedAgentName,
        isSidePanelCollapsed,
        setIsSidePanelCollapsed,
        openSidePanelTab,
        setTaskIdInSidePanel,
        isResponding,
        latestStatusText,
        sessionToDelete,
        closeSessionDeleteModal,
        confirmSessionDelete,
        sessionName,
    } = useChatContext();
    const { isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream } = useTaskContext();
    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(true);
    const [isSidePanelTransitioning, setIsSidePanelTransitioning] = useState(false);
    const [isChatSessionDialogOpen, setChatSessionDialogOpen] = useState(false);

    // Refs for resizable panel state
    const chatMessageListRef = useRef<ChatMessageListRef>(null);
    const chatSidePanelRef = useRef<ImperativePanelHandle>(null);
    const lastExpandedSizeRef = useRef<number | null>(null);

    const { chatPanelSizes, sidePanelSizes } = useMemo(() => {
        return isSessionSidePanelCollapsed ? PANEL_SIZES_CLOSED : PANEL_SIZES_OPEN;
    }, [isSessionSidePanelCollapsed]);

    const handleSidepanelToggle = useCallback(
        (collapsed: boolean) => {
            setIsSidePanelTransitioning(true);
            if (chatSidePanelRef.current) {
                if (collapsed) {
                    chatSidePanelRef.current.resize(COLLAPSED_SIZE);
                } else {
                    const targetSize = lastExpandedSizeRef.current || sidePanelSizes.default;
                    chatSidePanelRef.current.resize(targetSize);
                }
            }
            setTimeout(() => setIsSidePanelTransitioning(false), 300);
        },
        [sidePanelSizes.default]
    );

    const handleSidepanelCollapse = useCallback(() => {
        setIsSidePanelCollapsed(true);
    }, [setIsSidePanelCollapsed]);

    const handleSidepanelExpand = useCallback(() => {
        setIsSidePanelCollapsed(false);
    }, [setIsSidePanelCollapsed]);

    const handleSidepanelResize = useCallback((size: number) => {
        // Only store the size if the panel is not collapsed
        if (size > COLLAPSED_SIZE + 1) {
            lastExpandedSizeRef.current = size;
        }
    }, []);

    const handleSessionSidePanelToggle = useCallback(() => {
        setIsSessionSidePanelCollapsed(!isSessionSidePanelCollapsed);
    }, [isSessionSidePanelCollapsed]);

    useEffect(() => {
        if (chatSidePanelRef.current && isSidePanelCollapsed) {
            chatSidePanelRef.current.resize(COLLAPSED_SIZE);
        }

        const handleExpandSidePanel = () => {
            if (chatSidePanelRef.current && isSidePanelCollapsed) {
                // Set transitioning state to enable smooth animation
                setIsSidePanelTransitioning(true);

                // Expand the panel to the last expanded size or default size
                const targetSize = lastExpandedSizeRef.current || sidePanelSizes.default;
                chatSidePanelRef.current.resize(targetSize);

                setIsSidePanelCollapsed(false);

                // Reset transitioning state after animation completes
                setTimeout(() => setIsSidePanelTransitioning(false), 300);
            }
        };

        window.addEventListener("expand-side-panel", handleExpandSidePanel);
        return () => {
            window.removeEventListener("expand-side-panel", handleExpandSidePanel);
        };
    }, [isSidePanelCollapsed, setIsSidePanelCollapsed, sidePanelSizes.default]);

    useEffect(() => {
        if (!selectedAgentName && agents.length > 0) {
            const orchestratorAgent = agents.find(agent => agent.name === "OrchestratorAgent");
            const agentName = orchestratorAgent ? orchestratorAgent.name : agents[0].name;

            setSelectedAgentName(agentName);

            const selectedAgent = agents.find(agent => agent.name === agentName);
            const displayedText = selectedAgent?.displayName ? `Hi! I'm the ${selectedAgent?.displayName} Agent. How can I help?` : `Hi! I'm ${agentName}. How can I help?`;

            setMessages(prev => {
                const filteredMessages = prev.filter(msg => !msg.isStatusBubble);
                return [
                    ...filteredMessages,
                    {
                        role: "agent",
                        kind: "message",
                        messageId: `welcome-${Date.now()}`,
                        parts: [{ kind: "text", text: displayedText }],
                        isUser: false,
                        isComplete: true,
                        metadata: { sessionId, lastProcessedEventSequence: 0 },
                    },
                ];
            });
        }
    }, [agents, selectedAgentName, sessionId, setMessages, setSelectedAgentName]);

    const lastMessageIndexByTaskId = useMemo(() => {
        const map = new Map<string, number>();
        messages.forEach((message, index) => {
            if (message.taskId) {
                map.set(message.taskId, index);
            }
        });
        return map;
    }, [messages]);

    const loadingMessage = useMemo(() => {
        return messages.find(message => message.isStatusBubble);
    }, [messages]);

    const backendStatusText = useMemo(() => {
        if (!loadingMessage || !loadingMessage.parts) return null;
        const textPart = loadingMessage.parts.find(p => p.kind === "text") as TextPart | undefined;
        return textPart?.text || null;
    }, [loadingMessage]);

    const handleViewProgressClick = useMemo(() => {
        if (!loadingMessage?.taskId) return undefined;

        return () => {
            setTaskIdInSidePanel(loadingMessage.taskId!);
            openSidePanelTab("workflow");
        };
    }, [loadingMessage?.taskId, setTaskIdInSidePanel, openSidePanelTab]);

    // Handle window focus to reconnect when user returns to chat page
    useEffect(() => {
        const handleWindowFocus = () => {
            // Only attempt reconnection if we're disconnected and have an error
            if (!isTaskMonitorConnected && !isTaskMonitorConnecting && taskMonitorSseError) {
                console.log("ChatPage: Window focused while disconnected, attempting reconnection...");
                connectTaskMonitorStream();
            }
        };

        window.addEventListener("focus", handleWindowFocus);

        return () => {
            window.removeEventListener("focus", handleWindowFocus);
        };
    }, [isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream]);

    return (
        <div className="relative flex h-screen w-full flex-col overflow-hidden">
            <div className={`absolute top-0 left-0 z-20 h-screen transition-transform duration-300 ${isSessionSidePanelCollapsed ? "-translate-x-full" : "translate-x-0"}`}>
                <SessionSidePanel onToggle={handleSessionSidePanelToggle} />
            </div>
            <div className={`transition-all duration-300 ${isSessionSidePanelCollapsed ? "ml-0" : "ml-100"}`}>
                <Header
                    title={sessionName || "New Chat"}
                    leadingAction={
                        isSessionSidePanelCollapsed ? (
                            <div className="flex items-center gap-2">
                                <Button variant="ghost" onClick={handleSessionSidePanelToggle} className="h-10 w-10 p-0" tooltip="Show Sessions Panel">
                                    <PanelLeftIcon className="size-5" />
                                </Button>
                                <div className="h-6 w-px bg-gray-300 dark:bg-gray-600"></div>
                                <Button variant="ghost" onClick={() => setChatSessionDialogOpen(true)} className="h-10 w-10 p-0" tooltip="Start New Chat Session">
                                    <Edit className="size-5" />
                                </Button>
                            </div>
                        ) : null
                    }
                />
            </div>
            <div className="flex min-h-0 flex-1">
                <div className={`min-h-0 flex-1 overflow-x-auto transition-all duration-300 ${isSessionSidePanelCollapsed ? "ml-0" : "ml-100"}`}>
                    <ResizablePanelGroup direction="horizontal" autoSaveId="chat-side-panel" className="h-full">
                        <ResizablePanel defaultSize={chatPanelSizes.default} minSize={chatPanelSizes.min} maxSize={chatPanelSizes.max} id="chat-panel">
                            <div className="flex h-full w-full flex-col py-6">
                                <ChatMessageList className="text-base" ref={chatMessageListRef}>
                                    {messages.map((message, index) => {
                                        const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                                        return <ChatMessage message={message} key={`${message.metadata?.sessionId || "session"}-${index}-${message.isUser ? "received" : "sent"}`} isLastWithTaskId={isLastWithTaskId} />;
                                    })}
                                </ChatMessageList>
                                <div style={CHAT_STYLES}>
                                    {isResponding && <LoadingMessageRow statusText={(backendStatusText || latestStatusText.current) ?? undefined} onViewWorkflow={handleViewProgressClick} />}
                                    <ChatInputArea agents={agents} scrollToBottom={chatMessageListRef.current?.scrollToBottom} />
                                </div>
                            </div>
                        </ResizablePanel>
                        <ResizableHandle />
                        <ResizablePanel
                            ref={chatSidePanelRef}
                            defaultSize={sidePanelSizes.default}
                            minSize={sidePanelSizes.min}
                            maxSize={sidePanelSizes.max}
                            collapsedSize={COLLAPSED_SIZE}
                            collapsible={true}
                            onCollapse={handleSidepanelCollapse}
                            onExpand={handleSidepanelExpand}
                            onResize={handleSidepanelResize}
                            id="chat-side-panel"
                            className={isSidePanelTransitioning ? "transition-all duration-300 ease-in-out" : ""}
                        >
                            <div className="h-full">
                                <ChatSidePanel onCollapsedToggle={handleSidepanelToggle} isSidePanelCollapsed={isSidePanelCollapsed} setIsSidePanelCollapsed={setIsSidePanelCollapsed} isSidePanelTransitioning={isSidePanelTransitioning} />
                            </div>
                        </ResizablePanel>
                    </ResizablePanelGroup>
                </div>
            </div>
            <ChatSessionDialog isOpen={isChatSessionDialogOpen} onClose={() => setChatSessionDialogOpen(false)} />
            <ChatSessionDeleteDialog isOpen={!!sessionToDelete} onClose={closeSessionDeleteModal} onConfirm={confirmSessionDelete} sessionName={sessionToDelete?.name || `Session ${sessionToDelete?.id.substring(0, 8)}`} />
        </div>
    );
}
