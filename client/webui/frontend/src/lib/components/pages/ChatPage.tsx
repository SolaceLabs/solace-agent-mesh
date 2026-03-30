import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ArrowRightIcon, PanelLeftIcon, Loader2, GitFork } from "lucide-react";
import type { ImperativePanelHandle } from "react-resizable-panels";
import { useQueryClient } from "@tanstack/react-query";

import { Header } from "@/lib/components/header";
import { useChatContext, useTaskContext, useThemeContext, useTitleAnimation, useConfigContext, useUIMode, useIsChatSharingEnabled } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import type { CollaborativeUser } from "@/lib/types/collaboration";
import { ChatArea, ChatSessionDialog, ChatSessionDeleteDialog, ChatSidePanel, ProjectBadge, SessionSidePanel, UserPresenceAvatars } from "@/lib/components/chat";
import { Button, ResizablePanelGroup, ResizablePanel, ResizableHandle, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useShareLink, useShareUsers, forkSharedChat } from "@/lib/api/share";
import { useLocation, useNavigate } from "react-router-dom";
import { ShareButton } from "@/lib/components/share/ShareButton";
import { ShareDialog } from "@/lib/components/share/ShareDialog";

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
    const { isOnboardMode } = useUIMode();
    const queryClient = useQueryClient();
    const { activeProject } = useProjectContext();
    const { currentTheme } = useThemeContext();
    const { autoTitleGenerationEnabled, configWelcomeMessage } = useConfigContext();
    const chatSharingEnabled = useIsChatSharingEnabled();
    const location = useLocation();
    const navigate = useNavigate();
    const {
        sessionId,
        sessionName,
        messages,
        isSidePanelCollapsed,
        setIsSidePanelCollapsed,
        sessionToDelete,
        closeSessionDeleteModal,
        confirmSessionDelete,
        currentTaskId,
        isCollaborativeSession,
        currentUserEmail,
        sessionOwnerName,
        sessionOwnerEmail,
        handleSwitchSession,
        handleNewSession,
    } = useChatContext();
    const { isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream } = useTaskContext();
    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(true);
    const [isSidePanelTransitioning, setIsSidePanelTransitioning] = useState(false);
    const [isForkingChat, setIsForkingChat] = useState(false);
    const [isShareDialogOpen, setIsShareDialogOpen] = useState(false);
    const [sharedEditorUsers, setSharedEditorUsers] = useState<CollaborativeUser[]>([]);

    // Listen for share-updated events from ShareDialog to invalidate React Query cache
    useEffect(() => {
        const handleShareUpdated = () => {
            if (sessionId) {
                queryClient.invalidateQueries({ queryKey: ["shareLink", sessionId] });
                queryClient.invalidateQueries({ queryKey: ["shareUsers", sessionId] });
            }
        };
        window.addEventListener("share-updated", handleShareUpdated);
        return () => window.removeEventListener("share-updated", handleShareUpdated);
    }, [sessionId, queryClient]);

    // Track shared users for presence avatars (owner view)
    const { data: shareUsersData } = useShareUsers(sessionId || "");
    const { data: shareLinkData } = useShareLink(sessionId || "");

    // Update shared editor users for presence avatars
    useEffect(() => {
        if (!shareUsersData?.users || !shareLinkData) {
            setSharedEditorUsers([]);
            return;
        }
        const editors = shareUsersData.users
            .filter(u => u.accessLevel === "RESOURCE_EDITOR")
            .map(u => ({
                id: u.userEmail.toLowerCase(),
                name: u.userEmail,
                email: u.userEmail,
                role: "collaborator" as const,
                isOnline: true,
            }));
        setSharedEditorUsers(editors);
    }, [shareUsersData, shareLinkData]);

    // Refs for resizable panel state
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

    // Build collaborative users list from message sender info for presence avatars
    const collaborativeUsers = useMemo<CollaborativeUser[]>(() => {
        if (!isCollaborativeSession) return [];
        const userMap = new Map<string, CollaborativeUser>();

        if (sessionOwnerEmail) {
            userMap.set(sessionOwnerEmail.toLowerCase(), {
                id: sessionOwnerEmail.toLowerCase(),
                name: sessionOwnerName || sessionOwnerEmail,
                email: sessionOwnerEmail,
                role: "collaborator",
                isOnline: true,
            });
        }

        for (const msg of messages) {
            if (msg.isUser && msg.senderEmail && !userMap.has(msg.senderEmail.toLowerCase())) {
                userMap.set(msg.senderEmail.toLowerCase(), {
                    id: msg.senderEmail.toLowerCase(),
                    name: msg.senderDisplayName || msg.senderEmail,
                    email: msg.senderEmail,
                    role: "collaborator",
                    isOnline: true,
                });
            }
        }
        return Array.from(userMap.values());
    }, [isCollaborativeSession, messages, sessionOwnerEmail, sessionOwnerName]);

    // Fork collaborative chat: create a new session with the current messages
    const handleForkCollaborativeChat = useCallback(async () => {
        if (!sessionId) return;
        setIsForkingChat(true);
        try {
            const result = await forkSharedChat(sessionId);
            if (result?.sessionId) {
                handleSwitchSession(result.sessionId);
            }
        } catch (error) {
            console.error("Failed to fork collaborative chat:", error);
        } finally {
            setIsForkingChat(false);
        }
    }, [sessionId, handleSwitchSession]);

    // Handle navigation state (e.g., from SharedChatViewPage returning to /chat)
    useEffect(() => {
        const state = location.state as {
            openSessionsPanel?: boolean;
            switchToSession?: string;
            newChat?: boolean;
        } | null;
        if (!state) return;

        if (state.openSessionsPanel) {
            setIsSessionSidePanelCollapsed(false);
        }
        if (state.switchToSession) {
            handleSwitchSession(state.switchToSession);
        } else if (state.newChat) {
            handleNewSession();
        }
        // Clear the state to prevent re-triggering on browser back button
        navigate(location.pathname, { replace: true, state: {} });
    }, [location.state, location.pathname, navigate, handleSwitchSession, handleNewSession]);

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
            {!isOnboardMode && (
                <div className={`absolute top-0 left-0 z-20 h-screen transition-transform duration-300 ${isSessionSidePanelCollapsed ? "-translate-x-full" : "translate-x-0"}`}>
                    <SessionSidePanel onToggle={handleSessionSidePanelToggle} />
                </div>
            )}
            <div className={`transition-all duration-300 ${!isOnboardMode && !isSessionSidePanelCollapsed ? "ml-100" : "ml-0"}`}>
                <Header
                    title={
                        isOnboardMode ? (
                            <span className="text-inherit">Getting to know SAM</span>
                        ) : (
                            <div className="flex items-center gap-3">
                                <Tooltip delayDuration={300}>
                                    <TooltipTrigger className={`font-inherit max-w-[400px] cursor-default truncate border-0 bg-transparent p-0 text-left text-inherit transition-opacity duration-300 hover:bg-transparent ${titleAnimationClass}`}>
                                        {pageTitle}
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">
                                        <p>{pageTitle}</p>
                                    </TooltipContent>
                                </Tooltip>
                                {activeProject && <ProjectBadge text={activeProject.name} className="max-w-[360px]" />}
                            </div>
                        )
                    }
                    breadcrumbs={isOnboardMode ? undefined : breadcrumbs}
                    leadingAction={
                        isOnboardMode ? null :
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
                    buttons={isOnboardMode ? [
                        <Button
                            key="continue"
                            variant="default"
                            size="sm"
                            onClick={() => {
                                window.location.hash = "#/chat";
                                window.location.reload();
                            }}
                        >
                            Continue to full experience
                            <ArrowRightIcon className="ml-1 size-4" />
                        </Button>
                    ] : sessionId && chatSharingEnabled
                            ? [
                                  // Show presence avatars for both editors (collaborativeUsers) and owners (sharedEditorUsers)
                                  ...(isCollaborativeSession && collaborativeUsers.length > 0
                                      ? [<UserPresenceAvatars key="presence-avatars" users={collaborativeUsers} currentUserId={currentUserEmail} />]
                                      : sharedEditorUsers.length > 0
                                        ? [<UserPresenceAvatars key="presence-avatars" users={sharedEditorUsers} />]
                                        : []),
                                  // For editors: show "Continue in New Chat" (fork) button instead of Share
                                  ...(isCollaborativeSession
                                      ? [
                                            <Button key="fork-button" variant="outline" size="sm" onClick={handleForkCollaborativeChat} disabled={isForkingChat} title="Save a personal copy of this conversation">
                                                {isForkingChat ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitFork className="mr-2 h-4 w-4" />}
                                                Continue in New Chat
                                            </Button>,
                                        ]
                                      : [<ShareButton key="share-button" sessionId={sessionId} sessionTitle={sessionName || "New Chat"} onClick={() => setIsShareDialogOpen(true)} />]),
                              ]
                            : undefined
                    }
                />
            </div>
            <div className="flex min-h-0 flex-1">
                <div className={`min-h-0 flex-1 overflow-x-auto transition-all duration-300 ${!isOnboardMode && !isSessionSidePanelCollapsed ? "ml-100" : "ml-0"}`}>
                    {isOnboardMode ? (
                        /* Onboard mode: full-width chat panel, no side panel */
                        <div className="h-full" style={{ backgroundColor: currentTheme === "dark" ? "var(--color-background-w100)" : "var(--color-background-w20)" }}>
                            <ChatArea welcomeOverride={configWelcomeMessage ? { welcome_message: configWelcomeMessage } : undefined} />
                        </div>
                    ) : (
                        /* Normal mode: resizable chat + side panel */
                        <ResizablePanelGroup direction="horizontal" autoSaveId="chat-side-panel" className="h-full">
                            <ResizablePanel
                                defaultSize={chatPanelSizes.default}
                                minSize={chatPanelSizes.min}
                                maxSize={chatPanelSizes.max}
                                id="chat-panel"
                                style={{ backgroundColor: currentTheme === "dark" ? "var(--color-background-w100)" : "var(--color-background-w20)" }}
                            >
                                <ChatArea />
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
                    )}
                </div>
            </div>
            <ChatSessionDeleteDialog open={!!sessionToDelete} onCancel={closeSessionDeleteModal} onConfirm={confirmSessionDelete} sessionName={sessionToDelete?.name || ""} />
            {sessionId && <ShareDialog sessionId={sessionId} sessionTitle={sessionName || "New Chat"} open={isShareDialogOpen} onOpenChange={setIsShareDialogOpen} />}
        </div>
    );
}
