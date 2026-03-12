import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PanelLeftIcon, Loader2, GitFork } from "lucide-react";
import type { ImperativePanelHandle } from "react-resizable-panels";

import { Header } from "@/lib/components/header";
import { useChatContext, useTaskContext, useThemeContext, useTitleAnimation, useConfigContext } from "@/lib/hooks";
import { useProjectContext } from "@/lib/providers";
import type { TextPart } from "@/lib/types";
import type { CollaborativeUser } from "@/lib/types/collaboration";
import { ChatInputArea, ChatMessage, ChatSessionDialog, ChatSessionDeleteDialog, ChatSidePanel, LoadingMessageRow, ProjectBadge, SessionSidePanel, UserPresenceAvatars, ShareNotificationMessage } from "@/lib/components/chat";
import { Button, ChatMessageList, CHAT_STYLES, ResizablePanelGroup, ResizablePanel, ResizableHandle, Spinner, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";
import { ShareButton } from "@/lib/components/share/ShareButton";
import { getShareLinkForSession, getShareUsers } from "@/lib/api/shareApi";
import { api } from "@/lib/api";
import { useLocation, useNavigate } from "react-router-dom";

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
    const location = useLocation();
    const navigate = useNavigate();
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
        isCollaborativeSession,
        currentUserEmail,
        sessionOwnerName,
        sessionOwnerEmail,
        handleSwitchSession,
    } = useChatContext();
    const { isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream } = useTaskContext();
    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(true);
    const [isSidePanelTransitioning, setIsSidePanelTransitioning] = useState(false);
    const [isForkingChat, setIsForkingChat] = useState(false);
    // Share notification data: each entry represents a share action (user added at a specific time)
    const [shareNotifications, setShareNotifications] = useState<
        Array<
            | { variant: "shared-with-users"; names: string[]; timestamp: number; accessLevel: "viewer" | "editor" }
            | { variant: "role-changed"; names: string[]; timestamp: number; fromAccessLevel: "viewer" | "editor"; toAccessLevel: "viewer" | "editor" }
        >
    >([]);
    const [sharedEditorUsers, setSharedEditorUsers] = useState<CollaborativeUser[]>([]);
    const [shareVersion, setShareVersion] = useState(0);

    // Listen for share-updated events from ShareDialog to refresh notifications
    useEffect(() => {
        const handleShareUpdated = (event: Event) => {
            const detail = (event as CustomEvent).detail;
            if (detail?.sessionId === sessionId) {
                setShareVersion(v => v + 1);
            }
        };
        window.addEventListener("share-updated", handleShareUpdated);
        return () => window.removeEventListener("share-updated", handleShareUpdated);
    }, [sessionId]);

    // Fork collaborative chat into user's own session
    const handleForkCollaborativeChat = useCallback(async () => {
        if (!sessionId || isForkingChat) return;
        setIsForkingChat(true);
        try {
            // Use the sessions API to create a copy
            const response = await api.webui.post(`/api/v1/sessions/${sessionId}/fork`);
            const newSessionId = response?.session_id || response?.data?.session_id;
            if (newSessionId) {
                // Refresh the session list to show the new forked session
                window.dispatchEvent(new CustomEvent("new-chat-session"));
                handleSwitchSession(newSessionId);
                navigate("/chat");
            }
        } catch (error) {
            console.error("Failed to fork chat:", error);
        } finally {
            setIsForkingChat(false);
        }
    }, [sessionId, isForkingChat, handleSwitchSession, navigate]);

    // Refs for resizable panel state
    const chatMessageListRef = useRef<ChatMessageListRef>(null);
    const chatSidePanelRef = useRef<ImperativePanelHandle>(null);
    const lastExpandedSizeRef = useRef<number | null>(null);

    // Track which session started the response to avoid pulsing when switching to old sessions
    // We use a Map to track task ID -> session ID relationships, plus a version counter to trigger re-renders
    const taskToSessionRef = useRef<Map<string, string>>(new Map());
    const [taskMapVersion, setTaskMapVersion] = useState(0);

    // Fetch share link info and share users for the current session (to show share notifications for owner)
    useEffect(() => {
        if (!sessionId || isCollaborativeSession) {
            setShareNotifications([]);
            setSharedEditorUsers([]);
            return;
        }
        // Only fetch for owner's sessions (non-collaborative)
        getShareLinkForSession(sessionId)
            .then(async link => {
                if (link) {
                    try {
                        const usersResponse = await getShareUsers(link.share_id);
                        const users = usersResponse.users || [];
                        if (users.length === 0) {
                            setShareNotifications([]);
                            return;
                        }
                        // Build notifications: for each user, emit the original share event
                        // and, if access was changed, a separate role-changed event.
                        type ShareNotif =
                            | { variant: "shared-with-users"; names: string[]; timestamp: number; accessLevel: "viewer" | "editor" }
                            | { variant: "role-changed"; names: string[]; timestamp: number; fromAccessLevel: "viewer" | "editor"; toAccessLevel: "viewer" | "editor" };

                        const toDisplayName = (email: string) => {
                            const emailName = email.split("@")[0] || email;
                            return emailName.replace(/[._-]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
                        };

                        // Group original share events by (timestamp, accessLevel)
                        const origGroupKey = (ts: number, level: string) => `orig:${ts}:${level}`;
                        const origGroupMap = new Map<string, ShareNotif & { variant: "shared-with-users" }>();

                        // Group role-changed events by (timestamp, from, to)
                        const changeGroupKey = (ts: number, from: string, to: string) => `change:${ts}:${from}:${to}`;
                        const changeGroupMap = new Map<string, ShareNotif & { variant: "role-changed" }>();

                        for (const user of users) {
                            const displayName = toDisplayName(user.user_email);

                            if (user.original_access_level && user.original_added_at) {
                                // User had their access changed — emit original share event
                                const origLevel = user.original_access_level === "RESOURCE_EDITOR" ? ("editor" as const) : ("viewer" as const);
                                const oKey = origGroupKey(user.original_added_at, user.original_access_level);
                                if (!origGroupMap.has(oKey)) {
                                    origGroupMap.set(oKey, { variant: "shared-with-users", timestamp: user.original_added_at, names: [], accessLevel: origLevel });
                                }
                                origGroupMap.get(oKey)!.names.push(displayName);

                                // Emit role-changed event at the current added_at time
                                const newLevel = user.access_level === "RESOURCE_EDITOR" ? ("editor" as const) : ("viewer" as const);
                                const cKey = changeGroupKey(user.added_at, user.original_access_level, user.access_level);
                                if (!changeGroupMap.has(cKey)) {
                                    changeGroupMap.set(cKey, { variant: "role-changed", timestamp: user.added_at, names: [], fromAccessLevel: origLevel, toAccessLevel: newLevel });
                                }
                                changeGroupMap.get(cKey)!.names.push(displayName);
                            } else {
                                // Normal share — no access change history
                                const level = user.access_level === "RESOURCE_EDITOR" ? ("editor" as const) : ("viewer" as const);
                                const oKey = origGroupKey(user.added_at, user.access_level);
                                if (!origGroupMap.has(oKey)) {
                                    origGroupMap.set(oKey, { variant: "shared-with-users", timestamp: user.added_at, names: [], accessLevel: level });
                                }
                                origGroupMap.get(oKey)!.names.push(displayName);
                            }
                        }

                        const notifications: ShareNotif[] = [...Array.from(origGroupMap.values()), ...Array.from(changeGroupMap.values())].sort((a, b) => a.timestamp - b.timestamp);
                        setShareNotifications(notifications);
                        // Build editor users list for presence avatars (owner's view)
                        const editorUsers: CollaborativeUser[] = users
                            .filter(u => u.access_level === "RESOURCE_EDITOR")
                            .map(u => {
                                const emailName = u.user_email.split("@")[0] || u.user_email;
                                const name = emailName.replace(/[._-]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());
                                return {
                                    id: u.user_email.toLowerCase(),
                                    name,
                                    email: u.user_email,
                                    role: "collaborator" as const,
                                    isOnline: true,
                                };
                            });
                        setSharedEditorUsers(editorUsers);
                    } catch {
                        setShareNotifications([]);
                    }
                } else {
                    setShareNotifications([]);
                    setSharedEditorUsers([]);
                }
            })
            .catch(() => {
                setShareNotifications([]);
                setSharedEditorUsers([]);
            });
    }, [sessionId, isCollaborativeSession, shareVersion]);

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

        // Always include the session owner (from backend-provided info)
        // This ensures the owner appears even if their old messages don't have senderEmail
        if (sessionOwnerEmail) {
            userMap.set(sessionOwnerEmail.toLowerCase(), {
                id: sessionOwnerEmail.toLowerCase(),
                name: sessionOwnerName || sessionOwnerEmail,
                email: sessionOwnerEmail,
                role: "collaborator",
                isOnline: true,
            });
        }

        // Add users from message sender info (may update owner entry with better name)
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

    // Compute where each share notification should be inserted in the message list.
    // Each notification goes AFTER the last message whose createdTime <= notification.timestamp.
    const shareNotificationInsertions = useMemo(() => {
        if (shareNotifications.length === 0 || isCollaborativeSession || messages.length === 0) {
            return [];
        }

        return shareNotifications.map(notification => {
            // Find the last message with createdTime <= notification.timestamp
            let insertAfterIndex = -1;
            for (let i = messages.length - 1; i >= 0; i--) {
                const msg = messages[i];
                if (msg.createdTime && msg.createdTime <= notification.timestamp) {
                    insertAfterIndex = i;
                    break;
                }
            }
            // If no message has createdTime <= notification.timestamp, place after last message
            if (insertAfterIndex === -1) {
                insertAfterIndex = messages.length - 1;
            }
            return {
                ...notification,
                insertAfterIndex,
            };
        });
    }, [shareNotifications, isCollaborativeSession, messages]);

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

    // Handle opening sessions panel from navigation state
    useEffect(() => {
        const state = location.state as { openSessionsPanel?: boolean } | null;
        if (state?.openSessionsPanel) {
            setIsSessionSidePanelCollapsed(false);
            // Clear the state to prevent reopening on browser back button
            navigate(location.pathname, { replace: true, state: {} });
        }
    }, [location.state, location.pathname, navigate]);

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
                    buttons={
                        sessionId
                            ? [
                                  // Show presence avatars for both editors (collaborativeUsers) and owners (sharedEditorUsers)
                                  ...(isCollaborativeSession && collaborativeUsers.length > 0
                                      ? [<UserPresenceAvatars key="presence-avatars" users={collaborativeUsers} currentUserId={currentUserEmail} />]
                                      : sharedEditorUsers.length > 0
                                        ? [<UserPresenceAvatars key="presence-avatars" users={sharedEditorUsers} />]
                                        : []),
                                  // For editors: show "Create Personal Copy" (fork) button instead of Share
                                  ...(isCollaborativeSession
                                      ? [
                                            <Button key="fork-button" variant="outline" size="sm" onClick={handleForkCollaborativeChat} disabled={isForkingChat} title="Save a personal copy of this conversation">
                                                {isForkingChat ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitFork className="mr-2 h-4 w-4" />}
                                                Save as My Chat
                                            </Button>,
                                        ]
                                      : [<ShareButton key="share-button" sessionId={sessionId} sessionTitle={sessionName || "New Chat"} />]),
                              ]
                            : undefined
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
                                                {/* Show share notification for editor at the start */}
                                                {isCollaborativeSession && messages.length > 0 && (
                                                    <ShareNotificationMessage variant="shared-with-users" sharedBy={sessionOwnerName || "Someone"} sharedWith={["you"]} accessLevel="editor" timestamp={Date.now()} />
                                                )}
                                                {messages.map((message, index) => {
                                                    const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                                                    const messageKey = message.metadata?.messageId || `temp-${index}`;
                                                    const isLastMessage = index === messages.length - 1;
                                                    const shouldStream = isLastMessage && isResponding && !message.isUser;

                                                    // Check if any share notifications should appear AFTER this message
                                                    const notificationsAfterThis = shareNotificationInsertions.filter(n => n.insertAfterIndex === index);

                                                    return (
                                                        <div key={messageKey}>
                                                            {/* ChatMessage handles collaborative attribution internally */}
                                                            <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} isStreaming={shouldStream} />
                                                            {/* Render share notifications that belong after this message */}
                                                            {notificationsAfterThis.map((notification, nIdx) =>
                                                                notification.variant === "role-changed" ? (
                                                                    <ShareNotificationMessage
                                                                        key={`share-notif-${notification.timestamp}-${nIdx}`}
                                                                        variant="role-changed"
                                                                        sharedWith={notification.names}
                                                                        fromAccessLevel={notification.fromAccessLevel}
                                                                        toAccessLevel={notification.toAccessLevel}
                                                                        timestamp={notification.timestamp}
                                                                    />
                                                                ) : (
                                                                    <ShareNotificationMessage
                                                                        key={`share-notif-${notification.timestamp}-${nIdx}`}
                                                                        variant="shared-with-users"
                                                                        sharedWith={notification.names}
                                                                        accessLevel={notification.accessLevel}
                                                                        timestamp={notification.timestamp}
                                                                    />
                                                                )
                                                            )}
                                                        </div>
                                                    );
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
