import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PanelLeftIcon } from "lucide-react";
import type { ImperativePanelHandle } from "react-resizable-panels";

import { Header } from "@/lib/components/header";
import { useChatContext, useTaskContext, useThemeContext, useTitleAnimation, useConfigContext } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import type { TextPart } from "@/lib/types";
import { ChatInputArea, ChatMessage, ChatSessionDialog, ChatSessionDeleteDialog, ChatSidePanel, LoadingMessageRow, ProjectBadge, SessionSidePanel } from "@/lib/components/chat";
import { Button, ChatMessageList, CHAT_STYLES, ResizablePanelGroup, ResizablePanel, ResizableHandle, Spinner, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";

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
    const { activeProject } = useProjectContext();
    const { currentTheme } = useThemeContext();
    const { autoTitleGenerationEnabled } = useConfigContext();
    const {
        agents,
        sessionId,
        sessionName,
        messages,
        isSidePanelCollapsed,
        setIsSidePanelCollapsed,
        openSidePanelTab,
        setTaskIdInSidePanel,
        isResponding,
        latestStatusText,
        isLoadingSession,
        sessionToDelete,
        closeSessionDeleteModal,
        confirmSessionDelete,
        currentTaskId,
    } = useChatContext();
    const { isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream } = useTaskContext();
    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(true);
    const [isSidePanelTransitioning, setIsSidePanelTransitioning] = useState(false);

    // Refs for resizable panel state
    const chatMessageListRef = useRef<ChatMessageListRef>(null);
    const chatSidePanelRef = useRef<ImperativePanelHandle>(null);
    const lastExpandedSizeRef = useRef<number | null>(null);

    // Track which session started the response to avoid pulsing when switching to old sessions
    // We use a Map to track task ID -> session ID relationships, plus a version counter to trigger re-renders
    const taskToSessionRef = useRef<Map<string, string>>(new Map());
    const [taskMapVersion, setTaskMapVersion] = useState(0);

    // When a new task starts, remember which session it belongs to
    // Don't rely on currentTaskId changes during session switches
    useEffect(() => {
        if (currentTaskId && !taskToSessionRef.current.has(currentTaskId)) {
            // This is a genuinely new task - capture which session it started in
            taskToSessionRef.current.set(currentTaskId, sessionId);
            // Trigger a re-render so respondingSessionId useMemo recomputes
            setTaskMapVersion(v => v + 1);
        }
    }, [currentTaskId, sessionId]);

    // Derive respondingSessionId from the current task's owning session
    const respondingSessionId = useMemo(() => {
        if (!currentTaskId) return null;
        return taskToSessionRef.current.get(currentTaskId) || null;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentTaskId, taskMapVersion]);

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

    const breadcrumbs = undefined;

    // Determine the page title with pulse/fade effect
    const rawPageTitle = useMemo(() => {
        return sessionName || "New Chat";
    }, [sessionName]);

    const { text: pageTitle, isAnimating: isTitleAnimating, isGenerating: isTitleGenerating } = useTitleAnimation(rawPageTitle, sessionId);

    const isWaitingForTitle = useMemo(() => {
        if (!autoTitleGenerationEnabled) {
            return false;
        }
        const isNewChat = !sessionName || sessionName === "New Chat";
        // Only pulse if THIS session started the response (prevents pulsing when viewing old sessions)
        const isThisSessionResponding = respondingSessionId === sessionId;
        return (isNewChat && isThisSessionResponding) || isTitleGenerating;
    }, [sessionName, sessionId, respondingSessionId, isTitleGenerating, autoTitleGenerationEnabled]);

    // Determine the appropriate animation class
    const titleAnimationClass = useMemo(() => {
        if (!autoTitleGenerationEnabled) {
            return "opacity-100"; // No animation when disabled
        }
        if (isWaitingForTitle) {
            return "animate-pulse-slow";
        }
        if (isTitleAnimating) {
            return "animate-pulse opacity-50";
        }
        return "opacity-100";
    }, [isWaitingForTitle, isTitleAnimating, autoTitleGenerationEnabled]);

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
        // Use currentTaskId directly instead of relying on loadingMessage
        if (!currentTaskId) return undefined;

        return () => {
            setTaskIdInSidePanel(currentTaskId);
            openSidePanelTab("activity");
        };
    }, [currentTaskId, setTaskIdInSidePanel, openSidePanelTab]);

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
                    title={
                        <div className="flex items-center gap-3">
                            <Tooltip delayDuration={300}>
                                <TooltipTrigger className={`font-inherit max-w-[400px] cursor-default truncate border-0 bg-transparent p-0 text-left text-inherit transition-opacity duration-300 hover:bg-transparent ${titleAnimationClass}`}>
                                    {pageTitle}
                                </TooltipTrigger>
                                <TooltipContent side="bottom">
                                    <p>{pageTitle}</p>
                                </TooltipContent>
                            </Tooltip>
                            {activeProject && <ProjectBadge text={activeProject.name} className="max-w-[200px]" />}
                        </div>
                    }
                    breadcrumbs={breadcrumbs}
                    leadingAction={
                        isSessionSidePanelCollapsed ? (
                            <div className="flex items-center gap-2">
                                <Button data-testid="showSessionsPanel" variant="ghost" onClick={handleSessionSidePanelToggle} className="h-10 w-10 p-0" tooltip="Show Chat Sessions">
                                    <PanelLeftIcon className="size-5" />
                                </Button>
                                <div className="h-6 border-r"></div>

                                <ChatSessionDialog />
                            </div>
                        ) : null
                    }
                />
            </div>
            <div className="flex min-h-0 flex-1">
                <div className={`min-h-0 flex-1 overflow-x-auto transition-all duration-300 ${isSessionSidePanelCollapsed ? "ml-0" : "ml-100"}`}>
                    <ResizablePanelGroup direction="horizontal" autoSaveId="chat-side-panel" className="h-full">
                        <ResizablePanel
                            defaultSize={chatPanelSizes.default}
                            minSize={chatPanelSizes.min}
                            maxSize={chatPanelSizes.max}
                            id="chat-panel"
                            style={{ backgroundColor: currentTheme === "dark" ? "var(--color-background-w100)" : "var(--color-background-w20)" }}
                        >
                            <div className="flex h-full w-full flex-col">
                                <div className="flex min-h-0 flex-1 flex-col py-6">
                                    {isLoadingSession ? (
                                        <div className="flex h-full items-center justify-center">
                                            <Spinner size="medium" variant="primary">
                                                <p className="text-muted-foreground mt-4 text-sm">Loading session...</p>
                                            </Spinner>
                                        </div>
                                    ) : (
                                        <>
                                            <ChatMessageList className="text-base" ref={chatMessageListRef}>
                                                {messages.map((message, index) => {
                                                    const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                                                    const messageKey = message.metadata?.messageId || `temp-${index}`;
                                                    const isLastMessage = index === messages.length - 1;
                                                    const shouldStream = isLastMessage && isResponding && !message.isUser;
                                                    return <ChatMessage message={message} key={messageKey} isLastWithTaskId={isLastWithTaskId} isStreaming={shouldStream} />;
                                                })}
                                            </ChatMessageList>
                                            <div style={CHAT_STYLES}>
                                                {isResponding && <LoadingMessageRow statusText={(backendStatusText || latestStatusText.current) ?? undefined} onViewWorkflow={handleViewProgressClick} />}
                                                <ChatInputArea agents={agents} scrollToBottom={chatMessageListRef.current?.scrollToBottom} />
                                            </div>
                                        </>
                                    )}
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
            <ChatSessionDeleteDialog open={!!sessionToDelete} onCancel={closeSessionDeleteModal} onConfirm={confirmSessionDelete} sessionName={sessionToDelete?.name || ""} />
        </div>
    );
}
